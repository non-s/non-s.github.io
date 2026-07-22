import pytest

from utils.animal_branding import (
    ALL_SCENES,
    ALLOWED_ANIMAL_KEYWORDS,
    BROLL_QUERIES,
    JAMENDO_SEARCH_TERMS,
    hook_for_scene,
    is_allowed_animal_text,
    random_scene,
)


def test_scenes_only_cats_and_dogs():
    for scene in ALL_SCENES:
        text = f"{scene} video"
        assert is_allowed_animal_text(text), f"{scene!r} deve ser permitido"


def test_hooks_return_tuple():
    for scene in ALL_SCENES:
        hook, emoji = hook_for_scene(scene)
        assert isinstance(hook, str)
        assert isinstance(emoji, str)


def test_random_scene_in_allowed():
    scene = random_scene()
    assert scene in ALL_SCENES


def test_no_disallowed_animals():
    bad = ["bird", "rabbit", "bunny", "hamster", "storm", "rain", "thunder"]
    for word in bad:
        assert not is_allowed_animal_text(word)


def test_jazz_terms_only():
    for term in JAMENDO_SEARCH_TERMS:
        assert "jazz" in term.lower() or "bossa" in term.lower()
