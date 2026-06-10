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

The channel automation intentionally stays inside officially supported YouTube
Data API surfaces: playlist creation, playlist item insertion, top-level
comments, and comment replies.
