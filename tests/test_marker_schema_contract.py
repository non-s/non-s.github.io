"""Schema contract: every field a downstream consumer of `.done` markers
actually reads must be present in upload_youtube.py's _done_marker()
output. _done_marker()'s key list was trimmed once already this session
(~90 fields down to 31, after confirming via a repo-wide grep that the
removed ones were genuinely unread) -- this test is what should catch it
if a *future* trim removes one of the fields these other files, living
outside upload_youtube.py, actually depend on. Each assertion names its
real consumer so a failure here points straight at what would break.
"""

from __future__ import annotations

from upload_youtube import _done_marker

# field -> the module/function that reads it from a `.done` marker.
CONSUMERS = {
    "video_id": "utils/branding_metrics.py, scripts/detect_orphan_videos.py, scripts/rebrand_video_thumbnails.py",
    "title": "utils/branding_metrics.py (playlist bucket), scripts/build_dashboard.py, scripts/rebrand_video_thumbnails.py",
    "series": "utils/branding_metrics.py, upload_youtube.py._playlist_titles",
    "category": "upload_youtube.py._playlist_titles",
    "upload_title_dedupe": "utils/branding_metrics.py (collision rate)",
    "uploaded_at": "scripts/build_dashboard.py (Recent Shorts sort/display)",
    "url": "scripts/build_dashboard.py (Recent Shorts watch link)",
    "description": "scripts/rebrand_video_thumbnails.py (build_plan)",
    "duration_s": "dashboard/analytics production signals",
    "bgm_track_id": "attribution/analytics production signals",
    "source_license_evidence": "attribution -- required for CC-BY compliance",
}


def _minimal_meta(**overrides) -> dict:
    meta = {
        "title": "Rainy Night Anime Lofi — Amber Hours 🌧️",
        "description": "rain window lofi beats.",
        "category": "lofi",
        "series": "Rainy Night Lofi Shorts",
        "tags": ["rain window", "lofi"],
        "video": "/tmp/short-1.mp4",
        "duration_s": 45.0,
        "story_id": "lofi-1700000000-1234",
        "source": "pixabay",
        "source_clip_id": "1",
        "bgm_track_id": "1",
        "source_license_evidence": "https://pixabay.com/videos/id-1/",
    }
    meta.update(overrides)
    return meta


def test_done_marker_includes_every_field_a_downstream_consumer_reads():
    marker = _done_marker("VID123", _minimal_meta())
    missing = [field for field in CONSUMERS if field not in marker]
    assert not missing, f"_done_marker() dropped field(s) still read by: {[CONSUMERS[f] for f in missing]}"


def test_done_marker_video_id_url_and_uploaded_at_are_always_populated():
    """These three are set by _done_marker() itself (not sourced from
    meta), so they should never come back empty for a real upload."""
    marker = _done_marker("VID123", _minimal_meta())
    assert marker["video_id"] == "VID123"
    assert marker["url"]
    assert marker["uploaded_at"]


def test_done_marker_upload_title_dedupe_defaults_to_a_dict_not_missing():
    """utils/branding_metrics.py calls .get("applied") on this field --
    it must never come back as None/missing, or that call would crash."""
    marker = _done_marker("VID123", _minimal_meta())
    assert isinstance(marker["upload_title_dedupe"], dict)


def test_done_marker_contract_holds_for_mix_metadata_too():
    """generate_lofi_mix.py's metadata shape (is_short False, no
    pexels_video_id-style short-only fields) must satisfy the same
    contract as a Short's."""
    meta = _minimal_meta(
        series="Rainy Night Lofi Mix",
        is_short=False,
        title="Rainy Night Anime Lofi (1 Hour) — Amber Hours 🌧️",
    )
    marker = _done_marker("MIXVID1", meta)
    missing = [field for field in CONSUMERS if field not in marker]
    assert not missing
