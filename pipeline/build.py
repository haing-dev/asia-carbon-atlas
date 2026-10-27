"""Build website data files into web/public/data (docs/SPEC.md §9.2).

- meta.json            tiny, not cached: data-as-of, source health, hashed file names
- index.<hash>.json    compact columnar fields for map + filters (all projects)
- rows/<ISO3>.<hash>.json  display fields per country, loaded on demand
"""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict

from pipeline import common
from pipeline.process import STAGE_ORDER, build_projects

AREAS = {
    "asia": {"label": "Asia", "scope": "Asia, excluding mainland China"},
    "north_america": {"label": "North America", "scope": "North America, Central America and the Caribbean"},
    "south_america": {"label": "South America", "scope": "South America"},
    "africa": {"label": "Africa", "scope": "Africa"},
    "europe": {"label": "Europe", "scope": "Europe, including Turkey, the Caucasus and Russia"},
}
SUMMARY = {"id": "all", "label": "All Regions", "scope": "all regions covered"}
STAGES = ["pipeline", "registered", "issuing", "inactive", "announced"]
REGISTRY_LABELS = {
    "VCS": "Verra (VCS)", "GS": "Gold Standard", "CDM": "CDM", "PACM": "Article 6.4 (PACM)",
    "GCC": "Global Carbon Council", "UCR": "Universal Carbon Registry", "PURO": "Puro.earth",
    "ISO": "Isometric", "JCM": "JCM (Japan)", "A62": "Article 6.2 (bilateral)",
    "ANN": "Announcement only, unregistered yet",
    "ACR": "American Carbon Registry", "CAR": "Climate Action Reserve", "ART": "ART TREES",
}
REGISTRIES = list(REGISTRY_LABELS)
REGISTRY_GROUP = {"VCS": "Independent standards", "GS": "Independent standards", "ISO": "Independent standards",
                  "PURO": "Independent standards", "GCC": "Independent standards", "UCR": "Independent standards",
                  "CDM": "Government & UN mechanisms", "PACM": "Government & UN mechanisms",
                  "JCM": "Government & UN mechanisms", "A62": "Government & UN mechanisms",
                  "ANN": "Announcements", "ACR": "Independent standards", "CAR": "Independent standards",
                  "ART": "Independent standards"}


def load_notes() -> list[dict]:
    """content/notes.md -> [{key, points}] (owner-editable footnotes)."""
    path = common.ROOT / "content" / "notes.md"
    if not path.exists():
        return []
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    notes = []
    for line in text.splitlines():
        if line.startswith("## "):
            head = line[3:].strip()
            key, _, title = head.partition(":") if ":" in head else (head.split()[0], "", "")
            notes.append({"key": key.strip().lower(), "title": title.strip() or key.strip().capitalize(), "points": []})
        elif line.lstrip().startswith("- ") and notes:
            notes[-1]["points"].append(line.lstrip()[2:].strip())
        elif line.strip() and notes and notes[-1]["points"]:
            notes[-1]["points"][-1] += " " + line.strip()  # wrapped bullet
    return [n for n in notes if n["points"]]


# Registry links the browser can rebuild from the record id ({id} = the part after "REG:"); rows omit such links.
URL_TEMPLATES = {
    "VCS": "https://registry.verra.org/verra/public/program/VCS/projects/{id}",
    "CAR": "https://thereserve2.apx.com/mymodule/reg/prjView.asp?id1={id}",
    "ACR": "https://greentrace.ice.com/acr/projects",
    "ART": "https://greentrace.ice.com/art/projects",
    "PURO": "https://registry.puro.earth/projects/{id}",
    "JCM": "https://www.jcm.go.jp/jc/projects/{lid}/",
    "GCC": "https://gcc2.globalcarboncouncil.com/search/registration",
}
UNEP_CDM = "https://unepccc.org/cdm-ji-pipeline/"


def _template_url(record_id: str) -> str | None:
    reg, _, native = record_id.partition(":")
    t = URL_TEMPLATES.get(reg)
    return t.format(id=native, lid=native.lower()) if t else None


ELIG = common.load_yaml("eligibility.yaml")["labels"]


def eligibility_mask(p: dict) -> int:
    """Bitmask of config/eligibility.yaml labels that apply to the project (bit i = labels[i])."""
    mask = 0
    a6 = (p.get("article6") or {}).get("mechanism") or ""
    for i, lab in enumerate(ELIG):
        hit = any(m in a6 for m in lab.get("article6") or [])
        hit = hit or any(re.search(rx, st, re.I) for rx in lab.get("status") or [] for st in p.get("statuses") or [])
        if lab.get("a6_status") and p.get("article6"):
            hit = hit or any(re.search(rx, p["article6"].get("status") or "", re.I) for rx in lab["a6_status"])
        for reg, rxs in (lab.get("methodology") or {}).items():
            if any(r["registry"] == reg for r in p["registries"]):
                hit = hit or any(re.search(rx, c) for rx in rxs for c in p.get("methodology_codes") or [])
        for reg, rxs in (lab.get("methodology_name") or {}).items():
            if any(r["registry"] == reg for r in p["registries"]):
                hit = hit or any(re.search(rx, c, re.I) for rx in rxs for c in p.get("methodology_names") or [])
        if hit:
            mask |= 1 << i
    return mask


TAGS = common.load_yaml("tags.yaml")["tags"]
TAG_INDEX = {t["id"]: i for i, t in enumerate(TAGS)}


RET_BY_PROJECT: dict = {}   # set in main(): {project_id: {beneficiary: [t, first, last]}}
CANON = lambda n: n         # set in main(): buyer name -> canonical entity


def compact_row(p: dict) -> dict:
    """Display row for the browser, without empty fields or anything the browser can rebuild
    (see web/src/lib/data.js hydrateRow)."""
    row = {"id": p["project_id"], "n": p["display_name"], "c": p["countries"],
           "rg": [r["record_id"] if r["url"] == _template_url(r["record_id"]) else [r["record_id"], r["url"]]
                  for r in p["registries"]]}
    if p.get("developer"):
        row["d"] = p["developer"]
    if p.get("tags"):
        row["t"] = [TAG_INDEX[t] for t in p["tags"]]
    if len(p["countries"]) > 1:
        row["sh"] = p["country_shares"]
    y = [p["years"].get(k) for k in ("listed", "registered", "first_issuance")]
    if any(y):
        row["y"] = y
    for key, val in (("v", p.get("issuance_by_vintage")), ("m", p.get("methodology_codes")), ("a6", p.get("article6")),
                     ("f", p.get("flags")), ("pu", p.get("project_url")), ("du", p.get("developer_url"))):
        if val:
            row[key] = val
    if any(p.get("crediting") or []):
        row["cr"] = p["crediting"]
    offs = [{k: v for k, v in o.items() if v not in (None, "")} for o in p.get("offtakers") or []]
    if offs:
        row["o"] = offs
    rb = RET_BY_PROJECT.get(p["project_id"]) or {}
    named = defaultdict(float)
    for b, v in rb.items():
        if b:
            named[CANON(b)] += v[0]
    named = sorted(named.items(), key=lambda x: -x[1])
    if named:   # largest named retirement beneficiaries (registry records via OffsetsDB), then the unnamed remainder
        row["rb"] = [[b, round(t)] for b, t in named[:6]] + ([["", round(rb[None][0])]] if rb.get(None) else [])
    return row


def country_name(iso: str, cfg: dict) -> str:
    if iso in cfg:
        return cfg[iso]["name"]
    import pycountry
    c = pycountry.countries.get(alpha_3=iso)
    return getattr(c, "common_name", None) or (c.name if c else iso)


def source_date(sid: str, state: dict) -> str | None:
    """Date of the data at the source: a release/version date where the source publishes one, otherwise the date we
    last read the live registry (or imported the export)."""
    sig = state.get("signal") or {}
    if sid == "vrod" and sig.get("version"):
        return sig["version"]                                     # VROD release, e.g. 2026-08
    if sid == "cdm":
        m = re.search(r"/uploads/(\d{4})/(\d{2})/", sig.get("url") or "")
        if m:
            return f"{m.group(1)}-{m.group(2)}"                    # UNEP-CCC workbook upload month
    if sid == "gcc":
        return (state.get("last_changed") or "")[:10] or None     # date the owner's export was imported
    return (state.get("last_checked") or "")[:10] or None         # live registry, read on this date


def _write_hashed(dirpath, stem: str, obj) -> str:
    text = common.dumps(obj)
    h = common.sha256_bytes(text.encode())[:10]
    name = f"{stem}.{h}.json"
    (dirpath / name).write_text(text, encoding="utf-8")
    return name


def _canon():
    """Buyer name -> canonical entity (config/buyers.yaml names + aliases, offtakers.yaml buyer_aliases)."""
    ocfg = common.load_yaml("offtakers.yaml")
    bcfg = common.load_yaml("buyers.yaml") if (common.ROOT / "config" / "buyers.yaml").exists() else {}
    canon = {}
    for b in bcfg.get("buyers") or []:
        canon[b["name"].lower()] = b["name"]
        for a in b.get("aliases") or []:
            canon[a.lower()] = b["name"]
    for k, v in (ocfg.get("buyer_aliases") or {}).items():
        canon.setdefault(k.lower(), canon.get(v.lower(), v))
    exclude = [re.compile(x) for x in bcfg.get("exclude_beneficiaries") or []]
    return (lambda n: canon.get(n.lower(), n)), ocfg.get("buyer_splits") or {}, exclude


def _is_government():
    g = (common.load_yaml("buyers.yaml") or {}).get("government") or {}
    names = set(g.get("names") or [])
    pats = [re.compile(x) for x in g.get("patterns") or []]
    return lambda n: n in names or any(p.search(n) for p in pats)


def load_retirements(projects: list[dict]) -> tuple[dict, dict]:
    """data/lookups/retirements.jsonl -> ({project_id: {beneficiary: [t, first, last]}}, meta)."""
    path = common.ROOT / "data" / "lookups" / "retirements.jsonl"
    rows = common.read_jsonl(path)
    meta = next((r for r in rows if r["record_id"] == "META"), {})
    pid = {r["record_id"]: p["project_id"] for p in projects for r in p["registries"]}
    out: dict[str, dict] = defaultdict(dict)
    for r in rows:
        p = pid.get(r["record_id"])
        if not p or r["record_id"] == "META" or r["record_id"].startswith("COV:"):
            continue
        b = out[p].setdefault(r["beneficiary"], [0, r["first"], r["last"]])
        b[0] += r["retired_tco2e"]
        b[1] = min(filter(None, [b[1], r["first"]]), default=None)
        b[2] = max(filter(None, [b[2], r["last"]]), default=None)
    return out, meta


def delivery_ratio(p: dict, year: int) -> float | None:
    """Issued so far / (estimated annual x crediting years elapsed). Elapsed years run from the earliest of crediting
    start, registration year and first vintage to the latest issued vintage or two years ago, whichever is later
    (registries issue one to two years after the vintage), capped at the crediting end (2020 for CDM-only projects). Issuing projects only."""
    ea, iss = p.get("est_annual_tco2e"), p.get("issued_tco2e") or 0
    if not ea or ea <= 0 or iss <= 0:
        return None
    vint = [int(y) for y in (p.get("issuance_by_vintage") or {}) if str(y).isdigit()]
    cs, ce = (p.get("crediting") or [None, None])[:2]
    starts = [v for v in (int(cs[:4]) if cs else None, p["years"].get("registered"), min(vint) if vint else None) if v]
    if not starts:
        return None
    start = min(starts)
    endy = max(max(vint) if vint else 0, year - 2)
    if all(r["registry"] in ("CDM", "JCM") for r in p["registries"]):
        endy = min(endy, 2020)   # Kyoto-era crediting ended 2020 (later CDM years need an Article 6.4 transition)
    if ce:
        endy = min(endy, int(ce[:4]))
    yrs = endy - int(start) + 1
    if yrs < 1:
        return None
    return round(iss / (ea * yrs), 3)


def _q(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo = int(k)
    return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (k - lo)


def build_types(projects: list[dict], taxonomy: dict, area_of: dict | None = None, area: str | None = None) -> list[dict]:
    """Per credit type: issued, retired, retired share, and years to first issuance, counted from the project's first
    registry milestone or activity year (listing, registration/validation, crediting start or first vintage, whichever
    is earliest). With `area`,
    only that region's share of each project counts."""
    agg = defaultdict(lambda: {"n": 0, "is": 0.0, "re": 0.0, "re_n": 0, "t": []})
    for p in projects:
        iss = p.get("issued_tco2e") or 0
        if iss <= 0 or p["stage"] == "announced":
            continue
        w = 1.0 if not area else sum(sh for c, sh in p["country_shares"].items() if (area_of or {}).get(c) == area)
        if w <= 0:
            continue
        a = agg[p["l2"]]
        a["n"] += 1
        a["is"] += iss * w
        if p.get("retired_tco2e") is not None:
            a["re"] += p["retired_tco2e"] * w
            a["re_n"] += iss * w
        y = p["years"]
        cs = (p.get("crediting") or [None])[0]
        vint = [int(v) for v in (p.get("issuance_by_vintage") or {}) if str(v).isdigit()]
        starts = [v for v in (y.get("listed"), y.get("registered"), int(cs[:4]) if cs else None, min(vint) if vint else None) if v]
        if starts and y.get("first_issuance") and y["first_issuance"] >= min(starts):
            a["t"].append(y["first_issuance"] - min(starts))
    out = []
    for k, a in agg.items():
        t = a["t"]
        out.append({"l2": k, "l1": taxonomy["l2"][k]["l1"], "n": a["n"], "is": round(a["is"]), "re": round(a["re"]),
                    "share": round(a["re"] / a["re_n"], 3) if a["re_n"] else None,
                    "tt": [round(_q(t, 0.5), 1), round(_q(t, 0.25), 1), round(_q(t, 0.75), 1), len(t)] if t else None})
    out.sort(key=lambda r: -r["is"])
    return out


def build_buyers(projects: list[dict], taxonomy: dict, area_of: dict | None = None) -> dict:
    """Buyers through three lenses: Retired (registry retirements in the buyer's name, OffsetsDB), Issued (announced
    deals on projects that have issued credits), Announced (deals on projects not issuing yet or not registered).
    Each buyer lists its projects with the deal volume, the project's issued total and what the buyer retired there."""
    canon, splits, exclude = _canon()
    is_gov = _is_government()
    ret, rmeta = load_retirements(projects)
    l2 = taxonomy["l2"]
    buyers: dict[str, dict] = {}
    area_of = area_of or {}

    def aweights(p):   # share of the project in each region (population split for multi-country projects)
        w = defaultdict(float)
        for c, sh in p["country_shares"].items():
            if c in area_of:
                w[area_of[c]] += sh
        return {a: round(v, 4) for a, v in w.items()}

    def entry(name, p):
        b = buyers.setdefault(name, {"n": name, "an": 0, "is": 0, "re": 0, "p": {}})
        return b, b["p"].setdefault(p["project_id"], {
            "id": p["project_id"], "nm": p["display_name"], "l2": p["l2"], "l1": l2[p["l2"]]["l1"], "c": p["countries"],
            "rg": p["registries"][0]["record_id"], "iss": 1 if p["stage"] == "issuing" and (p.get("issued_tco2e") or 0) > 0 else 0,
            "pis": p.get("issued_tco2e"), "an": None, "dl": [], "re": 0, "rd": None, "aw": aweights(p)})
    for p in projects:
        seen = set()
        for o in p.get("offtakers") or []:
            members = splits.get(o["name"]) or [canon(o["name"])]
            for name in members:
                name = canon(name)
                if (name, o.get("source_url")) in seen:
                    continue
                seen.add((name, o.get("source_url")))
                b, e = entry(name, p)
                vol = round(o["volume_tco2e"] / len(members)) if o.get("volume_tco2e") else None
                share = (f"equal share of {o['volume_tco2e']:,} ({o['name']})" if len(members) > 1 and vol else
                         f"equal share of {o['shared']:,} with other buyers" if o.get("shared") else None)
                e["dl"].append([vol, o.get("date"), o.get("source_url"), share])
                if vol:
                    e["an"] = (e["an"] or 0) + vol
                    b["is" if e["iss"] else "an"] += vol
        for ben, (t, first, last) in (ret.get(p["project_id"]) or {}).items():
            if not ben or any(x.search(ben) for x in exclude):
                continue
            b, e = entry(canon(ben), p)
            e["re"] += t
            e["rd"] = [first, last]
            b["re"] += t
    def lens(e, k):
        return e["re"] if k == "re" else (e["an"] or 0) if (k == "is") == bool(e["iss"]) else 0
    keep = set()
    for a in [None, *AREAS]:   # the top buyers of every lens, overall and in each region
        for k in ("re", "is", "an"):
            tot = {b["n"]: sum(lens(e, k) * (e["aw"].get(a, 0) if a else 1) for e in b["p"].values()) for b in buyers.values()}
            keep |= {n for n, v in sorted(tot.items(), key=lambda kv: -kv[1])[:40] if v > 0}
    keep |= {b["n"] for b in buyers.values() if any(e["dl"] for e in b["p"].values())}
    out = []
    for b in buyers.values():
        if b["n"] not in keep:
            continue
        ps = sorted(b["p"].values(), key=lambda e: -max(e["re"], e["an"] or 0))
        out.append({**b, "np": len(ps), "p": ps[:400], **({"g": 1} if is_gov(b["n"]) else {})})
    out.sort(key=lambda b: -(b["re"] + b["is"] + b["an"]))
    snap = (rmeta.get("snapshot") or "")[:10] or None
    return {"retired_as_of": snap, "retired_source": rmeta.get("source_version"), "list": out}


def build_summary(projects: list[dict], countries: dict, taxonomy: dict) -> dict:
    """Data for the "All Regions" tab: per-region totals, buyers (three lenses) and per-credit-type market tables."""
    today = common.today()
    area_of = {c: v["area"] for c, v in countries.items()}
    regions = {a: {"is": 0.0, "ea": 0.0, "re": 0.0, "projects": 0, "countries": set()} for a in AREAS}
    for p in projects:
        seen = set()
        end = (p.get("crediting") or [None, None])[1]
        for c, sh in p["country_shares"].items():
            a = area_of.get(c)
            if not a:
                continue
            r = regions[a]
            r["is"] += (p.get("issued_tco2e") or 0) * sh
            r["re"] += (p.get("retired_tco2e") or 0) * sh
            if not (end and end < today) and p["stage"] != "inactive":  # same default as the region tabs
                r["ea"] += (p.get("est_annual_tco2e") or 0) * sh
            if (p.get("issued_tco2e") or 0) > 0:
                r["countries"].add(c)
            if a not in seen:
                r["projects"] += 1
                seen.add(a)
    l2 = taxonomy["l2"]
    return {
        "l1": [{"id": k, "label": v["label"]} for k, v in taxonomy["l1"].items()],
        "l2": {k: {"label": v["label"], "l1": v["l1"]} for k, v in l2.items()},
        "regions": [{"id": a, "label": AREAS[a]["label"], "is": round(r["is"]), "ea": round(r["ea"]), "re": round(r["re"]),
                     "projects": r["projects"], "countries": len(r["countries"])} for a, r in regions.items()],
        "buyers": build_buyers(projects, taxonomy, area_of),
        "types": {a: build_types(projects, taxonomy, area_of, None if a == "all" else a) for a in ["all", *AREAS]},
    }


def main() -> None:
    projects = build_projects()
    RET_BY_PROJECT.update(load_retirements(projects)[0])
    global CANON
    CANON = _canon()[0]
    countries = common.load_yaml("countries.yaml")["countries"]
    taxonomy = common.load_yaml("taxonomy.yaml")
    sources = common.load_yaml("sources.yaml")["sources"]
    manifest = common.load_manifest()

    out = common.WEB_DATA
    if out.exists():
        shutil.rmtree(out)
    (out / "rows").mkdir(parents=True)

    today = common.today()
    l2_ids = list(taxonomy["l2"])
    l2idx = {k: i for i, k in enumerate(l2_ids)}

    # One index per area (Asia, North America, South America); each lists only that area's countries and the
    # projects with a share there. Rows are per country, shared by all areas.
    files = {"index": {}, "rows": {}}
    by_country: dict[str, list[dict]] = defaultdict(list)
    rowcache: dict[str, dict] = {}
    names: set[str] = set()
    area_counts = {}
    for area in AREAS:
        country_ids = [c for c, v in countries.items() if v.get("area") == area]
        cidx = {c: i for i, c in enumerate(country_ids)}
        cols = defaultdict(list)
        present = 0
        for p in projects:
            shares = [[cidx[c], s] for c, s in p["country_shares"].items() if c in cidx]
            if not shares:
                continue
            mask = 0
            for r in p["registries"]:
                mask |= 1 << REGISTRIES.index(r["registry"])
            present |= mask
            cols["id"].append(p["project_id"])
            cols["c"].append(shares)
            cols["l2"].append(l2idx.get(p["l2"], l2idx["other"]))
            cols["st"].append(STAGES.index(p["stage"]))
            cols["rg"].append(mask)
            cols["a6"].append(1 if p.get("article6") else 0)
            cols["el"].append(eligibility_mask(p))
            cols["ea"].append(p.get("est_annual_tco2e"))   # null = not published by the source
            end = (p.get("crediting") or [None, None])[1]
            cols["ex"].append(1 if end and end < today else 0)  # crediting period over: left out of map est. totals
            cols["is"].append(p.get("issued_tco2e"))
            cols["re"].append(p.get("retired_tco2e"))
            cols["pi"].append(delivery_ratio(p, int(today[:4])))  # issued vs estimate to date (null = n/a)
            if p["project_id"] not in rowcache:
                row = compact_row(p)
                rowcache[p["project_id"]] = row
                names.update(p["countries"])
                for c in p["country_shares"]:
                    by_country[c].append(row)
        index = {
            "v": 2, "area": area,
            "countries": [{"id": c, "name": countries[c]["name"], "region": countries[c]["region"]} for c in country_ids],
            "l1": [{"id": k, **v} for k, v in taxonomy["l1"].items()],
            "l2": [{"id": k, **v} for k, v in taxonomy["l2"].items()],
            "stages": STAGES,
            "eligibility": [{"id": e["id"], "label": e["label"], "source": e.get("source")} for e in ELIG],
            "registries": [{"id": r, "label": REGISTRY_LABELS[r], "group": REGISTRY_GROUP[r], "present": bool(present >> i & 1)}
                           for i, r in enumerate(REGISTRIES)],
            "cols": cols,
        }
        files["index"][area] = _write_hashed(out, f"index-{area}", index)
        area_counts[area] = len(cols["id"])
    for c, rows in by_country.items():
        files["rows"][c] = "rows/" + _write_hashed(out / "rows", c, rows)
    files["summary"] = _write_hashed(out, "summary", build_summary(projects, countries, taxonomy))

    meta = {
        "built_from": {sid: {
            "label": s["label"], "enabled": bool(s.get("enabled")),
            "last_changed": (manifest["sources"].get(sid) or {}).get("last_changed"),
            "last_checked": (manifest["sources"].get(sid) or {}).get("last_checked"),
            "stale": bool((manifest["sources"].get(sid) or {}).get("stale")),
            "source_date": source_date(sid, manifest["sources"].get(sid) or {}),
            "live": sid not in ("vrod", "cdm", "gcc"),
            "url": s.get("url"), "license": s.get("license"),
        } for sid, s in sources.items() if s.get("enabled")},
        "names": {c: country_name(c, countries) for c in sorted(names)},
        "url_templates": URL_TEMPLATES,
        "tags": [{"label": t["label"], "aliases": t.get("aliases") or [], "broad": t["id"].startswith("t_")} for t in TAGS],
        "project_count": len(projects),
        "summary": SUMMARY,
        "areas": [{"id": a, "label": AREAS[a]["label"], "scope": AREAS[a]["scope"], "projects": area_counts[a]} for a in AREAS],
        "notes": load_notes(),
        "headlines": json.loads((common.ROOT / "data" / "headlines.json").read_text(encoding="utf-8"))
        if (common.ROOT / "data" / "headlines.json").exists() else None,
        "files": files,
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"built data for {len(projects)} projects, {len(by_country)} countries -> {out}")


if __name__ == "__main__":
    main()
