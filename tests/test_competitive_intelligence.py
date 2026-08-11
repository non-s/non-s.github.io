from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from utils import competitive_intelligence


def test_load_benchmark_channels_is_transparent_and_configurable(tmp_path, monkeypatch):
    config = tmp_path / "channels.json"
    config.write_text(json.dumps({"channels": [{"id": "channel-1", "label": "Reference"}]}))
    monkeypatch.setattr(competitive_intelligence, "CONFIG_FILE", config)
    assert competitive_intelligence.load_benchmark_channels() == [{"id": "channel-1", "label": "Reference"}]


def test_collects_public_metadata_without_copying(tmp_path, monkeypatch):
    config = tmp_path / "channels.json"
    config.write_text(json.dumps({"channels": [{"id": "channel-1", "label": "Reference"}]}))
    monkeypatch.setattr(competitive_intelligence, "CONFIG_FILE", config)
    service = MagicMock()
    service.channels().list.return_value.execute.return_value = {
        "items": [
            {
                "id": "channel-1",
                "snippet": {"title": "Reference"},
                "statistics": {"subscriberCount": "1", "videoCount": "2"},
                "contentDetails": {"relatedPlaylists": {"uploads": "uploads-1"}},
            }
        ]
    }
    service.playlistItems().list.return_value.execute.return_value = {
        "items": [{"snippet": {"title": "A public title"}, "contentDetails": {"videoId": "video-1"}}]
    }
    with patch("utils.competitive_intelligence.retry_youtube_call", side_effect=lambda call: call()):
        report = competitive_intelligence.collect_competitive_intelligence(service)
    assert report["method"] == "public metadata only; no copying permitted"
    assert report["channels"][0]["recent_videos"][0]["video_id"] == "video-1"
