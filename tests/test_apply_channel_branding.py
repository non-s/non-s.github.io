from unittest.mock import MagicMock, patch

import scripts.apply_channel_branding as apply_channel_branding


def test_update_channel_title_sets_branding_and_returns_channel_id():
    youtube = MagicMock()
    youtube.channels().list().execute.return_value = {
        "items": [{"id": "chan-1", "brandingSettings": {"channel": {"title": "Old Name"}}}]
    }

    channel_id = apply_channel_branding.update_channel_title(youtube, "Amber Hours")

    assert channel_id == "chan-1"
    update_call = youtube.channels().update.call_args
    assert update_call.kwargs["body"]["id"] == "chan-1"
    assert update_call.kwargs["body"]["brandingSettings"]["channel"]["title"] == "Amber Hours"


def test_update_channel_title_raises_when_no_channel_found():
    youtube = MagicMock()
    youtube.channels().list().execute.return_value = {"items": []}

    try:
        apply_channel_branding.update_channel_title(youtube, "Amber Hours")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass


def test_upload_banner_sets_banner_external_url(tmp_path):
    youtube = MagicMock()
    youtube.channelBanners().insert().execute.return_value = {"url": "https://yt3.example/banner.png"}
    youtube.channels().list().execute.return_value = {"items": [{"brandingSettings": {"channel": {"title": "x"}}}]}

    banner_path = tmp_path / "banner.png"
    banner_path.write_bytes(b"fake-png")

    with patch.object(apply_channel_branding, "MediaFileUpload", lambda *a, **k: MagicMock()):
        url = apply_channel_branding.upload_banner(youtube, "chan-1", banner_path)

    assert url == "https://yt3.example/banner.png"
    update_call = youtube.channels().update.call_args
    assert (
        update_call.kwargs["body"]["brandingSettings"]["image"]["bannerExternalUrl"] == "https://yt3.example/banner.png"
    )


def test_find_active_broadcast_id_returns_first_active():
    youtube = MagicMock()
    youtube.liveBroadcasts().list().execute.return_value = {
        "items": [
            {"id": "complete-1", "status": {"lifeCycleStatus": "complete"}},
            {"id": "live-1", "status": {"lifeCycleStatus": "live"}},
        ]
    }

    assert apply_channel_branding.find_active_broadcast_id(youtube) == "live-1"


def test_find_active_broadcast_id_returns_none_when_nothing_active():
    youtube = MagicMock()
    youtube.liveBroadcasts().list().execute.return_value = {"items": []}

    assert apply_channel_branding.find_active_broadcast_id(youtube) is None


def test_set_live_thumbnail_calls_thumbnails_set(tmp_path):
    youtube = MagicMock()
    thumb_path = tmp_path / "thumb.png"
    thumb_path.write_bytes(b"fake-png")

    with patch.object(apply_channel_branding, "MediaFileUpload", lambda *a, **k: MagicMock()):
        apply_channel_branding.set_live_thumbnail(youtube, "broadcast-1", thumb_path)

    youtube.thumbnails().set.assert_called_with(
        videoId="broadcast-1", media_body=youtube.thumbnails().set.call_args.kwargs["media_body"]
    )


def test_main_returns_zero_when_everything_succeeds(monkeypatch, tmp_path, capsys):
    banner = tmp_path / "banner.png"
    banner.write_bytes(b"x")
    thumb = tmp_path / "thumb.png"
    thumb.write_bytes(b"x")
    monkeypatch.setattr(apply_channel_branding, "BANNER_PATH", banner)
    monkeypatch.setattr(apply_channel_branding, "THUMBNAIL_PATH", thumb)

    fake_youtube = MagicMock()
    monkeypatch.setattr(apply_channel_branding, "get_youtube_service", lambda: fake_youtube)
    monkeypatch.setattr(apply_channel_branding, "update_channel_title", lambda yt, title: "chan-1")
    monkeypatch.setattr(apply_channel_branding, "upload_banner", lambda yt, cid, path: "https://yt3.example/banner.png")
    monkeypatch.setattr(apply_channel_branding, "find_active_broadcast_id", lambda yt: "broadcast-1")
    monkeypatch.setattr(apply_channel_branding, "set_live_thumbnail", lambda yt, bid, path: None)

    assert apply_channel_branding.main() == 0
    out = capsys.readouterr().out
    assert "Amber Hours" in out
    assert "avatar_800x800.png manually" in out


def test_main_returns_one_when_no_active_broadcast_for_thumbnail(monkeypatch, tmp_path):
    banner = tmp_path / "banner.png"
    banner.write_bytes(b"x")
    thumb = tmp_path / "thumb.png"
    thumb.write_bytes(b"x")
    monkeypatch.setattr(apply_channel_branding, "BANNER_PATH", banner)
    monkeypatch.setattr(apply_channel_branding, "THUMBNAIL_PATH", thumb)

    monkeypatch.setattr(apply_channel_branding, "get_youtube_service", lambda: MagicMock())
    monkeypatch.setattr(apply_channel_branding, "update_channel_title", lambda yt, title: "chan-1")
    monkeypatch.setattr(apply_channel_branding, "upload_banner", lambda yt, cid, path: "https://yt3.example/banner.png")
    monkeypatch.setattr(apply_channel_branding, "find_active_broadcast_id", lambda yt: None)

    assert apply_channel_branding.main() == 1


def test_main_returns_one_when_channel_title_update_fails(monkeypatch):
    monkeypatch.setattr(apply_channel_branding, "get_youtube_service", lambda: MagicMock())

    def boom(yt, title):
        raise RuntimeError("no channel")

    monkeypatch.setattr(apply_channel_branding, "update_channel_title", boom)

    assert apply_channel_branding.main() == 1
