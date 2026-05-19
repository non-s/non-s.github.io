"""
utils/velocity.py — Snapshot Shorts view counts at +2h / +6h / +24h.

The Shorts algorithm reads early-window velocity as the strongest
signal that a video is worth distributing further: a Short that hits
1 000 views in its first 2 h gets a meaningful explore-tab boost.
A Short that limps under 100 views in 2 h gets quietly shelved.

We can't manipulate velocity directly, but we CAN learn from it:

  1. Snapshot view counts at fixed offsets post-upload
  2. Persist as `_data/velocity.jsonl`
  3. Aggregate by category / hook style / topic_hashtag to find
     which dimensions correlate with high early-velocity
  4. Feed back into fetch_animals.py's scoring on the next run

The third + fourth steps land in the analytics workflow; this module
is the data-collection half.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

VELOCITY_LOG = Path(os.environ.get("VELOCITY_LOG", "_data/velocity.jsonl"))
# Snapshots are taken when the workflow run lands closest to each of
# these post-upload offsets (in hours). Tolerance is ±90 min, since
# the workflow runs at fixed cron times rather than offset-anchored.
SNAPSHOT_OFFSETS_H = (2, 6, 24)
SNAPSHOT_TOLERANCE_H = 1.5


def _iter_jsonl(path: Path):
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
    except Exception:
        return


def _videos_due_for_snapshot(done_dir: Path,
                              now: float | None = None) -> list[dict]:
    """Find all .done sidecars whose upload time matches a snapshot offset.

    Returns [{"video_id": ..., "offset_h": ..., "uploaded_at": ..., "slug": ...}].
    """
    now_ts = now or time.time()
    out: list[dict] = []
    if not done_dir.exists():
        return out
    for done_path in done_dir.glob("*.done"):
        try:
            data = json.loads(done_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        uploaded_at = data.get("uploaded_at", "")
        try:
            ts = datetime.fromisoformat(uploaded_at.replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        age_h = (now_ts - ts) / 3600.0
        for offset in SNAPSHOT_OFFSETS_H:
            if abs(age_h - offset) <= SNAPSHOT_TOLERANCE_H:
                out.append({
                    "video_id":    data.get("video_id"),
                    "slug":        done_path.stem,
                    "uploaded_at": uploaded_at,
                    "offset_h":    offset,
                    "age_h":       round(age_h, 2),
                    "category":    data.get("category", ""),
                    "experiments": data.get("experiments") or {},
                    "language":    data.get("language", "en"),
                })
                break
    return out


def _already_snapshotted(video_id: str, offset_h: int,
                         path: Path | None = None) -> bool:
    # Resolve at call time so tests can monkeypatch VELOCITY_LOG.
    p = path or VELOCITY_LOG
    for entry in _iter_jsonl(p):
        if (entry.get("video_id") == video_id and
                entry.get("offset_h") == offset_h):
            return True
    return False


def _append(entry: dict, path: Path | None = None) -> None:
    p = path or VELOCITY_LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def snapshot_velocities(youtube,
                         done_dirs: tuple[Path, ...] = (Path("_videos"),
                                                          Path("_videos_pt-BR")),
                         now: float | None = None) -> int:
    """For each .done sidecar in window, pull current view count + record.

    Returns the number of snapshots written. Idempotent — re-runs in
    the same offset window skip the videos already recorded for that
    offset.
    """
    from utils import youtube_quota

    n = 0
    targets: list[dict] = []
    for d in done_dirs:
        targets.extend(_videos_due_for_snapshot(d, now=now))
    if not targets:
        log.info("velocity: nothing due for snapshot this run")
        return 0
    # Batch by 50 (videos.list takes comma-separated ids).
    by_id: dict[str, dict] = {t["video_id"]: t for t in targets if t["video_id"]}
    ids = list(by_id)
    log.info("velocity: %d video(s) due for snapshot", len(ids))
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        try:
            resp = youtube.videos().list(
                part="statistics", id=",".join(chunk),
            ).execute()
            youtube_quota.record("videos.list",
                                   video_id=chunk[0] if chunk else "")
        except Exception as exc:
            log.warning("velocity: videos.list failed: %s", exc)
            continue
        for item in resp.get("items", []):
            vid = item["id"]
            target = by_id.get(vid)
            if not target:
                continue
            offset = target["offset_h"]
            if _already_snapshotted(vid, offset):
                continue
            stats = item.get("statistics") or {}
            entry = {
                "ts":           time.time(),
                "iso":          datetime.now(timezone.utc).isoformat(),
                "video_id":     vid,
                "slug":         target["slug"],
                "offset_h":     offset,
                "views":        int(stats.get("viewCount", 0)),
                "likes":        int(stats.get("likeCount", 0)),
                "comments":     int(stats.get("commentCount", 0)),
                "uploaded_at":  target["uploaded_at"],
                "category":     target["category"],
                "experiments":  target["experiments"],
                "language":     target["language"],
            }
            _append(entry)
            n += 1
            log.info("  📈 %s @+%dh → %d views",
                     vid, offset, entry["views"])
    return n


# ── Aggregation helpers (called by the analytics workflow) ──────

def aggregate_by_category(path: Path = VELOCITY_LOG) -> dict[str, dict]:
    """Mean +2h view count per category. Used to bias fetch_animals.py."""
    by_cat: dict[str, list[int]] = {}
    for entry in _iter_jsonl(path):
        if entry.get("offset_h") != 2:
            continue
        cat = (entry.get("category") or "").lower() or "uncategorised"
        by_cat.setdefault(cat, []).append(int(entry.get("views", 0)))
    out: dict[str, dict] = {}
    for cat, views in by_cat.items():
        if not views:
            continue
        out[cat] = {
            "n":         len(views),
            "mean_2h":   round(sum(views) / len(views), 1),
            "median_2h": sorted(views)[len(views) // 2],
            "max_2h":    max(views),
        }
    return out
