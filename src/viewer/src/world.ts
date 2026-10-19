// What the viewer draws into the 3D scene, through noclip's DebugDraw on the main
// view's colour and depth (the onWorldPasses hook, tools/vendor.py PATCHES). In
// Source coordinates. Everything uses DebugDraw's depth tint: drawn through walls,
// but at 15% where the map is in front, so it reads as behind them.
import { vec3 } from 'gl-matrix';
import { Color } from '../vendor/noclip/src/Color.js';
import { DebugDraw } from '../vendor/noclip/src/gfx/helpers/DebugDraw.js';
import { Fit, FL_DUCKED, Rec } from './rec.js';
import { Pose, sampleAt } from './playback.js';
import { Region, Zone, ZoneKind } from './zones.js';

const LINE_BEHIND = 2, LINE_AHEAD = 8;   // seconds of run line around the playhead
const LINE_POINTS = 600;                 // ribbon vertices in that window at most
const LINE_WIDTH = 3;                    // units
const LINE_NEAR = 48;                    // units: closer to the camera than this, not drawn

// mkplayermodel.py's body: a prism over this pentagon, nose on +X, origin at the
// feet, as tall as the hull standing (72) or ducked (54).
const BODY = [[-16, -16], [16, -16], [23.255, 0], [16, 16], [-16, 16]];
const BODY_H = 72, BODY_DUCK_H = 54;
const LIGHT = vec3.normalize(vec3.create(), [0.35, 0.25, 0.9]);

export const ZONE_COLOURS: Record<ZoneKind, Color> = {
    start: { r: 0.25, g: 0.9, b: 0.45, a: 1 },
    stage: { r: 0.95, g: 0.75, b: 0.3, a: 1 },
    checkpoint: { r: 0.35, g: 0.8, b: 1, a: 1 },
    end: { r: 1, g: 0.35, b: 0.35, a: 1 },
};

const a = vec3.create(), b = vec3.create(), c = vec3.create(), d = vec3.create();
const side = vec3.create(), dir = vec3.create(), toCam = vec3.create(), n = vec3.create();

function shade(base: Color, normal: vec3, alpha: number): Color {
    const l = 0.5 + 0.5 * Math.max(0, vec3.dot(normal, LIGHT));
    return { r: base.r * l, g: base.g * l, b: base.b * l, a: alpha };
}

export function speedColour(speed: number, max: number, alpha: number): Color {
    // The page's ramp: slow blue to fast gold (hsl 210 -> 40, 90%, 60%).
    const f = Math.min(1, speed / Math.max(max, 1));
    const h = (210 - f * 170) / 360, s = 0.9, l = 0.6;
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s, p = 2 * l - q;
    const ch = (t: number) => {
        t = (t + 1) % 1;
        return t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p;
    };
    return { r: ch(h + 1 / 3), g: ch(h), b: ch(h - 1 / 3), a: alpha };
}

// The run line around T as a ribbon that faces the camera, broken at every snap
// between two drawn points (a teleport must not streak across the map).
export function drawRunLine(dd: DebugDraw, rec: Rec, T: number, cam: vec3, maxSpeed: number): void {
    if (rec.n < 2) return;
    const lo = sampleAt(rec, T - LINE_BEHIND), hi = sampleAt(rec, T + LINE_AHEAD);
    const stride = Math.max(1, Math.ceil((hi - lo + 1) / LINE_POINTS));
    let prev = -1;
    for (let k = lo; k < hi + stride; k += stride) {
        const i = Math.min(k, hi);
        if (prev >= 0 && i > prev) {
            let snapped = false;
            for (let j = prev; j < i; j++)
                if (rec.fit[j] === Fit.Snap) { snapped = true; break; }
            if (!snapped) {
                vec3.set(a, rec.o[prev * 3], rec.o[prev * 3 + 1], rec.o[prev * 3 + 2] + 2);
                vec3.set(b, rec.o[i * 3], rec.o[i * 3 + 1], rec.o[i * 3 + 2] + 2);
                vec3.sub(dir, b, a);
                vec3.sub(toCam, cam, a);
                vec3.cross(side, dir, toCam);
                // A segment that passes by the camera would fill the screen.
                if (vec3.squaredLength(side) > 1e-6 && vec3.distance(cam, a) > LINE_NEAR && vec3.distance(cam, b) > LINE_NEAR) {
                    vec3.scale(side, vec3.normalize(side, side), LINE_WIDTH / 2);
                    const col = speedColour(Math.hypot(rec.v[i * 3], rec.v[i * 3 + 1]), maxSpeed, rec.t[i] <= T ? 0.45 : 0.95);
                    vec3.add(c, a, side); vec3.sub(a, a, side);
                    vec3.add(d, b, side); vec3.sub(b, b, side);
                    dd.drawTriSolidP(a, c, d, col);
                    dd.drawTriSolidP(a, d, b, col);
                }
            }
        }
        prev = i;
        if (i === hi) break;
    }
}

// The game's player body, turned to the pose's yaw, faces lit from above. Back
// faces are skipped: depth tint does not write depth, so a convex body drawn
// front faces only needs no sorting.
export function drawBody(dd: DebugDraw, pose: Pose, cam: vec3, base: Color): void {
    const h = pose.fl & FL_DUCKED ? BODY_DUCK_H : BODY_H;
    const cy = Math.cos(pose.yaw * Math.PI / 180), sy = Math.sin(pose.yaw * Math.PI / 180);
    const ring = BODY.map(([x, y]) => [pose.x + x * cy - y * sy, pose.y + x * sy + y * cy]);
    const face = (pts: vec3[], normal: vec3) => {
        vec3.sub(toCam, cam, pts[0]);
        if (vec3.dot(normal, toCam) <= 0) return;
        const col = shade(base, normal, 1);
        for (let i = 1; i + 1 < pts.length; i++)
            dd.drawTriSolidP(pts[0], pts[i], pts[i + 1], col);
    };
    const z0 = pose.z, z1 = pose.z + h;
    face(ring.map(([x, y]) => vec3.fromValues(x, y, z1)), vec3.fromValues(0, 0, 1));
    face(ring.slice().reverse().map(([x, y]) => vec3.fromValues(x, y, z0)), vec3.fromValues(0, 0, -1));
    for (let i = 0; i < ring.length; i++) {
        const [x0, y0] = ring[i], [x1, y1] = ring[(i + 1) % ring.length];
        vec3.normalize(n, vec3.set(n, y1 - y0, -(x1 - x0), 0));
        face([vec3.fromValues(x0, y0, z0), vec3.fromValues(x1, y1, z0), vec3.fromValues(x1, y1, z1), vec3.fromValues(x0, y0, z1)],
            vec3.clone(n));
    }
}

function drawRegion(dd: DebugDraw, r: Region, col: Color, cam: vec3): void {
    const p = r.pts, m = p.length / 2;
    // From inside a zone its faces would tint the whole view: outline only.
    const fill = { ...col, a: insidePrism(r, cam) ? 0 : 0.12 };
    for (let i = 0; i < m; i++) {
        const j = (i + 1) % m;
        vec3.set(a, p[i * 2], p[i * 2 + 1], r.bottom); vec3.set(b, p[j * 2], p[j * 2 + 1], r.bottom);
        vec3.set(c, p[j * 2], p[j * 2 + 1], r.top); vec3.set(d, p[i * 2], p[i * 2 + 1], r.top);
        dd.drawLine(a, b, col);
        dd.drawLine(d, c, col);
        dd.drawLine(a, d, col);
        if (fill.a > 0) {
            dd.drawTriSolidP(a, b, c, fill);
            dd.drawTriSolidP(a, c, d, fill);
        }
    }
    if (fill.a === 0) return;
    vec3.set(a, p[0], p[1], r.top);
    for (let i = 1; i + 1 < m; i++) {
        vec3.set(b, p[i * 2], p[i * 2 + 1], r.top); vec3.set(c, p[i * 2 + 2], p[i * 2 + 3], r.top);
        dd.drawTriSolidP(a, b, c, fill);
    }
}

function insidePrism(r: Region, q: vec3): boolean {
    if (q[2] < r.bottom || q[2] > r.top) return false;
    const p = r.pts, m = p.length / 2;
    let inside = false;
    for (let i = 0, j = m - 1; i < m; j = i++) {
        const yi = p[i * 2 + 1], yj = p[j * 2 + 1];
        if ((yi > q[1]) !== (yj > q[1]) && q[0] < (p[j * 2] - p[i * 2]) * (q[1] - yi) / (yj - yi) + p[i * 2])
            inside = !inside;
    }
    return inside;
}

export function drawZones(dd: DebugDraw, zones: Zone[], cam: vec3): void {
    for (const z of zones)
        for (const r of z.regions)
            drawRegion(dd, r, ZONE_COLOURS[z.kind], cam);
}

// Where a zone's label goes: the middle of its first region's top face.
export function zoneLabelPoint(z: Zone, out: vec3): vec3 {
    const p = z.regions[0].pts, m = p.length / 2;
    let x = 0, y = 0;
    for (let i = 0; i < m; i++) { x += p[i * 2]; y += p[i * 2 + 1]; }
    return vec3.set(out, x / m, y / m, z.regions[0].top);
}
