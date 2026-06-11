from utils.loop_engine import LoopGenerator


def test_loop_plan_returns_valid_payload_for_empty_script():
    out = LoopGenerator().plan({}, {})

    assert out["callback_keyword"]
    assert out["final_line"]
    assert 0 <= out["loop_score"] <= 1


def test_loop_score_rises_with_callback_structure():
    generator = LoopGenerator()
    weak = generator.plan(
        {"script": "The octopus changes skin. Then the ocean moves on."},
        {"hook": "This octopus changes skin before it attacks."},
    )
    strong = generator.plan(
        {"script": "The octopus changes skin. That skin is the warning."},
        {"hook": "This octopus changes skin before it attacks."},
    )

    assert strong["loop_score"] >= weak["loop_score"]
    assert len(strong["final_line"].split()) <= 13
