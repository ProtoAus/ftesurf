// Momentum zone files (the grammar is in src/shared/sh_zones.qc): extruded
// convex polygons. segments[k].checkpoints[0] is stage k's start zone, the rest
// are checkpoints, zones.end the finish; tracks.main is the run, tracks.bonuses[]
// the bonuses.
import { Rec } from './rec.js';

export type ZoneKind = 'start' | 'stage' | 'checkpoint' | 'end';

export interface Region {
    pts: number[];      // x, y, x, y, ...
    bottom: number;
    top: number;
}

export interface Zone {
    kind: ZoneKind;
    seg: number;        // 0-based segment
    ord: number;        // checkpoint ordinal within the segment
    regions: Region[];
}

const HULL_HALF = 16, HULL_HEIGHT = 72;   // sh_defs.qc PM_HULL_*

function regions(list: any): Region[] {
    const out: Region[] = [];
    for (const r of Array.isArray(list) ? list : []) {
        const pts: number[] = [];
        for (const p of Array.isArray(r?.points) ? r.points : [])
            if (Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1])) pts.push(p[0], p[1]);
        const bottom = Number(r?.bottom), height = Number(r?.height);
        if (pts.length >= 6 && Number.isFinite(bottom) && Number.isFinite(height))
            out.push({ pts, bottom, top: bottom + height });
    }
    return out;
}

export function parseZones(json: any, track: number): Zone[] {
    const t = track > 0 ? json?.tracks?.bonuses?.[track - 1] : json?.tracks?.main;
    const zones: Zone[] = [];
    const segs = t?.zones?.segments;
    if (Array.isArray(segs)) {
        segs.forEach((s: any, seg: number) => {
            (Array.isArray(s?.checkpoints) ? s.checkpoints : []).forEach((c: any, ord: number) => {
                const r = regions(c?.regions);
                if (r.length === 0) return;
                zones.push({ kind: ord > 0 ? 'checkpoint' : seg === 0 ? 'start' : 'stage', seg, ord, regions: r });
            });
        });
    }
    const end = regions(t?.zones?.end?.regions);
    if (end.length > 0) zones.push({ kind: 'end', seg: -1, ord: 0, regions: end });
    return zones;
}

// Whether a standing hull at origin (x, y, z) overlaps the region: the feet-to-head
// span against [bottom, top], and the point within HULL_HALF of the polygon (each
// edge's outward distance, so a convex ring of either winding works).
export function touches(r: Region, x: number, y: number, z: number): boolean {
    if (z > r.top || z + HULL_HEIGHT < r.bottom) return false;
    const p = r.pts, n = p.length / 2;
    let area = 0;
    for (let i = 0; i < n; i++) {
        const j = (i + 1) % n;
        area += p[i * 2] * p[j * 2 + 1] - p[j * 2] * p[i * 2 + 1];
    }
    const s = area > 0 ? 1 : -1;
    for (let i = 0; i < n; i++) {
        const j = (i + 1) % n;
        const ex = p[j * 2] - p[i * 2], ey = p[j * 2 + 1] - p[i * 2 + 1];
        const len = Math.hypot(ex, ey) || 1;
        // Outward normal of a counter-clockwise ring is (ey, -ex).
        const d = ((x - p[i * 2]) * ey - (y - p[i * 2 + 1]) * ex) * s / len;
        if (d > HULL_HALF) return false;
    }
    return true;
}

// When the run first entered each stage's start zone, in order, from its own
// samples: the splits of a run that recorded none (Momentum and KSF imports).
// Entering stage k's zone ends stage k (1-based), as a native `split k` does.
export function inferSplits(rec: Rec, zones: Zone[]): { seg: number; t: number }[] {
    const stages = zones.filter((z) => z.kind === 'stage').sort((a, b) => a.seg - b.seg);
    const out: { seg: number; t: number }[] = [];
    let next = 0;
    for (let i = 0; i < rec.n && next < stages.length; i++) {
        if (rec.t[i] < 0 || (rec.end !== null && rec.t[i] > rec.end)) continue;
        const x = rec.o[i * 3], y = rec.o[i * 3 + 1], z = rec.o[i * 3 + 2];
        if (stages[next].regions.some((r) => touches(r, x, y, z))) {
            out.push({ seg: stages[next].seg, t: rec.t[i] });
            next++;
        }
    }
    return out;
}
