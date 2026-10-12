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
from itertools import combinations

from rapidfuzz import fuzz

from pipeline import common

AUTO = 0.90
REVIEW = 0.70
STOP = set("""
project projects programme program power plant plants the of in at by and for with from to a an on
ltd limited pvt private co company ms corporation inc llc plc jsc group india indian vietnam viet nam
indonesia thailand pakistan bangladesh philippines cambodia lao laos nepal sri lanka myanmar mongolia
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
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(t for t in s.split() if t not in STOP and not t.isdigit())


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


def score(a: dict, b: dict) -> tuple[float, dict]:
    na, nb = a["_n"], b["_n"]
    if not na or not nb:
        return 0.0, {}
    cap = _cap_match(a["_cap"], b["_cap"])
    if cap is False:
        return 0.0, {"cap": False}
    if a["_ord"] != b["_ord"]:
        return 0.0, {"ord": False}
    pa, pb = places(na), places(nb)
    if pa and pb and pa != pb:
        return 0.0, {"place": False}
    ta, tb = techs(na), techs(nb)
    if ta and tb and not (ta & tb):
        return 0.0, {"tech": False}
    dev = bool(_tokens(a.get("developer_raw")) & _tokens(b.get("developer_raw")))
    da, db = a["_d"], b["_d"]
    if not da or not db:
        # Generic names ("Wind Power Project in Gujarat") never auto-merge; capacity + developer can only send them to review.
        return (0.8 if cap and dev else 0.0), {"generic": True, "cap": cap, "dev": dev}
    jacc = len(da & db) / len(da | db)
    name = 0.5 * fuzz.token_sort_ratio(na, nb) / 100 + 0.5 * jacc
    state = bool(a.get("state_raw") and b.get("state_raw") and
                 str(a["state_raw"]).strip().lower() == str(b["state_raw"]).strip().lower())
    meth = bool(set(a.get("methodology_codes") or []) & set(b.get("methodology_codes") or []))
    s = name + (0.10 if cap else 0) + (0.05 if dev else 0) + (0.03 if state else 0) + (0.02 if meth else 0)
    by_a, by_b = _by_part(a.get("name")), _by_part(b.get("name"))
    if cap is None and da <= by_a and db <= by_b:
        s = min(s, 0.85)  # only the developer's name identifies the project, and capacity can't confirm it
    if ("bundle" in (a.get("name") or "").lower()) != ("bundle" in (b.get("name") or "").lower()):
        s = min(s, 0.85)  # a bundle vs a single plant: never auto-merged
    return min(1.0, round(s, 3)), {"name": round(name, 3), "cap": cap, "dev": dev, "state": state, "meth": meth}


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
        if r.get("role") == "annotation" or r["registry"] in ("A62", "PACM"):
            continue
        r["_n"], r["_cap"], r["_ord"] = norm_name(r.get("name")), capacities(r), ordinals(r.get("name"))
        r["_d"] = distinct(r["_n"])
        for c in r.get("countries") or []:
            blocks[(c, l1_of(r))].append(r)
    cands, review, seen = [], [], set()
    merge: list[tuple[str, str, float]] = []
    for block in blocks.values():
        if len(block) < 2:
            continue
        for a, b in combinations(block, 2):
            if a["registry"] == b["registry"]:
                continue
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
