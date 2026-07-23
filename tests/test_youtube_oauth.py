"""
Testes unitários para utils/youtube_oauth.py
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.youtube_oauth import (
    SCOPES,
    _client_secrets_path,
    _load_token,
    _save_token,
    _token_path,
    get_youtube_service,
)


class TestYoutubeOauth:
    """Testes para o módulo youtube_oauth."""

    def test_token_path_default(self):
        """Testa caminho padrão do token."""
        with patch.dict(os.environ, {}, clear=True):
            assert _token_path() == "youtube_token.json"

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
    def test_get_youtube_service_cleans_temp_file(self, mock_flow, mock_secrets, mock_save, mock_load):
        """Testa que arquivo temporário é removido após uso."""
        mock_load.return_value = None
        temp_path = tempfile.mktemp(prefix="client_secret_")
        mock_secrets.return_value = temp_path
        mock_flow_instance = MagicMock()
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance
        mock_creds = MagicMock()
        mock_flow_instance.run_local_server.return_value = mock_creds

        # Cria arquivo temporário para simular
        Path(temp_path).write_text('{"web": {"client_id": "test"}}')

        try:
            get_youtube_service()
        except Exception:
            pass  # Ignora erros, só queremos testar limpeza

        # Verifica se arquivo temporário foi removido
        assert not Path(temp_path).exists()
