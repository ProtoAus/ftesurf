// The player's state at a run time T: watchtrace.py Sim.frame (Patch 379's
// Watch_Sample) for a recording without its .view, which the public route never has.
import { Fit, FL_DUCKED, Rec } from './rec.js';

const ASNAP = 45;   // degrees: a bigger step between two samples is held, not turned

export interface Pose {
    t: number;
    x: number; y: number; z: number;   // origin (feet)
    eyeZ: number;                      // origin z + eye height
    pitch: number; yaw: number;
    vx: number; vy: number; vz: number;
    fl: number; keys: number;
    i: number;                         // sample at or before T
}

export function wrap(a: number): number {
    return a - Math.floor((a + 180) / 360) * 360;
}

function arc(a: number, b: number): number {
    return wrap(b - a);
}

function smooth(x: number): number {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    return x * x * (3 - 2 * x);
}

function duckFrac(rec: Rec, t: number): number | null {
    for (const d of rec.ducks)
        if (d.ts <= t && t <= d.te)
            return smooth(d.u0 + (t - d.ts) * d.rate);
    return null;
}

// Largest i with rec.t[i] <= T (0 when T is before the first sample).
export function sampleAt(rec: Rec, T: number): number {
    let lo = 0, hi = rec.n - 1;
    if (hi < 0 || T < rec.t[0]) return 0;
    while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (rec.t[mid] <= T) lo = mid; else hi = mid - 1;
    }
    return lo;
}

export function poseAt(rec: Rec, T: number, out: Pose): Pose {
    const a = sampleAt(rec, T), b = a + 1 < rec.n ? a + 1 : -1;
    const o = rec.o, v = rec.v;
    let s = 0, dt = 0;
    if (b >= 0 && rec.t[b] > rec.t[a]) {
        dt = rec.t[b] - rec.t[a];
        s = Math.min(1, Math.max(0, (T - rec.t[a]) / dt));
    }
    const fit = b >= 0 ? rec.fit[a] : Fit.Linear;
    for (let k = 0; k < 3; k++) {
        const pa = o[a * 3 + k], va = v[a * 3 + k];
        let p = pa;
        if (b >= 0 && dt > 0) {
            const pb = o[b * 3 + k], vb = v[b * 3 + k];
            if (fit === Fit.Snap) {
                p = s < 0.5 ? pa + va * (T - rec.t[a]) : pb - vb * (rec.t[b] - T);
            } else if (fit === Fit.Hermite) {
                const s2 = s * s, s3 = s2 * s;
                p = pa * (2 * s3 - 3 * s2 + 1) + va * dt * (s3 - 2 * s2 + s) + pb * (3 * s2 - 2 * s3) + vb * dt * (s3 - s2);
            } else {
                p = pa + (pb - pa) * s;
            }
        }
        if (k === 0) out.x = p; else if (k === 1) out.y = p; else out.z = p;
    }
    // Velocity is shown, not integrated: the bracketing samples' lerp is enough.
    const vb = b >= 0 ? b : a, sv = fit === Fit.Snap ? (s < 0.5 ? 0 : 1) : s;
    out.vx = v[a * 3] + (v[vb * 3] - v[a * 3]) * sv;
    out.vy = v[a * 3 + 1] + (v[vb * 3 + 1] - v[a * 3 + 1]) * sv;
    out.vz = v[a * 3 + 2] + (v[vb * 3 + 2] - v[a * 3 + 2]) * sv;

    const da = rec.fl[a] & FL_DUCKED ? 1 : 0;
    const db = b >= 0 ? (rec.fl[b] & FL_DUCKED ? 1 : 0) : da;
    const fa = duckFrac(rec, rec.t[a]) ?? da;
    const f = duckFrac(rec, T) ?? (fa + (db - fa) * s);
    out.eyeZ = out.z + rec.eye + (rec.duckEye - rec.eye) * f;

    if (b < 0) {
        out.pitch = rec.pit[a]; out.yaw = wrap(rec.yaw[a]);
    } else if (fit === Fit.Snap || Math.abs(arc(rec.pit[a], rec.pit[b])) > ASNAP || Math.abs(arc(rec.yaw[a], rec.yaw[b])) > ASNAP) {
        const h = s < 0.5 ? a : b;
        out.pitch = wrap(rec.pit[h]); out.yaw = wrap(rec.yaw[h]);
    } else {
        out.pitch = wrap(rec.pit[a] + arc(rec.pit[a], rec.pit[b]) * s);
        out.yaw = wrap(rec.yaw[a] + arc(rec.yaw[a], rec.yaw[b]) * s);
    }
    out.t = T;
    out.fl = rec.fl[a];
    out.keys = rec.keys[a];
    out.i = a;
    return out;
}

export function newPose(): Pose {
    return { t: 0, x: 0, y: 0, z: 0, eyeZ: 0, pitch: 0, yaw: 0, vx: 0, vy: 0, vz: 0, fl: 0, keys: 0, i: 0 };
}
