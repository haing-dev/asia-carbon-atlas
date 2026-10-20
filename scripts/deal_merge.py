"""Merge agent deal sweeps into config/offtakers.yaml (round-trip, keeps comments).

usage: uv run --with ruamel.yaml python scripts/deal_merge.py plan  <sweep.json...>   -> work/deal_plan.json + printed review
       (edit work/deal_plan.json: "reject": true, "record": "<REG:id>", "force_ann": true, "shared": false ...)
       uv run --with ruamel.yaml python scripts/deal_merge.py apply work/deal_plan.json
Sweep JSON format and research rules: docs/deal-sweep-brief.md. Apply also syncs data/verified/ledger.jsonl.
Rules: verified only; in-scope countries; skip if (canonical buyer, source_url) or (buyer, supplier, volume) exists.
Mapping to a registry record: registry_id given and present in records, or a unique fuzzy name match (>=93) in the
same country and credit type family -> printed for review (field "match"); otherwise announcement row per supplier.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rapidfuzz import fuzz  # noqa: E402
from ruamel.yaml import YAML  # noqa: E402

from pipeline import common  # noqa: E402
from pipeline.build import _canon  # noqa: E402
from pipeline.process import build_projects  # noqa: E402

CFG = Path(__file__).resolve().parents[1] / "config" / "offtakers.yaml"
HERE = Path(__file__).resolve().parents[1] / "work"
yaml = YAML()
yaml.preserve_quotes = True
yaml.width = 4096
yaml.indent(mapping=2, sequence=4, offset=2)

countries = set(common.load_yaml("countries.yaml")["countries"])
tax = common.load_yaml("taxonomy.yaml")
L2 = set(tax["l2"])


def slug(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())[:20] or "x"


def rid_of(reg):
    if not reg:
        return None
    m = re.match(r"(?i)\s*(VCS|VERRA|GS|GOLD STANDARD|PURO|ACR|CAR|ART|CDM)\D{0,3}(\d+)", reg)
    if not m:
        return None
    r, n = m.group(1).upper(), int(m.group(2))
    r = {"VERRA": "VCS", "GOLD STANDARD": "GS"}.get(r, r)
    return {"ACR": f"ACR:{n:04d}", "ART": f"ART:{n:04d}"}.get(r, f"{r}:{n}")


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def plan(files):
    canon = _canon()[0]
    cfg = yaml.load(CFG)
    existing = set()
    for o in cfg["offtakes"]:
        existing.add((canon(o["buyer"]), o.get("source_url"), o.get("record")))
        existing.add((canon(o["buyer"]), o.get("record"), o.get("volume_tco2e")))
    for a in cfg["announced_rows"]:
        for o in a["offtakes"]:
            existing.add((canon(o["buyer"]), o.get("source_url"), slug(a.get("developer"))[:8]))
            existing.add((canon(o["buyer"]), a["id"], o.get("volume_tco2e")))
    projects = build_projects()
    rec2p = {r["record_id"]: p for p in projects for r in p["registries"]}
    from pipeline import ledger
    led = ledger.load()
    out = []
    batch = set()
    pre = set(existing)
    for f in files:
        for d in json.load(open(f)):
            if not d.get("verified") or d.get("already_listed"):
                continue
            cs = [c for c in d.get("countries") or [] if c in countries]
            if not cs:
                continue
            b = canon(d["buyer"].strip())
            if (b, d["source_url"], d.get("project")) in batch:
                continue
            lr = led.get(ledger.norm(d["source_url"]))
            if lr and lr["outcome"] == "not_added":
                continue
            seen_before = bool(lr and lr["outcome"] == "added" and b in {canon(x) for x in lr["buyers"]})
            l2 = d.get("credit_type") if d.get("credit_type") in L2 else "other"
            rid = rid_of(d.get("registry_id"))
            match = None
            if rid and rid in rec2p:
                match = (rid, rec2p[rid]["display_name"], 100)
            elif d.get("project"):
                cands = []
                for p in projects:
                    if p["project_id"].startswith("ANN:") or not set(p["countries"]) & set(cs):
                        continue
                    if tax["l2"][p["l2"]]["l1"] != tax["l2"][l2]["l1"]:
                        continue
                    s = fuzz.token_set_ratio(norm(d["project"]), norm(p["display_name"]))
                    if s >= 93:
                        cands.append((s, p))
                cands.sort(key=lambda x: -x[0])
                if cands and (len(cands) == 1 or cands[0][0] > cands[1][0]):
                    p = cands[0][1]
                    match = (p["registries"][0]["record_id"], p["display_name"], cands[0][0])
            key = (b, match[0] if match else None, d.get("volume_tco2e"))
            if match and key in existing:
                continue
            if (b, d["source_url"], match[0] if match else slug(d.get("supplier") or d.get("project"))[:8]) in pre:
                continue
            existing.add((b, d["source_url"]))
            batch.add((b, d["source_url"], d.get("project")))
            out.append({**d, "buyer": d["buyer"].strip(), "countries": cs, "credit_type": l2, "match": match, "src": Path(f).stem,
                        **({"reject": True, "why": "same buyer and source already added (ledger): check before un-rejecting"} if seen_before else {})})
    # One stated total covering several buyers or projects in the same source -> shared (split equally downstream).
    from collections import Counter
    grp = Counter((x["source_url"], x.get("volume_tco2e")) for x in out if x.get("volume_tco2e"))
    for x in out:
        x["shared"] = bool(x.get("volume_tco2e")) and grp[(x["source_url"], x["volume_tco2e"])] > 1
    HERE.mkdir(exist_ok=True)
    json.dump(out, open(HERE / "deal_plan.json", "w"), indent=1, ensure_ascii=False)
    for x in out:
        m = f"-> {x['match'][0]} ({x['match'][1][:50]}, {x['match'][2]:.0f})" if x["match"] else "-> ANN"
        print(f"{out.index(x):3} {x['src'][:8]:8} {'R' if x.get('reject') else 'S' if x['shared'] else ' '} {x['buyer'][:26]:26} | {(x['supplier'] or '')[:24]:24} | {(x['project'] or '')[:40]:40} {x['volume_tco2e'] or '':>10} {m}")
    print(len(out), "to add")


def apply(planfile, reject=()):
    cfg = yaml.load(CFG)
    rows = {a["id"]: a for a in cfg["announced_rows"]}
    n = 0
    for x in json.load(open(planfile)):
        if x.get("reject"):
            continue
        o = {"buyer": x["buyer"]}
        if x.get("volume_tco2e"):
            o["shared_volume_tco2e" if x.get("shared") else "volume_tco2e"] = int(x["volume_tco2e"])
        o["date"] = str(x["date"]) if x.get("date") else None
        o["source_url"] = x["source_url"]
        o["source_title"] = x["source_title"]
        note = "; ".join(t for t in [x.get("volume_note"), "retirement disclosed by the buyer" if x["kind"] == "retirement_disclosure" else None] if t)
        if note:
            o["note"] = note
        if o["date"] is None:
            del o["date"]
        if x.get("record") or (x.get("match") and not x.get("force_ann")):
            cfg["offtakes"].append({"record": x.get("record") or x["match"][0], **o})
        else:
            sup = x.get("supplier") or x.get("project") or "unknown"
            aid = f"ANN:{slug(sup)}-{x['credit_type']}-{x['countries'][0].lower()}"
            same = [a for a in rows.values() if slug(a.get("developer"))[:8] == slug(sup)[:8] and a["l2"] == x["credit_type"]
                    and set(a["countries"]) & set(x["countries"])]
            if aid not in rows and same:
                aid = same[0]["id"]
            if aid not in rows:
                name = f"{sup} — {x['project']}" if x.get("project") and slug(x["project"]) != slug(sup) else f"{sup} (supplier-level deal)"
                rows[aid] = {"id": aid, "name": name, "developer": sup, "countries": x["countries"], "l2": x["credit_type"], "offtakes": []}
                cfg["announced_rows"].append(rows[aid])
            rows[aid]["offtakes"].append(o)
        n += 1
    yaml.dump(cfg, CFG)
    from pipeline import ledger
    ledger.sync()
    print("added", n)


if __name__ == "__main__":
    if sys.argv[1] == "plan":
        plan(sys.argv[2:])
    else:
        apply(sys.argv[2])
