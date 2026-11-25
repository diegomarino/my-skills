---
name: cli-motion
description: Turns a declarative YAML scene (typed commands, highlighted output, spinners, real captured commands, banners with animated effects, scene transitions) into a crisp animated SVG terminal recording, still, GIF or MP4, themed with any of 25 palettes and 5 fonts. Use when asked for a terminal demo, CLI animation, README hero, screencast-style SVG, terminal GIF or MP4, or an animated banner for a command-line tool, without recording a real terminal. Output is deterministic, so regenerating gives byte-identical files.
compatibility: Node 20+. Network on first run (npm ci into the user cache, svg-term via npx). ffmpeg optional (MP4 export; GIF has a pure-JS fallback). Nerd Font (powerline prompt) downloaded once on demand. Writes nothing inside the skill folder.
---

# cli-motion

Scene in, animation out. You describe a terminal session in YAML; cli-motion generates the asciicast, renders it with svg-term, and post-processes the SVG so text stays sharp in browsers (and rasterises it for GIF/MP4).

Run everything with `node scripts/cli-motion.mjs <command>` (path relative to this skill folder; use the absolute path of the installed skill from elsewhere).

## When to use

- A README hero, docs page, release post or issue needs a terminal demo of a CLI.
- The demo must be reproducible and diff-friendly (a scene file in git, regenerated on demand).
- Not for recording an interactive session you cannot script, or TUIs that redraw the screen (`run` captures only finished output).

## Workflow: scene → format

1. **Understand the demo.** What command(s), what result, how long (aim for under 20 s), where it will be shown (README → SVG; chat/issue → GIF; video tag or slides → MP4).
2. **Taste choices.** If the user cares about look (theme, font, size), run `preview` first and show them the sheet (`cli-motion-preview.png`), then ask for a number. If they do not care, use the defaults without discussing them: catppuccin-mocha, JetBrains Mono 14, chrome window, `❯` prompt.
3. **Write `demo.scene.yaml`** next to where the output should live (see Quick start and [scene-format](references/scene-format.md)).
4. **Render** the format you need:

| Need | Command | Output |
|---|---|---|
| animated SVG (README, docs) | `render demo.scene.yaml` | `demo.svg` |
| one frame (screenshot, thumbnail) | `still demo.scene.yaml --at end` | `demo.still.svg` |
| GIF and/or MP4 | `export demo.scene.yaml [--gif] [--mp4] [--scale 1\|2\|3] [--fps N]` | `demo.gif`, `demo.mp4` |

   The first render or export takes about 20–60 s (npm ci into the cache, svg-term via npx, then rasterising). Run long exports in the background and wait for the exit; later runs are faster. After a dependency change the cache hash changes: run `doctor --install` once.
5. **Verify** (next section), adjust the scene, repeat.
6. **Deliver**: the scene and its rendered files, with the embed line (`![demo](demo.svg)`). For GIF/MP4 always set `window_background` first.

## Quick start

```yaml
style: { theme: catppuccin-mocha, prompt: git, width: 72 }
steps:
  - comment: "# render a terminal animation in one command"
  - command: "cli-motion render demo.scene.yaml"
  - spinner: { text: "rendering", for: 1.5s, done: "[ok]✓[/] wrote [accent]demo.svg[/]" }
  - output: "[muted]31 KB · 8s[/]"
  - prompt: true
```

`node scripts/cli-motion.mjs render demo.scene.yaml` writes `demo.svg` next to the scene (`-o` to move it, `--cast` to keep the asciicast).

## Verify the result

1. `doctor` first when something fails: Node version, ffmpeg, npx, dependency cache, which formats this machine can write.
2. `still demo.scene.yaml --at end` and look at the final frame; try `--at 1500` (ms) for a mid-animation check. Stills auto-size so nothing scrolls off.
3. Open the animated SVG in a browser and confirm text is crisp, nothing shimmers and the loop ends on a readable hold. To capture it with a browser tool, **screenshot the SVG element, or size the viewport to the SVG's width and height exactly** (read them from the root `<svg>`); a bigger viewport leaves a white border around the picture.
4. For GIF/MP4, check the length matches the cast and that the GIF really moves (open it, or compare two stills at different times).
5. Read the stderr notes from `render` (missing glyphs, banner effect frame counts and SVG size).
6. A pitfall you recognise (soft text, GIF stuck on the first frame, white line, bar past corners)? See "Bugs we already hit" in [rendering-pitfalls](references/rendering-pitfalls.md).

## Commands

| Command | Does |
|---|---|
| `render <scene> [-o out.svg] [--cast]` | animated SVG (loops by default) |
| `still <scene> [--at <ms\|end>] [-o out.svg]` | a single frame |
| `export <scene> [--gif] [--mp4] [--scale 1\|2\|3] [--fps N] [--out dir]` | GIF and MP4 (default both, 2×, 30 fps) |
| `preview [--fonts] [--sizes] [--themes] [--out sheet.png\|html]` | contact sheet of font × size × theme, each cell labelled |
| `themes [--json]` | list the 25 themes |
| `fonts [--json]` | the five fonts, their packages, Nerd Font cache state |
| `doctor [--install]` | Node, ffmpeg, npx, dependency cache; `--install` fills the cache |

## Writing a scene

A scene file has `style:` (options) and `scenes:` (or a bare `steps:`). Steps: `command`, `type`, `output` (with `[accent]…[/]` highlights), `comment`, `pause`, `spinner`, `run` (executes a real command and keeps its ANSI colours), `clear`, `prompt`. A scene can open with a `title:` banner (figlet, or cfonts gradients; animated with `effect:`: type, wipe, lines, slide, rainbow, gradient-sweep, pulse, decrypt, glitch; colour effects cost SVG size) and a `transition` of `cut`, `clear` or `fade`.

Every option has a default in `assets/defaults.yaml`; settings layer as defaults < project `cli-motion.yaml` < scene `style:` < per-scene/per-step options. Unknown keys fail with the valid ones listed, so fix the key rather than guessing.

Habits that work: keep clips under 20 s; one idea per scene; end on a waiting `prompt: true` or the key output; use `run` rather than typing fake output when the command is safe and deterministic; use `hold:` or `final_hold` so people can read the last frame; use `speed` instead of shortening commands.

## References (one level deep; read the one you need)

Each file has the same shape: default, alternatives, example image, when to use.

| File | Covers |
|---|---|
| [scene-format](references/scene-format.md) | every step and scene option, with an example |
| [themes](references/themes.md) | the 25 themes, light/dark choice |
| [fonts](references/fonts.md) | 5 fonts, sizes, Nerd Font, how fonts are embedded |
| [window](references/window.md) | chrome / plain / none, radius, shadow, outer background |
| [prompts](references/prompts.md) | simple, dollar, path, git, template, powerline |
| [cursor](references/cursor.md) | hidden, block, bar, underline, blinking |
| [text-styles](references/text-styles.md) | typed/output/comment weights, `[name]…[/]` highlights |
| [spinners](references/spinners.md) | dots, line, arc, bounce, fake progress bar |
| [timing](references/timing.md) | speed, typing delay, holds, seed, determinism |
| [transitions](references/transitions.md) | cut, clear, fade |
| [progress-bar](references/progress-bar.md) | the SMIL bar: colour, height, off |
| [banners](references/banners.md) | figlet and cfonts banners, gradients |
| [banner-effects](references/banner-effects.md) | the nine animated banner effects and their size cost |
| [preview](references/preview.md) | the contact sheet for choosing a look |
| [export](references/export.md) | GIF/MP4 formats, scales, fps, size budget |
| [rendering-pitfalls](references/rendering-pitfalls.md) | anti-shimmer, final hold, `--at`, bugs we already hit |

Examples with scene and rendered output: [examples/README.md](examples/README.md) (quick-demo, framed-demo, multi-scene, banner-effects, preview sheet).

## Rules

- Never write inside this skill folder; outputs go next to the scene or where `-o` says.
- Do not edit `assets/themes/*.json` by hand; regenerate with `scripts/sync-themes.mjs`.
- Keep scenes deterministic: no timestamps or machine paths in typed text unless pinned in the style (`prompt_time`, `prompt_cwd`).
- Tests: from this folder, `node --test tests/*.test.mjs` (a bare `tests/` directory argument fails). The first run needs network once (npm ci into `~/.cache/cli-motion`, svg-term via npx).
