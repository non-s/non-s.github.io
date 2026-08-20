# Master Mandate V2 — decision record

## ADR-008 — Every numbered section is a formal acceptance unit

The final closure pass treats sections 0–177, including their nested requirements,
as individually traceable acceptance units. A passing CI run or a completed core
loop is necessary but no longer sufficient to declare the mandate complete.

## ADR-009 — Long-horizon intelligence stays deterministic until data exists

Pareto analysis, value-of-information scoring, lineage and the creative map use
small transparent Python primitives. The creative map reports insufficient data
below eight final-render observations; it does not manufacture clusters. Evicted
raw catalog records are compacted into versioned aggregates so generations remain
auditable without unbounded state growth.

## ADR-001 — Evolve in place

Decision: preserve the existing generator, upload, analytics and quality
modules and add versioned contracts around them. A big-bang rewrite would
discard a mature 2,000+ test baseline and increase operational risk.

## ADR-002 — Intent and observation are different records

Decision: `Genome` records requested reproducible intent; `VisualDNA` and
`AudioDNA` record what survived final FFmpeg encoding. Learning consumes the
observed records and never assumes that a requested parameter appeared.

## ADR-003 — Filesystem state remains authoritative

Decision: use schema envelopes, locks, `fsync`, atomic replacement and rollback
copies instead of adding a database or service. Catalog and canon are bounded;
raw histories do not grow forever.

## ADR-004 — Python governs Gemini

Decision: channel evidence, validation, scores, limits and state transitions
remain deterministic Python. Gemini may assist editorial/research modules, but
the research cycle can operate without it and never treats model text as fact.

## ADR-005 — Evidence before evolution

Decision: evolution defaults to shadow, uses confidence and age-normalized
fitness, and applies only one semantic mutation. Canary is deterministic 10%.
Active mode is available but is not enabled by code without real evidence.

## ADR-006 — Correlation does not authorize causal claims

Decision: automatic hypotheses require at least eight comparable creations.
All correlations are labelled non-causal; experiments change exactly one
variable and may conclude insufficient data, inconclusive or contradicted.

## ADR-007 — Long-form is earned by Shorts

Decision: scheduled long-form requires two mature, confident Short
replications from the same family. Otherwise the slot remains a Short
experiment. Manual dispatch remains available but does not bypass quality.

## ADR-008 — Quality is not taste

Decision: objective technical, perception, novelty, audio and puzzle failures
block. Low occupancy and similar subjective properties become review prompts.
Private validation and Content ID precede public release.

## ADR-009 — The secret language is explicitly fictional

Decision: Liquid Wire glyphs are original wedge-inspired geometry codes, not
historical cuneiform. Density, checksum, difficulty, disclosure and canon are
validated. At most one in five creations carries a puzzle.

## ADR-010 — Cadence is governed

Decision: keep the existing hourly scheduler as a cheap wake-up mechanism but
permit at most four publications per rolling day and require a four-hour
learning interval. The legacy weekly batch is manual-only and private.
