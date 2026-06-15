import pytest

from utils import editorial
from utils.queue_pruner import production_quality_issues, prune_queue, quality_issues


@pytest.fixture(autouse=True)
def no_recent_editorial_memory(monkeypatch):
    monkeypatch.setattr(editorial.channel_memory, "_iter_recent", lambda days: iter(()))
    monkeypatch.setattr(editorial.channel_memory, "recent_angle_repeat", lambda story, days: False)


def _story(idx="1", **overrides):
    story = {
        "id": f"story-{idx}",
        "title": "Mallard ducks fake injuries to pull predators away",
        "seo_title": "Mallard ducks fake injuries to pull predators away",
        "hook": "Mallard ducks fake injuries to protect their young.",
        "script": (
            "Mallard ducks fake injuries to protect their young. "
            "Watch the wing cue first, because the limp pulls predators away "
            "from the nest before the duck escapes."
        ),
        "thumbnail_text": "WATCH THE WING",
        "yt_tags": ["ducks", "animal behavior"],
        "category": "farm",
        "source": "Pexels",
        "source_license": "Pexels License",
        "source_url": f"https://www.pexels.com/video/{idx}/",
        "score": 9,
    }
    story.update(overrides)
    return story


def test_quality_issues_rejects_generic_template_and_duplicate_title():
    seen_titles = set()
    seen_angles = set()
    seen_sources = set()
    first = _story()
    duplicate = _story("2")
    generic = _story(
        "3",
        title="Cows have another signal hiding in plain sight",
        seo_title="Cows have another signal hiding in plain sight",
    )

    assert quality_issues(first, seen_titles=seen_titles, seen_angles=seen_angles, seen_sources=seen_sources) == []

    duplicate_issues = quality_issues(
        duplicate,
        seen_titles=seen_titles,
        seen_angles=seen_angles,
        seen_sources=seen_sources,
    )
    generic_issues = quality_issues(
        generic,
        seen_titles=seen_titles,
        seen_angles=seen_angles,
        seen_sources=seen_sources,
    )

    assert "duplicate_title" in duplicate_issues
    assert "generic_title_template" in generic_issues


def test_quality_issues_rejects_script_subject_mismatch():
    issues = quality_issues(
        _story(
            title="orangutan relaxing outdoors with vegetation",
            seo_title="Primates show the hand cue before they follow",
            script="Monkeys follow hand cues because the body signal tells the group where to move.",
            category="primates",
            source_url="https://www.pexels.com/video/orangutan-relaxing-outdoors-with-vegetation/",
        ),
        seen_titles=set(),
        seen_angles=set(),
        seen_sources=set(),
    )

    assert "script_subject_mismatch" in issues


def test_production_quality_blocks_copy_that_disagrees_with_visible_subject():
    story = _story(
        "bee-copy-mismatch",
        title="bee collecting pollen on yellow flowers",
        seo_title="Butterflies rely on wing movement to survive",
        hook="Butterflies reveal the wing flash before they move.",
        script="Butterflies flash their wings before they move across the flower.",
        thumbnail_text="WING FLASH",
        category="insects",
        source_url="https://www.pexels.com/video/bee-collecting-pollen-on-yellow-flowers/",
    )

    issues = production_quality_issues(story)

    assert "copy_subject_mismatch" in issues
    assert "script_subject_mismatch" in issues


def test_production_quality_uses_source_title_before_ai_title():
    story = _story(
        "source-title-cartoon",
        source="Pexels",
        source_title="Magoo Beats the Heat (1956)",
        title="Turtles carry a magnetic map home",
        seo_title="Turtles carry a magnetic map home",
        hook="Turtles show the magnetic map before the payoff.",
        script="Turtles can navigate with Earth's magnetic field and return toward important coasts.",
        category="ocean",
        source_url="https://www.pexels.com/video/magoo-beats-the-heat-1956/",
        source_description="Mr. Magoo hooks a turtle in an animated cartoon.",
    )

    assert "off_topic_visual" in production_quality_issues(story)


def test_prune_queue_keeps_strong_traceable_candidates_and_quarantines_rest():
    queue = {
        "stories": [
            _story("1"),
            _story(
                "2",
                seo_title="Penguins slide on their bellies to save energy",
                title="Penguins slide on their bellies to save energy",
                source_url="",
            ),
            _story(
                "3",
                seo_title="Why tigers flick their ears before charging",
                title="tiger walking through grass",
                script=(
                    "Tigers flick their ears before charging. Watch the ear cue first, "
                    "because that movement can signal where their focus is before they move."
                ),
                thumbnail_text="WATCH THE EARS",
                category="wildlife",
                source_url="https://www.pexels.com/video/tiger-walking-through-grass/",
            ),
        ]
    }

    pruned, rejected, summary = prune_queue(queue, max_pending=1)

    kept = [story for story in pruned["stories"] if not story.get("consumed")]
    assert len(kept) == 1
    assert kept[0]["queue_prune"]["state"] in {"publish_ready", "rewrite"}
    assert kept[0]["packaging"]
    assert kept[0]["youtube_brain"]
    assert "queue_repair" in kept[0]
    assert summary["pending_before"] == 3
    assert summary["pending_after"] == 1
    assert len(rejected) == 2
    assert any("missing_source_url" in item["reasons"] for item in rejected)
    assert any({"queue_pruned_low_priority", "queue_score_reject"} & set(item["reasons"]) for item in rejected)


def test_prune_queue_repairs_editorial_do_not_publish_candidates_when_possible():
    weak = _story(
        "weak",
        title="Animals have another amazing secret",
        seo_title="Animals have another amazing secret",
        hook="Animals are amazing.",
        script="Animals are amazing and interesting.",
        thumbnail_text="AMAZING SECRET TODAY",
        category="wildlife",
        source_url="https://www.pexels.com/video/lion-resting/",
    )

    pruned, rejected, summary = prune_queue({"stories": [weak]}, max_pending=10)

    kept = [story for story in pruned["stories"] if not story.get("consumed")]
    assert len(kept) == 1
    assert kept[0]["queue_repair"]["applied"] is True
    assert kept[0]["queue_prune"]["state"] in {"publish_ready", "rewrite"}
    assert summary["repaired"] == 1
    assert rejected == []


def test_prune_queue_repairs_publish_minded_brain_risks_before_ready():
    generic = _story(
        "generic-hook",
        title="Ducklings use numbers before you notice",
        seo_title="Ducklings use numbers before you notice",
        hook="This movement changes what happens next",
        script=(
            "Ducklings show the useful cue before the payoff. Watch the first movement, "
            "because the detail is easy to miss. One body cue explains the visible payoff."
        ),
        thumbnail_text="DUCKLINGS BODY CUE",
        source_url="https://www.pexels.com/video/duckling-swimming/",
    )

    pruned, rejected, summary = prune_queue({"stories": [generic]}, max_pending=10)

    kept = [story for story in pruned["stories"] if not story.get("consumed")]
    assert len(kept) == 1
    assert kept[0]["queue_repair"]["applied"] is True
    assert kept[0]["hook"] != "This movement changes what happens next"
    assert not (kept[0]["youtube_brain"].get("risks") or [])
    assert kept[0]["queue_prune"]["state"] == "publish_ready"
    assert summary["repaired"] == 1
    assert rejected == []


def test_prune_queue_keeps_editorial_cooldown_out_of_publish_ready(monkeypatch):
    class FakeEditorialReview:
        approved = False
        score = 61
        state = "cooldown_subject"
        series = "Tiny Worlds"
        subject = "bee"
        reasons = (
            "subject repeated inside 3-day cooldown",
            "editorial score 61 is below 62",
        )

        def to_dict(self):
            return {
                "approved": self.approved,
                "score": self.score,
                "state": self.state,
                "series": self.series,
                "subject": self.subject,
                "humanity": {"score": 72},
                "reasons": list(self.reasons),
            }

    monkeypatch.setattr("utils.queue_pruner.editorial_review", lambda story: FakeEditorialReview())
    monkeypatch.setattr(
        "utils.queue_pruner.score_story",
        lambda story, analytics_strategy=None: {
            "approved": True,
            "state": "publish_ready",
            "score": 95,
            "editorial_guard": {"approved": True, "issues": []},
        },
    )
    monkeypatch.setattr("utils.queue_pruner.creator_premortem", lambda story: {"state": "publish_minded", "risks": []})
    monkeypatch.setattr("utils.queue_pruner.audit_rights", lambda story: {"approved": True, "reasons": []})
    story = _story(
        "cooldown",
        title="Bees show the wing beat before the payoff",
        seo_title="Bees show the wing beat before the payoff",
        hook="Bees show the wing beat before the payoff.",
        script=(
            "Bees show the wing beat before the payoff. Watch the wing beat first, "
            "because the vibration changes how the nearby bees react."
        ),
        thumbnail_text="WING BEAT",
        category="insects",
        yt_tags=["bees", "wing beat", "insects"],
        source_url="https://www.pexels.com/video/bee-on-flower/",
    )

    pruned, rejected, summary = prune_queue({"stories": [story]}, max_pending=10)

    kept = [story for story in pruned["stories"] if not story.get("consumed")]
    assert len(kept) == 1
    assert kept[0]["queue_prune"]["state"] == "rewrite"
    assert kept[0]["editorial"]["approved"] is False
    assert "editor_in_chief:subject repeated inside 3-day cooldown" in kept[0]["queue_prune"]["objective_reasons"]
    assert summary["pending_after"] == 1
    assert rejected == []


def test_prune_queue_blocks_title_repeated_from_uploaded_history_when_rewrite_is_unavailable(monkeypatch):
    repeated = "Ducklings rely on wing position to survive"
    monkeypatch.setattr("utils.queue_pruner.published_title_keys", lambda: {repeated.lower()})
    monkeypatch.setattr("utils.queue_pruner.rescue_story", lambda story, issues: (story, False))
    story = _story(
        "published-duplicate",
        title=repeated,
        seo_title=repeated,
        hook="Ducklings rely on wing position.",
        script=(
            "Ducklings rely on wing position. Watch the wing angle, "
            "because ducklings use it to stay safe when the moment changes."
        ),
        thumbnail_text="WING ANGLE",
        source_url="https://www.pexels.com/video/duckling-swimming/",
    )

    pruned, rejected, summary = prune_queue({"stories": [story]}, max_pending=10)

    assert [item for item in pruned["stories"] if not item.get("consumed")] == []
    assert len(rejected) == 1
    assert "duplicate_title" in rejected[0]["reasons"]
    assert summary["rejected"] == 1


def test_prune_queue_caps_publish_ready_title_template_clusters(monkeypatch):
    def fake_quality_issues(*args, **kwargs):
        return []

    def fake_enriched_score(story, analytics_strategy=None):
        return {
            "story": story,
            "score": 91,
            "state": "publish_ready",
            "publish_score": {"approved": True, "state": "publish_ready", "score": 91},
            "youtube_brain": {"risks": []},
            "packaging": {},
            "rights_audit": {"approved": True, "reasons": []},
            "editorial_guard": {"approved": True, "issues": []},
            "repair": {"attempted": False, "applied": False, "reasons": []},
        }

    monkeypatch.setattr("utils.queue_pruner.quality_issues", fake_quality_issues)
    monkeypatch.setattr("utils.queue_pruner.enriched_score", fake_enriched_score)
    queue = {
        "stories": [
            _story(
                str(idx),
                title=f"Chickens read the moment from one head cue {idx}",
                seo_title=f"Chickens read the moment from one head cue {idx}",
            )
            for idx in range(4)
        ]
    }

    pruned, rejected, summary = prune_queue(queue, max_pending=10)

    kept = [story for story in pruned["stories"] if not story.get("consumed")]
    states = [story["queue_prune"]["state"] for story in kept]
    objective_reasons = [story["queue_prune"]["objective_reasons"] for story in kept]
    assert states.count("publish_ready") == 2
    assert states.count("rewrite") == 2
    assert any("template_cluster_limit:read_the_moment" in reasons for reasons in objective_reasons)
    assert summary["pending_after"] == 4
    assert rejected == []


def test_prune_queue_caps_publish_ready_mechanism_clusters(monkeypatch):
    def fake_quality_issues(*args, **kwargs):
        return []

    def fake_enriched_score(story, analytics_strategy=None):
        return {
            "story": story,
            "score": 93,
            "state": "publish_ready",
            "publish_score": {"approved": True, "state": "publish_ready", "score": 93, "objective_gate": {}},
            "youtube_brain": {"risks": []},
            "packaging": {},
            "rights_audit": {"approved": True, "reasons": []},
            "editorial_guard": {"approved": True, "issues": []},
            "repair": {"attempted": False, "applied": False, "reasons": []},
        }

    monkeypatch.setattr("utils.queue_pruner.quality_issues", fake_quality_issues)
    monkeypatch.setattr("utils.queue_pruner.enriched_score", fake_enriched_score)
    queue = {
        "stories": [
            _story(
                "fin-1",
                title="Sharks follow one fin cue before the payoff",
                seo_title="Sharks follow one fin cue before the payoff",
                hook="Sharks follow one fin cue before the payoff.",
                thumbnail_text="SHARKS FIN CUE",
                script="Sharks follow one fin cue before the payoff. Watch the fin cue first.",
            ),
            _story(
                "fin-2",
                title="Dolphins turn fin movement into a warning",
                seo_title="Dolphins turn fin movement into a warning",
                hook="Dolphins turn fin movement into a warning.",
                thumbnail_text="DOLPHINS FIN",
                script="Dolphins turn fin movement into a warning before the payoff.",
            ),
            _story(
                "fin-3",
                title="Whales show the fin signal before they turn",
                seo_title="Whales show the fin signal before they turn",
                hook="Whales show the fin signal before they turn.",
                thumbnail_text="WHALES FIN",
                script="Whales show the fin signal before they turn. Watch the fin cue.",
            ),
        ]
    }

    pruned, rejected, summary = prune_queue(queue, max_pending=10)

    kept = [story for story in pruned["stories"] if not story.get("consumed")]
    states = [story["queue_prune"]["state"] for story in kept]
    reasons = [story["queue_prune"]["objective_reasons"] for story in kept]
    assert states.count("publish_ready") == 2
    assert states.count("rewrite") == 1
    assert any("mechanism_cluster_limit:fin_signal" in item for item in reasons)
    assert summary["pending_after"] == 3
    assert rejected == []


def test_prune_queue_prefers_scale_ready_inside_mechanism_cluster(monkeypatch):
    def fake_quality_issues(*args, **kwargs):
        return []

    def fake_enriched_score(story, analytics_strategy=None):
        return {
            "story": story,
            "score": 93,
            "state": "publish_ready",
            "publish_score": {
                "approved": True,
                "state": "publish_ready",
                "score": 93,
                "objective_gate": story.get("objective_gate") or {},
            },
            "youtube_brain": {"risks": []},
            "packaging": {},
            "rights_audit": {"approved": True, "reasons": []},
            "editorial_guard": {"approved": True, "issues": []},
            "repair": {"attempted": False, "applied": False, "reasons": []},
        }

    monkeypatch.setattr("utils.queue_pruner.quality_issues", fake_quality_issues)
    monkeypatch.setattr("utils.queue_pruner.enriched_score", fake_enriched_score)
    queue = {
        "stories": [
            _story(
                "observe-1",
                title="Sharks follow one fin cue before the payoff",
                seo_title="Sharks follow one fin cue before the payoff",
                hook="Sharks follow one fin cue before the payoff.",
                thumbnail_text="SHARKS FIN CUE",
                script="Sharks follow one fin cue before the payoff. Watch the fin cue first.",
                objective_gate={"scale_ready": False, "confidence_score": 0.2},
            ),
            _story(
                "observe-2",
                title="Dolphins turn fin movement into a warning",
                seo_title="Dolphins turn fin movement into a warning",
                hook="Dolphins turn fin movement into a warning.",
                thumbnail_text="DOLPHINS FIN",
                script="Dolphins turn fin movement into a warning before the payoff.",
                objective_gate={"scale_ready": False, "confidence_score": 0.21},
            ),
            _story(
                "scale",
                title="Whales show the fin signal before they turn",
                seo_title="Whales show the fin signal before they turn",
                hook="Whales show the fin signal before they turn.",
                thumbnail_text="WHALES FIN",
                script="Whales show the fin signal before they turn. Watch the fin cue.",
                objective_gate={"scale_ready": True, "confidence_score": 0.8},
            ),
        ]
    }

    pruned, _rejected, _summary = prune_queue(queue, max_pending=10)

    by_id = {story["id"]: story["queue_prune"]["state"] for story in pruned["stories"]}
    assert by_id["story-scale"] == "publish_ready"
