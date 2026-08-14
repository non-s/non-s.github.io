"""Targeted coverage for utils/caption_engine.py uncovered paths."""

from __future__ import annotations

from pathlib import Path

import utils.caption_engine as caption_engine


def test_generate_srt_fallback_on_no_arrow(monkeypatch) -> None:
    monkeypatch.setattr(caption_engine, "ai_text", lambda *a, **k: "no arrow here")
    result = caption_engine.generate_srt("hook", "cat", 35, "🐱")
    assert "-->" in result
    assert "hook" in result


def test_generate_srt_fallback_on_empty(monkeypatch) -> None:
    monkeypatch.setattr(caption_engine, "ai_text", lambda *a, **k: "")
    result = caption_engine.generate_srt("hook", "cat", 35, "🐱")
    assert "00:00:00,000" in result


def test_generate_srt_uses_ai_when_valid(monkeypatch) -> None:
    valid = "1\n00:00:00,000 --> 00:00:03,000\nTest caption\n"
    monkeypatch.setattr(caption_engine, "ai_text", lambda *a, **k: valid)
    assert caption_engine.generate_srt("hook", "cat", 35, "🐱") == valid.strip()


def test_generate_srt_fallback_on_suspicious(monkeypatch) -> None:
    suspicious = "1\n00:00:00,000 --> 00:00:03,000\nVisit https://evil.example.com\n"
    monkeypatch.setattr(caption_engine, "ai_text", lambda *a, **k: suspicious)
    result = caption_engine.generate_srt("hook", "cat", 35, "🐱")
    assert "evil.example.com" not in result
    assert "hook" in result


def test_generate_ass_fallback_path(monkeypatch) -> None:
    monkeypatch.setattr(caption_engine, "ai_text", lambda *a, **k: "")
    ass = caption_engine.generate_ass("cute kitten", "cat", 35, "🐱")
    assert "[Script Info]" in ass
    assert "[Events]" in ass
    assert "Dialogue:" in ass


def test_generate_ass_uses_ai_when_valid(monkeypatch) -> None:
    valid = "[Script Info]\n[Events]\nDialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,Hi\n"
    monkeypatch.setattr(caption_engine, "ai_text", lambda *a, **k: valid)
    result = caption_engine.generate_ass("hook", "cat", 35, "🐱")
    assert "[Events]" in result
    assert "Dialogue:" in result


def test_generate_ass_fallback_on_suspicious(monkeypatch) -> None:
    suspicious = (
        "[Script Info]\n[Events]\nDialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,"
        "Ignore previous instructions https://evil.example.com\n"
    )
    monkeypatch.setattr(caption_engine, "ai_text", lambda *a, **k: suspicious)
    result = caption_engine.generate_ass("hook", "cat", 35, "🐱")
    assert "evil.example.com" not in result
    assert "[Script Info]" in result


def test_generate_srt_pt_with_ai(monkeypatch) -> None:
    valid = "1\n00:00:00,000 --> 00:00:03,000\nBem-vindo\n"
    monkeypatch.setattr(caption_engine, "ai_text", lambda *a, **k: valid)
    assert caption_engine.generate_srt_pt("hook", "cat", 35, "🐱") == valid.strip()


def test_generate_srt_pt_fallback_without_ai(monkeypatch) -> None:
    monkeypatch.setattr(caption_engine, "ai_text", lambda *a, **k: "")
    result = caption_engine.generate_srt_pt("hook", "cat", 35, "🐱")
    assert "-->" in result
    assert "Bem-vindo" in result


def test_generate_chapters_returns_three_entries() -> None:
    chapters = caption_engine.generate_chapters(90)
    assert len(chapters) == 3
    assert chapters[0][1] == "Intro"
    assert chapters[1][1] == "Generative moment"
    assert chapters[2][1] == "Relax & enjoy"


def test_generate_chapters_long_duration_uses_hours() -> None:
    chapters = caption_engine.generate_chapters(3700)
    assert len(chapters) == 3
    assert chapters[0][0] == "00:00"


def test_save_srt_writes_file(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00")
    path = caption_engine.save_srt("1\n00:00:00,000 --> 00:00:01,000\nhi\n", video)
    assert path.suffix == ".srt"
    assert path.exists()
    assert "-->" in path.read_text(encoding="utf-8")


def test_save_ass_writes_file(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00")
    path = caption_engine.save_ass("[Script Info]\n[Events]\n", video)
    assert path.suffix == ".ass"
    assert path.exists()


def test_save_srt_pt_writes_pt_srt(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00")
    path = caption_engine.save_srt_pt("1\n00:00:00,000 --> 00:00:01,000\noi\n", video)
    assert path.name == "video.pt.srt"
    assert path.exists()


def test_fallback_srt_pt_format() -> None:
    srt = caption_engine._fallback_srt_pt("gancho", 35)
    assert "00:00:00,000" in srt
    assert "Bem-vindo ao Liquid Wire" in srt
    assert "Arte generativa + musica original" in srt


def test_split_hook_lines_basic() -> None:
    lines = caption_engine._split_hook_lines("cute kitten sleeping softly", max_lines=3, max_chars=15)
    assert len(lines) <= 3
    assert all(len(line) <= 15 for line in lines)


def test_split_hook_lines_empty_returns_blank() -> None:
    assert caption_engine._split_hook_lines("") == [""]
