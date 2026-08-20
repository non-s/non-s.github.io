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

## Autonomous core contract (engine 4.1)

The stable loop is now:

```text
profile -> versioned genome -> render -> final-MP4 perception
        -> versioned visual DNA -> quality gate -> catalog memory
        -> age-normalized YouTube evidence -> explainable fitness
        -> hypothesis/experiment -> controlled evolution
```

`utils/creative_models.py` separates creative intent (`Genome`) from observed
output (`VisualDNA`) and derives stable identifiers. `utils/atomic_state.py`
provides migration-aware atomic persistence. `utils/creative_memory.py` keeps
a bounded catalog that can later receive performance windows without growing
raw history forever. `utils/research_engine.py` supplies distinct Shorts and
long-form fitness models and conservative evidence states.

The profile remains an internal engine structure for compatibility. New
automation should depend on the versioned genome and visual-DNA metadata,
not on undocumented profile fields.

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

## Research and evolution

Analytics snapshots join the catalog through `content_id` and are stored in
non-overlapping maturity windows: `early`, `1h`, `6h`, `24h`, `72h` and
`mature`. Shorts and long-form use separate explainable fitness models;
missing API metrics lower confidence rather than being imputed.

The weekly research cycle produces JSON and Markdown reports and may propose
at most three testable hypotheses when at least eight comparable observations
exist. Correlations are always labelled non-causal. Experiments reference a
known hypothesis and may change exactly one variable.

Evolution uses a family/format archive of elites, confidence, novelty and an
adaptive exploration rate. Modes are `off`, `shadow` (default), `canary`
(deterministic 10%) and `active`. An applied descendant inherits a parent and
records exactly one bounded semantic mutation.

## Governance and secret identity

Quality Gate 2.0 separates objective blocking failures from subjective review
prompts and requires private validation by default. The uploader independently
enforces the 4.1 metadata contract and publication kill switch.

The Liquid Wire glyph language is original and fictional—not historical
cuneiform. At most one in five creations carries a message. Encoding,
checksum, density, difficulty, disclosure and canon are versioned, validated
and linked to lineage. The glyph codes subtly modulate geometry; they are not
an unrelated text overlay.

Safe mode disables evolution and puzzles while preserving stable offline
generation. Separate global and publication kill switches are checked before
generation and again by the uploader contract.

## Active Workflows

- `Liquid Wire - Generate and Upload`
- `Liquid Wire - Site`
- `OAuth Token Refresh`
- `CI - Liquid Wire`
- `Liquid Wire - Release Semanal`

## Disabled Legacy Surface

Legacy channel workflows, stock synchronization, and downloaded-media pipelines
generation are no longer part of the active operation.
# Independent scheduler fallback

GitHub scheduled workflows are best-effort and can be delayed. Production has
a second trigger registered in Windows Task Scheduler as
`Liquid Wire Hourly Watchdog`. It runs
`scripts/dispatch_liquid_wire_watchdog.ps1` once per hour. The script never
uploads directly: it dispatches the idempotent GitHub watchdog, which audits a
UTC slot and creates at most one recovery run for that slot.

Operational checks:

```powershell
Get-ScheduledTaskInfo -TaskName "Liquid Wire Hourly Watchdog"
Get-Content "$env:LOCALAPPDATA\LiquidWire\scheduler.log" -Tail 20
```
