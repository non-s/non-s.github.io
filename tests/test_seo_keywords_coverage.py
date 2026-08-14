"""Coverage for utils/seo_keywords.py - title/hashtag/description generation.

seo_keywords is the largest single coverage gap (22%). These tests cover the
title pattern, hashtag, description, and language-rotation helpers.
"""

from __future__ import annotations

import json
from pathlib import Path

import utils.seo_keywords as seo


def _isolate_data(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(seo, "data_dir", lambda: tmp_path)
    return tmp_path


def test_is_safe_title_history_entry_rejects_unsafe(tmp_path, monkeypatch) -> None:
    _isolate_data(tmp_path, monkeypatch)
    assert seo._is_safe_title_history_entry("Calm visuals") is True
    assert seo._is_safe_title_history_entry("anxiety relief music") is False
    assert seo._is_safe_title_history_entry("Deep Sleep healing") is False


def test_record_used_title_persists(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "used_titles.json"
    monkeypatch.setattr(seo, "_title_used_file", lambda: f)
    seo.record_used_title("Calm Wireframe Flow")
    seo.record_used_title("Calm Wireframe Flow")
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data == ["Calm Wireframe Flow"]


def test_record_used_title_skips_unsafe(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "used_titles.json"
    monkeypatch.setattr(seo, "_title_used_file", lambda: f)
    seo.record_used_title("anxiety relief for cats")
    assert not f.exists()


def test_record_used_title_skips_empty(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "used_titles.json"
    monkeypatch.setattr(seo, "_title_used_file", lambda: f)
    seo.record_used_title("")
    assert not f.exists()


def test_recent_titles_reads_and_filters(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "used_titles.json"
    monkeypatch.setattr(seo, "_title_used_file", lambda: f)
    f.write_text(json.dumps(["Calm visual", "stress relief bad", "Another title"]), encoding="utf-8")
    assert seo.recent_titles() == ["Calm visual", "Another title"]


def test_recent_titles_missing_returns_empty(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "used_titles.json"
    monkeypatch.setattr(seo, "_title_used_file", lambda: f)
    assert seo.recent_titles() == []


def test_title_similarity_identical() -> None:
    assert seo.title_similarity("calm wireframe flow", "calm wireframe flow") == 1.0


def test_title_similarity_no_overlap() -> None:
    assert seo.title_similarity("kittens playing", "geometry drift") == 0.0


def test_title_similarity_ignores_stop_words() -> None:
    assert seo.title_similarity("Liquid Wire art", "Liquid Wire music") == 0.0


def test_title_is_too_repetitive_true(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "used_titles.json"
    monkeypatch.setattr(seo, "_title_used_file", lambda: f)
    f.write_text(json.dumps(["calm wireframe flow drift"]), encoding="utf-8")
    assert seo.title_is_too_repetitive("calm wireframe flow drift") is True


def test_title_is_too_repetitive_false(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "used_titles.json"
    monkeypatch.setattr(seo, "_title_used_file", lambda: f)
    f.write_text(json.dumps(["calm wireframe flow drift"]), encoding="utf-8")
    assert seo.title_is_too_repetitive("completely different title") is False


def test_has_unsupported_outcome_claim() -> None:
    assert seo.has_unsupported_outcome_claim("anxiety relief") is True
    assert seo.has_unsupported_outcome_claim("deep sleep music") is True
    assert seo.has_unsupported_outcome_claim("healing music") is True
    assert seo.has_unsupported_outcome_claim("calm visuals") is False


def test_music_style_for_mood_known() -> None:
    assert seo.music_style_for_mood("relax") in seo.MUSIC_STYLE_BY_MOOD["relax"]
    assert seo.music_style_for_mood("focus") in seo.MUSIC_STYLE_BY_MOOD["focus"]
    assert seo.music_style_for_mood("sleep") in seo.MUSIC_STYLE_BY_MOOD["sleep"]


def test_music_style_for_mood_partial_match() -> None:
    result = seo.music_style_for_mood("deep_sleep")
    assert result in seo.MUSIC_STYLE_BY_MOOD["sleep"]


def test_music_style_for_mood_unknown_defaults_ambient() -> None:
    assert seo.music_style_for_mood("unknown_mood") == "ambient"
    assert seo.music_style_for_mood("") == "ambient"


def test_pick_title_pattern_returns_valid_pattern() -> None:
    import random

    random.seed(0)
    pattern = seo.pick_title_pattern("short")
    assert pattern in seo.active_channel.title_patterns["short"]


def test_pick_title_pattern_weighted(tmp_path, monkeypatch) -> None:
    import random

    random.seed(0)
    f = _isolate_data(tmp_path, monkeypatch) / "title_pattern_performance.json"
    monkeypatch.setattr(seo, "_title_pattern_performance_file", lambda: f)
    patterns = seo.active_channel.title_patterns["short"]
    weights = {p: 0.01 for p in patterns}
    weights[patterns[0]] = 100.0
    f.write_text(json.dumps(weights), encoding="utf-8")
    chosen = seo.pick_title_pattern("short")
    assert chosen == patterns[0]


def test_style_kind_detection() -> None:
    assert seo._style_kind("liquid wireframe flow") == "wireframe"
    assert seo._style_kind("organic coral growth") == "organic"
    assert seo._style_kind("crystal lattice geometric") == "geometric"
    assert seo._style_kind("nebula particle cloud") == "nebula"
    assert seo._style_kind("unknown style") == "wireframe"


def test_keywords_for_style_filters_other_kinds() -> None:
    kws = ["wireframe motion", "organic growth", "generative art", "geometric generative art"]
    filtered = seo._keywords_for_style(kws, "wireframe flow")
    assert "organic growth" not in filtered
    assert "geometric generative art" not in filtered
    assert "generative art" in filtered


def test_keywords_for_style_returns_all_when_all_filtered() -> None:
    kws = ["organic growth", "geometric shape"]
    filtered = seo._keywords_for_style(kws, "wireframe")
    assert filtered == kws


def test_format_trigger_fills_vars() -> None:
    assert seo._format_trigger("A {style} drift of {seconds}s", "wireframe", 30) == "A wireframe drift of 30s"


def test_format_pattern_with_seo_produces_title() -> None:
    import random

    random.seed(0)
    pattern = seo.active_channel.title_patterns["short"][0]
    title = seo._format_pattern_with_seo(pattern, "wireframe flow", "ambient", "✨", mood="relax", seconds=30)
    assert isinstance(title, str)
    assert len(title) > 0


def test_generate_title_with_pattern_returns_title_and_pattern() -> None:
    import random

    random.seed(0)
    title, pattern = seo.generate_title_with_pattern("wireframe flow", "relax", "ambient", "short", "✨", 30)
    assert isinstance(title, str)
    assert len(title) <= 100
    assert pattern in seo.active_channel.title_patterns["short"]


def test_generate_title_returns_string() -> None:
    import random

    random.seed(0)
    title = seo.generate_title("wireframe flow", "relax", "ambient", "short", "✨", 30)
    assert isinstance(title, str)
    assert len(title) <= 100


def test_generate_hashtags_brand_and_style() -> None:
    tags = seo.generate_hashtags("liquid wireframe", "relaxation", "short")
    assert "#LiquidWire" in tags
    assert "#Wireframe" in tags
    assert len(tags) <= seo._MAX_HASHTAGS


def test_generate_hashtags_organic_style() -> None:
    tags = seo.generate_hashtags("organic coral fluid", "focus", "short")
    assert "#OrganicArt" in tags


def test_generate_hashtags_geometric_style() -> None:
    tags = seo.generate_hashtags("crystal geometric", "focus", "short")
    assert "#GeometricArt" in tags


def test_generate_hashtags_nebula_style() -> None:
    tags = seo.generate_hashtags("nebula particle cloud", "relaxation", "short")
    assert "#NebulaArt" in tags


def test_generate_hashtags_unknown_style_falls_back() -> None:
    tags = seo.generate_hashtags("unknown visual", "relaxation", "short")
    assert "#LiquidWire" in tags


def test_generate_hashtags_mood_categories() -> None:
    assert "#FocusMusic" in seo.generate_hashtags("wireframe", "focus", "short")
    assert "#Electronic" in seo.generate_hashtags("wireframe", "energetic", "short")
    assert "#Ambient" in seo.generate_hashtags("wireframe", "sleep", "short")
    fallback = seo.generate_hashtags("wireframe", "unknown_cat", "short")
    assert len(fallback) <= seo._MAX_HASHTAGS


def test_select_description_keywords_returns_filtered_list() -> None:
    import random

    random.seed(0)
    kws = seo._select_description_keywords("wireframe flow", "relax")
    assert isinstance(kws, list)
    assert len(kws) <= 6
    assert all(not seo.has_unsupported_outcome_claim(k) for k in kws)


def test_select_description_keywords_focus_mood() -> None:
    import random

    random.seed(0)
    pool = set()
    for _ in range(20):
        pool.update(seo._select_description_keywords("wireframe", "focus"))
    assert "focus ambient" in pool or "procedural art for studying" in pool or "deep work visuals" in pool


def test_generate_description_returns_tuple() -> None:
    desc, cta = seo.generate_description("A calm moment", "short", ["#LiquidWire", "#GenerativeArt"])
    assert isinstance(desc, str)
    assert "#LiquidWire" in desc
    assert len(desc) <= 1500


def test_generate_description_no_cta() -> None:
    desc, cta = seo.generate_description("hook", "short", ["#x"], include_cta=False)
    assert cta == ""


def test_generate_description_truncates_over_1500() -> None:
    long_hashtags = [f"#tag{i}" for i in range(200)]
    desc, _ = seo.generate_description("hook", "short", long_hashtags)
    assert len(desc) <= 1500


def test_optimize_for_search_adds_keyword_when_missing() -> None:
    import random

    random.seed(0)
    title, desc = seo.optimize_for_search("Random Title", "A description here", "wireframe")
    assert isinstance(title, str)
    assert isinstance(desc, str)


def test_optimize_for_search_adds_related_term_to_description() -> None:
    import random

    random.seed(0)
    title, desc = seo.optimize_for_search("generative art", "no related terms here at all")
    assert "Great for moments of" in desc


def test_pick_upload_language_en_sequence(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "upload_language_counter.json"
    monkeypatch.setattr(seo, "_upload_language_counter_file", lambda: f)
    results = [seo.pick_upload_language() for _ in range(5)]
    assert all(r == "en" for r in results)
    assert json.loads(f.read_text(encoding="utf-8"))["count"] == 5


def test_pick_upload_language_pt_at_sixth(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "upload_language_counter.json"
    f.write_text(json.dumps({"count": 5}), encoding="utf-8")
    monkeypatch.setattr(seo, "_upload_language_counter_file", lambda: f)
    assert seo.pick_upload_language() == "pt"


def test_pick_upload_language_es_at_twelfth(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "upload_language_counter.json"
    f.write_text(json.dumps({"count": 11}), encoding="utf-8")
    monkeypatch.setattr(seo, "_upload_language_counter_file", lambda: f)
    assert seo.pick_upload_language() == "es"


def test_pick_upload_language_corrupt_file_defaults_en(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "upload_language_counter.json"
    f.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(seo, "_upload_language_counter_file", lambda: f)
    assert seo.pick_upload_language() == "en"


def test_keywords_for_language_pt() -> None:
    kws = seo.keywords_for_language("pt")
    assert "primary" in kws
    assert "arte generativa" in kws["primary"]


def test_keywords_for_language_es() -> None:
    kws = seo.keywords_for_language("es")
    assert "primary" in kws
    assert "arte generativa" in kws["primary"]


def test_keywords_for_language_en() -> None:
    kws = seo.keywords_for_language("en")
    assert "primary" in kws
    assert "generative art" in kws["primary"]


def test_keywords_for_language_unknown_defaults_en() -> None:
    kws = seo.keywords_for_language("fr")
    assert "generative art" in kws["primary"]


def test_title_pattern_weights_missing_returns_empty(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "title_pattern_performance.json"
    monkeypatch.setattr(seo, "_title_pattern_performance_file", lambda: f)
    assert seo._title_pattern_weights() == {}


def test_title_pattern_weights_corrupt_returns_empty(tmp_path, monkeypatch) -> None:
    f = _isolate_data(tmp_path, monkeypatch) / "title_pattern_performance.json"
    f.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(seo, "_title_pattern_performance_file", lambda: f)
    assert seo._title_pattern_weights() == {}
