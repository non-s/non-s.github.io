# Task Briefing: WildBrief Pipeline Hardening & Localization

You are teamwork_preview_worker. Your mission is to implement changes, refactor the codebase to address all remaining audit gaps, fix tests, and perform E2E verification of the WildBrief YouTube Shorts automation pipeline.

## MANDATORY INTEGRITY WARNING
> DO NOT CHEAT. All implementations must be genuine. DO NOT
> hardcode test results, create dummy/facade implementations, or
> circumvent the intended task. A Forensic Auditor will independently
> verify your work. Integrity violations WILL be detected and your
> work WILL be rejected.

## Task Details

Please perform the following tasks:

### 1. Code Hardening & Optimization
- **Redundant Code**:
  - Double check that there are no duplicate definitions of `ai_text` in `utils/ai_helper.py` and `_AI_PROMPT_TEMPLATE` in `fetch_animals.py`. If any exist, remove them.
- **AI Engine & API Resilience**:
  - Ensure the Mistral circuit breaker in `utils/ai_helper.py` trips not only on HTTP 429 but also on HTTP 5xx errors and network/timeouts.
  - Sanitize and wrap Pexels subject and untrusted metadata in `fetch_animals.py` using `wrap_untrusted` before inserting them into prompts.
  - Harden `_copy_matches_visible_subject` in `fetch_animals.py` to prevent prompt injection bypasses.
  - Log warning messages when Pexels API key is missing or when the API requests return non-200 responses in `utils/broll.py`.
  - Validate and repair AI-generated JSON outputs (word count 38-55, capitalization, missing keys) in `fetch_animals.py` using `_validate_and_repair_json`.
- **FFmpeg & Video Composition**:
  - Cross-platform font paths list: In `utils/video_compose.py`, make sure the font search includes Windows fonts (e.g. `C:/Windows/Fonts/arialbd.ttf` or `arial.ttf`) and fallback to a default font name if paths do not exist.
  - Zoom optimization: Optimize the zoom dimensions in `utils/video_compose.py` to target `SHORT_W * 1.25` (1350x2400) instead of 4K.
  - Replace memory-heavy CPU `loop` filter with demuxer-level stream looping (`-stream_loop -1` or similar) in `utils/video_compose.py`.
  - Fix volume drowning by setting `normalize=0` on `amix` filter parameters in `utils/video_compose.py`.
  - Remove segment fade-in/fade-out filters in `utils/video_compose.py`.
  - Guard `random.choice` candidates selection for valid audio extensions (not picking `.gitkeep`) in `utils/video_compose.py`.
  - Share BGM/SFX mixing between b-roll and static fallback paths in `utils/video_compose.py`.

### 2. Viral Hooks, A/B Testing & Localization
- **Localizations**:
  - Add target language support to Whisper/transcription hints.
  - Dynamically select the Whisper local model (e.g., multilingual `"tiny"` instead of `"tiny.en"`) in `utils/captions.py` when LANGUAGE is non-English.
  - Map `title` and `description` to the translatable fields in `utils/translation.py` so they get translated for PT-BR and ES-ES versions.
  - Route Spanish outputs to `_videos_es-MX/` instead of `_videos/` with suffix in `generate_shorts.py`.
  - Update `upload_youtube.py` to route YouTube OAuth tokens dynamically per language channel (`youtube_token_{LANGUAGE}.json`).
  - Update `.github/workflows/youtube-bot.yml` to backup and restore Spanish done markers (`shorts_done_es.json`), running separate jobs.
  - Implement locale-specific CTAs, logos, and `EMPHASIS_WORDS`.

### 3. Bug Fixes
- Fix undefined variable `category` NameError in `generate_short()` in `generate_shorts.py`.
- Fix the type/interface mismatch on phrase lists in `tests/test_captions.py` and `utils/captions.py`.
- Fix references to `"tiktok"` in `generate_shorts.py` (replace with `"short-form"` to clear the focus audit).

## Verification Requirements
1. Run `pytest` to run the test suite and ensure all tests pass.
2. Run `python generate_shorts.py` for both `en/pt-BR` and `es-ES` versions to ensure end-to-end video and audio generation is fully functional and correct.
3. Document commands used, results, and verify that the output layout conforms to `PROJECT.md`.
4. Write your handoff report to `handoff.md` in your working directory.

## 2026-06-23T14:43:23-03:00
Resume WildBrief pipeline hardening. Read the original request at C:/Users/Julio/.gemini/antigravity/scratch/non-s.github.io/.agents/worker_hardening_gen2/ORIGINAL_REQUEST.md and briefing at C:/Users/Julio/.gemini/antigravity/scratch/non-s.github.io/.agents/worker_hardening_gen2/BRIEFING.md. Complete all tasks, run the tests to verify, and write a handoff report at C:/Users/Julio/.gemini/antigravity/scratch/non-s.github.io/.agents/worker_hardening_gen2/handoff.md. Report completion back to the parent orchestrator f5329f9b-7007-416c-8401-5adc6b6aaf96.

