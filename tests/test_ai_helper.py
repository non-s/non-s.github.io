"""Testes para ai_helper.py."""
import pytest
from unittest.mock import patch, MagicMock
import utils.ai_helper as ai_helper


class TestAiHelper:
    """Testes para ai_helper."""
    
    def test_default_system_prompt(self):
        """Testa que o prompt padrão contém as instruções corretas."""
        prompt = ai_helper._default_system_prompt()
        
        assert "Pata Jazz" in prompt
        assert "portugues do Brasil" in prompt
        assert "gatos e cachorros" in prompt
        assert "clickbait" in prompt
    
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_no_api_key(self, mock_env):
        """Testa que ai_text retorna string vazia sem API key."""
        mock_env.get.return_value = ""
        
        result = ai_helper.ai_text("test prompt")
        
        assert result == ""
    
    @patch('utils.ai_helper._gemini_circuit_open', True)
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_circuit_breaker_open(self, mock_env):
        """Testa que ai_text retorna string vazia com circuit breaker aberto."""
        mock_env.get.return_value = "fake_key"
        
        result = ai_helper.ai_text("test prompt")
        
        assert result == ""
    
    @patch('utils.ai_helper._session')
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_success(self, mock_env, mock_session):
        """Testa chamada bem-sucedida ao Gemini."""
        mock_env.get.return_value = "fake_key"
        
        # Mock da resposta
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Texto gerado pelo Gemini"}]
                }
            }]
        }
        mock_session.post.return_value = mock_response
        
        result = ai_helper.ai_text("test prompt", task="test")
        
        assert result == "Texto gerado pelo Gemini"
        mock_session.post.assert_called_once()
    
    @patch('utils.ai_helper._session')
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_json_mode(self, mock_env, mock_session):
        """Testa chamada ao Gemini com json_mode=True."""
        mock_env.get.return_value = "fake_key"
        
        # Mock da resposta
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": '{"title": "Test"}'}]
                }
            }]
        }
        mock_session.post.return_value = mock_response
        
        result = ai_helper.ai_text("test prompt", json_mode=True)
        
        assert result == '{"title": "Test"}'
        # Verifica se responseMimeType foi definido
        call_args = mock_session.post.call_args
        assert call_args[1]["json"]["generationConfig"]["responseMimeType"] == "application/json"
    
    @patch('utils.ai_helper.sleep')
    @patch('utils.ai_helper._session')
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_429_retry(self, mock_env, mock_session, mock_sleep):
        """Testa retry com backoff exponencial para erro 429."""
        mock_env.get.return_value = "fake_key"
        
        # Mock das respostas: 429, 429, sucesso
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.raise_for_status.side_effect = Exception("429 Too Many Requests")
        
        mock_response_success = MagicMock()
        mock_response_success.raise_for_status.return_value = None
        mock_response_success.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Sucesso após retry"}]
                }
            }]
        }
        
        mock_session.post.side_effect = [
            Exception("429"),  # Primeira tentativa falha
            Exception("429"),  # Segunda tentativa falha
            mock_response_success  # Terceira tentativa sucesso
        ]
        
        result = ai_helper.ai_text("test prompt")
        
        assert result == "Sucesso após retry"
        assert mock_session.post.call_count == 3
        assert mock_sleep.call_count >= 2  # Deve ter dormido entre retries
    
    @patch('utils.ai_helper._session')
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_timeout_retry(self, mock_env, mock_session):
        """Testa retry para timeout."""
        mock_env.get.return_value = "fake_key"
        
        import requests
        
        # Mock: timeout na primeira, sucesso na segunda
        mock_session.post.side_effect = [
            requests.exceptions.Timeout("Connection timed out"),
            MagicMock(
                raise_for_status=lambda: None,
                json=lambda: {
                    "candidates": [{
                        "content": {
                            "parts": [{"text": "Sucesso após timeout"}]
                        }
                    }]
                }
            )
        ]
        
        result = ai_helper.ai_text("test prompt")
        
        assert result == "Sucesso após timeout"
        assert mock_session.post.call_count == 2
    
    @patch('utils.ai_helper._session')
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_connection_error_retry(self, mock_env, mock_session):
        """Testa retry para connection error."""
        mock_env.get.return_value = "fake_key"
        
        import requests
        
        # Mock: connection error na primeira, sucesso na segunda
        mock_session.post.side_effect = [
            requests.exceptions.ConnectionError("Connection refused"),
            MagicMock(
                raise_for_status=lambda: None,
                json=lambda: {
                    "candidates": [{
                        "content": {
                            "parts": [{"text": "Sucesso após connection error"}]
                        }
                    }]
                }
            )
        ]
        
        result = ai_helper.ai_text("test prompt")
        
        assert result == "Sucesso após connection error"
        assert mock_session.post.call_count == 2
    
    @patch('utils.ai_helper._session')
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_http_error_non_429(self, mock_env, mock_session):
        """Testa que outros erros HTTP não fazem retry."""
        mock_env.get.return_value = "fake_key"
        
        import requests
        
        # Mock: HTTP 500 error (não é 429)
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500
        mock_response_error.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Internal Server Error")
        
        mock_session.post.return_value = mock_response_error
        
        result = ai_helper.ai_text("test prompt")
        
        assert result == ""
        # Deve ter tentado apenas uma vez
        assert mock_session.post.call_count == 1
    
    @patch('utils.ai_helper._session')
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_max_retries_exceeded(self, mock_env, mock_session):
        """Testa que retorna string vazia após exceder retries."""
        mock_env.get.return_value = "fake_key"
        
        import requests
        
        # Mock: sempre falha
        mock_session.post.side_effect = requests.exceptions.Timeout("Always timeout")
        
        result = ai_helper.ai_text("test prompt")
        
        assert result == ""
        # Deve ter tentado 3 vezes (MAX_RETRIES)
        assert mock_session.post.call_count == 3
    
    @patch('utils.ai_helper._session')
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_with_custom_system_prompt(self, mock_env, mock_session):
        """Testa chamada com system prompt personalizado."""
        mock_env.get.return_value = "fake_key"
        
        # Mock da resposta
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Resposta com prompt customizado"}]
                }
            }]
        }
        mock_session.post.return_value = mock_response
        
        custom_system = "Prompt personalizado para teste"
        result = ai_helper.ai_text("test prompt", system=custom_system)
        
        assert result == "Resposta com prompt customizado"
        # Verifica se o system prompt personalizado foi usado
        call_args = mock_session.post.call_args
        assert call_args[1]["json"]["systemInstruction"]["parts"][0]["text"] == custom_system
    
    @patch('utils.ai_helper._session')
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_empty_response(self, mock_env, mock_session):
        """Testa que retorna string vazia quando resposta está vazia."""
        mock_env.get.return_value = "fake_key"
        
        # Mock da resposta vazia
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": ""}]
                }
            }]
        }
        mock_session.post.return_value = mock_response
        
        result = ai_helper.ai_text("test prompt")
        
        assert result == ""
    
    @patch('utils.ai_helper._session')
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_malformed_response(self, mock_env, mock_session):
        """Testa que retorna string vazia quando resposta está mal formatada."""
        mock_env.get.return_value = "fake_key"
        
        # Mock da resposta mal formatada
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "candidates": []  # Sem conteúdo
        }
        mock_session.post.return_value = mock_response
        
        result = ai_helper.ai_text("test prompt")
        
        assert result == ""
    
    @patch('utils.ai_helper._session')
    @patch('utils.ai_helper.os.environ')
    def test_ai_text_with_custom_timeout(self, mock_env, mock_session):
        """Testa chamada com timeout personalizado."""
        mock_env.get.return_value = "fake_key"
        
        # Mock da resposta
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Resposta com timeout customizado"}]
                }
            }]
        }
        mock_session.post.return_value = mock_response
        
        result = ai_helper.ai_text("test prompt", timeout=60)
        
        assert result == "Resposta com timeout customizado"
        # Verifica se timeout foi passado
        call_args = mock_session.post.call_args
        assert call_args[1]["timeout"] == 60
