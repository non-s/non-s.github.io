from utils.audio_novelty import audio_plan_distance, audio_plan_vector, nearest_audio_plan
from utils.liquid_wire_composer import build_composition
from utils.liquid_wire_timeline import build_timeline


def _composition(seed: int):
    music = {"key_shift": seed % 5, "beat_seconds": .65 + seed / 100, "meter": 4, "density": .8}
    return build_composition(seed, 12, music, build_timeline(seed, 12, music))


def test_audio_plan_vector_is_fixed_deterministic_and_discriminative():
    first = audio_plan_vector(_composition(3))
    assert first == audio_plan_vector(_composition(3))
    assert len(first) == 44
    assert audio_plan_distance(first, first) == 0
    assert audio_plan_distance(first, audio_plan_vector(_composition(19))) > 0


def test_nearest_audio_plan_ignores_legacy_records():
    vector = audio_plan_vector(_composition(3))
    distance, content_id = nearest_audio_plan(vector, [
        {"content_id": "legacy"},
        {"content_id": "same", "audio_intent_vector": vector},
    ])
    assert distance == 0
    assert content_id == "same"
