// Where a fade belongs on svg-term's timeline, shared by the SVG stabiliser and the raster timeline.
//
// The cast marks a scene change (the screen clear) at `at` seconds, but svg-term rounds its own
// keyframe times, so its state boundary lands a few milliseconds before or after the marker
// (7.010 s vs 7.012 s in a real scene). Both renderers must pick the same boundary, or one of
// them fades from a state that is already cleared and the "fade" is a cut.

/** Largest gap between a cast marker and svg-term's matching keyframe (seconds). */
export const FADE_TOLERANCE = 0.02;

/**
 * Index of the state that starts the faded-in scene: the first state boundary at or after
 * `at - FADE_TOLERANCE`. The outgoing state is the one before it. Returns -1 when there is none
 * (a fade at time 0, or past the last state).
 * @param {number[]} starts  state start times in seconds, ascending
 */
export function fadeBoundary(starts, at) {
  const idx = starts.findIndex((s) => s >= at - FADE_TOLERANCE);
  return idx > 0 ? idx : -1;
}
