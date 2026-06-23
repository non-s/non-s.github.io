# Handoff Report — explorer_audit_3

## 1. Observation

During our read-only audit of the orchestration pipeline, uploader, viral hooks, and multi-language structures, we directly observed the following from the codebase and the test runner output:

### Pipeline Execution & Error Handling Flaws
1. **Fatal Runtime Crash: Undefined Variable `category` in `generate_short`**
   - **Locations**: `generate_shorts.py` lines 2081, 2087, 2212, 2249, 2267.
   - **Verbatim Error**:
     ```
     FAILED tests/test_e2e_smoke.py::test_end_to_end_generate_short_ships_metadata - NameError: name 'category' is not defined
     ```
   - **Observation**:
     Inside `generate_short(story: dict, tmp_dir: Path, lang: str = "en")`, the variable `category` is used multiple times (such as in `pick_voice` and Solid Color background fallbacks) but is never defined in the function's scope. It must be initialized (e.g., `category = story.get("category", "wildlife")`).

2. **Fatal Audio Mix Crash: IndexError in BGM/SFX Selection**
   - **Location**: `utils/video_compose.py` line 349–350.
   - **Verbatim Error**:
     ```
     E   IndexError: Cannot choose from an empty sequence
     ```
   - **Observation**:
     ```python
     bgm_candidates = list(Path("_assets/audio/bgm").glob("*.*"))
     bgm_path = random.choice([p for p in bgm_candidates if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac")]) if bgm_candidates else None
     ```
     Checking `if bgm_candidates` only ensures the directory contains files. If the files do not match the suffix filters (e.g. `.gitkeep`), the list comprehension returns an empty list, and passing it to `random.choice` raises an `IndexError`.

3. **Shared Upload Directory / Same-Channel Upload Bug**
   - **Locations**: `generate_shorts.py` lines 2594–2607, `upload_youtube.py` lines 28–30, 79–80, and 61–65.
   - **Observation**:
     When running `generate_shorts.py` with `LANGUAGE=en`, it calls the Spanish (`es-MX`) dubbing pipeline inline. The outputs are placed in the English output folder `_videos/` (renamed with the suffix `_es`, e.g. `short-slug-date_es.mp4` and `short-slug-date_es.json`).
     `upload_youtube.py` then scans `_videos/` and grabs all files starting with `"short-"`, including `short-slug-date_es.json`.
     Since `upload_youtube.py` lacks token-routing logic (always using `youtube_token.json`), it uploads both the English and Spanish videos to the English channel.

4. **Missing Spanish done marker tracking in GitHub Actions**
   - **Location**: `.github/workflows/youtube-bot.yml` lines 456–461, 480–482.
   - **Observation**:
     The workflow only commits `_videos/shorts_done.json` and `_videos_pt-BR/shorts_done.json`. It fails to track Spanish done markers (`_videos_es-MX/shorts_done.json` or `_videos/shorts_done.json`'s Spanish entries), leading to lost state and duplicate uploads.

5. **Focus Audit Blocked Word Failure**
   - **Location**: `generate_shorts.py` line 2490, `tests/test_youtube_focus_audit.py` line 45.
   - **Verbatim Error**:
     ```
     AssertionError: legacy platform references found:
       generate_shorts.py: tiktok
     ```
   - **Observation**:
     `generate_shorts.py` references the blocked platform name `"tiktok"`, failing the repository's strict focus checks.

6. **Test Suite Interface Mismatch (Captions)**
   - **Location**: `tests/test_captions.py` lines 31, 40, 61, 77.
   - **Verbatim Errors**:
     ```
     E   AttributeError: 'list' object has no attribute 'word'
     E   TypeError: 'Caption' object is not subscriptable
     ```
   - **Observation**:
     `utils/captions.py`'s functions `group_words_into_phrases` and `write_ass` expect or return `list[list[Caption]]` structures. The tests in `tests/test_captions.py` pass a flat `list[Caption]` to `write_ass` and evaluate elements of `phrases` expecting single `Caption` properties rather than lists, causing the entire captions test suite to fail.

### Language Localization Bottlenecks
1. **Un-translated Title Bug (Hardcoded English Titles)**
   - **Location**: `generate_shorts.py` line 1994, `utils/translation.py` lines 81–89.
   - **Observation**:
     `title = story.get("title") or story.get("seo_title") or title`
     `translate_story()` translates `"seo_title"` but leaves `"title"` (which is English from `_queue_to_story()`) unchanged. Because `story.get("title")` is prioritized, translated videos retain English titles.

2. **Un-translated Key Points and English Descriptions**
   - **Location**: `generate_shorts.py` line 2246, `utils/translation.py` lines 81–89.
   - **Observation**:
     `points = extract_key_points(story.get("description", ""))`
     `"description"` is not in `_TRANSLATABLE_FIELDS`, meaning translated fallbacks and thumbnails feature English bullet points.

3. **Whisper Language Hint and Local Model Fallback Bug**
   - **Location**: `utils/captions.py` lines 77–80, 180.
   - **Observation**:
     `_whisper_language()` reads `os.environ.get("LANGUAGE", "en")` which remains `"en"` during the inline Spanish run. Additionally, the local fallback `transcribe_faster_whisper` defaults to `model_name="tiny.en"`, which is an English-only model and will fail on foreign audio.

4. **Subtitles and On-screen branding Hardcoded in English**
   - **Location**: `utils/captions.py` lines 255–319, `generate_shorts.py` lines 740, 809, 818, 822, 1493.
   - **Observation**:
     - `EMPHASIS_WORDS` is English-only, preventing caption word-highlighting on translated shorts.
     - On-screen CTA badges and logos (e.g. `"NATURE BRIEF"`, `"FOLLOW FOR WILD NATURE"`) are hardcoded in English.

### Viral Retention Hooks & A/B Testing Framework Strategy
1. **Pacing, Easter Egg, and SFX Fallback Discrepancy**
   - **Location**: `utils/video_compose.py` (`build_broll_short` vs `build_static_short`).
   - **Observation**:
     The static fallback path `build_static_short` misses the Easter Egg filter, has no BGM/SFX mixing (maps `1:a` directly), and uses a slow zoom instead of high-energy pacing, leading to significant retention drops on fallbacks.

---

## 2. Logic Chain

1. **Pipeline Execution Flaws**:
   - `generate_short` uses `category` without local binding or function-level argument definition, causing `NameError`.
   - `random.choice` receives an empty list when files exist in BGM/SFX folders but none clear the extension filter, causing `IndexError`.
   - Spanish videos are output directly to `_videos/` and collected by `glob("*.json")`, then uploaded via `youtube_token.json`.
   - *Therefore*, the pipeline crashes during generation, and if bypassed, Spanish videos are incorrectly published to the English channel.

2. **Localization Bottlenecks**:
   - `translate_story` leaves `"title"` and `"description"` in English.
   - *Therefore*, the English title is prioritized on-screen, and English bullet points are displayed on Spanish/Portuguese static fallbacks.
   - `_whisper_language()` reads process environment `LANGUAGE` which stays `"en"` during inline runs.
   - *Therefore*, Whisper attempts English transcription on Spanish audio, and the local fallback `tiny.en` fails on non-English files.

3. **Viral Retention & A/B Testing Gaps**:
   - `build_static_short` maps audio directly and lacks micro-animation pacing.
   - *Therefore*, fallback videos suffer severe retention drops.
   - The A/B testing registry doesn't segment logs by locale or track visual hooks.
   - *Therefore*, regional winner pollution occurs, and retention cannot be optimized.

---

## 3. Caveats

- We did not verify the behavior of the YouTube API upload calls directly as we operate in a read-only investigation environment.
- We assumed that `YOUTUBE_TOKEN` secrets in the repository belong to the English channel; we did not examine the contents of the secret directly.
- We did not test Whisper transcription with active Groq API keys since no keys are present in the local environment and we are in CODE_ONLY mode.

---

## 4. Conclusion

The pipeline has severe architectural flaws in multi-language handling, error propagation, and retention hooks:
1. **Fatal Bugs**: Undefined `category` variable crashes any generation attempt, and filtering BGM/SFX candidates crashes audio mixing.
2. **Account Separation**: Spanish videos are uploaded to the English channel because of directory and token sharing.
3. **Localization**: On-screen titles, descriptions/key points, Whisper language hints, local transcribe fallbacks, and brand CTAs are broken/hardcoded in English.
4. **Retention & A/B**: Fallback static videos lack major retention hooks (SFX, Easter Egg, pacing). The A/B testing framework is not segmented by locale and lacks registry axes for hooks.

### Actionable Recommendations:
1. **Fix Code Bugs**:
   - Bind `category = story.get("category", "wildlife")` at the top of `generate_short`.
   - Filter `bgm_candidates` and `sfx_candidates` by extension *before* checking list emptiness to avoid `IndexError`.
   - Replace the word `"tiktok"` in `generate_shorts.py` with `"short-form"` to clear the focus audit.
   - Fix interface types in `tests/test_captions.py` to match the list-of-lists structure expected by `utils/captions.py`.
2. **Fix Upload Routing**:
   - Segment videos by language directory (e.g. write Spanish to `_videos_es-MX/`).
   - Update `upload_youtube.py` to accept a `--language` parameter or dynamically swap `TOKEN_FILE`.
   - Update `youtube-bot.yml` to run uploads separately per language and back up all locale done markers.
3. **Fix Translation & Subtitles**:
   - Prioritize `story.get("seo_title")` over `story.get("title")` in `generate_shorts.py` for non-English runs.
   - Update `_whisper_language()` to accept the current video language parameter instead of reading the global process environment variable.
   - Change the default local model in `transcribe_faster_whisper` to `"tiny"` (multilingual) when `LANGUAGE != "en"`.
   - Translate branding CTAs and emphasis words (`EMPHASIS_WORDS`) using locale-specific dictionaries.
4. **Align Fallback Retention & Expand A/B registry**:
   - Port BGM/SFX mixing, the Easter Egg filter, and pacing cuts to `build_static_short`.
   - Introduce new experiment axes in `utils/experiments.py` for pacing, progress bars, and SFX.
   - Segment `experiments.json` and variant assignments by language (e.g. `experiments_pt-BR.json`).

---

## 5. Verification Method

To verify these findings and check for fixes:
1. **Test Suite**:
   Run the project's test command:
   ```powershell
   .\.venv\Scripts\pytest
   ```
2. **Translation Verification**:
   Inspect `generate_shorts.log` and `utils/translation.py`. Verify if translation errors occur when `LANGUAGE=pt-BR` is set.
3. **Done Markers Verification**:
   Verify that `.github/workflows/youtube-bot.yml` commits and restores the appropriate `shorts_done.json` files for all target languages (EN, PT-BR, ES-MX).
4. **Whisper Language Hint Unit Test**:
   Write a unit test in `tests/test_captions.py` to mock `os.environ["LANGUAGE"] = "en"` and call `transcribe` for a Spanish video to verify language hint corruption.
