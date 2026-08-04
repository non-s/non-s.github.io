# Operação Zeus — Plano Estratégico Pata Jazz

> Objetivo: transformar o Pata Jazz no maior canal de "pet relaxation music" do YouTube, com SEO agressivo, gatilhos mentais e estratégia de publicação baseada em dados. Um canal único, focado, gratuito e global.

## 1. Diagnóstico atual (por que 0 views?)

1. **Títulos genéricos**: "Pata Jazz | Cute cat relaxing" não espelha o que as pessoas digitam.
2. **Sem cauda longa de alto volume**: não usamos frases como "music for cats to sleep", "dog anxiety relief", "jazz for pets home alone".
3. **Thumbnails sem pattern interrupt**: falta contraste, curiosidade, emoção extrema, rosto humano/olhar do animal.
4. **Descrições curtas**: o YouTube usa a descrição para ranquear. 3 linhas é pouco.
5. **Sem funil de retenção**: Short de 35s não segura audiência. Precisa de hook, end-card, playlists.
6. **Publicação cega**: 24 shorts/dia sem saber quais horários/dias performam.
7. **Sem gatilhos mentais**: não usamos curiosidade, prova social, promessa específica, emoção.
8. **Sem benchmarking**: não estudamos o que os maiores canais do nicho fazem.

## 2. Posicionamento editorial

- **Marca**: Pata Jazz — "The world's calmest channel for cats, dogs and anxious pets".
- **Promessa**: relaxamento real em 30 segundos, para pets e humanos.
- **Tom**: acolhedor, premium, humano, científico leve ("calm your pet's anxiety").
- **Público-alvo**: donos de pets, pessoas com ansiedade, estudantes, pais de pets que deixam o animal sozinho.

## 3. SEO — palavras-chave de alto volume

### Cauda curta (competitiva, mas necessária na descrição)
- relaxing music for cats
- calming music for dogs
- pet anxiety music
- jazz for cats
- music for pets

### Cauda longa (alta conversão, menos concorrência)
- music for cats to sleep at night
- dog separation anxiety relief music
- calming music for anxious dogs home alone
- jazz music to relax my cat
- 1 hour relaxing music for pets
- music to calm hyperactive puppy
- sleepy cat music with birds
- soothing music for rescue dogs

### Tendências / buscas cíclicas
- thunderstorm music for dogs
- fireworks anxiety music for pets
- new years eve pet calming music
- 4th of july dog calming music
- pet sleep music compilation

## 4. Gatilhos mentais nos títulos

1. **Promessa específica**: "Your cat will sleep in 30 seconds".
2. **Curiosidade**: "This sound calms 9/10 anxious dogs".
3. **Prova social**: "1M pets relaxed to this".
4. **Escassez/urgência**: "Play this before you leave home".
5. **Emoção/empatia**: "For the dog that misses you".
6. **Identificação**: "If your cat is stressed, play this".
7. **Resultado transformador**: "From anxious to asleep in seconds".

## 5. Estratégia de publicação

- **Foco na semana 1 de um vídeo**: 80% do sucesso de um vídeo no YouTube é decidido nos primeiros 7 dias.
- **Horários de pico (benchmark inicial)**: 17h-21h BRT (fins de tarde/noite EUA + noite Europa) e domingo 10h-14h.
- **Dados reais**: `utils/publish_optimizer.py` cruza `publish_slots.json` (avg_views, ctr, retention) com slots benchmark; sem dados, usa a heurística acima.
- **Agendamento**: workflow `pata-jazz-shorts.yml` escolhe slot via `pick_publish_time()` e passa `--publish-at` ISO 8601 UTC para `upload_youtube.py`.
- **Reduzir volume, aumentar qualidade**: começar testando 6-8 shorts/dia nos horários preditivos, não 24.
- **Long-form toda semana**: 1 vídeo de 20-45min para session watch time.

## 6. Thumbnails — regras de CTR máximo

1. **Rosto/animal com olhar direto** — gatos/cachorros com olhos grandes transmitem emoção.
2. **Contraste extremo** — fundo escuro + animal claro + texto laranja/amarelo.
3. **Texto curto e grande** — máximo 3 palavras, fonte pesada, legível em mobile.
4. **Emoji como sinalizador visual** — 🐾🎷 ou 😴💤 para relaxamento.
5. **Variação A/B/C** com cores de alto CTR (vermelho, laranja, amarelo sobre fundo escuro).
6. **Elemento de curiosidade**: círculo discreto no canto superior direito para parar o scroll.
7. **Feedback loop**: `winning_thumbnail_variant()` lê `video_tags.json` + `analytics.json` e começa o próximo upload com a variante de maior média de views.

## 7. Funil de retenção

1. **Hook nos primeiros 5 segundos**: texto overlay do hook já aparece junto com o animal e a música.
2. **Legenda ASS animada**: palavras do hook aparecem palavra-a-palavra (karaoke) para prender atenção.
3. **End-card de sessão**: últimos 3s com CTA rotativo ("watch another to keep relaxing", "save this for bedtime").
4. **Playlists por problema e por animal**: Sleep, Anxiety, Home Alone, Thunder, For Cats, For Dogs.
5. **Long-form como âncora**: vídeos de 20-45min mantêm sessões longas e recomendações.

## 8. A/B testing e analytics

- **Thumbnails**: 3 variantes (A/B/C) geradas por vídeo; variante inicial escolhida por performance histórica.
- **Rotação reativa**: `collect_analytics.maybe_rotate_thumbnail()` troca A→B→C se views ficarem abaixo de 50% da mediana após 7 dias.
- **Vencedora global**: `utils/thumbnail_engine.winning_thumbnail_variant()` calcula média de views por variante.
- **Métricas coletadas**: ctr, averageViewPercentage, impressions, subscribersGained (YouTube Analytics API).
- **Modelo preditivo**: `scripts/predict_views.py` treina a partir de analytics + video_tags para prever views por cena/padrão/horário.
- **Feedback loop**: dados → `scene_performance.json`, `title_pattern_performance.json`, `publish_slots.json` → próximos vídeos.

## 9. Benchmarking — o que copiar dos maiores

### Canais de referência
- **Relax My Dog**: playlists por problema, títulos diretos, thumbnails com cachorro tranquilo.
- **Cat Music**: thumbnails com gato de olhos grandes, títulos de cauda longa.
- **MrBeast**: pattern interrupt, promessa clara, texto grande na thumbnail.
- **TikTok compilations**: ritmo rápido, hook imediato, legendas grandes.

### Padrões a copiar
- Título: [Promessa específica] + [Prova social/resultado] + [Emoji]
- Thumbnail: [Animal com olhar] + [Texto curto] + [Cor de alto CTR]
- Descrição: [Hook] + [Palavras-chave] + [Timestamps] + [Playlists] + [CTA]

## 10. Métricas de sucesso

| Métrica | Meta 30 dias | Meta 90 dias | Meta 1 ano |
|---|---|---|---|
| CTR médio | > 6% | > 8% | > 10% |
| Views/short (média) | > 100 | > 1.000 | > 10.000 |
| Retenção média (AVP) | > 45% | > 55% | > 65% |
| Inscritos/dia | > 10 | > 100 | > 1.000 |
| Long-form views | > 500 | > 5.000 | > 50.000 |
| Total views/mês | > 50K | > 500K | > 10M |

## 11. Implementação concluída

| Fase | Arquivos principais | Status |
|---|---|---|
| SEO títulos/descrições/hashtags | `utils/seo_keywords.py`, `utils/metadata_engine.py` | ✅ |
| Thumbnails A/B/C de alto CTR | `utils/thumbnail_engine.py` | ✅ |
| Publicação preditiva | `utils/publish_optimizer.py`, `.github/workflows/pata-jazz-shorts.yml`, `upload_youtube.py` | ✅ |
| A/B test + analytics | `scripts/collect_analytics.py`, `utils/thumbnail_engine.winning_thumbnail_variant()` | ✅ |
| Funil de retenção | `utils/video_builder.py`, `utils/caption_engine.py`, `utils/youtube_post_upload.py`, `utils/channel_config.py` | ✅ |
| Sinais virais enriquecidos | `scripts/collect_analytics.py`, `utils/content_strategy.py` | ✅ |

---

> "Não é automação. É uma redação global que nunca dorme." — Operação Zeus
