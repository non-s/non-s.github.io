from utils.liquid_wire_composer import build_composition
from utils.liquid_wire_timeline import build_timeline
from utils.living_scene import build_scene, identify_scene, orchestrate_scene, scene_distance, scene_music

FAMILIES = ("orb", "torus", "ribbon", "knot", "gyroid", "helix")


def test_scene_is_deterministic_compound_and_identified():
    first = build_scene(42, "short", FAMILIES, "orb")
    second = build_scene(42, "short", FAMILIES, "orb")
    assert first == second
    assert 2 <= len(first["organisms"]) <= 4
    assert len(first["relations"]) == len(first["organisms"]) - 1
    assert len(first["scene_id"]) == 24
    assert all(o["family"] in FAMILIES for o in first["organisms"])


def test_continuous_genomes_have_structural_distance():
    a = build_scene(1, "long", FAMILIES, "orb")
    b = build_scene(2, "long", FAMILIES, "orb")
    assert a["scene_id"] != b["scene_id"]
    assert 0 < scene_distance(a, b) <= 1
    assert scene_distance(a, a) == 0
    old_kind = a["relations"][0]["kind"]
    a["relations"][0]["kind"] = "fusion" if old_kind != "fusion" else "braid"
    assert identify_scene(a)["scene_id"] != a["scene_id"]


def test_scene_orchestration_creates_distinct_counterpoint():
    profile = {"scene": build_scene(9, "long", FAMILIES, "torus")}
    mapping = scene_music(profile)
    music = {"key_shift": 0, "beat_seconds": .8, "meter": 4, "density": .8}
    timeline = build_timeline(9, 12, music)
    base = build_composition(9, 12, music, timeline)
    result = orchestrate_scene(base, mapping, 12)
    assert len(result.notes) > len(base.notes)
    assert any("organism-" in note.voice for note in result.notes)
    assert mapping["voices"] == len(profile["scene"]["organisms"])
    assert mapping["version"] == 2
    agent_notes = [note for note in result.notes if "organism-" in note.voice]
    assert len({note.voice for note in agent_notes}) == mapping["voices"] - 1
    assert len({(note.note, note.start, note.duration) for note in agent_notes}) > 1
    assert orchestrate_scene(base, mapping, 12) == result
