# Pata Jazz — Amber Hours

Canal automatizado de conteúdo exclusivo: **gatinhos e cachorrinhos fofos + jazz real**. O projeto gera Shorts, vídeos horizontais e transmissões ao vivo para o YouTube usando assets licenciados e APIs públicas.

## Formatos

- **Shorts** (`generate_pata_jazz_short.py`) — vertical 1080×1920, ~35s, **2-3 clipes com crossfade + 1 música de jazz + text overlay do hook nos primeiros 3s**.
- **Vídeos horizontais** (`generate_pata_jazz_horizontal.py`) — 1920×1080, ~4min, **1 clipe + 1 música de jazz**.
- **Live em loop infinito** (`generate_pata_jazz_live.py`) — transmissão horizontal 720p com **vários clipes de gatos/cachorros** e **playlist de até 150 faixas de jazz**.

## Recursos inteligentes

- **Mood por horário**: Shorts e horizontais selecionam cenas baseado na hora (manhã = diversão, tarde = fofura, noite = relax)
- **Multi-clip com crossfade**: Shorts usam 2-3 clipes com transição suave em vez de 1 clipe repetido
- **Text overlay**: Hook aparece como texto no vídeo nos primeiros 3 segundos (drawtext FFmpeg)
- **Legendas automáticas**: SRT gerado via Gemini e enviado como caption track
- **Playlists automáticas**: Videos adicionados a playlists por mood/formato
- **Analytics semanal**: Coleta de métricas para feedback loop
- **Marca consistente**: Todos os títulos começam com "Pata Jazz |"

## APIs reais utilizadas

| Provedor | Uso |
|----------|-----|
| **Gemini** | Títulos, descrições, hashtags e legendas SRT |
| **Jamendo** | Músicas jazz com licença segura |
| **Pixabay** | Clips reais de gatos e cachorros |
| **YouTube Data API v3** | Upload de vídeos, live streams, playlists, captions e analytics |

## Stack

- **Python 3.11+** (CI roda 3.11; local testado com 3.12)
- **FFmpeg** — codificação, concatenação, xfade, drawtext e ffprobe
- **Pillow** — thumbnails
- **pytest** — testes unitários
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
│   ├── content_strategy.py   # Mood por horário e calendário
│   ├── discord_webhook.py    # Notificações Discord
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
pip install -r requirements.txt
```

Instale também o FFmpeg e certifique-se de que `ffmpeg` e `ffprobe` estão no PATH.

### 2. Variáveis de ambiente

Crie um arquivo `.env` (ou exporte manualmente) com as chaves abaixo:

```bash
GEMINI_API_KEY=xxx
PIXABAY_API_KEY=xxx
JAMENDO_CLIENT_ID=xxx  # opcional
YOUTUBE_PRIVACY=public
```

### 3. Credenciais do YouTube

Para upload e live, é necessário um token OAuth do YouTube. Execute uma vez:

```bash
python utils/youtube_oauth.py
```

Salve o JSON resultante como `_data/youtube_token.json` (ou use o secret `YOUTUBE_TOKEN` no GitHub Actions).

## Variáveis do GitHub Actions

### Secrets

- `GEMINI_API_KEY`
- `PIXABAY_API_KEY`
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
| **Live** | 1 por semana | Quarta 19:00 (6h, 720p) | `pata-jazz-youtube-live.yml` |
| **Sync de assets** | 2x por semana | Ter e Sex 03:00 | `pata-jazz-sync.yml` |
| **Analytics** | 1x por semana | Segunda 03:00 | `pata-jazz-analytics.yml` |

**Total semanal:** 28 Shorts + 7 Horizontais + 1 Live = **36 vídeos/semana**

> **Nota sobre quota:** A YouTube API permite 10.000 unidades/dia. Cada upload custa 1.600 unidades. 4 Shorts + 1 Horizontal = 8.000 unidades/dia (dentro do limite com folga).

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

### Fazer upload

```bash
python upload_youtube.py --language=pt --privacy=public _videos/seu_video.mp4
```

### Iniciar uma live

```bash
python generate_pata_jazz_live.py --privacy=public --loop-minutes=30
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
| `Validation failed: resolução` | FFmpeg gerou arquivo fora do formato | Verifique logs em `_videos/last_error.txt` |
| Upload retorna 401 | Token OAuth expirado | Renove em `utils/youtube_oauth.py` |
| Live cai após alguns minutos | Loop ou bitrate inconsistente | Use `--loop-minutes` menor e verifique FFmpeg |
| Thumbnail > 2MB | Imagem muito grande | Já tratado por `_save_under_2mb()` |

## Licença

Conteúdo gerado para o canal Amber Hours. Músicas e vídeos respeitam as licenças dos provedores (Jamendo CC/Pixabay).