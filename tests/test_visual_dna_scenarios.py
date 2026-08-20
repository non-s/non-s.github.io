from __future__ import annotations

import numpy as np

from utils.visual_intelligence import analyze_visual_dna


def _dna(monkeypatch, tmp_path, frames):
    monkeypatch.setattr("utils.visual_intelligence._sampled_frames", lambda path, samples: frames)
    result = analyze_visual_dna(tmp_path / "encoded.mp4")
    assert result is not None
    return result


def test_empty_and_low_contrast_final_frames_are_measured_not_crashed(monkeypatch, tmp_path):
    empty = [np.zeros((90, 160, 3), dtype=np.uint8) for _ in range(4)]
    empty_dna = _dna(monkeypatch, tmp_path, empty)
    assert empty_dna.composition["screen_fill"] == 0
    low = [np.full((90, 160, 3), 10 + index, dtype=np.uint8) for index in range(4)]
    low_dna = _dna(monkeypatch, tmp_path, low)
    assert low_dna.appearance["contrast"] < 0.02


def test_static_and_high_motion_are_distinguishable(monkeypatch, tmp_path):
    frame = np.zeros((90, 160, 3), dtype=np.uint8)
    frame[30:60, 60:100] = 255
    static = _dna(monkeypatch, tmp_path, [frame.copy() for _ in range(5)])
    moving = []
    for x in (5, 30, 60, 90, 120):
        current = np.zeros_like(frame)
        current[30:60, x : x + 25] = 255
        moving.append(current)
    dynamic = _dna(monkeypatch, tmp_path, moving)
    assert static.motion["frame_difference_mean"] == 0
    assert dynamic.motion["frame_difference_mean"] > static.motion["frame_difference_mean"]
    assert static.temporal["narrative_pass"] is False


def test_three_visually_distinct_acts_pass_temporal_narrative(monkeypatch, tmp_path):
    frames = []
    for index in range(12):
        frame = np.zeros((90, 160, 3), dtype=np.uint8)
        act = index // 4
        x = 10 + act * 45 + index * 2
        size = 15 + act * 8
        frame[20 : 20 + size, x : x + size] = (40 + act * 80, 120, 240 - act * 60)
        frames.append(frame)
    dna = _dna(monkeypatch, tmp_path, frames)
    assert dna.temporal["narrative_pass"] is True
    assert dna.temporal["opening_ending_distance"] > 0


def test_symmetric_asymmetric_and_dense_compositions_are_observed(monkeypatch, tmp_path):
    symmetric = np.zeros((90, 160, 3), dtype=np.uint8)
    symmetric[20:70, 30:50] = 255
    symmetric[20:70, 110:130] = 255
    asymmetric = np.zeros_like(symmetric)
    asymmetric[10:80, 5:35] = 255
    dense = np.indices((90, 160)).sum(axis=0) % 2
    dense = np.repeat((dense * 255).astype(np.uint8)[..., None], 3, axis=2)
    symmetric_dna = _dna(monkeypatch, tmp_path, [symmetric] * 4)
    asymmetric_dna = _dna(monkeypatch, tmp_path, [asymmetric] * 4)
    dense_dna = _dna(monkeypatch, tmp_path, [dense] * 4)
    assert symmetric_dna.composition["symmetry"] > asymmetric_dna.composition["symmetry"]
    assert dense_dna.composition["entropy"] > asymmetric_dna.composition["entropy"]


def test_unreadable_final_video_returns_no_dna(monkeypatch, tmp_path):
    monkeypatch.setattr("utils.visual_intelligence._sampled_frames", lambda path, samples: [])
    assert analyze_visual_dna(tmp_path / "broken.mp4") is None
