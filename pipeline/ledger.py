"""Ledger of deal sources already checked (back end only; not used by the website).

data/verified/ledger.jsonl — one row per source URL that a sweep has opened and judged:
  {"key": <normalised url>, "url": ..., "checked": "YYYY-MM-DD", "outcome": "added" | "not_added" | "unverified",
   "reason": "...", "buyers": [...], "suppliers": [...]}
- "added": the source backs a deal in config/offtakers.yaml (synced automatically by `sync`).
- "not_added": opened and judged out (out of scope, no supplier named, investment/option/MoU, duplicate...): skip it.
- "unverified": could not be opened; a later sweep should try again.
Sweeps check a URL first (`python -m pipeline.ledger check URL ...`) and skip anything "added" or "not_added", so
the same news is never searched and verified twice.

Usage:
  python -m pipeline.ledger sync                       # add/refresh "added" rows from config/offtakers.yaml
  python -m pipeline.ledger check URL [URL ...]        # prints outcome per URL ("new" if unknown)
  python -m pipeline.ledger import sweep.json [...]    # sweep outputs (brief format) -> not_added / unverified rows
"""
from __future__ import annotations

import json
import re
import sys
from urllib.parse import urlsplit

from pipeline import common

PATH = common.ROOT / "data" / "verified" / "ledger.jsonl"


def norm(url: str) -> str:
    u = urlsplit((url or "").strip())
    host = u.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", u.path)
    q = "&".join(x for x in u.query.split("&") if x and not x.startswith(("utm_", "fbclid", "gclid")))
    return f"{host}{path}" + (f"?{q}" if q else "")


def load() -> dict[str, dict]:
    return {r["key"]: r for r in common.read_jsonl(PATH)}


def save(rows: dict[str, dict]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    common.write_jsonl_if_changed(PATH, rows.values(), key="key", ordered=False)


def _merge(rows, url, outcome, buyer=None, supplier=None, reason=None, checked=None):
    k = norm(url)
    if not k:
        return
    r = rows.get(k) or {"key": k, "url": url, "checked": checked or common.today(), "outcome": outcome, "reason": reason,
                        "buyers": [], "suppliers": []}
    rank = {"unverified": 0, "not_added": 1, "added": 2}
    if rank[outcome] > rank.get(r["outcome"], 0):
        r["outcome"], r["reason"] = outcome, reason
    for field, v in (("buyers", buyer), ("suppliers", supplier)):
        if v and v not in r[field]:
            r[field].append(v)
    rows[k] = r


def sync() -> int:
    """Every source behind a deal in config/offtakers.yaml is 'added'."""
    rows = load()
    cfg = common.load_yaml("offtakers.yaml")
    n = len(rows)
    for o in cfg.get("offtakes") or []:
        for u in (o.get("source_url"), o.get("volume_source")):
            if u:
                _merge(rows, u, "added", o["buyer"], o.get("record"))
    for a in cfg.get("announced_rows") or []:
        for o in a.get("offtakes") or []:
            for u in (o.get("source_url"), o.get("volume_source")):
                if u:
                    _merge(rows, u, "added", o["buyer"], a.get("developer") or a["name"])
    save(rows)
    return len(rows) - n


def import_sweeps(files: list[str]) -> int:
    rows = load()
    n = len(rows)
    for f in files:
        for d in json.load(open(f, encoding="utf-8")):
            url = d.get("source_url")
            if not url:
                continue
            if not d.get("verified"):
                _merge(rows, url, "unverified", d.get("buyer"), d.get("supplier"), "page could not be opened")
            elif not d.get("countries") and norm(url) not in rows:
                _merge(rows, url, "unverified", d.get("buyer"), d.get("supplier"), "no project country stated; find it")
            elif norm(url) not in rows or rows[norm(url)]["outcome"] != "added":
                _merge(rows, url, "not_added", d.get("buyer"), d.get("supplier"),
                       "reviewed; not merged (out of scope, option/investment/MoU, seller-side or duplicate)")
    save(rows)
    return len(rows) - n


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else "sync"
    if cmd == "sync":
        print(f"ledger: +{sync()} rows ({len(load())} total)")
    elif cmd == "check":
        rows = load()
        for u in argv[1:]:
            r = rows.get(norm(u))
            print(f"{r['outcome'] if r else 'new'}\t{u}")
    elif cmd == "import":
        print(f"ledger: +{import_sweeps(argv[1:])} rows ({len(load())} total)")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
