"""Turn stored registry records into deduplicated projects (in memory; never stored).

M0: classification, stages and clustering are minimal placeholders; M3 replaces them
with the methodology dictionary + keyword rules, cross-reference/fuzzy dedupe, and
population-weighted country shares (docs/SPEC.md §5–8).
"""
from __future__ import annotations

import csv
import re
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


def load_type_rules() -> list[tuple[re.Pattern, str]]:
    rules = common.load_yaml("type_rules.yaml")["rules"]
    return [(re.compile(r["re"], re.I), r["l2"]) for r in rules]


def classify(rec: dict, mmap: dict, rules: list) -> str:
    """Methodology dictionary first, then ordered regex rules over type/methodology/name."""
    for code in rec.get("methodology_codes") or []:
        c = code.strip().upper()
        l2 = mmap.get((rec["registry"], c)) or mmap.get(("*", c))
        if l2:
            return l2
    text = " | ".join(str(x or "") for x in (
        rec.get("registry_type_raw"), " ".join(rec.get("methodology_codes") or []),
        rec.get("methodology_raw"), rec.get("name")))
    for rx, l2 in rules:
        if rx.search(text):
            return l2
    return "other"


def stage_of(rec: dict, stage_map: dict, today: str) -> str:
    raw = str(rec.get("registry_status_raw") or "").strip().lower()
    mapped = stage_map.get(rec["registry"], {}).get(raw)
    if mapped == "inactive":
        return "inactive"
    if (rec.get("issued_tco2e") or 0) > 0:
        return "issuing"
    if mapped is None:
        mapped = "registered" if raw else "pipeline"
    end = rec.get("crediting_end")
    if mapped == "registered" and end and end < today:
        return "inactive"
    return mapped


def country_shares(countries: list[str], in_scope: set[str], population: dict[str, float]) -> dict[str, float]:
    """Share of the project's volume attributed to each in-scope host country (population-weighted)."""
    if not countries:
        return {}
    weights = {c: population.get(c, 1.0) for c in countries}
    total = sum(weights.values()) or 1.0
    return {c: round(w / total, 6) for c, w in weights.items() if c in in_scope}


# Which record supplies the display name / estimate when a project is in several registries.
LEAD_PRIORITY = {"VCS": 0, "GS": 0, "ISO": 0, "PURO": 0, "GCC": 1, "UCR": 1, "PACM": 1, "JCM": 1, "CDM": 2}


def cluster_records(records: list[dict]) -> list[list[dict]]:
    """Union-find over explicit cross-registry references (docs/SPEC.md §7.1).
    Fuzzy matching for records without references is added in M3."""
    ids = {r["record_id"] for r in records}
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in records:
        for ref in r.get("cross_refs") or []:
            if ref in ids and ref != r["record_id"]:
                parent[find(ref)] = find(r["record_id"])
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[find(r["record_id"])].append(r)
    # Safety: never merge records whose country sets don't intersect.
    out = []
    for members in groups.values():
        if len(members) > 1 and not set.intersection(*(set(m.get("countries") or []) for m in members)):
            out.extend([m] for m in members)
        else:
            out.append(members)
    return out


def build_projects() -> list[dict]:
    records = common.load_all_records()
    countries_cfg = common.load_yaml("countries.yaml")["countries"]
    in_scope = set(countries_cfg)
    stage_map = (common.load_yaml("stages.yaml").get("map") or {})
    mmap = load_methodology_map()
    rules = load_type_rules()
    today = common.today()
    population: dict[str, float] = {}  # M3: UN WPP 2024 (2025) from config/population.csv

    clusters = cluster_records(records)

    projects = []
    for members in clusters:
        members.sort(key=lambda r: (LEAD_PRIORITY.get(r["registry"], 9), r["record_id"]))
        lead = members[0]
        countries = sorted({c for m in members for c in (m.get("countries") or [])})
        shares = country_shares(countries, in_scope, population)
        if not shares:
            continue
        stages = [stage_of(m, stage_map, today) for m in members]
        projects.append({
            "project_id": min(m["record_id"] for m in members),
            "display_name": lead.get("name") or lead["record_id"],
            "developer": lead.get("developer_raw"),
            "countries": countries,
            "country_shares": shares,
            "l2": classify(lead, mmap, rules),
            "stage": max(stages, key=lambda s: STAGE_ORDER[s]),
            "registries": [{"record_id": m["record_id"], "registry": m["registry"], "url": m["registry_url"]} for m in members],
            "est_annual_tco2e": lead.get("est_annual_tco2e") or next((m.get("est_annual_tco2e") for m in members if m.get("est_annual_tco2e")), None),
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
            + (["multi_registry"] if len(members) > 1 else [])
            + (["retired_gt_issued"] if any((m.get("retired_tco2e") or 0) > (m.get("issued_tco2e") or 0) for m in members) else []),
        })
    projects.sort(key=lambda p: p["project_id"])
    return projects


def main() -> None:
    projects = build_projects()
    print(f"{len(projects)} projects from {len(common.load_all_records())} records")


if __name__ == "__main__":
    main()
