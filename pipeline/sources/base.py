"""Source adapter interface.

Each adapter module `pipeline/sources/<id>.py` defines `class Adapter(Source)`.

- `probe()` makes one or a few cheap requests and returns a JSON-serialisable change signal
  (release version, ETag, newest issuance date, listing hash...). Equal signal => source unchanged.
- `fetch(previous, signal)` returns the full, current list of normalized Asian records for the source.
  It receives the previously stored records so it can fetch only new/changed detail pages.
"""
from __future__ import annotations

import importlib


class SourceError(Exception):
    """Raised when a source is blocked/broken; the source is marked stale and its old records are kept."""


class Source:
    id: str = ""
    implemented: bool = False

    def __init__(self, config: dict):
        self.config = config

    def probe(self) -> dict:
        raise NotImplementedError

    def fetch(self, previous: list[dict], signal: dict) -> list[dict]:
        raise NotImplementedError


def get_adapter(source_id: str, config: dict) -> Source:
    module = importlib.import_module(f"pipeline.sources.{source_id}")
    adapter = module.Adapter(config)
    adapter.id = source_id
    return adapter


STABLE_IGNORE = ("first_seen", "last_changed", "source_version", "raw_hash")


def carry_over(rec: dict, prev: dict[str, dict], today: str) -> dict:
    """Keep first_seen; keep last_changed/source_version/raw_hash when the record's content is unchanged
    (so a new source release doesn't rewrite every line of the stored file)."""
    old = prev.get(rec["record_id"])
    rec["first_seen"] = old.get("first_seen") if old else today
    same = bool(old) and all(old.get(k) == rec.get(k) for k in set(rec) | set(old) if k not in STABLE_IGNORE)
    if same:
        rec["last_changed"] = old.get("last_changed")
        rec["source_version"], rec["raw_hash"] = old.get("source_version"), old.get("raw_hash")
    else:
        rec["last_changed"] = today
    return rec
