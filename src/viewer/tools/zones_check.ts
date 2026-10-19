// Zone-inferred splits against native runs' own `split` records:
//   npx esbuild tools/zones_check.ts --bundle --platform=node --outfile=<tmp>.cjs
//   node <tmp>.cjs RUN.rec ZONES.json [RUN.rec ZONES.json ...]
// A recorded split is the LAST start of that stage: a `restart`/`retry`/`resume`
// at the split's own time means the run went back, and inference (first entry,
// right for imports, which never restart a stage) is not expected to match it.
// Every other split must be inferred within 0.05 s; exit 1 if one is not.
import { readFileSync } from 'node:fs';
import { parseRec } from '../src/rec.js';
import { inferSplits, parseZones } from '../src/zones.js';

let match = 0, restarted = 0, bad = 0;
const args = process.argv.slice(2);
for (let a = 0; a < args.length; a += 2) {
    const rec = parseRec(readFileSync(args[a], 'utf8'));
    const zones = parseZones(JSON.parse(readFileSync(args[a + 1], 'utf8')), Number(rec.head.get('track') ?? 0));
    const inferred = new Map(inferSplits(rec, zones).map((s) => [s.seg, s.t]));
    for (const s of rec.splits) {
        const back = rec.events.some((e) => (e.kind === 'restart' || e.kind === 'retry' || e.kind === 'resume') && Math.abs(e.t - s.t) < 0.02);
        const t = inferred.get(s.seg);
        if (back) { restarted++; continue; }
        if (t !== undefined && Math.abs(t - s.t) <= 0.05) { match++; continue; }
        bad++;
        console.log(`MISS ${args[a]} split ${s.seg}: recorded ${s.t.toFixed(3)} inferred ${t === undefined ? '-' : t.toFixed(3)}`);
    }
}
console.log(`${match} matched within 0.05 s, ${restarted} at a restart (not compared), ${bad} not matched`);
process.exit(bad === 0 && match > 0 ? 0 : 1);
