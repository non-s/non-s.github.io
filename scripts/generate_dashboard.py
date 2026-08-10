"""
scripts/generate_dashboard.py — gera um dashboard HTML estatico a partir dos
dados ja coletados em _data/ (analytics, scene/title_pattern performance).

Nenhum dado novo e coletado aqui - so consome o que collect_analytics.py e
upload_youtube.py ja gravam toda semana. Sem dependencias externas (so
stdlib), pra nao adicionar peso ao requirements.txt so por causa de um
relatorio. Chart.js entra via CDN no HTML final (sem build). Sempre gera algo,
mesmo com arquivos ausentes (canal novo, antes da primeira coleta de
analytics) - cada secao mostra um aviso em vez de quebrar o script inteiro.
"""

from __future__ import annotations

import json
import logging
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.paths import data_dir

log = logging.getLogger(__name__)

DATA_DIR = data_dir()
DASHBOARD_DIR = ROOT / "_dashboard"

ANALYTICS_FILE = DATA_DIR / "analytics.json"
HISTORY_FILE = DATA_DIR / "analytics_history.json"
SCENE_PERFORMANCE_FILE = DATA_DIR / "scene_performance.json"
TITLE_PATTERN_PERFORMANCE_FILE = DATA_DIR / "title_pattern_performance.json"
VIEW_PREDICTOR_FILE = DATA_DIR / "view_predictor.json"
VIDEO_TAGS_FILE = DATA_DIR / "video_tags.json"

_MAX_HISTORY_ROWS = 12

# Chart.js 4.x via jsdelivr (CDN estavel, sem build). SRI calculado a partir
# do arquivo oficial da versao; fallback offline copiado para _dashboard/.
_CHART_JS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"
_CHART_JS_SRI = "sha384-JUh163oCRItcbPme8pYnROHQMC6fNKTBWtRG3I3I0erJkzNgL7uxKlNwcrcFKeqF"
_CHART_JS_FALLBACK = "chart.umd.min.js"


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def _bar(value: float, max_value: float, color: str = "#f4a261") -> str:
    """Barra de progresso simples via CSS (sem SVG/JS)."""
    pct = 0.0 if max_value <= 0 else max(0.0, min(100.0, (value / max_value) * 100))
    return f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%;background:{color}"></div></div>'


def _card(label: str, value: str) -> str:
    return (
        f'<div class="card"><div class="card-value">{escape(value)}</div>'
        f'<div class="card-label">{escape(label)}</div></div>'
    )


def _render_summary(analytics: dict) -> str:
    if not analytics:
        return "<p class='empty'>Nenhum dado de analytics coletado ainda.</p>"
    retention = analytics.get("retention_metrics") or {}
    avg_ctr = _avg_metric(retention, "ctr")
    avg_avp = _avg_metric(retention, "averageViewPercentage")
    avg_subs = _avg_metric(retention, "subscribersGained")
    ypp = analytics.get("ypp_eligibility") or {}
    cards = [
        _card("Vídeos", str(analytics.get("total_videos", 0))),
        _card("Views totais", f"{analytics.get('total_views', 0):,}".replace(",", ".")),
        _card("Likes totais", f"{analytics.get('total_likes', 0):,}".replace(",", ".")),
        _card("Comentários", f"{analytics.get('total_comments', 0):,}".replace(",", ".")),
        _card("Média de views/vídeo", f"{analytics.get('avg_views', 0):,}".replace(",", ".")),
        _card("CTR médio", f"{avg_ctr:.2%}" if avg_ctr else "—"),
        _card("Retenção média", f"{avg_avp:.1f}%" if avg_avp else "—"),
        _card("Inscritos ganhos", f"{avg_subs:+.1f}" if avg_subs else "—"),
        _card(
            "Progresso YPP",
            f"{int(ypp.get('subscriber_progress', 0) * 100)}% / {int(ypp.get('watch_hours_progress', 0) * 100)}%",
        ),
    ]
    return f'<div class="cards">{"".join(cards)}</div>'


def _avg_metric(retention: dict, key: str) -> float | None:
    """Calcula a média simples de uma métrica presente no dict retention_metrics."""
    values = [v.get(key, 0) for v in retention.values() if isinstance(v, dict)]
    if not values:
        return None
    total = sum(float(x) for x in values if x is not None)
    return total / len(values) if total else None


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
        ctr = v.get("ctr")
        avp = v.get("averageViewPercentage")
        rows.append(
            f"<tr><td><a href='{escape(link)}' target='_blank' rel='noopener'>{title}</a></td>"
            f"<td>{v.get('views', 0):,}</td><td>{v.get('likes', 0):,}</td>"
            f"<td>{v.get('comments', 0):,}</td>"
            f"<td>{f'{ctr:.2%}' if ctr is not None else '—'}</td>"
            f"<td>{f'{avp:.1f}%' if avp is not None else '—'}</td></tr>".replace(",", ".")
        )
    return (
        "<table><thead><tr><th>Título</th><th>Views</th>"
        "<th>Likes</th><th>Comentários</th><th>CTR</th>"
        f"<th>Retenção</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _render_thumbnail_variants(video_tags: dict) -> str:
    """Painel A/B/C de thumbnails.

    Le _data/video_tags.json (gravado por collect_analytics.py/upload_youtube.py)
    e mostra tabela por video: id (link youtu.be), variante ativa, views e data
    de rotacao. Retorna aviso em vez de quebrar quando o arquivo esta ausente
    ou vazio."""
    if not video_tags:
        return "<p class='empty'>Sem dados de variantes ainda.</p>"
    rows = []
    for vid, entry in video_tags.items():
        if not isinstance(entry, dict):
            continue
        variant = escape(str(entry.get("thumbnail_variant", "A")))
        views = entry.get("views", 0)
        rotated_at = escape(str(entry.get("rotated_at", ""))[:10])
        link = f"https://youtu.be/{vid}" if vid else "#"
        rows.append(
            f"<tr><td class='mono'><a href='{escape(link)}' target='_blank' rel='noopener'>{escape(str(vid))}</a></td>"
            f"<td>{variant}</td><td>{views:,}</td><td>{rotated_at}</td></tr>".replace(",", ".")
        )
    if not rows:
        return "<p class='empty'>Sem dados de variantes ainda.</p>"
    return (
        "<table><thead><tr><th>Vídeo</th><th>Variante ativa</th><th>Views</th>"
        f"<th>Rotação</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


_DAY_OF_WEEK_NAMES = [
    "seg",
    "ter",
    "qua",
    "qui",
    "sex",
    "sáb",
    "dom",
]


def _render_predicted_views(predictor: dict) -> str:
    """Seção "Predicted views (next 7 days)" — previsões para os próximos
    4 slots de cron de shorts (cron horário, ver SHORTS_CRON_HOURS_UTC em
    scripts/predict_views.py).

    Consome apenas o modelo já salvo em _data/view_predictor.json por
    scripts/predict_views.py (que treina a partir de analytics + video_tags).
    Nunca quebra o dashboard: modelo ausente/vazio mostra aviso em vez de erro."""
    if not predictor or predictor.get("n_samples", 0) == 0:
        return (
            "<p class='empty'>Sem modelo de previsão ainda (rodar scripts/predict_views.py após coletar analytics).</p>"
        )
    from scripts.predict_views import expected_views_for_slot, next_cron_slots

    slots = next_cron_slots(n=4)
    if not slots:
        return "<p class='empty'>Não foi possível enumerar os próximos slots de cron.</p>"

    rows = []
    for hour, dow in slots:
        predicted = expected_views_for_slot(hour, dow)
        label = f"{hour:02d}:00 UTC ({_DAY_OF_WEEK_NAMES[dow]})"
        rows.append(f"<tr><td class='mono'>{escape(label)}</td><td>{max(0, int(round(predicted)))}</td></tr>")
    return (
        "<table><thead><tr><th>Próximo slot</th><th>Views previstos (7d)</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _render_recommendations(
    predictor: dict,
    scene_weights: dict,
    title_pattern_weights: dict,
) -> str:
    """Seção de recomendações ativas: melhor cena, melhor padrão e próximo
    slot otimizado, de acordo com o modelo preditivo e pesos de performance.

    Usa o mesmo modelo de predict_views; sem modelo, usa os pesos de
    performance como fallback."""
    if not predictor or predictor.get("n_samples", 0) == 0:
        if scene_weights or title_pattern_weights:
            best_scene = max(scene_weights.items(), key=lambda kv: kv[1])[0] if scene_weights else "—"
            best_pattern = max(title_pattern_weights.items(), key=lambda kv: kv[1])[0] if title_pattern_weights else "—"
            return (
                f"<p class='empty'>Sem modelo preditivo ainda. Fallback por performance: "
                f"cena <strong>{escape(str(best_scene))}</strong>, "
                f"padrão <strong>{escape(str(best_pattern))}</strong>.</p>"
            )
        return "<p class='empty'>Sem dados suficientes para recomendações ainda.</p>"

    from scripts.predict_views import expected_views_for_slot, next_cron_slots, predict_views

    scenes = predictor.get("scenes") or []
    title_patterns = predictor.get("title_patterns") or []
    if not scenes or not title_patterns:
        return "<p class='empty'>Modelo preditivo sem vocabulário de cenas/padrões.</p>"

    # Próximo slot otimizado (próximas 24h)
    best_slot = None
    best_slot_score = -1.0
    for hour, dow in next_cron_slots(n=24):
        score = expected_views_for_slot(hour, dow)
        if score > best_slot_score:
            best_slot_score = score
            best_slot = (hour, dow)

    # Melhor (cena, padrão) para o melhor slot
    best_combo = None
    best_combo_score = -1.0
    hour, dow = best_slot or (0, 0)
    for scene in scenes:
        for pattern in title_patterns:
            score = predict_views(scene, pattern, hour, dow)
            if score > best_combo_score:
                best_combo_score = score
                best_combo = (scene, pattern)

    slot_label = f"{hour:02d}:00 UTC ({_DAY_OF_WEEK_NAMES[dow]})" if best_slot else "—"
    scene_str, pattern_str = best_combo or ("—", "—")
    predicted = max(0, int(round(best_combo_score)))
    return (
        "<div class='recommendations'>"
        f"<div class='rec-card'><strong>Melhor slot</strong>"
        f"<span>{escape(slot_label)}</span></div>"
        f"<div class='rec-card'><strong>Melhor cena</strong>"
        f"<span>{escape(str(scene_str))}</span></div>"
        f"<div class='rec-card'><strong>Melhor padrão</strong>"
        f"<span>{escape(str(pattern_str))}</span></div>"
        f"<div class='rec-card'><strong>Previsão 7d</strong>"
        f"<span>{predicted} views</span></div>"
        "</div>"
    )


_HEATMAP_HOUR_BUCKETS = (
    ("manhã", 9),
    ("tarde", 15),
    ("noite", 21),
)


def _build_scene_hour_matrix(predictor: dict) -> dict:
    """Matriz de views previstos por (cena, hour_bucket) usando o modelo
    view_predictor. Para cada bucket, usa uma hora representativa (9/15/21 UTC)
    e um weekday neutro (quarta=2). Retorna {"scenes": [...], "buckets": [...],
    "matrix": {scene: {bucket: value}}}.

    Sem modelo (ou n_samples==0), retorna estrutura vazia — o render mostra aviso.
    """
    if not predictor or predictor.get("n_samples", 0) == 0:
        return {"scenes": [], "buckets": [b for b, _ in _HEATMAP_HOUR_BUCKETS], "matrix": {}}
    from scripts.predict_views import predict_views

    scenes = predictor.get("scenes") or []
    title_patterns = predictor.get("title_patterns") or []
    # Padrão "neutro" para isolar o efeito cena × horário: media sobre todos
    # os padrões (igual a expected_views_for_slot, mas fixando a cena).
    matrix: dict[str, dict[str, float]] = {}
    for scene in scenes:
        row: dict[str, float] = {}
        for bucket_label, hour in _HEATMAP_HOUR_BUCKETS:
            if not title_patterns:
                row[bucket_label] = predict_views(scene, "", hour, 2)
            else:
                total = 0.0
                for pattern in title_patterns:
                    total += predict_views(scene, pattern, hour, 2)
                row[bucket_label] = total / len(title_patterns)
        matrix[scene] = row
    return {"scenes": scenes, "buckets": [b for b, _ in _HEATMAP_HOUR_BUCKETS], "matrix": matrix}


def _heatmap_color(intensity: float) -> str:
    """Retorna background-color CSS baseado na intensidade [0,1] — escala
    laranja (accent Pata Jazz) sobre fundo escuro."""
    if intensity <= 0:
        return "#2a2a40"
    # Interpola de #2a2a40 (fundo) ate #f4a261 (accent) por canal.
    r_fondo, g_fondo, b_fondo = (42, 42, 64)
    r_accent, g_accent, b_accent = (244, 162, 97)
    r = int(r_fondo + (r_accent - r_fondo) * intensity)
    g = int(g_fondo + (g_accent - g_fondo) * intensity)
    b = int(b_fondo + (b_accent - b_fondo) * intensity)
    return f"rgb({r},{g},{b})"


def _render_scene_hour_heatmap(predictor: dict) -> str:
    """Renderiza a matriz cena × horário como tabela HTML colorida (CSS
    inline background-color baseado na intensidade do valor). Sem Chart.js."""
    data = _build_scene_hour_matrix(predictor)
    scenes = data["scenes"]
    buckets = data["buckets"]
    matrix = data["matrix"]
    if not scenes or not matrix:
        return "<p class='empty'>Sem modelo de previsão ainda para o heatmap (rodar scripts/predict_views.py).</p>"
    # Max para normalizar intensidade.
    all_values = [matrix[s][b] for s in scenes for b in buckets if b in matrix[s]]
    max_value = max(all_values) if all_values else 0.0

    header = "".join(f"<th>{escape(b)}</th>" for b in buckets)
    rows = []
    for scene in scenes:
        cells = [f'<td class="mono">{escape(scene)}</td>']
        for b in buckets:
            value = matrix[scene].get(b, 0.0)
            intensity = (value / max_value) if max_value > 0 else 0.0
            color = _heatmap_color(intensity)
            cells.append(f'<td style="background:{color};text-align:center">{max(0, int(round(value)))}</td>')
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return "<table><thead><tr><th>Cena × Horário</th>" + header + f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _chart_canvas(canvas_id: str, height: str = "300px") -> str:
    """Container responsivo com canvas para um grafico Chart.js."""
    return f'<div class="chart-wrap" style="height:{height}"><canvas id="{canvas_id}"></canvas></div>'


def _build_chart_datasets(history: list) -> dict:
    """Extrai labels/datasets do historico semanal para o grafico de linha
    de views totais + media por video."""
    rows = history[-_MAX_HISTORY_ROWS:] if history else []
    labels = [str(r.get("collected_at", ""))[:10] for r in rows]
    total_views = [r.get("total_views", 0) for r in rows]
    avg_views = [r.get("avg_views", 0) for r in rows]
    return {"labels": labels, "total_views": total_views, "avg_views": avg_views}


def _build_views_by_day_dataset(analytics: dict) -> dict:
    """#11: Agrupa views por dia de publicacao (published_at) para um
    grafico de serie temporal de views/dia - mostra se as features novas
    estao funcionando ao longo do tempo."""
    if not analytics:
        return {"labels": [], "views": []}
    all_videos = analytics.get("all_videos") or []
    by_day: dict[str, int] = {}
    for v in all_videos:
        if not isinstance(v, dict):
            continue
        pub = str(v.get("published_at", ""))[:10]
        if not pub:
            continue
        by_day[pub] = by_day.get(pub, 0) + int(v.get("views", 0) or 0)
    if not by_day:
        return {"labels": [], "views": []}
    sorted_days = sorted(by_day.items())
    return {
        "labels": [d for d, _ in sorted_days],
        "views": [v for _, v in sorted_days],
    }


def _build_scene_dataset(scene_weights: dict) -> dict:
    ordered = sorted(scene_weights.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "labels": [escape(str(name)) for name, _ in ordered],
        "weights": [float(w) for _, w in ordered],
    }


def _build_title_pattern_dataset(title_pattern_weights: dict) -> dict:
    ordered = sorted(title_pattern_weights.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "labels": [escape(str(name)) for name, _ in ordered],
        "weights": [float(w) for _, w in ordered],
    }


def _build_top_videos_dataset(analytics: dict) -> dict:
    top = analytics.get("top_10") if analytics else None
    if not top:
        return {"labels": [], "views": []}
    return {
        "labels": [escape(str(v.get("title", ""))[:40]) for v in top],
        "views": [int(v.get("views", 0)) for v in top],
    }


def _build_thumbnail_variant_dataset(video_tags: dict) -> dict:
    """Conta quantos videos estao em cada variante (A/B/C) para o doughnut."""
    counts = {"A": 0, "B": 0, "C": 0}
    if video_tags:
        for entry in video_tags.values():
            if not isinstance(entry, dict):
                continue
            variant = str(entry.get("thumbnail_variant", "A")).upper()
            if variant in counts:
                counts[variant] += 1
    return {"labels": ["A", "B", "C"], "counts": [counts["A"], counts["B"], counts["C"]]}


def _ensure_chart_js_fallback(output_dir: Path) -> None:
    """Copia uma versao offline do Chart.js para _dashboard/.

    Se o CDN falhar no navegador do usuario, o <script> troca para este
    arquivo local. Tenta primeiro baixar a versao oficial para garantir que
    o fallback seja identico ao CDN; se a rede nao estiver disponivel na
    geracao, usa uma copia ja existente em _dashboard/ (ou gera o HTML
    sem fallback, que ainda funciona via CDN).
    """
    fallback_path = output_dir / _CHART_JS_FALLBACK
    existing = fallback_path.exists()
    try:
        # URL fixa e conhecida (jsdelivr CDN). O uso de urllib aqui e
        # seguro porque o destino e controlado; bandit B310 alerta sobre
        # schemes arbitrarios, mas o valor e hardcoded HTTPS.
        with urllib.request.urlopen(_CHART_JS_CDN, timeout=30) as resp:  # nosec B310
            data = resp.read()
        output_dir.mkdir(parents=True, exist_ok=True)
        fallback_path.write_bytes(data)
        log.info("Fallback Chart.js atualizado em %s (%d bytes).", fallback_path, len(data))
        return
    except urllib.error.URLError as exc:
        log.warning("Nao foi possivel baixar Chart.js para fallback offline: %s", exc)
    except OSError as exc:
        log.warning("Erro ao salvar Chart.js offline: %s", exc)

    if existing:
        log.info("Mantendo Chart.js offline existente em %s.", fallback_path)


def build_dashboard_html() -> str:
    analytics = _load_json(ANALYTICS_FILE, {})
    history = _load_json(HISTORY_FILE, [])
    scene_weights = _load_json(SCENE_PERFORMANCE_FILE, {})
    title_pattern_weights = _load_json(TITLE_PATTERN_PERFORMANCE_FILE, {})
    view_predictor = _load_json(VIEW_PREDICTOR_FILE, {})
    video_tags = _load_json(VIDEO_TAGS_FILE, {})

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # Datasets embutidos como JSON (autocontido, sem backend). html.escape nao
    # se aplica a conteudo de <script> JSON — usamos json.dumps com
    # ensure_ascii=False e escapamos "</" para evitar fechamento prematuro do
    # bloco de script. Dados de _data/ (titulos do YouTube, etc.) sao
    # escapados nos datasets de barra/doughnut (labels) via escape() antes do
    # dumps.
    history_ds = _build_chart_datasets(history)
    views_by_day_ds = _build_views_by_day_dataset(analytics)
    scene_ds = _build_scene_dataset(scene_weights)
    title_ds = _build_title_pattern_dataset(title_pattern_weights)
    top_ds = _build_top_videos_dataset(analytics)
    thumb_ds = _build_thumbnail_variant_dataset(video_tags)

    def _safe_json(obj) -> str:
        # Escapa "</" para evitar saida prematura de <script> e mantem JSON
        # valido. json.dumps ja escapa aspas/barra; so precisamos cuidar do
        # "</" sequencia.
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    history_json = _safe_json(history_ds)
    views_by_day_json = _safe_json(views_by_day_ds)
    scene_json = _safe_json(scene_ds)
    title_json = _safe_json(title_ds)
    top_json = _safe_json(top_ds)
    thumb_json = _safe_json(thumb_ds)

    return rf"""<!doctype html>
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
    background: rgba(26, 26, 62, 0.55); backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px); border: 1px solid rgba(244, 162, 97, 0.12);
    border-radius: 12px; padding: 16px 20px; min-width: 140px; flex: 1;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25);
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
  .chart-wrap {{
    background: rgba(26, 26, 62, 0.45); backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px); border: 1px solid rgba(244, 162, 97, 0.08);
    border-radius: 12px; padding: 16px; margin: 12px 0 24px;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.2); position: relative;
  }}
  .chart-wrap canvas {{ max-width: 100%; }}
  .filters {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 8px 0 4px; }}
  .filters label {{ color: #9a9ab8; font-size: 0.85rem; }}
  .filters select {{
    background: #1a1a3e; color: #f8f8ff; border: 1px solid #2a2a40;
    border-radius: 6px; padding: 4px 8px; font-size: 0.85rem;
  }}
  footer {{ margin-top: 48px; color: #6a6a8a; font-size: 0.75rem; }}
  .refresh-bar {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 24px; }}
  .refresh-btn {{
    background: #1a1a3e; color: #f4a261; border: 1px solid rgba(244, 162, 97, 0.4);
    border-radius: 6px; padding: 6px 14px; font-size: 0.85rem; cursor: pointer;
  }}
  .refresh-btn:hover {{ background: #2a2a40; }}
  .refresh-btn:disabled {{ opacity: 0.5; cursor: wait; }}
  .refresh-status {{ color: #9a9ab8; font-size: 0.8rem; }}
  .note {{ color: #6a6a8a; font-size: 0.75rem; margin: 8px 0 0; }}
  .recommendations {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 12px 0 24px; }}
  .rec-card {{
    background: rgba(26, 26, 62, 0.55); border: 1px solid rgba(244, 162, 97, 0.12);
    border-radius: 12px; padding: 14px 18px; min-width: 160px; flex: 1;
    display: flex; flex-direction: column; gap: 4px;
  }}
  .rec-card strong {{ color: #f4a261; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .rec-card span {{ font-size: 1.1rem; font-weight: 600; }}
</style>
</head>
<body>
  <h1 id="dash-title">🐾🎷 Pata Jazz — Dashboard</h1>
  <p class="subtitle" id="dash-subtitle">Gerado automaticamente a partir dos
  dados coletados por collect_analytics.py</p>

  <div class="refresh-bar">
    <button id="refresh-btn" class="refresh-btn" type="button">Atualizar dados</button>
    <button id="csv-btn" class="refresh-btn" type="button">Baixar CSV</button>
    <span id="refresh-status" class="refresh-status"></span>
  </div>
  <p class="note">
    Os dados em _data/ só atualizam quando o workflow pata-jazz-analytics.yml roda (semanal).
    O botão "Atualizar dados" refaz o fetch de analytics.json hospedado no mesmo GitHub Pages —
    se já publicado, os gráficos refletem o último snapshot; caso contrário, mantém os dados
    embutidos na geração estática.
  </p>

  <h2>Resumo geral</h2>
  {_render_summary(analytics)}

  <h2>Tendência semanal</h2>
  <div class="filters">
    <label for="period-filter">Período:</label>
    <select id="period-filter" aria-label="Seletor de período do gráfico de views">
      <option value="4">Últimas 4 semanas</option>
      <option value="12" selected>Últimas 12 semanas</option>
      <option value="0">Tudo</option>
    </select>
  </div>
  {_chart_canvas("viewsChart")}
  {_render_history(history)}

  <h2>Views por dia de publicação</h2>
  {_chart_canvas("viewsByDayChart", "280px")}

  <h2>Views por cena</h2>
  {_chart_canvas("sceneChart")}
  {_render_weighted_table(scene_weights, "Cena")}

  <h2>Views por padrão de título</h2>
  {_chart_canvas("titlePatternChart", "360px")}
  {_render_weighted_table(title_pattern_weights, "Padrão")}

  <h2>Top 10 vídeos</h2>
  {_chart_canvas("topVideosChart", "320px")}
  {_render_top_videos(analytics)}

  <h2>Variações de thumbnail (A/B/C)</h2>
  {_chart_canvas("thumbnailVariantsChart", "240px")}
  {_render_thumbnail_variants(video_tags)}

  <h2>Recomendações para o próximo short</h2>
  {_render_recommendations(view_predictor, scene_weights, title_pattern_weights)}

  <h2>Previsão de views (próximos 7 dias)</h2>
  {_render_predicted_views(view_predictor)}

  <h2>Heatmap cena × horário</h2>
  {_render_scene_hour_heatmap(view_predictor)}

  <footer>Gerado em {generated_at}</footer>

  <script src="{_CHART_JS_CDN}"
          integrity="{_CHART_JS_SRI}"
          crossorigin="anonymous"
          onerror="this.onerror=null;this.src='{_CHART_JS_FALLBACK}'"></script>
  <script>
    // Dados embutidos (dashboard autocontido, sem backend).
    var HISTORY_DS = {history_json};
    var VIEWS_BY_DAY_DS = {views_by_day_json};
    var SCENE_DS = {scene_json};
    var TITLE_DS = {title_json};
    var TOP_DS = {top_json};
    var THUMB_DS = {thumb_json};
    var ACTIVE_CHANNEL = "Pata Jazz";

    // Paleta Pata Jazz.
    var ACCENT = "#f4a261";
    var ACCENT2 = "#2a9d8f";
    var GRID = "rgba(154, 154, 184, 0.15)";
    var TICK = "#9a9ab8";

    Chart.defaults.color = TICK;
    Chart.defaults.borderColor = GRID;
    Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

    function makeViewsChart() {{
      var ds = HISTORY_DS;
      var allLabels = ds.labels;
      var allTotal = ds.total_views;
      var allAvg = ds.avg_views;
      var ctx = document.getElementById("viewsChart").getContext("2d");

      function slices(n) {{
        if (n <= 0 || n >= allLabels.length) {{
          return [allLabels, allTotal, allAvg];
        }}
        var start = Math.max(0, allLabels.length - n);
        return [
          allLabels.slice(start),
          allTotal.slice(start),
          allAvg.slice(start),
        ];
      }}

      function render(n) {{
        var parts = slices(n);
        viewsChart.data.labels = parts[0];
        viewsChart.data.datasets[0].data = parts[1];
        viewsChart.data.datasets[1].data = parts[2];
        viewsChart.update();
      }}

      var initial = slices(parseInt(document.getElementById("period-filter").value, 10) || 0);
      var viewsChart = new Chart(ctx, {{
        type: "line",
        data: {{
          labels: initial[0],
          datasets: [
            {{
              label: "Views totais",
              data: initial[1],
              borderColor: ACCENT,
              backgroundColor: "rgba(244, 162, 97, 0.15)",
              fill: true, tension: 0.3, pointRadius: 3,
            }},
            {{
              label: "Média de views/vídeo",
              data: initial[2],
              borderColor: ACCENT2,
              backgroundColor: "rgba(42, 157, 143, 0.10)",
              fill: false, tension: 0.3, pointRadius: 2, borderDash: [4, 4],
            }},
          ],
        }},
        options: {{
          responsive: true, maintainAspectRatio: false,
          plugins: {{ legend: {{ labels: {{ color: TICK }} }} }},
          scales: {{
            x: {{ ticks: {{ color: TICK }}, grid: {{ color: GRID }} }},
            y: {{ ticks: {{ color: TICK }}, grid: {{ color: GRID }}, beginAtZero: true }},
          }},
        }},
      }});

      document.getElementById("period-filter").addEventListener("change", function (e) {{
        render(parseInt(e.target.value, 10) || 0);
      }});
    }}

    function makeSceneChart() {{
      var ds = SCENE_DS;
      if (!ds.labels.length) return;
      new Chart(document.getElementById("sceneChart").getContext("2d"), {{
        type: "bar",
        data: {{
          labels: ds.labels,
          datasets: [{{ label: "Peso de performance", data: ds.weights, backgroundColor: ACCENT, borderRadius: 4 }}],
        }},
        options: {{
          responsive: true, maintainAspectRatio: false,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{
            x: {{ ticks: {{ color: TICK }}, grid: {{ display: false }} }},
            y: {{ ticks: {{ color: TICK }}, grid: {{ color: GRID }}, beginAtZero: true }},
          }},
        }},
      }});
    }}

    function makeTitlePatternChart() {{
      var ds = TITLE_DS;
      if (!ds.labels.length) return;
      new Chart(document.getElementById("titlePatternChart").getContext("2d"), {{
        type: "bar",
        data: {{
          labels: ds.labels,
          datasets: [{{ label: "Peso de performance", data: ds.weights, backgroundColor: ACCENT2, borderRadius: 4 }}],
        }},
        options: {{
          indexAxis: "y", responsive: true, maintainAspectRatio: false,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{
            x: {{ ticks: {{ color: TICK }}, grid: {{ color: GRID }}, beginAtZero: true }},
            y: {{ ticks: {{ color: TICK, autoSkip: false }}, grid: {{ display: false }} }},
          }},
        }},
      }});
    }}

    function makeTopVideosChart() {{
      var ds = TOP_DS;
      if (!ds.labels.length) return;
      new Chart(document.getElementById("topVideosChart").getContext("2d"), {{
        type: "doughnut",
        data: {{
          labels: ds.labels,
          datasets: [{{
            data: ds.views,
            backgroundColor: [
              "#f4a261", "#e76f51", "#2a9d8f", "#e9c46a", "#264653",
              "#8ab17d", "#e63946", "#457b9d", "#a8dadc", "#f1faee",
            ],
            borderWidth: 0,
          }}],
        }},
        options: {{
          responsive: true, maintainAspectRatio: false,
          plugins: {{ legend: {{ position: "right", labels: {{ color: TICK, boxWidth: 12, font: {{ size: 11 }} }} }} }},
        }},
      }});
    }}

    function makeThumbnailVariantsChart() {{
      var ds = THUMB_DS;
      var total = ds.counts.reduce(function (a, b) {{ return a + b; }}, 0);
      if (!total) return;
      new Chart(document.getElementById("thumbnailVariantsChart").getContext("2d"), {{
        type: "doughnut",
        data: {{
          labels: ds.labels,
          datasets: [{{
            data: ds.counts,
            backgroundColor: ["#f4a261", "#2a9d8f", "#e76f51"],
            borderWidth: 0,
          }}],
        }},
        options: {{
          responsive: true, maintainAspectRatio: false,
          plugins: {{ legend: {{ position: "right", labels: {{ color: TICK, boxWidth: 12, font: {{ size: 11 }} }} }} }},
        }},
      }});
    }}

    function makeViewsByDayChart() {{
      var ds = VIEWS_BY_DAY_DS;
      if (!ds.labels.length) return;
      new Chart(document.getElementById("viewsByDayChart").getContext("2d"), {{
        type: "bar",
        data: {{
          labels: ds.labels,
          datasets: [{{ label: "Views", data: ds.views, backgroundColor: ACCENT, borderRadius: 4 }}],
        }},
        options: {{
          responsive: true, maintainAspectRatio: false,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{
            x: {{ ticks: {{ color: TICK, maxRotation: 45 }}, grid: {{ display: false }} }},
            y: {{ ticks: {{ color: TICK }}, grid: {{ color: GRID }}, beginAtZero: true }},
          }},
        }},
      }});
    }}

    if (window.Chart) {{
      makeViewsChart();
      makeViewsByDayChart();
      makeSceneChart();
      makeTitlePatternChart();
      makeTopVideosChart();
      makeThumbnailVariantsChart();
    }}

    // Item 17: endpoint client-side opcional que busca dados ao vivo do
    // GitHub Pages (analytics.json hospedado no mesmo site). Como o GitHub
    // Pages e estatico, os dados so atualizam quando o workflow
    // pata-jazz-analytics.yml roda (semanal) - por isso o botao e opcional
    // e os graficos ja vem populados com o snapshot da geracao.
    var REFRESH_INTERVAL_MS = 60000;
    var DATA_BASE = "./";
    var refreshBtn = document.getElementById("refresh-btn");
    var refreshStatus = document.getElementById("refresh-status");

    function setRefreshStatus(msg, isErr) {{
      if (!refreshStatus) return;
      refreshStatus.textContent = msg;
      refreshStatus.style.color = isErr ? "#e76f51" : "#9a9ab8";
    }}

    function fetchLiveAnalytics() {{
      if (!refreshBtn) return;
      refreshBtn.disabled = true;
      setRefreshStatus("Buscando dados...", false);
      var ts = Date.now();
      fetch(DATA_BASE + "analytics.json?t=" + ts, {{ cache: "no-store" }})
        .then(function (r) {{ return r.ok ? r.json() : null; }}).catch(function () {{ return null; }})
        .then(function (analytics) {{
        if (!analytics) {{
          setRefreshStatus("Dados ao vivo indisponiveis (ainda nao publicados no GitHub Pages).", true);
          refreshBtn.disabled = false;
          return;
        }}
        if (analytics.total_views !== undefined) {{
          var cards = document.querySelectorAll(".card-value");
          // Atualiza o card de "Views totais" se presente.
          for (var i = 0; i < cards.length; i++) {{
            var label = cards[i].nextElementSibling;
            if (label && label.textContent && label.textContent.indexOf("Views totais") !== -1) {{
              cards[i].textContent = String(analytics.total_views).replace(/(\d)(?=(\d{{3}})+$)/g, "$1.");
            }}
          }}
        }}
        setRefreshStatus("Dados ao vivo carregados em " + new Date().toLocaleTimeString() + ".", false);
        refreshBtn.disabled = false;
      }}).catch(function (err) {{
        setRefreshStatus("Erro ao buscar dados: " + err, true);
        refreshBtn.disabled = false;
      }});
    }}

    if (refreshBtn) {{
      refreshBtn.addEventListener("click", fetchLiveAnalytics);
    }}

    // Item 6.5: exportacao CSV do historico de views (HISTORY_DS).
    var csvBtn = document.getElementById("csv-btn");
    function downloadHistoryCsv() {{
      var ds = HISTORY_DS;
      var rows = ["Semana,Views totais,Média de views/vídeo"];
      for (var i = 0; i < ds.labels.length; i++) {{
        rows.push(ds.labels[i] + "," + ds.total_views[i] + "," + ds.avg_views[i]);
      }}
      var blob = new Blob([rows.join("\n")], {{ type: "text/csv;charset=utf-8;" }});
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "pata_jazz_analytics.csv";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }}
    if (csvBtn) {{
      csvBtn.addEventListener("click", downloadHistoryCsv);
    }}

    // Auto-refresh a cada 60s (opcional, silencioso se falhar).
    setInterval(fetchLiveAnalytics, REFRESH_INTERVAL_MS);
  </script>
</body>
</html>
"""


def main() -> int:
    # Usa ROOT dinamicamente para respeitar monkeypatches em testes.
    output_dir = ROOT / "_dashboard"
    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_chart_js_fallback(output_dir)
    output_path = output_dir / "index.html"
    output_path.write_text(build_dashboard_html(), encoding="utf-8")
    print(f"Dashboard gerado: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
