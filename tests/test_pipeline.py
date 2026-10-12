import json

from pipeline import common, validate
from pipeline.process import country_shares


def test_write_jsonl_is_deterministic(tmp_path):
    p = tmp_path / "x.jsonl"
    rows = [{"record_id": "B", "registry": "CDM"}, {"record_id": "A", "registry": "VCS"}]
    assert common.write_jsonl_if_changed(p, rows) is True
    assert common.write_jsonl_if_changed(p, list(reversed(rows))) is False
    first = json.loads(p.read_text().splitlines()[0])
    assert first["record_id"] == "A"
    assert list(first)[:3] == ["record_id", "registry", "native_id"]


def test_country_shares_population_weighted():
    shares = country_shares(["IND", "NPL", "KEN"], {"IND", "NPL"}, {"IND": 90, "NPL": 5, "KEN": 5})
    assert shares == {"IND": 0.9, "NPL": 0.05}


def test_validation_catches_bad_records():
    bad = [{"record_id": "VCS:1", "registry": "VCS", "native_id": "1", "registry_url": "x",
            "countries": ["IND"], "issued_tco2e": 5, "retired_tco2e": 9}]
    errs = validate.check_records(bad)
    assert any("not a URL" in e for e in errs)
    assert any("retired > issued" in w for w in validate.WARNINGS)


def test_jcm_issues_sum_country_rows():
    from pipeline.sources.jcm import parse_issues
    page = ('<table id="refno_desc"><tbody><tr><td colspan="8">t</td></tr>'
            '<tr><td rowspan="2">VN014</td><td rowspan="2">p</td><td rowspan="2">31 Oct 24</td><td rowspan="2">379</td>'
            '<td>Viet Nam</td><td>189</td><td>05 Mar 25</td><td>189</td></tr>'
            '<tr><td>Japan</td><td>190</td><td>14 Nov 24</td><td>190</td></tr></tbody></table>')
    assert parse_issues(page) == {"VN014": {"issued": 379, "first_issuance": "2024-11-14"}}


def test_ucr_serial_ranges_are_counted_once():
    from pipeline.sources.ucr import serials
    s = "0001-000001-002119-UCR-CoU-IN-028-23012020-31122020"
    text = f"Serial Number | {s} | Retired CoU | {s} | 0001-002120-002463-UCR-CoU-IN-028-01012021-31122021"
    issued, retired, by_vintage, codes = serials(text)
    assert (issued, retired, codes) == (2119 + 344, 2119, ["IN"])
    assert by_vintage == {"2020": 2119, "2021": 344}


def test_article6_annotation_tags_without_adding_volume(monkeypatch):
    from pipeline import process
    base = {"countries": ["KHM"], "registry_url": "https://x", "registry_status_raw": None}
    recs = [
        base | {"record_id": "VCS:2925", "registry": "VCS", "name": "Cookstoves", "issued_tco2e": 100},
        base | {"record_id": "A62:KH-ND-2925", "registry": "A62", "role": "annotation", "issued_tco2e": 90,
                "cross_refs": ["VCS:2925"], "article6": {"mechanism": "Art. 6.2", "buyer_countries": [], "status": "MO issued"}},
        base | {"record_id": "A62:XX-JP-0001", "registry": "A62", "role": "annotation", "cross_refs": ["JCM:XX001"]},
    ]
    monkeypatch.setattr(process.common, "load_all_records", lambda: recs)
    projects = process.build_projects()
    assert len(projects) == 1
    p = projects[0]
    assert p["issued_tco2e"] == 100 and [r["registry"] for r in p["registries"]] == ["VCS"]
    assert p["article6"]["mechanism"] == "Art. 6.2"
