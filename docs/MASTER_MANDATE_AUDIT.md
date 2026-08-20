# Master Mandate V2 — engineering audit

Audit date: 2026-08-20. Baseline commit: the `main` checkout immediately
before the 4.1 autonomous-core changes.

## Baseline

- 242 Python files and approximately 38,538 Python lines.
- 88 test files; 2,179 tests collected.
- Baseline suite passed in 3.67 seconds with xdist in this checkout.
- 14 GitHub Actions workflows, including CI, video, analytics, engagement,
  evolution, identity, live, site, SLA, thumbnail optimization, watchdog,
  weekly publication, OAuth refresh and release.
- Ruff baseline: clean.
- Runtime dependencies already include NumPy, SciPy, OpenCV, Pillow, FFmpeg
  integration, Google/YouTube clients and filelock. No new dependency was
  needed for the autonomous core.
- Generated media and operational `_data` state are intentionally ignored.

## Capability classification

| Capability | Class | Evidence / action |
| --- | --- | --- |
| Procedural visual and audio generation | A | Mature local generator, DSP, genre and instrument modules; preserved. |
| YouTube upload, OAuth, quota and retries | A | Dedicated modules and tests; preserved. |
| Technical quality gate | A | Final-MP4 validation and 32-dimensional perceptual/audio fingerprint. |
| Visual perception | B | Basic signals existed; 4.1 adds versioned final-render visual DNA and optical flow. |
| Reproducible genome | C | Seed/profile existed; 4.1 adds a stable, versioned genome contract and ID. |
| Catalog memory | C | Fragmented histories existed; 4.1 adds a bounded, versioned creation catalog. |
| Analytics feedback | B | Rich collection exists; fitness normalization needs wiring to comparable age windows. |
| Evolution | B | Weighted profile adaptation exists; lineage and controlled semantic mutation remain next. |
| Gemini governance | B | Validation/fallback/circuit breaker exist; experiment proposals need a dedicated schema. |
| Experiments/hypotheses | C | A/B and analytics pieces exist; 4.1 adds deterministic fitness/status primitives. |
| Atomic state and schema migration | C/G | Locks existed but many writes are direct; 4.1 provides atomic versioned state primitives. |
| Puzzle/lore/cuneiform | D | Deliberately deferred until P0–P4 feedback is operating. |
| Workflow surface | E risk | 14 workflows are functional but should be consolidated only with schedule evidence. |
| External/social integrations | Out of scope | No additions; the project remains one YouTube channel only. |

## Decisions

1. No big-bang rewrite. Existing generation, quality, upload and analytics
   paths remain authoritative.
2. `genome` is requested intent; `visual_dna` is observed encoded output.
   They are never inferred from each other.
3. Visual DNA is calculated after FFmpeg and after the existing gate, so it
   measures compression-surviving output.
4. Fitness is explainable and different for Shorts and long-form. Missing API
   fields stay missing and reduce confidence.
5. State writes use a schema envelope, `fsync`, atomic replace and one rollback
   copy. Legacy state is not silently coerced.
6. Puzzle/lore work is deferred: adding it before reliable perception,
   memory and learning would violate the mandate's P0–P4 priority.

## Validation after 4.1

- Full suite: 2,179 tests passed (with expected skips), serial run.
- Ruff: all checks passed.
- `git diff --check`: clean except Windows line-ending notices.
- No network service, database or new runtime dependency introduced.

## Checkpoint 2 — scientific loop and governed evolution

- YouTube observations are attached to creations by `content_id` and maturity
  window; unmatched videos remain explicit and never create phantom records.
- Hypotheses and experiments use a versioned ledger with conservative evidence
  states and a single-variable causal-design guard.
- Weekly research emits machine- and human-readable reports without requiring
  Gemini or manufacturing conclusions during cold start.
- Evolution includes lineage, controlled semantic mutation, adaptive
  exploration, novelty pressure and a bounded archive of elites.
- Cheap candidate ranking precedes expensive rendering; final encoded visual
  DNA remains authoritative.
- Audio DNA, Quality Gate 2.0, safe mode, private validation, canary controls
  and upload-level kill switches close the governance path.
- The fictional glyph/puzzle protocol is versioned, density-limited,
  checksum-validated, canon-linked and explicitly disclaims historical
  cuneiform.

## Remaining sequence

1. Collect enough real channel observations to graduate evolution from shadow
   to canary; no code can manufacture that evidence.
2. Add an optional low-resolution rendered-preview stage if runner benchmarks
   prove that cheap intent ranking is insufficient.
3. Consolidate legacy state writers into atomic/versioned envelopes by risk,
   without breaking rollback compatibility.
4. Consolidate workflows only after schedule/run-duration evidence identifies
   safe combinations.
