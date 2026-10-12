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
