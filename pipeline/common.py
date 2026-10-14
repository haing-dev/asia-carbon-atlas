"""Shared paths, config loading and deterministic file IO."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
RECORDS_DIR = ROOT / "data" / "records"
ENRICHMENT = ROOT / "data" / "enrichment.jsonl"
MANIFEST = ROOT / "state" / "manifest.json"
WEB_DATA = ROOT / "web" / "public" / "data"
WORK = ROOT / "work"

# Fixed field order for stored records (keeps git diffs small and stable).
RECORD_FIELDS = [
    "record_id", "registry", "native_id", "registry_url", "name",
    "developer_raw", "participants_raw", "countries", "methodology_codes",
    "registry_type_raw", "registry_status_raw", "est_annual_tco2e",
    "issued_tco2e", "retired_tco2e", "issuance_by_vintage",
    "crediting_start", "crediting_end", "cross_refs", "beneficiaries",
    "source_version", "raw_hash", "first_seen", "last_changed",
]


def load_yaml(name: str) -> dict:
    with open(CONFIG / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def today() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dumps(obj: Any) -> str:
    """Compact, stable JSON (sorted dict keys)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def order_record(rec: dict) -> dict:
    """Return the record with fields in canonical order; unknown fields go last, sorted."""
    out = {k: rec.get(k) for k in RECORD_FIELDS}
    for k in sorted(set(rec) - set(RECORD_FIELDS)):
        out[k] = rec[k]
    return out


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl_if_changed(path: Path, rows: Iterable[dict], key: str = "record_id", ordered: bool = True) -> bool:
    """Write rows sorted by `key`, one compact JSON object per line (project records in the standard field order
    unless ordered=False). Returns True if the file changed."""
    rows = sorted(rows, key=lambda r: str(r.get(key, "")))
    text = "".join(
        json.dumps(order_record(r) if key == "record_id" and ordered else r, ensure_ascii=False, separators=(",", ":")) + "\n"
        for r in rows
    )
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"sources": {}, "last_commit_at": None}


def save_manifest(manifest: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_all_records() -> list[dict]:
    rows: list[dict] = []
    for p in sorted(RECORDS_DIR.glob("*.jsonl")):
        rows.extend(read_jsonl(p))
    return rows
