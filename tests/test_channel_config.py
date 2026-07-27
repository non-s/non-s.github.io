"""Testes para utils/channel_config.py — abstracao de multi-canal.

Valida que PATA_JAZZ esta populado com todos os campos, que set_channel
troca o canal ativo (e rejeita nomes inexistentes), e que a backward
compat com os modulos que leem active_channel esta mantida (random_scene
sem arg continua funcionando).
"""
from __future__ import annotations

import pytest

from utils import channel_config
from utils.animal_branding import ALL_SCENES, random_scene
from utils.channel_config import (
    CHANNELS,
    PATA_CLASSICAL,
    PATA_JAZZ,
    PATA_LOFI,
    ChannelConfig,
    active_channel,
    set_channel,
)


@pytest.fixture(autouse=True)
def _restore_active_channel():
    """Garante que cada teste termine com pata_jazz ativo, mesmo se falhar
    no meio de um teste que trocou o canal."""
    set_channel("pata_jazz")
    yield
    set_channel("pata_jazz")


class TestPataJazzConfig:
    """PATA_JAZZ tem todos os campos esperados de ChannelConfig."""

    def test_is_channel_config_instance(self):
        assert isinstance(PATA_JAZZ, ChannelConfig)

    def test_name(self):
        assert PATA_JAZZ.name == "Pata Jazz"

    def test_brand_prefix(self):
        assert PATA_JAZZ.brand_prefix == "Pata Jazz |"

    def test_hashtag_brand(self):
        assert "#PataJazz" in PATA_JAZZ.hashtag_brand
        assert isinstance(PATA_JAZZ.hashtag_brand, list)

    def test_base_tags(self):
        assert "Pata Jazz" in PATA_JAZZ.base_tags
        assert "cat" in PATA_JAZZ.base_tags
        assert "dog" in PATA_JAZZ.base_tags
        assert "jazz" in PATA_JAZZ.base_tags

    def test_playlists_by_mood(self):
        assert PATA_JAZZ.playlists_by_mood["relax"] == "Pata Jazz | Relaxar e Dormir"
        assert "fofura" in PATA_JAZZ.playlists_by_mood
        assert "diversao" in PATA_JAZZ.playlists_by_mood

    def test_playlists_by_kind(self):
        assert PATA_JAZZ.playlists_by_kind["short"] == "Pata Jazz | Shorts"
        assert "horizontal" in PATA_JAZZ.playlists_by_kind

    def test_live_tags(self):
        assert isinstance(PATA_JAZZ.live_tags, list)
        assert len(PATA_JAZZ.live_tags) > 0
        assert "Pata Jazz" in PATA_JAZZ.live_tags

    def test_live_title_prompt(self):
        assert isinstance(PATA_JAZZ.live_title_prompt, str)
        assert "live stream" in PATA_JAZZ.live_title_prompt.lower()

    def test_seo_keywords(self):
        assert "cuteness" in PATA_JAZZ.seo_keywords
        assert "relaxation" in PATA_JAZZ.seo_keywords
        assert "fun" in PATA_JAZZ.seo_keywords
        assert "music" in PATA_JAZZ.seo_keywords
        assert "jazz" in PATA_JAZZ.seo_keywords["music"]

    def test_title_patterns(self):
        for kind in ("short", "horizontal", "live"):
            assert kind in PATA_JAZZ.title_patterns
            assert len(PATA_JAZZ.title_patterns[kind]) > 0

    def test_emojis(self):
        assert "brand" in PATA_JAZZ.emojis

    def test_scene_categories(self):
        for mood in ("fofura", "diversao", "relax"):
            assert mood in PATA_JAZZ.scene_categories
            assert isinstance(PATA_JAZZ.scene_categories[mood], list)

    def test_hourly_mood(self):
        assert len(PATA_JAZZ.hourly_mood) == 24
        assert PATA_JAZZ.hourly_mood[0] == "relax"
        assert PATA_JAZZ.hourly_mood[9] == "diversao"
        assert PATA_JAZZ.hourly_mood[14] == "fofura"

    def test_default_description(self):
        assert isinstance(PATA_JAZZ.default_description, str)
        assert len(PATA_JAZZ.default_description) > 0


class TestRegistryAndSetActive:
    """Registry CHANNELS e set_channel()."""

    def test_pata_jazz_in_registry(self):
        assert "pata_jazz" in CHANNELS
        assert CHANNELS["pata_jazz"] is PATA_JAZZ

    def test_default_active_channel_is_pata_jazz(self):
        assert active_channel is PATA_JAZZ

    def test_set_channel_pata_jazz(self):
        set_channel("pata_jazz")
        assert channel_config.active_channel is PATA_JAZZ

    def test_set_channel_unknown_raises_keyerror(self):
        with pytest.raises(KeyError):
            set_channel("inexistente")

    def test_set_channel_changes_active_channel(self):
        # Cria um canal fake no registry para validar a troca sem depender
        # de um canal real novo (a tarefa pediu para nao criar canais novos,
        # mas precisamos de um segundo para validar a troca).
        fake = ChannelConfig(
            name="Pata Test",
            brand_prefix="Pata Test |",
            hashtag_brand=["#PataTest"],
            base_tags=["Pata Test", "lofi"],
            playlists_by_mood={"relax": "Pata Test | Relax"},
            playlists_by_kind={"short": "Pata Test | Shorts"},
            live_tags=["lofi for pets"],
            live_title_prompt="prompt",
            seo_keywords={"cuteness": ["cute"]},
            title_patterns={"short": ["{animal}"]},
            emojis={"brand": "🐾"},
            scene_categories={"fofura": ["cat"]},
            hourly_mood={h: "relax" for h in range(24)},
            default_description="desc",
        )
        original = dict(CHANNELS)
        try:
            CHANNELS["pata_test"] = fake
            assert channel_config.active_channel.base_tags != fake.base_tags
            set_channel("pata_test")
            assert channel_config.active_channel is fake
            assert channel_config.active_channel.base_tags == fake.base_tags
        finally:
            channel_config.CHANNELS.clear()
            channel_config.CHANNELS.update(original)
            set_channel("pata_jazz")

    def test_switching_channel_changes_base_tags(self):
        # Mesma logica do teste anterior, focado no contrato do enunciado:
        # trocar canal muda active_channel.base_tags.
        fake = ChannelConfig(
            name="Pata Other",
            brand_prefix="Pata Other |",
            hashtag_brand=["#PataOther"],
            base_tags=["Pata Other", "classical"],
            playlists_by_mood={},
            playlists_by_kind={},
            live_tags=[],
            live_title_prompt="p",
            seo_keywords={},
            title_patterns={},
            emojis={"brand": "🐾"},
            scene_categories={},
            hourly_mood={},
            default_description="d",
        )
        original = dict(CHANNELS)
        try:
            CHANNELS["pata_other"] = fake
            before = channel_config.active_channel.base_tags
            set_channel("pata_other")
            after = channel_config.active_channel.base_tags
            assert before != after
        finally:
            channel_config.CHANNELS.clear()
            channel_config.CHANNELS.update(original)
            set_channel("pata_jazz")


class TestPataLofiConfig:
    def test_is_channel_config_instance(self):
        assert isinstance(PATA_LOFI, ChannelConfig)

    def test_name(self):
        assert PATA_LOFI.name == "Pata Lofi"

    def test_base_tags_contain_lofi_keywords(self):
        assert "lofi" in PATA_LOFI.base_tags
        assert "study" in PATA_LOFI.base_tags
        assert "chill" in PATA_LOFI.base_tags
        assert "beats" in PATA_LOFI.base_tags

    def test_in_registry(self):
        assert "pata_lofi" in CHANNELS
        assert CHANNELS["pata_lofi"] is PATA_LOFI

    def test_set_channel_changes_base_tags(self):
        before = channel_config.active_channel.base_tags
        set_channel("pata_lofi")
        after = channel_config.active_channel.base_tags
        assert after is PATA_LOFI.base_tags
        assert before != after


class TestPataClassicalConfig:
    def test_is_channel_config_instance(self):
        assert isinstance(PATA_CLASSICAL, ChannelConfig)

    def test_name(self):
        assert PATA_CLASSICAL.name == "Pata Classical"

    def test_base_tags_contain_classical_keywords(self):
        assert "classical" in PATA_CLASSICAL.base_tags
        assert "piano" in PATA_CLASSICAL.base_tags
        assert "orchestra" in PATA_CLASSICAL.base_tags

    def test_in_registry(self):
        assert "pata_classical" in CHANNELS
        assert CHANNELS["pata_classical"] is PATA_CLASSICAL

    def test_set_channel_changes_base_tags(self):
        before = channel_config.active_channel.base_tags
        set_channel("pata_classical")
        after = channel_config.active_channel.base_tags
        assert after is PATA_CLASSICAL.base_tags
        assert before != after


class TestBackwardCompat:
    """Backward compat: modulos existentes continuam funcionando sem arg."""

    def test_random_scene_without_arg_works(self):
        scene = random_scene()
        assert isinstance(scene, str)
        assert scene in ALL_SCENES

    def test_random_scene_returns_valid_for_pata_jazz(self):
        set_channel("pata_jazz")
        for _ in range(20):
            assert random_scene() in ALL_SCENES
