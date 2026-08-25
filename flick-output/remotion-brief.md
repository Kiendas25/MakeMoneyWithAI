# Remotion Composition Brief: Flick

## Objective
Create the approved short-form scene animations from the timestamped transcript.

## Output
- Remotion project: `flick-output/remotion/`
- Format: 9:16 — 1080x1920 at 30 fps
- Rendered scenes:
  - `promise-flash` → `scenes/promise-flash/promise-flash.mp4`
  - `empty-toolbox` → `scenes/empty-toolbox/empty-toolbox.mp4`
  - `star-ranked-scroll` → `scenes/star-ranked-scroll/star-ranked-scroll.mp4`
  - `rapid-fire-cards` → `scenes/rapid-fire-cards/rapid-fire-cards.mp4`
  - `monetize-annotation` → `scenes/monetize-annotation/monetize-annotation.mp4`
  - `pick-one-ship-it` → `scenes/pick-one-ship-it/pick-one-ship-it.mp4`

## Source Material
- Transcript: `transcript.json`
- Approved plan: `flick-plan.md`
- Selected brand assets: none supplied
- Available sound effects: `remotion/public/sounds/`
- Display fonts: `remotion/public/fonts/Anton.ttf`, `remotion/public/fonts/ArchivoBlack.ttf`

## Creative Direction
- User direction: "anime visuals".
- Interpretation: build the whole piece out of anime's visual grammar rather than
  photoreal or AI-generated imagery — radial speed lines, screentone halftone,
  cel-shaded flat colour with hard ink outlines, white impact frames on every beat,
  overshoot-and-settle easing, hard cuts instead of cross-fades, brief chromatic
  RGB split on slams, and drifting petals on the closing scene. Restraint: one
  dominant idea per scene, no decorative motion that is not carrying a transcript beat.
- Avoid: generic filler visuals, unapproved assets, background music, invented
  Japanese text used as decoration.

## Scene Compositions

### promise-flash
- Composition ID: `promise-flash`
- Component: `PromiseFlash`
- Transcript: "Everyone tells you AI will make you rich."
- Time: 0.0s–4.0s (frames 0–120)
- Output: `scenes/promise-flash/promise-flash.mp4`
- What is on screen: gold sunburst rotating behind a gold screentone field; radial speed
  lines rush outward on the slam; "RICH" lands at 1.34× and settles.
- Text on screen: "EVERYONE SAYS" / "AI WILL MAKE YOU" / "RICH"
- Brand assets: none
- Sequential / interaction: kicker rises → headline holds → RICH slams
- Sound effect: `Impact.mp3` at frame 18, on the slam
- Audio-coupled idea: speed-line rush and RGB split both peak on the impact transient
- Transition: white impact frame at 18, exit flash at 116

### empty-toolbox
- Composition ID: `empty-toolbox`
- Component: `EmptyToolbox`
- Transcript: "Nobody tells you which tools actually do it."
- Time: 4.0s–8.5s (frames 120–255)
- Output: `scenes/empty-toolbox/empty-toolbox.mp4`
- What is on screen: six dashed hollow cards track camera-left over an ink screentone
  field; a pink scanline sweeps down and stamps "?" into each card it passes; a pink
  slash is drawn across the row.
- Text on screen: "NOBODY TELLS YOU WHICH" / "ACTUALLY DO IT"
- Brand assets: none
- Sequential / interaction: card row drifts → scan sweep stamps each card → slash strikes
- Sound effect: `Suspense.mp3` at frame 6 under the scan; `transitions.mp3` at frame 100 on the slash
- Audio-coupled idea: the slash stroke and a 6-frame camera shake land on the transient
- Transition: enters on the previous scene's flash, exits on the drawn slash

### star-ranked-scroll
- Composition ID: `star-ranked-scroll`
- Component: `StarRankedScroll`
- Transcript: "Five hundred open-source AI projects. Ranked by stars."
- Time: 8.5s–14.0s (frames 255–420)
- Output: `scenes/star-ranked-scroll/star-ranked-scroll.mp4`
- What is on screen: paper stock with halftone; a clipped viewport scrolls eight ranked
  repo rows upward past a gold focus band; the focused row fills its star and scales up;
  a counter in the header races 0 → 500.
- Text on screen: counter "500+", "OPEN-SOURCE AI PROJECTS", "RANKED BY STARS", and the
  ranked rows (AutoGPT 178.8k, stable-diffusion 157.0k, ollama 153.4k, transformers 150.5k,
  n8n 143.7k, langchain 116.5k, dify 115.6k, ComfyUI 89.8k) — all taken from this repo's README
- Brand assets: none
- Sequential / interaction: rows cross the focus band one at a time; counter locks at frame 132
- Sound effect: `Pop.mp3` at frames 10, 30, 51, 71, 91, 112 (one per row crossing);
  `Correct.mp3` at frame 132 when the counter locks
- Audio-coupled idea: each star fill fires on its pop; the 7% punch-in lands on `Correct.mp3`
- Transition: hard cut in; punch-in hold out

### rapid-fire-cards
- Composition ID: `rapid-fire-cards`
- Component: `RapidFireCards`
- Transcript: "AutoGPT. Ollama. LangChain. n8n. ComfyUI."
- Time: 14.0s–19.5s (frames 420–585)
- Output: `scenes/rapid-fire-cards/rapid-fire-cards.mp4`
- What is on screen: five cel-shaded paper cards, one per beat, each snapping in from an
  alternating direction over its own accent-coloured speed-line field, held 33 frames,
  replaced by a white impact frame. No cross-fades.
- Text on screen: "AutoGPT / 178.8k", "Ollama / 153.4k", "LangChain / 116.5k",
  "n8n / 143.7k", "ComfyUI / 89.8k", each with an "NN / 05" kicker
- Brand assets: none
- Sequential / interaction: card 1 → 2 → 3 → 4 → 5, hard replacement at frames 0/33/66/99/132
- Sound effect: `Pop.mp3` at frames 0, 33, 66, 99, 132 — one per card entry
- Audio-coupled idea: the 3-frame impact flash sits exactly on each pop
- Transition: impact frame in and out of every card

### monetize-annotation
- Composition ID: `monetize-annotation`
- Component: `MonetizeAnnotation`
- Transcript: "Every single one, with how people actually monetize it."
- Time: 19.5s–24.5s (frames 585–735)
- Output: `scenes/monetize-annotation/monetize-annotation.mp4`
- What is on screen: one ink repo card centre on paper stock; three leader lines draw
  outward from the card to three labelled tags that type in character by character;
  a gold rule wipes under the headline; the frame darkens to ink at the end.
- Text on screen: "HOW PEOPLE ACTUALLY MONETIZE IT" / "ollama ★ 153.4k" / "SaaS" / "API" / "CONSULTING"
- Brand assets: none
- Sequential / interaction: card settles → line 1 draws then types (f26) → line 2 (f52) → line 3 (f78) → rule wipes (f104)
- Sound effect: `Typing.mp3` at frame 26, under the label typing
- Audio-coupled idea: each label's characters advance while the typing bed plays
- Transition: scale-in entry; darken-to-ink exit into the final scene

### pick-one-ship-it
- Composition ID: `pick-one-ship-it`
- Component: `PickOneShipIt`
- Transcript: "Star it. Pick one. Ship it."
- Time: 24.5s–29.5s (frames 735–885)
- Output: `scenes/pick-one-ship-it/pick-one-ship-it.mp4`
- What is on screen: counter-rotating gold sunburst, screentone, drifting petals; a hollow
  star fills gold bottom-up and pops; three words slam in on the beat, each with its own
  speed-line burst; ends on the repo wordmark with a gold rule wiping out beneath it.
- Text on screen: "STAR IT" / "PICK ONE" / "SHIP IT" / "MAKE MONEY WITH AI" / "500+ PROJECTS · RANKED"
- Brand assets: none
- Sequential / interaction: star fills (f8–20) → pops (f18–26) → STAR IT (f22) → PICK ONE (f48) → SHIP IT (f74) → wordmark (f110)
- Sound effect: `aha-moment.MP3` at frame 12 on the star fill; `energy.MP3` at frame 110 on the wordmark
- Audio-coupled idea: every word slam is a 3-frame white impact frame on its transient; the
  wordmark lands on a gold impact frame
- Transition: hard cut in; holds on the wordmark to the last frame

## Remotion Instructions
- Build one dedicated React component for each approved scene under `src/scenes/`.
- Register each scene as its own `<Composition>` in `src/Root.tsx`.
- Do not create a combined or all-scenes composition.
- Derive frame timing from the approved transcript timestamps and `scene-spec.json`.
- Use frame-driven Remotion motion. Build the approved visual idea; do not fall back to
  generic title-card layouts.
- Use only selected brand assets from `public/brand-assets/` and bundled SFX from `public/sounds/`.
- Do not add background music. Use an SFX only when it supports the visible action.
- Keep on-screen text readable and render each scene before review.

## Implementation notes
- Shared anime primitives live in `src/anime/kit.tsx`: `Screentone`, `SpeedLines`,
  `Sunburst`, `ImpactFlash`, `CelText`, `Petals`, `slamIn`, and a seeded `rng`.
- Particle and speed-line fields are derived from a fixed seed, not `Math.random`, because
  Remotion renders frames across parallel workers and an unseeded field re-scatters per frame.
- Display fonts are loaded through the FontFace API behind `delayRender` in
  `src/anime/fonts.ts` so type does not reflow mid-render.
