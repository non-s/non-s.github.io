"""
scripts/generate_dashboard.py — gera um dashboard HTML estatico a partir dos
dados ja coletados em _data/ (analytics, scene/title_pattern performance,
audiencia da live).

Nenhum dado novo e coletado aqui - so consome o que collect_analytics.py e
upload_youtube.py ja gravam toda semana. Sem dependencias externas (so
stdlib), pra nao adicionar peso ao requirements.txt so por causa de um
relatorio. Sempre gera algo, mesmo com arquivos ausentes (canal novo,
antes da primeira coleta de analytics) - cada secao mostra um aviso em vez
de quebrar o script inteiro.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "_data"

ANALYTICS_FILE = DATA_DIR / "analytics.json"
HISTORY_FILE = DATA_DIR / "analytics_history.json"
SCENE_PERFORMANCE_FILE = DATA_DIR / "scene_performance.json"
TITLE_PATTERN_PERFORMANCE_FILE = DATA_DIR / "title_pattern_performance.json"
LIVE_VIEWER_HISTORY_FILE = DATA_DIR / "live_viewer_history.json"

_MAX_HISTORY_ROWS = 12
_MAX_LIVE_SNAPSHOTS = 20


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def _bar(value: float, max_value: float, color: str = "#f4a261") -> str:
    """Barra de progresso simples via CSS (sem SVG/JS)."""
    pct = 0.0 if max_value <= 0 else max(0.0, min(100.0, (value / max_value) * 100))
    return (
        f'<div class="bar-track"><div class="bar-fill" '
        f'style="width:{pct:.1f}%;background:{color}"></div></div>'
    )


def _card(label: str, value: str) -> str:
    return f'<div class="card"><div class="card-value">{escape(value)}</div><div class="card-label">{escape(label)}</div></div>'


def _render_summary(analytics: dict) -> str:
    if not analytics:
        return "<p class='empty'>Nenhum dado de analytics coletado ainda.</p>"
    cards = [
        _card("Vídeos", str(analytics.get("total_videos", 0))),
        _card("Views totais", f"{analytics.get('total_views', 0):,}".replace(",", ".")),
        _card("Likes totais", f"{analytics.get('total_likes', 0):,}".replace(",", ".")),
        _card("Comentários", f"{analytics.get('total_comments', 0):,}".replace(",", ".")),
        _card("Média de views/vídeo", f"{analytics.get('avg_views', 0):,}".replace(",", ".")),
    ]
    return f'<div class="cards">{"".join(cards)}</div>'


def _render_history(history: list) -> str:
    if not history:
        return "<p class='empty'>Sem histórico semanal ainda (primeira coleta ainda não rodou).</p>"
    rows = history[-_MAX_HISTORY_ROWS:]
    max_views = max((r.get("total_views", 0) for r in rows), default=0)
    trs = []
    for r in rows:
        date = escape(str(r.get("collected_at", ""))[:10])
        views = r.get("total_views", 0)
        trs.append(
            f"<tr><td>{date}</td><td>{views:,}</td><td>{r.get('total_likes', 0):,}</td>"
            f"<td>{r.get('avg_views', 0):,}</td><td>{_bar(views, max_views)}</td></tr>".replace(",", ".")
        )
    return (
        "<table><thead><tr><th>Semana</th><th>Views</th><th>Likes</th>"
        f"<th>Média/vídeo</th><th>Tendência</th></tr></thead><tbody>{''.join(trs)}</tbody></table>"
    )


def _render_weighted_table(weights: dict, name_col: str) -> str:
    if not weights:
        return "<p class='empty'>Sem dados suficientes ainda (menos de 3 amostras por opção).</p>"
    ordered = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    max_weight = max((w for _, w in ordered), default=1.0)
    rows = []
    for name, weight in ordered:
        rows.append(
            f"<tr><td class='mono'>{escape(str(name))}</td><td>{weight:.2f}×</td>"
            f"<td>{_bar(weight, max_weight)}</td></tr>"
        )
    return (
        f"<table><thead><tr><th>{escape(name_col)}</th><th>Peso</th><th></th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_top_videos(analytics: dict) -> str:
    top = analytics.get("top_10") if analytics else None
    if not top:
        return "<p class='empty'>Sem dados de vídeos ainda.</p>"
    rows = []
    for v in top:
        title = escape(str(v.get("title", ""))[:80])
        vid = v.get("video_id", "")
        link = f"https://youtu.be/{vid}" if vid else "#"
        rows.append(
            f"<tr><td><a href='{escape(link)}' target='_blank' rel='noopener'>{title}</a></td>"
            f"<td>{v.get('views', 0):,}</td><td>{v.get('likes', 0):,}</td></tr>".replace(",", ".")
        )
    return (
        "<table><thead><tr><th>Título</th><th>Views</th><th>Likes</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_live_audience(snapshots: list) -> str:
    if not snapshots:
        return "<p class='empty'>Sem amostras de audiência da live ainda.</p>"
    recent = snapshots[-_MAX_LIVE_SNAPSHOTS:]
    viewers = [s.get("concurrent_viewers", 0) for s in recent]
    avg = sum(viewers) / len(viewers) if viewers else 0
    peak = max(viewers, default=0)
    cards = [
        _card("Espectadores (média recente)", f"{avg:.0f}"),
        _card("Pico recente", str(peak)),
        _card("Amostras", str(len(snapshots))),
    ]
    return f'<div class="cards">{"".join(cards)}</div>'


def build_dashboard_html() -> str:
    analytics = _load_json(ANALYTICS_FILE, {})
    history = _load_json(HISTORY_FILE, [])
    scene_weights = _load_json(SCENE_PERFORMANCE_FILE, {})
    title_pattern_weights = _load_json(TITLE_PATTERN_PERFORMANCE_FILE, {})
    live_snapshots = _load_json(LIVE_VIEWER_HISTORY_FILE, [])

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pata Jazz — Dashboard</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    max-width: 960px; margin: 0 auto; padding: 24px 16px 64px;
    background: #0f0f23; color: #f8f8ff;
  }}
  h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
  .subtitle {{ color: #9a9ab8; margin-top: 0; margin-bottom: 32px; font-size: 0.9rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 40px; border-bottom: 1px solid #2a2a40; padding-bottom: 8px; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 12px; }}
  .card {{
    background: #1a1a3e; border-radius: 10px; padding: 16px 20px; min-width: 140px; flex: 1;
  }}
  .card-value {{ font-size: 1.5rem; font-weight: 700; color: #f4a261; }}
  .card-label {{ font-size: 0.8rem; color: #9a9ab8; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #2a2a40; }}
  th {{ color: #9a9ab8; font-weight: 600; }}
  a {{ color: #f4a261; }}
  .mono {{ font-family: ui-monospace, monospace; font-size: 0.8rem; }}
  .bar-track {{ width: 100px; height: 8px; background: #2a2a40; border-radius: 4px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; }}
  .empty {{ color: #9a9ab8; font-style: italic; }}
  footer {{ margin-top: 48px; color: #6a6a8a; font-size: 0.75rem; }}
</style>
</head>
<body>
  <h1>🐾🎷 Pata Jazz — Dashboard</h1>
  <p class="subtitle">Gerado automaticamente a partir dos dados coletados por collect_analytics.py</p>

  <h2>Resumo geral</h2>
  {_render_summary(analytics)}

  <h2>Tendência semanal</h2>
  {_render_history(history)}

  <h2>Top 10 vídeos</h2>
  {_render_top_videos(analytics)}

  <h2>Performance por cena</h2>
  {_render_weighted_table(scene_weights, "Cena")}

  <h2>Performance por padrão de título</h2>
  {_render_weighted_table(title_pattern_weights, "Padrão")}

  <h2>Audiência da live</h2>
  {_render_live_audience(live_snapshots)}

  <footer>Gerado em {generated_at}</footer>
</body>
</html>
"""


def main() -> int:
    output_dir = ROOT / "_dashboard"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "index.html"
    output_path.write_text(build_dashboard_html(), encoding="utf-8")
    print(f"Dashboard gerado: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
