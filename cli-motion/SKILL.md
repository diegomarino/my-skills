---
name: cli-motion
description: Turns a declarative YAML scene (typed commands, output with highlights, spinners, real captured commands, banners, scene transitions) into a crisp animated SVG terminal recording or a still, themed with any of 25 palettes. Use when asked to make a terminal demo, CLI animation, README hero, or screencast-style SVG for a command-line tool, without recording a real terminal. Output is deterministic, so regenerating gives byte-identical files.
compatibility: Node 20+. Network on first run (npm ci into the user cache, svg-term via npx). ffmpeg optional (MP4 export, later release). Writes nothing inside the skill folder.
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
| `export`, `preview`, `fonts` | arrive in later releases |

## Writing a scene

A scene file has `style:` (options) and `scenes:` (or a bare `steps:`). Steps: `command`, `type`, `output` (with `[accent]…[/]` highlights), `comment`, `pause`, `spinner`, `run` (executes a real command and keeps its ANSI colours), `clear`, `prompt`. Scenes can have a `title:` banner and a `transition` of `cut`, `clear` or `fade`.

Every option has a default in `assets/defaults.yaml`; settings layer as defaults < project `cli-motion.yaml` < scene `style:` < per-scene/per-step options. Unknown keys fail with the valid ones listed, so fix the key rather than guessing.

Habits that work: keep clips under 20 s; one idea per scene; end on a waiting `prompt: true` or the key output; use `run` rather than typing fake output when the command is safe and deterministic; use `hold:` or `final_hold` so people can read the last frame; use `speed` instead of shortening commands.

## References (read the one you need)

- [scene-format](references/scene-format.md): every step and option, with an example
- [themes](references/themes.md), [prompts](references/prompts.md), [text-styles](references/text-styles.md), [cursor](references/cursor.md)
- [spinners](references/spinners.md), [timing](references/timing.md), [transitions](references/transitions.md), [progress-bar](references/progress-bar.md)
- [rendering-pitfalls](references/rendering-pitfalls.md): anti-shimmer, final hold, `--at`

Examples: `examples/quick-demo.scene.yaml` and `examples/multi-scene.scene.yaml` with their rendered `.svg` files.

## Rules

- Never write inside this skill folder; outputs go next to the scene or where `-o` says.
- Do not edit `assets/themes/*.json` by hand; regenerate with `scripts/sync-themes.mjs`.
- Keep scenes deterministic: no timestamps or machine paths in typed text unless pinned in the style (`prompt_time`, `prompt_cwd`).
- Tests: `node --test tests/*.test.mjs` from this folder.
