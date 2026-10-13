"""Gold Standard registry page ids, from the registry's public API (https://public-api.goldstandard.org/projects).

The VROD lists Gold Standard projects by their GS number (e.g. GS23411), but the registry's project page is addressed
by a separate internal id (GS23411 -> registry.goldstandard.org/projects/details/5335). This lookup maps one to the
other so every Gold Standard row links to its real registry page. It adds no projects or volumes.
Output: data/lookups/gsreg.jsonl, one {"record_id": "GS:<GS number>", "registry_id": "<page id>"} per project.
Probe: total project count + newest project (1 request). Fetch: ~30 pages of 150 at ≤1 req/s.
"""
from __future__ import annotations

from pipeline import common
from pipeline.http import PoliteClient
from pipeline.sources.base import Source, SourceError

API = "https://public-api.goldstandard.org/projects"
PAGE_SIZE = 150  # the API's maximum page size
OUTPUT = common.ROOT / "data" / "lookups" / "gsreg.jsonl"


class Adapter(Source):
    implemented = True
    output_path = OUTPUT

    def __init__(self, config: dict):
        super().__init__(config)
        self.client = PoliteClient(timeout=60)

    def _page(self, page: int, size: int):
        r = self.client.get(f"{API}?page={page}&size={size}")
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list):
            raise SourceError("GS registry API: unexpected response shape")
        return rows, int(r.headers.get("x-total-count") or 0)

    def probe(self) -> dict:
        rows, total = self._page(1, 1)
        return {"total": total, "newest": rows[0].get("id") if rows else None,
                "updated": rows[0].get("updated_at") if rows else None}

    def fetch(self, previous: list[dict], signal: dict) -> list[dict]:
        total = signal.get("total") or 0
        out: dict[str, str] = {}
        for page in range(1, total // PAGE_SIZE + 2):
            rows, _ = self._page(page, PAGE_SIZE)
            for p in rows:
                if p.get("sustaincert_id") and p.get("id"):
                    out[f"GS:{int(p['sustaincert_id'])}"] = str(p["id"])
            if len(rows) < PAGE_SIZE:
                break
        if len(out) < 0.9 * total:
            raise SourceError(f"GS registry API: got {len(out)} of {total} projects")
        return [{"record_id": k, "registry_id": v} for k, v in sorted(out.items(), key=lambda kv: int(kv[0][3:]))]
