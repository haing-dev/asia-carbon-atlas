"""Credit retirements by beneficiary, from CarbonPlan OffsetsDB (https://carbonplan.org/research/offsetsdb).

OffsetsDB republishes the transaction records of Verra, Gold Standard, ACR, CAR, ART TREES, Isometric and Cercarbono,
including each retirement's beneficiary / account / note fields, and a harmonized beneficiary name (CarbonPlan's
OpenRefine mapping). Facts only; CarbonPlan claims no copyright (TERMS_OF_DATA_ACCESS.txt in the archive).

Output: data/lookups/retirements.jsonl — one row per project x beneficiary:
  {"record_id": "VCS:1477", "beneficiary": "Microsoft", "matched_by": "harmonized"|"pattern", "retired_tco2e": ..,
   "n": <transactions>, "first": "YYYY-MM-DD", "last": "YYYY-MM-DD"}
plus one row per project with beneficiary null for retirements with no identifiable beneficiary, and
one {"record_id": "META", ...} row with the snapshot date, and {"record_id": "COV:Cercarbono:<ISO3>", "issued_tco2e"}
rows: credits issued per country in Cercarbono (a registry the atlas does not cover; used for the coverage %).
A beneficiary is the harmonized name when CarbonPlan set one; otherwise a buyer from config/buyers.yaml whose
pattern matches the beneficiary, account or note text. Nothing else is inferred.
Probe: HEAD of the archive (ETag / Last-Modified). Fetch: one ~9 MB download.
"""
from __future__ import annotations

import collections
import csv
import io
import json
import re
import zipfile

import yaml

from pipeline import common
from pipeline.http import PoliteClient
from pipeline.normalize import in_scope, iso3
from pipeline.sources.base import Source, SourceError

URL = "https://carbonplan-offsets-db.s3.us-west-2.amazonaws.com/production/latest/offsets-db.csv.zip"
OUTPUT = common.ROOT / "data" / "lookups" / "retirements.jsonl"
BUYERS = common.ROOT / "config" / "buyers.yaml"


def record_id(pid: str) -> str | None:
    """OffsetsDB project_id -> atlas record_id (None for registries the atlas does not cover)."""
    m = re.fullmatch(r"(VCS|GLD|ACR|CAR|ART)(\d+)", pid or "")
    if not m:
        return None
    reg, num = m.groups()
    n = int(num)
    return {"VCS": f"VCS:{n}", "GLD": f"GS:{n}", "CAR": f"CAR:{n}", "ACR": f"ACR:{n:04d}", "ART": f"ART:{n:04d}"}[reg]


def load_patterns() -> list[tuple[str, re.Pattern]]:
    if not BUYERS.exists():
        return []
    cfg = yaml.safe_load(BUYERS.read_text(encoding="utf-8")) or {}
    out = []
    for b in cfg.get("buyers") or []:
        for p in b.get("retirement_patterns") or []:
            out.append((b["name"], re.compile(p)))
    return out


def match(patterns, *texts: str) -> str | None:
    text = " ; ".join(t for t in texts if t)
    if not text:
        return None
    for name, rx in patterns:
        if rx.search(text):
            return name
    return None


class Adapter(Source):
    implemented = True
    output_path = OUTPUT  # a lookup, not project records

    def __init__(self, config: dict):
        super().__init__(config)
        self.client = PoliteClient(timeout=300)

    def probe(self) -> dict:
        r = self.client.head(URL)
        r.raise_for_status()
        return {"etag": r.headers.get("etag"), "modified": r.headers.get("last-modified"),
                "bytes": r.headers.get("content-length"), "buyers": common.sha256_bytes(BUYERS.read_bytes()) if BUYERS.exists() else None}

    def fetch(self, previous: list[dict], signal: dict) -> list[dict]:
        r = self.client.get(URL)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(z.namelist())
        if not {"credits.csv", "projects.csv"} <= names:
            raise SourceError(f"OffsetsDB archive: unexpected members {sorted(names)}")
        meta = json.loads(z.read("metadata.json")) if "metadata.json" in names else {}

        scope = {}
        uncovered: dict[tuple, float] = collections.defaultdict(float)
        with z.open("projects.csv") as f:
            for p in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")):
                rid = record_id(p["project_id"])
                if not rid and p["project_id"].startswith("CCB"):   # Cercarbono: not an atlas registry (coverage only)
                    c = iso3(p.get("country"))
                    if c and in_scope([c]):
                        try:
                            uncovered[("Cercarbono", c)] += float(p.get("issued") or 0)
                        except ValueError:
                            pass
                if rid:
                    c = iso3(p.get("country"))
                    scope[rid] = (c is None) or in_scope([c])

        patterns = load_patterns()
        agg: dict[tuple, dict] = {}
        total = 0
        with z.open("credits.csv") as f:
            for c in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")):
                if c["transaction_type"] != "retirement":
                    continue
                rid = record_id(c["project_id"])
                if not rid or not scope.get(rid, True):
                    continue
                try:
                    q = float(c["quantity"] or 0)
                except ValueError:
                    continue
                if q <= 0:
                    continue
                total += 1
                ben, how = (c.get("retirement_beneficiary_harmonized") or "").strip() or None, "harmonized"
                if not ben:
                    ben, how = match(patterns, c.get("retirement_beneficiary"), c.get("retirement_account"),
                                     c.get("retirement_note")), "pattern"
                if not ben:
                    how = None
                d = (c.get("transaction_date") or "")[:10] or None
                a = agg.setdefault((rid, ben), {"record_id": rid, "beneficiary": ben, "matched_by": how,
                                                "retired_tco2e": 0.0, "n": 0, "first": d, "last": d})
                a["retired_tco2e"] += q
                a["n"] += 1
                if d:
                    a["first"] = min(filter(None, [a["first"], d]))
                    a["last"] = max(filter(None, [a["last"], d]))
        if total < 100_000:
            raise SourceError(f"OffsetsDB: only {total} in-scope retirement rows")
        rows = sorted(agg.values(), key=lambda a: (a["record_id"], a["beneficiary"] or ""))
        for a in rows:
            a["retired_tco2e"] = round(a["retired_tco2e"])
        head = {"record_id": "META", "snapshot": meta.get("generated_at") or signal.get("modified"),
                "source_version": f"OffsetsDB {meta.get('generated_at') or signal.get('modified')}",
                "raw_hash": common.sha256_bytes(r.content), "rows": total}
        cov = [{"record_id": f"COV:{reg}:{c}", "registry": reg, "country": c, "issued_tco2e": round(v)}
               for (reg, c), v in sorted(uncovered.items()) if v > 0]
        return [head] + rows + cov
