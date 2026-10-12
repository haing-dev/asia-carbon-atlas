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
    assert any("retired > issued" in e for e in errs)
