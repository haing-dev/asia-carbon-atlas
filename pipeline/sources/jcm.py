"""Joint Crediting Mechanism (Japan) — registered projects only (docs/SPEC.md §3).

Project list: https://www.jcm.go.jp/jc/projects (one static HTML table, all partner countries).
Issuances:    https://www.jcm.go.jp/jc/projects-issues (credits issued per monitoring period and country).
Detail page per registered project (fetched once, then reused): estimated emission reductions per year.
Probe: ETag/Last-Modified of the two list pages (served from S3, 2 HEAD requests).
"""
from __future__ import annotations

import html as htmllib
import re
import statistics

from pipeline import common
from pipeline.http import PoliteClient
from pipeline.normalize import in_scope, iso3, to_date
from pipeline.sources.base import Source, SourceError, carry_over

BASE = "https://www.jcm.go.jp"
LIST_URL = f"{BASE}/jc/projects"
ISSUES_URL = f"{BASE}/jc/projects-issues"
REGISTERED = "project registered"


def clean(s: str) -> str:
    s = htmllib.unescape(re.sub(r"<[^>]+>", " ", htmllib.unescape(s)))
    return re.sub(r"\s+", " ", s).strip()


def parse_list(page: str) -> list[dict]:
    i = page.find('id="pro_list"')
    if i < 0:
        raise SourceError("JCM: project table #pro_list not found")
    body = page[i:page.find("</table>", i)]
    out = []
    for row in re.findall(r'<tr class="data-row">(.*?)</tr>', body, re.S):
        cells = {k: v for k, v in re.findall(r'<td class="(\w+)">(.*?)</td>', row, re.S)}
        link = re.search(r'href="([^"]+)"', cells.get("Reference_number", ""))
        out.append({k: clean(v) for k, v in cells.items()} | {"url": link.group(1) if link else None})
    if not out:
        raise SourceError("JCM: no project rows found")
    return out


def parse_issues(page: str) -> dict[str, dict]:
    """ref -> {issued, first_issuance}; sums every country row of every monitoring period listed."""
    i = page.find('id="refno_desc"')
    if i < 0:
        raise SourceError("JCM: issuance table not found")
    body = page[i:page.find("</table>", i)]
    out: dict[str, dict] = {}
    ref = None
    for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        tds = [clean(t) for t in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(tds) == 8 and re.fullmatch(r"[A-Z]{2}\d{3}", tds[0]):
            ref, tail = tds[0], tds[4:]
        elif len(tds) == 4 and ref:
            tail = tds
        else:
            continue
        amount = re.sub(r"[^\d]", "", tail[3])
        d = to_date(tail[2])
        e = out.setdefault(ref, {"issued": 0, "first_issuance": None})
        e["issued"] += int(amount) if amount else 0
        if d and (not e["first_issuance"] or d < e["first_issuance"]):
            e["first_issuance"] = d
    return out


def estimated_annual(page: str) -> int | None:
    """Median of the non-zero 'Estimated emission reductions in each year' values on the detail page."""
    text = clean(re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S))
    k = text.find("Estimated emission reductions in each year")
    if k < 0:
        return None
    vals = [int(v.replace(",", "")) for v in re.findall(r"([\d,]+) \(in (?:19|20)\d\d\)", text[k:k + 3000])]
    vals = [v for v in vals if v > 0]
    return int(statistics.median(vals)) if vals else None


def participants(s: str) -> list[str]:
    return [p.strip() for p in re.split(r";", s or "") if p.strip()]


class Adapter(Source):
    implemented = True

    def probe(self) -> dict:
        client = PoliteClient()
        sig = {}
        for name, url in (("list", LIST_URL), ("issues", ISSUES_URL)):
            r = client.head(url)
            r.raise_for_status()
            sig[name] = r.headers.get("etag") or r.headers.get("last-modified")
        return sig

    def fetch(self, previous: list[dict], signal: dict) -> list[dict]:
        client = PoliteClient(timeout=120)
        r = client.get(LIST_URL)
        r.raise_for_status()
        rows = parse_list(r.text)
        r = client.get(ISSUES_URL)
        r.raise_for_status()
        issues = parse_issues(r.text)
        prev = {p["record_id"]: p for p in previous}
        today = common.today()
        out = []
        for row in rows:
            if row.get("Status", "").lower() != REGISTERED:
                continue
            country = iso3(row.get("Host_country"))
            if not country or not in_scope([country]):
                continue
            ref = row["Reference_number"].upper()
            rid = f"JCM:{ref}"
            url = row["url"] or f"{BASE}/jc/projects/{ref.lower()}/"
            old = prev.get(rid)
            if old and old.get("est_annual_tco2e") is not None:
                est = old["est_annual_tco2e"]
            else:
                d = client.get(url)
                est = estimated_annual(d.text) if d.status_code == 200 else None
            iss = issues.get(ref, {})
            jp, host = participants(row.get("Japanese_participant")), participants(row.get("Host_country_participant"))
            rec = {
                "record_id": rid,
                "registry": "JCM",
                "native_id": ref,
                "registry_url": url,
                "name": row.get("Project_title"),
                "developer_raw": jp[0] if jp else (host[0] if host else None),
                "participants_raw": "; ".join(jp + host) or None,
                "countries": [country],
                "methodology_codes": [m for m in re.findall(r"[A-Z]{2}_AM\d{3}", row.get("Methodology_no", ""))],
                "registry_type_raw": None,
                "registry_status_raw": row.get("Status"),
                "est_annual_tco2e": est,
                "issued_tco2e": iss.get("issued", 0),
                "retired_tco2e": None,
                "issuance_by_vintage": {},
                "crediting_start": None,
                "crediting_end": None,
                "cross_refs": [],
                "beneficiaries": [],
                "source_version": f"JCM website {today}",
                "raw_hash": common.sha256_bytes(common.dumps(row).encode()),
                "listed_date": None,
                "registered_date": to_date(row.get("Registration_date")),
                "first_issuance_date": iss.get("first_issuance"),
            }
            out.append(carry_over(rec, prev, today))
        return out
