"""Berkeley Voluntary Registry Offsets Database (VROD): Verra (VCS), Gold Standard, Isometric.

Probe: the version label of the main download link on the VROD page (1 request).
Fetch: the main workbook (~17 MB) only when the version changes; keep Asian VCS/GS/ISO rows.
License CC BY 4.0 — cite per the VROD page.
"""
from __future__ import annotations

import io
import re

import openpyxl

from pipeline import common
from pipeline.http import PoliteClient
from pipeline.normalize import cross_refs, in_scope, methodology_codes, split_countries, to_date, to_int
from pipeline.sources.base import Source, SourceError, carry_over

PAGE = "https://gspp.berkeley.edu/berkeley-carbon-trading-project/offsets-database"
LINK_RE = re.compile(r'href="([^"]*Voluntary-Registry-Offsets-Database--v([0-9A-Za-z.-]+?)\.xlsx)"')
REGISTRY = {"VCS": "VCS", "GOLD": "GS", "GS": "GS", "ISO": "ISO", "ISOMETRIC": "ISO",
            "ACR": "ACR", "CAR": "CAR", "ART": "ART", "ART TREES": "ART"}
# ACR and ART moved to ICE GreenTrace (per-project pages are not linkable without a session): link the public project list.
LIST_PAGES = {"ACR": "https://greentrace.ice.com/acr/projects", "ART": "https://greentrace.ice.com/art/projects"}
HEADER_ROW = 3  # zero-based row index of the column headers in the PROJECTS sheet


def registry_url(reg: str, native: str, docs: str | None) -> str:
    if reg == "VCS":
        return f"https://registry.verra.org/verra/public/program/VCS/projects/{native}"
    if reg == "GS":  # page id differs from the GS number; process.fix_gs_links sets the real registry page
        return f"https://assurance-platform.goldstandard.org/project-documents/GS{native}"
    if reg == "CAR":
        return f"https://thereserve2.apx.com/mymodule/reg/prjView.asp?id1={native}"
    if reg in LIST_PAGES:
        return docs if docs and docs.startswith("http") and native.lower() in docs.lower() else LIST_PAGES[reg]
    if docs and docs.startswith("http") and native.lower() in docs.lower():
        return docs
    return docs if docs and docs.startswith("http") else "https://registry.isometric.com/"


def year_block(header: list[str], start: int) -> list[tuple[int, str]]:
    """(column, year) pairs for one run of increasing year columns starting at `start`."""
    out: list[tuple[int, str]] = []
    j = start
    while j < len(header) and re.fullmatch(r"\d{4}", header[j] or "") and (not out or header[j] > out[-1][1]):
        out.append((j, header[j]))
        j += 1
    return out


class Adapter(Source):
    implemented = True

    def probe(self) -> dict:
        client = PoliteClient()
        r = client.get(PAGE)
        r.raise_for_status()
        m = LINK_RE.search(r.text)
        if not m:
            raise SourceError("VROD download link not found on page")
        url = m.group(1)
        if url.startswith("/"):
            url = "https://gspp.berkeley.edu" + url
        return {"version": m.group(2), "url": url}

    def fetch(self, previous: list[dict], signal: dict) -> list[dict]:
        client = PoliteClient(timeout=300)
        r = client.get(signal["url"])
        r.raise_for_status()
        raw_hash = common.sha256_bytes(r.content)
        wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True, data_only=True)
        ws = wb["PROJECTS"]
        rows = ws.iter_rows(values_only=True, max_col=300)
        header = None
        for i, row in enumerate(rows):
            if i == HEADER_ROW:
                header = [" ".join(str(h).split()) if h is not None else "" for h in row]
                break
        if not header or "Project ID" not in header:
            raise SourceError("VROD PROJECTS header not found")

        def col(name: str) -> int:
            return header.index(name)

        c = {k: col(k) for k in [
            "Project ID", "Project Name", "Voluntary Registry", "Voluntary Status", "Scope", "Type",
            "Reduction / Removal", "Methodology / Protocol", "Country", "State", "Project Developer",
            "Total Credits Issued", "Total Credits Retired", "Estimated Annual Emission Reductions",
            "PoA / Aggregate ID", "Project Listed", "Project Registered", "Registry Documents",
            "Project Website", "Project Description", "Project Owner",
        ]}
        # Three year-blocks follow "First Year of Project (Vintage)": credits issued by vintage, credits retired
        # or cancelled in each year, credits remaining by vintage. Only the first is issuance by vintage: stop
        # where the years start again.
        years = year_block(header, col("First Year of Project (Vintage)") + 1)

        # "Credits issued by issuance year" block: the run of year columns right after "Project Website".
        iss_years = year_block(header, col("Project Website") + 1)

        prev = {p["record_id"]: p for p in previous}
        today = common.today()
        out = []
        for row in rows:
            if not row or row[c["Project ID"]] in (None, ""):
                continue
            reg = REGISTRY.get(str(row[c["Voluntary Registry"]] or "").strip().upper())
            if not reg:
                continue
            countries = split_countries(row[c["Country"]])
            if not in_scope(countries):
                continue
            pid = str(row[c["Project ID"]]).strip()
            native = re.sub(r"^(VCS|GS|GOLD|ISO|ACR|CAR|ART)[-_ ]?", "", pid, flags=re.I)
            vint = {y: to_int(row[j]) for j, y in years if to_int(row[j])}
            name = str(row[c["Project Name"]] or "").strip()
            rec = {
                "record_id": f"{reg}:{native}",
                "registry": reg,
                "native_id": native,
                "registry_url": registry_url(reg, native, row[c["Registry Documents"]]),
                "name": name,
                "developer_raw": (row[c["Project Developer"]] or row[c["Project Owner"]] or None),
                "participants_raw": row[c["Project Owner"]] or None,
                "countries": countries,
                "methodology_codes": methodology_codes(row[c["Methodology / Protocol"]]),
                "registry_type_raw": f"{row[c['Scope']] or ''} / {row[c['Type']] or ''}".strip(" /"),
                "registry_status_raw": row[c["Voluntary Status"]],
                "est_annual_tco2e": to_int(row[c["Estimated Annual Emission Reductions"]]),
                "issued_tco2e": to_int(row[c["Total Credits Issued"]]) or 0,
                "retired_tco2e": to_int(row[c["Total Credits Retired"]]) or 0,
                "issuance_by_vintage": vint,
                "crediting_start": None,
                "crediting_end": None,
                "cross_refs": [x for x in cross_refs(name, row[c["Project Description"]]) if x != f"{reg}:{native}"],
                "beneficiaries": [],
                "source_version": f"VROD v{signal['version']}",
                "raw_hash": raw_hash,
                "methodology_raw": row[c["Methodology / Protocol"]],
                "removal_raw": row[c["Reduction / Removal"]],
                "state_raw": row[c["State"]],
                "poa_id": row[c["PoA / Aggregate ID"]],
                "listed_date": to_date(row[c["Project Listed"]]),
                "registered_date": to_date(row[c["Project Registered"]]),
                "first_issuance_date": next((y for j, y in iss_years if to_int(row[j])), None),
                "project_website_raw": row[c["Project Website"]] or None,
            }
            out.append(carry_over(rec, prev, today))
        if not out:
            raise SourceError("VROD: no Asian rows parsed")
        return out
