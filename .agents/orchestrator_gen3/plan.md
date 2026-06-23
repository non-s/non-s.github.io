# Project Plan - WildBrief Pipeline Audit and Hardening

Our strategy is to execute the following phases:
1. **Architectural & Functional Audit (M1)**: Spawn `teamwork_preview_explorer` to inspect `fetch_animals.py`, `generate_shorts.py`, `utils/video_compose.py`, and other scripts. Generate a comprehensive audit artifact listing all gaps.
2. **Apex Code Hardening & Optimization (M2)**: Spawn `teamwork_preview_worker` to refactor the codebase for zero-defect operation, optimize FFmpeg parameters, and handle API errors cleanly.
3. **The Final 1% Viral Hooks (M3)**: Implement micro-animations, audio pacing, and A/B testing via the worker.
4. **E2E Verification (M4)**: Validate the entire pipeline with a clean execution of `generate_shorts.py` for both EN/PT and ES versions. Verify correct video/audio generation.
