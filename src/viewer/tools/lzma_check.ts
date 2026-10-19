// The viewer's TypeScript LZMA (stubs/rustlib.ts) against Python's, on a real map:
//   npx esbuild tools/lzma_check.ts --bundle --platform=node --outfile=<tmp>.cjs
//   python tools/lzma_ref.py MAP.bsp > ref.txt && node <tmp>.cjs MAP.bsp ref.txt
// Prints one line per compressed lump and pakfile entry that differs, then a count.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import ArrayBufferSlice from '../vendor/noclip/src/ArrayBufferSlice.js';
import { decodeLZMAProperties, decompress } from '../vendor/noclip/src/Common/Compression/LZMA.js';
import { decompressZipFileEntry, parseZipFile } from '../vendor/noclip/src/ZipFile.js';

const [bspPath, refPath] = process.argv.slice(2);
const file = readFileSync(bspPath);
const buf = new ArrayBufferSlice(file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength) as ArrayBuffer);
const view = buf.createDataView();
const sha = (s: ArrayBufferSlice) => createHash('sha256').update(s.createTypedArray(Uint8Array)).digest('hex');

const got = new Map<string, string>();
let pak: ArrayBufferSlice | null = null;
for (let i = 0; i < 64; i++) {
    const off = view.getInt32(8 + i * 16, true), len = view.getInt32(12 + i * 16, true);
    if (len <= 0) continue;
    const blob = buf.subarray(off, len);
    if (i === 40) pak = blob;
    const b = blob.createDataView();
    if (b.getUint32(0, false) !== 0x4C5A4D41) continue;   // 'LZMA'
    const actual = b.getUint32(4, true);
    const props = decodeLZMAProperties(blob.subarray(12, 5));
    got.set(`lump ${i}`, sha(decompress(blob.slice(17), props, actual)));
}
if (pak !== null)
    for (const e of parseZipFile(pak))
        if (e.compressionMethod !== 0)
            got.set(`pak ${e.filename.toLowerCase().replace(/\\/g, '/')}`, sha(decompressZipFileEntry(e)));

let bad = 0, n = 0;
for (const line of readFileSync(refPath, 'utf8').split('\n')) {
    const m = /^(\S+) (.+) ([0-9a-f]{64})$/.exec(line.trim());
    if (m === null) continue;
    n++;
    const key = `${m[1]} ${m[2]}`;
    if (got.get(key) !== m[3]) { bad++; console.log(`DIFF ${key}: ${got.get(key) ?? 'missing'}`); }
}
console.log(`${n} reference digests, ${bad} differ, ${got.size} decoded here`);
process.exit(bad === 0 && n > 0 ? 0 : 1);
