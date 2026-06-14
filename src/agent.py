"""The Developer Research Assistant agent.

Built on Pydantic AI so the model is swappable (Claude / GPT / Gemini) via one
OpenRouter key — the on-brand "Arize is provider-neutral" demo.

Tools:
  - doc_lookup    → local RAG retriever (emits a RETRIEVER span). The grounding
                    surface, and the deliberate-failure surface for Phase 4.
  - web_search    → real Tavily search if TAVILY_API_KEY is set, else a clearly
                    labeled "unavailable" (never fabricates web results).
  - code_snippet  → pulls runnable code blocks out of the best-matching doc.
"""
from __future__ import annotations

import os
import re

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import OPENROUTER_BASE_URL, DEFAULT_AGENT_MODEL, get_settings, resolve_model_slug
from .rag import Retriever, format_results

SYSTEM_PROMPT = """\
You are a Developer Research Assistant. Answer developer questions about building
and observing AI agents. Plan briefly, call your tools to ground the answer, then
write a concise, cited answer.

Tools:
- doc_lookup(query): search the local developer-docs corpus. Use this first.
- web_search(query): search the live web. May be unavailable; if so, rely on docs.
- code_snippet(topic): get runnable code from the docs for a topic.

Rules:
- Ground every claim in retrieved sources. Cite the doc name (e.g. [arize-tracing.md]).
- If sources are thin or missing, SAY SO plainly. Do NOT fabricate package names,
  APIs, version numbers, or web results.
"""


def build_model(label: str | None = None) -> OpenAIChatModel:
    """Construct a Pydantic AI model routed through OpenRouter."""
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is unset. Add it to .env "
            "(get one at https://openrouter.ai/keys)."
        )
    slug = resolve_model_slug(label or DEFAULT_AGENT_MODEL)
    return OpenAIChatModel(
        slug,
        provider=OpenAIProvider(
            base_url=OPENROUTER_BASE_URL,
            api_key=settings.openrouter_api_key,
        ),
    )


def _web_search(query: str) -> str:
    """Real Tavily search if configured; otherwise an honest 'unavailable'."""
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return ("WEB_SEARCH_UNAVAILABLE: no TAVILY_API_KEY configured. "
                "Rely on doc_lookup and say if the docs don't cover this.")
    import httpx

    resp = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": key, "query": query, "max_results": 3},
        timeout=20,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        return "NO_WEB_RESULTS for this query."
    return "\n\n---\n\n".join(
        f"[{r.get('title','?')}] {r.get('url','')}\n{r.get('content','')}" for r in results
    )


def build_agent(
    label: str | None = None,
    dropped_docs: set[str] | None = None,
    context_sink: list[str] | None = None,
) -> Agent:
    """Build the agent with its tools. Call setup_tracing() first to trace it.

    `dropped_docs` simulates a degraded corpus (Phase 4 failure injection).
    `context_sink`, if given, accumulates every passage `doc_lookup` returns so the
    caller can stamp the concatenated retrieved context onto the root span — that's
    what lets the online groundedness eval compare answer vs. context on one row.
    """
    retriever = Retriever(dropped_docs=dropped_docs)

    agent = Agent(
        build_model(label),
        system_prompt=SYSTEM_PROMPT,
        name="dev-research-assistant",
    )

    @agent.tool_plain
    def doc_lookup(query: str) -> str:
        """Search the local developer-docs corpus for passages relevant to `query`."""
        passages = format_results(retriever.retrieve(query, top_k=3))
        if context_sink is not None:
            context_sink.append(passages)
        return passages

    @agent.tool_plain
    def web_search(query: str) -> str:
        """Search the live web for `query` (may be unavailable)."""
        return _web_search(query)

    @agent.tool_plain
    def code_snippet(topic: str) -> str:
        """Return runnable code blocks from the docs most relevant to `topic`."""
        # Rank broadly, then keep only chunks that actually contain code fences —
        # code tokens rarely out-score prose on a natural-language query.
        ranked = retriever.retrieve(topic, top_k=len(retriever.chunks))
        blocks: list[str] = []
        for r in ranked:
            if "```" not in r.chunk.text:
                continue
            for m in re.finditer(r"```[a-zA-Z]*\n(.*?)```", r.chunk.text, re.DOTALL):
                blocks.append(f"# from [{r.chunk.doc}]\n{m.group(1).strip()}")
            if len(blocks) >= 2:
                break
        return "\n\n".join(blocks) if blocks else "NO_CODE_FOUND in the docs for this topic."

    return agent
