"""
Shared utilities for GlobalBR News automation scripts.

Modules:
  ai_helper    — Mistral (primary) + Cerebras (fallback) text generation
  dedup        — Levenshtein + Jaccard title deduplication
  ranking      — Pre-AI relevance scoring for RSS entries
  retry        — retry_call() helper and with_retry() decorator
  text         — slug generation, sanitisation, TTS humaniser, RSS helpers
  video_common — Pillow drawing helpers + image download for the Shorts renderer
"""
