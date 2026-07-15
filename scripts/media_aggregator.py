#!/usr/bin/env python3
"""Media Aggregator: The ultimate yt-dlp Swiss Army Knife for WildBrief.

This script implements advanced media extraction capabilities:
1. scrape: Extracts SEO tags and stats from competitors.
2. transcript: Pulls subtitles for script cloning.
3. audio: Downloads high-quality MP3 of meme/viral audio.
4. slice: Surgically extracts a specific time slice of a 4K video.
"""

import sys
import json
import logging
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("media_aggregator")

DATA_DIR = ROOT / "_data" / "espionage"
AUDIO_DIR = ROOT / "_assets" / "audio" / "sfx"
BROLL_DIR = ROOT / "_data" / "broll_cache"

for d in [DATA_DIR, AUDIO_DIR, BROLL_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def run_ytdlp(cmd_args: list[str]) -> subprocess.CompletedProcess:
    """Wrapper to safely run yt-dlp via sys.executable."""
    cmd = [sys.executable, "-m", "yt_dlp"] + cmd_args
    log.info(f"Running command: {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True)


def scrape_metadata(url: str):
    """Downloads full JSON metadata (tags, descriptions, views) from a video."""
    log.info(f"Scraping metadata for {url}...")
    
    cmd = ["--dump-json", "--no-playlist", url]
    result = run_ytdlp(cmd)
    
    if result.returncode == 0 and result.stdout:
        try:
            data = json.loads(result.stdout)
            vid = data.get("id", "unknown")
            save_path = DATA_DIR / f"{vid}_metadata.json"
            save_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            log.info(f"Metadata saved to {save_path}")
            log.info(f"Title: {data.get('title')}")
            log.info(f"Views: {data.get('view_count')}")
            log.info(f"Tags: {data.get('tags', [])}")
        except Exception as e:
            log.error(f"Failed to parse metadata: {e}")
    else:
        log.error(f"Failed to scrape metadata: {result.stderr}")


def extract_transcript(url: str):
    """Downloads auto-generated or manual subtitles as VTT."""
    log.info(f"Extracting transcript for {url}...")
    dest = DATA_DIR / "%(id)s"
    
    cmd = [
        "--write-auto-subs", "--write-subs", 
        "--sub-langs", "en,pt", 
        "--skip-download", 
        "-o", str(dest), 
        url
    ]
    result = run_ytdlp(cmd)
    if result.returncode == 0:
        log.info("Transcript downloaded successfully.")
    else:
        log.error(f"Failed to extract transcript: {result.stderr}")


def extract_audio(url: str, output_name: str):
    """Downloads only the audio and converts to MP3."""
    log.info(f"Extracting audio from {url} to {output_name}...")
    dest = AUDIO_DIR / f"{output_name}.%(ext)s"
    
    cmd = [
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", str(dest),
        url
    ]
    result = run_ytdlp(cmd)
    if result.returncode == 0:
        log.info("Audio extracted successfully.")
    else:
        log.error(f"Failed to extract audio: {result.stderr}")


def download_fraction(url: str, start_time: str, end_time: str, output_name: str):
    """Surgically downloads a slice of a video using ffmpeg args."""
    log.info(f"Slicing {url} from {start_time} to {end_time}...")
    dest = BROLL_DIR / f"{output_name}.mp4"
    
    cmd = [
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
        "--download-sections", f"*{start_time}-{end_time}",
        "--force-keyframes-at-cuts",
        "-o", str(dest),
        url
    ]
    result = run_ytdlp(cmd)
    if result.returncode == 0:
        log.info(f"Fraction downloaded successfully to {dest}.")
    else:
        log.error(f"Failed to download fraction: {result.stderr}")


def main():
    parser = argparse.ArgumentParser(description="WildBrief Media Aggregator")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    p_meta = subparsers.add_parser("scrape")
    p_meta.add_argument("url", help="Target video URL")
    
    p_trans = subparsers.add_parser("transcript")
    p_trans.add_argument("url", help="Target video URL")
    
    p_audio = subparsers.add_parser("audio")
    p_audio.add_argument("url", help="Target video URL")
    p_audio.add_argument("name", help="Output filename without extension")
    
    p_slice = subparsers.add_parser("slice")
    p_slice.add_argument("url", help="Target video URL")
    p_slice.add_argument("start", help="Start time (e.g., 00:01:15)")
    p_slice.add_argument("end", help="End time (e.g., 00:01:25)")
    p_slice.add_argument("name", help="Output filename without extension")
    
    args = parser.parse_args()
    
    if args.command == "scrape":
        scrape_metadata(args.url)
    elif args.command == "transcript":
        extract_transcript(args.url)
    elif args.command == "audio":
        extract_audio(args.url, args.name)
    elif args.command == "slice":
        download_fraction(args.url, args.start, args.end, args.name)

if __name__ == "__main__":
    main()
