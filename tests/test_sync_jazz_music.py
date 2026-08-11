"""Testes para scripts/sync_jazz_music.py - sem I/O real."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import scripts.sync_jazz_music as sync_jazz_music


class TestEvictOldest:
    def test_removes_oldest_files_and_their_metadata(self, tmp_path):
        import os
        import time

        paths = []
        for i in range(5):
            p = tmp_path / f"track{i}.mp3"
            p.write_bytes(b"x")
            (tmp_path / f"track{i}.json").write_text("{}", encoding="utf-8")
            paths.append(p)
            # Garante mtimes distintos e crescentes (track0 = mais antigo).
            t = time.time() + i
            os.utime(p, (t, t))

        evicted = sync_jazz_music._evict_oldest(tmp_path, "*.mp3", 2)

        assert evicted == 2
        assert not (tmp_path / "track0.mp3").exists()
        assert not (tmp_path / "track0.json").exists()
        assert not (tmp_path / "track1.mp3").exists()
        assert (tmp_path / "track2.mp3").exists()
        assert (tmp_path / "track4.mp3").exists()

    def test_zero_count_removes_nothing(self, tmp_path):
        (tmp_path / "track0.mp3").write_bytes(b"x")
        assert sync_jazz_music._evict_oldest(tmp_path, "*.mp3", 0) == 0
        assert (tmp_path / "track0.mp3").exists()

    def test_missing_metadata_does_not_raise(self, tmp_path):
        (tmp_path / "track0.mp3").write_bytes(b"x")  # sem .json correspondente
        assert sync_jazz_music._evict_oldest(tmp_path, "*.mp3", 1) == 1


class TestIsJazz:
    @pytest.mark.parametrize(
        "hit,expected",
        [
            ({"name": "Smooth Jazz Night"}, True),
            ({"artist_name": "Jazz Quartet"}, True),
            ({"tags": "bossa nova"}, True),
            ({"musicinfo": {"tags": {"genres": ["jazz"]}}}, True),
            # Jazz animado (mood "diversao") - tags/nome nem sempre repetem "jazz".
            ({"name": "Bebop Nights"}, True),
            ({"tags": "swing upbeat"}, True),
            ({"artist_name": "Fusion Trio"}, True),
            # Lofi jazz (mood "fofura"/"relax").
            ({"tags": "lofi chill beats"}, True),
            ({"name": "Rock Anthem"}, False),
            ({"name": "EDM Dance Hit"}, False),
            ({"name": ""}, False),
            ({}, False),
        ],
    )
    def test_is_jazz(self, hit, expected):
        assert sync_jazz_music._is_jazz(hit) is expected


class TestClientId:
    def test_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("JAMENDO_CLIENT_ID", "my-id")
        assert sync_jazz_music._client_id() == "my-id"

    def test_returns_empty_when_not_set(self, monkeypatch):
        monkeypatch.delenv("JAMENDO_CLIENT_ID", raising=False)
        assert sync_jazz_music._client_id() == ""


class TestSearchAndDownload:
    def _hit(self, name="track", audio="https://x/y.mp3", hid="1", tags="jazz", artist="Jazz Artist"):
        return {
            "name": name,
            "artist_name": artist,
            "audio": audio,
            "audio_download": None,
            "id": hid,
            "tags": tags,
        }

    @patch("scripts.sync_jazz_music._download", return_value=True)
    @patch("scripts.sync_jazz_music.requests.get")
    def test_success_downloads_jazz_hits(self, mock_get, mock_download, monkeypatch):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"results": [self._hit(), self._hit(name="t2", hid="2")]}
        mock_get.return_value = mock_response

        monkeypatch.setattr(sync_jazz_music, "AUDIO_DIR", MagicMock())
        sync_jazz_music.AUDIO_DIR.__truediv__ = lambda self, other: MagicMock(
            exists=lambda: False,
            with_suffix=lambda s: MagicMock(),
        )

        assert sync_jazz_music.search_and_download("jazz", max_results=5, client_id="id") == 2
        assert mock_download.call_count == 2

    @patch("scripts.sync_jazz_music._download", return_value=True)
    @patch("scripts.sync_jazz_music.requests.get")
    def test_network_error_returns_zero(self, mock_get, mock_download):
        import requests

        mock_get.side_effect = requests.exceptions.ConnectionError("boom")

        assert sync_jazz_music.search_and_download("jazz", client_id="id") == 0
        mock_download.assert_not_called()

    @patch("scripts.sync_jazz_music._download", return_value=True)
    @patch("scripts.sync_jazz_music.requests.get")
    def test_no_results_returns_zero(self, mock_get, mock_download):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        assert sync_jazz_music.search_and_download("jazz", client_id="id") == 0
        mock_download.assert_not_called()

    @patch("scripts.sync_jazz_music._download", return_value=True)
    @patch("scripts.sync_jazz_music.requests.get")
    def test_skips_non_jazz_hits(self, mock_get, mock_download, monkeypatch):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"results": [self._hit(name="rock", tags="rock", artist="Rock Band")]}
        mock_get.return_value = mock_response
        monkeypatch.setattr(sync_jazz_music, "AUDIO_DIR", MagicMock())
        sync_jazz_music.AUDIO_DIR.__truediv__ = lambda self, other: MagicMock(
            exists=lambda: False,
            with_suffix=lambda s: MagicMock(),
        )

        assert sync_jazz_music.search_and_download("jazz", client_id="id") == 0
        mock_download.assert_not_called()


class TestDownload:
    def test_success(self, tmp_path, monkeypatch):
        dest = tmp_path / "out.mp3"
        fake_resp = MagicMock()
        fake_resp.raise_for_status.return_value = None
        chunks = [b"abc", b"def"]

        def _iter_content(chunk_size=8192):
            yield from chunks

        fake_resp.iter_content = _iter_content
        fake_resp.__enter__ = lambda self: self
        fake_resp.__exit__ = lambda self, *a: False

        monkeypatch.setattr(sync_jazz_music.requests, "get", lambda *a, **k: fake_resp)
        assert sync_jazz_music._download("https://x/y.mp3", dest) is True
        assert dest.read_bytes() == b"abcdef"

    def test_failure_3x(self, tmp_path, monkeypatch):
        dest = tmp_path / "out.mp3"
        monkeypatch.setattr(sync_jazz_music.requests, "get", MagicMock(side_effect=ConnectionError("boom")))
        # Acelera os sleeps entre retries
        monkeypatch.setattr("time.sleep", lambda s: None)
        assert sync_jazz_music._download("https://x/y.mp3", dest) is False
        assert not dest.exists()

    def test_timeout(self, tmp_path, monkeypatch):
        import requests

        dest = tmp_path / "out.mp3"
        monkeypatch.setattr(sync_jazz_music.requests, "get", MagicMock(side_effect=requests.exceptions.Timeout("slow")))
        monkeypatch.setattr("time.sleep", lambda s: None)
        assert sync_jazz_music._download("https://x/y.mp3", dest) is False


class TestMain:
    def test_no_client_id_returns_1(self, monkeypatch):
        monkeypatch.delenv("JAMENDO_CLIENT_ID", raising=False)
        monkeypatch.setattr(sync_jazz_music, "configure_logging", lambda: None)
        assert sync_jazz_music.main() == 1

    def test_pool_full_evicts_oldest_and_continues(self, monkeypatch, tmp_path):
        """Pool cheio nao e mais um no-op permanente: rotaciona as faixas
        mais antigas pra abrir espaco, depois segue pro sync normal - sem
        isso o pool congelava pra sempre nas mesmas 200 faixas."""
        monkeypatch.setenv("JAMENDO_CLIENT_ID", "id")
        monkeypatch.setattr(sync_jazz_music, "configure_logging", lambda: None)
        monkeypatch.setattr(sync_jazz_music, "ensure_dirs", lambda: None)
        # Pool cheio: 200 mp3s
        mp3s = [MagicMock() for _ in range(sync_jazz_music.MAX_POOL_SIZE)]
        monkeypatch.setattr(sync_jazz_music, "AUDIO_DIR", MagicMock())
        sync_jazz_music.AUDIO_DIR.glob = lambda *a, **k: iter(mp3s)
        with patch.object(sync_jazz_music, "_evict_oldest", return_value=20) as mock_evict:
            assert sync_jazz_music.main() == 0
        expected_evict = max(1, int(sync_jazz_music.MAX_POOL_SIZE * sync_jazz_music._POOL_ROTATION_FRACTION))
        mock_evict.assert_called_once_with(sync_jazz_music.AUDIO_DIR, "*.mp3", expected_evict)

    def test_normal_search_path(self, monkeypatch):
        monkeypatch.setenv("JAMENDO_CLIENT_ID", "id")
        monkeypatch.setattr(sync_jazz_music, "configure_logging", lambda: None)
        monkeypatch.setattr(sync_jazz_music, "ensure_dirs", lambda: None)
        monkeypatch.setattr(sync_jazz_music, "AUDIO_DIR", MagicMock())
        sync_jazz_music.AUDIO_DIR.glob = lambda *a, **k: iter([])  # pool vazio
        # search_and_download retorna 2 por termo
        monkeypatch.setattr(sync_jazz_music, "search_and_download", lambda *a, **k: 2)
        assert sync_jazz_music.main() == 0

    def test_normal_search_breaks_when_pool_fills(self, monkeypatch):
        monkeypatch.setenv("JAMENDO_CLIENT_ID", "id")
        monkeypatch.setattr(sync_jazz_music, "configure_logging", lambda: None)
        monkeypatch.setattr(sync_jazz_music, "ensure_dirs", lambda: None)
        monkeypatch.setattr(sync_jazz_music, "AUDIO_DIR", MagicMock())
        # Primeira chamada retorna pool vazio, segunda retorna pool cheio
        calls = {"n": 0}

        def _glob(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                return iter([])
            return iter([MagicMock() for _ in range(sync_jazz_music.MAX_POOL_SIZE)])

        sync_jazz_music.AUDIO_DIR.glob = _glob
        monkeypatch.setattr(sync_jazz_music, "search_and_download", lambda *a, **k: 2)
        with patch.object(sync_jazz_music, "_evict_oldest", return_value=4):
            assert sync_jazz_music.main() == 0
