import json

import scripts.prune_offbrand_broll as prune_offbrand_broll


def _write_clip(broll_dir, clip_id, is_ai_generated, title):
    (broll_dir / f"pixabay_{clip_id}.mp4").write_bytes(b"x")
    (broll_dir / f"pixabay_{clip_id}.json").write_text(json.dumps({"is_ai_generated": is_ai_generated, "title": title}))


def test_find_offbrand_clips_flags_non_ai_generated_only(tmp_path):
    _write_clip(tmp_path, "1", True, "anime")
    _write_clip(tmp_path, "2", False, "man")

    offbrand = prune_offbrand_broll.find_offbrand_clips(tmp_path)

    assert [p.stem for p in offbrand] == ["pixabay_2"]


def test_find_offbrand_clips_ignores_corrupt_sidecars(tmp_path):
    (tmp_path / "pixabay_3.mp4").write_bytes(b"x")
    (tmp_path / "pixabay_3.json").write_text("not json")

    assert prune_offbrand_broll.find_offbrand_clips(tmp_path) == []


def test_main_removes_offbrand_clips_and_keeps_good_ones(tmp_path, monkeypatch):
    monkeypatch.setattr(prune_offbrand_broll, "BROLL_DIR", tmp_path)
    _write_clip(tmp_path, "1", True, "anime")
    _write_clip(tmp_path, "2", False, "man")
    _write_clip(tmp_path, "3", False, "train")

    assert prune_offbrand_broll.main() == 0

    remaining = sorted(p.stem for p in tmp_path.glob("pixabay_*.mp4"))
    assert remaining == ["pixabay_1"]
    assert not (tmp_path / "pixabay_2.json").exists()
    assert not (tmp_path / "pixabay_3.json").exists()
