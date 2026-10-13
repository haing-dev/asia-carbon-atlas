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
    monkeypatch.setattr(process, "load_offtakes", lambda: ({}, []))
    projects = process.build_projects()
    assert len(projects) == 1
    p = projects[0]
    assert p["issued_tco2e"] == 100 and [r["registry"] for r in p["registries"]] == ["VCS"]
    assert p["article6"]["mechanism"] == "Art. 6.2"


def test_vintage_overlap_counts_once():
    from pipeline.process import rollup
    cdm = {"registry": "CDM", "issued_tco2e": 300, "retired_tco2e": 0, "issuance_by_vintage": {"2010": 100, "2011": 200}}
    vcs = {"registry": "VCS", "issued_tco2e": 250, "retired_tco2e": 50, "issuance_by_vintage": {"2011": 200, "2012": 50}}
    issued, retired, by_vintage, overlap = rollup([cdm, vcs])
    assert (issued, overlap) == (350, True) and by_vintage == {"2010": 100, "2011": 200, "2012": 50}


def test_fuzzy_guards():
    from pipeline import dedupe
    def rec(rid, reg, name, **kw):
        r = {"record_id": rid, "registry": reg, "name": name, "countries": ["IND"], **kw}
        return r
    recs = [
        rec("CDM:1", "CDM", "Nam Mo 3 Hydropower Project, Vietnam"), rec("VCS:1", "VCS", "Nam Mo 3 Hydro Power Project"),
        rec("CDM:2", "CDM", "Distribution of Improved cook stove - Phase IV"), rec("VCS:2", "VCS", "Distribution of Improved cook stove - Phase VI"),
        rec("CDM:3", "CDM", "Enercon Wind Farm in Karnataka"), rec("VCS:3", "VCS", "Enercon Wind Farm in Rajasthan"),
        rec("CDM:4", "CDM", "Wind Power Project in Gujarat"), rec("VCS:4", "VCS", "Wind Power Project in Gujarat, India"),
    ]
    merge, _ = dedupe.fuzzy_links(recs, lambda r: "renewables")
    pairs = {tuple(sorted(p[:2])) for p in merge}
    assert ("CDM:1", "VCS:1") in pairs
    assert not pairs & {("CDM:2", "VCS:2"), ("CDM:3", "VCS:3"), ("CDM:4", "VCS:4")}


def test_cdm_buyers_parsed():
    from pipeline.process import cdm_buyers
    out = cdm_buyers({"registry": "CDM", "credit_buyer_raw": "Netherlands (AES AgriVerde), Switzerland (ACE-Asia) "})
    assert [(o["name"], o["country"]) for o in out] == [("AES AgriVerde", "Netherlands"), ("ACE-Asia", "Switzerland")]


def test_programme_activities_add_up_within_a_registry():
    from pipeline.process import estimate, rollup
    design = {"registry": "GS", "native_id": "100", "poa_id": 100, "est_annual_tco2e": 0, "issued_tco2e": 0}
    vpa1 = {"registry": "GS", "native_id": "101", "poa_id": 100, "est_annual_tco2e": 50, "issued_tco2e": 80,
            "issuance_by_vintage": {"2023": 80}}
    vpa2 = {"registry": "GS", "native_id": "102", "poa_id": 100, "est_annual_tco2e": 60, "issued_tco2e": 70,
            "issuance_by_vintage": {"2023": 70}}
    issued, _, by_vintage, overlap = rollup([design, vpa1, vpa2])
    assert (issued, by_vintage, overlap) == (150, {"2023": 150}, False)   # same vintage, different credits: added
    assert estimate([design, vpa1, vpa2]) == 110
    big_design = dict(design, est_annual_tco2e=500)
    assert estimate([big_design, vpa1, vpa2]) == 500                      # programme-level figure is larger
    # The same project in two registries: one registry's estimate, not a sum.
    assert estimate([{"registry": "VCS", "est_annual_tco2e": 90}, {"registry": "CDM", "est_annual_tco2e": 100}]) == 90


def test_unknown_volumes_stay_unknown():
    from pipeline.process import rollup
    issued, retired, _, _ = rollup([{"registry": "GCC", "issued_tco2e": None, "retired_tco2e": None}])
    assert issued is None and retired is None


def test_issued_projects_are_issuing_even_if_status_is_inactive():
    from pipeline.process import stage_of
    smap = {"VCS": {"inactive": "inactive", "registered": "registered"}}
    assert stage_of({"registry": "VCS", "registry_status_raw": "Inactive", "issued_tco2e": 5}, smap, "2026-10-12") == "issuing"
    assert stage_of({"registry": "VCS", "registry_status_raw": "Inactive", "issued_tco2e": 0}, smap, "2026-10-12") == "inactive"


def test_vrod_year_block_stops_at_next_block():
    from pipeline.sources.vrod import year_block
    header = ["First Year", "2020", "2021", "2022", "2020", "2021", "Owner"]
    assert year_block(header, 1) == [(1, "2020"), (2, "2021"), (3, "2022")]


def test_compact_row_drops_rebuildable_fields():
    from pipeline.build import compact_row
    p = {"project_id": "VCS:1", "display_name": "X", "developer": None, "countries": ["IND"], "country_shares": {"IND": 1.0},
         "registries": [{"record_id": "VCS:1", "registry": "VCS", "url": "https://registry.verra.org/app/projectDetail/VCS/1"},
                        {"record_id": "CDM:9", "registry": "CDM", "url": "https://cdm.unfccc.int/x"}],
         "years": {"listed": None, "registered": 2020, "first_issuance": None}, "issuance_by_vintage": {},
         "methodology_codes": [], "crediting": [None, None], "article6": None, "flags": [], "project_url": None,
         "developer_url": None,
         "offtakers": [], "cdm_buyers": [{"name": "Vitol", "type": "CDM credit buyer", "country": "Switzerland",
                                          "source_url": "https://unepccc.org/cdm-ji-pipeline/", "source_title": "t"}]}
    row = compact_row(p)
    assert row == {"id": "VCS:1", "n": "X", "c": ["IND"], "rg": ["VCS:1", ["CDM:9", "https://cdm.unfccc.int/x"]],
                   "y": [None, 2020, None]}


def test_gs_links_use_registry_page_id(tmp_path, monkeypatch):
    from pipeline import common, process
    monkeypatch.setattr(common, "ROOT", tmp_path)
    (tmp_path / "data" / "lookups").mkdir(parents=True)
    (tmp_path / "data" / "lookups" / "gsreg.jsonl").write_text('{"record_id": "GS:23411", "registry_id": "5335"}\n')
    recs = [{"record_id": "GS:23411", "registry": "GS", "native_id": "23411", "registry_url": "x", "cross_refs": []},
            {"record_id": "GS:99", "registry": "GS", "native_id": "99", "registry_url": "x", "cross_refs": []},
            {"record_id": "A62:X", "registry": "A62", "native_id": "X", "registry_url": "y", "cross_refs": ["GSREG:5335"]}]
    out = process.fix_gs_links(recs)
    assert out[0]["registry_url"] == "https://registry.goldstandard.org/projects/details/5335"
    assert out[1]["registry_url"] == "https://assurance-platform.goldstandard.org/project-documents/GS99"
    assert out[2]["cross_refs"] == ["GS:23411"]
