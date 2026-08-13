# Liquid Wire Architecture

Liquid Wire is a procedural YouTube pipeline. It does not download or compose
stock footage or stock music.

## Flow

1. `generate_liquid_wire_video.py` reserves a unique generator profile in
   `_data/generator_history.json`.
2. It renders PNG frames from procedural mesh math.
3. It synthesizes an ambient audio bed locally.
4. FFmpeg combines frames and audio into `_videos/liquid_wire_*.mp4`.
5. Metadata is written next to the video, including the seed and full
   `generator_profile`.
6. `upload_youtube.py` uploads the latest `liquid_wire_*.mp4` using OAuth.

## Uniqueness

Each video gets a cryptographic-random seed unless a seed is passed manually.
The generated profile includes:

- object family
- continuous palette parameters
- deformation rates
- camera motion
- strand count
- wire density
- haze color
- signature hash

The history file prevents accidental reuse of the same seed/signature.

## Active Workflows

- `Liquid Wire - Generate and Upload`
- `Liquid Wire - Site`
- `OAuth Token Refresh`
- `CI - Liquid Wire`
- `Liquid Wire - Release Semanal`

## Disabled Legacy Surface

Legacy channel workflows, stock synchronization, and downloaded-media pipelines
generation are no longer part of the active operation.
