"""
tests/test_seo_keywords.py — testa geração de títulos e descrições otimizadas.
"""

import json

import pytest

import utils.seo_keywords as seo_keywords
from utils.seo_keywords import (
    CTAS,
    HIGH_PERFORMANCE_KEYWORDS,
    TITLE_PATTERNS,
    generate_description,
    generate_hashtags,
    generate_title,
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

    def test_pick_pattern_horizontal(self):
        """Seleciona padrão para vídeos horizontais."""
        pattern = pick_title_pattern("horizontal")
        assert pattern in TITLE_PATTERNS["horizontal"]

    def test_pick_pattern_live(self):
        """Seleciona padrão para lives."""
        pattern = pick_title_pattern("live")
        assert pattern in TITLE_PATTERNS["live"]
        assert "LIVE" in pattern.upper()


class TestTitlePatternWeights:
    """pick_title_pattern pondera pela performance real
    (title_pattern_performance.json, gerado por collect_analytics.py)
    quando ela existe, sem nunca excluir nenhum padrao do formato - mesmo
    mecanismo de content_strategy.scene_for_mood, so que title_pattern era
    gravado em video_tags.json mas nunca lido de volta ate agora."""

    def _isolate(self, tmp_path, monkeypatch):
        perf_file = tmp_path / "title_pattern_performance.json"
        monkeypatch.setattr(seo_keywords, "_TITLE_PATTERN_PERFORMANCE_FILE", perf_file)
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
        perf_file.write_text(
            json.dumps({patterns[0]: 2.5, patterns[1]: 0.4}), encoding="utf-8"
        )

        results = [pick_title_pattern("short") for _ in range(200)]
        assert results.count(patterns[0]) > results.count(patterns[1])


class TestGenerateTitle:
    """Testa geração de títulos otimizados."""

    @pytest.mark.parametrize(
        "kind,extra,assertion",
        [
            (
                "short",
                {"animal": "cat", "acao": "sleeping", "estilo_musical": "relaxing jazz", "emoji": "🐱"},
                lambda t: len(t) <= 100 and len(t) > 0 and ("🐱" in t or "cat" in t.lower()),
            ),
            (
                "horizontal",
                {
                    "animal": "dog",
                    "acao": "playing",
                    "estilo_musical": "smooth jazz",
                    "emoji": "🐶",
                    "duracao": 4,
                },
                lambda t: len(t) <= 100 and ("dog" in t.lower() or "smooth jazz" in t.lower()),
            ),
            (
                "live",
                {"animal": "cat", "acao": "relaxing", "estilo_musical": "jazz", "emoji": "🔴"},
                lambda t: "🔴" in t or "LIVE" in t.upper(),
            ),
        ],
        ids=["short", "horizontal", "live"],
    )
    def test_generate_title_by_kind(self, kind, extra, assertion):
        title = generate_title(kind=kind, **extra)
        assert assertion(title)

    def test_generate_title_uses_keywords(self):
        """Título usa keywords de alta performance."""
        title = generate_title(
            animal="cat",
            acao="sleeping",
            estilo_musical="jazz",
            kind="short",
            emoji="🐱"
        )
        # Verifica se usa pelo menos uma keyword
        all_keywords = []
        for category in HIGH_PERFORMANCE_KEYWORDS.values():
            all_keywords.extend(category)

        title_lower = title.lower()
        uses_keyword = any(kw.lower() in title_lower for kw in all_keywords)
        # "jazz" (estilo_musical) esta em HIGH_PERFORMANCE_KEYWORDS["music"] e
        # aparece literalmente em todos os patterns de "short" (todos incluem
        # {estilo_musical}), entao isso sempre deve ser verdadeiro - "or True"
        # tornava essa asserção incapaz de falhar independente do resultado.
        assert uses_keyword

    def test_generate_title_within_limit(self):
        """Título respeita limite de 100 caracteres."""
        for _ in range(10):  # Testa múltiplas vezes
            title = generate_title(
                animal="cat",
                acao="sleeping",
                estilo_musical="relaxing jazz",
                kind="horizontal",
                emoji="🐱"
            )
            assert len(title) <= 100


class TestGenerateDescription:
    """Testa geração de descrições otimizadas."""

    def test_generate_description_short(self):
        """Gera descrição para Short."""
        hashtags = ["#PataJazz", "#Cats", "#Jazz"]
        desc = generate_description(
            hook="Cute kitten sleeping",
            kind="short",
            hashtags=hashtags,
            include_cta=True
        )
        assert len(desc) > 0
        assert "#PataJazz" in desc or "#Cats" in desc
        assert "🐾" in desc or "✨" in desc  # Tem emojis

    def test_generate_description_horizontal(self):
        """Gera descrição para vídeo horizontal."""
        hashtags = ["#PataJazz", "#Jazz"]
        desc = generate_description(
            hook="Relax with cats and jazz",
            kind="horizontal",
            hashtags=hashtags,
            include_cta=True
        )
        assert "Relax" in desc or "enjoy" in desc.lower()
        assert len(desc) > 50  # Descrições longas têm mais conteúdo

    def test_generate_description_live(self):
        """Gera descrição para live."""
        hashtags = ["#PataJazz", "#Live"]
        desc = generate_description(
            hook="Jazz 24/7 with cats",
            kind="live",
            hashtags=hashtags,
            include_cta=True
        )
        assert "LIVE" in desc.upper() or "24/7" in desc

    def test_generate_description_without_cta(self):
        """Gera descrição sem CTA."""
        hashtags = ["#PataJazz"]
        desc_with_cta = generate_description(
            hook="Test",
            kind="short",
            hashtags=hashtags,
            include_cta=True
        )
        desc_without_cta = generate_description(
            hook="Test",
            kind="short",
            hashtags=hashtags,
            include_cta=False
        )
        # Descrição sem CTA deve ser menor
        assert len(desc_without_cta) < len(desc_with_cta)
        # Verifica que não tem CTAs comuns quando include_cta=False
        for cta in CTAS:
            if cta.strip():
                assert cta not in desc_without_cta

    def test_generate_description_includes_hashtags(self):
        """Descrição inclui hashtags."""
        hashtags = ["#PataJazz", "#Cats", "#Jazz", "#Shorts"]
        desc = generate_description(
            hook="Test",
            kind="short",
            hashtags=hashtags,
            include_cta=True
        )
        assert "#PataJazz" in desc


class TestGenerateHashtags:
    """Testa geração de hashtags em camadas."""

    def test_generate_hashtags_cat(self):
        """Gera hashtags para vídeo de gato."""
        hashtags = generate_hashtags(animal="cat", categoria="cuteness", kind="short")
        assert len(hashtags) <= 15
        assert "#Cats" in hashtags or "#Kittens" in hashtags
        assert "#PataJazz" in hashtags  # Brand sempre presente

    def test_generate_hashtags_dog(self):
        """Gera hashtags para vídeo de cachorro."""
        hashtags = generate_hashtags(animal="dog", categoria="fun", kind="horizontal")
        assert len(hashtags) <= 15
        assert "#Dogs" in hashtags or "#Puppies" in hashtags

    def test_generate_hashtags_relax(self):
        """Gera hashtags para categoria relaxamento."""
        hashtags = generate_hashtags(animal="cat", categoria="relaxation", kind="live")
        assert "#Relaxation" in hashtags or "#Peaceful" in hashtags or "#Calm" in hashtags

    def test_generate_hashtags_short_format(self):
        """Inclui hashtags de formato para Shorts."""
        hashtags = generate_hashtags(animal="cat", categoria="cuteness", kind="short")
        assert "#Shorts" in hashtags or "#YouTubeShorts" in hashtags

    def test_generate_hashtags_live_format(self):
        """Inclui hashtags de formato para Live."""
        hashtags = generate_hashtags(animal="dog", categoria="cuteness", kind="live")
        assert "#Live" in hashtags or "#LiveStream" in hashtags or "#247" in hashtags

    def test_generate_hashtags_no_duplicates(self):
        """Não gera hashtags duplicadas."""
        hashtags = generate_hashtags(animal="cat", categoria="cuteness", kind="short")
        assert len(hashtags) == len(set(hashtags))


class TestOptimizeForSearch:
    """Testa otimização para busca do YouTube."""

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
        assert len(hashtags) <= 15

        # Gera descrição
        description = generate_description(title, kind, hashtags)
        assert len(description) > 0

        # Otimiza para busca
        final_title, final_desc = optimize_for_search(title, description)
        assert len(final_title) <= 100
        assert "#PataJazz" in final_desc or "Pata Jazz" in final_desc
