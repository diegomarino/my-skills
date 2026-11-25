# Themes

**Default:** `catppuccin-mocha`. **Alternatives:** the 25 themes copied from tui-design (`node scripts/cli-motion.mjs themes`): catppuccin (latte, frappe, macchiato, mocha), dracula (classic, alucard), everforest, gruvbox, kanagawa, nord-dark, onedark, rose-pine, solarized, tokyonight (day, moon, night, storm), each with its dark/light variants.

```yaml
style:
  theme: tokyonight-night
```

A theme supplies the terminal background, foreground, cursor and the 16 ANSI colours (what `fg:red`, `fg:bright-black` and program output use), plus the named colours `accent`, `accent2`, `success`, `warning`, `error`, `info` that highlights and the progress bar use.

## When to use

- Match the theme of the project's README or site; pick a light theme for light docs.
- Use a dark theme with strong contrast for terminals shown on a coloured page.
- `theme_light` (a light twin for a `<picture>` dark/light pair) is accepted but implemented in a later task.

## Provenance

`assets/themes/*.json` are generated from a tui-design checkout by `scripts/sync-themes.mjs [--from <dir>] [--check]`. Each file keeps its license and sources; do not edit them by hand.

Theme colours reach the SVG through svg-term's Xresources profile. Typed text and the highlight styles use truecolor values from the theme, so light themes stay readable.
