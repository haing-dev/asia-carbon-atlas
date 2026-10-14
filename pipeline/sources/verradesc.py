"""Verra project descriptions (used only for tags, config/tags.yaml), from Verra's public registry.

Verra's public project page (https://registry.verra.org/verra/public/program/VCS/projects/<id>) loads its data from a
public endpoint on S&P's registry platform. That endpoint is rate-limited, so this lookup is deliberately slow: at most
MAX_PER_RUN projects per run, one request every SPACING seconds; a "429 rate limit" response pauses once and then
ends the run (progress is kept; the next run continues). Descriptions are cached in data/lookups/verradesc.jsonl and
fetched once per project; only Verra projects already in the atlas (data/records/vrod.jsonl) are looked up, most
tag-relevant credit types first. No login; the request carries the same public headers the registry page sends.
Probe: number of in-scope Verra projects without a cached description (no network).
"""
from __future__ import annotations

import os
import time

from pipeline import common
from pipeline.http import PoliteClient
from pipeline.sources.base import Source, SourceError

API = "https://prod-us.api.platts.com/ci-raas-prod/br-reg/rest/public-report-manager/getProjectById/{id}/Markit"
PAGE = "https://registry.verra.org/verra/public/program/VCS/projects/{id}"
CONFIG = "https://registry.verra.org/config/environment.config.json"  # public site config (headers the page sends)
OUTPUT = common.ROOT / "data" / "lookups" / "verradesc.jsonl"
MAX_PER_RUN = 120
SPACING = 20.0
# Credit types whose tags depend most on the description come first; types where the name says it all come last.
PRIORITY = ["rice_methane", "soil_carbon", "agroforestry", "blue_carbon", "peat_wetland", "fertilizer", "livestock",
            "arr", "redd", "ifm", "other_land", "cookstoves", "water", "household_biogas", "biochar", "erw",
            "mineralization", "wastewater", "biogas_ad", "composting", "landfill", "buildings", "biomass_power"]


def find_text(obj) -> str | None:
    """The project description: the longest string under a key containing "desc" (any depth)."""
    best = ""

    def walk(o):
        nonlocal best
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and "desc" in k.lower() and len(v.strip()) > len(best):
                    best = v.strip()
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return best if len(best) > 20 else None


def all_keys(obj, prefix="") -> list[str]:
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(prefix + k)
            out += all_keys(v, prefix + k + ".")
    elif isinstance(obj, list) and obj:
        out += all_keys(obj[0], prefix + "[0].")
    return out


def wanted() -> list[str]:
    """In-scope Verra ids, most tag-relevant credit types first (credit type as classified from the record)."""
    from pipeline import process
    mmap, rules = process.load_methodology_map(), process.load_type_rules()
    recs = [r for r in common.read_jsonl(common.RECORDS_DIR / "vrod.jsonl")
            if r.get("registry") == "VCS" and str(r.get("native_id") or "").isdigit()]
    rank = {l2: i for i, l2 in enumerate(PRIORITY)}
    recs.sort(key=lambda r: (rank.get(process.classify(r, mmap, rules), len(PRIORITY)), -int(r["native_id"])))
    return [r["native_id"] for r in recs]


class Adapter(Source):
    implemented = True
    output_path = OUTPUT

    def probe(self) -> dict:
        have = {r["record_id"] for r in common.read_jsonl(OUTPUT)}
        missing = [i for i in wanted() if f"VCS:{i}" not in have]
        # While anything is missing, every run should fetch (the signal changes daily); afterwards it stays put.
        return {"missing": len(missing), "day": common.today() if missing else None}

    def fetch(self, previous: list[dict], signal: dict) -> list[dict]:
        out = {r["record_id"]: r for r in previous}
        todo = [i for i in wanted() if f"VCS:{i}" not in out][:int(os.environ.get("VERRADESC_MAX", MAX_PER_RUN))]
        client = PoliteClient(timeout=60)
        cfg = client.get(CONFIG)
        cfg.raise_for_status()
        headers = dict((cfg.json().get("uris", {}).get("common", {}) or {}).get("DEFAULT_HEADERS") or {})
        headers.pop("Cookie", None)
        headers.update({"registry": "VERRA", "standardacronym": "VCS", "standardid": "150000000000001",
                        "referer": "https://registry.verra.org/", "accept": "application/json"})
        done = 0
        for i in todo:
            time.sleep(SPACING)
            r = client.get(API.format(id=i), headers=dict(headers))
            if r.status_code == 429:
                time.sleep(180)
                r = client.get(API.format(id=i), headers=dict(headers))
                if r.status_code == 429:
                    print(f"[verradesc] rate limited after {done} projects; continuing next run")
                    break
            if r.status_code == 404:
                out[f"VCS:{i}"] = {"record_id": f"VCS:{i}", "description": None, "fetched": common.today()}
                continue
            if r.status_code != 200:
                raise SourceError(f"Verra project {i}: HTTP {r.status_code}")
            data = r.json()
            desc = find_text(data)
            if desc is None and done == 0:
                raise SourceError(f"Verra project {i}: no description field found; keys {all_keys(data)}")
            out[f"VCS:{i}"] = {"record_id": f"VCS:{i}", "description": " ".join(desc.split())[:4000] if desc else None,
                               "fetched": common.today()}
            done += 1
        print(f"[verradesc] fetched {done}; {len([x for x in wanted() if f'VCS:{x}' not in out])} still missing")
        return sorted(out.values(), key=lambda r: (len(r["record_id"]), r["record_id"]))
