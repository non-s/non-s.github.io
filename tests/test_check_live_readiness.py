from scripts.check_live_readiness import check_live_readiness


def test_live_readiness_reads_broadcasts_and_streams() -> None:
    class Request:
        def __init__(self, value):
            self.value = value

        def execute(self):
            return self.value

    class Service:
        def liveBroadcasts(self):
            return self

        def liveStreams(self):
            return self

        def list(self, **kwargs):
            return Request({"items": [{"id": "one"}] if "status" in kwargs["part"] else []})

    report = check_live_readiness(Service())
    assert report["api_access"] is True
    assert report["ready_for_live_setup"] is True
    assert report["existing_broadcasts"] == 1
    assert report["existing_streams"] == 1
