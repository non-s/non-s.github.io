"""Deterministic rescue rewrites before rejecting usable animal footage."""

from __future__ import annotations

import re

from utils.curiosity_angles import build_curiosity_package
from utils.editorial_guard import editorial_issues
from utils.packaging import extract_action, extract_animal, extract_cue
from utils.story_intelligence import classify_format

ANIMAL_TAG_WORDS = {
    "ant",
    "ants",
    "bear",
    "bears",
    "bee",
    "bees",
    "beetle",
    "beetles",
    "bird",
    "birds",
    "butterfly",
    "butterflies",
    "cat",
    "cats",
    "chicken",
    "chickens",
    "cow",
    "cows",
    "deer",
    "dog",
    "dogs",
    "dolphin",
    "dolphins",
    "dragonfly",
    "dragonflies",
    "duck",
    "ducks",
    "duckling",
    "ducklings",
    "elephant",
    "elephants",
    "fox",
    "foxes",
    "goat",
    "goats",
    "horse",
    "horses",
    "lion",
    "lions",
    "macaw",
    "macaws",
    "mantis",
    "mantises",
    "monkey",
    "monkeys",
    "octopus",
    "octopuses",
    "orangutan",
    "orangutans",
    "owl",
    "owls",
    "parrot",
    "parrots",
    "penguin",
    "penguins",
    "seal",
    "seals",
    "shark",
    "sharks",
    "sheep",
    "snake",
    "snakes",
    "tiger",
    "tigers",
    "turtle",
    "turtles",
    "whale",
    "whales",
    "wolf",
    "wolves",
}

FALLBACK_CUES = {
    "ant": "antenna movement",
    "ants": "antenna movement",
    "bear": "tail position",
    "bears": "tail position",
    "bee": "wing movement",
    "bees": "wing movement",
    "beetle": "antenna movement",
    "beetles": "antenna movement",
    "bird": "wing position",
    "birds": "wing position",
    "butterfly": "wing movement",
    "butterflies": "wing movement",
    "cat": "ear position",
    "cats": "ear position",
    "chicken": "head movement",
    "chickens": "head movement",
    "cow": "ear position",
    "cows": "ear position",
    "deer": "ear position",
    "dog": "tail position",
    "dogs": "tail position",
    "dolphin": "fin movement",
    "dolphins": "fin movement",
    "dragonfly": "wing movement",
    "dragonflies": "wing movement",
    "duck": "wing position",
    "ducks": "wing position",
    "duckling": "wing position",
    "ducklings": "wing position",
    "elephant": "ear movement",
    "elephants": "ear movement",
    "fox": "tail position",
    "foxes": "tail position",
    "forest": "canopy shift",
    "forests": "canopy shift",
    "geology": "rock layers",
    "geologies": "rock layers",
    "goat": "ear position",
    "goats": "ear position",
    "horse": "ear position",
    "horses": "ear position",
    "lion": "ear position",
    "lions": "ear position",
    "macaw": "beak movement",
    "macaws": "beak movement",
    "mantis": "front-leg movement",
    "mantises": "front-leg movement",
    "monkey": "hand movement",
    "monkeys": "hand movement",
    "octopus": "arm movement",
    "octopuses": "arm movement",
    "orangutan": "hand movement",
    "orangutans": "hand movement",
    "owl": "eye contact",
    "owls": "eye contact",
    "parrot": "beak movement",
    "parrots": "beak movement",
    "penguin": "flipper movement",
    "penguins": "flipper movement",
    "seal": "whisker movement",
    "seals": "whisker movement",
    "shark": "fin movement",
    "sharks": "fin movement",
    "sheep": "ear position",
    "snake": "head movement",
    "snakes": "head movement",
    "tiger": "ear position",
    "tigers": "ear position",
    "tree": "root network",
    "trees": "root network",
    "turtle": "head movement",
    "turtles": "head movement",
    "whale": "fin movement",
    "whales": "fin movement",
    "wolf": "tail position",
    "wolves": "tail position",
}
NATURE_SUBJECTS = {
    "aurora",
    "auroras",
    "badlands",
    "canyon",
    "canyons",
    "chemistry",
    "cloud",
    "clouds",
    "crystal",
    "crystals",
    "discoveries",
    "earth",
    "earth systems",
    "earth from space",
    "earth_from_space",
    "ecosystem",
    "ecosystems",
    "fossil",
    "fossils",
    "forest",
    "forests",
    "fungi",
    "fungus",
    "geothermal",
    "geology",
    "geologies",
    "lightning",
    "magnet",
    "magnets",
    "mountain",
    "mountains",
    "mushroom",
    "mushrooms",
    "physics",
    "plant",
    "plants",
    "rare phenomena",
    "rare_phenomena",
    "river",
    "rivers",
    "rock",
    "rock layers",
    "rocks",
    "storm",
    "storms",
    "tree",
    "trees",
    "volcano",
    "volcanoes",
    "weather",
    "weather patterns",
}


def _animal(text: str) -> str:
    normalised = re.sub(r"\bsheep[\s_-]*dogs?\b", "working dog", text or "", flags=re.I)
    normalised = re.sub(r"\belephant[\s_-]*seals?\b", "seal", normalised, flags=re.I)
    normalised = re.sub(r"[-_/]+", " ", normalised)
    for word in re.findall(r"[A-Za-z][A-Za-z']+", normalised):
        low = word.lower().replace("'s", "")
        if low in {
            "cow",
            "cows",
            "duck",
            "ducks",
            "duckling",
            "ducklings",
            "chicken",
            "chickens",
            "deer",
            "horse",
            "horses",
            "tiger",
            "tigers",
            "penguin",
            "penguins",
            "goat",
            "goats",
            "wolf",
            "wolves",
            "bear",
            "bears",
            "bird",
            "birds",
            "owl",
            "owls",
            "cat",
            "cats",
            "dog",
            "dogs",
            "lion",
            "lions",
            "elephant",
            "elephants",
            "dolphin",
            "dolphins",
            "whale",
            "whales",
            "octopus",
            "octopuses",
            "seal",
            "seals",
            "fox",
            "foxes",
            "sheep",
            "parrot",
            "parrots",
            "macaw",
            "macaws",
            "orangutan",
            "orangutans",
            "monkey",
            "monkeys",
            "donkey",
            "donkeys",
            "shark",
            "sharks",
            "bee",
            "bees",
            "butterfly",
            "butterflies",
            "ant",
            "ants",
            "beetle",
            "beetles",
            "mantis",
            "mantises",
            "dragonfly",
            "dragonflies",
            "snake",
            "snakes",
            "chameleon",
            "chameleons",
            "turtle",
            "turtles",
        }:
            return word.capitalize()
    return "Animals"


def _subject(animal: str) -> str:
    return animal[:1].upper() + animal[1:] if animal else "Animals"


def _lower_subject(animal: str) -> str:
    return (animal or "animals").lower()


def _plural_subject(animal: str) -> str:
    lower = _lower_subject(animal)
    irregular = {
        "deer": "Deer",
        "sheep": "Sheep",
        "earth": "Earth systems",
        "earth systems": "Earth systems",
        "earth from space": "Earth systems",
        "earth_from_space": "Earth systems",
        "geology": "Geology",
        "geologies": "Geology",
        "weather": "Weather patterns",
        "wildlife": "Wildlife",
        "wolf": "Wolves",
        "fox": "Foxes",
        "octopus": "Octopuses",
        "fungus": "Fungi",
        "cactus": "Cacti",
        "goose": "Geese",
        "mouse": "Mice",
        "butterfly": "Butterflies",
    }
    if lower in irregular:
        return irregular[lower]
    if lower.endswith("s"):
        return _subject(animal)
    if lower.endswith("ch") or lower.endswith("sh"):
        return f"{_subject(animal)}es"
    if lower.endswith("y"):
        return f"{_subject(animal)[:-1]}ies"
    return f"{_subject(animal)}s"


def _lower_plural_subject(animal: str) -> str:
    return _plural_subject(animal).lower()


def _plural(animal: str) -> bool:
    lower = _lower_subject(animal)
    if lower in {
        "cacti",
        "deer",
        "earth",
        "earth systems",
        "earth from space",
        "earth_from_space",
        "fish",
        "fungi",
        "geese",
        "mice",
        "sheep",
        "weather",
        "weather patterns",
        "wildlife",
    }:
        return True
    return lower.endswith("s")


def _verb(animal: str, base: str) -> str:
    display_subject = _plural_subject(animal).lower()
    if _plural(animal) or display_subject.endswith("s"):
        return base
    if base.endswith("ch") or base.endswith("sh"):
        return f"{base}es"
    if base.endswith("y"):
        return f"{base[:-1]}ies"
    return f"{base}s"


def _usable_action(action: str, fmt: str) -> str:
    action = (action or "").lower().strip()
    if action in {"show", "watch", "cue", "use", "changes", "change", "rely", ""}:
        if fmt == "animal_memory":
            return "recognize"
        if fmt == "body_superpower":
            return "survive"
        return "signal"
    return action


def _fallback_cue(animal: str) -> str:
    return FALLBACK_CUES.get(_lower_subject(animal), "first movement")


def _usable_cue(cue: str, animal: str = "") -> str:
    cue = (cue or "").lower().strip()
    animal_key = _lower_subject(animal)
    if cue in {"", "cue", "movement", "first movement", "body", "body cue", "body posture", "detail"}:
        return _fallback_cue(animal)
    if cue in {"hand", "hands", "hand cue", "hand movement"} and animal_key not in {
        "monkey",
        "monkeys",
        "macaque",
        "macaques",
        "orangutan",
        "orangutans",
    }:
        return _fallback_cue(animal)
    return {
        "ears": "ear position",
        "ear": "ear position",
        "eyes": "eye contact",
        "tail": "tail position",
        "tongue": "tongue flick",
        "tongues": "tongue flick",
        "paw": "paw position",
        "paws": "paw position",
        "wing": "wing position",
        "wings": "wing position",
        "feet": "footwork",
        "hooves": "hoof movement",
        "feathers": "feather position",
        "head": "head movement",
        "hand": "hand movement",
        "hands": "hand movement",
        "fin": "fin movement",
        "fins": "fin movement",
        "beak": "beak movement",
        "flipper": "flipper movement",
        "flippers": "flipper movement",
        "antenna": "antenna movement",
        "antennae": "antenna movement",
        "whisker": "whisker movement",
        "whiskers": "whisker movement",
        "rock": "rock layers",
        "rocks": "rock layers",
        "cloud": "cloud pattern",
        "clouds": "cloud pattern",
        "canopy": "canopy shift",
        "leaf": "leaf movement",
        "leaves": "leaf movement",
        "movement": "movement",
        "body": "body posture",
        "call": "call",
    }.get(cue, cue)


def _benefit(action: str, fmt: str) -> str:
    if fmt == "animal_memory":
        return "recognize familiar signals faster"
    if action in {"escape", "hide", "protect", "survive"}:
        return "stay safe when the moment changes"
    if action in {"hunt", "trick", "signal", "call"}:
        return "send a clear signal before the next move"
    return "solve one visible problem in the scene"


def _is_nature_subject(animal: str) -> bool:
    return _lower_subject(animal) in NATURE_SUBJECTS or _lower_plural_subject(animal) in NATURE_SUBJECTS


def _nature_motion_verb(animal: str) -> str:
    return "shift" if _plural(animal) or _lower_plural_subject(animal).endswith("s") else "shifts"


def _reason_clause(
    *,
    animal: str,
    lower_subject: str,
    cue_object_pronoun: str,
    benefit: str,
    use_verb: str,
) -> str:
    if _is_nature_subject(animal):
        return f"that detail shows how {lower_subject} {_nature_motion_verb(animal)} over time"
    return f"{lower_subject} {use_verb} {cue_object_pronoun} to {benefit}"


def _source_context(story: dict) -> str:
    related = story.get("sequel_of") or story.get("remake_of") or {}
    if not isinstance(related, dict):
        related = {}
    return " ".join(
        str(value or "")
        for value in (
            related.get("title"),
            story.get("source_title"),
            story.get("raw_title"),
            story.get("title"),
            story.get("seo_title"),
            story.get("category"),
        )
    )


def _clean_tags(existing: object, subject: str, category: str) -> list[str]:
    tags: list[str] = []
    for tag in existing if isinstance(existing, list) else []:
        text = str(tag or "").strip()
        words = {word.lower() for word in re.findall(r"[A-Za-z]+", text)}
        if text and not (words & ANIMAL_TAG_WORDS):
            tags.append(text)
    nature_categories = {
        "chemistry",
        "conservation",
        "discoveries",
        "earth_from_space",
        "ecosystems",
        "forests",
        "fungi",
        "geology",
        "microscopy",
        "mountains",
        "physics",
        "plants",
        "rare_phenomena",
        "rivers",
        "space",
        "trees",
        "volcanoes",
        "weather",
    }
    evergreen = "nature facts" if str(category or "").lower() in nature_categories else "animal facts"
    preferred = [subject.lower(), category.lower(), evergreen]
    out: list[str] = []
    for tag in preferred + tags:
        clean = re.sub(r"\s+", " ", str(tag or "")).strip()
        if clean and clean.lower() not in {item.lower() for item in out}:
            out.append(clean)
    return out[:8]


def _cue_moment(cue: str) -> str:
    cue = str(cue or "").lower().strip()
    return {
        "ear position": "their ears shift",
        "ear movement": "their ears move",
        "ear": "their ears shift",
        "ears": "their ears shift",
        "head movement": "their heads move",
        "head": "their heads move",
        "fin movement": "their fins shift",
        "fin": "their fins shift",
        "fins": "their fins shift",
        "hand movement": "their hands move",
        "hand": "their hands move",
        "hands": "their hands move",
        "tail position": "their tails lift",
        "tail": "their tails lift",
        "tongue flick": "their tongues flick",
        "tongue": "their tongues flick",
        "tongues": "their tongues flick",
        "wing movement": "their wings move",
        "wing position": "their wings shift",
        "wing": "their wings move",
        "wings": "their wings move",
        "paw": "their paws move",
        "paws": "their paws move",
        "beak movement": "their beaks move",
        "beak": "their beaks move",
        "flipper movement": "their flippers shift",
        "flipper": "their flippers shift",
        "flippers": "their flippers shift",
        "first movement": "the first move appears",
        "feeding cue": "the feeding cue appears",
        "object group": "the object group changes",
        "number cue": "the number cue appears",
        "rock layers": "the rock layer appears",
        "rocks": "the rock layer appears",
        "cloud pattern": "the cloud pattern appears",
        "clouds": "the cloud pattern appears",
        "canopy shift": "the canopy shift appears",
        "leaf movement": "the leaf movement appears",
        "leaf": "the leaf movement appears",
        "leaves": "the leaf movement appears",
    }.get(cue, f"the {cue} changes")


def _cue_signal(cue: str) -> str:
    cue = str(cue or "").lower().strip()
    return {
        "ear position": "ear shift",
        "ear movement": "ear shift",
        "ear": "ear shift",
        "ears": "ear shift",
        "head movement": "head movement",
        "head": "head movement",
        "fin movement": "fin cue",
        "fin": "fin cue",
        "fins": "fin cue",
        "hand movement": "hand cue",
        "hand": "hand cue",
        "hands": "hand cue",
        "tail position": "tail lift",
        "tail": "tail lift",
        "tongue flick": "tongue flick",
        "tongue": "tongue flick",
        "tongues": "tongue flick",
        "wing movement": "wing beat",
        "wing position": "wing angle",
        "wing": "wing beat",
        "wings": "wing beat",
        "paws": "paw cue",
        "paw": "paw cue",
        "beak movement": "beak cue",
        "beak": "beak cue",
        "flipper movement": "flipper cue",
        "flipper": "flipper cue",
        "flippers": "flipper cue",
        "first movement": "first move",
        "feeding cue": "feeding cue",
        "object group": "object group",
        "number cue": "number cue",
        "rock layers": "rock layer",
        "rocks": "rock layer",
        "cloud pattern": "cloud pattern",
        "clouds": "cloud pattern",
        "canopy shift": "canopy shift",
        "leaf movement": "leaf movement",
        "leaf": "leaf movement",
        "leaves": "leaf movement",
    }.get(cue, cue or "first cue")


def _thumbnail_label(cue: str) -> str:
    return _cue_signal(cue).upper()[:28]


def _title_from_hook(text: object) -> str:
    first_sentence = re.split(r"[.!?]", str(text or "").strip(), maxsplit=1)[0]
    title = re.sub(r"\s+", " ", first_sentence).strip(" ,;:")
    words = re.findall(r"[A-Za-z]+", title)
    if len(words) < 4:
        return ""
    return title[:60].rstrip(" ,;:")


def _title_key(title: object) -> str:
    text = re.sub(r"[^\w\s'-]", " ", str(title or "").lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _context_has(context: str, *terms: str) -> bool:
    return any(re.search(r"\b" + re.escape(term.lower()) + r"\b", context) for term in terms)


def _duplicate_context_variant(story: dict, animal: str, visual_text: str) -> dict:
    context = " ".join(
        str(value or "")
        for value in (
            visual_text,
            story.get("source_title"),
            story.get("raw_title"),
            story.get("source_url"),
            story.get("url"),
            story.get("category"),
            animal,
        )
    ).lower()
    category = str(story.get("category") or "").strip().lower()

    def variant(
        *,
        title: str,
        hook: str,
        script: str,
        thumbnail: str,
        cue: str,
        subject: str,
        story_format: str = "earth_engine",
    ) -> dict:
        return {
            "seo_title": title[:60],
            "title": title[:60],
            "hook": hook,
            "script": script,
            "lead": script[:400],
            "thumbnail_text": thumbnail[:28],
            "story_format": story_format,
            "yt_tags": _clean_tags(story.get("yt_tags"), subject.lower(), category),
        }

    if category == "geology" or _context_has(context, "geology", "rock", "rocks", "canyon", "cave", "geyser"):
        if _context_has(context, "slot", "canyon", "utah", "sandstone"):
            title = "Rock layers reveal flood paths carved into stone"
            hook = "Rock layers can show where fast water carved the wall."
            script = (
                f"{hook} Watch the narrow curves, because floodwater and blowing sand wear weak rock "
                "over long stretches of time. The smooth wall is erosion written into stone. Which canyon "
                "clue should we read next?"
            )
            return variant(
                title=title,
                hook=hook,
                script=script,
                thumbnail="CANYON PATHS",
                cue="canyon wall",
                subject="rock layers",
            )
        if _context_has(context, "cave", "caves", "tunnel", "tunnels", "underground", "pillar", "pillars"):
            title = "Rock layers show their timeline inside caves"
            hook = "Rock layers keep a hidden timeline inside caves."
            script = (
                f"{hook} Watch the cave wall, because water can dissolve, deposit, and expose minerals "
                "over long periods. The chamber becomes a cross-section of slow chemistry and stone. "
                "Which underground clue should we inspect next?"
            )
            return variant(
                title=title, hook=hook, script=script, thumbnail="CAVE TIMELINE", cue="cave wall", subject="rock layers"
            )
        if _context_has(context, "geyser", "geothermal", "steam", "steamy", "thermal"):
            title = "Rock layers reveal heat moving under the surface"
            hook = "Rock layers can expose heat moving below ground."
            script = (
                f"{hook} Watch the steam, because hot water rises through cracks after being heated "
                "underground. Pressure and minerals turn hidden energy into a visible signal at the surface. "
                "Which geothermal clue should come next?"
            )
            return variant(
                title=title, hook=hook, script=script, thumbnail="HEAT PATH", cue="steam vent", subject="rock layers"
            )
        if _context_has(context, "badlands", "rolling", "eroded"):
            title = "Rock layers expose erosion in bare open hills"
            hook = "Rock layers show erosion without much cover."
            script = (
                f"{hook} Watch the bare ridges, because soft rock and sparse plants let rain and wind "
                "carve the surface quickly. Each groove is a small drainage path made visible. Which landform "
                "should we compare next?"
            )
            return variant(
                title=title,
                hook=hook,
                script=script,
                thumbnail="BARE EROSION",
                cue="bare ridges",
                subject="rock layers",
            )
        if _context_has(context, "himalayan", "himalaya", "nepal", "mountain", "mountains", "peak", "valley"):
            title = "Rock layers rise into view when mountains lift"
            hook = "Rock layers can be lifted high enough to read."
            script = (
                f"{hook} Watch the exposed slopes, because mountain building can push old rock upward "
                "while erosion strips cover away. A peak can reveal material that formed far below. Which "
                "uplift clue should we decode next?"
            )
            return variant(
                title=title,
                hook=hook,
                script=script,
                thumbnail="UPLIFT CLUE",
                cue="exposed slopes",
                subject="rock layers",
            )

    if category in {"earth_from_space", "weather"} or _context_has(context, "cloud", "clouds", "cloudy", "sky"):
        if _context_has(context, "timelapse", "cloudy", "changing", "moving"):
            title = "Storm clouds show air layers changing over time"
            hook = "Storm clouds show air layers changing over time."
            script = (
                f"{hook} Watch the cloud deck, because winds at different heights can push each layer "
                "in a different direction. A timelapse turns that invisible motion into a map. Which sky "
                "motion should we read next?"
            )
            return variant(
                title=title, hook=hook, script=script, thumbnail="AIR LAYERS", cue="cloud deck", subject="storm clouds"
            )
        if _context_has(context, "airplane", "plane", "window", "above", "horizon"):
            title = "Storm clouds reveal weather from above the clouds"
            hook = "Storm clouds look different when seen from above."
            script = (
                f"{hook} Watch the cloud tops, because the upper shape shows where air is rising, "
                "flattening, or spreading out. From above, weather becomes a texture map instead of a "
                "ceiling. Which above-cloud clue should we compare next?"
            )
            return variant(
                title=title, hook=hook, script=script, thumbnail="CLOUD TOPS", cue="cloud tops", subject="storm clouds"
            )
        if _context_has(context, "ocean", "water", "coast"):
            title = "Storm clouds trace wind bands over the ocean"
            hook = "Storm clouds can trace wind moving over water."
            script = (
                f"{hook} Watch the long cloud bands, because wind, moisture, and temperature shape where "
                "air rises over the ocean. The pattern is not random scenery; it is atmosphere in motion. "
                "Which ocean-sky clue should come next?"
            )
            return variant(
                title=title, hook=hook, script=script, thumbnail="WIND BANDS", cue="cloud bands", subject="storm clouds"
            )
        if _context_has(context, "overcast", "grey", "gray", "cloudscape"):
            title = "Storm clouds filter sunlight into a softer glow"
            hook = "Storm clouds spread sunlight before it reaches the ground."
            script = (
                f"{hook} Watch the flat light, because thick cloud layers scatter direct sun in many "
                "directions. That makes shadows softer and shows how weather can change a scene before "
                "rain arrives. Which light clue should we compare next?"
            )
            return variant(
                title=title, hook=hook, script=script, thumbnail="SOFT LIGHT", cue="flat light", subject="storm clouds"
            )

    if category == "forests" or _context_has(context, "forest", "forests", "fog", "trail"):
        if _context_has(context, "fog", "foggy", "mist", "misty"):
            title = "Forests hold cool fog between the trees"
            hook = "Forests can trap cool fog near the ground."
            script = (
                f"{hook} Watch the low mist, because shade, leaves, and damp soil slow how fast the "
                "air warms back up. That is why a forest path can feel cooler than open ground. Which "
                "forest layer should we decode next?"
            )
            return variant(
                title=title, hook=hook, script=script, thumbnail="FOG LAYER", cue="low mist", subject="forests"
            )
        if _context_has(context, "trail", "path", "bridge", "hike"):
            title = "Forests reveal edge climates along trails"
            hook = "Forests change climate at the trail edge."
            script = (
                f"{hook} Watch the brighter opening beside the trees, because edges get more sun and "
                "wind than the shaded interior. A few steps can shift moisture, heat, and plant life. "
                "Which edge clue should we compare next?"
            )
            return variant(
                title=title, hook=hook, script=script, thumbnail="EDGE CLIMATE", cue="trail edge", subject="forests"
            )

    if category == "plants" or _context_has(context, "plant", "plants", "leaf", "leaves", "greenhouse"):
        if _context_has(context, "greenhouse", "glass"):
            title = "Plants speed growth under protected glass"
            hook = "Plants grow faster when warmth stays trapped."
            script = (
                f"{hook} Watch the protected leaves, because greenhouse glass keeps heat and humidity "
                "more stable around the plant. That calmer microclimate lets growth spend less energy on "
                "stress. Which growing trick should we test next?"
            )
            return variant(
                title=title,
                hook=hook,
                script=script,
                thumbnail="GREENHOUSE BOOST",
                cue="protected leaves",
                subject="plants",
                story_format="plant_mechanism",
            )
        if _context_has(context, "desert", "cactus", "dry", "windy", "sand"):
            title = "Plants save water with slow desert tricks"
            hook = "Plants survive by slowing water loss."
            script = (
                f"{hook} Watch the thick leaves or waxy surface, because many desert plants store water "
                "and limit evaporation. The shape is not decoration; it is a survival budget. Which dry "
                "land adaptation should come next?"
            )
            return variant(
                title=title,
                hook=hook,
                script=script,
                thumbnail="WATER BUDGET",
                cue="waxy surface",
                subject="plants",
                story_format="plant_mechanism",
            )
        if _context_has(context, "sunlit", "sunlight", "foliage", "green"):
            title = "Plants turn sunlight into stored sugar"
            hook = "Plants turn light into food."
            script = (
                f"{hook} Watch the leaf surface, because chlorophyll captures light energy and uses it "
                "to build sugar from air and water. The green color is a tiny factory at work. Which "
                "plant clue should we decode next?"
            )
            return variant(
                title=title,
                hook=hook,
                script=script,
                thumbnail="LIGHT TO SUGAR",
                cue="leaf surface",
                subject="plants",
                story_format="plant_mechanism",
            )

    return {}


def _collision_rescue_variant(story: dict, angle_package: dict, animal: str) -> dict:
    """Build a second safe angle when the top deterministic angle already exists."""
    subject = str(angle_package.get("subject") or _plural_subject(animal)).strip() or _plural_subject(animal)
    if _is_nature_subject(subject):
        return {}
    lower_subject = subject.lower()
    cue = _usable_cue(extract_cue(story), animal)
    if cue in {"body posture", "cue", "first movement", "movement"}:
        cue = str(angle_package.get("cue") or _fallback_cue(animal))
    cue_signal = _cue_signal(cue)
    cue_reference = _cue_reference(cue)
    story_format = str(angle_package.get("story_format") or classify_format(_source_context(story)))
    angle_key = str(angle_package.get("angle_key") or "")
    if angle_key == "duck_fake_injury":
        title = f"{subject} fake weak wings to protect ducklings"
        hook = f"{subject} fake weak wings to protect ducklings."
        script = (
            f"{hook} Watch the wing position, because {lower_subject} make the adult look like the easier "
            "target while predators search near the nest. The distraction buys a few seconds, "
            f"and a few seconds can keep the ducklings safer. Which {lower_subject} survival detail should we compare next?"
        )
        return {
            "seo_title": title[:60],
            "title": title[:60],
            "hook": hook,
            "script": script,
            "lead": script[:400],
            "thumbnail_text": "WING DECOY",
            "story_format": story_format,
            "yt_tags": _clean_tags(story.get("yt_tags"), subject.lower(), str(story.get("category") or "")),
        }
    if story_format == "survival_trick":
        title = f"{subject} redirect danger with {cue_signal}"
        hook = f"{subject} can redirect danger with {cue_signal}."
        body = (
            f"Watch {cue_reference}, because {lower_subject} make that visible move more tempting "
            "than the real target. The distraction buys a few seconds, and those seconds can change "
            f"the escape window. Which {lower_subject} survival clue should we compare next?"
        )
    elif story_format == "animal_memory":
        title = f"{subject} sort familiar clues with {cue_signal}"
        hook = f"{subject} can sort familiar clues with {cue_signal}."
        body = (
            f"Watch {cue_reference}, because {lower_subject} connect that detail with what happened "
            "before. The clue helps them react differently next time, instead of treating every "
            f"moment as new. Which {lower_subject} memory clue should come next?"
        )
    else:
        title = f"{subject} solve one problem with {cue_signal}"
        hook = f"{subject} can solve one problem with {cue_signal}."
        body = (
            f"Watch {cue_reference}, because {lower_subject} use that detail to handle a real "
            "physical problem in the scene. The useful part is visible before the payoff, which is "
            f"why the clip is worth replaying. Which {lower_subject} clue should we decode next?"
        )
    script = f"{hook} {body}"
    return {
        "seo_title": title[:60],
        "title": title[:60],
        "hook": hook,
        "script": script,
        "lead": script[:400],
        "thumbnail_text": _thumbnail_label(cue),
        "story_format": story_format,
        "yt_tags": _clean_tags(story.get("yt_tags"), subject.lower(), str(story.get("category") or "")),
    }


def _cue_reference(cue: str) -> str:
    cue = str(cue or "cue").lower().strip()
    if cue.startswith(("the ", "their ", "its ")):
        return cue
    return f"the {cue}"


def _cue_object_pronoun(cue: str) -> str:
    cue = str(cue or "").lower().strip()
    if re.search(r"\b(?:layers|threads|roots|spores|clouds|leaves)\b", cue):
        return "them"
    return "it"


def rescue_story(story: dict, reasons: list[str]) -> tuple[dict, bool]:
    """Return a locally rewritten story when the issue is editorial, not visual."""
    reasons = list(reasons)
    if "off_topic_visual" in reasons:
        return story, False
    if not any(
        reason in reasons
        for reason in (
            "repetitive_title_template",
            "duplicate_title",
            "generic_script_template",
            "script_word_loop",
            "duplicate_script",
            "duplicate_angle",
            "rewrite_packaging",
            "missing_visible_cue",
            "missing_action_word",
            "title_needs_stronger_shape",
            "animal_not_immediately_clear",
            "subject_not_immediately_clear",
            "no_action_promise",
            "payoff_not_explicit",
            "missing_visual_cue",
            "generic_creator_language",
            "hook_shape_weak",
            "title_shape_weak",
            "copy_subject_mismatch",
            "script_subject_mismatch",
            "encoding_artifact",
            "stacked_animal_title",
            "robotic_use_loop",
            "robotic_because_of_this",
            "robotic_not_random_title",
            "robotic_not_accident_title",
            "generic_watch_cue",
            "generic_visible_cue",
            "generic_visual_cue_language",
            "generic_signal_cue",
            "generic_detail_clue_title",
            "generic_next_move_movement",
            "generic_body_posture_template",
            "generic_detail_template",
            "generic_movement_template",
            "generic_movement_promise",
            "generic_bodypart_movement_promise",
            "generic_rely_bodypart_to_outcome",
            "generic_false_face_memory",
            "generic_signal_through_body_cue",
            "generic_rely_to_signal_cue",
            "generic_next_move_cue",
            "generic_movement_changes_title",
            "generic_first_movement_reason",
            "generic_first_move_title",
            "awkward_ear_movement_changes",
            "awkward_this_ear_position_changes",
            "awkward_head_cue_title",
            "impossible_marine_wing_cue",
            "impossible_hoofed_wing_or_fin_cue",
            "impossible_bird_hoof_cue",
            "impossible_non_primate_hand_cue",
            "awkward_plural_loop_line",
            "generic_clickbait_language",
            "generic_hiding_plain_sight",
            "robotic_not_random_line",
            "generic_payoff_filler",
            "robotic_memory_title",
            "bad_domain_plural",
            "awkward_uncountable_one_cue",
            "awkward_non_animal_use_pronoun",
            "anthropomorphic_nature_read_moment",
            "bad_plural_verb",
            "bad_singular_subject_verb",
            "bad_because_changes",
            "truncated_heres_title",
            "stitched_category_title",
            "stitched_repeated_animal_title",
            "script_length_risk",
            "script_hook_mismatch",
            "robotic_rely_loop",
            "generic_retention_scaffold",
        )
    ):
        return story, False
    out = dict(story)
    text = " ".join(str(out.get(k) or "") for k in ("title", "seo_title", "hook", "script", "category"))
    visual_text = " ".join(
        str(value or "")
        for value in (
            out.get("source_url"),
            out.get("url"),
            out.get("source_title"),
            out.get("raw_title"),
            _source_context(out),
            out.get("title"),
            out.get("category"),
        )
    )
    animal = _animal(visual_text)
    if animal == "Animals":
        animal = extract_animal(out)
    if animal.lower() == "animal":
        animal = _animal(text)
    angle_package = build_curiosity_package(out, subject=_plural_subject(animal), context=visual_text, force=True)
    original_title_key = _title_key(out.get("seo_title") or out.get("title") or "")
    if angle_package:
        if set(reasons) & {"duplicate_script", "duplicate_angle"}:
            collision = _collision_rescue_variant(out, angle_package, animal)
            if collision:
                candidate = dict(out)
                candidate.update(collision)
                candidate["local_rewrite"] = {
                    "applied": True,
                    "reasons": reasons,
                    "method": "curiosity_angle_collision_rescue",
                    "angle_key": angle_package.get("angle_key"),
                }
                if not editorial_issues(candidate):
                    return candidate, True
        candidate = dict(out)
        candidate.update(
            {
                "seo_title": str(angle_package["seo_title"])[:60],
                "title": str(angle_package["title"])[:60],
                "hook": angle_package["hook"],
                "script": angle_package["script"],
                "lead": angle_package["lead"],
                "thumbnail_text": angle_package["thumbnail_text"],
                "story_format": angle_package["story_format"],
                "yt_tags": _clean_tags(
                    angle_package.get("yt_tags"),
                    str(angle_package.get("subject") or animal).lower(),
                    str(out.get("category") or ""),
                ),
                "local_rewrite": {
                    "applied": True,
                    "reasons": reasons,
                    "method": "curiosity_angle_rescue",
                    "angle_key": angle_package.get("angle_key"),
                },
            }
        )
        candidate_title_key = _title_key(candidate.get("seo_title") or candidate.get("title") or "")
        still_duplicate_title = "duplicate_title" in reasons and candidate_title_key == original_title_key
        if still_duplicate_title:
            contextual = _duplicate_context_variant(out, str(angle_package.get("subject") or animal), visual_text)
            if contextual and _title_key(contextual.get("seo_title") or contextual.get("title")) != original_title_key:
                candidate.update(contextual)
                local_rewrite = dict(candidate.get("local_rewrite") or {})
                local_rewrite["method"] = "contextual_duplicate_title_rescue"
                candidate["local_rewrite"] = local_rewrite
                still_duplicate_title = False
        if still_duplicate_title:
            alternate_title = _title_from_hook(candidate.get("hook") or candidate.get("script") or "")
            if alternate_title and _title_key(alternate_title) != original_title_key:
                candidate["seo_title"] = alternate_title
                candidate["title"] = alternate_title
                local_rewrite = dict(candidate.get("local_rewrite") or {})
                local_rewrite["method"] = "curiosity_angle_duplicate_title_rescue"
                candidate["local_rewrite"] = local_rewrite
                still_duplicate_title = False
        if not still_duplicate_title and not editorial_issues(candidate):
            return candidate, True
    if "duplicate_title" in reasons:
        contextual = _duplicate_context_variant(out, animal, visual_text)
        if contextual:
            candidate = dict(out)
            candidate.update(contextual)
            candidate["local_rewrite"] = {
                "applied": True,
                "reasons": reasons,
                "method": "contextual_duplicate_title_rescue",
            }
            if not editorial_issues(candidate):
                return candidate, True
    if _is_nature_subject(animal):
        return story, False
    fmt = classify_format(text)
    cue = _usable_cue(extract_cue(out), animal)
    action = _usable_action(extract_action(out), fmt)
    subject = _plural_subject(animal)
    lower_subject = _lower_plural_subject(animal)
    read_verb = _verb(animal, "read")
    reveal_verb = _verb(animal, "reveal")
    signal_verb = _verb(animal, "signal")
    use_verb = _verb(animal, "use")
    benefit = _benefit(action, fmt)
    cue_reference = _cue_reference(cue)
    cue_object_pronoun = _cue_object_pronoun(cue)
    reason_clause = _reason_clause(
        animal=animal,
        lower_subject=lower_subject,
        cue_object_pronoun=cue_object_pronoun,
        benefit=benefit,
        use_verb=use_verb,
    )
    if _is_nature_subject(animal):
        title = f"{subject} {signal_verb} through {_cue_signal(cue)}"
        hook = f"{subject} {signal_verb} through {_cue_signal(cue)}."
    elif "duplicate_title" in reasons:
        title = f"{subject} show why {_cue_signal(cue)} matters"
        hook = f"{subject} {reveal_verb} the {_cue_signal(cue)} in seconds."
    elif fmt == "animal_memory":
        if cue in {"face", "faces", "face cue", "eye contact", "eyes"}:
            title = f"{subject} remember familiar faces by sight"
            hook = f"{subject} recognize familiar faces."
        else:
            title = f"{subject} react differently when {_cue_moment(cue)}"
            hook = f"{subject} {read_verb} the {_cue_signal(cue)} fast."
    elif fmt == "body_superpower":
        if action == "signal":
            title = f"{subject} use {_cue_signal(cue)} to solve a problem"
            hook = f"{subject} use {_cue_signal(cue)} for a reason."
        else:
            title = f"{subject} rely on {cue} to {action}"
            hook = f"{subject} rely on {cue}."
    else:
        title = f"{subject} reveal the answer with {_cue_signal(cue)}"
        hook = f"{subject} {reveal_verb} the {_cue_signal(cue)} fast."
    script = (
        f"{hook} Watch {cue_reference}, because {reason_clause}. "
        f"That detail changes the next decision in the scene and gives viewers a reason "
        f"to look back at the opening shot. Which {lower_subject} detail should we decode next?"
    )
    out.update(
        {
            "seo_title": title[:60],
            "title": title[:60],
            "hook": hook,
            "script": script,
            "lead": script[:400],
            "thumbnail_text": _thumbnail_label(cue),
            "yt_tags": _clean_tags(out.get("yt_tags"), lower_subject, str(out.get("category") or "")),
            "local_rewrite": {"applied": True, "reasons": reasons, "method": "deterministic_rescue"},
        }
    )
    if editorial_issues(out):
        return story, False
    return out, True
