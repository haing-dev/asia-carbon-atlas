"""UNFCCC Clean Development Mechanism, via the UNEP Copenhagen Climate Centre CDM Pipeline workbook.

UNFCCC's own project search and registry listings are disallowed by cdm.unfccc.int/robots.txt
(with a 60 s crawl delay), so project-level data comes from UNEP-CCC's CDM Pipeline, which compiles
UNFCCC records. Each row links to the project's official UNFCCC page by its unique project ID.

Probe: the workbook link on the UNEP-CCC page + its Last-Modified/ETag (2 requests).
"""
from __future__ import annotations

import io
import re

import openpyxl

from pipeline import common
from pipeline.http import PoliteClient
from pipeline.normalize import cross_refs, in_scope, iso3, methodology_codes, split_countries, to_date, to_int
from pipeline.sources.base import Source, SourceError, carry_over

PAGE = "https://unepccc.org/cdm-ji-pipeline/"
LINK_RE = re.compile(r'href="(https://unepccc\.org/wp-content/uploads/[^"]*cdm-pipeline[^"]*\.xlsx)"', re.I)
HEADER_ROW = 3


def unfccc_url(kind: str, uid: str) -> str:
    if (kind or "").upper() == "POA":
        return f"https://cdm.unfccc.int/ProgrammeOfActivities/Validation/DB/{uid}/view.html"
    return f"https://cdm.unfccc.int/Projects/Validation/DB/{uid}/view.html"


def kt(v) -> int | None:
    """kilotonnes -> tonnes"""
    if v in (None, ""):
        return None
    try:
        return int(round(float(v) * 1000))
    except (TypeError, ValueError):
        return None


class Adapter(Source):
    implemented = True

    def probe(self) -> dict:
        client = PoliteClient()
        r = client.get(PAGE)
        r.raise_for_status()
        links = LINK_RE.findall(r.text)
        if not links:
            raise SourceError("CDM pipeline link not found on UNEP-CCC page")
        url = sorted(set(links))[-1]  # paths include /YYYY/MM/, so the latest sorts last
        h = client.head(url)
        return {"url": url, "etag": h.headers.get("etag"), "last_modified": h.headers.get("last-modified")}

    def fetch(self, previous: list[dict], signal: dict) -> list[dict]:
        client = PoliteClient(timeout=300)
        r = client.get(signal["url"])
        r.raise_for_status()
        raw_hash = common.sha256_bytes(r.content)
        version = re.search(r"/uploads/(\d{4}/\d{2})/", signal["url"])
        version = f"UNEP-CCC CDM Pipeline {version.group(1) if version else ''}".strip()
        wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True, data_only=True)
        ws = wb["CDM_Projects"]
        rows = ws.iter_rows(values_only=True, max_col=100)
        header = None
        for i, row in enumerate(rows):
            if i == HEADER_ROW:
                header = [str(h).strip() if h is not None else "" for h in row]
                break
        if not header or "Unique project ID" not in header:
            raise SourceError("CDM_Projects header not found")
        c = {h: i for i, h in enumerate(header) if h}

        def g(row, name):
            i = c.get(name)
            return row[i] if i is not None and i < len(row) else None

        prev = {p["record_id"]: p for p in previous}
        today = common.today()
        out = []
        for row in rows:
            uid = g(row, "Unique project ID")
            ref = to_int(g(row, "Ref."))
            if not uid or not ref:
                continue
            countries = []
            host = iso3(g(row, "Host country - ISO2")) or iso3(g(row, "Host country"))
            if host:
                countries.append(host)
            for o in split_countries(g(row, "Other host countries")):
                if o not in countries:
                    countries.append(o)
            if not in_scope(countries):
                continue
            kind = str(g(row, "PA/PoA") or "PA")
            title = str(g(row, "Title") or "").strip()
            end = to_date(g(row, "End of last crediting period"))
            rec = {
                "record_id": f"CDM:{ref}",
                "registry": "CDM",
                "native_id": str(ref),
                "registry_url": unfccc_url(kind, uid),
                "name": title,
                "developer_raw": None,
                "participants_raw": None,
                "countries": countries,
                "methodology_codes": methodology_codes(g(row, "Methodology")) or [str(g(row, "Methodology") or "")][:1],
                "registry_type_raw": f"{g(row, 'Type') or ''} / {g(row, 'Sub-type') or ''}".strip(" /"),
                "registry_status_raw": g(row, "Status"),
                "est_annual_tco2e": kt(g(row, "Reductions (ktCO2e/yr)")),
                "issued_tco2e": kt(g(row, "Total issuance (kCERs)")) or 0,
                "retired_tco2e": kt(g(row, "Voluntary cancellations (kCERs)")) or 0,
                "issuance_by_vintage": {},
                "crediting_start": to_date(g(row, "Start 1st period")),
                "crediting_end": end,
                "cross_refs": cross_refs(g(row, "SD Tool, Gold Standard & CCB project number")),
                "beneficiaries": [],
                "source_version": version,
                "raw_hash": raw_hash,
                "kind": kind,
                "unfccc_uid": uid,
                "state_raw": g(row, "Province / State"),
                "credit_buyer_raw": g(row, "Credit buyer") if g(row, "Credit buyer") not in (None, "n.a.") else None,
                "pdd_consultant_raw": g(row, "PDD Consultant"),
                "transition_request": g(row, "Transition Request"),
                "mw": g(row, "MW"),
            }
            if rec["retired_tco2e"] > rec["issued_tco2e"]:
                rec["retired_tco2e"] = rec["issued_tco2e"]  # rounding of kCERs
            out.append(carry_over(rec, prev, today))
        if not out:
            raise SourceError("CDM: no Asian rows parsed")
        return out
