import json

from scripts.build_crosspost_pack import build_pack


def test_crosspost_pack_skips_malformed_uploaded_titles(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    (videos / "bad.done").write_text(
        json.dumps({
            "video_id": "bad",
            "title": "Lions use their ears to use",
            "url": "https://www.youtube.com/shorts/bad",
            "tags": ["lions"],
        }),
        encoding="utf-8",
    )
    (videos / "good.done").write_text(
        json.dumps({
            "video_id": "good",
            "title": "Dolphins recognize signals through call",
            "url": "https://www.youtube.com/shorts/good",
            "tags": ["dolphins"],
        }),
        encoding="utf-8",
    )

    report = build_pack(tmp_path)
    titles = [item["title"] for item in report["items"]]

    assert titles == ["Dolphins recognize signals through call"]
    assert (tmp_path / "_data" / "crosspost_pack.json").exists()


def test_crosspost_pack_orders_across_language_dirs_by_uploaded_at(tmp_path):
    videos = tmp_path / "_videos"
    videos_pt = tmp_path / "_videos_pt-BR"
    videos.mkdir()
    videos_pt.mkdir()
    (videos / "old.done").write_text(
        json.dumps({
            "video_id": "old",
            "title": "Octopus skin warning",
            "url": "https://www.youtube.com/shorts/old",
            "uploaded_at": "2026-06-01T00:00:00+00:00",
        }),
        encoding="utf-8",
    )
    (videos_pt / "new.done").write_text(
        json.dumps({
            "video_id": "new",
            "title": "Dolphins recognize signals through call",
            "url": "https://www.youtube.com/shorts/new",
            "uploaded_at": "2026-06-12T00:00:00+00:00",
        }),
        encoding="utf-8",
    )

    report = build_pack(tmp_path, limit=1)

    assert [item["video_id"] for item in report["items"]] == ["new"]
