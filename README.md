# Dev Research Assistant — Arize AX take-home

### ▶ View it live (fully rendered): **https://bhparsons.github.io/arize-ax-take-home/**

A multi-tool research agent (**Pydantic AI on Claude**) instrumented end-to-end on **Arize AX**:
tracing, offline experiments, online evals, and a deliberately-debugged retrieval failure. Built by
Blake Parsons for the Arize AI **AI Product Manager** take-home.

> **Start here.** Open the [live site](https://bhparsons.github.io/arize-ax-take-home/) to click
> through everything rendered. (On GitHub directly, `.html` files show as source — the live link is
> the easy path. If you have this as a zip, open [`index.html`](index.html) in a browser instead.)

*▸ [Watch the short primer voiceover](https://www.loom.com/share/554e56c942da46c3be57cae7c7282295) — a quick spoken tour, if you'd rather be walked through it first.*

The assignment has three parts — a **build**, evidence of both Arize **workflows**, and a visual
**proposal**. Each has a home below.

| # | Deliverable | Where it lives | Status |
|---|---|---|---|
| ① | **Build** — agent traced + evaluated on AX | [`src/`](src/) (live in AX project `dev-research-assistant`) | ✅ |
| ② | **Workflows + onboarding feedback** | [`artifacts/results.html`](artifacts/results.html), [`artifacts/quick-fixes.html`](artifacts/quick-fixes.html), [`artifacts/FEEDBACK.html`](artifacts/FEEDBACK.html) | ✅ |
| ③ | **Proposal** — visual MVP | [`artifacts/proposal-v3.html`](artifacts/proposal-v3.html) · mocks [`artifacts/mocks-v3.html`](artifacts/mocks-v3.html) | ✅ |

**Short on time? A ~10-minute read** — punchline first, then the evidence:
**1.** [`artifacts/proposal-v3.html`](artifacts/proposal-v3.html) (the pitch — *From Signal to Decisions*) →
**2.** [`artifacts/results.html`](artifacts/results.html) (the workflow evidence) →
**3.** skim [`src/agent.py`](src/agent.py) + [`src/tracing.py`](src/tracing.py) →
**4.** [`artifacts/architecture.html`](artifacts/architecture.html) for the traced execution path.
Everything else supports those.

## The journey — five stops, build to proposal

The table above is the three deliverables Arize asked for. **This** is the path I actually took to
produce them — read top to bottom. I built and ran the agent, analyzed its behavior on Arize, shipped
the small fixes I'd want tomorrow, pulled the bigger themes out of that experience — and **the proposal
flows from those themes**. It climbs from tactical to strategic, which is the point: the Part-3 pitch is
grounded in the build, not invented.

> the path · **build → analyze → fix → themes → proposal**

| # | Stop | What I did | Where to look |
|---|---|---|---|
| 1 | **Build & run the agent** | Pydantic-AI research agent on Claude, traced end-to-end into AX | [`architecture.html`](artifacts/architecture.html) · [`code-internals.html`](artifacts/code-internals.html) |
| 2 | **Run the initial analysis** | Golden set → experiment → LLM judges, with a deliberate retriever failure to debug | [`results.html`](artifacts/results.html) · [`FEEDBACK.html`](artifacts/FEEDBACK.html) (raw log) |
| 3 | **Ship the quick fixes** | Nine onboarding / DX papercuts I'd fix tomorrow — all found live in the build | [`quick-fixes.html`](artifacts/quick-fixes.html) |
| 4 | **Pull out the themes** | Step back: which gaps are real, what evals are actually for, what to build vs. skip | [`concept-ledger.html`](artifacts/concept-ledger.html) |
| 5 | **The proposal flows from there** | *From Signal to Decisions* — the biggest theme, built into an MVP | [`proposal-v3.html`](artifacts/proposal-v3.html) · [`mocks-v3.html`](artifacts/mocks-v3.html) |

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

**Deep tour:** [`artifacts/code-internals.html`](artifacts/code-internals.html) is the full
walkthrough — it opens with the system diagram, traces one query ①→⑨, and explains the wiring
(tracing link, span emission, decorators, the eval engine). For the live, zoomable diagram on its own,
open [`artifacts/architecture.html`](artifacts/architecture.html).

## ② Workflows + evidence

Both Arize workflows were run:

- **Development** — a 12-row golden dataset → an experiment with two LLM-judges (correctness +
  groundedness) → a three-model comparison (Claude / GPT / Gemini). Repro commands in `results.html`.
- **Observability** — traces land in AX; a **deliberate retriever failure** (drop corpus docs) makes
  the groundedness judge score those traces low; root-cause in the waterfall (empty RETRIEVER span →
  fabricated answer); fix → score recovers.

| File | What it shows |
|---|---|
| [`artifacts/results.html`](artifacts/results.html) | Model comparison + failure delta, with the AX waterfall + experiment-comparison captures embedded, and repro commands |
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
