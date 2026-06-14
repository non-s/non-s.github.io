"""Deterministic fact-first rescue copy for Wild Brief.

This module is the free fallback when an AI provider returns weak copy or when
the local rewriter has to repair a candidate. The goal is not to replace good
AI output; it is to avoid publishing templated filler when the automation is
under pressure.
"""

from __future__ import annotations

import re
from hashlib import sha256
from dataclasses import dataclass


@dataclass(frozen=True)
class FactAngle:
    title: str
    hook: str
    script: str
    thumbnail: str
    terms: tuple[str, ...] = ()


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z'-]*", str(text or "").lower())


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    haystack = " ".join(_words(text))
    return any(term in haystack for term in terms)


def _term_score(text: str, terms: tuple[str, ...]) -> int:
    haystack = " ".join(_words(text))
    return sum(1 for term in terms if term in haystack)


def _stable_index(seed: str, size: int) -> int:
    if size <= 1:
        return 0
    digest = sha256(str(seed or "wildbrief").encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % size


def canonical_subject(subject: str, category: str = "", context: str = "") -> str:
    text = " ".join(_words(f"{subject} {category} {context}"))
    aliases = {
        "cats": "cat",
        "cat": "cat",
        "dogs": "dog",
        "dog": "dog",
        "puppies": "dog",
        "whales": "whale",
        "whale": "whale",
        "dolphins": "dolphin",
        "dolphin": "dolphin",
        "sharks": "shark",
        "shark": "shark",
        "birds": "bird",
        "bird": "bird",
        "pigeon": "bird",
        "pigeons": "bird",
        "chickens": "chicken",
        "chicken": "chicken",
        "ducklings": "duckling",
        "duckling": "duckling",
        "ducks": "duck",
        "duck": "duck",
        "snakes": "snake",
        "snake": "snake",
        "turtles": "turtle",
        "turtle": "turtle",
        "chameleons": "chameleon",
        "chameleon": "chameleon",
        "tigers": "tiger",
        "tiger": "tiger",
        "wolves": "wolf",
        "wolf": "wolf",
        "lions": "lion",
        "lion": "lion",
        "bears": "bear",
        "bear": "bear",
        "foxes": "fox",
        "fox": "fox",
        "monkeys": "monkey",
        "monkey": "monkey",
        "gorillas": "gorilla",
        "gorilla": "gorilla",
        "chimpanzees": "chimpanzee",
        "chimpanzee": "chimpanzee",
        "orangutans": "orangutan",
        "orangutan": "orangutan",
        "elephants": "elephant",
        "elephant": "elephant",
        "cows": "cow",
        "cow": "cow",
        "goats": "goat",
        "goat": "goat",
        "horses": "horse",
        "horse": "horse",
        "donkeys": "donkey",
        "donkey": "donkey",
        "bees": "bee",
        "bee": "bee",
        "butterflies": "butterfly",
        "butterfly": "butterfly",
        "dragonflies": "dragonfly",
        "dragonfly": "dragonfly",
        "beetles": "beetle",
        "beetle": "beetle",
        "mantises": "mantis",
        "mantis": "mantis",
        "ants": "ant",
        "ant": "ant",
        "insects": "insect",
        "insect": "insect",
        "bats": "bat",
        "bat": "bat",
        "owls": "owl",
        "owl": "owl",
        "macaws": "parrot",
        "macaw": "parrot",
        "parrots": "parrot",
        "parrot": "parrot",
        "octopuses": "octopus",
        "octopus": "octopus",
        "seals": "seal",
        "seal": "seal",
        "penguins": "penguin",
        "penguin": "penguin",
        "forests": "forest",
        "forest": "forest",
        "trees": "tree",
        "tree": "tree",
        "plants": "plant",
        "plant": "plant",
        "mushrooms": "fungus",
        "mushroom": "fungus",
        "fungi": "fungus",
        "fungus": "fungus",
        "geology": "geology",
        "geologies": "geology",
        "earth": "earth_system",
        "systems": "earth_system",
        "weather": "weather",
        "rivers": "river",
        "river": "river",
        "ocean": "ocean",
        "oceans": "ocean",
        "volcano": "volcano",
        "volcanoes": "volcano",
    }
    for token in _words(text):
        if token in aliases:
            return aliases[token]
    return ""


FACT_LIBRARY: dict[str, tuple[FactAngle, ...]] = {
    "cat": (
        FactAngle(
            title="Cats reuse paw prints to move quietly",
            hook="Cats reuse paw prints to move quietly.",
            script=(
                "Cats reuse paw prints to move quietly. Watch the paw placement: the back foot lands near "
                "the front print, so less grass or floor shifts under it. I love this because the hunting "
                "trick is visible before the jump. Did you catch it?"
            ),
            thumbnail="QUIET PAWS",
            terms=("paw", "paws", "foot", "feet"),
        ),
        FactAngle(
            title="Cats walk on toe pads for silent speed",
            hook="Cats walk on toe pads for silent speed.",
            script=(
                "Cats walk on toe pads for silent speed. Watch the soft paw contact: the heel stays lifted, "
                "so each step lands lightly and the body can spring without much warning. The cute little "
                "feet are built for stealth. Did you hear a step?"
            ),
            thumbnail="TOE WALK",
            terms=("paw", "paws", "foot", "feet"),
        ),
        FactAngle(
            title="Kittens learn bite control during play",
            hook="Kittens learn bite control during play.",
            script=(
                "Kittens learn bite control during play. Watch the quick nibble and release: young cats test "
                "pressure while playing, because too much force ends the game with littermates or people. The "
                "cute chaos is practice for a careful mouth. Did the bite soften?"
            ),
            thumbnail="PLAY BITE",
            terms=("bite", "biting", "nibble", "play", "playfully", "hand", "kitten", "kittens"),
        ),
        FactAngle(
            title="Cats aim their ears before turning",
            hook="Cats aim their ears before turning.",
            script=(
                "Cats aim their ears before turning. Watch the ear shift: each ear can track sound while "
                "the head stays still, so the cat checks a room before committing its body. That tiny scan "
                "is the real clue, and it often happens before the paws move. Would you notice it?"
            ),
            thumbnail="EAR SCAN",
            terms=("ear", "ears"),
        ),
        FactAngle(
            title="Cats rotate each ear toward tiny sounds",
            hook="Cats rotate each ear toward tiny sounds.",
            script=(
                "Cats rotate each ear toward tiny sounds. Watch one ear move before the head does: the outer "
                "ear funnels sound from a direction, so the cat can locate interest before committing its "
                "whole body. The turn starts with listening. Which ear moved first?"
            ),
            thumbnail="SOUND EARS",
            terms=("ear", "ears", "sound", "sounds", "listening"),
        ),
        FactAngle(
            title="Cats map tight spaces with whiskers",
            hook="Cats map tight spaces with whiskers.",
            script=(
                "Cats map tight spaces with whiskers. Watch the face near an edge: those whiskers brush "
                "air and surfaces, so the cat reads width before squeezing through. The cute part is also "
                "a measuring tool. Would you trust that map?"
            ),
            thumbnail="WHISKER MAP",
        ),
    ),
    "dog": (
        FactAngle(
            title="Dogs read scent with a wet nose",
            hook="Dogs read scent with a wet nose.",
            script=(
                "Dogs read scent with a wet nose. Watch the nose dip and lift: moisture catches odor "
                "particles, then each sniff samples a new layer of the scene. That is why a tiny pause "
                "can be a full investigation. What would your dog check first?"
            ),
            thumbnail="SCENT MAP",
        ),
        FactAngle(
            title="Dogs cool their bodies by panting",
            hook="Dogs cool their bodies by panting.",
            script=(
                "Dogs cool their bodies by panting. Watch the open mouth after movement: moisture evaporates "
                "from the tongue and airways because sweating through skin would not dump enough heat. The "
                "happy-looking pant is temperature control in plain sight. Did you read it that way?"
            ),
            thumbnail="COOLING PANT",
        ),
        FactAngle(
            title="Dogs point attention with ears and posture",
            hook="Dogs point attention with ears and posture.",
            script=(
                "Dogs point attention with ears and posture. Watch the body before the next step: ears, head, "
                "and weight shift toward whatever matters, giving away focus before a bark or run. The clue "
                "arrives early because attention changes posture first. What did this dog notice?"
            ),
            thumbnail="FOCUS SHIFT",
        ),
    ),
    "whale": (
        FactAngle(
            title="Whale fins hide hand-like bones",
            hook="Whale fins hide hand-like bones.",
            script=(
                "Whale fins hide hand-like bones. Watch the flipper sweep: inside it are finger-shaped "
                "bones from a land-mammal blueprint, now steering a giant body through water. I love this "
                "detail because evolution is visible in one slow turn. Did you know that?"
            ),
            thumbnail="HIDDEN HANDS",
        ),
    ),
    "dolphin": (
        FactAngle(
            title="Dolphins use signature whistles like names",
            hook="Dolphins use signature whistles like names.",
            script=(
                "Dolphins use signature whistles like names. Watch the group spacing: the sound lets one "
                "animal call another through messy water, so contact stays personal even when visibility "
                "drops. That makes the social scene feel different. Which call would you answer?"
            ),
            thumbnail="DOLPHIN NAMES",
        ),
    ),
    "shark": (
        FactAngle(
            title="Sharks feel movement through the water",
            hook="Sharks feel movement through the water.",
            script=(
                "Sharks feel movement through the water. Watch the smooth turn: a pressure-sensing line "
                "along the body helps detect vibration from nearby animals, even before the eyes do much. "
                "That is why the fin cue feels so precise. Would you spot the turn?"
            ),
            thumbnail="WATER SENSOR",
        ),
    ),
    "bird": (
        FactAngle(
            title="Bird wing tips split the air",
            hook="Bird wing tips split the air.",
            script=(
                "Bird wing tips split the air. Watch the outer feathers: they separate like tiny slots, "
                "reducing drag while the bird holds lift. The graceful glide is not magic; it is airflow "
                "management happening feather by feather. Which feather moved first?"
            ),
            thumbnail="AIR SLOTS",
        ),
    ),
    "chicken": (
        FactAngle(
            title="Chickens use different alarm calls",
            hook="Chickens use different alarm calls.",
            script=(
                "Chickens use different alarm calls. Watch the head snap up: the call can change depending "
                "on whether danger is above or on the ground, so the flock reacts with the right move. "
                "That farmyard noise is information. Did it sound simple before?"
            ),
            thumbnail="ALARM CALL",
        ),
    ),
    "duck": (
        FactAngle(
            title="Ducks waterproof feathers with oil",
            hook="Ducks waterproof feathers with oil.",
            script=(
                "Ducks waterproof feathers with oil. Watch the preening move: oil from a small gland spreads "
                "through the feathers, so water rolls away instead of soaking in. That calm float starts "
                "with grooming. Would you notice the preen?"
            ),
            thumbnail="WATERPROOF",
        ),
    ),
    "duckling": (
        FactAngle(
            title="Ducklings lock onto movement after hatching",
            hook="Ducklings lock onto movement after hatching.",
            script=(
                "Ducklings lock onto movement after hatching. Watch the little line follow: early imprinting "
                "sets the target, which helps them stay near the moving parent instead of wandering off, especially in busy water "
                "or grass. It looks cute, but the single-file march is survival organization. Would you "
                "follow the leader?"
            ),
            thumbnail="FOLLOW MODE",
        ),
    ),
    "snake": (
        FactAngle(
            title="Snakes smell in stereo with a forked tongue",
            hook="Snakes smell in stereo with a forked tongue.",
            script=(
                "Snakes smell in stereo with a forked tongue. Watch the head and tongue: each fork samples "
                "a slightly different spot, then the mouth organ compares the trail. That is how a silent "
                "move becomes navigation. Would you track the path?"
            ),
            thumbnail="STEREO SMELL",
        ),
    ),
    "turtle": (
        FactAngle(
            title="Turtle shells are living bone",
            hook="Turtle shells are living bone.",
            script=(
                "Turtle shells are living bone. Watch the body under the shell: the ribs and spine are fused "
                "into that armor, so the turtle is not carrying a house; it is built into one. That changes "
                "the whole scene. Did that surprise you?"
            ),
            thumbnail="LIVING ARMOR",
        ),
    ),
    "chameleon": (
        FactAngle(
            title="Chameleons scan with independent eyes",
            hook="Chameleons scan with independent eyes.",
            script=(
                "Chameleons scan with independent eyes. Watch the eye movement: each eye can survey a "
                "different direction before both lock onto one target. The slow body hides a very active "
                "search system. Which eye would you follow?"
            ),
            thumbnail="EYE SCAN",
        ),
    ),
    "tiger": (
        FactAngle(
            title="Tigers step inside their own tracks",
            hook="Tigers step inside their own tracks.",
            script=(
                "Tigers step inside their own tracks. Watch the paw placement: a back foot can land close "
                "to the front print, cutting noise while the body moves forward. That quiet geometry is why "
                "the walk feels so controlled. Would you hear it coming?"
            ),
            thumbnail="SILENT STEPS",
        ),
    ),
    "wolf": (
        FactAngle(
            title="Wolves carry scent back to the pack",
            hook="Wolves carry scent back to the pack.",
            script=(
                "Wolves carry scent back to the pack. Watch a rub or roll: scent clings to the fur, turning "
                "the body into a message because the group can inspect that smell later. That odd behavior is "
                "field reporting, not random rolling. What smell would matter most?"
            ),
            thumbnail="SCENT REPORT",
        ),
    ),
    "lion": (
        FactAngle(
            title="Lions use wind before they stalk",
            hook="Lions use wind before they stalk.",
            script=(
                "Lions use wind before they stalk. Watch the pause before movement: approaching from downwind "
                "keeps scent from reaching prey too soon, so patience becomes part of the attack. The still "
                "moment is doing work. Would you wait that long?"
            ),
            thumbnail="WIND CHECK",
        ),
    ),
    "bear": (
        FactAngle(
            title="Bears read the world mostly by smell",
            hook="Bears read the world mostly by smell.",
            script=(
                "Bears read the world mostly by smell. Watch the nose before the body moves: scent tells them "
                "where food, rivals, and trails sit in the landscape. The slow sniff is not hesitation; it is "
                "a map loading. What would it find?"
            ),
            thumbnail="SMELL MAP",
        ),
    ),
    "fox": (
        FactAngle(
            title="Fox tails balance sharp turns",
            hook="Fox tails balance sharp turns.",
            script=(
                "Fox tails balance sharp turns. Watch the tail swing: it works like a counterweight when the "
                "body cuts direction, helping the animal stay steady during a quick chase. That fluffy detail "
                "is steering. Did the tail give it away?"
            ),
            thumbnail="TAIL BALANCE",
        ),
    ),
    "monkey": (
        FactAngle(
            title="Monkeys use grooming like social currency",
            hook="Monkeys use grooming like social currency.",
            script=(
                "Monkeys use grooming like social currency. Watch the grooming hands and faces: cleaning fur "
                "lowers tension and reinforces alliances, so a quiet moment can decide who stays close later. "
                "It is not just hygiene; it is social politics. Who would you trust?"
            ),
            thumbnail="SOCIAL GROOMING",
        ),
    ),
    "gorilla": (
        FactAngle(
            title="Gorilla chest beats travel through the forest",
            hook="Gorilla chest beats travel through the forest.",
            script=(
                "Gorilla chest beats travel through the forest. Watch the posture before the sound: the beat "
                "advertises size and presence without needing a fight. That dramatic moment is also a distance "
                "message. Would you move closer or back away?"
            ),
            thumbnail="CHEST SIGNAL",
        ),
    ),
    "chimpanzee": (
        FactAngle(
            title="Chimpanzees read faces before they act",
            hook="Chimpanzees read faces before they act.",
            script=(
                "Chimpanzees read faces before they act. Watch the glance before the move: eyes, lips, and "
                "posture help them judge mood inside a social group. The small pause is not empty; it is "
                "decision time. Which face would you watch?"
            ),
            thumbnail="FACE CHECK",
        ),
    ),
    "orangutan": (
        FactAngle(
            title="Orangutans plan routes through the canopy",
            hook="Orangutans plan routes through the canopy.",
            script=(
                "Orangutans plan routes through the canopy. Watch the hand reach: each branch choice has to "
                "support a heavy body before the next move begins. That calm climb is a chain of decisions. "
                "Would you trust that branch?"
            ),
            thumbnail="CANOPY PLAN",
        ),
    ),
    "elephant": (
        FactAngle(
            title="Elephant ears work like heat panels",
            hook="Elephant ears work like heat panels.",
            script=(
                "Elephant ears work like heat panels. Watch the flap: blood moving through those broad ears "
                "can dump body heat into the air, so a gentle wave helps cool a giant animal. The signal is "
                "also climate control. Did you know that?"
            ),
            thumbnail="HEAT PANELS",
        ),
    ),
    "cow": (
        FactAngle(
            title="Cows see wide without turning much",
            hook="Cows see wide without turning much.",
            script=(
                "Cows see wide without turning much. Watch the head angle: eyes on the sides give a broad "
                "view of the pasture, so a small ear or head shift can mean attention moved. The quiet look "
                "is a safety scan. What caught it?"
            ),
            thumbnail="WIDE VIEW",
        ),
        FactAngle(
            title="Cows turn grass into fuel twice",
            hook="Cows turn grass into fuel twice.",
            script=(
                "Cows turn grass into fuel twice. Watch the slow chew: food comes back as cud, then gets "
                "chewed again because microbes in the four-part stomach unlock energy from tough plants. The "
                "calm mouth is a whole visible factory. Did you know that?"
            ),
            thumbnail="CUD ENGINE",
        ),
    ),
    "goat": (
        FactAngle(
            title="Goat pupils stay level while grazing",
            hook="Goat pupils stay level while grazing.",
            script=(
                "Goat pupils stay level while grazing. Watch the sideways eye shape: it helps scan the horizon "
                "while the head drops to feed, so the animal can eat and monitor danger together. That calm "
                "stare is surveillance, not attitude. Did you notice it?"
            ),
            thumbnail="HORIZON EYES",
        ),
    ),
    "horse": (
        FactAngle(
            title="Horse ears point toward attention",
            hook="Horse ears point toward attention.",
            script=(
                "Horse ears point toward attention. Watch the ear direction: each turn shows where sound or "
                "interest is pulling because the body often follows that focus next. Riders read that clue "
                "constantly, but you can see it from the clip too. Which way did it point?"
            ),
            thumbnail="EAR DIRECTION",
        ),
    ),
    "donkey": (
        FactAngle(
            title="Donkeys inspect footing before moving",
            hook="Donkeys inspect footing before moving.",
            script=(
                "Donkeys inspect footing before moving. Watch the pause before a step: sturdy hooves still "
                "need a safe path, so hesitation can be terrain reading rather than stubbornness. The slow "
                "choice is the survival clue. Would you step there?"
            ),
            thumbnail="FOOTING CHECK",
        ),
    ),
    "bee": (
        FactAngle(
            title="Bees dance directions inside the hive",
            hook="Bees dance directions inside the hive.",
            script=(
                "Bees dance directions inside the hive. Watch the wing and body vibration: the waggle points "
                "nestmates toward food because direction and distance are packed into the path. That tiny "
                "motion is a living map, not random buzzing, and another bee can fly by it. Would you follow "
                "the dance?"
            ),
            thumbnail="DANCE MAP",
        ),
        FactAngle(
            title="Bees can sense electric fields on flowers",
            hook="Bees can sense electric fields on flowers.",
            script=(
                "Bees can sense electric fields on flowers. Watch the antennae and tiny hairs: a bloom's "
                "charge can shift after another bee visits, so the next bee gets extra information before "
                "landing. The flower is not only color and scent; it is a signal. Did you expect that?"
            ),
            thumbnail="FLOWER CHARGE",
            terms=("electric", "field", "fields", "charge", "flower", "flowers", "antenna", "antennae", "hairs"),
        ),
    ),
    "butterfly": (
        FactAngle(
            title="Butterfly wings are covered in tiny scales",
            hook="Butterfly wings are covered in tiny scales.",
            script=(
                "Butterfly wings are covered in tiny scales. Watch the color flash: those scales bend and "
                "reflect light, creating patterns that help with camouflage, warning, or attraction. The wing "
                "is not painted; it is built. Which color pulled your eye?"
            ),
            thumbnail="WING SCALES",
        ),
    ),
    "dragonfly": (
        FactAngle(
            title="Dragonflies steer four wings separately",
            hook="Dragonflies steer four wings separately.",
            script=(
                "Dragonflies steer four wings separately. Watch the wing angle: each wing can adjust on its "
                "own, letting the insect hover, brake, or dart sideways with ridiculous control. That is why "
                "the still moment looks ready to explode. Could you track it?"
            ),
            thumbnail="FOUR WINGS",
        ),
    ),
    "beetle": (
        FactAngle(
            title="Beetles fold flight wings under armor",
            hook="Beetles fold flight wings under armor.",
            script=(
                "Beetles fold flight wings under armor. Watch the hard back: those outer cases protect the "
                "delicate wings that unfold when it needs to fly. The tiny body is carrying a hidden aircraft "
                "under a shield. Did you expect that?"
            ),
            thumbnail="HIDDEN WINGS",
        ),
    ),
    "mantis": (
        FactAngle(
            title="Mantises store speed in folded front legs",
            hook="Mantises store speed in folded front legs.",
            script=(
                "Mantises store speed in folded front legs. Watch the patient pose: the limbs are already "
                "loaded for a snap strike, so stillness becomes part of the weapon. That calm shape is not "
                "resting. Would you stand that close?"
            ),
            thumbnail="SNAP LEGS",
        ),
    ),
    "ant": (
        FactAngle(
            title="Ants build trails with scent",
            hook="Ants build trails with scent.",
            script=(
                "Ants build trails with scent. Watch one path repeat: each worker can leave chemicals that "
                "guide the next ant, turning tiny steps into a shared route. The line on the ground is group "
                "memory. Would you follow it?"
            ),
            thumbnail="SCENT TRAIL",
        ),
    ),
    "insect": (
        FactAngle(
            title="Insects read the world with antennae",
            hook="Insects read the world with antennae.",
            script=(
                "Insects read the world with antennae. Watch the head movement: those feelers sample touch, "
                "smell, and air changes, so a tiny pause can be a full environmental check. The smallest "
                "motion is doing real sensing. What did it test?"
            ),
            thumbnail="ANTENNA MAP",
        ),
        FactAngle(
            title="Insects cling with claws and foot pads",
            hook="Insects cling with claws and foot pads.",
            script=(
                "Insects cling with claws and foot pads. Watch the legs on the surface: tiny hooks grab rough "
                "texture while soft pads help on smoother leaves, so the animal can pause, climb, or launch "
                "without slipping. The footwork is the superpower. Could you spot the grip?"
            ),
            thumbnail="CLAW PADS",
            terms=("claw", "claws", "leg", "legs", "pad", "pads", "leaf", "leaves", "cling", "claws and pads"),
        ),
        FactAngle(
            title="Insects carry pollen between flowers",
            hook="Insects carry pollen between flowers.",
            script=(
                "Insects carry pollen between flowers. Watch the legs and body near a bloom: grains can stick "
                "to the surface, then move to the next flower because plants need that transfer to reproduce. "
                "The tiny visitor is also a delivery system with visible cargo, not just a blur of motion. "
                "Which plant gets helped next?"
            ),
            thumbnail="POLLEN DELIVERY",
            terms=("pollinate", "pollination", "pollen", "flower", "flowers", "plant", "plants", "farmer"),
        ),
    ),
    "bat": (
        FactAngle(
            title="Bats map darkness with returning sound",
            hook="Bats map darkness with returning sound.",
            script=(
                "Bats map darkness with returning sound. Watch the quick turns: calls bounce off objects and "
                "return as timing clues, so the animal can fly through clutter without daylight. The silence "
                "you see is full of data. Could you fly that way?"
            ),
            thumbnail="SOUND MAP",
        ),
    ),
    "owl": (
        FactAngle(
            title="Owls turn their face into a sound dish",
            hook="Owls turn their face into a sound dish.",
            script=(
                "Owls turn their face into a sound dish. Watch the head angle: the round facial feathers help "
                "focus tiny sound differences toward the ears, so prey position becomes easier to locate. The "
                "stare is listening. Would you hear it?"
            ),
            thumbnail="LISTENING FACE",
        ),
    ),
    "parrot": (
        FactAngle(
            title="Parrots climb with beak and feet together",
            hook="Parrots climb with beak and feet together.",
            script=(
                "Parrots climb with beak and feet together. Watch the beak touch: it works like a third limb "
                "while the toes grip from two directions. The bright bird is also a careful climber. Which "
                "part moved first?"
            ),
            thumbnail="BEAK CLIMB",
        ),
    ),
    "octopus": (
        FactAngle(
            title="Octopus skin changes color and texture",
            hook="Octopus skin changes color and texture.",
            script=(
                "Octopus skin changes color and texture. Watch the body surface: pigment cells shift color "
                "while tiny muscles can raise bumps, so the animal matches both pattern and shape. Camouflage "
                "is happening in layers. Would you spot the edge?"
            ),
            thumbnail="SKIN CONTROL",
        ),
    ),
    "seal": (
        FactAngle(
            title="Seal whiskers track trails in water",
            hook="Seal whiskers track trails in water.",
            script=(
                "Seal whiskers track trails in water. Watch the muzzle: those sensitive whiskers can feel "
                "tiny wake patterns left by moving fish, so hunting continues even when visibility drops. The "
                "face is reading currents. Would you notice the trail?"
            ),
            thumbnail="WATER TRAILS",
        ),
    ),
    "penguin": (
        FactAngle(
            title="Penguins use flippers like underwater wings",
            hook="Penguins use flippers like underwater wings.",
            script=(
                "Penguins use flippers like underwater wings. Watch the stroke: the bird flies through water "
                "with stiff flippers while the body stays streamlined. On land it waddles, but underwater the "
                "design makes sense. Which version looks smoother?"
            ),
            thumbnail="WATER WINGS",
        ),
    ),
    "forest": (
        FactAngle(
            title="Forests trade signals through root partners",
            hook="Forests trade signals through root partners.",
            script=(
                "Forests trade signals through root partners. Watch the still floor: fungi connect with roots "
                "underground, moving nutrients and chemical messages between plants. The quiet scene is not "
                "silent; it is networked. What would the forest send?"
            ),
            thumbnail="ROOT NETWORK",
        ),
    ),
    "tree": (
        FactAngle(
            title="Trees trade resources through fungal partners",
            hook="Trees trade resources through fungal partners.",
            script=(
                "Trees trade resources through fungal partners. Watch the roots and soil: mycorrhizal threads "
                "help move minerals and sugars between plant and fungus, especially where fine roots meet the "
                "network. The trunk is only the visible part of the partnership. What is happening below?"
            ),
            thumbnail="FUNGAL PARTNER",
        ),
    ),
    "plant": (
        FactAngle(
            title="Carnivorous plants snap shut with trigger hairs",
            hook="Carnivorous plants snap shut with trigger hairs.",
            script=(
                "Carnivorous plants snap shut with trigger hairs. Watch the inside of the trap: when an insect "
                "touches the hairs more than once, the leaf closes fast enough to hold the meal. The plant is "
                "not chasing; it is waiting with a sensor. Did you spot the trigger?"
            ),
            thumbnail="TRIGGER HAIRS",
            terms=("carnivorous", "venus", "trap", "snap", "trigger", "hairs", "insect", "insects", "eat"),
        ),
        FactAngle(
            title="Plants breathe through tiny leaf pores",
            hook="Leaves breathe through tiny pores.",
            script=(
                "Leaves breathe through tiny pores. Watch the leaf surface: stomata open and close to trade "
                "water vapor and carbon dioxide, so the plant manages growth and drying at the same time. "
                "The flat leaf is full of valves. Did you know that?"
            ),
            thumbnail="LEAF PORES",
            terms=("stomata", "pore", "pores", "leaf", "leaves", "breathe", "breath", "carbon", "vapor", "farm"),
        ),
    ),
    "fungus": (
        FactAngle(
            title="Mushrooms are the fruit of a hidden network",
            hook="Mushrooms are the fruit of a hidden network.",
            script=(
                "Mushrooms are the fruit of a hidden network. Watch the cap above the soil: most of the fungus "
                "is threadlike mycelium running underneath, feeding and spreading before the mushroom appears. "
                "The visible part is the reveal. What else is underground?"
            ),
            thumbnail="HIDDEN NETWORK",
        ),
    ),
    "geology": (
        FactAngle(
            title="Geology keeps old environments in rock layers",
            hook="Rock layers keep old environments in order.",
            script=(
                "Rock layers keep old environments in order. Watch the bands: each layer formed under a "
                "different condition, so color and texture can preserve a timeline of water, pressure, or "
                "volcanic dust. The cliff is a stack of clues. Which layer stands out?"
            ),
            thumbnail="ROCK TIMELINE",
        ),
    ),
    "earth_system": (
        FactAngle(
            title="Earth systems reveal moving air in cloud lines",
            hook="Cloud lines reveal moving air.",
            script=(
                "Cloud lines reveal moving air. Watch the pattern from above: clouds form where rising air "
                "cools enough for vapor to condense, so the sky sketches invisible motion. The view is not "
                "just pretty; it is physics drawn across the atmosphere. Which line moved first?"
            ),
            thumbnail="AIR MAP",
        ),
    ),
    "weather": (
        FactAngle(
            title="Storm clouds show rising air at work",
            hook="Storm clouds show rising air at work.",
            script=(
                "Storm clouds show rising air at work. Watch the growing tower: warm moist air climbs, cools, "
                "and condenses, building the cloud upward before rain or lightning arrives. The shape is the "
                "engine showing itself. Would you keep watching?"
            ),
            thumbnail="STORM ENGINE",
        ),
    ),
    "river": (
        FactAngle(
            title="Rivers write curves into the land",
            hook="Rivers write curves into the land.",
            script=(
                "Rivers write curves into the land. Watch the bend: faster water cuts the outer bank while "
                "slower water drops sediment inside the curve. The river is editing its own path. Which side "
                "looks stronger?"
            ),
            thumbnail="RIVER CURVE",
        ),
    ),
    "ocean": (
        FactAngle(
            title="Ocean color hints at life below",
            hook="Ocean color hints at life below.",
            script=(
                "Ocean color hints at life below. Watch the surface shade: plankton, sediment, and depth can "
                "change how water reflects light, so a color shift may point to activity underneath. The blue "
                "is not empty. What would you check below?"
            ),
            thumbnail="OCEAN COLOR",
        ),
    ),
    "volcano": (
        FactAngle(
            title="Lava builds new ground as it cools",
            hook="Lava builds new ground as it cools.",
            script=(
                "Lava builds new ground as it cools. Watch the glowing edge: molten rock loses heat, hardens, "
                "and becomes fresh surface where the landscape can start changing again. Destruction and "
                "construction happen together. Would you stand that close?"
            ),
            thumbnail="NEW GROUND",
        ),
    ),
}


def choose_fact_angle(subject_key: str, cue: str = "", title: str = "", seed: str = "") -> FactAngle | None:
    angles = FACT_LIBRARY.get(subject_key)
    if not angles:
        return None
    context = f"{cue} {title}".lower()
    scored = [
        (3 * _term_score(cue, angle.terms) + _term_score(title, angle.terms), angle)
        for angle in angles
        if angle.terms and _contains_any(context, angle.terms)
    ]
    if scored:
        best_score = max(score for score, _angle in scored)
        matching = [angle for score, angle in scored if score == best_score]
        return matching[_stable_index(seed or context, len(matching))]
    generic = [angle for angle in angles if not angle.terms]
    pool = generic or list(angles)
    return pool[_stable_index(seed or context, len(pool))]


def build_fact_rescue(story: dict, *, subject: str, lower_subject: str, cue: str, category: str) -> dict | None:
    context_fields = ("title", "seo_title", "hook", "script", "source_title", "raw_title", "description", "url", "source_url")
    if (story.get("fact_rescue") or {}).get("applied"):
        context_fields = ("source_title", "raw_title", "description", "url", "source_url")
    context = " ".join(str(story.get(key) or "") for key in context_fields)
    key = canonical_subject(lower_subject or subject, category, context)
    seed = " ".join(
        str(story.get(field) or "")
        for field in ("_fact_rescue_salt", "id", "source_url", "url", "title", "raw_title")
    )
    angle = choose_fact_angle(key, cue, context, seed=seed)
    if not angle:
        return None
    tags = []
    for tag in (lower_subject, key.replace("_", " "), str(category or "").lower(), "nature facts", "wild brief"):
        clean = re.sub(r"\s+", " ", str(tag or "")).strip()
        if clean and clean.lower() not in {item.lower() for item in tags}:
            tags.append(clean)
    return {
        "seo_title": angle.title[:60],
        "title": angle.title[:60],
        "hook": angle.hook,
        "script": angle.script,
        "lead": angle.script[:400],
        "thumbnail_text": angle.thumbnail[:28],
        "yt_tags": tags[:8],
        "fact_rescue": {
            "applied": True,
            "subject_key": key,
            "cue": cue,
            "angle_title": angle.title,
        },
    }
