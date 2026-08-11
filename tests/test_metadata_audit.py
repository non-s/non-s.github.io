"""Testes das regras de auditoria de títulos públicos."""

from scripts import audit_channel_metadata
from utils.metadata_audit import audit_description, audit_title


def test_flags_cross_species_keywords() -> None:
    assert audit_title("Pata Jazz | Sleepy Cat | relaxing music for dogs") == ["mixed_cat_dog_keywords"]


def test_flags_repeated_brand() -> None:
    assert audit_title("Pata Jazz | Cozy Cat | Pata Jazz | music for cats") == ["repeated_brand"]


def test_accepts_consistent_title() -> None:
    assert audit_title("Pata Jazz | Dog Sleeping Peacefully | relaxing music for dogs") == []


def test_flags_dog_keywords_in_a_cat_description() -> None:
    assert audit_description("Pata Jazz | Sleepy Cat", "Relaxing music for dogs") == [
        "description_conflicts_with_cat_title"
    ]


def test_accepts_species_consistent_description() -> None:
    assert audit_description("Pata Jazz | Sleepy Dog", "Calm music for dogs and pets") == []


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
                            "snippet": {"title": "Pata Jazz | Sleepy Cat", "description": "music for dogs"},
                        }
                    ]
                }
            )

    assert audit_channel_metadata.fetch_uploads_audit(Service()) == [
        {
            "video_id": "legacy",
            "title": "Pata Jazz | Sleepy Cat",
            "description": "music for dogs",
            "issues": ["description_conflicts_with_cat_title"],
        }
    ]
