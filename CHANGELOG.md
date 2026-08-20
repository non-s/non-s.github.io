# Changelog

## Master Mandate V2 — exhaustive closure pass

- Added independently enforced generation/upload/Gemini/evolution/puzzle/private/schedule controls.
- Expanded pre-publication self-critique to all seven mandated dimensions and added bounded rejection memory.
- Added strategy versioning, compacted long-term catalog aggregates, Pareto analysis, creative-space mapping,
  value-of-information scoring and a dependency-free lineage graph.
- Added prompt provenance (version, model, prompt hash, structured/fallback state) without storing prompt text or secrets.
- Added a cached, schema-validated Gemini research advisor over bounded experiments, canon and non-causal evidence.
- Prevented analytics research from mixing formats or maturity windows and attached explicit observation cutoffs.
- Migrated central plain-JSON state to atomic replacement while preserving legacy schemas and rollback copies.
- Added objective rollback criteria and bounded rejection-memory influence on candidate selection.
- Expanded traceability from 178 sections to all 658 explicit bullet sub-requirements.

## 4.1.0 - 2026-08-20

- Added versioned procedural genomes, final-render visual DNA and stable
  content/provenance identifiers.
- Added OpenCV composition, palette, entropy, temporal-change and optical-flow
  observation of the encoded MP4.
- Added bounded catalog memory with atomic versioned JSON writes and rollback
  copies.
- Added explainable, confidence-aware and format-specific fitness primitives.
- Added the Master Mandate V2 baseline/audit and autonomous-core tests.
- Joined YouTube metrics to catalog memory in comparable maturity windows and
  added deterministic research reports, hypotheses and experiment ledgers.
- Added governed lineage, semantic mutations, adaptive exploration, novelty
  pressure, archive of elites and cheap candidate selection.
- Added audio DNA, Quality Gate 2.0, private validation, safe mode, canary and
  kill-switch enforcement.
- Added a fictional, versioned Liquid Wire glyph/puzzle protocol and canon;
  it explicitly does not claim historical cuneiform.

All notable changes to Liquid Wire are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Weekly releases are auto-tagged by `.github/workflows/release.yml`; this
file captures human-curated highlights between releases.

## [Unreleased]

### Added — Engine 4.0: Massive expansion of music and video engines

**Music engine — 68 instruments (from 31), 32 genres (from 12):**
- **5 new DSP engines**: FM multi-operator (DX7-style 6-op with algorithms
  and feedback), wavetable synthesis with morphing, granular synthesis (cloud
  grains, freeze, time-stretch), Karplus-Strong/waveguide physical modeling,
  6 extra effects (flanger, ring mod, tremolo, vibrato, pitch shifter,
  harmonizer).
- **39 new instruments**: 10 winds (clarinet, oboe, sax, trumpet, trombone,
  harmonica, accordion, shakuhachi, ocarina, panpipes), 7 strings with
  physical modeling (violin, cello, harp, koto, banjo, mandolin, ukulele),
  6 advanced synths (vocoder, wavetable, FM, granular pad, supersaw stereo,
  shimmer pad), 16 percussion (tambourine, conga, bongo, cowbell, shaker,
  woodblock, clave, agogo, rimshot, sidestick, china, splash, surdo, caixa,
  cuica, tamborim).
- **20 new genres**: techno, trance, dubstep, dnb, metal, country, folk,
  pop, soul, disco, salsa, bossa_nova, samba, afrobeat, flamenco, gamelan,
  vaporwave, chiptune, industrial, shoegaze.
- **Extended composer**: 6-8 voices (motif, bass, pad following progression,
  counter-melody, arpeggiator, ostinato, walking bass, gesture) with
  phrase-level call-and-response and walking bass for jazz/groove genres.

**Video engine — 42 visual families (from 22), cinematic post-processing:**
- **Virtual camera**: 3D camera with position, FOV, Bezier paths, procedural
  shake.
- **Lighting system**: point/directional/spot lights, Phong shading,
  Fresnel, ambient occlusion.
- **20 new visual families**: Mobius, Klein bottle, Julia set, Sierpinski,
  Voronoi sphere, Lissajous 3D, harmonograph, hyperbolic tiling, smoke
  plume, fire flame, plasma field, lightning bolt, ink in water,
  ferrofluid, caustics, DNA helix, aurora, accretion disk, gravitational
  lens, Menger sponge.
- **8 cinematic post-effects**: lens flare, god rays, halation, color
  grading LUTs, anamorphic flare, film halation, optical aberrations, bokeh.
- **Transitions**: crossfade, morph with correspondence, dissolve, wipe,
  glitch, match cut, SceneTransition.
- **Extended particle system**: emitters, lifetimes, 9 particle types
  (embers, sparks, dust, smoke, rain, snow, bubbles, fireflies, debris),
  trails, 3D projection.

**Tests**: 2007 passed (from 1346), 87.31% coverage, ruff clean, mypy clean.

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
