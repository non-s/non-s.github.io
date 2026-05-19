"""Tests for the animal category-inference helper used by
youtube_analytics.py.

Lives in `utils/categorise.py` so the unit tests don't need to import
the google-api client stack.
"""
from __future__ import annotations

from utils.categorise import infer_category_from_title


def test_infer_category_picks_cats_for_feline_titles():
    assert infer_category_from_title("Why cats purr — and what it really means") == "cats"
    assert infer_category_from_title("Kittens born this spring break a record") == "cats"


def test_infer_category_picks_dogs_for_canine_titles():
    assert infer_category_from_title("This golden retriever puppy has a job") == "dogs"
    assert infer_category_from_title("Why dogs tilt their heads when you speak") == "dogs"


def test_infer_category_picks_ocean_for_marine_titles():
    assert infer_category_from_title("Dolphins call each other by name") == "ocean"
    assert infer_category_from_title("Sharks can detect a heartbeat in the water") == "ocean"


def test_infer_category_picks_birds_for_avian_titles():
    assert infer_category_from_title("Hummingbirds beat their wings 80 times a second") == "birds"
    assert infer_category_from_title("This eagle dives at 150 mph") == "birds"


def test_infer_category_picks_farm_for_livestock_titles():
    assert infer_category_from_title("Why horses sleep standing up") == "farm"
    assert infer_category_from_title("Baby goats have surprising friends") == "farm"


def test_infer_category_picks_wildlife_for_safari_titles():
    assert infer_category_from_title("Lions hunt at night for one reason") == "wildlife"
    assert infer_category_from_title("Elephants mourn their dead") == "wildlife"


def test_infer_category_handles_unknown():
    assert infer_category_from_title("Mysterious headline about nothing specific") is None


def test_infer_category_handles_empty():
    assert infer_category_from_title("") is None
    assert infer_category_from_title(None) is None
