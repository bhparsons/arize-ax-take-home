# LLM-as-a-judge evaluations

An LLM-as-a-judge eval uses a language model to score outputs against a rubric.
Common eval types for agents:

- **Groundedness / hallucination**: did the answer stay faithful to the
  retrieved context, or did it fabricate?
- **Correctness**: does the answer match expected key points?
- **Function/tool-calling**: did the agent pick the right tool with the right
  arguments?

In the Arize/Phoenix stack you run these with `arize-phoenix-evals`
(`llm_classify` for classification-style judges) over a dataset, attaching the
scores to an experiment run so you can compare prompt or model versions
side by side. The same judge can run online as an AX Task to score live traces.
