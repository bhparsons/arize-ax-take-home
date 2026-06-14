# Datasets and experiments

A **dataset** is a versioned set of examples (e.g. question + expected key
points) you evaluate against. An **experiment** runs a task (your agent) over a
dataset and applies one or more evaluators, recording outputs and scores.

With `arize-phoenix-client` you create/upload a dataset and call
`run_experiment(dataset, task, evaluators=[...])`. Do a `dry_run` first to catch
shape errors cheaply. Because every run is recorded, you compare two runs — for
example the same agent on Claude vs GPT vs Gemini — by their eval scores. This
is the development workflow: dataset → experiment → eval → iterate.
