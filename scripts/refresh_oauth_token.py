"""
scripts/refresh_oauth_token.py — renova o token OAuth do YouTube em CI.

Le o token OAuth de youtube_token.json (escrito a partir do secret
YOUTUBE_TOKEN por .github/actions/restore-token-and-cache), tenta renovar
o access_token via Credentials.refresh(Request()), e se o refresh
funcionar escreve o novo token de volta no secret YOUTUBE_TOKEN usando
`gh secret set` (requer um Personal Access Token com scope `repo` no
secret GH_PAT).

Se o refresh falhar (refresh_token expirado — 90 dias sem uso, padrao do
Google), abre uma issue no repositorio pedindo para rodar
`python utils/youtube_oauth.py` localmente.

Este script NAO roda localmente (a renovacao local ja e automatica em
utils/youtube_oauth.get_youtube_service). Ele e feito para rodar dentro
do workflow .github/workflows/oauth-token-refresh.yml, que precisa do
secret GH_PAT configurado.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from google.auth.transport.requests import Request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.channel_config import CHANNELS, set_channel_from_env
from utils.youtube_oauth import _load_token, _save_token


def _secret_name(channel_slug: str) -> str:
    """Retorna o nome do secret de token para o canal (ex: YOUTUBE_TOKEN_LOFI)."""
    if channel_slug == "pata_jazz":
        return "YOUTUBE_TOKEN"
    return f"YOUTUBE_TOKEN_{channel_slug.split('_', 1)[1].upper()}"


def _token_filename(channel_slug: str) -> str:
    """Retorna o nome do arquivo de token no runner para o canal."""
    if channel_slug == "pata_jazz":
        return "youtube_token.json"
    return f"youtube_token_{channel_slug.split('_', 1)[1].lower()}.json"


def refresh_and_persist(token_path: Path, secret_name: str, channel_slug: str) -> int:
    """Tenta renovar o token; se conseguir, atualiza o secret correspondente.

    Retorna 0 se renovou e atualizou o secret; 1 se o refresh falhou (e
    abriu issue); 2 se nao ha token para renovar.
    """
    creds = _load_token()
    if creds is None:
        print(f"::error::Nenhum token OAuth encontrado ({secret_name} nao setado?).")
        return 2
    if not creds.refresh_token:
        print("::error::Token sem refresh_token — nao e possivel renovar automaticamente.")
        return 2

    try:
        creds.refresh(Request())
    except Exception as exc:
        print(f"::error::Refresh do token falhou (refresh_token expirado?): {exc}")
        _open_issue_token_expired(str(exc), channel_slug)
        return 1

    try:
        _save_token(creds, str(token_path))
    except Exception as exc:
        print(f"::warning::Token renovado mas falhou ao salvar em disco: {exc}")

    new_token_json = creds.to_json()
    gh_pat = os.environ.get("GH_PAT")
    if not gh_pat:
        print("::error::GH_PAT ausente: nao e possivel atualizar o secret automaticamente.")
        print("::error::Configure um Personal Access Token com scope 'repo' como secret GH_PAT.")
        _open_issue_token_expired("GH_PAT ausente — configure o secret GH_PAT.", channel_slug)
        return 1

    rc = _gh_secret_set(secret_name, new_token_json, gh_pat)
    if rc != 0:
        print(f"::error::gh secret set {secret_name} falhou (rc={rc}).")
        return 1

    print(f"::notice::Token OAuth ({channel_slug}) renovado e secret {secret_name} atualizado.")
    return 0


def _gh_secret_set(name: str, value: str, gh_pat: str) -> int:
    """Atualiza um secret do repositorio via `gh secret set`."""
    cmd = ["gh", "secret", "set", name, "--body", value]
    env = {**os.environ, "GH_TOKEN": gh_pat}
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"::error::gh secret set stderr: {proc.stderr}")
    return proc.returncode


def _open_issue_token_expired(reason: str, channel_slug: str) -> None:
    """Abre uma issue pedindo renovacao manual do token OAuth."""
    gh_pat = os.environ.get("GH_PAT")
    if not gh_pat:
        print("::warning::GH_PAT ausente: nao e possivel abrir issue automaticamente.")
        print("::warning::Abra manualmente uma issue: 'Token OAuth expirado'.")
        return

    channel_name = CHANNELS[channel_slug].name if channel_slug in CHANNELS else channel_slug
    title = f"Token OAuth expirado — {channel_name}"
    body = (
        f"O refresh do token OAuth do {channel_name} falhou no workflow "
        f"`oauth-token-refresh.yml`:\n\n```\n"
        f"{reason}\n```\n\n"
        "Para renovar:\n"
        "1. Rode `python utils/youtube_oauth.py` localmente "
        "(com `YOUTUBE_CLIENT_SECRET` apontando para o `client_secret.json`).\n"
        f"2. Atualize o secret `{_secret_name(channel_slug)}` no GitHub com o conteudo do "
        "`youtube_token.json` gerado.\n\n"
        "Aviso: o workflow `oauth-token-refresh.yml` requer um Personal Access "
        "Token (PAT) com scope `repo` armazenado como secret `GH_PAT` para "
        "atualizar os secrets automaticamente. Sem o `GH_PAT`, "
        "a renovacao do token e sempre manual."
    )
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    env = {**os.environ, "GH_TOKEN": gh_pat}
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"::warning::gh issue create falhou: {proc.stderr}")
    else:
        print(f"::notice::Issue criada: {proc.stdout.strip()}")


def main() -> int:
    set_channel_from_env()
    channel_slug = os.environ.get("YOUTUBE_CHANNEL", "pata_jazz").lower()
    token_path = Path(os.environ.get("YOUTUBE_TOKEN_PATH", str(ROOT / _token_filename(channel_slug))))
    if not token_path.exists():
        print(f"::error::{token_path} nao encontrado (secret {_secret_name(channel_slug)} ausente?).")
        return 2
    return refresh_and_persist(token_path, _secret_name(channel_slug), channel_slug)


if __name__ == "__main__":
    sys.exit(main())
