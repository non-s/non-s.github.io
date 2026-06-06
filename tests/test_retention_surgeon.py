from utils.retention_surgeon import diagnose, remake_brief


def test_retention_surgeon_flags_weak_opening():
    story = {
        "title": "Cats purr to heal",
        "hook": "Did you know cats are amazing?",
        "script": "Did you know cats are amazing? Cats purr. It is neat.",
        "category": "cats",
    }
    out = diagnose(story)
    assert out["verdict"] == "rewrite"
    assert "weak_opener" in out["issues"]
    assert out["fixes"]


def test_retention_surgeon_rewards_tight_payoff():
    story = {
        "title": "Dogs remember faces after one meeting",
        "hook": "Dogs remember your face after one meeting.",
        "script": (
            "Dogs remember your face after one meeting. Watch their eyes "
            "because tiny gestures help them decide who feels familiar. "
            "That is why one calm voice can change the whole room."
        ),
        "category": "dogs",
    }
    assert diagnose(story)["score"] >= 80


def test_remake_brief_adds_rewrite_instructions():
    brief = remake_brief({"title": "Goats bury their heads", "script": "Today goats are amazing."})
    assert brief["retention_surgery"]["fixes"]
    assert "rewrite_instructions" in brief
