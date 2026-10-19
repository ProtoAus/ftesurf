// What the viewer keeps on the visitor's own PC: downloaded maps, and the files
// a map read from the visitor's games (so the next visit needs no folder). The
// bytes are in Cache Storage, each entry's size, last use and version in its own
// IndexedDB record (idb.ts), so tabs cannot overwrite each other's. Trimmed
// least-recently-used to the smaller of its budget and a share of what the
// browser grants the site. Nothing here is ever sent anywhere. Without Cache
// Storage or IndexedDB nothing is kept and the page works as before.
import { idb, idbEntries, META } from './idb.js';

interface Entry { b: number; u: number; v?: string }

const QUOTA_SHARE = 0.4;     // of the site's quota, per store (there are two)

export class Store {
    private cache: Cache | null = null;
    private index = new Map<string, Entry>();
    private quota = Infinity;
    public budget: number;

    constructor(private name: string, budgetBytes: number) {
        this.budget = budgetBytes;
    }

    private url(key: string): string { return `https://viewer.store/${this.name}/${encodeURIComponent(key)}`; }
    private meta(key: string): string { return `${this.name}\n${key}`; }

    public async open(): Promise<this> {
        try {
            this.cache = await caches.open(this.name);
            await this.reload();
            const est = await navigator.storage?.estimate?.();
            if (est?.quota) this.quota = est.quota * QUOTA_SHARE;
            void this.sweep();
        } catch {
            this.cache = null;
            this.index.clear();
        }
        return this;
    }

    private async reload(): Promise<void> {
        this.index.clear();
        const pre = this.meta('');
        for (const [k, e] of await idbEntries<Entry>(META, pre))
            if (e && typeof e.b === 'number' && typeof e.u === 'number') this.index.set(k.slice(pre.length), e);
    }

    // Bytes with no record (a tab closed mid-put) are nobody's: delete them.
    private async sweep(): Promise<void> {
        if (this.cache === null) return;
        const pre = this.url('');
        for (const r of await this.cache.keys()) {
            const key = decodeURIComponent(r.url.slice(pre.length));
            if (r.url.startsWith(pre) && !this.index.has(key)) await this.cache.delete(r);
        }
    }

    public get usable(): boolean { return this.cache !== null; }
    public has(key: string): boolean { return this.index.has(key); }
    private get limit(): number { return Math.min(this.budget, this.quota); }

    public info(): { count: number; bytes: number } {
        let bytes = 0;
        for (const e of this.index.values()) bytes += e.b;
        return { count: this.index.size, bytes };
    }

    // The stored bytes, if any, and of `ver` when one is asked for.
    public async get(key: string, ver?: string): Promise<ArrayBuffer | null> {
        const e = this.index.get(key);
        if (this.cache === null || e === undefined || (ver !== undefined && e.v !== ver)) return null;
        try {
            const r = await this.cache.match(this.url(key));
            if (r === undefined) {             // the record outlived its bytes
                await this.drop(key);
                return null;
            }
            e.u = Date.now();
            void idb(META, 'readwrite', (s) => s.put(e, this.meta(key))).catch(() => undefined);
            return await r.arrayBuffer();
        } catch {
            return null;
        }
    }

    public async put(key: string, data: ArrayBuffer | Uint8Array, ver?: string): Promise<void> {
        if (this.cache === null || data.byteLength > this.limit) return;
        const e: Entry = { b: data.byteLength, u: Date.now(), v: ver };
        try {
            await this.trim(data.byteLength, key);
            try {
                await this.cache.put(this.url(key), new Response(data as BodyInit));
            } catch {
                // The browser's own quota is tighter than ours: make room once more.
                await this.trim(data.byteLength * 2, key);
                await this.cache.put(this.url(key), new Response(data as BodyInit));
            }
            await idb(META, 'readwrite', (s) => s.put(e, this.meta(key)));
            this.index.set(key, e);
        } catch {
            await this.cache.delete(this.url(key)).catch(() => false);
        }
    }

    public async setBudget(bytes: number): Promise<void> {
        this.budget = bytes;
        await this.trim(0, null).catch(() => undefined);
    }

    public async clear(): Promise<void> {
        for (const k of [...this.index.keys()]) await this.drop(k).catch(() => undefined);
        try {
            await caches.delete(this.name);
            this.cache = await caches.open(this.name);
        } catch {
            this.cache = null;
        }
        this.index.clear();
    }

    private async drop(key: string): Promise<void> {
        this.index.delete(key);
        await this.cache?.delete(this.url(key));
        await idb(META, 'readwrite', (s) => s.delete(this.meta(key)));
    }

    // Oldest first until `room` more bytes fit; never `keep`. Before evicting, the
    // records are read again, so other tabs' entries count too.
    private async trim(room: number, keep: string | null): Promise<void> {
        if (this.cache === null || this.info().bytes + room <= this.limit) return;
        await this.reload();
        let total = this.info().bytes;
        if (total + room <= this.limit) return;
        const old = [...this.index.entries()].filter(([k]) => k !== keep).sort((a, b) => a[1].u - b[1].u);
        for (const [k, e] of old) {
            if (total + room <= this.limit) break;
            await this.drop(k);
            total -= e.b;
        }
    }
}

export const GB = 1 << 30;
export const maps = new Store('ftesurf-maps-v1', 4 * GB);
export const gameFiles = new Store('ftesurf-game-v1', 4 * GB);
