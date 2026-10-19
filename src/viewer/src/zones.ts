// Momentum zone files (the grammar is in src/shared/sh_zones.qc): extruded
// polygons, one in ten of them concave (sh_zones.qc's point-in-zone note).
// segments[k].checkpoints[0] is stage k's start zone, the rest are checkpoints,
// zones.end the finish; tracks.main is the run, tracks.bonuses[] the bonuses.
import { Fit, FL_DUCKED, Rec } from './rec.js';

export type ZoneKind = 'start' | 'stage' | 'checkpoint' | 'end';

export interface Region {
    pts: number[];      // x, y, x, y, ...
    bottom: number;
    top: number;
    convex: boolean;
    minX: number; minY: number; maxX: number; maxY: number;
}

export interface Zone {
    kind: ZoneKind;
    seg: number;        // 0-based segment
    cp: number;         // the game's checkpoint number (Zone_AddTrack's cpn), 0 if not a checkpoint
    regions: Region[];
}

// sh_zones.qc ZT_MINS '-16 -16 0', ZT_STAND_MAXS '16 16 62', ZT_DUCK_MAXS '16 16 45'.
const HULL_HALF = 16, HULL_STAND = 62, HULL_DUCK = 45;
const SWEEP_STEP = 8;   // units between the points tested along one tick's travel

function regions(list: any): Region[] {
    const out: Region[] = [];
    for (const r of Array.isArray(list) ? list : []) {
        const pts: number[] = [];
        for (const p of Array.isArray(r?.points) ? r.points : [])
            if (Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1])) pts.push(p[0], p[1]);
        const bottom = Number(r?.bottom), height = Number(r?.height);
        if (pts.length < 6 || !Number.isFinite(bottom) || !Number.isFinite(height)) continue;
        const n = pts.length / 2;
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity, pos = false, neg = false;
        for (let i = 0; i < n; i++) {
            const x = pts[i * 2], y = pts[i * 2 + 1];
            minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
            const j = (i + 1) % n, k = (i + 2) % n;
            const c = (pts[j * 2] - x) * (pts[k * 2 + 1] - pts[j * 2 + 1]) - (pts[j * 2 + 1] - y) * (pts[k * 2] - pts[j * 2]);
            if (c > 0) pos = true; else if (c < 0) neg = true;
        }
        out.push({ pts, bottom, top: bottom + height, convex: !(pos && neg), minX, minY, maxX, maxY });
    }
    return out;
}

export function parseZones(json: any, track: number): Zone[] {
    const t = track > 0 ? json?.tracks?.bonuses?.[track - 1] : json?.tracks?.main;
    const zones: Zone[] = [];
    const segs = t?.zones?.segments;
    let cpn = 0;
    if (Array.isArray(segs)) {
        segs.forEach((s: any, seg: number) => {
            (Array.isArray(s?.checkpoints) ? s.checkpoints : []).forEach((c: any, ci: number) => {
                if (ci > 0) cpn++;      // every region of one checkpoint shares its number
                const r = regions(c?.regions);
                if (r.length === 0) return;
                zones.push({ kind: ci > 0 ? 'checkpoint' : seg === 0 ? 'start' : 'stage', seg, cp: ci > 0 ? cpn : 0, regions: r });
            });
        });
    }
    const end = regions(t?.zones?.end?.regions);
    if (end.length > 0) zones.push({ kind: 'end', seg: -1, cp: 0, regions: end });
    return zones;
}

// PNPOLY, x/y only (sh_zones.qc Zone_XYInRing).
export function inRing(r: Region, x: number, y: number): boolean {
    const p = r.pts, n = p.length / 2;
    let inside = false;
    for (let i = 0, j = n - 1; i < n; j = i++) {
        const yi = p[i * 2 + 1], yj = p[j * 2 + 1];
        if ((yi > y) !== (yj > y) && x < (p[j * 2] - p[i * 2]) * (y - yi) / (yj - yi) + p[i * 2]) inside = !inside;
    }
    return inside;
}

function crosses(ax: number, ay: number, bx: number, by: number, cx: number, cy: number, dx: number, dy: number): boolean {
    const d1 = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax), d2 = (bx - ax) * (dy - ay) - (by - ay) * (dx - ax);
    const d3 = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx), d4 = (dx - cx) * (by - cy) - (dy - cy) * (bx - cx);
    return d1 * d2 < 0 && d3 * d4 < 0;
}

// Whether the hull with its feet at (x, y, z) overlaps the region, as
// Zone_BoxInside: the Z slab, the bounds, the centre in the ring, then the
// hull's rect against the ring (corners either way, then edges).
export function touches(r: Region, x: number, y: number, z: number, h: number): boolean {
    if (z < r.bottom - h || z > r.top) return false;
    const x0 = x - HULL_HALF, x1 = x + HULL_HALF, y0 = y - HULL_HALF, y1 = y + HULL_HALF;
    if (x1 < r.minX || x0 > r.maxX || y1 < r.minY || y0 > r.maxY) return false;
    if (inRing(r, x, y)) return true;
    const p = r.pts, n = p.length / 2;
    for (let i = 0; i < n; i++)
        if (p[i * 2] >= x0 && p[i * 2] <= x1 && p[i * 2 + 1] >= y0 && p[i * 2 + 1] <= y1) return true;
    if (inRing(r, x0, y0) || inRing(r, x1, y0) || inRing(r, x1, y1) || inRing(r, x0, y1)) return true;
    const rect = [x0, y0, x1, y0, x1, y1, x0, y1];
    for (let i = 0; i < n; i++) {
        const j = (i + 1) % n;
        for (let k = 0; k < 4; k++) {
            const l = (k + 1) % 4;
            if (crosses(p[i * 2], p[i * 2 + 1], p[j * 2], p[j * 2 + 1], rect[k * 2], rect[k * 2 + 1], rect[l * 2], rect[l * 2 + 1])) return true;
        }
    }
    return false;
}

function zoneTouches(zone: Zone, x: number, y: number, z: number, h: number): boolean {
    return zone.regions.some((r) => touches(r, x, y, z, h));
}

// The first sample index at or after `from` whose tick touched the zone: the
// sample itself, or the travel from the one before it (not across a teleport).
function firstTouch(rec: Rec, zone: Zone, from: number): number {
    for (let i = from; i < rec.n; i++) {
        if (rec.t[i] < 0) continue;
        if (rec.end !== null && rec.t[i] > rec.end) break;
        const h = rec.fl[i] & FL_DUCKED ? HULL_DUCK : HULL_STAND;
        const x = rec.o[i * 3], y = rec.o[i * 3 + 1], z = rec.o[i * 3 + 2];
        if (zoneTouches(zone, x, y, z, h)) return i;
        if (i === 0 || rec.t[i - 1] < 0 || rec.fit[i - 1] === Fit.Snap) continue;
        const px = rec.o[i * 3 - 3], py = rec.o[i * 3 - 2], pz = rec.o[i * 3 - 1];
        const steps = Math.ceil(Math.hypot(x - px, y - py, z - pz) / SWEEP_STEP);
        for (let s = 1; s < steps; s++) {
            const f = s / steps;
            if (zoneTouches(zone, px + (x - px) * f, py + (y - py) * f, pz + (z - pz) * f, h)) return i;
        }
    }
    return -1;
}

// When the run first entered each stage's start zone, in order, from its own
// samples: the splits of a run that recorded none (Momentum and KSF imports).
// Entering stage k's zone ends stage k (1-based), as a native `split k` does. A
// stage never touched is skipped, and the next is still searched.
export function inferSplits(rec: Rec, zones: Zone[]): { seg: number; t: number }[] {
    const stages = zones.filter((z) => z.kind === 'stage').sort((a, b) => a.seg - b.seg);
    const out: { seg: number; t: number }[] = [];
    let from = 0;
    for (const st of stages) {
        const i = firstTouch(rec, st, from);
        if (i < 0) continue;
        out.push({ seg: st.seg, t: rec.t[i] });
        from = i;
    }
    return out;
}
