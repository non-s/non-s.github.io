from unittest.mock import MagicMock

from utils.youtube_reporting import reporting_inventory


def test_reporting_inventory_is_read_only():
    service = MagicMock()
    service.jobs().list.return_value.execute.return_value = {
        "jobs": [{"id": "a", "reportTypeId": "channel_basic_a1", "systemManaged": True}]
    }
    report = reporting_inventory(service)
    assert report["jobs"][0]["id"] == "a"
    service.jobs().create.assert_not_called()
