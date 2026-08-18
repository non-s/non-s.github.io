from utils.format_strategy import format_strategy


def test_short_strategy_is_immediate_without_manipulation():
    strategy = format_strategy(kind="short", duration=32, mood="fofura", scene="playful cat")
    assert strategy["orientation"] == "vertical 9:16"
    assert "immediately" in strategy["opening_contract"]
    assert "urgency" in strategy["rhythm"]


def test_long_strategy_prioritizes_a_calm_companion_session():
    strategy = format_strategy(kind="long", duration=900, mood="relax", scene="sleepy dog")
    assert strategy["orientation"] == "horizontal 16:9"
    assert "unhurried" in strategy["viewer_need"]
    assert "returning viewers" in strategy["success_signal"]


def test_short_strategy_has_all_required_fields():
    strategy = format_strategy(kind="short", duration=30, mood="focus", scene="orb")
    for key in ("orientation", "opening_contract", "rhythm", "viewer_need", "success_signal"):
        assert key in strategy, f"Missing key: {key}"


def test_long_strategy_has_all_required_fields():
    strategy = format_strategy(kind="long", duration=180, mood="ambient", scene="torus")
    for key in ("orientation", "opening_contract", "rhythm", "viewer_need", "success_signal"):
        assert key in strategy, f"Missing key: {key}"


def test_short_is_vertical_long_is_horizontal():
    short = format_strategy(kind="short", duration=30, mood="focus", scene="orb")
    long_ = format_strategy(kind="long", duration=180, mood="relax", scene="shell")
    assert "9:16" in short["orientation"]
    assert "16:9" in long_["orientation"]
