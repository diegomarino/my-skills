// Give a TTF a `name` table. @fontsource files ship without one, and rasterisers (resvg)
// choose a font by family name: without names every embedded font is anonymous and they
// all collapse onto the same face. Browsers do not care (they use @font-face).

const checksum = (buf) => {
  let sum = 0;
  const padded = Buffer.concat([buf, Buffer.alloc((4 - (buf.length % 4)) % 4)]);
  for (let i = 0; i < padded.length; i += 4) sum = (sum + padded.readUInt32BE(i)) >>> 0;
  return sum;
};

function nameTable(family, subfamily) {
  const records = [[1, family], [2, subfamily], [4, `${family} ${subfamily}`], [6, `${family}-${subfamily}`.replace(/\s+/g, '')]];
  const strings = records.map(([, text]) => Buffer.from(text, 'utf16le').swap16());
  const head = Buffer.alloc(6 + records.length * 12);
  head.writeUInt16BE(0, 0);
  head.writeUInt16BE(records.length, 2);
  head.writeUInt16BE(head.length, 4);
  let offset = 0;
  records.forEach(([id], i) => {
    const at = 6 + i * 12;
    head.writeUInt16BE(3, at); // Windows
    head.writeUInt16BE(1, at + 2); // Unicode BMP
    head.writeUInt16BE(0x409, at + 4); // en-US
    head.writeUInt16BE(id, at + 6);
    head.writeUInt16BE(strings[i].length, at + 8);
    head.writeUInt16BE(offset, at + 10);
    offset += strings[i].length;
  });
  return Buffer.concat([head, ...strings]);
}

export function withNames(sfnt, family, subfamily) {
  const count = sfnt.readUInt16BE(4);
  const tables = [];
  for (let i = 0; i < count; i++) {
    const at = 12 + i * 16;
    const tag = sfnt.toString('latin1', at, at + 4);
    const offset = sfnt.readUInt32BE(at + 8);
    const length = sfnt.readUInt32BE(at + 12);
    if (tag !== 'name') tables.push({ tag, data: sfnt.subarray(offset, offset + length) });
  }
  tables.push({ tag: 'name', data: nameTable(family, subfamily) });
  tables.sort((a, b) => (a.tag < b.tag ? -1 : 1));
  const dirEnd = 12 + tables.length * 16;
  const header = Buffer.alloc(dirEnd);
  sfnt.copy(header, 0, 0, 4);
  header.writeUInt16BE(tables.length, 4);
  let pow = 1;
  while (pow * 2 <= tables.length) pow *= 2;
  header.writeUInt16BE(pow * 16, 6);
  header.writeUInt16BE(Math.log2(pow), 8);
  header.writeUInt16BE(tables.length * 16 - pow * 16, 10);
  const bodies = [];
  let offset = dirEnd;
  tables.forEach((t, i) => {
    const at = 12 + i * 16;
    header.write(t.tag, at, 'latin1');
    header.writeUInt32BE(checksum(t.data), at + 4);
    header.writeUInt32BE(offset, at + 8);
    header.writeUInt32BE(t.data.length, at + 12);
    const padded = Buffer.concat([t.data, Buffer.alloc((4 - (t.data.length % 4)) % 4)]);
    bodies.push(padded);
    offset += padded.length;
  });
  return Buffer.concat([header, ...bodies]);
}
