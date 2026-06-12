"""Tests for utils/face_crop.py — pure logic + fallbacks, no real OpenCV
required (we monkeypatch the imports for cross-platform sandboxes)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from utils import face_crop


def test_x_crop_offset_centered_when_no_face():
    assert face_crop.x_crop_offset_expr(None) == "(iw-ow)/2"


def test_x_crop_offset_biases_toward_face():
    # Face at 75 % of source width → crop window centred around there
    # but clamped to [0, iw-ow].
    expr = face_crop.x_crop_offset_expr(0.75, source_w=1920, short_w=1080)
    assert "0.7500" in expr
    assert "max(0" in expr
    assert "min(iw-ow" in expr


def test_x_crop_offset_zero_handled():
    expr = face_crop.x_crop_offset_expr(0.0)
    assert "0.0000" in expr


def test_detect_face_falls_back_when_opencv_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(face_crop, "_try_import_opencv", lambda: False)
    fake_clip = tmp_path / "clip.mp4"
    fake_clip.write_bytes(b"x" * 100)
    out = face_crop.detect_face_center(fake_clip, tmp_path)
    assert out is None


def test_detect_face_falls_back_when_frame_extract_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(face_crop, "_try_import_opencv", lambda: True)
    monkeypatch.setattr(face_crop, "_extract_first_frame", lambda c, d: False)
    fake_clip = tmp_path / "clip.mp4"
    fake_clip.write_bytes(b"x" * 100)
    assert face_crop.detect_face_center(fake_clip, tmp_path) is None


def test_detect_face_returns_normalised_center_when_face_found(tmp_path, monkeypatch):
    """Stub the entire cv2 chain so we can assert the math without ffmpeg."""
    monkeypatch.setattr(face_crop, "_try_import_opencv", lambda: True)
    monkeypatch.setattr(face_crop, "_extract_first_frame", lambda clip_path, dest: (dest.write_bytes(b"x"), True)[1])

    import types

    fake_cv2 = types.SimpleNamespace()

    class _FakeCascade:
        def detectMultiScale(self, gray, scaleFactor, minNeighbors, minSize):
            # Return ONE face at (x=400, y=200, w=100, h=100) in a
            # 1920x1080 frame → centre at (450, 250) → (0.234..., 0.231...).
            return [(400, 200, 100, 100)]

    fake_cv2.CascadeClassifier = lambda path: _FakeCascade()
    fake_cv2.data = types.SimpleNamespace(haarcascades="/fake/")
    fake_cv2.cvtColor = lambda img, code: img
    fake_cv2.COLOR_BGR2GRAY = 0

    class _FakeImg:
        shape = (1080, 1920)  # ndarray.shape = (h, w)

    fake_cv2.imread = lambda path: _FakeImg()

    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    fake_clip = tmp_path / "clip.mp4"
    fake_clip.write_bytes(b"x")
    result = face_crop.detect_face_center(fake_clip, tmp_path)
    assert result is not None
    fx, fy = result
    assert abs(fx - 450 / 1920) < 0.001
    assert abs(fy - 250 / 1080) < 0.001


def test_detect_face_returns_none_when_no_face_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(face_crop, "_try_import_opencv", lambda: True)
    monkeypatch.setattr(face_crop, "_extract_first_frame", lambda clip_path, dest: (dest.write_bytes(b"x"), True)[1])

    import types

    fake_cv2 = types.SimpleNamespace()

    class _FakeCascade:
        def detectMultiScale(self, *a, **k):
            return []

    fake_cv2.CascadeClassifier = lambda path: _FakeCascade()
    fake_cv2.data = types.SimpleNamespace(haarcascades="/fake/")
    fake_cv2.cvtColor = lambda img, code: img
    fake_cv2.COLOR_BGR2GRAY = 0

    class _FakeImg:
        shape = (1080, 1920)

    fake_cv2.imread = lambda path: _FakeImg()

    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    fake_clip = tmp_path / "clip.mp4"
    fake_clip.write_bytes(b"x")
    assert face_crop.detect_face_center(fake_clip, tmp_path) is None
