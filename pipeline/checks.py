"""Background hygiene checks on the built projects (not shown on the site).

Run by `python -m pipeline.validate` (refresh workflow) and `make test`. Errors block the commit/deploy; warnings are
printed as GitHub `::warning::` annotations and written to review/hygiene.csv for the owner / weekly task.

Errors (must never happen):
  - one registry record inside two projects (a project counted twice);
  - the same deal (buyer + project + source) listed twice on a project.
Warnings (look at them):
  - the same deal both mapped to a registry project and listed as an announcement row (same buyer and source);
  - a buyer credited with more retirements on a project than the project's retired total;
  - issued-by-vintage that does not add up to the issued total (>2% off);
  - announcement rows whose developer has exactly one registry project of the same credit type and country
    (probably mappable to that project).
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict

from pipeline import common

OUT = common.ROOT / "review" / "hygiene.csv"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def run(projects: list[dict]) -> tuple[list[str], list[list[str]]]:
    from pipeline.build import _canon, load_retirements   # local import: build imports process

    canon = _canon()[0]
    errors: list[str] = []
    warns: list[list[str]] = []

    owner: dict[str, str] = {}
    for p in projects:
        for r in p["registries"]:
            if r["record_id"] in owner and owner[r["record_id"]] != p["project_id"]:
                errors.append(f"record {r['record_id']} is in two projects: {owner[r['record_id']]} and {p['project_id']}")
            owner[r["record_id"]] = p["project_id"]

    deal_where: dict[tuple, set] = defaultdict(set)
    for p in projects:
        seen = set()
        for o in p.get("offtakers") or []:
            k = (canon(o["name"]), o.get("source_url"))
            if k in seen:
                errors.append(f"{p['project_id']}: deal listed twice ({k[0]}, {k[1]})")
            seen.add(k)
            deal_where[k].add(p["project_id"])
    for (buyer, url), pids in deal_where.items():
        if len(pids) > 1 and any(x.startswith("ANN:") for x in pids) and any(not x.startswith("ANN:") for x in pids):
            warns.append(["deal_mapped_and_announced", buyer, url or "", " ".join(sorted(pids))])

    ret, _ = load_retirements(projects)
    for p in projects:
        rt = p.get("retired_tco2e")
        if rt is None:
            continue
        named = sum(v[0] for b, v in (ret.get(p["project_id"]) or {}).items() if b)
        if named > rt * 1.02 + 1000:
            warns.append(["retired_by_buyers_gt_project", p["project_id"], f"{named:.0f}", f"{rt:.0f}"])

    for p in projects:
        v = p.get("issuance_by_vintage") or {}
        iss = p.get("issued_tco2e") or 0
        if v and iss and abs(sum(v.values()) - iss) > 0.02 * iss + 10:
            warns.append(["vintage_sum_ne_issued", p["project_id"], f"{sum(v.values()):.0f}", f"{iss:.0f}"])

    by_dev = defaultdict(list)
    for p in projects:
        if p["developer"] and not p["project_id"].startswith("ANN:"):
            for c in p["countries"]:
                by_dev[(_norm(p["developer"]).split(" ")[0], c, p["l2"])].append(p["project_id"])
    for p in projects:
        if p["project_id"].startswith("ANN:") and p.get("developer"):
            for c in p["countries"]:
                cand = by_dev.get((_norm(p["developer"]).split(" ")[0], c, p["l2"])) or []
                if len(cand) == 1:
                    warns.append(["announcement_maybe_mappable", p["project_id"], cand[0], p["developer"]])
    return errors, warns


def main() -> int:
    from pipeline.process import build_projects

    errors, warns = run(build_projects())
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["check", "a", "b", "c"])
        w.writerows(sorted(warns))
    kinds = defaultdict(int)
    for x in warns:
        kinds[x[0]] += 1
    for k, n in sorted(kinds.items()):
        print(f"::warning::hygiene {k}: {n} (see review/hygiene.csv)")
    for e in errors:
        print("ERROR", e)
    print(f"hygiene: {len(errors)} errors, {len(warns)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
