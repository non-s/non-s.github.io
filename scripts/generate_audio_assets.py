#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

def generate_assets():
    bgm_dir = Path("_assets/audio/bgm")
    sfx_dir = Path("_assets/audio/sfx")
    bgm_dir.mkdir(parents=True, exist_ok=True)
    sfx_dir.mkdir(parents=True, exist_ok=True)

    commands = [
        # BGM 1: Dark Cinematic Rumble (Brown noise with lowpass filter)
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=c=brown:r=44100:a=0.8",
            "-af", "lowpass=f=150, volume=0.6", "-t", "60",
            str(bgm_dir / "dark_rumble.mp3")
        ],
        # BGM 2: Tension Drone (Sine wave with vibrato)
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "synth=60:0:sine:65",
            "-af", "vibrato=f=0.3:d=0.8, volume=0.4", "-t", "60",
            str(bgm_dir / "tension_drone.mp3")
        ],
        # BGM 3: Mysterious Wind (Pink noise with bandpass)
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=c=pink:r=44100:a=0.5",
            "-af", "bandpass=f=400:width_type=q:w=0.5, volume=0.5", "-t", "60",
            str(bgm_dir / "mysterious_wind.mp3")
        ],
        # SFX 1: Fast Whoosh
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=c=white:r=44100:a=1",
            "-af", "bandpass=f=800:width_type=h:w=500, afade=t=in:ss=0:d=0.1, afade=t=out:ss=0.1:d=0.6, volume=1.0",
            "-t", "0.7",
            str(sfx_dir / "whoosh1.mp3")
        ],
        # SFX 2: Deep Impact Thud
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "synth=1:0:sine:40",
            "-af", "afade=t=out:ss=0:d=1, volume=1.5",
            "-t", "1",
            str(sfx_dir / "impact_thud.mp3")
        ]
    ]

    for cmd in commands:
        print(f"Generating {cmd[-1]}...")
        subprocess.run(cmd, capture_output=True)

if __name__ == "__main__":
    generate_assets()
    print("Done generating audio assets.")
