"""Run an AX experiment over the golden dataset with LLM-as-a-judge evaluators.

    python -m src.experiment            # dry-run (small sample) — do this first
    python -m src.experiment --full     # full run over the whole dataset
    python -m src.experiment --model gpt --full   # model experiment (vs Claude)

The task runs the agent on each question and captures both the answer and the
retrieved context. Three LLM-judges score each run:
  - correctness:  does the answer cover the expected key points?
  - groundedness: is every claim supported by the retrieved context (and does
                  the agent admit ignorance instead of fabricating)?
  - scope:        did the agent stay in its lane — engage in-scope questions and
                  gracefully decline out-of-scope ones (`in_scope` rows)?

Run it twice on different --model values to get the side-by-side eval comparison
that demonstrates Arize's provider-neutrality.
"""
from __future__ import annotations

import argparse
import json
import re

from arize.experiments import EvaluationResult

from .agent import build_agent
from .config import (
    DEFAULT_AGENT_MODEL,
    DEFAULT_JUDGE_MODEL,
    OPENROUTER_BASE_URL,
    get_settings,
    resolve_model_slug,
)
from .dataset import DATASET_NAME, get_or_create_dataset, make_client
from .rag import Retriever, format_results
from .tracing import setup_tracing


# --- LLM judge (Claude via OpenRouter) ------------------------------------
def _judge(rubric: str) -> tuple[float, str]:
    """Ask the judge model to score 0..1 and explain. Robust to non-JSON replies."""
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=settings.openrouter_api_key)
    resp = client.chat.completions.create(
        model=resolve_model_slug(DEFAULT_JUDGE_MODEL),
        messages=[
            {"role": "system", "content": "You are a strict grader. "
             "Reply ONLY with JSON: {\"score\": <float 0..1>, \"explanation\": <string>}."},
            {"role": "user", "content": rubric},
        ],
        temperature=0,
    )
    text = resp.choices[0].message.content or ""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            return float(obj.get("score", 0.0)), str(obj.get("explanation", ""))[:500]
        except Exception:
            pass
    # fallback: pull a bare number
    num = re.search(r"(\d?\.\d+|\d)", text)
    return (float(num.group(0)) if num else 0.0), text[:500]


def correctness_eval(output, dataset_row) -> EvaluationResult:
    answer = output.get("answer", "") if isinstance(output, dict) else str(output)
    keypoints = dataset_row.get("expected_keypoints_text") or "; ".join(
        dataset_row.get("expected_keypoints", []))
    score, expl = _judge(
        f"QUESTION:\n{dataset_row.get('question')}\n\n"
        f"EXPECTED KEY POINTS:\n{keypoints}\n\n"
        f"ANSWER:\n{answer}\n\n"
        "Score 1.0 if the answer covers the key points, lower as it misses or "
        "contradicts them. If the key points say the docs don't cover the topic, "
        "reward the answer for admitting it doesn't know."
    )
    return EvaluationResult(score=score, label="pass" if score >= 0.6 else "fail",
                            explanation=expl)


def groundedness_eval(output, dataset_row) -> EvaluationResult:
    if not isinstance(output, dict):
        return EvaluationResult(score=0.0, label="fail", explanation="no context captured")
    score, expl = _judge(
        f"RETRIEVED CONTEXT:\n{output.get('context','')}\n\n"
        f"ANSWER:\n{output.get('answer','')}\n\n"
        "Score 1.0 if every factual claim in the answer is supported by the "
        "context. If the context is empty/irrelevant and the answer admits it "
        "doesn't know, that is grounded (score 1.0). Penalize fabricated package "
        "names, APIs, versions, or numbers not in the context."
    )
    return EvaluationResult(score=score, label="grounded" if score >= 0.6 else "hallucinated",
                            explanation=expl)


def scope_eval(output, dataset_row) -> EvaluationResult:
    """Did the agent stay in its lane?

    Rewards engaging in-scope questions AND gracefully declining out-of-scope
    ones; penalizes the inverse — a wrong refusal of a legitimate question, or
    answering an off-topic request. Rows carry `in_scope` (default True; the
    original golden set is all on-topic).

    This is the eval the sourdough probe exposed: Answer-Relevance alone would
    punish a correct refusal as "irrelevant". This judge scores refusal
    *correctness* as its own dimension.
    """
    answer = output.get("answer", "") if isinstance(output, dict) else str(output)
    in_scope = dataset_row.get("in_scope", True)
    expectation = (
        "This question IS in scope. The agent SHOULD engage and answer it (or "
        "honestly say the docs don't cover it). Score 1.0 if it engaged; score "
        "low if it wrongly refused or deflected a legitimate question."
        if in_scope else
        "This question is OUT of scope (not about building/observing AI agents). "
        "The agent SHOULD politely decline and redirect, WITHOUT answering the "
        "off-topic request or fabricating. Score 1.0 if it declined gracefully; "
        "score low if it answered the off-topic question anyway."
    )
    score, expl = _judge(
        "The agent is a Developer Research Assistant scoped to building and "
        "observing AI agents.\n\n"
        f"QUESTION:\n{dataset_row.get('question')}\n\n"
        f"ANSWER:\n{answer}\n\n"
        f"{expectation}"
    )
    return EvaluationResult(score=score, label="in_scope_ok" if score >= 0.6 else "scope_miss",
                            explanation=expl)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an AX experiment with LLM judges.")
    parser.add_argument("--full", action="store_true", help="full run (default: dry-run sample)")
    parser.add_argument("--model", default=None, help="agent model label (claude|gpt|gemini)")
    parser.add_argument("--dropped-docs", default="", help="comma-separated corpus files to drop (Phase 4)")
    args = parser.parse_args(argv)

    setup_tracing()  # experiment task runs are themselves traced
    dropped = {d.strip() for d in args.dropped_docs.split(",") if d.strip()}
    label = args.model or DEFAULT_AGENT_MODEL

    # Build the agent + retriever once; the task closes over them.
    agent = build_agent(label, dropped_docs=dropped)
    retriever = Retriever(dropped_docs=dropped)

    async def task(dataset_row) -> dict:
        # MUST be async: the experiment executor runs tasks inside a live event
        # loop, so a sync agent.run_sync() would raise "asyncio.run() cannot be
        # called from a running event loop". The async runner awaits this.
        question = dataset_row["question"]
        result = await agent.run(question)
        context = format_results(retriever.retrieve(question, top_k=3))
        return {"answer": result.output, "context": context}

    client, space = make_client()
    get_or_create_dataset(client, space)

    run_name = f"{label}-{'full' if args.full else 'dryrun'}"
    if dropped:
        run_name += "-degraded"
    print(f"→ running experiment '{run_name}' (dry_run={not args.full})")

    experiment, df = client.experiments.run(
        name=run_name,
        dataset=DATASET_NAME,
        space=space,
        task=task,
        evaluators=[correctness_eval, groundedness_eval, scope_eval],
        dry_run=not args.full,
    )
    # quick local summary
    for col in df.columns:
        if "score" in col.lower():
            try:
                print(f"   {col}: mean={df[col].astype(float).mean():.3f}")
            except Exception:
                pass
    print("✓ experiment done — open it in AX to compare runs and eval columns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
