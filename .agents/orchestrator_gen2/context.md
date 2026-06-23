# Context - WildBrief Pipeline Audit and Hardening

## Overview
We are conducting an audit, refactoring/hardening, viral hook implementation, and E2E verification of the WildBrief YouTube Shorts automation pipeline.

## Repository Details
- Path: `C:/Users/Julio/.gemini/antigravity/scratch/non-s.github.io`
- Main entrypoint: `generate_shorts.py`
- AI fetching: `fetch_animals.py`
- Video composition: `utils/video_compose.py`
- Configuration & scripts: `pyproject.toml`, `requirements.txt`, `auth_youtube.py`, `upload_youtube.py`.

## Constraints & Requirements
- No direct writing or modification of code files by the orchestrator.
- No direct execution of builds or tests by the orchestrator.
- Zero-tolerance on integrity violations.
- Verify both EN/PT and ES versions cleanly.
