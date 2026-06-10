# Wild Brief Growth Plan

Wild Brief is no longer an animal-only Shorts bot. The channel is now a fast
nature-science brand: one surprising visual idea per Short, covering animals,
plants, trees, fungi, oceans, rivers, mountains, forests, volcanoes, weather,
rare natural phenomena, geology, ecosystems, Earth-from-space stories,
conservation, discoveries, and biological curiosities.

## Retention Diagnosis

The old system had three main retention leaks:

1. Topic ceiling: animal-only programming limits audience surfaces and makes the
   feed feel repetitive after a few sessions.
2. Script density: many queue items run long, stack too many facts, and delay the
   visual payoff.
3. Visual rhythm: three slow b-roll segments, white captions, and static
   overlays do not create enough pattern interrupts for Shorts viewers.

## New Shorts Formula

Every Short should ship with this structure:

- 0-1s: outcome-first hook. No setup, no question hook.
- 1-4s: tell the viewer exactly what to watch in the footage.
- 4-12s: explain the mechanism with one vivid cause.
- Final beat: payoff plus a tiny comment question that points back to the cue.

Target script length is 38-55 words, with 12-18 seconds of finished runtime.
The aim is not maximum information; the aim is completion, replay, sharing, and
format recognition.

## Visual System

Implemented production direction:

- Yellow CapCut-style burned captions.
- Important words pop in white with slightly larger scale.
- Caption groups tightened to 1-3 words.
- Four b-roll beats per Short instead of three.
- Stronger automatic zoom and subtle contrast/saturation lift.
- Short micro-fades between segments.
- CTA changed from animal-only to Wild Brief nature positioning.

## Programming Pillars

Use repeatable series so viewers recognize the brand:

- Nature Trick: a survival or physical mechanism with a visible cue.
- Earth Engine: volcanoes, rivers, storms, glaciers, erosion, and geology.
- Hidden Network: fungi, roots, forests, ecosystems, and signals.
- Rare Earth: auroras, bioluminescence, eclipses, ice caves, blooms.
- Planet Repair: conservation wins and measurable ecosystem recovery.
- Discovery Brief: new research, fossils, field science, and biology.

## Viral Packaging Rules

- Title starts with the subject, not "Why" or "This".
- Thumbnail text is 2-4 words and names the mystery: FUNGAL INTERNET,
  STORM ENGINE, LAVA ISLAND.
- Captions must carry the hook even when muted.
- Every script contains a visible cue, a because/that's-why payoff, and one
  reason to rewatch the footage.
- Avoid generic words: amazing, incredible, secret, crazy, unbelievable.

## Autonomous Growth Engine

`utils/growth_engine.py` is now the editorial brain that runs before production:

- Opportunity Score ranks every candidate by viral, visual, replay, comment,
  education, emotion, and novelty potential.
- Weak topics are discarded before rendering, with priority weight for fungi,
  forests, oceans, volcanoes, extreme weather, geology, strange biology, rare
  behavior, natural phenomena, conservation, and discoveries.
- Retention Score checks hook strength, curiosity, visual surface, replay loop,
  and completion prediction.
- Packaging generation creates 10 titles, 10 thumbnail texts, and 5 alternate
  hooks, scores each combination, and selects the strongest package.
- `_data/format_memory.json` stores learned category, format, title,
  thumbnail, and hook patterns from finished videos.
- When enough `.done` markers include views, likes, comments, retention, and
  subscriber gains, the engine derives category and format weights from real
  performance instead of only fixed editorial priors.
- Weak Content Detection blocks saturated topics, generic hooks, generic
  thumbnails, repetitive scripts, and recently recycled angles before render.
- Packaging V2 caches each story's packaging matrix so title, thumbnail, hook,
  score, and report calls reuse the same selection instead of recomputing it.
- The experiment layer records whether a Short is exploring a fresh variant or
  exploiting winning hook/thumbnail patterns from memory.

The production gate now rejects candidates with low opportunity or retention
before spending render/upload time, and stores the reason for future audits.

## Scale Plan

1. Build queue volume across all nature pillars.
2. Publish 3-5 Shorts/day only if strict quality gates pass.
3. Track completion rate, average view percentage, shares, comments, and subs
   per 1,000 views by category and format.
4. Double down on winners by format, not just subject. A winning volcano hook
   pattern can become a river, storm, fungi, or forest format.
5. Remake weak videos only when the source clip has strong visual motion; bad
   footage cannot be rescued by better copy.

## Engagement Automation

Implemented operating loop:

- Every uploaded Short is added to a Start Here playlist, its narrative series
  playlist, and its category/pillar playlist.
- Every upload receives a first comment that asks for the next subject or points
  the viewer back to the visible cue.
- `scripts/reply_comments.py` replies to recent eligible viewer comments with
  concise Wild Brief responses and stores `_data/comment_replies.json` so no
  comment is answered twice.
- Comment replies classify praise, criticism, suggestions, questions, and
  neutral comments, then choose short varied responses while avoiding repeated
  reply text.

The channel automation intentionally stays inside officially supported YouTube
Data API surfaces: playlist creation, playlist item insertion, top-level
comments, and comment replies.

## Robustness Rules

- All learning files are local JSON artifacts committed by the bot workflow.
- Missing analytics, missing visual QA, or provider failures degrade to local
  deterministic scoring instead of stopping the full pipeline.
- Duplicate prevention happens through done markers, rejected queues, cooldowns,
  and comment reply ledgers.
- The system uses only free/open surfaces: GitHub Actions, configured free text
  providers, Pexels, Pixabay, Wikimedia Commons, GBIF, and open-source Python
  libraries.
