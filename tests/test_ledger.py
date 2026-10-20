from pipeline import common, ledger


def test_every_deal_source_is_in_the_ledger():
    """Run `python -m pipeline.ledger sync` after editing config/offtakers.yaml."""
    rows = ledger.load()
    cfg = common.load_yaml("offtakers.yaml")
    urls = [o["source_url"] for o in cfg["offtakes"]] + [o["source_url"] for a in cfg["announced_rows"] for o in a["offtakes"]]
    missing = [u for u in urls if rows.get(ledger.norm(u), {}).get("outcome") != "added"]
    assert missing == []
