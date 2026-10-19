// Stand-ins for the Valve content a map names but nobody provided: a material
// that is not there becomes a flat, muted colour picked from its name, lit by
// the map's own lightmaps -- so walls, ramps and floors stay apart without one
// pixel of the texture. Tool materials become hidden, normal maps flat.
import ArrayBufferSlice from '../vendor/noclip/src/ArrayBufferSlice.js';

export const MISSING_DIR = 'materials/__missing/';

function hash(s: string): number {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++)
        h = Math.imul(h ^ s.charCodeAt(i), 16777619);
    return h >>> 0;
}

// A 4x4 RGBA8888 VTF 7.2, the layout VTF.ts reads: image data at 0x50, no low-res image.
function vtf(r: number, g: number, b: number): ArrayBufferSlice {
    const buf = new ArrayBuffer(0x50 + 64);
    const v = new DataView(buf);
    [0x56, 0x54, 0x46, 0].forEach((c, i) => v.setUint8(i, c));
    v.setUint32(0x04, 7, true);
    v.setUint32(0x08, 2, true);
    v.setUint32(0x0C, 0x50, true);
    v.setUint16(0x10, 4, true);
    v.setUint16(0x12, 4, true);
    v.setUint16(0x18, 1, true);             // frames
    v.setFloat32(0x20, 0.5, true); v.setFloat32(0x24, 0.5, true); v.setFloat32(0x28, 0.5, true);
    v.setFloat32(0x30, 1, true);
    v.setUint32(0x34, 0, true);             // RGBA8888
    v.setUint8(0x38, 1);                    // one mip level
    v.setUint32(0x39, 0xFFFFFFFF, true);    // no low-res image
    v.setUint16(0x41, 1, true);             // depth
    for (let i = 0; i < 16; i++) {
        v.setUint8(0x50 + i * 4, r); v.setUint8(0x51 + i * 4, g); v.setUint8(0x52 + i * 4, b); v.setUint8(0x53 + i * 4, 255);
    }
    return new ArrayBufferSlice(buf);
}

function hsl(h: number, s: number, l: number): [number, number, number] {
    const f = (n: number) => {
        const k = (n + h / 30) % 12;
        return Math.round(255 * (l - s * Math.min(l, 1 - l) * Math.max(-1, Math.min(k - 3, 9 - k, 1))));
    };
    return [f(0), f(8), f(4)];
}

const textures = new Map<string, ArrayBufferSlice>();

export function missingTexture(path: string): ArrayBufferSlice {
    let t = textures.get(path);
    if (t !== undefined) return t;
    const name = path.slice(path.lastIndexOf('/') + 1);
    if (/(_normal|_nrm|_bump|_n|_ssbump|normal)\.vtf$/.test(name))
        t = vtf(128, 128, 255);
    else if (path.startsWith('materials/detail/') || /_detail\.vtf$/.test(name))
        t = vtf(128, 128, 128);
    else {
        const h = hash(path);
        t = vtf(...hsl(200 + (h % 60) - 30, 0.10 + ((h >>> 8) % 10) / 100, 0.44 + ((h >>> 16) % 22) / 100));
    }
    textures.set(path, t);
    return t;
}

export function missingMaterial(path: string): ArrayBufferSlice {
    // VMT.ts asks for materials/materials/<path> after missing <path>.
    if (path.startsWith('materials/materials/'))
        path = path.slice('materials/'.length);
    let text: string;
    if (path.startsWith('materials/tools/'))
        text = '"LightmappedGeneric" { "%compiletrigger" "1" }';
    else {
        const shader = path.startsWith('materials/models/') ? 'VertexLitGeneric' : 'LightmappedGeneric';
        text = `"${shader}" { "$basetexture" "${MISSING_DIR.slice('materials/'.length)}${path.slice('materials/'.length, -4)}" }`;
    }
    return new ArrayBufferSlice(new TextEncoder().encode(text).buffer as ArrayBuffer);
}
