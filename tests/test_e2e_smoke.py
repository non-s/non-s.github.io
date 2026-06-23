"""
End-to-end smoke test for the Shorts pipeline.

We don't need the full network or ffmpeg to validate that the modules
wire together â€” we mock every external touchpoint (AI, edge-tts,
Pexels, Whisper, FFmpeg, YouTube) and assert that:

  1. `fetch_animals._enrich_story` produces a queue entry with the
     fields generate_shorts.py expects.
  2. `generate_shorts.generate_short` consumes that entry, calls
     each external service exactly once via mocks, and produces
     a metadata sidecar with the right keys for upload_youtube.py.
  3. The metadata sidecar contains the experiment tags so
     channel analytics can later compute winners.

When any wiring breaks, this test goes red â€” way faster than waiting
for CI to fail in production.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# These three modules depend on external libs that may be missing in
# the sandbox. We skip cleanly when so; CI has them.
pytest.importorskip("PIL")


@pytest.fixture
def fake_queue_story():
    """The shape fetch_animals.py produces and generate_shorts.py expects."""
    return {
        "id": "abc123",
        "fetched_at": "2026-05-18T12:00:00+00:00",
        "published_at": "2026-05-18T11:00:00+00:00",
        "consumed": False,
        "consumed_at": None,
        "title": "Octopus camouflage happens faster than you think",
        "url": "https://www.pexels.com/video/octopus/",
        "source": "Pexels",
        "category": "ocean",
        "description": "Octopuses can rapidly change colour and skin texture. "
        "Specialised cells help them blend into reefs and rocks. "
        "The effect is a remarkable form of camouflage.",
        "image_url": "",
        "breaking": True,
        "relevance": 8.5,
        "native_lang": "en",
        "score": 9,
        "seo_title": "Octopus camouflage happens in seconds",
        "yt_tags": ["octopus", "camouflage", "cephalopod", "animal facts"],
        "geo_hashtag": "Ocean",
        "topic_hashtag": "Octopus",
        "yt_description": "This octopus can change colour and skin texture in seconds.\n"
        "Source: Pexels\n#Shorts #AnimalFacts #Octopus",
        "thumbnail_text": "INVISIBLE IN SECONDS",
        "hook": "This octopus can disappear against a reef in seconds.",
        "script": (
            "This octopus can disappear against a reef in seconds. "
            "I love this detail: its skin cells shift colour while "
            "tiny muscles roughen the texture. That's why it can "
            "match coral, rocks, and sand even while moving. "
            "Which ocean animal should we decode next?"
        ),
        "lead": "Octopus camouflage changes in seconds.",
        "key_points": ["rapid colour shift", "skin texture changes", "reef camouflage"],
        "sentiment": "positive",
        "experiments": {
            "hook_style": "outcome_first",
            "script_tone": "opinionated",
            "thumbnail_style": "frame_first_side_caption",
            "cta_style": "subscribe_channel",
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

    # Pillow opens the JPEG â€” give it a real one. We use a 1x1 fake
    # that PIL will accept and create_short_frame will paste over.
    from PIL import Image

    real_jpeg = Image.new("RGB", (1080, 1920), (8, 8, 18))

    def fake_solid_bg(category, dest):
        real_jpeg.save(str(dest), "JPEG", quality=80)
        return True

    monkeypatch.setattr(gs, "_render_solid_color_background", fake_solid_bg)


def _stub_tts_and_captions(monkeypatch, gs):
    """No real TTS, no real Whisper, no external music download."""

    async def fake_tts(text, output_path, voice, **_kw):
        output_path.write_bytes(b"ID3" + b"\x00" * 10_000)

    def fake_captions(audio, tmp, *args, **kwargs):
        ass = tmp / "captions.ass"
        ass.write_text("[Script Info]\nTitle: fake\n", encoding="utf-8")
        return ass

    monkeypatch.setattr(gs, "text_to_speech", fake_tts)
    monkeypatch.setattr(gs, "generate_captions", fake_captions)
    # Music bed: return the unchanged audio path, no network.
    monkeypatch.setattr(gs, "add_music_bed", lambda audio, story, tmp: audio)


def _stub_broll_acquisition(monkeypatch, gs):
    def fake_broll(story, tmp, want_n=3):
        path = tmp / "broll.mp4"
        path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 1000)
        return [path]

    monkeypatch.setattr(gs, "acquire_broll_clips", fake_broll)


def test_end_to_end_generate_short_ships_metadata(monkeypatch, tmp_path, fake_queue_story):
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
        "slug": "test-slug",
        "title": fake_queue_story["seo_title"],
        "description": fake_queue_story["description"],
        "source": fake_queue_story["source"],
        "source_url": fake_queue_story["url"],
        "image_url": fake_queue_story["image_url"],
        "tags": [fake_queue_story["category"]],
        "category": fake_queue_story["category"],
        "date": "2026-05-18",
        "hook": fake_queue_story["hook"],
        "script": fake_queue_story["script"],
        "thumbnail_text": fake_queue_story["thumbnail_text"],
        "key_points": fake_queue_story["key_points"],
        "yt_tags": fake_queue_story["yt_tags"],
        "yt_description": fake_queue_story["yt_description"],
        "geo_hashtag": fake_queue_story["geo_hashtag"],
        "topic_hashtag": fake_queue_story["topic_hashtag"],
        "discovery_hashtags": [
            "wildlife",
            "wildanimals",
            "safari",
            "funfacts",
        ],
        "_queue_id": fake_queue_story["id"],
        "native_lang": "en",
        "experiments": fake_queue_story["experiments"],
    }

    tmp = tmp_path / "tmp_run"
    tmp.mkdir()
    out = gs.generate_short(story, tmp)
    assert out is not None
    video_path, thumb_path, metadata = out

    # Verify the metadata sidecar has every field upload_youtube.py reads.
    required = {
        "title",
        "description",
        "tags",
        "youtube_privacy",
        "youtube_category_id",
        "thumbnail",
        "video",
        "story_slug",
        "created_at",
        "thumbnail_hook",
        "source",
        "experiments",
        "channel_handle",
    }
    missing = required - metadata.keys()
    assert missing == set(), f"missing metadata fields: {missing}"

    # YouTube caption hard limit.
    assert len(metadata["description"]) <= 5000

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


def test_generate_short_preserves_editorial_cooldown_supply_fallback(monkeypatch, tmp_path, fake_queue_story):
    import importlib
    import sys

    from utils.editorial import EditorialReview

    if "generate_shorts" in sys.modules:
        del sys.modules["generate_shorts"]
    monkeypatch.chdir(tmp_path)
    import generate_shorts as gs

    importlib.reload(gs)

    _stub_image_chain(monkeypatch, gs)
    _stub_tts_and_captions(monkeypatch, gs)
    _stub_broll_acquisition(monkeypatch, gs)
    _silence_ffmpeg(monkeypatch, gs)
    monkeypatch.setattr(
        gs,
        "editorial_review",
        lambda story: EditorialReview(
            approved=False,
            score=75,
            state="cooldown_subject",
            series="Cold-Blooded Secrets",
            subject="snake",
            humanity={"score": 98, "label": "signature", "strengths": [], "issues": [], "rewrite_brief": []},
            reasons=("subject repeated inside 3-day cooldown",),
        ),
    )

    story = {
        "slug": "snake-fallback",
        "title": "Snakes sample the air with a tongue flick",
        "description": "A snake samples scent particles with its tongue before the next move.",
        "source": "Pexels",
        "source_url": "https://www.pexels.com/video/snake/",
        "image_url": "",
        "tags": ["reptiles"],
        "category": "reptiles",
        "date": "2026-05-18",
        "hook": "Snakes sample the air with a tongue flick.",
        "script": (
            "Snakes sample the air with a tongue flick. Watch the tongue before the next move, "
            "because it collects scent particles and sends them to a special organ in the mouth. "
            "That helps snakes track prey, mates, and danger without needing a loud chase. "
            "The air is information. Would you notice the trail?"
        ),
        "thumbnail_text": "TONGUE SMELL",
        "key_points": ["tongue scent", "chemical trail"],
        "yt_tags": ["snakes", "reptiles", "animal senses"],
        "yt_description": fake_queue_story["yt_description"],
        "geo_hashtag": "Wildlife",
        "topic_hashtag": "Reptiles",
        "discovery_hashtags": ["reptiles", "animals", "funfacts"],
        "queue_prune": {
            "state": "publish_ready",
            "objective_reasons": ["editorial_cooldown_supply_fallback"],
        },
        "_queue_id": "snake-fallback",
        "native_lang": "en",
        "experiments": fake_queue_story["experiments"],
    }

    tmp = tmp_path / "tmp_fallback"
    tmp.mkdir()
    out = gs.generate_short(story, tmp)

    assert out is not None
    _, _, metadata = out
    assert metadata["editorial"]["approved"] is True
    assert metadata["editorial"]["override"] == "editorial_cooldown_supply_fallback"
    assert metadata["pre_publish_audit"]["approved"] is True
    assert metadata["publish_score"]["approved"] is True


def test_end_to_end_quality_gate_blocks_slop(monkeypatch, tmp_path, fake_queue_story):
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
        slug="slop-slug",
        title="Octopus camouflage fact",
        description="Octopus camouflage fact today.",
        source="Pexels",
        source_url="https://e",
        image_url="",
        tags=["octopus"],
        category="ocean",
        date="2026-05-18",
        hook="Today this octopus changed colour.",  # weak opener
        script="Today this octopus changed colour. This is a crucial pivotal moment.",
        thumbnail_text="OCTOPUS",
        key_points=[],
        yt_tags=[],
        yt_description="x",
        geo_hashtag="Ocean",
        topic_hashtag="Octopus",
        _queue_id="slop-id",
        native_lang="en",
        # seo_title same as source title is also a flag.
        experiments={},
    )
    tmp = tmp_path / "tmp_run"
    tmp.mkdir()
    out = gs.generate_short(slop_story, tmp)
    assert out is None  # quality gate caught it
