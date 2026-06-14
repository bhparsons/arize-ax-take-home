# Dev Research Assistant — Arize AX take-home

### ▶ View it live (fully rendered): **https://bhparsons.github.io/arize-ax-take-home/**

A multi-tool research agent (**Pydantic AI on Claude**) instrumented end-to-end on **Arize AX**:
tracing, offline experiments, online evals, and a deliberately-debugged retrieval failure. Built by
Blake Parsons for the Arize AI **AI Product Manager** take-home.

> **Start here.** Open the [live site](https://bhparsons.github.io/arize-ax-take-home/) to click
> through everything rendered. (On GitHub directly, `.html` files show as source — the live link is
> the easy path. If you have this as a zip, open [`index.html`](index.html) in a browser instead.)

The assignment has three parts — a **build**, evidence of both Arize **workflows**, and a visual
**proposal**. Each has a home below.

| # | Deliverable | Where it lives | Status |
|---|---|---|---|
| ① | **Build** — agent traced + evaluated on AX | [`src/`](src/) (live in AX project `dev-research-assistant`) | ✅ |
| ② | **Workflows + onboarding feedback** | [`artifacts/RESULTS.html`](artifacts/RESULTS.html), [`artifacts/quick-fixes.html`](artifacts/quick-fixes.html), [`artifacts/FEEDBACK.html`](artifacts/FEEDBACK.html) | ✅ |
| ③ | **Proposal** — visual MVP | [`artifacts/proposal-v3.html`](artifacts/proposal-v3.html) · mocks [`artifacts/mocks-v3.html`](artifacts/mocks-v3.html) | ✅ |

**If you read one thing:** [`artifacts/proposal-v3.html`](artifacts/proposal-v3.html) (the proposal —
*From Signal to Decisions*) and [`artifacts/RESULTS.html`](artifacts/RESULTS.html) (the workflow evidence).
Everything else supports those two.

## Quick start — run the agent in ~2 minutes

```bash
uv venv --python 3.12 && source .venv/bin/activate   # 3.12 for wheel compatibility
uv pip install -r requirements.txt
cp .env.example .env        # fill in OPENROUTER_API_KEY + ARIZE_SPACE_ID/ARIZE_API_KEY
python -m src.run                          # default demo question
python -m src.run "How do I run an experiment with an LLM judge?"
python -m src.run --model gpt "..."        # swap provider via OpenRouter (model-agnostic demo)
```

Model auth is a single **OpenRouter** key (reaches Claude/GPT/Gemini through one OpenAI-compatible
endpoint). The tracing backend is selected by `TRACING_BACKEND=ax|phoenix` in `.env` — only
`src/tracing.py` knows the difference.

## ① The build

A **Developer Research Assistant** — "an agent that helps devs build agents." It plans a lookup,
retrieves over a local doc corpus, optionally web-searches, reasons over the sources, and writes a
cited answer. Pydantic AI (model-agnostic) on Claude, instrumented to AX via OpenInference/OTel.

```
AGENT (researcher)
 ├─ LLM   plan the lookup
 ├─ TOOL  doc_lookup → RETRIEVER (local RAG corpus)   ← the deliberate failure surface
 ├─ TOOL  web_search
 ├─ LLM   reason over sources
 └─ LLM   writer → cited answer
```

| File | Responsibility |
|---|---|
| `src/run.py` | CLI entry — settings → tracing → build agent → run |
| `src/agent.py` | Builds the Pydantic-AI agent + the three tools |
| `src/rag.py` | TF-IDF retriever over `corpus/`; emits the RETRIEVER span |
| `src/tracing.py` | The only file that knows the backend (AX vs Phoenix) |
| `src/config.py` | Keys, model map, OpenRouter endpoint |
| `src/dataset.py` · `src/experiment.py` | Golden dataset + LLM-judge experiment engine |

**Deep tour:** [`artifacts/architecture.html`](artifacts/architecture.html) (one query traced ①→⑨) and
[`artifacts/code-internals.html`](artifacts/code-internals.html) (the code mental-model).

## ② Workflows + evidence

Both Arize workflows were run:

- **Development** — a 12-row golden dataset → an experiment with two LLM-judges (correctness +
  groundedness) → a three-model comparison (Claude / GPT / Gemini). Repro commands in `RESULTS.html`.
- **Observability** — traces land in AX; a **deliberate retriever failure** (drop corpus docs) makes
  the groundedness judge score those traces low; root-cause in the waterfall (empty RETRIEVER span →
  fabricated answer); fix → score recovers.

| File | What it shows |
|---|---|
| [`artifacts/RESULTS.html`](artifacts/RESULTS.html) | Model comparison + failure delta, with the AX waterfall + experiment-comparison captures embedded, and repro commands |
| [`artifacts/quick-fixes.html`](artifacts/quick-fixes.html) | Onboarding DX writeup — nine papercuts + a "what went well" box, with evidence screenshots |
| [`artifacts/FEEDBACK.html`](artifacts/FEEDBACK.html) | The raw, as-it-happened onboarding-friction log |

## ③ Proposal — *From Signal to Decisions*

**Grounding the improvement loop in outcomes.** The visual MVP answer to "what should Arize build to
grow AX adoption among developers building agents?" The bet: finding agent failures is table stakes
now — Signal, LangSmith Engine, and Raindrop all cluster failures and propose fixes. Nobody owns the
two ends of the loop: **ground truth** (did the session achieve its business outcome?) and **the
decision** (did the org ship the change, and did it move the metric?). Arize should ground the
improvement loop in the agent's true objective function — objective → ranked issues → decisions routed
to owners → verified lift. Presented verbally in a later round.

- [`artifacts/proposal-v3.html`](artifacts/proposal-v3.html) — the visual digest (start here)
- [`artifacts/mocks-v3.html`](artifacts/mocks-v3.html) — UI mocks: objective setup → decision queue → decision detail → tool spec
- [`artifacts/quick-fixes.html`](artifacts/quick-fixes.html) — onboarding/DX papercuts, rendered with evidence screenshots
- [`artifacts/concept-ledger.html`](artifacts/concept-ledger.html) — appendix: every concept considered + how it was triaged

> V3 supersedes two earlier drafts — V1 "Eval Copilot in the IDE" (pre-market-scan) and V2 "From
> Evals to Actions" (pre-Signal-pressure-test). The [concept ledger](artifacts/concept-ledger.html)
> records why the direction moved.

## Where everything lives

| Path | What |
|---|---|
| `src/` | The agent, RAG tool, tracing setup, dataset + experiment scripts |
| `corpus/` | 5 local Markdown docs the agent retrieves over |
| `data/golden.jsonl` | The 12-row golden eval set |
| `artifacts/` | The visual deliverables, the explainer companions, and the evidence (HTML + screenshots) |

## Running it

The repo is git-clean — `.env` and `.venv` are gitignored; the evidence screenshots ship. Copy
`.env.example` to `.env`, add your `OPENROUTER_API_KEY` + `ARIZE_SPACE_ID`/`ARIZE_API_KEY`, and run
`python -m src.run`. If you received this as a zip, open [`index.html`](index.html) in a browser.
