from pipeline import checks
from pipeline.process import build_projects


def test_no_duplicate_projects_or_deals():
    errors, _ = checks.run(build_projects())
    assert errors == []
