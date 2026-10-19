// FTESurf stand-in for noclip's rustlib.ts. Upstream loads a Rust/wasm crate
// (naga, polymorph, lzma-rs, ...); the Source renderer needs only the four
// calls below, so they are TypeScript here and the viewer ships no wasm.
// lzma_decompress is a port of LzmaSpec.cpp (LZMA SDK, public domain); the
// output buffer is the dictionary, since BSP lumps and pakfile entries carry
// their unpacked size. tools/lzma_check.mjs compares it with Python's lzma.
import { mat4, vec4 } from 'gl-matrix';
import { unzlibSync, inflateSync } from 'fflate';

const PROB_INIT = 1024;

class RangeDecoder {
    private range = 0xFFFFFFFF;
    private code = 0;
    private pos: number;

    constructor(private src: Uint8Array, start: number) {
        this.pos = start;
        if (src[this.pos++] !== 0)
            throw new Error('lzma: bad range coder header');
        for (let i = 0; i < 4; i++)
            this.code = ((this.code << 8) | this.src[this.pos++]) >>> 0;
        if (this.code === this.range)
            throw new Error('lzma: corrupt stream');
    }

    private normalize(): void {
        if (this.range < 0x1000000) {
            this.range = (this.range << 8) >>> 0;
            // Past the end reads 0, as LzmaSpec's stream does on a truncated input.
            this.code = ((this.code << 8) | (this.src[this.pos++] ?? 0)) >>> 0;
        }
    }

    public bit(probs: Uint16Array, i: number): number {
        const p = probs[i];
        const bound = (this.range >>> 11) * p;
        let b: number;
        if (this.code < bound) {
            this.range = bound;
            probs[i] = p + ((2048 - p) >>> 5);
            b = 0;
        } else {
            this.range -= bound;
            this.code -= bound;
            probs[i] = p - (p >>> 5);
            b = 1;
        }
        this.normalize();
        return b;
    }

    public direct(numBits: number): number {
        let res = 0;
        do {
            this.range >>>= 1;
            this.code = (this.code - this.range) >>> 0;
            const t = (this.code >>> 31) ? -1 : 0;
            this.code = (this.code + (this.range & t)) >>> 0;
            this.normalize();
            res = res * 2 + (t + 1);
        } while (--numBits);
        return res;
    }
}

function bitTree(rc: RangeDecoder, probs: Uint16Array, base: number, numBits: number): number {
    let m = 1;
    for (let i = 0; i < numBits; i++)
        m = (m << 1) + rc.bit(probs, base + m);
    return m - (1 << numBits);
}

function bitTreeReverse(rc: RangeDecoder, probs: Uint16Array, base: number, numBits: number): number {
    let m = 1, sym = 0;
    for (let i = 0; i < numBits; i++) {
        const b = rc.bit(probs, base + m);
        m = (m << 1) + b;
        sym |= b << i;
    }
    return sym;
}

// choice, choice2, low[16][8], mid[16][8], high[256]
const LEN_LOW = 2, LEN_MID = LEN_LOW + 16 * 8, LEN_HIGH = LEN_MID + 16 * 8, LEN_SIZE = LEN_HIGH + 256;

function lenDecode(rc: RangeDecoder, probs: Uint16Array, posState: number): number {
    if (rc.bit(probs, 0) === 0)
        return bitTree(rc, probs, LEN_LOW + posState * 8, 3);
    if (rc.bit(probs, 1) === 0)
        return 8 + bitTree(rc, probs, LEN_MID + posState * 8, 3);
    return 16 + bitTree(rc, probs, LEN_HIGH, 8);
}

function lzma_decompress(src: Uint8Array, lc: number, lp: number, pb: number, _dictSize: number, unpackedSize: bigint): Uint8Array {
    const size = Number(unpackedSize);
    const out = new Uint8Array(size);
    const rc = new RangeDecoder(src, 0);

    const literal = new Uint16Array(0x300 << (lc + lp)).fill(PROB_INIT);
    const isMatch = new Uint16Array(12 << 4).fill(PROB_INIT);
    const isRep = new Uint16Array(12).fill(PROB_INIT);
    const isRepG0 = new Uint16Array(12).fill(PROB_INIT);
    const isRepG1 = new Uint16Array(12).fill(PROB_INIT);
    const isRepG2 = new Uint16Array(12).fill(PROB_INIT);
    const isRep0Long = new Uint16Array(12 << 4).fill(PROB_INIT);
    const posSlot = new Uint16Array(4 << 6).fill(PROB_INIT);
    const posDec = new Uint16Array(1 + 128 - 14).fill(PROB_INIT);
    const align = new Uint16Array(1 << 4).fill(PROB_INIT);
    const lenDec = new Uint16Array(LEN_SIZE).fill(PROB_INIT);
    const repLenDec = new Uint16Array(LEN_SIZE).fill(PROB_INIT);

    const pbMask = (1 << pb) - 1, lpMask = (1 << lp) - 1;
    let state = 0, rep0 = 0, rep1 = 0, rep2 = 0, rep3 = 0;
    let pos = 0;

    while (pos < size) {
        const posState = pos & pbMask;

        if (rc.bit(isMatch, (state << 4) + posState) === 0) {
            const prev = pos > 0 ? out[pos - 1] : 0;
            const base = 0x300 * (((pos & lpMask) << lc) + (prev >>> (8 - lc)));
            let sym = 1;
            if (state >= 7) {
                let matchByte = out[pos - rep0 - 1];
                do {
                    const matchBit = (matchByte >>> 7) & 1;
                    matchByte <<= 1;
                    const b = rc.bit(literal, base + ((1 + matchBit) << 8) + sym);
                    sym = (sym << 1) | b;
                    if (matchBit !== b)
                        break;
                } while (sym < 0x100);
            }
            while (sym < 0x100)
                sym = (sym << 1) | rc.bit(literal, base + sym);
            out[pos++] = sym - 0x100;
            state = state < 4 ? 0 : (state < 10 ? state - 3 : state - 6);
            continue;
        }

        let len: number;
        if (rc.bit(isRep, state) !== 0) {
            if (pos === 0)
                throw new Error('lzma: rep match at start');
            if (rc.bit(isRepG0, state) === 0) {
                if (rc.bit(isRep0Long, (state << 4) + posState) === 0) {
                    state = state < 7 ? 9 : 11;
                    out[pos] = out[pos - rep0 - 1];
                    pos++;
                    continue;
                }
            } else {
                let dist: number;
                if (rc.bit(isRepG1, state) === 0) {
                    dist = rep1;
                } else {
                    if (rc.bit(isRepG2, state) === 0) {
                        dist = rep2;
                    } else {
                        dist = rep3;
                        rep3 = rep2;
                    }
                    rep2 = rep1;
                }
                rep1 = rep0;
                rep0 = dist;
            }
            len = lenDecode(rc, repLenDec, posState);
            state = state < 7 ? 8 : 11;
        } else {
            rep3 = rep2; rep2 = rep1; rep1 = rep0;
            len = lenDecode(rc, lenDec, posState);
            state = state < 7 ? 7 : 10;

            const slot = bitTree(rc, posSlot, (len < 3 ? len : 3) << 6, 6);
            if (slot < 4) {
                rep0 = slot;
            } else {
                const numDirect = (slot >>> 1) - 1;
                let dist = (2 | (slot & 1)) * 2 ** numDirect;
                if (slot < 14) {
                    dist += bitTreeReverse(rc, posDec, dist - slot, numDirect);
                } else {
                    dist += rc.direct(numDirect - 4) * 16;
                    dist += bitTreeReverse(rc, align, 0, 4);
                }
                rep0 = dist;
            }
            if (rep0 === 0xFFFFFFFF)
                break; // end marker
            if (rep0 >= pos)
                throw new Error('lzma: distance past start');
        }

        len += 2;
        const from = pos - rep0 - 1;
        const n = Math.min(len, size - pos);
        for (let i = 0; i < n; i++)
            out[pos + i] = out[from + i];
        pos += n;
    }

    return out;
}

function deflate_decompress(src: Uint8Array): Uint8Array {
    return unzlibSync(src);
}

function deflate_raw_decompress(src: Uint8Array): Uint8Array {
    return inflateSync(src);
}

const enum Intersection { Inside, Outside, Intersection }

// noclip's ConvexHull (rust/src/geometry.rs): planes kept normalized, a point
// is inside when every plane's distance is >= 0.
class ConvexHull {
    private planes: number[] = [];

    public clear(): void { this.planes.length = 0; }
    public free(): void {}

    public copy(): ConvexHull {
        const c = new ConvexHull();
        c.planes = this.planes.slice();
        return c;
    }

    public push_plane(x: number, y: number, z: number, d: number): void {
        const mag = Math.hypot(x, y, z);
        this.planes.push(x / mag, y / mag, z / mag, d / mag);
    }

    public js_intersect_aabb(x0: number, y0: number, z0: number, x1: number, y1: number, z1: number): number {
        let result = Intersection.Inside;
        const p = this.planes;
        for (let i = 0; i < p.length; i += 4) {
            const nx = p[i], ny = p[i + 1], nz = p[i + 2], d = p[i + 3];
            if (nx * (nx >= 0 ? x1 : x0) + ny * (ny >= 0 ? y1 : y0) + nz * (nz >= 0 ? z1 : z0) + d < 0)
                return Intersection.Outside;
            if (nx * (nx > 0 ? x0 : x1) + ny * (ny > 0 ? y0 : y1) + nz * (nz > 0 ? z0 : z1) + d < 0)
                result = Intersection.Intersection;
        }
        return result;
    }

    public js_contains_aabb(x0: number, y0: number, z0: number, x1: number, y1: number, z1: number): boolean {
        const p = this.planes;
        for (let i = 0; i < p.length; i += 4) {
            const nx = p[i], ny = p[i + 1], nz = p[i + 2], d = p[i + 3];
            if (nx * (nx >= 0 ? x1 : x0) + ny * (ny >= 0 ? y1 : y0) + nz * (nz >= 0 ? z1 : z0) + d < 0)
                return false;
        }
        return true;
    }

    public js_contains_sphere(x: number, y: number, z: number, radius: number): boolean {
        const p = this.planes;
        for (let i = 0; i < p.length; i += 4)
            if (p[i] * x + p[i + 1] * y + p[i + 2] * z + p[i + 3] < -radius)
                return false;
        return true;
    }

    public js_contains_point(v: Float32Array): boolean {
        const p = this.planes;
        for (let i = 0; i < p.length; i += 4)
            if (p[i] * v[0] + p[i + 1] * v[1] + p[i + 2] * v[2] + p[i + 3] < 0)
                return false;
        return true;
    }

    public js_transform(m: Float32Array): void {
        const inv = mat4.create();
        mat4.invert(inv, m);
        mat4.transpose(inv, inv);
        const v = vec4.create();
        const p = this.planes;
        for (let i = 0; i < p.length; i += 4) {
            vec4.set(v, p[i], p[i + 1], p[i + 2], p[i + 3]);
            vec4.transformMat4(v, v, inv);
            p[i] = v[0]; p[i + 1] = v[1]; p[i + 2] = v[2]; p[i + 3] = v[3];
        }
    }
}

export type { ConvexHull };

export const rust = { lzma_decompress, deflate_decompress, deflate_raw_decompress, ConvexHull };

export async function loadRustLib(): Promise<void> {}
