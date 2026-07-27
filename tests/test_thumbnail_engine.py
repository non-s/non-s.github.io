"""Testes para thumbnail_engine.py."""
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

import utils.thumbnail_engine as thumbnail_engine
from utils.thumbnail_engine import (
    _LayoutConfig,
    _render_thumbnail,
    create_gradient_background,
    enhance_thumbnail_image,
)


def test_hex_to_rgb():
    """Converte cores hex da paleta em tuplas RGB válidas."""
    assert thumbnail_engine._hex_to_rgb("#f4a261") == (244, 162, 97)
    assert thumbnail_engine._hex_to_rgb("0f0f23") == (15, 15, 35)


def test_create_gradient_background():
    img = create_gradient_background(64, 32)
    assert img.size == (64, 32)
    assert img.mode == "RGB"


def test_enhance_thumbnail_image():
    img = Image.new("RGB", (32, 32), (100, 100, 100))
    out = enhance_thumbnail_image(img)
    assert out.size == (32, 32)


def test_load_fonts_failure():
    with patch("utils.thumbnail_engine.ImageFont.truetype", side_effect=OSError("no font")):
        with pytest.raises(RuntimeError, match="fonte|TrueType"):
            thumbnail_engine._load_fonts()


class TestThumbnailEngineRealRender:
    """Renderiza com Pillow de verdade (sem mocks) para pegar erros de tipo
    que os testes mockados abaixo não conseguem detectar, ex.: cores mal
    formadas passadas para ImageDraw."""

    def test_make_horizontal_thumbnail_real_render(self, tmp_path):
        output = tmp_path / "horizontal.png"
        thumbnail_engine.make_horizontal_thumbnail(
            hook="Gatinhos Fofos", emoji="🐱", output=output, brand="Pata Jazz"
        )
        assert output.exists()
        assert output.stat().st_size > 0

    def test_make_short_thumbnail_real_render(self, tmp_path):
        output = tmp_path / "short.png"
        thumbnail_engine.make_short_thumbnail(
            hook="Meow Monday", emoji="🎷", output=output, brand="Pata Jazz"
        )
        assert output.exists()
        assert output.stat().st_size > 0


class TestThumbnailVariantB:
    """Variante B para A/B testing: paleta com accent trocado (#e76f51 em
    vez de #f4a261) e hook com wrap width menor (texto maior)."""

    def test_variant_b_renders_real(self, tmp_path):
        out_a = tmp_path / "thumb_a.png"
        out_b = tmp_path / "thumb_b.png"
        thumbnail_engine.make_short_thumbnail(
            hook="Meow Monday", emoji="🎷", output=out_a, variant="A"
        )
        thumbnail_engine.make_short_thumbnail(
            hook="Meow Monday", emoji="🎷", output=out_b, variant="B"
        )
        assert out_a.exists() and out_a.stat().st_size > 0
        assert out_b.exists() and out_b.stat().st_size > 0

    def test_variant_b_uses_alternate_palette(self):
        assert thumbnail_engine._palette_for("A") is thumbnail_engine.PALETTE
        assert thumbnail_engine._palette_for("B") is thumbnail_engine.PALETTE_B
        assert thumbnail_engine.PALETTE_B["accent"] == "#e76f51"
        assert thumbnail_engine.PALETTE["accent"] == "#f4a261"

    def test_variant_b_gradient_is_inverted(self):
        """Variante B inverte gradiente (start/end trocados) pra dar outro
        impacto visual - garante que PALETTE_B realmente e diferente da A."""
        bg_a = create_gradient_background(64, 32)
        bg_b = create_gradient_background(64, 32, thumbnail_engine.PALETTE_B)
        # Pixel superior (gradient_start) deve ser diferente entre A e B.
        assert bg_a.getpixel((0, 0)) != bg_b.getpixel((0, 0))

    @patch("utils.thumbnail_engine.ImageDraw")
    @patch("utils.thumbnail_engine._save_under_2mb")
    @patch("utils.thumbnail_engine._fonts_for_variant", return_value=(MagicMock(), MagicMock()))
    @patch("utils.thumbnail_engine.extract_frame_from_video", return_value=None)
    def test_variant_b_passes_palette_b_to_render(self, mock_extract, mock_fonts, mock_save, mock_draw, tmp_path):
        """_render_thumbnail com variant='B' deve usar PALETTE_B - captura o
        fill do emoji principal e confirma que e accent de B (#e76f51)."""
        captured_fills: list = []
        draw_instance = mock_draw.Draw.return_value
        draw_instance.text.side_effect = lambda *a, **kw: captured_fills.append(kw.get("fill"))
        out_path = tmp_path / "b.png"
        cfg = _LayoutConfig(
            border_margin=60, border_radius=60, border_width=6,
            emoji_y=520, emoji_shadow_offset=(6, 6),
            hook_y_start=760, hook_wrap_width=18, hook_line_height=90,
            brand_y=1700, crop_target_ratio=1080 / 1920,
            overlay_alpha=100, frame_timestamp="00:00:01",
        )
        _render_thumbnail(1080, 1920, "hook", "🐱", out_path, "brand", None, cfg, variant="B")
        # O fill do emoji principal (nao a shadow) e PALETTE_B["accent"].
        assert thumbnail_engine.PALETTE_B["accent"] in {str(f) for f in captured_fills if isinstance(f, str)}


class TestThumbnailVariantC:
    """Variante C: hook truncado (texto menor) + emoji gigante (fonte 2x maior).
    Mesma paleta de A para nao competir em cores, mas impacto visual diferente
    via escala do emoji."""

    def test_variant_c_renders_real(self, tmp_path):
        out_a = tmp_path / "thumb_a.png"
        out_c = tmp_path / "thumb_c.png"
        thumbnail_engine.make_short_thumbnail(
            hook="Meow Monday", emoji="🎷", output=out_a, variant="A"
        )
        thumbnail_engine.make_short_thumbnail(
            hook="Meow Monday", emoji="🎷", output=out_c, variant="C"
        )
        assert out_a.exists() and out_a.stat().st_size > 0
        assert out_c.exists() and out_c.stat().st_size > 0

    def test_variant_c_uses_palette_c(self):
        assert thumbnail_engine._palette_for("C") is thumbnail_engine.PALETTE_C
        # Paleta C mantem o accent default (nao troca cor, so escala do emoji).
        assert thumbnail_engine.PALETTE_C["accent"] == thumbnail_engine.PALETTE["accent"]

    def test_variant_c_uses_larger_emoji_font(self, tmp_path):
        """Variante C usa emoji 2x maior (240 vs 120) - verifica via mock."""
        with patch("utils.thumbnail_engine._load_font_path", return_value="arial.ttf"), \
             patch("utils.thumbnail_engine.ImageFont.truetype") as mock_truetype:
            mock_truetype.side_effect = lambda path, size: MagicMock(size=size)
            font_large, font_small = thumbnail_engine._fonts_for_variant("C")
            # font_large deve ser 240 (2x do default 120).
            assert font_large.size == 240
            # font_small menor que o default 48.
            assert font_small.size < 48

    def test_variant_a_uses_default_font_sizes(self, tmp_path):
        with patch("utils.thumbnail_engine._load_font_path", return_value="arial.ttf"), \
             patch("utils.thumbnail_engine.ImageFont.truetype") as mock_truetype:
            mock_truetype.side_effect = lambda path, size: MagicMock(size=size)
            font_large, font_small = thumbnail_engine._fonts_for_variant("A")
            assert font_large.size == 120
            assert font_small.size == 48


class TestThumbnailEngine:
    """Testes para thumbnail_engine."""

    @patch('PIL.Image.new')
    @patch('utils.thumbnail_engine.ImageDraw')
    @patch('utils.thumbnail_engine.ImageFont')
    def test_make_horizontal_thumbnail(self, mock_font, mock_draw, mock_image, tmp_path):
        """Testa criação de thumbnail horizontal."""
        mock_img = MagicMock()
        mock_image.return_value = mock_img
        mock_draw_instance = MagicMock()
        mock_draw.Draw.return_value = mock_draw_instance
        mock_font.truetype.return_value = MagicMock()

        output = tmp_path / "test_thumb.png"

        # Não deve levantar exceção
        thumbnail_engine.make_horizontal_thumbnail(
            hook="Gatinhos Fofos",
            emoji="🐱",
            output=output,
            brand="Pata Jazz"
        )

        mock_image.assert_called()

    @patch('PIL.Image.new')
    @patch('utils.thumbnail_engine.ImageDraw')
    @patch('utils.thumbnail_engine.ImageFont')
    def test_make_short_thumbnail(self, mock_font, mock_draw, mock_image, tmp_path):
        """Testa criação de thumbnail vertical (Short)."""
        mock_img = MagicMock()
        mock_image.return_value = mock_img
        mock_draw_instance = MagicMock()
        mock_draw.Draw.return_value = mock_draw_instance
        mock_font.truetype.return_value = MagicMock()

        output = tmp_path / "test_short_thumb.png"

        # Não deve levantar exceção
        thumbnail_engine.make_short_thumbnail(
            hook="Meow Monday",
            emoji="🎷",
            output=output,
            brand="Pata Jazz"
        )

        mock_image.assert_called()


class TestRenderThumbnailWithVideo:
    def _cfg(self, width=1280, height=720):
        return _LayoutConfig(
            border_margin=40, border_radius=40, border_width=4,
            emoji_y=100, emoji_shadow_offset=(4, 4),
            hook_y_start=280, hook_wrap_width=22, hook_line_height=70,
            brand_y=height - 120, crop_target_ratio=None,
            overlay_alpha=128, frame_timestamp="00:00:02",
        )

    @patch("utils.thumbnail_engine.ImageDraw")
    @patch("utils.thumbnail_engine._save_under_2mb")
    @patch("utils.thumbnail_engine._fonts_for_variant", return_value=(MagicMock(), MagicMock()))
    @patch("utils.thumbnail_engine.extract_frame_from_video")
    def test_with_video_path_uses_frame(self, mock_extract, mock_fonts, mock_save, mock_draw, tmp_path):
        frame = Image.new("RGB", (640, 480), (10, 20, 30))
        mock_extract.return_value = frame
        vid = tmp_path / "vid.mp4"
        vid.write_bytes(b"fake")
        out = tmp_path / "thumb.png"
        _render_thumbnail(1280, 720, "hook", "🐱", out, "brand", vid, self._cfg())
        mock_extract.assert_called_once()
        mock_save.assert_called_once()

    @patch("utils.thumbnail_engine.ImageDraw")
    @patch("utils.thumbnail_engine._save_under_2mb")
    @patch("utils.thumbnail_engine._fonts_for_variant", return_value=(MagicMock(), MagicMock()))
    @patch("utils.thumbnail_engine.extract_frame_from_video")
    def test_without_video_path_uses_gradient(self, mock_extract, mock_fonts, mock_save, mock_draw, tmp_path):
        out = tmp_path / "thumb.png"
        _render_thumbnail(1280, 720, "hook", "🐱", out, "brand", None, self._cfg())
        mock_extract.assert_not_called()
        mock_save.assert_called_once()

    @patch("utils.thumbnail_engine.ImageDraw")
    @patch("utils.thumbnail_engine._save_under_2mb")
    @patch("utils.thumbnail_engine._fonts_for_variant", return_value=(MagicMock(), MagicMock()))
    @patch("utils.thumbnail_engine.extract_frame_from_video", return_value=None)
    def test_video_path_but_extraction_fails_falls_back_to_gradient(
        self, mock_extract, mock_fonts, mock_save, mock_draw, tmp_path
    ):
        vid = tmp_path / "vid.mp4"
        vid.write_bytes(b"fake")
        out = tmp_path / "thumb.png"
        _render_thumbnail(1280, 720, "hook", "🐱", out, "brand", vid, self._cfg())
        mock_extract.assert_called_once()
        mock_save.assert_called_once()

    @patch("utils.thumbnail_engine.ImageDraw")
    @patch("utils.thumbnail_engine._save_under_2mb")
    @patch("utils.thumbnail_engine._fonts_for_variant", return_value=(MagicMock(), MagicMock()))
    @patch("utils.thumbnail_engine.extract_frame_from_video")
    def test_with_crop_target_ratio(self, mock_extract, mock_fonts, mock_save, mock_draw, tmp_path):
        # frame muito largo (1920x480) com crop_target_ratio=9/16 -> corta laterais
        frame = Image.new("RGB", (1920, 480), (50, 60, 70))
        mock_extract.return_value = frame
        vid = tmp_path / "vid.mp4"
        vid.write_bytes(b"fake")
        cfg_dict = {
            "border_margin": 60, "border_radius": 60, "border_width": 6,
            "emoji_y": 520, "emoji_shadow_offset": (6, 6),
            "hook_y_start": 760, "hook_wrap_width": 18, "hook_line_height": 90,
            "brand_y": 1700, "crop_target_ratio": 1080 / 1920,
            "overlay_alpha": 100, "frame_timestamp": "00:00:01",
        }
        cfg = _LayoutConfig(**cfg_dict)
        out = tmp_path / "thumb.png"
        _render_thumbnail(1080, 1920, "hook", "🐱", out, "brand", vid, cfg)
        mock_save.assert_called_once()


class TestSaveUnder2mb:
    def test_png_small(self, tmp_path):
        img = Image.new("RGB", (64, 64), (10, 20, 30))
        out = tmp_path / "t.png"
        thumbnail_engine._save_under_2mb(img, out)
        assert out.exists()
        assert out.stat().st_size <= 2 * 1024 * 1024

    def test_jpeg_small(self, tmp_path):
        img = Image.new("RGB", (64, 64), (10, 20, 30))
        out = tmp_path / "t.jpg"
        thumbnail_engine._save_under_2mb(img, out)
        assert out.exists()
        assert out.stat().st_size <= 2 * 1024 * 1024

    def test_huge_image_downscales_to_fit(self, tmp_path):
        img = Image.new("RGB", (3000, 3000), (200, 200, 200))
        # Adiciona ruido para o JPEG nao comprimir demais
        import random as _r
        px = img.load()
        for x in range(0, 3000, 7):
            for y in range(0, 3000, 7):
                px[x, y] = (_r.randint(0, 255), _r.randint(0, 255), _r.randint(0, 255))
        out = tmp_path / "big.jpg"
        thumbnail_engine._save_under_2mb(img, out)
        assert out.exists()
        assert out.stat().st_size <= 2 * 1024 * 1024


class TestExtractFrame:
    def test_ffmpeg_success(self, tmp_path):
        # Cria PNG real para Image.open ler
        png = tmp_path / "frame.png"
        Image.new("RGB", (16, 16), (1, 2, 3)).save(png)
        # Patch tempfile + subprocess + Image.open via patches no modulo
        with patch("utils.thumbnail_engine.tempfile.NamedTemporaryFile") as mock_tmp, \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run, \
             patch("utils.thumbnail_engine.Image.open", return_value=Image.open(png)):
            mock_tmp.return_value.__enter__.return_value.name = str(tmp_path / "tmp.png")
            # Como delete=False, precisa que o nome seja valido
            ntf = MagicMock()
            ntf.name = str(tmp_path / "tmp_frame.png")
            mock_tmp.return_value = ntf
            img = thumbnail_engine.extract_frame_from_video(tmp_path / "v.mp4")
        assert img is not None
        mock_run.assert_called_once()

    def test_ffmpeg_failure_returns_none(self, tmp_path):
        with patch("utils.thumbnail_engine.tempfile.NamedTemporaryFile") as mock_tmp, \
             patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="err")):
            ntf = MagicMock()
            ntf.name = str(tmp_path / "tmp_frame.png")
            mock_tmp.return_value = ntf
            img = thumbnail_engine.extract_frame_from_video(tmp_path / "v.mp4")
        assert img is None

    def test_ffmpeg_timeout_returns_none(self, tmp_path):
        import subprocess
        with patch("utils.thumbnail_engine.tempfile.NamedTemporaryFile") as mock_tmp, \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)):
            ntf = MagicMock()
            ntf.name = str(tmp_path / "tmp_frame.png")
            mock_tmp.return_value = ntf
            img = thumbnail_engine.extract_frame_from_video(tmp_path / "v.mp4")
        assert img is None

    def test_ffmpeg_generic_exception_returns_none(self, tmp_path):
        with patch("utils.thumbnail_engine.tempfile.NamedTemporaryFile") as mock_tmp, \
             patch("subprocess.run", side_effect=ValueError("boom")):
            ntf = MagicMock()
            ntf.name = str(tmp_path / "tmp_frame.png")
            mock_tmp.return_value = ntf
            img = thumbnail_engine.extract_frame_from_video(tmp_path / "v.mp4")
        assert img is None
