"""Testes para thumbnail_engine.py."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import utils.thumbnail_engine as thumbnail_engine


def test_hex_to_rgb():
    """Converte cores hex da paleta em tuplas RGB válidas."""
    assert thumbnail_engine._hex_to_rgb("#f4a261") == (244, 162, 97)
    assert thumbnail_engine._hex_to_rgb("0f0f23") == (15, 15, 35)


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


class TestThumbnailEngine:
    """Testes para thumbnail_engine."""
    
    @patch('PIL.Image.new')
    @patch('utils.thumbnail_engine.ImageDraw')
    @patch('utils.thumbnail_engine.ImageFont')
    def test_make_horizontal_thumbnail(self, mock_font, mock_draw, mock_image):
        """Testa criação de thumbnail horizontal."""
        mock_img = MagicMock()
        mock_image.return_value = mock_img
        mock_draw_instance = MagicMock()
        mock_draw.Draw.return_value = mock_draw_instance
        mock_font.truetype.return_value = MagicMock()
        
        output = Path("test_thumb.png")
        
        # Não deve levantar exceção
        thumbnail_engine.make_horizontal_thumbnail(
            hook="Gatinhos Fofos",
            emoji="🐱",
            output=output,
            brand="Pata Jazz"
        )
        
        mock_image.assert_called_once()
    
    @patch('PIL.Image.new')
    @patch('utils.thumbnail_engine.ImageDraw')
    @patch('utils.thumbnail_engine.ImageFont')
    def test_make_short_thumbnail(self, mock_font, mock_draw, mock_image):
        """Testa criação de thumbnail vertical (Short)."""
        mock_img = MagicMock()
        mock_image.return_value = mock_img
        mock_draw_instance = MagicMock()
        mock_draw.Draw.return_value = mock_draw_instance
        mock_font.truetype.return_value = MagicMock()
        
        output = Path("test_short_thumb.png")
        
        # Não deve levantar exceção
        thumbnail_engine.make_short_thumbnail(
            hook="Meow Monday",
            emoji="🎷",
            output=output,
            brand="Pata Jazz"
        )
        
        mock_image.assert_called_once()
