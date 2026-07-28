# Roadmap de Canais — Pata Jazz Network

O projeto já abstrai múltiplos canais via `utils/channel_config.py`. Este
documento define a ordem de ativação e os critérios para cada canal.

## Canais definidos

| Canal | Status | Nicho | Audio | Brand pronta |
|---|---|---|---|---|
| Pata Jazz | ✅ Ativo | Pets + Jazz | Jamendo (jazz) | Sim |
| Pata Lofi | ⏳ Pendente | Pets + Lofi | Jamendo (lofi) | Sim |
| Pata Classical | ⏳ Pendente | Pets + Classical | Jamendo (classical) | Sim |

## Ordem de ativação recomendada

### 1. Pata Lofi (próximo)
- **Por quê primeiro:** Maior overlap de assets com Pata Jazz (mesmos
  clipes de pets, mesma estrutura de Shorts/horizontais/live); só muda o
  áudio (lofi beats em vez de jazz) e a marca.
- **Pré-requisitos:**
  - Isolamento de `_data/<channel>/` (em andamento) para não contaminar
    pesos de performance entre canais.
  - OAuth multi-conta (`YOUTUBE_TOKEN_LOFI`).
  - `sync_jazz_music.py` parametrizado por canal (termos de busca lofi).
  - Workflows `pata-lofi-*.yml` espelhando os do Jazz.
- **Esforço estimado:** M (1-2 semanas).

### 2. Pata Classical (depois)
- **Por quê depois:** Classical exige pool de áudio diferente (piano,
  orchestra) e o nicho tem volume de busca menor que lofi.
- **Pré-requisitos:** Mesmos do Lofi, mais sync de áudio classical.
- **Esforço estimado:** M.

## Critérios para ativar um novo canal

1. **Abstração validada:** `channel_config.py` já define o canal; rodar
   `set_channel("<nome>")` em teste de integração.
2. **Isolamento de estado:** `_data/<channel>/` separado.
3. **OAuth do canal:** Token próprio no GitHub Secrets.
4. **Pool de áudio:** `sync_jazz_music.py` parametrizado.
5. **Workflows:** Cron espelhado dos 4 formatos (shorts, horizontal,
   live, sync).
6. **Dashboard:** Seletor de canal já implementado (cosmético).

## Monitoramento pós-ativação

- Acompanhar quota separada por canal (YouTube API tem 10k/dia por
  projeto OAuth, não por canal — compartilhar projeto exige cuidado).
- Dashboard: alternar entre canais via dropdown.
- Feedback loop: pesos de cena/padrão independentes por canal.