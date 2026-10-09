"""Detect which datasets changed since the last shipped build.

Compares the freshly-fetched source hashes (``data-raw/sources/<collection>/_sources.json``)
against the hashes recorded in the shipped ``_collection.json`` and writes the
list of datasets that need re-export to ``data-raw/_changed.json``.

Run after ``01_fetch_sources.py`` and before the R export stage:

    uv run python data-raw/01b_detect_changes.py

Datasets whose source file is absent upstream are *not* listed — shipped data
is kept even when the upstream source drops it.
"""

from __future__ import annotations

import json
from pathlib import Path

from pharmadata._core.data import COLLECTIONS

PKG = Path(__file__).resolve().parents[1]
SOURCE_DIR = PKG / "data-raw" / "sources"
DATA_DIR = PKG / "src" / "pharmadata" / "_data"
CHANGED = PKG / "data-raw" / "_changed.json"


def _stored_hashes(collection: str) -> dict[str, str]:
    """Source hashes recorded in the shipped ``_collection.json``.

    A missing ``sources`` field (legacy collections) means every dataset is
    treated as changed so the first incremental run rebuilds everything.
    """
    path = DATA_DIR / collection / "_collection.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    sources = raw.get("sources")
    if not isinstance(sources, dict):
        return {}
    return {
        name: entry["sha256"]
        for name, entry in sources.items()
        if isinstance(entry, dict) and "sha256" in entry
    }


def _current_hashes(collection: str) -> dict[str, str]:
    """Source hashes from the just-fetched ``_sources.json``."""
    path = SOURCE_DIR / collection / "_sources.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        name: entry["sha256"]
        for name, entry in raw.items()
        if isinstance(entry, dict) and "sha256" in entry
    }


def changed_datasets() -> dict[str, list[str]]:
    """Datasets whose source hash differs from the shipped record.

    A dataset is changed when it is new (present in sources, absent in the
    shipped record) or its SHA-256 differs. Upstream deletions (present in the
    shipped record, absent in sources) are intentionally ignored: shipped data
    is kept.
    """
    result: dict[str, list[str]] = {}
    for collection in COLLECTIONS:
        stored = _stored_hashes(collection)
        current = _current_hashes(collection)
        changed = sorted(
            name for name, digest in current.items() if stored.get(name) != digest
        )
        if changed:
            result[collection] = changed
    return result


def main() -> None:
    """Write ``data-raw/_changed.json`` and report the change summary."""
    changed = changed_datasets()
    CHANGED.write_text(
        json.dumps(changed, indent=1, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )
    if not changed:
        print("ok: no source changes; nothing to rebuild")
        return
    total = sum(len(names) for names in changed.values())
    for collection, names in changed.items():
        print(f"[{collection}] {len(names)} changed: {', '.join(names)}")
    print(f"ok: {total} dataset(s) changed across {len(changed)} collection(s)")


if __name__ == "__main__":
    main()
