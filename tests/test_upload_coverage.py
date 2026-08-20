"""Targeted coverage for upload_youtube.py uncovered helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import upload_youtube


def test_build_tags_with_scene_words() -> None:
    tags = upload_youtube._build_tags("calm wireframe flow", None)
    assert "wireframe" in tags
    assert "flow" in tags
    assert all(len(w) > 2 for w in tags if w not in {t for t in upload_youtube.active_channel.base_tags})


def test_build_tags_with_hashtags_strips_hash() -> None:
    tags = upload_youtube._build_tags("cat", ["#Chill", "#Focus"])
    assert "Chill" in tags
    assert "Focus" in tags
    assert all(not t.startswith("#") for t in tags)


def test_build_tags_dedupes_and_caps_at_15() -> None:
    tags = upload_youtube._build_tags("a", ["#x"] * 20)
    assert len(tags) <= 15
    assert len(tags) == len(set(tags))


def test_build_tags_empty_scene_and_hashtags() -> None:
    tags = upload_youtube._build_tags("", None)
    assert isinstance(tags, list)
    assert len(tags) <= 15


def test_record_video_tags_writes_json(tmp_path: Path, monkeypatch) -> None:
    tags_file = tmp_path / "video_tags.json"
    monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tags_file)
    upload_youtube._record_video_tags("vid1", {"scene": "cat", "hook": "Cute", "mood": "relax"})
    data = json.loads(tags_file.read_text(encoding="utf-8"))
    assert data["vid1"]["scene"] == "cat"
    assert data["vid1"]["hook"] == "Cute"


def test_record_video_tags_skips_when_no_scene(tmp_path: Path, monkeypatch) -> None:
    tags_file = tmp_path / "video_tags.json"
    monkeypatch.setattr(upload_youtube, "_VIDEO_TAGS_FILE", tags_file)
    upload_youtube._record_video_tags("vid1", {"hook": "Cute"})
    assert not tags_file.exists()


def test_meta_path_returns_none_for_missing(tmp_path: Path) -> None:
    assert upload_youtube._meta_path({}, "thumbnail") is None
    assert upload_youtube._meta_path({"thumbnail": ""}, "thumbnail") is None


def test_meta_path_returns_path_for_value(tmp_path: Path) -> None:
    assert upload_youtube._meta_path({"thumbnail": "/tmp/x.png"}, "thumbnail") == Path("/tmp/x.png")


def test_production_contract_issues_clean() -> None:
    meta = {
        "visual_source": "procedural_python",
        "audio_source": "synthetic_python",
        "quality_report": {"passed": True, "issues": [], "fingerprint": [0.0] * 20},
        "generator_profile": {"engine_version": "2.1.0"},
    }
    assert upload_youtube._production_contract_issues(meta) == []


def test_production_contract_issues_quality_has_issues() -> None:
    meta = {
        "visual_source": "procedural_python",
        "audio_source": "synthetic_python",
        "quality_report": {"passed": True, "issues": ["low_motion"], "fingerprint": [0.0] * 20},
        "generator_profile": {"engine_version": "2.1.0"},
    }
    assert "quality_report_has_issues" in upload_youtube._production_contract_issues(meta)


def test_production_contract_issues_bad_version_string() -> None:
    meta = {
        "visual_source": "procedural_python",
        "audio_source": "synthetic_python",
        "quality_report": {"passed": True, "issues": [], "fingerprint": [0.0] * 20},
        "generator_profile": {"engine_version": "not-a-version"},
    }
    assert "engine_version_below_2_1" in upload_youtube._production_contract_issues(meta)


def test_production_contract_issues_no_profile() -> None:
    meta = {
        "visual_source": "procedural_python",
        "audio_source": "synthetic_python",
        "quality_report": {"passed": True, "issues": [], "fingerprint": [0.0] * 20},
    }
    assert "engine_version_below_2_1" in upload_youtube._production_contract_issues(meta)


def test_update_privacy_to_public_success() -> None:
    service = MagicMock()
    service.videos().update().execute.return_value = {}
    assert upload_youtube._update_privacy_to_public(service, "vid1") is True


def test_update_privacy_to_public_failure_sends_alert() -> None:
    service = MagicMock()
    service.videos().update().execute.side_effect = RuntimeError("boom")
    with patch("upload_youtube.send_alert") as mock_alert:
        assert upload_youtube._update_privacy_to_public(service, "vid2") is False
    mock_alert.assert_called_once()


def test_wait_for_content_id_check_processing_complete() -> None:
    service = MagicMock()
    service.videos().list().execute.return_value = {
        "items": [{"processingDetails": {"processingStatus": "succeeded"}, "status": {"rejectionReason": ""}}]
    }
    with patch("upload_youtube.time.sleep"), patch(
        "upload_youtube._retry_youtube_call", side_effect=lambda func, *a, **k: func()
    ):
        result = upload_youtube.wait_for_content_id_check(service, "v", max_wait_minutes=1)
    assert result["processing_complete"] is True
    assert result["safe_to_publish"] is True
