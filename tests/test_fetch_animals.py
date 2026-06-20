"""Tests for fetch_animals.py.

Cover the queue-shape contract with generate_shorts.py, the AI JSON
parsing, dedupe, and prune-on-age behaviour. The Pexels and AI
network calls are mocked — no test should hit the real internet.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import fetch_animals
from utils.broll import BrollClip


def _clip(
    url: str = "https://www.pexels.com/video/cat/123/",
    dl: str = "https://files.pexels.com/v/cat-1.mp4",
    title: str = "Cat playing in sunlight",
) -> BrollClip:
    return BrollClip(
        source="pexels",
        url=url,
        download_url=dl,
        width=1080,
        height=1920,
        duration_s=12.0,
        title=title,
        license="Pexels",
    )


_AI_OK_PAYLOAD = json.dumps(
    {
        "score": 8,
        "seo_title": "Why cats really purr — it is not just happiness",
        "yt_tags": ["cats", "cat facts", "purring", "animals", "wildlife"],
        "topic_hashtag": "Cats",
        "yt_description": "Cats purr for more than joy. They self-soothe and "
        "even heal their own bones at 25-150 Hz. Source: Pexels",
        "thumbnail_text": "WHY CATS PURR",
        "hook": "Cats purr to heal their own bones.",
        "script": "Cats purr to heal their own bones. The 25-150 Hz "
        "frequency promotes bone density. Big cats can purr "
        "too — sometimes. What's the strangest thing your "
        "cat does?",
        "sentiment": "positive",
    }
)


# ── AI parsing ────────────────────────────────────────────────────


def test_ai_enhance_animal_parses_valid_json(monkeypatch):
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: _AI_OK_PAYLOAD)
    out = fetch_animals._ai_enhance_animal("cat playing", "A clip of cats")
    assert out is not None
    assert out["seo_title"].startswith("Why cats really purr")
    assert out["hook"].startswith("Cats purr")
    assert out["topic_hashtag"] == "Cats"
    # _ai_enhance_animal no longer appends hashtags to yt_description —
    # generate_shorts.py owns the YouTube Shorts hashtag block.
    assert "#Shorts" not in out["yt_description"]
    assert "#Animals" not in out["yt_description"]
    assert out["sentiment"] == "positive"


def test_ai_enhance_includes_trend_context_in_prompt(monkeypatch):
    seen = {}
    dog_payload = dict(json.loads(_AI_OK_PAYLOAD))
    dog_payload["script"] = "Dogs can read human gestures and remember social cues from people."
    dog_payload["hook"] = "Dogs read people better than most animals."
    dog_payload["seo_title"] = "Why dogs read people so well"

    def fake_ai(prompt, *args, **kwargs):
        seen["prompt"] = prompt
        return json.dumps(dog_payload)

    monkeypatch.setattr(fetch_animals, "ai_text", fake_ai)
    out = fetch_animals._ai_enhance_animal(
        "dog running",
        "A clip of dogs",
        {
            "animal": "dog",
            "trend_score": 91,
            "terms": ["rescue", "viral"],
            "headline": "Viral dog rescue draws attention",
            "source_urls": ["https://example.com/dog"],
            "query": "dog animal rescue",
        },
    )
    assert out is not None
    assert out["trend_context"]["animal"] == "dog"
    assert "Viral dog rescue draws attention" in seen["prompt"]
    assert "not as a claim about the exact clip" in seen["prompt"]


def test_ai_enhance_returns_none_on_empty_response(monkeypatch):
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: "")
    assert fetch_animals._ai_enhance_animal("cat", "a cat clip") is None


def test_ai_enhance_returns_none_on_unparseable(monkeypatch):
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: "not json {{{")
    assert fetch_animals._ai_enhance_animal("cat", "a cat clip") is None


def test_ai_enhance_strips_code_fences(monkeypatch):
    wrapped = f"```json\n{_AI_OK_PAYLOAD}\n```"
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: wrapped)
    out = fetch_animals._ai_enhance_animal("cat", "a cat clip")
    assert out is not None and out["topic_hashtag"] == "Cats"


def test_ai_enhance_caps_tag_list_to_five(monkeypatch):
    bloat = dict(json.loads(_AI_OK_PAYLOAD))
    bloat["yt_tags"] = ["a", "b", "c", "d", "e", "f", "g", "h"]
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: json.dumps(bloat))
    out = fetch_animals._ai_enhance_animal("cat", "a cat clip")
    assert len(out["yt_tags"]) <= 5


def test_ai_enhance_rejects_script_about_different_visible_animal(monkeypatch):
    mismatch = dict(json.loads(_AI_OK_PAYLOAD))
    mismatch["script"] = "Jellyfish drift through the ocean without a brain."
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: json.dumps(mismatch))
    assert fetch_animals._ai_enhance_animal("Sea turtle swimming over coral", "ocean") is None


def test_copy_alignment_requires_explicit_visible_animal_in_viewer_copy():
    assert not fetch_animals._copy_matches_visible_subject(
        "amur leopard in snow",
        "Magnets make invisible fields visible",
        "Magnets can show a hidden force map.",
        "Watch the filings line up because each tiny piece becomes a small magnet.",
    )
    assert fetch_animals._copy_matches_visible_subject(
        "amur leopard in snow",
        "Leopards vanish against snowy rocks",
        "Leopards use stillness before the next move.",
        "Leopards use their coat and silence to hide before they move.",
    )


def test_ai_enhance_accepts_alias_for_visible_animal(monkeypatch):
    dog = dict(json.loads(_AI_OK_PAYLOAD))
    dog["seo_title"] = "Dogs read snow trails by smell"
    dog["title"] = dog["seo_title"]
    dog["hook"] = "Dogs track snow trails by smell."
    dog["script"] = "Dogs see blues and yellows better than reds and greens."
    dog["thumbnail_text"] = "DOG VISION"
    monkeypatch.setattr(fetch_animals, "ai_text", lambda *a, **kw: json.dumps(dog))
    assert fetch_animals._ai_enhance_animal("Husky running through snow", "dogs") is not None


def test_script_key_normalises_case_and_punctuation():
    assert fetch_animals._script_key("Cats purr. Really!") == fetch_animals._script_key("  CATS PURR -- really  ")


def test_subject_from_clip_prefers_descriptive_pexels_slug():
    clip = _clip(url="https://www.pexels.com/video/sea-turtle-over-coral-reef-12345/", title="Uploader Name")
    assert fetch_animals._subject_from_clip(clip, "ocean") == "sea turtle over coral reef"


def test_topic_rejects_explicit_animal_from_wrong_category():
    assert not fetch_animals._topic_accepts_subject(fetch_animals.ANIMAL_TOPICS["dogs"], "blue bird perched on branch")


def test_topic_rejects_visible_animal_in_nature_lane_without_reclassification():
    assert not fetch_animals._topic_accepts_subject(fetch_animals.ANIMAL_TOPICS["plants"], "bee on a flower")


def test_topic_rejects_title_that_only_mentions_animal_as_media_context():
    assert not fetch_animals._topic_accepts_subject(fetch_animals.ANIMAL_TOPICS["farm"], "Duck and Cover")
    assert not fetch_animals._topic_accepts_subject(
        fetch_animals.ANIMAL_TOPICS["ocean"],
        "Mr. Magoo hooks a turtle in an animated cartoon",
    )
    assert not fetch_animals._topic_accepts_subject(
        fetch_animals.ANIMAL_TOPICS["insects"],
        "Beetlejuice Promotes His Run For Senator",
    )
    assert not fetch_animals._topic_accepts_subject(
        fetch_animals.ANIMAL_TOPICS["arctic"],
        "76th reupload screen recording of an arctic fox",
    )


def test_topic_for_subject_reclassifies_bee_from_plants_to_insects():
    key, cfg = fetch_animals._topic_for_subject(
        "plants",
        fetch_animals.ANIMAL_TOPICS["plants"],
        "bee on a flower",
    )

    assert key == "insects"
    assert cfg is fetch_animals.ANIMAL_TOPICS["insects"]


def test_topic_for_subject_reclassifies_leaf_clip_from_insects_to_plants():
    key, cfg = fetch_animals._topic_for_subject(
        "insects",
        fetch_animals.ANIMAL_TOPICS["insects"],
        "a vine with a green stem and a leaf",
    )

    assert key == "plants"
    assert cfg is fetch_animals.ANIMAL_TOPICS["plants"]


def test_topic_accepts_visible_animal_from_category():
    assert fetch_animals._topic_accepts_subject(fetch_animals.ANIMAL_TOPICS["farm"], "baby goat in the grass")
    assert fetch_animals._topic_accepts_subject(fetch_animals.ANIMAL_TOPICS["farm"], "close up on chickens")


def test_topic_rejects_animal_costume_or_prop_subject():
    assert not fetch_animals._topic_accepts_subject(fetch_animals.ANIMAL_TOPICS["nocturnal"], "child in bat costume")
    assert not fetch_animals._topic_accepts_subject(fetch_animals.ANIMAL_TOPICS["cats"], "toy cat on a table")


# ── Story builder ─────────────────────────────────────────────────


def test_build_story_shape_matches_shared_queue_schema():
    """The downstream generate_shorts.py reads a fixed set of keys;
    pin them here so a future fetch_animals refactor can't silently
    drop one and break the rest of the pipeline."""
    ai_out = json.loads(_AI_OK_PAYLOAD)
    # Reproduce the post-parse normalisation _ai_enhance_animal does.
    ai_out["geo_hashtag"] = "Global"
    ai_out["lead"] = ai_out["script"][:400]
    ai_out["trend_context"] = {"animal": "cat", "trend_score": 77}
    # No hashtag injection anymore — generate_shorts owns that step.
    story = fetch_animals._build_story(
        clip_subject="cat playing",
        topic_key="cats",
        topic_cfg=fetch_animals.ANIMAL_TOPICS["cats"],
        pexels_clip=_clip(),
        ai_out=ai_out,
    )
    for required in (
        # Queue identity / state
        "id",
        "fetched_at",
        "published_at",
        "consumed",
        "consumed_at",
        # Original fields generate_shorts reads as fallbacks
        "title",
        "url",
        "source",
        "category",
        "description",
        "image_url",
        # Score chain
        "breaking",
        "relevance",
        "score",
        "safety_penalty",
        "native_lang",
        # AI-enriched fields generate_shorts reads directly
        "seo_title",
        "yt_tags",
        "geo_hashtag",
        "topic_hashtag",
        "yt_description",
        "thumbnail_text",
        "hook",
        "script",
        "lead",
        "sentiment",
        "trend_context",
        # YouTube Shorts discovery hashtag bundle (set from ANIMAL_TOPICS).
        "discovery_hashtags",
    ):
        assert required in story, f"missing field: {required}"
    # Each topic ships a non-empty discovery_hashtag list.
    assert "cats" in story["discovery_hashtags"]
    assert story["trend_context"]["animal"] == "cat"


def test_build_story_starts_unconsumed():
    ai_out = json.loads(_AI_OK_PAYLOAD)
    ai_out.setdefault("geo_hashtag", "Global")
    ai_out.setdefault("lead", ai_out["script"][:400])
    story = fetch_animals._build_story(
        "cat",
        "cats",
        fetch_animals.ANIMAL_TOPICS["cats"],
        _clip(),
        ai_out,
    )
    assert story["consumed"] is False
    assert story["consumed_at"] is None
    assert story["source"] == "Pexels"
    assert story["category"] == "cats"


def test_build_story_sanitizes_generated_source_focus_terms():
    ai_out = json.loads(_AI_OK_PAYLOAD)
    ai_out.setdefault("geo_hashtag", "Global")
    ai_out.setdefault("lead", ai_out["script"][:400])
    clip = _clip(
        url="https://www.pexels.com/video/solar-flare-12345/",
        dl="https://files.pexels.com/v/solar-flare.mp4",
        title=("NA" + "SA" + " solar flare"),
    )
    clip.source_metadata.update(
        {
            "creator": "NA" + "SA",
            "collection": "jsc-pao-video-collection, " + ("na" + "sa"),
            "description": ("NA" + "SA") + " public-domain solar footage.",
        }
    )
    story = fetch_animals._build_story(
        "solar flare",
        "space",
        fetch_animals.ANIMAL_TOPICS["space"],
        clip,
        ai_out,
    )
    combined = json.dumps(story, ensure_ascii=False).lower()
    assert "na" + "sa" not in combined
    assert "space agency" in combined


def test_build_story_scrubs_blocked_commons_terms():
    ai_out = json.loads(_AI_OK_PAYLOAD)
    ai_out.setdefault("geo_hashtag", "Global")
    ai_out.setdefault("lead", ai_out["script"][:400])
    story = fetch_animals._build_story(
        "cat",
        "cats",
        fetch_animals.ANIMAL_TOPICS["cats"],
        _clip(),
        ai_out,
        enrichment={"commons": {"artist": "NA" + "SA", "image_url": "https://example.test/cat.png"}},
    )
    assert story["commons_artist"] == ""
    assert story["commons_image_url"] == "https://example.test/cat.png"


def test_build_story_id_is_stable():
    """Same clip URL → same id. Used for dedupe across runs."""
    ai_out = json.loads(_AI_OK_PAYLOAD)
    ai_out.setdefault("geo_hashtag", "Global")
    ai_out.setdefault("lead", "")
    a = fetch_animals._build_story(
        "cat", "cats", fetch_animals.ANIMAL_TOPICS["cats"], _clip(url="https://x/y/1"), ai_out
    )
    b = fetch_animals._build_story(
        "cat", "cats", fetch_animals.ANIMAL_TOPICS["cats"], _clip(url="https://x/y/1"), ai_out
    )
    assert a["id"] == b["id"]


def test_build_story_id_differs_per_clip():
    ai_out = json.loads(_AI_OK_PAYLOAD)
    ai_out.setdefault("geo_hashtag", "Global")
    ai_out.setdefault("lead", "")
    a = fetch_animals._build_story(
        "cat", "cats", fetch_animals.ANIMAL_TOPICS["cats"], _clip(url="https://x/y/1"), ai_out
    )
    b = fetch_animals._build_story(
        "cat", "cats", fetch_animals.ANIMAL_TOPICS["cats"], _clip(url="https://x/y/2"), ai_out
    )
    assert a["id"] != b["id"]


# ── Prune ──────────────────────────────────────────────────────────


def test_prune_keeps_unconsumed_regardless_of_age():
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    queue = [
        {"id": "a", "consumed": False, "fetched_at": old},
        {"id": "b", "consumed": False, "fetched_at": old},
    ]
    out = fetch_animals._prune_queue(queue, keep_days=14)
    assert [s["id"] for s in out] == ["a", "b"]


def test_prune_drops_old_consumed():
    long_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    queue = [
        {"id": "old", "consumed": True, "consumed_at": long_ago},
        {"id": "new", "consumed": True, "consumed_at": recent},
        {"id": "pending", "consumed": False},
    ]
    out = fetch_animals._prune_queue(queue, keep_days=14)
    ids = {s["id"] for s in out}
    assert "old" not in ids
    assert "new" in ids
    assert "pending" in ids


# ── Query rotation ────────────────────────────────────────────────


def test_rotate_queries_returns_requested_count():
    queries = ["a", "b", "c", "d", "e"]
    out = fetch_animals._rotate_queries("cats", queries, take=2)
    assert len(out) == 2
    assert set(out).issubset(set(queries))


def test_rotate_queries_empty_input_returns_empty():
    assert fetch_animals._rotate_queries("cats", [], take=2) == []


def test_rotate_queries_is_deterministic_within_window():
    """Same topic + same 3-hour window → same picks."""
    qs = ["a", "b", "c", "d", "e", "f"]
    a = fetch_animals._rotate_queries("cats", qs, take=2)
    b = fetch_animals._rotate_queries("cats", qs, take=2)
    assert a == b


# ── Topic table ───────────────────────────────────────────────────


def test_topic_table_covers_expected_categories():
    """Pivot doc / channel branding refers to these 6 topics; if one
    drops out the channel suddenly stops covering, say, ocean life
    without anyone noticing in code review."""
    expected = {"cats", "dogs", "ocean", "wildlife", "birds", "farm"}
    assert expected.issubset(set(fetch_animals.ANIMAL_TOPICS))


def test_every_topic_has_queries_and_hashtag():
    for key, cfg in fetch_animals.ANIMAL_TOPICS.items():
        assert cfg.get("queries"), f"{key} has no queries"
        assert cfg.get("topic_hashtag"), f"{key} has no topic_hashtag"
        assert cfg.get("tags"), f"{key} has no tags"
        # YouTube Shorts discovery hashtags are required for captions.
        disc = cfg.get("discovery_hashtags") or []
        assert len(disc) >= 4, f"{key} discovery_hashtags too short"
        # Keep search tags lowercase and alphanumeric.
        for tag in disc:
            assert tag == tag.lower(), f"{key} hashtag {tag!r} not lowercase"
            assert tag.isalnum(), f"{key} hashtag {tag!r} not alphanumeric"


# ── Permanent published-clips dedup ledger ───────────────────────


def test_topic_table_expands_discovery_surface():
    expected = {"reptiles", "insects", "primates", "nocturnal", "arctic"}
    assert expected.issubset(set(fetch_animals.ANIMAL_TOPICS))


def test_topic_table_expands_science_surface():
    expected = {"space", "physics", "chemistry", "microscopy"}
    assert expected.issubset(set(fetch_animals.ANIMAL_TOPICS))


def test_science_topics_accept_matching_visible_subjects():
    assert fetch_animals._topic_accepts_subject(fetch_animals.ANIMAL_TOPICS["space"], "Solar flare on the sun")
    assert fetch_animals._topic_accepts_subject(
        fetch_animals.ANIMAL_TOPICS["physics"],
        "Pendulum experiment with a magnetic field",
    )
    assert fetch_animals._topic_accepts_subject(
        fetch_animals.ANIMAL_TOPICS["chemistry"],
        "Crystal growth chemical reaction",
    )
    assert fetch_animals._topic_accepts_subject(
        fetch_animals.ANIMAL_TOPICS["microscopy"],
        "Bacteria cells under a microscope",
    )
    assert not fetch_animals._topic_accepts_subject(fetch_animals.ANIMAL_TOPICS["chemistry"], "Solar flare on the sun")


def test_topic_fetch_plan_boosts_thin_hot_topics():
    queue = {
        "stories": [
            {"category": "cats", "consumed": False},
            {"category": "cats", "consumed": False},
            *({"category": "farm", "consumed": False} for _ in range(14)),
        ]
    }
    plan = fetch_animals._topic_fetch_plan(
        queue,
        {"category_weights": {"cats": 1.5, "farm": 0.75}},
        max_per_topic=4,
    )
    assert plan["cats"]["budget"] > 4
    assert plan["farm"]["budget"] < 4
    assert plan["cats"]["query_take"] >= 2


def test_topic_iteration_order_skips_ops_paused_categories():
    queue = {"stories": []}
    plan = fetch_animals._topic_fetch_plan(queue, max_per_topic=4)

    order = fetch_animals._topic_iteration_order(
        queue,
        plan,
        paused={"wildlife", "primates", "forests"},
    )

    assert "wildlife" not in order
    assert "primates" not in order
    assert "forests" not in order
    assert "cats" in order


def test_topic_iteration_order_recovers_empty_publish_ready_supply_with_visual_topics():
    queue = {
        "stories": [
            {
                "category": "discoveries",
                "consumed": False,
                "queue_prune": {"state": "rewrite"},
                "publish_score": {"approved": False, "state": "rewrite"},
            }
        ]
    }
    plan = fetch_animals._topic_fetch_plan(queue, max_per_topic=4)

    order = fetch_animals._topic_iteration_order(queue, plan)

    assert order.index("cats") < order.index("discoveries")
    assert order.index("dogs") < order.index("physics")
    assert order.index("birds") < order.index("plants")


def test_topic_iteration_order_keeps_table_order_when_publish_ready_supply_exists():
    queue = {
        "stories": [
            {
                "category": "cats",
                "consumed": False,
                "queue_prune": {"state": "publish_ready"},
                "publish_score": {"approved": True, "state": "publish_ready"},
            }
        ]
    }
    plan = fetch_animals._topic_fetch_plan(queue, max_per_topic=4)

    order = fetch_animals._topic_iteration_order(queue, plan, paused={"wildlife"})

    assert order[:4] == ["cats", "dogs", "ocean", "birds"]
    assert "wildlife" not in order


def test_topic_fetch_plan_boosts_viewer_requested_animals():
    queue = {"stories": [{"category": "ocean", "consumed": False} for _ in range(10)]}
    plain = fetch_animals._topic_fetch_plan(queue, {}, {}, max_per_topic=4)
    requested = fetch_animals._topic_fetch_plan(
        queue,
        {},
        {"requested_animals": ["shark"]},
        max_per_topic=4,
    )
    assert requested["ocean"]["budget"] > plain["ocean"]["budget"]


def test_topic_fetch_plan_boosts_trending_animals():
    queue = {"stories": []}
    trends = {
        "topics": [
            {
                "category": "ocean",
                "animal": "orca",
                "trend_score": 85,
                "query": "orca animal behavior",
            }
        ]
    }
    plan = fetch_animals._topic_fetch_plan(queue, {}, {}, trends, max_per_topic=4)
    assert plan["ocean"]["budget"] > 4
    assert plan["ocean"]["trend_queries"] == ["orca animal behavior"]


def test_backfill_per_topic_cap_spreads_short_queue_targets():
    assert fetch_animals._backfill_per_topic_cap(5, topic_count=10) == 1
    assert fetch_animals._backfill_per_topic_cap(24, topic_count=10) == 3
    assert fetch_animals._backfill_per_topic_cap(0, topic_count=10) is None


def test_load_published_clip_keys_returns_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_animals, "PUBLISHED_CLIPS_FILE", tmp_path / "missing.json")
    assert fetch_animals.load_published_clip_keys() == set()


def test_load_published_clip_keys_extracts_both_id_fields(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    f.write_text(
        json.dumps(
            {
                "clips": [
                    {"pexels_video_id": "111", "story_id": "abc123"},
                    {"pexels_video_id": "222"},  # only pexels id
                    {"story_id": "def456"},  # only story id
                    {"pexels_video_id": "", "story_id": ""},  # both empty — ignored
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(fetch_animals, "PUBLISHED_CLIPS_FILE", f)
    assert fetch_animals.load_published_clip_keys() == {
        "111",
        "222",
        "abc123",
        "def456",
    }


def test_load_published_clip_keys_tolerates_malformed_json(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    f.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(fetch_animals, "PUBLISHED_CLIPS_FILE", f)
    assert fetch_animals.load_published_clip_keys() == set()


def test_record_published_clip_appends_to_empty_ledger(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    monkeypatch.setattr(fetch_animals, "PUBLISHED_CLIPS_FILE", f)
    fetch_animals.record_published_clip(
        pexels_video_id="123",
        story_id="abc",
        pexels_url="https://pexels.com/v/123",
        platform_video_id="tt_xyz",
    )
    payload = json.loads(f.read_text(encoding="utf-8"))
    assert len(payload["clips"]) == 1
    assert payload["clips"][0]["pexels_video_id"] == "123"
    assert payload["clips"][0]["story_id"] == "abc"
    assert payload["clips"][0]["platform_video_id"] == "tt_xyz"
    assert payload["updated_at"] is not None


def test_record_published_clip_appends_to_existing_ledger(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    f.write_text(
        json.dumps(
            {
                "clips": [{"pexels_video_id": "111", "story_id": "old1"}],
                "updated_at": "2026-05-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(fetch_animals, "PUBLISHED_CLIPS_FILE", f)
    fetch_animals.record_published_clip(pexels_video_id="222", story_id="new2")
    payload = json.loads(f.read_text(encoding="utf-8"))
    assert len(payload["clips"]) == 2
    assert {c["pexels_video_id"] for c in payload["clips"]} == {"111", "222"}


def test_record_published_clip_noop_without_identifiers(tmp_path, monkeypatch):
    f = tmp_path / "p.json"
    monkeypatch.setattr(fetch_animals, "PUBLISHED_CLIPS_FILE", f)
    fetch_animals.record_published_clip()  # both ids empty
    assert not f.exists()


def test_record_then_load_round_trip(tmp_path, monkeypatch):
    """Permanent dedup contract: a clip recorded as published must
    appear in the load() set on the next call, regardless of any
    queue prune that happened in between."""
    f = tmp_path / "p.json"
    monkeypatch.setattr(fetch_animals, "PUBLISHED_CLIPS_FILE", f)
    fetch_animals.record_published_clip(pexels_video_id="999", story_id="zzz")
    keys = fetch_animals.load_published_clip_keys()
    assert "999" in keys
    assert "zzz" in keys


def test_pexels_id_from_clip_extracts_canonical_id():
    clip = BrollClip(
        source="pexels",
        url="https://www.pexels.com/video/cat/12345/",
        download_url="https://files.pexels.com/v/cat-1.mp4",
        width=1080,
        height=1920,
        duration_s=10,
    )
    assert fetch_animals._pexels_id_from_clip(clip) == "12345"


def test_pexels_id_from_clip_extracts_id_appended_to_slug():
    clip = BrollClip(
        source="pexels",
        url="https://www.pexels.com/video/sea-turtle-over-coral-reef-12345/",
        download_url="https://files.pexels.com/v/turtle.mp4",
        width=1080,
        height=1920,
        duration_s=10,
    )
    assert fetch_animals._pexels_id_from_clip(clip) == "12345"


def test_pexels_id_from_clip_handles_missing_url():
    clip = BrollClip(source="pexels", url="", download_url="x", width=1080, height=1920, duration_s=10)
    assert fetch_animals._pexels_id_from_clip(clip) == ""


def test_pexels_id_from_clip_rejects_non_pexels_id():
    clip = BrollClip(
        source="legacy",
        url="https://example.invalid/videos/octopus-12345/",
        download_url="https://cdn.example.invalid/v/octopus.mp4",
        width=1080,
        height=1920,
        duration_s=10,
    )
    assert fetch_animals._pexels_id_from_clip(clip) == ""
