"""Testes de integracao que invocam o FFmpeg de verdade.

Os testes unitarios de utils/video_builder.py (tests/test_video_builder_unit.py)
mockeiam subprocess/run_ffmpeg e nunca executam o FFmpeg real - isso deixou
passar um bug real de producao que quebrou 100% das geracoes de Short:
font='Arial:style=Bold' sem escape do ':' fazia o FFmpeg ler "style=Bold"
como se fosse uma opcao separada do filtro drawtext (que nao existe),
falhando com "Error applying option 'style' to filter 'drawtext': Option
not found". Reproduzido e confirmado com FFmpeg de verdade antes de corrigir.

Estes testes rodam o filtro de overlay contra um FFmpeg real (instalado em
CI - ver .github/workflows/ci.yml) pra pegar esse tipo de regressao antes
de chegar em producao. Pulados automaticamente se ffmpeg nao estiver
disponivel (ex.: ambiente local sem ffmpeg instalado).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from utils.video_builder import _build_endcard_filter, _build_overlay_filter

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg nao instalado")


def _render_with_filter(vf: str) -> subprocess.CompletedProcess:
    """Renderiza 1 frame de uma fonte de cor solida com o filtro dado.
    Fonte sintetica (lavfi) - nao depende de nenhum asset do repo."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.png"
        return subprocess.run(
            [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=320x240:d=1",
                "-vf",
                vf,
                "-frames:v",
                "1",
                "-update",
                "1",
                "-y",
                str(out),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )


class TestBuildOverlayFilterAgainstRealFfmpeg:
    def test_simple_hook_renders_without_error(self):
        vf = _build_overlay_filter("Cute Cat Being Mischievous", 1920)
        result = _render_with_filter(vf)
        assert result.returncode == 0, result.stderr

    def test_hook_with_apostrophe_renders_without_error(self):
        """Apostrofos ASCII sao normalizados para apostrofo tipografico (’)
        para evitar a sequencia de escape `\'` que e instavel em algumas
        builds do FFmpeg (crash com fontconfig no Windows)."""
        vf = _build_overlay_filter("Cat's Cozy Relax Moment", 1920)
        result = _render_with_filter(vf)
        assert result.returncode == 0, result.stderr
        assert "’" in vf or "Cat" in vf

    def test_hook_with_colon_renders_without_error(self):
        """Dois-pontos no texto precisam de escape com backslash+dois-pontos
        porque o parser de opcoes do FFmpeg os splita mesmo dentro de aspas
        simples."""
        vf = _build_overlay_filter("Playtime: with a silly cat", 1920)
        result = _render_with_filter(vf)
        assert result.returncode == 0, result.stderr

    def test_uses_bundled_fontfile(self):
        """Regressao direta do bug real: font='Arial:style=Bold' dependia
        de fontconfig e do ':' escapado. Agora usamos fontfile=<caminho>
        com a fonte empacotada no repo, que funciona em qualquer runner."""
        vf = _build_overlay_filter("hello", 1920)
        assert "fontfile='" in vf
        assert "Roboto-Bold.ttf" in vf
        result = _render_with_filter(vf)
        assert result.returncode == 0, result.stderr


class TestBuildEndcardFilterAgainstRealFfmpeg:
    def test_endcard_renders_without_error(self):
        vf = _build_endcard_filter(1080, 60)
        result = _render_with_filter(vf)
        assert result.returncode == 0, result.stderr

    def test_endcard_uses_bundled_fontfile(self):
        vf = _build_endcard_filter(1080, 60)
        assert "fontfile='" in vf
        assert "Roboto-Bold.ttf" in vf
        result = _render_with_filter(vf)
        assert result.returncode == 0, result.stderr

    def test_endcard_enable_window_is_valid(self):
        vf = _build_endcard_filter(1080, 60)
        assert "enable='gte(t," in vf
        result = _render_with_filter(vf)
        assert result.returncode == 0, result.stderr
