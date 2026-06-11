# Wild Brief World-Class Upgrade

## Executive Summary

Wild Brief is no longer just an upload bot. It is a zero-cost YouTube Shorts
growth system with queue building, vertical rendering, TTS, captions, official
YouTube upload, analytics feedback, dashboard publishing and editorial learning.
The next lift is not more automation for its own sake. The lift is better
decision quality before render and better learning after upload.

This upgrade preserves every current provider and API. It adds a central
package rulebook, normalized analytics schemas, safer baseline artifacts and a
phased path toward stronger retention, replay, session growth and subscriber
conversion.

## Priority Code Changes

| Priority | File | Function or class | Inputs | Outputs | Why it matters |
| --- | --- | --- | --- | --- | --- |
| P0 | `utils/editorial_rules.py` | `EditorialRulebook.evaluate` | story, package, context | approval, score, violations, format, duration | Creates one central pre-render scorecard for hook, first frame, payoff, loop and freshness. |
| P0 | `utils/analytics_schema.py` | `build_video_metric_row` | video id, title, metrics, context | normalized JSON row | Gives future jobs stable fields and derived metrics. |
| P0 | `utils/analytics_schema.py` | `build_variant_row` | axis, variant, story id, video id | assignment row | Makes experiment logging explicit and durable. |
| P0 | `scripts/bootstrap_growth_baseline.py` | `build_baseline` | repo root | JSONL files and weekly summary | Creates empty-state-safe baseline analytics artifacts. |
| P1 | `generate_shorts.py` | planned package preflight | selected story/package | metadata with rulebook and loop score | Stops weak packages before expensive render work. |
| P1 | `scripts/build_dashboard.py` | planned dashboard sections | weekly summary and package scores | Pages sections | Shows what to publish, pause, sequel and review. |

## Implementation Status

Implemented:

- FASE 1 baseline schemas, rulebook and bootstrap artifacts.
- FASE 2 `CuriosityGapEngine` and `SwipeRiskScore`.
- FASE 3 `LoopGenerator` and metadata persistence through `package_story`
  and `generate_shorts.py`.
- FASE 4 expanded experiment axes and `BayesianABSelector`.
- FASE 5 `collect_analytics_extended.py` and `weekly_growth_review.py`.
- FASE 6 `free_signal_harvester.py`, `trend_bridge.py` and
  `post_upload_session_ops.py`.
- FASE 7 structured observability helpers, optional TTS fallback hooks,
  environment docs, security updates, dashboard sections and scoped CI linting.

## Pipeline Diagram

```mermaid
flowchart LR
  A["Free footage and existing sources"] --> B["fetch_animals.py"]
  B --> C["_data/stories_queue.json"]
  C --> D["EditorialRulebook"]
  D --> E["generate_shorts.py"]
  E --> F["_videos/*.mp4 and metadata"]
  F --> G["upload_youtube.py"]
  G --> H["Official YouTube Data API"]
  H --> I[".done sidecars"]
  I --> J["analyze_channel.py"]
  J --> K["utils.analytics_schema"]
  K --> L["_data/analytics/*.jsonl"]
  L --> M["weekly review and dashboard"]
```

## Data Flow Diagram

```mermaid
flowchart TD
  Q["Queue story"] --> P["Package score"]
  P --> R["Render metadata"]
  R --> U["Upload marker"]
  U --> V["Video metrics JSONL"]
  U --> X["Variant assignment JSONL"]
  V --> W["weekly_summary.json"]
  X --> W
  W --> D["GitHub Pages dashboard"]
  W --> N["Next Shorts recommendations"]
```

## FASE 1 - Baseline, Schemas, Consolidation

Implemented now:

- `utils/editorial_rules.py`
  - `EditorialRulebook`
  - `evaluate_story_package(story, package, context=None)`
  - Scores visual immediacy, hook specificity, script concreteness, payoff
    timing, loop potential, CTA burden, duplicate-angle risk and freshness.
- `utils/analytics_schema.py`
  - `build_video_metric_row`
  - `build_variant_row`
  - `build_retention_row`
  - `build_trend_signal_row`
  - `write_jsonl_row`
  - `read_jsonl`
  - `validate_row`
- `scripts/bootstrap_growth_baseline.py`
  - Reads `_data/analytics/latest.json` when present.
  - Writes `_data/analytics/video_metrics.jsonl`.
  - Writes `_data/analytics/variant_assignments.jsonl`.
  - Writes `_data/analytics/weekly_summary.json`.
  - Runs safely with missing historical files.

Acceptance tests:

- Empty analytics directory does not crash.
- Created JSON and JSONL files are valid.
- Derived metrics avoid division by zero.
- Weak package shapes are penalized.

## FASE 2 - Curiosity Gap and Swipe Defense

Planned files:

- `utils/curiosity_gap.py`
  - `HookCandidate`
  - `CuriosityGapEngine.build_candidates`
  - `CuriosityGapEngine.score_candidate`
  - `CuriosityGapEngine.choose_best`
- `utils/swipe_risk.py`
  - `SwipeRiskScore.score_opening`
  - `SwipeRiskScore.explain`

Acceptance tests:

- Concrete hooks beat generic hooks.
- High-motion short-copy openings score lower risk than abstract openings.
- Recent duplicate hooks receive a penalty.

## FASE 3 - Loop and Rewatch Engine

Planned file:

- `utils/loop_engine.py`
  - `LoopGenerator.plan`
  - `LoopGenerator.build_outro_to_intro_bridge`
  - `LoopGenerator.apply_render_hints`

Rules:

- Last line should call back to the opening image or question.
- Last subtitle should carry one keyword from the first subtitle.
- Avoid dead-stop endings and explicit replay begging.
- Use subtle audio tail guidance only where rendering supports it.

Acceptance tests:

- A valid loop dict is always returned.
- Final line stays inside the duration budget.
- Loop score rises when opening and ending share callback structure.

## FASE 4 - A/B Learning and Auto-Selection

Extend `utils/experiments.py`; do not replace it.

Recommended axes:

- `hook_style`: `outcome_first`, `mechanism_gap`, `question`, `time_pressure`
- `opening_visual_pattern`: `animal_closeup`, `action_first`, `before_after`, `impossible_result`
- `subtitle_density`: `low`, `medium`
- `loop_style`: `callback`, `unfinished_mechanism`, `mirror_opening`
- `cta_pattern`: `question_tease`, `sequel_tease`, `identity_follow`
- `title_shape`: `curiosity_gap`, `mechanism_reveal`, `impossible_fact`

Planned file:

- `utils/ab_selector.py`
  - `BayesianABSelector.score_variant`
  - `BayesianABSelector.choose_live_variant`
  - `BayesianABSelector.has_enough_data`

Stopping rules:

- Keep a permanent exploration slice, default 15 percent.
- Require a minimum sample size and multiple publish days before crowning a
  winner.
- Do not overfit to one outlier.

## FASE 5 - Analytics Augmentation and Weekly Decision Job

Planned files:

- `scripts/collect_analytics_extended.py`
- `scripts/weekly_growth_review.py`

Metrics:

- views
- engaged views
- estimated minutes watched
- average view duration
- average view percentage
- likes
- comments
- shares
- subscribers gained
- traffic source type and safe detail when available
- publish slot, weekday, series, format, category and variants

Derived metrics:

- `engaged_view_rate = engaged_views / max(views, 1)`
- `replay_rate_proxy = max(views - engaged_views, 0) / max(engaged_views, 1)`
- `sub_per_1k_engaged = 1000 * subscribers_gained / max(engaged_views, 1)`
- `comment_rate_per_1k_engaged = 1000 * comments / max(engaged_views, 1)`
- `minutes_per_engaged_view = estimated_minutes_watched * 60 / max(engaged_views, 1)`
- `source_diversity = normalized traffic-source entropy`

Output:

- `_data/analytics/weekly_summary.json`
- `_data/reports/weekly-growth-YYYY-MM-DD.md`
- `_data/next_shorts.json`
- `_data/experiments_recommendations.json`

## FASE 6 - Free Signal Ingestion and Session Expansion

Planned files:

- `scripts/free_signal_harvester.py`
- `utils/trend_bridge.py`
- `scripts/post_upload_session_ops.py`

Safe signal rules:

- Prefer official exports, manual CSV drops and curated RSS sources.
- Cache all external pulls.
- Add timeouts and retries.
- Do not use private or unsupported YouTube endpoints.
- If an action is not officially automatable, generate an operator-assist
  artifact instead.

Session outputs:

- `_data/post_upload_session_ops.json`
- `_data/related_video_recommendations.json`
- `_data/comment_reply_short_candidates.json`

## FASE 7 - CI/CD, Dashboard UX, Observability, Security

CI/CD:

- Keep compile, parse, pytest, dependency audit and Bandit.
- Add `ruff check` and `black --check` only after the current tree is made
  compatible or the scope is tightly configured.
- Add a dashboard smoke test.
- Upload failure artifacts when low-friction.

Dashboard:

- Winners this week.
- Top hook patterns.
- Swipe risk alerts.
- Loop winners.
- Related video suggestions.
- Reply-with-a-Short candidates.
- Experiment scoreboard.
- Downloadable JSON/CSV links when files exist.

Observability:

- Planned `utils/observability.py`
  - `get_logger`
  - `emit_event`
  - `append_csv_metric`
  - `append_jsonl_metric`
  - `maybe_send_gmail_alert`

Gmail alerts must be explicitly enabled, short and secret-free.

## Editorial Rules

Hook templates:

- `This [subject] does [specific visible action].`
- `Why does this [subject] [specific behavior] right before [outcome]?`
- `[Number] seconds before [outcome], this [subject] changes [visible trait].`
- `What looks like [simple visual] is actually [counterintuitive mechanism].`

Micro-story timing:

- 0.0-1.2s: immediate visual plus hook.
- 1.2-4.0s: what is happening.
- 4.0-8.5s: why it matters or escalation.
- 8.5-15.0s: reveal, mechanism or surprise.
- 15.0-24.0s: payoff or second surprise.
- 24.0-end: loop line and one low-friction CTA when useful.

Packaging:

- First-frame text target: 2-4 words.
- First-frame text hard cap: 5 words.
- First spoken sentence target: 8-11 words.
- Title, first-frame text and narration should not repeat the same phrase.
- Use one CTA only.

## Free Tools Comparison

| Area | Option | Cost | Recommendation | Integration point |
| --- | --- | --- | --- | --- |
| TTS | existing edge-tts path | free | keep primary | `generate_shorts.py` |
| TTS fallback | Coqui local models | free | optional only | `utils/tts_fallback.py` |
| Music | existing Pixabay flow | free | keep and refine | `utils/music_bed.py` |
| Music manual library | YouTube Audio Library local manifest | free | optional operator-curated fallback | `_data/audio_library_manifest.json` |
| Trends | Google Trends official exports | free | support manual cached snapshots | `scripts/free_signal_harvester.py` |
| Discovery validation | YouTube Data API low-cost calls | free quota | use carefully | analytics scripts |
| Freshness | curated RSS sources | free | add as optional signal | `utils/trend_bridge.py` |

## Security Checklist

- Maintain a strict environment-variable inventory.
- Mark secrets required vs optional.
- Never print tokens or OAuth payloads.
- Redact suspected secrets in logs.
- Do not commit generated credentials.
- Keep local tokens, temp renders and audio caches ignored.
- Review workflow logs after auth or upload changes.
- Keep large secret handling out of source unless encrypted and justified.

## Prioritized Task List

| Priority | Task | Effort | Dependencies |
| --- | --- | --- | --- |
| P0 | Add editorial rulebook and baseline analytics schema | Medium | none |
| P0 | Add curiosity gap and swipe risk package preflight | Medium | baseline schema |
| P0 | Extend experiments and variant logging | Medium | baseline schema |
| P1 | Add loop engine and metadata persistence | Medium | generation integration |
| P1 | Add weekly growth review | Medium | analytics normalization |
| P1 | Add free signal harvester | Medium | analytics schema |
| P1 | Improve dashboard with winners, risks and session suggestions | Medium | weekly outputs |
| P2 | Add Coqui fallback | High | optional local dependency handling |
| P2 | Add Gmail alerts | Low | observability module |
| P2 | Harden CI with format and lint gates | Low | tests in place |

## Final 10/10 Validation Checklist

These are internal operating targets, not official platform benchmarks.

- 20-35s Shorts median average view percentage is at least 78 percent.
- Top quartile Shorts average view percentage is at least 88 percent.
- Median replay proxy is at least 0.10.
- Median engaged view rate is at least 0.78.
- Subscribers gained per 1,000 engaged views is at least 1.5.
- Comment rate per 1,000 engaged views is at least 4.
- At least 3 stable winning hook/package patterns identified.
- At least 2 losing patterns explicitly paused.
- Traffic source mix is not overconcentrated only in Shorts.
- Dashboard updates automatically.
- Weekly review runs automatically.
- CI blocks broken parsing, tests and high-severity security findings.
- No secrets exposed in logs.
- Operator can see what to publish next.
- Operator can see what to stop publishing.
- Operator can see what to sequel.
- Operator can see what related video to set.
- Operator can see what comment should become a reply Short concept.
