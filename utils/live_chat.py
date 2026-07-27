"""
utils/live_chat.py — le o chat ao vivo do YouTube e reage a comandos.

Lives 24/7 de pets vivem de recorrencia; interacao aumenta watch time. Este
modulo faz poll do endpoint liveChatMessages.list a cada 10s (intervalo
recomendado pela API - custa 1 unidade por chamada, 6/min < 10000/dia),
parseia comandos prefixados com '!' e escreve respostas em arquivos que o
overlay FFmpeg le (textfile=...:reload=1).

Nao posta mensagens no chat automaticamente: enviar mensagens
programaticamente pode violar o ToS do YouTube se parecer bot spam. A
reacao e puramente visual no overlay da live.

Arquivos produzidos (em _data/):
- live_chat_replies.json  - historico das ultimas respostas (debug/inspecao)
- live_chat_overlay.txt   - ultima resposta, exibida no canto inferior
                            direito do FFmpeg; apagada apos 10s para fade out
- live_next_scene.json    - cena forcada por !scene (one-shot, consumida pelo
                            loop de clipes em generate_pata_jazz_live.py)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from utils.youtube_retry import retry_youtube_call

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
LIVE_META_DIR = ROOT / "_data"

POLL_INTERVAL_SECONDS = 10
OVERLAY_TTL_SECONDS = 10
_MAX_REPLY_HISTORY = 200

_HELP_TEXT = (
    "Comandos: !scene <cena> | !uptime | !song | !help  "
    "(cenas: cat, kitten, puppy, dog, sleepy cat, sleepy dog, "
    "playful dog, cat playing, puppy playing, dog relaxing, cat relaxing)"
)


def fetch_chat_messages(
    service: Resource, chat_id: str, page_token: str = ""
) -> tuple[list[dict], str]:
    """Lista mensagens do chat ao vivo.

    Retorna (items, next_page_token). Usa retry_youtube_call para transient
    errors. items e a lista bruta retornada pela API (cada item tem
    snippet.textMessageDetails.messageText, authorDetails.displayName etc).
    """
    request = service.liveChatMessages().list(
        liveChatId=chat_id,
        part="snippet,authorDetails",
        pageToken=page_token,
    )
    response = retry_youtube_call(request.execute)
    items = (response or {}).get("items", [])
    next_token = (response or {}).get("nextPageToken", "") or ""
    return items, next_token


def _format_uptime(seconds: float) -> str:
    """Formata segundos como HH:MM:SS."""
    total = int(max(0.0, seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class LiveChatWatcher:
    """Thread daemon que faz poll do chat e reage a comandos.

    Reacao visual apenas: escreve em _data/live_chat_overlay.txt (lido pelo
    overlay FFmpeg) e _data/live_chat_replies.json (historico). Nao posta
    mensagens no chat.
    """

    def __init__(
        self,
        service: Resource,
        chat_id: str,
        start_time: float,
        meta_dir: Path = LIVE_META_DIR,
        poll_interval: float = POLL_INTERVAL_SECONDS,
    ) -> None:
        self._service = service
        self._chat_id = chat_id
        self._start_time = start_time
        self._meta_dir = meta_dir
        self._poll_interval = poll_interval
        self._page_token = ""
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._overlay_clear_at: float = 0.0

    # ---- comandos -----------------------------------------------------

    def parse_command(self, text: str) -> tuple[str, str] | None:
        """Extrai (comando, argumento) de uma linha de chat, ou None se nao
        for um comando (nao comeca com '!' ou e so o prefixo). Case
        insensitivo no comando; argumento preserva case (cenas sao lowercased
        pelo consumidor)."""
        stripped = text.strip()
        if not stripped.startswith("!"):
            return None
        body = stripped[1:].strip()
        if not body:
            return None
        parts = body.split(None, 1)
        command = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""
        return command, argument

    def handle_command(self, command: str, argument: str, author: str = "") -> str | None:
        """Processa um comando e devolve o texto de resposta a exibir no
        overlay, ou None se o comando nao for reconhecido. Efeitos colaterais
        (escrever live_next_scene.json) acontecem aqui."""
        if command == "scene":
            return self._handle_scene(argument)
        if command == "uptime":
            return self._handle_uptime()
        if command == "song":
            return self._handle_song()
        if command == "help":
            return _HELP_TEXT
        return None

    def _handle_scene(self, argument: str) -> str:
        scene = argument.lower().strip()
        if not scene:
            return "Uso: !scene <cena> (ex: !scene sleepy cat)"
        from utils.animal_branding import ALL_SCENES

        if scene not in ALL_SCENES:
            return f"Cena desconhecida: {scene}. Validas: {', '.join(ALL_SCENES)}"
        payload = {
            "scene": scene,
            "requested_at": datetime.now(UTC).isoformat(),
        }
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        (self._meta_dir / "live_next_scene.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return f"Proxima cena: {scene} (obrigado!)"

    def _handle_uptime(self) -> str:
        uptime = _format_uptime(time.time() - self._start_time)
        return f"Uptime: {uptime}"

    def _handle_song(self) -> str:
        track_path = self._meta_dir / "live_current_track.json"
        if not track_path.exists():
            return "Nao sei que musica esta tocando agora :("
        try:
            data = json.loads(track_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("live_current_track.json corrompido: %s", exc)
            return "Nao consegui ler a faixa atual :("
        title = data.get("title") or data.get("name") or "faixa desconhecida"
        artist = data.get("artist") or ""
        if artist:
            return f"Tocando agora: {artist} - {title}"
        return f"Tocando agora: {title}"

    # ---- overlay / historico -----------------------------------------

    def _write_overlay(self, text: str) -> None:
        """Escreve a ultima resposta no arquivo de overlay e agenda a limpeza
        (fade out) apos OVERLAY_TTL_SECONDS."""
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        overlay_path = self._meta_dir / "live_chat_overlay.txt"
        try:
            overlay_path.write_text(text, encoding="utf-8")
        except Exception as exc:
            log.warning("Falha ao escrever overlay do chat: %s", exc)
            return
        self._overlay_clear_at = time.time() + OVERLAY_TTL_SECONDS
        self._append_reply_history(text)

    def _maybe_clear_overlay(self) -> None:
        if self._overlay_clear_at and time.time() >= self._overlay_clear_at:
            overlay_path = self._meta_dir / "live_chat_overlay.txt"
            try:
                overlay_path.unlink(missing_ok=True)
            except Exception as exc:
                log.debug("Falha ao apagar overlay do chat: %s", exc)
            self._overlay_clear_at = 0.0

    def _append_reply_history(self, text: str) -> None:
        path = self._meta_dir / "live_chat_replies.json"
        try:
            history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        except Exception:
            history = []
        history.append({"at": datetime.now(UTC).isoformat(), "reply": text})
        history = history[-_MAX_REPLY_HISTORY:]
        try:
            path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.warning("Falha ao salvar historico de respostas do chat: %s", exc)

    # ---- loop principal ----------------------------------------------

    def _poll_once(self) -> None:
        try:
            items, self._page_token = fetch_chat_messages(
                self._service, self._chat_id, self._page_token
            )
        except Exception as exc:
            log.warning("Falha ao buscar mensagens do chat: %s", exc)
            return
        for item in items:
            text = (item.get("snippet", {}) or {})
            text = text.get("textMessageDetails", {}).get("messageText", "")
            author = (item.get("authorDetails", {}) or {}).get("displayName", "")
            parsed = self.parse_command(text)
            if parsed is None:
                continue
            command, argument = parsed
            log.info("Comando de chat de %s: !%s %s", author, command, argument)
            reply = self.handle_command(command, argument, author=author)
            if reply:
                self._write_overlay(reply)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as exc:
                log.warning("Erro inesperado no loop do LiveChatWatcher: %s", exc)
            self._maybe_clear_overlay()
            self._stop_event.wait(self._poll_interval)

    # ---- API publica --------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="LiveChatWatcher", daemon=True
        )
        self._thread.start()
        log.info("LiveChatWatcher iniciado para chat %s", self._chat_id)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None
        # Limpa overlay pendente para nao deixar texto obsoleto na tela.
        try:
            (self._meta_dir / "live_chat_overlay.txt").unlink(missing_ok=True)
        except Exception:
            pass


def write_uptime(start_time: float, path: Path = LIVE_META_DIR / "live_uptime.txt") -> None:
    """Escreve o uptime formatado no arquivo lido pelo drawtext do FFmpeg
    (textfile=...:reload=1). Chamado a cada 1s por uma thread daemon em
    run_live.py."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"\U0001f534 LIVE {_format_uptime(time.time() - start_time)}", encoding="utf-8")
    except Exception as exc:
        log.debug("Falha ao escrever uptime da live: %s", exc)


def start_uptime_writer(start_time: float) -> threading.Thread:
    """Inicia thread daemon que escreve _data/live_uptime.txt a cada 1s."""
    stop_event = threading.Event()

    def _loop() -> None:
        path = LIVE_META_DIR / "live_uptime.txt"
        while not stop_event.is_set():
            write_uptime(start_time, path)
            stop_event.wait(1.0)

    thread = threading.Thread(target=_loop, name="LiveUptimeWriter", daemon=True)
    thread._stop_event = stop_event  # type: ignore[attr-defined]
    thread.start()
    return thread


def stop_uptime_writer(thread: threading.Thread) -> None:
    stop_event = getattr(thread, "_stop_event", None)
    if stop_event is not None:
        stop_event.set()
    if thread.is_alive():
        thread.join(timeout=2.0)


def discover_chat_id(service: Resource, broadcast_id: str) -> str | None:
    """Descobre o liveChatId de um broadcast via liveBroadcasts.list(part=snippet)."""
    try:
        resp = retry_youtube_call(
            service.liveBroadcasts().list(part="snippet", id=broadcast_id).execute
        )
    except Exception as exc:
        log.warning("Falha ao descobrir liveChatId do broadcast %s: %s", broadcast_id, exc)
        return None
    items = (resp or {}).get("items", [])
    if not items:
        return None
    chat_id = items[0].get("snippet", {}).get("liveChatId")
    return chat_id or None
