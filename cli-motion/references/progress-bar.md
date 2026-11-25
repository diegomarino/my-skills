# Progress bar

**Default:** on, 4 px high, in the theme accent colour over a track derived from the theme background.

```yaml
style:
  progress_bar: true
  progress_color: "#ff6b6b"   # null = theme accent
  progress_track: null        # null = background mixed 12% towards the foreground
  progress_height: 4
```

Set `progress_bar: false` to remove it entirely (no track, no `<animate>`).

The bar is a SMIL `<animate>` on the width of a rect along the bottom edge, with the cast duration as its length. SMIL runs inside `<img>`, which is how GitHub renders SVGs in READMEs; page CSS and JavaScript would not. With `playback: once` it runs one time and freezes full.

## When to use

Leave it on for anything with pauses longer than a second: without it a held frame looks like a frozen image. Turn it off for loops that sit in tight layouts or for stills (stills never have one).
