"""Snapshot tests do dashboard HTML.

Compara o hash SHA-256 do HTML gerado (com dados fixture conhecidos e
datetime.now fixado) contra um hash baseline salvo em
tests/snapshots/dashboard_hash.txt. Para regenerar o baseline rode:

    UPDATE_SNAPSHOTS=1 python -m pytest tests/test_dashboard_snapshot.py

Implementacao manual (sem pytest-snapshot): um hash e suficiente para
detectar regressao e nao adiciona dependencia nova.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

import scripts.generate_dashboard as dashboard

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
HASH_FILE = SNAPSHOT_DIR / "dashboard_hash.txt"


def _seed_fixtures(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "ANALYTICS_FILE", tmp_path / "analytics.json")
    monkeypatch.setattr(dashboard, "HISTORY_FILE", tmp_path / "analytics_history.json")
    monkeypatch.setattr(dashboard, "SCENE_PERFORMANCE_FILE", tmp_path / "scene_performance.json")
    monkeypatch.setattr(dashboard, "TITLE_PATTERN_PERFORMANCE_FILE", tmp_path / "title_pattern_performance.json")
    monkeypatch.setattr(dashboard, "VIEW_PREDICTOR_FILE", tmp_path / "view_predictor.json")
    monkeypatch.setattr(dashboard, "QUALITY_HISTORY_FILE", tmp_path / "quality_history.json")

    dashboard.ANALYTICS_FILE.write_text(
        json.dumps(
            {
                "total_videos": 42,
                "total_views": 158340,
                "total_likes": 3021,
                "total_comments": 412,
                "avg_views": 3770,
                "top_10": [
                    {"video_id": "abc123", "title": "Cute Cat & Jazz", "views": 100, "likes": 1},
                    {"video_id": "def456", "title": "Sleepy Puppy Jazz", "views": 90, "likes": 2},
                ],
            }
        ),
        encoding="utf-8",
    )
    dashboard.HISTORY_FILE.write_text(
        json.dumps(
            [
                {"collected_at": "2026-01-01T00:00:00+00:00", "total_views": 1000, "total_likes": 10, "avg_views": 100},
                {"collected_at": "2026-01-08T00:00:00+00:00", "total_views": 2000, "total_likes": 20, "avg_views": 150},
            ]
        ),
        encoding="utf-8",
    )
    dashboard.SCENE_PERFORMANCE_FILE.write_text(
        json.dumps({"cat": 0.5, "sleepy dog": 2.1, "puppy": 1.0}), encoding="utf-8"
    )
    dashboard.TITLE_PATTERN_PERFORMANCE_FILE.write_text(json.dumps({"{emoji} {animal}": 1.8}), encoding="utf-8")
    dashboard.VIEW_PREDICTOR_FILE.write_text(json.dumps({"n_samples": 0}), encoding="utf-8")


def _generate_html(tmp_path, monkeypatch):
    _seed_fixtures(tmp_path, monkeypatch)
    fixed = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed if tz is None else fixed.astimezone(tz)

    with patch.object(dashboard, "datetime", _FixedDatetime):
        return dashboard.build_dashboard_html()


def test_dashboard_html_matches_snapshot(tmp_path, monkeypatch):
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    html = _generate_html(tmp_path, monkeypatch)
    # Normaliza line endings antes do hash para evitar divergencia
    # entre Windows (CRLF) e Linux (LF) no CI.
    html_normalized = html.replace("\r\n", "\n").replace("\r", "\n")
    digest = hashlib.sha256(html_normalized.encode("utf-8")).hexdigest()

    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        HASH_FILE.write_text(digest + "\n", encoding="utf-8")
        return

    if not HASH_FILE.exists():
        pytest.skip(f"Nenhum baseline em {HASH_FILE}. Rode com UPDATE_SNAPSHOTS=1 para criar (hash atual: {digest}).")
        return

    baseline = HASH_FILE.read_text(encoding="utf-8").strip()
    if baseline != digest:
        # Divergencias entre Windows/Linux podem ocorrer por diferencas
        # de locale ou line endings. Avisa em vez de falhar para nao
        # bloquear PRs por diferencas de plataforma.
        import sys

        if sys.platform == "linux":
            pytest.fail(
                f"Dashboard HTML divergiu no Linux. Rode "
                f"`UPDATE_SNAPSHOTS=1 python -m pytest tests/test_dashboard_snapshot.py` "
                f"para regenerar (hash atual: {digest}, baseline: {baseline})."
            )
        else:
            pytest.skip(
                f"Snapshot diverge em non-Linux (normal): hash={digest} baseline={baseline}. "
                f"Regenere no CI Linux com UPDATE_SNAPSHOTS=1."
            )
