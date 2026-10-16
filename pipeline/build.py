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


TAGS = common.load_yaml("tags.yaml")["tags"]
TAG_INDEX = {t["id"]: i for i, t in enumerate(TAGS)}


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


def build_summary(projects: list[dict], countries: dict, taxonomy: dict) -> dict:
    """Data for the "All Regions" tab: per-region totals and announced offtakes by buyer.
    Deal status: "issued" = the deal is on a registry project that has issued credits; "announced" = the project
    has not issued yet or is not in a registry (announcement only). Volumes only where the announcement states one."""
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
    aliases = (common.load_yaml("offtakers.yaml").get("buyer_aliases") or {})
    l2 = taxonomy["l2"]
    buyers: dict[tuple, dict] = {}
    seen_deals = set()
    for p in projects:
        status = "issued" if p["stage"] == "issuing" and (p.get("issued_tco2e") or 0) > 0 else "announced"
        for o in p.get("offtakers") or []:
            name = aliases.get(o["name"], o["name"])
            key = (name, o.get("source_url"), p["project_id"])
            if key in seen_deals:
                continue
            seen_deals.add(key)
            b = buyers.setdefault((status, name), {"name": name, "status": status, "volume": 0, "deals": []})
            vol = o.get("volume_tco2e") or None
            b["volume"] += vol or 0
            b["deals"].append({"project": p["display_name"], "id": p["project_id"], "l2": p["l2"], "l1": l2[p["l2"]]["l1"],
                               "c": p["countries"], "v": vol, "d": o.get("date"), "u": o.get("source_url")})
    out_b = {}
    for st in ("issued", "announced"):
        rows = [b for (s, _), b in buyers.items() if s == st]
        rows.sort(key=lambda b: (-b["volume"], -len(b["deals"]), b["name"]))
        out_b[st] = {"buyers": rows, "with_volume": sum(1 for b in rows if b["volume"] > 0),
                     "deals": sum(len(b["deals"]) for b in rows),
                     "deals_no_volume": sum(1 for b in rows for d in b["deals"] if not d["v"])}
    return {
        "l1": [{"id": k, "label": v["label"]} for k, v in taxonomy["l1"].items()],
        "l2": {k: {"label": v["label"], "l1": v["l1"]} for k, v in l2.items()},
        "regions": [{"id": a, "label": AREAS[a]["label"], "is": round(r["is"]), "ea": round(r["ea"]), "re": round(r["re"]),
                     "projects": r["projects"], "countries": len(r["countries"])} for a, r in regions.items()],
        "offtakers": out_b,
    }


def main() -> None:
    projects = build_projects()
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
            cols["ea"].append(p.get("est_annual_tco2e"))   # null = not published by the source
            end = (p.get("crediting") or [None, None])[1]
            cols["ex"].append(1 if end and end < today else 0)  # crediting period over: left out of map est. totals
            cols["is"].append(p.get("issued_tco2e"))
            cols["re"].append(p.get("retired_tco2e"))
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
