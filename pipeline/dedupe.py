"""Fuzzy matching of the same project across registries when they don't cross-reference each other (SPEC §7.2).

Blocking: same country set overlap + same broad credit type (L1); only records from different registries are compared.
Score (0–1) = name similarity (rapidfuzz) + small bonuses for equal capacity (MW), developer, state and methodology.
A capacity mismatch (both names state MW and none agree) is a hard "no".
- score ≥ 0.90: merge.
- 0.70–0.90: merge only if capacity and developer both agree; otherwise listed in review/dedupe_pending.csv.
Owner decisions in review/dedupe_decisions.csv (id = "A|B", decision = yes/no) always win.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict

from rapidfuzz import fuzz

from pipeline import common

AUTO = 0.90
REVIEW = 0.70
STOP = set("""
project projects programme program power plant plants the of in at by and for with from to a an on
ltd limited pvt private co company ms corporation inc llc plc jsc group india indian
indonesia thailand pakistan bangladesh philippines cambodia lao laos nepal sri lanka myanmar mongolia vietnam
malaysia china republic district state province village
bundled grid connected grid-connected based activity cdm vcs gs gold standard verra gcc ucr bundled
scale small large mw kw mwp mwac mwdc capacity installed total
""".split())
# Words that describe the technology or place rather than identify a project.
GENERIC = set("""
wind solar energy hydro hydropower hydroelectric hydel renewable electricity generation generating farm farms
photovoltaic pv spv biomass biogas bio cook stove stoves cookstove cookstoves improved efficient efficiency
distribution water heater heaters waste heat recovery rooftop roof mini micro run river canal top interactive
emission emissions reduction reductions clean green new unit units phase stage expansion extension wtg wtgs
states various multiple cer cers conversion vcu vcus cpa vpa poa precdmver ver vers
""".split())
# Place and direction words: shared ones don't identify a project, but different ones separate two projects.
PLACES = set("""
gujarat maharashtra tamil nadu tamilnadu karnataka rajasthan andhra pradesh madhya uttar himachal arunachal telangana
kerala punjab haryana odisha orissa bihar jharkhand chhattisgarh uttarakhand sikkim assam bengal goa
west east north south central southern northern eastern western
""".split())
TECH = {"wind": "wind", "solar": "solar", "spv": "solar", "photovoltaic": "solar", "pv": "solar", "hydro": "hydro",
        "hydropower": "hydro", "hydroelectric": "hydro", "hydel": "hydro", "biomass": "biomass", "bagasse": "biomass",
        "biogas": "biogas", "landfill": "landfill", "cookstove": "stove", "cookstoves": "stove", "stove": "stove",
        "stoves": "stove", "geothermal": "geo", "rice": "rice"}
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11, "xii": 12}
MW_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(MW|MWp|MWac|MWdc|KW|kWp)\b", re.I)
DECISIONS = common.ROOT / "review" / "dedupe_decisions.csv"
PENDING = common.ROOT / "review" / "dedupe_pending.csv"


def norm_name(name: str | None) -> str:
    name = re.sub(r"\bGS\d+\b|\bVPA\s*\d+\b|\bCPA\s*\d+\b", " ", name or "", flags=re.I)
    s = re.sub(r"\d+(?:\.\d+)?\s*(mw|mwp|mwac|mwdc|kw|kwp)\b", " ", name.lower())
    s = re.sub(r"viet\s*nam", "vietnam", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\bhydro (power|electric)\b", "hydro", s)
    syn = {"hydropower": "hydro", "hydroelectric": "hydro", "hydel": "hydro", "cookstove": "stove", "cookstoves": "stove",
           "stoves": "stove", "farms": "farm", "photovoltaic": "pv", "spv": "pv"}
    return " ".join(syn.get(t, t) for t in s.split() if t not in STOP and not t.isdigit())


def distinct(n: str) -> set[str]:
    return {t for t in n.split() if t not in GENERIC and t not in PLACES and len(t) > 1}


def places(n: str) -> set[str]:
    return {t for t in n.split() if t in PLACES}


def techs(n: str) -> set[str]:
    return {TECH[t] for t in n.split() if t in TECH}


def ordinals(name: str | None) -> set[int]:
    """Phase/unit numbers in a name (digits or roman numerals), excluding capacities."""
    s = re.sub(r"\bGS\d+\b|\bVPA\s*\d+\b|\bCPA\s*\d+\b", " ", name or "", flags=re.I)
    s = MW_RE.sub(" ", s.lower())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    out = set()
    for t in s.split():
        if t.isdigit() and len(t) <= 3:
            out.add(int(t))
        elif t in ROMAN:
            out.add(ROMAN[t])
    return out


def capacities(rec: dict) -> set[float]:
    out = set()
    for v, unit in MW_RE.findall(rec.get("name") or ""):
        x = float(v) / (1000 if unit.lower().startswith("k") else 1)
        if x > 0:
            out.add(round(x, 2))
    try:
        if rec.get("mw"):
            out.add(round(float(rec["mw"]), 2))
    except (TypeError, ValueError):
        pass
    return out


def _cap_match(a: set[float], b: set[float]) -> bool | None:
    if not a or not b:
        return None
    return any(abs(x - y) <= 0.02 * max(x, y) for x in a for y in b)


def _tokens(s: str | None) -> set[str]:
    return {t for t in re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split() if t not in STOP and len(t) > 2}


def _by_part(name: str | None) -> set[str]:
    m = re.search(r"\bby\b(.*)", (name or "").lower())
    return distinct(norm_name(m.group(1))) if m else set()


def prepare(r: dict) -> None:
    """Pre-compute everything the pair score needs, once per record."""
    n = norm_name(r.get("name"))
    r["_n"], r["_cap"], r["_ord"], r["_d"] = n, capacities(r), ordinals(r.get("name")), distinct(n)
    r["_pl"], r["_te"] = places(n), techs(n)
    r["_dev"] = _tokens(r.get("developer_raw"))
    r["_by"] = _by_part(r.get("name"))
    r["_bundle"] = "bundle" in (r.get("name") or "").lower()
    st = str(r.get("state_raw") or "").strip().lower()
    r["_st"] = st or None
    r["_meth"] = set(r.get("methodology_codes") or [])


def score(a: dict, b: dict) -> tuple[float, dict]:
    na, nb = a["_n"], b["_n"]
    if not na or not nb:
        return 0.0, {}
    cap = _cap_match(a["_cap"], b["_cap"])
    if cap is False:
        return 0.0, {"cap": False}
    if a["_ord"] != b["_ord"]:
        return 0.0, {"ord": False}
    pa, pb = a["_pl"], b["_pl"]
    if pa and pb and pa != pb:
        return 0.0, {"place": False}
    ta, tb = a["_te"], b["_te"]
    if ta and tb and not (ta & tb):
        return 0.0, {"tech": False}
    dev = bool(a["_dev"] & b["_dev"])
    da, db = a["_d"], b["_d"]
    if not da or not db:
        # Generic names ("Wind Power Project in Gujarat") never auto-merge; capacity + developer can only send them to review.
        return (0.8 if cap and dev else 0.0), {"generic": True, "cap": cap, "dev": dev}
    jacc = len(da & db) / len(da | db)
    name = 0.5 * fuzz.token_sort_ratio(na, nb) / 100 + 0.5 * jacc
    state = bool(a["_st"] and a["_st"] == b["_st"])
    meth = bool(a["_meth"] & b["_meth"])
    s = name + (0.10 if cap else 0) + (0.05 if dev else 0) + (0.03 if state else 0) + (0.02 if meth else 0)
    if cap is None and da <= a["_by"] and db <= b["_by"]:
        s = min(s, 0.85)  # only the developer's name identifies the project, and capacity can't confirm it
    if a["_bundle"] != b["_bundle"]:
        s = min(s, 0.85)  # a bundle vs a single plant: never auto-merged
    return min(1.0, round(s, 3)), {"name": round(name, 3), "cap": cap, "dev": dev, "state": state, "meth": meth}


def candidate_pairs(block: list[dict]):
    """Pairs that can score >= REVIEW. A pair with no distinctive name token in common has a name score <= 0.5 and
    can't get there, except two generic names that share a developer (the capacity + developer path). So only
    pairs sharing a distinctive token, or a developer token where one name is generic, are compared."""
    by_tok: dict[str, list[int]] = defaultdict(list)
    by_dev: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(block):
        for t in r["_d"]:
            by_tok[t].append(i)
        for t in r["_dev"]:
            by_dev[t].append(i)
    seen: set[tuple[int, int]] = set()
    for ids in by_tok.values():
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                seen.add((ids[x], ids[y]))
    for i, r in enumerate(block):
        if r["_d"]:
            continue
        for t in r["_dev"]:
            for j in by_dev[t]:
                if j != i:
                    seen.add((min(i, j), max(i, j)))
    for i, j in seen:
        a, b = block[i], block[j]
        if a["registry"] != b["registry"]:
            yield a, b


def load_decisions() -> dict[str, str]:
    if not DECISIONS.exists():
        return {}
    with open(DECISIONS, encoding="utf-8") as f:
        return {r["id"]: (r.get("decision") or "").strip().lower() for r in csv.DictReader(f) if r.get("id")}


def pair_id(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


def fuzzy_links(records: list[dict], l1_of) -> tuple[list[tuple[str, str, float]], list[dict]]:
    """Return (pairs to merge with score, pairs for review)."""
    decisions = load_decisions()
    blocks: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        if r.get("role") == "annotation" or r["registry"] in ("A62", "PACM", "ANN"):
            continue
        prepare(r)
        for c in r.get("countries") or []:
            blocks[(c, l1_of(r))].append(r)
    cands, review, seen = [], [], set()
    merge: list[tuple[str, str, float]] = []
    for block in blocks.values():
        if len(block) < 2:
            continue
        for a, b in candidate_pairs(block):
            pid = pair_id(a["record_id"], b["record_id"])
            if pid in seen:
                continue
            seen.add(pid)
            d = decisions.get(pid)
            if d in ("yes", "no"):
                if d == "yes":
                    merge.append((a["record_id"], b["record_id"], 1.0))
                continue
            s, why = score(a, b)
            if s >= REVIEW:
                cands.append((a, b, s, why))
    ids = {r["record_id"] for r in records}
    for pid, d in decisions.items():
        a, _, b = pid.partition("|")
        if d == "yes" and a in ids and b in ids and pid not in seen:
            merge.append((a, b, 1.0))
    # A match must be unambiguous: each record's best candidate in the other registry, clearly ahead of the runner-up.
    best: dict[tuple[str, str], list[float]] = defaultdict(list)
    for a, b, s, _ in cands:
        best[(a["record_id"], b["registry"])].append(s)
        best[(b["record_id"], a["registry"])].append(s)
    for k in best:
        best[k].sort(reverse=True)

    def clear(rid: str, other_reg: str, s: float) -> bool:
        lst = best[(rid, other_reg)]
        return lst[0] == s and (len(lst) == 1 or lst[0] - lst[1] >= 0.03)

    for a, b, s, why in cands:
        unique = clear(a["record_id"], b["registry"], s) and clear(b["record_id"], a["registry"], s)
        ok = s >= AUTO or (why.get("cap") and why.get("dev") and not why.get("generic"))
        if ok and unique:
            merge.append((a["record_id"], b["record_id"], s))
        else:
            review.append({"id": pair_id(a["record_id"], b["record_id"]), "score": s,
                           "a_name": a.get("name"), "b_name": b.get("name"), **why})
    return merge, review


def write_pending(review: list[dict]) -> None:
    """Pairs in the review band, for the owner (or the monthly enrichment task) to decide. Only rewritten when changed."""
    fields = ["id", "score", "a_name", "b_name", "name", "cap", "dev", "state", "meth"]
    rows = sorted(review, key=lambda r: -r["score"])
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    text = buf.getvalue()
    if not PENDING.exists() or PENDING.read_text(encoding="utf-8") != text:
        PENDING.write_text(text, encoding="utf-8")
