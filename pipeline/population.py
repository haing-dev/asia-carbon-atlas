"""Write config/population.csv from UN World Population Prospects 2024 (medium variant, 1 July 2025).

Used only to split multi-country projects' volumes across host countries (SPEC §8).
Run rarely (the file is committed): `python -m pipeline.population` (via the `tools` workflow).
"""
from __future__ import annotations

import csv
import gzip
import io

from pipeline import common
from pipeline.http import PoliteClient

URL = ("https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/CSV_FILES/"
       "WPP2024_Demographic_Indicators_Medium.csv.gz")
YEAR = "2025"
OUT = common.CONFIG / "population.csv"


def main() -> None:
    r = PoliteClient(timeout=600).get(URL)
    r.raise_for_status()
    data = gzip.decompress(r.content) if r.content[:2] == b"\x1f\x8b" else r.content
    ours = set(common.load_yaml("countries.yaml")["countries"])
    rows = {}
    for row in csv.DictReader(io.StringIO(data.decode("utf-8-sig", errors="replace"))):
        iso = row.get("ISO3_code")
        if iso and len(iso) == 3 and row.get("Time") == YEAR and row.get("Variant", "Medium") == "Medium":
            rows[iso] = round(float(row["TPopulation1July"]) * 1000)  # thousands -> persons
    missing = sorted(ours - set(rows))  # all countries are kept: non-Asian hosts dilute the Asian share
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(f"# UN DESA, World Population Prospects 2024, medium variant, total population 1 July {YEAR}.\n")
        f.write(f"# Source: {URL}\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["iso3", "population"])
        for iso in sorted(rows):
            w.writerow([iso, rows[iso]])
    print(f"wrote {len(rows)} countries to {OUT}; missing: {missing or 'none'}")


if __name__ == "__main__":
    main()
