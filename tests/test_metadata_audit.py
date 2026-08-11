"""Testes das regras de auditoria de títulos públicos."""

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
