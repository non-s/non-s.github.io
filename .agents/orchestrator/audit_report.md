# WildBrief Pipeline Audit Report

This report synthesizes the architectural, functional, and editorial audit findings for the WildBrief YouTube Shorts automation pipeline.

---

## 1. Executive Summary
The WildBrief automation pipeline was audited across three main areas:
1. **AI Scripting & Prompts** (`fetch_animals.py`, `utils/ai_helper.py`)
2. **Video & Audio Composition** (`utils/video_compose.py`)
3. **Pipeline Orchestration & Localization** (`generate_shorts.py`, `upload_youtube.py`, workflows)

A total of 16 failing tests in the test suite were analyzed. We identified critical bottlenecks in rendering, vulnerabilities in prompt injection defenses, same-channel upload routing bugs for localized content, and audio/video generation crashes.

---

## 2. Key Findings & Gaps

### A. Video Composition & FFmpeg Gaps (M2 focus)
1. **OOM Risks (FFmpeg `loop` filter)**: Buffering 10,000 uncompressed frames on CPU causes massive RAM consumption (~12.44 GB for 4K frames).
2. **CPU Rendering Bottleneck**: Redundant 4K scaling on CPU instead of using `SHORT_W * 1.25` (1350x2400) for zoom operations, slowing down generation.
3. **Cross-Platform Overlay Bug**: Hardcoded Linux-only font paths (`/usr/share/fonts/...`) disable all text overlays (hooks, watermarks, cover text, CTAs) on Windows/macOS.
4. **Audio Balance Bug**: Omission of `normalize=0` in the `amix` filter heavily attenuates the TTS narrator voice when background music/sound effects are present.
5. **Static Fallback Silence**: The fallback static generation pipeline lacks BGM/SFX audio composition entirely.
6. **BGM/SFX Selection IndexError**: An empty candidates list (due to filtering out files like `.gitkeep`) causes `random.choice` to raise an `IndexError`, crashing the video composition tests.
7. **Jarring Fade Transitions**: The 0.08s fade-in/fade-out filter on every b-roll segment causes a jarring blinking effect.

### B. AI Engine & Prompt Injection Gaps (M2 focus)
8. **Duplicate Function/Variable Definitions**: Dead code blocks in `utils/ai_helper.py` (duplicate `ai_text`) and `fetch_animals.py` (duplicate `_AI_PROMPT_TEMPLATE`) create logic risks.
9. **Circuit Breaker Timeout Gaps**: Mistral's circuit breaker only trips on HTTP 429, leaving the pipeline vulnerable to hangs/timeouts on 5xx errors or network drops.
10. **Prompt Injection System Guard Mismatch**: The system prompt references untrusted fields like "animal title" or "description" which are not present in the user-facing template prompts.
11. **Bypassable Content Validation**: Video metadata (subject) from Pexels is directly interpolated into prompts without sanitization. An injection omitting animal terms bypasses the validation guards (`_copy_matches_visible_subject`) completely.
12. **Silent Pexels API Failures**: Empty results due to rate limits (429) or missing API keys fail silently.
13. **Editorial Gating Absence**: The AI-generated output is not validated against editorial guidelines (word count, casing, JSON format repair) before enqueuing.

### C. Pipeline Localization & Upload Gaps (M3/M4 focus)
14. **Same-Channel Upload Bug**: Translated Spanish (`es-MX`) videos are output to the English `_videos` directory with an `_es` suffix and are automatically uploaded to the English channel.
15. **Missing Token & Workflow Separation**: Token routing is hardcoded to a single `youtube_token.json`. Localized done markers (e.g. `shorts_done.json` for Spanish) are not tracked or committed in GHA workflow files.
16. **Translation Bypass Bottlenecks**:
    - `"title"` and `"description"` are missing from translatable fields, leading to English titles/bullet points on Spanish/Portuguese shorts.
    - Whisper uses the global process environment `LANGUAGE` ("en") instead of the local target language during Spanish dubbing runs.
    - Local fallback uses `tiny.en` which fails on non-English audio.
17. **Static Fallback Retention Gaps**: Static fallback videos lack the Easter Egg filter and pacing cuts.
18. **A/B Testing Regional Pollution**: Experiments and winners are not segmented by language/locale.
19. **Fatal Runtime NameError**: Undefined variable `category` is used in `generate_short()`.
20. **Captions Interface Mismatch**: Subtitle/captions tests fail due to an interface type mismatch on phrase lists in `tests/test_captions.py`.

---

## 3. Remediations & Action Plan

### Step 1: Apex Code Hardening & API Resilience (M2)
- Remove duplicate definitions of `ai_text` and `_AI_PROMPT_TEMPLATE`.
- Extend the circuit breaker to handle network timeouts and HTTP 5xx errors.
- Wrap all untrusted Pexels metadata fields in XML blocks and sanitize them. Harden animal term checks.
- Add warnings for missing Pexels keys and log API errors explicitly.
- Add post-generation validation and JSON format repair for AI outputs.
- Fix the font paths list to include Windows and macOS system fonts, and fall back to font name if files do not exist.
- Replace the memory-heavy FFmpeg `loop` filter with `-stream_loop -1` input flags.
- Optimize b-roll scaling to 1.25x (1350x2400) instead of 4K.
- Disable volume normalization on the `amix` filter to prevent TTS attenuation.
- Fix the `random.choice` candidate list selection logic to prevent `IndexError` on non-audio files (like `.gitkeep`).
- Remove the blink-inducing segment fades.
- Share BGM/SFX mixing between b-roll and static fallback paths.

### Step 2: Viral Hooks & A/B Testing Localization (M3)
- Add target language support to Whisper/transcription hints and default to multilingual local models (`tiny`) for non-English locales.
- Add locale-specific translations for CTA overlay text, logos, and emphasis word styling.
- Align static fallback retention features (BGM mixing, Easter Egg, pacing).
- Segment A/B testing configurations and winners by language/locale (e.g. `experiments_pt-BR.json`).

### Step 3: Multi-Language Pipeline Upload Routing (M4)
- Route Spanish outputs to `_videos_es-MX/` directory.
- Update `upload_youtube.py` to support language-specific tokens (`youtube_token_{LANGUAGE}.json`).
- Update `.github/workflows/youtube-bot.yml` to restore and backup Spanish done markers, and run separate jobs for each language upload.
