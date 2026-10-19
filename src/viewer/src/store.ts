// What the viewer keeps on the visitor's own PC, in the browser's Cache Storage:
// downloaded maps, and the files a map read from the visitor's games (so the
// next visit needs no folder). Nothing here is ever sent anywhere. Each store
// has a manifest (bytes, last used, version) and is trimmed least-recently-used
// to its budget. Without Cache Storage (an insecure origin, a private window
// that refuses it) every call is a quiet no-op and the page works as before.

interface Entry { b: number; u: number; v?: string }

const KEY = (store: string, key: string) => `https://viewer.store/${store}/${encodeURIComponent(key)}`;
const MANIFEST = '__manifest';

export class Store {
    private cache: Cache | null = null;
    private index = new Map<string, Entry>();
    private saving: ReturnType<typeof setTimeout> | null = null;
    public budget: number;

    constructor(private name: string, budgetBytes: number) {
        this.budget = budgetBytes;
    }

    public async open(): Promise<this> {
        try {
            this.cache = await caches.open(this.name);
            const r = await this.cache.match(KEY(this.name, MANIFEST));
            const m = r ? await r.json() : {};
            for (const [k, e] of Object.entries(m as Record<string, Entry>))
                if (e && typeof e.b === 'number' && typeof e.u === 'number') this.index.set(k, e);
        } catch {
            this.cache = null;
            this.index.clear();
        }
        return this;
    }

    public get usable(): boolean { return this.cache !== null; }
    public has(key: string): boolean { return this.index.has(key); }
    public version(key: string): string | undefined { return this.index.get(key)?.v; }

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
            const r = await this.cache.match(KEY(this.name, key));
            if (r === undefined) {             // the manifest outlived its entry
                this.index.delete(key);
                this.saveSoon();
                return null;
            }
            e.u = Date.now();
            this.saveSoon();
            return await r.arrayBuffer();
        } catch {
            return null;
        }
    }

    public async put(key: string, data: ArrayBuffer | Uint8Array, ver?: string): Promise<void> {
        if (this.cache === null || data.byteLength > this.budget) return;
        try {
            await this.cache.put(KEY(this.name, key), new Response(data as BodyInit));
            this.index.set(key, { b: data.byteLength, u: Date.now(), v: ver });
            await this.trim(key);
            this.saveSoon();
        } catch {
            // Quota or a closed cache: the page carries on without keeping it.
        }
    }

    public async setBudget(bytes: number): Promise<void> {
        this.budget = bytes;
        await this.trim(null);
        this.saveSoon();
    }

    public async clear(): Promise<void> {
        this.index.clear();
        try {
            await caches.delete(this.name);
            this.cache = await caches.open(this.name);
        } catch {
            this.cache = null;
        }
    }

    // Oldest first until under budget; never the entry just written.
    private async trim(keep: string | null): Promise<void> {
        let total = this.info().bytes;
        if (total <= this.budget || this.cache === null) return;
        const old = [...this.index.entries()].filter(([k]) => k !== keep).sort((a, b) => a[1].u - b[1].u);
        for (const [k, e] of old) {
            if (total <= this.budget) break;
            await this.cache.delete(KEY(this.name, k));
            this.index.delete(k);
            total -= e.b;
        }
    }

    private saveSoon(): void {
        if (this.saving !== null || this.cache === null) return;
        this.saving = setTimeout(() => {
            this.saving = null;
            const body = JSON.stringify(Object.fromEntries(this.index));
            void this.cache?.put(KEY(this.name, MANIFEST), new Response(body)).catch(() => undefined);
        }, 1000);
    }
}

export const GB = 1 << 30;
export const maps = new Store('ftesurf-maps-v1', 4 * GB);
export const gameFiles = new Store('ftesurf-game-v1', 4 * GB);
