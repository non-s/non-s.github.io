import json
import os
import subprocess
import sys
from pathlib import Path

INTENTS_FILE = Path("_data/upload_intents.jsonl")
TIKTOK_INTENTS_FILE = Path("_data/tiktok_intents.jsonl")

def main():
    if not INTENTS_FILE.exists():
        print("No YouTube upload intents found. Exiting.")
        return

    # Load all YouTube uploaded intents
    youtube_uploaded = {}
    with open(INTENTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("status") == "uploaded":
                vid_path = data.get("video")
                if vid_path:
                    youtube_uploaded[vid_path] = data

    # Load already synced TikTok videos
    tiktok_synced = set()
    if TIKTOK_INTENTS_FILE.exists():
        with open(TIKTOK_INTENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("status") == "uploaded":
                    tiktok_synced.add(data.get("video"))

    # Find videos that are on YouTube but NOT on TikTok
    to_upload = []
    for vid_path, data in youtube_uploaded.items():
        if vid_path not in tiktok_synced:
            # Check if file still exists on disk
            if Path(vid_path).exists():
                to_upload.append(data)

    if not to_upload:
        print("TikTok is fully synced. No new videos to upload.")
        return

    # Upload each pending video
    for data in to_upload:
        vid_path = data["video"]
        title = data.get("title", "New WildBrief Short! #wildlife #nature #animals")
        desc = f"{title} #wildbrief #wildlife #nature #animals #shorts"
        
        print(f"Syncing {vid_path} to TikTok...")
        
        # Run upload_tiktok.py
        cmd = [
            sys.executable,
            "scripts/upload_tiktok.py",
            "--video", vid_path,
            "--desc", desc
        ]
        
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            # Record success
            record = {
                "video": vid_path,
                "title": title,
                "status": "uploaded"
            }
            with open(TIKTOK_INTENTS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            print(f"Successfully synced {vid_path} to TikTok.")
        else:
            print(f"Failed to sync {vid_path} to TikTok.")
            # Break to avoid spamming failures if session is invalid
            sys.exit(1)

if __name__ == "__main__":
    main()
