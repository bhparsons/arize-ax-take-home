"""Central config: env loading, model registry, backend selection.

One place to change models/backends. Everything else imports from here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # read .env once, at import time


# --- Model registry (OpenRouter slugs) ------------------------------------
# We auth to ALL providers through ONE OpenRouter key. Pydantic AI does the
# switching; these are the OpenRouter model slugs each label maps to.
#
# ⚠️ Slugs move — confirm the exact current slug at https://openrouter.ai/models
# when your key lands. Defaults below are conservative (cheap during dev).
MODELS: dict[str, str] = {
    "claude": "anthropic/claude-sonnet-4",   # on-brand default for the agent
    "claude-opus": "anthropic/claude-opus-4",
    "gpt": "openai/gpt-4o",                   # for the model-swap experiment
    "gemini": "google/gemini-2.5-pro",        # for the model-swap experiment
}

# Which label the agent runs on by default (override via AGENT_MODEL env).
DEFAULT_AGENT_MODEL = os.getenv("AGENT_MODEL", "claude")
# Which label the LLM-judge runs on (evals). Claude is on-brand.
DEFAULT_JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str | None
    tracing_backend: str          # "ax" | "phoenix"
    project_name: str
    # AX
    arize_space_id: str | None
    arize_api_key: str | None
    # AX SDK/experiments auth — often a separate "developer key" from the
    # ingest key used for tracing. Falls back to arize_api_key if unset.
    arize_developer_key: str | None
    # Phoenix
    phoenix_api_key: str | None
    phoenix_endpoint: str | None


def get_settings() -> Settings:
    return Settings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        tracing_backend=os.getenv("TRACING_BACKEND", "ax").lower(),
        project_name=os.getenv("PROJECT_NAME", "dev-research-assistant"),
        arize_space_id=os.getenv("ARIZE_SPACE_ID") or None,
        arize_api_key=os.getenv("ARIZE_API_KEY") or None,
        arize_developer_key=os.getenv("ARIZE_DEVELOPER_KEY") or None,
        phoenix_api_key=os.getenv("PHOENIX_API_KEY") or None,
        phoenix_endpoint=os.getenv("PHOENIX_COLLECTOR_ENDPOINT") or None,
    )


def resolve_model_slug(label: str) -> str:
    """Map a friendly label ('claude') to its OpenRouter slug."""
    if label in MODELS:
        return MODELS[label]
    # Allow passing a raw slug straight through (e.g. 'anthropic/claude-opus-4').
    if "/" in label:
        return label
    raise KeyError(
        f"Unknown model label {label!r}. Known: {list(MODELS)} "
        f"(or pass a raw OpenRouter slug like 'anthropic/claude-opus-4')."
    )
