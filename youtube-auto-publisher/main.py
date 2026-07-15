"""
main.py - Ponto de entrada principal do YouTube Auto Publisher
Orquestra todo o pipeline de criacao e publicacao de videos
Suporte a 4 videos/dia nos melhores horarios do YouTube
"""
import sys
import shutil
import argparse
import json
import time
import schedule
from pathlib import Path
from datetime import datetime, date
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table
import config

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from pexels_downloader import PexelsDownloader
from voice_generator import VoiceGenerator
from subtitle_generator import SubtitleGenerator
from music_mixer import MusicMixer
from video_editor import VideoEditor
from youtube_uploader import QuotaExceededError, YouTubeUploader
from database import DatabaseManager

console = Console()

# Arquivo para rastrear topicos usados recentemente (evita duplicatas)
USED_TOPICS_FILE = config.DATA_DIR / "used_topics.json"


def read_json_file(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning(f"Arquivo JSON corrompido ou incompleto: {path}")
        return default


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(int(value), maximum))


def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        level=config.LOG_LEVEL,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )
    logger.add(
        config.LOG_FILE,
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
    )


def load_used_topics() -> list:
    """Carrega lista de topicos usados recentemente"""
    data = read_json_file(USED_TOPICS_FILE, {"topics": []})
    topics = [str(topic) for topic in data.get("topics", []) if str(topic).strip()]
    # Mantem apenas os ultimos 40 topicos para evitar repeticao recente.
    return topics[-40:]


def save_used_topic(topic: str):
    """Registra um topico como usado"""
    topics = load_used_topics()
    if topic not in topics:
        topics.append(topic)
    write_json_atomic(USED_TOPICS_FILE, {"topics": topics[-40:]})


def get_next_topic() -> str:
    """Retorna proximo topico ainda nao publicado recentemente"""
    used = load_used_topics()
    topic = config.get_unused_topic(used)
    logger.info(f"Topico selecionado: '{topic}' (usados recentes: {len(used)})")
    return topic


def get_videos_published_today() -> int:
    """Retorna quantos videos foram publicados hoje"""
    today = date.today().isoformat()
    today_file = config.DATA_DIR / f"published_{today}.json"
    data = read_json_file(today_file, {"videos": []})
    return len(data.get("videos", []))


def register_video_published_today(session_id: str, topic: str):
    """Registra um video publicado hoje"""
    today = date.today().isoformat()
    today_file = config.DATA_DIR / f"published_{today}.json"
    data = read_json_file(today_file, {"videos": []})
    data["videos"].append({
        "session_id": session_id,
        "topic": topic,
        "time": datetime.now().isoformat()
    })
    write_json_atomic(today_file, data)


def create_video(
    topic: str = None,
    duration: int = 60,
    num_clips: int = 5,
    voice: str = None,
    upload: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Pipeline completo de criacao e publicacao de video de curiosidades.
    """
    duration = clamp_int(duration, config.VIDEO_MIN_DURATION, config.VIDEO_MAX_DURATION)
    num_clips = clamp_int(num_clips, 1, config.VIDEO_MAX_CLIPS)
    if topic:
        topic = topic.strip()[:120]

    should_upload = upload and not dry_run
    config.validate_config(
        require_youtube=should_upload,
        require_youtube_token=should_upload,
    )

    if should_upload:
        today_count = get_videos_published_today()
        if today_count >= config.MAX_VIDEOS_PER_DAY:
            message = (
                f"Limite diario atingido "
                f"({today_count}/{config.MAX_VIDEOS_PER_DAY}). Pulando publicacao."
            )
            logger.info(message)
            console.print(f"[yellow]{message}[/yellow]")
            return {
                "topic": topic,
                "session_id": None,
                "success": False,
                "skipped": True,
                "skip_reason": "daily_limit",
                "video_path": None,
                "youtube_id": None,
                "youtube_url": None,
            }

    # Seleciona topico automaticamente se nao fornecido
    if not topic:
        topic = get_next_topic()

    start_time = datetime.now()
    session_id = start_time.strftime("%Y%m%d_%H%M%S")
    session_dir = config.TEMP_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "topic": topic,
        "session_id": session_id,
        "success": False,
        "video_path": None,
        "youtube_id": None,
        "youtube_url": None,
        "skipped": False,
        "skip_reason": None,
    }

    db = DatabaseManager()

    try:
        console.print(Panel(
            f"[bold green]Criando video de curiosidades: [cyan]{topic}[/cyan][/bold green]\n"
            f"Duracao: {duration}s | Clipes: {num_clips} | Sessao: {session_id}",
            title="YouTube Auto Publisher - Curiosidades"
        ))

        # ETAPA 1: Gerar roteiro de curiosidades
        with Progress(SpinnerColumn(), TextColumn("{task.description}")) as p:
            t = p.add_task("Gerando roteiro com Groq...", total=None)
            voice_gen = VoiceGenerator()
            script = voice_gen.generate_curiosity_script(topic, duration)
            p.update(t, description="Roteiro gerado!")

        console.print(f"[green]Roteiro:[/green] {script[:150]}...")

        # ETAPA 2: Gerar audio (TTS edge-tts PT-BR)
        with Progress(SpinnerColumn(), TextColumn("{task.description}")) as p:
            t = p.add_task("Gerando narracao PT-BR (edge-tts)...", total=None)
            voice_path = session_dir / "narration.wav"
            voice_gen.generate_random_voice_audio(script, voice_path)
            p.update(t, description="Narracao gerada!")

        # ETAPA 3: Gerar legendas
        with Progress(SpinnerColumn(), TextColumn("{task.description}")) as p:
            t = p.add_task("Gerando legendas (Whisper)...", total=None)
            sub_gen = SubtitleGenerator(model_size="base")
            srt_path, subtitles = sub_gen.generate_subtitles_from_audio(
                voice_path, session_dir
            )
            p.update(t, description=f"Legendas geradas! ({len(subtitles)} segmentos)")

        if len(subtitles) == 0:
            logger.warning("Legendas vazias - gerando legendas sinteticas do roteiro")
            srt_path, subtitles = sub_gen.generate_synthetic_subtitles(
                script, voice_path, session_dir
            )

        # ETAPA 4: Baixar clipes do Pexels
        with Progress(SpinnerColumn(), TextColumn("{task.description}")) as p:
            t = p.add_task("Baixando clipes do Pexels...", total=None)
            downloader = PexelsDownloader()
            clips = downloader.download_clips_for_topic(
                topic, session_dir, num_clips=num_clips
            )
            p.update(t, description=f"Clipes baixados: {len(clips)}")

        if not clips:
            raise ValueError(f"Nenhum clipe encontrado para topico: {topic}")

        # ETAPA 5: Mixar audio com musica de fundo
        with Progress(SpinnerColumn(), TextColumn("{task.description}")) as p:
            t = p.add_task("Mixando audio com musica de fundo...", total=None)
            mixer = MusicMixer()
            mixed_audio = mixer.mix_with_background(
                voice_path, session_dir, topic=topic
            )
            p.update(t, description="Audio mixado!")

        # ETAPA 6: Montar video final com legendas dinamicas
        with Progress(SpinnerColumn(), TextColumn("{task.description}")) as p:
            t = p.add_task("Montando video final com legendas...", total=None)
            editor = VideoEditor()
            video_filename = f"curiosidades_{session_id}.mp4"
            video_path = config.OUTPUT_DIR / video_filename
            editor.create_video(
                clips=clips,
                audio_path=mixed_audio,
                srt_path=srt_path,
                output_path=video_path,
                duration=duration,
            )
            p.update(t, description="Video montado!")

        result["video_path"] = str(video_path)
        console.print(f"[green]Video criado:[/green] {video_path}")

        # ETAPA 7: Gerar titulo e descricao SEO
        with Progress(SpinnerColumn(), TextColumn("{task.description}")) as p:
            t = p.add_task("Gerando titulo e descricao SEO...", total=None)
            meta = voice_gen.generate_title_and_description(topic, script)
            p.update(t, description="Metadados gerados!")

        console.print(f"[bold]Titulo:[/bold] {meta.get('title', '')}")

        # ETAPA 8: Publicar no YouTube
        if should_upload:
            with Progress(SpinnerColumn(), TextColumn("{task.description}")) as p:
                t = p.add_task("Publicando no YouTube...", total=None)
                uploader = YouTubeUploader()
                yt_result = uploader.upload_video(
                    video_path=video_path,
                    title=meta.get("title", f"Curiosidades sobre {topic}"),
                    description=meta.get("description", ""),
                    tags=meta.get("tags", "").split(",") if meta.get("tags") else [],
                    category_id=config.VIDEO_CATEGORY_ID,
                    privacy_status=config.VIDEO_PRIVACY_STATUS,
                )
                p.update(t, description="Video publicado!")

            video_id = yt_result.get("id") if isinstance(yt_result, dict) else str(yt_result)
            if not video_id:
                raise RuntimeError("Resposta da API do YouTube sem id do video")
            result["youtube_id"] = video_id
            result["youtube_url"] = f"https://youtu.be/{video_id}"
            console.print(f"[bold green]Publicado:[/bold green] {result['youtube_url']}")
        elif dry_run:
            console.print("[yellow]Modo dry-run: video nao publicado[/yellow]")

        result["success"] = True

        # Registra topico como usado para evitar duplicatas
        save_used_topic(topic)
        if should_upload and result.get("youtube_id"):
            register_video_published_today(session_id, topic)

        # Salva no banco de dados
        db.save_video(
            session_id=session_id,
            topic=topic,
            title=meta.get("title", ""),
            description=meta.get("description", ""),
            tags=meta.get("tags", "").split(",") if meta.get("tags") else [],
            youtube_id=result.get("youtube_id"),
            youtube_url=result.get("youtube_url"),
            video_path=str(video_path),
            duration_seconds=duration,
            clips_count=len(clips),
            subtitles_count=len(subtitles),
            voice_used=voice or "edge-tts-random",
            success=True,
        )

        elapsed = (datetime.now() - start_time).seconds
        console.print(Panel(
            f"[bold green]Video concluido em {elapsed}s![/bold green]\n"
            f"Topico: {topic}\n"
            f"URL: {result.get('youtube_url', 'N/A')}",
            title="Sucesso!"
        ))

    except QuotaExceededError as e:
        # YouTube's daily API quota / upload limit was hit. This is an
        # expected, recoverable-on-a-later-run condition - handle it the
        # same way as the "daily video limit" skip above (safe, graceful
        # exit) instead of treating it as a generic pipeline failure.
        message = (
            f"Cota diaria da API do YouTube excedida (motivo: {e.reason}). "
            "Publicacao pulada com seguranca; tente novamente apos a renovacao da cota."
        )
        logger.warning(message)
        console.print(f"[yellow]{message}[/yellow]")
        result["skipped"] = True
        result["skip_reason"] = "quota_exceeded"
        result["error"] = str(e)
        db.save_video(
            session_id=session_id,
            topic=topic,
            success=False,
            error_message=str(e),
        )

    except Exception as e:
        logger.error(f"Erro no pipeline: {e}")
        result["error"] = str(e)
        db.save_video(
            session_id=session_id,
            topic=topic,
            success=False,
            error_message=str(e),
        )
        console.print(f"[bold red]Erro:[/bold red] {e}")

    finally:
        # Limpa arquivos temporarios
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)

    return result


def run_scheduler():
    """
    Agenda publicacao de 4 videos por dia nos melhores horarios do YouTube.
    
    Melhores horarios baseados em pesquisas de audiencia:
    - 08:00 - Manha: audiencia acorda e consome conteudo
    - 12:00 - Almoco: pico de visualizacoes no meio do dia  
    - 17:00 - Fim de tarde: retorno do trabalho/escola
    - 20:00 - Noite: maior pico de audiencia do YouTube
    """
    console.print(Panel(
        "[bold green]Iniciando agendador automatico[/bold green]\n"
        "Horarios: 08:00 | 12:00 | 17:00 | 20:00\n"
        "[yellow]Pressione Ctrl+C para parar[/yellow]",
        title="YouTube Auto Publisher - Scheduler"
    ))

    times = config.PUBLISH_TIMES.split(",")
    if len(times) < 4:
        times = ["08:00", "12:00", "17:00", "20:00"]

    def publish_job():
        """Job de publicacao - verifica limite diario antes de publicar"""
        today_count = get_videos_published_today()
        if today_count >= config.MAX_VIDEOS_PER_DAY:
            logger.info(f"Limite diario atingido ({today_count}/{config.MAX_VIDEOS_PER_DAY}). Pulando.")
            return
        
        console.print(f"\n[cyan]Iniciando publicacao automatica ({today_count + 1}/{config.MAX_VIDEOS_PER_DAY})...[/cyan]")
        result = create_video(
            duration=config.VIDEO_DURATION,
            num_clips=config.VIDEO_NUM_CLIPS,
            upload=config.ENABLE_AUTO_PUBLISH,
        )
        if result["success"]:
            logger.success(f"Video publicado com sucesso: {result.get('youtube_url')}")
        else:
            logger.error(f"Falha na publicacao: {result.get('error')}")

    # Agenda os 4 horarios
    for t in times:
        t = t.strip()
        schedule.every().day.at(t).do(publish_job)
        console.print(f"[green]Agendado:[/green] {t}")

    console.print(f"\n[bold]Total agendado:[/bold] {len(times)} publicacoes/dia")
    console.print(f"[bold]Maximo por dia:[/bold] {config.MAX_VIDEOS_PER_DAY}")

    # Loop principal do agendador
    while True:
        schedule.run_pending()
        next_run = schedule.next_run()
        if next_run:
            wait_secs = (next_run - datetime.now()).total_seconds()
            if wait_secs > 60:
                logger.debug(f"Proximo video em {int(wait_secs/60)} minutos")
        time.sleep(30)


def show_status():
    """Mostra status do sistema"""
    today = get_videos_published_today()
    used_topics = load_used_topics()

    table = Table(title="Status do YouTube Auto Publisher")
    table.add_column("Item", style="cyan")
    table.add_column("Valor", style="green")

    table.add_row("Videos hoje", f"{today}/{config.MAX_VIDEOS_PER_DAY}")
    table.add_row("Topicos usados (recentes)", str(len(used_topics)))
    table.add_row("Topicos disponiveis", str(len(config.CURIOSITY_TOPICS)))
    table.add_row("Auto publish", "Ativado" if config.ENABLE_AUTO_PUBLISH else "Desativado")
    table.add_row("Horarios", config.PUBLISH_TIMES)
    table.add_row("Privacidade", config.VIDEO_PRIVACY_STATUS)

    console.print(table)

    if used_topics:
        console.print(f"\n[dim]Ultimos topicos usados: {', '.join(used_topics[-5:])}[/dim]")


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="YouTube Auto Publisher - Cria e publica videos de curiosidades automaticamente",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--topic", type=str, help="Topico especifico (auto se omitido)")
    parser.add_argument("--duration", type=int, default=config.VIDEO_DURATION, help="Duracao em segundos")
    parser.add_argument("--clips", type=int, default=config.VIDEO_NUM_CLIPS, help="Numero de clipes")
    parser.add_argument("--voice", type=str, default=None, help="Voz especifica")
    parser.add_argument("--no-upload", action="store_true", help="Criar video sem publicar")
    parser.add_argument("--dry-run", action="store_true", help="Modo teste")
    parser.add_argument("--schedule", action="store_true", help="Modo agendador automatico (4x/dia)")
    parser.add_argument("--status", action="store_true", help="Mostra status do sistema")
    parser.add_argument("--list-topics", action="store_true", help="Lista todos os topicos de curiosidades")
    parser.add_argument("--reset-topics", action="store_true", help="Reinicia lista de topicos usados")

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.list_topics:
        console.print(Panel(
            "\n".join([f"  {i+1}. {t}" for i, t in enumerate(config.CURIOSITY_TOPICS)]),
            title=f"Topicos de Curiosidades ({len(config.CURIOSITY_TOPICS)} total)"
        ))
        return

    if args.reset_topics:
        if USED_TOPICS_FILE.exists():
            USED_TOPICS_FILE.unlink()
        console.print("[green]Lista de topicos usados reiniciada![/green]")
        return

    if args.schedule:
        run_scheduler()
        return

    # Criacao de video unico
    result = create_video(
        topic=args.topic,
        duration=args.duration,
        num_clips=args.clips,
        voice=args.voice,
        upload=not args.no_upload,
        dry_run=args.dry_run,
    )
    if not result.get("success") and not result.get("skipped"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
