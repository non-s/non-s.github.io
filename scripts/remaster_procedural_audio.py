"""Replace a generated video's audio with the procedural lo-fi piano score."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generate_liquid_wire_video import _profile, _synth_audio
from utils.liquid_wire_composer import build_composition
from utils.liquid_wire_timeline import build_timeline


def remaster(video: Path) -> Path:
    metadata_path = video.with_suffix(".json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    duration = float(metadata["duration"])
    seed = int(metadata["seed"])
    profile = metadata.get("generator_profile") or _profile(seed, str(metadata.get("kind", "long")))
    output = video.with_name(f"{video.stem}_lofi{video.suffix}")
    audio = video.with_name(f"{video.stem}_lofi.wav")
    events = build_timeline(seed, duration, profile["music"])
    composition = build_composition(seed, duration, profile["music"], events)
    _synth_audio(audio, duration, seed, profile, events, composition)
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11", "-shortest", str(output),
        ],
        check=True,
    )
    metadata["video_path"] = str(output)
    metadata["audio_source"] = "procedural_python_lofi_piano_v1"
    metadata["description"] = (
        "A slow generative visual session with liquid wireframes and an original procedural lo-fi piano score.\n\n"
        "Visuals and music were generated locally from code. No stock footage or external music."
    )
    output.with_suffix(".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    audio.unlink(missing_ok=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    args = parser.parse_args()
    print(remaster(args.video.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
