// Globals the vendored noclip code names. `window.main` is noclip's app object;
// the viewer never sets it, and the code that reads it is debug-only.
interface ImportMeta { env: Record<string, string>; }
interface Window { main: any; }
