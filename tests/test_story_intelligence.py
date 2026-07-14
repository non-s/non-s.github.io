from utils.story_intelligence import audit_hook, audit_title, classify_format, postmortem


def test_classify_format_detects_memory():
    assert classify_format("Chickens remember faces and hold grudges") == "animal_memory"


def test_classify_format_keeps_physical_nature_out_of_animal_intelligence():
    text = "Storm clouds spread sunlight before it reaches the ground. " "Which light clue should we compare next?"

    assert classify_format(text, category="earth_from_space") == "earth_engine"
    assert classify_format(text) == "earth_engine"


def test_audit_hook_rewards_direct_payoff():
    audit = audit_hook("Chickens remember your face.")
    assert audit.score >= 80
    assert audit.issues == ()


def test_audit_hook_flags_weak_question():
    audit = audit_hook("Why are chickens smarter than you think?")
    assert audit.score < 80
    assert "weak_first_word" in audit.issues


def test_audit_title_flags_missing_animal_keyword():
    audit = audit_title("A secret nobody tells you")
    assert "missing_animal_keyword" in audit.issues


def test_audit_title_penalizes_repetitive_template():
    audit = audit_title("Cows have another signal hiding in plain sight")
    assert "repetitive_template" in audit.issues
    assert audit.score < 90


def test_audit_title_rewards_specific_action():
    audit = audit_title("Ducks fake injuries to trick predators")
    assert "weak_curiosity_shape" not in audit.issues
    assert audit.score >= 80


def test_audit_title_recognizes_birds_plural():
    audit = audit_title("Birds read the moment from one wing angle")
    assert "missing_animal_keyword" not in audit.issues
    assert "animal_not_front_loaded" not in audit.issues
    assert audit.score >= 80


def test_postmortem_collects_likely_causes():
    out = postmortem(
        title="A secret nobody tells you",
        hook="Why is this happening?",
        views=25,
        views_per_hour=1,
        average_view_percentage=35,
        growth_score=20,
    )
    assert "hook_needs_work" in out["likely_causes"]
    assert "low_retention" in out["likely_causes"]
