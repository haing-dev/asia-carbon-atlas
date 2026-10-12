"""Puro.earth Registry (engineered carbon removal: biochar, ERW, carbonated materials...).

The public /projects page embeds every project as JSON (Next.js payload). Asian projects' detail
pages show issued/retired totals and the issuance list.
Probe: hash of the embedded project list + the newest issuance on /issuances (2 requests).
Fetch: detail page per Asian project only.
"""
from __future__ import annotations

import json
import re

from pipeline import common
from pipeline.http import PoliteClient
from pipeline.normalize import in_scope, iso3, to_date
from pipeline.sources.base import Source, SourceError, carry_over

BASE = "https://registry.puro.earth"
PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')
METHODOLOGY_RE = re.compile(r'"methodologyCode":"(\w+)"[^{}]*?"methodology":\{"code":"\w+","name":"([^"]+)"')


def next_payload(html: str) -> str:
    """Concatenate the Next.js flight payload chunks embedded in the page."""
    return "".join(json.loads(f'"{m}"') for m in PUSH_RE.findall(html))


def embedded_objects(payload: str, key: str) -> list[dict]:
    """All JSON objects in the payload that start with {"<key>": ..."""
    dec = json.JSONDecoder()
    out, seen = [], set()
    for m in re.finditer(r'\{"' + re.escape(key) + '":', payload):
        try:
            obj, _ = dec.raw_decode(payload, m.start())
        except json.JSONDecodeError:
            continue
        ident = json.dumps(obj, sort_keys=True)
        if ident not in seen:
            seen.add(ident)
            out.append(obj)
    return out


def text_of(html: str) -> str:
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def num(s: str) -> int:
    return int(s.replace(",", "").replace(" ", "").replace(" ", ""))


class Adapter(Source):
    implemented = True

    def _projects(self, client: PoliteClient) -> list[dict]:
        r = client.get(f"{BASE}/projects")
        r.raise_for_status()
        projects = embedded_objects(next_payload(r.text), "projectId")
        if not projects:
            raise SourceError("Puro: no embedded project list found")
        return projects

    def probe(self) -> dict:
        client = PoliteClient()
        projects = self._projects(client)
        r = client.get(f"{BASE}/issuances")
        r.raise_for_status()
        first = re.search(r"(\d{1,2} \w{3,5} \d{4}) ([^|]{3,120}?) (\d[\d,]*) ", text_of(r.text))
        return {
            "projects_hash": common.sha256_bytes(common.dumps(projects).encode())[:16],
            "newest_issuance": first.group(0)[:160] if first else None,
        }

    def fetch(self, previous: list[dict], signal: dict) -> list[dict]:
        client = PoliteClient()
        projects = self._projects(client)
        prev = {p["record_id"]: p for p in previous}
        today = common.today()
        out = []
        for p in projects:
            country = iso3(p.get("countryCode"))
            if not country or not in_scope([country]):
                continue
            pid = str(p.get("projectId") or p.get("code"))
            url = f"{BASE}/projects/{pid}"
            r = client.get(url)
            r.raise_for_status()
            text = text_of(r.text)
            issued = re.search(r"Issued credits ([\d,  ]+?) Retired", text)
            retired = re.search(r"Retired credits ([\d,  ]+?) ", text)
            meth = p.get("methodology") or {}
            # Issuance rows read "07 Sept 2023 22 Biochar, ..." -> dates of each issuance listed on the page.
            iss_dates = sorted(filter(None, (to_date(f"{d} {m[:3]} {y}")
                                             for d, m, y in re.findall(r"\b(\d{1,2}) ([A-Z][a-z]{2,4}) (\d{4}) [\d,]+ ", text))))
            rec = {
                "record_id": f"PURO:{pid}",
                "registry": "PURO",
                "native_id": pid,
                "registry_url": url,
                "name": p.get("name"),
                "developer_raw": p.get("supplierName"),
                "participants_raw": None,
                "countries": [country],
                "methodology_codes": [meth.get("name") or p.get("methodologyCode")] if (meth or p.get("methodologyCode")) else [],
                "registry_type_raw": meth.get("name") or p.get("methodologyCode"),
                "registry_status_raw": "issuing" if issued and num(issued.group(1)) > 0 else "registered",
                "est_annual_tco2e": None,
                "issued_tco2e": num(issued.group(1)) if issued else 0,
                "retired_tco2e": num(retired.group(1)) if retired else 0,
                "issuance_by_vintage": {},
                "crediting_start": to_date(p.get("creditingPeriodStart")),
                "crediting_end": to_date(p.get("creditingPeriodEnd")),
                "cross_refs": [],
                "beneficiaries": [],
                "source_version": f"Puro Registry {today}",
                "raw_hash": common.sha256_bytes(r.content),
                "supplier_listing_url": p.get("supplierListingUrl"),
                "listed_date": None,
                "registered_date": to_date(p.get("creditingPeriodStart")),
                "first_issuance_date": iss_dates[0] if iss_dates else None,
            }
            out.append(carry_over(rec, prev, today))
        return out
