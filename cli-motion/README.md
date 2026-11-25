# cli-motion

![all nine banner effects](examples/banner-effects.svg)

Terminal animations from a YAML scene: typed commands, highlighted output, spinners, real captured commands, banners and scene transitions, rendered as a crisp animated SVG (or a still) with one of 25 colour themes. Output is deterministic, so regenerating gives byte-identical files and clean git diffs.

It generalises the demo pipeline of [gh-delta](https://github.com/diegomarino/gh-delta): generate the asciicast instead of recording it, render with svg-term, then replace svg-term's moving frame reel with stationary frames so Chromium does not blur the text.

## Install

```bash
npx skills add diegomarino/my-skills@cli-motion
```

## Requirements

- Node 20+ (nothing else is required).
- Network on first run: `npm ci` of the pinned dependencies into `${XDG_CACHE_HOME:-~/.cache}/cli-motion/<lock-hash>/` including the pinned `svg-term-cli@2.1.1` (later runs need no network).
- ffmpeg is optional: needed for MP4, and gives GIF its best encoder (GIF has a pure-JS fallback).
- Nothing is written inside the skill folder and nothing is installed globally.

The first render or export takes about 20–60 s (the pinned svg-term from the cache, then rasterising). Run long exports in the background. After a dependency change the cache hash changes: run `cli-motion doctor --install` once.

## Quick start

```bash
cat > demo.scene.yaml <<'YAML'
style: { theme: catppuccin-mocha, prompt: git, width: 72 }
steps:
  - comment: "# render a terminal animation in one command"
  - command: "cli-motion render demo.scene.yaml"
  - spinner: { text: "rendering", for: 1.5s, done: "[ok]✓[/] wrote [accent]demo.svg[/]" }
  - prompt: true
YAML
node cli-motion/scripts/cli-motion.mjs render demo.scene.yaml    # → demo.svg
```

Then embed it: `![demo](demo.svg)`. See [`examples/`](examples/README.md) for more scenes with their rendered output.

## Commands

```bash
node cli-motion/scripts/cli-motion.mjs render cli-motion/examples/quick-demo.scene.yaml -o /tmp/out/quick-demo.svg
node cli-motion/scripts/cli-motion.mjs still  cli-motion/examples/quick-demo.scene.yaml --at end -o /tmp/out/quick-demo.still.svg
node cli-motion/scripts/cli-motion.mjs export cli-motion/examples/quick-demo.scene.yaml --out /tmp/out   # GIF + MP4 (--out is required inside the skill folder)
node cli-motion/scripts/cli-motion.mjs themes
node cli-motion/scripts/cli-motion.mjs doctor
```

![quick demo](examples/quick-demo.svg)

First run installs the pinned dependencies (`yaml`, `figlet`, `@resvg/resvg-js`, `gifenc`, fonts …) into `${XDG_CACHE_HOME:-~/.cache}/cli-motion/<lock-hash>/` with `npm ci`; nothing is written inside the skill folder and nothing is global. svg-term-cli@2.1.1 is one of those pinned dependencies and runs from the cache.

## Layout

```
SKILL.md  README.md
scripts/cli-motion.mjs        CLI: render, still, export, themes, fonts, preview, doctor
scripts/lib/{config,scene,svg,raster,preview,fonts}/   options+themes, scene→cast, cast→SVG, SVG→GIF/MP4, contact sheet, fonts
scripts/package.json + lock   pinned runtime dependencies
scripts/sync-themes.mjs       regenerate assets/themes from a tui-design checkout
assets/defaults.yaml          every option and its default
assets/{themes,prompts}/  assets/spinners.json
references/*.md               one file per option family
examples/                     scenes and their rendered SVG/GIF/MP4 (gallery in examples/README.md)
tests/                        node --test
```

## Develop

```bash
cd cli-motion && node --test tests/*.test.mjs       # a bare tests/ directory argument fails
node scripts/sync-themes.mjs --check                # themes match ../tui-design
```

The first test run needs network once (npm ci into `~/.cache/cli-motion`, svg-term included).

Themes come from [tui-design](../tui-design/) (MIT/Apache-2.0 palettes, each theme file keeps its license and sources). Options implemented in later releases (dark/light pairs) are already accepted in `assets/defaults.yaml` and marked there.
