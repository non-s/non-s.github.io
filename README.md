# Pata Jazz — Amber Hours

Canal automatizado de conteúdo exclusivo: **gatinhos e cachorrinhos fofos + jazz real**. O projeto gera Shorts, vídeos horizontais e transmissões ao vivo para o YouTube usando assets licenciados e APIs públicas.

## Formatos

- **Shorts** (`generate_pata_jazz_short.py`) — vertical 1080×1920, ~35s, **2-3 clipes com crossfade + 1 música de jazz + text overlay do hook nos primeiros 3s**.
- **Vídeos horizontais** (`generate_pata_jazz_horizontal.py`) — 1920×1080, ~5min (300s, passado explicitamente pelo workflow; o default do script é 240s/4min quando rodado sem `--duration`), **1 clipe + 1 música de jazz**.
- **Live 24/7** (`generate_pata_jazz_live.py` + `scripts/run_live.py`) — transmissão horizontal 720p contínua com **vários clipes de gatos/cachorros** e **playlist de até 150 faixas de jazz** em loop infinito. Cada sessão do GitHub Actions dura ~350min (limite de job); ao final de uma sessão normal (duração atingida ou SIGTERM do GHA) o broadcast **não é finalizado** - fica "live" sem receber vídeo até a próxima sessão do cron reconectar no mesmo broadcast/stream (`upload_youtube._try_resume_existing_broadcast`), em vez de criar um link novo a cada ~6h. Só finaliza de fato quando o stream nunca ficou ativo ou as reconexões se esgotam (broadcast provavelmente morto do lado do YouTube). Reconecta sozinha (até 200x) se o FFmpeg cair no meio da sessão.

## Recursos inteligentes

- **Mood por horário**: Shorts e horizontais selecionam cenas baseado na hora (manhã = diversão, tarde = fofura, noite = relax)
- **Multi-clip com crossfade**: Shorts usam 2-3 clipes com transição suave em vez de 1 clipe repetido (validação automática garante que cada clipe é longo o suficiente para o xfade)
- **Text overlay**: Hook aparece como texto no vídeo nos primeiros 3 segundos (drawtext FFmpeg)
- **Legendas automáticas**: SRT gerado via Gemini e enviado como caption track (mimetype correto por extensão)
- **Playlists automáticas**: Videos adicionados a playlists por mood/formato (cache persistente em `_data/playlist_cache.json`)
- **Analytics semanal com feedback loop real**: coleta views/likes/comentários, cruza com a cena que gerou cada vídeo (`_data/video_tags.json`, gravado no upload) e grava um peso por cena em `_data/scene_performance.json` — `scene_for_mood()` passa a preferir cenas com melhor performance real, sem nunca zerar as demais
- **Contagem de espectadores da live**: uma amostra de `concurrentViewers` por segmento de FFmpeg, salva em `_data/live_viewer_history.json`
- **Marca consistente**: Todos os títulos começam com "Pata Jazz |"
- **Conteúdo em inglês**: título, descrição, hashtags e legendas são gerados em inglês (`utils/seo_keywords.py`, `utils/metadata_engine.py`, `utils/caption_engine.py`) - o formato pet+jazz não depende de idioma e o volume de busca em inglês é muito maior que o equivalente em português. O system prompt padrão do Gemini (`utils/ai_helper.py::_default_system_prompt`) também reforça isso - qualquer chamada de IA que precise de outro idioma tem que passar `system=` explicitamente.
- **Robustez de APIs**: Circuit breaker no Gemini (429/502/503), retry exponencial no YouTube, fallback local em todas as chamadas de IA
- **Thumbnails com shadow RGBA**: Gradiente via `Image.linear_gradient` (Pillow ≥9.1), shadows com alpha real
- **Live sem deadlock**: stderr do FFmpeg redirecionado para arquivo (evita congelamento em lives longas)

## APIs reais utilizadas

| Provedor | Uso |
|----------|-----|
| **Gemini** | Títulos, descrições, hashtags e legendas SRT |
| **Jamendo** | Músicas jazz com licença segura |
| **Pixabay** | Clips reais de gatos e cachorros |
| **YouTube Data API v3** | Upload de vídeos, live streams, playlists, captions e analytics |

## Stack

- **Python 3.11+** (CI roda 3.11; local testado com 3.12/3.14)
- **FFmpeg** — codificação, concatenação, xfade, drawtext e ffprobe (com timeout)
- **Pillow ≥10.3** — thumbnails (gradiente, shadows RGBA, fontes TrueType)
- **pytest** — testes unitários (300 testes, cobertura ≥70% de `utils/`)
- **ruff** — lint (regras E, F, W, I, UP, B)
- **GitHub Actions** — CI/CD e agendamento

## Estrutura

```
.
├── .github/workflows/        # Workflows do GitHub Actions
├── _assets/
│   ├── audio/animal_jazz/    # Faixas jazz (Jamendo)
│   ├── video/animal_broll/   # B-roll de gatos/cachorros (Pixabay)
│   └── thumbnails/           # Thumbnails geradas
├── _data/                    # Estado local (analytics, live_state)
├── _videos/                  # Vídeos gerados e logs de erro
├── scripts/
│   ├── batch_generate.py     # Geração em lote
│   ├── collect_analytics.py  # Coleta de métricas YouTube
│   ├── healthcheck.py        # Verifica dependências e tokens
│   ├── run_live.py           # Inicia live com supervisão
│   ├── sync_animal_broll.py  # Sync Pixabay (gatos/cachorros)
│   └── sync_jazz_music.py    # Sync Jamendo (jazz)
├── tests/                    # Testes pytest
├── utils/
│   ├── ai_helper.py          # Chamadas Gemini
│   ├── animal_branding.py    # Identidade Pata Jazz
│   ├── caption_engine.py     # Legendas SRT automáticas
│   ├── content_strategy.py   # Mood por horário (e peso por cena, se houver dados de performance)
│   ├── ffmpeg_helpers.py      # FFmpeg e ffprobe
│   ├── log_config.py         # Logging centralizado
│   ├── media_pool.py         # Pool de mídia local
│   ├── metadata_engine.py    # Títulos/descrições/hashtags
│   ├── playlist_manager.py   # Playlists automáticas YouTube
│   ├── seo_keywords.py       # SEO otimizado
│   ├── thumbnail_engine.py   # Geração de thumbnails (<2MB)
│   ├── video_builder.py      # Pipeline comum (multi-clip + overlay)
│   ├── video_validator.py    # Validação técnica dos vídeos
│   └── youtube_oauth.py      # OAuth YouTube
├── generate_pata_jazz_*.py   # Geradores
├── upload_youtube.py         # Upload/insert + live + caption + playlist
└── requirements.txt
```

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

Para upload e live, é necessário um token OAuth do YouTube. Execute uma vez:

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

### Variables

- `PATA_JAZZ_ENABLED` — `1` para ligar todos os workflows.
- `PATA_JAZZ_SHORTS_ENABLED` — `1` para Shorts.
- `PATA_JAZZ_HORIZONTAL_ENABLED` — `1` para vídeos horizontais.
- `PATA_JAZZ_LIVE_ENABLED` — `1` para live.
- `YOUTUBE_PRIVACY` — `public`, `unlisted` ou `private`.

## Grade de publicação (GitHub Actions)

| Conteúdo | Frequência | Horário BRT | Workflow |
|---|---|---|---|
| **Shorts** | 4 por dia | 07:00, 13:00, 18:00, 22:00 | `pata-jazz-shorts.yml` |
| **Vídeo horizontal** | 1 por dia | 10:00 | `pata-jazz-horizontal.yml` |
| **Live** | 24/7, sessões de ~320min encadeadas | a cada 6h (`0 */6 * * *` UTC) | `pata-jazz-youtube-live.yml` |
| **Sync de assets** | 2x por semana | Ter e Sex 03:00 | `pata-jazz-sync.yml` |
| **Analytics** | 1x por semana | Segunda 03:00 | `pata-jazz-analytics.yml` |
| **Lote semanal** (manual/eventual) | Gera 28 shorts + 7 horizontais de uma vez, publica 6/dia até esgotar | só disparo manual (`action: all`/`generate`/`publish`) | `pata-jazz-weekly.yml` |

**Total semanal (crons diários):** 4 Shorts/dia + 1 Horizontal/dia = **35 vídeos/semana**, mais a live contínua. O lote semanal (`pata-jazz-weekly.yml`) é um mecanismo separado e não roda por padrão — só produz vídeos extras quando disparado manualmente com `action: all`/`generate`/`publish`.

> **Nota sobre quota (histórico):** o lote semanal já teve um cron diário próprio de "publicar próximos 6" rodando em paralelo aos crons de Shorts/Horizontal - isso empilhava ~11 uploads/dia, passando da quota de ~10.000 unidades/dia da API (cada upload custa ~1.600 unidades) e causando falhas em produção (24-25/07). O cron foi removido; hoje só os crons de Shorts (4/dia) + Horizontal (1/dia) publicam automaticamente. Se for rodar `pata-jazz-weekly.yml` manualmente, ainda vale conferir a soma de uploads do dia antes de disparar.

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
```

### Iniciar uma live

```bash
python generate_pata_jazz_live.py --stream-url rtmp://a.rtmp.youtube.com/live2/xxxx --duration 30 --resolution 1280x720
```

### Coletar analytics

```bash
python scripts/collect_analytics.py
```

## Testes

```bash
pytest -q --cov=utils --cov-report=term-missing
python -m compileall -q .
```

## Troubleshooting

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| `Pool de b-roll vazio` | Nenhum vídeo baixado ainda | Rode `scripts/sync_animal_broll.py` |
| `Pool de jazz vazio` | Nenhuma música baixada ainda | Rode `scripts/sync_jazz_music.py` |
| `Validation failed: resolução` | FFmpeg gerou arquivo fora do formato | Verifique logs em `_videos/last_error.txt` (histórico com timestamp) |
| Upload retorna 401 | Token OAuth expirado | Renove em `utils/youtube_oauth.py` |
| Live cai após alguns minutos | Deadlock de pipe (corrigido) | stderr agora vai para `_videos/live_ffmpeg.log` |
| Thumbnail > 2MB | Imagem muito grande | Já tratado por `_save_under_2mb()` (redimensiona se necessário) |
| `Nenhuma fonte TrueType encontrada` | Fontes não instaladas | Instale DejaVu/arial ou defina `PIL_IMAGE_FONT_PATH` |
| Gemini retorna vazio | Circuit breaker aberto ou modelo inválido | Verifique `GEMINI_MODEL` (default: `gemini-2.0-flash-001`) |
| `Circuit breaker do Gemini aberto` | Muitas respostas 429/503 | Aguarde 120s (reset automático) ou verifique quota |

## Licença

Conteúdo gerado para o canal Amber Hours. Músicas e vídeos respeitam as licenças dos provedores (Jamendo CC/Pixabay).