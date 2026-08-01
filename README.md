# Pata Jazz — Amber Hours

Canal automatizado de conteúdo exclusivo: **gatinhos e cachorrinhos fofos + jazz real**. O projeto gera Shorts verticais 9:16 e publica no YouTube e no TikTok usando assets licenciados e APIs públicas — 100% focado em conteúdo curto.

## Formato

- **Shorts** (`generate_pata_jazz_short.py`) — vertical 1080×1920, ~35s, **2-3 clipes com crossfade + 1 música de jazz + text overlay do hook nos primeiros 3s**.
- **Long-form Loop & Relax** (`scripts/generate_pata_jazz_long.py`) — horizontal 1920×1080, 10-45min, clipes em loop até cobrir a duração com crossfade lento 2.0s + jazz em loop — watch time longo que compensa a alta frequência de Shorts (1/semana).

## Plataformas

- **YouTube** (`upload_youtube.py`) — upload direto via YouTube Data API v3 (OAuth), 1 short/hora (24/dia).
- **TikTok** (`upload_tiktok.py`) — cross-posting via Playwright (browser automation, sem API oficial), disparado logo após cada upload do YouTube (`cross-post.yml`).
- **Instagram Reels** (`upload_reels.py`) — cross-posting best-effort junto com o TikTok.

## Recursos inteligentes

- **End-card CTA de sessão**: últimos ~2s de cada vídeo trazem uma call-to-action ASCII rotativa ("Keep the vibe going", "More calm here", etc.) com fade-in, incentivando a próxima sessão/short — engajamento encadeado em vez de vídeo morto
- **Anti-repeat de títulos**: os últimos 60 títulos usados são guardados em `_data/used_titles.json`; antes de publicar, o título é checado por similaridade (Jaccard, ignorando palavras vazias da marca) e re-sorteado até 3x se estiver repetindo (`utils/seo_keywords.py` + `utils/metadata_engine.py`)
- **Respostas automáticas a comentários**: `scripts/respond_comments.py` responde comentários do canal com IA (mesmo system prompt "pessoa real"), no idioma do comentário, sem links e com rate-limits por usuário/run — canal que responde gera mais engajamento real (`utils/comment_responder.py`, a cada hora)
- **Identidade do canal viva**: `scripts/update_channel_identity.py` rotaciona o about (descrição) e as keywords do canal por semana ISO com IA + fallback local e trava de 1x/semana — a página do canal respira e não parece feed de bot (`utils/channel_identity.py`, semanal)
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
│   ├── generate_pata_jazz_long.py        # Gerador do long-form Loop & Relax (10-45min)
│   ├── healthcheck.py                    # Verifica dependências e tokens
│   ├── predict_views.py                  # Analytics preditivo (regressão linear)
│   ├── publish_weekly_batch.py           # Publica próximos N do lote semanal
│   ├── respond_comments.py               # Respostas automáticas a comentários (canal vivo)
│   ├── sync_animal_broll.py              # Sync Pixabay (gatos/cachorros)
│   ├── sync_jazz_music.py                # Sync Jamendo (jazz)
│   └── update_channel_identity.py        # Atualizador de identidade do canal (about/keywords)
├── tests/                                # Testes pytest
├── utils/
│   ├── ai_helper.py                      # Chamadas Gemini (circuit breaker + fallback)
│   ├── animal_branding.py                # Identidade Pata Jazz
│   ├── caption_engine.py                 # Legendas ASS animadas + PT-BR + chapters
│   ├── channel_config.py                 # Abstração multi-canal (ChannelConfig + CHANNELS)
│   ├── channel_identity.py               # Atualizador de identidade do canal (about/keywords semanais)
│   ├── comment_responder.py              # Resposta automática a comentários (IA + fallback + lock)
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
TIKTOK_EMAIL=xxx     # opcional - so funciona pra contas que logam com senha
TIKTOK_PASSWORD=xxx  # opcional - idem; ver secao 4 pra contas QR code/Google
```

### 3. Credenciais do YouTube

Para upload, é necessário um token OAuth do YouTube. Execute uma vez:

```bash
python utils/youtube_oauth.py
```

Salve o JSON resultante como `youtube_token.json` na raiz do projeto (ou use o secret `YOUTUBE_TOKEN` no GitHub Actions).

### 4. Sessão do TikTok (contas que logam via QR code/Google)

Contas que só logam com QR code (celular) ou "Continuar com o Google" não
têm senha pra automatizar - `TIKTOK_EMAIL`/`TIKTOK_PASSWORD` não servem
nesse caso. A automação então reusa uma sessão (cookies) gerada por você
manualmente:

```bash
python scripts/tiktok_login_qr.py
```

Isso abre um Chromium visível na página de login do TikTok. Faça login do
jeito que você já usa; o script detecta a sessão ativa, salva
`tiktok_state.json` na raiz do projeto e imprime o conteúdo pra você colar
no secret `TIKTOK_STATE_JSON` do GitHub. O workflow `cross-post.yml`
escreve esse secret em `tiktok_state.json` antes de cada execução e reusa
a sessão até ela expirar - quando expirar, rode o script de novo e
atualize o secret.

Se você usa `--use-chrome-profile` (login com o SEU Chrome de verdade) e
escolhe "Continuar com o Google" como método, o próprio Google **bloqueia
o login** ("Esse navegador ou app pode não ser seguro") - ele detecta que
o navegador está sob automação (é assim que o Playwright funciona, não
tem como esconder) e recusa OAuth de qualquer ferramenta de automação,
não tem contorno confiável. Nesse caso, use o caminho alternativo que não
automatiza login nenhum - captura os cookies de uma sessão já logada no
seu Chrome normal:

```bash
python scripts/tiktok_cookies_to_state.py tiktok_cookies_export.json
```

Exporte os cookies com a extensão [Cookie-Editor](https://cookie-editor.com/)
(Chrome Web Store) estando logado em tiktok.com no seu Chrome normal
("Export" → "Export as JSON"), cole o conteúdo copiado num arquivo, e
rode o comando acima. Gera o mesmo `tiktok_state.json` de sempre.

## Variáveis do GitHub Actions

### Secrets

- `GEMINI_API_KEY`
- `PIXABAY_API_KEY`
- `JAMENDO_CLIENT_ID`
- `YOUTUBE_TOKEN` — JSON do token OAuth do YouTube
- `TIKTOK_STATE_JSON` — sessão (storage_state) do TikTok; gere com `python scripts/tiktok_login_qr.py` (necessário para contas que logam via QR code/Google, sem senha)
- `TIKTOK_EMAIL` / `TIKTOK_PASSWORD` — opcional, só usado como fallback quando a sessão acima expira e a conta tem senha

### Variables

- `PATA_JAZZ_ENABLED` — `1` para ligar todos os workflows.
- `PATA_JAZZ_SHORTS_ENABLED` — `1` para Shorts.
- `PATA_JAZZ_COMMENTS_ENABLED` — `1` para respostas automáticas a comentários.
- `PATA_JAZZ_LONG_ENABLED` — `1` para o long-form Loop & Relax semanal.
- `PATA_JAZZ_IDENTITY_ENABLED` — `1` para o atualizador semanal de identidade do canal.
- `YOUTUBE_PRIVACY` — `public`, `unlisted` ou `private`.

## Grade de publicação (GitHub Actions)

| Conteúdo | Frequência | Horário | Workflow |
|---|---|---|---|
| **Shorts (YouTube)** | 1 por hora (24/dia) | minuto 7 de cada hora UTC | `pata-jazz-shorts.yml` |
| **Cross-post (TikTok/Reels)** | Após cada Short publicado (1/hora, 24/dia) | — | `cross-post.yml` |
| **Comentários (canal vivo)** | 1x por hora | minuto 37 de cada hora UTC | `pata-jazz-engagement.yml` |
| **Sync de assets** | 2x por semana | Ter e Sex 03:00 | `pata-jazz-sync.yml` |
| **Analytics** | 1x por semana | Segunda 03:00 | `pata-jazz-analytics.yml` |
| **Long-form Loop & Relax** | 1x por semana | Domingo 01:13 | `pata-jazz-long.yml` |
| **Identidade do canal** | 1x por semana | Segunda 02:23 | `pata-jazz-identity.yml` |
| **Lote semanal** (manual/eventual) | Gera 35 shorts de uma vez, publica 6/dia até esgotar | só disparo manual (`action: all`/`generate`/`publish`) | `pata-jazz-weekly.yml` |

**Total (crons horários):** 24 Shorts/dia × 7 = **168 vídeos/semana** no YouTube, cada um cross-postado para TikTok (e Reels, quando configurado). O lote semanal (`pata-jazz-weekly.yml`) é um mecanismo separado e não roda por padrão — só produz vídeos extras quando disparado manualmente com `action: all`/`generate`/`publish`.

> **Nota sobre quota:** `videos.insert` tem cota própria de ~100/dia (24 uploads/dia fica bem abaixo). Os outros endpoints usados por upload (thumbnail, captions, playlists) somam ~200 unidades/upload do pool compartilhado de 10.000/dia — 24 uploads/dia usa ~4.800, abaixo do alerta em 8.000 (`utils/quota_tracker.py`). O lote semanal já teve um cron diário próprio de "publicar próximos 6" rodando em paralelo ao cron de Shorts, o que estourava a quota e causava falhas em produção (24-25/07) - esse cron foi removido, hoje só o cron horário de Shorts publica automaticamente. Se for rodar `pata-jazz-weekly.yml` manualmente, ainda vale conferir `_data/quota_usage.json` antes de disparar, já que o cron horário já usa boa parte da margem diária.

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
