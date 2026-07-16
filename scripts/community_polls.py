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
LIVE_VOTES_FILE = ROOT / "_data" / "live_votes.json"


def build_live_vote_update() -> str:
    """Surface the running !vote tally from the 24/7 live chat as a
    ready-to-post Community update, without consuming the votes (the long
    video generator consumes them once it picks a winner)."""
    if not LIVE_VOTES_FILE.exists():
        return ""
    try:
        votes = json.loads(LIVE_VOTES_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to read live votes: {e}")
        return ""
    if not votes:
        return ""

    ranked = sorted(votes.items(), key=lambda item: item[1], reverse=True)[:5]
    total = sum(count for _, count in ranked)
    lines = [f"{i}. {name.title()} — {count} vote(s)" for i, (name, count) in enumerate(ranked, start=1)]
    leader = ranked[0][0].title()
    return (
        "🗳️ Placar atual da votação ao vivo (chat, !vote [animal]):\n\n"
        + "\n".join(lines)
        + f"\n\nLíder no momento: {leader}! Ele vira o próximo episódio do documentário se continuar na frente. "
        "Digite !vote [animal] no chat da live 24/7 para escolher o próximo assunto. 🦁🐋🦅"
    )


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

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    POLLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    wrote_something = False

    live_vote_update = build_live_vote_update()
    if live_vote_update:
        with open(POLLS_FILE, "a", encoding="utf-8") as f:
            f.write(f"## 🗳️ Placar da votação ao vivo ({now_str})\n")
            f.write("Copie e cole isso na Aba Comunidade do seu YouTube:\n\n")
            f.write(f"{live_vote_update}\n\n")
            f.write("---\n\n")
        print(f"✅ Placar da votação ao vivo salvo em: {POLLS_FILE}")
        wrote_something = True

    poll = generate_poll()
    if poll:
        with open(POLLS_FILE, "a", encoding="utf-8") as f:
            f.write(f"## 🎯 Enquete para a Aba Comunidade ({now_str})\n")
            f.write("Copie e cole isso na Aba Comunidade do seu YouTube:\n\n")
            f.write(f"{poll}\n\n")
            f.write("---\n\n")
        print(f"✅ Nova enquete salva em: {POLLS_FILE}")
        wrote_something = True

    if not wrote_something:
        print("Failed to generate poll.")

if __name__ == "__main__":
    main()
