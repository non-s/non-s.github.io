# Arquitetura — Pata Jazz

Este documento descreve o fluxo de dados, decisões de design, componentes,
workflows e estado persistente do projeto Pata Jazz. Para setup e contribuição,
veja [CONTRIBUTING.md](./CONTRIBUTING.md).

## Fluxo de dados

```
sync (Pixabay/Jamendo) ─┐
                        ├─→ generate (Short) ──→ upload (YouTube) ──→ cross-post (TikTok/Reels)
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
4. **Cross-post** (`upload_tiktok.py`, `upload_reels.py`) publica o mesmo Short
   no TikTok (via Playwright) e no Instagram Reels logo após o upload no
   YouTube, disparado pelo workflow `cross-post.yml`.
5. **Analytics** (`scripts/collect_analytics.py`) coleta views/likes semanalmente,
   cruza com `video_tags.json` e grava pesos em `_data/scene_performance.json` e
   `_data/title_pattern_performance.json`.
6. **Feedback loop**: `utils.content_strategy.scene_for_mood()` e
   `utils.seo_keywords.pick_title_pattern()` leem esses pesos e passam a preferir
   o que performa melhor na geração futura, sem nunca zerar as demais opções.
7. **Predict** (`scripts/predict_views.py`) treina um modelo de regressão linear
   sobre os dados históricos e grava `_data/view_predictor.json`, consumido pelo
   dashboard para projeção de views nos próximos slots de cron.
8. **Engagement** (`scripts/respond_comments.py`) responde comentários do canal
   com IA (canal vivo) e grava `_data/comments_responded.json` para anti-repeat.
9. **Identidade** (`scripts/update_channel_identity.py`) rotaciona about/keywords
   do canal por semana ISO (IA + fallback local) e grava `_data/identity.json`.
10. **Long-form** (`scripts/generate_pata_jazz_long.py`) monta 1 vídeo
    horizontal de 10-45min por semana (Loop & Relax) para watch time longo.

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
  rodam sobrepostos (shorts + analytics + cross-post). Sem lock, o último
  a salvar vence e mudanças são perdidas silenciosamente. `filelock` é portável
  (Linux/Windows) e leve — não precisa de `fcntl`/`msvcrt`.
- **Cross-posting via browser automation**: o TikTok não tem uma API pública de
  upload equivalente à do YouTube; `utils/tiktok_uploader.py` usa Playwright
  para logar e publicar como um usuário real faria, com sessão persistida em
  `tiktok_state.json` (cacheada entre runs do `cross-post.yml` via
  `actions/cache`) para não precisar logar a cada upload.
- **Rastreio de cross-posting independente por plataforma**: `upload_tiktok.py`
  decide o que já foi postado no TikTok pela presença de `tiktok_url` no
  `.json` do vídeo - não pelos campos `published`/`video_id` que
  `scripts/publish_weekly_batch.py` usa para rastrear publicação no
  YouTube. São publicações independentes; reusar o filtro do YouTube fazia
  o cross-posting pular vídeos já publicados lá mesmo sem nunca terem ido
  pro TikTok.
- **Multi-canal**: `utils/channel_config.py` abstrai a marca/tags/playlists/prompts
  por canal. Hoje só `PATA_JAZZ` existe, mas novos canais (`Pata Lofi`,
  `Pata Classical`...) podem ser adicionados ao registry `CHANNELS` sem mudar os
  módulos consumidores (`animal_branding`, `playlist_manager`, `seo_keywords`,
  `upload_youtube`) — eles leem de `active_channel`. Evita duplicar o repo
  inteiro por canal.
- **Quota tracker**: `utils/quota_tracker.py` rastreia unidades de quota da
  YouTube API em `_data/quota_usage.json` com alerta em 8000/dia (limite 10000).
  `utils/youtube_retry.retry_youtube_call` registra automaticamente o custo por
  endpoint após sucesso — falhas de rede não gastam quota do lado do YouTube,
  então só conta após retry bem-sucedido.
- **Humanização — canal "vivo"**: publicação sozinha não é um canal, é um feed.
  Quatro unidades fazem a página e o canal reagirem como um criador real:
  (1) **respostas a comentários** (`utils/comment_responder.py`) — IA com o
  system prompt "pessoa real", no idioma do comentário, sem links, com rate-limit
  por usuário/run; comentários são sinal de satisfação pro algoritmo; (2)
  **end-card CTA de sessão** (`utils/video_builder._build_endcard_filter`) —
  call-to-action ASCII rotativa nos últimos ~2s de cada vídeo pra encadear a
  próxima sessão; (3) **identidade do canal viva** (`utils/channel_identity.py`)
  — about/keywords rotacionados por semana ISO com IA + fallback local e trava
  de 1x/semana via `_data/identity.json`; (4) **anti-repeat de títulos**
  (`utils/seo_keywords.py` + `utils/metadata_engine.py`) — os últimos 60 títulos
  ficam em `_data/used_titles.json` e o novo título é re-sorteado até 3x se
  similar (Jaccard) demais ao histórico.
- **Long-form Loop & Relax**: 24 Shorts/dia dão frequência mas sessão curta. O
  gerador `scripts/generate_pata_jazz_long.py` monta 1 vídeo horizontal
  (1920×1080) de 10-45min com clipes em `-stream_loop` até cobrir a duração,
  crossfade lento 2.0s e jazz em loop — poucos uploads que rendem semanas de
  watch time e buscam o público de relaxamento/sono (mood sempre `relax`).

## Componentes

### `utils/`

| Módulo | Responsabilidade |
|--------|------------------|
| `ai_helper.py` | Chamadas Gemini com circuit breaker (429/502/503) e fallback local |
| `animal_branding.py` | Identidade Pata Jazz: detecção de animal, hook por cena, cena aleatória |
| `caption_engine.py` | Legendas ASS animadas (overlay), legenda PT-BR e chapters via Gemini |
| `channel_config.py` | Abstração multi-canal: `ChannelConfig`, registry `CHANNELS`, `active_channel` |
| `channel_identity.py` | Identidade do canal viva: about/keywords rotacionados por semana ISO (IA + fallback) via `channels.update` |
| `comment_responder.py` | Resposta automática a comentários: seleção anti-spam, IA "pessoa real", state + lock |
| `content_strategy.py` | Mood por horário (BRT) + cena ponderada por performance real |
| `ffmpeg_helpers.py` | Wrappers FFmpeg/ffprobe com timeout |
| `log_config.py` | Logging centralizado + log de erros em `_videos/last_error.txt` |
| `media_pool.py` | Pool de mídia local com anti-repeat (`_data/recent_media.json`) |
| `metadata_engine.py` | Títulos/descrições/hashtags em inglês |
| `playlist_manager.py` | Playlists automáticas por mood/formato (cache em `_data/playlist_cache.json`) |
| `quota_tracker.py` | Rastreio de unidades de quota YouTube em `_data/quota_usage.json` |
| `seo_keywords.py` | SEO do YouTube + `pick_title_pattern` ponderado por performance + hashtags nativas do TikTok (`generate_tiktok_hashtags`) |
| `state_lock.py` | `state_lock()` — lock de arquivo para estado JSON compartilhado |
| `thumbnail_engine.py` | Geração de thumbnails A/B/C <2MB com shadow RGBA |
| `tiktok_uploader.py` | Upload no TikTok via Playwright (login + storage_state persistido) |
| `video_builder.py` | Pipeline: assets → FFmpeg (multi-clip + xfade) → validação → thumbnail |
| `video_validator.py` | Validação técnica (resolução, duração, codecs) via ffprobe |
| `youtube_oauth.py` | OAuth YouTube (`youtube_token.json` ou `YOUTUBE_TOKEN`) |
| `youtube_retry.py` | Retry exponencial para YouTube API + registro automático de quota |

### `scripts/`

| Script | Responsabilidade |
|--------|------------------|
| `batch_generate.py` | Geração em lote (N shorts de uma vez) |
| `cleanup_youtube.py` | Remove do canal os vídeos legados de horizontal/live (uso pontual) |
| `collect_analytics.py` | Coleta views/likes semanal; alimenta feedback loop (scene/title_pattern) |
| `generate_dashboard.py` | Dashboard HTML autocontido a partir de `_data/` |
| `generate_pata_jazz_long.py` | Long-form Loop & Relax (1920×1080, 10-45min, mood relax) |
| `healthcheck.py` | Verifica dependências e tokens do ambiente |
| `predict_views.py` | Treina regressão linear para prever views nos primeiros 7 dias |
| `publish_weekly_batch.py` | Publica próximos N vídeos do lote semanal gerado |
| `respond_comments.py` | Responde a comentários do canal (engajamento humano) |
| `sync_animal_broll.py` | Sync Pixabay (clipes de gatos/cachorros) |
| `sync_jazz_music.py` | Sync Jamendo (faixas jazz) |
| `update_channel_identity.py` | Atualiza about/keywords do canal (identidade viva) |

### Geradores e upload (raiz)

| Arquivo | Responsabilidade |
|---------|------------------|
| `generate_pata_jazz_short.py` | Shorts verticais 1080×1920, ~35s, multi-clip + xfade + ASS overlay |
| `upload_youtube.py` | Upload de vídeo gravado (insert + caption + playlist) |
| `upload_tiktok.py` | Cross-posting no TikTok via Playwright |
| `upload_reels.py` | Cross-posting no Instagram Reels |

## Workflows

| Workflow | Trigger | O que faz |
|----------|---------|-----------|
| `ci.yml` | `push`/`pull_request` em `main` | ruff, compile, pytest+cov, pip-audit, mypy (advisory), bandit |
| `pata-jazz-shorts.yml` | cron horário (minuto 7, `7 * * * *` UTC) / manual | Gera e publica 1 Short no YouTube |
| `cross-post.yml` | `workflow_run` (após `pata-jazz-shorts.yml`) / manual | Cross-posta o Short mais recente para TikTok e Reels |
| `pata-jazz-engagement.yml` | cron horário (minuto 37, `37 * * * *` UTC) / manual | Responde a comentários do canal (canal vivo) |
| `pata-jazz-sync.yml` | cron 2x/semana (Ter e Sex 06:00 UTC) / manual | Sync b-roll + jazz + evict caches antigos |
| `pata-jazz-analytics.yml` | cron semanal Seg 06:00 UTC / manual | Coleta analytics, gera dashboard, publica no GitHub Pages |
| `pata-jazz-long.yml` | cron semanal Dom 01:13 UTC / manual | Gera e publica 1 long-form Loop & Relax (10-45min) |
| `pata-jazz-identity.yml` | cron semanal Seg 02:23 UTC / manual | Atualiza about/keywords do canal (identidade viva) |
| `pata-jazz-batch.yml` | só manual (`workflow_dispatch`) | Gera N shorts em lote |
| `pata-jazz-weekly.yml` | só manual (`all`/`generate`/`publish`) | Lote semanal: 35 shorts, publica 6/dia |
| `cleanup-youtube.yml` | só manual (`workflow_dispatch`, `dry_run`) | Remove vídeos legados de horizontal/live do canal |
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
| `quota_usage.json` | `utils/quota_tracker.py` (via `youtube_retry`) | `utils/quota_tracker.log_final_total()` | sim |
| `comments_responded.json` | `utils/comment_responder.py` (a cada resposta) | `utils/comment_responder.select_comments_to_reply()` (anti-repeat/rate-limit) | sim |
| `used_titles.json` | `utils/seo_keywords.record_used_title()` (no upload) | `utils/seo_keywords.title_is_too_repetitive()` (anti-repeat de títulos) | sim |
| `identity.json` | `utils/channel_identity.py` (a cada atualização) | `utils/channel_identity.run_identity_update()` (trava de 1x/semana) | sim |
| `tiktok_posts.json` | `utils/tiktok_uploader._record_tiktok_post()` (a cada post publicado) | `scripts/generate_dashboard.py` (seção "Cross-posting TikTok") | sim |

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
