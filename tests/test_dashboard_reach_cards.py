import importlib
import json
import sys
from pathlib import Path


def _dashboard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scripts = Path(__file__).resolve().parent.parent / "scripts"
    sys.path.insert(0, str(scripts))
    sys.modules.pop("build_dashboard", None)
    import build_dashboard

    return importlib.reload(build_dashboard)


def test_dashboard_renders_reach_and_operator_cards(tmp_path, monkeypatch):
    dashboard = _dashboard(tmp_path, monkeypatch)
    analytics = tmp_path / "_data" / "analytics"
    analytics.mkdir(parents=True)
    (analytics / "studio_reach_latest.json").write_text(
        json.dumps(
            {
                "summary": {
                    "rows": 1,
                    "stayed_to_watch_rate": 0.7,
                    "swipe_away_rate": 0.3,
                    "worst_swipe_videos": [
                        {
                            "video_id": "abc",
                            "title": "Octopus",
                            "metrics": {"stayed_to_watch_rate": 0.7, "swipe_away_rate": 0.3},
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "_data" / "trends").mkdir(parents=True)
    (tmp_path / "_data" / "trends" / "freshness_report.json").write_text(json.dumps({"coverage": 1}), encoding="utf-8")
    (tmp_path / "_data" / "opening_audit_report.json").write_text(json.dumps({"pass_rate": 1}), encoding="utf-8")
    (tmp_path / "_data" / "session_graph.json").write_text(json.dumps({"coverage": 1}), encoding="utf-8")
    (analytics / "api_quota_latest.json").write_text(
        json.dumps({"estimated_units": 1700, "guard": {"mode": "warn"}}), encoding="utf-8"
    )

    dashboard.main()
    body = (tmp_path / "_site" / "index.html").read_text(encoding="utf-8")

    assert "World-class growth cockpit" in body
    assert "Stayed to watch" in body
    assert "Shorts Reach: worst swipe risk" in body
    assert "Quota" in body
