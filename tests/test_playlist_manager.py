"""Testes unitarios para utils/playlist_manager.py."""

from unittest.mock import MagicMock, patch

import pytest

from utils import playlist_manager


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reseta o cache global entre testes para evitar poluicao de estado."""
    playlist_manager._playlist_cache = {}
    with patch("utils.playlist_manager._load_cache"):
        yield
    playlist_manager._playlist_cache = {}


def test_find_or_create_playlist_uses_cache():
    """Playlist em cache e retornada sem buscar na API."""
    playlist_manager._playlist_cache = {"Liquid Wire | Shorts": "PL123"}
    service = MagicMock()
    pid = playlist_manager._find_or_create_playlist(service, "Liquid Wire | Shorts")
    assert pid == "PL123"
    service.playlists().list.assert_not_called()


def test_find_or_create_playlist_searches_existing():
    """Playlist encontrada na API e adicionada ao cache."""
    service = MagicMock()
    service.playlists().list().execute.return_value = {
        "items": [{"id": "PL456", "snippet": {"title": "Liquid Wire | Shorts"}}],
        "nextPageToken": "",
    }
    with patch("utils.playlist_manager._save_cache"):
        pid = playlist_manager._find_or_create_playlist(service, "Liquid Wire | Shorts")
    assert pid == "PL456"
    assert playlist_manager._playlist_cache["Liquid Wire | Shorts"] == "PL456"


def test_find_or_create_playlist_creates_new():
    """Playlist nao encontrada e criada via API."""
    service = MagicMock()
    service.playlists().list().execute.return_value = {"items": [], "nextPageToken": ""}
    service.playlists().insert().execute.return_value = {"id": "PL789"}
    with patch("utils.playlist_manager._save_cache"):
        pid = playlist_manager._find_or_create_playlist(service, "Liquid Wire | Shorts")
    assert pid == "PL789"
    assert playlist_manager._playlist_cache["Liquid Wire | Shorts"] == "PL789"


def test_find_or_create_playlist_handles_api_error():
    """Erro na API (busca e criacao) retorna string vazia sem quebrar."""
    service = MagicMock()
    service.playlists().list.side_effect = Exception("API down")
    service.playlists().insert.side_effect = Exception("API down")
    with patch("utils.playlist_manager._save_cache"):
        pid = playlist_manager._find_or_create_playlist(service, "Liquid Wire | Shorts")
    assert pid == ""


def test_add_video_to_playlist_no_target():
    """Mood/kind invalidos nao fazem nada."""
    service = MagicMock()
    playlist_manager.add_video_to_playlist(service, "vid1", mood="unknown", kind="unknown")
    service.playlistItems().insert.assert_not_called()


def test_add_video_to_playlist_by_kind():
    """Adiciona video a playlist por kind."""
    playlist_manager._playlist_cache = {"Liquid Wire | Shorts": "PL1"}
    service = MagicMock()
    playlist_manager.add_video_to_playlist(service, "vid1", kind="short")
    service.playlistItems().insert.assert_called_once()


def test_add_video_to_playlist_no_pid():
    """Se playlist nao pode ser criada, nao insere."""
    service = MagicMock()
    service.playlists().list().execute.return_value = {"items": [], "nextPageToken": ""}
    service.playlists().insert().execute.side_effect = Exception("quota")
    with patch("utils.playlist_manager._save_cache"):
        playlist_manager.add_video_to_playlist(service, "vid1", kind="short")
    service.playlistItems().insert.assert_not_called()


def test_load_cache_invalid_json():
    """Cache invalido e ignorado sem quebrar."""
    fake_file = MagicMock()
    fake_file.exists.return_value = True
    fake_file.read_text.return_value = "not json"
    with patch("utils.playlist_manager._cache_file", return_value=fake_file):
        playlist_manager._load_cache()
    assert playlist_manager._playlist_cache == {}


def test_add_video_to_playlist_api_error_logs(tmp_path, monkeypatch):
    """Erro ao inserir item e logado; nao propaga excecao."""
    playlist_manager._playlist_cache = {"Liquid Wire | Shorts": "PL1"}
    service = MagicMock()
    called_with: list[dict] = []

    class _FakeInsert:
        def __init__(self, **kw):
            called_with.append(kw)

        def execute(self):
            raise Exception("quota")

    service.playlistItems.return_value.insert = _FakeInsert
    with patch("utils.playlist_manager._save_cache"):
        playlist_manager.add_video_to_playlist(service, "vid1", kind="short")
    assert len(called_with) == 1
    assert called_with[0]["part"] == "snippet"


def test_find_or_create_playlist_pagination(monkeypatch):
    """Busca percorre multiplas paginas ate achar a playlist."""
    service = MagicMock()
    service.playlists().list().execute.side_effect = [
        {"items": [{"id": "PL1", "snippet": {"title": "Outra"}}], "nextPageToken": "TOKEN1"},
        {"items": [{"id": "PL2", "snippet": {"title": "Liquid Wire | Shorts"}}], "nextPageToken": ""},
    ]
    with patch("utils.playlist_manager._save_cache") as mock_save:
        pid = playlist_manager._find_or_create_playlist(service, "Liquid Wire | Shorts")
    assert pid == "PL2"
    assert mock_save.called
