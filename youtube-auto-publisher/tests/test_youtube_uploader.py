"""Unit tests for src/youtube_uploader.py.

Covers:
- exponential backoff/retry math in ``_sleep_before_retry``
- the resumable-upload retry loop in ``upload_video`` for retriable HTTP
  statuses (429/500/502/503/504)
- distinct handling of 403 quota/upload-limit errors (``QuotaExceededError``)
  versus other, unrelated 403 responses

No real network or OAuth calls are made: ``YouTubeUploader._authenticate``
is patched out and the YouTube API client (``self.service``) is replaced
with a ``unittest.mock.MagicMock``.
"""
import http.client
import json
import types
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

import youtube_uploader as yt_uploader_module
from youtube_uploader import QuotaExceededError, YouTubeUploader


def make_fake_resp(status: int) -> types.SimpleNamespace:
    """Builds a minimal stand-in for the httplib2.Response object the real
    googleapiclient HttpError expects: it needs both ``.status`` (used by
    the uploader's retry logic) and ``.reason`` (read internally by
    HttpError.__init__ via _get_reason())."""
    return types.SimpleNamespace(
        status=status,
        reason=http.client.responses.get(status, ""),
    )


def make_http_error(status: int, reason: str = "", message: str = "") -> HttpError:
    """Builds a real googleapiclient HttpError with a JSON error body,
    matching the shape the YouTube Data API actually returns."""
    payload = {
        "error": {
            "code": status,
            "message": message or reason,
            "errors": [{"reason": reason, "message": message or reason}] if reason else [],
        }
    }
    content = json.dumps(payload).encode("utf-8")
    return HttpError(make_fake_resp(status), content)


def make_uploader() -> YouTubeUploader:
    """Builds a YouTubeUploader without touching real OAuth/HTTP."""
    with patch.object(YouTubeUploader, "_authenticate", lambda self: None):
        uploader = YouTubeUploader()
    uploader.service = MagicMock()
    return uploader


class TestSleepBeforeRetry:
    def test_increments_retry_count_and_sleeps(self, monkeypatch):
        uploader = make_uploader()
        sleep_calls = []
        monkeypatch.setattr(yt_uploader_module.time, "sleep", lambda s: sleep_calls.append(s))
        monkeypatch.setattr(yt_uploader_module.random, "random", lambda: 0.0)

        next_count = uploader._sleep_before_retry(0, "HTTP 503")

        assert next_count == 1
        assert sleep_calls == [1.0]  # 2**0 + 0.0

    def test_backoff_grows_exponentially(self, monkeypatch):
        uploader = make_uploader()
        sleep_calls = []
        monkeypatch.setattr(yt_uploader_module.time, "sleep", lambda s: sleep_calls.append(s))
        monkeypatch.setattr(yt_uploader_module.random, "random", lambda: 0.0)

        uploader._sleep_before_retry(3, "HTTP 500")  # 2**3 = 8

        assert sleep_calls == [8.0]

    def test_sleep_is_capped_at_configured_max(self, monkeypatch):
        uploader = make_uploader()
        sleep_calls = []
        monkeypatch.setattr(yt_uploader_module.time, "sleep", lambda s: sleep_calls.append(s))
        monkeypatch.setattr(yt_uploader_module.random, "random", lambda: 0.0)
        monkeypatch.setattr(yt_uploader_module.config, "UPLOAD_RETRY_MAX_SLEEP_SECONDS", 5)
        monkeypatch.setattr(yt_uploader_module.config, "MAX_UPLOAD_RETRIES", 20)

        uploader._sleep_before_retry(10, "HTTP 500")  # 2**10 uncapped, must clamp to 5

        assert sleep_calls == [5]

    def test_raises_runtime_error_after_max_retries(self, monkeypatch):
        uploader = make_uploader()
        monkeypatch.setattr(yt_uploader_module.config, "MAX_UPLOAD_RETRIES", 3)

        with pytest.raises(RuntimeError):
            uploader._sleep_before_retry(3, "HTTP 500")


class TestUploadVideoRetryBehavior:
    """Exercises the retry loop inside upload_video for the 429/500/502/503/504
    family, using a mocked resumable-upload request object."""

    @patch.object(yt_uploader_module, "MediaFileUpload")
    def test_retries_on_retriable_statuses_then_succeeds(self, mock_media, monkeypatch, tmp_path):
        uploader = make_uploader()
        monkeypatch.setattr(yt_uploader_module.time, "sleep", lambda s: None)

        mock_request = MagicMock()
        mock_request.next_chunk.side_effect = [
            make_http_error(503),
            make_http_error(500),
            make_http_error(502),
            make_http_error(504),
            make_http_error(429),
            (None, {"id": "video123"}),
        ]
        uploader.service.videos.return_value.insert.return_value = mock_request

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake-video-bytes")

        result = uploader.upload_video(video_path, "Title", "Description")

        assert result == {"id": "video123"}
        assert mock_request.next_chunk.call_count == 6

    @patch.object(yt_uploader_module, "MediaFileUpload")
    def test_retries_on_transient_connection_errors(self, mock_media, monkeypatch, tmp_path):
        uploader = make_uploader()
        monkeypatch.setattr(yt_uploader_module.time, "sleep", lambda s: None)

        mock_request = MagicMock()
        mock_request.next_chunk.side_effect = [
            ConnectionError("reset"),
            TimeoutError("timed out"),
            (None, {"id": "video456"}),
        ]
        uploader.service.videos.return_value.insert.return_value = mock_request

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake-video-bytes")

        result = uploader.upload_video(video_path, "Title", "Description")

        assert result == {"id": "video456"}
        assert mock_request.next_chunk.call_count == 3

    @patch.object(yt_uploader_module, "MediaFileUpload")
    def test_non_retriable_status_raises_immediately(self, mock_media, monkeypatch, tmp_path):
        uploader = make_uploader()
        monkeypatch.setattr(yt_uploader_module.time, "sleep", lambda s: None)

        mock_request = MagicMock()
        mock_request.next_chunk.side_effect = make_http_error(404, reason="notFound")
        uploader.service.videos.return_value.insert.return_value = mock_request

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake-video-bytes")

        with pytest.raises(HttpError):
            uploader.upload_video(video_path, "Title", "Description")
        assert mock_request.next_chunk.call_count == 1

    @patch.object(yt_uploader_module, "MediaFileUpload")
    def test_gives_up_after_max_retries(self, mock_media, monkeypatch, tmp_path):
        uploader = make_uploader()
        monkeypatch.setattr(yt_uploader_module.time, "sleep", lambda s: None)
        monkeypatch.setattr(yt_uploader_module.config, "MAX_UPLOAD_RETRIES", 2)

        mock_request = MagicMock()
        mock_request.next_chunk.side_effect = [make_http_error(500) for _ in range(10)]
        uploader.service.videos.return_value.insert.return_value = mock_request

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake-video-bytes")

        with pytest.raises(RuntimeError):
            uploader.upload_video(video_path, "Title", "Description")


class TestQuotaExceededHandling:
    """Task requirement: 403 responses whose body reason is quotaExceeded or
    uploadLimitExceeded must be detected distinctly, logged clearly, and
    raised as QuotaExceededError instead of an unhandled HttpError. Other
    403s must be completely unaffected."""

    @pytest.mark.parametrize("reason", ["quotaExceeded", "uploadLimitExceeded"])
    @patch.object(yt_uploader_module, "MediaFileUpload")
    def test_quota_reasons_raise_quota_exceeded_error(self, mock_media, reason, monkeypatch, tmp_path):
        uploader = make_uploader()
        monkeypatch.setattr(yt_uploader_module.time, "sleep", lambda s: None)

        mock_request = MagicMock()
        mock_request.next_chunk.side_effect = make_http_error(403, reason=reason)
        uploader.service.videos.return_value.insert.return_value = mock_request

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake-video-bytes")

        with pytest.raises(QuotaExceededError) as exc_info:
            uploader.upload_video(video_path, "Title", "Description")

        assert exc_info.value.reason == reason
        # Must not have retried - quota errors are not transient.
        assert mock_request.next_chunk.call_count == 1

    @patch.object(yt_uploader_module, "MediaFileUpload")
    def test_other_403_reasons_still_raise_plain_http_error(self, mock_media, monkeypatch, tmp_path):
        uploader = make_uploader()
        monkeypatch.setattr(yt_uploader_module.time, "sleep", lambda s: None)

        mock_request = MagicMock()
        mock_request.next_chunk.side_effect = make_http_error(403, reason="forbidden")
        uploader.service.videos.return_value.insert.return_value = mock_request

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake-video-bytes")

        with pytest.raises(HttpError) as exc_info:
            uploader.upload_video(video_path, "Title", "Description")

        assert not isinstance(exc_info.value, QuotaExceededError)
        assert mock_request.next_chunk.call_count == 1

    @patch.object(yt_uploader_module, "MediaFileUpload")
    def test_403_with_no_parseable_body_still_raises_plain_http_error(self, mock_media, monkeypatch, tmp_path):
        uploader = make_uploader()
        monkeypatch.setattr(yt_uploader_module.time, "sleep", lambda s: None)

        resp = make_fake_resp(403)
        error = HttpError(resp, b"not json at all")

        mock_request = MagicMock()
        mock_request.next_chunk.side_effect = error
        uploader.service.videos.return_value.insert.return_value = mock_request

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake-video-bytes")

        with pytest.raises(HttpError):
            uploader.upload_video(video_path, "Title", "Description")

    def test_extract_error_reason_from_typical_quota_body(self):
        error = make_http_error(403, reason="quotaExceeded", message="The request cannot be completed")
        assert YouTubeUploader._extract_error_reason(error) == "quotaExceeded"

    def test_extract_error_reason_returns_empty_for_malformed_body(self):
        resp = make_fake_resp(403)
        error = HttpError(resp, b"{not valid json")
        assert YouTubeUploader._extract_error_reason(error) == ""
