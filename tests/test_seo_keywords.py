"""
tests/test_seo_keywords.py — testa geração de títulos e descrições otimizadas.
"""

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


class TestGenerateTitle:
    """Testa geração de títulos otimizados."""

    def test_generate_title_short(self):
        """Gera título para Short."""
        title = generate_title(
            animal="cat",
            acao="sleeping",
            estilo_musical="relaxing jazz",
            kind="short",
            emoji="🐱"
        )
        assert len(title) <= 100
        assert len(title) > 0
        assert "🐱" in title or "cat" in title.lower()

    def test_generate_title_horizontal(self):
        """Gera título para vídeo horizontal."""
        title = generate_title(
            animal="dog",
            acao="playing",
            estilo_musical="smooth jazz",
            kind="horizontal",
            emoji="🐶",
            duracao=4
        )
        assert len(title) <= 100
        # Pelo menos um dos patterns tem duração, mas não é garantido
        # Então verificamos apenas se tem animal e estilo musical
        assert "dog" in title.lower() or "smooth jazz" in title.lower()

    def test_generate_title_live(self):
        """Gera título para live."""
        title = generate_title(
            animal="cat",
            acao="relaxing",
            estilo_musical="jazz",
            kind="live",
            emoji="🔴"
        )
        assert "🔴" in title or "LIVE" in title.upper()

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
        assert "cute kitten" in optimized_title.lower() or "cat" in optimized_title.lower() or "dog" in optimized_title.lower()

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
