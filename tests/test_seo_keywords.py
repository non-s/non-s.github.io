"""
tests/test_seo_keywords.py — testa geração de títulos e descrições otimizadas.
"""

import json

import utils.seo_keywords as seo_keywords
from utils.seo_keywords import (
    CTAS,
    HIGH_VOLUME_KEYWORDS,
    MUSIC_STYLE_BY_MOOD,
    TITLE_PATTERNS,
    generate_description,
    generate_hashtags,
    generate_title,
    music_style_for_mood,
    optimize_for_search,
    pick_title_pattern,
)


class TestPickTitlePattern:
    """Testa seleção de padrões de título."""

    def test_pick_pattern_short(self):
        """Seleciona padrão para Shorts."""
        pattern = pick_title_pattern("short")
        assert pattern in TITLE_PATTERNS["short"]
        assert "{emoji}" in pattern or "{animal}" in pattern


class TestTitlePatternWeights:
    """pick_title_pattern pondera pela performance real
    (title_pattern_performance.json, gerado por collect_analytics.py)
    quando ela existe, sem nunca excluir nenhum padrao do formato - mesmo
    mecanismo de content_strategy.scene_for_mood, so que title_pattern era
    gravado em video_tags.json mas nunca lido de volta ate agora."""

    def _isolate(self, tmp_path, monkeypatch):
        perf_file = tmp_path / "title_pattern_performance.json"
        monkeypatch.setattr(seo_keywords, "_title_pattern_performance_file", lambda: perf_file)
        return perf_file

    def test_no_performance_file_falls_back_to_uniform(self, tmp_path, monkeypatch):
        self._isolate(tmp_path, monkeypatch)
        assert seo_keywords._title_pattern_weights() == {}

    def test_reads_weights_from_file(self, tmp_path, monkeypatch):
        perf_file = self._isolate(tmp_path, monkeypatch)
        perf_file.write_text(json.dumps({"pattern-x": 2.0}), encoding="utf-8")

        assert seo_keywords._title_pattern_weights() == {"pattern-x": 2.0}

    def test_corrupted_file_falls_back_to_empty(self, tmp_path, monkeypatch):
        perf_file = self._isolate(tmp_path, monkeypatch)
        perf_file.write_text("not json", encoding="utf-8")

        assert seo_keywords._title_pattern_weights() == {}

    def test_pick_title_pattern_still_stays_within_kind_when_weighted(self, tmp_path, monkeypatch):
        perf_file = self._isolate(tmp_path, monkeypatch)
        weighted = {p: 2.5 for p in TITLE_PATTERNS["short"][:1]}
        perf_file.write_text(json.dumps(weighted), encoding="utf-8")

        for _ in range(20):
            assert pick_title_pattern("short") in TITLE_PATTERNS["short"]

    def test_heavily_weighted_pattern_is_picked_far_more_often(self, tmp_path, monkeypatch):
        import random

        random.seed(42)
        perf_file = self._isolate(tmp_path, monkeypatch)
        patterns = TITLE_PATTERNS["short"]
        perf_file.write_text(json.dumps({patterns[0]: 2.5, patterns[1]: 0.4}), encoding="utf-8")

        results = [pick_title_pattern("short") for _ in range(200)]
        assert results.count(patterns[0]) > results.count(patterns[1])


class TestGenerateTitle:
    """Testa geração de títulos otimizados."""

    def test_generate_title_by_kind(self):
        title = generate_title(animal="cat", acao="sleeping", estilo_musical="relaxing jazz", kind="short", emoji="🐱")
        assert len(title) <= 100 and len(title) > 0
        assert "🐱" in title or "cat" in title.lower()

    def test_generate_title_uses_keywords(self):
        """Título usa keywords de alta performance."""
        title = generate_title(animal="cat", acao="sleeping", estilo_musical="jazz", kind="short", emoji="🐱")
        # Verifica se usa pelo menos uma keyword
        all_keywords = []
        for category in HIGH_VOLUME_KEYWORDS.values():
            if isinstance(category, list):
                all_keywords.extend(category)
            elif isinstance(category, dict):
                for sublist in category.values():
                    all_keywords.extend(sublist)

        title_lower = title.lower()
        uses_keyword = any(kw.lower() in title_lower for kw in all_keywords)
        assert uses_keyword

    def test_generate_title_within_limit(self):
        """Título respeita limite de 100 caracteres."""
        for _ in range(10):  # Testa múltiplas vezes
            title = generate_title(
                animal="cat", acao="sleeping", estilo_musical="relaxing jazz", kind="short", emoji="🐱"
            )
            assert len(title) <= 100


class TestMusicStyleForMood:
    """music_style_for_mood alinha a frase de estilo musical do title/
    description ao audio REAL da cena (mood -> generos tocados de verdade,
    ver JAMENDO_SEARCH_TERMS em utils/animal_branding.py)."""

    def test_relax_mood_never_says_relaxing_jazz(self):
        """Regressao do bug real: acao='relaxing' + estilo_musical='relaxing
        jazz' produzia titulos redundantes ('cat relaxing to relaxing
        jazz'). Nenhuma opcao do mood 'relax' pode repetir a palavra
        'relaxing'."""
        for _ in range(30):
            style = music_style_for_mood("relax")
            assert "relaxing" not in style.lower()
            assert "jazz" in style.lower()

    def test_all_mapped_moods_contain_jazz_keyword(self):
        """Todo estilo precisa conter 'jazz' - garante que o titulo sempre
        bate com HIGH_PERFORMANCE_KEYWORDS['music'] (ver
        test_generate_title_uses_keywords: todos os TITLE_PATTERNS incluem
        {estilo_musical})."""
        for mood, options in MUSIC_STYLE_BY_MOOD.items():
            for style in options:
                assert "jazz" in style.lower(), f"mood={mood!r} style={style!r} sem 'jazz'"

    def test_unknown_mood_falls_back_to_relaxing_jazz(self):
        assert music_style_for_mood("") == "relaxing jazz"
        assert music_style_for_mood("nao-existe") == "relaxing jazz"

    def test_diversao_mood_uses_energetic_styles(self):
        for _ in range(30):
            style = music_style_for_mood("diversao")
            assert style in MUSIC_STYLE_BY_MOOD["diversao"]


class TestGenerateDescription:
    """Testa geração de descrições otimizadas."""

    def test_generate_description_short(self):
        """Gera descrição para Short."""
        hashtags = ["#PataJazz", "#Cats", "#Jazz"]
        desc, _ = generate_description(hook="Cute kitten sleeping", kind="short", hashtags=hashtags, include_cta=True)
        assert len(desc) > 0
        assert "#PataJazz" in desc or "#Cats" in desc
        assert "🐾" in desc or "💫" in desc or "🎷" in desc  # Tem emojis da marca/SEO

    def test_generate_description_without_cta(self):
        """Gera descrição sem CTA.

        intro/corpo agora variam por sorteio (mais humano) - sem fixar a
        seed, as duas chamadas podiam sortear textos de tamanhos diferentes
        e o teste comparava coisas nao comparaveis. Seed identica antes de
        cada chamada faz random.choice(intro)/random.choice(corpo) (as duas
        primeiras chamadas de random dentro de generate_description) saírem
        iguais nas duas vezes, isolando a diferença apenas no CTA.
        """
        import random as _random

        hashtags = ["#PataJazz"]
        _random.seed(42)
        desc_with_cta, _ = generate_description(hook="Test", kind="short", hashtags=hashtags, include_cta=True)
        _random.seed(42)
        desc_without_cta, _ = generate_description(hook="Test", kind="short", hashtags=hashtags, include_cta=False)
        # Descrição sem CTA deve ser menor
        assert len(desc_without_cta) < len(desc_with_cta)
        # Verifica que não tem CTAs comuns quando include_cta=False
        for cta in CTAS:
            if cta.strip():
                assert cta not in desc_without_cta

    def test_generate_description_includes_hashtags(self):
        """Descrição inclui hashtags."""
        hashtags = ["#PataJazz", "#Cats", "#Jazz", "#Shorts"]
        desc, _ = generate_description(hook="Test", kind="short", hashtags=hashtags, include_cta=True)
        assert "#PataJazz" in desc

    def test_generate_description_returns_cta(self):
        """generate_description retorna tambem o CTA usado (A/B tracking)."""
        hashtags = ["#PataJazz"]
        desc, cta = generate_description(hook="Test", kind="short", hashtags=hashtags, include_cta=True)
        assert cta in CTAS
        assert cta in desc

    def test_generated_description_avoids_unsupported_pet_outcomes(self):
        desc, _ = generate_description(
            hook="Sleepy cat",
            kind="short",
            hashtags=["#PataJazz"],
            animal="cat",
            mood="anxiety",
        )
        lowered = desc.lower()
        assert "reduce anxiety" not in lowered
        assert "anxiety relief" not in lowered
        assert "stress relief" not in lowered

    def test_generate_description_no_cta_returns_empty(self):
        """Sem CTA, o segundo elemento do retorno e vazio."""
        hashtags = ["#PataJazz"]
        desc, cta = generate_description(hook="Test", kind="short", hashtags=hashtags, include_cta=False)
        assert cta == ""


class TestGenerateHashtags:
    """Testa geração de hashtags em camadas."""

    def test_generate_hashtags_cat(self):
        """Gera hashtags para vídeo de gato."""
        hashtags = generate_hashtags(animal="cat", categoria="cuteness", kind="short")
        assert len(hashtags) <= 10
        assert "#Cats" in hashtags
        assert "#PataJazz" in hashtags  # Brand sempre presente

    def test_generate_hashtags_dog(self):
        """Gera hashtags para vídeo de cachorro."""
        hashtags = generate_hashtags(animal="dog", categoria="fun", kind="short")
        assert len(hashtags) <= 10
        assert "#Dogs" in hashtags

    def test_generate_hashtags_relax(self):
        """Gera hashtags para categoria relaxamento."""
        hashtags = generate_hashtags(animal="cat", categoria="relaxation", kind="short")
        assert "#PetAnxiety" in hashtags or "#SleepMusic" in hashtags

    def test_generate_hashtags_short_format(self):
        """Inclui hashtags de formato para Shorts."""
        hashtags = generate_hashtags(animal="cat", categoria="cuteness", kind="short")
        assert "#Shorts" in hashtags or "#YouTubeShorts" in hashtags

    def test_generate_hashtags_no_duplicates(self):
        """Não gera hashtags duplicadas."""
        hashtags = generate_hashtags(animal="cat", categoria="cuteness", kind="short")
        assert len(hashtags) == len(set(hashtags))

    def test_optimize_title_with_keyword(self):
        """Otimiza título adicionando keyword se necessário."""
        title = "Cute Kitten"
        description = "Test description"

        optimized_title, optimized_desc = optimize_for_search(title, description)

        # Deve manter o título ou adicionar keyword
        assert len(optimized_title) >= len(title)
        assert (
            "cute kitten" in optimized_title.lower()
            or "cat" in optimized_title.lower()
            or "dog" in optimized_title.lower()
        )

    def test_optimize_title_keeps_animal_audience_coherent(self, monkeypatch):
        """A keyword final nao pode redirecionar um video de gato para cachorros."""
        monkeypatch.setattr(seo_keywords.random, "choice", lambda values: values[0])
        optimized_title, _ = optimize_for_search("Cozy kitten nap", "A quiet moment", animal="cat")
        assert "dog" not in optimized_title.lower()
        assert "cat" in optimized_title.lower()

    def test_optimize_description_with_keywords(self):
        """Otimiza descrição com keywords relacionadas."""
        title = "Cat Jazz"
        description = "Basic description"

        optimized_title, optimized_desc = optimize_for_search(title, description)

        # Deve adicionar termos relacionados
        related_terms = ["relaxation", "meditation", "studying", "working", "focus"]
        has_related = any(term in optimized_desc.lower() for term in related_terms)
        assert has_related or "Great for moments of" in optimized_desc

    def test_optimize_preserves_existing_keywords(self):
        """Preserva título que já tem keywords."""
        title = "Relaxing Cat Jazz for Sleeping"

        optimized_title, _ = optimize_for_search(title, "description")

        # Ja contem uma primary keyword ("relaxing music for cats" nao bate
        # exatamente, mas o titulo nao deve ser truncado/alterado no meio)
        assert "Relaxing Cat Jazz for Sleeping" in optimized_title


class TestIntegration:
    """Testes de integração do fluxo completo."""

    def test_full_metadata_generation(self):
        """Gera metadados completos otimizados."""
        animal = "cat"
        acao = "sleeping"
        estilo = "relaxing jazz"
        kind = "short"
        emoji = "🐱"

        # Gera título
        title = generate_title(animal, acao, estilo, kind, emoji)
        assert len(title) <= 100

        # Gera hashtags
        hashtags = generate_hashtags(animal, "relaxation", kind)
        assert len(hashtags) <= 10

        # Gera descrição
        description, _ = generate_description(title, kind, hashtags)
        assert len(description) > 0

        # Otimiza para busca
        final_title, final_desc = optimize_for_search(title, description)
        assert len(final_title) <= 100
        assert "#PataJazz" in final_desc or "Pata Jazz" in final_desc


class TestPlaylistPromotionPatterns:
    """A5: padrões de título que promovem playlists temáticas explicitamente.
    Esses padrões referenciam cenarios/problemas especificos (thunder,
    fireworks, anxiety) e direcionam para a playlist correspondente,
    aumentando CTR em buscas long-tail e session duration via playlists."""

    def test_playlist_promotion_patterns_exist(self):
        patterns = TITLE_PATTERNS["short"]
        playlist_patterns = [p for p in patterns if "playlist" in p.lower()]
        assert len(playlist_patterns) >= 2, "deve haver pelo menos 2 padroes de playlist"

    def test_playlist_promotion_pattern_uses_scenario(self):
        patterns = TITLE_PATTERNS["short"]
        scenario_pattern = [p for p in patterns if "{scenario}" in p and "playlist" in p.lower()]
        assert len(scenario_pattern) >= 1

    def test_playlist_promotion_pattern_generates_valid_title(self):
        """Padrão de playlist gera título valido com prefixo de marca."""
        from utils.seo_keywords import generate_title

        for _ in range(10):
            title = generate_title(
                animal="dog", acao="anxiety", estilo_musical="calming jazz", kind="short", emoji="🐶"
            )
            assert len(title) <= 100
            assert title.startswith("Pata Jazz |")


class TestTitleTemplateQuality:
    """Fallbacks editoriais precisam soar naturais, mesmo sem Gemini."""

    def test_templates_avoid_automation_artifacts(self):
        forbidden = ("dog dog", "cat cat", "instantly", "9 out of 10", "scared of anxious")
        for animal, emoji in (("cat", "*"), ("dog", "*")):
            for _ in range(100):
                title = generate_title(
                    animal=animal, acao="anxiety", estilo_musical="calming jazz", kind="short", emoji=emoji
                )
                assert not any(fragment in title.lower() for fragment in forbidden), title


class TestTitleAntiRepeat:
    """Anti-repeat de titulos: near-duplicados dos recentes denunciam
    conteudo em massa ("mesmo video de novo") e afastam o publico. O gerador
    usa used_titles.json para trocar de padrao antes de gravar."""

    def _isolate(self, tmp_path, monkeypatch):
        used_file = tmp_path / "used_titles.json"
        monkeypatch.setattr(seo_keywords, "_title_used_file", lambda: used_file)
        return used_file

    def test_similarity_same_words_reordered_is_one(self):
        assert (
            seo_keywords.title_similarity(
                "Gato Dormindo Com Jazz",
                "Com Jazz Gato Dormindo",
            )
            == 1.0
        )

    def test_similarity_shared_words(self):
        sim = seo_keywords.title_similarity(
            "Gato Dormindo Com Jazz",
            "Gato Brincando Com Jazz",
        )
        assert 0.5 < sim < 1.0

    def test_similarity_disjoint_is_zero(self):
        assert seo_keywords.title_similarity("Gato Jazz", "Cachorro Forro") == 0.0

    def test_no_history_never_repetitive(self, tmp_path, monkeypatch):
        self._isolate(tmp_path, monkeypatch)
        assert not seo_keywords.title_is_too_repetitive("Gato Dormindo Com Jazz")

    def test_repetitive_when_near_duplicate_in_history(self, tmp_path, monkeypatch):
        used_file = self._isolate(tmp_path, monkeypatch)
        used_file.write_text(json.dumps(["Gato Dormindo Com Jazz"]), encoding="utf-8")
        assert seo_keywords.title_is_too_repetitive("Com Jazz Gato Dormindo")

    def test_distinct_title_not_repetitive(self, tmp_path, monkeypatch):
        used_file = self._isolate(tmp_path, monkeypatch)
        used_file.write_text(json.dumps(["Gato Dormindo Com Jazz"]), encoding="utf-8")
        assert not seo_keywords.title_is_too_repetitive("Cachorro Dançando Rock")

    def test_record_used_title_persists_and_dedupes(self, tmp_path, monkeypatch):
        used_file = self._isolate(tmp_path, monkeypatch)
        seo_keywords.record_used_title("Título Um")
        seo_keywords.record_used_title("Título Dois")
        seo_keywords.record_used_title("Título Um")
        data = json.loads(used_file.read_text(encoding="utf-8"))
        assert data == ["Título Um", "Título Dois"]

    def test_record_caps_history_size(self, tmp_path, monkeypatch):
        used_file = self._isolate(tmp_path, monkeypatch)
        for i in range(130):
            seo_keywords.record_used_title(f"Título {i}")
        data = json.loads(used_file.read_text(encoding="utf-8"))
        assert len(data) == 120
        assert "Título 0" not in data

    def test_corrupted_history_is_empty(self, tmp_path, monkeypatch):
        used_file = self._isolate(tmp_path, monkeypatch)
        used_file.write_text("not json", encoding="utf-8")
        assert seo_keywords.recent_titles() == []
        assert not seo_keywords.title_is_too_repetitive("Qualquer Título")
