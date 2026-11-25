// Make svg-term animations render sharply in Chromium.
//
// svg-term lays every terminal frame beside the previous one (`<svg x="…">`) and
// animates their parent with `transform: translateX(…)`. Chromium promotes that very
// wide moving reel to a raster layer, so glyph anti-aliasing changes with the
// sub-pixel position and text shimmers or blurs. We keep the same vector frames and
// timing but select a frame differently:
//
// - `x` is removed, so every frame sits at the same origin (no reel, no translate);
// - each frame is `visibility:hidden` by default and made visible for exactly its
//   keyframe interval (`visibility` rather than `opacity`: hidden frames are not painted);
// - one discrete CSS animation per frame with `step-end`, so nothing interpolates;
// - keyframes are derived from svg-term's own percentages, so typing cadence, pauses,
//   the final hold and the progress bar stay in sync.
//
// Extensions over the original gh-delta stabiliser:
// - `once`: play a single time and keep the last frame (no restart);
// - `fades`: a short opacity ramp from the old frame to the first frame of the next
//   scene. Both frames stay stationary; only opacity changes, and only briefly.

function keyframeBlock(svg) {
  const start = svg.indexOf('@keyframes ');
  if (start === -1) throw new Error('svg-term keyframes not found');
  const open = svg.indexOf('{', start);
  let depth = 0;
  for (let index = open; index < svg.length; index++) {
    if (svg[index] === '{') depth++;
    if (svg[index] === '}') depth--;
    if (depth === 0) return { start, end: index + 1, css: svg.slice(start, index + 1) };
  }
  throw new Error('unterminated svg-term keyframes');
}

const num = (n) => String(Number(n.toFixed(4)));

export function stabilizeSvgAnimation(svg, { once = false, fades = [], duration: castDuration } = {}) {
  const duration = svg.match(/animation-duration:([\d.]+)s/)?.[1];
  const keyframes = keyframeBlock(svg);
  const reel = svg.match(
    /<g style="animation-duration:[^"]+"><svg width="\d+">((?:<svg(?: x="\d+")?>[\s\S]*?<\/svg>)+)<\/svg><\/g>/,
  );
  if (!duration || !reel) throw new Error('unsupported svg-term animated reel');
  const total = Number(duration);

  const steps = [
    ...keyframes.css.matchAll(/([\d.]+%|to)\{transform:translateX\((-?\d+)px\)\}/g),
  ].map(([, at, offset]) => ({
    at: at === 'to' ? 100 : Number.parseFloat(at),
    x: Math.abs(Number(offset)),
  }));
  if (steps.length < 2) throw new Error('svg-term animation has too few frames');

  const frames = [...reel[1].matchAll(/<svg(?: x="(\d+)")?>[\s\S]*?<\/svg>/g)];
  const frameAt = new Map(frames.map((match) => [Number(match[1] ?? 0), match[0]]));

  // Which intervals start a faded-in scene, and how long the fade lasts (in %).
  const pct = (seconds) => (seconds / (castDuration ?? total)) * 100;
  const fadeAtIndex = new Map();
  for (const f of fades) {
    const at = pct(f.at);
    let idx = steps.findIndex((s, i) => i < steps.length - 1 && s.at >= at - 0.05);
    if (idx > 0) fadeAtIndex.set(idx, pct(f.duration));
  }

  const rules = [];
  const overlays = [];
  const lastIndex = steps.length - 2;

  // The state at 100% is the instantaneous loop boundary; the previous frame already
  // stays visible through 100%, so it is not emitted again.
  for (let index = 0; index <= lastIndex; index++) {
    const start = steps[index].at;
    const end = steps[index + 1].at;
    const frame = frameAt.get(steps[index].x);
    if (!frame) throw new Error(`svg-term frame at x=${steps[index].x} not found`);

    // A frame that precedes a fade stays painted while the next one fades in over it.
    let visibleEnd = end;
    const next = fadeAtIndex.get(index + 1);
    if (next != null) visibleEnd = Math.min(100, end + next);

    const name = `overlay-${index}`;
    const before = Math.max(0, start - 0.001);
    const isLastHeld = once && index === lastIndex;
    const until = isLastHeld ? 100 : Math.max(start, visibleEnd - 0.001);
    let css =
      `@keyframes ${name}{` +
      `${start === 0 ? '' : `0%,${num(before)}%{visibility:hidden}`}` +
      `${num(start)}%{visibility:visible}${num(until)}%{visibility:visible}`;
    if (!isLastHeld) css += `${num(visibleEnd)}%{visibility:hidden}100%{visibility:hidden}`;
    css += '}';
    rules.push(css);

    let anim = `animation:${name} ${duration}s step-end ${once ? '1 forwards' : 'infinite'}`;
    const fadeLen = fadeAtIndex.get(index);
    if (fadeLen != null) {
      const fname = `fade-${index}`;
      const fadeEnd = Math.min(100, start + fadeLen);
      rules.push(
        `@keyframes ${fname}{0%,${num(start)}%{opacity:0}${num(fadeEnd)}%{opacity:1}100%{opacity:1}}`,
      );
      anim += `,${fname} ${duration}s linear ${once ? '1 forwards' : 'infinite'}`;
    }
    overlays.push(frame.replace(/^<svg(?: x="\d+")?>/, `<svg style="visibility:hidden;${anim}">`));
  }

  return svg.replace(keyframes.css, rules.join('')).replace(reel[0], `<g>${overlays.join('')}</g>`);
}

/**
 * The stationary states of an svg-term animation, for raster export.
 * Returns { total, states: [{ start, end, markup }] (seconds; markup is the frame without
 * its reel offset), compose(markup) } where compose puts markup in the svg as the only frame.
 */
export function reelStates(svg) {
  const duration = svg.match(/animation-duration:([\d.]+)s/)?.[1];
  const keyframes = keyframeBlock(svg);
  const reel = svg.match(
    /<g style="animation-duration:[^"]+"><svg width="\d+">((?:<svg(?: x="\d+")?>[\s\S]*?<\/svg>)+)<\/svg><\/g>/,
  );
  if (!duration || !reel) throw new Error('unsupported svg-term animated reel');
  const total = Number(duration);
  const steps = [
    ...keyframes.css.matchAll(/([\d.]+%|to)\{transform:translateX\((-?\d+)px\)\}/g),
  ].map(([, at, offset]) => ({ at: at === 'to' ? 100 : Number.parseFloat(at), x: Math.abs(Number(offset)) }));
  if (steps.length < 2) throw new Error('svg-term animation has too few frames');
  const frames = [...reel[1].matchAll(/<svg(?: x="(\d+)")?>[\s\S]*?<\/svg>/g)];
  const frameAt = new Map(frames.map((m) => [Number(m[1] ?? 0), m[0]]));
  const states = [];
  for (let i = 0; i < steps.length - 1; i++) {
    const markup = frameAt.get(steps[i].x);
    if (!markup) throw new Error(`svg-term frame at x=${steps[i].x} not found`);
    states.push({
      start: (steps[i].at / 100) * total,
      end: (steps[i + 1].at / 100) * total,
      markup: markup.replace(/^<svg(?: x="\d+")?>/, '<svg>'),
    });
  }
  const stripped = svg.replace(keyframes.css, '');
  return { total, states, compose: (markup) => stripped.replace(reel[0], () => `<g>${markup}</g>`) };
}
