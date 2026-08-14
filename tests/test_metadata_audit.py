"""Testes das regras de auditoria de títulos públicos."""

from scripts import audit_channel_metadata
from utils.metadata_audit import audit_description, audit_title


def test_flags_repeated_brand() -> None:
    assert audit_title("Liquid Wire | Cozy Cat | Liquid Wire | generative art") == ["repeated_brand"]


def test_accepts_consistent_title() -> None:
    assert audit_title("Liquid Wire | Wireframe Dreams | ambient visuals") == []


def test_empty_title() -> None:
    assert audit_title("") == ["empty_title"]


def test_description_no_conflict() -> None:
    assert audit_description("Liquid Wire | Wireframe", "Generative art and ambient music") == []


def test_authenticated_audit_covers_uploads_outside_public_feed_window() -> None:
    class Request:
        def __init__(self, value):
            self.value = value

        def execute(self):
            return self.value

    class Service:
        def channels(self):
            return self

        def playlistItems(self):
            return self

        def videos(self):
            return self

        def list(self, **kwargs):
            if kwargs.get("mine"):
                return Request({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "uploads"}}}]})
            if kwargs.get("playlistId"):
                return Request({"items": [{"contentDetails": {"videoId": "legacy"}}]})
            return Request(
                {
                    "items": [
                        {
                            "id": "legacy",
                            "snippet": {"title": "Liquid Wire | Wireframe Dreams", "description": "generative art"},
                        }
                    ]
                }
            )

    assert audit_channel_metadata.fetch_uploads_audit(Service()) == []
