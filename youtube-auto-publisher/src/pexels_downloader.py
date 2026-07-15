"""
pexels_downloader.py - Download de videos do Pexels
"""
import json
import os
import random
import requests
from pathlib import Path
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import config

USED_VIDEO_IDS_FILE = config.DATA_DIR / "used_pexels_ids.json"
MAX_TRACKED_VIDEO_IDS = 300


def _load_used_video_ids() -> list:
    """Carrega ids de videos do Pexels ja usados recentemente (evita repetir o mesmo clipe)."""
    if not USED_VIDEO_IDS_FILE.exists():
        return []
    try:
        data = json.loads(USED_VIDEO_IDS_FILE.read_text(encoding="utf-8"))
        return [str(v) for v in data.get("ids", [])]
    except (json.JSONDecodeError, OSError):
        return []


def _save_used_video_ids(ids: list) -> None:
    USED_VIDEO_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ids": ids[-MAX_TRACKED_VIDEO_IDS:]}
    temp_path = USED_VIDEO_IDS_FILE.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload), encoding="utf-8")
    temp_path.replace(USED_VIDEO_IDS_FILE)


class PexelsDownloader:
    """Classe para download de videos do Pexels"""

    def __init__(self):
        self.api_key = config.PEXELS_API_KEY
        self.headers = {
            "Authorization": self.api_key,
            "User-Agent": config.HTTP_USER_AGENT,
        }
        self.video_url = config.PEXELS_VIDEO_URL
        self.temp_dir = config.TEMP_DIR
        self.session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def search_videos(self, query: str, per_page: int = 15) -> list:
        """Busca videos no Pexels"""
        url = f"{self.video_url}/search"
        params = {
            "query": query,
            "per_page": per_page,
            "orientation": "landscape",
            "size": "medium",
        }
        try:
            response = self.session.get(
                url,
                headers=self.headers,
                params=params,
                timeout=config.PEXELS_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("videos", [])
        except Exception as e:
            logger.warning(f"Erro ao buscar videos no Pexels: {e}")
            return []

    def get_video_download_url(self, video: dict) -> str:
        """Extrai URL de download do video"""
        files = video.get("video_files", [])
        hd_files = [f for f in files if f.get("quality") == "hd"]
        if hd_files:
            return hd_files[0]["link"]
        if files:
            return files[0]["link"]
        return ""

    def download_video(self, url: str, output_path: Path) -> bool:
        """Baixa um video para o caminho especificado"""
        try:
            response = self.session.get(
                url,
                stream=True,
                timeout=max(config.PEXELS_TIMEOUT_SECONDS, 60),
                headers={"User-Agent": config.HTTP_USER_AGENT},
            )
            response.raise_for_status()
            max_bytes = config.PEXELS_MAX_DOWNLOAD_MB * 1024 * 1024
            content_length = int(response.headers.get("content-length") or 0)
            if content_length > max_bytes:
                logger.warning(
                    f"Video ignorado por tamanho: {content_length / 1024 / 1024:.1f} MB"
                )
                return False
            output_path.parent.mkdir(parents=True, exist_ok=True)
            downloaded = 0
            too_large = False
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > max_bytes:
                        logger.warning(
                            f"Download interrompido por exceder {config.PEXELS_MAX_DOWNLOAD_MB} MB"
                        )
                        too_large = True
                        break
                    f.write(chunk)
            if too_large:
                output_path.unlink(missing_ok=True)
                return False
            return True
        except Exception as e:
            logger.warning(f"Erro ao baixar video: {e}")
            return False

    def download_clips_for_topic(
        self,
        topic: str,
        output_dir: Path,
        count: int = 5,
        num_clips: int | None = None,
    ) -> list:
        """Baixa multiplos clipes para um topico"""
        if num_clips is not None:
            count = num_clips
        count = max(1, min(int(count), config.VIDEO_MAX_CLIPS))
        output_dir.mkdir(parents=True, exist_ok=True)
        topic_translations = {
            "natureza": "nature", "tecnologia": "technology",
            "ciencia": "science", "historia": "history",
            "curiosidades": "curiosities", "saude": "health",
            "fitness": "fitness", "culinaria": "cooking food",
            "animais": "animals wildlife", "espaco": "space universe",
            "oceano": "ocean sea", "viagem": "travel",
        }
        search_query = (
            config.TOPIC_SEARCH_QUERIES.get(topic)
            or topic_translations.get(topic.lower())
            or topic
        )
        used_ids = _load_used_video_ids()

        def _fetch_unused(query: str) -> list:
            results = self.search_videos(query, per_page=max(count * 3, 15))
            fresh = [v for v in results if str(v.get("id")) not in used_ids]
            return fresh or results

        videos = _fetch_unused(search_query)
        if not videos:
            videos = _fetch_unused("nature")
        random.shuffle(videos)

        downloaded = []
        new_ids = []
        for i, video in enumerate(videos):
            if len(downloaded) >= count:
                break
            download_url = self.get_video_download_url(video)
            if not download_url:
                continue
            output_path = output_dir / f"clip_{i:03d}.mp4"
            if self.download_video(download_url, output_path):
                downloaded.append(output_path)
                video_id = video.get("id")
                if video_id is not None:
                    new_ids.append(str(video_id))

        if new_ids:
            _save_used_video_ids(used_ids + new_ids)

        return downloaded
