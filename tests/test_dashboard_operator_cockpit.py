import importlib
import json
import sys
from pathlib import Path


def test_dashboard_renders_comment_and_session_actions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scripts = Path(__file__).resolve().parent.parent / "scripts"
    sys.path.insert(0, str(scripts))
    sys.modules.pop("build_dashboard", None)
    import build_dashboard

    dashboard = importlib.reload(build_dashboard)
    (tmp_path / "_data").mkdir()
    (tmp_path / "_data" / "comment_to_short_candidates.json").write_text(
        json.dumps({"candidates": [{"hook": "A viewer asked: can you do sharks?"}]}),
        encoding="utf-8",
    )
    (tmp_path / "_data" / "next_session_actions.json").write_text(
        json.dumps(
            {"items": [{"action": "operator_assist_pinned_comment", "video_id": "abc", "reason": "same series"}]}
        ),
        encoding="utf-8",
    )
    (tmp_path / "_data" / "fresh_upload_actions.json").write_text(
        json.dumps(
            {
                "counts": {"total": 1},
                "items": [
                    {
                        "priority": "high",
                        "lane": "measurement",
                        "video_id": "fresh",
                        "title": "Mushrooms release spores from hidden gills",
                        "url": "https://www.youtube.com/shorts/fresh",
                        "checkpoint_label": "1h",
                        "checkpoint_state": "due",
                        "recommended_action": "Pull fresh YouTube Studio analytics.",
                        "why": "First-hour checkpoint is due.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "_data" / "sequence_plan.json").write_text(
        json.dumps(
            {
                "fresh_upload_handoffs": 1,
                "variants": [
                    {
                        "sequence_variant": "fresh_upload_package_rescue",
                        "sequence_source": "fresh_upload_actions",
                        "title": "Mushrooms release spores from hidden gills",
                        "category": "fungi",
                        "fresh_upload_handoff": {"video_id": "fresh"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    dashboard.main()
    body = (tmp_path / "_site" / "index.html").read_text(encoding="utf-8")

    assert "Reply with a Short" in body
    assert "Next session actions" in body
    assert "Fresh upload action queue" in body
    assert "Fresh handoffs" in body
    assert "fresh upload" in body
    assert "sharks" in body
