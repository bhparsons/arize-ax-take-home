# Tracing a Pydantic AI agent to Arize AX

Arize AX ingests OpenTelemetry (OTel) traces via OpenInference semantic
conventions. To trace a Pydantic AI agent:

1. Install `arize-otel` and `openinference-instrumentation-pydantic-ai`.
2. Call `register(...)` from `arize.otel`, passing the OpenInference processor.
3. Enable Pydantic AI's OTel emission with `Agent.instrument_all(True)`.

```python
from arize.otel import register
from openinference.instrumentation.pydantic_ai import OpenInferenceSpanProcessor
from pydantic_ai import Agent
register(space_id="...", api_key="...", project_name="dev-research-assistant", span_processors=[OpenInferenceSpanProcessor()])
Agent.instrument_all(True)
```
4. Run the agent. Traces appear in the named project's trace view as a span
   waterfall: an AGENT span with nested LLM and TOOL spans.

The OpenInference span processor reshapes Pydantic AI's native OTel spans into
the OpenInference conventions Arize expects (span kinds like LLM, TOOL,
RETRIEVER; attributes like input/output, token counts, tool arguments).
