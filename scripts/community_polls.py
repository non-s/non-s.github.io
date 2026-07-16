#!/usr/bin/env python3
"""
Community Polls Generator
Generates highly engaging trivia polls about animals for the YouTube Community Tab.
Saves suggestions into a markdown file for easy copying by the channel owner.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from utils.ai_helper import ai_text

POLLS_FILE = ROOT / "community_polls_suggestions.md"

def generate_poll() -> str:
    print("Generating a new highly engaging Community Poll...")
    prompt = (
        "You are an expert YouTube Community Manager for an animal facts channel.\n"
        "Generate a highly engaging, moderately difficult trivia poll about animals/wildlife.\n\n"
        "Rules:\n"
        "1. Write in English.\n"
        "2. Include a catchy question (e.g., 'Which of these animals has the strongest bite force?').\n"
        "3. Provide exactly 4 options (A, B, C, D).\n"
        "4. Include the correct answer in a format that encourages people to comment (e.g., 'Comment your guess! The answer is hidden below 👇').\n"
        "5. Keep the tone fun and curious, use emojis.\n"
        "Return the output as plain text formatted for a YouTube post."
    )
    
    try:
        response = ai_text(prompt, task="community_poll")
        return response.strip()
    except Exception as e:
        print(f"AI generation failed: {e}")
        return ""

def main():
    print("📊 Initiating Community Polls Generator...")
    
    poll = generate_poll()
    if not poll:
        print("Failed to generate poll.")
        return
        
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    POLLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POLLS_FILE, "a", encoding="utf-8") as f:
        f.write(f"## 🎯 Enquete para a Aba Comunidade ({now_str})\n")
        f.write("Copie e cole isso na Aba Comunidade do seu YouTube:\n\n")
        f.write(f"{poll}\n\n")
        f.write("---\n\n")
        
    print(f"✅ Nova enquete salva em: {POLLS_FILE}")

if __name__ == "__main__":
    main()
