# Pata Jazz — Amber Hours

Canal automatizado de conteúdo exclusivo: **gatinhos e cachorrinhos fofos + jazz real**. O projeto gera Shorts verticais 9:16 e publica no YouTube usando assets licenciados e APIs públicas — **100% focado no YouTube**.

## Formato

- **Shorts** (`generate_pata_jazz_short.py`) — vertical 1080×1920, ~28-42s, **2-3 clipes com crossfade + 1 música de jazz + text overlay do hook nos primeiros 5s**.
- **Long-form Loop & Relax** (`scripts/generate_pata_jazz_long.py`) — horizontal 1920×1080, 15-30min, clipes em loop até cobrir a duração com crossfade lento 2.0s + jazz em loop — sessões longas para retenção e construção de hábito (2/semana).

## Plataforma

- **YouTube** (`upload_youtube.py`) — upload direto via YouTube Data API v3 (OAuth), com uma publicação diária programada.

## Recursos inteligentes

- **End-card CTA de sessão**: últimos ~2s de cada vídeo trazem uma call-to-action ASCII rotativa ("Keep the vibe going", "More calm here", etc.) com fade-in, incentivando a próxima sessão/short — engajamento encadeado em vez de vídeo morto
- **Anti-repeat de títulos**: os últimos 60 títulos usados são guardados em `_data/used_titles.json`; antes de publicar, o título é checado por similaridade (Jaccard, ignorando palavras vazias da marca) e re-sorteado até 3x se estiver repetindo (`utils/seo_keywords.py` + `utils/metadata_engine.py`)
- **Respostas automáticas a comentários**: `scripts/respond_comments.py` responde até 3 comentários por dia, no idioma do comentário, sem links e com rate-limits por usuário — presença humana sem parecer automação (`utils/comment_responder.py`)
- **Identidade estável do canal**: `scripts/update_channel_identity.py` compara a descrição e as keywords canônicas versionadas com o canal e só publica uma mudança mediante disparo manual explícito (`utils/channel_identity.py`)
- **Mood por horário**: Shorts selecionam cenas baseado na hora (manhã = diversão, tarde = fofura, noite = relax)
- **Publicação preditiva**: o horário de upload de cada short é escolhido por `utils/publish_optimizer.py`, cruzando dados reais (`_data/publish_slots.json`) com slots de alto CTR (fins de tarde/noite) e passado para o YouTube via `--publish-at`
- **Multi-clip com crossfade**: 2-3 clipes com transição suave em vez de 1 clipe repetido (validação automática garante que cada clipe é longo o suficiente para o xfade)
- **Text overlay**: Hook aparece como texto no vídeo nos primeiros 5 segundos (drawtext FFmpeg)
- **Legendas ASS estilizadas**: legendas animadas palavra-a-palavra com posicionamento/estilo via ASS (FFmpeg `ass=` filter) — o texto é parte do hook visual
- **Legenda PT-BR**: segunda caption track em português gerada via Gemini, sem regravar o vídeo
- **Chapters automáticos**: timestamps `00:00 Título` na descrição para SEO/navegação no YouTube
- **Música por mood**: faixas de jazz selecionadas por mood (diversão/fofura/relax) em vez de aleatório puro
- **AI hooks**: títulos/descrições/hashtags/legendas gerados via Gemini com circuit breaker (429/502/503) e fallback local — nunca quebra o pipeline por falha de IA
- **Thumbnail A/B/C**: três variantes de thumbnail geradas por vídeo (paleta/wrap diferentes) para testar CTR, com shadow RGBA real (gradiente via `Image.linear_gradient`), redimensionadas automaticamente para <2MB
- **Dashboard interativo**: `scripts/generate_dashboard.py` gera relatório HTML autocontido (sem deps novas) com analytics, performance por cena/padrão de título e projeção de views — publicado toda semana em **https://non-s.github.io/** via GitHub Pages
- **Analytics preditivo**: `scripts/predict_views.py` treina regressão linear (Python puro, sem numpy/scikit-learn) sobre os dados históricos e prevê views nos primeiros 7 dias após o upload por cena/padrão/horário — modelo salvo em `_data/view_predictor.json`, consumido pelo dashboard
- **Planejamento editorial auditável**: calendário de 30 dias, pesquisa aberta GBIF/Openverse, inteligência competitiva por metadados públicos e um conselho editorial assistido geram briefs para revisão — nenhum desses componentes tem autoridade para publicar
- **Estação visual ao vivo**: planejamento e readiness separados da transmissão; apenas assets com licença verificada entram no plano e o workflow de live é exclusivamente manual
- **Playlists automáticas**: Vídeos adicionados a playlists por mood/formato **e por animal** (gatos/cachorros), cache persistente em `_data/playlist_cache.json`
- **Analytics semanal com feedback loop real**: coleta views/likes/comentários e, via **YouTube Analytics API v2**, também `averageViewDuration`, `averageViewPercentage`, `ctr`, `impressions` e `subscribersGained`. Cruza tudo com a cena e o padrão de título que geraram cada vídeo (`_data/video_tags.json`, gravado no upload) e grava um peso por cena (`_data/scene_performance.json`) e por padrão de título (`_data/title_pattern_performance.json`) — `scene_for_mood()` e `pick_title_pattern()` passam a preferir o que performa melhor de verdade, sem nunca zerar as demais opções
- **Detecção de virais**: `scripts/collect_analytics.py` detecta vídeos acima de 8× a mediana de views e armazena `_data/viral_signals.json`; cenas de virais recentes recebem boost de escolha futuro, ponderado também por CTR/retenção
- **Rastreio de quota YouTube**: `utils/quota_tracker.py` loga unidades de quota gastas em `_data/quota_usage.json` (com lock e thread-safe), com alerta em 8000/dia (limite 10000); `retry_youtube_call` registra automaticamente o custo por endpoint após sucesso
- **Marca consistente**: Todos os títulos começam com o prefixo da marca do canal (`Pata Jazz |`)
- **Conteúdo em inglês**: título, descrição, hashtags e legendas são gerados em inglês (`utils/seo_keywords.py`, `utils/metadata_engine.py`, `utils/caption_engine.py`) - o formato pet+jazz não depende de idioma e o volume de busca em inglês é muito maior que o equivalente em português. O system prompt padrão do Gemini (`utils/ai_helper.py::_default_system_prompt`) também reforça isso - qualquer chamada de IA que precise de outro idioma tem que passar `system=` explicitamente.
- **Robustez de APIs**: Circuit breaker no Gemini (429/502/503), retry exponencial no YouTube, fallback local em todas as chamadas de IA
- **Thumbnails com shadow RGBA**: Gradiente via `Image.linear_gradient` (Pillow ≥9.1), shadows com alpha real

## APIs reais utilizadas

| Provedor | Uso |
|----------|-----|
| **Gemini** | Títulos, descrições, hashtags e legendas |
| **Jamendo** | Músicas com licença segura (jazz/lofi/classical) |
| **Pixabay** | Clips reais de gatos e cachorros |
| **YouTube Data API v3** | Upload de vídeos, playlists, captions e analytics |
| **YouTube Analytics API v2** | Retenção, CTR, impressions e inscritos ganhos por vídeo |

## Stack

- **Python 3.11+** (CI roda 3.11; local testado com 3.12/3.14)
- **FFmpeg** — codificação, concatenação, xfade, drawtext e ffprobe (com timeout)
- **Pillow ≥10.3** — thumbnails (gradiente, shadows RGBA, fontes TrueType)
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
│   ├── collect_competitive_intelligence.py # Benchmark apenas de metadados públicos
│   ├── collect_open_research.py          # Pesquisa GBIF/Openverse para revisão
│   ├── generate_editorial_calendar.py    # Calendário editorial sem publicação
│   ├── generate_dashboard.py             # Dashboard HTML a partir de _data/
│   ├── generate_pata_jazz_long.py        # Gerador do long-form Loop & Relax (10-45min)
│   ├── healthcheck.py                    # Verifica dependências e tokens
│   ├── predict_views.py                  # Analytics preditivo (regressão linear)
│   ├── plan_live_station.py              # Plano de live com validação de direitos
│   ├── run_agency_council.py             # Brief editorial diário, sem publicar
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
│   ├── channel_config.py                 # Configuração do canal Pata Jazz
│   ├── channel_identity.py               # Atualizador de identidade do canal (about/keywords semanais)
│   ├── agency_council.py                 # Conselho editorial e memória de decisões
│   ├── competitive_intelligence.py       # Inteligência por metadados públicos
│   ├── comment_responder.py              # Resposta automática a comentários (IA + fallback + lock)
│   ├── content_strategy.py               # Mood por horário + cena ponderada por performance
│   ├── ffmpeg_helpers.py                 # FFmpeg e ffprobe (com timeout)
│   ├── log_config.py                     # Logging centralizado
│   ├── media_pool.py                     # Pool de mídia local (anti-repeat)
│   ├── live_station.py                   # Plano auditável da estação visual
│   ├── metadata_engine.py                # Títulos/descrições/hashtags
│   ├── playlist_manager.py               # Playlists automáticas YouTube
│   ├── quota_tracker.py                  # Rastreio de quota YouTube (_data/quota_usage.json)
│   ├── seo_keywords.py                   # SEO + pick_title_pattern ponderado por performance
│   ├── state_lock.py                     # filelock para estado JSON compartilhado
│   ├── thumbnail_engine.py               # Geração de thumbnails A/B/C (<2MB, shadow RGBA)
│   ├── video_builder.py                  # Pipeline de geração (multi-clip + overlay + ASS)
│   ├── video_validator.py                # Validação técnica dos vídeos
│   ├── youtube_oauth.py                  # OAuth YouTube
│   └── youtube_retry.py                  # Retry exponencial + registro automático de quota
├── generate_pata_jazz_short.py           # Gerador do Short
├── upload_youtube.py                     # Upload de vídeo no YouTube (insert + caption + playlist)
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
- `YOUTUBE_TOKEN` — JSON do token OAuth do YouTube (Pata Jazz)
- `GH_PAT` — fine-grained PAT limitado a este repositório para renovar `YOUTUBE_TOKEN` e abrir issue de alerta.
- `OPENVERSE_ACCESS_TOKEN` — opcional, para ampliar a pesquisa de mídia aberta.

### Variables

- `PATA_JAZZ_ENABLED` — `1` para ligar todos os workflows do Pata Jazz.
- `PATA_JAZZ_SHORTS_ENABLED` — `1` para Shorts do Pata Jazz.
- `PATA_JAZZ_COMMENTS_ENABLED` — `1` para respostas automáticas a comentários do Pata Jazz.
- `PATA_JAZZ_LONG_ENABLED` — `1` para os long-forms Loop & Relax do Pata Jazz.
- `PATA_JAZZ_IDENTITY_ENABLED` — `1` para o atualizador semanal de identidade do Pata Jazz.
- `YOUTUBE_PRIVACY` — `public`, `unlisted` ou `private`.

## Grade de publicação (GitHub Actions)

| Canal | Conteúdo | Frequência | Horário | Workflow |
|---|---|---|---|---|
| **Pata Jazz** | Shorts (YouTube) | 1 por dia | 18:07 UTC | `pata-jazz-shorts.yml` |
| **Pata Jazz** | Comentários (canal vivo) | 1x por dia, até 3 respostas | 19:37 UTC | `pata-jazz-engagement.yml` |
| **Pata Jazz** | Sync de assets | 2x por semana | Ter e Sex 03:00 | `pata-jazz-sync.yml` |
| **Pata Jazz** | Analytics | 1x por semana | Segunda 03:00 | `pata-jazz-analytics.yml` |
| **Pata Jazz** | Snapshot analytics | 1x por dia | 03:25 | `pata-jazz-analytics-daily.yml` |
| **Pata Jazz** | Long-form Loop & Relax | 2x por semana | Domingo e terça 01:13 | `pata-jazz-long.yml` |
| **Pata Jazz** | Identidade do canal | Sob demanda, com aplicação explícita | manual | `pata-jazz-identity.yml` |
| **Pata Jazz** | Batch manual otimizado | Sob demanda | workflow_dispatch | `pata-jazz-batch.yml` |
| **Pata Jazz** | Lote manual de preparação | Gera até 6 rascunhos privados para revisão | só disparo manual (`action: all`/`generate`/`publish`) | `pata-jazz-weekly.yml` |

**Cadência base:** 1 Short/dia, ou **7 vídeos/semana**. A cadência só deve aumentar depois que os dados de retenção e velocidade de visualização sustentarem a decisão. O lote semanal (`pata-jazz-weekly.yml`) permanece manual e não deve competir com o cron diário.

> **Nota sobre quota:** o projeto registra o consumo em `_data/quota_usage.json` e alerta em 8.000 unidades/dia. A cadência diária deixa margem para uploads, thumbnails, legendas, playlists e ações manuais. Antes de executar um lote manual, confira o arquivo de quota e a agenda de publicações já pendentes.

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
python upload_youtube.py --mode upload --language=en
```

> Todo o estado do canal é mantido em `_data/` na raiz do projeto.

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
| Thumbnail > 2MB | Imagem muito grande | Já tratado por `_save_under_2mb()` (redimensiona se necessário) |
| `Nenhuma fonte TrueType encontrada` | Fontes não instaladas | O projeto empacota `Roboto-Bold.ttf` em `_assets/fonts/` e usa paths absolutos/escapados para FFmpeg — não depende mais de fontconfig |
| Gemini retorna vazio | Circuit breaker aberto ou modelo inválido | Verifique `GEMINI_MODEL` (default: `gemini-2.0-flash-001`) |
| `Circuit breaker do Gemini aberto` | Muitas respostas 429/503 | Aguarde 120s (reset automático) ou verifique quota |

## Licença

Conteúdo gerado para o canal Amber Hours. Músicas e vídeos respeitam as licenças dos provedores (Jamendo CC/Pixabay).
