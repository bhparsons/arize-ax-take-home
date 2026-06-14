# Building agents with Pydantic AI

Pydantic AI is a model-agnostic agent framework. You construct an `Agent` with a
model, a system prompt, and tools, then call `agent.run_sync(question)`.

```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
model = OpenAIChatModel("anthropic/claude-sonnet-4", provider=OpenAIProvider(base_url="https://openrouter.ai/api/v1", api_key="..."))
agent = Agent(model, system_prompt="You are a helpful assistant.")
result = agent.run_sync("How do I trace this agent?")
```

Models are swappable: point an `OpenAIChatModel` at any OpenAI-compatible
endpoint (including the OpenRouter gateway, `https://openrouter.ai/api/v1`) to
reach Claude, GPT, or Gemini through one key. Tools are registered with
decorators like `@agent.tool_plain`; the agent's LLM decides when to call them.

Because the framework emits native OpenTelemetry spans (enabled via
`Agent.instrument_all(True)`), any OTel/OpenInference backend — Arize AX or
Phoenix — can trace it without provider-specific glue.
