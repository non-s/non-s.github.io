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
    from utils.channel_config import active_channel

    scene = random_scene()
    allowed = ALL_SCENES + [s for group in active_channel.scene_categories.values() for s in group]
    assert scene in allowed


def test_rejects_non_animal_and_unapproved_animals():
    bad = ["hamster", "storm", "rain", "thunder"]
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


def test_station_terms_are_instrumental_and_curated():
    for term in JAMENDO_SEARCH_TERMS:
        assert any(
            style in term.lower()
            for style in ("jazz", "bossa", "ambient", "piano", "acoustic", "classical", "lofi")
        )


def test_jazz_terms_cover_slow_upbeat_and_lofi_variety():
    """Sem isso, o pool de audio so tinha jazz lento/relaxante - cenas de
    mood 'diversao' (playful dog, cat playing) nunca tinham musica animada
    de verdade pra combinar, e o pedido de variar entre jazz lento/animado/
    lofi nunca era atendido na sincronizacao real."""
    terms_lower = [t.lower() for t in JAMENDO_SEARCH_TERMS]
    assert any("swing" in t or "bebop" in t or "upbeat" in t or "fusion" in t for t in terms_lower)
    assert any("lofi" in t for t in terms_lower)
    assert any("smooth" in t or "relaxing" in t or "soft" in t for t in terms_lower)


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
            return "Cached Cat Hook Moment"

        monkeypatch.setattr(ab, "ai_text", fake_ai_text)
        generate_hook_with_ai("cat")
        generate_hook_with_ai("cat")
        assert calls["n"] == 1

    def test_prompt_varies_retention_angle_across_calls(self, monkeypatch):
        """O prompt sorteia um angulo de retencao (_HOOK_ANGLES) por
        chamada, nao sempre a mesma instrucao "cute e jazzy" - varia o
        *tipo* de hook, nao so o texto final."""
        prompts: list[str] = []

        def fake_ai_text(prompt, *a, **k):
            prompts.append(prompt)
            return "Some Valid Hook Text Here"

        monkeypatch.setattr(ab, "ai_text", fake_ai_text)
        monkeypatch.setattr(ab.random, "choice", lambda seq: ab._HOOK_ANGLES[2])
        generate_hook_with_ai("cat")
        assert ab._HOOK_ANGLES[2] in prompts[0]

    def test_prompt_mentions_first_seconds_retention(self, monkeypatch):
        prompts: list[str] = []
        monkeypatch.setattr(ab, "ai_text", lambda prompt, *a, **k: (prompts.append(prompt), "Valid Hook Text Here")[1])
        generate_hook_with_ai("cat")
        assert "1-2 seconds" in prompts[0]


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


class TestHookValidation:
    def setup_method(self):
        ab._AI_HOOK_CACHE.clear()
        ab._AI_HOOK_HISTORY.clear()

    def test_too_short_hook_rejected_and_falls_back(self, monkeypatch):
        # IA devolve hook curto (< 20 chars) — deve rejeitar e tentar de novo
        # (retry tambem curto) — cai no fallback vazio (cache ""), e
        # hook_for_scene cai no hardcoded.
        monkeypatch.setattr(ab, "ai_text", lambda *a, **k: "Hi cat")
        hook, _ = hook_for_scene("cat", use_ai=True)
        hardcoded = [h for h, _ in ab.HOOK_BY_SCENE["cat"]]
        assert hook in hardcoded

    def test_too_long_hook_truncated_to_ideal_max(self, monkeypatch):
        long_hook = "A" * 80
        monkeypatch.setattr(ab, "ai_text", lambda *a, **k: long_hook)
        out = generate_hook_with_ai("cat")
        # 80 chars: > _AI_HOOK_MAX_LEN (70) -> rejeitado, retry idem -> "".
        assert out == ""

    def test_negative_hook_rejected(self, monkeypatch):
        monkeypatch.setattr(ab, "ai_text", lambda *a, **k: "Sad cat is very cute today")
        hook, _ = hook_for_scene("cat", use_ai=True)
        hardcoded = [h for h, _ in ab.HOOK_BY_SCENE["cat"]]
        assert hook in hardcoded

    def test_similar_to_recent_rejected(self, monkeypatch):
        # Primeira chamada aceita "Cute Cat Jazz Moment".
        monkeypatch.setattr(ab, "ai_text", lambda *a, **k: "Cute Cat Jazz Moment")
        first = generate_hook_with_ai("cat")
        assert first == "Cute Cat Jazz Moment"
        # Limpa o cache para forcar nova chamada a IA; o historico permanece.
        ab._AI_HOOK_CACHE.clear()
        # Segunda chamada devolve hook com mesmas palavras-chave (similar >80%).
        monkeypatch.setattr(ab, "ai_text", lambda *a, **k: "Cute Cat Jazz Today")
        out = generate_hook_with_ai("cat")
        # Rejeitado por similaridade -> retry idem -> "" (cache).
        assert out == ""

    def test_valid_hook_accepted(self, monkeypatch):
        monkeypatch.setattr(ab, "ai_text", lambda *a, **k: "A Cute Cat Being Mischievous Today")
        out = generate_hook_with_ai("cat")
        assert out == "A Cute Cat Being Mischievous Today"

    def test_validate_hook_directly(self):
        assert ab._validate_hook("A Cute Cat Being Mischievous Today", "cat") is True
        assert ab._validate_hook("Hi", "cat") is False
        assert ab._validate_hook("x" * 80, "cat") is False
        assert ab._validate_hook("Sad cat is very cute today", "cat") is False


class TestBestHookForScene:
    """A7: best_hook_for_scene gera 2 candidatos e escolhe o de maior
    qualidade (tamanho ideal + keywords de alto volume)."""

    def test_returns_tuple_of_str_str(self):
        hook, emoji = ab.best_hook_for_scene("cat", use_ai=False)
        assert isinstance(hook, str)
        assert isinstance(emoji, str)
        assert len(hook) > 0

    def test_chooses_hook_with_better_score(self, monkeypatch):
        """Quando 2 hooks diferentes sao gerados, o com maior score de
        qualidade (tamanho ideal + keywords) e escolhido."""
        # Forca fallback (sem IA) e controla random.choice para retornar
        # 2 hooks diferentes com scores diferentes.
        hooks = ab.HOOK_BY_SCENE["cat"]
        # "This Cat's Morning Mood" tem 25 chars (+1) e sem keywords CTR (0)
        # "Cute Cat Being Mischievous" tem 27 chars (+1) e "cute" (+1) = 2
        monkeypatch.setattr(ab.random, "choice", lambda pool: hooks[0] if pool is hooks else hooks[1])
        # Primeira chamada retorna hooks[0], segunda hooks[1]
        call_count = {"n": 0}

        def mock_choice(pool):
            call_count["n"] += 1
            return pool[call_count["n"] % len(pool)]

        monkeypatch.setattr(ab.random, "choice", mock_choice)
        hook, _ = ab.best_hook_for_scene("cat", use_ai=False)
        # hooks[1] ("Cute Cat Being Mischievous") tem score maior (cute keyword)
        assert "Mischievous" in hook or "Morning" in hook

    def test_returns_first_when_both_identical(self, monkeypatch):
        """Se os 2 candidatos forem identicos, retorna o primeiro sem A/B."""
        monkeypatch.setattr(ab, "hook_for_scene", lambda scene, mood="", use_ai=True: ("Same Hook", "🐱"))
        hook, emoji = ab.best_hook_for_scene("cat", use_ai=False)
        assert hook == "Same Hook"
        assert emoji == "🐱"

    def test_hook_quality_score_prefers_ideal_length(self):
        """Hooks com 30-60 chars ganham +2; muito curto/longo perde pontos."""
        ideal = ab._hook_quality_score("A Cute Cat Being Extra Today And Happy")
        too_short = ab._hook_quality_score("Hi")
        too_long = ab._hook_quality_score("x" * 80)
        assert ideal > too_short
        assert ideal > too_long

    def test_hook_quality_score_rewards_ctr_keywords(self):
        """Hooks com keywords de alto volume (sleep, calm, cute) ganham +1 cada."""
        with_keyword = ab._hook_quality_score("Calm Cat Sleeping Peacefully Today Right Now")
        without = ab._hook_quality_score("A Cat Being Extra Today Right Now As Always")
        assert with_keyword > without
