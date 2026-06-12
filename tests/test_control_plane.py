import json

from utils.control_plane import build_control_plane_report


def test_control_plane_report_flags_live_git_state_pressure(tmp_path):
    data = tmp_path / "_data"
    videos = tmp_path / "_videos"
    workflows = tmp_path / ".github" / "workflows"
    data.mkdir(parents=True)
    videos.mkdir()
    workflows.mkdir(parents=True)
    (data / "stories_queue.json").write_text(
        json.dumps({"stories": [{"id": str(i), "title": "Story"} for i in range(120)]}, indent=2),
        encoding="utf-8",
    )
    for idx in range(85):
        (data / f"state-{idx}.json").write_text("{}", encoding="utf-8")
    for idx in range(35):
        (videos / f"short-{idx}.done").write_text("done", encoding="utf-8")
    (workflows / "dashboard.yml").write_text("\n".join(["_data/stories_queue.json"] * 60), encoding="utf-8")

    report = build_control_plane_report(tmp_path)

    assert report["state"] in {"watch", "migration_needed"}
    assert report["metrics"]["data_state_files"] >= 86
    assert report["metrics"]["video_done_markers"] == 35
    assert report["metrics"]["state_path_refs"] == 60
    assert report["migration_lanes"][0]["lane"] == "queue_and_upload_intents"
