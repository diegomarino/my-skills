# Spinners

**Default:** `dots` (⠋⠙⠹…). **Alternatives:** `line` (`-\|/`), `arc` (◜◠◝), `bounce`, `bar` (a fake progress bar that fills over the duration).

```yaml
steps:
  - spinner: { text: "rendering", for: 1.5s, done: "[ok]✓[/] rendered" }
  - spinner: { preset: bar, for: 2s }
```

`for` is the duration (scaled by `speed`), `done` replaces the line when finished (omit it to just clear the line), `style` picks the colour (default `spinner_style: accent`). Change the default with `style.spinner`.

Presets live in `assets/spinners.json`: `frames` plus an `interval`, or `kind: progress` with `width`, `fill`, `empty`.

## When to use

Use a spinner to stand in for slow work the viewer should not wait through (installs, builds). Keep it between 1 and 2 seconds; longer reads as a stall. Use `bar` when a percentage tells the story.
