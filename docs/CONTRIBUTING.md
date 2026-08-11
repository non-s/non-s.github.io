# Contribuindo para o Pata Jazz

Obrigado por contribuir! Este documento cobre setup local, testes, convenções
 e boas práticas para novos workflows. Para visão geral da arquitetura, veja
[ARCHITECTURE.md](./ARCHITECTURE.md).

## Setup local

### 1. Dependências

```bash
pip install -r requirements-dev.txt   # inclui ruff, pytest, pytest-cov, mypy, bandit, pip-audit
pre-commit install                    # hooks de lint/format/typecheck a cada commit
```

### 2. FFmpeg

Instale o **FFmpeg** (com `ffprobe`) e garanta que ambos estão no `PATH`:

- Windows: `winget install Gyan.FFmpeg` ou baixe de <https://www.gyan.dev/ffmpeg/builds/>
- macOS: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

Verifique com `ffmpeg -version` e `ffprobe -version`.

### 3. Variáveis de ambiente

Crie um arquivo `.env` (ou exporte manualmente) com:

```bash
GEMINI_API_KEY=xxx
PIXABAY_API_KEY=xxx
JAMENDO_CLIENT_ID=xxx        # opcional (recomendado)
GEMINI_MODEL=gemini-2.0-flash-001  # opcional (default)
YOUTUBE_PRIVACY=public
```

### 4. Credenciais do YouTube

Para upload é necessário um token OAuth. Rode uma vez:

```bash
python utils/youtube_oauth.py
# Salve o JSON resultante como o secret YOUTUBE_TOKEN no GitHub Actions.
```

Localmente, `utils/youtube_oauth.py` salva `youtube_token.json` na raiz.

## Rodar testes e lint

O projeto usa um `Makefile` com os atalhos mais comuns:

```bash
make test         # pytest -q
make test-cov     # pytest -q --cov --cov-report=term-missing
make lint         # ruff check .
make format       # ruff format . && ruff check --fix .
make typecheck    # mypy
make security     # bandit -ll + pip-audit
make healthcheck  # python scripts/healthcheck.py
make sync         # sync b-roll + jazz
make clean        # remove caches e artefatos
make all          # lint test typecheck
```

Antes de abrir um PR, rode pelo menos `make lint test`.

### Higiene de mídia e histórico

Nunca versione MP3/MP4/MOV/WebM gerado ou baixado. `_assets/audio`,
`_assets/video` e `_videos` existem apenas no workspace/cache. O CI também
bloqueia qualquer arquivo rastreado acima de 10 MB para impedir que o histórico
volte a crescer com artefatos que deveriam permanecer fora do Git.

## Pre-commit hooks

Após `pre-commit install`, os hooks rodam automaticamente a cada commit:

- `ruff --fix` + `ruff-format` (lint e formatação)
- `mypy` (typecheck — advisory, não bloqueia se houver ruído de stubs)
- `check-merge-conflict`, `check-yaml`, `end-of-file-fixer`, `trailing-whitespace`

Para rodar manualmente em todos os arquivos:

```bash
pre-commit run --all-files
```

## Convenção de commits

Use [Conventional Commits](https://www.conventionalcommits.org/) em português/inglês:

| Tipo | Quando usar |
|------|-------------|
| `feat:` | Nova funcionalidade |
| `fix:` | Correção de bug |
| `security:` | Correção de vulnerabilidade |
| `refactor:` | Refatoração sem mudança de comportamento |
| `docs:` | Apenas documentação |
| `chore:` | Tarefas de manutenção (deps, CI, etc) |

Exemplos:

```
feat: adicionar wrapper de quota em retry_youtube_call
fix: corrigir corrida no lock de estado do analytics
security: atualizar Pillow para 12.3
docs: documentar fluxo de dados em ARCHITECTURE.md
chore: pin actions por SHA
```

> **Nota:** o workflow `release.yml` gera release notes semanais a partir dos
> commits `feat:`/`fix:`/`security:` — use o prefixo correto para que sua
> mudança apareça no changelog automático.

## Como adicionar um workflow novo

Checklist para criar `.github/workflows/<novo>.yml`:

- [ ] **`concurrency:`** com `group:` único e `cancel-in-progress:` definido
      (evita runs sobrepostos que competem pelo mesmo estado em `_data/`).
- [ ] **`permissions:`** mínimas — só o que o workflow precisa
      (`contents: read` por default; `issues: write` só se abrir issue;
      `actions: write` só se manipular caches).
- [ ] **`persist-credentials: false`** no `actions/checkout` (evita vazar
      `GITHUB_TOKEN` no config do git dentro do runner).
- [ ] **Pin actions por SHA** — `actions/checkout@<sha> # v4`, nunca `@v4`
      direto (supply chain). O SHA está nos workflows existentes como referência.
- [ ] **`timeout-minutes:`** definido (job zombie consome quota do runner).
- [ ] **Cleanup de token** — se o workflow escreve `youtube_token.json`,
      adicione um step final `if: always()` com `rm -f youtube_token.json`.
- [ ] **Cron em UTC** — comente no YAML o equivalente em BRT (UTC-3).
- [ ] **Restaurar caches** via `.github/actions/restore-token-and-cache` se o
      workflow lê/escreve estado em `_data/`.

## Onde adicionar testes

- **Localização:** `tests/test_<modulo>.py` (espelha a estrutura de `utils/` e
  `scripts/`).
- **Mocks:** sempre mockar rede (Gemini, Pixabay, Jamendo, YouTube API),
  FFmpeg (`subprocess.run`) e chamadas de IA — nenhum teste deve fazer chamada
  real de rede ou depender de FFmpeg instalado.
- **`tmp_path`:** use a fixture `tmp_path` para qualquer arquivo de estado —
  nunca escreva em `_data/` real a partir de testes.
- **`monkeypatch`:** para mudar `QUOTA_FILE`, `LAST_HEALTH_FILE`, etc. sem
  afetar outros testes (os defaults de função são avaliados na definição,
  então use `monkeypatch.setattr` no atributo do módulo).
- **Cobertura:** o alvo é ≥85% em `utils/` (ver `[tool.coverage.report]` em
  `pyproject.toml`). Testes novos devem cobrir os caminhos de erro, não só
  o happy path.

## Execução local útil

```bash
python scripts/healthcheck.py                 # verifica ambiente
python scripts/sync_animal_broll.py            # baixa clipes
python scripts/sync_jazz_music.py              # baixa músicas
python generate_pata_jazz_short.py --dry-run   # simula sem FFmpeg
python scripts/collect_analytics.py            # coleta métricas
python scripts/generate_dashboard.py           # gera dashboard HTML
python scripts/predict_views.py                # treina modelo de previsão
```

## Setup de novo canal (novo YouTube)

### 1. Criar projeto no Google Cloud Console

1. Acesse <https://console.cloud.google.com/> e crie um projeto (ex: `pata-jazz`).
2. Ative as APIs: **YouTube Data API v3** e **YouTube Analytics API v2**.
3. Configure a **OAuth consent screen** (External, app name = Pata Jazz).
4. Adicione os scopes:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube.force-ssl`
   - `https://www.googleapis.com/auth/yt-analytics.readonly`
5. Crie uma credencial **OAuth client ID** (tipo: Desktop app).
6. Baixe o `client_secret.json`.

### 2. Gerar token OAuth

```bash
# Localmente, com client_secret.json na raiz do projeto:
export YOUTUBE_CLIENT_SECRET_PATH=./client_secret.json
python utils/youtube_oauth.py
# Abre browser, autorize com a conta do novo canal, copia o JSON salvo.
```

### 3. Configurar secrets no GitHub

```bash
gh secret set YOUTUBE_TOKEN < youtube_token.json
gh secret set GEMINI_API_KEY --body "sua-key"
gh secret set PIXABAY_API_KEY --body "sua-key"
gh secret set JAMENDO_CLIENT_ID --body "sua-key"
gh secret set GH_PAT --body "seu-pat-com-scope-repo"  # para renovar token automaticamente
```

### 4. Configurar variables no GitHub

```bash
gh variable set PATA_JAZZ_ENABLED --body "1"
gh variable set PATA_JAZZ_SHORTS_ENABLED --body "1"
gh variable set PATA_JAZZ_LONG_ENABLED --body "1"
gh variable set PATA_JAZZ_COMMENTS_ENABLED --body "1"
gh variable set PATA_JAZZ_IDENTITY_ENABLED --body "1"
gh variable set YOUTUBE_PRIVACY --body "public"
```

### 5. Limpar caches antigos (se reusando o repo)

```bash
# Deleta todos os caches do GitHub Actions (dados do canal antigo)
gh cache list --limit 100 | tail -n +2 | awk '{print $1}' | xargs -I{} gh cache delete {}
```

### 6. Disparar primeiro upload

```bash
gh workflow run "Pata Jazz - Shorts" --ref main
```

O canal novo publica imediatamente (sem agendamento) até acumular ≥10
amostras em `publish_slots.json`. Os primeiros 10 uploads priorizam cenas
universalmente fofas (kitten, puppy, sleepy cat) para causar boa primeira
impressão no algoritmo do YouTube.
