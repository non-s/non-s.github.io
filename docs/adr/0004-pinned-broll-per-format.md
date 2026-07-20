# ADR 0004: Pinned B-Roll Clip Per Format

## Status
Accepted

## Context
Early versions of the pipeline pooled b-roll from Pixabay searches, sometimes allowing off-brand clips to slip through (e.g., 3D renders instead of anime).

## Decision
Standardize on **one hand-picked b-roll clip per format** (Shorts, horizontal mix, live):
- `_assets/video/pinned_short_clip.mp4` — 30–58s vertical loop
- `_assets/video/pinned_mix_clip.mp4` — 1-hour horizontal loop
- `_assets/video/pinned_live_clips/*.mp4` — rotating set of ~5 clips, swapped weekly

Both generators (`generate_lofi_short.py`, `generate_lofi_mix.py`) loop this single clip.

## Rationale
1. **Brand consistency:** Every video uses the same trusted visual baseline
2. **Eliminates curation risk:** No tag-based filtering, no off-brand clips
3. **Faster rendering:** Single clip is pre-processed once with baked crossfade
4. **Mood decoupling:** Mood (title/tags/music) varies per video; b-roll stays constant
5. **Live stream resilience:** Single clip loops indefinitely; no file I/O during stream

## Consequences
- ✅ Quality control: one excellent clip is better than 100 mediocre auto-selected ones
- ✅ Faster delivery: no per-video clip selection or preprocessing
- ⚠️ Visual monotony: all Shorts use the same background (mitigated by music/title variety)
- ⚠️ Requires upfront curation: choosing the "perfect" clip is time-intensive
- ⚠️ Live clip rotation manual: no automatic refresh; requires weekly curator intervention

## Alternatives Considered
1. **Pool of recent clips:** Reintroduces off-brand risk; slower selection
2. **Per-mood clip selection:** More variety, but 10x more likely to have off-brand slips
3. **AI-generated backgrounds:** Violates zero-cost principle; requires API key

## See Also
- `generate_lofi_short.py` — pinned clip usage in Shorts
- `generate_lofi_mix.py` — pinned clip usage in mix
- `scripts/live_stream_dynamic.py` — pinned clip rotation in 24/7 stream
