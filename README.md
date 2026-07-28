# Pata Jazz — Amber Hours

Canal automatizado de conteúdo exclusivo: **gatinhos e cachorrinhos fofos + jazz real**. O projeto gera Shorts verticais 9:16 e publica no YouTube e no TikTok usando assets licenciados e APIs públicas — 100% focado em conteúdo curto.

## Formato

- **Shorts** (`generate_pata_jazz_short.py`) — vertical 1080×1920, ~35s, **2-3 clipes com crossfade + 1 música de jazz + text overlay do hook nos primeiros 3s**.

## Plataformas

- **YouTube** (`upload_youtube.py`) — upload direto via YouTube Data API v3 (OAuth), 4x/dia.
- **TikTok** (`upload_tiktok.py`) — cross-posting via Playwright (browser automation, sem API oficial), disparado logo após cada upload do YouTube (`cross-post.yml`).
- **Instagram Reels** (`upload_reels.py`) — cross-posting best-effort junto com o TikTok.

## Recursos inteligentes

- **Mood por horário**: Shorts selecionam cenas baseado na hora (manhã = diversão, tarde = fofura, noite = relax)
- **Multi-clip com crossfade**: 2-3 clipes com transição suave em vez de 1 clipe repetido (validação automática garante que cada clipe é longo o suficiente para o xfade)
- **Text overlay**: Hook aparece como texto no vídeo nos primeiros 3 segundos (drawtext FFmpeg)
- **Legendas ASS estilizadas**: legendas animadas palavra-a-palavra com posicionamento/estilo via ASS (FFmpeg `ass=` filter) — o texto é parte do hook visual
- **Legenda PT-BR**: segunda caption track em português gerada via Gemini, sem regravar o vídeo
- **Chapters automáticos**: timestamps `00:00 Título` na descrição para SEO/navegação no YouTube
- **Multi-canal**: `utils/channel_config.py` abstrai marca/tags/playlists/prompts por canal — hoje só `Pata Jazz`, mas novos canais (`Pata Lofi`, `Pata Classical`...) podem ser registrados em `CHANNELS` sem duplicar o repo nem mudar os módulos consumidores
- **Música por mood**: faixas de jazz selecionadas por mood (diversão/fofura/relax) em vez de aleatório puro
- **AI hooks**: títulos/descrições/hashtags/legendas gerados via Gemini com circuit breaker (429/502/503) e fallback local — nunca quebra o pipeline por falha de IA
- **Thumbnail A/B/C**: três variantes de thumbnail geradas por vídeo (paleta/wrap diferentes) para testar CTR, com shadow RGBA real (gradiente via `Image.linear_gradient`), redimensionadas automaticamente para <2MB
- **Dashboard interativo**: `scripts/generate_dashboard.py` gera relatório HTML autocontido (sem deps novas) com analytics, performance por cena/padrão de título e projeção de views — publicado toda semana em **https://non-s.github.io/** via GitHub Pages
- **Analytics preditivo**: `scripts/predict_views.py` treina regressão linear (Python puro, sem numpy/scikit-learn) sobre os dados históricos e prevê views nos primeiros 7 dias após o upload por cena/padrão/horário — modelo salvo em `_data/view_predictor.json`, consumido pelo dashboard
- **Playlists automáticas**: Videos adicionados a playlists por mood/formato (cache persistente em `_data/playlist_cache.json`)
- **Analytics semanal com feedback loop real**: coleta views/likes/comentários, cruza com a cena e o padrão de título que geraram cada vídeo (`_data/video_tags.json`, gravado no upload) e grava um peso por cena (`_data/scene_performance.json`) e por padrão de título (`_data/title_pattern_performance.json`) — `scene_for_mood()` e `pick_title_pattern()` passam a preferir o que performa melhor de verdade, sem nunca zerar as demais opções
- **Rastreio de quota YouTube**: `utils/quota_tracker.py` loga unidades de quota gastas em `_data/quota_usage.json` (com lock e thread-safe), com alerta em 8000/dia (limite 10000); `retry_youtube_call` registra automaticamente o custo por endpoint após sucesso
- **Marca consistente**: Todos os títulos começam com "Pata Jazz |"
- **Conteúdo em inglês**: título, descrição, hashtags e legendas são gerados em inglês (`utils/seo_keywords.py`, `utils/metadata_engine.py`, `utils/caption_engine.py`) - o formato pet+jazz não depende de idioma e o volume de busca em inglês é muito maior que o equivalente em português. O system prompt padrão do Gemini (`utils/ai_helper.py::_default_system_prompt`) também reforça isso - qualquer chamada de IA que precise de outro idioma tem que passar `system=` explicitamente.
- **Robustez de APIs**: Circuit breaker no Gemini (429/502/503), retry exponencial no YouTube, fallback local em todas as chamadas de IA
- **Thumbnails com shadow RGBA**: Gradiente via `Image.linear_gradient` (Pillow ≥9.1), shadows com alpha real

## APIs reais utilizadas

| Provedor | Uso |
|----------|-----|
| **Gemini** | Títulos, descrições, hashtags e legendas |
| **Jamendo** | Músicas jazz com licença segura |
| **Pixabay** | Clips reais de gatos e cachorros |
| **YouTube Data API v3** | Upload de vídeos, playlists, captions e analytics |
| **TikTok** (via Playwright) | Cross-posting de Shorts sem API oficial |

## Stack

- **Python 3.11+** (CI roda 3.11; local testado com 3.12/3.14)
- **FFmpeg** — codificação, concatenação, xfade, drawtext e ffprobe (com timeout)
- **Pillow ≥10.3** — thumbnails (gradiente, shadows RGBA, fontes TrueType)
- **Playwright** — upload no TikTok via browser automation
- **pytest** — testes unitários (cobertura ≥85% de `utils/`+`scripts/`)
- **ruff** — lint (regras E, F, W, I, UP, B)
- **GitHub Actions** — CI/CD e agendamento

## Estrutura

```
.
├── .github/
│   ├── actions/restore-token-and-cache/  # Composite action: token + caches _data/
│   ├── workflows/                        # Workflows GitHub Actions
│   └── dependabot.yml                    # Updates agrupados (pip + github-actions)
├── _assets/
│   ├── audio/animal_jazz/                # Faixas jazz (Jamendo)
│   ├── video/animal_broll/               # B-roll de gatos/cachorros (Pixabay)
│   └── thumbnails/                       # Thumbnails geradas
├── _data/                                # Estado local (analytics, quota, etc.)
├── _videos/                              # Vídeos gerados e logs de erro
├── docs/
│   ├── ARCHITECTURE.md                   # Fluxo de dados, design, componentes
│   └── CONTRIBUTING.md                   # Setup, testes, convenções, novos canais/workflows
├── scripts/
│   ├── batch_generate.py                 # Geração em lote de shorts
│   ├── cleanup_youtube.py                # Remove vídeos legados (horizontal/live) do canal
│   ├── collect_analytics.py              # Coleta de métricas YouTube + feedback loop
│   ├── generate_dashboard.py             # Dashboard HTML a partir de _data/
│   ├── healthcheck.py                    # Verifica dependências e tokens
│   ├── predict_views.py                  # Analytics preditivo (regressão linear)
│   ├── publish_weekly_batch.py           # Publica próximos N do lote semanal
│   ├── sync_animal_broll.py              # Sync Pixabay (gatos/cachorros)
│   └── sync_jazz_music.py                # Sync Jamendo (jazz)
├── tests/                                # Testes pytest
├── utils/
│   ├── ai_helper.py                      # Chamadas Gemini (circuit breaker + fallback)
│   ├── animal_branding.py                # Identidade Pata Jazz
│   ├── caption_engine.py                 # Legendas ASS animadas + PT-BR + chapters
│   ├── channel_config.py                 # Abstração multi-canal (ChannelConfig + CHANNELS)
│   ├── content_strategy.py               # Mood por horário + cena ponderada por performance
│   ├── ffmpeg_helpers.py                 # FFmpeg e ffprobe (com timeout)
│   ├── log_config.py                     # Logging centralizado
│   ├── media_pool.py                     # Pool de mídia local (anti-repeat)
│   ├── metadata_engine.py                # Títulos/descrições/hashtags
│   ├── playlist_manager.py               # Playlists automáticas YouTube
│   ├── quota_tracker.py                  # Rastreio de quota YouTube (_data/quota_usage.json)
│   ├── seo_keywords.py                   # SEO + pick_title_pattern ponderado por performance
│   ├── state_lock.py                     # filelock para estado JSON compartilhado
│   ├── thumbnail_engine.py               # Geração de thumbnails A/B/C (<2MB, shadow RGBA)
│   ├── tiktok_uploader.py                # Upload no TikTok via Playwright
│   ├── video_builder.py                  # Pipeline de geração (multi-clip + overlay + ASS)
│   ├── video_validator.py                # Validação técnica dos vídeos
│   ├── youtube_oauth.py                  # OAuth YouTube
│   └── youtube_retry.py                  # Retry exponencial + registro automático de quota
├── generate_pata_jazz_short.py           # Gerador do Short
├── upload_youtube.py                     # Upload de vídeo no YouTube (insert + caption + playlist)
├── upload_tiktok.py                      # Cross-posting no TikTok (Playwright)
├── upload_reels.py                       # Cross-posting no Instagram Reels
├── Makefile                              # Atalhos: test, test-cov, lint, format, typecheck, security, sync, clean, all
├── .pre-commit-config.yaml               # ruff + mypy + higiene (check-yaml, EOF, trailing-whitespace)
├── pyproject.toml                        # ruff/pytest/coverage/mypy config
├── requirements.txt                      # Deps runtime
├── requirements-dev.txt                  # Deps dev (ruff, pytest, mypy, bandit, pip-audit)
└── requirements.lock                     # Lockfile (pip-compile)
```

> **Documentação detalhada:** veja [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
> (fluxo de dados, decisões de design, componentes, workflows, estado
> persistente) e [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) (setup, testes,
> convenções de commit, como adicionar canal/workflow novos).

## Configuração

### 1. Dependências locais

```bash
pip install -r requirements-dev.txt  # inclui ruff, pytest, pytest-cov
playwright install chromium          # browser usado pelo upload no TikTok
```

Instale também o FFmpeg e certifique-se de que `ffmpeg` e `ffprobe` estão no PATH.

### 2. Variáveis de ambiente

Crie um arquivo `.env` (ou exporte manualmente) com as chaves abaixo:

```bash
GEMINI_API_KEY=xxx
PIXABAY_API_KEY=xxx
JAMENDO_CLIENT_ID=xxx  # opcional (recomendado)
GEMINI_MODEL=gemini-2.0-flash-001  # opcional (default)
YOUTUBE_PRIVACY=public
TIKTOK_EMAIL=xxx     # opcional (cross-posting no TikTok)
TIKTOK_PASSWORD=xxx  # opcional (cross-posting no TikTok)
```

### 3. Credenciais do YouTube

Para upload, é necessário um token OAuth do YouTube. Execute uma vez:

```bash
python utils/youtube_oauth.py
```

Salve o JSON resultante como `youtube_token.json` na raiz do projeto (ou use o secret `YOUTUBE_TOKEN` no GitHub Actions).

## Variáveis do GitHub Actions

### Secrets

- `GEMINI_API_KEY`
- `PIXABAY_API_KEY`
- `JAMENDO_CLIENT_ID`
- `YOUTUBE_TOKEN` — JSON do token OAuth do YouTube
- `TIKTOK_EMAIL` / `TIKTOK_PASSWORD` — login usado pelo cross-posting no TikTok

### Variables

- `PATA_JAZZ_ENABLED` — `1` para ligar todos os workflows.
- `PATA_JAZZ_SHORTS_ENABLED` — `1` para Shorts.
- `YOUTUBE_PRIVACY` — `public`, `unlisted` ou `private`.

## Grade de publicação (GitHub Actions)

| Conteúdo | Frequência | Horário BRT | Workflow |
|---|---|---|---|
| **Shorts (YouTube)** | 4 por dia | 07:00, 13:00, 18:00, 22:00 | `pata-jazz-shorts.yml` |
| **Cross-post (TikTok/Reels)** | Após cada Short publicado | — | `cross-post.yml` |
| **Sync de assets** | 2x por semana | Ter e Sex 03:00 | `pata-jazz-sync.yml` |
| **Analytics** | 1x por semana | Segunda 03:00 | `pata-jazz-analytics.yml` |
| **Lote semanal** (manual/eventual) | Gera 35 shorts de uma vez, publica 6/dia até esgotar | só disparo manual (`action: all`/`generate`/`publish`) | `pata-jazz-weekly.yml` |

**Total semanal (crons diários):** 4 Shorts/dia × 7 = **28 vídeos/semana** no YouTube, cada um cross-postado para TikTok e Reels. O lote semanal (`pata-jazz-weekly.yml`) é um mecanismo separado e não roda por padrão — só produz vídeos extras quando disparado manualmente com `action: all`/`generate`/`publish`.

> **Nota sobre quota (histórico):** o lote semanal já teve um cron diário próprio de "publicar próximos 6" rodando em paralelo ao cron de Shorts - isso empilhava uploads/dia, passando da quota de ~10.000 unidades/dia da API (cada upload custa ~1.600 unidades) e causando falhas em produção (24-25/07). O cron foi removido; hoje só o cron de Shorts (4/dia) publica automaticamente. Se for rodar `pata-jazz-weekly.yml` manualmente, ainda vale conferir a soma de uploads do dia antes de disparar.

## Execução local

### Verificar saúde do ambiente

```bash
python scripts/healthcheck.py
```

### Baixar assets

```bash
python scripts/sync_animal_broll.py
python scripts/sync_jazz_music.py
```

### Gerar um Short

```bash
python generate_pata_jazz_short.py
```

Use `--dry-run` para simular sem executar FFmpeg nem gerar arquivos:

```bash
python generate_pata_jazz_short.py --dry-run
```

### Fazer upload

O upload usa o vídeo mais recente gerado (metadados em `_videos/*.json`):

```bash
python upload_youtube.py --mode upload --language=en --prefix pata_jazz_short_
python upload_tiktok.py --all --prefix pata_jazz_short_
```

### Coletar analytics

```bash
python scripts/collect_analytics.py
```

### Gerar o dashboard HTML

```bash
python scripts/generate_dashboard.py  # gera _dashboard/index.html a partir do que já está em _data/
```

## Testes

```bash
pytest -q --cov=utils --cov-report=term-missing
python -m compileall -q .
```

## Desenvolvimento

> Guia completo de setup, testes, convenções de commit e como adicionar
> canais/workflows novos: [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

### Pre-commit hooks

Rode uma vez após clonar o repositório para instalar os hooks de lint/format/typecheck que rodam a cada commit:

```bash
pip install pre-commit
pre-commit install
```

A partir disso, `ruff check --fix`, `ruff format`, `mypy` e checagens de
higiene (YAML, merge conflict, trailing whitespace, EOF) rodam automaticamente
antes de cada commit.

### Makefile

Atalhos para as tarefas comuns de desenvolvimento:

```bash
make test         # pytest -q
make test-cov     # pytest -q --cov --cov-report=term-missing
make lint         # ruff check .
make format       # ruff format . && ruff check --fix .
make typecheck    # mypy
make security     # bandit -ll + pip-audit
make healthcheck  # python scripts/healthcheck.py
make sync         # sync b-roll + jazz
make clean        # remove caches e artefatos
make all          # lint test typecheck
```

## Troubleshooting

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| `Pool de b-roll vazio` | Nenhum vídeo baixado ainda | Rode `scripts/sync_animal_broll.py` |
| `Pool de jazz vazio` | Nenhuma música baixada ainda | Rode `scripts/sync_jazz_music.py` |
| `Validation failed: resolução` | FFmpeg gerou arquivo fora do formato | Verifique logs em `_videos/last_error.txt` (histórico com timestamp) |
| Upload retorna 401 | Token OAuth expirado | Renove em `utils/youtube_oauth.py` |
| TikTok pede login novamente | `tiktok_state.json` expirado/ausente | Rode `upload_tiktok.py` localmente uma vez com `TIKTOK_HEADLESS=0` para recriar a sessão |
| Thumbnail > 2MB | Imagem muito grande | Já tratado por `_save_under_2mb()` (redimensiona se necessário) |
| `Nenhuma fonte TrueType encontrada` | Fontes não instaladas | Instale DejaVu/arial ou defina `PIL_IMAGE_FONT_PATH` |
| Gemini retorna vazio | Circuit breaker aberto ou modelo inválido | Verifique `GEMINI_MODEL` (default: `gemini-2.0-flash-001`) |
| `Circuit breaker do Gemini aberto` | Muitas respostas 429/503 | Aguarde 120s (reset automático) ou verifique quota |

## Licença

Conteúdo gerado para o canal Amber Hours. Músicas e vídeos respeitam as licenças dos provedores (Jamendo CC/Pixabay).
