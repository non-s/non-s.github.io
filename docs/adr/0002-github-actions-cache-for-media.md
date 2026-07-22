# ADR 0002: GitHub Actions Cache for Media Libraries

## Status
Accepted

## Context
Pixabay and Jamendo APIs have rate limits. Re-downloading the same clips/tracks on every workflow run wastes API quota and time. However, storing 150+ music files in git is infeasible (~500MB).

## Decision
Use **GitHub Actions cache** (`actions/cache`) to persist media libraries (`_assets/audio/bgm`, `_assets/video/lofi_broll`) across ephemeral runners. Cache key: `lofi-media-{matrix.os}-v1`.

## Rationale
1. **Free quota:** GitHub includes 5GB cache per account (more than enough for ~100 music files + 20 video clips)
2. **Per-repo isolation:** Cache is scoped to the repo, preventing cross-contamination
3. **Automatic eviction:** Unused cache auto-deletes after 7 days (prevents stale libraries)
4. **Graceful degradation:** If cache miss, scripts re-download from source APIs

## Consequences
- ✅ Fast workflow startup: library loads in seconds, not minutes
- ✅ API quota savings: ~50% fewer calls to Pixabay/Jamendo
- ⚠️ Cache hit depends on key matching: if version suffix changes, full re-download
- ⚠️ Cache miss on first run: no warm start for new repos/branches
- ⚠️ Library growth is gradual: reaches ~150 tracks over ~3 months, not immediately

## Alternatives Considered
1. **Store media in git LFS:** Requires GitHub LFS quota, complicates cloning
2. **Use external S3/blob storage:** Adds infrastructure cost and complexity
3. **Re-download every run:** Simpler but wastes API quota and time

## See Also
- `.github/workflows/youtube-bot.yml` — cache restore/save steps
- `scripts/sync_lofi_broll.py` — Pixabay sync with cache-aware state
- `scripts/sync_jamendo_music.py` — Jamendo sync with cache-aware state
