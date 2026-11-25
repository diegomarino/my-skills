# Export: GIF and MP4

```bash
node scripts/cli-motion.mjs export demo.scene.yaml                 # demo.gif + demo.mp4 next to the scene
node scripts/cli-motion.mjs export demo.scene.yaml --gif --scale 1 # a small GIF
node scripts/cli-motion.mjs export demo.scene.yaml --mp4 --fps 60 --out dist/
```

**Defaults:** both formats, 2× scale, MP4 at 30 fps (H.264, yuv420p, `faststart`), one global GIF palette, no dithering. With neither `--gif` nor `--mp4`, both are written; without ffmpeg the MP4 is skipped with a note.

| Option | Config key | Default | Alternatives |
|---|---|---|---|
| `--scale` | `scale` | `2` | `1`, `3` (integers only: text stays pixel-aligned) |
| `--fps` | `mp4_fps` | `30` | 1–120. Fades and the progress bar are sampled at it |
| (none) | `gif_fps` | `15` | frames per second of a fade in a GIF |
| (none) | `gif_progress_step` | `0.5s` | how often the GIF progress bar moves |
| (none) | `gif_dither` | `false` (none) | `bayer` (ordered; ffmpeg only). Error diffusion is refused |
| `--out dir` | | next to the scene | |
| `--encoder` | | `auto` | `ffmpeg`, `js` (force pure JS for the GIF) |

`playback: loop` writes a GIF that loops forever, `once` a GIF that plays once and holds the last frame. `window_background` is the opaque colour behind the window and its rounded corners (GIF and MP4 have no transparency); unset, it is white for light themes and `#0d1117` for dark ones. `cli-motion doctor` lists which formats this machine can write.

## How it works

1. The same stabilised frames as the SVG: every stationary frame with its exact visible interval.
2. Each frame is drawn as a standalone SVG (window, embedded font subset, outer background, the progress bar at that moment) and rasterised once by `@resvg/resvg-js` at an integer scale.
3. Pixel-identical consecutive frames are merged and their durations added; they are never re-encoded.
4. Fades become blended frames (the old screen under the new one at rising opacity).
5. MP4: ffmpeg `concat` with exact durations, resampled to the fps, BT.709 tagged. GIF: ffmpeg `palettegen stats_mode=full` + `paletteuse dither=none` (one palette for the whole file), or without ffmpeg the pure-JS `gifenc` with one shared palette. Durations are written by cli-motion itself (GIF delays are centiseconds; nothing shorter than 20 ms because browsers raise it to 100 ms). Total length stays within one frame of the cast.

## Size budget

GIF size follows the number of distinct frames and their pixels:

- **Scale** is the biggest lever: 1× is about a quarter of 2×. 2× is sharp on retina screens; 1× is fine for docs pages.
- **Progress bar:** each bar step is one more frame in a GIF. `gif_progress_step: 1s` or `progress_bar: false` shrinks the file; `0.25s` makes it smoother and larger. The MP4 samples the bar at the fps, so it is always smooth and costs almost nothing in H.264.
- **Length and width:** fewer columns (`width`), shorter holds, higher `speed`.
- **Typing speed:** every typed character is a frame; `typing_delay` above 0.06 s means fewer, longer frames.
- Prefer MP4 where a video tag works (a README on GitHub can embed an MP4 via a user-attachments URL): it is usually 5–20× smaller than the GIF and plays smoothly.
- A palette of ≤256 colours is used exactly; scenes with many anti-aliased colours are reduced to 256 with no dithering, so flat areas stay flat.

## Needs

Node 20+. ffmpeg is optional: required for MP4 (with libx264), optional for GIF.
