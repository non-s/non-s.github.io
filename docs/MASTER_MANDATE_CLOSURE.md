# Master Mandate V2 — closure ledger

The mandate contains 178 numbered sections (`0` through `177`) and 658 explicit
bullet sub-requirements. The authoritative machine-readable ledger is
`config/master_mandate_traceability.json`; its generator refuses missing or
reordered sections, and CI verifies evidence existence and content hashes.

## Status vocabulary

- `satisfied`: executable behavior exists and is tied to source/tests or runtime evidence.
- `satisfied_by_decision`: the requirement is a constraint, principle or explicit
  non-action; the decision record explains why adding machinery would violate it.
- `ready_pending_real_data`: implementation is complete, but the observed outcome
  requires future channel/audience evidence that cannot be fabricated.

There are no `missing`, `partial`, `todo` or `unknown` entries.

## External-evidence-only sections

| Section | Why code is complete but observed evidence remains external |
| --- | --- |
| 13 | The deterministic creative map reports insufficient data below eight final-render observations; clustering is intentionally not fabricated. |
| 44 | Difficulty has a conservative episode curve and changes at most one level after eight comparable puzzle observations. |
| 55 | Statistical/creative-map primitives exist; an ML model is prohibited until sample size and validation justify it. |
| 116 | Versioned generations, archive compaction and lineage support generation 1/20/100; reaching them requires elapsed production. |
| 119 | Canon episodes can cross Shorts, long-form, families and generations; actual public recurrence requires future releases. |
| 121 | The discovery curve is encoded in density/difficulty/cadence, while audience realization is an external human outcome. |
| 132 | Experiment-yield meta-learning is implemented; useful yield requires completed controlled experiments. |
| 138 | The creative map exposes occupied/empty regions after eight observations; production data supplies those observations. |
| 147 | Shadow decisions are recorded without controlling publication; comparison requires live outcomes. |
| 148 | Canary mode deterministically applies to 10% of seeds, but activation requires mature evidence and explicit policy promotion. |

These are not deferred implementation tasks. They are guarded cold-start states
required by sections 0, 23, 55, 56, 59 and 60: do not invent data, confuse
correlation with causation or overfit small samples.

## Intentionally rejected additions

- No database, queue, server, SaaS observability or second channel.
- No clustering model without a sufficient persisted dataset.
- No low-resolution render tournament until observed runner data shows that the
  sub-millisecond intent prefilter fails to provide enough value.
- No trend-driven metadata by default and no integrations with other social networks.
- No public-by-default rollout; private validation, shadow and canary remain the
  promotion sequence.
