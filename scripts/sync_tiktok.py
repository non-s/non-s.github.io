import json
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

    for data in to_upload:
        vid_path = data["video"]
        # Convert YouTube title to a viral TikTok hook
        raw_title = data.get("title", "Você não vai acreditar no que esse animal fez!")
        
        # TikTok SEO Strategy: Hook + Emotion + Viral Hashtags
        viral_hook = f"😱 {raw_title}"
        cta = "Qual o seu animal preferido? Comenta aí embaixo! 👇"
        
        # Dynamic hashtag logic based on keywords
        base_tags = ["#wildbrief", "#vidaanimal", "#natureza", "#curiosidades", "#animaisdotiktok", "#fyp", "#viral"]
        lower_title = raw_title.lower()
        
        if "leão" in lower_title or "lion" in lower_title:
            base_tags.extend(["#leao", "#predador", "#reidaselva"])
        if "tubarão" in lower_title or "shark" in lower_title:
            base_tags.extend(["#tubarao", "#oceano", "#mar"])
        if "tigre" in lower_title or "tiger" in lower_title:
            base_tags.extend(["#tigre", "#selva"])
        if "cobra" in lower_title or "snake" in lower_title:
            base_tags.extend(["#cobra", "#serpente", "#veneno"])
            
        tags_str = " ".join(base_tags)
        
        desc = f"{viral_hook}\n\n{cta}\n\n{tags_str}"
        
        print(f"Syncing {vid_path} to TikTok with SEO:")
        print(f"Description:\n{desc}\n")
        
        # Run upload_tiktok.py
        cmd = [
            sys.executable,
            "scripts/upload_tiktok.py",
            "--video", vid_path,
            "--desc", desc
        ]
        
        result = subprocess.run(cmd)  # nosec B603
        
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
