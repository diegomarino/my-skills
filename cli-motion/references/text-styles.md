# Text styles and highlights

**Defaults:** typed text is bold in the theme's foreground colour (`typed_style: "bold fg:foreground"`), output is normal weight, comments are grey (`comment_style: "fg:bright-black"`).

The gh-delta demos type in bold bright white (`\x1b[1;97m`). Bright white is a theme slot that is dim or invisible in some themes (catppuccin's is darker than its foreground; light themes make it unreadable), so cli-motion uses the theme foreground in bold: the same "bold and brightest" look on every theme.

## Style syntax

Space-separated tokens: `bold`, `dim`, `italic`, `underline`, `fg:<colour>`, `bg:<colour>`. A colour is `black red green yellow blue magenta cyan white` (prefix `bright-`), `#rrggbb`, or a theme colour: `foreground background accent accent2 success warning error info`.

## Highlight markup

Inside `output` text (and prompt templates) write `[name]text[/]`:

```yaml
style:
  styles:
    brand: "bold fg:#ff6b6b"        # your own named style
steps:
  - output: |
      [accent]wrote[/] demo.svg in [strong]0.8s[/] [brand]✦[/]
      [bold fg:red]inline[/] styles work too
```

Built-in names: `accent`, `strong`, `muted`, `warn`, `error`, `ok`, plus `prompt`, `cwd`, `branch`, `continuation` for prompts. `[/]` closes the innermost open style. Write a literal bracket as `\[`; text like `[1/3]` is left alone. An unknown name fails the render and lists the defined ones.

## Redefining weights

`typed_style`, `output_style` and `comment_style` take the same syntax, globally or per scene:

```yaml
style: { typed_style: "fg:accent", output_style: "dim" }
```

## When to use

Keep colour for meaning: `accent` for the thing to look at, `muted` for secondary detail, `warn`/`error` for problems. Raw ANSI escapes in `output` and `run` pass through unchanged.
