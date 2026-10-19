// Game folders picked with Chrome's or Edge's folder picker, remembered in this
// browser (IndexedDB) so a later visit mounts them again: by itself when the
// browser kept the permission, else after one click. The picker refuses folders
// under Program Files, so Steam's default library is never one of these; the
// files a map used from there are kept instead (store.ts).
import { FOLDERS, idb } from './idb.js';

export async function rememberFolder(h: FileSystemDirectoryHandle): Promise<void> {
    try {
        for (const old of await savedFolders())
            if (await (old as any).isSameEntry(h)) return;
        await idb(FOLDERS, 'readwrite', (s) => s.put(h, `${h.name}:${Date.now()}`));
    } catch {
        // No IndexedDB here: the folder works for this visit only.
    }
}

export async function savedFolders(): Promise<FileSystemDirectoryHandle[]> {
    try {
        return (await idb(FOLDERS, 'readonly', (s) => s.getAll())) as FileSystemDirectoryHandle[];
    } catch {
        return [];
    }
}

export async function forgetFolders(): Promise<void> {
    try {
        await idb(FOLDERS, 'readwrite', (s) => s.clear());
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
