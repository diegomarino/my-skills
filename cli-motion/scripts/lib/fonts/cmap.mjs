// Minimal sfnt `cmap` reader: which code points does a TTF/OTF contain?
// Enough for formats 4 and 12, which cover every Unicode font we embed.

export function sfntCodepoints(buf) {
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const tables = dv.getUint16(4);
  let cmapOffset = -1;
  for (let i = 0; i < tables; i++) {
    const rec = 12 + i * 16;
    const tag = String.fromCharCode(buf[rec], buf[rec + 1], buf[rec + 2], buf[rec + 3]);
    if (tag === 'cmap') cmapOffset = dv.getUint32(rec + 8);
  }
  if (cmapOffset < 0) return new Set();
  const count = dv.getUint16(cmapOffset + 2);
  const out = new Set();
  for (let i = 0; i < count; i++) {
    const sub = cmapOffset + dv.getUint32(cmapOffset + 4 + i * 8 + 4);
    const format = dv.getUint16(sub);
    if (format === 4) {
      const segX2 = dv.getUint16(sub + 6);
      const ends = sub + 14;
      const starts = ends + segX2 + 2;
      const deltas = starts + segX2;
      const ranges = deltas + segX2;
      for (let s = 0; s < segX2 / 2; s++) {
        const end = dv.getUint16(ends + s * 2);
        const start = dv.getUint16(starts + s * 2);
        if (start === 0xffff) continue;
        const delta = dv.getInt16(deltas + s * 2);
        const rangeOffset = dv.getUint16(ranges + s * 2);
        for (let c = start; c <= end; c++) {
          let glyph;
          if (rangeOffset === 0) glyph = (c + delta) & 0xffff;
          else {
            const at = ranges + s * 2 + rangeOffset + (c - start) * 2;
            glyph = dv.getUint16(at);
            if (glyph !== 0) glyph = (glyph + delta) & 0xffff;
          }
          if (glyph !== 0) out.add(c);
        }
      }
    } else if (format === 12) {
      const groups = dv.getUint32(sub + 12);
      for (let g = 0; g < groups; g++) {
        const at = sub + 16 + g * 12;
        const start = dv.getUint32(at);
        const end = dv.getUint32(at + 4);
        const glyph = dv.getUint32(at + 8);
        for (let c = start; c <= end; c++) if (glyph + (c - start) !== 0) out.add(c);
      }
    }
  }
  return out;
}
