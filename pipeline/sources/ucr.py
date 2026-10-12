"""Universal Carbon Registry (UCR) — CoU projects.

List:   one GET of the public project grid (all ~300 projects on one page).
Detail: /Registry/Details?id=... — location, type, contact, and every serial-number block
        (available, retired, tokenized). Issued = sum of the distinct serial ranges shown.
Probe: hash of the grid + the month, so details are re-read when the list changes and at least monthly
(~5 min at 1 request/second).
"""
from __future__ import annotations

import datetime as dt
import html as htmllib
import re

from pipeline import common
from pipeline.http import PoliteClient
from pipeline.normalize import in_scope, iso3
from pipeline.sources.base import Source, SourceError, carry_over

BASE = "https://www.ucarbonregistry.io"
GRID_URL = (f"{BASE}/CouRegistry/Grid?IsBindData=1&currentPageIndex=1&orderby=Id&IsAsc=0&PageSize=1000"
            "&SearchTitle=&ProjectId=&Type=&ProjectProponent=")
SERIAL_RE = re.compile(r"\b\d{4}-(\d{6,})-(\d{6,})-UCR-CoU-([A-Z]{2})-(\d+)-(\d{8})-(\d{8})\b")
INDIA_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat", "haryana",
    "himachal pradesh", "jharkhand", "karnataka", "kerala", "madhya pradesh", "maharashtra", "manipur",
    "meghalaya", "mizoram", "nagaland", "odisha", "orissa", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal", "delhi", "jammu and kashmir",
    "jammu & kashmir", "ladakh", "puducherry", "chandigarh", "andaman and nicobar islands",
    "dadra and nagar haveli", "daman and diu", "lakshadweep",
}


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_grid(page: str) -> list[dict]:
    out = []
    for block in re.split(r'<div class="listarea">', page)[1:]:
        a = re.search(r'<a href="(/Registry/Details\?id=[^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        title = clean(a.group(2))
        m = re.search(r"\(UCR ID Number:\s*(\d+)\)", title)
        if not m:
            continue

        def field(label: str) -> str | None:
            f = re.search(r">\s*" + re.escape(label) + r"\s*</p>\s*<p>(.*?)</p>", block, re.S)
            return clean(f.group(1)) if f else None

        badge = re.search(r'<span class="badge[^"]*">(.*?)</span>', block, re.S)
        out.append({
            "ucr_id": str(int(m.group(1))),
            "url": BASE + htmllib.unescape(a.group(1)),
            "title": title,
            "status": clean(badge.group(1)) if badge else None,
            "start_year": field("Start Year"),
            "end_year": field("End Year"),
            "location": field("Country, Province/State"),
            "type": field("Type"),
        })
    if not out:
        raise SourceError("UCR: no projects found in the grid")
    return out


def detail_text(page: str) -> str:
    page = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", " ", page, flags=re.S)
    text = re.sub(r"<[^>]+>", " | ", page)
    return re.sub(r"(\s*\|\s*)+", " | ", htmllib.unescape(text))


def after(text: str, label: str) -> str | None:
    m = re.search(re.escape(label) + r" \| ([^|]+?) \|", text)
    return m.group(1).strip() if m else None


def serials(text: str) -> tuple[int, int, dict[str, int], list[str]]:
    """(issued, retired, issued by vintage, country codes) from the distinct serial ranges on the page."""
    seen: dict[tuple, bool] = {}
    prev_end = 0
    for m in SERIAL_RE.finditer(text):
        key = (m.group(3), m.group(5), m.group(6), int(m.group(1)), int(m.group(2)))
        # Label between the previous serial and this one (e.g. "Retired CoU", "Burnt & Tokenized CoU").
        retired = "retire" in text[max(prev_end, m.start() - 160):m.start()].lower()
        prev_end = m.end()
        seen[key] = seen.get(key, False) or retired
    issued = retired = 0
    by_vintage: dict[str, int] = {}
    for (cc, start, _end, a, b), ret in seen.items():
        n = max(0, b - a + 1)
        issued += n
        retired += n if ret else 0
        by_vintage[start[4:]] = by_vintage.get(start[4:], 0) + n
    return issued, retired, dict(sorted(by_vintage.items())), sorted({k[0] for k in seen})


def country_of(text: str, codes: list[str], grid_location: str | None) -> list[str]:
    out = [c for c in (iso3(x) for x in codes) if c]
    if out:
        return out
    loc = after(text, "Location") or grid_location or ""
    for part in reversed(re.split(r"[,\s]{2,}|,", loc)):
        part = part.strip()
        if part.lower() in INDIA_STATES:
            return ["IND"]
        c = iso3(part) if len(part) > 3 else None
        if c:
            return [c]
    return ["IND"] if loc.strip().lower() in INDIA_STATES else []


def developer_of(title: str, text: str) -> str | None:
    m = re.search(r"\bby (.+?)\s*\(UCR ID", title, re.I)
    if m:
        dev = re.sub(r"\s*\([^)]*\)\s*$", "", m.group(1).strip())
        dev = re.sub(r",?\s*(India|Bangladesh|Viet ?nam|Indonesia|Thailand)\s*$", "", dev, flags=re.I)
        return dev or None
    return after(text, "Authorized Project Contact")


class Adapter(Source):
    implemented = True

    def probe(self) -> dict:
        r = PoliteClient(timeout=120).get(GRID_URL)
        r.raise_for_status()
        grid = parse_grid(r.text)
        return {"grid_hash": common.sha256_bytes(common.dumps(grid).encode())[:16],
                "projects": len(grid), "month": dt.date.today().strftime("%Y-%m")}

    def fetch(self, previous: list[dict], signal: dict) -> list[dict]:
        client = PoliteClient(timeout=120)
        r = client.get(GRID_URL)
        r.raise_for_status()
        prev = {p["record_id"]: p for p in previous}
        today = common.today()
        out = []
        for g in parse_grid(r.text):
            d = client.get(g["url"])
            if d.status_code != 200:
                old = prev.get(f"UCR:{g['ucr_id']}")
                if old:
                    out.append(old)  # keep the last good copy of this project
                continue
            text = detail_text(d.text)
            issued, retired, by_vintage, codes = serials(text)
            countries = country_of(text, codes, g["location"])
            if not countries or not in_scope(countries):
                continue
            name = re.sub(r"\s*\(UCR ID Number:\s*\d+\)\s*$", "", g["title"]).strip()
            rec = {
                "record_id": f"UCR:{g['ucr_id']}",
                "registry": "UCR",
                "native_id": g["ucr_id"],
                "registry_url": g["url"],
                "name": name,
                "developer_raw": developer_of(g["title"], text),
                "participants_raw": after(text, "Authorized Project Contact"),
                "countries": countries,
                "methodology_codes": [],
                "registry_type_raw": g["type"],
                "registry_status_raw": g["status"],
                "est_annual_tco2e": None,
                "issued_tco2e": issued,
                "retired_tco2e": retired,
                "issuance_by_vintage": by_vintage,
                "crediting_start": f"{g['start_year']}-01-01" if (g["start_year"] or "").isdigit() else None,
                "crediting_end": None,  # the grid's "End Year" is not the crediting-period end
                "cross_refs": [],
                "beneficiaries": [],
                "source_version": f"UCR registry {today}",
                "raw_hash": common.sha256_bytes(text.encode()),
                "listed_date": None,
                "registered_date": None,
                "first_issuance_date": None,  # UCR pages show vintages, not issuance dates
            }
            out.append(carry_over(rec, prev, today))
        return out
