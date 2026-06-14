from utils.fact_script import build_fact_rescue


def test_fact_rescue_uses_script_context_for_bee_electric_field_angle():
    story = {
        "id": "bee-electric",
        "title": "Bees use wing flash before they remember",
        "hook": "Start with the wing flash; it explains the next move",
        "script": "Flowers hum with invisible electric fields. Her tiny hairs sense the charge change.",
        "description": "A close clip of insects: macro shot of bee on lavender flowers",
    }

    repaired = build_fact_rescue(story, subject="Bees", lower_subject="bees", cue="wing flash", category="insects")

    assert repaired
    assert repaired["title"] == "Bees can sense electric fields on flowers"
    assert "electric fields" in repaired["script"]


def test_fact_rescue_uses_script_context_for_insect_feet_angle():
    story = {
        "id": "insect-feet",
        "title": "Insects use leaf movement before they remember",
        "hook": "Watch the leaf movement; the payoff lands seconds later",
        "script": "Watch their legs, claws and pads cling to leaves before they dart away.",
        "description": "A close clip of insects: hand holding insects",
    }

    repaired = build_fact_rescue(story, subject="Insects", lower_subject="insects", cue="leaf movement", category="insects")

    assert repaired
    assert repaired["title"] == "Insects cling with claws and foot pads"
    assert "claws and foot pads" in repaired["script"]


def test_fact_rescue_uses_script_context_for_insect_pollination_angle():
    story = {
        "id": "insect-pollen",
        "title": "Insects use leaf movement before they remember",
        "hook": "Watch the leaf movement; the payoff lands seconds later",
        "script": "These insects pollinate plants and carry pollen like tiny six-legged farmers.",
        "description": "A close clip of insects: hand holding insects",
    }

    repaired = build_fact_rescue(story, subject="Insects", lower_subject="insects", cue="movement", category="insects")

    assert repaired
    assert repaired["title"] == "Insects carry pollen between flowers"
    assert "pollen" in repaired["script"]
