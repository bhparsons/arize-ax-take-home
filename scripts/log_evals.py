"""Log LLM-as-judge evaluations directly onto live AX spans (index-independent).

WHY THIS EXISTS
---------------
The online-eval *Task* path (ax tasks create-evaluation + trigger-run) deploys
three evaluators into the AX Evaluators tab, but on this trial space every run
skips 100% of spans (status=FAILED, 0 errors) — even a no-filter task over
3-day-old traces — because the project's online-eval index isn't returning rows.

This script bypasses that index entirely: it exports the spans, runs the SAME
three reference-free rubrics through the OpenRouter Claude judge, and writes the
scores back onto each span with client.spans.update_evaluations(). The result is
groundedness / relevance / retrieval-relevance columns visible on the traces in
the AX UI — the outcome the online Task was meant to produce.

RUN IT WITH THE ax CLI's PYTHON (it has the full arize SDK v8.35.0 + requests):
    ~/.local/share/uv/tools/arize-ax-cli/bin/python scripts/log_evals.py
Requires OPENROUTER_API_KEY in the environment (or .env).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

import requests

from ax.core.client_factory import make_client  # authenticated via the active ax profile

SPACE_ID = "U3BhY2U6NDY1MjM6Q1ZDYg=="
PROJECT = "dev-research-assistant"
JUDGE_MODEL = "anthropic/claude-sonnet-4"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _load_openrouter_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:  # fall back to .env
        for line in open(os.path.join(os.path.dirname(__file__), "..", ".env")):
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip()
                break
    if not key:
        raise SystemExit("OPENROUTER_API_KEY not set (env or .env).")
    return key


KEY = _load_openrouter_key()


def judge(rubric: str, labels: tuple[str, str]) -> tuple[str, float, str]:
    """Ask the judge to pick one of two labels and score 1/0. Robust to non-JSON."""
    sys_msg = (
        "You are a strict evaluator. Reply ONLY with JSON: "
        f'{{"label": one of {list(labels)}, "score": 1 or 0, "explanation": <string>}}. '
        f"Use score 1 for {labels[0]!r} and 0 for {labels[1]!r}."
    )
    resp = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        json={
            "model": JUDGE_MODEL,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": rubric},
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"] or ""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            label = str(obj.get("label", "")).strip()
            if label not in labels:  # snap to nearest valid label
                label = labels[0] if str(obj.get("score", 0)) in ("1", "1.0") else labels[1]
            return label, float(obj.get("score", 1.0 if label == labels[0] else 0.0)), str(obj.get("explanation", ""))[:900]
        except Exception:
            pass
    # last resort: infer from text
    lab = labels[0] if labels[0] in text.lower() else labels[1]
    return lab, (1.0 if lab == labels[0] else 0.0), text[:900]


def _docs_to_text(cell) -> str:
    """retrieval.documents is a list of {document.content,...}; flatten to text."""
    if cell is None:
        return ""
    if isinstance(cell, str):
        return cell
    try:
        parts = []
        for d in cell:
            if isinstance(d, dict):
                parts.append(str(d.get("document.content") or d.get("content") or d))
            else:
                parts.append(str(d))
        return "\n\n---\n\n".join(parts)
    except TypeError:
        return str(cell)


# --- the three rubrics (reference-free; mirror the deployed evaluators) -------
def eval_retrieval_relevance(row):
    rubric = (
        "Are the retrieved documents relevant to the developer's question?\n\n"
        f"QUESTION:\n{row['attributes.input.value']}\n\n"
        f"RETRIEVED DOCUMENTS:\n{_docs_to_text(row['attributes.retrieval.documents'])}\n\n"
        "'relevant' if at least one document helps answer it; 'irrelevant' if off-topic/empty."
    )
    return ("retrieval_relevance", *judge(rubric, ("relevant", "irrelevant")))


def eval_answer_relevance(row):
    rubric = (
        "Does the ANSWER address the QUESTION?\n\n"
        f"QUESTION:\n{row['attributes.input.value']}\n\n"
        f"ANSWER:\n{row['attributes.output.value']}\n\n"
        "'relevant' if on-topic and responsive (incl. correctly saying the docs don't cover it); "
        "'irrelevant' if off-topic or evasive."
    )
    return ("answer_relevance", *judge(rubric, ("relevant", "irrelevant")))


def eval_groundedness(row):
    rubric = (
        "Is every factual claim in the ANSWER supported by the RETRIEVED CONTEXT?\n\n"
        f"RETRIEVED CONTEXT:\n{row['attributes.retrieved_context']}\n\n"
        f"ANSWER:\n{row['attributes.output.value']}\n\n"
        "'grounded' if all claims are supported OR the answer appropriately says it can't find the "
        "info; 'hallucinated' if it states facts (packages, APIs, versions) not in the context."
    )
    return ("groundedness", *judge(rubric, ("grounded", "hallucinated")))


def main() -> int:
    import pandas as pd

    client, _ = make_client()
    df = client.spans.export_to_df(
        space_id=SPACE_ID,
        project_name=PROJECT,
        start_time=datetime(2026, 6, 12, 0, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 13, 0, 0, 0, tzinfo=timezone.utc),
    )
    kind = "attributes.openinference.span.kind"
    print(f"exported {len(df)} spans; kinds={df[kind].value_counts().to_dict()}")

    retr = df[df[kind] == "RETRIEVER"].dropna(subset=["attributes.input.value"])
    chain = df[df[kind] == "CHAIN"].dropna(subset=["attributes.output.value"])
    print(f"scoring {len(retr)} RETRIEVER + {len(chain)} CHAIN spans...")

    # accumulate one eval-rows dict per (eval_name) -> list of {span_id,label,score,expl}
    buckets: dict[str, list[dict]] = {}

    def run(row, fn):
        name, label, score, expl = fn(row)
        buckets.setdefault(name, []).append(
            {
                "context.span_id": row["context.span_id"],
                f"eval.{name}.label": label,
                f"eval.{name}.score": score,
                f"eval.{name}.explanation": expl,
            }
        )

    for _, row in retr.iterrows():
        run(row, eval_retrieval_relevance)
    for _, row in chain.iterrows():
        run(row, eval_answer_relevance)
        run(row, eval_groundedness)

    # log each eval as its own dataframe
    for name, rows in buckets.items():
        edf = pd.DataFrame(rows)
        mean = edf[f"eval.{name}.score"].mean()
        print(f"  {name}: {len(edf)} spans, mean score={mean:.3f} -> logging...")
        client.spans.update_evaluations(
            space_id=SPACE_ID, project_name=PROJECT, dataframe=edf
        )
    print("✓ evaluations logged — open the traces in AX; scores show on each span.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
