# Wild Brief Architecture

Wild Brief is a zero-cost Shorts production loop. Public/free discovery and
operator exports feed `_data/stories_queue.json`; `generate_shorts.py` renders
vertical videos and metadata; `upload_youtube.py` publishes through the
official YouTube Data API; analytics, comments and `.done` sidecars feed
weekly decisions and the GitHub Pages dashboard.

## Core Loops

- Discovery: `fetch_animals.py`, `scripts/free_signal_harvester.py`,
  `scripts/trend_radar.py`, `scripts/apply_topic_freshness.py`.
- Production: `generate_shorts.py`, `utils/editorial_rules.py`,
  `utils/first_frame_audit.py`, `utils/seo_optimizer.py`.
- Upload/session: `upload_youtube.py`, `scripts/post_upload_session_ops.py`,
  `utils/session_graph.py`, `scripts/comment_to_short_pipeline.py`.
- Learning: `scripts/collect_analytics_extended.py`,
  `scripts/import_studio_reach_export.py`, `scripts/reporting_pull.py`,
  `scripts/weekly_growth_review.py`.
- Operations: `scripts/quota_preflight.py`, `scripts/compact_analytics.py`,
  `scripts/check_repo_contracts.py`, `scripts/tts_healthcheck.py`.

## Durable Artifacts

The flat analytics files remain backward-compatible. Monthly partitions under
`_data/analytics/partitions/` reduce diff churn for longer history. Optional
Studio/Reporting imports degrade safely when no CSV files are present.
