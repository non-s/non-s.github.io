"""
utils/categorise.py â€” Pure-Python category inference for Short titles.

Extracted so it can be unit-tested without pulling in any platform SDK.

`infer_category_from_title()` maps a YouTube caption (or any short text)
back to one of the coarse animal buckets the rest of the pipeline
knows: cats, dogs, ocean, wildlife, birds, farm. Returns None when
there's no signal.
"""

from __future__ import annotations


# Order matters â€” earlier rules win. Place sharper signals first.
# Used by analytics dashboards to back-classify uploaded Shorts that
# pre-date the explicit `category` field on the queue (or whose
# metadata got truncated). For freshly-published Wild Brief Shorts
# this returns the same category fetch_animals.py already wrote.
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("cats", ("cat", "cats", "kitten", "kittens", "feline", "tabby", "purr")),
    ("dogs", ("dog", "dogs", "puppy", "puppies", "canine", "retriever", "husky", "labrador", "poodle")),
    (
        "ocean",
        (
            "dolphin",
            "whale",
            "shark",
            "octopus",
            "fish",
            "coral",
            "reef",
            "sea turtle",
            "underwater",
            "marine",
            "stingray",
            "jellyfish",
        ),
    ),
    (
        "birds",
        (
            "bird",
            "eagle",
            "owl",
            "parrot",
            "hummingbird",
            "penguin",
            "flamingo",
            "macaw",
            "falcon",
            "hawk",
            "sparrow",
            "crow",
        ),
    ),
    ("farm", ("horse", "horses", "cow", "cows", "sheep", "goat", "duckling", "duck", "chicken", "pig")),
    # Wildlife is the catch-all for safari + forest animals; place
    # AFTER the more specific buckets so a "lion-fish" doesn't outrank
    # ocean.
    (
        "wildlife",
        (
            "lion",
            "lions",
            "tiger",
            "leopard",
            "elephant",
            "bear",
            "wolf",
            "fox",
            "deer",
            "rhino",
            "giraffe",
            "monkey",
            "zebra",
            "cheetah",
            "panda",
            "koala",
        ),
    ),
]


def infer_category_from_title(title: str | None) -> str | None:
    """Map a title (or any short text) to an animal category bucket.
    None if no signal."""
    if not title:
        return None
    t = title.lower()
    for cat, kws in _RULES:
        if any(k in t for k in kws):
            return cat
    return None
