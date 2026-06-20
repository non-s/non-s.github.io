"""Deterministic animal curiosity angles for Wild Brief packaging.

The generator can drift toward generic "movement/cue" copy when the source
clip has little metadata. This file gives the local pipeline a concrete,
animal-specific fallback before a story reaches upload.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CuriosityAngle:
    key: str
    keywords: tuple[str, ...]
    title_template: str
    hook_template: str
    script_template: str
    thumbnail_text: str
    cue: str
    story_format: str
    tags: tuple[str, ...]


ANIMAL_ALIASES = {
    "ant": "ant",
    "ants": "ant",
    "bear": "bear",
    "bears": "bear",
    "bee": "bee",
    "bees": "bee",
    "bumblebee": "bee",
    "bumblebees": "bee",
    "beetle": "beetle",
    "beetles": "beetle",
    "bird": "bird",
    "birds": "bird",
    "butterfly": "butterfly",
    "butterflies": "butterfly",
    "cat": "cat",
    "cats": "cat",
    "kitten": "cat",
    "kittens": "cat",
    "chicken": "chicken",
    "chickens": "chicken",
    "cow": "cow",
    "cows": "cow",
    "deer": "deer",
    "dog": "dog",
    "dogs": "dog",
    "puppy": "dog",
    "puppies": "dog",
    "dolphin": "dolphin",
    "dolphins": "dolphin",
    "dragonfly": "dragonfly",
    "dragonflies": "dragonfly",
    "duck": "duck",
    "ducks": "duck",
    "duckling": "duckling",
    "ducklings": "duckling",
    "elephant": "elephant",
    "elephants": "elephant",
    "fox": "fox",
    "foxes": "fox",
    "goat": "goat",
    "goats": "goat",
    "horse": "horse",
    "horses": "horse",
    "lion": "lion",
    "lions": "lion",
    "macaw": "macaw",
    "macaws": "macaw",
    "mantis": "mantis",
    "mantises": "mantis",
    "monkey": "monkey",
    "monkeys": "monkey",
    "octopus": "octopus",
    "octopuses": "octopus",
    "orangutan": "orangutan",
    "orangutans": "orangutan",
    "owl": "owl",
    "owls": "owl",
    "parrot": "parrot",
    "parrots": "parrot",
    "penguin": "penguin",
    "penguins": "penguin",
    "seal": "seal",
    "seals": "seal",
    "shark": "shark",
    "sharks": "shark",
    "sheep": "sheep",
    "snake": "snake",
    "snakes": "snake",
    "tiger": "tiger",
    "tigers": "tiger",
    "turtle": "turtle",
    "turtles": "turtle",
    "whale": "whale",
    "whales": "whale",
    "wolf": "wolf",
    "wolves": "wolf",
}

PLURAL_DISPLAY = {
    "ant": "Ants",
    "bear": "Bears",
    "bee": "Bees",
    "beetle": "Beetles",
    "bird": "Birds",
    "butterfly": "Butterflies",
    "cat": "Cats",
    "chicken": "Chickens",
    "cow": "Cows",
    "deer": "Deer",
    "dog": "Dogs",
    "dolphin": "Dolphins",
    "dragonfly": "Dragonflies",
    "duck": "Ducks",
    "duckling": "Ducklings",
    "elephant": "Elephants",
    "fox": "Foxes",
    "goat": "Goats",
    "horse": "Horses",
    "lion": "Lions",
    "macaw": "Macaws",
    "mantis": "Mantises",
    "monkey": "Monkeys",
    "octopus": "Octopuses",
    "orangutan": "Orangutans",
    "owl": "Owls",
    "parrot": "Parrots",
    "penguin": "Penguins",
    "seal": "Seals",
    "shark": "Sharks",
    "sheep": "Sheep",
    "snake": "Snakes",
    "tiger": "Tigers",
    "turtle": "Turtles",
    "whale": "Whales",
    "wolf": "Wolves",
}

NATURE_ALIASES = {
    "plant": "plants",
    "plants": "plants",
    "leaf": "plants",
    "leaves": "plants",
    "flower": "plants",
    "flowers": "plants",
    "tree": "trees",
    "trees": "trees",
    "root": "trees",
    "roots": "trees",
    "ring": "trees",
    "rings": "trees",
    "forest": "forests",
    "forests": "forests",
    "canopy": "forests",
    "rainforest": "forests",
    "fungi": "fungi",
    "fungus": "fungi",
    "mushroom": "fungi",
    "mushrooms": "fungi",
    "mycelium": "fungi",
    "river": "rivers",
    "rivers": "rivers",
    "stream": "rivers",
    "waterfall": "rivers",
    "delta": "rivers",
    "bank": "rivers",
    "banks": "rivers",
    "bend": "rivers",
    "bends": "rivers",
    "mountain": "mountains",
    "mountains": "mountains",
    "glacier": "mountains",
    "glaciers": "mountains",
    "volcano": "volcanoes",
    "volcanoes": "volcanoes",
    "lava": "volcanoes",
    "magma": "volcanoes",
    "crater": "volcanoes",
    "storm": "weather",
    "storms": "weather",
    "weather": "weather",
    "sky": "weather",
    "skies": "weather",
    "cloudy": "weather",
    "overcast": "weather",
    "cloud": "weather",
    "clouds": "weather",
    "lightning": "weather",
    "tornado": "weather",
    "aurora": "rare_phenomena",
    "eclipse": "rare_phenomena",
    "bioluminescence": "rare_phenomena",
    "bioluminescent": "rare_phenomena",
    "rock": "geology",
    "rocks": "geology",
    "geology": "geology",
    "mineral": "geology",
    "minerals": "geology",
    "crystal": "geology",
    "crystals": "geology",
    "cave": "geology",
    "caves": "geology",
    "canyon": "geology",
    "canyons": "geology",
    "badlands": "geology",
    "geyser": "geology",
    "geothermal": "geology",
    "terrain": "geology",
    "ecosystem": "ecosystems",
    "ecosystems": "ecosystems",
    "habitat": "ecosystems",
    "habitats": "ecosystems",
    "coral": "ecosystems",
    "reef": "ecosystems",
    "earth": "earth_from_space",
    "planet": "earth_from_space",
    "atmosphere": "earth_from_space",
    "satellite": "earth_from_space",
    "hurricane": "earth_from_space",
    "conservation": "conservation",
    "restoration": "conservation",
    "reforestation": "conservation",
    "mangrove": "conservation",
    "mangroves": "conservation",
    "science": "discoveries",
    "research": "discoveries",
    "fossil": "discoveries",
    "fossils": "discoveries",
    "space": "space",
    "moon": "space",
    "mars": "space",
    "sun": "space",
    "solar": "space",
    "galaxy": "space",
    "nebula": "space",
    "orbit": "space",
    "rocket": "space",
    "physics": "physics",
    "magnet": "physics",
    "magnets": "physics",
    "magnetic": "physics",
    "pendulum": "physics",
    "prism": "physics",
    "spectrum": "physics",
    "light": "physics",
    "wave": "physics",
    "electricity": "physics",
    "electric": "physics",
    "fluid": "physics",
    "chemistry": "chemistry",
    "chemical": "chemistry",
    "reaction": "chemistry",
    "reactions": "chemistry",
    "flame": "chemistry",
    "electrolysis": "chemistry",
    "sublimation": "chemistry",
    "laboratory": "chemistry",
    "microscope": "microscopy",
    "microscopy": "microscopy",
    "cell": "microscopy",
    "cells": "microscopy",
    "bacteria": "microscopy",
    "microbe": "microscopy",
    "microbes": "microscopy",
    "algae": "microscopy",
}

NATURE_DISPLAY = {
    "plants": "Plants",
    "trees": "Trees",
    "forests": "Forests",
    "fungi": "Mushrooms",
    "rivers": "Rivers",
    "mountains": "Glaciers",
    "volcanoes": "Lava",
    "weather": "Lightning",
    "rare_phenomena": "Auroras",
    "geology": "Rock layers",
    "ecosystems": "Coral reefs",
    "earth_from_space": "Storm clouds",
    "conservation": "Mangroves",
    "discoveries": "Fossils",
    "space": "The moon",
    "physics": "Magnets",
    "chemistry": "Crystals",
    "microscopy": "Cells",
}


def _angle(
    *,
    key: str,
    keywords: tuple[str, ...],
    title: str,
    hook: str,
    script_body: str,
    thumbnail: str,
    cue: str,
    story_format: str = "animal_intelligence",
    tags: tuple[str, ...] = (),
) -> CuriosityAngle:
    return CuriosityAngle(
        key=key,
        keywords=keywords,
        title_template=title,
        hook_template=hook,
        script_template="{hook} " + script_body,
        thumbnail_text=thumbnail,
        cue=cue,
        story_format=story_format,
        tags=tags,
    )


ANGLE_LIBRARY: dict[str, tuple[CuriosityAngle, ...]] = {
    "ant": (
        _angle(
            key="ant_scent_roads",
            keywords=("trail", "line", "food", "colony", "follow", "scent"),
            title="{subject} lay scent roads other ants can follow",
            hook="{subject} leave invisible roads for the colony.",
            script_body=(
                "Watch the line tighten near the food, because each ant can add a chemical trail "
                "the next worker reads. A busy trail gets stronger, so the colony turns scattered "
                "searching into one tiny highway. Which insect map should come next?"
            ),
            thumbnail="SCENT ROAD",
            cue="scent road",
            tags=("ants", "scent trail", "insect behavior"),
        ),
    ),
    "bear": (
        _angle(
            key="bear_super_smell",
            keywords=("smell", "nose", "food", "sniff", "forest"),
            title="{subject} smell food from miles away",
            hook="{subject} can smell a meal long before seeing it.",
            script_body=(
                "Watch the nose first, because smell drives many bear decisions before the eyes "
                "do. That huge scent map helps them find food, avoid danger, and read who crossed "
                "the area earlier. Would you trust your nose that much?"
            ),
            thumbnail="SCENT MAP",
            cue="scent map",
            story_format="body_superpower",
            tags=("bears", "smell", "animal senses"),
        ),
    ),
    "bee": (
        _angle(
            key="bee_dance_map",
            keywords=("dance", "hive", "flower", "nectar", "pollen", "wing", "food"),
            title="{subject} dance directions back to the hive",
            hook="{subject} can point the hive toward food.",
            script_body=(
                "Watch the body angle, because a bee dance can carry direction and distance. "
                "The hive reads that pattern like a living map, then sends more workers to the "
                "same flowers. Tiny body, huge navigation system. Which insect should we decode next?"
            ),
            thumbnail="DANCE MAP",
            cue="dance map",
            story_format="animal_intelligence",
            tags=("bees", "waggle dance", "insect navigation"),
        ),
    ),
    "beetle": (
        _angle(
            key="beetle_star_steering",
            keywords=("dung", "ball", "night", "stars", "steer", "walking"),
            title="{subject} can steer by the Milky Way",
            hook="{subject} can use the night sky like a compass.",
            script_body=(
                "Watch the straight path, because some dung beetles use sky patterns to keep "
                "from circling back into rivals. That celestial shortcut helps a tiny insect roll "
                "food away fast. Would you expect a beetle to use astronomy?"
            ),
            thumbnail="STAR COMPASS",
            cue="star compass",
            story_format="animal_intelligence",
            tags=("beetles", "navigation", "insect facts"),
        ),
    ),
    "bird": (
        _angle(
            key="bird_uv_vision",
            keywords=("color", "feather", "flower", "bright", "wing", "eye"),
            title="{subject} see ultraviolet patterns we miss",
            hook="{subject} see colors humans cannot see.",
            script_body=(
                "Watch the feathers and eyes, because many birds see ultraviolet detail hidden "
                "from us. That extra color can help with mates, food, and navigation. The same "
                "scene is richer to them than it is to us. Which bird fact next?"
            ),
            thumbnail="UV VISION",
            cue="ultraviolet vision",
            story_format="body_superpower",
            tags=("birds", "uv vision", "animal senses"),
        ),
    ),
    "butterfly": (
        _angle(
            key="butterfly_wing_scales",
            keywords=("wing", "wings", "color", "pattern", "flash"),
            title="{subject} carry color on tiny wing scales",
            hook="{subject} are covered in tiny color scales.",
            script_body=(
                "Watch the wing surface, because butterfly color often comes from thousands of "
                "tiny overlapping scales. Some scales use pigment, and others bend light itself. "
                "That is why one wing can look painted up close. Which tiny detail should we zoom into next?"
            ),
            thumbnail="WING SCALES",
            cue="wing scales",
            story_format="body_superpower",
            tags=("butterflies", "wing scales", "insect facts"),
        ),
        _angle(
            key="butterfly_taste_feet",
            keywords=("flower", "nectar", "feet", "foot", "land", "feeding"),
            title="{subject} taste flowers with their feet",
            hook="{subject} can taste a flower by landing on it.",
            script_body=(
                "Watch the feet touch first, because butterflies have taste sensors there. Landing "
                "helps them test whether a plant is food, a nursery, or a waste of energy. The meal "
                "check starts before the mouth even opens. Would you spot that?"
            ),
            thumbnail="TASTE FEET",
            cue="taste feet",
            story_format="body_superpower",
            tags=("butterflies", "taste sensors", "insect behavior"),
        ),
    ),
    "cat": (
        _angle(
            key="cat_grooming_reset",
            keywords=("groom", "grooming", "lick", "window", "fur", "coat", "paw"),
            title="{subject} groom to reset their scent map",
            hook="{subject} use grooming to reset their scent map.",
            script_body=(
                "Watch the tongue and paw movements, because grooming spreads familiar scent across the coat. "
                "That can help a cat settle after a tense moment and keep the fur ready for the next move. "
                "The cleanup is also a signal. Which pet behavior should we decode next?"
            ),
            thumbnail="GROOMING SIGNAL",
            cue="grooming signal",
            story_format="body_superpower",
            tags=("cats", "grooming", "cat behavior"),
        ),
        _angle(
            key="cat_whisker_ruler",
            keywords=("whisker", "face", "jump", "gap", "night", "purr"),
            title="{subject} use whiskers like built-in rulers",
            hook="{subject} measure tight spaces with their whiskers.",
            script_body=(
                "Watch the whiskers near the face, because they sense tiny touches and air changes. "
                "That helps cats judge gaps, hunt in low light, and protect their eyes before contact. "
                "The face is doing math. What pet sense should we test next?"
            ),
            thumbnail="WHISKER MAP",
            cue="whisker map",
            story_format="body_superpower",
            tags=("cats", "whiskers", "animal senses"),
        ),
    ),
    "chicken": (
        _angle(
            key="chicken_steady_eyes",
            keywords=("head", "tilt", "walk", "walking", "movement"),
            title="{subject} keep their view steady while walking",
            hook="{subject} lock their view between steps.",
            script_body=(
                "Watch the eyes stay level while the body steps forward, because chickens stabilize "
                "their view in tiny pauses. That helps them judge distance and spot danger without "
                "the world blurring. Once you see the pause, the walk feels different. Did you notice it?"
            ),
            thumbnail="STEADY EYES",
            cue="steady eyes",
            story_format="body_superpower",
            tags=("chickens", "vision", "animal behavior"),
        ),
        _angle(
            key="chicken_face_memory",
            keywords=("face", "faces", "flock", "remember", "recognize"),
            title="{subject} remember familiar faces in the flock",
            hook="{subject} can remember individual faces.",
            script_body=(
                "Watch the face and posture first, because chickens learn who is familiar inside "
                "the flock. That memory helps them choose who to follow, avoid, or challenge. The "
                "tiny stare is not empty. Would you recognize the same bird twice?"
            ),
            thumbnail="FACE MEMORY",
            cue="face memory",
            story_format="animal_memory",
            tags=("chickens", "face memory", "farm animals"),
        ),
    ),
    "cow": (
        _angle(
            key="cow_face_memory",
            keywords=("face", "herd", "remember", "friend", "calf"),
            title="{subject} remember faces across the herd",
            hook="{subject} can remember who belongs in the herd.",
            script_body=(
                "Watch the calm face first, because cows can recognize familiar herd members and "
                "people. That memory lowers stress when the group feels predictable. A quiet look can "
                "carry more history than it seems. Which farm animal should we explain next?"
            ),
            thumbnail="HERD MEMORY",
            cue="herd memory",
            story_format="animal_memory",
            tags=("cows", "herd memory", "farm animals"),
        ),
    ),
    "deer": (
        _angle(
            key="deer_ear_radar",
            keywords=("ear", "ears", "listen", "freeze", "forest", "danger"),
            title="{subject} aim their ears like sound radar",
            hook="{subject} can aim each ear toward danger.",
            script_body=(
                "Watch the ears first, because deer can turn them to sample sound from different "
                "directions. That quick listening check helps them decide whether to freeze, flee, "
                "or keep feeding. One quiet second tells the whole body what to do. Would you freeze?"
            ),
            thumbnail="SOUND RADAR",
            cue="sound radar",
            story_format="body_superpower",
            tags=("deer", "hearing", "wildlife"),
        ),
    ),
    "dog": (
        _angle(
            key="dog_pointing",
            keywords=("point", "human", "person", "hand", "training", "play"),
            title="{subject} read human pointing surprisingly well",
            hook="{subject} can follow a human point fast.",
            script_body=(
                "Watch the eyes check the person, because dogs are unusually good at using human "
                "gestures. That skill helps them cooperate with us before any command gets repeated. "
                "The small glance is social intelligence, not random obedience. What dog skill should come next?"
            ),
            thumbnail="HUMAN SIGNAL",
            cue="human pointing",
            story_format="animal_intelligence",
            tags=("dogs", "human pointing", "animal intelligence"),
        ),
        _angle(
            key="dog_scent_map",
            keywords=("nose", "smell", "sniff", "trail", "snow"),
            title="{subject} read the world through scent maps",
            hook="{subject} build a map with smell.",
            script_body=(
                "Watch the nose before the feet, because every sniff samples layers of scent. Dogs "
                "can learn who passed, where they moved, and what changed since the last check. The "
                "ground is basically a news feed. What should they sniff next?"
            ),
            thumbnail="SCENT MAP",
            cue="scent map",
            story_format="body_superpower",
            tags=("dogs", "scent", "animal senses"),
        ),
    ),
    "dolphin": (
        _angle(
            key="dolphin_signature_whistle",
            keywords=("call", "sound", "whistle", "name", "pod", "swim"),
            title="{subject} use signature whistles like names",
            hook="{subject} can call each other with signature whistles.",
            script_body=(
                "Watch the group spacing, because dolphins use sound to keep track of individuals "
                "in open water. A signature whistle works like a personal label, helping the pod "
                "reconnect when visibility drops. Ocean social life is loud. Which sound should we decode next?"
            ),
            thumbnail="DOLPHIN NAME",
            cue="signature whistle",
            story_format="animal_intelligence",
            tags=("dolphins", "signature whistle", "ocean animals"),
        ),
    ),
    "dragonfly": (
        _angle(
            key="dragonfly_motion_lock",
            keywords=("fly", "prey", "wing", "hunt", "air"),
            title="{subject} lock onto prey in midair",
            hook="{subject} track prey with extreme precision.",
            script_body=(
                "Watch the eyes before the flight path, because dragonflies process motion fast. "
                "They can predict where prey is going, then adjust in the air like a tiny interceptor. "
                "That is why the catch looks impossibly clean. Would you see it coming?"
            ),
            thumbnail="MOTION LOCK",
            cue="motion lock",
            story_format="body_superpower",
            tags=("dragonflies", "predator", "insect facts"),
        ),
    ),
    "duck": (
        _angle(
            key="duck_fake_injury",
            keywords=("fake", "injury", "broken", "wing", "nest", "predator", "young", "duckling"),
            title="{subject} fake injuries to protect their young",
            hook="{subject} can act injured to pull danger away.",
            script_body=(
                "Watch the low, awkward display, because some ducks use a distraction act near "
                "the nest. Predators chase the easier target while the young stay hidden. The drama "
                "is a decoy, not weakness. Would you fall for the trick?"
            ),
            thumbnail="FAKE INJURY",
            cue="injury display",
            story_format="survival_trick",
            tags=("ducks", "fake injury", "bird behavior"),
        ),
        _angle(
            key="duck_waterproof_feathers",
            keywords=("water", "swim", "feather", "rain", "pond"),
            title="{subject} carry waterproof oil on their feathers",
            hook="{subject} keep water sliding off their feathers.",
            script_body=(
                "Watch the feathers after the splash, because ducks spread oil from a gland near "
                "the tail. That coating helps water bead away, keeping the body warmer and lighter. "
                "The pond looks easy because the feather coat is engineered. Would you test it?"
            ),
            thumbnail="WATERPROOF",
            cue="waterproof feathers",
            story_format="body_superpower",
            tags=("ducks", "waterproof feathers", "bird facts"),
        ),
    ),
    "duckling": (
        _angle(
            key="duckling_number_sense",
            keywords=("math", "number", "group", "count", "swim", "duckling"),
            title="{subject} compare groups before they swim",
            hook="{subject} can notice which group is bigger.",
            script_body=(
                "Watch which group they follow, because young ducklings can compare simple amounts "
                "surprisingly early. That number sense helps them stay near safer groups instead of "
                "wandering alone. Tiny feet, useful math. Which baby animal should we test next?"
            ),
            thumbnail="TINY MATH",
            cue="number sense",
            story_format="animal_intelligence",
            tags=("ducklings", "number sense", "bird behavior"),
        ),
        _angle(
            key="duckling_imprint",
            keywords=("follow", "mother", "baby", "duckling", "line"),
            title="{subject} imprint on the first safe guide",
            hook="{subject} can lock onto a guide fast.",
            script_body=(
                "Watch who they follow first, because ducklings quickly learn the safe moving shape "
                "near them after hatching. That imprinting keeps the group together before they can "
                "judge the world alone. The line is survival, not cuteness. Would you lead them right?"
            ),
            thumbnail="FIRST GUIDE",
            cue="imprinting",
            story_format="animal_intelligence",
            tags=("ducklings", "imprinting", "bird behavior"),
        ),
    ),
    "elephant": (
        _angle(
            key="elephant_ear_cooling",
            keywords=("ear", "ears", "heat", "hot", "cool", "walk"),
            title="{subject} cool blood through giant ears",
            hook="{subject} use their ears as living radiators.",
            script_body=(
                "Watch the ear surface, because warm blood flows through those broad veins. Moving "
                "air can dump heat before it spreads through the body. That is why the ears are more "
                "than decoration in hot places. Which giant animal trick next?"
            ),
            thumbnail="EAR RADIATOR",
            cue="ear radiator",
            story_format="body_superpower",
            tags=("elephants", "ears", "animal facts"),
        ),
        _angle(
            key="elephant_foot_hearing",
            keywords=("ground", "foot", "feet", "rumble", "herd"),
            title="{subject} can feel rumbles through the ground",
            hook="{subject} can sense low rumbles underfoot.",
            script_body=(
                "Watch the feet and stillness, because low elephant calls can travel through ground "
                "as vibrations. The herd can pick up distant signals before a human would hear much "
                "at all. Big bodies, subtle messages. Would you notice the signal?"
            ),
            thumbnail="GROUND SIGNAL",
            cue="ground signal",
            story_format="body_superpower",
            tags=("elephants", "vibration", "animal communication"),
        ),
    ),
    "fox": (
        _angle(
            key="fox_snow_hearing",
            keywords=("snow", "listen", "jump", "hunt", "mouse"),
            title="{subject} hear tiny prey under snow",
            hook="{subject} can hunt sounds hidden under snow.",
            script_body=(
                "Watch the pause before the leap, because foxes can aim at prey they cannot see. "
                "Their ears help triangulate faint rustles under snow or grass. The jump is the last "
                "step of a sound puzzle. Would you hear it?"
            ),
            thumbnail="SNOW HEARING",
            cue="snow hearing",
            story_format="body_superpower",
            tags=("foxes", "hearing", "wildlife"),
        ),
    ),
    "goat": (
        _angle(
            key="goat_wide_pupils",
            keywords=("eye", "eyes", "pupil", "danger", "field", "farm"),
            title="{subject} use wide pupils to watch danger",
            hook="{subject} see wide with rectangular pupils.",
            script_body=(
                "Watch the eyes from the side, because rectangular pupils give grazing animals a "
                "wide view of the horizon. That helps goats feed while still checking for danger. "
                "The weird eye shape is a safety system. Which farm detail should we decode next?"
            ),
            thumbnail="WIDE VISION",
            cue="wide pupils",
            story_format="body_superpower",
            tags=("goats", "rectangular pupils", "farm animals"),
        ),
        _angle(
            key="goat_feeding_memory",
            keywords=("bottle", "feeding", "milk", "baby", "voice"),
            title="{subject} learn feeding routines fast",
            hook="{subject} can learn who brings the bottle.",
            script_body=(
                "Watch the rush toward the feeder, because young goats quickly link voices, smells, "
                "and routines with food. That learning helps them find care in a busy herd. The cute "
                "moment is also memory at work. Would they remember you?"
            ),
            thumbnail="BOTTLE MEMORY",
            cue="feeding memory",
            story_format="cute_behavior",
            tags=("goats", "feeding", "farm animals"),
        ),
    ),
    "horse": (
        _angle(
            key="horse_ear_focus",
            keywords=("ear", "ears", "listen", "focus", "attention", "position"),
            title="{subject} point their ears toward what matters",
            hook="{subject} show attention with their ears.",
            script_body=(
                "Watch the ears before the body moves, because each ear can turn toward a sound "
                "or animal the horse is tracking. That small shift shows where attention is going "
                "before the next step. The ears are a radar dish, not decoration. Would you spot it?"
            ),
            thumbnail="EAR RADAR",
            cue="ear focus",
            story_format="animal_intelligence",
            tags=("horses", "ears", "farm animals"),
        ),
        _angle(
            key="horse_standing_sleep",
            keywords=("sleep", "stand", "leg", "field", "rest"),
            title="{subject} sleep standing without falling over",
            hook="{subject} can lock their legs while resting.",
            script_body=(
                "Watch the legs when the body looks calm, because horses have a stay apparatus "
                "that helps support them while they rest. It lets them doze and react quickly if "
                "danger appears. The nap is built for speed. Would you sleep like that?"
            ),
            thumbnail="LOCKED LEGS",
            cue="locked legs",
            story_format="body_superpower",
            tags=("horses", "sleep", "farm animals"),
        ),
        _angle(
            key="horse_face_memory",
            keywords=("face", "remember", "human", "friend", "watch"),
            title="{subject} remember familiar faces for months",
            hook="{subject} can remember familiar faces.",
            script_body=(
                "Watch the eyes and ears, because horses can learn who is familiar and who feels "
                "safe. That memory changes how calmly they approach people and other horses. The "
                "look is part recognition, part decision. Which herd animal next?"
            ),
            thumbnail="FACE MEMORY",
            cue="face memory",
            story_format="animal_memory",
            tags=("horses", "face memory", "farm animals"),
        ),
    ),
    "lion": (
        _angle(
            key="lion_ear_marks",
            keywords=("ear", "ears", "cub", "pride", "follow", "dark"),
            title="{subject} use dark ear marks to guide cubs",
            hook="{subject} have dark ear marks cubs can follow.",
            script_body=(
                "Watch the backs of the ears, because those dark marks can stand out when a lion "
                "moves through grass. For cubs, that contrast helps track the adult ahead. The detail "
                "is small, but the pride depends on staying together. Would you spot it?"
            ),
            thumbnail="EAR MARKS",
            cue="ear marks",
            story_format="survival_trick",
            tags=("lions", "ear marks", "wildlife"),
        ),
        _angle(
            key="lion_pride_hunt",
            keywords=("hunt", "hunting", "noise", "quiet", "sound", "predator", "group", "pride", "lioness", "stalk"),
            title="{subject} hunt better when the pride coordinates",
            hook="{subject} turn hunting into a team problem.",
            script_body=(
                "Watch the spacing before the chase, because lions can use different positions in "
                "a group hunt. One animal pressures while another blocks the escape path. The power "
                "is not just muscle. Which predator tactic should we break down next?"
            ),
            thumbnail="PRIDE PLAN",
            cue="pride plan",
            story_format="animal_intelligence",
            tags=("lions", "group hunting", "wildlife"),
        ),
    ),
    "macaw": (
        _angle(
            key="macaw_beak_tool",
            keywords=("beak", "climb", "branch", "seed", "parrot"),
            title="{subject} use beaks like climbing tools",
            hook="{subject} use their beak like a third foot.",
            script_body=(
                "Watch the beak touch before the feet move, because macaws use it for grip, balance, "
                "and testing branches. That tool also cracks tough food. The face is helping the body "
                "climb. Which bird tool should come next?"
            ),
            thumbnail="BEAK TOOL",
            cue="beak tool",
            story_format="body_superpower",
            tags=("macaws", "beak", "bird facts"),
        ),
    ),
    "mantis": (
        _angle(
            key="mantis_3d_vision",
            keywords=("eye", "eyes", "strike", "hunt", "front", "leg"),
            title="{subject} judge distance with 3D vision",
            hook="{subject} can measure a strike in 3D.",
            script_body=(
                "Watch the head and front legs, because mantises use depth vision to judge when "
                "prey is close enough. That distance check makes the strike look sudden, but the "
                "math happened first. Tiny hunter, serious geometry. Would you see the setup?"
            ),
            thumbnail="3D STRIKE",
            cue="3d vision",
            story_format="body_superpower",
            tags=("mantis", "3d vision", "insect facts"),
        ),
    ),
    "monkey": (
        _angle(
            key="monkey_food_washing",
            keywords=("food", "water", "wash", "hand", "sand", "stone"),
            title="{subject} wash food when grit gets annoying",
            hook="{subject} can change habits to solve small problems.",
            script_body=(
                "Watch the hands near the food, because some monkeys learn useful routines from "
                "their group. Washing or handling food differently can remove grit and make eating "
                "easier. The habit spreads because it works. Which primate trick should come next?"
            ),
            thumbnail="SMART HANDS",
            cue="learned habit",
            story_format="animal_intelligence",
            tags=("monkeys", "learned behavior", "primates"),
        ),
    ),
    "octopus": (
        _angle(
            key="octopus_taste_arms",
            keywords=("arm", "arms", "touch", "rock", "hide", "color"),
            title="{subject} taste objects with their arms",
            hook="{subject} can taste what their arms touch.",
            script_body=(
                "Watch the arms explore first, because octopus suckers contain sensors for touch "
                "and chemistry. That means an arm can inspect food, texture, and danger without "
                "waiting for the head. The whole body is curious. Which ocean animal next?"
            ),
            thumbnail="TASTE ARMS",
            cue="taste arms",
            story_format="body_superpower",
            tags=("octopus", "arms", "ocean animals"),
        ),
    ),
    "orangutan": (
        _angle(
            key="orangutan_leaf_umbrella",
            keywords=("leaf", "rain", "tool", "hand", "forest"),
            title="{subject} use leaves like rain umbrellas",
            hook="{subject} turn forest leaves into tools.",
            script_body=(
                "Watch the hands choose the leaf, because orangutans are skilled problem solvers. "
                "A leaf can become cover, a glove, or a sound tool depending on the moment. The "
                "forest is full of objects they can repurpose. Which ape tool next?"
            ),
            thumbnail="LEAF TOOL",
            cue="leaf tool",
            story_format="animal_intelligence",
            tags=("orangutans", "tool use", "primates"),
        ),
    ),
    "owl": (
        _angle(
            key="owl_silent_feathers",
            keywords=("fly", "wing", "night", "hunt", "silent", "feather"),
            title="{subject} fly silently because feathers break sound",
            hook="{subject} can make a hunt almost silent.",
            script_body=(
                "Watch the wing edge, because owl feathers have soft fringes that break up noisy "
                "airflow. That quiet flight helps them hear prey and arrive without warning. The "
                "silence is built into the feather. Would you hear the landing?"
            ),
            thumbnail="SILENT WINGS",
            cue="silent feathers",
            story_format="body_superpower",
            tags=("owls", "silent flight", "bird facts"),
        ),
    ),
    "parrot": (
        _angle(
            key="parrot_beak_foot",
            keywords=("beak", "climb", "talk", "seed", "branch"),
            title="{subject} use their beak like a third foot",
            hook="{subject} climb with help from their beak.",
            script_body=(
                "Watch the beak touch before the body shifts, because parrots use it for grip and "
                "balance. The beak is also a food tool, a tester, and a climber. That face is doing "
                "real work. Which bird skill should we decode next?"
            ),
            thumbnail="BEAK GRIP",
            cue="beak grip",
            story_format="body_superpower",
            tags=("parrots", "beak", "bird facts"),
        ),
    ),
    "penguin": (
        _angle(
            key="penguin_air_bubbles",
            keywords=("water", "swim", "feather", "dive", "ice", "slide"),
            title="{subject} trap air bubbles under feathers",
            hook="{subject} carry tiny air pockets into the water.",
            script_body=(
                "Watch the feathers before the dive, because penguins trap air that can help with "
                "insulation and speed. When bubbles release, the water drag changes around the body. "
                "The smooth swim starts in the feather coat. Which polar trick next?"
            ),
            thumbnail="AIR BUBBLES",
            cue="air bubbles",
            story_format="body_superpower",
            tags=("penguins", "feathers", "polar animals"),
        ),
    ),
    "seal": (
        _angle(
            key="seal_whisker_wakes",
            keywords=("whisker", "fish", "water", "hunt", "swim"),
            title="{subject} track fish trails with whiskers",
            hook="{subject} can follow wakes with their whiskers.",
            script_body=(
                "Watch the whiskers near the water, because seals can sense tiny trails left by "
                "moving fish. Those vibrations help them hunt even when the water is dark or messy. "
                "The face becomes a current detector. Which ocean sense next?"
            ),
            thumbnail="WAKE TRACKER",
            cue="whisker wake",
            story_format="body_superpower",
            tags=("seals", "whiskers", "ocean animals"),
        ),
    ),
    "shark": (
        _angle(
            key="shark_electric_sense",
            keywords=("electric", "sense", "field", "hunt", "water", "fin"),
            title="{subject} sense tiny electric fields",
            hook="{subject} can feel electricity in the water.",
            script_body=(
                "Watch the head before the turn, because sharks have sensory pores that detect "
                "tiny electric fields from other animals. That helps them hunt when sight is limited. "
                "The ocean is full of signals we cannot feel. Would you swim differently?"
            ),
            thumbnail="ELECTRIC SENSE",
            cue="electric sense",
            story_format="body_superpower",
            tags=("sharks", "electric sense", "ocean animals"),
        ),
    ),
    "sheep": (
        _angle(
            key="sheep_face_memory",
            keywords=("face", "flock", "remember", "watch", "farm"),
            title="{subject} recognize faces across the flock",
            hook="{subject} can remember familiar faces.",
            script_body=(
                "Watch the face and spacing, because sheep can learn who is familiar in the flock. "
                "That recognition helps them stay near safe partners and avoid stress. The group is "
                "not just a blur to them. Which farm animal should we compare next?"
            ),
            thumbnail="FLOCK MEMORY",
            cue="face memory",
            story_format="animal_memory",
            tags=("sheep", "face memory", "farm animals"),
        ),
    ),
    "snake": (
        _angle(
            key="snake_tongue_smell",
            keywords=("tongue", "smell", "air", "head", "hunt"),
            title="{subject} smell the air with their tongues",
            hook="{subject} sample the air with a tongue flick.",
            script_body=(
                "Watch the tongue flick, because it collects scent particles and sends them to a "
                "special organ in the mouth. That helps snakes track prey, mates, and danger without "
                "needing a loud chase. The air is information. Would you notice the trail?"
            ),
            thumbnail="TONGUE SMELL",
            cue="tongue smell",
            story_format="body_superpower",
            tags=("snakes", "tongue", "reptile facts"),
        ),
        _angle(
            key="snake_heat_pits",
            keywords=("heat", "pit", "warm", "night", "prey"),
            title="{subject} can detect warm prey in the dark",
            hook="{subject} can sense heat when light disappears.",
            script_body=(
                "Watch the head before the strike, because some snakes have heat-sensitive pits "
                "that detect warm bodies. That gives them a second kind of vision at night. The "
                "target glows to them without glowing to us. Which reptile sense next?"
            ),
            thumbnail="HEAT VISION",
            cue="heat pits",
            story_format="body_superpower",
            tags=("snakes", "heat pits", "reptile facts"),
        ),
    ),
    "tiger": (
        _angle(
            key="tiger_stripe_camouflage",
            keywords=("stripe", "hide", "grass", "camouflage", "hunt"),
            title="{subject} wear stripe shadows as camouflage",
            hook="{subject} use stripes to break up their outline.",
            script_body=(
                "Watch the stripes against grass and shade, because they split the body outline into "
                "harder pieces to track. That camouflage helps a big animal get closer before prey "
                "locks on. The pattern is stealth, not decoration. Would you spot the tiger first?"
            ),
            thumbnail="STRIPE STEALTH",
            cue="stripe camouflage",
            story_format="survival_trick",
            tags=("tigers", "stripes", "wildlife"),
        ),
    ),
    "turtle": (
        _angle(
            key="turtle_magnetic_map",
            keywords=("ocean", "beach", "swim", "map", "magnetic", "head"),
            title="{subject} carry a magnetic map home",
            hook="{subject} can navigate with Earth's magnetic field.",
            script_body=(
                "Watch the slow direction change, because many turtles use magnetic information "
                "like a map. That sense helps them cross huge distances and return toward important "
                "coasts later in life. Slow animal, massive route. Which reptile journey next?"
            ),
            thumbnail="MAGNETIC MAP",
            cue="magnetic map",
            story_format="body_superpower",
            tags=("turtles", "navigation", "reptile facts"),
        ),
    ),
    "whale": (
        _angle(
            key="whale_tail_slap",
            keywords=("tail", "slap", "water", "pod", "warn", "surface"),
            title="{subject} slap the surface to warn the pod",
            hook="{subject} can turn one splash into a warning.",
            script_body=(
                "Watch the white splash first, because a tail slap sends sound and pressure through "
                "water. Other whales can react before the situation gets closer. The surface hit is "
                "not just drama. Which ocean signal should we decode next?"
            ),
            thumbnail="TAIL SLAP",
            cue="tail slap",
            story_format="animal_intelligence",
            tags=("whales", "tail slap", "ocean animals"),
        ),
        _angle(
            key="whale_long_songs",
            keywords=("song", "sound", "call", "ocean", "sing"),
            title="{subject} send songs across huge ocean distances",
            hook="{subject} can send sound farther than sight.",
            script_body=(
                "Watch the body rise and listen to the idea behind it, because whale sound can "
                "travel through water far better than light. Songs and calls help with contact over "
                "huge distances. The ocean is a sound network. Which call should come next?"
            ),
            thumbnail="OCEAN SONG",
            cue="ocean song",
            story_format="animal_intelligence",
            tags=("whales", "songs", "ocean animals"),
        ),
    ),
    "wolf": (
        _angle(
            key="wolf_scent_posts",
            keywords=("tail", "pack", "scent", "mark", "forest", "snow"),
            title="{subject} read scent posts like a map",
            hook="{subject} leave scent notes for the pack.",
            script_body=(
                "Watch where the animal pauses, because wolves use scent marking to share territory, "
                "identity, and timing. A single spot can tell the pack who passed and how recently. "
                "The forest has messages we cannot read. Which pack signal next?"
            ),
            thumbnail="SCENT POST",
            cue="scent post",
            story_format="animal_intelligence",
            tags=("wolves", "scent marking", "wildlife"),
        ),
    ),
}

NATURE_ANGLE_LIBRARY: dict[str, tuple[CuriosityAngle, ...]] = {
    "plants": (
        _angle(
            key="plant_touch_count",
            keywords=("venus", "flytrap", "trap", "leaf", "plant", "touch"),
            title="{subject} count touches before snapping shut",
            hook="{subject} can count touches before closing.",
            script_body=(
                "Watch the trap hairs, because the plant waits for more than one touch before "
                "spending energy on a snap. That delay helps it ignore rain and debris, then close "
                "when prey is real. Which plant trick should we decode next?"
            ),
            thumbnail="TOUCH COUNT",
            cue="trap hairs",
            story_format="plant_mechanism",
            tags=("plants", "venus flytrap", "botany"),
        ),
        _angle(
            key="plant_leaf_sugar",
            keywords=("leaf", "leaves", "sunlit", "sunlight", "green", "foliage"),
            title="{subject} turn sunlight into stored sugar",
            hook="{subject} turn light into food.",
            script_body=(
                "Watch the leaf surface, because chlorophyll captures light energy and uses it to "
                "build sugar from air and water. The green color is a tiny factory at work. Which "
                "plant clue should we decode next?"
            ),
            thumbnail="LIGHT TO SUGAR",
            cue="leaf surface",
            story_format="plant_mechanism",
            tags=("plants", "photosynthesis", "botany"),
        ),
        _angle(
            key="plant_desert_water",
            keywords=("desert", "cactus", "dry", "windy", "sand", "arid"),
            title="{subject} save water with slow desert tricks",
            hook="{subject} survive by slowing water loss.",
            script_body=(
                "Watch the thick leaves or waxy surface, because many desert plants store water and "
                "limit evaporation. The shape is not decoration; it is a survival budget. Which dry "
                "land adaptation should come next?"
            ),
            thumbnail="WATER BUDGET",
            cue="waxy surface",
            story_format="plant_mechanism",
            tags=("plants", "desert plants", "botany"),
        ),
        _angle(
            key="plant_greenhouse_growth",
            keywords=("greenhouse", "glass", "panning", "seedling", "houseplant", "grow"),
            title="{subject} speed growth under protected glass",
            hook="{subject} grow faster when warmth stays trapped.",
            script_body=(
                "Watch the protected leaves, because greenhouse glass keeps heat and humidity more "
                "stable around the plant. That calmer microclimate lets growth spend less energy on "
                "stress. Which growing trick should we test next?"
            ),
            thumbnail="GREENHOUSE BOOST",
            cue="protected leaves",
            story_format="plant_mechanism",
            tags=("plants", "greenhouse", "botany"),
        ),
    ),
    "trees": (
        _angle(
            key="tree_ring_weather",
            keywords=("tree", "rings", "bark", "ancient", "root", "forest"),
            title="{subject} record wet years inside their rings",
            hook="{subject} keep weather history in their rings.",
            script_body=(
                "Watch the trunk pattern, because each growing season leaves a new layer. Wide "
                "rings often mean easier growth, while thin rings can mark stress. That is why an "
                "old tree can become a climate diary. Which hidden record should come next?"
            ),
            thumbnail="TREE RINGS",
            cue="tree rings",
            story_format="earth_engine",
            tags=("trees", "tree rings", "earth science"),
        ),
    ),
    "forests": (
        _angle(
            key="forest_cool_canopy",
            keywords=("forest", "canopy", "rainforest", "mist", "shade", "jungle"),
            title="{subject} make cooler air under the canopy",
            hook="{subject} can cool the air below them.",
            script_body=(
                "Watch the shade and mist, because leaves block direct sun and release water vapor. "
                "That combination can make the forest floor feel like a different climate. The canopy "
                "is a cooling machine, not just cover. Which forest layer next?"
            ),
            thumbnail="COOL CANOPY",
            cue="cool canopy",
            story_format="earth_engine",
            tags=("forests", "canopy", "ecosystems"),
        ),
        _angle(
            key="forest_fog_hold",
            keywords=("fog", "foggy", "mist", "misty", "trail", "bridge"),
            title="{subject} hold cool fog between the trees",
            hook="{subject} can trap cool fog near the ground.",
            script_body=(
                "Watch the low mist, because shade, leaves, and damp soil slow how fast the air "
                "warms back up. That is why a forest path can feel cooler than open ground. Which "
                "forest layer should we decode next?"
            ),
            thumbnail="FOG LAYER",
            cue="low mist",
            story_format="earth_engine",
            tags=("forests", "fog", "ecosystems"),
        ),
        _angle(
            key="forest_trail_edges",
            keywords=("trail", "path", "hike", "spring", "rustic", "bridge"),
            title="{subject} reveal edge climates along trails",
            hook="{subject} change climate at the trail edge.",
            script_body=(
                "Watch the brighter opening beside the trees, because edges get more sun and wind "
                "than the shaded interior. A few steps can shift moisture, heat, and plant life. "
                "Which edge clue should we compare next?"
            ),
            thumbnail="EDGE CLIMATE",
            cue="trail edge",
            story_format="earth_engine",
            tags=("forests", "microclimate", "ecosystems"),
        ),
    ),
    "fungi": (
        _angle(
            key="fungi_thread_trade",
            keywords=("mushroom", "mushrooms", "fungi", "mycelium", "thread", "threads", "forest"),
            title="{subject} trade nutrients through underground threads",
            hook="{subject} connect through threads under the soil.",
            script_body=(
                "Watch the mushroom cap, then imagine the hidden part below it. Mycelium spreads "
                "through soil as fine threads, moving nutrients while breaking down dead material. "
                "That is why the real fungal story is usually underground. Which tiny network next?"
            ),
            thumbnail="FUNGAL WEB",
            cue="mycelium threads",
            story_format="hidden_network",
            tags=("mushrooms", "mycelium", "fungi"),
        ),
        _angle(
            key="fungi_spore_release",
            keywords=("cap", "gills", "pumpkin", "mushroom", "mushrooms", "spore", "spores"),
            title="{subject} release spores from hidden gills",
            hook="{subject} spread by releasing tiny spores.",
            script_body=(
                "Watch under the cap, because many mushrooms carry spore-producing surfaces there. "
                "When conditions are right, those tiny particles move out to start the next fungal "
                "network. Which hidden structure should we look under next?"
            ),
            thumbnail="SPORE GILLS",
            cue="mushroom gills",
            story_format="hidden_network",
            tags=("mushrooms", "spores", "fungi"),
        ),
        _angle(
            key="fungi_decay_engine",
            keywords=("log", "tree", "trunk", "decay", "forest", "oyster"),
            title="{subject} turn fallen wood back into soil",
            hook="{subject} break down wood into usable nutrients.",
            script_body=(
                "Watch where the mushrooms grow, because fungi release enzymes that take apart dead "
                "wood. That slow cleanup returns nutrients to the forest instead of leaving a locked "
                "pile of carbon. Which decomposer should we decode next?"
            ),
            thumbnail="DECAY ENGINE",
            cue="fallen wood",
            story_format="hidden_network",
            tags=("mushrooms", "decomposition", "fungi"),
        ),
    ),
    "rivers": (
        _angle(
            key="river_bend_erosion",
            keywords=("river", "stream", "current", "waterfall", "delta", "flow"),
            title="{subject} carve bends by stealing from one bank",
            hook="{subject} move sideways while they flow.",
            script_body=(
                "Watch the outside of the bend, because faster water cuts that bank while slower "
                "water drops sediment inside the curve. Over time the whole river shifts across the "
                "landscape. A bend is motion written in mud. Which water shape next?"
            ),
            thumbnail="RIVER BEND",
            cue="river bend",
            story_format="earth_engine",
            tags=("rivers", "erosion", "earth science"),
        ),
        _angle(
            key="river_stone_transport",
            keywords=("rocky", "rocks", "stone", "stream", "mountain", "water"),
            title="{subject} carry stone grains while they flow",
            hook="{subject} move tiny pieces of stone downstream.",
            script_body=(
                "Watch the water near the rocks, because moving current can lift sand, roll pebbles, "
                "and grind larger stones over time. The stream is carrying the landscape in small "
                "pieces. Which water clue should we follow next?"
            ),
            thumbnail="STONE CURRENT",
            cue="rocky current",
            story_format="earth_engine",
            tags=("rivers", "sediment", "earth science"),
        ),
        _angle(
            key="river_bank_sorting",
            keywords=("bank", "banks", "bend", "bends", "meadow", "peaceful", "flowing"),
            title="{subject} sort mud and sand along each bank",
            hook="{subject} sort sediment while they bend.",
            script_body=(
                "Watch the edge of the flow, because slower water drops heavier material while faster "
                "water keeps cutting. That sorting is how a quiet bend slowly redraws the map. Which "
                "river edge should we compare next?"
            ),
            thumbnail="BANK SORTING",
            cue="river bank",
            story_format="earth_engine",
            tags=("rivers", "sediment", "earth science"),
        ),
    ),
    "mountains": (
        _angle(
            key="glacier_valley_carving",
            keywords=("mountain", "glacier", "ice", "alpine", "valley", "snow"),
            title="{subject} carve valleys while moving slowly",
            hook="{subject} can reshape mountains while crawling.",
            script_body=(
                "Watch the ice line, because glaciers drag rock like sandpaper over long timescales. "
                "That slow grinding can widen valleys and polish bedrock. The movement looks quiet, "
                "but the landscape remembers it. Which mountain clue next?"
            ),
            thumbnail="GLACIER CARVE",
            cue="glacier carve",
            story_format="earth_engine",
            tags=("glaciers", "mountains", "geology"),
        ),
    ),
    "volcanoes": (
        _angle(
            key="lava_new_land",
            keywords=("lava", "volcano", "magma", "crater", "eruption", "ash"),
            title="{subject} turns into new ground as it cools",
            hook="{subject} can become new land in minutes.",
            script_body=(
                "Watch the glowing edge, because lava starts as molten rock and hardens as heat "
                "escapes. Fresh crust forms first, then thicker layers build underneath. That is how "
                "an eruption can redraw the ground. Which volcanic clue next?"
            ),
            thumbnail="NEW LAND",
            cue="cooling lava",
            story_format="earth_engine",
            tags=("lava", "volcanoes", "geology"),
        ),
    ),
    "weather": (
        _angle(
            key="lightning_thunder_snap",
            keywords=("lightning", "storm", "cloud", "rain", "tornado", "sky"),
            title="{subject} makes air explode into thunder",
            hook="{subject} turns air into a shock wave.",
            script_body=(
                "Watch the flash first, because lightning heats a narrow path of air extremely fast. "
                "That air expands suddenly, and the pressure wave reaches us as thunder. The sound "
                "is the atmosphere snapping back. Which storm signal next?"
            ),
            thumbnail="THUNDER SNAP",
            cue="lightning flash",
            story_format="earth_engine",
            tags=("lightning", "weather", "storms"),
        ),
        _angle(
            key="cloud_layer_motion",
            keywords=("cloud", "clouds", "cloudy", "timelapse", "sky", "changing", "moving"),
            title="{subject} reveal air layers moving at different speeds",
            hook="{subject} show stacked air moving at different speeds.",
            script_body=(
                "Watch the cloud layers, because wind can change direction and speed with height. "
                "That makes one part of the sky slide past another, turning invisible air motion into "
                "a visible map. Which sky layer should we read next?"
            ),
            thumbnail="AIR LAYERS",
            cue="cloud layers",
            story_format="earth_engine",
            tags=("clouds", "weather", "earth science"),
        ),
        _angle(
            key="overcast_light_filter",
            keywords=("overcast", "grey", "gray", "cloudscape", "cloudy", "sky"),
            title="{subject} filter sunlight into a softer glow",
            hook="{subject} spread sunlight before it reaches the ground.",
            script_body=(
                "Watch the flat light, because thick cloud layers scatter direct sun in many directions. "
                "That makes shadows softer and shows how weather can change a whole scene before rain "
                "arrives. Which light clue should we compare next?"
            ),
            thumbnail="SOFT LIGHT",
            cue="flat light",
            story_format="earth_engine",
            tags=("clouds", "weather", "light"),
        ),
    ),
    "rare_phenomena": (
        _angle(
            key="aurora_solar_air",
            keywords=("aurora", "sky", "light", "eclipse", "bioluminescent", "ice"),
            title="{subject} glow when solar particles hit air",
            hook="{subject} start with charged particles from the sun.",
            script_body=(
                "Watch the moving color, because charged particles follow Earth's magnetic field "
                "toward the upper atmosphere. When they hit oxygen and nitrogen, the air releases "
                "light. The sky is reacting to space weather. Which rare sky event next?"
            ),
            thumbnail="AURORA GLOW",
            cue="aurora glow",
            story_format="rare_nature",
            tags=("aurora", "space weather", "earth science"),
        ),
    ),
    "geology": (
        _angle(
            key="rock_layer_time",
            keywords=("rock", "rocks", "layer", "layers", "crystal", "cave", "mineral", "canyon"),
            title="{subject} store ancient environments in stripes",
            hook="{subject} are time stamps made of stone.",
            script_body=(
                "Watch the stripe pattern, because each layer can mark a different setting: river "
                "mud, ocean floor, windblown sand, or volcanic ash. Stack enough layers and the cliff "
                "becomes a timeline. Which rock clue should we read next?"
            ),
            thumbnail="ROCK TIME",
            cue="rock layers",
            story_format="earth_engine",
            tags=("geology", "rock layers", "earth science"),
        ),
        _angle(
            key="slot_canyon_flood_paths",
            keywords=("slot", "canyon", "utah", "desert", "narrow", "sandstone"),
            title="{subject} reveal flood paths carved into stone",
            hook="{subject} can show where fast water carved the wall.",
            script_body=(
                "Watch the narrow curves, because floodwater and blowing sand wear weak rock over "
                "long stretches of time. The smooth wall is erosion written into stone. Which canyon "
                "clue should we read next?"
            ),
            thumbnail="CANYON PATHS",
            cue="canyon wall",
            story_format="earth_engine",
            tags=("geology", "canyons", "erosion"),
        ),
        _angle(
            key="cave_inside_layers",
            keywords=("cave", "caves", "tunnel", "tunnels", "underground", "pillar", "pillars"),
            title="{subject} show their timeline inside caves",
            hook="{subject} keep a hidden timeline inside caves.",
            script_body=(
                "Watch the cave wall, because water can dissolve, deposit, and expose minerals over "
                "long periods. The chamber becomes a cross-section of slow chemistry and stone. Which "
                "underground clue should we inspect next?"
            ),
            thumbnail="CAVE TIMELINE",
            cue="cave wall",
            story_format="earth_engine",
            tags=("geology", "caves", "earth science"),
        ),
        _angle(
            key="geyser_heat_path",
            keywords=("geyser", "geothermal", "steam", "steamy", "hot", "thermal"),
            title="{subject} reveal heat moving under the surface",
            hook="{subject} can expose heat moving below ground.",
            script_body=(
                "Watch the steam, because hot water rises through cracks after being heated underground. "
                "Pressure and minerals turn hidden energy into a visible signal at the surface. Which "
                "geothermal clue should come next?"
            ),
            thumbnail="HEAT PATH",
            cue="steam vent",
            story_format="earth_engine",
            tags=("geology", "geothermal", "earth science"),
        ),
        _angle(
            key="badlands_fast_erosion",
            keywords=("badlands", "rolling", "hills", "terrain", "eroded", "desert"),
            title="{subject} expose erosion in bare open hills",
            hook="{subject} show erosion without much cover.",
            script_body=(
                "Watch the bare ridges, because soft rock and sparse plants let rain and wind carve "
                "the surface quickly. Each groove is a small drainage path made visible. Which landform "
                "should we compare next?"
            ),
            thumbnail="BARE EROSION",
            cue="bare ridges",
            story_format="earth_engine",
            tags=("geology", "badlands", "erosion"),
        ),
        _angle(
            key="mountain_uplift_exposure",
            keywords=("himalayan", "himalaya", "nepal", "mountain", "mountains", "peak", "valley"),
            title="{subject} rise into view when mountains lift",
            hook="{subject} can be lifted high enough to read.",
            script_body=(
                "Watch the exposed slopes, because mountain building can push old rock upward while "
                "erosion strips cover away. A peak can reveal material that formed far below. Which "
                "uplift clue should we decode next?"
            ),
            thumbnail="UPLIFT CLUE",
            cue="exposed slopes",
            story_format="earth_engine",
            tags=("geology", "mountains", "earth science"),
        ),
    ),
    "ecosystems": (
        _angle(
            key="reef_tiny_builders",
            keywords=("coral", "reef", "ecosystem", "habitat", "biodiversity", "tide"),
            title="{subject} are cities built by tiny animals",
            hook="{subject} are built by tiny living builders.",
            script_body=(
                "Watch the reef texture, because coral animals build hard skeletons that stack into "
                "habitat. Fish, algae, and countless small creatures then use that structure like a "
                "city. The color sits on top of engineering. Which habitat next?"
            ),
            thumbnail="REEF CITY",
            cue="reef city",
            story_format="ecosystem_engine",
            tags=("coral reefs", "ecosystems", "biodiversity"),
        ),
    ),
    "earth_from_space": (
        _angle(
            key="storm_heat_engine",
            keywords=("earth", "cloud", "clouds", "hurricane", "satellite", "atmosphere", "space"),
            title="{subject} reveal a storm's heat engine",
            hook="{subject} show where a storm is feeding.",
            script_body=(
                "Watch the spiral shape, because warm ocean air rises near the center and releases "
                "heat as clouds build. Rotation organizes that energy into bands. From above, the "
                "storm is not random; it is an engine. Which satellite clue next?"
            ),
            thumbnail="STORM ENGINE",
            cue="cloud spiral",
            story_format="earth_engine",
            tags=("earth", "storm clouds", "satellite"),
        ),
        _angle(
            key="cloud_timelapse_air_layers",
            keywords=("timelapse", "cloudy", "changing", "moving", "clouds", "sky"),
            title="{subject} show air layers changing over time",
            hook="{subject} show air layers changing over time.",
            script_body=(
                "Watch the cloud deck, because winds at different heights can push each layer in a "
                "different direction. A timelapse turns that invisible motion into a map. Which sky "
                "motion should we read next?"
            ),
            thumbnail="AIR LAYERS",
            cue="cloud deck",
            story_format="earth_engine",
            tags=("clouds", "weather", "earth science"),
        ),
        _angle(
            key="airplane_cloud_tops",
            keywords=("airplane", "plane", "window", "above", "cloud", "clouds", "horizon"),
            title="{subject} reveal weather from above the clouds",
            hook="{subject} look different when seen from above.",
            script_body=(
                "Watch the cloud tops, because the upper shape shows where air is rising, flattening, "
                "or spreading out. From above, weather becomes a texture map instead of a ceiling. "
                "Which above-cloud clue should we compare next?"
            ),
            thumbnail="CLOUD TOPS",
            cue="cloud tops",
            story_format="earth_engine",
            tags=("clouds", "weather", "earth science"),
        ),
        _angle(
            key="ocean_cloud_bands",
            keywords=("ocean", "horizon", "aerial", "clouds", "water", "coast"),
            title="{subject} trace wind bands over the ocean",
            hook="{subject} can trace wind moving over water.",
            script_body=(
                "Watch the long cloud bands, because wind, moisture, and temperature shape where air "
                "rises over the ocean. The pattern is not random scenery; it is atmosphere in motion. "
                "Which ocean-sky clue should come next?"
            ),
            thumbnail="WIND BANDS",
            cue="cloud bands",
            story_format="earth_engine",
            tags=("clouds", "ocean", "earth science"),
        ),
    ),
    "conservation": (
        _angle(
            key="mangrove_wave_buffer",
            keywords=("mangrove", "restoration", "reforestation", "coral", "cleanup", "protected"),
            title="{subject} take power out of waves",
            hook="{subject} can slow waves before they hit land.",
            script_body=(
                "Watch the roots in the water, because mangroves create a rough barrier that breaks "
                "up wave energy. They also shelter young fish and hold muddy coastlines together. "
                "Restoration can be infrastructure made of roots. Which repair story next?"
            ),
            thumbnail="WAVE BUFFER",
            cue="mangrove roots",
            story_format="conservation_signal",
            tags=("mangroves", "conservation", "coasts"),
        ),
    ),
    "discoveries": (
        _angle(
            key="fossil_time_clue",
            keywords=("fossil", "research", "science", "discovery", "biology", "field"),
            title="{subject} turn old bones into time clues",
            hook="{subject} can preserve a clue from deep time.",
            script_body=(
                "Watch the shape in the rock, because fossils form when buried remains leave mineral "
                "records behind. The original body is gone, but the pattern can reveal age, habitat, "
                "and behavior. Which ancient clue should we read next?"
            ),
            thumbnail="FOSSIL CLUE",
            cue="fossil shape",
            story_format="science_clue",
            tags=("fossils", "discoveries", "earth science"),
        ),
    ),
    "space": (
        _angle(
            key="moon_locked_face",
            keywords=("moon", "earth", "orbit", "space", "satellite", "planet"),
            title="{subject} keeps one face turned toward Earth",
            hook="{subject} shows us one face for a reason.",
            script_body=(
                "Watch the moon's position, because its rotation and orbit are locked together. It "
                "spins once in about the same time it circles Earth, so the same side keeps facing us. "
                "That is synchronized motion, not stillness. Which orbit clue next?"
            ),
            thumbnail="LOCKED FACE",
            cue="locked orbit",
            story_format="space_science",
            tags=("moon", "space", "astronomy"),
        ),
    ),
    "physics": (
        _angle(
            key="magnet_field_lines",
            keywords=("magnet", "magnets", "magnetic", "iron", "filings", "field"),
            title="{subject} make invisible fields visible",
            hook="{subject} can show a hidden force map.",
            script_body=(
                "Watch the filings line up, because each tiny piece becomes a small magnet in the "
                "field. Together they trace the direction of the force around the magnet. The pattern "
                "is physics drawing itself. Which force next?"
            ),
            thumbnail="FIELD LINES",
            cue="field lines",
            story_format="physics_demo",
            tags=("magnets", "physics", "field lines"),
        ),
    ),
    "chemistry": (
        _angle(
            key="crystal_repeat_pattern",
            keywords=("crystal", "crystals", "reaction", "chemical", "solution", "flame"),
            title="{subject} grow by repeating one tiny pattern",
            hook="{subject} build shape from repeating atoms.",
            script_body=(
                "Watch the edge grow, because atoms or molecules lock into a repeating arrangement. "
                "Once the pattern starts, new pieces fit most easily along the same order. That is why "
                "a crystal can look designed. Which reaction should we slow down next?"
            ),
            thumbnail="CRYSTAL GROWTH",
            cue="crystal edge",
            story_format="chemistry_demo",
            tags=("crystals", "chemistry", "science"),
        ),
    ),
    "microscopy": (
        _angle(
            key="cell_copy_first",
            keywords=("cell", "cells", "microscope", "bacteria", "algae", "division"),
            title="{subject} copy instructions before splitting",
            hook="{subject} have to copy themselves before dividing.",
            script_body=(
                "Watch the cell boundary, because division only works after the internal instructions "
                "are copied and organized. Then the cell can split the material into two working lives. "
                "At this scale, reproduction is careful logistics. Which tiny process next?"
            ),
            thumbnail="CELL COPY",
            cue="cell division",
            story_format="microscopy_demo",
            tags=("cells", "microscopy", "biology"),
        ),
    ),
}

CURIOUS_CUE_WORDS = tuple(
    sorted(
        {angle.cue for angles in (*ANGLE_LIBRARY.values(), *NATURE_ANGLE_LIBRARY.values()) for angle in angles}
        | {
            "air bubbles",
            "alarm call",
            "beak grip",
            "beak tool",
            "dance map",
            "ear marks",
            "electric sense",
            "face memory",
            "fake injury",
            "heat vision",
            "imprinting",
            "magnetic map",
            "motion lock",
            "scent map",
            "silent wings",
            "steady eyes",
            "taste feet",
            "tongue smell",
            "uv vision",
            "whisker map",
            "wing scales",
        }
    )
)

GENERIC_MOVEMENT_RE = re.compile(
    r"\b(?:body|body cue|body posture|cue|ear position|fin position|first movement|head movement|movement|"
    r"one visible signal|read the moment|another signal|another secret|signal cue|tail position|"
    r"watch the cue|wing movement|wing position|before the payoff|hidden cue|final move|"
    r"payoff appears|replay the first second)\b",
    re.I,
)


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text or "")


def _normalise_subject_phrases(text: str) -> str:
    normalised = re.sub(r"\bsheep[\s_-]*dogs?\b", "working dog", text or "", flags=re.I)
    return re.sub(r"\belephant[\s_-]*seals?\b", "seal", normalised, flags=re.I)


def _clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _subject_key_from_text(text: str) -> str:
    normalised = re.sub(r"[-_/]+", " ", _normalise_subject_phrases(text))
    for word in _words(normalised.lower()):
        clean = word.replace("'s", "")
        if clean in ANIMAL_ALIASES:
            return ANIMAL_ALIASES[clean]
    return ""


def _nature_key_from_text(text: str) -> str:
    normalised = re.sub(r"[-_/]+", " ", text or "")
    for word in _words(normalised.lower()):
        clean = word.replace("'s", "")
        if clean in NATURE_ALIASES:
            return NATURE_ALIASES[clean]
    return ""


def plural_subject(subject: str, key: str = "") -> str:
    key = key or _subject_key_from_text(subject)
    if key in PLURAL_DISPLAY:
        return PLURAL_DISPLAY[key]
    text = _clean_spaces(subject).title()
    if not text:
        return "Animals"
    if text.lower().endswith("s"):
        return text
    if text.lower().endswith("y") and len(text) > 1 and text[-2].lower() not in "aeiou":
        return text[:-1] + "ies"
    if text.lower().endswith(("ch", "sh", "x", "z")):
        return text + "es"
    return text + "s"


def is_generic_movement_copy(text: str) -> bool:
    return bool(GENERIC_MOVEMENT_RE.search(str(text or "")))


def _story_context(story: dict, subject: str = "", context: str = "") -> str:
    values: list[str] = [str(subject or ""), str(context or "")]
    for key in (
        "source_title",
        "raw_title",
        "title",
        "seo_title",
        "hook",
        "script",
        "thumbnail_text",
        "category",
        "topic_hashtag",
        "description",
    ):
        values.append(str(story.get(key) or ""))
    tags = story.get("yt_tags") or story.get("tags") or []
    if isinstance(tags, list):
        values.extend(str(tag or "") for tag in tags)
    else:
        values.append(str(tags or ""))
    related = story.get("sequel_of") or story.get("remake_of") or {}
    if isinstance(related, dict):
        values.extend(str(value or "") for value in related.values())
    return " ".join(values)


def subject_key_for_story(story: dict, subject: str = "", context: str = "") -> str:
    subject_key = _subject_key_from_text(subject)
    body_key = _subject_key_from_text(_story_context(story, subject="", context=context))
    if subject_key in {"bird"} and body_key:
        return body_key
    if subject_key or body_key:
        return subject_key or body_key
    category_key = str(story.get("category") or "").strip().lower()
    if category_key in NATURE_ANGLE_LIBRARY:
        return category_key
    nature_subject = _nature_key_from_text(subject)
    nature_body = _nature_key_from_text(_story_context(story, subject="", context=context))
    return nature_subject or nature_body


def select_curiosity_angle(
    story: dict, subject: str = "", context: str = "", *, force: bool = False
) -> CuriosityAngle | None:
    full_context = _story_context(story, subject=subject, context=context).lower()
    key = subject_key_for_story(story, subject=subject, context=context)
    angles = ANGLE_LIBRARY.get(key) or NATURE_ANGLE_LIBRARY.get(key)
    if not angles:
        return None
    scored: list[tuple[int, int, CuriosityAngle]] = []
    for index, angle in enumerate(angles):
        hits = sum(1 for keyword in angle.keywords if re.search(r"\b" + re.escape(keyword) + r"\b", full_context))
        scored.append((hits, -index, angle))
    scored.sort(reverse=True, key=lambda row: (row[0], row[1]))
    if scored[0][0] <= 0 and not force and not is_generic_movement_copy(full_context):
        return None
    return scored[0][2]


def build_curiosity_package(story: dict, subject: str = "", context: str = "", *, force: bool = False) -> dict:
    angle = select_curiosity_angle(story, subject=subject, context=context, force=force)
    if not angle:
        return {}
    key = subject_key_for_story(story, subject=subject, context=context)
    display = NATURE_DISPLAY.get(key) or plural_subject(subject, key=key)
    lower = display.lower()
    hook = _clean_spaces(angle.hook_template.format(subject=display, subject_lower=lower))
    if hook and hook[-1] not in ".!?":
        hook = f"{hook}."
    title = _clean_spaces(angle.title_template.format(subject=display, subject_lower=lower))
    script = _clean_spaces(angle.script_template.format(subject=display, subject_lower=lower, hook=hook))
    evergreen_tags = (
        ("nature facts", "science", "wild brief") if key in NATURE_ANGLE_LIBRARY else ("animal facts", "wildlife")
    )
    tags = [display.lower(), *angle.tags, *evergreen_tags]
    clean_tags: list[str] = []
    for tag in tags:
        clean = _clean_spaces(tag.lower())
        if clean and clean not in clean_tags:
            clean_tags.append(clean)
    return {
        "angle_key": angle.key,
        "subject_key": key,
        "subject": display,
        "title": title[:82],
        "seo_title": title[:60],
        "hook": hook,
        "script": script,
        "lead": script[:400],
        "thumbnail_text": angle.thumbnail_text,
        "cue": angle.cue,
        "story_format": angle.story_format,
        "yt_tags": clean_tags[:8],
    }
