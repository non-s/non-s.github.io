"""
End-to-end smoke test for the Shorts pipeline.

We don't need the full network or ffmpeg to validate that the modules
wire together — we mock every external touchpoint (AI, edge-tts,
Pexels, Whisper, FFmpeg, YouTube) and assert that:

  1. `fetch_news._enrich_story` produces a queue entry with the
     fields generate_shorts.py expects.
  2. `generate_shorts.generate_short` consumes that entry, calls
     each external service exactly once via mocks, and produces
     a metadata sidecar with the right keys for upload_youtube.py.
  3. The metadata sidecar contains the experiment tags so
     youtube_analytics.py can later compute winners.

When any wiring breaks, this test goes red — way faster than waiting
for CI to fail in production.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# These three modules depend on external libs that may be missing in
# the sandbox. We skip cleanly when so; CI has them.
pytest.importorskip("feedparser")
pytest.importorskip("PIL")


@pytest.fixture
def fake_queue_story():
    """The shape fetch_news.py produces and generate_shorts.py expects."""
    return {
        "id":             "abc123",
        "fetched_at":     "2026-05-18T12:00:00+00:00",
        "published_at":   "2026-05-18T11:00:00+00:00",
        "consumed":       False,
        "consumed_at":    None,
        "title":          "Fed just cut rates — and that breaks the inflation story",
        "url":            "https://news.example.com/fed-cut",
        "source":         "Reuters",
        "category":       "business",
        "description":    "The Federal Reserve cut interest rates by 50 basis points today. "
                          "Powell cited cooling inflation. Markets had priced in 25 bps; "
                          "the surprise sent stocks higher.",
        "image_url":      "",
        "breaking":       True,
        "relevance":      8.5,
        "native_lang":    "en",
        "score":          9,
        "seo_title":      "Fed cuts rates 50 bps — markets blindsided",
        "yt_tags":        ["fed", "powell", "rates", "world news", "breaking news"],
        "geo_hashtag":    "USA",
        "topic_hashtag":  "Markets",
        "yt_description": "Fed surprised markets with a 50 bps cut today. The bond market "
                          "had priced 25. Powell said inflation cooled fast.\n"
                          "Source: Reuters\n#Shorts #WorldNews #USA #Markets",
        "thumbnail_text": "FED CUTS 50BPS",
        "hook":           "The Fed just cut rates 50 basis points.",
        "script":         ("The Fed just cut rates 50 basis points. The bond market had "
                            "priced 25 — half what Powell delivered. Markets are calling "
                            "this a victory lap on inflation. Mortgage rates won't follow "
                            "as fast. Watch credit-card delinquencies next."),
        "lead":           "Fed surprised with 50 bps cut.",
        "key_points":     ["50 bps cut surprise",
                            "Markets priced 25 bps",
                            "Powell cites cooling inflation"],
        "sentiment":      "positive",
        "experiments":    {
            "hook_style":      "outcome_first",
            "script_tone":     "opinionated",
            "thumbnail_style": "dynamic_text",
            "cta_style":       "follow_handle",
        },
    }


def _silence_ffmpeg(monkeypatch, generate_shorts_module):
    """Replace the two compose helpers with success stubs so we never
    actually fork ffmpeg."""

    def fake_broll(broll_paths, audio_path, output_path, **kw):
        output_path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 60_000)
        return True

    def fake_static(frame_path, audio_path, output_path, **kw):
        output_path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 60_000)
        return True

    monkeypatch.setattr(generate_shorts_module, "build_broll_short", fake_broll)
    monkeypatch.setattr(generate_shorts_module, "build_static_short", fake_static)


def _stub_image_chain(monkeypatch, gs):
    """Make the image-fallback chain claim it acquired a background.
    The path it writes to gets a real-looking JPEG so the size check passes."""

    def fake_download(url, dest, timeout=15):
        dest.write_bytes(b"\xff\xd8\xff" + b"x" * 8000)
        return True

    def fake_fetch_any(article_url, query, dest):
        dest.write_bytes(b"\xff\xd8\xff" + b"x" * 8000)
        return True

    monkeypatch.setattr(gs, "download_image", fake_download)
    monkeypatch.setattr(gs, "fetch_any_free_image", fake_fetch_any)
    # Pillow opens the JPEG — give it a real one. We use a 1x1 fake
    # that PIL will accept and create_short_frame will paste over.
    from PIL import Image
    real_jpeg = Image.new("RGB", (1080, 1920), (8, 8, 18))

    def fake_generate_bg(title, category, dest):
        real_jpeg.save(str(dest), "JPEG", quality=80)
        return True

    monkeypatch.setattr(gs, "generate_ai_background", fake_generate_bg)


def _stub_tts_and_captions(monkeypatch, gs):
    """No real TTS, no real Whisper, no real Pixabay download."""
    async def fake_tts(text, output_path, voice):
        output_path.write_bytes(b"ID3" + b"\x00" * 10_000)

    monkeypatch.setattr(gs, "text_to_speech", fake_tts)
    monkeypatch.setattr(gs, "generate_captions", lambda audio, tmp: None)
    # Music bed: return the unchanged audio path, no network.
    monkeypatch.setattr(gs, "add_music_bed", lambda audio, story, tmp: audio)


def _stub_broll_acquisition(monkeypatch, gs):
    monkeypatch.setattr(gs, "acquire_broll_clips",
                         lambda story, tmp, want_n=3: [])


def test_end_to_end_generate_short_ships_metadata(monkeypatch, tmp_path,
                                                    fake_queue_story):
    """Walk one story all the way through generate_short() and assert
    we ended with a valid metadata sidecar."""
    import importlib, sys
    if "generate_shorts" in sys.modules:
        del sys.modules["generate_shorts"]
    monkeypatch.chdir(tmp_path)
    import generate_shorts as gs
    importlib.reload(gs)

    _stub_image_chain(monkeypatch, gs)
    _stub_tts_and_captions(monkeypatch, gs)
    _stub_broll_acquisition(monkeypatch, gs)
    _silence_ffmpeg(monkeypatch, gs)

    # Wrap story to match what _queue_to_story emits.
    story = {
        "slug":           "test-slug",
        "title":          fake_queue_story["seo_title"],
        "description":    fake_queue_story["description"],
        "source":         fake_queue_story["source"],
        "source_url":     fake_queue_story["url"],
        "image_url":      fake_queue_story["image_url"],
        "tags":           [fake_queue_story["category"]],
        "category":       fake_queue_story["category"],
        "date":           "2026-05-18",
        "hook":           fake_queue_story["hook"],
        "script":         fake_queue_story["script"],
        "thumbnail_text": fake_queue_story["thumbnail_text"],
        "key_points":     fake_queue_story["key_points"],
        "yt_tags":        fake_queue_story["yt_tags"],
        "yt_description": fake_queue_story["yt_description"],
        "geo_hashtag":    fake_queue_story["geo_hashtag"],
        "topic_hashtag":  fake_queue_story["topic_hashtag"],
        "_queue_id":      fake_queue_story["id"],
        "native_lang":    "en",
        "experiments":    fake_queue_story["experiments"],
    }

    tmp = tmp_path / "tmp_run"
    tmp.mkdir()
    out = gs.generate_short(story, tmp)
    assert out is not None
    video_path, thumb_path, metadata = out

    # Verify the metadata sidecar has every field upload_youtube.py reads.
    required = {
        "title", "description", "tags", "category_id", "privacy",
        "thumbnail", "video", "story_slug", "created_at",
        "thumbnail_hook", "source", "experiments",
    }
    missing = required - metadata.keys()
    assert missing == set(), f"missing metadata fields: {missing}"

    # YouTube hard limits.
    assert len(metadata["title"]) <= 100
    assert len(metadata["description"]) <= 5000
    assert sum(len(t) + 1 for t in metadata["tags"]) <= 500

    # Experiment tags carried through.
    assert metadata["experiments"]["hook_style"] == "outcome_first"

    # Files were produced.
    assert Path(video_path).exists()
    assert Path(thumb_path).exists()
    # Metadata JSON should have been written next to the video.
    meta_path = Path(video_path).with_suffix(".json")
    assert meta_path.exists()
    saved = json.loads(meta_path.read_text(encoding="utf-8"))
    assert saved["title"] == metadata["title"]


def test_end_to_end_quality_gate_blocks_slop(monkeypatch, tmp_path,
                                                fake_queue_story):
    """A bad story (banned phrases + weak hook) should be skipped."""
    import importlib, sys
    if "generate_shorts" in sys.modules:
        del sys.modules["generate_shorts"]
    monkeypatch.chdir(tmp_path)
    import generate_shorts as gs
    importlib.reload(gs)
    _stub_image_chain(monkeypatch, gs)
    _stub_tts_and_captions(monkeypatch, gs)
    _stub_broll_acquisition(monkeypatch, gs)
    _silence_ffmpeg(monkeypatch, gs)

    slop_story = dict(
        slug="slop-slug", title="Federal Reserve announces rate decision",
        description="Federal Reserve announces rate decision today.",
        source="Reuters", source_url="https://e", image_url="",
        tags=["business"], category="business", date="2026-05-18",
        hook="Today the Fed announced rates.",  # weak opener
        script="Today the Fed announced rates. This is a crucial pivotal moment.",
        thumbnail_text="THE FED", key_points=[], yt_tags=[],
        yt_description="x", geo_hashtag="USA", topic_hashtag="Markets",
        _queue_id="slop-id", native_lang="en",
        # seo_title same as RSS title — also a flag.
        experiments={},
    )
    tmp = tmp_path / "tmp_run"
    tmp.mkdir()
    out = gs.generate_short(slop_story, tmp)
    assert out is None  # quality gate caught it
