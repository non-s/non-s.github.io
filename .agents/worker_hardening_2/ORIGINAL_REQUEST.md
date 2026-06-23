## 2026-06-23T17:40:12Z

You are a versatile worker subagent. Your working directory is C:/Users/Julio/.gemini/antigravity/scratch/non-s.github.io/.agents/worker_hardening_2.
Your task is to refactor, optimize, and harden the WildBrief YouTube Shorts automation pipeline to address all identified audit gaps.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please implement the following changes:

1. Redundant Code Cleanup:
- In `utils/ai_helper.py`, remove the duplicate definition of `ai_text` (the one at line 247 without the `task` parameter) to ensure only the fully parameterized `ai_text` version is active.
- In `fetch_animals.py`, remove the duplicate definition of `_AI_PROMPT_TEMPLATE` (the first one, lines 397-471).

2. AI Engine & API Resilience:
- In `utils/ai_helper.py`, update the circuit breaker logic so that the Mistral circuit breaker trips not only on HTTP 429 status code, but also on HTTP 5xx errors and network timeouts.
- In `fetch_animals.py`, sanitize and wrap Pexels subject and other untrusted metadata inputs before interpolating them into the prompt (e.g., wrap in custom XML tags or clean up non-alphanumeric chars). Harden the validation logic `_copy_matches_visible_subject` so that it returns `False` if both the subject and script contain no animal terms when a strict animal term check is expected, preventing prompt injection bypasses.
- In `utils/broll.py`, log explicit warnings/errors (not just DEBUG logs) if the Pexels API key is missing or if the request returns non-200 status codes.
- In `fetch_animals.py`, validate the AI-generated JSON outputs for: word count limits (38-55 words), capitalization (no all-caps, no multiple punctuation), and missing keys. Implement simple repair logic (e.g. trimming punctuation or correcting formatting) if a minor constraint is violated, otherwise reject or regenerate.

3. FFmpeg & Video Composition:
- In `utils/video_compose.py`:
  - Update `_FONT_CANDIDATES` to include Windows and macOS fonts (e.g., "C:/Windows/Fonts/arialbd.ttf", "/Library/Fonts/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf") and update overlay drawing filters to use a default font family name (like "font='Arial'") if `fontfile` is not resolved, ensuring text overlays are never skipped.
  - Optimize zoom scale dimensions by scaling b-roll clips to `1.25x` target width/height (1350x2400) instead of CPU-heavy 4K resolution (2160x3840).
  - Replace the memory-heavy CPU-bound `loop` filter on uncompressed frames (which buffers up to 10,000 frames) with demuxer-level stream looping using `-stream_loop -1` input parameters.
  - Fix the volume drowning issue by setting `normalize=0` on the `amix` filter parameters.
  - Remove segment fade-in/fade-out filters that cause jarring blinking cuts.
  - Share the BGM/SFX audio loading and mixing logic between the `build_broll_short` and `build_static_short` pipelines so fallback videos have audio.
  - Guard the `random.choice` candidates selection: filter `bgm_candidates` and `sfx_candidates` for valid extensions (`.mp3`, `.wav`, `.m4a`, `.aac`) before checking list truthiness, resolving the `IndexError` crash.

4. Multi-Language Pipeline, Localization & Upload:
- In `generate_shorts.py`, update the Spanish (`es-MX`) dubbing pipeline to output generated files (MP4, JPG, JSON) to a dedicated `_videos_es-MX/` directory instead of storing them in the English `_videos/` directory with a suffix.
- In `upload_youtube.py`, dynamically route YouTube OAuth tokens per language channel (e.g., check output directory or use a `--language` argument to load `youtube_token_{LANGUAGE}.json` instead of a hardcoded `youtube_token.json`).
- Update `.github/workflows/youtube-bot.yml` to track, back up, and restore the Spanish done markers (`_videos_es-MX/shorts_done.json`) and run uploads for English and Spanish channels separately.
- In `utils/translation.py` / `generate_shorts.py`, translate/map the titles and key points correctly so Spanish/Portuguese videos do not contain English texts on-screen or in descriptions.
- In `utils/captions.py`, update the Whisper language hint and local Whisper fallback model (`tiny` instead of `tiny.en`) to match the current target language dynamically.
- Implement locale-specific branding overlays, CTAs, and `EMPHASIS_WORDS`.

5. Additional Bug Fixes:
- In `generate_shorts.py`, fix the NameError for `category` in `generate_short()` by ensuring it is properly defined or extracted (e.g., `story.get("category", "animals")`).
- Fix the type/interface mismatch on phrase lists in `tests/test_captions.py` / `utils/captions.py`.

6. Verification:
- Run `pytest` to ensure all 1026 tests pass successfully. Fix any reference to `tiktok` in `generate_shorts.py` to address the YouTube focus audit test failure.
- Verify end-to-end execution: run `python generate_shorts.py` for both the English/Portuguese and Spanish versions and check that it completes cleanly and generates correct videos under the correct directories (`_videos` and `_videos_es-MX`).

Report back your progress, passing tests, and the path to your handoff report.
