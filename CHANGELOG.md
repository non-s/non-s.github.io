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

### Fixed — CI stability and render performance (2026-08-18)
- **`state_lock` deadlock**: `FileLock` is not reentrant, so the nested
  `state_lock` call inside `_update_style_drift` -> `_load_style_drift` blocked
  the calling thread for the full 30 s timeout on every style-drift rotation.
  This single bug accounted for ~90 s of the CI test job's time (three
  parametrised coverage tests each waited 30 s) and was the root cause of the
  CI - Liquid Wire job timing out at the 15 min ceiling. `state_lock` is now
  reentrant per-thread: the outermost call holds the real `FileLock` and
  nested calls on the same path bump a depth counter and yield without
  re-acquiring, releasing only when the outermost call exits.
- **Additive-synthesis hot spot**: `osc._additive` iterated harmonics one at
  a time through Python lambdas, which dominated render time for low notes
  (a 65 Hz supersaw spent ~9 s per note) and pushed the `test_universal_music`
  suite past the CI job timeout. The harmonic range, amplitude and sign
  masks are now computed once via numpy arrays; the sinusoidal sum still
  streams per-harmonic (a materialised 2D `np.sin` blows the cache) but
  without the per-iteration lambda/Python overhead. Output is numerically
  identical (max abs diff ~1e-11).
- **Sub-audio oscillator fast path**: `sawtooth`/`square`/`triangle` now use
  direct geometric waveforms for `freq <= 20 Hz` (LFOs, vibrato, control
  signals). The bandlimited additive path iterates up to `nyquist/freq`
  harmonics (88 200 iterations for a 0.5 Hz Phaser LFO) and made a single
  `Phaser.process` call take ~4 s; the direct path is ~5000x faster and
  inaudibly different below 20 Hz.
- **Test suite budget**: `test_universal_music` synthesised 5 s clips per
  genre across three parametrised cases; with the additive-synthesis hot
  spot this alone exceeded 20 min. Reduced `SHORT_DURATION` to 1.5 s, which
  still exercises the full instrument/mixer/mastering chain and validates
  stereo/silence/clipping while keeping the whole suite under 80 s.

## [1.0.0] — 2024

Initial production release of the Liquid Wire generative-art pipeline.

- Procedural wireframe renderer (16 object families, supersampling).
- Synthetic ambient audio engine (12 genres, mixer, DSP, instruments).
- 32-dim perceptual quality gate with near-duplicate detection.
- YouTube upload with Content ID pre-check, captions, playlists.
- 10 GitHub Actions workflows (hourly generation, weekly publishing,
  analytics, engagement, identity, site, SLA, watchdog, OAuth refresh).
- GitHub Pages site with schema.org metadata.