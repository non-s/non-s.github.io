from unittest.mock import MagicMock

import scripts.check_channel_branding as check_channel_branding


def test_main_prints_snippet_and_branding_titles(monkeypatch, capsys):
    fake_youtube = MagicMock()
    fake_youtube.channels().list().execute.return_value = {
        "items": [
            {
                "id": "chan-1",
                "snippet": {
                    "title": "Wild Brief",
                    "thumbnails": {"high": {"url": "https://yt3.example/avatar.jpg"}},
                },
                "brandingSettings": {"channel": {"title": "Amber Hours"}},
            }
        ]
    }
    monkeypatch.setattr(check_channel_branding, "get_youtube_service", lambda: fake_youtube)

    assert check_channel_branding.main() == 0
    out = capsys.readouterr().out
    assert "Wild Brief" in out
    assert "Amber Hours" in out
    assert "https://yt3.example/avatar.jpg" in out


def test_main_returns_one_when_no_channel_found(monkeypatch, capsys):
    fake_youtube = MagicMock()
    fake_youtube.channels().list().execute.return_value = {"items": []}
    monkeypatch.setattr(check_channel_branding, "get_youtube_service", lambda: fake_youtube)

    assert check_channel_branding.main() == 1
