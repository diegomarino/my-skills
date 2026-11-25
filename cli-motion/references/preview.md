# Preview sheet

`cli-motion preview` renders one mini scene across font × size × theme and lays the results out as a contact sheet, so you can look and say "number 7".

```bash
node scripts/cli-motion.mjs preview                                  # all 5 fonts × 14 px × 3 themes → cli-motion-preview.png
node scripts/cli-motion.mjs preview --fonts "Fira Code,JetBrains Mono" --sizes 12,14,16 --themes nord-dark,dracula-classic --out sheet.png
node scripts/cli-motion.mjs preview --fonts all --themes all --out sheet.html
```

**Default:** a PNG sheet of all five fonts × 14 px × three themes. **Alternatives:** `--out sheet.html` for a browser grid; `--fonts`, `--sizes`, `--themes` narrow or widen it.

**Example:**

![a preview contact sheet](../examples/preview-sheet.png)

| Flag | Default | Notes |
|---|---|---|
| `--fonts` | all five | comma list or `all` |
| `--sizes` | `14` | px, comma list |
| `--themes` | `catppuccin-mocha,tokyonight-night,solarized-light` | ids from `cli-motion themes`, or `all` |
| `--out` | `cli-motion-preview.png` | `.png` or `.html` |

The mini scene is picked to make fonts differ: ligatures (`=> != -> <= ===`), confusable letters (`Il1 O0o agQ rn m`), bold and muted text, and none of the glyphs that every font borrows from DejaVu.

Every cell is a real render through the same pipeline as `render` (window frame, embedded font subset), with a label beneath: `#07`, `font: …`, `font_size: …`, `theme: …`. Those three lines paste straight into `style:`.

- **PNG** is drawn by `@resvg/resvg-js` at 2× (the font subsets are passed to it as TTF files: resvg ignores `@font-face`); one image, easy to send in a chat or issue.
- **HTML** inlines each cell as an `<img>` of its SVG (so it also checks `<img>` rendering) in a responsive grid; opens in any browser, light or dark.

The sheet is deterministic: same flags, same bytes. Many cells take time (about 1 s each); keep `--themes all --fonts all` for HTML you open once.

Example: `examples/preview-sheet.png`.

## When to use

Before committing to a look: when someone asks "which font/theme?", run a sheet with 3 to 6 candidates instead of rendering full animations.
