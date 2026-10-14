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


def load_tags() -> list[tuple]:
    """config/tags.yaml -> [(id, regex or None, allowed credit types or None, max MW or None)], in display order."""
    out = []
    for t in common.load_yaml("tags.yaml")["tags"]:
        out.append((t["id"], re.compile(t["re"], re.I) if t.get("re") else None, set(t["l2"]) if t.get("l2") else None,
                    t.get("max_mw")))
    return out


MW_X = re.compile(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*MW\b", re.I)
MW_1 = re.compile(r"(\d+(?:\.\d+)?)\s*MW\b", re.I)


def capacity_mw(rec: dict) -> float | None:
    """Installed capacity: the registry's own figure (CDM) or the one stated in the project name ("2 x 3.5 MW")."""
    if rec.get("mw"):
        return float(rec["mw"])
    name = str(rec.get("name") or "")
    m = MW_X.search(name)
    if m:
        return float(m.group(1)) * float(m.group(2))
    m = MW_1.search(name)
    return float(m.group(1)) if m else None


def tags_of(members: list[dict], l2: str, tags: list, overrides: dict | None = None) -> list[str]:
    """Tags whose regex matches any member record's own text (type | methodology | name | registry description),
    limited to the tag's credit types; broad tags (no regex) follow the project's credit type. A tag with `max_mw`
    also applies when the record's stated capacity is at most that (e.g. small hydro ≤ 25 MW)."""
    texts = [" | ".join(str(x or "") for x in (m.get("registry_type_raw"), " ".join(m.get("methodology_codes") or []),
                                                  m.get("methodology_raw"), m.get("name"), m.get("description")))
             for m in members]
    out = []
    for tid, rx, l2s, max_mw in tags:
        if l2s is not None and l2 not in l2s:
            continue
        if rx is None or any(rx.search(t) for t in texts):
            out.append(tid)
        elif max_mw and any((c := capacity_mw(m)) is not None and 0 < c <= max_mw for m in members):
            out.append(tid)
    if overrides:
        order = {t[0]: i for i, t in enumerate(tags)}
        for m in members:
            o = overrides.get(m["record_id"]) or {}
            out = [t for t in out if t not in (o.get("remove") or [])]
            out += [t for t in (o.get("add") or []) if t in order and t not in out]
        out.sort(key=order.get)
    return out


def load_tag_overrides() -> dict:
    path = common.CONFIG / "tag_overrides.yaml"
    return (common.load_yaml("tag_overrides.yaml").get("overrides") or {}) if path.exists() else {}


def stage_of(rec: dict, stage_map: dict, today: str) -> str:
    """Issuing whenever anything has been issued (credits exist even if the project later became inactive);
    otherwise the registry status mapped by config/stages.yaml; registered with the crediting period over and
    nothing issued counts as inactive."""
    if (rec.get("issued_tco2e") or 0) > 0:
        return "issuing"
    raw = str(rec.get("registry_status_raw") or "").strip().lower()
    mapped = stage_map.get(rec["registry"], {}).get(raw)
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


def _known_sum(values) -> int | None:
    vals = [v for v in values if v is not None]
    return sum(vals) if vals else None


def rollup(members: list[dict]) -> tuple[int | None, int | None, dict[str, int], bool]:
    """Issued/retired for one project (SPEC §7.3).
    Records in the same registry (programme + its activities) are added up. Across registries the same project is
    listed twice, so a vintage year issued in more than one registry counts once (the largest). Records without
    vintage detail add their totals as they are. None = no source reports the figure."""
    total = _known_sum(m.get("issued_tco2e") for m in members)
    retired = _known_sum(m.get("retired_tco2e") for m in members)
    by_reg: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    reg_total: dict[str, int] = defaultdict(int)
    for m in members:
        reg_total[m["registry"]] += m.get("issued_tco2e") or 0
        for y, v in (m.get("issuance_by_vintage") or {}).items():
            if v:
                by_reg[m["registry"]][y] += int(v)
    years = sorted({y for reg in by_reg.values() for y in reg})
    by_vintage = {y: max(reg.get(y, 0) for reg in by_reg.values()) for y in years}
    dup = sum(sum(reg.get(y, 0) for reg in by_reg.values()) - by_vintage[y] for y in years)
    overlap = dup > 0
    if overlap and total is not None:
        # Never deduct more than everything outside the largest registry.
        dup = min(dup, total - max(reg_total.values()))
        total -= dup
    if retired is not None and total is not None and len(reg_total) > 1:
        retired = min(retired, total)
    return total, retired, by_vintage, overlap


def estimate(members: list[dict]) -> int | None:
    """Estimated annual volume: one registry's figure (the lead registry's, else the next that has one), never a
    sum across registries (the same project listed twice). Within one registry, a programme's activities
    (VPAs/CPAs) add up; the programme's own figure is used instead when it is larger. Other same-registry
    duplicates take the largest figure."""
    order: list[str] = []
    for m in members:
        if m["registry"] not in order:
            order.append(m["registry"])
    for reg in order:
        recs = [m for m in members if m["registry"] == reg and m.get("est_annual_tco2e")]
        if not recs:
            continue
        acts = [m for m in recs if m.get("poa_id") and str(m["poa_id"]) != str(m.get("native_id"))]
        if acts:
            umbrella = max((int(m["est_annual_tco2e"]) for m in recs if m not in acts), default=0)
            return max(umbrella, sum(int(m["est_annual_tco2e"]) for m in acts))
        return max(int(m["est_annual_tco2e"]) for m in recs)
    return None


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


GS_PAGE = "https://registry.goldstandard.org/projects/details/{}"
GS_DOCS = "https://assurance-platform.goldstandard.org/project-documents/GS{}"


def fix_gs_links(records: list[dict]) -> list[dict]:
    """Gold Standard registry pages are addressed by an internal id, not the GS number the sources use.
    Link each GS record to its registry page via data/lookups/gsreg.jsonl; without a mapping, link GS's own
    project-documents page for that GS number. Cross-refs to registry pages ("GSREG:<page id>") become GS numbers.
    Also attaches the registry's project description (used only for tags)."""
    rows = common.read_jsonl(common.ROOT / "data" / "lookups" / "gsreg.jsonl")
    page = {r["record_id"]: r["registry_id"] for r in rows}
    desc = {r["record_id"]: r.get("description") for r in rows if r.get("description")}
    gs_of_page = {v: k for k, v in page.items()}
    for r in records:
        if r.get("registry") == "GS":
            pid = page.get(r["record_id"])
            r["registry_url"] = GS_PAGE.format(pid) if pid else GS_DOCS.format(r["native_id"])
            if r["record_id"] in desc:
                r["description"] = desc[r["record_id"]]
        if any(c.startswith("GSREG:") for c in r.get("cross_refs") or []):
            r["cross_refs"] = [gs_of_page.get(c[6:], c) if c.startswith("GSREG:") else c for c in r["cross_refs"]]
    return records


def build_projects(write_review: bool = False) -> list[dict]:
    deals_by_record, announced = load_offtakes()
    records = fix_gs_links(common.load_all_records()) + announced
    countries_cfg = common.load_yaml("countries.yaml")["countries"]
    in_scope = set(countries_cfg)
    stage_map = (common.load_yaml("stages.yaml").get("map") or {})
    mmap = load_methodology_map()
    rules = load_type_rules()
    today = common.today()
    population = load_population()
    tag_rules = load_tags()
    tag_overrides = load_tag_overrides()

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
            "l2": l2_cache[lead["record_id"]],
            "tags": tags_of(members, l2_cache[lead["record_id"]], tag_rules, tag_overrides),
            "stage": max(stages, key=lambda s: STAGE_ORDER[s]),
            "registries": [{"record_id": m["record_id"], "registry": m["registry"], "url": m["registry_url"]} for m in members],
            "est_annual_tco2e": estimate(members),
            "issued_tco2e": issued,
            "retired_tco2e": retired,
            "issuance_by_vintage": by_vintage,
            "methodology_codes": sorted({c for m in members for c in (m.get("methodology_codes") or [])}),
            "crediting": [lead.get("crediting_start"), lead.get("crediting_end")],
            "years": {k: _min_year(members, f"{k}_date") for k in ("listed", "registered", "first_issuance")},
            "article6": merge_article6([m.get("article6") for m in members + notes]),
            # Offtakers = publicly announced deals only (each linked to the announcement).
            "offtakers": sorted([o for m in members for o in deals_by_record.get(m["record_id"], []) + m.get("_deals", [])],
                                key=lambda o: str(o.get("date") or ""), reverse=True),
            # The UNEP-CCC "Credit buyer" column is not shown: it mixes Annex I participants, traders and even host
            # companies (e.g. CDM 1 lists the Indian project owner), and no public page confirms a purchase.
            "cdm_buyers": [o for m in members for o in cdm_buyers(m)],
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
