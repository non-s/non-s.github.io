# Project: WildBrief Pipeline Audit and Hardening

## Architecture
WildBrief is a YouTube Shorts automation pipeline:
1. AI Engine (`fetch_animals.py`) queries/generates animal-related facts and scripts.
2. Video Composition (`utils/video_compose.py` / `generate_shorts.py`) takes audio/subtitles/images/videos and uses FFmpeg to compile YouTube Shorts videos.
3. YouTube uploader (`upload_youtube.py`) handles publishing.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Architectural & Functional Audit | Detailed file-by-file audit to identify bottlenecks and viral vectors. | None | DONE |
| 2 | Apex Code Hardening & Optimization | Refactor for zero defects, robust API error handling, and optimized FFmpeg commands. | M1 | DONE |
| 3 | Viral Hooks & A/B Testing | Implement micro-animations, audio pacing, and an A/B testing framework. | M2 | DONE |
| 4 | E2E Testing & Verification | Verify E2E generation for EN/PT and ES versions cleanly. | M3 | DONE |

## Code Layout
- `fetch_animals.py` - AI scripting logic
- `generate_shorts.py` - main execution pipeline
- `utils/video_compose.py` - video rendering using FFmpeg
- `upload_youtube.py` - uploading pipeline
