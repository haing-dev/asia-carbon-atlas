"""Turn stored registry records into deduplicated projects (in memory; never stored).

M0: classification, stages and clustering are minimal placeholders; M3 replaces them
with the methodology dictionary + keyword rules, cross-reference/fuzzy dedupe, and
population-weighted country shares (docs/SPEC.md §5–8).
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict

from pipeline import common, dedupe

STAGE_ORDER = {"inactive": 0, "announced": 0.5, "pipeline": 1, "registered": 2, "issuing": 3}


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
    if rec.get("l2_override"):
        return rec["l2_override"]
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


def load_population() -> dict[str, float]:
    """UN WPP 2024, 1 July 2025 (config/population.csv, written by pipeline.population)."""
    path = common.CONFIG / "population.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["iso3"]: float(r["population"]) for r in csv.DictReader(line for line in f if not line.startswith("#"))}


def share_countries(lead: dict, countries: list[str], cfg: dict) -> list[str]:
    """Host countries used for the map split: the lead record's hosts; if the project's name names exactly one of
    them (e.g. "Dagachhu Hydropower Project, Bhutan"), that country only."""
    hosts = [c for c in (lead.get("countries") or []) if c in countries] or countries
    if len(hosts) > 1:
        name = (lead.get("name") or "").lower()
        named = [c for c in hosts if c in cfg and re.search(r"\b" + re.escape(cfg[c]["name"].lower()) + r"\b", name)]
        if len(named) == 1:
            return named
    return hosts


def country_shares(countries: list[str], in_scope: set[str], population: dict[str, float]) -> dict[str, float]:
    """Share of the project's volume attributed to each in-scope host country (population-weighted)."""
    if not countries:
        return {}
    weights = {c: population.get(c, 1.0) for c in countries}
    total = sum(weights.values()) or 1.0
    return {c: round(w / total, 6) for c, w in weights.items() if c in in_scope}


# Which record supplies the display name / estimate when a project is in several registries.
LEAD_PRIORITY = {"VCS": 0, "GS": 0, "ISO": 0, "PURO": 0, "ACR": 0, "CAR": 0, "ART": 0, "GCC": 1, "UCR": 1, "PACM": 1, "JCM": 1, "A62": 1, "CDM": 2}


def merge_article6(items: list[dict]) -> dict | None:
    """Combine Article 6 tags from a project's records/annotations into one display value."""
    items = [a for a in items if a]
    if not items:
        return None
    mechs = sorted({a["mechanism"] for a in items})
    buyers = sorted({b for a in items for b in (a.get("buyer_countries") or [])})
    statuses = sorted({a["status"] for a in items if a.get("status")})
    itmos = sum(a.get("itmos_transferred") or 0 for a in items)
    return {"mechanism": " + ".join(mechs), "buyer_countries": buyers, "status": "; ".join(statuses),
            "itmos_transferred": itmos or None}


def cluster_records(records: list[dict], fuzzy: list[tuple[str, str, float]] | None = None) -> list[list[dict]]:
    """Union-find over explicit cross-registry references (SPEC §7.1), then fuzzy matches (§7.2).
    A fuzzy match never joins two clusters that already hold a record from the same registry."""
    ids = {r["record_id"] for r in records}
    parent = {i: i for i in ids}
    regs: dict[str, set[str]] = {r["record_id"]: ({r["registry"]} if r.get("role") != "annotation" else set()) for r in records}
    fuzzy_roots: set[str] = set()

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
            regs[rb] |= regs.pop(ra, set())
            if ra in fuzzy_roots:
                fuzzy_roots.discard(ra)
                fuzzy_roots.add(rb)
        return rb

    for r in records:
        for ref in r.get("cross_refs") or []:
            if ref in ids and ref != r["record_id"]:
                union(ref, r["record_id"])
    for a, b, _s in sorted(fuzzy or [], key=lambda x: -x[2]):
        ra, rb = find(a), find(b)
        if ra == rb or (regs.get(ra, set()) & regs.get(rb, set())):
            continue
        fuzzy_roots.add(union(a, b))
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[find(r["record_id"])].append(r)
    # Safety: never merge records whose country sets don't intersect.
    out = []
    for root, members in groups.items():
        if len(members) > 1 and not set.intersection(*(set(m.get("countries") or []) for m in members)):
            out.extend([m] for m in members)
        else:
            if root in fuzzy_roots:
                for m in members:
                    m["_fuzzy"] = True
            out.append(members)
    return out


def rollup(members: list[dict]) -> tuple[int, int, dict[str, int], bool]:
    """Issued/retired across registries (SPEC §7.3): a vintage year issued in two registries counts once (the max).
    Records without vintage detail add their totals as they are. Retired is capped at the rolled-up issued."""
    total = sum(m.get("issued_tco2e") or 0 for m in members)
    retired = sum(m.get("retired_tco2e") or 0 for m in members)
    years: dict[str, list[int]] = defaultdict(list)
    for m in members:
        for y, v in (m.get("issuance_by_vintage") or {}).items():
            if v:
                years[y].append(int(v))
    by_vintage = {y: max(v) for y, v in sorted(years.items())}
    # Each vintage year issued in more than one registry is counted once (the largest).
    dup = sum(sum(v) - max(v) for v in years.values() if len(v) > 1)
    overlap = dup > 0
    if overlap:
        smallest = min(m.get("issued_tco2e") or 0 for m in members if m.get("issuance_by_vintage"))
        dup = min(dup, smallest)
    issued = total - dup
    if len(members) > 1:
        retired = min(retired, issued)
    return issued, retired, by_vintage, overlap


def _min_year(members: list[dict], field: str) -> int | None:
    years = [int(str(m[field])[:4]) for m in members if m.get(field) and str(m[field])[:4].isdigit()]
    return min(years) if years else None


CDM_BUYER_RE = re.compile(r"([^,()]+?)\s*\(([^()]+)\)")
UNEP_CDM = "https://unepccc.org/cdm-ji-pipeline/"


def cdm_buyers(rec: dict) -> list[dict]:
    """'Switzerland (Vitol), United K. (EcoSecurities)' -> offtaker entries (UNEP-CCC 'Credit buyer' column)."""
    raw = rec.get("credit_buyer_raw")
    if rec["registry"] != "CDM" or not raw:
        return []
    out = []
    for country, name in CDM_BUYER_RE.findall(str(raw)):
        out.append({"name": name.strip(), "type": "CDM credit buyer", "country": country.strip(),
                    "source_url": UNEP_CDM, "source_title": "UNEP-CCC CDM Pipeline, 'Credit buyer' column"})
    return out


def _deal(d: dict) -> dict:
    return {"name": d["buyer"], "type": "Announced offtake", "date": str(d.get("date") or "") or None,
            "volume_tco2e": d.get("volume_tco2e"), "source_url": d["source_url"],
            "source_title": d.get("source_title"), "note": d.get("note")}


def load_offtakes() -> tuple[dict[str, list[dict]], list[dict]]:
    """config/offtakers.yaml -> (deals by record_id, pseudo-records for announced rows)."""
    cfg = common.load_yaml("offtakers.yaml") if (common.CONFIG / "offtakers.yaml").exists() else {}
    by_record: dict[str, list[dict]] = defaultdict(list)
    for d in cfg.get("offtakes") or []:
        by_record[d["record"]].append(_deal(d))
    rows = []
    for a in cfg.get("announced_rows") or []:
        deals = [_deal(d) for d in a.get("offtakes") or []]
        rows.append({
            "record_id": a["id"], "registry": "ANN", "native_id": a["id"].split(":", 1)[-1],
            "registry_url": deals[0]["source_url"] if deals else None, "name": a["name"],
            "developer_raw": a.get("developer"), "countries": a["countries"], "l2_override": a["l2"],
            "registry_status_raw": "announced", "issued_tco2e": 0, "retired_tco2e": 0, "_deals": deals,
        })
    return by_record, rows


def build_projects(write_review: bool = False) -> list[dict]:
    deals_by_record, announced = load_offtakes()
    records = common.load_all_records() + announced
    countries_cfg = common.load_yaml("countries.yaml")["countries"]
    in_scope = set(countries_cfg)
    stage_map = (common.load_yaml("stages.yaml").get("map") or {})
    mmap = load_methodology_map()
    rules = load_type_rules()
    today = common.today()
    population = load_population()

    taxonomy_l2 = common.load_yaml("taxonomy.yaml")["l2"]
    l2_cache = {r["record_id"]: classify(r, mmap, rules) for r in records}
    fuzzy, review = dedupe.fuzzy_links(records, lambda r: taxonomy_l2.get(l2_cache[r["record_id"]], {}).get("l1"))
    if write_review:
        dedupe.write_pending(review)
    clusters = cluster_records(records, fuzzy)

    projects = []
    for members in clusters:
        # Annotation records (e.g. Article 6.2 tags) only label the project they cross-reference;
        # they never add rows, volumes or registries.
        notes = [m for m in members if m.get("role") == "annotation"]
        members = [m for m in members if m.get("role") != "annotation"]
        if not members:
            continue
        members.sort(key=lambda r: (LEAD_PRIORITY.get(r["registry"], 9), r["record_id"]))
        lead = members[0]
        countries = sorted({c for m in members for c in (m.get("countries") or [])})
        shares = country_shares(share_countries(lead, countries, countries_cfg), in_scope, population)
        if not shares:
            continue
        stages = [stage_of(m, stage_map, today) for m in members]
        issued, retired, by_vintage, overlap = rollup(members)
        projects.append({
            "project_id": min(m["record_id"] for m in members),
            "display_name": next((m["name"] for m in members if m.get("name")), lead["record_id"]),
            "developer": next((m["developer_raw"] for m in members if m.get("developer_raw")), None),
            "countries": countries,
            "country_shares": shares,
            "l2": classify(lead, mmap, rules),
            "stage": max(stages, key=lambda s: STAGE_ORDER[s]),
            "registries": [{"record_id": m["record_id"], "registry": m["registry"], "url": m["registry_url"]} for m in members],
            "est_annual_tco2e": lead.get("est_annual_tco2e") or next((m.get("est_annual_tco2e") for m in members if m.get("est_annual_tco2e")), None),
            "issued_tco2e": issued,
            "retired_tco2e": retired,
            "issuance_by_vintage": by_vintage,
            "methodology_codes": sorted({c for m in members for c in (m.get("methodology_codes") or [])}),
            "crediting": [lead.get("crediting_start"), lead.get("crediting_end")],
            "years": {k: _min_year(members, f"{k}_date") for k in ("listed", "registered", "first_issuance")},
            "article6": merge_article6([m.get("article6") for m in members + notes]),
            "offtakers": sorted(sorted(
                [o for m in members for o in deals_by_record.get(m["record_id"], []) + m.get("_deals", [])]
                + [o for m in members for o in cdm_buyers(m)],
                key=lambda o: str(o.get("date") or ""), reverse=True), key=lambda o: o["type"] != "Announced offtake"),
            "project_url": None,
            "developer_url": None,
            "flags": (["multi_country"] if len(countries) > 1 else [])
            + (["multi_registry"] if len(members) > 1 else [])
            + (["name_match"] if any(m.get("_fuzzy") for m in members) else [])
            + (["vintage_overlap"] if overlap else [])
            + (["retired_gt_issued"] if any((m.get("retired_tco2e") or 0) > (m.get("issued_tco2e") or 0) for m in members) else []),
        })
    known = {r["record_id"] for r in records}
    for rid in deals_by_record:
        if rid not in known:
            print(f"WARNING offtakers.yaml: unknown record {rid}")
    projects.sort(key=lambda p: p["project_id"])
    return projects


def main() -> None:
    projects = build_projects(write_review=True)
    print(f"{len(projects)} projects from {len(common.load_all_records())} records")


if __name__ == "__main__":
    main()
