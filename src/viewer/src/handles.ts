// Game folders picked with Chrome's or Edge's folder picker, remembered in this
// browser (IndexedDB) so a later visit mounts them again: by itself when the
// browser kept the permission, else after one click. The picker refuses folders
// under Program Files, so Steam's default library is never one of these; the
// files a map used from there are kept instead (store.ts).

const DB = 'ftesurf-viewer', OS = 'folders';

function open(): Promise<IDBDatabase> {
    return new Promise((res, rej) => {
        const q = indexedDB.open(DB, 1);
        q.onupgradeneeded = () => q.result.createObjectStore(OS);
        q.onsuccess = () => res(q.result);
        q.onerror = () => rej(q.error);
    });
}

function run<T>(mode: IDBTransactionMode, f: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
    return open().then((db) => new Promise<T>((res, rej) => {
        const r = f(db.transaction(OS, mode).objectStore(OS));
        r.onsuccess = () => res(r.result);
        r.onerror = () => rej(r.error);
    }));
}

export async function rememberFolder(h: FileSystemDirectoryHandle): Promise<void> {
    try {
        for (const old of await savedFolders())
            if (await (old as any).isSameEntry(h)) return;
        await run('readwrite', (s) => s.put(h, `${h.name}:${Date.now()}`));
    } catch {
        // No IndexedDB here: the folder works for this visit only.
    }
}

export async function savedFolders(): Promise<FileSystemDirectoryHandle[]> {
    try {
        return (await run('readonly', (s) => s.getAll())) as FileSystemDirectoryHandle[];
    } catch {
        return [];
    }
}

export async function forgetFolders(): Promise<void> {
    try {
        await run('readwrite', (s) => s.clear());
    } catch {
        // Nothing to forget.
    }
}

// 'granted' mounts it now; 'prompt' needs a click (requestPermission must be
// called from one); anything else, it is gone.
export async function folderPermission(h: FileSystemDirectoryHandle, ask: boolean): Promise<string> {
    try {
        const o = { mode: 'read' };
        return ask ? await (h as any).requestPermission(o) : await (h as any).queryPermission(o);
    } catch {
        return 'denied';
    }
}
