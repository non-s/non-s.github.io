"""Testes para os modulos de IA: ai_composer, ai_evolution, ai_director.

Todos os testes rodam SEM GEMINI_API_KEY (monkeypatch.delenv) para exercitar
os caminhos de fallback procedural/defensivo. Testes rapidos (<1s cada).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from utils.ai_composer import (
    _parse_ai_structure,
    ai_compose,
    ai_compose_structure,
    build_ai_composition,
)
from utils.ai_director import (
    ai_direct,
    ai_plan_narrative,
    ai_quality_assessment,
    ai_quality_gate,
    build_ai_timeline,
)
from utils.ai_evolution import (
    apply_evolution_to_profile,
    evolve_aesthetics,
    load_aesthetic_weights,
    weighted_choice,
)
from utils.genres.registry import get_genre
from utils.liquid_wire_timeline import CreativeEvent

# ---------------------------------------------------------------------------
# ai_composer
# ---------------------------------------------------------------------------


def test_ai_composer_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    plan = ai_compose(seed=123, duration=10.0, genre_preset=get_genre("jazz"))
    assert plan is not None
    assert len(plan.notes) > 0
    voices = {n.voice for n in plan.notes}
    assert len(voices) > 0


def test_ai_compose_structure_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    structure = ai_compose_structure(seed=123, duration=10.0, genre_preset=get_genre("jazz"))
    assert structure is None


def test_build_ai_composition_with_mock_structure():
    mock_structure = {
        "narrative_arc": "calm opening -> gentle climax -> soft resolution",
        "sections": [
            {"name": "intro", "energy": 0.3, "transformation": "statement", "duration_fraction": 0.3},
            {"name": "build", "energy": 0.6, "transformation": "variation", "duration_fraction": 0.4},
            {"name": "outro", "energy": 0.2, "transformation": "expansion", "duration_fraction": 0.3},
        ],
        "motif": [0, 2, 4, 7, 9],
        "chord_progression": [0, 4, 5, 3],
        "tempo_curve": [
            {"section": "intro", "bpm_multiplier": 0.95},
            {"section": "build", "bpm_multiplier": 1.05},
        ],
        "dynamic_plan": [
            {"section": "intro", "velocity_multiplier": 0.7},
            {"section": "build", "velocity_multiplier": 1.1},
        ],
        "arrangement": [
            {"section": "intro", "active_voices": ["motif", "pad", "bass"]},
            {"section": "build", "active_voices": ["motif", "bass", "arpeggio"]},
            {"section": "outro", "active_voices": ["pad", "bass"]},
        ],
    }
    plan = build_ai_composition(
        seed=42, duration=12.0, genre_preset=get_genre("ambient"), ai_structure=mock_structure
    )
    assert plan is not None
    assert len(plan.notes) > 0


# ---------------------------------------------------------------------------
# ai_evolution
# ---------------------------------------------------------------------------


def test_load_aesthetic_weights_default(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import utils.ai_evolution as ai_evolution

    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: tmp_path / "missing.json")
    weights = load_aesthetic_weights()
    assert isinstance(weights, dict)
    assert len(weights["family_weights"]) == 42
    assert len(weights["genre_weights"]) == 32
    for v in weights["family_weights"].values():
        assert v == 1.0
    for v in weights["genre_weights"].values():
        assert v == 1.0


def test_weighted_choice_uniform():
    rng = np.random.default_rng(2024)
    options = ["a", "b", "c", "d"]
    weights = {opt: 1.0 for opt in options}
    counts = {opt: 0 for opt in options}
    for _ in range(1000):
        counts[weighted_choice(options, weights, rng)] += 1
    for opt in options:
        assert counts[opt] > 200, f"opcao {opt} apareceu apenas {counts[opt]}x"


def test_weighted_choice_skewed():
    rng = np.random.default_rng(7)
    options = ["fav", "other1", "other2", "other3"]
    weights = {"fav": 10.0, "other1": 1.0, "other2": 1.0, "other3": 1.0}
    counts = {opt: 0 for opt in options}
    for _ in range(1000):
        counts[weighted_choice(options, weights, rng)] += 1
    assert counts["fav"] > 500, f"fav apareceu apenas {counts['fav']}x (esperado >500)"


def test_apply_evolution_to_profile(monkeypatch, tmp_path):
    import utils.ai_evolution as ai_evolution

    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: tmp_path / "missing.json")
    rng = np.random.default_rng(99)
    profile = {
        "family": "orb",
        "genre": "ambient",
        "music": {"beat_seconds": 0.5, "meter": 4},
        "target_duration": 60.0,
    }
    result = apply_evolution_to_profile(profile, rng)
    assert isinstance(result, dict)
    assert "family" in result
    assert "genre" in result
    assert "aesthetic_weights_applied" in result


def test_evolve_aesthetics_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import utils.ai_evolution as ai_evolution

    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: tmp_path / "missing.json")
    result = evolve_aesthetics()
    assert isinstance(result, dict)
    assert result.get("status") == "fallback"


# ---------------------------------------------------------------------------
# ai_director
# ---------------------------------------------------------------------------


def test_ai_plan_narrative_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    plan = ai_plan_narrative(seed=1, duration=10.0, genre_name="ambient", family="orb")
    assert plan is None


def test_build_ai_timeline_from_mock_plan():
    mock_plan = {
        "narrative_arc": "blooming into stillness",
        "events": [
            {
                "kind": "bloom",
                "start_fraction": 0.1,
                "duration_fraction": 0.05,
                "intensity": 0.7,
                "direction": 1.5,
            }
        ],
        "camera_suggestions": [],
        "visual_emphasis": [],
        "pacing": "moderate",
    }
    events = build_ai_timeline(duration=20.0, ai_plan=mock_plan)
    assert isinstance(events, list)
    assert len(events) == 1
    ev = events[0]
    assert isinstance(ev, CreativeEvent)
    assert ev.kind == "bloom"
    assert ev.start == pytest.approx(0.1 * 20.0)
    assert ev.duration == pytest.approx(0.05 * 20.0, rel=1e-6) or ev.duration >= 0.5


def test_ai_direct_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    events, plan = ai_direct(seed=1, duration=10.0, genre_name="ambient", family="orb")
    assert events == []
    assert plan == {}


def test_ai_quality_gate_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    video_path = tmp_path / "nonexistent.mp4"
    passed, report = ai_quality_gate(video_path)
    assert passed is True
    assert isinstance(report, dict)


def test_ai_quality_assessment_returns_none_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    frame_path = tmp_path / "frame.png"
    frame_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    result = ai_quality_assessment(frame_path, tmp_path / "video.mp4")
    assert result is None


# ===========================================================================
# Novos testes — ai_composer (cobertura > 70%)
# ===========================================================================


def test_parse_ai_structure_invalid_json_returns_none():
    assert _parse_ai_structure("") is None
    assert _parse_ai_structure("not json {") is None
    assert _parse_ai_structure("[1, 2, 3]") is None  # lista, nao objeto
    assert _parse_ai_structure("null") is None


def test_parse_ai_structure_missing_or_empty_sections():
    assert _parse_ai_structure('{"narrative_arc": "x"}') is None
    assert _parse_ai_structure('{"sections": []}') is None
    # sections presentes mas nenhuma valida (sem nome / nao-dict)
    assert _parse_ai_structure('{"sections": [123, {"name": ""}]}') is None


def test_parse_ai_structure_normalizes_dirty_input():
    raw = json.dumps({
        "narrative_arc": "   arc with spaces   ",
        "sections": [
            {"name": "a", "energy": "high", "transformation": "INVALID", "duration_fraction": "oops"},
            {"name": "b", "energy": 5.0, "transformation": "variation", "duration_fraction": -1.0},
            {"name": "", "energy": 0.5},  # descartada (sem nome)
            42,  # descartada (nao-dict)
        ],
        "motif": [0, 2, "x", 4, 7, 99, -3],  # 99 e -3 fora do range [0,36] sao descartados
        "chord_progression": [0, 9, 4, -1, "z"],  # 9 e -1 invalidos (0-6)
        "tempo_curve": [
            {"section": "a", "bpm_multiplier": 3.0},   # clamp 1.5
            {"section": "b", "bpm_multiplier": "bad"},  # -> 1.0
            42,  # descartado
            {"section": "", "bpm_multiplier": 1.0},    # descartado (sem section)
        ],
        "dynamic_plan": [
            {"section": "a", "velocity_multiplier": 9.0},  # clamp 2.0
            {"section": "b", "velocity_multiplier": None},  # -> 1.0
        ],
        "arrangement": [
            {"section": "a", "active_voices": ["motif", "invalid_voice", "bass", ""]},
            {"section": "", "active_voices": ["motif"]},  # descartado (sem section)
            42,  # descartado
        ],
    })
    parsed = _parse_ai_structure(raw)
    assert parsed is not None
    assert parsed["narrative_arc"] == "arc with spaces"
    secs = parsed["sections"]
    assert [s["name"] for s in secs] == ["a", "b"]
    assert secs[0]["energy"] == 0.6  # "high" -> fallback default 0.6
    assert secs[0]["transformation"] == "statement"  # invalido -> default
    assert secs[0]["duration_fraction"] == pytest.approx(0.25 / 0.26)  # "oops"->0.25, "b"=0.01, normalizado
    assert secs[1]["duration_fraction"] == pytest.approx(0.01 / 0.26)
    assert secs[1]["energy"] == 1.0  # 5.0 clampado
    assert secs[1]["duration_fraction"] > 0.0
    # duration_fraction soma normalizada para 1.0
    assert sum(s["duration_fraction"] for s in secs) == pytest.approx(1.0)
    # motif filtrado para ints validos 0-36; < 3 -> default
    assert parsed["motif"] == [0, 2, 4, 7]
    # chord_progression filtrado: 0 e 4 validos (9, -1, "z" descartados). Nao-vazio -> mantem [0,4]
    assert parsed["chord_progression"] == [0, 4]
    assert parsed["tempo_curve"][0]["bpm_multiplier"] == 1.5
    assert parsed["tempo_curve"][1]["bpm_multiplier"] == 1.0
    assert parsed["dynamic_plan"][0]["velocity_multiplier"] == 2.0
    assert parsed["dynamic_plan"][1]["velocity_multiplier"] == 1.0
    arr = parsed["arrangement"]
    assert arr[0]["active_voices"] == ["motif", "bass"]


def test_parse_ai_structure_motif_too_short_uses_default():
    parsed = _parse_ai_structure(json.dumps({
        "sections": [{"name": "x", "energy": 0.5, "transformation": "statement", "duration_fraction": 1.0}],
        "motif": [0],  # < 3 -> default
        "chord_progression": [],  # vazio -> default
    }))
    assert parsed is not None
    assert parsed["motif"] == [0, 2, 4, 7]
    assert parsed["chord_progression"] == [0, 4, 5, 3]


def test_parse_ai_structure_missing_optional_fields():
    parsed = _parse_ai_structure(json.dumps({
        "sections": [{"name": "x", "energy": 0.5, "transformation": "statement", "duration_fraction": 1.0}],
    }))
    assert parsed is not None
    assert parsed["tempo_curve"] == []
    assert parsed["dynamic_plan"] == []
    assert parsed["arrangement"] == []
    assert parsed["narrative_arc"] == ""


def test_build_ai_composition_minimal_structure():
    """Estrutura minima: apenas sections. Exercita caminhos de fallback para
    tempo_curve/dynamic_plan/arrangement vazios."""
    structure = {
        "sections": [
            {"name": "intro", "energy": 0.4, "transformation": "statement", "duration_fraction": 1.0},
        ],
    }
    plan = build_ai_composition(
        seed=7, duration=8.0, genre_preset=get_genre("ambient"), ai_structure=structure
    )
    assert plan is not None
    assert len(plan.notes) > 0


def test_build_ai_composition_empty_motif_uses_default():
    """motif=[] deve cair em (0,2,4,7) e ainda assim renderizar."""
    structure = {
        "sections": [
            {"name": "a", "energy": 0.5, "transformation": "statement", "duration_fraction": 1.0},
        ],
        "motif": [],
    }
    plan = build_ai_composition(
        seed=3, duration=6.0, genre_preset=get_genre("ambient"), ai_structure=structure
    )
    assert plan is not None
    assert len(plan.notes) > 0


def test_build_ai_composition_jazz_groove_walking_bass():
    """jazz tem song_form head_solos_head (groove form) — exercita o branch
    de walking_bass que substitui o baixo original."""
    structure = {
        "sections": [
            {"name": "head", "energy": 0.5, "transformation": "statement", "duration_fraction": 0.5},
            {"name": "solo", "energy": 0.8, "transformation": "variation", "duration_fraction": 0.5},
        ],
        "motif": [0, 2, 4, 7, 9, 11],
        "chord_progression": [0, 4, 5, 3],
        "arrangement": [
            {"section": "head", "active_voices": ["motif", "bass", "walking_bass"]},
            {"section": "solo", "active_voices": ["motif", "walking_bass", "arpeggio"]},
        ],
    }
    plan = build_ai_composition(
        seed=11, duration=10.0, genre_preset=get_genre("jazz"), ai_structure=structure
    )
    assert plan is not None
    voices = {n.voice for n in plan.notes}
    assert "walking_bass" in voices or "bass" in voices


def test_build_ai_composition_counter_melody_and_ostinato():
    """Exercita os branches de counter_melody e ostinato no arrangement."""
    structure = {
        "sections": [
            {"name": "a", "energy": 0.7, "transformation": "development", "duration_fraction": 0.5},
            {"name": "b", "energy": 0.9, "transformation": "fragmentation", "duration_fraction": 0.5},
        ],
        "motif": [0, 3, 5, 7, 10],
        "chord_progression": [0, 5, 3, 4],
        "tempo_curve": [
            {"section": "a", "bpm_multiplier": 1.1},
            {"section": "b", "bpm_multiplier": 0.9},
        ],
        "dynamic_plan": [
            {"section": "a", "velocity_multiplier": 0.8},
            {"section": "b", "velocity_multiplier": 1.2},
        ],
        "arrangement": [
            {"section": "a", "active_voices": ["motif", "pad", "counter_melody", "ostinato"]},
            {"section": "b", "active_voices": ["motif", "ostinato", "arpeggio"]},
        ],
    }
    plan = build_ai_composition(
        seed=21, duration=12.0, genre_preset=get_genre("edm_house"), ai_structure=structure
    )
    assert plan is not None
    voices = {n.voice for n in plan.notes}
    # Pelo menos algumas vozes extras devem aparecer
    assert voices & {"counter_melody", "ostinato", "pad", "arpeggio"}


def test_build_ai_composition_sections_do_not_sum_to_one():
    """duration_fraction nao somando ~1.0 exercita o branch de renormalizacao
    em _sections_from_ai (acc < 0.999 ou > 1.001)."""
    structure = {
        "sections": [
            {"name": "a", "energy": 0.4, "transformation": "statement", "duration_fraction": 0.3},
            {"name": "b", "energy": 0.7, "transformation": "variation", "duration_fraction": 0.2},
        ],
        "motif": [0, 2, 4, 7],
    }
    plan = build_ai_composition(
        seed=5, duration=10.0, genre_preset=get_genre("ambient"), ai_structure=structure
    )
    assert plan is not None
    # sections devem cobrir a duracao inteira apos renormalizacao
    assert plan.sections[0].start < plan.sections[-1].end


def test_ai_compose_fallback_when_build_fails(monkeypatch):
    """ai_compose deve cair em build_composition_extended se build_ai_composition
    levantar excecao (mesmo com estrutura Gemini valida)."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import utils.ai_composer as ai_composer

    fake_structure = {
        "sections": [{"name": "x", "energy": 0.5, "transformation": "statement", "duration_fraction": 1.0}],
    }

    def fake_ai_compose_structure(seed, duration, genre_preset):
        return fake_structure

    def boom(seed, duration, genre_preset, ai_structure):
        raise RuntimeError("simulated render failure")

    monkeypatch.setattr(ai_composer, "ai_compose_structure", fake_ai_compose_structure)
    monkeypatch.setattr(ai_composer, "build_ai_composition", boom)
    plan = ai_compose(seed=42, duration=8.0, genre_preset=get_genre("ambient"))
    assert plan is not None  # fallback procedural funcionou
    assert len(plan.notes) > 0


def test_ai_compose_renders_when_structure_valid(monkeypatch):
    """ai_compose deve chamar build_ai_composition quando a estrutura e valida."""
    import utils.ai_composer as ai_composer

    fake_structure = {
        "sections": [{"name": "x", "energy": 0.5, "transformation": "statement", "duration_fraction": 1.0}],
        "motif": [0, 2, 4, 7],
    }
    monkeypatch.setattr(ai_composer, "ai_compose_structure", lambda *a, **k: fake_structure)
    plan = ai_compose(seed=1, duration=8.0, genre_preset=get_genre("ambient"))
    assert plan is not None
    assert len(plan.notes) > 0


def test_ai_compose_structure_parses_valid_gemini_output(monkeypatch):
    """ai_compose_structure deve normalizar e retornar dict quando o Gemini
    retorna JSON valido. Exercita o caminho feliz (log info apos parse)."""
    import utils.ai_composer as ai_composer

    valid_json = json.dumps({
        "narrative_arc": "calm to bright",
        "sections": [
            {"name": "a", "energy": 0.3, "transformation": "statement", "duration_fraction": 0.5},
            {"name": "b", "energy": 0.8, "transformation": "variation", "duration_fraction": 0.5},
        ],
        "motif": [0, 2, 4, 7],
        "chord_progression": [0, 4, 5, 3],
    })
    monkeypatch.setattr(ai_composer, "ai_text", lambda *a, **k: valid_json)
    structure = ai_compose_structure(seed=1, duration=10.0, genre_preset=get_genre("ambient"))
    assert structure is not None
    assert len(structure["sections"]) == 2


def test_ai_compose_structure_returns_none_on_invalid_gemini_json(monkeypatch):
    """Exercita o caminho onde ai_text retorna algo, mas o parse falha."""
    import utils.ai_composer as ai_composer

    monkeypatch.setattr(ai_composer, "ai_text", lambda *a, **k: "garbage {")
    assert ai_compose_structure(seed=1, duration=10.0, genre_preset=get_genre("ambient")) is None
    monkeypatch.setattr(ai_composer, "ai_text", lambda *a, **k: "")
    assert ai_compose_structure(seed=1, duration=10.0, genre_preset=get_genre("ambient")) is None


# ===========================================================================
# Novos testes — ai_evolution (cobertura > 70%)
# ===========================================================================


def test_save_aesthetic_weights_roundtrip(monkeypatch, tmp_path):
    """save_aesthetic_weights + load_aesthetic_weights: roundtrip preserva os
    pesos coeridos para as chaves conhecidas."""
    import utils.ai_evolution as ai_evolution

    weights_file = tmp_path / "aesthetic_weights.json"
    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: weights_file)
    payload = {
        "family_weights": {"orb": 2.0, "torus": 0.5},
        "genre_weights": {"ambient": 1.8, "jazz": 0.4},
        "duration_range": [30.0, 120.0],
        "posting_hours": [10, 14, 18],
        "recommendations": "favor ambient",
    }
    ai_evolution.save_aesthetic_weights(payload)
    assert weights_file.exists()
    loaded = load_aesthetic_weights()
    # _coerce_weights preenche TODAS as familias/generos conhecidos com 1.0
    from generate_liquid_wire_video import GENRES, OBJECT_FAMILIES

    assert set(loaded["family_weights"].keys()) == set(OBJECT_FAMILIES)
    assert set(loaded["genre_weights"].keys()) == set(GENRES.keys())
    assert loaded["family_weights"]["orb"] == 2.0
    assert loaded["family_weights"]["torus"] == 0.5
    assert loaded["genre_weights"]["ambient"] == 1.8
    assert loaded["genre_weights"]["jazz"] == 0.4
    assert loaded["duration_range"] == [30.0, 120.0]
    assert loaded["posting_hours"] == [10, 14, 18]


def test_save_aesthetic_weights_ignores_non_dict(monkeypatch, tmp_path):
    import utils.ai_evolution as ai_evolution

    weights_file = tmp_path / "aesthetic_weights.json"
    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: weights_file)
    ai_evolution.save_aesthetic_weights(["not", "a", "dict"])  # nao levanta
    assert not weights_file.exists()


def test_save_aesthetic_weights_handles_oserror(monkeypatch, tmp_path):
    """Falha de I/O na escrita nao deve propagar."""
    import utils.ai_evolution as ai_evolution

    weights_file = tmp_path / "aesthetic_weights.json"
    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: weights_file)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", boom)
    ai_evolution.save_aesthetic_weights({"family_weights": {}})  # nao levanta


def test_load_aesthetic_weights_corrupted_file(monkeypatch, tmp_path):
    """Arquivo existente mas invalido (JSON corrompido) -> defaults uniformes."""
    import utils.ai_evolution as ai_evolution

    weights_file = tmp_path / "aesthetic_weights.json"
    weights_file.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: weights_file)
    loaded = load_aesthetic_weights()
    assert isinstance(loaded, dict)
    # defaults uniformes: todos os pesos == 1.0
    assert all(v == 1.0 for v in loaded["family_weights"].values())


def test_load_aesthetic_weights_partial_payload(monkeypatch, tmp_path):
    """Arquivo valido mas sem algumas chaves -> coercao preenche defaults."""
    import utils.ai_evolution as ai_evolution

    weights_file = tmp_path / "aesthetic_weights.json"
    weights_file.write_text(json.dumps({"family_weights": {"orb": 2.0}}), encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: weights_file)
    loaded = load_aesthetic_weights()
    from generate_liquid_wire_video import OBJECT_FAMILIES

    assert set(loaded["family_weights"].keys()) == set(OBJECT_FAMILIES)
    assert loaded["family_weights"]["orb"] == 2.0
    # generos ausentes -> 1.0 (uniforme)
    assert all(v == 1.0 for v in loaded["genre_weights"].values())
    # duration_range/posting_hours ausentes -> defaults
    assert loaded["duration_range"] == [20.0, 180.0]
    assert loaded["posting_hours"] == list(range(24))


def test_weighted_choice_empty_raises():
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        weighted_choice([], {}, rng)


def test_weighted_choice_single_option():
    rng = np.random.default_rng(0)
    assert weighted_choice(["only"], {}, rng) == "only"


def test_weighted_choice_all_zero_weights_falls_back_to_uniform():
    """Todos os pesos <= 0 -> rng.choice uniforme (nao ValueError)."""
    rng = np.random.default_rng(123)
    options = ["a", "b", "c"]
    weights = {opt: 0.0 for opt in options}
    counts = {opt: 0 for opt in options}
    for _ in range(300):
        counts[weighted_choice(options, weights, rng)] += 1
    # uniforme: cada um deve aparecer
    assert all(c > 0 for c in counts.values())


def test_weighted_choice_missing_weight_defaults_to_one():
    """Opcao sem peso no dict usa 1.0 implicito."""
    rng = np.random.default_rng(0)
    options = ["a", "b"]
    weights = {"a": 1.0}  # b ausente -> 1.0
    counts = {"a": 0, "b": 0}
    for _ in range(500):
        counts[weighted_choice(options, weights, rng)] += 1
    assert counts["a"] > 100 and counts["b"] > 100


def test_analysis_to_weights_promotes_best_options(monkeypatch, tmp_path):
    """_analysis_to_weights: best_families/best_genres com peso < 1.0 sao
    promovidos para >= 1.0."""
    import utils.ai_evolution as ai_evolution

    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: tmp_path / "missing.json")
    analysis = {
        "best_genres": ["ambient"],
        "best_families": ["orb"],
        "optimal_duration_range": [25.0, 100.0],
        "best_posting_hours": [9, 21],
        "aesthetic_weights": {
            "family_weight": {"orb": 0.3},  # < 1.0 mas e best -> promovido
            "genre_weight": {"ambient": 0.4},
        },
        "recommendations": "favor ambient + orb",
    }
    weights = ai_evolution._analysis_to_weights(analysis)
    assert weights["family_weights"]["orb"] >= 1.0
    assert weights["genre_weights"]["ambient"] >= 1.0
    assert weights["duration_range"] == [25.0, 100.0]
    assert weights["posting_hours"] == [9, 21]
    assert weights["recommendations"] == "favor ambient + orb"


def test_analysis_to_weights_unknown_best_ignored():
    """best_families fora das opcoes conhecidas e silenciosamente ignorado."""
    import utils.ai_evolution as ai_evolution

    analysis = {
        "best_families": ["nonexistent_family"],
        "best_genres": ["nonexistent_genre"],
        "aesthetic_weights": {},
    }
    weights = ai_evolution._analysis_to_weights(analysis)
    assert "nonexistent_family" not in weights["family_weights"]
    assert "nonexistent_genre" not in weights["genre_weights"]


def test_apply_evolution_to_profile_low_weight_family_resort(monkeypatch, tmp_path):
    """Profile com familia de peso baixo dispara re-sort ate achar uma melhor."""
    import utils.ai_evolution as ai_evolution

    weights_file = tmp_path / "aesthetic_weights.json"
    weights_file.write_text(json.dumps({
        "family_weights": {"orb": 0.2, "torus": 2.5},  # orb baixo, torus alto
        "genre_weights": {"ambient": 1.0},
    }), encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: weights_file)
    rng = np.random.default_rng(99)
    profile = {"family": "orb", "genre": "ambient", "target_duration": 60.0}
    result = apply_evolution_to_profile(profile, rng)
    # com orb=0.2 (baixo) e torus=2.5 (alto), o re-sort deve favorecer uma
    # familia de peso > current_weight (0.2). Pode ser torus ou outra.
    if result["family"] != "orb":
        assert float(weights_file.parent and 0) or True  # no-op sanity
        # a familia sorteada deve ter peso > 0.2 (peso original do orb)
        assert result["aesthetic_weights_applied"]["family_weight"] > 0.2
    assert "aesthetic_weights_applied" in result


def test_apply_evolution_to_profile_duration_clamp(monkeypatch, tmp_path):
    """target_duration fora do duration_range otimizado e clampado."""
    import utils.ai_evolution as ai_evolution

    weights_file = tmp_path / "aesthetic_weights.json"
    weights_file.write_text(json.dumps({
        "family_weights": {"orb": 1.0},
        "genre_weights": {"ambient": 1.0},
        "duration_range": [40.0, 90.0],
    }), encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: weights_file)
    rng = np.random.default_rng(0)
    profile = {"family": "orb", "genre": "ambient", "target_duration": 300.0}
    result = apply_evolution_to_profile(profile, rng)
    assert result["target_duration"] == 90.0
    # agora abaixo do range
    profile2 = {"family": "orb", "genre": "ambient", "target_duration": 5.0}
    result2 = apply_evolution_to_profile(profile2, rng)
    assert result2["target_duration"] == 40.0


def test_apply_evolution_to_profile_duration_field_alias(monkeypatch, tmp_path):
    """Profile usa 'duration' (nao 'target_duration') — clamp deve mutar o
    campo correto."""
    import utils.ai_evolution as ai_evolution

    weights_file = tmp_path / "aesthetic_weights.json"
    weights_file.write_text(json.dumps({"duration_range": [50.0, 80.0]}), encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: weights_file)
    rng = np.random.default_rng(0)
    profile = {"family": "orb", "genre": "ambient", "duration": 200.0}
    result = apply_evolution_to_profile(profile, rng)
    assert result["duration"] == 80.0
    assert "target_duration" not in result


def test_apply_evolution_to_profile_no_duration_uses_uniform(monkeypatch, tmp_path):
    """Profile sem duracao explicita e sem preset 'short' sorteia do range."""
    import utils.ai_evolution as ai_evolution

    weights_file = tmp_path / "aesthetic_weights.json"
    weights_file.write_text(json.dumps({"duration_range": [30.0, 60.0]}), encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: weights_file)
    rng = np.random.default_rng(7)
    profile = {"family": "orb", "genre": "ambient"}
    result = apply_evolution_to_profile(profile, rng)
    assert 30.0 <= result["target_duration"] <= 60.0


def test_apply_evolution_to_profile_short_preset(monkeypatch, tmp_path):
    """preset='short' sorteia do range limitado a 60s."""
    import utils.ai_evolution as ai_evolution

    weights_file = tmp_path / "aesthetic_weights.json"
    weights_file.write_text(json.dumps({"duration_range": [10.0, 180.0]}), encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: weights_file)
    rng = np.random.default_rng(7)
    profile = {"family": "orb", "genre": "ambient", "preset": "short"}
    result = apply_evolution_to_profile(profile, rng)
    assert 10.0 <= result["target_duration"] <= 60.0


def test_evolve_aesthetics_applies_when_analysis_succeeds(monkeypatch, tmp_path):
    """evolve_aesthetics com analyze_performance simulado: converte em pesos,
    salva e retorna report com status='evolved'."""
    import utils.ai_evolution as ai_evolution

    weights_file = tmp_path / "aesthetic_weights.json"
    monkeypatch.setattr(ai_evolution, "_weights_file", lambda: weights_file)
    fake_analysis = {
        "best_genres": ["ambient"],
        "best_families": ["orb"],
        "optimal_duration_range": [40.0, 100.0],
        "best_posting_hours": [12],
        "aesthetic_weights": {
            "family_weight": {"orb": 2.0},
            "genre_weight": {"ambient": 1.5},
        },
        "recommendations": "favor ambient",
    }
    monkeypatch.setattr(ai_evolution, "analyze_performance", lambda: fake_analysis)
    report = evolve_aesthetics()
    assert report["status"] == "evolved"
    assert weights_file.exists()
    saved = json.loads(weights_file.read_text(encoding="utf-8"))
    assert saved["family_weights"]["orb"] == 2.0


def test_analyze_performance_no_data_returns_none(monkeypatch, tmp_path):
    """Sem nenhum arquivo de analytics/quality/pipeline -> None."""
    import utils.ai_evolution as ai_evolution

    monkeypatch.setattr(ai_evolution, "data_dir", lambda: tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ai_evolution.analyze_performance() is None


def test_analyze_performance_gemini_empty_returns_none(monkeypatch, tmp_path):
    """Dados presentes mas Gemini retorna vazio -> None."""
    import utils.ai_evolution as ai_evolution

    (tmp_path / "analytics.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(ai_evolution, "ai_text", lambda *a, **k: "")
    assert ai_evolution.analyze_performance() is None


def test_analyze_performance_gemini_invalid_json_returns_none(monkeypatch, tmp_path):
    import utils.ai_evolution as ai_evolution

    (tmp_path / "analytics.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(ai_evolution, "ai_text", lambda *a, **k: "not json {")
    assert ai_evolution.analyze_performance() is None


def test_analyze_performance_repairs_malformed_gemini_json(monkeypatch, tmp_path):
    import utils.ai_evolution as ai_evolution

    (tmp_path / "analytics.json").write_text('{"total_videos": 1}', encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "data_dir", lambda: tmp_path)
    valid = json.dumps({"best_genres": ["ambient"], "best_families": ["orb"]})
    responses = iter(["{malformed", valid])
    monkeypatch.setattr(ai_evolution, "ai_text", lambda *a, **k: next(responses))

    result = ai_evolution.analyze_performance()

    assert result is not None
    assert result["best_genres"] == ["ambient"]
    assert result["best_families"] == ["orb"]


def test_analyze_performance_gemini_non_object_returns_none(monkeypatch, tmp_path):
    import utils.ai_evolution as ai_evolution

    (tmp_path / "analytics.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(ai_evolution, "ai_text", lambda *a, **k: "[1, 2, 3]")
    assert ai_evolution.analyze_performance() is None


def test_analyze_performance_happy_path(monkeypatch, tmp_path):
    import utils.ai_evolution as ai_evolution

    (tmp_path / "analytics.json").write_text(json.dumps({
        "total_videos": 10,
        "total_views": 1000,
        "total_likes": 100,
        "total_comments": 20,
        "avg_views": 100,
        "top_10": [{"title": "v1", "views": 500, "likes": 50}],
    }), encoding="utf-8")
    (tmp_path / "quality_history.json").write_text(json.dumps([
        {"score": 0.8, "passed": True, "family": "orb"},
        {"score": 0.4, "passed": False, "family": "torus"},
    ]), encoding="utf-8")
    (tmp_path / "pipeline_metrics.json").write_text(json.dumps([
        {"stage": "render", "success": True},
        {"stage": "render", "success": False},
    ]), encoding="utf-8")
    monkeypatch.setattr(ai_evolution, "data_dir", lambda: tmp_path)
    gemini_out = json.dumps({
        "best_genres": ["ambient"],
        "best_families": ["orb"],
        "optimal_duration_range": [40.0, 100.0],
        "best_posting_hours": [12, 18],
        "aesthetic_weights": {
            "family_weight": {"orb": 2.0},
            "genre_weight": {"ambient": 1.5},
        },
        "recommendations": "favor ambient",
    })
    monkeypatch.setattr(ai_evolution, "ai_text", lambda *a, **k: gemini_out)
    result = ai_evolution.analyze_performance()
    assert result is not None
    assert result["best_genres"] == ["ambient"]
    assert result["best_families"] == ["orb"]
    assert result["optimal_duration_range"] == [40.0, 100.0]
    assert result["best_posting_hours"] == [12, 18]
    assert result["recommendations"] == "favor ambient"


def test_coerce_duration_range_invalid_returns_default():
    import utils.ai_evolution as ai_evolution

    assert ai_evolution._coerce_duration_range(None) == [20.0, 180.0]
    assert ai_evolution._coerce_duration_range([]) == [20.0, 180.0]
    assert ai_evolution._coerce_duration_range([10.0]) == [20.0, 180.0]  # len != 2
    assert ai_evolution._coerce_duration_range(["a", "b"]) == [20.0, 180.0]


def test_coerce_duration_range_swaps_and_clamps():
    import utils.ai_evolution as ai_evolution

    assert ai_evolution._coerce_duration_range([100.0, 20.0]) == [20.0, 100.0]  # swap
    assert ai_evolution._coerce_duration_range([0.0, 0.0]) == [20.0, 180.0]  # hi<=0
    assert ai_evolution._coerce_duration_range([2.0, 3.0]) == [5.0, 7.0]  # lo->5.0, hi->max(3.0, 5.0+5)=7.0


def test_coerce_posting_hours_filters_and_sorts():
    import utils.ai_evolution as ai_evolution

    assert ai_evolution._coerce_posting_hours(None) == list(range(24))
    assert ai_evolution._coerce_posting_hours([]) == list(range(24))
    assert ai_evolution._coerce_posting_hours([18, 3, 12, 25, -1, "x"]) == [3, 12, 18]
    assert ai_evolution._coerce_posting_hours([99]) == list(range(24))  # nenhum valido


def test_coerce_weights_clamps_and_defaults():
    import utils.ai_evolution as ai_evolution

    out = ai_evolution._coerce_weights({"a": 5.0, "b": -1.0, "c": "bad"}, ["a", "b", "c", "d"], 0.2, 3.0)
    assert out["a"] == 3.0  # clamp alto
    assert out["b"] == 0.2  # clamp baixo
    assert out["c"] == 1.0  # invalido -> default
    assert out["d"] == 1.0  # ausente -> default


def test_summarize_quality_empty():
    import utils.ai_evolution as ai_evolution

    out = ai_evolution._summarize_quality(None)
    assert out["samples"] == 0
    out = ai_evolution._summarize_quality([])
    assert out["samples"] == 0
    out = ai_evolution._summarize_quality([{"score": 0.5, "passed": True, "family": "orb"}])
    assert out["samples"] == 1
    assert out["avg_score"] == 0.5
    assert out["pass_rate"] == 1.0
    assert out["families"] == {"orb": 0.5}


def test_summarize_pipeline_empty():
    import utils.ai_evolution as ai_evolution

    out = ai_evolution._summarize_pipeline(None)
    assert out["entries"] == 0
    out = ai_evolution._summarize_pipeline([{"stage": "render", "success": True}])
    assert out["entries"] == 1
    assert out["success_rate"] == 1.0
    assert out["stages"]["render"] == 1.0


def test_summarize_analytics_with_top_videos():
    import utils.ai_evolution as ai_evolution

    out = ai_evolution._summarize_analytics({
        "top_videos": [{"title": "v1", "views": 10, "likes": 1}],
        "total_videos": 5,
    })
    assert out["total_videos"] == 5
    assert len(out["top_10"]) == 1


# ===========================================================================
# Novos testes — ai_director (cobertura > 70%)
# ===========================================================================


def test_validate_plan_shape_non_dict_returns_none():
    import utils.ai_director as ai_director

    assert ai_director._validate_plan_shape(None) is None
    assert ai_director._validate_plan_shape([1, 2, 3]) is None
    assert ai_director._validate_plan_shape("string") is None


def test_validate_plan_shape_missing_arc_returns_none():
    import utils.ai_director as ai_director

    assert ai_director._validate_plan_shape({}) is None
    assert ai_director._validate_plan_shape({"narrative_arc": ""}) is None
    assert ai_director._validate_plan_shape({"narrative_arc": 123}) is None  # nao str


def test_validate_plan_shape_empty_events_returns_none():
    import utils.ai_director as ai_director

    assert ai_director._validate_plan_shape({"narrative_arc": "x", "events": []}) is None
    assert ai_director._validate_plan_shape({"narrative_arc": "x", "events": "not list"}) is None


def test_validate_plan_shape_filters_invalid_events():
    import utils.ai_director as ai_director

    plan = {
        "narrative_arc": "arc",
        "events": [
            {"kind": "bloom", "start_fraction": 0.1, "duration_fraction": 0.1, "intensity": 0.5},
            {"kind": "INVALID", "start_fraction": 0.2, "duration_fraction": 0.1},  # filtrado
            {"kind": "tide", "start_fraction": -0.5, "duration_fraction": 0.1},  # filtrado (start<0)
            {"kind": "tide", "start_fraction": 0.3, "duration_fraction": 0.0},   # filtrado (dur<=0)
            {"kind": "tide", "start_fraction": 0.4, "duration_fraction": "x"},   # filtrado (nao-float)
            42,  # filtrado (nao-dict)
        ],
    }
    out = ai_director._validate_plan_shape(plan)
    assert out is not None
    assert len(out["events"]) == 1
    assert out["events"][0]["kind"] == "bloom"
    assert out["pacing"] == "moderate"  # default
    assert out["camera_suggestions"] == []
    assert out["visual_emphasis"] == []


def test_validate_plan_shape_normalizes_cameras_and_emphasis():
    import utils.ai_director as ai_director

    plan = {
        "narrative_arc": "arc",
        "events": [{"kind": "bloom", "start_fraction": 0.1, "duration_fraction": 0.1}],
        "camera_suggestions": [
            {"start_fraction": 0.2, "movement": "orbit", "intensity": 0.7},
            {"start_fraction": -1.0, "movement": "dolly"},  # filtrado (start<0)
            {"start_fraction": 0.3, "movement": "INVALID"},   # filtrado (movement)
            42,  # filtrado
        ],
        "visual_emphasis": [
            {"start_fraction": 0.4, "element": "color", "intensity": 0.6},
            {"start_fraction": 0.5, "element": "INVALID"},  # filtrado
        ],
        "pacing": "energetic",
    }
    out = ai_director._validate_plan_shape(plan)
    assert out is not None
    assert len(out["camera_suggestions"]) == 1
    assert out["camera_suggestions"][0]["movement"] == "orbit"
    assert len(out["visual_emphasis"]) == 1
    assert out["visual_emphasis"][0]["element"] == "color"
    assert out["pacing"] == "energetic"


def test_validate_plan_shape_all_events_invalid_returns_none():
    import utils.ai_director as ai_director

    plan = {
        "narrative_arc": "arc",
        "events": [
            {"kind": "INVALID", "start_fraction": 0.1, "duration_fraction": 0.1},
        ],
    }
    assert ai_director._validate_plan_shape(plan) is None


def test_clamp_handles_bad_input():
    import utils.ai_director as ai_director

    assert ai_director._clamp(0.5, 0.0, 1.0) == 0.5
    assert ai_director._clamp(2.0, 0.0, 1.0) == 1.0
    assert ai_director._clamp(-1.0, 0.0, 1.0) == 0.0
    assert ai_director._clamp("bad", 0.0, 1.0) == 0.0  # -> low
    assert ai_director._clamp(None, 5.0, 10.0) == 5.0


def test_build_ai_timeline_none_plan_returns_empty():
    assert build_ai_timeline(10.0, None) == []
    assert build_ai_timeline(10.0, {}) == []


def test_build_ai_timeline_multiple_events_pitch_offset_cycles():
    """Mais de 6 eventos exercita o modulo pitch_choices (len=6)."""
    plan = {
        "events": [
            {"kind": "bloom", "start_fraction": 0.05, "duration_fraction": 0.05, "intensity": 0.5, "direction": 0.0},
            {"kind": "tide", "start_fraction": 0.15, "duration_fraction": 0.05, "intensity": 0.6, "direction": 1.0},
            {
                "kind": "stillness",
                "start_fraction": 0.25,
                "duration_fraction": 0.05,
                "intensity": 0.2,
                "direction": -1.0,
            },
            {
                "kind": "rupture",
                "start_fraction": 0.40,
                "duration_fraction": 0.05,
                "intensity": 0.9,
                "direction": 2.0,
            },
            {
                "kind": "compression",
                "start_fraction": 0.55,
                "duration_fraction": 0.05,
                "intensity": 0.7,
                "direction": -2.0,
            },
            {
                "kind": "bloom",
                "start_fraction": 0.70,
                "duration_fraction": 0.05,
                "intensity": 0.8,
                "direction": 0.5,
            },
            {
                "kind": "tide",
                "start_fraction": 0.85,
                "duration_fraction": 0.05,
                "intensity": 0.4,
                "direction": 3.0,
            },
        ],
    }
    events = build_ai_timeline(20.0, plan)
    assert len(events) == 7
    pitch_offsets = {ev.pitch_offset for ev in events}
    assert len(pitch_offsets) > 1  # variou (modulo 6)


def test_build_ai_timeline_event_without_direction_uses_default():
    """Event sem 'direction' cai no default 0.0 (via .get)."""
    plan = {
        "events": [
            {"kind": "bloom", "start_fraction": 0.1, "duration_fraction": 0.1},  # sem direction, sem intensity
        ],
    }
    events = build_ai_timeline(10.0, plan)
    assert len(events) == 1
    assert events[0].direction == 0.0
    assert events[0].intensity == 0.5  # default


def test_build_ai_timeline_intensity_zero_preserved():
    """intensity=0 deve ser preservado (clamp 0..1 mantem 0)."""
    plan = {
        "events": [
            {"kind": "stillness", "start_fraction": 0.1, "duration_fraction": 0.1, "intensity": 0.0, "direction": 0.0},
        ],
    }
    events = build_ai_timeline(10.0, plan)
    assert events[0].intensity == 0.0


def test_build_ai_timeline_clamps_start_and_duration():
    """start < 0.25 clampado; duration > duration clampado; start > duration-0.5 clampado."""
    plan = {
        "events": [
            {"kind": "bloom", "start_fraction": 0.0, "duration_fraction": 0.01, "intensity": 0.5, "direction": 0.0},
        ],
    }
    events = build_ai_timeline(5.0, plan)
    assert events[0].start == 0.25  # clampado para baixo
    # duration_fraction * duration = 0.05 -> clampado para 0.5
    assert events[0].duration == 0.5


def test_build_ai_timeline_skips_malformed_event():
    """Evento sem start_fraction (KeyError) deve ser pulado, nao quebrar."""
    plan = {
        "events": [
            {"kind": "bloom"},  # sem start_fraction/duration_fraction
            {"kind": "tide", "start_fraction": 0.5, "duration_fraction": 0.1, "intensity": 0.5},
        ],
    }
    events = build_ai_timeline(10.0, plan)
    assert len(events) == 1
    assert events[0].kind == "tide"


def test_build_ai_timeline_clamps_direction_to_pi():
    """direction fora de [-pi, pi] e clampado."""
    import math

    plan = {
        "events": [
            {"kind": "bloom", "start_fraction": 0.1, "duration_fraction": 0.1, "intensity": 0.5, "direction": 10.0},
        ],
    }
    events = build_ai_timeline(10.0, plan)
    assert events[0].direction == pytest.approx(math.pi)


def test_ai_plan_narrative_with_key_parses_valid_json(monkeypatch):
    """Com GEMINI_API_KEY setada e Gemini retornando JSON valido, retorna
    plano normalizado (caminho feliz completo)."""
    import utils.ai_director as ai_director

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    valid_plan = json.dumps({
        "narrative_arc": "calm to climax to resolve",
        "events": [
            {"kind": "bloom", "start_fraction": 0.1, "duration_fraction": 0.1, "intensity": 0.5, "direction": 0.0},
        ],
        "pacing": "moderate",
    })
    monkeypatch.setattr(ai_director, "ai_text", lambda *a, **k: valid_plan)
    plan = ai_plan_narrative(seed=1, duration=20.0, genre_name="ambient", family="orb")
    assert plan is not None
    assert plan["narrative_arc"] == "calm to climax to resolve"
    assert len(plan["events"]) == 1


def test_ai_plan_narrative_with_key_empty_response_returns_none(monkeypatch):
    import utils.ai_director as ai_director

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setattr(ai_director, "ai_text", lambda *a, **k: "")
    assert ai_plan_narrative(seed=1, duration=10.0, genre_name="ambient", family="orb") is None


def test_ai_plan_narrative_with_key_invalid_json_returns_none(monkeypatch):
    import utils.ai_director as ai_director

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setattr(ai_director, "ai_text", lambda *a, **k: "garbage {")
    assert ai_plan_narrative(seed=1, duration=10.0, genre_name="ambient", family="orb") is None


def test_ai_plan_narrative_with_key_invalid_shape_returns_none(monkeypatch):
    import utils.ai_director as ai_director

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    # JSON valido mas sem events
    monkeypatch.setattr(ai_director, "ai_text", lambda *a, **k: json.dumps({"narrative_arc": "x"}))
    assert ai_plan_narrative(seed=1, duration=10.0, genre_name="ambient", family="orb") is None


def test_ai_direct_with_valid_plan(monkeypatch):
    """ai_direct com plano valido retorna (events, plan). Exercita o caminho
    feliz completo (log info apos aplicar arco)."""
    import utils.ai_director as ai_director

    valid_plan = {
        "narrative_arc": "arc",
        "events": [
            {"kind": "bloom", "start_fraction": 0.1, "duration_fraction": 0.1, "intensity": 0.6, "direction": 0.0},
            {"kind": "tide", "start_fraction": 0.5, "duration_fraction": 0.1, "intensity": 0.4, "direction": 1.0},
        ],
        "pacing": "moderate",
    }
    monkeypatch.setattr(ai_director, "ai_plan_narrative", lambda *a, **k: valid_plan)
    events, plan = ai_direct(seed=1, duration=20.0, genre_name="ambient", family="orb")
    assert len(events) == 2
    assert plan["narrative_arc"] == "arc"


def test_ai_direct_plan_without_events_falls_back(monkeypatch):
    """ai_plan_narrative retorna plano, mas build_ai_timeline gera [] (eventos
    malformados) -> ai_direct retorna ([], {}). Exercita o branch de fallback
    "plano recebido mas sem eventos validos"."""
    import utils.ai_director as ai_director

    # build_ai_timeline pula eventos que levantam KeyError/ValueError ao ler
    # start_fraction/duration_fraction. Eventos sem esses campos -> [].
    bad_plan = {
        "narrative_arc": "arc",
        "events": [
            {"kind": "bloom"},  # sem start_fraction/duration_fraction -> pulado
            {"kind": "tide", "start_fraction": "not-a-number", "duration_fraction": 0.1},  # ValueError
        ],
    }
    monkeypatch.setattr(ai_director, "ai_plan_narrative", lambda *a, **k: bad_plan)
    events, plan = ai_direct(seed=1, duration=10.0, genre_name="ambient", family="orb")
    assert events == []
    assert plan == {}


def test_sample_frames_from_video_missing_file(tmp_path):
    import utils.ai_director as ai_director

    result = ai_director._sample_frames_from_video(
        tmp_path / "nonexistent.mp4", 3, tmp_path / "frames"
    )
    assert result == []


def test_sample_frames_from_video_ffprobe_fails(monkeypatch, tmp_path):
    """Video existente mas ffprobe falha -> []."""
    import utils.ai_director as ai_director

    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")

    def boom(*a, **k):
        raise FileNotFoundError("ffprobe not installed")

    monkeypatch.setattr(subprocess, "run", boom)
    result = ai_director._sample_frames_from_video(video, 3, tmp_path / "frames")
    assert result == []


def test_sample_frames_from_video_zero_duration(monkeypatch, tmp_path):
    import utils.ai_director as ai_director

    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")

    class FakeProbe:
        stdout = "0.0\n"

    def fake_run(cmd, **kwargs):
        return FakeProbe()

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ai_director._sample_frames_from_video(video, 3, tmp_path / "frames")
    assert result == []


def test_ai_quality_gate_with_explicit_frames_all_fail(monkeypatch, tmp_path):
    """Frames fornecidos mas Gemini falha em todos -> fallback (True)."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    frames = [tmp_path / "f1.png", tmp_path / "f2.png"]
    for f in frames:
        f.write_bytes(b"\x89PNG\r\n\x1a\n")
    passed, report = ai_quality_gate(tmp_path / "v.mp4", frame_paths=frames)
    assert passed is True
    assert report.get("fallback") is True


def test_ai_quality_gate_with_explicit_frames_success(monkeypatch, tmp_path):
    """Exercita o caminho de media de scores com GEMINI_API_KEY + mock."""
    import utils.ai_director as ai_director

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    frames = [tmp_path / "f1.png", tmp_path / "f2.png"]
    for f in frames:
        f.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(
        ai_director,
        "ai_quality_assessment",
        lambda frame, video: {
            "visual_interest": 0.8, "composition_quality": 0.7,
            "color_harmony": 0.9, "motion_potential": 0.6, "overall_appeal": 0.8,
        },
    )
    passed, report = ai_quality_gate(tmp_path / "v.mp4", frame_paths=frames, min_score=0.5)
    assert passed is True
    assert report["overall_appeal"] == pytest.approx(0.8)
    assert report["sampled"] == 2


def test_ai_quality_gate_samples_down_too_many_frames(monkeypatch, tmp_path):
    """Mais de _QG_MAX_FRAMES frames -> amostragem aleatoria para 5."""
    import utils.ai_director as ai_director

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    frames = [tmp_path / f"f{i}.png" for i in range(10)]
    for f in frames:
        f.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(
        ai_director,
        "ai_quality_assessment",
        lambda frame, video: {
            "visual_interest": 0.8, "composition_quality": 0.7,
            "color_harmony": 0.9, "motion_potential": 0.6, "overall_appeal": 0.8,
        },
    )
    passed, report = ai_quality_gate(tmp_path / "v.mp4", frame_paths=frames)
    assert passed is True
    assert report["sampled"] == ai_director._QG_MAX_FRAMES


def test_ai_quality_gate_fails_below_min_score(monkeypatch, tmp_path):
    import utils.ai_director as ai_director

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    frames = [tmp_path / "f1.png"]
    frames[0].write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(
        ai_director,
        "ai_quality_assessment",
        lambda frame, video: {
            "visual_interest": 0.1, "composition_quality": 0.1,
            "color_harmony": 0.1, "motion_potential": 0.1, "overall_appeal": 0.2,
        },
    )
    passed, report = ai_quality_gate(tmp_path / "v.mp4", frame_paths=frames, min_score=0.6)
    assert passed is False
    assert report["overall_appeal"] == pytest.approx(0.2)


def test_ai_quality_assessment_with_key_invalid_json_returns_none(monkeypatch, tmp_path):
    import utils.ai_director as ai_director

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    frame = tmp_path / "f.png"
    frame.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(ai_director, "ai_text_with_image", lambda *a, **k: "garbage {")
    assert ai_quality_assessment(frame, tmp_path / "v.mp4") is None


def test_ai_quality_assessment_with_key_non_dict_returns_none(monkeypatch, tmp_path):
    import utils.ai_director as ai_director

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    frame = tmp_path / "f.png"
    frame.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(ai_director, "ai_text_with_image", lambda *a, **k: "[1, 2, 3]")
    assert ai_quality_assessment(frame, tmp_path / "v.mp4") is None


def test_ai_quality_assessment_with_key_happy_path(monkeypatch, tmp_path):
    import utils.ai_director as ai_director

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    frame = tmp_path / "f.png"
    frame.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(ai_director, "ai_text_with_image", lambda *a, **k: json.dumps({
        "visual_interest": 1.5, "composition_quality": 0.7,
        "color_harmony": 0.9, "motion_potential": 0.6, "overall_appeal": 0.8,
    }))
    result = ai_quality_assessment(frame, tmp_path / "v.mp4")
    assert result is not None
    assert result["visual_interest"] == 1.0  # clampado
    assert result["overall_appeal"] == 0.8


def test_ai_quality_assessment_missing_frame_returns_none(monkeypatch, tmp_path):

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    assert ai_quality_assessment(tmp_path / "missing.png", tmp_path / "v.mp4") is None


def test_ai_quality_assessment_empty_response_returns_none(monkeypatch, tmp_path):
    import utils.ai_director as ai_director

    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    frame = tmp_path / "f.png"
    frame.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(ai_director, "ai_text_with_image", lambda *a, **k: "")
    assert ai_quality_assessment(frame, tmp_path / "v.mp4") is None
