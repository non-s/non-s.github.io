"""
utils/digest.py — Daily digest GitHub Issue for human-in-the-loop review.

The case-study research is unanimous: the #1 thing that gets automated
channels terminated is "treating automation as abdication" — no human
reviewing the output. A 30-second daily glance is enough.

This module renders a Markdown digest of everything published in the
last 24 hours (titles, hooks, script previews, b-roll status, caption
status, quality grade, retention if available) and posts it as a
GitHub Issue.

GitHub Issues are free, persistent, and a clean audit trail. The
operator opens the Issue once a day on their phone, eyeballs the
Shorts that shipped, comments with feedback or `/block <slug>` to
prevent a Short from re-running, then closes the Issue.

Activation
----------
Set `DIGEST_REPO` (e.g. "non-s/non-s.github.io") + a token with
issues:write permission. The workflow's `GITHUB_TOKEN` is sufficient
when the digest runs INSIDE the repo's own Actions.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)

VIDEOS_DIRS = (Path("_videos"), Path("_videos_pt-BR"))


def _read_done(done_path: Path) -> dict | None:
    try:
        return json.loads(done_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_meta_alongside(done_path: Path) -> dict:
    """If a metadata JSON sibling still exists, parse it for extra fields.
    Most of the time it's been deleted by upload_youtube.py after success."""
    meta_path = done_path.with_suffix(".json")
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def collect_recent_shorts(lookback_hours: int = 24) -> list[dict]:
    """Walk every *.done file across all language video directories and
    return the ones uploaded inside the lookback window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    out: list[dict] = []
    for d in VIDEOS_DIRS:
        if not d.exists():
            continue
        for done_path in sorted(d.glob("*.done")):
            data = _read_done(done_path)
            if not data:
                continue
            try:
                ts = datetime.fromisoformat(
                    (data.get("uploaded_at") or "").replace("Z", "+00:00")
                )
            except Exception:
                continue
            if ts < cutoff:
                continue
            data["_dir"] = d.name
            data["_slug"] = done_path.stem
            out.append(data)
    out.sort(key=lambda d: d.get("uploaded_at", ""), reverse=True)
    return out


def render_digest(shorts: list[dict], analytics_summary: dict | None = None) -> str:
    """Return a Markdown body for the GitHub Issue."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines: list[str] = [
        f"## Daily Short Review — {today} UTC",
        "",
        f"**{len(shorts)} Short(s) published in the last 24 hours.**",
        "",
        "Review checklist (30 seconds):",
        "- [ ] Each hook leads with action / number — no \"Today\" / \"In a recent\"",
        "- [ ] Each script adds analysis beyond the source article",
        "- [ ] No AI-tell phrases on display (\"crucial\", \"pivotal\", \"delve\")",
        "- [ ] Thumbnails read clearly at small size",
        "- [ ] Captions are accurate (open one and skim)",
        "",
        "Reply with `/block <slug>` to skip the underlying story on the next run, "
        "or close this issue when reviewed.",
        "",
        "---",
        "",
    ]

    # Channel pulse appears even on 0-Short days so the operator
    # can spot "we published nothing AND retention's dropping" early.
    if analytics_summary:
        lines.append("### Channel pulse (last 14 days, from analytics workflow)")
        lines.append("")
        lines.append(f"- Avg view %: **{analytics_summary.get('avg_view_pct', '?')}**")
        lines.append(f"- Total views (14d): {analytics_summary.get('total_views_14d', '?')}")
        underperf = analytics_summary.get("below_60_pct") or []
        lines.append(f"- Underperforming (<60 % retention): {len(underperf)}")
        cat = analytics_summary.get("category_avg_view_pct") or {}
        if cat:
            top = sorted(cat.items(), key=lambda kv: kv[1], reverse=True)[:5]
            lines.append("- Top categories: " + ", ".join(f"{k} ({v:.0f}%)" for k, v in top))
        lines.append("")

    # A/B experiment winners (set by the analytics workflow).
    exp_path = Path("_data/analytics/experiments.json")
    if exp_path.exists():
        try:
            exp_payload = json.loads(exp_path.read_text(encoding="utf-8"))
        except Exception:
            exp_payload = {}
        winners = exp_payload.get("winners") or {}
        if winners:
            lines.append("### A/B winners")
            lines.append("")
            for axis, variant in winners.items():
                lift = (exp_payload.get("lift") or {}).get(axis, {}).get("lift")
                lift_s = f" (+{lift:.1f} pp)" if isinstance(lift, (int, float)) else ""
                lines.append(f"- **{axis}**: `{variant}`{lift_s}")
            lines.append("")

    # Audience cohort timing recommendation.
    cohort_path = Path("_data/analytics/cohort_timing.json")
    if cohort_path.exists():
        try:
            cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
        except Exception:
            cohort = {}
        slots = cohort.get("recommended_utc_hours") or []
        if slots:
            lines.append("### Optimal posting times (per audience cohort)")
            lines.append("")
            for s in slots:
                lines.append(
                    f"- {s['country']} ({s['views']} views, "
                    f"UTC{s['local_offset_h']:+d}) → **{s['utc_hour']:02d}:00 UTC**"
                )
            lines.append("")

    if not shorts:
        lines.append("_No Shorts shipped in the last 24 h._ Possible causes: "
                     "Mistral 429 with no fallback configured, all stories failed "
                     "the quality gate, or the workflow didn't run.")
        return "\n".join(lines)

    for s in shorts:
        title = s.get("title", "(no title)")
        url = s.get("url", "")
        slug = s.get("_slug", "?")
        directory = s.get("_dir", "_videos")
        lang = "PT-BR" if directory.endswith("_pt-BR") else "EN"
        uploaded = s.get("uploaded_at", "")
        lines.append(f"### [{lang}] {title}")
        lines.append("")
        if url:
            lines.append(f"- 📺 {url}")
        lines.append(f"- 🆔 `{slug}`")
        lines.append(f"- ⏰ uploaded {uploaded}")
        # Pull the hook + script preview from the sibling metadata file
        # if it was kept (we delete it on success today, but stay defensive).
        meta = _read_meta_alongside(Path(directory) / (slug + ".done"))
        hook = meta.get("hook") or ""
        if hook:
            lines.append(f"- 🎯 hook: _{hook[:200]}_")
        desc = s.get("description") or ""
        desc_lead = desc.split("\n", 1)[0][:240]
        if desc_lead:
            lines.append(f"- 📝 description: {desc_lead}")
        tags = s.get("tags") or []
        if tags:
            lines.append(f"- 🏷  tags: {', '.join(tags[:6])}")
        lines.append("")
    return "\n".join(lines)


# ── GitHub Issues API ────────────────────────────────────────────

def post_digest_issue(body: str, repo: str | None = None,
                       token: str | None = None,
                       title: str | None = None) -> str | None:
    """POST a new Issue to `repo`. Returns the URL, or None on failure.

    The workflow's `GITHUB_TOKEN` has `issues:write` permission as
    long as `permissions: issues: write` is set on the job. We use
    the default GITHUB_REPOSITORY env var for `repo` unless one is
    explicitly passed.
    """
    repo = repo or os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = token or os.environ.get("GITHUB_TOKEN", "").strip()
    if not repo or not token:
        log.info("digest: GITHUB_REPOSITORY / GITHUB_TOKEN not set — skipping")
        return None
    title = title or f"Daily Short review — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    try:
        r = requests.post(
            f"https://api.github.com/repos/{repo}/issues",
            json={
                "title": title,
                "body":  body[:60_000],   # GitHub caps issue body at 64 KB
                "labels": ["digest", "auto"],
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Accept":        "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )
        if r.status_code not in (200, 201):
            log.warning("digest issue create %d: %s", r.status_code, r.text[:200])
            return None
        return r.json().get("html_url")
    except Exception as exc:
        log.warning("digest issue create failed: %s", exc)
        return None


# ── /block <slug> harvesting ──────────────────────────────────────
#
# The operator can comment `/block <slug>` on any digest issue to
# stop the underlying story re-shipping. We accumulate those slugs
# into `_data/blocked_slugs.json`; generate_shorts.py consults the
# list and skips matches before any AI work.

BLOCKED_FILE = Path("_data/blocked_slugs.json")


def load_blocked_slugs() -> set[str]:
    if not BLOCKED_FILE.exists():
        return set()
    try:
        data = json.loads(BLOCKED_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(s) for s in data}
    except Exception:
        pass
    return set()


def save_blocked_slugs(slugs: set[str]) -> None:
    BLOCKED_FILE.parent.mkdir(parents=True, exist_ok=True)
    BLOCKED_FILE.write_text(
        json.dumps(sorted(slugs), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def harvest_block_commands(repo: str | None = None,
                            token: str | None = None,
                            lookback_days: int = 7) -> set[str]:
    """Read recent digest-issue comments, return slugs after `/block`.

    Idempotent: re-running just refreshes the same set.
    """
    repo = repo or os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = token or os.environ.get("GITHUB_TOKEN", "").strip()
    if not repo or not token:
        return set()
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    blocked: set[str] = set()
    try:
        # Pull issues with our "digest" label.
        r = requests.get(
            f"https://api.github.com/repos/{repo}/issues",
            params={
                "labels": "digest",
                "state":  "all",
                "since":  since,
                "per_page": "30",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Accept":        "application/vnd.github+json",
            },
            timeout=30,
        )
        if r.status_code != 200:
            return set()
        issues = r.json() or []
    except Exception:
        return set()

    import re
    block_re = re.compile(r"/block\s+([a-z0-9\-]{6,})", re.IGNORECASE)
    for issue in issues:
        comments_url = issue.get("comments_url", "")
        if not comments_url:
            continue
        try:
            r = requests.get(
                comments_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept":        "application/vnd.github+json",
                },
                timeout=15,
            )
            if r.status_code != 200:
                continue
            for c in r.json() or []:
                body = c.get("body", "") or ""
                for m in block_re.finditer(body):
                    blocked.add(m.group(1).lower())
        except Exception:
            continue
    return blocked
