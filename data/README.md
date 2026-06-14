# data/

| File | Role | Edit it? |
|---|---|---|
| **`golden.jsonl`** | **Canonical** golden dataset — one JSON object per line (JSONL). This is what `src/dataset.py` uploads to Arize. | ✅ Yes — this is the source of truth. |
| `golden.json` | **Generated** pretty-printed array, for human reading / review / clean diffs only. Nothing loads it. | ❌ No — it's overwritten by the formatter. |

## Workflow

Edit `golden.jsonl` (add/change rows), then regenerate the readable copy and
normalize the source in one step:

```bash
./scripts/format-golden.sh
```

That script (needs `jq`): validates every line is valid JSON, formats
`golden.jsonl` in place (compact, consistent, key order preserved), and refreshes
`golden.json`. Run it after any edit so the two files never drift.

**Why JSONL is canonical:** it's the standard for ML/eval datasets — streamable,
append-only, one record per line, and what Arize/Phoenix tooling expects. The
pretty `.json` exists only because a 261-char single line is hard to review.
