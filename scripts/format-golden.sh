#!/usr/bin/env bash
# format-golden.sh — format the golden dataset and refresh its readable copy.
#
#   data/golden.jsonl  = CANONICAL source of truth (what src/dataset.py uploads).
#                        JSONL: one JSON object per line, stream-friendly.
#   data/golden.json   = GENERATED pretty array, for human reading/review ONLY.
#                        Do not edit by hand — it's overwritten by this script.
#
# Usage:  ./scripts/format-golden.sh        (run from the repo root)
# Requires: jq  (brew install jq)
set -euo pipefail

cd "$(dirname "$0")/.."          # repo root, regardless of where it's called from
SRC="data/golden.jsonl"
PRETTY="data/golden.json"

command -v jq >/dev/null || { echo "✗ jq not found — install with: brew install jq"; exit 1; }

# 1. Validate: every non-empty line must be a complete JSON object (true JSONL).
n=0
while IFS= read -r line; do
  [ -z "${line// }" ] && continue
  echo "$line" | jq -e . >/dev/null || { echo "✗ invalid JSON on a line:"; echo "  $line"; exit 1; }
  n=$((n+1))
done < "$SRC"

# 2. Format the canonical JSONL in place: compact, one object per line,
#    key order preserved (no -S, so "question" stays before "expected_keypoints").
tmp="$(mktemp)"
jq -c . "$SRC" > "$tmp" && mv "$tmp" "$SRC"

# 3. Generate the pretty, readable array copy (slurp the stream into one array).
jq -s . "$SRC" > "$PRETTY"

echo "✓ formatted $SRC ($n rows) → refreshed $PRETTY"
