"""
subtitle_generator.py - Geracao de legendas sincronizadas
Usa Whisper da OpenAI para transcrever audio e gerar legendas SRT.
Tambem gera legendas sinteticas como fallback quando Whisper falha.
"""
import srt
import re
from pathlib import Path
from datetime import timedelta
from loguru import logger
import config

# Whisper ocasionalmente "aluciona" trechos de texto (tokens/simbolos sem
# relacao com o audio) em segmentos de silencio ou baixa confianca. Esses
# limiares descartam segmentos suspeitos antes que virem legenda.
NO_SPEECH_PROB_THRESHOLD = 0.6
AVG_LOGPROB_THRESHOLD = -1.0
# Caracteres validos para legendas em PT-BR: letras (com acentos), numeros,
# espacos e pontuacao basica. Qualquer outra coisa (chaves, barras invertidas,
# tags de formatacao vazadas, etc.) e removida.
ALLOWED_SUBTITLE_CHARS = re.compile(r"[^A-Za-zÀ-ÖØ-öø-ÿ0-9\s.,!?;:'\"\-()]")


def sanitize_subtitle_text(text: str) -> str:
    """Remove caracteres invalidos/vazados (ex.: tags e simbolos de baixa confianca)."""
    cleaned = ALLOWED_SUBTITLE_CHARS.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def is_likely_hallucination(segment: dict, text: str) -> bool:
    """Detecta segmentos provavelmente alucinados pelo Whisper."""
    if segment.get("no_speech_prob", 0.0) >= NO_SPEECH_PROB_THRESHOLD:
        return True
    if segment.get("avg_logprob", 0.0) <= AVG_LOGPROB_THRESHOLD:
        return True
    letters = sum(1 for c in text if c.isalpha())
    if not text or letters / max(len(text), 1) < 0.5:
        return True
    return False


class SubtitleGenerator:
    """Gera legendas sincronizadas com o audio"""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None
        self.language = "pt"

    @property
    def model(self):
        if self._model is None:
            import whisper
            logger.info(f"Carregando modelo Whisper '{self.model_size}'...")
            self._model = whisper.load_model(self.model_size)
        return self._model

    def transcribe_audio(self, audio_path: Path) -> dict:
        """Transcreve audio usando Whisper"""
        logger.info(f"Transcrevendo audio: {audio_path}")
        result = self.model.transcribe(
            str(audio_path),
            language=self.language,
            task="transcribe",
            word_timestamps=True,
        )
        return result

    def create_srt_subtitles(self, transcription: dict) -> list:
        """Converte transcricao Whisper em objetos SRT, descartando alucinacoes"""
        subtitles = []
        index = 1
        for segment in transcription.get("segments", []):
            raw_text = segment.get("text", "").strip()
            if not raw_text:
                continue
            if is_likely_hallucination(segment, raw_text):
                logger.warning(f"Segmento descartado (possivel alucinacao): {raw_text!r}")
                continue
            text = sanitize_subtitle_text(raw_text)
            if not text:
                continue
            start = timedelta(seconds=segment["start"])
            end = timedelta(seconds=segment["end"])
            subtitle = srt.Subtitle(
                index=index,
                start=start,
                end=end,
                content=text,
            )
            subtitles.append(subtitle)
            index += 1
        return subtitles

    def save_srt_file(self, subtitles: list, output_path: Path) -> Path:
        """Salva legendas em arquivo SRT"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not subtitles:
            output_path.write_text("", encoding="utf-8")
            logger.warning("Legendas vazias - arquivo SRT em branco criado")
            return output_path
        srt_content = srt.compose(subtitles)
        output_path.write_text(srt_content, encoding="utf-8")
        logger.success(f"Legendas salvas: {output_path} ({len(subtitles)} segmentos)")
        return output_path

    def generate_synthetic_subtitles(
        self, script: str, audio_path: Path, output_dir: Path,
        words_per_second: float = 2.3
    ) -> tuple:
        """
        Gera legendas sinteticas a partir do roteiro quando Whisper falha.
        Distribui o texto ao longo da duracao estimada do audio.
        """
        logger.info("Gerando legendas sinteticas do roteiro...")
        # Estima duracao do audio
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(str(audio_path))
            total_duration = len(audio) / 1000.0
        except Exception:
            words = len(script.split())
            total_duration = words / words_per_second

        # Divide o roteiro em segmentos de ~8-10 palavras
        words = script.split()
        chunk_size = 8
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)

        if not chunks:
            return output_dir / "subtitles.srt", []

        time_per_chunk = total_duration / len(chunks)
        subtitles = []
        index = 1
        for i, chunk in enumerate(chunks):
            text = sanitize_subtitle_text(chunk)
            if not text:
                continue
            start_sec = i * time_per_chunk
            end_sec = min((i + 1) * time_per_chunk, total_duration)
            subtitle = srt.Subtitle(
                index=index,
                start=timedelta(seconds=start_sec),
                end=timedelta(seconds=end_sec - 0.1),
                content=text,
            )
            subtitles.append(subtitle)
            index += 1

        srt_path = output_dir / "subtitles.srt"
        self.save_srt_file(subtitles, srt_path)
        logger.success(f"Legendas sinteticas geradas: {len(subtitles)} segmentos")
        return srt_path, subtitles

    def generate_subtitles_from_audio(
        self, audio_path: Path, output_dir: Path
    ) -> tuple:
        """Pipeline completo: audio -> transcricao Whisper -> arquivo SRT"""
        try:
            transcription = self.transcribe_audio(audio_path)
            subtitles = self.create_srt_subtitles(transcription)
            srt_path = output_dir / "subtitles.srt"
            self.save_srt_file(subtitles, srt_path)
            if len(subtitles) == 0:
                logger.warning("Whisper retornou legendas vazias")
            return srt_path, subtitles
        except Exception as e:
            logger.error(f"Erro ao gerar legendas com Whisper: {e}")
            # Retorna arquivo vazio - main.py vai chamar generate_synthetic_subtitles
            empty_path = output_dir / "subtitles.srt"
            empty_path.parent.mkdir(parents=True, exist_ok=True)
            empty_path.write_text("", encoding="utf-8")
            return empty_path, []
