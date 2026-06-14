"""Tracing setup — the one block that changes between Arize AX and Phoenix.

`setup_tracing()` registers an OTel tracer provider pointed at the chosen
backend and attaches the OpenInference span processor that reshapes Pydantic
AI's native OTel spans into OpenInference semantic conventions, then flips on
Pydantic AI instrumentation globally.

Switch backends with TRACING_BACKEND=ax|phoenix in .env. Only this file knows
the difference — agent code is backend-agnostic.
"""
from __future__ import annotations

from pydantic_ai import Agent

from .config import Settings, get_settings


def setup_tracing(settings: Settings | None = None):
    """Wire traces to the configured backend. Returns the tracer provider.

    Call once, before building/running the agent.
    """
    settings = settings or get_settings()
    # Imported lazily so the unused backend's SDK never has to import cleanly.
    from openinference.instrumentation.pydantic_ai import OpenInferenceSpanProcessor

    if settings.tracing_backend == "ax":
        if not (settings.arize_space_id and settings.arize_api_key):
            raise RuntimeError(
                "TRACING_BACKEND=ax but ARIZE_SPACE_ID / ARIZE_API_KEY are unset. "
                "Add them to .env, or switch TRACING_BACKEND=phoenix."
            )
        from arize.otel import register

        # register() accepts extra processors and adds them in the right order
        # relative to its exporter — pass OpenInference here (don't bolt it on after).
        tracer_provider = register(
            space_id=settings.arize_space_id,
            api_key=settings.arize_api_key,
            project_name=settings.project_name,
            span_processors=[OpenInferenceSpanProcessor()],
        )

    elif settings.tracing_backend == "phoenix":
        if not settings.phoenix_api_key:
            raise RuntimeError(
                "TRACING_BACKEND=phoenix but PHOENIX_API_KEY is unset. "
                "Add it to .env (and PHOENIX_COLLECTOR_ENDPOINT if self-hosting)."
            )
        from phoenix.otel import register

        # phoenix.otel.register() has no span_processors arg, so attach after.
        # NOTE: confirm OpenInference reshaping shows up correctly on the FIRST
        # trace's waterfall — processor ordering is the thing to eyeball here.
        tracer_provider = register(
            project_name=settings.project_name,
            endpoint=settings.phoenix_endpoint,  # None → SDK default (Phoenix Cloud)
            api_key=settings.phoenix_api_key,
        )
        tracer_provider.add_span_processor(OpenInferenceSpanProcessor())

    else:
        raise ValueError(
            f"Unknown TRACING_BACKEND={settings.tracing_backend!r}; use 'ax' or 'phoenix'."
        )

    # Flip on Pydantic AI's native OTel emission for every Agent in the process.
    # (In pydantic-ai 1.x the old `Agent(instrument=True)` kwarg is deprecated;
    # instrument_all() is the supported global switch.)
    Agent.instrument_all(True)
    return tracer_provider
