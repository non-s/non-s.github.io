"""utils/font_config.py — localiza a fonte usada pelo FFmpeg e por PIL.

O projeto empacota a Roboto Bold em _assets/fonts/ para garantir que o
mesmo texto renderize de forma identica em qualquer runner (CI, GitHub
Actions, Windows, Linux, macOS) sem depender de fontconfig ou de fontes do
sistema. Se a fonte empacotada estiver ausente, cai em busca por fontes
comuns do sistema como fallback.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLED_FONT = ROOT / "_assets" / "fonts" / "Roboto-Bold.ttf"

# Fallbacks comuns por sistema operacional, do mais provavel ao menos.
_FALLBACK_FONTS = [
    # Windows
    r"C:\\Windows\\Fonts\\arialbd.ttf",
    r"C:\\Windows\\Fonts\\Arial-Bold.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    "~/Library/Fonts/Roboto-Bold.ttf",
]


def bundled_font_path() -> Path:
    """Retorna o caminho da fonte empacotada no repo."""
    return BUNDLED_FONT


def _resolve_font() -> Path:
    """Localiza a fonte a ser usada (empacotada ou fallback do sistema)."""
    if BUNDLED_FONT.exists():
        return BUNDLED_FONT.resolve()
    for candidate in _FALLBACK_FONTS:
        expanded = Path(candidate).expanduser()
        if expanded.exists():
            return expanded.resolve()
    raise RuntimeError(f"Nenhuma fonte TrueType encontrada. Verifique se {BUNDLED_FONT} existe.")


def _ffmpeg_escape_drive_colon(path: str) -> str:
    """Escapa o ':' da letra de drive em paths Windows para FFmpeg.

    O parser de filtergraph do FFmpeg trata ':' como separador de opcoes,
    mesmo dentro de aspas simples. Em Windows, 'C:/foo' precisa virar
    'C\\:/foo' dentro do valor de fontfile='...'. Esse escape e valido e
    reconhecido pelo FFmpeg em qualquer plataforma.
    """
    if len(path) >= 2 and path[1] == ":" and path[0].isalpha():
        return path[0] + "\\" + path[1:]
    return path


def font_path(ffmpeg_safe: bool = True) -> str:
    """Retorna o caminho absoluto de uma fonte bold TrueType disponivel.

    Preferencia: fonte empacotada > fontes do sistema.

    Quando `ffmpeg_safe=True` (padrao), normaliza o path para uso no valor de
    `fontfile='...'` do FFmpeg: converte barras Windows para '/' e escapa o
    ':' da letra de drive (ex: 'C\\\\:/...'). Isso evita que o parser de
    filtergraph quebre o path em partes.
    """
    path = str(_resolve_font())
    if ffmpeg_safe:
        path = path.replace("\\", "/")
        path = _ffmpeg_escape_drive_colon(path)
    return path


def pil_font_path() -> str:
    """Retorna o caminho da fonte para PIL/Pillow (mantem barras do sistema)."""
    return str(_resolve_font())
