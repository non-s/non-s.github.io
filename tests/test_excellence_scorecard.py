import json

from utils.excellence_scorecard import evaluate_scorecard


def test_ten_requires_every_criterion(tmp_path):
    spec = {"areas": {"live": {"criteria": ["handoff", "chaos"]}}}
    path = tmp_path / "scorecard.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    partial = evaluate_scorecard(path, {"live": {"handoff": True}})
    assert partial["areas"]["live"]["score"] == 5
    assert not partial["complete"]
    complete = evaluate_scorecard(path, {"live": {"handoff": True, "chaos": True}})
    assert complete["areas"]["live"]["score"] == 10
    assert complete["complete"]
