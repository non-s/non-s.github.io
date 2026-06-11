"""Voice registry, pronunciation hints and loudness targets."""

from __future__ import annotations

VOICE_REGISTRY = {
    "en": {"primary": "en-US-AriaNeural", "backup": "en-US-GuyNeural", "target_lufs": -16, "pronunciations": {}},
    "pt-BR": {
        "primary": "pt-BR-FranciscaNeural",
        "backup": "pt-BR-AntonioNeural",
        "target_lufs": -16,
        "pronunciations": {},
    },
    "es-ES": {
        "primary": "es-ES-ElviraNeural",
        "backup": "es-ES-AlvaroNeural",
        "target_lufs": -16,
        "pronunciations": {},
    },
    "fr-FR": {"primary": "fr-FR-DeniseNeural", "backup": "fr-FR-HenriNeural", "target_lufs": -16, "pronunciations": {}},
}


def voice_profile(locale: str = "en") -> dict:
    return dict(VOICE_REGISTRY.get(locale) or VOICE_REGISTRY["en"])


def normalize_pronunciations(text: str, locale: str = "en") -> str:
    out = str(text or "")
    for source, target in (voice_profile(locale).get("pronunciations") or {}).items():
        out = out.replace(source, target)
    return out
