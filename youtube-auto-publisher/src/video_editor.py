"""
video_editor.py - Edicao e montagem de video dinamico
Combina clipes, audio, legendas dinamicas em video final.
Compativel com moviepy 2.x
"""
import random
import srt
from pathlib import Path
from loguru import logger
import config


class VideoEditor:
    """Editor de video com legendas dinamicas e efeitos"""

    def __init__(self):
        self.width = config.VIDEO_WIDTH
        self.height = config.VIDEO_HEIGHT
        self.fps = config.VIDEO_FPS

    def _load_subtitles(self, srt_path: Path) -> list:
        """Carrega legendas do arquivo SRT"""
        if not srt_path.exists():
            return []
        content = srt_path.read_text(encoding="utf-8").strip()
        if not content:
            return []
        try:
            return list(srt.parse(content))
        except Exception as e:
            logger.warning(f"Erro ao parsear SRT: {e}")
            return []

    def _make_subtitle_clips(self, subtitles: list, video_duration: float):
        """Cria clips de texto para legendas dinamicas"""
        from moviepy import TextClip, CompositeVideoClip
        subtitle_clips = []
        for sub in subtitles:
            start = sub.start.total_seconds()
            end = sub.end.total_seconds()
            if start >= video_duration:
                continue
            end = min(end, video_duration)
            duration = end - start
            if duration <= 0:
                continue
            text = sub.content.strip()
            if not text:
                continue
            try:
                txt_clip = (
                    TextClip(
                        text=text,
                        font_size=config.SUBTITLE_FONT_SIZE,
                        color=config.SUBTITLE_COLOR,
                        font="Arial",
                        stroke_color=config.SUBTITLE_STROKE_COLOR,
                        stroke_width=config.SUBTITLE_STROKE_WIDTH,
                        method="caption",
                        size=(int(self.width * 0.85), None),
                    )
                    .with_start(start)
                    .with_duration(duration)
                    .with_position(("center", int(self.height * 0.82)))
                )
                subtitle_clips.append(txt_clip)
            except Exception as e:
                logger.warning(f"Erro ao criar clip de legenda: {e}")
                continue
        return subtitle_clips

    def create_video(
        self,
        clips: list,
        audio_path: Path,
        srt_path: Path,
        output_path: Path,
        duration: int = 60,
    ) -> Path:
        """Monta o video final com clipes, audio e legendas dinamicas"""
        try:
            from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip

            if not clips:
                raise ValueError("Nenhum clipe de video disponivel")

            logger.info(f"Montando video com {len(clips)} clipes...")

            clip_duration = duration / len(clips)
            video_clips = []

            for clip_path in clips:
                try:
                    clip = VideoFileClip(str(clip_path))
                    clip = clip.resized((self.width, self.height))
                    if clip.duration > clip_duration:
                        clip = clip.subclipped(0, clip_duration)
                    video_clips.append(clip)
                except Exception as e:
                    logger.warning(f"Erro ao carregar clipe {clip_path.name}: {e}")
                    continue

            if not video_clips:
                raise ValueError("Nenhum clipe valido encontrado")

            # Concatena clipes
            final_video = concatenate_videoclips(video_clips, method="compose")

            # Adiciona audio
            if audio_path and audio_path.exists():
                audio = AudioFileClip(str(audio_path))
                if audio.duration > final_video.duration:
                    audio = audio.subclipped(0, final_video.duration)
                final_video = final_video.with_audio(audio)

            # Adiciona legendas dinamicas
            subtitles = self._load_subtitles(srt_path)
            if subtitles:
                logger.info(f"Adicionando {len(subtitles)} legendas ao video...")
                subtitle_clips = self._make_subtitle_clips(subtitles, final_video.duration)
                if subtitle_clips:
                    final_video = CompositeVideoClip([final_video] + subtitle_clips)
                    logger.success(f"Legendas adicionadas: {len(subtitle_clips)} clips")
            else:
                logger.warning("Sem legendas para adicionar ao video")

            # Renderiza video
            output_path.parent.mkdir(parents=True, exist_ok=True)
            final_video.write_videofile(
                str(output_path),
                fps=self.fps,
                codec="libx264",
                audio_codec="aac",
                logger=None,
                threads=4,
            )

            # Libera memoria
            for clip in video_clips:
                clip.close()
            final_video.close()

            logger.success(f"Video criado: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Erro ao criar video: {e}")
            raise
