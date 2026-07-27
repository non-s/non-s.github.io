"""Testes para scripts/sync_animal_broll.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import scripts.sync_animal_broll as sync_animal_broll


def _hit(width=1280, height=720, tags="cute cat real", video_type="film"):
    return {
        "tags": tags,
        "user": "someone",
        "pageURL": "https://pixabay.com/videos/cute-cat-1",
        "type": video_type,
        "likes": 10,
        "videos": {"large": {"url": "https://cdn.example/cat.mp4", "width": width, "height": height}},
    }


class TestResolutionFilter:
    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_rejects_low_resolution_hit(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = lambda self, other: MagicMock(exists=lambda: False, with_suffix=lambda s: MagicMock())
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit(width=320, height=180)]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        downloaded = sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5)

        assert downloaded == 0
        mock_download.assert_not_called()

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_accepts_normal_resolution_hit(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = lambda self, other: MagicMock(exists=lambda: False, with_suffix=lambda s: MagicMock())
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit(width=1280, height=720)]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        downloaded = sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5)

        assert downloaded == 1
        mock_download.assert_called_once()

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_missing_dimensions_does_not_block(self, mock_get, mock_video_dir, mock_download):
        """Campos width/height ausentes (API mudou/hit incompleto) nao devem
        bloquear o clip - so pula a checagem de resolucao."""
        mock_video_dir.__truediv__ = lambda self, other: MagicMock(exists=lambda: False, with_suffix=lambda s: MagicMock())
        hit = _hit()
        hit["videos"]["large"] = {"url": "https://cdn.example/cat.mp4"}
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [hit]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        downloaded = sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5)

        assert downloaded == 1
