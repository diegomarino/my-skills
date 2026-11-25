# Scene transitions

**Default:** `cut`. **Alternatives:** `clear`, `fade`.

| `transition:` | What happens at the start of the next scene |
|---|---|
| `cut` | the screen is wiped instantly and the new scene starts |
| `clear` | `clear` is typed at a prompt, then the screen wipes, like a real shell |
| `fade` | the old frame dissolves into the empty terminal over `transition_duration` (default 0.4s), then the new scene starts |

```yaml
style: { transition: cut, transition_duration: 0.5s }   # default for all scenes
scenes:
  - steps: [{ command: "one" }]
  - transition: fade       # this scene only
    steps: [{ command: "two" }]
```

The first scene has no transition. The old scene's dwell comes from its `hold` (default `scene_hold`, 1 s).

## How fade works

A fade is a short opacity change between two stationary frames: the old frame stays painted while the next one goes from opacity 0 to 1. Nothing moves, so text stays crisp and only a handful of frames are involved. Outside the fade, frames switch with discrete `visibility` steps.

## When to use

`cut` for tight demos, `clear` when the shell realism matters, `fade` between chapters. Do not fade more than once or twice in a short clip.
