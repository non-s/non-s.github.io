import json

from scripts.post_upload_session_ops import build_session_ops


def test_session_ops_recommends_related_video(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    first = {
        "video_id": "a",
        "title": "Octopus skin warning",
        "category": "ocean",
        "series": "Ocean Mysteries",
        "story_format": "mechanism_reveal",
    }
    second = {
        "video_id": "b",
        "title": "Octopus color signal",
        "category": "ocean",
        "series": "Ocean Mysteries",
        "story_format": "mechanism_reveal",
    }
    (videos / "a.done").write_text(json.dumps(first), encoding="utf-8")
    (videos / "b.done").write_text(json.dumps(second), encoding="utf-8")

    out = build_session_ops(tmp_path)

    assert out["related_video_recommendations"]
    assert (tmp_path / "_data" / "related_video_recommendations.json").exists()


def test_session_ops_survives_missing_inputs(tmp_path):
    out = build_session_ops(tmp_path)

    assert out["related_video_recommendations"] == []
    assert out["comment_reply_short_candidates"] == []


def test_session_ops_filters_malformed_sequel_opportunities(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    (videos / "bad.done").write_text(
        json.dumps(
            {
                "video_id": "bad",
                "title": "Lions use their ears to use",
                "category": "wildlife",
            }
        ),
        encoding="utf-8",
    )
    (videos / "good.done").write_text(
        json.dumps(
            {
                "video_id": "good",
                "title": "Dolphins recognize signals through call",
                "category": "ocean",
            }
        ),
        encoding="utf-8",
    )

    out = build_session_ops(tmp_path)
    titles = [item["title"] for item in out["sequel_opportunities"]]

    assert titles == ["Dolphins recognize signals through call"]


def test_session_ops_filters_malformed_related_targets(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    (videos / "source.done").write_text(
        json.dumps(
            {
                "video_id": "source",
                "title": "Chickens remember faces",
                "category": "birds",
                "series": "Birds",
            }
        ),
        encoding="utf-8",
    )
    (videos / "bad.done").write_text(
        json.dumps(
            {
                "video_id": "bad",
                "title": "Bird slides because of this tail",
                "category": "birds",
                "series": "Birds",
                "views": 10000,
            }
        ),
        encoding="utf-8",
    )
    (videos / "good.done").write_text(
        json.dumps(
            {
                "video_id": "good",
                "title": "Dolphins recognize signals through call",
                "category": "birds",
                "series": "Birds",
                "views": 10,
            }
        ),
        encoding="utf-8",
    )

    out = build_session_ops(tmp_path)
    targets = [(row.get("recommendation") or {}).get("title") for row in out["related_video_recommendations"]]

    assert "Bird slides because of this tail" not in targets
    assert "Dolphins recognize signals through call" in targets


def test_session_ops_skips_malformed_related_sources(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    (videos / "bad-source.done").write_text(
        json.dumps(
            {
                "video_id": "bad-source",
                "title": "Lions use their ears to use",
                "category": "wildlife",
                "series": "Wildlife",
            }
        ),
        encoding="utf-8",
    )
    (videos / "good-target.done").write_text(
        json.dumps(
            {
                "video_id": "good-target",
                "title": "Dolphins recognize signals through call",
                "category": "wildlife",
                "series": "Wildlife",
                "views": 100,
            }
        ),
        encoding="utf-8",
    )

    out = build_session_ops(tmp_path)
    sources = [row.get("source_title") for row in out["related_video_recommendations"]]

    assert "Lions use their ears to use" not in sources


def test_session_ops_uses_recent_clean_sources_when_newest_markers_are_malformed(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    (videos / "01-good-source.done").write_text(
        json.dumps(
            {
                "video_id": "good-source",
                "title": "Octopus skin warning",
                "category": "ocean",
                "series": "Ocean",
                "story_format": "mechanism_reveal",
            }
        ),
        encoding="utf-8",
    )
    (videos / "02-good-target.done").write_text(
        json.dumps(
            {
                "video_id": "good-target",
                "title": "Dolphins recognize signals through call",
                "category": "ocean",
                "series": "Ocean",
                "story_format": "mechanism_reveal",
                "views": 100,
            }
        ),
        encoding="utf-8",
    )
    for index in range(5):
        (videos / f"9{index}-bad.done").write_text(
            json.dumps(
                {
                    "video_id": f"bad-{index}",
                    "title": "Lions use their ears to use",
                    "category": "wildlife",
                    "series": "Wildlife",
                }
            ),
            encoding="utf-8",
        )

    out = build_session_ops(tmp_path)
    sources = [row.get("source_video_id") for row in out["related_video_recommendations"]]
    targets = [(row.get("recommendation") or {}).get("video_id") for row in out["related_video_recommendations"]]

    assert "good-source" in sources
    assert "good-target" in targets


def test_session_ops_orders_latest_markers_by_uploaded_at(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    (videos / "99-old.done").write_text(
        json.dumps(
            {
                "video_id": "old",
                "title": "Octopus skin warning",
                "category": "ocean",
                "series": "Ocean",
                "uploaded_at": "2026-06-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    for index in range(5):
        (videos / f"0{index}-new.done").write_text(
            json.dumps(
                {
                    "video_id": f"new-{index}",
                    "title": "Dolphins recognize signals through call",
                    "category": "ocean",
                    "series": "Ocean",
                    "uploaded_at": f"2026-06-12T0{index}:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

    out = build_session_ops(tmp_path)
    sequel_ids = [row.get("video_id") for row in out["sequel_opportunities"]]

    assert "old" not in sequel_ids
    assert sequel_ids == [f"new-{index}" for index in range(5)]


def test_session_ops_writes_fresh_upload_watchlist(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    (videos / "fresh.done").write_text(
        json.dumps(
            {
                "video_id": "fresh",
                "title": "Mushrooms release spores from hidden gills",
                "category": "fungi",
                "uploaded_at": "2999-01-01T00:00:00+00:00",
                "publish_score": {"opening_retention": {"score": 100, "state": "retention_ready"}},
            }
        ),
        encoding="utf-8",
    )

    out = build_session_ops(tmp_path)
    written = json.loads((tmp_path / "_data" / "fresh_upload_watchlist.json").read_text(encoding="utf-8"))

    assert out["fresh_upload_watchlist"]["items"]
    assert written["items"][0]["video_id"] == "fresh"
