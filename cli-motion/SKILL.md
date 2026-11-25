---
name: cli-motion
description: Turns a declarative YAML scene (typed commands, output with highlights, spinners, real captured commands, banners, scene transitions) into a crisp animated SVG terminal recording, GIF, MP4 or a still, themed with any of 25 palettes. Use when asked to make a terminal demo, CLI animation, README hero, or screencast-style SVG for a command-line tool, without recording a real terminal. Output is deterministic, so regenerating gives byte-identical files.
compatibility: Node 20+. Network on first run (npm ci into the user cache, svg-term via npx). ffmpeg optional (MP4 export; GIF has a pure-JS fallback). Nerd Font (powerline prompt) downloaded once on demand. Writes nothing inside the skill folder.
---

# cli-motion

Scene in, animation out. You describe a terminal session in YAML; cli-motion generates the asciicast, renders it with svg-term, and post-processes the SVG so text stays sharp in browsers.

Run everything with `node scripts/cli-motion.mjs` (path relative to this skill folder). The first run installs pinned dependencies into `${XDG_CACHE_HOME:-~/.cache}/cli-motion/` (needs network once).

## Quick start

1. Write `demo.scene.yaml`:

```yaml
style: { theme: catppuccin-mocha, prompt: git, width: 72 }
steps:
  - comment: "# render a terminal animation in one command"
  - command: "cli-motion render demo.scene.yaml"
  - spinner: { text: "rendering", for: 1.5s, done: "[ok]✓[/] wrote [accent]demo.svg[/]" }
  - output: "[muted]31 KB · 8s[/]"
  - prompt: true
```

2. Render it: `node scripts/cli-motion.mjs render demo.scene.yaml` → `demo.svg` next to the scene (`-o` to move it, `--cast` to keep the asciicast).
3. Check one frame: `node scripts/cli-motion.mjs still demo.scene.yaml --at end`.
4. Open the SVG in a browser and confirm the text is crisp.

## Commands

| Command | Does |
|---|---|
| `render <scene> [-o out.svg] [--cast]` | animated SVG (loops by default) |
| `still <scene> [--at <ms\|end>] [-o out.svg]` | a single frame |
| `themes [--json]` | list the 25 themes |
| `doctor [--install]` | Node version, ffmpeg, dependency cache |
| `fonts [--json]` | the five fonts, their packages, Nerd Font cache state |
| `preview [--fonts] [--sizes] [--themes] [--out sheet.png\|html]` | contact sheet of font × size × theme, each cell labelled |
| `export <scene> [--gif] [--mp4] [--scale 1\|2\|3] [--fps N] [--out dir]` | GIF and MP4 (default both, 2×, 30 fps); see [export](references/export.md) |

## Writing a scene

A scene file has `style:` (options) and `scenes:` (or a bare `steps:`). Steps: `command`, `type`, `output` (with `[accent]…[/]` highlights), `comment`, `pause`, `spinner`, `run` (executes a real command and keeps its ANSI colours), `clear`, `prompt`. Scenes can have a `title:` banner (figlet, or cfonts gradients) and a `transition` of `cut`, `clear` or `fade`.

Every option has a default in `assets/defaults.yaml`; settings layer as defaults < project `cli-motion.yaml` < scene `style:` < per-scene/per-step options. Unknown keys fail with the valid ones listed, so fix the key rather than guessing.

Choosing a look: run `preview` for a labelled contact sheet and pick by number. The window frame (title bar, dots, radius, shadow) is ours: see [window](references/window.md).

Habits that work: keep clips under 20 s; one idea per scene; end on a waiting `prompt: true` or the key output; use `run` rather than typing fake output when the command is safe and deterministic; use `hold:` or `final_hold` so people can read the last frame; use `speed` instead of shortening commands.

## References (read the one you need)

- [scene-format](references/scene-format.md): every step and option, with an example
- [themes](references/themes.md), [prompts](references/prompts.md), [text-styles](references/text-styles.md), [cursor](references/cursor.md)
- [spinners](references/spinners.md), [timing](references/timing.md), [transitions](references/transitions.md), [progress-bar](references/progress-bar.md)
- [window](references/window.md), [fonts](references/fonts.md), [banners](references/banners.md), [preview](references/preview.md)
- [export](references/export.md): GIF/MP4 formats, scales, fps, size budget
- [rendering-pitfalls](references/rendering-pitfalls.md): anti-shimmer (SVG and raster), final hold, `--at`

Examples: `examples/quick-demo.scene.yaml` and `examples/multi-scene.scene.yaml` with their rendered `.svg` files.

## Rules

- Never write inside this skill folder; outputs go next to the scene or where `-o` says.
- Do not edit `assets/themes/*.json` by hand; regenerate with `scripts/sync-themes.mjs`.
- Keep scenes deterministic: no timestamps or machine paths in typed text unless pinned in the style (`prompt_time`, `prompt_cwd`).
- Tests: `node --test tests/*.test.mjs` from this folder.
