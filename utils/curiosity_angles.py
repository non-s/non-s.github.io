"""Deterministic animal curiosity angles for Wild Brief packaging.

The generator can drift toward generic "movement/cue" copy when the source
clip has little metadata. This file gives the local pipeline a concrete,
animal-specific fallback before a story reaches upload.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


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

CURIOUS_CUE_WORDS = tuple(
    sorted(
        {angle.cue for angles in ANGLE_LIBRARY.values() for angle in angles}
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
    r"watch the cue|wing movement|wing position)\b",
    re.I,
)


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text or "")


def _clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _subject_key_from_text(text: str) -> str:
    normalised = re.sub(r"[-_/]+", " ", text or "")
    for word in _words(normalised.lower()):
        clean = word.replace("'s", "")
        if clean in ANIMAL_ALIASES:
            return ANIMAL_ALIASES[clean]
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
    values: list[str] = [subject, context]
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
    return subject_key or body_key


def select_curiosity_angle(
    story: dict, subject: str = "", context: str = "", *, force: bool = False
) -> CuriosityAngle | None:
    full_context = _story_context(story, subject=subject, context=context).lower()
    key = subject_key_for_story(story, subject=subject, context=context)
    angles = ANGLE_LIBRARY.get(key)
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
    display = plural_subject(subject, key=key)
    lower = display.lower()
    hook = _clean_spaces(angle.hook_template.format(subject=display, subject_lower=lower))
    if hook and hook[-1] not in ".!?":
        hook = f"{hook}."
    title = _clean_spaces(angle.title_template.format(subject=display, subject_lower=lower))
    script = _clean_spaces(angle.script_template.format(subject=display, subject_lower=lower, hook=hook))
    tags = [display.lower(), *angle.tags, "animal facts", "wildlife"]
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
