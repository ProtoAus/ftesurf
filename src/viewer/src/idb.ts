// The viewer's one IndexedDB database: remembered folders (handles.ts) and the
// per-entry records of what store.ts keeps. One record per key, so two tabs
// writing at once each change only their own entries.

const DB = 'ftesurf-viewer';
export const FOLDERS = 'folders', META = 'meta';

let db: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
    db ??= new Promise((res, rej) => {
        const q = indexedDB.open(DB, 2);
        q.onupgradeneeded = () => {
            for (const s of [FOLDERS, META])
                if (!q.result.objectStoreNames.contains(s)) q.result.createObjectStore(s);
        };
        q.onsuccess = () => res(q.result);
        q.onerror = () => rej(q.error);
        q.onblocked = () => rej(new Error('IndexedDB blocked'));
    });
    db.catch(() => { db = null; });
    return db;
}

export function idb<T>(os: string, mode: IDBTransactionMode, f: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
    return open().then((d) => new Promise<T>((res, rej) => {
        const r = f(d.transaction(os, mode).objectStore(os));
        r.onsuccess = () => res(r.result);
        r.onerror = () => rej(r.error);
    }));
}

// Every [key, value] whose key starts with `prefix`.
export function idbEntries<T>(os: string, prefix: string): Promise<[string, T][]> {
    return open().then((d) => new Promise((res, rej) => {
        const out: [string, T][] = [];
        const r = d.transaction(os, 'readonly').objectStore(os).openCursor(IDBKeyRange.bound(prefix, prefix + '￿'));
        r.onsuccess = () => {
            const c = r.result;
            if (c === null) { res(out); return; }
            out.push([String(c.key), c.value as T]);
            c.continue();
        };
        r.onerror = () => rej(r.error);
    }));
}
