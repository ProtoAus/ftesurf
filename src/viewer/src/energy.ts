// Energy as the game's HUD reads it (sh_strafe.qc Strafe_Energy): E = z + |v|^2/2g,
// a height, measured from a zero. The zero is cl_hud.qc's hud_energy_ref: 1 (the
// game's default) the ground under the last jump, which before the first jump
// follows the ground, so standing reads 0; 0 the floor of the start zone.
import { FL_ONGROUND, Rec } from './rec.js';

export const GRAVITY = 800;   // sv_gravity on our lobbies, Momentum and KSF

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

// The last-jump zero at each sample, or null for a recording with no ground
// flag at all (some imports): then only the start can be the zero.
export function jumpRefs(r: Rec): Float32Array | null {
    let any = false;
    for (let i = 0; i < r.n && !any; i++) any = (r.fl[i] & FL_ONGROUND) !== 0;
    if (!any) return null;
    const out = new Float32Array(r.n);
    let ground = r.o[2], ref = r.o[2], jumped = false, was = false;
    for (let i = 0; i < r.n; i++) {
        const z = r.o[i * 3 + 2], on = (r.fl[i] & FL_ONGROUND) !== 0;
        if (on) {
            ground = z;
            if (!jumped) ref = z;
        } else if (was && r.v[i * 3 + 2] > 0) {
            ref = ground;                   // only a jump moves the zero; a ledge does not
            jumped = true;
        }
        was = on;
        out[i] = ref;
    }
    return out;
}

// The start's zero: the start zone's floor when the map has one, else where the
// run stood when its clock started.
export function startRef(r: Rec, startFloor: number | null): number {
    if (startFloor !== null) return startFloor;
    for (let i = 0; i < r.n; i++)
        if (r.t[i] >= 0) return r.o[i * 3 + 2];
    return r.o[2];
}
