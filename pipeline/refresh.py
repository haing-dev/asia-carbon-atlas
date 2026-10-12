"""Probe sources and fetch only those whose change signal moved.

Usage: python -m pipeline.refresh [--sources a,b|all] [--force]
Writes data/records/<source>.jsonl and state/manifest.json only when something changed.
In GitHub Actions, writes `changed=true|false` and `commit=true|false` to $GITHUB_OUTPUT.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import traceback

from pipeline import common
from pipeline.sources.base import SourceError, get_adapter

HEARTBEAT_DAYS = 30  # keep the scheduled workflow alive (GitHub disables idle schedules after 60 days)


def _days_since(iso: str | None) -> float:
    if not iso:
        return 1e9
    then = dt.datetime.fromisoformat(iso)
    return (dt.datetime.now(dt.timezone.utc) - then).total_seconds() / 86400


def run(selected: list[str] | None, force: bool) -> dict:
    cfg = common.load_yaml("sources.yaml")["sources"]
    manifest = common.load_manifest()
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    data_changed = False
    manifest_changed = False

    for sid, scfg in cfg.items():
        if selected and sid not in selected:
            continue
        state = manifest["sources"].setdefault(sid, {})
        adapter = get_adapter(sid, scfg)
        if not scfg.get("enabled") or not adapter.implemented:
            print(f"[{sid}] skipped (not enabled yet)")
            continue
        if not force and _days_since(state.get("last_checked")) < scfg.get("cadence_days", 10) - 0.5:
            print(f"[{sid}] skipped (checked recently)")
            continue
        try:
            signal = adapter.probe()
            state["last_checked"] = now
            if not force and signal == state.get("signal") and not state.get("stale"):
                print(f"[{sid}] unchanged")
                continue
            path = common.RECORDS_DIR / f"{sid}.jsonl"
            previous = common.read_jsonl(path)
            records = adapter.fetch(previous, signal)
            changed = common.write_jsonl_if_changed(path, records)
            state.update(signal=signal, rows=len(records), stale=False, error=None)
            if changed:
                state["last_changed"] = now
                data_changed = True
            manifest_changed = True
            print(f"[{sid}] fetched {len(records)} records ({'changed' if changed else 'no record changes'})")
        except (SourceError, PermissionError, Exception) as e:  # broken source: keep old data, flag stale
            traceback.print_exc()
            state.update(stale=True, error=f"{type(e).__name__}: {e}"[:300], last_checked=now)
            manifest_changed = True
            print(f"[{sid}] FAILED -> marked stale, previous records kept")

    heartbeat = _days_since(manifest.get("last_commit_at")) > HEARTBEAT_DAYS
    commit = data_changed or heartbeat or (manifest_changed and any(
        s.get("stale") for s in manifest["sources"].values()))
    if commit:
        manifest["last_commit_at"] = now
        common.save_manifest(manifest)
    return {"changed": data_changed, "commit": commit}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="all")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    selected = None if args.sources in ("", "all") else [s.strip() for s in args.sources.split(",")]
    result = run(selected, args.force)
    print(result)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"changed={str(result['changed']).lower()}\ncommit={str(result['commit']).lower()}\n")


if __name__ == "__main__":
    main()
