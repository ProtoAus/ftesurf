// Energy as the game's HUD reads it (sh_strafe.qc Strafe_Energy): E = z + |v|^2/2g,
// a height, measured from one of cl_hud.qc's two zeros (hud_energy_ref), both
// computed per sample here by the game's own rules.
import { Fit, FL_ONGROUND, Rec } from './rec.js';
import { inRing, Region, Zone, ZoneKind } from './zones.js';

export const GRAVITY = 800;   // sv_gravity on our lobbies, Momentum and KSF
const SEG_JUMPDIST = 512;     // cl_board.qc

// A local .rec carries the server's own in `pmpin`; the board's track does not.
export function gravityOf(r: Rec): number {
    const m = /(?:^|\s)gravity=([\d.]+)/.exec(r.head.get('pmpin') ?? '');
    const g = m ? Number(m[1]) : NaN;
    return g >= 1 ? g : GRAVITY;
}

export function energy(z: number, vx: number, vy: number, vz: number, g: number): number {
    return z + (vx * vx + vy * vy + vz * vz) / (2 * g);
}

// Strafe_EquivSpeed: the energy written back as the speed it is worth.
export function equivSpeed(e: number, g: number): number {
    return Math.sign(e) * Math.sqrt(2 * g * Math.abs(e));
}

// The first region of those kinds the feet are inside, in the file's order
// (Zone_PointInside: the Z slab and PNPOLY).
function inside(zones: Zone[], kinds: ZoneKind[], x: number, y: number, z: number): Region | null {
    for (const zone of zones) {
        if (!kinds.includes(zone.kind)) continue;
        for (const r of zone.regions)
            if (z >= r.bottom && z <= r.top && inRing(r, x, y)) return r;
    }
    return null;
}

export interface Zeros {
    jump: Float32Array | null;   // hud_energy_ref 1; null when the recording has no ground flag
    anchor: Float32Array;        // hud_energy_ref 0; NaN before the feet are in any start or stage zone
}

// HUD_UpdateJumpRef and HUD_UpdateAnchor over the whole recording. The jump
// zero re-bases at a teleport of more than 512 units (the game's test is that
// step in one frame; a thinned track steps that far without one, so the step
// must also be one the recording marks as a teleport), follows the ground until
// a jump, is the floor under you in a start zone while the clock is stopped, and
// is the last ground height when you leave the ground going up. The anchor is
// the floor of the last start or stage zone the feet were in.
export function zeros(r: Rec, zones: Zone[]): Zeros {
    let anyGround = false;
    for (let i = 0; i < r.n && !anyGround; i++) anyGround = (r.fl[i] & FL_ONGROUND) !== 0;
    const anchor = new Float32Array(r.n), jump = anyGround ? new Float32Array(r.n) : null;
    let a = NaN, cur: Region | null = null;
    let have = false, ground = 0, jz = 0, wasOn = false;
    for (let i = 0; i < r.n; i++) {
        const x = r.o[i * 3], y = r.o[i * 3 + 1], z = r.o[i * 3 + 2];
        const hit = inside(zones, ['start', 'stage'], x, y, z);
        if (hit !== null && hit !== cur) { cur = hit; a = hit.bottom; }
        anchor[i] = a;
        if (jump === null) continue;
        if (!have || (i > 0 && r.fit[i - 1] === Fit.Snap && Math.hypot(x - r.o[i * 3 - 3], y - r.o[i * 3 - 2], z - r.o[i * 3 - 1]) > SEG_JUMPDIST)) {
            ground = z; jz = z; have = true;
        }
        if (r.fl[i] & FL_ONGROUND) {
            ground = z;
            wasOn = true;
            const running = r.t[i] >= 0 && (r.end === null || r.t[i] <= r.end);
            if (!running && inside(zones, ['start'], x, y, z) !== null) jz = z;
        } else {
            if (wasOn && r.v[i * 3 + 2] > 0) jz = ground;   // only a jump moves it; a ledge does not
            wasOn = false;
        }
        jump[i] = jz;
    }
    return { jump, anchor };
}

// The zero a whole-run graph is drawn from: the anchor where the clock started,
// or the height there when no zone held it.
export function runZero(r: Rec, zs: Zeros): number {
    for (let i = 0; i < r.n; i++)
        if (r.t[i] >= 0) return Number.isNaN(zs.anchor[i]) ? r.o[i * 3 + 2] : zs.anchor[i];
    return r.o[2];
}
