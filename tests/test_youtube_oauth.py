"""
Testes unitários para utils/youtube_oauth.py
"""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials

from utils.youtube_oauth import (
    ROOT,
    SCOPES,
    _client_secrets_path,
    _load_token,
    _save_token,
    _token_path,
    get_youtube_service,
    refresh_token_if_needed,
)


class TestYoutubeOauth:
    """Testes para o módulo youtube_oauth."""

    def test_token_path_default(self):
        """Testa caminho padrão do token (resolvido relativo ao ROOT do projeto)."""
        with patch.dict(os.environ, {}, clear=True):
            assert _token_path() == str(ROOT / "youtube_token.json")

    def test_token_path_from_env(self):
        """Testa caminho do token via variável de ambiente."""
        with patch.dict(os.environ, {"YOUTUBE_TOKEN_PATH": "/custom/path/token.json"}):
            assert _token_path() == "/custom/path/token.json"

    def test_load_token_nonexistent(self, tmp_path):
        """Testa carregamento de token inexistente."""
        with patch.dict(os.environ, {"YOUTUBE_TOKEN_PATH": str(tmp_path / "nonexistent.json")}):
            assert _load_token() is None

    def test_load_token_valid(self, tmp_path):
        """Testa carregamento de token válido."""
        token_data = {
            "token": "test_token",
            "refresh_token": "test_refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": SCOPES,
        }
        token_path = tmp_path / "token.json"
        token_path.write_text(json.dumps(token_data))

        with patch.dict(os.environ, {"YOUTUBE_TOKEN_PATH": str(token_path)}):
            creds = _load_token()
            assert creds is not None
            assert creds.token == "test_token"
            assert creds.refresh_token == "test_refresh"

    def test_load_token_invalid_json(self, tmp_path):
        """Testa carregamento de token com JSON inválido."""
        token_path = tmp_path / "invalid.json"
        token_path.write_text("invalid json")

        with patch.dict(os.environ, {"YOUTUBE_TOKEN_PATH": str(token_path)}):
            creds = _load_token()
            assert creds is None

    def test_save_token(self, tmp_path):
        """Testa salvamento de token."""
        token_path = tmp_path / "token.json"
        creds = MagicMock()
        creds.to_json.return_value = json.dumps({"token": "test"})

        with patch.dict(os.environ, {"YOUTUBE_TOKEN_PATH": str(token_path)}):
            _save_token(creds)
            assert token_path.exists()
            creds.to_json.assert_called_once()

    def test_client_secrets_path_from_env(self, tmp_path):
        """Testa caminho do client secrets via variável de ambiente."""
        secret_file = tmp_path / "secret.json"
        secret_file.write_text('{"web": {"client_id": "test"}}')

        with patch.dict(os.environ, {"YOUTUBE_CLIENT_SECRET_PATH": str(secret_file)}):
            assert _client_secrets_path() == str(secret_file)

    def test_client_secrets_path_from_env_content(self, tmp_path):
        """Testa client secrets via conteúdo da variável de ambiente."""
        secret_content = '{"web": {"client_id": "test"}}'

        with patch.dict(os.environ, {"YOUTUBE_CLIENT_SECRET": secret_content}):
            secrets_path = _client_secrets_path()
            assert secrets_path is not None
            assert Path(secrets_path).exists()
            assert Path(secrets_path).read_text() == secret_content
            # Limpa arquivo temporário
            Path(secrets_path).unlink(missing_ok=True)

    def test_client_secrets_path_not_found(self):
        """Testa quando client secrets não existe."""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(Path, "exists", return_value=False):
                assert _client_secrets_path() is None

    @patch("utils.youtube_oauth._load_token")
    @patch("utils.youtube_oauth._save_token")
    @patch("utils.youtube_oauth._client_secrets_path")
    @patch("utils.youtube_oauth.InstalledAppFlow")
    @patch("utils.youtube_oauth.build")
    def test_get_youtube_service_with_valid_token(self, mock_build, mock_flow, mock_secrets, mock_save, mock_load):
        """Testa obtenção do serviço YouTube com token válido."""
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_load.return_value = mock_creds
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        service = get_youtube_service()

        assert service == mock_service
        mock_build.assert_called_once_with("youtube", "v3", credentials=mock_creds, cache_discovery=False)
        mock_flow.assert_not_called()

    @patch("utils.youtube_oauth._load_token")
    @patch("utils.youtube_oauth._save_token")
    @patch("utils.youtube_oauth._client_secrets_path")
    @patch("utils.youtube_oauth.InstalledAppFlow")
    @patch("utils.youtube_oauth.build")
    def test_get_youtube_service_with_expired_token(
        self, mock_build, mock_flow, mock_secrets, mock_save, mock_load
    ):
        """Testa obtenção do serviço com token expirado que pode ser refresh."""
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "test_refresh"
        mock_load.return_value = mock_creds
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        service = get_youtube_service()

        assert service == mock_service
        mock_creds.refresh.assert_called_once()
        mock_save.assert_called_once_with(mock_creds)
        mock_flow.assert_not_called()

    @patch("utils.youtube_oauth._load_token")
    @patch("utils.youtube_oauth._save_token")
    @patch("utils.youtube_oauth._client_secrets_path")
    @patch("utils.youtube_oauth.InstalledAppFlow")
    @patch("utils.youtube_oauth.build")
    def test_get_youtube_service_with_new_flow(
        self, mock_build, mock_flow, mock_secrets, mock_save, mock_load
    ):
        """Testa obtenção do serviço com novo fluxo OAuth."""
        mock_load.return_value = None
        mock_secrets.return_value = "/path/to/secret.json"
        mock_flow_instance = MagicMock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_creds = MagicMock()
        mock_flow_instance.run_local_server.return_value = mock_creds
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        service = get_youtube_service()

        assert service == mock_service
        mock_flow.from_client_secrets_file.assert_called_once_with("/path/to/secret.json", SCOPES)
        mock_flow_instance.run_local_server.assert_called_once_with(port=0)
        mock_save.assert_called_once_with(mock_creds)

    @patch("utils.youtube_oauth._load_token")
    @patch("utils.youtube_oauth._client_secrets_path")
    def test_get_youtube_service_no_credentials(self, mock_secrets, mock_load):
        """Testa obtenção do serviço sem credenciais."""
        mock_load.return_value = None
        mock_secrets.return_value = None

        with pytest.raises(RuntimeError, match="Nenhuma credencial do YouTube encontrada."):
            get_youtube_service()

    @patch("utils.youtube_oauth._load_token")
    @patch("utils.youtube_oauth._save_token")
    @patch("utils.youtube_oauth._client_secrets_path")
    @patch("utils.youtube_oauth.InstalledAppFlow")
    def test_get_youtube_service_cleans_temp_file(
        self, mock_flow, mock_secrets, mock_save, mock_load, tmp_path, monkeypatch
    ):
        """Testa que arquivo temporário é removido após uso."""
        mock_load.return_value = None
        temp_dir = tmp_path / "tmp"
        temp_dir.mkdir()
        temp_path = temp_dir / "client_secret_test.json"
        mock_secrets.return_value = str(temp_path)
        mock_flow_instance = MagicMock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_creds = MagicMock()
        mock_flow_instance.run_local_server.return_value = mock_creds

        temp_path.write_text('{"web": {"client_id": "test"}}')
        monkeypatch.setattr("utils.youtube_oauth.tempfile.gettempdir", lambda: str(temp_dir))

        get_youtube_service()

        assert not temp_path.exists()

    @patch("utils.youtube_oauth.refresh_token_if_needed", return_value=False)
    @patch("utils.youtube_oauth._load_token")
    @patch("utils.youtube_oauth.build")
    def test_get_youtube_service_calls_refresh_token_if_needed(
        self, mock_build, mock_load, mock_refresh
    ):
        """get_youtube_service deve chamar refresh_token_if_needed antes de buildar o service."""
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_load.return_value = mock_creds
        mock_build.return_value = MagicMock()

        get_youtube_service()

        # refresh_token_if_needed foi chamado (com o caminho do token).
        mock_refresh.assert_called_once()
        mock_build.assert_called_once_with("youtube", "v3", credentials=mock_creds, cache_discovery=False)


class TestRefreshTokenIfNeeded:
    """Testes para refresh_token_if_needed."""

    def _write_token(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data))

    def test_no_expiry_no_refresh_token_returns_false(self, tmp_path):
        """Token sem expiry/refresh_token -> retorna False, nao tenta."""
        token_path = tmp_path / "token.json"
        self._write_token(token_path, {"token": "t"})
        assert refresh_token_if_needed(token_path) is False

    def test_missing_refresh_token_returns_false(self, tmp_path):
        """Token sem refresh_token -> retorna False (nao ha como renovar)."""
        token_path = tmp_path / "token.json"
        self._write_token(token_path, {"token": "t", "expiry": "2000-01-01T00:00:00Z"})
        assert refresh_token_if_needed(token_path) is False

    def test_missing_expiry_returns_false(self, tmp_path):
        """Token sem expiry -> retorna False (nao sabemos se precisa)."""
        token_path = tmp_path / "token.json"
        self._write_token(
            token_path,
            {"token": "t", "refresh_token": "r", "client_id": "cid", "client_secret": "csec"},
        )
        assert refresh_token_if_needed(token_path) is False

    def test_future_expiry_returns_false(self, tmp_path):
        """Token com expiry no futuro -> retorna False."""
        future = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        token_path = tmp_path / "token.json"
        self._write_token(
            token_path,
            {
                "token": "t",
                "refresh_token": "r",
                "client_id": "cid",
                "client_secret": "csec",
                "token_uri": "https://oauth2.googleapis.com/token",
                "expiry": future,
            },
        )
        with patch("utils.youtube_oauth.Credentials.refresh") as mock_refresh:
            assert refresh_token_if_needed(token_path) is False
            mock_refresh.assert_not_called()

    def test_past_expiry_triggers_refresh_and_saves(self, tmp_path):
        """Token com expiry no passado -> refresh, salva token, retorna True."""
        token_path = tmp_path / "token.json"
        self._write_token(
            token_path,
            {
                "token": "old",
                "refresh_token": "r",
                "client_id": "cid",
                "client_secret": "csec",
                "token_uri": "https://oauth2.googleapis.com/token",
                "expiry": "2000-01-01T00:00:00Z",
            },
        )
        refreshed_token_path = tmp_path / "token.json"

        def fake_refresh(self_creds, request):
            self_creds.token = "new_access_token"
            self_creds.expiry = datetime.now(UTC) + timedelta(hours=1)

        with patch.object(Credentials, "refresh", autospec=True, side_effect=fake_refresh) as mock_refresh:
            result = refresh_token_if_needed(refreshed_token_path)

        assert result is True
        mock_refresh.assert_called_once()
        # Token salvo de volta no disco com novo access_token.
        saved = json.loads(refreshed_token_path.read_text())
        assert saved["token"] == "new_access_token"

    def test_refresh_raises_returns_false(self, tmp_path, caplog):
        """Refresh levanta excecao -> loga warning, retorna False."""
        token_path = tmp_path / "token.json"
        self._write_token(
            token_path,
            {
                "token": "old",
                "refresh_token": "r",
                "client_id": "cid",
                "client_secret": "csec",
                "token_uri": "https://oauth2.googleapis.com/token",
                "expiry": "2000-01-01T00:00:00Z",
            },
        )
        with patch.object(Credentials, "refresh", autospec=True, side_effect=RuntimeError("boom")):
            with caplog.at_level("WARNING"):
                result = refresh_token_if_needed(token_path)
        assert result is False
        assert any("falha ao renovar" in rec.message.lower() for rec in caplog.records)

    def test_nonexistent_file_returns_false(self, tmp_path):
        """Arquivo inexistente -> retorna False."""
        assert refresh_token_if_needed(tmp_path / "nope.json") is False

    def test_invalid_json_returns_false(self, tmp_path, caplog):
        """JSON invalido -> loga warning, retorna False."""
        token_path = tmp_path / "token.json"
        token_path.write_text("not json")
        with caplog.at_level("WARNING"):
            assert refresh_token_if_needed(token_path) is False
        assert any("nao foi ler" in rec.message.lower() for rec in caplog.records)

    def test_aware_timezone_expiry_handled(self, tmp_path):
        """Expiry com timezone offset (nao-Z) deve ser tratado sem TypeError."""
        token_path = tmp_path / "token.json"
        self._write_token(
            token_path,
            {
                "token": "t",
                "refresh_token": "r",
                "client_id": "cid",
                "client_secret": "csec",
                "token_uri": "https://oauth2.googleapis.com/token",
                "expiry": "2000-01-01T00:00:00+00:00Z",
            },
        )
        # from_authorized_user_info falha a parsear esse formato nesta versao
        # do google-auth; refresh_token_if_needed deve tratar graciosamente.
        assert refresh_token_if_needed(token_path) is False
