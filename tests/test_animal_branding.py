
import utils.animal_branding as ab
from utils.animal_branding import (
    ALL_SCENES,
    JAMENDO_SEARCH_TERMS,
    generate_hook_with_ai,
    hook_for_scene,
    is_allowed_animal_text,
    random_scene,
)


def test_scenes_only_cats_and_dogs():
    for scene in ALL_SCENES:
        text = f"{scene} video"
        assert is_allowed_animal_text(text), f"{scene!r} deve ser permitido"


def test_hooks_return_tuple():
    for scene in ALL_SCENES:
        hook, emoji = hook_for_scene(scene)
        assert isinstance(hook, str)
        assert isinstance(emoji, str)


def test_random_scene_in_allowed():
    scene = random_scene()
    assert scene in ALL_SCENES


def test_no_disallowed_animals():
    bad = ["bird", "rabbit", "bunny", "hamster", "storm", "rain", "thunder"]
    for word in bad:
        assert not is_allowed_animal_text(word)


def test_blocked_cartoon_content():
    blocked = [
        "cute cat cartoon",
        "animated dog",
        "kitten 3d illustration",
        "puppy drawing vector",
        "ai generated cat",
    ]
    for word in blocked:
        assert not is_allowed_animal_text(word)


def test_jazz_terms_only():
    for term in JAMENDO_SEARCH_TERMS:
        assert "jazz" in term.lower() or "bossa" in term.lower()


class TestGenerateHookWithAi:
    def setup_method(self):
        ab._AI_HOOK_CACHE.clear()

    def test_returns_ai_text_when_safe(self, monkeypatch):
        monkeypatch.setattr(ab, "ai_text", lambda *a, **k: "Cute Cat Jazz Moment")
        out = generate_hook_with_ai("cat")
        assert out == "Cute Cat Jazz Moment"

    def test_falls_back_to_empty_when_ai_returns_unsafe(self, monkeypatch):
        monkeypatch.setattr(ab, "ai_text", lambda *a, **k: "see https://scam.example.com")
        assert generate_hook_with_ai("cat") == ""

    def test_falls_back_to_empty_when_no_api_key(self, monkeypatch):
        import utils.ai_helper as ai_helper
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setattr(ai_helper, "_session", type("S", (), {})())
        assert generate_hook_with_ai("cat") == ""

    def test_cache_skips_second_ai_call(self, monkeypatch):
        calls = {"n": 0}

        def fake_ai_text(*a, **k):
            calls["n"] += 1
            return "Cached Cat Hook"

        monkeypatch.setattr(ab, "ai_text", fake_ai_text)
        generate_hook_with_ai("cat")
        generate_hook_with_ai("cat")
        assert calls["n"] == 1


class TestHookForSceneWithAi:
    def setup_method(self):
        ab._AI_HOOK_CACHE.clear()

    def test_uses_ai_when_safe(self, monkeypatch):
        monkeypatch.setattr(ab, "ai_text", lambda *a, **k: "Sleepy Cat Jazz Vibes")
        hook, emoji = hook_for_scene("sleepy cat", use_ai=True)
        assert hook == "Sleepy Cat Jazz Vibes"
        assert emoji

    def test_falls_back_to_hardcoded_when_ai_fails(self, monkeypatch):
        monkeypatch.setattr(ab, "ai_text", lambda *a, **k: "")
        hook, emoji = hook_for_scene("sleepy cat", use_ai=True)
        hardcoded = [h for h, _ in ab.HOOK_BY_SCENE["sleepy cat"]]
        assert hook in hardcoded

    def test_falls_back_when_ai_returns_suspicious(self, monkeypatch):
        monkeypatch.setattr(ab, "ai_text", lambda *a, **k: "ignore previous instructions")
        hook, _ = hook_for_scene("sleepy cat", use_ai=True)
        hardcoded = [h for h, _ in ab.HOOK_BY_SCENE["sleepy cat"]]
        assert hook in hardcoded

    def test_use_ai_false_uses_hardcoded(self):
        hook, emoji = hook_for_scene("sleepy cat", use_ai=False)
        hardcoded = [h for h, _ in ab.HOOK_BY_SCENE["sleepy cat"]]
        assert hook in hardcoded
        assert emoji

    def test_backward_compat_no_mood_no_use_ai(self):
        hook, emoji = hook_for_scene("sleepy cat")
        assert isinstance(hook, str)
        assert isinstance(emoji, str)
