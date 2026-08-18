"""Registry of all genre presets.

Importing this module imports every preset module so that the full catalogue
is available via :data:`GENRES`. Use :func:`get_genre` / :func:`list_genres`
to look presets up by name.
"""

from __future__ import annotations

from utils.genres.afrobeat import AFROBEAT
from utils.genres.ambient import AMBIENT
from utils.genres.base import GenrePreset
from utils.genres.blues import BLUES
from utils.genres.bossa_nova import BOSSA_NOVA
from utils.genres.chiptune import CHIPTUNE
from utils.genres.cinematic import CINEMATIC
from utils.genres.classical import CLASSICAL
from utils.genres.country import COUNTRY
from utils.genres.disco import DISCO
from utils.genres.dnb import DNB
from utils.genres.dubstep import DUBSTEP
from utils.genres.edm_house import EDM_HOUSE
from utils.genres.flamenco import FLAMENCO
from utils.genres.folk import FOLK
from utils.genres.funk import FUNK
from utils.genres.gamelan import GAMELAN
from utils.genres.hip_hop import HIP_HOP
from utils.genres.industrial import INDUSTRIAL
from utils.genres.jazz import JAZZ
from utils.genres.lofi_ambient import LOFI_AMBIENT
from utils.genres.metal import METAL
from utils.genres.pop import POP
from utils.genres.reggae_dub import REGGAE_DUB
from utils.genres.rock import ROCK
from utils.genres.salsa import SALSA
from utils.genres.samba import SAMBA
from utils.genres.shoegaze import SHOEGAZE
from utils.genres.soul import SOUL
from utils.genres.synthwave import SYNTHWAVE
from utils.genres.techno import TECHNO
from utils.genres.trance import TRANCE
from utils.genres.vaporwave import VAPORWAVE

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
    "techno": TECHNO,
    "trance": TRANCE,
    "dubstep": DUBSTEP,
    "dnb": DNB,
    "metal": METAL,
    "country": COUNTRY,
    "folk": FOLK,
    "pop": POP,
    "soul": SOUL,
    "disco": DISCO,
    "salsa": SALSA,
    "bossa_nova": BOSSA_NOVA,
    "samba": SAMBA,
    "afrobeat": AFROBEAT,
    "flamenco": FLAMENCO,
    "gamelan": GAMELAN,
    "vaporwave": VAPORWAVE,
    "chiptune": CHIPTUNE,
    "industrial": INDUSTRIAL,
    "shoegaze": SHOEGAZE,
}


def get_genre(name: str) -> GenrePreset:
    """Return the :class:`GenrePreset` registered under ``name``."""
    return GENRES[name]


def list_genres() -> list[str]:
    """Return a sorted list of all registered genre names."""
    return sorted(GENRES.keys())
