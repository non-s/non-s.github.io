"""
music_mixer.py - Mixagem de audio com musica de fundo
Combina narracao com musica ambiente.
Se nao houver musica local, gera tom de fundo sintetico como fallback.
"""
import random
from pathlib import Path
from loguru import logger
import config


class MusicMixer:
    """Gerencia e mixa musicas de fundo para videos"""

    TOPIC_MUSIC_MAP = {
        "natureza": "relaxante",
        "tecnologia": "tecnologia",
        "ciencia": "motivacional",
        "historia": "aventura",
        "curiosidades": "motivacional",
        "saude": "relaxante",
        "fitness": "motivacional",
        "culinaria": "relaxante",
        "animais": "relaxante",
        "espaco": "aventura",
        "oceano": "relaxante",
        "viagem": "aventura",
    }

    def find_music_files(self) -> list:
        """Encontra arquivos de musica no diretorio de assets"""
        music_dir = config.MUSIC_DIR
        extensions = [".mp3", ".wav", ".ogg", ".flac"]
        files = []
        for ext in extensions:
            files.extend(music_dir.glob(f"*{ext}"))
        return files

    def _generate_silent_background(self, duration_ms: int, output_path: Path) -> Path:
        """Gera audio silencioso como ultimo fallback (sem musica)"""
        from pydub import AudioSegment
        silence = AudioSegment.silent(duration=duration_ms)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        silence.export(str(output_path), format="wav")
        return output_path

    def _download_free_music(self, output_dir: Path) -> list:
        """
        Tenta baixar musica CC0 de fontes abertas para usar como fundo.
        Usa URLs publicas de musicas CC0 conhecidas.
        """
        import urllib.request
        # URLs de musicas CC0 (dominio publico / Creative Commons Zero)
        cc0_tracks = [
            ("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", "bg_track1.mp3"),
            ("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3", "bg_track2.mp3"),
            ("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3", "bg_track3.mp3"),
        ]
        downloaded = []
        for url, filename in cc0_tracks[:1]:  # Baixa apenas 1 para economizar tempo
            dest = output_dir / filename
            if dest.exists():
                downloaded.append(dest)
                continue
            try:
                logger.info(f"Baixando musica de fundo CC0: {filename}")
                urllib.request.urlretrieve(url, str(dest))
                downloaded.append(dest)
                logger.success(f"Musica baixada: {dest}")
                break
            except Exception as e:
                logger.warning(f"Falha ao baixar {url}: {e}")
        return downloaded

    def mix_with_background(
        self,
        voice_path: Path,
        output_dir: Path,
        topic: str = None,
        voice_volume: float = None,
        music_volume: float = None,
    ) -> Path:
        """Mixa naracao com musica de fundo"""
        from pydub import AudioSegment

        voice_vol = voice_volume or config.AUDIO_VOICE_VOLUME
        music_vol = music_volume or config.AUDIO_MUSIC_VOLUME
        fade_dur = config.AUDIO_FADE_DURATION * 1000

        output_path = output_dir / "mixed_audio.wav"

        try:
            # Carrega naracao
            voice = AudioSegment.from_file(str(voice_path))
            voice_duration_ms = len(voice)

            # Ajusta volume da voz
            if voice_vol != 1.0:
                voice = voice + (20 * (voice_vol - 1))

            # Procura musica local
            music_files = self.find_music_files()

            # Se nao tem musica local, tenta baixar
            if not music_files:
                logger.info("Sem musica local - tentando baixar musica CC0...")
                music_files = self._download_free_music(config.MUSIC_DIR)

            if music_files:
                music_file = random.choice(music_files)
                music = AudioSegment.from_file(str(music_file))

                # Repete musica se necessario
                while len(music) < voice_duration_ms:
                    music = music + music

                music = music[:voice_duration_ms]

                # Reduz volume da musica
                db_reduction = 20 * (1 - music_vol)
                music = music - db_reduction

                # Fade in/out suave
                music = music.fade_in(fade_dur).fade_out(fade_dur)

                # Mixa voz + musica
                mixed = voice.overlay(music)
                logger.info(f"Musica mixada: {music_file.name}")
            else:
                # Sem musica - usa apenas naracao
                mixed = voice
                logger.warning("Sem musica disponivel - usando apenas narracao")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            mixed.export(str(output_path), format="wav")
            logger.success(f"Audio mixado salvo: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Erro ao mixar audio: {e}")
            import shutil
            shutil.copy(voice_path, output_path)
            return output_path
