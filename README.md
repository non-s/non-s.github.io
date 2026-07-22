# Pata Jazz — Amber Hours

Canal resetado com conteúdo exclusivo de **gatinhos e cachorrinhos fofos + jazz real**.

## Formatos

- **Shorts** (`generate_pata_jazz_short.py`) — vertical 1080×1920.
- **Vídeos horizontais** (`generate_pata_jazz_horizontal.py`) — 1920×1080.
- **Live em loop infinito** (`generate_pata_jazz_live.py`) — transmissão contínua com clipes de gatos/cachorros e jazz de fundo.

## APIs reais utilizadas

| Provedor | Uso |
|----------|-----|
| **Gemini** | Títulos, descrições e hashtags |
| **Jamendo** | Músicas jazz com licença segura |
| **Pixabay** | Clips de gatos e cachorros |
| **YouTube** | Upload de vídeos e live streams |

## Estrutura

```
.
├── .github/workflows/     # Workflows do GitHub Actions
├── _assets/
│   ├── video/animal_broll/  # B-roll de gatos/cachorros
│   ├── audio/animal_jazz/   # Faixas jazz
│   └── thumbnails/          # Thumbnails geradas
├── _data/                   # Estado local (não comitar tokens)
├── _videos/                 # Vídeos de saída
├── scripts/
│   ├── sync_animal_broll.py # Sync Pixabay (gatos/cachorros)
│   └── sync_jazz_music.py   # Sync Jamendo (jazz)
├── utils/
│   ├── animal_branding.py   # Identidade Pata Jazz
│   ├── ai_helper.py         # Chamadas Gemini
│   ├── ffmpeg_helpers.py   # FFmpeg
│   ├── media_pool.py        # Pool de mídia local
│   └── youtube_oauth.py     # OAuth YouTube
├── generate_pata_jazz_*.py  # Geradores
├── upload_youtube.py        # Upload/insert + live
└── requirements.txt
```

## Variáveis do GitHub

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

## Execução local

```bash
pip install -r requirements.txt
python scripts/sync_animal_broll.py
python scripts/sync_jazz_music.py
python generate_pata_jazz_short.py
python upload_youtube.py --language=pt
```

## Licença

Conteúdo gerado para o canal Amber Hours. Músicas e vídeos respeitam as licenças dos provedores (Jamendo CC/Pixabay).
