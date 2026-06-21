from scripts import next_shorts
from scripts.backfill_done_markers import backfill_marker
from scripts.dry_run_publish import build_dry_run
from utils import rejected_queue as rejected_queue_module
from utils.channel_objective import cognitive_mechanism_cluster, objective_gate_for_story
from utils.editorial_guard import editorial_issues
from utils.local_rewriter import rescue_story
from utils.packaging import package_story
from utils.post24_review import build_review, classify_video
from utils.publish_schedule import recommend_schedule
from utils.publish_score import score_metadata, score_story
from utils.rejected_queue import load_rejections, record_rejection
from utils.rights_audit import audit_rights
from utils.sequence_factory import build_sequence_plan


def _strong_story(**overrides):
    story = {
        "id": "ducks-1",
        "title": "Mallard ducks fake injuries to pull predators away",
        "seo_title": "Mallard ducks fake injuries to pull predators away",
        "hook": "Mallard ducks fake injuries to protect their young.",
        "script": (
            "Mallard ducks fake injuries when danger gets too close. "
            "The limp pulls attention away from the nest, then the duck escapes "
            "once the threat follows. It is a simple trick with a clear payoff."
        ),
        "category": "birds",
        "story_format": "animal_intelligence",
        "score": 9,
    }
    story.update(overrides)
    return story


def test_score_story_approves_specific_winning_candidate():
    score = score_story(_strong_story())

    assert score["state"] == "publish_ready"
    assert score["approved"] is True
    assert score["score"] >= 72


def test_score_metadata_does_not_mask_pre_publish_audit_gate():
    score = score_metadata(
        _strong_story(
            has_captions=True,
            has_broll=True,
            pre_publish_audit={"approved": False, "score": 30, "reasons": ["diagnostic gate"]},
        )
    )

    assert score["state"] == "publish_ready"
    assert score["approved"] is True


def test_score_story_approves_borderline_visual_cue_candidate():
    score = score_story(
        _strong_story(
            id="horse-borderline",
            title="Horses point their ears toward what matters",
            seo_title="Horses point their ears toward what matters",
            hook="Horses show attention with their ears.",
            script=(
                "Horses show attention with their ears. Watch the ears before the body moves, "
                "because each ear can turn toward a sound or animal the horse is tracking. "
                "That small shift shows where attention is going before the next step. "
                "The ears are a radar dish, not decoration. Would you spot it?"
            ),
            thumbnail_text="EAR RADAR",
            category="farm",
            story_format="animal_intelligence",
            score=9,
        )
    )

    assert score["approved"] is True
    assert score["state"] == "publish_ready"
    assert score["opportunity"]["score"] >= 50
    assert score["opportunity"]["verdict"] == "rewrite"


def test_score_story_sends_repetitive_template_to_rewrite_or_reject():
    story = _strong_story(
        title="Cows have another signal hiding in plain sight",
        seo_title="Cows have another signal hiding in plain sight",
        hook="Cows have another signal hiding in plain sight.",
        script="Another signal hiding in plain sight. Another signal hiding in plain sight.",
        story_format="animal_memory",
    )

    score = score_story(story)

    assert score["approved"] is False
    assert score["state"] in {"rewrite", "reject"}
    assert score["phrase_risk"]["hits"]


def test_score_story_blocks_late_payoff_for_current_swipe_baseline():
    story = _strong_story(
        packaging={
            "swipe_risk": {"band": "low"},
            "preflight_inputs": {"payoff_time_s": 13},
        }
    )

    score = score_story(story)

    assert score["approved"] is False
    assert score["state"] in {"rewrite", "reject"}
    assert score["objective_gate"]["publish_blocking"] is True
    assert "payoff_too_late_for_current_swipe_baseline" in score["objective_gate"]["reasons"]


def test_objective_gate_lets_day_zero_bootstrap_observe_without_penalty():
    gate = objective_gate_for_story(
        _strong_story(),
        {
            "decision_confidence": {
                "confidence_score": 0.03,
                "sample_size": 1,
                "minimum_sample_size": 20,
            }
        },
    )

    assert gate["penalty"] == 0
    assert gate["publish_blocking"] is False
    assert "bootstrap_observe_before_scaling" in gate["reasons"]


def test_cognitive_mechanism_cluster_uses_whole_cue_words():
    story = _strong_story(
        title="Rivers carve bends by stealing from one bank",
        seo_title="Rivers carve bends by stealing from one bank",
        hook="Rivers move sideways while they flow.",
        script=(
            "Rivers move sideways while they flow. Watch the outside bank, "
            "because faster water cuts that side while sediment drops inside the bend."
        ),
        thumbnail_text="BANK SHIFT",
        category="rivers",
        story_format="earth_engine",
    )

    assert cognitive_mechanism_cluster(story) == ""


def test_rescue_story_rewrites_editorial_template_but_not_visual_mismatch():
    story = _strong_story(
        title="Cows have another signal hiding in plain sight",
        hook="Another signal hiding in plain sight.",
    )

    rescued, applied = rescue_story(story, ["repetitive_title_template"])
    unchanged, blocked = rescue_story(story, ["off_topic_visual"])

    assert applied is True
    assert rescued["local_rewrite"]["applied"] is True
    assert "hiding in plain sight" not in rescued["seo_title"].lower()
    assert "not random" not in rescued["script"].lower()
    assert "because" in rescued["script"].lower()
    assert "to use" not in rescued["title"].lower()
    assert blocked is False
    assert unchanged is story


def test_rescue_story_preserves_visible_cue_for_plant_touch_count():
    story = _strong_story(
        title="Plants count touches before snapping shut",
        seo_title="Plants count touches before snapping shut",
        hook="Plants can count touches before closing.",
        script=(
            "Plants can count touches before closing. Watch the trap hairs, because the plant waits "
            "for more than one touch before spending energy on a snap."
        ),
        thumbnail_text="TOUCH COUNT",
        category="plants",
        source_title="close up of the small plants in the ground",
        source_url="https://www.pexels.com/video/close-up-of-the-small-plants-in-the-ground-8745499/",
    )

    rescued, applied = rescue_story(story, ["missing_visible_cue", "subject_not_immediately_clear"])
    packaged = package_story(rescued)

    assert applied is True
    assert rescued["title"].startswith("Plants use trap hairs")
    assert "trap hairs" in rescued["title"].lower()
    assert rescued["thumbnail_text"] == "TRAP HAIRS"
    assert "missing_visible_cue" not in packaged["packaging"]["risks"]


def test_rescue_story_does_not_generate_to_rely_title():
    story = _strong_story(
        title="Lions rely on the ear position for a reason",
        seo_title="Lions rely on the ear position for a reason",
        hook="This movement changes what happens next",
        script=(
            "Lions rely on the ear position before the payoff. Watch the first movement, "
            "because the detail explains the behavior."
        ),
        thumbnail_text="LIONS EAR POSITION",
        category="wildlife",
        source_url="https://www.pexels.com/video/lion-walking/",
    )

    rescued, applied = rescue_story(story, ["hook_shape_weak"])

    assert applied is True
    assert "to rely" not in rescued["title"].lower()
    assert rescued["title"] == "Lions use dark ear marks to guide cubs"
    assert rescued["thumbnail_text"] == "EAR MARKS"


def test_rescue_story_uses_sequel_source_title_for_subject():
    story = _strong_story(
        id="sequel-ducklings",
        title="Farms rely on movement to survive",
        seo_title="Farms rely on movement to survive",
        category="farm",
        sequel_of={"title": "Ducklings know math before they can swim", "video_id": "abc"},
    )

    rescued, applied = rescue_story(story, ["title_shape_weak", "script_length_risk"])

    assert applied is True
    assert rescued["seo_title"].startswith("Ducklings")
    assert "farms" not in rescued["script"].lower()


def test_rescue_story_rewrites_generic_signal_cue_template():
    story = _strong_story(
        id="chicken-signal",
        title="Chickens remember the signal cue for a reason",
        seo_title="Chickens remember the signal cue for a reason",
        hook="Chickens remember the signal cue before the payoff.",
        script=(
            "Chickens remember the signal cue before the payoff. Watch the movement first, "
            "because that cue changes how they react."
        ),
        thumbnail_text="CHICKENS SIGNAL",
        category="farm",
        source_url="https://www.pexels.com/video/chicken-1/",
    )

    rescued, applied = rescue_story(story, ["generic_signal_cue"])

    assert applied is True
    assert "signal cue" not in rescued["title"].lower()
    assert "turn the detail into the clue" not in rescued["title"].lower()
    assert "reveal the next move through movement" not in rescued["title"].lower()


def test_rescue_story_replaces_generic_body_posture_with_animal_cue():
    story = _strong_story(
        id="penguin-body",
        title="Penguins rely on body posture to signal",
        seo_title="Penguins rely on body posture to signal",
        hook="Penguins rely on body posture.",
        script=(
            "Penguins rely on body posture. Watch body posture, because penguins use it "
            "to send a clear signal before the next move."
        ),
        thumbnail_text="PENGUINS BODY",
        category="birds",
        source_url="https://www.pexels.com/video/penguin-1/",
    )

    rescued, applied = rescue_story(story, ["generic_body_posture_template"])

    assert applied is True
    assert "body posture" not in rescued["title"].lower()
    assert rescued["title"] == "Penguins trap air bubbles under feathers"
    assert rescued["thumbnail_text"] == "AIR BUBBLES"


def test_rescue_story_replaces_false_face_memory_with_signal_memory():
    story = _strong_story(
        id="bear-face",
        title="Bears recognize faces through tail position",
        seo_title="Bears recognize faces through tail position",
        hook="Bears recognize familiar faces.",
        script=(
            "Bears recognize familiar faces. Watch tail position, because bears use it "
            "to recognize familiar faces faster."
        ),
        thumbnail_text="BEARS TAIL",
        category="wildlife",
        source_url="https://www.pexels.com/video/bear-1/",
    )

    rescued, applied = rescue_story(story, ["generic_false_face_memory"])

    assert applied is True
    assert "recognize faces through tail" not in rescued["title"].lower()
    assert "recognize signals through" not in rescued["title"].lower()
    assert rescued["title"] == "Bears smell food from miles away"
    assert rescued["thumbnail_text"] == "SCENT MAP"


def test_rescue_story_handles_singular_truncated_and_stitched_titles():
    singular, singular_applied = rescue_story(
        _strong_story(
            title="Snake use their body to follow",
            seo_title="Snake use their body to follow",
            category="reptiles",
        ),
        ["bad_singular_subject_verb"],
    )
    truncated, truncated_applied = rescue_story(
        _strong_story(
            title="Tigers never roar at their prey — here's",
            seo_title="Tigers never roar at their prey — here's",
            category="wildlife",
        ),
        ["truncated_heres_title"],
    )
    stitched, stitched_applied = rescue_story(
        _strong_story(
            title="Birds This black bird's ear tufts aren't ears at all",
            seo_title="Birds This black bird's ear tufts aren't ears at all",
            category="birds",
        ),
        ["stitched_category_title", "stitched_repeated_animal_title"],
    )

    assert singular_applied is True
    assert singular["title"].startswith("Snakes ")
    assert truncated_applied is True
    assert "here's" not in truncated["title"].lower()
    assert stitched_applied is True
    assert not stitched["title"].startswith("Birds This")


def test_rescue_story_repairs_non_animal_domain_grammar():
    geology, geology_applied = rescue_story(
        _strong_story(
            id="geology-1",
            title="Geologies read the moment from one rocks",
            seo_title="Geologies read the moment from one rocks",
            hook="Geologies reveal one visible signal",
            script=(
                "Geologies reveal one visible signal. Watch rocks, because geologies use it "
                "to send a clear signal before the next move."
            ),
            thumbnail_text="GEOLOGIES ROCKS",
            category="geology",
        ),
        ["bad_domain_plural", "awkward_uncountable_one_cue"],
    )
    earth, earth_applied = rescue_story(
        _strong_story(
            id="earth-1",
            title="Earth systems read the moment from one clouds",
            seo_title="Earth systems read the moment from one clouds",
            hook="Earth systems reveal one visible signal",
            script=(
                "Earth systems reveal one visible signal. Watch clouds, because earth systems use it "
                "to send a clear signal before the next move."
            ),
            thumbnail_text="EARTH CLOUDS",
            category="earth_from_space",
        ),
        ["awkward_uncountable_one_cue"],
    )
    forest, forest_applied = rescue_story(
        _strong_story(
            id="forest-1",
            title="Forests read the moment from one leaves",
            seo_title="Forests read the moment from one leaves",
            hook="Forests reveal one visible signal",
            script=(
                "Forests reveal one visible signal. Watch the leaves, because forests use it "
                "to send a clear signal before the next move."
            ),
            thumbnail_text="FORESTS LEAVES",
            category="forests",
            source_title="Foggy forest with leaves and canopy",
        ),
        ["awkward_uncountable_one_cue"],
    )

    assert geology_applied is True
    assert "Geologies" not in geology["title"]
    assert "one rocks" not in geology["title"].lower()
    assert "cliff becomes a timeline" in geology["script"].lower()
    assert earth_applied is True
    assert earth["title"] == "Storm clouds reveal a storm's heat engine"
    assert "storm" in earth["title"].lower()
    assert forest_applied is True
    assert forest["title"] == "Forests make cooler air under the canopy"
    assert forest["thumbnail_text"] == "COOL CANOPY"
    assert "one leaves" not in forest["script"].lower()
    assert "forests use it" not in forest["script"].lower()
    assert "cooling machine" in forest["script"].lower()


def test_rescue_story_uses_contextual_nature_duplicate_titles():
    geology = _strong_story(
        id="geology-slot-canyon",
        title="Rock layers store ancient environments in stripes",
        seo_title="Rock layers store ancient environments in stripes",
        hook="Rock layers are time stamps made of stone.",
        script=(
            "Rock layers are time stamps made of stone. Watch the stripe pattern, "
            "because each layer can mark a different setting: river mud, ocean floor, "
            "windblown sand, or volcanic ash. Stack enough layers and the cliff becomes "
            "a timeline. Which rock clue should we read next?"
        ),
        thumbnail_text="ROCK TIME",
        category="geology",
        source_title="Exploring a majestic slot canyon in Utah deserts",
        source_url="https://www.pexels.com/video/exploring-a-majestic-slot-canyon-in-utah-deserts-37526463/",
    )
    weather = _strong_story(
        id="cloud-timelapse",
        title="Storm clouds reveal a storm's heat engine",
        seo_title="Storm clouds reveal a storm's heat engine",
        hook="Storm clouds show where a storm is feeding.",
        script=(
            "Storm clouds show where a storm is feeding. Watch the spiral shape, "
            "because warm ocean air rises near the center and releases heat as clouds build. "
            "Rotation organizes that energy into bands. From above, the storm is not random; "
            "it is an engine. Which satellite clue next?"
        ),
        thumbnail_text="STORM ENGINE",
        category="earth_from_space",
        source_title="Dynamic timelapse of changing cloudy sky",
        source_url="https://www.pexels.com/video/dynamic-timelapse-of-changing-cloudy-sky-32571811/",
    )

    geology_rescued, geology_applied = rescue_story(geology, ["duplicate_title"])
    weather_rescued, weather_applied = rescue_story(weather, ["duplicate_title"])

    assert geology_applied is True
    assert geology_rescued["title"] == "Rock layers reveal flood paths carved into stone"
    assert "slot canyon" not in geology_rescued["title"].lower()
    assert not editorial_issues(geology_rescued)
    assert package_story(geology_rescued)["title"] == geology_rescued["title"]
    assert weather_applied is True
    assert weather_rescued["title"] == "Storm clouds show air layers changing over time"
    assert not editorial_issues(weather_rescued)
    assert package_story(weather_rescued)["title"] == weather_rescued["title"]


def test_rescue_story_keeps_elephant_seal_in_seal_lane():
    story = _strong_story(
        id="elephant-seal-arctic",
        title="Elephants cool blood through giant ears",
        seo_title="Elephants cool blood through giant ears",
        hook="Elephants cool blood through giant ears.",
        script=(
            "Elephants cool blood through giant ears. Watch the ear movement, "
            "because elephants use blood flow there to release heat."
        ),
        thumbnail_text="GIANT EARS",
        category="arctic",
        source_title="Elephant seals on coastal beach resting",
        source_url="https://www.pexels.com/video/elephant-seals-on-coastal-beach-resting-35629750/",
    )

    rescued, applied = rescue_story(story, ["copy_subject_mismatch", "script_subject_mismatch"])

    assert applied is True
    assert rescued["title"] == "Seals track fish trails with whiskers"
    assert "elephant" not in " ".join(
        str(rescued.get(key) or "").lower() for key in ("title", "hook", "script", "thumbnail_text")
    )
    assert not editorial_issues(rescued)
    assert package_story(rescued)["title"] == rescued["title"]


def test_rejected_queue_records_and_replaces_same_story_stage(tmp_path):
    path = tmp_path / "rejected_queue.json"
    story = {"id": "abc", "title": "Weak story"}

    record_rejection(story, ["generic_script_template"], path=path, stage="queue_quality")
    record_rejection(story, ["duplicate_script"], path=path, stage="queue_quality")

    items = load_rejections(path)
    assert len(items) == 1
    assert items[0]["reasons"] == ["duplicate_script"]


def test_rejected_queue_jsonl_default_format_records_deduped_items(tmp_path):
    path = tmp_path / "rejected_queue.jsonl"
    story = {"id": "abc", "title": "Weak story"}

    record_rejection(story, ["weak_packaging"], path=path, stage="youtube_brain")
    record_rejection(story, ["generic_packaging"], path=path, stage="youtube_brain")

    items = load_rejections(path)
    assert len(items) == 1
    assert items[0]["reasons"] == ["generic_packaging"]


def test_rejected_queue_records_rewrite_attempt_metadata(tmp_path):
    path = tmp_path / "rejected_queue.jsonl"
    story = {
        "id": "abc",
        "title": "Weak story",
        "_queue_quality_repair": {
            "attempted": True,
            "applied": False,
            "reasons": ["duplicate_title"],
        },
    }

    record_rejection(story, ["duplicate_title"], path=path, stage="queue_prune")

    items = load_rejections(path)
    assert items[0]["rewrite_attempted"] is True
    assert items[0]["rewrite_applied"] is False


def test_rejected_queue_records_copy_memory_keys(tmp_path):
    path = tmp_path / "rejected_queue.jsonl"
    story = {
        "id": "abc",
        "title": "Ducks fake injuries to protect their young",
        "script": "Ducks fake injuries to protect their young. Watch the wing position.",
        "thumbnail_text": "WING POSITION",
        "category": "farm",
    }

    record_rejection(story, ["duplicate_script"], path=path, stage="queue_prune")

    items = load_rejections(path)
    assert items[0]["script_key"] == "ducks fake injuries to protect their young watch the wing position"
    assert items[0]["angle_key"] == "ducks|fake|wing position|farm"


def test_rejected_queue_default_path_can_be_isolated(monkeypatch, tmp_path):
    path = tmp_path / "isolated_rejected_queue.jsonl"
    monkeypatch.setattr(rejected_queue_module, "REJECTED_QUEUE", path)

    record_rejection({"id": "abc", "title": "Weak story"}, ["weak_packaging"], stage="youtube_brain")

    items = load_rejections()
    assert len(items) == 1
    assert items[0]["story_id"] == "abc"
    assert path.exists()


def test_rights_audit_requires_known_source_license_and_url():
    approved = audit_rights(
        {
            "source": "Pexels",
            "source_license": "Pexels License",
            "source_url": "https://www.pexels.com/video/1/",
        }
    )
    rejected = audit_rights({"source": "mystery source"})

    assert approved["approved"] is True
    assert rejected["approved"] is False
    assert "unknown_source" in rejected["reasons"]
    assert "missing_source_url" in rejected["reasons"]


def test_rights_audit_rejects_retired_source_as_unknown_source():
    rejected = audit_rights(
        {
            "source": "Retired Video Source",
            "source_license": "https://creativecommons.org/publicdomain/mark/1.0/",
            "source_license_evidence": "creativecommons.org/publicdomain/mark",
            "source_url": "https://example.invalid/removed-source",
        }
    )

    assert rejected["approved"] is False
    assert "unknown_source" in rejected["reasons"]


def test_backfill_done_marker_preserves_upload_identity_fields():
    marker = {
        "video_id": "yt123",
        "uploaded_at": "2026-01-01T00:00:00Z",
        "url": "https://youtube.com/shorts/yt123",
        "title": "Mallard ducks fake injuries to protect young",
        "seo_title": "Mallard ducks fake injuries to protect young",
        "script": "Mallard ducks fake injuries. Watch the wing cue first because it pulls predators away.",
        "thumbnail_text": "WATCH THE WING",
        "category": "birds",
    }

    updated, changed = backfill_marker(marker)

    assert changed is True
    assert updated["video_id"] == marker["video_id"]
    assert updated["uploaded_at"] == marker["uploaded_at"]
    assert updated["url"] == marker["url"]
    assert updated["packaging"]
    assert updated["publish_score"]
    assert updated["youtube_brain"]
    assert updated["story_format"]
    assert updated["humanity"]
    assert updated["retention_surgery"]
    assert updated["studio_state"] == "legacy_backfilled"


def test_sequence_plan_generates_three_variants_per_winner():
    plan = build_sequence_plan(
        {
            "top_performers": [
                {
                    "video_id": "v1",
                    "title": "Mallard ducks fake injuries to protect young",
                    "category": "birds",
                    "views": 1400,
                    "view_pct": 66,
                    "growth_score": 220,
                }
            ]
        }
    )

    assert plan["source_winners"] == 1
    assert len(plan["variants"]) == 3
    assert {item["sequence_variant"] for item in plan["variants"]} == {
        "same_format_new_animal",
        "same_animal_new_behavior",
        "same_topic_stronger_hook",
    }


def test_sequence_plan_skips_malformed_winner_titles():
    plan = build_sequence_plan(
        {
            "top_performers": [
                {
                    "video_id": "bad",
                    "title": "Chickens have another signal hiding in plain sight",
                    "category": "farm",
                    "views": 1400,
                    "view_pct": 66,
                    "growth_score": 220,
                },
                {
                    "video_id": "good",
                    "title": "Mallard ducks fake injuries to protect young",
                    "category": "birds",
                    "views": 1400,
                    "view_pct": 66,
                    "growth_score": 220,
                },
            ]
        }
    )

    assert plan["source_winners"] == 1
    assert all((variant.get("remake_of") or {}).get("video_id") != "bad" for variant in plan["variants"])
    assert "hiding in plain sight" not in str(plan["variants"]).lower()


def test_post24_review_classifies_scale_rewrite_pause_and_watch():
    assert classify_video({"views": 1200, "view_pct": 70, "growth_score": 250}) == "scale"
    assert (
        classify_video({"title": "Lions use their ears to use", "views": 1200, "view_pct": 70, "growth_score": 250})
        == "repair_package"
    )
    assert (
        classify_video(
            {
                "title": "Baby goats love bottle feeding \u00e2\u20ac\u201d here's why \u00f0\u0178",
                "views": 1200,
                "view_pct": 70,
                "growth_score": 250,
            }
        )
        == "repair_package"
    )
    assert classify_video({"views": 1200, "view_pct": 61, "growth_score": 250}) == "rewrite_hook"
    assert classify_video({"views": 1000, "view_pct": 45, "growth_score": 120}) == "rewrite_hook"
    assert classify_video({"views": 200, "view_pct": 40, "growth_score": 20}) == "pause_topic"
    assert classify_video({"views": 700, "view_pct": 55, "growth_score": 100}) == "watch"

    review = build_review(
        {
            "top_performers": [
                {"video_id": "x", "title": "X", "views": 1200, "view_pct": 70, "growth_score": 250},
                {
                    "video_id": "bad",
                    "title": "Lions use their ears to use",
                    "views": 1200,
                    "view_pct": 70,
                    "growth_score": 250,
                },
            ]
        }
    )
    assert review["counts"]["scale"] == 1
    assert review["counts"]["repair_package"] == 1
    assert review["items"][1]["title_issues"] == ["robotic_use_loop"]
    assert "62" in review["rules"]["scale"]


def test_post24_review_suggests_title_repairs():
    review = build_review(
        {
            "top_performers": [
                {
                    "video_id": "bad",
                    "title": "Lions use their ears to use",
                    "category": "wildlife",
                    "views": 1200,
                    "view_pct": 70,
                    "growth_score": 250,
                },
                {
                    "video_id": "tiger",
                    "title": "Tigers never roar at their prey — here's",
                    "category": "wildlife",
                    "views": 1200,
                    "view_pct": 70,
                    "growth_score": 250,
                },
            ]
        }
    )

    row = review["items"][0]
    assert row["decision"] == "repair_package"
    assert row["suggested_titles"] == ["Lions use dark ear marks to guide cubs"]
    assert review["items"][1]["suggested_titles"] == ["Tigers stay silent before they strike"]


def test_dry_run_publish_uses_autonomy_priority_before_queue_score(monkeypatch):
    class ApprovedEditorialReview:
        approved = True
        score = 90
        state = "publish_now"
        series = "Ocean Mysteries"
        subject = "whale"
        reasons = ()

        def to_dict(self):
            return {
                "approved": self.approved,
                "score": self.score,
                "state": self.state,
                "series": self.series,
                "subject": self.subject,
                "humanity": {"score": 80},
                "reasons": [],
            }

    monkeypatch.setattr("utils.queue_pruner.editorial_review", lambda story: ApprovedEditorialReview())
    base = {
        "seo_title": "Whales use tail slaps to warn the group",
        "title": "Whales use tail slaps to warn the group",
        "hook": "Whales warn the group with one tail slap.",
        "script": (
            "Whales warn the group with one tail slap. Watch the white splash first, "
            "because that hit sends pressure through the water before danger gets close. "
            "The pod reacts faster than sound alone, and that is why the first splash "
            "matters. Would you spot it?"
        ),
        "thumbnail_text": "TAIL SLAP",
        "yt_tags": ["whales", "tail slap", "ocean", "nature", "science"],
        "source": "Pexels",
        "source_url": "https://www.pexels.com/video/whale-tail-slap-1/",
        "url": "https://www.pexels.com/video/whale-tail-slap-1/",
        "source_license": "Pexels License",
        "category": "ocean",
        "score": 10,
    }
    payload = build_dry_run(
        {
            "stories": [
                {**base, "id": "low", "autonomy": {"priority": 10, "lane": "fresh_experiment"}},
                {
                    **base,
                    "id": "high",
                    "source_url": "https://www.pexels.com/video/whale-tail-slap-2/",
                    "url": "https://www.pexels.com/video/whale-tail-slap-2/",
                    "autonomy": {"priority": 130, "lane": "proven_category"},
                },
            ]
        }
    )

    assert payload["would_publish"][0]["id"] == "high"
    assert payload["would_publish"][0]["autonomy_lane"] == "proven_category"
    assert payload["selection_rule"] == "autonomy_priority first, queue_score and publish_score as tie-breakers"


def test_dry_run_publish_excludes_ops_paused_category(monkeypatch):
    monkeypatch.setattr("scripts.dry_run_publish.paused_categories", lambda: {"wildlife": {"category": "wildlife"}})
    story = {
        **_strong_story(category="wildlife"),
        "queue_prune": {"state": "publish_ready", "score": 100},
        "publish_score": {"approved": True, "state": "publish_ready", "score": 95},
        "editorial": {"approved": True, "state": "publish_now"},
        "source": "Pexels",
        "source_url": "https://www.pexels.com/video/paused/",
        "source_license": "Pexels License",
    }

    payload = build_dry_run({"stories": [story]}, env={"OPS_GUARDIAN_ENFORCE": "1"})

    assert payload["eligible_count"] == 0


def test_dry_run_publish_excludes_agency_held_candidate(monkeypatch, tmp_path):
    gate = tmp_path / "agency_gate.json"
    gate.write_text(
        '{"held_items":[{"id":"held","reasons":["success_recovery_hook_required"]}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.dry_run_publish.AGENCY_GATE", gate)
    monkeypatch.setattr("scripts.dry_run_publish.prune_queue", lambda data: (data, [], {}))
    story = {
        **_strong_story(id="held", category="birds"),
        "queue_prune": {"state": "publish_ready", "score": 100},
        "publish_score": {"approved": True, "state": "publish_ready", "score": 95},
        "editorial": {"approved": True, "state": "publish_now"},
        "source": "Pexels",
        "source_url": "https://www.pexels.com/video/held/1/",
        "source_license": "Pexels License",
    }

    payload = build_dry_run({"stories": [story]})

    assert payload["eligible_count"] == 0
    assert payload["objective_reasons"]["agency_gate:success_recovery_hook_required"] == 1


def test_next_shorts_excludes_ops_paused_category(monkeypatch, tmp_path):
    import json

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "_data"
    data_dir.mkdir()
    (data_dir / "stories_queue.json").write_text(json.dumps({"stories": []}), encoding="utf-8")
    pruned = {
        "stories": [
            {
                "id": "paused",
                "seo_title": "Wildlife story",
                "title": "Wildlife story",
                "category": "wildlife",
                "queue_prune": {"state": "publish_ready", "score": 100},
                "editorial": {"approved": True, "state": "publish_now"},
            }
        ]
    }

    monkeypatch.setattr(next_shorts, "QUEUE", data_dir / "stories_queue.json")
    monkeypatch.setattr(next_shorts, "OUT", data_dir / "next_shorts.json")
    monkeypatch.setattr(next_shorts, "prune_queue", lambda data: (pruned, [], {"pending_after": 1}))
    monkeypatch.setattr(next_shorts, "paused_categories", lambda: {"wildlife": {"category": "wildlife"}})
    monkeypatch.setenv("OPS_GUARDIAN_ENFORCE", "1")

    assert next_shorts.main() == 0
    payload = json.loads((data_dir / "next_shorts.json").read_text(encoding="utf-8"))
    assert payload["items"] == []


def test_next_shorts_uses_pruned_queue_for_reporting(monkeypatch, tmp_path):
    import json

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "_data"
    data_dir.mkdir()
    (data_dir / "stories_queue.json").write_text(json.dumps({"stories": []}), encoding="utf-8")
    pruned = {
        "stories": [
            {
                "id": "ready",
                "seo_title": "Chickens keep their view steady while walking",
                "title": "Chickens keep their view steady while walking",
                "hook": "Chickens lock their view between steps.",
                "script": (
                    "Chickens lock their view between steps. Watch the eyes stay level while the body "
                    "steps forward, because chickens stabilize their view in tiny pauses. That helps "
                    "them judge distance and spot danger without the world blurring. Did you notice it?"
                ),
                "thumbnail_text": "STEADY EYES",
                "yt_tags": ["chickens", "animal facts"],
                "source": "Pexels",
                "source_url": "https://www.pexels.com/video/chicken-1/",
                "source_license": "Pexels License",
                "category": "farm",
                "queue_prune": {"state": "publish_ready", "score": 100},
                "editorial": {"approved": True, "state": "publish_now"},
                "autonomy": {"priority": 130},
                "score": 9,
            }
        ]
    }

    monkeypatch.setattr(next_shorts, "QUEUE", data_dir / "stories_queue.json")
    monkeypatch.setattr(next_shorts, "OUT", data_dir / "next_shorts.json")
    monkeypatch.setattr(next_shorts, "prune_queue", lambda data: (pruned, [], {"pending_after": 1}))
    monkeypatch.setattr(
        next_shorts, "score_story", lambda story: {"approved": True, "state": "publish_ready", "score": 99}
    )

    assert next_shorts.main() == 0
    payload = json.loads((data_dir / "next_shorts.json").read_text(encoding="utf-8"))
    assert payload["items"][0]["id"] == "ready"
    assert payload["items"][0]["autonomy_priority"] == 130
    assert payload["prune_summary"]["pending_after"] == 1
    assert payload["title_shape_mix"]["status"] == "healthy"


def test_next_shorts_preserves_clean_publish_ready_reserve(monkeypatch, tmp_path):
    import json

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "_data"
    data_dir.mkdir()
    (data_dir / "stories_queue.json").write_text(json.dumps({"stories": []}), encoding="utf-8")
    story = {
        "id": "reserve",
        "seo_title": "Chickens remember familiar faces in the flock",
        "title": "Chickens remember familiar faces in the flock",
        "hook": "Chickens can recognize familiar faces.",
        "script": (
            "Chickens can recognize familiar faces in the flock. Watch how quickly a bird reacts "
            "to a known neighbor, because chickens learn faces and remember who belongs nearby. "
            "That memory helps them keep order without starting over every morning."
        ),
        "thumbnail_text": "FACE MEMORY",
        "category": "farm",
        "queue_prune": {
            "state": "publish_ready",
            "score": 78,
            "objective_reasons": ["publish_ready_supply_reserve_fallback"],
        },
        "publish_score": {
            "approved": True,
            "state": "publish_ready",
            "score": 100,
            "reserve_override": {"reason": "publish_ready_supply_reserve_fallback"},
        },
        "editorial": {"approved": True, "state": "publish_now"},
        "youtube_brain": {"state": "publish_minded", "risks": []},
        "packaging": {"state": "magnetic", "risks": []},
        "autonomy": {"priority": 120},
    }

    monkeypatch.setattr(next_shorts, "QUEUE", data_dir / "stories_queue.json")
    monkeypatch.setattr(next_shorts, "OUT", data_dir / "next_shorts.json")
    monkeypatch.setattr(next_shorts, "prune_queue", lambda data: ({"stories": [story]}, [], {"pending_after": 1}))
    monkeypatch.setattr(next_shorts, "filter_candidates", lambda stories: (list(stories), []))
    monkeypatch.setattr(next_shorts, "paused_categories", lambda: {})
    monkeypatch.setattr(next_shorts, "ops_guardian_enforced", lambda: False)
    monkeypatch.setattr(
        next_shorts,
        "score_story",
        lambda story: {
            "approved": False,
            "state": "rewrite",
            "score": 91.9,
            "opportunity": {"reasons": ["weak_visual_surface", "low_opportunity_score"]},
        },
    )

    assert next_shorts.main() == 0
    payload = json.loads((data_dir / "next_shorts.json").read_text(encoding="utf-8"))

    assert payload["items"][0]["id"] == "reserve"
    assert payload["items"][0]["score"]["state"] == "publish_ready"
    assert payload["items"][0]["score"]["score"] == 100
    assert payload["items"][0]["score"]["reserve_override"]["reason"] == "publish_ready_supply_reserve_fallback"


def test_next_shorts_reports_repeated_title_shapes():
    rows = [
        {"title": "Bears recognize signals through tail position"},
        {"title": "Elephants recognize signals through ear position"},
        {"title": "Orangutans recognize signals through hand movement"},
        {"title": "Chickens recognize signals through head movement"},
        {"title": "Penguins slide faster because flippers steer"},
        {"title": "Sharks turn quietly before they strike"},
        {"title": "Owls map sound before they land"},
        {"title": "Ducks follow water ripples to food"},
        {"title": "Lions freeze when the wind shifts"},
        {"title": "Bees dance directions inside the hive"},
    ]

    mix = next_shorts.build_title_shape_mix(rows)

    assert mix["status"] == "watch"
    warning = next(item for item in mix["warnings"] if item["window"] == 10)
    assert warning["shape"] == "{subject} recognize signals through {cue}"
    assert warning["count"] == 4
    assert warning["action"] == "alternate title promises before publishing this block"
    assert mix["rewrite_candidates"] == [
        {
            "rank": 4,
            "id": "",
            "title": "Chickens recognize signals through head movement",
            "shape": "{subject} recognize signals through {cue}",
            "suggested_titles": [
                "Chickens keep their view steady while walking",
                "Chickens react differently when their heads move",
                "Chickens read the moment from one head movement",
            ],
            "window": 10,
            "action": "rewrite title with a different promise shape before publishing this cluster",
        }
    ]
    assert all(
        next_shorts.title_shape(title) != "{subject} recognize signals through {cue}"
        for title in mix["rewrite_candidates"][0]["suggested_titles"]
    )


def test_next_shorts_title_suggestions_use_natural_cue_language():
    suggestions = next_shorts.title_rewrite_suggestions("Horses recognize signals through ear position")
    movement_suggestions = next_shorts.title_rewrite_suggestions("Elephants recognize signals through ear movement")

    assert "Horses react differently when their ears shift" in suggestions
    assert "Elephants react differently when their ears move" in movement_suggestions
    assert all("one ear position" not in title for title in suggestions)
    assert all("through ear position" not in title for title in suggestions)


def test_next_shorts_title_suggestions_handle_short_plural_cues():
    suggestions = next_shorts.title_rewrite_suggestions("Bees rely on wings to signal")

    assert "Bees react differently when their wings move" in suggestions
    assert "Bees read the moment from one wing beat" in suggestions
    assert all("one wings" not in title for title in suggestions)


def test_publish_schedule_adapts_to_retention_health():
    low = recommend_schedule({"avg_view_pct": 45})
    mid = recommend_schedule({"avg_view_pct": 59})
    high = recommend_schedule({"avg_view_pct": 75})

    expected_slots = [f"{hour:02d}:00" for hour in range(24)]

    assert low["recommended_shorts_per_day"] == 24
    assert mid["recommended_shorts_per_day"] == 24
    assert mid["recommended_slots"] == expected_slots
    assert high["recommended_shorts_per_day"] == 24
    assert high["recommended_slots"] == expected_slots
    assert high["rolling_batch_size"] == 24
    assert high["queue_target_pending"] == 24
    assert high["reason"] == "operator_day_zero_hourly_publish_with_quality_and_quota_guards"
    assert len(high["recommended_slots"]) == len(low["recommended_slots"]) == 24
