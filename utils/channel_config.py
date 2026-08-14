"""Channel configuration for Liquid Wire."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelConfig:
    name: str
    slug: str
    brand_prefix: str
    hashtag_brand: list[str]
    base_tags: list[str]
    playlists_by_mood: dict[str, str]
    playlists_by_kind: dict[str, str]
    seo_keywords: dict[str, list[str]]
    title_patterns: dict[str, list[str]]
    emojis: dict[str, str]
    scene_categories: dict[str, list[str]]
    hourly_mood: dict[int, str]
    default_description: str
    channel_id: str = ""


LIQUID_WIRE: ChannelConfig = ChannelConfig(
    name="Liquid Wire",
    slug="liquid_wire",
    brand_prefix="Liquid Wire |",
    hashtag_brand=["#LiquidWire", "#GenerativeArt", "#AmbientVisuals", "#NoStockFootage"],
    base_tags=[
        "Liquid Wire",
        "generative art",
        "ambient visuals",
        "procedural animation",
        "wireframe",
        "abstract video",
        "relaxing visuals",
        "no stock footage",
    ],
    playlists_by_mood={
        "ambient": "Liquid Wire | Ambient Sessions",
        "focus": "Liquid Wire | Focus Flow",
        "sleep": "Liquid Wire | Night Drift",
        "live": "Liquid Wire | Live Streams",
    },
    playlists_by_kind={
        "short": "Liquid Wire | Shorts",
        "long": "Liquid Wire | Long Sessions",
        "live-test": "Liquid Wire | Live Tests",
    },
    seo_keywords={
        "visuals": [
            "generative visuals",
            "ambient visuals",
            "abstract visuals",
            "procedural animation",
            "liquid wireframe",
            "relaxing abstract video",
        ],
        "mood": ["calm", "slow", "hypnotic", "focus", "late night", "ambient", "soft motion"],
        "format": ["live wallpaper", "visual radio", "ambient loop", "generative art stream"],
    },
    title_patterns={
        "short": [
            "Liquid Wire {episode} | slow generative ambient visuals",
            "Liquid Wire | liquid wireframe motion for focus",
            "Slowform {episode} | procedural ambient visual",
        ],
    },
    emojis={"brand": "", "calm": "", "focus": "", "night": ""},
    scene_categories={
        "ambient": ["liquid wire procedural blob", "slow wireframe gel", "fluid mesh form"],
        "focus": ["calm wireframe flow", "soft liquid mesh", "abstract focus field"],
        "sleep": ["dark liquid wire", "night ambient mesh", "slowform drift"],
    },
    hourly_mood={h: ("sleep" if h < 6 or h >= 22 else "focus" if 9 <= h < 17 else "ambient") for h in range(24)},
    default_description=(
        "Slow generative visuals, liquid wireframes, soft motion, and ambient "
        "soundscapes for focus, rest, and late-night calm. Original procedural "
        "visuals. No stock footage."
    ),
    channel_id="UCYAxnaW6H8g3XJMntkDXZjg",
)


CHANNELS: dict[str, ChannelConfig] = {
    "liquid_wire": LIQUID_WIRE,
}

active_channel: ChannelConfig = LIQUID_WIRE


def set_channel(name: str) -> None:
    global active_channel
    if name not in CHANNELS:
        raise KeyError(f"Unknown channel: {name!r}. Available: {sorted(CHANNELS)}")
    active_channel = CHANNELS[name]


def set_channel_from_env() -> None:
    import os

    channel = os.environ.get("YOUTUBE_CHANNEL", "").strip().lower()
    if channel:
        set_channel(channel)
