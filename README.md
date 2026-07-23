# Pata Jazz — Amber Hours

Canal automatizado de conteúdo exclusivo: **gatinhos e cachorrinhos fofos + jazz real**. O projeto gera Shorts, vídeos horizontais e transmissões ao vivo para o YouTube usando assets licenciados e APIs públicas.

## Formatos

- **Shorts** (`generate_pata_jazz_short.py`) — vertical 1080×1920, ~35s, **1 clipe fofo + 1 música de jazz**.
- **Vídeos horizontais** (`generate_pata_jazz_horizontal.py`) — 1920×1080, ~4min, **1 clipe fofo + 1 música de jazz**.
- **Live em loop infinito** (`generate_pata_jazz_live.py`) — transmissão horizontal com **vários clipes de gatos/cachorros** e **playlist de até 150 faixas de jazz**.

## APIs reais utilizadas

| Provedor | Uso |
|----------|-----|
| **Gemini** | Títulos, descrições e hashtags |
| **Jamendo** | Músicas jazz com licença segura |
| **Pixabay** | Clips reais de gatos e cachorros |
| **YouTube Data API v3** | Upload de vídeos e live streams |

## Stack

- **Python 3.11+** (CI roda 3.11; local testado com 3.12)
- **FFmpeg** — codificação, concatenação e ffprobe
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
├── _data/                    # Estado local (não comitar tokens)
├── _videos/                  # Vídeos gerados e logs de erro
├── scripts/
│   ├── batch_generate.py     # Geração em lote
│   ├── healthcheck.py        # Verifica dependências e tokens
│   ├── run_live.py           # Inicia live com supervisão
│   ├── sync_animal_broll.py  # Sync Pixabay (gatos/cachorros)
│   └── sync_jazz_music.py    # Sync Jamendo (jazz)
├── tests/                    # Testes pytest
├── utils/
│   ├── ai_helper.py          # Chamadas Gemini
│   ├── animal_branding.py    # Identidade Pata Jazz
│   ├── ffmpeg_helpers.py     # FFmpeg e ffprobe
│   ├── log_config.py         # Logging centralizado
│   ├── media_pool.py         # Pool de mídia local
│   ├── metadata_engine.py    # Títulos/descrições/hashtags
│   ├── thumbnail_engine.py   # Geração de thumbnails
│   ├── video_builder.py      # Pipeline comum de geração
│   ├── video_validator.py    # Validação técnica dos vídeos
│   └── youtube_oauth.py      # OAuth YouTube
├── generate_pata_jazz_*.py   # Geradores
├── upload_youtube.py         # Upload/insert + live
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
JAMENDO_API_KEY=xxx  # opcional
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
- `YOUTUBE_CLIENT_SECRET` — JSON do client_secret do Google

### Variables

- `PATA_JAZZ_ENABLED` — `1` para ligar todos os workflows.
- `PATA_JAZZ_SHORTS_ENABLED` — `1` para Shorts.
- `PATA_JAZZ_HORIZONTAL_ENABLED` — `1` para vídeos horizontais.
- `PATA_JAZZ_LIVE_ENABLED` — `1` para live.
- `YOUTUBE_PRIVACY` — `public`, `unlisted` ou `private`.

## Grade de publicação (GitHub Actions) - PLANO 7 DIAS

| Conteúdo | Frequência | Horário BRT | Workflow |
|---|---|---|---|
| **Shorts** | 3 por dia | 08:30, 14:30, 19:30 | `pata-jazz-shorts.yml` |
| **Vídeo horizontal** | 2 por semana | Terça 10:00, Sexta 16:00 | `pata-jazz-horizontal.yml` |
| **Live** | 1 por semana | Quarta 19:00 (6h) | `pata-jazz-youtube-live.yml` |

**Total semanal:** 21 Shorts + 2 Horizontais + 1 Live = **24 vídeos/semana**

> **Observação sobre a live:** O runner gratuito do GitHub Actions tem limite de ~6h por execução. A live semanal roda por 6 horas contínuas. Para lives 24/7 verdadeiras, é necessário runner pago, VPS ou cloud externa.

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

## Testes

```bash
pytest -q
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

## Licença

Conteúdo gerado para o canal Amber Hours. Músicas e vídeos respeitam as licenças dos provedores (Jamendo CC/Pixabay).
