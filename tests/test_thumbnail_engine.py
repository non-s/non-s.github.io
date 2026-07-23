"""Testes para thumbnail_engine.py."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import utils.thumbnail_engine as thumbnail_engine


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
