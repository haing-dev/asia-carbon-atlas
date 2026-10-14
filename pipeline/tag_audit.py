"""Tag consistency audit (offline). Usage: python -m pipeline.tag_audit [--samples N] [--tag ID ...]

For every tag in config/tags.yaml it reports:
- MISSES: projects whose own text (name, registry type, methodology, registry description) contains the tag's label or
  an alias, but which did not get the tag (rule gap, credit-type gate, or misclassified credit type);
- WEAK HITS: projects that got the tag although their text never names it (assigned by a looser pattern) -- to check
  for false positives.
Writes review/tag_audit.csv (one row per finding) and prints a summary.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict

from pipeline import common, process

# Aliases too short/generic to judge a miss by plain text (they'd flag unrelated projects).
SKIP_TERMS = {"ad", "ee", "pv", "dam", "rail", "metro", "ev", "evs", "efficiency", "biomass", "landfill", "wastewater",
              "compost", "rice", "peat", "concrete", "brick", "bricks", "pellets", "briquettes", "reservoir", "lpg",
              "led", "cfl", "stoves", "cookstove", "hfc", "trees", "jurisdictional", "solar", "wind", "hydro", "soc", "ar", "a/r", "ror", "wte", "ics", "apd", "aud", "chp"}


def term_rx(terms: list[str]) -> re.Pattern | None:
    parts = []
    for t in terms:
        t = t.strip().lower()
        if not t or t in SKIP_TERMS or len(t) < 3:
            continue
        parts.append(r"[\s\-/]*".join(re.escape(w) for w in re.split(r"[\s\-/]+", t)))
    return re.compile(r"(?<![a-z0-9])(" + "|".join(parts) + r")(?![a-z0-9])", re.I) if parts else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--tag", nargs="*")
    args = ap.parse_args()

    tags_cfg = common.load_yaml("tags.yaml")["tags"]
    records = process.fix_gs_links(common.load_all_records())
    by_id = {r["record_id"]: r for r in records}
    projects = process.build_projects()
    findings = []
    summary = []
    for t in tags_cfg:
        if args.tag and t["id"] not in args.tag:
            continue
        rx = term_rx([t["label"], *(t.get("aliases") or [])])
        miss, weak = [], []
        for p in projects:
            ms = [by_id.get(g["record_id"], {}) for g in p["registries"]]
            text = " | ".join(process.record_text(m) + " | " + process.background_text(m) for m in ms if m)
            has = t["id"] in p["tags"]
            hit = rx.search(text) if rx else None
            if hit and not has:
                miss.append((p, hit.group(0)))
            elif has and not t["id"].startswith("t_") and rx and not hit:
                weak.append((p, ""))
        summary.append((t["id"], sum(t["id"] in p["tags"] for p in projects), len(miss), len(weak)))
        for kind, rows in (("miss", miss), ("weak", weak)):
            for p, term in rows:
                findings.append({"kind": kind, "tag": t["id"], "term": term, "project_id": p["project_id"],
                                 "l2": p["l2"], "name": p["display_name"], "tags": " ".join(p["tags"])})
    out = common.ROOT / "review" / "tag_audit.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["kind", "tag", "term", "project_id", "l2", "name", "tags"])
        w.writeheader()
        w.writerows(findings)
    print(f"{'tag':28} {'tagged':>7} {'misses':>7} {'weak':>6}")
    for tid, n, m, wk in sorted(summary, key=lambda s: -(s[2] + s[3])):
        if m or wk:
            print(f"{tid:28} {n:7} {m:7} {wk:6}")
    by = defaultdict(list)
    for fnd in findings:
        by[(fnd["kind"], fnd["tag"])].append(fnd)
    for (kind, tid), rows in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"\n== {kind} {tid} ({len(rows)})")
        for r in rows[: args.samples]:
            print(f"   {r['project_id']:<22} {r['l2']:<16} [{r['term']}] {r['name'][:80]}")
    print(f"\n{len(findings)} findings -> {out}")


if __name__ == "__main__":
    main()
