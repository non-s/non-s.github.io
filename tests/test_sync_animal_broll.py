"""Testes para scripts/sync_animal_broll.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import scripts.sync_animal_broll as sync_animal_broll
from scripts.sync_animal_broll import _safe_name


def _fake_video_dir_truediv(self, other):
    return MagicMock(
        exists=lambda: False,
        with_suffix=lambda s: MagicMock(),
    )


def _hit(width=1280, height=720, tags="cute cat real", video_type="film", url="https://cdn.example/cat.mp4"):
    return {
        "tags": tags,
        "user": "someone",
        "pageURL": "https://pixabay.com/videos/cute-cat-1",
        "type": video_type,
        "likes": 10,
        "videos": {"large": {"url": url, "width": width, "height": height}},
    }


class TestSafeName:
    def test_basic(self):
        name = _safe_name("Cute Cat Real", 3, "https://cdn.example/x.mp4", "mp4")
        assert name.startswith("cute_cat_real_03_")
        assert name.endswith(".mp4")

    def test_lowercases_and_replaces(self):
        name = _safe_name("Dog & Cat!", 0, "https://x/y", "webm")
        assert name.startswith("dog___cat__00_")
        assert name.endswith(".webm")

    def test_different_urls_produce_different_hashes(self):
        n1 = _safe_name("q", 0, "https://a", "mp4")
        n2 = _safe_name("q", 0, "https://b", "mp4")
        assert n1 != n2


class TestBlockedFilters:
    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_blocks_cartoon(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit(tags="cute cat cartoon", video_type="film")]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5) == 0
        mock_download.assert_not_called()

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_blocks_animation_type(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit(tags="cute cat real", video_type="animation")]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5) == 0
        mock_download.assert_not_called()

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_blocks_ai_generated(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit(tags="ai generated cat")]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5) == 0
        mock_download.assert_not_called()


class TestExistingSkip:
    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_existing_file_skips_download(self, mock_get, mock_video_dir, mock_download):
        # O destino já existe -> não baixa
        mock_video_dir.__truediv__ = lambda self, other: MagicMock(
            exists=lambda: True,
            with_suffix=lambda s: MagicMock(),
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit()]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5) == 0
        mock_download.assert_not_called()


class TestOrientation:
    """Canal e 100% Shorts verticais - crop_filter em video_builder so e
    no-op pra clipe ja vertical; clipe horizontal perde ~68% da largura no
    crop central. search_and_download deve buscar vertical por padrao."""

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_default_orientation_is_vertical(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit()]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5)

        assert mock_get.call_args.kwargs["params"]["orientation"] == "vertical"

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_orientation_param_is_forwarded(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit()]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5, orientation="horizontal")

        assert mock_get.call_args.kwargs["params"]["orientation"] == "horizontal"

    def test_main_mixes_vertical_and_horizontal_orientations(self, monkeypatch):
        """1 a cada 3 queries busca horizontal (fallback de oferta), o
        resto busca vertical - garante que main() nao fique 100% preso a
        uma unica orientacao (nem some com a horizontal como fallback)."""
        monkeypatch.setenv("PIXABAY_API_KEY", "key")
        monkeypatch.setattr(sync_animal_broll, "configure_logging", lambda: None)
        monkeypatch.setattr(sync_animal_broll, "ensure_dirs", lambda: None)
        monkeypatch.setattr(sync_animal_broll, "VIDEO_DIR", MagicMock())
        sync_animal_broll.VIDEO_DIR.glob = lambda *a, **k: iter([])

        seen_orientations = []

        def _fake_search(api_key, query, max_results, orientation="vertical"):
            seen_orientations.append(orientation)
            return 0

        monkeypatch.setattr(sync_animal_broll, "search_and_download", _fake_search)
        assert sync_animal_broll.main() == 0

        assert "vertical" in seen_orientations
        assert "horizontal" in seen_orientations


class TestResolutionFilter:
    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_accepts_genuinely_vertical_hit(self, mock_get, mock_video_dir, mock_download):
        """Um clipe vertical legitimo (480x854) tem width < MIN_WIDTH mas e
        boa resolucao - so orientado diferente. O filtro compara por lado
        maior/menor, nao w/h direto, entao nao deve rejeitar."""
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit(width=480, height=854)]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        downloaded = sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5)

        assert downloaded == 1
        mock_download.assert_called_once()

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_rejects_low_resolution_vertical_hit(self, mock_get, mock_video_dir, mock_download):
        """Vertical mas realmente baixa resolucao (180x320) ainda deve ser
        rejeitado - o lado maior (320) fica abaixo de MIN_WIDTH (640)."""
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit(width=180, height=320)]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        downloaded = sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5)

        assert downloaded == 0
        mock_download.assert_not_called()

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_rejects_low_resolution_hit(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit(width=320, height=180)]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        downloaded = sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5)

        assert downloaded == 0
        mock_download.assert_not_called()

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_accepts_normal_resolution_hit(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [_hit(width=1280, height=720)]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        downloaded = sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5)

        assert downloaded == 1
        mock_download.assert_called_once()

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_missing_dimensions_does_not_block(self, mock_get, mock_video_dir, mock_download):
        """Campos width/height ausentes (API mudou/hit incompleto) nao devem
        bloquear o clip - so pula a checagem de resolucao."""
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        hit = _hit()
        hit["videos"]["large"] = {"url": "https://cdn.example/cat.mp4"}
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [hit]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        downloaded = sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5)

        assert downloaded == 1


class TestSearchEdgeCases:
    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_network_error_returns_zero(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        mock_get.side_effect = ConnectionError("boom")
        assert sync_animal_broll.search_and_download("fake-key", "cute cat real") == 0

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_falls_back_to_medium_then_small(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        hit = _hit()
        del hit["videos"]["large"]
        hit["videos"]["medium"] = {"url": "https://cdn.example/m.mp4", "width": 1280, "height": 720}
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [hit]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5) == 1

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_no_video_variants_skips(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        hit = _hit()
        hit["videos"] = {}
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [hit]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5) == 0

    @patch("scripts.sync_animal_broll._download_video", return_value=True)
    @patch("scripts.sync_animal_broll.VIDEO_DIR")
    @patch("scripts.sync_animal_broll.requests.get")
    def test_bad_extension_defaults_mp4(self, mock_get, mock_video_dir, mock_download):
        mock_video_dir.__truediv__ = _fake_video_dir_truediv
        hit = _hit(url="https://cdn.example/cat.xyz")
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": [hit]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        assert sync_animal_broll.search_and_download("fake-key", "cute cat real", max_results=5) == 1
        # Verifica que o nome gerado usa mp4
        called_dest = mock_download.call_args.args[1]
        # _fake_video_dir_truediv retorna MagicMock, entao so confirma que chamou
        assert mock_download.call_count == 1


class TestDownloadVideo:
    def test_success(self, tmp_path, monkeypatch):
        dest = tmp_path / "v.mp4"
        fake_resp = MagicMock()
        fake_resp.raise_for_status.return_value = None

        def _iter_content(chunk_size=8192):
            yield b"chunk1"
            yield b"chunk2"

        fake_resp.iter_content = _iter_content
        fake_resp.__enter__ = lambda self: self
        fake_resp.__exit__ = lambda self, *a: False
        monkeypatch.setattr(sync_animal_broll.requests, "get", lambda *a, **k: fake_resp)
        assert sync_animal_broll._download_video("https://x", dest) is True
        assert dest.read_bytes() == b"chunk1chunk2"

    def test_failure_returns_false(self, tmp_path, monkeypatch):
        dest = tmp_path / "v.mp4"
        monkeypatch.setattr(sync_animal_broll.requests, "get", MagicMock(side_effect=ConnectionError("boom")))
        assert sync_animal_broll._download_video("https://x", dest) is False
        assert not dest.exists()


class TestMain:
    def test_no_api_key_returns_1(self, monkeypatch):
        monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
        monkeypatch.setattr(sync_animal_broll, "configure_logging", lambda: None)
        assert sync_animal_broll.main() == 1

    def test_pool_full_evicts_oldest_and_continues(self, monkeypatch):
        """Pool cheio nao e mais um no-op permanente: rotaciona os clips
        mais antigos pra abrir espaco, depois segue pro sync normal - sem
        isso o pool congelava pra sempre nos mesmos 300 clips."""
        monkeypatch.setenv("PIXABAY_API_KEY", "key")
        monkeypatch.setattr(sync_animal_broll, "configure_logging", lambda: None)
        monkeypatch.setattr(sync_animal_broll, "ensure_dirs", lambda: None)
        mp4s = [MagicMock() for _ in range(sync_animal_broll.MAX_POOL_SIZE)]
        monkeypatch.setattr(sync_animal_broll, "VIDEO_DIR", MagicMock())
        sync_animal_broll.VIDEO_DIR.glob = lambda *a, **k: iter(mp4s)
        with patch.object(sync_animal_broll, "_evict_oldest", return_value=30) as mock_evict:
            assert sync_animal_broll.main() == 0
        expected_evict = max(1, int(sync_animal_broll.MAX_POOL_SIZE * sync_animal_broll._POOL_ROTATION_FRACTION))
        mock_evict.assert_called_once_with(sync_animal_broll.VIDEO_DIR, "*.mp4", expected_evict)

    def test_normal_path(self, monkeypatch):
        monkeypatch.setenv("PIXABAY_API_KEY", "key")
        monkeypatch.setattr(sync_animal_broll, "configure_logging", lambda: None)
        monkeypatch.setattr(sync_animal_broll, "ensure_dirs", lambda: None)
        monkeypatch.setattr(sync_animal_broll, "VIDEO_DIR", MagicMock())
        sync_animal_broll.VIDEO_DIR.glob = lambda *a, **k: iter([])  # pool vazio
        monkeypatch.setattr(sync_animal_broll, "search_and_download", lambda *a, **k: 3)
        assert sync_animal_broll.main() == 0
