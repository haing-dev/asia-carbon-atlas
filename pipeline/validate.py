"""Validation gates (docs/SPEC.md §11). Exit code 1 blocks commit and deploy."""
from __future__ import annotations

import sys

from pipeline import common

REQUIRED = ["record_id", "registry", "native_id", "registry_url", "countries"]
WARNINGS: list[str] = []
REGISTRIES = {"VCS", "GS", "CDM", "PACM", "GCC", "UCR", "PURO", "ISO", "JCM", "A62", "ACR", "CAR", "ART"}


def check_records(records: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    stage_map = common.load_yaml("stages.yaml").get("map") or {}
    for r in records:
        rid = r.get("record_id", "?")
        for k in REQUIRED:
            if not r.get(k):
                errors.append(f"{rid}: missing {k}")
        if rid in seen:
            errors.append(f"{rid}: duplicate record_id")
        seen.add(rid)
        if r.get("registry") not in REGISTRIES:
            errors.append(f"{rid}: unknown registry {r.get('registry')}")
        url = r.get("registry_url") or ""
        if not url.startswith("https://") and not url.startswith("http://"):
            errors.append(f"{rid}: registry_url is not a URL")
        for k in ("issued_tco2e", "retired_tco2e", "est_annual_tco2e"):
            v = r.get(k)
            if v is not None and v < 0:
                errors.append(f"{rid}: negative {k}")
        if (r.get("retired_tco2e") or 0) > (r.get("issued_tco2e") or 0):
            WARNINGS.append(f"{rid}: retired > issued (as published by the source; flagged)")
        raw = str(r.get("registry_status_raw") or "").strip().lower()
        if raw and stage_map and r.get("registry") in stage_map and raw not in stage_map[r["registry"]]:
            errors.append(f"{rid}: unmapped status '{raw}' (add to config/stages.yaml)")
    return errors


def check_row_counts(manifest: dict, previous: dict | None) -> list[str]:
    errors = []
    if not previous:
        return errors
    for sid, st in manifest.get("sources", {}).items():
        before = (previous.get("sources", {}).get(sid) or {}).get("rows")
        after = st.get("rows")
        if before and after is not None and after < before * 0.8:
            errors.append(f"{sid}: row count dropped {before} -> {after} (>20%)")
    return errors


def main() -> None:
    errors = check_records(common.load_all_records())
    for w in WARNINGS[:50]:
        print("WARNING", w)
    print(f"{len(WARNINGS)} warnings")
    for e in errors[:200]:
        print("ERROR", e)
    if errors:
        print(f"{len(errors)} validation errors")
        sys.exit(1)
    print("validation passed")


if __name__ == "__main__":
    main()
