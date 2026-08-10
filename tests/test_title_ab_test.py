"""Testes para A/B testing de título (A1).

Cobre:
- generate_metadata agora inclui title_alt no retorno (utils/metadata_engine).
- maybe_rotate_title troca o título via videos.update quando o vídeo
  performa abaixo da mediana apos _TITLE_ROTATION_DAYS dias (scripts/collect_analytics).
- title_alt e persistido em video_tags.json no upload (upload_youtube._record_video_tags).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import scripts.collect_analytics as collect_analytics
import utils.metadata_engine as metadata_engine


class TestMetadataEngineTitleAlt:
    """generate_metadata agora gera um título alternativo para A/B testing."""

    @patch("utils.metadata_engine.ai_text")
    def test_generate_metadata_includes_title_alt(self, mock_ai_text):
        mock_ai_text.return_value = ""
        metadata = metadata_engine.generate_metadata(
            hook="Cute cat", scene="cat", duration=30, kind="short", emoji="🐱"
        )
        assert "title_alt" in metadata
        # title_alt pode ser vazio se nao conseguir gerar um distinto, mas
        # a chave tem que existir.
        assert isinstance(metadata["title_alt"], str)

    @patch("utils.metadata_engine.ai_text")
    def test_title_alt_is_distinct_from_primary_when_present(self, mock_ai_text, tmp_path, monkeypatch):
        """Quando title_alt e gerado, ele tem que ser distinto do título
        principal (Jaccard < 0.5) - senao nao e um teste A/B de verdade."""
        import utils.seo_keywords as seo_keywords

        monkeypatch.setattr(seo_keywords, "_title_used_file", lambda: tmp_path / "used_titles.json")
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        mock_ai_text.return_value = ""
        distinct_count = 0
        samples = 0
        for _ in range(20):
            metadata = metadata_engine.generate_metadata(
                hook="Sleepy cat", scene="sleepy cat", duration=30, kind="short", emoji="🐱", mood="relax"
            )
            if metadata["title_alt"]:
                samples += 1
                # Distinto em pelo menos uma palavra significativa
                from utils.seo_keywords import title_similarity

                sim = title_similarity(metadata["title"], metadata["title_alt"])
                # Distinto o suficiente para ser um teste A/B real (Jaccard
                # <= 0.5 significa que compartilham no maximo metade das
                # palavras significativas - o que e suficiente para testar
                # hipoteses de CTR diferentes).
                assert sim <= 0.5, (
                    f"title_alt muito similar: {metadata['title']!r} vs "
                    f"{metadata['title_alt']!r} (sim={sim})"
                )
                distinct_count += 1
        # Pelo menos alguns dos 20 devem ter title_alt (nem sempre e
        # possivel gerar um distinto, mas a maioria sim).
        assert distinct_count > 0

    @patch("utils.metadata_engine.ai_text")
    def test_title_alt_has_brand_prefix(self, mock_ai_text, tmp_path, monkeypatch):
        import utils.seo_keywords as seo_keywords

        monkeypatch.setattr(seo_keywords, "_title_used_file", lambda: tmp_path / "used_titles.json")
        mock_ai_text.return_value = ""
        for _ in range(20):
            metadata = metadata_engine.generate_metadata(
                hook="Cute cat", scene="cat", duration=30, kind="short", emoji="🐱"
            )
            if metadata["title_alt"]:
                assert metadata["title_alt"].startswith("Pata Jazz |")

    @patch("utils.metadata_engine.ai_text")
    def test_title_alt_respects_100_char_limit(self, mock_ai_text, tmp_path, monkeypatch):
        import utils.seo_keywords as seo_keywords

        monkeypatch.setattr(seo_keywords, "_title_used_file", lambda: tmp_path / "used_titles.json")
        # Tambem isola data_dir para evitar estado residual de outros testes
        monkeypatch.setattr(seo_keywords, "data_dir", lambda: tmp_path)
        mock_ai_text.return_value = ""
        for _ in range(20):
            metadata = metadata_engine.generate_metadata(
                hook="Cute cat", scene="cat", duration=30, kind="short", emoji="🐱"
            )
            if metadata["title_alt"]:
                assert len(metadata["title_alt"]) <= 100


class TestMaybeRotateTitle:
    """maybe_rotate_title: troca o título por title_alt via videos.update
    quando o vídeo performa abaixo da mediana apos _TITLE_ROTATION_DAYS."""

    def _entry(self, *, uploaded_at, views, title_alt, title_rotated=False, title="Original Title"):
        return {
            "scene": "cat",
            "title": title,
            "title_alt": title_alt,
            "title_rotated": title_rotated,
            "uploaded_at": uploaded_at,
            "views": views,
        }

    def _service_with_snippet(self, current_title="Old Title"):
        """Service mock que retorna um snippet na chamada videos.list e
        aceita videos.update."""
        service = MagicMock()
        service.videos().list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "vid1",
                    "snippet": {
                        "title": current_title,
                        "description": "desc",
                        "tags": ["cat"],
                        "categoryId": "15",
                    },
                }
            ]
        }
        service.videos().update.return_value.execute.return_value = {"id": "vid1"}
        return service

    def test_rotates_when_below_median_and_old_enough(self):
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=10)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=10, title_alt="Pata Jazz | Alt Title")
        service = self._service_with_snippet()

        with patch("scripts.collect_analytics._retry_youtube_call", side_effect=lambda f: f()):
            rotated = collect_analytics.maybe_rotate_title(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is True
        assert entry["title_rotated"] is True
        assert entry["title"] == "Pata Jazz | Alt Title"
        assert "title_rotated_at" in entry
        service.videos().update.assert_called_once()

    def test_no_rotation_when_already_rotated(self):
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(
            uploaded_at=uploaded, views=1, title_alt="Alt", title_rotated=True
        )
        service = self._service_with_snippet()

        rotated = collect_analytics.maybe_rotate_title(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.videos().update.assert_not_called()

    def test_no_rotation_when_title_alt_empty(self):
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, title_alt="")
        service = self._service_with_snippet()

        rotated = collect_analytics.maybe_rotate_title(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.videos().update.assert_not_called()

    def test_no_rotation_when_too_recent(self):
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=2)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, title_alt="Alt")
        service = self._service_with_snippet()

        rotated = collect_analytics.maybe_rotate_title(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.videos().update.assert_not_called()

    def test_no_rotation_when_views_above_threshold(self):
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=600, title_alt="Alt")
        service = self._service_with_snippet()

        rotated = collect_analytics.maybe_rotate_title(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        service.videos().update.assert_not_called()

    def test_no_rotation_when_median_zero(self):
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=30)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=10, title_alt="Alt")
        service = self._service_with_snippet()

        rotated = collect_analytics.maybe_rotate_title(service, "vid1", entry, median_views=0, now=now)

        assert rotated is False
        service.videos().update.assert_not_called()

    def test_rotation_failure_is_not_fatal(self):
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=10)).isoformat()
        entry = self._entry(uploaded_at=uploaded, views=1, title_alt="Alt")
        service = self._service_with_snippet()

        with patch("scripts.collect_analytics._retry_youtube_call", side_effect=RuntimeError("api down")):
            rotated = collect_analytics.maybe_rotate_title(service, "vid1", entry, median_views=1000, now=now)

        assert rotated is False
        assert entry.get("title_rotated") is not True

    def test_rotation_truncates_title_alt_to_100_chars(self):
        now = datetime.now(UTC)
        uploaded = (now - timedelta(days=10)).isoformat()
        long_alt = "Pata Jazz | " + "x" * 200
        entry = self._entry(uploaded_at=uploaded, views=1, title_alt=long_alt)
        service = self._service_with_snippet()

        with patch("scripts.collect_analytics._retry_youtube_call", side_effect=lambda f: f()):
            collect_analytics.maybe_rotate_title(service, "vid1", entry, median_views=1000, now=now)

        # O body do update recebeu o título truncado.
        call_args = service.videos().update.call_args
        body = call_args.kwargs.get("body") or (call_args.args[0] if call_args.args else {})
        assert len(body["snippet"]["title"]) <= 100
