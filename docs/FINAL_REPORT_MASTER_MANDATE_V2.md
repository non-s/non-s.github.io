# Liquid Wire — Master Mandate V2 final engineering report

Date: 2026-08-20
Scope: one YouTube channel, `@LiquidWireStudio`.

## Before

The project already had a strong procedural generator, synthetic audio,
YouTube OAuth/upload/analytics, a final-video quality gate, perceptual
fingerprints, retries, quota control, state locks, dashboards and extensive
tests. Creative intent, final perception, YouTube evidence and evolution were
not connected through one stable versioned contract. Long-form and publication
frequency were mostly cron-driven, and the legacy weekly batch bypassed the
active upload contract.

## After

The pipeline is a governed feedback loop:

```text
GENOME -> CHEAP CANDIDATES -> FINAL RENDER -> VISUAL/AUDIO DNA
       -> QUALITY/PUBLICATION GATES -> YOUTUBE -> MATURITY WINDOWS
       -> MEMORY -> RESEARCH -> HYPOTHESIS -> EXPERIMENT
       -> CONFIDENCE -> ELITES/LINEAGE/MUTATION -> NEXT GENOME
```

## Implemented

- Versioned genome, visual DNA, audio DNA, provenance and stable content IDs.
- Final-MP4 OpenCV observation: composition, center of mass, symmetry, edges,
  entropy, palette, optical flow and opening/middle/ending activity.
- Bounded catalog and canon memory with atomic schema-versioned state.
- Real YouTube metric normalization in early/1h/6h/24h/72h/mature windows.
- Separate explainable Short and long-form fitness with missing-data confidence.
- Machine/human research reports, stable hypotheses and single-variable
  experiments with conservative evidence states.
- Archive of elites, lineage, controlled mutation, adaptive exploration,
  novelty pressure, shadow/canary/active modes and cold-start behavior.
- Cheap bounded candidate selection before expensive rendering.
- Quality Gate 2.0, private validation, Content ID gate and 4.1 upload contract.
- Safe mode, global/publication kill switches and failure-rate guardrail.
- Replicated-Short long-form promotion and adaptive publication cadence.
- Versioned fictional glyph language, fair puzzle density and lore/canon links.
- Pipeline timing/output-size metrics and control-plane resource benchmark.

## Improved

- Production remains dependency-light: no database, SaaS, server, queue or new
  runtime dependency was introduced.
- The weekly research workflow reuses existing infrastructure and emits all
  evidence in one artifact instead of creating workflow sprawl.
- The legacy weekly public batch is now manual-only, private and contract-aware.
- Type regressions in post-processing/multi-camera were corrected while making
  the full mypy gate pass.

## Not implemented

- No clustering model was added: the repository has no persisted dataset large
  enough to justify ML. Deterministic statistics run first.
- No low-resolution rendered-preview tournament was enabled: cheap candidate
  ranking is within budget, while actual preview value must be demonstrated by
  runner measurements before spending extra render minutes.
- Evolution is not force-enabled beyond shadow. Graduation to canary requires
  real mature channel evidence; code cannot legitimately fabricate it.
- No external platform, second channel, database or paid observability was added.

## Why

These omissions are deliberate applications of the mandate: do not invent
data, do not overfit cold start, do not add infrastructure without proof and do
not sacrifice P0–P4 for decorative complexity.

## Tests

- 2,242 tests collected.
- Full suite passed with expected environment-dependent skips.
- Targeted workflow, upload, analytics, evolution, puzzle and governance tests
  passed.
- Ruff, mypy (172 source files), compile, Bandit and diff checks passed.
- A real six-second FFmpeg render completed end to end: 12 visual-DNA samples,
  visual/audio DNA v1, quality and publication policy passed, private
  validation required, and the 4.1 uploader contract returned no issue.

## Coverage

Full measured coverage: **85.56%**, above the required 85% gate.

## Benchmarks

Control-plane benchmark with a 100-item catalog:

- candidate selection mean: approximately 0.50 ms;
- research cycle: approximately 0.07 s;
- traced peak memory: approximately 1.2 MB;
- all configured budgets passed.

The end-to-end validation render was 6.0 seconds and 11,303,271 bytes with
supersampling disabled, completing successfully in about 183 seconds on this
Windows environment.

Actual render duration/output bytes are recorded in `pipeline_metrics.json` so
GitHub Actions data, not workstation guesses, controls future resource choices.

## Security

- No new secret or external network surface.
- Existing pinned Actions, least-privilege permissions, OAuth handling, quota
  controls, Content ID check and dependency/security scans remain active.
- Kill switches are enforced before generation and independently by upload.

## Architecture

The existing engine remains compatible. New automation consumes versioned
contracts in focused modules: creative models/memory, analytics feedback,
research/experiments, evolution, publication policy, cadence and canon.

## Migrations

New state uses schema version 1. Loaders reject unknown future schemas and
missing migration paths. Existing legacy JSON remains readable and was not
silently rewritten.

## Rollback

- Every new versioned state write retains a `.bak` predecessor.
- Evolution can be switched to `off` or `shadow` without code changes.
- Safe mode disables mutation and puzzles while retaining stable generation.
- Global and publication-only kill switches stop risky operations immediately.
- The feature branch and checkpoint commits provide source rollback.

## Remaining risks

- Channel data may be sparse or API fields unavailable; the system reports
  low confidence/insufficient data and does not guess.
- Optical flow adds modest CPU cost; sampling is bounded to 12 frames.
- Existing legacy state files still use mixed direct-write conventions and
  should migrate incrementally when touched, not through a dangerous rewrite.

## Next data needed

- At least eight age-comparable creations for correlation-based hypotheses.
- At least two mature, confident Short replications for long-form promotion.
- Real GitHub Actions render duration, failure rate and artifact-size history.
- Controlled experiment results before shadow evolution graduates to canary.
