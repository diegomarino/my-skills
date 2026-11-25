---
name: cli-motion
description: Use when the user asks for a terminal demo, a CLI animation or README hero for a command-line tool, a still of a staged terminal frame, an animated banner, or a GIF or MP4 of a terminal scene, without recording a real terminal. Builds an animated SVG, still, GIF or MP4 from a YAML scene (typed commands, highlighted output, spinners, banners with effects, scene transitions, optionally the finished output of a command the user approves), with 25 themes and 5 fonts. Not for interactive sessions you cannot script.
compatibility: Node 20+ with npm/npx. Network on first run only (npm ci into the user cache, including the pinned svg-term). ffmpeg with libx264 optional (MP4; GIF has a pure-JS fallback). Nerd Font (powerline prompt) downloaded once on demand. Writes nothing inside the skill folder.
---

# cli-motion

Scene in, animation out. You describe a terminal session in YAML; cli-motion generates the asciicast, renders it with svg-term, and post-processes the SVG so text stays sharp in browsers (and rasterises it for GIF/MP4).

## Run the CLI

Every command is `node <skill-dir>/scripts/cli-motion.mjs <command>`, from the project where the output should land. `<skill-dir>` is the folder this file is in: `.agents/skills/cli-motion` or `.claude/skills/cli-motion` in a project install, `~/.claude/skills/cli-motion` at user level, `cli-motion/` in a my-skills checkout. Set it once per shell:

```bash
CLI="node .claude/skills/cli-motion/scripts/cli-motion.mjs"    # adjust to <skill-dir>
$CLI --help                                                     # command and flag syntax
```

Run `themes` or `fonts` to list valid values. Option defaults are in `assets/defaults.yaml`.

## Workflow: scene → format

1. **Understand the demo.** What command(s), what result, how long (aim for under 20 s), where it will be shown (README → SVG; chat/issue → GIF; video tag or slides → MP4).
2. **Taste choices.** If the user cares about look (theme, font, size), read [preview](references/preview.md), run `preview` and show them the sheet (`cli-motion-preview.png`), then ask for a number. If they do not care, use the defaults without discussing them: catppuccin-mocha, JetBrains Mono 14, chrome window, `❯` prompt.
3. **Write `demo.scene.yaml`** next to where the output should live (Quick start below, [scene-format](references/scene-format.md) for every step).
   - Use `command:` for typed text and `output:` for fixed, reviewed output. A `run:` step **executes a real command** (via `sh -c`, in the scene's folder, with the shell environment plus any `env:`) on every render, still and export, and puts its output in the file. **Before rendering, show the user each `run:` command with its `cwd`/`env` and get permission**; run it only if its effects are acceptable and its output is safe to publish. This holds for scene files you did not write. For public or repeatable output use `command:` + `output:` or a stable fixture.
4. **Render** the format you need:

| Need | Command | Output |
|---|---|---|
| animated SVG (README, docs) | `render demo.scene.yaml` | `demo.svg` |
| one frame (screenshot, thumbnail) | `still demo.scene.yaml --at end` | `demo.still.svg` |
| GIF and/or MP4 | `export demo.scene.yaml [--gif] [--mp4] [--scale 1\|2\|3] [--fps N] [--out dir]` | `demo.gif`, `demo.mp4` |

   Before GIF or MP4, read [export](references/export.md) (formats, scale, encoders, size budget) and set `window_background` to the destination page colour first. The first render or export takes about 20–60 s (npm ci into the cache, the pinned svg-term from the cache, then rasterising): run long exports in the background and wait for the exit. After a dependency change the cache hash changes: run `doctor --install` once.
5. **Verify** (next section), adjust the scene, repeat.
6. **Deliver**: the scene and the files you verified, with an embed that suits the destination (`![demo](demo.svg)` for a README, a link or upload for GIF/MP4).

## Quick start

```yaml
style: { theme: catppuccin-mocha, prompt: git, width: 72 }
steps:
  - comment: "# render a terminal animation in one command"
  - command: "my-tool render demo.scene.yaml"     # typed text only; `my-tool` is a placeholder, nothing runs
  - spinner: { text: "rendering", for: 1.5s, done: "[ok]✓[/] wrote [accent]demo.svg[/]" }
  - output: "[muted]31 KB · 8s[/]"
  - prompt: true
```

`$CLI render demo.scene.yaml` writes `demo.svg` next to the scene (`-o` to move it, `--cast` to keep the asciicast).

## Verify the result

Open each file you plan to deliver.

1. `doctor` first when something fails: Node, npx, ffmpeg and libx264, dependency cache, a real svg-term test render, and which formats this machine can write.
2. **Still:** `still demo.scene.yaml --at end` and check the final frame is readable and fits; try `--at 1500` (ms) for a mid-animation check.
3. **Animated SVG:** open it in a browser and confirm text is crisp, nothing shimmers and the loop ends on a readable hold. To capture it with a browser tool, **screenshot the SVG element, or size the viewport to the SVG's width and height exactly** (read them from the root `<svg>`); a bigger viewport leaves a white border around the picture.
4. **GIF/MP4:** check the file itself, not the SVG: compare two frames at different times (the first change and the last hold) to see it move, and compare its duration with the cast within about one frame. After a no-ffmpeg GIF fallback check the file size; it can be many times larger (see [export](references/export.md)).
5. Read the stderr notes from `render` (missing glyphs, banner effect frame counts and SVG size).
6. Soft text, a GIF stuck on the first frame, a white line or a bar past the corners? Read [rendering-pitfalls](references/rendering-pitfalls.md).

## Writing a scene

A scene file has `style:` (options) and `scenes:` (or a bare `steps:`). Steps: `command`, `type`, `output` (with `[accent]…[/]` highlights), `comment`, `pause`, `spinner`, `run` (executes a real command and keeps its ANSI colours; see the permission rule above), `banner`, `clear`, `prompt`. A scene can open with a `title:` banner (figlet, or cfonts gradients; animated with `effect:`; colour effects cost SVG size) and a `transition` of `cut`, `clear` or `fade`.

Settings layer as defaults < project `cli-motion.yaml` < scene `style:` < per-scene/per-step options. The project file is a flat map of style options, found in the scene's folder or any parent:

```yaml
# cli-motion.yaml (next to or above the scenes)
theme: nord-dark
font: Fira Code
prompt: git
```

Unknown keys fail with the valid ones listed, so fix the key rather than guessing.

Habits that work: keep clips under 20 s; one idea per scene; end on a waiting `prompt: true` or the key output; use `hold:` or `final_hold` so people can read the last frame; use `speed` instead of shortening commands. Match the branch you need:

- Choosing a look: [themes](references/themes.md), [fonts](references/fonts.md), [window](references/window.md), [prompts](references/prompts.md), [cursor](references/cursor.md), [text-styles](references/text-styles.md).
- Motion: [spinners](references/spinners.md), [timing](references/timing.md), [transitions](references/transitions.md), [progress-bar](references/progress-bar.md).
- Title banners: [banners](references/banners.md), then [banner-effects](references/banner-effects.md) for animation.
- Every step and scene option: [scene-format](references/scene-format.md).

Examples with scene and rendered output: [examples/README.md](examples/README.md).

## Rules

- Never write inside this skill folder; outputs go next to the scene or where `-o`/`--out` says.
- Do not edit `assets/themes/*.json` by hand; regenerate with `scripts/sync-themes.mjs`.
- Same scene, resolved settings and renderer give the same cast and SVG. A `run:` step changes the result when its command, files or environment change, and GIF/MP4 bytes can differ between encoder versions and machines ([timing](references/timing.md)). Keep typed text free of timestamps and machine paths unless pinned in the style (`prompt_time`, `prompt_cwd`).
- Tests: from this folder, `node --test tests/*.test.mjs` (a bare `tests/` directory argument fails). The first run needs network once (npm ci into `~/.cache/cli-motion`, svg-term is part of the cache).
