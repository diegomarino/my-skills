// What the machine can encode. Needs nothing from the dependency cache.

import { spawnSync } from 'node:child_process';

let cached;

/** { ffmpeg: version line | null, libx264: bool } */
export function ffmpegInfo() {
  if (cached) return cached;
  const v = spawnSync('ffmpeg', ['-version'], { encoding: 'utf8' });
  if (v.error || v.status !== 0) return (cached = { ffmpeg: null, libx264: false });
  const enc = spawnSync('ffmpeg', ['-hide_banner', '-encoders'], { encoding: 'utf8' });
  return (cached = { ffmpeg: v.stdout.split('\n')[0], libx264: /\blibx264\b/.test(enc.stdout ?? '') });
}

export function runFfmpeg(args) {
  const res = spawnSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...args], { encoding: 'utf8', maxBuffer: 64 << 20 });
  if (res.error || res.status !== 0) {
    return { ok: false, detail: (res.stderr || res.error?.message || '').trim() };
  }
  return { ok: true };
}
