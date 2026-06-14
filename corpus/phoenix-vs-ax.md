# Phoenix vs Arize AX

Phoenix is Arize's open-source observability library (self-hostable or free on
Phoenix Cloud). Arize AX is the commercial platform. Both ingest the same
OpenInference/OTel traces, so agent and eval code is identical — only the
`register()` block differs (`phoenix.otel.register` vs `arize.otel.register`).

AX adds surfaces Phoenix does not: the Prompt Playground (compare prompt/model
versions in the UI), online evaluation Tasks (continuously score production
traces with an LLM judge), Copilot assistance, and team/production-scale
features. A common workflow: prototype on Phoenix, then move to AX for the
production observability and online-eval surfaces.
