"""Unit tests for src/pexels_downloader.py, focused on the "used video id"
dedup logic that keeps the pipeline from repeatedly downloading the same
Pexels clips across runs.

No real HTTP calls are made: ``PexelsDownloader.search_videos`` and
``download_video`` are patched with ``unittest.mock``.
"""
import json
from unittest.mock import patch

import pexels_downloader
from pexels_downloader import PexelsDownloader


def _write_used_ids(path, ids):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ids": ids}), encoding="utf-8")


def _video(video_id, quality="hd"):
    return {
        "id": video_id,
        "video_files": [{"quality": quality, "link": f"http://example.test/{video_id}.mp4"}],
    }


class TestUsedVideoIdPersistence:
    def test_load_returns_empty_list_when_file_missing(self, monkeypatch, tmp_path):
        used_ids_file = tmp_path / "used_pexels_ids.json"
        monkeypatch.setattr(pexels_downloader, "USED_VIDEO_IDS_FILE", used_ids_file)

        assert pexels_downloader._load_used_video_ids() == []

    def test_load_returns_empty_list_for_corrupted_json(self, monkeypatch, tmp_path):
        used_ids_file = tmp_path / "used_pexels_ids.json"
        used_ids_file.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(pexels_downloader, "USED_VIDEO_IDS_FILE", used_ids_file)

        assert pexels_downloader._load_used_video_ids() == []

    def test_save_then_load_round_trip(self, monkeypatch, tmp_path):
        used_ids_file = tmp_path / "used_pexels_ids.json"
        monkeypatch.setattr(pexels_downloader, "USED_VIDEO_IDS_FILE", used_ids_file)

        pexels_downloader._save_used_video_ids(["1", "2", "3"])

        assert pexels_downloader._load_used_video_ids() == ["1", "2", "3"]

    def test_save_trims_to_max_tracked_ids_keeping_most_recent(self, monkeypatch, tmp_path):
        used_ids_file = tmp_path / "used_pexels_ids.json"
        monkeypatch.setattr(pexels_downloader, "USED_VIDEO_IDS_FILE", used_ids_file)
        ids = [str(i) for i in range(pexels_downloader.MAX_TRACKED_VIDEO_IDS + 50)]

        pexels_downloader._save_used_video_ids(ids)

        saved = pexels_downloader._load_used_video_ids()
        assert len(saved) == pexels_downloader.MAX_TRACKED_VIDEO_IDS
        # Only the most recent ids are kept (oldest are dropped).
        assert saved[0] == ids[50]
        assert saved[-1] == ids[-1]

    def test_save_writes_atomically_via_temp_file_replace(self, monkeypatch, tmp_path):
        used_ids_file = tmp_path / "used_pexels_ids.json"
        monkeypatch.setattr(pexels_downloader, "USED_VIDEO_IDS_FILE", used_ids_file)

        pexels_downloader._save_used_video_ids(["7"])

        # The temp file used for the atomic replace must not be left behind.
        assert not used_ids_file.with_suffix(".json.tmp").exists()
        assert used_ids_file.exists()


class TestDownloadClipsForTopicDedup:
    def test_prefers_videos_not_already_used(self, monkeypatch, tmp_path):
        used_ids_file = tmp_path / "used_pexels_ids.json"
        monkeypatch.setattr(pexels_downloader, "USED_VIDEO_IDS_FILE", used_ids_file)
        _write_used_ids(used_ids_file, ["1", "2"])
        monkeypatch.setattr(pexels_downloader.random, "shuffle", lambda seq: None)

        videos = [_video(1), _video(2), _video(3)]
        downloader = PexelsDownloader()

        with patch.object(downloader, "search_videos", return_value=videos), \
                patch.object(downloader, "download_video", return_value=True) as mock_download:
            result = downloader.download_clips_for_topic("nature", tmp_path / "out", count=1)

        assert len(result) == 1
        assert mock_download.call_count == 1
        downloaded_url = mock_download.call_args[0][0]
        assert downloaded_url == "http://example.test/3.mp4"

    def test_falls_back_to_all_results_when_every_id_already_used(self, monkeypatch, tmp_path):
        used_ids_file = tmp_path / "used_pexels_ids.json"
        monkeypatch.setattr(pexels_downloader, "USED_VIDEO_IDS_FILE", used_ids_file)
        _write_used_ids(used_ids_file, ["1", "2"])
        monkeypatch.setattr(pexels_downloader.random, "shuffle", lambda seq: None)

        videos = [_video(1), _video(2)]
        downloader = PexelsDownloader()

        with patch.object(downloader, "search_videos", return_value=videos), \
                patch.object(downloader, "download_video", return_value=True) as mock_download:
            result = downloader.download_clips_for_topic("nature", tmp_path / "out", count=2)

        # No fresh ids were available, so the downloader must still return
        # clips (fall back to previously-used videos) rather than nothing.
        assert len(result) == 2
        assert mock_download.call_count == 2

    def test_persists_newly_downloaded_ids_for_future_dedup(self, monkeypatch, tmp_path):
        used_ids_file = tmp_path / "used_pexels_ids.json"
        monkeypatch.setattr(pexels_downloader, "USED_VIDEO_IDS_FILE", used_ids_file)
        monkeypatch.setattr(pexels_downloader.random, "shuffle", lambda seq: None)

        videos = [_video(42)]
        downloader = PexelsDownloader()

        with patch.object(downloader, "search_videos", return_value=videos), \
                patch.object(downloader, "download_video", return_value=True):
            downloader.download_clips_for_topic("nature", tmp_path / "out", count=1)

        assert "42" in pexels_downloader._load_used_video_ids()

    def test_does_not_persist_ids_when_nothing_downloaded(self, monkeypatch, tmp_path):
        used_ids_file = tmp_path / "used_pexels_ids.json"
        monkeypatch.setattr(pexels_downloader, "USED_VIDEO_IDS_FILE", used_ids_file)
        monkeypatch.setattr(pexels_downloader.random, "shuffle", lambda seq: None)

        videos = [_video(99)]
        downloader = PexelsDownloader()

        with patch.object(downloader, "search_videos", return_value=videos), \
                patch.object(downloader, "download_video", return_value=False):
            result = downloader.download_clips_for_topic("nature", tmp_path / "out", count=1)

        assert result == []
        assert not used_ids_file.exists()

    def test_num_clips_keyword_overrides_count(self, monkeypatch, tmp_path):
        """Regression guard for the main.py -> downloader num_clips keyword
        contract enforced by scripts/check_production_contracts.py."""
        used_ids_file = tmp_path / "used_pexels_ids.json"
        monkeypatch.setattr(pexels_downloader, "USED_VIDEO_IDS_FILE", used_ids_file)
        monkeypatch.setattr(pexels_downloader.random, "shuffle", lambda seq: None)

        videos = [_video(i) for i in range(5)]
        downloader = PexelsDownloader()

        with patch.object(downloader, "search_videos", return_value=videos), \
                patch.object(downloader, "download_video", return_value=True) as mock_download:
            result = downloader.download_clips_for_topic(
                "nature", tmp_path / "out", count=1, num_clips=3
            )

        assert len(result) == 3
        assert mock_download.call_count == 3
