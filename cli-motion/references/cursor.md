# Cursor

**Default:** `hidden`. **Alternatives:** `block`, `bar`, `underline`; add `cursor_blink: true` to blink while idle.

```yaml
style:
  cursor: block
  cursor_blink: true
```

The cursor is drawn by the scene engine (a coloured cell that follows the typed text, using the theme cursor colour), not by svg-term, so the same look applies to every export. It shows while a prompt waits or text is typed and disappears while output streams. A blinking cursor toggles every 530 ms during pauses, which adds a few frames and a few KB per second of idle time.

A scene can override it: `scenes: - style: { cursor: bar }`.

## When to use

- `hidden` for the smallest files and the calmest result.
- `block` for the classic terminal feel; pair with `cursor_blink` on long pauses so the clip feels alive.
- `bar` or `underline` to imitate an editor or a specific terminal.
