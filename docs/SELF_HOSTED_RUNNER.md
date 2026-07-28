# Self-hosted runner para a live 24/7

## Por que

O runner gratuito do GitHub Actions cai a cada ~2.8 min em média durante uma
sessão de live longa (~125 reconexões de FFmpeg registradas por sessão na live
24/7 atual). Cada reconexão gera um buraco curto sem vídeo no stream, o que
derruba `concurrentViewers` e prejudica o algoritmo do YouTube. Um runner
self-hosted elimina essa instabilidade: o processo roda em uma máquina que
você controla, sem os limites de 360 min/job e sem as quedas arbitrárias do
runner efêmero.

### Por que 1080p live exige self-hosted

O runner gratuito do GitHub Actions (2 vCPU) não consegue codificar 1080p em
tempo real: medido em produção, o encode de `libx264 -preset ultrafast` a
1080p30 cai para ~0.43x (menos de metade da velocidade necessária), os frames
acumulam e a conexão RTMP quebra em menos de 1 minuto. Por isso o live
workflow hoje força `1280x720` (720p) — ver o cap em `generate_pata_jazz_live.py`:

```python
if w >= 1920:
    log.warning("Resolucao %sx%s nao e suportada no runner gratuito do GitHub Actions "
                "(encode nao acompanha o tempo real). Usando 1280x720.", w, h)
    w, h = 1280, 720
```

720p tem ~2.25x menos pixels por frame que 1080p, dando folga real de CPU.
Um self-hosted com CPU dedicada (≥4 vCPU) codifica 1080p30 em tempo real sem
queda, eliminando esse cap. O comentário sobre o cap de 720p deve ser
atualizado no live workflow (`pata-jazz-youtube-live.yml`) ao migrar para
self-hosted — ver "Remover o cap de 720p" abaixo.

## Setup (Ubuntu 22.04 ou 24.04)

Usa um Droplet pequeno da DigitalOcean (ou equivalente) como referência.

> Para 1080p live, prefira uma instância com ≥4 vCPU e ≥8 GB RAM (ex.:
> DigitalOcean Premium AMD 4 vCPU / 8 GB, ~$48/mês). 2 vCPU/4 GB serve para
> 720p estável mas não tem folga para 1080p em tempo real.

### 1. Instalar Docker (opcional, para isolamento)

Útil se quiser rodar o runner dentro de um container em vez de bare-metal:

```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl enable --now docker
```

### 2. Instalar FFmpeg (necessário para a live)

A live usa FFmpeg (`libx264` + `aac`) para codificar o stream RTMP. O FFmpeg
dos repositórios do Ubuntu é suficiente (não precisa de build custom):

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
# Confirma que o encoder libx264 está disponível:
ffmpeg -encoders | grep libx264
```

### 3. Registrar o runner

No repositório: **Settings → Actions → Runners → New self-hosted runner**.
Siga as instruções exibidas para Linux x64 (baixar `actions-runner-linux-x64`,
extrair, rodar `./config.sh` com o token exibido).

### 4. Labels recomendadas

Configure o runner com as labels:

```
self-hosted, linux, x64, live
```

A label `live` garante que **só** o workflow da live use esse runner — os
demais workflows continuam em `ubuntu-latest` e não disputam a máquina.

### 5. Instalar como serviço

```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

Isso reinicia o runner automaticamente em boot/crash.

## Secrets

Os secrets do GitHub Actions são **por repositório, não por runner**. Os
secret já configurados (`GEMINI_API_KEY`, `PIXABAY_API_KEY`,
`JAMENDO_CLIENT_ID`, `YOUTUBE_TOKEN`) ficam disponíveis para o runner
self-hosted sem nenhuma configuração extra — basta o runner estar registrado
no mesmo repositório.

## Migrar o workflow da live

Em `.github/workflows/pata-jazz-youtube-live.yml`, troque:

```yaml
runs-on: ubuntu-latest
timeout-minutes: 355
```

por:

```yaml
runs-on: [self-hosted, live]
timeout-minutes: 1440
```

`1440` (24h) permite uma única sessão contínua em vez de 4 sessões encadeadas
de ~6h. O runner self-hosted não tem o hard cap de 360 min dos runners
gratuitos.

Ajuste também o default de duração da sessão:

```yaml
env:
  LIVE_DURATION_MINUTES: ${{ github.event.inputs.duration_minutes || '1380' }}
```

`1380` (23h) deixa ~1h de folga antes do `timeout-minutes: 1440` para os steps
finais (sync de assets, preparo do loop, limpeza). Com isso a live roda **uma
sessão por dia** em vez de 4 sessões de 6h, eliminando os handoffs e as
reconexões entre elas.

### Remover o cap de 720p (1080p em self-hosted)

Ao usar `runs-on: [self-hosted, live]`, o cap de 720p em
`generate_pata_jazz_live.py` (e no input `resolution` do workflow) deixa de
fazer sentido — o self-hosted tem CPU suficiente para 1080p em tempo real.
No workflow, amplie a opção de resolução do `workflow_dispatch`:

```yaml
inputs:
  resolution:
    description: "Resolucao da live (self-hosted suporta 1080p)"
    required: false
    default: "1920x1080"
    type: choice
    options:
      - "1920x1080"
      - "1280x720"
```

E em `generate_pata_jazz_live.py`, adicione um comentário no cap de 720p
indicando que ele só se aplica ao runner gratuito (não ao self-hosted):

```python
if w >= 1920:
    # Cap de 720p: o runner gratuito do GitHub Actions (2 vCPU) nao codifica
    # 1080p em tempo real. Em self-hosted (runs-on: [self-hosted, live]) com
    # >=4 vCPU, remova este cap e use 1920x1080 (LIVE_RESOLUTION default).
    log.warning("Resolucao %sx%s nao e suportada no runner gratuito do GitHub Actions "
                "(encode nao acompanha o tempo real). Usando 1280x720.", w, h)
    w, h = 1280, 720
```

> Não modifique o workflow nem o script automaticamente — faça a troca
> manualmente após registrar o runner e validar que 1080p codifica estável
> (speed >= 1.0x por alguns minutos em `_wait_ffmpeg_stream`).

## Custo

| Opção | Custo | Confiabilidade | Resolução |
|-------|-------|----------------|-----------|
| Runner gratuito do GHA | grátis | instável (~125 reconexões/sessão) | 720p (cap) |
| Droplet 2 vCPU / 4 GB | ~$12/mês | estável (sem quedas arbitrárias) | 720p |
| Droplet 4 vCPU / 8 GB | ~$48/mês | estável | 1080p |

## Riscos e mitigações

Um runner self-hosted **executa código do repositório na sua máquina**. Se o
repo for público, qualquer PR pode disparar código arbitrário no servidor.

Mitigações:

- **Usar `environment` com required reviewers**: configure o job da live em
  um `environment` (ex.: `live-prod`) com reviewers aprovados. PRs de
  terceiros não rodam no runner até um maintainer aprovar o deploy.
- **Manter o repo privado**: se não houver motivo para público, tornar o repo
  privado bloqueia PRs externos por padrão.
- **Isolamento via Docker**: rodar o runner dentro de um container limita o
  impacto de código malicioso (não é sandbox perfeito, mas reduz a
  superfície).

O workflow da live já usa `workflow_dispatch` (manual) e `schedule` (cron),
não `pull_request`, então PRs não disparam a live por padrão — mas vale
revisar os demais workflows se algum escutar `pull_request`.