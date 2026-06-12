"""Audience-comment learning for Wild Brief."""

from __future__ import annotations

import html
import re
from collections import Counter

_STOPWORDS = {
    "about",
    "after",
    "again",
    "animal",
    "animals",
    "because",
    "brief",
    "could",
    "great",
    "learn",
    "maybe",
    "please",
    "really",
    "short",
    "shorts",
    "thanks",
    "their",
    "there",
    "these",
    "thing",
    "video",
    "watch",
    "where",
    "which",
    "while",
    "would",
    "youtube",
}

_ANIMALS = {
    "ant",
    "bat",
    "bear",
    "bee",
    "bird",
    "butterfly",
    "cat",
    "chicken",
    "chimpanzee",
    "cow",
    "crocodile",
    "deer",
    "dog",
    "dolphin",
    "duck",
    "eagle",
    "elephant",
    "fish",
    "fox",
    "goat",
    "gorilla",
    "horse",
    "leopard",
    "lion",
    "monkey",
    "octopus",
    "owl",
    "parrot",
    "penguin",
    "seal",
    "shark",
    "snake",
    "tiger",
    "turtle",
    "whale",
    "wolf",
}


def clean_comment(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([?.!,;:])", r"\1", text)


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z][a-z0-9'-]{2,}", text.lower()) if token not in _STOPWORDS]


def _animal_tokens(text: str) -> list[str]:
    out: list[str] = []
    for token in _tokens(text):
        singular = token[:-1] if token.endswith("s") else token
        if singular in _ANIMALS and singular not in out:
            out.append(singular)
    return out


def analyze_comments(comments: list[dict], limit: int = 8) -> dict:
    """Summarise comments into free audience signals."""
    keywords: Counter[str] = Counter()
    animals: Counter[str] = Counter()
    questions: list[dict] = []
    total_likes = 0
    for raw in comments:
        text = clean_comment(str(raw.get("text") or raw.get("textDisplay") or raw.get("textOriginal") or ""))
        if not text:
            continue
        likes = int(raw.get("likeCount", 0) or 0)
        total_likes += likes
        keywords.update(_tokens(text))
        animals.update(_animal_tokens(text))
        if "?" in text or re.search(r"\b(can you|do one|what about|why do|how do)\b", text.lower()):
            questions.append(
                {
                    "text": text[:240],
                    "likes": likes,
                    "video_id": raw.get("video_id", ""),
                }
            )
    questions.sort(key=lambda item: (int(item.get("likes", 0) or 0), len(item.get("text", ""))), reverse=True)
    top_questions = questions[:limit]
    return {
        "comments_sampled": len(
            [
                c
                for c in comments
                if clean_comment(str(c.get("text") or c.get("textDisplay") or c.get("textOriginal") or ""))
            ]
        ),
        "total_comment_likes": total_likes,
        "question_count": len(questions),
        "requested_animals": [key for key, _ in animals.most_common(limit)],
        "topic_keywords": [key for key, _ in keywords.most_common(limit)],
        "top_questions": top_questions,
        "content_prompts": [f"Answer this viewer question: {item['text']}" for item in top_questions[:5]],
    }
