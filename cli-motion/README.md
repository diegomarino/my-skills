# cli-motion

Make terminal demos from YAML for READMEs and docs: typed commands, progress and output as an animated SVG, still, GIF or MP4. No terminal recording needed.

![a terminal demo: a typed command, a spinner and its result](examples/quick-demo.svg)

You write a scene (typed commands, highlighted output, spinners, banners, transitions, optionally a real command's finished output) and cli-motion renders it with one of 25 colour themes. With the same scene and renderer the SVG is reproducible, so git diffs stay small.

It generalises the demo pipeline of [gh-delta](https://github.com/diegomarino/gh-delta): generate the asciicast instead of recording it, render with svg-term, then replace svg-term's moving frame reel with stationary frames so Chromium does not blur the text.

Scope: scripted demos. A `run:` step captures a command's finished output only; use a terminal recorder for interactive sessions.

## Banner effects

Banners can animate: `type`, `wipe`, `lines`, `slide`, `rainbow`, `gradient-sweep`, `pulse`, `decrypt` and `glitch`. All nine, one per scene:

![all nine banner effects, one scene each](examples/banner-effects.svg)

See [`references/banner-effects.md`](references/banner-effects.md) for options.

## Real-world example

The common PR loop from [gh-delta](https://github.com/diegomarino/gh-delta), recreated as a cli-motion scene from that project's own demo text and colours ([`gh-delta-loop.scene.yaml`](examples/gh-delta-loop.scene.yaml)). It uses `output:` blocks, so it renders without gh-delta installed.

![gh-delta's PR loop, rendered by cli-motion](examples/gh-delta-loop.svg)

## Install

Run in your project (the skill is copied into the project's skill folder):

```bash
npx skills add diegomarino/my-skills --skill cli-motion
```

Then ask your agent for a terminal demo. The installer needs Node 22.20+ (its own requirement); the skill itself runs on Node 20+ with npm/npx.

## Run it yourself

The skill lives in your agent's skill folder, so call its script by path from your project root. The installer prints the destination; for a project install it is `.agents/skills/cli-motion` (and `.claude/skills/cli-motion` for Claude Code). In a my-skills checkout it is `cli-motion/`.

```bash
CLI=.agents/skills/cli-motion/scripts/cli-motion.mjs   # or .claude/skills/…, ~/.claude/skills/…, cli-motion/
node "$CLI" --help
node "$CLI" doctor --install   # first time: fills the dependency cache (network once), then checks Node, npx, ffmpeg + libx264 and runs a test render
node "$CLI" doctor             # any time later: the same checks, no install
```

## Requirements

- Node 20+ with npm and npx.
- Network on first run: `npm ci` of the pinned dependencies (including `svg-term-cli@2.1.1`) into `${XDG_CACHE_HOME:-~/.cache}/cli-motion/<lock-hash>/`. Later runs need no network. After a dependency change run `doctor --install` once.
- ffmpeg **with libx264** for MP4 (`ffmpeg -encoders | grep libx264`). It also gives GIF its best encoder; without it GIF uses a pure-JS fallback that can be many times larger.
- Nothing is written inside the skill folder and nothing is installed globally.

The first render or export takes about 20–60 s. Run long exports in the background.

## Quick start

From your project root:

```bash
cat > demo.scene.yaml <<'YAML'
style: { theme: catppuccin-mocha, prompt: git, width: 72 }
steps:
  - comment: "# render a terminal animation in one command"
  - command: "my-tool render demo.scene.yaml"    # typed text only; my-tool is a placeholder
  - spinner: { text: "rendering", for: 1.5s, done: "[ok]✓[/] wrote [accent]demo.svg[/]" }
  - prompt: true
YAML
node "$CLI" render demo.scene.yaml                       # → demo.svg
node "$CLI" export demo.scene.yaml --out ./out           # → out/demo.gif and out/demo.mp4
node "$CLI" preview --out ./sheet.png                    # contact sheet of fonts × sizes × themes
```

Then embed it: `![demo](demo.svg)`. See [`examples/`](examples/README.md) for more scenes with their rendered output.

A `run: "cmd"` step executes that command on every render. Check each one before you render, especially in a scene someone else wrote.

## More commands

```bash
node "$CLI" still  demo.scene.yaml --at end -o demo.still.svg   # a single frame
node "$CLI" export demo.scene.yaml --gif --scale 1 --out ./out  # a small GIF only
node "$CLI" themes                                              # list the 25 themes (also: fonts)
```

Inside a my-skills checkout, add `-o`/`--out` to anything you run on the shipped examples, or the output lands next to them.

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

From a my-skills checkout:

```bash
cd cli-motion && node --test tests/*.test.mjs       # a bare tests/ directory argument fails
node scripts/sync-themes.mjs --check                # themes match ../tui-design
```

The first test run needs network once (npm ci into `~/.cache/cli-motion`, svg-term included).

## Determinism

With the same scene, resolved settings and renderer, the cast and SVG are reproducible. A `run:` step can change the result when its command, files or environment change. GIF and MP4 bytes can differ between encoder versions and machines; pin the encoder if you compare them.

## License

Each bundled theme (MIT/Apache-2.0 palettes from [tui-design](../tui-design/)) keeps its own license and sources in its file. cli-motion itself is MIT-licensed (see [LICENSE](LICENSE)); the theme licenses found are MIT and Apache-2.0 (Tokyo Night), both compatible with redistribution under MIT. Upstream license texts and notices are reproduced in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Options implemented in later releases (dark/light pairs) are already accepted in `assets/defaults.yaml` and marked there.
