// P1447: runs the viewer's own BSPFile parser over a map folder, one JSON line per map.
//   node tools/bspcensus.mjs <maps dir> <out.jsonl> [maxMB] [name filter]
// Parse only (no renderer: that needs WebGL). Stops if free memory drops under 1.2 GB.
import './census-shim.js';
import '../vendor/noclip/src/SourceEngine/Main.js';    // load order: see AGENT_NOTES 'Import order is load-bearing'
import { closeSync, openSync, readFileSync, readSync, readdirSync, statSync, writeFileSync, appendFileSync } from 'node:fs';
import { freemem } from 'node:os';
import path from 'node:path';
import ArrayBufferSlice from '../vendor/noclip/src/ArrayBufferSlice.js';
import { BSPFile } from '../vendor/noclip/src/SourceEngine/BSPFile.js';

const [dir, out, maxArg, filter] = process.argv.slice(2);
const maxBytes = (maxArg ? Number(maxArg) : 120) * 1048576;
const only = filter && filter.endsWith('.txt') ? new Set(readFileSync(filter, 'utf8').split(/\s+/).filter(Boolean)) : null;
const names = readdirSync(dir).filter((n) => n.toLowerCase().endsWith('.bsp') &&
    (only ? only.has(n.slice(0, -4)) : !filter || n.includes(filter))).sort();
writeFileSync(out, '');

function frame(e: unknown): string {
    const st = e instanceof Error && e.stack ? e.stack.split('\n').slice(1) : [];
    const f = st.find((l) => (l.includes('vendor') || l.includes('stubs')) && !l.includes('util.ts')) ?? st[0] ?? '';
    const m = f.match(/(vendor[\\/].*|stubs[\\/].*)$/);
    return (m ? m[1] : f.trim()).replace(/\\/g, '/').replace(/\)$/, '');
}

for (const n of names) {
    const p = path.join(dir, n);
    const size = statSync(p).size;
    const hdr = Buffer.alloc(8);
    const fd = openSync(p, 'r');
    readSync(fd, hdr, 0, 8, 0);
    closeSync(fd);
    const row: Record<string, unknown> = { map: n.slice(0, -4), mb: +(size / 1048576).toFixed(1), ident: hdr.toString('latin1', 0, 4), version: hdr.readUInt32LE(4) };
    if (size > maxBytes) {
        row.result = 'skipped-large';
    } else if (freemem() < 1.2 * 1073741824) {
        row.result = 'stopped-lowmem';
        appendFileSync(out, JSON.stringify(row) + '\n');
        break;
    } else {
        const buf = readFileSync(p);
        const t0 = performance.now();
        try {
            new BSPFile(new ArrayBufferSlice(buf.buffer, buf.byteOffset, buf.byteLength), row.map as string);
            row.result = 'ok';
        } catch (e) {
            row.result = 'fail';
            row.error = String(e instanceof Error ? e.message : e).slice(0, 160);
            row.at = frame(e);
            row.stack = (e instanceof Error && e.stack ? e.stack.split('\n').slice(1, 7)
                .map((l) => l.trim().replace(/^.*[\\/](vendor|stubs|src)[\\/]/, '$1/')).join(' < ') : '');
        }
        row.ms = Math.round(performance.now() - t0);
    }
    appendFileSync(out, JSON.stringify(row) + '\n');
}
