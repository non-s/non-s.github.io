# Progress Tracking

Last visited: 2026-06-23T16:53:38Z

## Task Checklist
- [ ] Redundant Code Cleanup
  - [ ] Remove duplicate definition of `ai_text` in `utils/ai_helper.py`
  - [ ] Remove duplicate definition of `_AI_PROMPT_TEMPLATE` in `fetch_animals.py`
- [ ] AI Engine & API Resilience
  - [ ] Mistral circuit breaker trips on 429, 5xx, and timeouts in `utils/ai_helper.py`
  - [ ] Sanitize and wrap Pexels subject and untrusted metadata in `fetch_animals.py`
  - [ ] Harden `_copy_matches_visible_subject` in `fetch_animals.py` to prevent prompt injection bypasses
  - [ ] Log warnings/errors if Pexels API key is missing or returns non-200 in `utils/broll.py`
  - [ ] Validate AI-generated JSON outputs (word count 38-55, capitalization, missing keys, simple repair logic) in `fetch_animals.py`
- [ ] FFmpeg & Video Composition
  - [ ] Update `_FONT_CANDIDATES` and default font overlay fallback in `utils/video_compose.py`
  - [ ] Optimize zoom scale dimensions (1.25x target width/height 1350x2400) in `utils/video_compose.py`
  - [ ] Replace memory-heavy CPU `loop` filter with demuxer-level stream looping (`-stream_loop -1`) in `utils/video_compose.py`
  - [ ] Fix volume drowning issue by setting `normalize=0` on `amix` filter parameters in `utils/video_compose.py`
  - [ ] Remove segment fade-in/fade-out filters in `utils/video_compose.py`
  - [ ] Share BGM/SFX audio loading/mixing between `build_broll_short` and `build_static_short` pipelines in `utils/video_compose.py`
  - [ ] Guard `random.choice` candidates selection for valid audio extensions in `utils/video_compose.py`
- [ ] Multi-Language Pipeline, Localization & Upload
  - [ ] Output Spanish dubbing files to `_videos_es-MX/` instead of `_videos/` with suffix in `generate_shorts.py`
  - [ ] Route YouTube OAuth tokens dynamically per language channel in `upload_youtube.py`
  - [ ] Update `.github/workflows/youtube-bot.yml` for Spanish done markers and separate runs
  - [ ] Translate/map titles and key points correctly to avoid English on-screen/description texts in `utils/translation.py` and `generate_shorts.py`
  - [ ] Update Whisper language hint and local model (`tiny`) dynamically in `utils/captions.py`
  - [ ] Implement locale-specific branding overlays, CTAs, and `EMPHASIS_WORDS`
- [ ] Bug Fixes from System Message
  - [ ] Fix undefined variable `category` NameError in `generate_short()` in `generate_shorts.py`
  - [ ] Fix type/interface mismatch on phrase lists in `tests/test_captions.py` and `utils/captions.py`
- [ ] Verification
  - [ ] Fix references to `tiktok` in `generate_shorts.py`
  - [ ] Run `pytest` to ensure all 1026 tests pass successfully
  - [ ] Verify end-to-end execution of English/Portuguese and Spanish pipelines
