"""Shared normalisation helpers: countries, numbers, dates, cross-reference extraction."""
from __future__ import annotations

import datetime as dt
import re

import pycountry

from pipeline import common

# Names seen in registries that pycountry doesn't resolve on its own.
ALIASES = {
    "viet nam": "VNM", "vietnam": "VNM", "lao pdr": "LAO", "laos": "LAO", "lao": "LAO",
    "lao people's democratic republic": "LAO", "korea": "KOR", "south korea": "KOR",
    "republic of korea": "KOR", "korea, republic of": "KOR", "korea (republic of)": "KOR",
    "north korea": "PRK", "democratic people's republic of korea": "PRK", "taiwan": "TWN",
    "chinese taipei": "TWN", "taiwan, province of china": "TWN", "hong kong": "HKG",
    "hong kong sar": "HKG", "macau": "MAC", "macao": "MAC", "burma": "MMR", "myanmar": "MMR",
    "brunei": "BRN", "brunei darussalam": "BRN", "east timor": "TLS", "timor leste": "TLS",
    "timor-leste": "TLS", "kyrgyz republic": "KGZ", "kyrgyzstan": "KGZ", "iran": "IRN",
    "türkiye": "TUR", "turkey": "TUR", "russia": "RUS", "bolivia": "BOL", "tanzania": "TZA",
    "congo, democratic republic of the": "COD", "democratic republic of the congo": "COD",
    "drc": "COD", "cote d'ivoire": "CIV", "côte d'ivoire": "CIV", "ivory coast": "CIV",
    "swaziland": "SWZ", "eswatini": "SWZ", "cape verde": "CPV", "moldova": "MDA",
    "venezuela": "VEN", "syria": "SYR", "palestine": "PSE", "micronesia": "FSM",
    "united states": "USA", "usa": "USA", "united kingdom": "GBR", "uk": "GBR",
    "czech republic": "CZE", "the gambia": "GMB", "gambia": "GMB", "kosovo": "XKX",
    "china": "CHN", "people's republic of china": "CHN",
}

_cache: dict[str, str | None] = {}


def iso3(name: str | None) -> str | None:
    """Country name or ISO2/ISO3 code -> ISO3 (None if unknown)."""
    if not name:
        return None
    key = name.strip().lower()
    if key in _cache:
        return _cache[key]
    out = ALIASES.get(key)
    if not out:
        s = name.strip()
        try:
            if len(s) == 2:
                out = pycountry.countries.get(alpha_2=s.upper()).alpha_3
            elif len(s) == 3 and s.isupper():
                out = pycountry.countries.get(alpha_3=s).alpha_3
            else:
                out = pycountry.countries.lookup(s).alpha_3
        except (LookupError, AttributeError):
            try:
                out = pycountry.countries.search_fuzzy(s)[0].alpha_3
            except LookupError:
                out = None
    _cache[key] = out
    return out


def split_countries(text: str | None) -> list[str]:
    """'India, Nepal' / 'India; Nepal' -> ['IND', 'NPL'] (order kept, unknowns dropped)."""
    if not text:
        return []
    out: list[str] = []
    for part in re.split(r"[;,/]|\band\b", str(text)):
        c = iso3(part.strip())
        if c and c not in out:
            out.append(c)
    return out


_in_scope: set[str] | None = None


def in_scope(countries: list[str]) -> bool:
    global _in_scope
    if _in_scope is None:
        _in_scope = set(common.load_yaml("countries.yaml")["countries"])
    return any(c in _in_scope for c in countries)


def to_int(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(round(float(str(v).replace(",", ""))))
    except ValueError:
        return None


def to_date(v) -> str | None:
    if v is None or v == "":
        return None
    if isinstance(v, (dt.datetime, dt.date)):
        if isinstance(v, dt.datetime) and v.year < 1900:
            return None
        return v.date().isoformat() if isinstance(v, dt.datetime) else v.isoformat()
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if 1900 <= v <= 2100:  # a bare year
            return str(int(v))
        if 20000 <= v <= 80000:  # Excel serial date
            return (dt.date(1899, 12, 30) + dt.timedelta(days=int(v))).isoformat()
        return None
    s = str(v).strip()
    if re.fullmatch(r"(19|20)\d\d", s):
        return s
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y", "%d %b %y", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S", "%d-%b-%Y", "%b %d, %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


METH_RE = re.compile(
    r"\b(VM\d{4}|VMR\d{4}|AR-A[CM]{1,2}\d{4}|AR-AMS\d{4}|ACM\d{4}|AMS-[IV]{1,3}\.[A-Z]{1,3}\.?|AM\d{4}|"
    r"GS-?[A-Z]*\d+|TPDDTEC|MSW\d*)\b"
)


def methodology_codes(text: str | None) -> list[str]:
    if not text:
        return []
    return sorted({m.rstrip(".") for m in METH_RE.findall(str(text))})


XREF_PATTERNS = [
    ("CDM", re.compile(r"\bCDM\s*(?:ref(?:erence)?\.?|project|no\.?|#|id)?\s*:?\s*(\d{3,5})\b", re.I)),
    ("VCS", re.compile(r"\bVCS\s*(?:ID|#|no\.?)?\s*:?\s*(\d{2,5})\b", re.I)),
    ("GS", re.compile(r"\b(?:GS|Gold Standard)\s*(?:ID|#|no\.?)?\s*:?\s*(\d{2,5})\b", re.I)),
    ("GCC", re.compile(r"\bGCC\s*(?:ID|#|no\.?)?\s*:?\s*S?\d*?(\d{2,5})\b", re.I)),
    ("ACR", re.compile(r"\bACR\s*(?:ID|#|no\.?)?\s*:?\s*(\d{2,4})\b")),
    ("CAR", re.compile(r"\bCAR\s*(?:ID|#|no\.?)?\s*:?\s*(\d{3,4})\b")),
    ("UCR", re.compile(r"\bUCR\s*(?:ID|#|no\.?)?\s*:?-?\s*(\d{2,5})\b", re.I)),
]


def cross_refs(*texts: str | None) -> list[str]:
    refs: set[str] = set()
    for t in texts:
        if not t:
            continue
        for reg, rx in XREF_PATTERNS:
            for m in rx.findall(str(t)):
                refs.add(f"{reg}:{int(m)}")
    return sorted(refs)
