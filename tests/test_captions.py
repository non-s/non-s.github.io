"""Tests for utils/captions.py â€” pure logic, no live API."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils import captions
from utils.captions import Caption, group_words_into_phrases, write_ass


# â”€â”€ group_words_into_phrases â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _w(word: str, start: float, end: float) -> Caption:
    return Caption(word=word, start=start, end=end)


def test_groups_break_on_max_words():
    words = [_w(f"w{i}", i * 0.1, i * 0.1 + 0.08) for i in range(10)]
    phrases = group_words_into_phrases(words, max_words=3,
                                        max_gap_s=10, max_duration_s=10)
    # Each phrase has 3 words, plus one final shorter one.
    assert all(len(p.word.split()) <= 3 for p in phrases)
    assert sum(len(p.word.split()) for p in phrases) == 10


def test_groups_break_on_gap():
    # Two clusters separated by a 2-second gap.
    words = [_w("a", 0, 0.3), _w("b", 0.4, 0.7),
             _w("c", 3.0, 3.3), _w("d", 3.4, 3.7)]
    phrases = group_words_into_phrases(words, max_words=10,
                                        max_gap_s=0.6, max_duration_s=10)
    assert len(phrases) == 2
    assert phrases[0].word == "a b"
    assert phrases[1].word == "c d"


def test_groups_break_on_duration():
    # Words that span longer than max_duration_s should split.
    words = [_w(f"w{i}", i * 1.0, i * 1.0 + 0.5) for i in range(5)]
    phrases = group_words_into_phrases(words, max_words=10,
                                        max_gap_s=10, max_duration_s=2.0)
    assert len(phrases) >= 2


def test_groups_handles_empty():
    assert group_words_into_phrases([]) == []


# â”€â”€ write_ass â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_write_ass_creates_valid_file(tmp_path):
    caps = [_w("Hello world", 0.0, 1.2), _w("How are you", 1.5, 2.8)]
    out = tmp_path / "subs.ass"
    assert write_ass(caps, out)
    body = out.read_text(encoding="utf-8")
    assert "[Script Info]" in body
    assert "[V4+ Styles]" in body
    assert "[Events]" in body
    # Words are uppercased.
    assert "HELLO WORLD" in body
    assert "HOW ARE YOU" in body
    # Timing format `0:00:00.00`.
    assert "0:00:00.00" in body


def test_write_ass_escapes_curly_braces(tmp_path):
    caps = [_w("hello {world}", 0.0, 1.0)]
    out = tmp_path / "subs.ass"
    write_ass(caps, out)
    body = out.read_text(encoding="utf-8")
    # Curly braces become parens so libass doesn't treat them as overrides.
    assert "(WORLD)" in body or "(world)" in body.upper()
    assert "{" not in body.split("[Events]")[1]


def test_write_ass_empty_returns_false(tmp_path):
    out = tmp_path / "subs.ass"
    assert not write_ass([], out)


# â”€â”€ transcribe_groq â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_transcribe_groq_returns_none_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    fake = tmp_path / "a.mp3"
    fake.write_bytes(b"x" * 100)
    assert captions.transcribe_groq(fake) is None


def test_transcribe_groq_parses_word_timestamps(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    fake_audio = tmp_path / "a.mp3"
    fake_audio.write_bytes(b"x" * 100)
    payload = {
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.4},
            {"word": "world", "start": 0.5, "end": 0.9},
            {"word": "",      "start": 0.9, "end": 0.9},
        ]
    }
    resp = MagicMock(status_code=200)
    resp.json.return_value = payload
    with patch("utils.captions.requests.post", return_value=resp):
        out = captions.transcribe_groq(fake_audio)
    assert out is not None
    assert [c.word for c in out] == ["Hello", "world"]


def test_transcribe_groq_handles_non_200(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    fake_audio = tmp_path / "a.mp3"
    fake_audio.write_bytes(b"x" * 100)
    resp = MagicMock(status_code=429, text="rate limited")
    with patch("utils.captions.requests.post", return_value=resp):
        assert captions.transcribe_groq(fake_audio) is None


# â”€â”€ transcribe (unified) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_transcribe_prefers_groq_when_available(monkeypatch, tmp_path):
    fake_audio = tmp_path / "a.mp3"
    fake_audio.write_bytes(b"x" * 100)
    groq_result = [_w("hi", 0, 0.3)]
    with patch.object(captions, "transcribe_groq", return_value=groq_result) as g, \
         patch.object(captions, "transcribe_faster_whisper") as fw:
        out = captions.transcribe(fake_audio)
    assert out == groq_result
    g.assert_called_once()
    fw.assert_not_called()


def test_transcribe_falls_through_to_faster_whisper(monkeypatch, tmp_path):
    fake_audio = tmp_path / "a.mp3"
    fake_audio.write_bytes(b"x" * 100)
    fw_result = [_w("hi", 0, 0.3)]
    with patch.object(captions, "transcribe_groq", return_value=None):
        with patch.object(captions, "transcribe_faster_whisper",
                          return_value=fw_result) as fw:
            out = captions.transcribe(fake_audio)
    assert out == fw_result
    fw.assert_called_once()


def test_transcribe_returns_none_if_both_fail(tmp_path):
    fake_audio = tmp_path / "a.mp3"
    fake_audio.write_bytes(b"x" * 100)
    with patch.object(captions, "transcribe_groq", return_value=None):
        with patch.object(captions, "transcribe_faster_whisper", return_value=None):
            assert captions.transcribe(fake_audio) is None


def test_transcribe_returns_none_for_missing_audio(tmp_path):
    missing = tmp_path / "nope.mp3"
    assert captions.transcribe(missing) is None


def test_write_ass_default_margin_v_clears_shorts_ui(tmp_path):
    """YouTube's bottom UI band (caption preview + sound link + share
    rail) takes ~250 px; we keep margin_v â‰¥ 320 so captions land in
    the centre-safe zone, not under the UI."""
    import inspect
    sig = inspect.signature(write_ass)
    assert sig.parameters["margin_v"].default >= 320


# â”€â”€ language hint â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def test_whisper_language_defaults_to_en(monkeypatch):
    monkeypatch.delenv("LANGUAGE", raising=False)
    assert captions._whisper_language() == "en"


def test_whisper_language_maps_locale_to_base(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "pt-BR")
    assert captions._whisper_language() == "pt"
    monkeypatch.setenv("LANGUAGE", "es-MX")
    assert captions._whisper_language() == "es"
    monkeypatch.setenv("LANGUAGE", "fr-FR")
    assert captions._whisper_language() == "fr"


def test_whisper_language_falls_through_for_unknown(monkeypatch):
    """An unmapped LANGUAGE shouldn't poison the Whisper request â€” we
    return "" so the caller omits the hint and Whisper auto-detects."""
    monkeypatch.setenv("LANGUAGE", "zz-ZZ")
    assert captions._whisper_language() == ""


# â”€â”€ Groq 429 retry â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def test_transcribe_groq_retries_once_on_429(tmp_path, monkeypatch):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x" * 100)
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    monkeypatch.setattr(captions, "_GROQ_RETRY_DELAY_S", 0.0)

    call_count = {"n": 0}

    def _fake_post(*args, **kwargs):
        call_count["n"] += 1
        resp = MagicMock()
        if call_count["n"] == 1:
            resp.status_code = 429
            resp.text = "rate limited"
        else:
            resp.status_code = 200
            resp.json.return_value = {
                "words": [{"word": "hi", "start": 0.0, "end": 0.3}]
            }
        return resp

    monkeypatch.setattr(captions.requests, "post", _fake_post)
    out = captions.transcribe_groq(audio)
    assert out is not None
    assert call_count["n"] == 2  # first 429, then 200


def test_transcribe_groq_gives_up_after_one_retry(tmp_path, monkeypatch):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x" * 100)
    monkeypatch.setenv("GROQ_API_KEY", "fake")
    monkeypatch.setattr(captions, "_GROQ_RETRY_DELAY_S", 0.0)

    call_count = {"n": 0}

    def _fake_post(*args, **kwargs):
        call_count["n"] += 1
        resp = MagicMock()
        resp.status_code = 429
        resp.text = "rate limited"
        return resp

    monkeypatch.setattr(captions.requests, "post", _fake_post)
    out = captions.transcribe_groq(audio)
    assert out is None
    # Original + 1 retry = 2 calls total.
    assert call_count["n"] == 2

