# Timing

**Defaults:** typing 45 ms per character plus up to 30 ms of seeded jitter, 120 ms before Enter, 400 ms before a prompt, 50 ms between output lines, 1 s at the end of each scene, 3 s final hold, speed 1×, seed 42.

```yaml
style:
  speed: 1.2          # global: everything 20% faster
  typing_delay: 0.03
  seed: 7
steps:
  - command: "make"
    speed: 3          # this step only: three times faster
  - pause: 2s
  - output: "done"
    hold: 1s          # wait after the step
```

- **Speed** divides every duration (typing, pauses, spinners, holds) except `final_hold`.
- **Determinism:** typing jitter comes from a seeded generator (the same LCG as gh-delta). The same scene, style and seed produce a byte-identical cast and SVG, so regenerating changes git diffs only when the scene changes. Change `seed` to get a different rhythm.
- **Final hold:** `final_hold` is how long the last frame stays before a looping SVG restarts. svg-term derives the loop length from the last event, so the engine appends a no-op event after the hold; without it the hold would silently disappear. See [rendering-pitfalls](rendering-pitfalls.md).
- **`run`** captured output is printed at `line_delay` per line; the real command's duration is not replayed.

## When to use

Keep clips under about 20 seconds. Raise `speed` for long commands, add `pause` before the punchline, and give the last frame a final hold of 3–5 s so people can read it.
