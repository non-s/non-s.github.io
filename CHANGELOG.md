# Changelog

All notable changes to Liquid Wire are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Weekly releases are auto-tagged by `.github/workflows/release.yml`; this
file captures human-curated highlights between releases.

## [Unreleased]

### Added — Engine 3.0: "Best in class" upgrade
- **DSP performance**: biquad and ladder filters now use scipy.signal.lfilter
  for vectorized C-speed processing (50-100x faster than per-sample Python
  loops). Pink/brown noise generators, chorus, delay, phaser and dynamics
  envelopes are also vectorized.
- **8 new high-fidelity instruments**: GlassHarp, MusicBox, Theremin,
  PulsarSynth, Dulcimer, Hang, CrystalBow, WarmPad — all 100% procedural
  using advanced synthesis (physical modeling, FM, granular, wavetable).
- **5 new mastering effects**: StereoWidener (mid/side), HarmonicExciter,
  TapeSim (analog tape saturation with wow/flutter), MultibandCompressor
  (3-band Linkwitz-Riley), ConvolutionReverb (procedurally synthesized IR).
  The master chain now applies multiband compression + excitation + tape
  saturation + stereo widening for a professional, glued sound.
- **6 new visual families**: helix, gyroid, mandelbulb, torus_knot,
  spiral_galaxy, superformula — adding fractal, organic and cosmic variety.
- **3 new post-processing effects**: HDR tone mapping (ACES filmic), depth
  fog (atmospheric perspective), motion blur (directional smear).
- **Robustness**: graceful frame degradation (falls back to orb family on
  numerical instability), ffmpeg fallback preset on timeout, float32 audio
  rendering for videos >300s to halve memory usage.
- scipy added as a dependency for signal processing.

### Security
- Fix OAuth token passed to `gh secret set` via command-line argument
  (visible in process listings) — now piped via stdin.
- Add `SECURITY.md` with disclosure policy.
- Narrow `except Exception` in `validate_token_scopes` to
  `(OSError, json.JSONDecodeError)` so real corruption isn't masked.

### Changed
- CI now enforces the 85% coverage gate (`--cov-fail-under=85`).
- mypy and bandit now scan the full `scripts/` and `utils/` trees
  instead of a curated subset.
- `make all` now includes `security` (was: `lint test typecheck`).
- `make clean` is now Windows-compatible (PowerShell branch).

### Added
- `LICENSE` (MIT) — previously missing on a public repo.
- `CODE_OF_CONDUCT.md`.
- `CHANGELOG.md` (this file).

### Removed
- Stray `__nonexistent_dir__/` from the repository root.

## [1.0.0] — 2024

Initial production release of the Liquid Wire generative-art pipeline.

- Procedural wireframe renderer (16 object families, supersampling).
- Synthetic ambient audio engine (12 genres, mixer, DSP, instruments).
- 32-dim perceptual quality gate with near-duplicate detection.
- YouTube upload with Content ID pre-check, captions, playlists.
- 10 GitHub Actions workflows (hourly generation, weekly publishing,
  analytics, engagement, identity, site, SLA, watchdog, OAuth refresh).
- GitHub Pages site with schema.org metadata.