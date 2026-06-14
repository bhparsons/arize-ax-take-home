"""Run the agent on one question and land a trace.

    python -m src.run                      # default demo question
    python -m src.run "your question"      # custom question
    python -m src.run --model gpt "..."    # swap provider via OpenRouter

This is the Phase-1 cliff: run it once, then open the project in AX/Phoenix and
confirm the AGENT → LLM → TOOL waterfall.
"""
from __future__ import annotations

import argparse
import sys

from opentelemetry import trace

from .agent import build_agent
from .config import get_settings
from .tracing import setup_tracing

DEFAULT_QUESTION = "How do I send traces from a Pydantic AI agent to Arize?"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Developer Research Assistant.")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--model", default=None,
                        help="model label (claude|claude-opus|gpt|gemini) or raw OpenRouter slug")
    args = parser.parse_args(argv)

    settings = get_settings()
    print(f"→ backend={settings.tracing_backend}  project={settings.project_name}")
    setup_tracing(settings)

    # Capture the passages doc_lookup returns so we can stamp the retrieved
    # context onto the root span — this is what gives the online groundedness
    # eval a single row carrying BOTH the answer and its source context.
    context_sink: list[str] = []
    agent = build_agent(args.model, context_sink=context_sink)
    print(f"→ question: {args.question}\n")

    # Wrap the run in one explicit "research_request" span. It holds the
    # question, the final answer, and the retrieved context together, so the
    # Answer-Relevance and Groundedness online evals both target this one span.
    tracer = trace.get_tracer("dev-research-assistant")
    with tracer.start_as_current_span("research_request") as span:
        span.set_attribute("openinference.span.kind", "CHAIN")
        span.set_attribute("input.value", args.question)
        span.set_attribute("input.mime_type", "text/plain")
        result = agent.run_sync(args.question)
        span.set_attribute("output.value", str(result.output))
        span.set_attribute("output.mime_type", "text/plain")
        span.set_attribute(
            "retrieved_context",
            "\n\n---\n\n".join(context_sink) or "NO_CONTEXT_RETRIEVED",
        )

    print(result.output)
    print("\n✓ done — open the project in your backend and inspect the trace waterfall.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
