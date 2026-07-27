# Self-hosted runner para a live 24/7

## Por que

O runner gratuito do GitHub Actions cai a cada ~2.8 min em média durante uma
sessão de live longa (~125 reconexões de FFmpeg registradas por sessão na live
24/7 atual). Cada reconexão gera um buraco curto sem vídeo no stream, o que
derruba `concurrentViewers` e prejudica o algoritmo do YouTube. Um runner
self-hosted elimina essa instabilidade: o processo roda em uma máquina que
você controla, sem os limites de 360 min/job e sem as quedas arbitrárias do
runner efêmero.

## Setup (Ubuntu 22.04 ou 24.04)

Usa um Droplet pequeno da DigitalOcean (ou equivalente) como referência.

### 1. Instalar Docker (opcional, para isolamento)

Útil se quiser rodar o runner dentro de um container em vez de bare-metal:

```bash
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl enable --now docker
```

### 2. Registrar o runner

No repositório: **Settings → Actions → Runners → New self-hosted runner**.
Siga as instruções exibidas para Linux x64 (baixar `actions-runner-linux-x64`,
extrair, rodar `./config.sh` com o token exibido).

### 3. Labels recomendadas

Configure o runner com as labels:

```
self-hosted, linux, x64, live
```

A label `live` garante que **só** o workflow da live use esse runner — os
demais workflows continuam em `ubuntu-latest` e não disputam a máquina.

### 4. Instalar como serviço

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

## Custo

| Opção | Custo | Confiabilidade |
|-------|-------|----------------|
| Runner gratuito do GHA | grátis | instável (~125 reconexões/sessão) |
| Droplet 2 vCPU / 4 GB | ~$12/mês | estável (sem quedas arbitrárias) |

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