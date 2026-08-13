# Arquitetura — Pata Jazz

Este documento descreve o fluxo de dados, decisões de design, componentes,
workflows e estado persistente do projeto Pata Jazz. Para setup e contribuição,
veja [CONTRIBUTING.md](./CONTRIBUTING.md).

## Fluxo de dados

```
sync (Pixabay/Jamendo) ─┐
                        ├─→ generate (Short) ──→ upload (YouTube)
                        │                              │
                        │                              └─→ analytics (views/likes)
                        │                                    │
                        │                                    └─→ feedback loop
                        │                                          (scene/title_pattern performance)
                        │                                          → scene_for_mood / pick_title_pattern
                        │                                          → próxima geração prioriza o que performa
                        └─→ _assets/ (cache local) ←──── (reutilizado entre runs via actions/cache)
```

1. **Sync** (`scripts/sync_animal_broll.py`, `scripts/sync_jazz_music.py`) baixa
   assets licenciados (Pixabay/Jamendo) para `_assets/` e grava
   `_data/recent_media.json` para anti-repeat.
2. **Generate** (`generate_pata_jazz_short.py`) monta o Short com FFmpeg usando
   o pool de assets local, escolhe cena/mood/título e gera thumbnail (A/B/C) +
   legendas.
3. **Upload** (`upload_youtube.py`) publica no YouTube, anexa caption track,
   adiciona a playlists e grava `_data/video_tags.json` (cena/padrão de título
   que geraram cada vídeo).
4. **Analytics** (`scripts/collect_analytics.py`) coleta views/likes/semana
   via YouTube Data API v3 e, via **YouTube Analytics API v2**, também
   `averageViewDuration`, `averageViewPercentage`, `ctr`, `impressions` e
   `subscribersGained`. Cruza com `video_tags.json` e grava pesos em
   `_data/scene_performance.json` e `_data/title_pattern_performance.json`.
   Também detecta vídeos virais (≥8× mediana de views) e salva
   `_data/viral_signals.json`; cenas recentes em virais recebem boost de escolha
   futuro, modulado por CTR/retenção.

5. **Feedback loop**: `utils.content_strategy.scene_for_mood()` e
   `utils.seo_keywords.pick_title_pattern()` leem esses pesos e passam a preferir
   o que performa melhor na geração futura, sem nunca zerar as demais opções.
6. **Predict** (`scripts/predict_views.py`) treina um modelo de regressão linear
   sobre os dados históricos e grava `_data/view_predictor.json`, consumido pelo
   dashboard para projeção de views nos próximos slots de cron. As features
   incluem scene/title_pattern one-hot, hora/dia/mês calendário, CTR, AVP e
   interações cena × bucket de horário.
7. **Publish optimizer** (`utils/publish_optimizer.py`) cruza slots de cron do
   canal com desempenho real de cada horário (avg_views, CTR, retenção) e
   devolve os próximos slots mais promissores; workflows de upload passam
   `--publish-at` ISO 8601 UTC para `upload_youtube.py`.
8. **Engagement** (`scripts/respond_comments.py`) responde comentários do canal
   com IA (canal vivo) e grava `_data/comments_responded.json` para anti-repeat.
9. **Identidade** (`scripts/update_channel_identity.py`) rotaciona about/keywords
    do canal por semana ISO (IA + fallback local) e grava `_data/identity.json`.
10. **Long-form** (`scripts/generate_pata_jazz_long.py`) monta 1 vídeo
    horizontal de 15-30min por semana (Loop & Relax) para watch time longo.

## Decisões de design

- **Pool de assets sempre fresco**: `sync_animal_broll.py`/`sync_jazz_music.py`
  paravam de baixar qualquer coisa assim que o pool atingia `MAX_POOL_SIZE`
  (300 clips / 200 faixas) - depois disso, os mesmos assets eram reusados pra
  sempre. Agora, pool cheio dispara `_evict_oldest()` (remove os ~10% mais
  antigos por mtime) antes de continuar o sync, então o pool rotaciona aos
  poucos em vez de congelar. `JAMENDO_SEARCH_TERMS` também ganhou termos de
  jazz animado (swing/bebop/fusion) e lofi jazz - antes só tinha termos
  relaxantes, então `MOOD_GENRES["diversao"]` (swing/bebop/upbeat) nunca
  encontrava nada no pool pra combinar com cenas animadas (playful dog, cat
  playing).
- **ASS animado no Short**: legendas estilizadas (ASS com animação
  palavra-a-palavra) fazem sentido em conteúdo vertical de ~35s onde o texto é
  parte do hook visual — o overlay carrega o gancho de retenção nos primeiros
  segundos.
- **Thumbnail A/B/C com dois loops de feedback**: `utils.thumbnail_engine.winning_thumbnail_variant()`
  calcula qual variante (A/B/C) teve mais views em média e é usada como
  thumbnail *primária* já no próximo upload (loop rápido, fecha a cada
  geração); `scripts.collect_analytics.maybe_rotate_thumbnail()` complementa
  com rotação reativa por vídeo (A→B→C após `_THUMBNAIL_ROTATION_DAYS` dias
  se o vídeo específico estiver abaixo da mediana). Os dois são compatíveis:
  a rotação reativa sempre anda para frente na sequência a partir de
  `thumbnail_variant` gravado no upload, seja qual for o ponto de partida.
- **Wilson score para ranking de performance**: `collect_analytics.py` usa Wilson
  score interval em vez de média pura porque é conservador com amostras pequenas.
  Um vídeo com 100 views e 80% de retenção num vídeo com 10 views e 90% de
  retenção não deve ser classificado abaixo só pela taxa bruta — Wilson dá
  intervalo de confiança que penaliza amostras pequenas sem zerá-las.
- **filelock para estado JSON**: os arquivos em `_data/` sofrem
  read-modify-write de múltiplos scripts e múltiplos jobs do GitHub Actions que
  rodam sobrepostos (shorts + analytics). Sem lock, o último
  a salvar vence e mudanças são perdidas silenciosamente. `filelock` é portável
  (Linux/Windows) e leve — não precisa de `fcntl`/`msvcrt`.
- **Configuração do canal**: `utils/channel_config.py` centraliza a marca,
  tags, playlists e prompts do canal **Pata Jazz**. Todos os módulos consumidores
  (`animal_branding`, `playlist_manager`, `seo_keywords`, `upload_youtube`) leem de
  `active_channel`. O estado do canal é mantido em `_data/` na raiz do projeto.
- **Quota tracker**: `utils/quota_tracker.py` rastreia unidades de quota da
  YouTube API em `_data/quota_usage.json` com alerta em 8000/dia (limite 10000).
  `utils/youtube_retry.retry_youtube_call` registra automaticamente o custo por
  endpoint após sucesso — falhas de rede não gastam quota do lado do YouTube,
  então só conta após retry bem-sucedido.
- **Humanização — canal "vivo"**: publicação sozinha não é um canal, é um feed.
  Cinco unidades fazem a página e o canal reagirem como um criador real:
  (1) **respostas a comentários** (`utils/comment_responder.py`) — IA com o
  system prompt "pessoa real", no idioma do comentário, sem links, com rate-limit
  por usuário/run; comentários são sinal de satisfação pro algoritmo; (2)
  **end-card CTA de sessão** (`utils/video_builder._build_endcard_filter`) —
  call-to-action ASCII rotativa nos últimos ~3s de cada vídeo pra encadear a
  próxima sessão; (3) **identidade do canal viva** (`utils/channel_identity.py`)
  — about/keywords rotacionados por semana ISO com IA + fallback local e trava
  de 1x/semana via `_data/identity.json`; (4) **anti-repeat de títulos**
  (`utils/seo_keywords.py` + `utils/metadata_engine.py`) — os últimos 60 títulos
  ficam em `_data/used_titles.json` e o novo título é re-sorteado até 3x se
  similar (Jaccard) demais ao histórico; (5) **otimização ativa de cena/padrão**
  (`utils/slot_optimizer.py`) — escolhe cena e padrão de título com maior
  previsão de views para o slot de publicação, usando `view_predictor.json`.
- **Long-form Loop & Relax**: 1 Short/dia dá consistência mas sessão curta. O
  gerador `scripts/generate_pata_jazz_long.py` monta 1 vídeo horizontal
  (1920×1080) de 15-30min com clipes em `-stream_loop` até cobrir a duração,
  crossfade lento 2.0s e jazz em loop — poucos uploads que rendem semanas de
  watch time e buscam o público de relaxamento/sono (mood sempre `relax`).

## Componentes

### `utils/`

| Módulo | Responsabilidade |
|--------|------------------|
| `ai_helper.py` | Chamadas Gemini com circuit breaker (429/502/503) e fallback local |
| `animal_branding.py` | Identidade Pata Jazz: detecção de animal, hook por cena, cena aleatória |
| `caption_engine.py` | Legendas ASS animadas (overlay), legenda PT-BR e chapters via Gemini |
| `channel_config.py` | Configuração do canal Pata Jazz: `ChannelConfig`, `CHANNELS`, `active_channel` |
| `channel_identity.py` | Identidade do canal viva: about/keywords rotacionados por semana ISO (IA + fallback) via `channels.update` |
| `comment_responder.py` | Resposta automática a comentários: seleção anti-spam, IA "pessoa real", state + lock |
| `content_strategy.py` | Mood por horário (BRT) + cena ponderada por performance real |
| `ffmpeg_helpers.py` | Wrappers FFmpeg/ffprobe com timeout |
| `log_config.py` | Logging centralizado + log de erros em `_videos/last_error.txt` |
| `media_pool.py` | Pool de mídia local com anti-repeat (`_data/recent_media.json`) |
| `metadata_engine.py` | Títulos/descrições/hashtags em inglês |
| `playlist_manager.py` | Playlists automáticas por mood/formato e por animal (cats/dogs) |
| `publish_optimizer.py` | Escolha de slots de publicação por desempenho real de horário |
| `quota_tracker.py` | Rastreio de unidades de quota YouTube em `_data/quota_usage.json` |
| `seo_keywords.py` | SEO do YouTube + `pick_title_pattern` ponderado por performance |
| `slot_optimizer.py` | Escolha ativa de cena/padrão por previsão de views (`view_predictor.json`) |
| `state_lock.py` | `state_lock()` — lock de arquivo para estado JSON compartilhado |
| `thumbnail_engine.py` | Geração de thumbnails A/B/C <2MB com shadow RGBA |
| `video_builder.py` | Pipeline: assets → FFmpeg (multi-clip + xfade) → validação → thumbnail |
| `video_validator.py` | Validação técnica (resolução, duração, codecs) via ffprobe |
| `youtube_oauth.py` | OAuth YouTube (`youtube_token.json` ou `YOUTUBE_TOKEN`) |
| `youtube_retry.py` | Retry exponencial para YouTube API + registro automático de quota |
| `agency_council.py` | Conselho editorial assistido, sem autoridade de publicação |
| `competitive_intelligence.py` | Benchmark de metadados públicos de canais de referência |
| `content_funnel.py` | Fila editorial entre pesquisa, revisão e produção |
| `editorial_calendar.py` | Plano editorial determinístico de 30 dias |
| `live_station.py` | Planejamento auditável da estação visual ao vivo |
| `openverse_catalog.py` / `gbif_research.py` | Pesquisa aberta e atribuível para revisão humana |
| `visual_intelligence.py` | Sinais visuais conservadores extraídos de assets locais |

### `scripts/`

| Script | Responsabilidade |
|--------|------------------|
| `batch_generate.py` | Geração em lote (N shorts de uma vez) |
| `cleanup_youtube.py` | Remove do canal os vídeos legados de horizontal/live (uso pontual) |
| `collect_analytics.py` | Coleta views/likes/semana + métricas YouTube Analytics API v2 (retention/CTR/impressions/inscritos); alimenta feedback loop (scene/title_pattern) |
| `generate_dashboard.py` | Dashboard HTML autocontido a partir de `_data/`; exibe métricas de retention, CTR, impressions e inscritos ganhos, mais recomendações ativas de slot/cena/padrão. Saída em `_dashboard/` e publicada no Pages |
| `generate_pata_jazz_long.py` | Long-form Loop & Relax (1920×1080, 15-30min, mood relax) |
| `generate_site.py` | Site estático SEO (schema.org) por canal em `_site/<slug>/` a partir de `video_tags.json` + `analytics.json` |
| `healthcheck.py` | Verifica dependências e tokens do ambiente |
| `predict_views.py` | Treina regressão linear para prever views nos primeiros 7 dias |
| `publish_weekly_batch.py` | Publica próximos N vídeos do lote semanal gerado |
| `respond_comments.py` | Responde a comentários do canal (engajamento humano) |
| `sync_animal_broll.py` | Sync Pixabay (clipes de gatos/cachorros) |
| `sync_jazz_music.py` | Sync Jamendo (faixas jazz) |
| `update_channel_identity.py` | Atualiza about/keywords do canal (identidade viva) |
| `collect_competitive_intelligence.py` | Coleta painel de referências por metadados públicos |
| `collect_open_research.py` | Gera catálogo de pesquisa GBIF/Openverse para revisão |
| `generate_editorial_calendar.py` | Gera plano editorial revisável, sem publicar |
| `plan_live_station.py` | Verifica direitos e prepara o plano da estação ao vivo |
| `run_agency_council.py` | Consolida sinais em um brief diário, sem publicar |
| `refresh_oauth_token.py` | Renova OAuth e persiste o token no secret protegido |

### Geradores e upload (raiz)

| Arquivo | Responsabilidade |
|---------|------------------|
| `generate_pata_jazz_short.py` | Shorts verticais 1080×1920, ~28-42s, multi-clip + xfade + ASS overlay |
| `upload_youtube.py` | Upload de vídeo gravado (insert + caption + playlist) |

## Workflows

| Workflow | Trigger | O que faz |
|----------|---------|-----------|
| `ci.yml` | `push`/`pull_request` em `main` | ruff, compile, pytest+cov, pip-audit, mypy bloqueante, bandit |
| `pata-jazz-shorts.yml` | diário, 18:07 UTC / manual | Gera e publica 1 Short no YouTube (Pata Jazz) |
| `pata-jazz-engagement.yml` | diário, 19:37 UTC / manual | Responde a comentários do canal (Pata Jazz) |
| `pata-jazz-sync.yml` | cron 2x/semana (Ter e Sex 06:00 UTC) / manual | Sync b-roll + jazz + evict caches antigos (Pata Jazz) |
| `pata-jazz-analytics.yml` | cron semanal Seg 06:00 UTC / manual | Coleta analytics e gera dashboard como artifact |
| `pata-jazz-analytics-daily.yml` | cron diário 06:00 UTC / manual | Snapshot leve de analytics para histórico fino (Pata Jazz) |
| `pata-jazz-long.yml` | cron semanal Dom 01:13 UTC / manual | Gera e publica 1 long-form Loop & Relax (15-30min) (Pata Jazz) |
| `pata-jazz-identity.yml` | somente manual | Atualiza about/keywords do canal (Pata Jazz) |
| `pata-jazz-batch.yml` | só manual (`workflow_dispatch`) | Gera N shorts em lote, opcionalmente agendando slots otimizados (Pata Jazz) |
| `pata-jazz-weekly.yml` | só manual (`all`/`generate`/`publish`) | Lote adicional controlado para revisão/publicação |
| `oauth-token-refresh.yml` | domingo e quarta, 02:00 UTC / manual | Renova o `access_token` e atualiza `YOUTUBE_TOKEN` (requer `GH_PAT`) |
| `pata-jazz-agency.yml` | diário, 05:35 UTC / manual | Gera brief editorial e memória de decisão |
| `pata-jazz-planning.yml` | segunda, 05:40 UTC / manual | Gera calendário editorial revisável |
| `pata-jazz-trending.yml` | terça e sexta, 05:00 UTC / manual | Atualiza sinais de busca e tendências |
| `pata-jazz-site.yml` | segunda, 08:00 UTC / manual | Gera e publica o site SEO no Pages |
| `pata-jazz-live.yml` | manual | Executa estação ao vivo após readiness explícito |
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
| `view_predictor.json` | `scripts/predict_views.py` (modelo treinado) | `scripts/generate_dashboard.py`, `predict_views()`, `utils/slot_optimizer.py` | sim |
| `viral_signals.json` | `scripts/collect_analytics.py` | `utils/content_strategy.viral_boosted_scenes()` | sim |
| `publish_slots.json` | `utils/publish_optimizer.py` (pontuação histórica) | `utils/publish_optimizer.pick_publish_time()` | sim |
| `quota_usage.json` | `utils/quota_tracker.py` (via `youtube_retry`) | `utils/quota_tracker.log_final_total()` | sim |
| `comments_responded.json` | `utils/comment_responder.py` (a cada resposta) | `utils/comment_responder.select_comments_to_reply()` (anti-repeat/rate-limit) | sim |
| `used_titles.json` | `utils/seo_keywords.record_used_title()` (no upload) | `utils/seo_keywords.title_is_too_repetitive()` (anti-repeat de títulos) | sim |
| `identity.json` | `utils/channel_identity.py` (a cada atualização) | `utils/channel_identity.run_identity_update()` (trava de 1x/semana) | sim |
| `_dashboard/index.html` | `scripts/generate_dashboard.py` | GitHub Pages | não |
| `_site/*.html` | `scripts/generate_site.py` | GitHub Pages | não |

> **Nota sobre persistência entre runs:** os arquivos com lock (JSON de estado)
  são restaurados/persistidos entre runs do GitHub Actions via `actions/cache`
  na composite action `.github/actions/restore-token-and-cache`. Todos os
  workflows que alteram esses snapshots usam o grupo global de concorrência
  `pata-jazz-state`, com `cancel-in-progress: false`. O `filelock` coordena
  processos no mesmo runner; o grupo global impede forks e perda de atualização
  entre runners diferentes.

### OAuth refresh persistente (CI)

O `refresh_token` do Google expira após 90 dias sem uso. O workflow
`.github/workflows/oauth-token-refresh.yml` roda semanalmente (domingo
02:00 UTC) e tenta renovar o `access_token` via
`Credentials.refresh(Request())`. Se o refresh funcionar, atualiza o
secret `YOUTUBE_TOKEN` automaticamente com `gh secret set` — isso
**requer um fine-grained Personal Access Token (PAT) limitado a este
repositório** armazenado
como secret `GH_PAT`. Se o `GH_PAT` não estiver configurado, ou se o
`refresh_token` expirou, o workflow abre uma issue pedindo a renovação
manual (`python utils/youtube_oauth.py` localmente + atualizar o secret
`YOUTUBE_TOKEN` manualmente).
