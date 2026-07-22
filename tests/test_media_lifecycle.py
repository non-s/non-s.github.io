from utils.media_lifecycle import cleanup_meta_artifacts, cleanup_output_dirs, tracked_media_risks


def test_cleanup_meta_artifacts_deletes_uploaded_media_only(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    video = videos / "short-demo.mp4"
    thumb = videos / "short-demo_thumb.jpg"
    brand = tmp_path / "scripts" / "assets" / "brand.png"
    brand.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    thumb.write_bytes(b"thumb")
    brand.write_bytes(b"brand")

    report = cleanup_meta_artifacts(
        {
            "video": str(video),
            "thumbnail": str(thumb),
            "source_local_path": str(brand),
        },
        root=tmp_path,
    )

    assert not video.exists()
    assert not thumb.exists()
    assert brand.exists()
    assert report["deleted_bytes"] == len(b"video") + len(b"thumb")
    assert {row["reason"] for row in report["skipped"]} == {"outside_lifecycle_roots"}


def test_cleanup_output_dirs_keeps_pending_render_and_deletes_orphans(tmp_path):
    videos = tmp_path / "_videos"
    videos.mkdir()
    pending_video = videos / "short-pending.mp4"
    pending_thumb = videos / "short-pending_thumb.jpg"
    orphan_video = videos / "short-uploaded.mp4"
    pending_video.write_bytes(b"pending")
    pending_thumb.write_bytes(b"thumb")
    orphan_video.write_bytes(b"orphan")
    (videos / "short-pending.json").write_text("{}", encoding="utf-8")
    (videos / "short-uploaded.done").write_text("{}", encoding="utf-8")

    report = cleanup_output_dirs(root=tmp_path)

    assert pending_video.exists()
    assert pending_thumb.exists()
    assert not orphan_video.exists()
    assert [row["path"] for row in report["deleted"]] == ["_videos/short-uploaded.mp4"]
    assert {row["reason"] for row in report["skipped"]} == {"pending_metadata"}


def test_tracked_media_risks_flags_generated_media_only(tmp_path):
    report = tracked_media_risks(
        root=tmp_path,
        paths=[
            "assets/audio/posts/old.mp3",
            "_videos/short-demo_thumb.jpg",
            "scripts/assets/amberhours_profile.png",
            "utils/media_lifecycle.py",
        ],
    )

    assert report["ok"] is False
    assert [row["path"] for row in report["risks"]] == [
        "assets/audio/posts/old.mp3",
        "_videos/short-demo_thumb.jpg",
    ]
