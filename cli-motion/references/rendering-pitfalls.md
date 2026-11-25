# Rendering pitfalls

## Anti-shimmer (why the SVG is post-processed)

svg-term lays all terminal frames side by side on a wide reel and animates the reel with `transform: translateX(…)`. Chromium promotes that large moving layer to a raster layer, so the text is re-rasterised as it moves and glyph anti-aliasing changes with each sub-pixel offset: README-sized text looks soft or shimmers.

cli-motion keeps svg-term's vector frames but rewrites how a frame is chosen: every frame sits at the same origin, is `visibility:hidden` by default, and a discrete `step-end` animation makes it visible for exactly its interval. No `translateX` remains and nothing is composited as a moving layer. (`visibility`, not `opacity`: hidden frames are not painted.) The rewrite is `scripts/lib/svg/stabilize.mjs`, ported from gh-delta, and the tests assert no `translateX` is left. For raster exports the same principle applies: integer pixel positions, one rasteriser, no error-diffusion dithering.

## Raster anti-shimmer (GIF and MP4)

GIF and MP4 shimmer for different reasons than the SVG: a changing palette or error-diffusion dithering gives the same text different pixels from frame to frame. The export follows these rules, and the tests check them:

- **One rasteriser:** every frame goes through `@resvg/resvg-js`, never a mix of browsers or renderers.
- **Integer scale and integer positions:** `--scale` is 1, 2 or 3; the window, terminal and progress bar sit on whole pixels (the bar's width is rounded to a whole pixel), so a frame that did not change renders to the very same pixels.
- **Identical frames are merged**, not re-encoded, so a held frame cannot drift between encodes.
- **One global palette for the whole GIF** (`palettegen stats_mode=full`, or one shared palette in the pure-JS encoder), never a palette per frame: the same colour keeps the same index in every frame.
- **No error-diffusion dithering** (`dither=none`, optionally `bayer`, which is a fixed pattern). Floyd–Steinberg and `sierra2_4a` spread rounding errors to neighbouring pixels, so a changed pixel on one line changes the dots on the next; `gif_dither` rejects them.
- **Frame times are written exactly:** GIF delays are centiseconds and ffmpeg's GIF muxer snaps to its own time base, so cli-motion writes the delays itself and never emits a frame under 20 ms.
- **MP4:** yuv420p halves colour resolution, which softens coloured text edges slightly; the export tags BT.709 so players do not shift colours, and uses `-tune animation` with a low CRF.

## Final hold

svg-term takes the loop duration from the **last event**. A trailing `wait` emits nothing, so the hold would be dropped and the loop would restart the instant the last line appears. The engine therefore appends a no-op event (`\x1b[0m`) after `final_hold`. If you hand-write casts, do the same.

## Stills: `--at`

`cli-motion still scene.yaml --at <ms|end>` renders one frame. `end` is the last event minus 100 ms, the final frame after the last output but before the hold ends. The terminal height is `auto` by default (rows of the tallest screen), so nothing scrolls off the final frame; set `height:` yourself only when you want an exact size.

## Other things that bite

- **Playback:** `playback: once` makes the animation play one time and hold the last frame; the default loops forever.
- **Wide characters:** CJK and emoji count as one cell in the row tracker but may take two on screen; keep demos to single-width glyphs or widen `width`.
- **Output that moves the cursor** (`run` of a TUI) will not look right; capture plain output or use `output:`.
- **Colours not themed:** a program printing 256-colour or truecolor codes keeps those exact colours; only the 16 ANSI slots follow the theme.
- **Banners:** a figlet banner wider than `width` fails; pick a narrower font (`small`, `mini`) or widen the terminal.
- **First run** installs dependencies into the cache directory and fetches svg-term via npx; offline, only an already-cached run works (`cli-motion doctor`).
- **Banner effects:** colour effects repaint every cell per frame; each frame is a full SVG screen. Frames = fps × duration; keep `fps` low. See [banner-effects](banner-effects.md).
