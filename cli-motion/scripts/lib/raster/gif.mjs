// Pure-JS GIF (gifenc): ONE global palette for the whole animation, nearest-colour mapping
// with no dithering. A shared palette plus no error diffusion means a pixel that does not
// change between frames keeps the same index in every frame, so text cannot shimmer.

import { dep } from '../deps.mjs';

/** Palette from the colours of all frames: exact when they fit in 256, else median cut. */
export function globalPalette(histogram) {
  const { quantize } = dep('gifenc');
  if (histogram.size <= 256) {
    const palette = [...histogram.keys()].sort((a, b) => histogram.get(b) - histogram.get(a))
      .map((rgb) => [(rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255]);
    return { palette, exact: true };
  }
  // gifenc builds its own histogram from pixels: weight each colour by log2(count) repeats
  let total = 0;
  const reps = new Map();
  for (const [rgb, count] of histogram) {
    const r = 1 + Math.floor(Math.log2(count));
    reps.set(rgb, r);
    total += r;
  }
  const data = new Uint8Array(total * 4);
  let o = 0;
  for (const [rgb, r] of reps) {
    for (let i = 0; i < r; i++) {
      data[o++] = (rgb >> 16) & 255; data[o++] = (rgb >> 8) & 255; data[o++] = rgb & 255; data[o++] = 255;
    }
  }
  return { palette: quantize(data, 256, { format: 'rgb444' }), exact: false };
}

export function addHistogram(histogram, rgba) {
  for (let i = 0; i < rgba.length; i += 4) {
    const key = (rgba[i] << 16) | (rgba[i + 1] << 8) | rgba[i + 2];
    histogram.set(key, (histogram.get(key) ?? 0) + 1);
  }
}

/** frames: async iterable of { rgba, width, height, delayMs }. Returns the GIF bytes. */
export async function encodeGif(frames, palette, { loop = true } = {}) {
  const { GIFEncoder, nearestColorIndex } = dep('gifenc');
  const full = palette.slice(0, 256);
  while (full.length < 256) full.push([0, 0, 0]);
  const exact = new Map(palette.map((c, i) => [(c[0] << 16) | (c[1] << 8) | c[2], i]));
  const enc = GIFEncoder();
  const near = new Map();
  let first = true;
  for await (const f of frames) {
    const index = new Uint8Array(f.width * f.height);
    for (let i = 0, p = 0; i < index.length; i++, p += 4) {
      const key = (f.rgba[p] << 16) | (f.rgba[p + 1] << 8) | f.rgba[p + 2];
      let idx = exact.get(key);
      if (idx === undefined) {
        idx = near.get(key);
        if (idx === undefined) {
          idx = nearestColorIndex(full, [f.rgba[p], f.rgba[p + 1], f.rgba[p + 2]]);
          near.set(key, idx);
        }
      }
      index[i] = idx;
    }
    // the palette goes on the first frame only: it becomes the global colour table
    enc.writeFrame(index, f.width, f.height, {
      delay: f.delayMs, repeat: loop ? 0 : -1, ...(first ? { palette: full } : {}),
    });
    first = false;
  }
  enc.finish();
  return Buffer.from(enc.bytes());
}

/**
 * Rewrite the per-frame delays (centiseconds) of an existing GIF in place. ffmpeg's GIF muxer
 * snaps frame times to its own time base (25 fps by default) and can drop frames closer than
 * that; so ffmpeg only does the palette and the colour mapping (every frame at a uniform
 * 1 s), and the exact durations are written here.
 */
export function patchGifDelays(buf, delaysCs) {
  const out = Buffer.from(buf);
  let p = 13;
  if (out[10] & 0x80) p += 3 * (1 << ((out[10] & 7) + 1));
  const skipSub = () => { while (out[p] !== 0) p += out[p] + 1; p++; };
  let frame = 0;
  let surplus = -1;
  while (p < out.length && out[p] !== 0x3b) {
    if (out[p] === 0x21) {
      if (out[p + 1] === 0xf9) {
        // the concat demuxer's repeated last entry can add one surplus frame: cut that one off
        if (frame === delaysCs.length) { surplus = p; frame++; p += 2; skipSub(); continue; }
        if (frame > delaysCs.length) throw new Error('GIF has more frames than delays');
        out.writeUInt16LE(delaysCs[frame++], p + 4);
      }
      p += 2;
      skipSub();
    } else if (out[p] === 0x2c) {
      const flags = out[p + 9];
      p += 10;
      if (flags & 0x80) p += 3 * (1 << ((flags & 7) + 1));
      p++;
      skipSub();
    } else throw new Error('unexpected GIF block');
  }
  if (frame === delaysCs.length + 1 && surplus >= 0) return Buffer.concat([out.subarray(0, surplus), Buffer.from([0x3b])]);
  if (frame !== delaysCs.length) throw new Error(`GIF has ${frame} frames but ${delaysCs.length} delays`);
  return out;
}
