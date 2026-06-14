"""Create/upload the golden dataset to Arize AX.

    python -m src.dataset                 # create (or reuse) the dataset on AX

Reads data/golden.jsonl (question + expected_keypoints) and uploads it as an AX
dataset that experiments run against. Idempotent-ish: if a dataset with the same
name exists, we reuse it rather than erroring.
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import get_settings

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "data" / "golden.jsonl"
DATASET_NAME = "dev-research-golden"


def load_golden() -> list[dict]:
    rows = [json.loads(line) for line in GOLDEN_PATH.read_text().splitlines() if line.strip()]
    # expected_keypoints stored as a list; keep a joined string too for easy judging.
    for r in rows:
        r["expected_keypoints_text"] = "; ".join(r.get("expected_keypoints", []))
    return rows


def make_client():
    """Build an ArizeClient for the datasets/experiments API.

    Prefers ARIZE_DEVELOPER_KEY (the SDK/GraphQL key) over the ingest ARIZE_API_KEY.
    If you get a 401/permission error, that's the cause — grab the developer key
    from AX → Settings and set ARIZE_DEVELOPER_KEY in .env.
    """
    from arize import ArizeClient

    settings = get_settings()
    key = settings.arize_developer_key or settings.arize_api_key
    if not key:
        raise RuntimeError("Set ARIZE_API_KEY (or ARIZE_DEVELOPER_KEY) in .env.")
    if not settings.arize_space_id:
        raise RuntimeError("Set ARIZE_SPACE_ID in .env.")
    return ArizeClient(api_key=key), settings.arize_space_id


def get_or_create_dataset(client, space: str, name: str = DATASET_NAME):
    """Return an existing dataset by name, else create it from the golden file."""
    # `get` takes dataset=<id or name> (name needs space). 404 → create.
    from arize import NotFoundError

    try:
        existing = client.datasets.get(dataset=name, space=space)
        if existing is not None:
            print(f"→ reusing existing dataset '{name}'")
            return existing
    except NotFoundError:
        pass  # doesn't exist yet → create below
    rows = load_golden()
    print(f"→ creating dataset '{name}' with {len(rows)} examples")
    return client.datasets.create(name=name, space=space, examples=rows)


def main() -> int:
    client, space = make_client()
    ds = get_or_create_dataset(client, space)
    print(f"✓ dataset ready: {getattr(ds, 'name', DATASET_NAME)} "
          f"(id={getattr(ds, 'id', '?')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
