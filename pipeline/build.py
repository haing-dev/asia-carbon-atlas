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
}
STAGES = ["pipeline", "registered", "issuing", "inactive", "announced"]
REGISTRY_LABELS = {
    "VCS": "Verra (VCS)", "GS": "Gold Standard", "CDM": "CDM", "PACM": "Article 6.4 (PACM)",
    "GCC": "Global Carbon Council", "UCR": "Universal Carbon Registry", "PURO": "Puro.earth",
    "ISO": "Isometric", "JCM": "JCM (Japan)", "A62": "Article 6.2 (bilateral)",
    "ANN": "Announced deal (no registry record)",
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
            notes.append({"key": line[3:].strip().split()[0].lower(), "points": []})
        elif line.lstrip().startswith("- ") and notes:
            notes[-1]["points"].append(line.lstrip()[2:].strip())
        elif line.strip() and notes and notes[-1]["points"]:
            notes[-1]["points"][-1] += " " + line.strip()  # wrapped bullet
    return [n for n in notes if n["points"]]


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

    l2_ids = list(taxonomy["l2"])
    l2idx = {k: i for i, k in enumerate(l2_ids)}

    # One index per area (Asia, North America, South America); each lists only that area's countries and the
    # projects with a share there. Rows are per country, shared by all areas.
    files = {"index": {}, "rows": {}}
    by_country: dict[str, list[dict]] = defaultdict(list)
    rowcache: dict[str, dict] = {}
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
            cols["ea"].append(p.get("est_annual_tco2e") or 0)
            cols["is"].append(p.get("issued_tco2e") or 0)
            cols["re"].append(p.get("retired_tco2e") or 0)
            if p["project_id"] not in rowcache:
                row = {k: p[k] for k in (
                    "project_id", "display_name", "developer", "developer_url", "project_url", "countries", "country_shares",
                    "registries", "issuance_by_vintage", "methodology_codes", "crediting", "years", "article6",
                    "offtakers", "flags")}
                row["country_names"] = [country_name(c, countries) for c in p["countries"]]
                rowcache[p["project_id"]] = row
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

    meta = {
        "built_from": {sid: {
            "label": s["label"], "enabled": bool(s.get("enabled")),
            "last_changed": (manifest["sources"].get(sid) or {}).get("last_changed"),
            "last_checked": (manifest["sources"].get(sid) or {}).get("last_checked"),
            "stale": bool((manifest["sources"].get(sid) or {}).get("stale")),
            "source_date": source_date(sid, manifest["sources"].get(sid) or {}),
            "live": sid not in ("vrod", "cdm", "gcc"),
            "url": s.get("url"), "license": s.get("license"),
        } for sid, s in sources.items()},
        "project_count": len(projects),
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
