"""
utils/caption_engine.py — gera legendas SRT automaticas via Gemini.

Cria um arquivo .srt com transcricao narrada do video e envia para o YouTube
como caption track. Legendas melhoram SEO e acessibilidade.
"""

from __future__ import annotations

import logging
from pathlib import Path

from utils.ai_helper import ai_text, is_safe_ai_text

log = logging.getLogger(__name__)


def generate_srt(hook: str, scene: str, duration: int, kind: str, emoji: str) -> str:
    """Gera conteudo SRT via Gemini, com fallback local.

    Retorna o texto completo do arquivo .srt.
    """
    prompt = (
        f"Create English captions for a {duration}-second {'Short' if kind == 'short' else 'video'} "
        f"about {hook} {emoji}. "
        f"The channel is Pata Jazz (cute cats and dogs + relaxing jazz). "
        f"Create 4-6 short caption lines (max 40 chars each), spread across the duration. "
        f"Return ONLY the SRT format (numbered, with timestamps HH:MM:SS,mmm --> HH:MM:SS,mmm)."
    )
    out = ai_text(prompt, task="caption")

    # Mesma checagem aplicada a titulo/descricao em metadata_engine.py: a
    # legenda tambem vira texto publico (caption track do YouTube), entao
    # nao pode escapar dessa validacao so porque passa por um caminho
    # diferente.
    if out and " --> " in out:
        if is_safe_ai_text(out):
            return out.strip()
        log.warning("Legenda da IA rejeitada (padrao suspeito); usando fallback local.")

    # Fallback: gerar SRT localmente
    return _fallback_srt(hook, duration)


def _fmt_ts(seconds: float) -> str:
    """Formata segundos como timestamp SRT ``HH:MM:SS,mmm`` (zero-padded)."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fallback_srt(hook: str, duration: int) -> str:
    """Gera SRT simples com o hook dividido em 3 partes."""
    lines = [
        (_fmt_ts(0.0), _fmt_ts(min(3.0, duration)), hook[:40]),
        (_fmt_ts(min(3.0, duration)), _fmt_ts(min(8.0, duration)), "Welcome to Pata Jazz"),
        (_fmt_ts(min(8.0, duration)), _fmt_ts(float(duration)), "Cats and dogs + jazz"),
    ]

    srt_lines: list[str] = []
    for i, (start, end, text) in enumerate(lines, 1):
        srt_lines.append(str(i))
        srt_lines.append(f"{start} --> {end}")
        srt_lines.append(text)
        srt_lines.append("")
    return "\n".join(srt_lines)


def save_srt(content: str, video_path: Path) -> Path:
    """Salva o SRT ao lado do video com o mesmo nome."""
    srt_path = video_path.with_suffix(".srt")
    srt_path.write_text(content, encoding="utf-8")
    log.info("SRT salvo: %s", srt_path)
    return srt_path


def _fmt_ass_ts(seconds: float) -> str:
    """Formata segundos como timestamp ASS ``H:MM:SS.cc`` (centesimos)."""
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6_000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _escape_ass_text(text: str) -> str:
    """Escapa caracteres especiais do ASS em texto de dialogue."""
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _split_hook_lines(hook: str, max_lines: int = 3, max_chars: int = 40) -> list[str]:
    """Quebra o hook em ate ``max_lines`` linhas de no maximo ``max_chars``."""
    words = hook.split()
    lines: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for w in words:
        add = (1 if cur else 0) + len(w)
        if cur and cur_len + add > max_chars:
            lines.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
        else:
            cur.append(w)
            cur_len += add
    if cur:
        lines.append(" ".join(cur))
    return lines[:max_lines] or [""]


def _ass_header(fontsize: int, play_res_x: int, play_res_y: int) -> str:
    """Cabecalho ASS completo (Script Info + V4+ Styles + Events Format)."""
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {play_res_x}\n"
        f"PlayResY: {play_res_y}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        # Alignment=5 (center-middle, \an5); branco com outline preto + sombra.
        "Style: Default,Arial,"
        f"{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        "1,0,0,0,100,100,0,0,1,3,1,5,120,120,80,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )


def _ass_word_dialogue(
    start: float, end: float, word: str
) -> str:
    """Uma linha Dialogue para uma palavra com fade-in + escala 1.2x -> 1.0x."""
    safe = _escape_ass_text(word)
    text = (
        r"{\an5\fad(300,0)\fscx120\fscy120\t(0,300,\fscx100\fscy100)}" + safe
    )
    return (
        f"Dialogue: 0,{_fmt_ass_ts(start)},{_fmt_ass_ts(end)},"
        f"Default,,0,0,0,,{text}\n"
    )


def _ass_line_words(
    start: float, end: float, line: str
) -> list[str]:
    """Gera um Dialogue por palavra da linha, escalonadas a cada ~0.3s."""
    words = line.split()
    if not words:
        return []
    window = max(end - start, 0.0)
    stagger = min(0.3, window / (len(words) + 1))
    dialogues: list[str] = []
    for i, w in enumerate(words):
        w_start = start + i * stagger
        w_end = max(end, w_start + stagger)
        dialogues.append(_ass_word_dialogue(w_start, w_end, w))
    return dialogues


def _fallback_ass(hook: str, duration: int, kind: str) -> str:
    """Gera ASS localmente (mesma estrutura do _fallback_srt, animado)."""
    fontsize = 48 if kind == "short" else 36
    res_x, res_y = (1080, 1920) if kind == "short" else (1920, 1080)
    header = _ass_header(fontsize, res_x, res_y)

    hook_end = min(6.0, duration * 0.5)
    welcome_end = min(hook_end + 4.0, float(duration))
    cats_end = float(duration)

    events: list[str] = []
    for line in _split_hook_lines(hook):
        events.extend(_ass_line_words(0.0, hook_end, line))
    events.extend(_ass_line_words(hook_end, welcome_end, "Welcome to Pata Jazz"))
    if cats_end > welcome_end:
        events.extend(_ass_line_words(welcome_end, cats_end, "Cats and dogs + jazz"))

    return header + "".join(events)


def generate_ass(hook: str, scene: str, duration: int, kind: str, emoji: str) -> str:
    """Gera conteudo ASS estilizado (animado palavra-a-palavra) via Gemini.

    Retorna o texto completo do arquivo .ass. Em falha da IA, usa fallback
    local em ASS.
    """
    prompt = (
        f"Create English captions for a {duration}-second {'Short' if kind == 'short' else 'video'} "
        f"about {hook} {emoji}. "
        f"The channel is Pata Jazz (cute cats and dogs + relaxing jazz). "
        f"Create 4-6 short caption lines (max 40 chars each), spread across the duration. "
        f"Return ONLY a valid ASS (Advanced SubStation Alpha) subtitle file with "
        f"[Script Info], [V4+ Styles] and [Events] sections, one Dialogue line per caption. "
        f"Use timestamps in H:MM:SS.cc format."
    )
    out = ai_text(prompt, task="caption")

    if out and "[Events]" in out and "Dialogue:" in out:
        if is_safe_ai_text(out):
            return out.strip() + ("\n" if not out.endswith("\n") else "")
        log.warning("Legenda ASS da IA rejeitada (padrao suspeito); usando fallback local.")

    return _fallback_ass(hook, duration, kind)


def save_ass(content: str, video_path: Path) -> Path:
    """Salva o ASS ao lado do video com o mesmo nome."""
    ass_path = video_path.with_suffix(".ass")
    ass_path.write_text(content, encoding="utf-8")
    log.info("ASS salvo: %s", ass_path)
    return ass_path
