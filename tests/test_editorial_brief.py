from utils.editorial_brief import build_editorial_brief


def test_short_brief_is_a_discovery_asset():
    brief = build_editorial_brief(
        scene="sleepy cat by window", mood="relax", kind="short", duration=30, hook="Cozy cat"
    )
    assert brief["pillar"] == "atmospheric-pet-jazz"
    assert brief["format_role"] == "discovery and funnel entry"
    assert brief["primary_metric"] == "stayed to watch"


def test_long_brief_is_a_retention_asset():
    brief = build_editorial_brief(
        scene="dog relaxing", mood="relax", kind="long", duration=1800, hook="Gentle dog"
    )
    assert brief["pillar"] == "gentle-dog-jazz"
    assert brief["format_role"] == "retention session"
    assert brief["primary_metric"] == "average view duration"
