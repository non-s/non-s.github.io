"""Garante que todos os geradores e scripts principais importam sem erro."""

import importlib


def test_import_generators():
    for name in [
        "generate_pata_jazz_short",
        "generate_pata_jazz_horizontal",
        "generate_pata_jazz_live",
        "upload_youtube",
    ]:
        mod = importlib.import_module(name)
        assert mod is not None
        assert hasattr(mod, "main")


def test_import_sync_scripts():
    for name in ["scripts.sync_animal_broll", "scripts.sync_jazz_music"]:
        mod = importlib.import_module(name)
        assert hasattr(mod, "main")


def test_import_utils():
    for name in [
        "utils.animal_branding",
        "utils.ai_helper",
        "utils.ffmpeg_helpers",
        "utils.media_pool",
        "utils.youtube_oauth",
    ]:
        mod = importlib.import_module(name)
        assert mod is not None
