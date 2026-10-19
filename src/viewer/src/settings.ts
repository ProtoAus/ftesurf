// The viewer's display settings: what is drawn in the map, what the HUD shows,
// how energy reads, what is kept on this PC. Remembered in this browser
// (localStorage) and bound to every control marked data-set="<key>".

export interface Settings {
    line: boolean; zones: boolean; zoneNames: boolean; bodies: boolean; ghostName: boolean;
    timer: boolean; stage: boolean; gap: boolean; speed: boolean; vz: boolean; energy: boolean; keys: boolean;
    energyUnits: string;    // 'units' (a height, the game's hud_energy 1) or 'speed' (hud_energy 2)
    energyZero: string;     // 'jump' (hud_energy_ref 1) or 'start' (0)
    graph: string;          // 'speed' or 'energy'
    clean: boolean;         // everything above but the bodies hidden, for a clean picture
    keepMaps: boolean; keepGame: boolean; storeGB: number;
}

export const DEFAULTS: Settings = {
    line: true, zones: true, zoneNames: true, bodies: true, ghostName: true,
    timer: true, stage: true, gap: true, speed: true, vz: true, energy: true, keys: true,
    energyUnits: 'units', energyZero: 'jump', graph: 'speed',
    clean: false, keepMaps: true, keepGame: true, storeGB: 4,
};

const KEY = 'ftesurf.viewer.settings.v1';

export function loadSettings(): Settings {
    const s: Settings = { ...DEFAULTS };
    try {
        const saved = JSON.parse(localStorage.getItem(KEY) ?? '{}');
        for (const k of Object.keys(DEFAULTS) as (keyof Settings)[])
            if (typeof saved[k] === typeof DEFAULTS[k]) (s as any)[k] = saved[k];
    } catch {
        // Defaults, every time: storage refused or unreadable.
    }
    return s;
}

export function saveSettings(s: Settings): void {
    try {
        localStorage.setItem(KEY, JSON.stringify(s));
    } catch {
        // This visit only.
    }
}

// Every [data-set] control shows its setting; a change writes it back, saves,
// and tells `changed` which key moved.
export function bindSettings(root: ParentNode, s: Settings, changed: (key: keyof Settings) => void): void {
    for (const el of Array.from(root.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-set]'))) {
        const key = el.dataset.set as keyof Settings;
        if (!(key in DEFAULTS)) continue;
        el.addEventListener('change', () => {
            const d = DEFAULTS[key];
            (s as any)[key] = typeof d === 'boolean' ? (el as HTMLInputElement).checked
                : typeof d === 'number' ? Number(el.value) : el.value;
            saveSettings(s);
            changed(key);
        });
    }
    showSettings(root, s);
}

export function showSettings(root: ParentNode, s: Settings): void {
    for (const el of Array.from(root.querySelectorAll<HTMLInputElement | HTMLSelectElement>('[data-set]'))) {
        const key = el.dataset.set as keyof Settings;
        if (!(key in DEFAULTS)) continue;
        if (typeof DEFAULTS[key] === 'boolean') (el as HTMLInputElement).checked = s[key] as boolean;
        else el.value = String(s[key]);
    }
}
