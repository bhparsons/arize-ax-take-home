"""Local RAG retriever over corpus/*.md — the deliberate failure surface.

Chunk the corpus, score chunks against the query with TF-IDF cosine (numpy, no
embedding API needed — "naive cosine / small vector store" per the architecture),
and emit a proper OpenInference RETRIEVER span so the trace shows
TOOL(doc_lookup) → RETRIEVER with retrieved documents + scores.

Phase 4 degrades this on purpose (drop a doc, shrink top_k) to induce a
grounded-ness failure, then we watch the online judge catch it.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from opentelemetry import trace
from openinference.semconv.trace import (
    DocumentAttributes,
    OpenInferenceSpanKindValues,
    SpanAttributes,
)

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"
_tracer = trace.get_tracer(__name__)
_token_re = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [t for t in _token_re.findall(text.lower()) if len(t) > 2]


@dataclass
class Chunk:
    doc: str          # source filename
    idx: int          # chunk index within the doc
    text: str

    @property
    def id(self) -> str:
        return f"{self.doc}#{self.idx}"


@dataclass
class Retrieved:
    chunk: Chunk
    score: float


def _chunk_doc(path: Path) -> list[Chunk]:
    """Split a markdown doc into paragraph chunks (blank-line separated)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", path.read_text(encoding="utf-8"))]
    return [Chunk(path.name, i, p) for i, p in enumerate(p for p in paras if p)]


class Retriever:
    """TF-IDF cosine retriever. Construct once; call .retrieve() per query.

    Degrade knobs (Phase 4): pass `dropped_docs` to simulate a missing corpus
    file, or a smaller `top_k` to starve grounding.
    """

    def __init__(self, dropped_docs: set[str] | None = None) -> None:
        self.dropped_docs = dropped_docs or set()
        self.chunks: list[Chunk] = []
        for path in sorted(CORPUS_DIR.glob("*.md")):
            if path.name in self.dropped_docs:
                continue
            self.chunks.extend(_chunk_doc(path))
        self._build_index()

    def _build_index(self) -> None:
        docs_tokens = [_tokenize(c.text) for c in self.chunks]
        vocab: dict[str, int] = {}
        for toks in docs_tokens:
            for t in toks:
                vocab.setdefault(t, len(vocab))
        self.vocab = vocab
        n = len(self.chunks)
        df = np.zeros(len(vocab))
        tf = np.zeros((n, len(vocab)))
        for i, toks in enumerate(docs_tokens):
            seen = set()
            for t in toks:
                j = vocab[t]
                tf[i, j] += 1
                if t not in seen:
                    df[j] += 1
                    seen.add(t)
        idf = np.log((n + 1) / (df + 1)) + 1.0
        self.idf = idf
        mat = tf * idf
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.matrix = mat / norms  # row-normalized for cosine via dot product

    def _vectorize(self, query: str) -> np.ndarray:
        vec = np.zeros(len(self.vocab))
        for t in _tokenize(query):
            j = self.vocab.get(t)
            if j is not None:
                vec[j] += 1
        vec *= self.idf
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def retrieve(self, query: str, top_k: int = 3) -> list[Retrieved]:
        """Return the top_k chunks for `query`, wrapped in a RETRIEVER span."""
        with _tracer.start_as_current_span("doc_lookup.retrieve") as span:
            span.set_attribute(
                SpanAttributes.OPENINFERENCE_SPAN_KIND,
                OpenInferenceSpanKindValues.RETRIEVER.value,
            )
            span.set_attribute(SpanAttributes.INPUT_VALUE, query)

            if not self.chunks:
                span.set_attribute("retrieval.empty", True)
                return []
            sims = self.matrix @ self._vectorize(query)
            order = np.argsort(sims)[::-1][:top_k]
            results = [
                Retrieved(self.chunks[i], float(sims[i]))
                for i in order
                if sims[i] > 0
            ]

            base = SpanAttributes.RETRIEVAL_DOCUMENTS
            for i, r in enumerate(results):
                span.set_attribute(f"{base}.{i}.{DocumentAttributes.DOCUMENT_ID}", r.chunk.id)
                span.set_attribute(f"{base}.{i}.{DocumentAttributes.DOCUMENT_CONTENT}", r.chunk.text)
                span.set_attribute(f"{base}.{i}.{DocumentAttributes.DOCUMENT_SCORE}", r.score)
            span.set_attribute("retrieval.num_documents", len(results))
            return results


def format_results(results: list[Retrieved]) -> str:
    """Render retrieved chunks for the LLM, with citable doc names."""
    if not results:
        return "NO_DOCS_MATCHED — the corpus has nothing relevant to this query."
    return "\n\n---\n\n".join(
        f"[{r.chunk.doc}] (score={r.score:.3f})\n{r.chunk.text}" for r in results
    )
