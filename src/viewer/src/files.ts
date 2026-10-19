// Game files: the BSP and Valve content the page reads from the viewer's own
// disk. Nothing is uploaded; a VPK is read by slices, so a 1.3 GB CS:S set
// costs only the textures the map names.
import ArrayBufferSlice from '../vendor/noclip/src/ArrayBufferSlice.js';
import { DataFetcher, NamedArrayBufferSlice } from '../vendor/noclip/src/DataFetcher.js';
import { LooseMount, SourceFileSystem } from '../vendor/noclip/src/SourceEngine/Main.js';
import { decompressZipFileEntry } from '../vendor/noclip/src/ZipFile.js';
import { MISSING_DIR, missingMaterial, missingTexture } from './missing.js';
import { Store } from './store.js';

export const LOCAL = 'local:';

// A file: a File from the folder the viewer picked, or (on this machine only)
// a range-fetched one from tools/serve.py --steam.
export interface Readable {
    slice(start: number, end: number): { arrayBuffer(): Promise<ArrayBuffer> };
    arrayBuffer(): Promise<ArrayBuffer>;
}

// A file by a path relative to whatever folder the viewer picked.
interface Source {
    file(path: string): Promise<Readable | null>;
    list(dir: string): Promise<string[]>;      // every file under dir/, relative to dir
}

class HttpFile implements Readable {
    constructor(private url: string) {}
    public slice(start: number, end: number) {
        return { arrayBuffer: async () => {
            const r = await fetch(this.url, { headers: { Range: `bytes=${start}-${end - 1}` } });
            if (r.status !== 206 && r.status !== 200) throw new Error(`${this.url}: ${r.status}`);
            return r.arrayBuffer();
        } };
    }
    public async arrayBuffer(): Promise<ArrayBuffer> {
        return (await fetch(this.url)).arrayBuffer();
    }
}

export class HttpSource implements Source {
    constructor(private base: string) {}
    public async file(path: string): Promise<Readable | null> {
        const url = this.base + path.split('/').map(encodeURIComponent).join('/');
        const r = await fetch(url, { method: 'HEAD' });
        return r.ok ? new HttpFile(url) : null;
    }
    public async list(): Promise<string[]> { return []; }
}

class HandleSource implements Source {
    constructor(private root: FileSystemDirectoryHandle) {}

    private async dir(path: string): Promise<FileSystemDirectoryHandle | null> {
        let dir = this.root;
        try {
            for (const p of path.split('/').filter((s) => s !== ''))
                dir = await dir.getDirectoryHandle(p);
            return dir;
        } catch {
            return null;
        }
    }

    public async file(path: string): Promise<Readable | null> {
        const cut = path.lastIndexOf('/');
        const dir = await this.dir(cut < 0 ? '' : path.slice(0, cut));
        try {
            return dir === null ? null : await (await dir.getFileHandle(path.slice(cut + 1))).getFile();
        } catch {
            return null;
        }
    }

    public async list(path: string): Promise<string[]> {
        const out: string[] = [];
        const walk = async (d: FileSystemDirectoryHandle, pre: string) => {
            for await (const [name, h] of (d as any).entries()) {
                if (h.kind === 'directory') await walk(h, `${pre}${name}/`);
                else out.push(pre + name);
            }
        };
        const d = await this.dir(path);
        if (d !== null) await walk(d, '');
        return out;
    }
}

// What a picked folder is kept for: VPKs, the BSPs in a maps folder, the games'
// signature files, and Momentum's loose content. A whole Steam `common` is 300k
// files (96 s for Chrome to list on the PC, 19 Oct) of which ~8,700 are these.
const KEEP = /\.vpk$|(^|\/)maps\/[^/]+\.bsp$|^[^/]+\.bsp$|momentum\.fgd$|(^|momentum\/)(materials|models)\//i;

class ListSource implements Source {
    private byPath = new Map<string, File>();

    constructor(files: FileList) {
        // webkitRelativePath starts with the picked folder's own name; drop it.
        for (let i = 0; i < files.length; i++) {
            const f = files[i];
            const rel = f.webkitRelativePath || f.name;
            const cut = rel.indexOf('/');
            const path = (cut > 0 ? rel.slice(cut + 1) : rel).toLowerCase();
            if (KEEP.test(path)) this.byPath.set(path, f);
        }
    }

    public async file(path: string): Promise<Readable | null> {
        return this.byPath.get(path.toLowerCase()) ?? null;
    }

    public async list(dir: string): Promise<string[]> {
        const pre = dir === '' ? '' : dir.toLowerCase() + '/';
        return [...this.byPath.keys()].filter((p) => p.startsWith(pre)).map((p) => p.slice(pre.length));
    }
}

// Each game from Steam's `common`, its own folder, or its gamedir, known by a
// file only it has. `rank` is mount priority, lowest first: the game's
// fs_addons order (cstrike before hl2), then Momentum's bundled HL2 copy last.
// Momentum keeps its own textures and models loose, not in VPKs.
const GAMES = [
    { name: 'Momentum Mod', dirs: ['Momentum Mod Playtest/momentum', 'momentum', ''], sig: 'momentum.fgd', vpks: [], loose: ['materials', 'models'], maps: true, rank: 0 },
    { name: 'Counter-Strike: Source', dirs: ['Counter-Strike Source/cstrike', 'cstrike', ''], sig: 'cstrike_pak_dir.vpk', vpks: ['cstrike_pak'], loose: [], maps: true, rank: 1 },
    { name: 'Half-Life 2', dirs: ['Half-Life 2/hl2', 'hl2', ''], sig: 'hl2_textures_dir.vpk', vpks: ['hl2_textures', 'hl2_misc', 'hl2_pak'], loose: [], maps: false, rank: 2 },
    { name: 'Momentum Mod (HL2 content)', dirs: ['Momentum Mod Playtest/mount', 'mount', ''], sig: 'hl2_dir.vpk', vpks: ['hl2'], loose: [], maps: false, rank: 3 },
];

export interface Mount {
    game: string;
    rank: number;
    vpks: string[];         // LOCAL path stems of VPK sets
    loose: { base: string; files: string[] } | null;   // LOCAL base and paths under it
    maps: string | null;    // LOCAL directory of BSPs
}

export class GameFiles {
    private sources: Source[] = [];
    public mounts: Mount[] = [];

    public addHandle(root: FileSystemDirectoryHandle): Promise<Mount[]> {
        return this.add(new HandleSource(root));
    }

    public addList(files: FileList): Promise<Mount[]> {
        return this.add(new ListSource(files));
    }

    public async add(src: Source): Promise<Mount[]> {
        const si = this.sources.push(src) - 1;
        const found: Mount[] = [];
        for (const g of GAMES) {
            for (const d of g.dirs) {
                const base = d ? d + '/' : '';
                if (await src.file(base + g.sig) === null)
                    continue;
                const vpks = [];
                for (const v of g.vpks)
                    if (await src.file(`${base}${v}_dir.vpk`) !== null)
                        vpks.push(`${LOCAL}${si}/${base}${v}`);
                const loose: string[] = [];
                for (const l of g.loose)
                    for (const f of await src.list(base + l))
                        loose.push(`${l}/${f}`);
                found.push({ game: g.name, rank: g.rank, vpks, maps: g.maps ? `${LOCAL}${si}/${base}maps` : null,
                    loose: loose.length ? { base: `${LOCAL}${si}${d ? '/' + d : ''}`, files: loose } : null });
                break;
            }
        }
        // No game in it: a folder of BSPs, picked directly.
        if (found.length === 0)
            found.push({ game: 'maps folder', rank: 9, vpks: [], loose: null, maps: `${LOCAL}${si}` });
        this.mounts.push(...found);
        this.mounts.sort((a, b) => a.rank - b.rank);
        return found;
    }

    public async file(localPath: string): Promise<Readable | null> {
        const m = /^local:(\d+)(?:\/(.*))?$/.exec(localPath);
        if (m === null) return null;
        const src = this.sources[Number(m[1])];
        return src === undefined || m[2] === undefined ? null : src.file(m[2]);
    }

    public async findMap(name: string): Promise<Readable | null> {
        for (const m of this.mounts) {
            if (m.maps === null) continue;
            const f = await this.file(`${m.maps}/${name}.bsp`);
            if (f !== null) return f;
        }
        return null;
    }
}

// noclip's fetcher, with `local:` paths answered from GameFiles.
export class Fetcher extends DataFetcher {
    constructor(public files: GameFiles) {
        super(null);
        this.useDevelopmentStorage = false;
    }

    public override async fetchData(path: string, options: { rangeStart?: number | bigint; rangeSize?: number | bigint } = {}): Promise<NamedArrayBufferSlice> {
        if (!path.startsWith(LOCAL))
            return super.fetchData(path, options);
        const f = await this.files.file(path);
        if (f === null)
            throw new Error(`${path}: not found`);
        let part: { arrayBuffer(): Promise<ArrayBuffer> } = f;
        if (options.rangeStart !== undefined && options.rangeSize !== undefined) {
            const start = Number(options.rangeStart);
            part = f.slice(start, start + Number(options.rangeSize));
        }
        const slice = new ArrayBufferSlice(await part.arrayBuffer()) as NamedArrayBufferSlice;
        slice.name = path;
        return slice;
    }
}

// noclip's LooseMount asks Array.includes per lookup; a set, for a few thousand files.
class SetLooseMount extends LooseMount {
    private set: Set<string>;
    constructor(path: string, files: string[]) {
        super(path, files);
        this.set = new Set(files.map((f) => f.toLowerCase()));
    }
    public override hasEntry(resolvedPath: string): boolean { return this.set.has(resolvedPath); }
}

// A map's own pakfile wins over mounted games, as in the game since Patch 765
// and in Source itself; noclip searches its VPKs first. Then the games, then what
// an earlier visit kept from them (`kept`), and what nothing provides is stood
// in for (missing.ts) and counted, so the page can say what it lacks.
export class MapFileSystem extends SourceFileSystem {
    public missing = new Set<string>();
    public fromKept = 0;

    constructor(fetcher: DataFetcher, private kept: Store, private keepNew: boolean) {
        super(fetcher);
    }

    public addLoose(base: string, files: string[]): void {
        this.loose.push(new SetLooseMount(base, files));
    }

    // Only VMT.ts's last retry, `materials/<path>` after a real miss, is told yes
    // for a file nobody has, so its name still picks the stand-in's colour. Every
    // other question gets the truth: a model's cdmaterials search takes the first
    // folder that answers yes.
    public override hasEntry(resolvedPath: string): boolean {
        return super.hasEntry(resolvedPath) || this.kept.has(resolvedPath) ||
            (resolvedPath.startsWith('materials/materials/') && resolvedPath.endsWith('.vmt'));
    }

    public override async fetchFileData(resolvedPath: string): Promise<ArrayBufferSlice | null> {
        for (const zip of this.pakfiles) {
            const entry = zip.find((e) => e.filename === resolvedPath);
            if (entry !== undefined)
                return decompressZipFileEntry(entry);
        }
        if (resolvedPath.startsWith(MISSING_DIR))
            return missingTexture(resolvedPath);
        // Past the pakfile, anything super finds is the visitor's own game files.
        const found = await super.fetchFileData(resolvedPath);
        if (found !== null) {
            if (this.keepNew && !this.kept.has(resolvedPath))
                void this.kept.put(resolvedPath, found.copyToBuffer());
            return found;
        }
        const stored = await this.kept.get(resolvedPath);
        if (stored !== null) {
            this.fromKept++;
            return new ArrayBufferSlice(stored);
        }
        if (resolvedPath.endsWith('.vmt')) {
            this.missing.add(resolvedPath.replace(/^materials\/materials\//, 'materials/'));
            return missingMaterial(resolvedPath);
        }
        if (resolvedPath.endsWith('.vtf')) {
            this.missing.add(resolvedPath);
            return missingTexture(resolvedPath);
        }
        if (resolvedPath.endsWith('.mdl'))
            this.missing.add(resolvedPath);
        return null;
    }
}
