# Arquitetura — Pata Jazz

Este documento descreve o fluxo de dados, decisões de design, componentes,
workflows e estado persistente do projeto Pata Jazz. Para setup e contribuição,
veja [CONTRIBUTING.md](./CONTRIBUTING.md).

## Fluxo de dados

```
sync (Pixabay/Jamendo) ─┐
                        ├─→ generate (Shorts/Horizontal/Live) ──→ upload (YouTube) ──→ analytics (views/likes)
                        │                                                              │
                        │                                                              └─→ feedback loop
                        │                                                                    (scene/title_pattern performance)
                        │                                                                    → scene_for_mood / pick_title_pattern
                        │                                                                    → próxima geração prioriza o que performa
                        └─→ _assets/ (cache local) ←──── (reutilizado entre runs via actions/cache)
```

1. **Sync** (`scripts/sync_animal_broll.py`, `scripts/sync_jazz_music.py`) baixa
   assets licenciados (Pixabay/Jamendo) para `_assets/` e grava
   `_data/recent_media.json` para anti-repeat.
2. **Generate** (`generate_pata_jazz_short.py`, `generate_pata_jazz_horizontal.py`,
   `generate_pata_jazz_live.py`) monta o vídeo com FFmpeg usando o pool de assets
   local, escolhe cena/mood/título e gera thumbnail + legendas.
3. **Upload** (`upload_youtube.py` para vídeos gravados; `live_broadcast.py` para
   live) publica no YouTube, anexa caption track, adiciona a playlists e grava
   `_data/video_tags.json` (cena/padrão de título que geraram cada vídeo) e
   `_data/live_state.json` (broadcast/stream para reconexão).
4. **Analytics** (`scripts/collect_analytics.py`) coleta views/likes semanalmente,
   cruza com `video_tags.json` e grava pesos em `_data/scene_performance.json` e
   `_data/title_pattern_performance.json`.
5. **Feedback loop**: `utils.content_strategy.scene_for_mood()` e
   `utils.seo_keywords.pick_title_pattern()` leem esses pesos e passam a preferir
   o que performa melhor na geração futura, sem nunca zerar as demais opções.
6. **Predict** (`scripts/predict_views.py`) treina um modelo de regressão linear
   sobre os dados históricos e grava `_data/view_predictor.json`, consumido pelo
   dashboard para projeção de views nos próximos slots de cron.

## Decisões de design

- **ASS só em Shorts**: legendas estilizadas (ASS com animação/posicionamento)
  fazem sentido em conteúdo vertical de ~35s onde o texto é parte do hook visual.
  Em vídeos horizontais de 5min e na live 24/7, ASS seria overkill — a legenda
  SRT simples como caption track do YouTube é suficiente e mais acessível
  (suporte nativo do player, não depende do overlay do FFmpeg).
- **Wilson score para ranking de performance**: `collect_analytics.py` usa Wilson
  score interval em vez de média pura porque é conservador com amostras pequenas.
  Um vídeo com 100 views e 80% de retenção num vídeo com 10 views e 90% de
  retenção não deve ser classificado abaixo só pela taxa bruta — Wilson dá
  intervalo de confiança que penaliza amostras pequenas sem zerá-las.
- **filelock para estado JSON**: os arquivos em `_data/` sofrem
  read-modify-write de múltiplos scripts e múltiplos jobs do GitHub Actions que
  rodam sobrepostos (shorts + horizontal + live + analytics). Sem lock, o último
  a salvar vence e mudanças são perdidas silenciosamente. `filelock` é portável
  (Linux/Windows) e leve — não precisa de `fcntl`/`msvcrt`.
- **Split upload_youtube / live_broadcast**: antes tudo vivia em `upload_youtube.py`.
  Separar evita que mudanças na lógica de live quebrem upload de vídeo gravado
  (e vice-versa) e mantém cada módulo focado — `live_broadcast.py` nunca importa
  `MediaFileUpload`. O modo `--mode live` em `upload_youtube.py` ainda funciona
  chamando `live_broadcast.create_live_stream()` por compatibilidade.
- **Multi-canal**: `utils/channel_config.py` abstrai a marca/tags/playlists/prompts
  por canal. Hoje só `PATA_JAZZ` existe, mas novos canais (`Pata Lofi`,
  `Pata Classical`...) podem ser adicionados ao registry `CHANNELS` sem mudar os
  módulos consumidores (`animal_branding`, `playlist_manager`, `seo_keywords`,
  `upload_youtube`, `live_broadcast`) — eles leem de `active_channel`. Evita
  duplicar o repo inteiro por canal.
- **Quota tracker**: `utils/quota_tracker.py` rastreia unidades de quota da
  YouTube API em `_data/quota_usage.json` com alerta em 8000/dia (limite 10000).
  `utils/youtube_retry.retry_youtube_call` registra automaticamente o custo por
  endpoint após sucesso — falhas de rede não gastam quota do lado do YouTube,
  então só conta após retry bem-sucedido.

## Componentes

### `utils/`

| Módulo | Responsabilidade |
|--------|------------------|
| `ai_helper.py` | Chamadas Gemini com circuit breaker (429/502/503) e fallback local |
| `animal_branding.py` | Identidade Pata Jazz: detecção de animal, hook por cena, cena aleatória |
| `caption_engine.py` | Legendas SRT (caption track YouTube) e ASS (overlay Shorts) via Gemini |
| `channel_config.py` | Abstração multi-canal: `ChannelConfig`, registry `CHANNELS`, `active_channel` |
| `content_strategy.py` | Mood por horário (BRT) + cena ponderada por performance real |
| `ffmpeg_helpers.py` | Wrappers FFmpeg/ffprobe com timeout |
| `live_chat.py` | Le chat ao vivo, parseia comandos `!`, escreve overlay para FFmpeg |
| `log_config.py` | Logging centralizado + log de erros em `_videos/last_error.txt` |
| `media_pool.py` | Pool de mídia local com anti-repeat (`_data/recent_media.json`) |
| `metadata_engine.py` | Títulos/descrições/hashtags em inglês |
| `playlist_manager.py` | Playlists automáticas por mood/formato (cache em `_data/playlist_cache.json`) |
| `quota_tracker.py` | Rastreio de unidades de quota YouTube em `_data/quota_usage.json` |
| `seo_keywords.py` | SEO otimizado + `pick_title_pattern` ponderado por performance |
| `state_lock.py` | `state_lock()` — lock de arquivo para estado JSON compartilhado |
| `thumbnail_engine.py` | Geração de thumbnails <2MB com shadow RGBA |
| `video_builder.py` | Pipeline comum: assets → FFmpeg (multi-clip + xfade) → validação → thumbnail |
| `video_validator.py` | Validação técnica (resolução, duração, codecs) via ffprobe |
| `youtube_oauth.py` | OAuth YouTube (`youtube_token.json` ou `YOUTUBE_TOKEN`) |
| `youtube_retry.py` | Retry exponencial para YouTube API + registro automático de quota |

### `scripts/`

| Script | Responsabilidade |
|--------|------------------|
| `batch_generate.py` | Geração em lote (N vídeos de uma vez) |
| `check_live_health.py` | Verifica broadcast `active`; abre issue se cair; grava `_data/last_health.json` |
| `collect_analytics.py` | Coleta views/likes semanal; alimenta feedback loop (scene/title_pattern) |
| `generate_dashboard.py` | Dashboard HTML autocontido a partir de `_data/` |
| `healthcheck.py` | Verifica dependências e tokens do ambiente |
| `predict_views.py` | Treina regressão linear para prever views nos primeiros 7 dias |
| `publish_weekly_batch.py` | Publica próximos N vídeos do lote semanal gerado |
| `run_live.py` | Inicia live com supervisão (reconecta FFmpeg até 200x) |
| `sync_animal_broll.py` | Sync Pixabay (clipes de gatos/cachorros) |
| `sync_jazz_music.py` | Sync Jamendo (faixas jazz) |

### Geradores e upload (raiz)

| Arquivo | Responsabilidade |
|---------|------------------|
| `generate_pata_jazz_short.py` | Shorts verticais 1080×1920, ~35s, multi-clip + xfade + ASS overlay |
| `generate_pata_jazz_horizontal.py` | Vídeos horizontais 1920×1080, ~5min, 1 clipe + 1 música |
| `generate_pata_jazz_live.py` | Live 24/7 720p: loop de clipes + playlist jazz + overlay FFmpeg |
| `upload_youtube.py` | Upload de vídeo gravado (insert + caption + playlist) |
| `live_broadcast.py` | Cria/gerencia liveBroadcast/liveStream no YouTube (separado de upload) |

## Workflows

| Workflow | Trigger | O que faz |
|----------|---------|-----------|
| `ci.yml` | `push`/`pull_request` em `main` | ruff, compile, pytest+cov, pip-audit, mypy (advisory), bandit |
| `pata-jazz-shorts.yml` | cron 4x/dia (10:00,16:00,21:00,01:00 UTC) / manual | Gera e publica 1 Short |
| `pata-jazz-horizontal.yml` | cron diário 13:00 UTC / manual | Gera e publica 1 vídeo horizontal |
| `pata-jazz-youtube-live.yml` | cron 6h (`0 */6 * * *` UTC) / manual | Sessão de live ~320min (reconecta no mesmo broadcast) |
| `pata-jazz-sync.yml` | cron 2x/semana (Ter e Sex 06:00 UTC) / manual | Sync b-roll + jazz + evict caches antigos |
| `pata-jazz-analytics.yml` | cron semanal Seg 06:00 UTC / manual | Coleta analytics, gera dashboard, publica no GitHub Pages |
| `pata-jazz-live-healthcheck.yml` | cron 2h (`0 */2 * * *` UTC) / manual | Verifica broadcast `active`; abre/fecha issue com contexto |
| `pata-jazz-batch.yml` | só manual (`workflow_dispatch`) | Gera N vídeos de um tipo específico em lote |
| `pata-jazz-weekly.yml` | só manual (`all`/`generate`/`publish`) | Lote semanal: 28 shorts + 7 horizontais, publica 6/dia |
| `oauth-token-refresh.yml` | cron domingo 02:00 UTC / manual | Renova o `access_token` e atualiza o secret `YOUTUBE_TOKEN` via `gh secret set` (requer secret `GH_PAT`) |
| `release.yml` | cron domingo 00:00 UTC / manual | Gera tag `vYYYY-MM-DD` + release notes a partir de commits `feat:`/`fix:`/`security:` |

## Estado persistente (`_data/`)

| Arquivo | Quem escreve | Quem lê | Lock |
|---------|--------------|---------|------|
| `recent_media.json` | `utils/media_pool.py` (sync + generate) | `utils/media_pool.py` (anti-repeat) | sim |
| `playlist_cache.json` | `utils/playlist_manager.py` | `utils/playlist_manager.py` | sim |
| `video_tags.json` | `upload_youtube.py` (no upload) | `scripts/collect_analytics.py`, `scripts/predict_views.py` | sim |
| `scene_performance.json` | `scripts/collect_analytics.py` | `utils/content_strategy.scene_for_mood()` | sim |
| `title_pattern_performance.json` | `scripts/collect_analytics.py` | `utils/seo_keywords.pick_title_pattern()` | sim |
| `analytics.json` | `scripts/collect_analytics.py` | `scripts/generate_dashboard.py`, `scripts/predict_views.py` | sim |
| `analytics_history.json` | `scripts/collect_analytics.py` (snapshots semanais) | `scripts/generate_dashboard.py` | sim |
| `view_predictor.json` | `scripts/predict_views.py` (modelo treinado) | `scripts/generate_dashboard.py`, `predict_views()` | sim |
| `live_state.json` | `live_broadcast.py`, `generate_pata_jazz_live.py` | `live_broadcast._try_resume_existing_broadcast()`, `upload_youtube` | sim |
| `live_viewer_history.json` | `upload_youtube.record_live_viewer_snapshot()` (por segmento FFmpeg) | `scripts/generate_dashboard.py` | sim |
| `live_chat_replies.json` | `utils/live_chat.py` | — (debug/inspeção) | sim |
| `live_chat_overlay.txt` | `utils/live_chat.py` | FFmpeg overlay (`textfile=...:reload=1`) | não (arquivo simples) |
| `live_current_track.json` | `generate_pata_jazz_live.py` (faixa atual) | overlay FFmpeg | não |
| `live_next_scene.json` | `utils/live_chat.py` (comando `!scene`) | `generate_pata_jazz_live.py` (one-shot) | não |
| `live_uptime.txt` | `generate_pata_jazz_live.py` | overlay FFmpeg | não |
| `last_health.json` | `scripts/check_live_health.py` | workflow healthcheck (contexto da issue) | não |
| `quota_usage.json` | `utils/quota_tracker.py` (via `youtube_retry`) | `utils/quota_tracker.log_final_total()` | sim |

> **Nota sobre persistência entre runs:** os arquivos com lock (JSON de estado)
  são restaurados/persistidos entre runs do GitHub Actions via `actions/cache`
  na composite action `.github/actions/restore-token-and-cache`. Sem isso, cada
  run começa de um checkout limpo e o feedback loop nunca acumula dados.

### OAuth refresh persistente (CI)

O `refresh_token` do Google expira após 90 dias sem uso. O workflow
`.github/workflows/oauth-token-refresh.yml` roda semanalmente (domingo
02:00 UTC) e tenta renovar o `access_token` via
`Credentials.refresh(Request())`. Se o refresh funcionar, atualiza o
secret `YOUTUBE_TOKEN` automaticamente com `gh secret set` — isso
**requer um Personal Access Token (PAT) com scope `repo`** armazenado
como secret `GH_PAT`. Se o `GH_PAT` não estiver configurado, ou se o
`refresh_token` expirou, o workflow abre uma issue pedindo a renovação
manual (`python utils/youtube_oauth.py` localmente + atualizar o secret
`YOUTUBE_TOKEN` manualmente).