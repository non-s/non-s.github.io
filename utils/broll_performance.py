"""Feed real per-video view performance back into b-roll mood weighting.

_data/analytics/reporting_video_metrics.jsonl (built by
scripts/reporting_pull.py from a manually-imported YouTube Reporting API
CSV, or studio-reach-import.yml's Shorts Reach import) has one row per
video with a real `views` count. Joined here against each `.done`
marker's title -- via the same utils.lofi_branding.playlist_bucket_for_title()
grouping used for playlists -- this computes a per-mood-bucket weight
multiplier so utils.broll.pick_weighted_broll_file() can lean toward
moods that have actually performed better on this channel, instead of
only the fixed rain/night/snow editorial bias picked before there was
any real data to go on.

As of 2026-07-19 reporting_video_metrics.jsonl has zero rows -- the
channel's analytics epoch only just reset and no CSV has been imported
yet -- so mood_performance_weights() returns {} (meaning "no adjustment,
fall back to the static weight only") until an operator actually runs
studio-reach-import.yml or reporting_pull.py with real data. That's
deliberate: this module is real and tested against synthetic data, but
it doesn't pretend to have learned from performance data that doesn't
exist yet.
"""

from __future__ import annotations

import json
from pathlib import Path

from utils.lofi_branding import playlist_bucket_for_title

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "_data" / "analytics" / "reporting_video_metrics.jsonl"
VIDEOS_DIR = ROOT / "_videos"

# A bucket needs at least this many published, measured videos before it
# gets a real multiplier -- otherwise 1-2 lucky/unlucky videos would swing
# an entire mood's future selection odds off of a tiny sample.
MIN_SAMPLES_PER_BUCKET = 3
MIN_WEIGHT = 0.5
MAX_WEIGHT = 2.0


def _load_views_by_video_id(path: Path = METRICS_PATH) -> dict[str, float]:
    if not path.exists():
        return {}
    views: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        video_id = str(row.get("video_id") or "")
        if not video_id:
            continue
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else row
        try:
            views[video_id] = float(metrics.get("views") or 0)
        except (TypeError, ValueError):
            continue
    return views


def mood_performance_weights(
    *,
    metrics_path: Path = METRICS_PATH,
    videos_dir: Path = VIDEOS_DIR,
    min_samples: int = MIN_SAMPLES_PER_BUCKET,
) -> dict[str, float]:
    """{playlist bucket: weight multiplier}, clamped to
    [MIN_WEIGHT, MAX_WEIGHT] so one standout or one flop can't swing
    selection odds too hard in either direction. Returns {} when there
    isn't enough real, measured data yet for any bucket."""
    views_by_id = _load_views_by_video_id(metrics_path)
    if not views_by_id:
        return {}

    bucket_views: dict[str, list[float]] = {}
    for path in sorted(videos_dir.glob("*.done")):
        try:
            marker = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        video_id = str(marker.get("video_id") or "")
        if video_id not in views_by_id:
            continue
        bucket = playlist_bucket_for_title(str(marker.get("title") or ""))
        bucket_views.setdefault(bucket, []).append(views_by_id[video_id])

    eligible = {bucket: samples for bucket, samples in bucket_views.items() if len(samples) >= min_samples}
    if not eligible:
        return {}

    all_samples = [v for samples in eligible.values() for v in samples]
    channel_avg = sum(all_samples) / len(all_samples)
    if channel_avg <= 0:
        return {}

    weights: dict[str, float] = {}
    for bucket, samples in eligible.items():
        bucket_avg = sum(samples) / len(samples)
        ratio = bucket_avg / channel_avg
        weights[bucket] = round(min(MAX_WEIGHT, max(MIN_WEIGHT, ratio)), 3)
    return weights
