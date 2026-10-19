// FTESURF-REC reader: the grammar is the block above SV_RecOpen in
// src/server/sv_timer.qc; the snap/fit/duck tables follow tools/watchtrace.py's
// scan_rec (itself cl_watch.qc's Watch_ScanRecord/ScanPair) without its float32
// emulation, which only matters to the game's own counters.

export const enum Fit { Snap, Linear, Hermite }

export const FL_ONGROUND = 1, FL_DUCKED = 2, FL_JUMP = 4, FL_RAMP = 16;
// sh_defs.qc FSI_*: the keys column of a sample.
export const KEY_FORWARD = 1, KEY_BACK = 2, KEY_LEFT = 4, KEY_RIGHT = 8, KEY_JUMP = 16, KEY_DUCK = 32;

const DUCK_T = 0.4, UNDUCK_T = 0.2;     // pm_source.c PMSRC_TIME_TO_DUCK / UNDUCK
// `portal` is the server's form of a portal record (recplot.track writes it as a warp kind).
const FORCE_KINDS = new Set(['tele', 'telerel', 'bhop', 'zone', 'portal']);
const NEVER_KINDS = new Set(['speed', 'push', 'lift']);

export type RecEventKind = 'stage' | 'stagestart' | 'cp' | 'restart' | 'retry' | 'resume' | 'warp' | 'ghost' | 'abandon';

export interface RecEvent {
    kind: RecEventKind;
    t: number;          // run seconds
    n: number;          // segment, checkpoint ordinal, slot or ghost state
    what?: string;      // warp kind
}

export interface DuckSlide { ts: number; te: number; u0: number; rate: number; }

export interface Rec {
    ver: number;
    head: Map<string, string>;
    tickrate: number;
    eye: number;
    duckEye: number;
    n: number;
    t: Float64Array;
    o: Float32Array;    // xyz per sample
    v: Float32Array;
    pit: Float32Array;
    yaw: Float32Array;
    fl: Uint8Array;
    keys: Uint16Array;
    fit: Uint8Array;    // Fit from sample i to i+1
    ducks: DuckSlide[];
    events: RecEvent[];
    splits: { seg: number; t: number }[];
    end: number | null; // finish time, seconds
}

function isSample(s: string): boolean {
    const c = s.charCodeAt(0);
    return c === 45 || (c >= 48 && c <= 57);
}

function interpFit(o: Float32Array, v: Float32Array, a: number, b: number, dt: number): Fit {
    let r2 = 0, d2 = 0, va2 = 0, vb2 = 0;
    for (let k = 0; k < 3; k++) {
        const d = o[b * 3 + k] - o[a * 3 + k];
        const e = d - (v[a * 3 + k] + v[b * 3 + k]) * 0.5 * dt;
        r2 += e * e; d2 += d * d;
        va2 += v[a * 3 + k] ** 2; vb2 += v[b * 3 + k] ** 2;
    }
    const r = Math.sqrt(r2);
    if (r > 0.5 * (Math.sqrt(va2) + Math.sqrt(vb2)) * dt + 64)
        return Fit.Snap;
    if (r > 1 + 0.05 * Math.sqrt(d2))
        return Fit.Linear;
    return Fit.Hermite;
}

export function parseRec(text: string): Rec {
    const lines = text.split('\n');
    const head = new Map<string, string>();
    let ver = 0, tickrate = 0, eye = 0, duckEye = 0;
    let i = 0;
    for (; i < lines.length; i++) {
        const s = lines[i].trimEnd();
        if (s === 'begin') { i++; break; }
        const sp = s.indexOf(' ');
        if (sp < 0) continue;
        const k = s.slice(0, sp), val = s.slice(sp + 1).trim();
        if (k === 'FTESURF-REC') ver = parseFloat(val);
        else head.set(k, val);
    }
    tickrate = parseFloat(head.get('movetickrate') ?? head.get('tickrate') ?? '') || 0.015;
    // `eye` is the public route's form of pmpin's two heights; a local file has pmpin.
    const eyeKey = head.get('eye'), pm = head.get('pmpin');
    if (eyeKey !== undefined) {
        [eye, duckEye] = eyeKey.split(/\s+/).map(parseFloat);
    } else if (pm !== undefined) {
        eye = parseFloat(/(?:^| )viewheight=(\S+)/.exec(pm)?.[1] ?? '');
        duckEye = parseFloat(/ duckviewheight=(\S+)/.exec(pm)?.[1] ?? '');
    }
    if (!(eye > 0) || !(duckEye > 0)) { eye = 64; duckEye = 47; }   // default.cfg pm_viewheight / pm_duckviewheight

    const cap = lines.length - i;
    const t = new Float64Array(cap), o = new Float32Array(cap * 3), v = new Float32Array(cap * 3);
    const pit = new Float32Array(cap), yaw = new Float32Array(cap);
    const fl = new Uint8Array(cap), keys = new Uint16Array(cap), fit = new Uint8Array(cap);
    const events: RecEvent[] = [], splits: { seg: number; t: number }[] = [], ducks: DuckSlide[] = [];
    let end: number | null = null;

    let n = 0, frc = false, veto = false, dkreset = false, ride = false;
    let phase = 0, press = 0;
    const tick = (s: string) => parseFloat(s) * tickrate;

    for (; i < lines.length; i++) {
        const s = lines[i];
        if (s.length === 0) continue;
        if (!isSample(s)) {
            const tok = s.trim().split(/\s+/);
            const k = tok[0];
            switch (k) {
            case 'warp': {
                // v9 has a row index before the kind; older files do not.
                let kind = tok[3] ?? '';
                if (isSample(kind) && tok.length >= 5) kind = tok[4];
                if (FORCE_KINDS.has(kind)) frc = true;
                else if (NEVER_KINDS.has(kind)) veto = true;
                events.push({ kind: 'warp', t: n > 0 ? t[n - 1] : 0, n: 0, what: kind });
                break;
            }
            case 'portal': frc = true; break;
            case 'restart': case 'resume':
                frc = true; dkreset = true;
                events.push({ kind: k, t: tick(tok[2]), n: parseInt(tok[1], 10) });
                break;
            case 'retry':
                frc = true; dkreset = true;
                events.push({ kind: 'retry', t: tick(tok[1]), n: 0 });
                break;
            case 'ride':
                veto = true;
                if (tok.length >= 7)
                    ride = tok[3] === 'arm' && (parseFloat(tok[4]) !== 0 || parseFloat(tok[5]) !== 0 || parseFloat(tok[6]) !== 0);
                break;
            case 'stage': case 'stagestart': case 'cp': case 'ghost':
                if (tok.length >= 3) events.push({ kind: k, t: tick(tok[2]), n: parseInt(tok[1], 10) });
                break;
            case 'abandon':
                events.push({ kind: 'abandon', t: tick(tok[1]), n: 0 });
                break;
            case 'end':
                end = tick(tok[1]);
                break;
            case 'split':
                splits.push({ seg: parseInt(tok[1], 10), t: tick(tok[2]) });
                break;
            }
            continue;
        }

        const tok = s.trim().split(/\s+/);
        const g = (j: number) => (j < tok.length ? parseFloat(tok[j]) || 0 : 0);
        t[n] = g(0);
        o[n * 3] = g(1); o[n * 3 + 1] = g(2); o[n * 3 + 2] = g(3);
        v[n * 3] = g(4); v[n * 3 + 1] = g(5); v[n * 3 + 2] = g(6);
        pit[n] = g(7); yaw[n] = g(8); fl[n] = g(9); keys[n] = g(10);

        if (n > 0) {
            const a = n - 1;
            if (ride) veto = true;
            const dt = t[n] - t[a];
            let f = Fit.Linear;
            if (dt > 0) {
                f = interpFit(o, v, a, n, dt);
                if (frc || (f === Fit.Snap && !veto))
                    f = Fit.Snap;
                else if (f === Fit.Snap || (fl[n] & FL_DUCKED) !== (fl[a] & FL_DUCKED))
                    f = Fit.Linear;
            }
            fit[a] = f;

            // The duck-slide machine (PMSrc_Duck at sample resolution).
            const gnd = fl[n] & FL_ONGROUND, h = fl[n] & FL_DUCKED, key = keys[n] & KEY_DUCK;
            const pg = fl[a] & FL_ONGROUND, ph = fl[a] & FL_DUCKED, pkey = keys[a] & KEY_DUCK;
            if (dkreset) {
                phase = 0;
                const last = ducks[ducks.length - 1];
                if (last !== undefined && last.te > t[a]) last.te = t[a];
            } else if (h && !ph) {
                if (phase === 1) {
                    ducks.push({ ts: press, te: pg ? t[n] : t[a], u0: 0, rate: 1 / DUCK_T });
                    phase = 0;
                }
            } else if (ph && !h) {
                if (pg) ducks.push({ ts: t[n] - UNDUCK_T, te: t[n], u0: 1, rate: -1 / UNDUCK_T });
                phase = 0;
            } else if (!h) {
                if (phase === 1 && pkey && !key) {
                    const u0 = Math.min((t[n] - press) / DUCK_T, 1);
                    ducks.push({ ts: press, te: t[n], u0: 0, rate: 1 / DUCK_T });
                    ducks.push({ ts: t[n], te: t[n] + u0 * UNDUCK_T, u0, rate: -1 / UNDUCK_T });
                    phase = 0;
                } else if (phase === 0 && key && !pkey && gnd) {
                    phase = 1;
                    press = t[n];
                }
            }
        }
        frc = veto = dkreset = false;
        n++;
    }

    return {
        ver, head, tickrate, eye, duckEye, n,
        t: t.subarray(0, n), o: o.subarray(0, n * 3), v: v.subarray(0, n * 3),
        pit: pit.subarray(0, n), yaw: yaw.subarray(0, n), fl: fl.subarray(0, n), keys: keys.subarray(0, n),
        fit: fit.subarray(0, n), ducks, events, splits, end,
    };
}
