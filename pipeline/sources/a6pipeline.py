"""UNEP-CCC Article 6 Pipeline (https://a6pipeline.unepccc.org/), public JSON behind its activity tables.

- Article 6.4 (PACM): registered activities (today all CDM transitions) -> PACM records, cross-referenced
  to the CDM record so they merge into one project. Component projects (CPAs) are summed per programme.
- Article 6.2 (bilateral): activities -> annotation records ("role": "annotation") that tag the matching
  JCM/Verra/Gold Standard project with Article 6.2 status and buyer country. They never add volume.
  Authorised 6.2 activities with no registry record elsewhere become their own rows (registry A62).
Probe = hash of both tables (2 POST requests); fetch reuses the probe's responses.
"""
from __future__ import annotations

import html as htmllib
import re

import pycountry

from pipeline import common
from pipeline.http import PoliteClient
from pipeline.normalize import in_scope, iso3
from pipeline.sources.base import Source, SourceError, carry_over

BASE = "https://a6pipeline.unepccc.org"
API = f"{BASE}/api/graphs/4003"
PAYLOADS = {
    "pacm": {"show_as": "table", "source": "pacm", "pacm_stage": "all_all_registered"},
    "a6p2": {"show_as": "table", "source": "a6p2"},
}
SKIP_62 = {"withdrawn", "rejected", "proposed"}
STANDALONE_62 = {"registered", "mo issued"}
LINK_REFS = [
    (re.compile(r"registry\.verra\.org/app/projectDetail/VCS/(\d+)", re.I), "VCS:{}"),
    (re.compile(r"registry\.goldstandard\.org/projects/details/(\d+)", re.I), "GS:{}"),
    (re.compile(r"jcm\.go\.jp/jc/projects/([a-z]{2}\d{3})", re.I), "JCM:{}"),
]


def clean(s) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()


def link(docs) -> str | None:
    m = re.search(r'href="([^"]+)"', str(docs or ""))
    return htmllib.unescape(m.group(1)) if m else None


def num(v) -> int:
    return int(v) if isinstance(v, (int, float)) else 0


def buyer(a6_id: str) -> str | None:
    parts = a6_id.split("-")
    if len(parts) < 3 or parts[1] == "ND":
        return None
    c = pycountry.countries.get(alpha_2=parts[1])
    return getattr(c, "common_name", None) or (c.name if c else parts[1])


def link_refs(url: str | None) -> list[str]:
    refs = []
    for rx, fmt in LINK_REFS:
        m = rx.search(url or "")
        if m:
            refs.append(fmt.format(m.group(1).upper()))
    return refs


def table_rows(resp: dict) -> list[dict]:
    try:
        return resp["response"]["data"]["blocks"][0]["data"]["rows"]
    except (KeyError, IndexError, TypeError) as e:
        raise SourceError(f"A6 pipeline: unexpected response shape ({e})") from e


def pacm_records(rows: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(str(r["id"]), []).append(r)
    out = []
    for aid, members in groups.items():
        countries = sorted({c for c in (iso3(m.get("country")) for m in members) if c})
        if not countries or not in_scope(countries):
            continue
        heads = [m for m in members if not m.get("cp_id")]
        head = heads[0] if heads else members[0]
        cpas = [m for m in members if m.get("cp_id")]
        est = num(head.get("pm_raw")) if heads and num(head.get("pm_raw")) else sum(num(m.get("pm_raw")) for m in cpas)
        # Only component projects listed: the CPA title doesn't name the programme; the CDM record does.
        title = clean(head.get("title")) if heads else None
        out.append({
            "record_id": f"PACM:{aid}",
            "registry": "PACM",
            "native_id": aid,
            "registry_url": link(head.get("docs")) or next((link(m.get("docs")) for m in members if link(m.get("docs"))), None) or BASE + "/",
            "name": title,
            "developer_raw": None,
            "participants_raw": None,
            "countries": countries,
            "methodology_codes": sorted({m["meth"] for m in members if m.get("meth")}),
            "registry_type_raw": " / ".join(x for x in (head.get("activity_type"), head.get("subtype")) if x),
            "registry_status_raw": "Registered (CDM transition)" if "CDM Transition" in (head.get("tags") or "") else "Registered",
            "est_annual_tco2e": est or None,
            "issued_tco2e": sum(num(m.get("er_issued_raw")) for m in members),
            "retired_tco2e": None,
            "issuance_by_vintage": {},
            "crediting_start": None,
            "crediting_end": None,
            "cross_refs": [f"CDM:{int(aid)}"] if aid.isdigit() else [],
            "beneficiaries": [],
            "article6": {"mechanism": "Art. 6.4", "buyer_countries": [], "status": "Registered"},
            "components": len(cpas) or None,
        })
    return out


def a62_records(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        status = clean(r.get("tags"))
        if status.lower() in SKIP_62:
            continue
        country = iso3(r.get("country"))
        if not country or not in_scope([country]):
            continue
        url = link(r.get("docs"))
        refs = link_refs(url)
        b = buyer(str(r["id"]))
        standalone = not refs and status.lower() in STANDALONE_62 and bool(url)
        if not refs and not standalone:
            continue
        out.append({
            "record_id": f"A62:{r['id']}",
            "registry": "A62",
            "native_id": str(r["id"]),
            "registry_url": url,
            "name": clean(r.get("title")),
            "developer_raw": None,
            "participants_raw": None,
            "countries": [country],
            "methodology_codes": [r["meth"]] if r.get("meth") else [],
            "registry_type_raw": " / ".join(x for x in (r.get("activity_type"), r.get("subtype")) if x),
            "registry_status_raw": status,
            "est_annual_tco2e": num(r.get("pm_raw")) or None,
            "issued_tco2e": num(r.get("er_issued_raw")),
            "retired_tco2e": None,
            "issuance_by_vintage": {},
            "crediting_start": None,
            "crediting_end": None,
            "cross_refs": refs,
            "beneficiaries": [],
            "article6": {"mechanism": "Art. 6.2", "buyer_countries": [b] if b else [], "status": status,
                         "itmos_transferred": num(r.get("itmos_raw")) or None},
            "role": "record" if standalone else "annotation",
        })
    return out


class Adapter(Source):
    implemented = True
    _cache: dict | None = None

    def _get(self) -> dict:
        if self._cache is None:
            client = PoliteClient(timeout=120)
            self._cache = {}
            for key, payload in PAYLOADS.items():
                r = client.post_json(API, payload)
                r.raise_for_status()
                data = r.json()
                if not data.get("status"):
                    raise SourceError(f"A6 pipeline {key}: status false")
                self._cache[key] = table_rows(data)
        return self._cache

    def probe(self) -> dict:
        data = self._get()
        return {k: common.sha256_bytes(common.dumps(v).encode())[:16] for k, v in data.items()} | {
            "rows": {k: len(v) for k, v in data.items()}}

    def fetch(self, previous: list[dict], signal: dict) -> list[dict]:
        data = self._get()
        prev = {p["record_id"]: p for p in previous}
        today = common.today()
        out = []
        for rec in pacm_records(data["pacm"]) + a62_records(data["a6p2"]):
            rec["source_version"] = f"UNEP-CCC Article 6 Pipeline {today}"
            rec["raw_hash"] = common.sha256_bytes(common.dumps(rec).encode())
            out.append(carry_over(rec, prev, today))
        return out
