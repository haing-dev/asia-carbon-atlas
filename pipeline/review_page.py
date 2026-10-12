"""Build the dedupe review page (published as a private claude.ai artifact; decisions are stored in its database).

Usage: python -m pipeline.review_page  -> work/review/dedupe_review.html
Apply decisions afterwards: python -m pipeline.review_page --apply decisions.json
(decisions.json = rows read from the artifact's `decisions` collection: [{"pair": "A+B", "decision": "same"|"different"}]).
"""
from __future__ import annotations

import csv
import json
import sys

from pipeline import common, dedupe

OUT = common.WORK / "review" / "dedupe_review.html"
TEMPLATE = common.ROOT / "pipeline" / "templates" / "dedupe_review.html"


def pairs() -> list[dict]:
    recs = {r["record_id"]: r for r in common.load_all_records()}
    decided = dedupe.load_decisions()
    out = []
    with open(dedupe.PENDING, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["id"] in decided:
                continue
            a, b = row["id"].split("|")
            if a not in recs or b not in recs:
                continue

            def side(r):
                return {"id": r["record_id"], "url": r["registry_url"], "name": r.get("name"),
                        "dev": r.get("developer_raw"), "c": r.get("countries"), "state": r.get("state_raw"),
                        "type": r.get("registry_type_raw"), "status": r.get("registry_status_raw"),
                        "est": r.get("est_annual_tco2e"), "iss": r.get("issued_tco2e"),
                        "start": r.get("crediting_start"), "meth": (r.get("methodology_codes") or [])[:3]}
            out.append({"key": f"{a}+{b}", "score": float(row["score"]), "a": side(recs[a]), "b": side(recs[b])})
    out.sort(key=lambda p: -p["score"])
    return out


def build() -> None:
    data = pairs()
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__PAIRS__*/[]", json.dumps(data, ensure_ascii=False))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"{len(data)} pairs -> {OUT}")


def apply(path: str) -> None:
    rows = json.loads(open(path, encoding="utf-8").read())
    current = dedupe.load_decisions()
    added = 0
    for r in rows:
        d = {"same": "yes", "different": "no"}.get(r.get("decision"))
        pid = "|".join(sorted(str(r.get("pair", "")).split("+")))
        if d and pid.count("|") == 1 and current.get(pid) != d:
            current[pid] = d
            added += 1
    with open(dedupe.DECISIONS, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "decision"])
        for pid in sorted(current):
            w.writerow([pid, current[pid]])
    print(f"{added} decisions added/changed; {len(current)} total in {dedupe.DECISIONS}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--apply":
        apply(sys.argv[2])
    else:
        build()
