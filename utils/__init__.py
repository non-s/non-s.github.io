"""
Shared utilities for GlobalBR News automation scripts.

Modules:
  retry       — retry_call() helper and with_retry() decorator with exponential back-off
  frontmatter — Jekyll frontmatter parser (parse, get_str, get_list)
  dedup       — Levenshtein + Jaccard title deduplication
  text        — slug generation, text sanitisation, RSS helpers
"""
