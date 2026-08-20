"""Tests for upload_youtube.wait_for_content_id_check (Frente F)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import upload_youtube


def _mock_service(response: dict, error: Exception | None = None) -> MagicMock:
    service = MagicMock()
    execute = MagicMock(return_value=response)
    if error is not None:
        execute = MagicMock(side_effect=error)
    service.videos().list.return_value.execute = execute
    return service


@patch("upload_youtube.time.sleep")
@patch("upload_youtube._retry_youtube_call", side_effect=lambda func, *a, **k: func())
def test_processing_complete_no_claims_is_safe(_retry, _sleep):
    """Processing terminated, no rejection/failure -> safe_to_publish True."""
    response = {
        "items": [
            {
                "processingDetails": {"processingStatus": "succeeded"},
                "status": {"rejectionReason": ""},
            }
        ]
    }
    service = _mock_service(response)
    result = upload_youtube.wait_for_content_id_check(service, "vid1")
    assert result == {
        "processing_complete": True,
        "has_claims": False,
        "safe_to_publish": True,
    }


@patch("upload_youtube.time.sleep")
@patch("upload_youtube._retry_youtube_call", side_effect=lambda func, *a, **k: func())
def test_claims_detected_is_not_safe(_retry, _sleep):
    """A rejectionReason means claims -> not safe to publish."""
    response = {
        "items": [
            {
                "processingDetails": {"processingStatus": "succeeded"},
                "status": {"rejectionReason": "copyright"},
            }
        ]
    }
    service = _mock_service(response)
    result = upload_youtube.wait_for_content_id_check(service, "vid2")
    assert result["processing_complete"] is True
    assert result["has_claims"] is True
    assert result["safe_to_publish"] is False


@patch("upload_youtube.time.sleep")
@patch("upload_youtube._retry_youtube_call", side_effect=lambda func, *a, **k: func())
def test_processing_failure_reason_counts_as_claims(_retry, _sleep):
    response = {
        "items": [
            {
                "processingDetails": {
                    "processingStatus": "failed",
                    "processingFailureReason": "unsupported_format",
                },
                "status": {"rejectionReason": ""},
            }
        ]
    }
    service = _mock_service(response)
    result = upload_youtube.wait_for_content_id_check(service, "vid3")
    assert result["has_claims"] is True
    assert result["safe_to_publish"] is False


@patch("upload_youtube.time.sleep")
@patch("upload_youtube._retry_youtube_call", side_effect=lambda func, *a, **k: func())
def test_terminated_processing_is_not_safe(_retry, _sleep):
    service = _mock_service(
        {"items": [{"processingDetails": {"processingStatus": "terminated"}, "status": {}}]}
    )
    result = upload_youtube.wait_for_content_id_check(service, "vid-terminated")
    assert result == {"processing_complete": True, "has_claims": True, "safe_to_publish": False}


@patch("upload_youtube.time.sleep")
@patch("upload_youtube._retry_youtube_call", side_effect=lambda func, *a, **k: func())
def test_timeout_returns_not_safe(_retry, _sleep):
    """Processing never terminates -> loop exits at deadline, not safe."""
    response = {
        "items": [
            {
                "processingDetails": {"processingStatus": "processing"},
                "status": {"rejectionReason": ""},
            }
        ]
    }
    service = _mock_service(response)
    # max_wait_minutes=0 -> deadline already in the past, loop body never runs.
    result = upload_youtube.wait_for_content_id_check(service, "vid4", max_wait_minutes=0)
    assert result == {
        "processing_complete": False,
        "has_claims": False,
        "safe_to_publish": False,
    }


@patch("upload_youtube.time.sleep")
@patch("upload_youtube._retry_youtube_call", side_effect=lambda func, *a, **k: func())
def test_empty_items_returns_not_safe(_retry, _sleep):
    """No items in the response -> not safe (video vanished)."""
    service = _mock_service({"items": []})
    result = upload_youtube.wait_for_content_id_check(service, "vid5", max_wait_minutes=0)
    assert result["safe_to_publish"] is False
    assert result["processing_complete"] is False


@patch("upload_youtube.time.sleep")
@patch("upload_youtube._retry_youtube_call", side_effect=lambda func, *a, **k: func())
def test_api_error_is_handled_gracefully(_retry, _sleep):
    """An API error inside the loop is logged, not raised; deadline then exits."""
    service = _mock_service({}, error=RuntimeError("api boom"))
    result = upload_youtube.wait_for_content_id_check(service, "vid6", max_wait_minutes=0)
    assert result["safe_to_publish"] is False
    assert result["processing_complete"] is False
