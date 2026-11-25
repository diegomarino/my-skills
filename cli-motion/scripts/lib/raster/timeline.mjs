// Timeline of raster frames: which stationary state is on screen, with which fade blend and
// which progress-bar position, for how long. Pure data, no rendering.
//
// Times are whole milliseconds so durations add up exactly. A frame is a maximal run in which
// nothing changes; a stationary frame therefore keeps its exact visible interval, however
// long, and is rasterised once.
//
// Breakpoints are the state boundaries plus:
//   - fade samples: a fade of D seconds becomes round(D × fadeFps) blended frames;
//   - progress samples every `progressStep` seconds (MP4: 1/fps, so the bar moves smoothly;
//     GIF: coarser, every extra step costs a frame, see references/export.md).

const toMs = (s) => Math.round(s * 1000);

/**
 * @param {{start:number,end:number}[]} states  stationary states in seconds (contiguous)
 * @param {{at:number,duration:number}[]} fades
 * @returns {{start:number,end:number,state:number,base:number|null,alpha:number|null,progress:number|null}[]}
 */
export function buildTimeline({ states, fades = [], total, fadeFps, progressStep = null }) {
  const totalMs = toMs(total);
  const bounds = states.map((s) => toMs(s.start));
  const stateAt = (ms) => {
    let lo = 0;
    for (let i = 0; i < bounds.length; i++) if (bounds[i] <= ms) lo = i;
    return lo;
  };

  const fadeWindows = fades.map((f) => {
    const start = toMs(f.at);
    const len = Math.max(1, toMs(f.duration));
    const n = Math.max(1, Math.round(f.duration * fadeFps));
    return { start, len, n, base: Math.max(0, stateAt(start - 1)) };
  }).filter((w) => w.start > 0 && w.start < totalMs);

  const points = new Set([0, totalMs, ...bounds.filter((b) => b < totalMs)]);
  for (const w of fadeWindows) {
    for (let k = 0; k <= w.n; k++) points.add(Math.min(totalMs, w.start + Math.round((w.len * k) / w.n)));
  }
  if (progressStep) {
    const step = Math.max(1, toMs(progressStep));
    for (let t = 0; t < totalMs; t += step) points.add(t);
  }
  const sorted = [...points].sort((a, b) => a - b);

  const frames = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    const start = sorted[i];
    const end = sorted[i + 1];
    let base = null;
    let alpha = null;
    for (const w of fadeWindows) {
      if (start >= w.start && start < w.start + w.len) {
        const k = Math.min(w.n - 1, Math.floor(((start - w.start) / w.len) * w.n + 0.5));
        base = w.base;
        alpha = (k + 1) / (w.n + 1);
      }
    }
    const state = stateAt(start);
    if (base === state) { base = null; alpha = null; }
    // The bar sits on its sample grid: the latest sample at or before the frame start.
    let progress = null;
    if (progressStep) {
      const step = Math.max(1, toMs(progressStep));
      progress = (Math.floor(start / step) * step) / totalMs;
    }
    const prev = frames.at(-1);
    if (prev && prev.state === state && prev.base === base && prev.alpha === alpha && prev.progress === progress) {
      prev.end = end;
    } else frames.push({ start, end, state, base, alpha, progress });
  }
  return frames;
}

/**
 * Snap frame durations to a grid of `unit` ms with a running total, so rounding never
 * accumulates (the total stays within one unit of the cast). Frames shorter than `minUnits`
 * of the grid are folded into the previous frame.
 * @returns {{index:number,units:number}[]} index into `frames`, duration in grid units
 */
export function snapDurations(frames, unit, minUnits = 1) {
  const out = [];
  let emitted = 0;
  frames.forEach((f, index) => {
    const endUnits = Math.round(f.end / unit);
    const units = endUnits - emitted;
    if (units < minUnits) {
      // too short to display: its time goes to the frame before it (or the next one at the start)
      if (out.length) { out[out.length - 1].units += units; emitted = endUnits; }
      return;
    }
    out.push({ index, units });
    emitted = endUnits;
  });
  return out;
}
