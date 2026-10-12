"""Turn stored registry records into deduplicated projects (in memory; never stored).

M0: classification, stages and clustering are minimal placeholders; M3 replaces them
with the methodology dictionary + keyword rules, cross-reference/fuzzy dedupe, and
population-weighted country shares (docs/SPEC.md §5–8).
"""
from __future__ import annotations

import csv
from collections import defaultdict

from pipeline import common

STAGE_ORDER = {"inactive": 0, "pipeline": 1, "registered": 2, "issuing": 3}


def load_methodology_map() -> dict[tuple[str, str], str]:
    path = common.CONFIG / "methodology_map.csv"
    out: dict[tuple[str, str], str] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[(row["registry"] or "*", row["code"].strip().upper())] = row["l2"]
    return out


def classify(rec: dict, mmap: dict) -> str:
    for code in rec.get("methodology_codes") or []:
        c = code.strip().upper()
        l2 = mmap.get((rec["registry"], c)) or mmap.get(("*", c))
        if l2:
            return l2
    return "other"


def stage_of(rec: dict, stage_map: dict) -> str:
    if (rec.get("issued_tco2e") or 0) > 0:
        return "issuing"
    raw = str(rec.get("registry_status_raw") or "").strip().lower()
    return stage_map.get(rec["registry"], {}).get(raw, "registered" if raw else "pipeline")


def country_shares(countries: list[str], in_scope: set[str], population: dict[str, float]) -> dict[str, float]:
    """Share of the project's volume attributed to each in-scope host country (population-weighted)."""
    if not countries:
        return {}
    weights = {c: population.get(c, 1.0) for c in countries}
    total = sum(weights.values()) or 1.0
    return {c: round(w / total, 6) for c, w in weights.items() if c in in_scope}


def build_projects() -> list[dict]:
    records = common.load_all_records()
    countries_cfg = common.load_yaml("countries.yaml")["countries"]
    in_scope = set(countries_cfg)
    stage_map = (common.load_yaml("stages.yaml").get("map") or {})
    mmap = load_methodology_map()
    population: dict[str, float] = {}  # M3: UN WPP 2024 (2025) from config/population.csv

    clusters: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        clusters[rec["record_id"]].append(rec)  # M3: union-find over cross-refs + fuzzy matches

    projects = []
    for members in clusters.values():
        members.sort(key=lambda r: r["record_id"])
        lead = members[0]
        countries = sorted({c for m in members for c in (m.get("countries") or [])})
        shares = country_shares(countries, in_scope, population)
        if not shares:
            continue
        stages = [stage_of(m, stage_map) for m in members]
        projects.append({
            "project_id": lead["record_id"],
            "display_name": lead.get("name") or lead["record_id"],
            "developer": lead.get("developer_raw"),
            "countries": countries,
            "country_shares": shares,
            "l2": classify(lead, mmap),
            "stage": max(stages, key=lambda s: STAGE_ORDER[s]),
            "registries": [{"record_id": m["record_id"], "registry": m["registry"], "url": m["registry_url"]} for m in members],
            "est_annual_tco2e": lead.get("est_annual_tco2e"),
            "issued_tco2e": sum(m.get("issued_tco2e") or 0 for m in members),
            "retired_tco2e": sum(m.get("retired_tco2e") or 0 for m in members),
            "issuance_by_vintage": lead.get("issuance_by_vintage") or {},
            "methodology_codes": sorted({c for m in members for c in (m.get("methodology_codes") or [])}),
            "crediting": [lead.get("crediting_start"), lead.get("crediting_end")],
            "article6": None,
            "offtakers": [],
            "project_url": None,
            "developer_url": None,
            "flags": (["multi_country"] if len(countries) > 1 else [])
            + (["retired_gt_issued"] if any((m.get("retired_tco2e") or 0) > (m.get("issued_tco2e") or 0) for m in members) else []),
        })
    projects.sort(key=lambda p: p["project_id"])
    return projects


def main() -> None:
    projects = build_projects()
    print(f"{len(projects)} projects from {len(common.load_all_records())} records")


if __name__ == "__main__":
    main()
