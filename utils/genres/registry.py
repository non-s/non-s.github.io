"""Registry of all genre presets.

Importing this module imports every preset module so that the full catalogue
is available via :data:`GENRES`. Use :func:`get_genre` / :func:`list_genres`
to look presets up by name.
"""

from __future__ import annotations

from utils.genres.ambient import AMBIENT
from utils.genres.base import GenrePreset
from utils.genres.blues import BLUES
from utils.genres.cinematic import CINEMATIC
from utils.genres.classical import CLASSICAL
from utils.genres.edm_house import EDM_HOUSE
from utils.genres.funk import FUNK
from utils.genres.hip_hop import HIP_HOP
from utils.genres.jazz import JAZZ
from utils.genres.lofi_ambient import LOFI_AMBIENT
from utils.genres.reggae_dub import REGGAE_DUB
from utils.genres.rock import ROCK
from utils.genres.synthwave import SYNTHWAVE

GENRES: dict[str, GenrePreset] = {
    "lofi_ambient": LOFI_AMBIENT,
    "rock": ROCK,
    "edm_house": EDM_HOUSE,
    "synthwave": SYNTHWAVE,
    "jazz": JAZZ,
    "hip_hop": HIP_HOP,
    "classical": CLASSICAL,
    "ambient": AMBIENT,
    "reggae_dub": REGGAE_DUB,
    "blues": BLUES,
    "funk": FUNK,
    "cinematic": CINEMATIC,
}


def get_genre(name: str) -> GenrePreset:
    """Return the :class:`GenrePreset` registered under ``name``."""
    return GENRES[name]


def list_genres() -> list[str]:
    """Return a sorted list of all registered genre names."""
    return sorted(GENRES.keys())
