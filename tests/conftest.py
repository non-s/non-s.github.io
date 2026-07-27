"""Insere o diretorio raiz do projeto no inicio do sys.path para evitar conflitos."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def youtube_service_mock():
    """MagicMock configuravel representando um youtube.Service.

    Padrao: liveBroadcasts().list().execute retorna um broadcast com
    status.streamStatus='active' e boundStreamId definido. Testes podem
    sobrescrever .return_value ou .side_effect conforme necessario.

    Uso:
        def test_foo(youtube_service_mock):
            youtube_service_mock.liveBroadcasts().list().execute.return_value = {...}
    """
    service = MagicMock()
    service.liveBroadcasts.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "bc123",
                "status": {"lifeCycleStatus": "live", "privacyStatus": "public"},
                "contentDetails": {"boundStreamId": "stream123"},
            }
        ]
    }
    service.liveStreams.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "stream123", "status": {"streamStatus": "active"}}]
    }
    return service
