// Node stand-ins for the browser globals noclip touches at module load (SaveManager).
const store = { getItem: () => null, setItem: () => {}, removeItem: () => {}, key: () => null, length: 0 };
(globalThis as any).window ??= { localStorage: store, addEventListener: () => {}, location: { search: '', hash: '' } };
