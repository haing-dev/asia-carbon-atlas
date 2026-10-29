from pipeline import common


def test_every_country_has_a_flag():
    """Flags: flag-icons (MIT), web/public/flags/<ISO3>.svg. Add one when a country is added to countries.yaml."""
    flags = common.ROOT / "web" / "public" / "flags"
    missing = [c for c in common.load_yaml("countries.yaml")["countries"] if not (flags / f"{c}.svg").exists()]
    assert missing == []
