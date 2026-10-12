"""Global Carbon Council — registered ("approved") projects, from the registry's own Excel export.

The GCC website sits behind a Cloudflare bot challenge, so the atlas does not fetch it (no bypass, per policy).
Instead the owner downloads "Approved Projects → Export" from https://gcc2.globalcarboncouncil.com/search/registration
and commits it to data/manual/gcc/ (any *.xlsx; the newest file wins). No network access here.
Probe: hash of that file. The export has no issuance volumes, developers or per-project links.
"""
from __future__ import annotations

import io
import re

import openpyxl

from pipeline import common
from pipeline.normalize import in_scope, methodology_codes, split_countries, to_int
from pipeline.sources.base import Source, SourceError, carry_over

MANUAL_DIR = common.ROOT / "data" / "manual" / "gcc"
SEARCH_URL = "https://gcc2.globalcarboncouncil.com/search/registration"


def latest_file():
    files = sorted(MANUAL_DIR.glob("*.xlsx"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SourceError("GCC: no export in data/manual/gcc/")
    return files[-1]


def norm(h) -> str:
    return " ".join(str(h or "").split())


def parse(data: bytes) -> list[dict]:
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    if not rows or "Project Submission No." not in [norm(h) for h in rows[0]]:
        raise SourceError("GCC: unexpected export layout")
    header = [norm(h) for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:] if any(r)]


def col(row: dict, prefix: str):
    return next((v for k, v in row.items() if k.startswith(prefix)), None)


class Adapter(Source):
    implemented = True

    def probe(self) -> dict:
        f = latest_file()
        return {"file": f.name, "sha256": common.sha256_bytes(f.read_bytes())[:16]}

    def fetch(self, previous: list[dict], signal: dict) -> list[dict]:
        f = latest_file()
        data = f.read_bytes()
        prev = {p["record_id"]: p for p in previous}
        today = common.today()
        out = []
        for row in parse(data):
            sub = str(row.get("Project Submission No.") or "").strip()
            m = re.fullmatch(r"S0*(\d+)", sub)
            if not m:
                continue
            countries = split_countries(row.get("Country"))
            if not countries or not in_scope(countries):
                continue
            crediting = re.findall(r"\d{4}-\d{2}-\d{2}", str(row.get("Crediting Period") or ""))
            markets = str(row.get("Validated Market Eligibility") or "")
            meth = str(row.get("Methodologies & Version") or "")
            rec = {
                "record_id": f"GCC:{int(m.group(1))}",
                "registry": "GCC",
                "native_id": sub,
                "registry_url": SEARCH_URL,  # the export carries no per-project link
                "name": str(row.get("Project Title") or "").strip(),
                "developer_raw": None,
                "participants_raw": None,
                "countries": countries,
                "methodology_codes": methodology_codes(meth) or re.findall(r"\bGCCM\d+\b", meth),
                "registry_type_raw": row.get("Project Kinds/ Activity Type"),
                "registry_status_raw": "Registered",
                "est_annual_tco2e": to_int(col(row, "Validated GHG Emission Reduction")),
                "issued_tco2e": 0,
                "retired_tco2e": None,
                "issuance_by_vintage": {},
                "crediting_start": crediting[0] if crediting else None,
                "crediting_end": crediting[1] if len(crediting) > 1 else None,
                "cross_refs": [],
                "beneficiaries": [],
                "source_version": f"GCC approved-projects export ({f.name}, {signal.get('sha256', '')[:8]})",
                "raw_hash": common.sha256_bytes(common.dumps({k: str(v) for k, v in row.items()}).encode()),
                "listed_date": None,
                "registered_date": str(row.get("Project Registration Date") or "")[:10] or None,
                "first_issuance_date": None,
                "market_eligibility_raw": markets if markets != "-" else None,
                "validator_raw": row.get("Approved Validator"),
            }
            if "Article 6.2" in markets:
                rec["article6"] = {"mechanism": "Art. 6.2", "buyer_countries": [], "status": "GCC CA+ label (authorised)"}
            out.append(carry_over(rec, prev, today))
        return out
