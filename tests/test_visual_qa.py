"""Tests for optional Gemini thumbnail review."""
from unittest.mock import MagicMock, patch

from PIL import Image

from utils.visual_qa import evaluate_frame, evaluate_local_frame


def test_visual_qa_is_fail_open_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    image = tmp_path / "frame.jpg"; image.write_bytes(b"x")
    result = evaluate_frame(image, "octopus")
    assert result["approved"]
    assert not result["checked"]


def test_visual_qa_blocks_valid_negative_verdict(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    image = tmp_path / "frame.jpg"; image.write_bytes(b"x" * 6000)
    response = MagicMock(status_code=200)
    response.json.return_value = {"candidates": [{"content": {"parts": [{"text":
        '{"approved": false, "subject_visible": true, "subject_match": false, '
        '"thumbnail_quality": 4, "reason": "unrelated person"}'
    }]}}]}
    with patch("utils.visual_qa.requests.post", return_value=response):
        result = evaluate_frame(image, "octopus")
    assert result["checked"]
    assert not result["approved"]


def test_local_visual_qa_scores_good_frame(tmp_path):
    image = tmp_path / "good.jpg"
    Image.new("RGB", (320, 480), (90, 140, 100)).save(image)
    result = evaluate_local_frame(image)
    assert result["checked"]
    assert result["score"] >= 5


def test_local_visual_qa_warns_on_dark_flat_frame(tmp_path):
    image = tmp_path / "dark.jpg"
    Image.new("RGB", (320, 480), (5, 5, 5)).save(image)
    result = evaluate_local_frame(image)
    assert result["checked"]
    assert result["score"] < 6
    assert "too_dark" in result["reason"]
