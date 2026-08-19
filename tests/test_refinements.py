"""Testes para os 5 modulos de refinamento.

Todos os testes funcionam SEM GEMINI_API_KEY (fallbacks). Usa tmp_path
para cache/arquivos e monkeypatch para mockar data_dir e funcoes de IA.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from utils.comment_ai_responder import (
    ai_reply_with_context,
    classify_comment,
    contextual_reply_strategy,
    enhanced_reply_to_comment,
)
from utils.liquid_wire_timeline import build_timeline
from utils.lufs_mastering import (
    apply_dither,
    loudness_normalize,
    master_audio,
    measure_lufs,
)
from utils.multi_camera import (
    CameraShot,
    camera_state_at,
    plan_camera_shots,
)
from utils.thumbnail_ab_test import (
    check_thumbnail_swap_needed,
    record_thumbnail_ctr,
    run_thumbnail_optimization,
)
from utils.trending_topics import (
    enrich_metadata,
    fetch_trending_topics,
    load_trending_cache,
    save_trending_cache,
    trending_inspired_title,
)

# ---------------------------------------------------------------------------
# Fixtures auxiliares
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def _patch_data_dir(monkeypatch, tmp_path):
    import utils.paths as paths

    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    # trending_topics, thumbnail_ab_test importam data_dir no topo
    import utils.thumbnail_ab_test as tab
    import utils.trending_topics as tt

    monkeypatch.setattr(tt, "data_dir", lambda: tmp_path, raising=False)
    monkeypatch.setattr(tab, "data_dir", lambda: tmp_path, raising=False)
    # thumbnail_ab_test captura _EXPERIMENTS_FILE/_ANALYTICS_FILE no import;
    # patch as funcoes helper para apontar para tmp_path.
    monkeypatch.setattr(tab, "_EXPERIMENTS_FILE", tmp_path / "thumbnail_experiments.json", raising=False)
    monkeypatch.setattr(tab, "_ANALYTICS_FILE", tmp_path / "analytics.json", raising=False)


# ===========================================================================
# Trending topics
# ===========================================================================


def test_fetch_trending_topics_fallback():
    assert fetch_trending_topics() == []


def test_trending_inspired_title_fallback():
    assert trending_inspired_title("desc", "flow_field", "ambient") == ""


def test_enrich_metadata_fallback():
    meta = {"title": "Original Title", "description": "Original desc"}
    out = enrich_metadata(meta, "flow_field", "ambient", "long")
    assert out is meta
    assert out.get("trending_inspired") is not True
    assert out["title"] == "Original Title"
    assert out["description"] == "Original desc"


def test_trending_cache_roundtrip(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    topics = [{"topic": "x", "relevance": 0.5, "source": "test"}]
    save_trending_cache({"topics": topics})
    loaded = load_trending_cache()
    assert loaded is not None
    assert loaded["topics"] == topics
    assert isinstance(loaded["saved_at"], float)


def test_trending_cache_expired(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    # Escreve um cache com saved_at > 6h atras.
    cache_file = tmp_path / "trending_cache.json"
    payload = {
        "saved_at": time.time() - 7 * 3600,
        "saved_at_iso": "2020-01-01T00:00:00+00:00",
        "topics": [{"topic": "old", "relevance": 0.1, "source": "x"}],
    }
    cache_file.write_text(json.dumps(payload), encoding="utf-8")
    assert load_trending_cache() is None


# ===========================================================================
# Thumbnail A/B test
# ===========================================================================


def test_check_thumbnail_swap_needed_no_experiment(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    assert check_thumbnail_swap_needed("nonexistent_id") is None


def test_run_thumbnail_optimization_empty(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    assert run_thumbnail_optimization() == []


def test_record_thumbnail_ctr(monkeypatch, tmp_path):
    _patch_data_dir(monkeypatch, tmp_path)
    record_thumbnail_ctr("vid_1", "a", 0.045)
    record_thumbnail_ctr("vid_1", "a", 0.055)
    exp_file = tmp_path / "thumbnail_experiments.json"
    data = json.loads(exp_file.read_text(encoding="utf-8"))
    obs = data["vid_1"]["ctr"]["a"]
    assert obs == [0.045, 0.055]


# ===========================================================================
# Multi-camera
# ===========================================================================


def _make_events(duration=30.0):
    music = {"beat_seconds": 0.5, "meter": 4}
    return build_timeline(seed=42, duration=duration, music=music)


def test_plan_camera_shots_count():
    events = _make_events(30.0)
    shots = plan_camera_shots(30.0, events)
    assert isinstance(shots, list)
    assert 4 <= len(shots) <= 8
    assert all(isinstance(s, CameraShot) for s in shots)


def test_plan_camera_shots_coverage():
    events = _make_events(30.0)
    shots = plan_camera_shots(30.0, events)
    total = sum(s.duration for s in shots)
    assert abs(total - 30.0) < 0.5
    assert shots[0].start == pytest.approx(0.0, abs=1e-6)
    assert shots[-1].start + shots[-1].duration == pytest.approx(30.0, abs=1e-3)


def test_camera_state_at():
    events = _make_events(30.0)
    shots = plan_camera_shots(30.0, events)
    eye, target, fov = camera_state_at(5.0, shots)
    assert isinstance(eye, list) and len(eye) == 3
    assert isinstance(target, list) and len(target) == 3
    assert isinstance(fov, float) and fov > 0.0


def test_camera_state_at_boundaries():
    events = _make_events(30.0)
    shots = plan_camera_shots(30.0, events)
    duration = shots[-1].start + shots[-1].duration
    for t in (0.0, duration - 1e-3):
        eye, target, fov = camera_state_at(t, shots)
        assert len(eye) == 3 and len(target) == 3 and fov > 0.0


def test_camera_state_at_with_ai_plan():
    ai_plan = {
        "camera_suggestions": [
            {
                "start_fraction": 0.0,
                "duration_fraction": 0.25,
                "preset": "orbital_wide",
                "eye": [7.5, 4.5, 7.5],
                "target": [0.0, 0.0, 0.0],
                "fov": 60.0,
                "transition_in": "cut",
                "transition_out": "fade",
            },
            {
                "start_fraction": 0.25,
                "duration_fraction": 0.25,
                "preset": "low_angle",
                "transition_in": "fade",
                "transition_out": "cut",
            },
            {
                "start_fraction": 0.5,
                "duration_fraction": 0.25,
                "preset": "top_down",
            },
            {
                "start_fraction": 0.75,
                "duration_fraction": 0.25,
                "preset": "dramatic_zoom",
            },
        ]
    }
    shots = plan_camera_shots(40.0, [], ai_plan=ai_plan)
    assert len(shots) >= 2
    eye, target, fov = camera_state_at(10.0, shots)
    assert len(eye) == 3 and len(target) == 3 and fov > 0.0


# ===========================================================================
# LUFS mastering
# ===========================================================================


def _sine(freq=440.0, dur=1.0, sr=48000, amp=0.3):
    t = np.linspace(0.0, dur, int(sr * dur), endpoint=False)
    return amp * np.sin(2.0 * np.pi * freq * t)


def test_measure_lufs_sine():
    audio = _sine(440.0, 1.0)
    out = measure_lufs(audio, 48000)
    assert np.isfinite(out["lufs_integrated"])


def test_loudness_normalize():
    audio = _sine(440.0, 1.0, amp=0.1)
    norm = loudness_normalize(audio, 48000, target_lufs=-16.0)
    assert norm.shape == audio.shape
    assert float(np.max(np.abs(norm))) != pytest.approx(float(np.max(np.abs(audio))), abs=1e-6)


def test_apply_dither():
    audio = _sine(440.0, 0.5, amp=0.3)
    d = apply_dither(audio, bits=16, seed=1)
    assert d.shape == audio.shape
    assert float(np.max(np.abs(d - audio))) > 0.0


def test_master_audio():
    sr = 48000
    mono = _sine(440.0, 1.0, sr=sr, amp=0.3)
    stereo = np.stack([mono, mono], axis=1)
    out = master_audio(stereo, sr, target_lufs=-16.0)
    assert out.ndim == 2
    assert out.shape[0] == 2 or out.shape[1] == 2
    # Traz para formato (2, N) se veio como (N, 2).
    if out.shape[0] == stereo.shape[0]:
        out_t = out.T
    else:
        out_t = out
    assert out_t.shape[0] == 2
    post = measure_lufs(out, sr)
    assert abs(post["lufs_integrated"] - (-16.0)) < 3.0


def test_measure_lufs_silence():
    audio = np.zeros(48000, dtype=np.float64)
    out = measure_lufs(audio, 48000)
    assert out["lufs_integrated"] <= -70.0


# ===========================================================================
# Comment AI responder
# ===========================================================================


def test_classify_comment_fallback():
    assert classify_comment("Great video!") == "neutral"


def test_ai_reply_with_context_fallback():
    video = {"title": "T", "visual_family": "flow_field", "music_genre": "ambient"}
    assert ai_reply_with_context("nice!", video, commenter="bob") == ""


def test_contextual_reply_strategy_spam():
    video = {"title": "T"}
    assert contextual_reply_strategy("buy my course", "spam", video) == ""


def test_enhanced_reply_to_comment_fallback():
    comment = {
        "snippet": {
            "topLevelComment": {
                "snippet": {
                    "textDisplay": "Loved the visuals!",
                    "authorDisplayName": "viewer1",
                }
            }
        }
    }
    video = {"title": "T", "visual_family": "flow_field", "music_genre": "ambient"}
    out = enhanced_reply_to_comment(comment, video)
    assert out == ""


def test_enhanced_reply_to_comment_spam(monkeypatch):
    import utils.comment_ai_responder as car

    monkeypatch.setattr(car, "classify_comment", lambda text: "spam")
    comment = {
        "snippet": {
            "topLevelComment": {
                "snippet": {
                    "textDisplay": "click my link",
                    "authorDisplayName": "spammer",
                }
            }
        }
    }
    video = {"title": "T"}
    assert enhanced_reply_to_comment(comment, video) == ""
