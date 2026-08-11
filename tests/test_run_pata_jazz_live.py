from scripts.run_pata_jazz_live import _ingestion_url


def test_builds_rtmp_url_from_youtube_stream() -> None:
    stream = {"cdn": {"ingestionInfo": {"ingestionAddress": "rtmp://a.example/live/", "streamName": "key"}}}
    assert _ingestion_url(stream) == "rtmp://a.example/live/key"
