# Scene format

A scene file is YAML: optional `name`, optional `style`, and `scenes` (or a bare `steps` list for a single scene).

```yaml
name: my demo                       # asciicast title (default: cli-motion)
style: { theme: tokyonight-night, prompt: git, speed: 1.2 }
scenes:
  - title: { banner: "cli-motion", font: standard, subtitle: "scene in, animation out" }
    hold: 2s
  - transition: clear
    steps:
      - comment: "# install in a second"
      - command: "npx skills add diegomarino/my-skills@cli-motion"
      - spinner: { text: "installing", for: 1.5s, done: "[ok]✓[/] installed" }
      - output: |
          wrote [accent]demo.svg[/] in [strong]0.8s[/]
      - pause: 2s
  - transition: fade
    steps:
      - run: "my-cli --help"        # real output, ANSI kept
        hold: 4s
```

## Steps

Each step has exactly one action; the other keys are options.

| Action | What it does | Options |
|---|---|---|
| `command: "ls"` | prompt, the text typed in bold, Enter. Extra lines get a `>` continuation prompt | |
| `type: "text"` | types at the cursor, no prompt, no Enter | `enter: true`, `prompt: true`, `bold: false`, `style: name` |
| `output: "text"` | a block revealed line by line; `[name]…[/]` markup | `delay` (per line), `instant: true`, `style` |
| `comment: "# note"` | grey line, instant | `typed: true` (typed after a prompt) |
| `pause: 2s` | wait | |
| `spinner: {…}` | animated line that clears itself | `text`, `for`, `preset`, `done`, `style` |
| `run: "cmd"` | executes a real command, shows the typed command and its captured output | `show` (text to display instead), `timeout` (30s), `cwd`, `env`, `show_command: false`, `allow_failure: true`, `delay`, `instant` |
| `clear` | clears the screen | |
| `prompt: true` | shows a prompt (end a demo on a waiting prompt) | |

Options on every step: `speed` (multiplier for this step), `hold` (pause after the step).

`run` fails the render on a non-zero exit or a timeout, unless `allow_failure: true`. It runs through `sh -c` in the scene's folder with `FORCE_COLOR=1`, so most CLIs keep their colours. Commands that move the cursor or redraw the screen will not look right; capture plain output instead.

## Scenes

A scene takes `title` (banner), `steps`, `transition`, `hold` (dwell at the end of the scene; default `scene_hold`, 2s for a title-only scene), and its own `style:` with scene-scoped options only (prompt, cursor, text styles, timing, spinner, banner, transition). Theme, font, window, size, playback and the progress bar are fixed for the whole render.

Durations are `1.5s`, `800ms`, or a bare number of seconds.

## Errors you will see

Unknown keys, steps with two actions, unknown styles and bad durations fail with the file position and the valid choices. Nothing is silently ignored.

See also: [themes](themes.md), [prompts](prompts.md), [text-styles](text-styles.md), [timing](timing.md), [transitions](transitions.md).
