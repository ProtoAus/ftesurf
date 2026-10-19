// The run viewer page (surfd/web/watch.html): a board run played back in 3D
// over noclip's Source renderer, with the run's own numbers beside it.
// SourceEngine/Main.js FIRST: the Materials modules import each other in a
// cycle that only evaluates in order when Main.ts is where it is entered, as in
// noclip. Reached through BSPFile first, Material_Eyes extends an undefined base.
import { BSPRenderer, SkyboxRenderer, SourceLoadContext, SourceRenderContext, SourceRenderer } from '../vendor/noclip/src/SourceEngine/Main.js';
import { vec3 } from 'gl-matrix';
import ArrayBufferSlice from '../vendor/noclip/src/ArrayBufferSlice.js';
import { BSPFile } from '../vendor/noclip/src/SourceEngine/BSPFile.js';
import { Fetcher, GameFiles, HttpSource, MapFileSystem, Mount } from './files.js';
import { newPose, poseAt, Pose, sampleAt, wrap } from './playback.js';
import { FL_DUCKED, FL_ONGROUND, KEY_BACK, KEY_DUCK, KEY_FORWARD, KEY_JUMP, KEY_LEFT, KEY_RIGHT, parseRec, Rec } from './rec.js';
import { View } from './view.js';

// The R2-backed map route the game downloads from (cfg/default.cfg cl_download_mapsrc);
// a page served from this machine reads its own /maps/ (src/viewer/tools/serve.py).
const LOCAL_DEV = location.hostname === '127.0.0.1' || location.hostname === 'localhost';
const MAP_URL = (name: string) => (LOCAL_DEV ? `/maps/${name}.bsp` : `https://play.proto.bar/maps/${name}.bsp`);
const SPEEDS = [0.25, 0.5, 1, 2, 4];
const PATH_POINTS = 1500;   // overlay path vertices, whatever the run's length
const PATH_BEHIND = 2, PATH_AHEAD = 8;   // seconds of run line around the playhead

type CamMode = 'eye' | 'chase' | 'top' | 'free';

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

function plain(s: string): string {
    return String(s).replace(/\^(\^|x[0-9A-Fa-f]{3}|&[0-9A-Fa-f-]{2}|[0-9abhmrsu])/g, (_m, c) => (c === '^' ? '^' : ''));
}

function fmt(sec: number): string {
    const neg = sec < 0;
    const ms = Math.round(Math.abs(sec) * 1000);
    const m = Math.floor(ms / 60000), s = Math.floor(ms / 1000) % 60, r = ms % 1000;
    return (neg ? '-' : '') + m + ':' + (s < 10 ? '0' : '') + s + '.' + ('00' + r).slice(-3);
}

function el(tag: string, cls: string | null, text?: string): HTMLElement {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
}

function status(msg: string, busy = false): void {
    const s = $('wstatus');
    s.textContent = msg;
    s.hidden = msg === '';
    s.classList.toggle('busy', busy);
}

// ---- state -----------------------------------------------------------------

const files = new GameFiles();
const fetcher = new Fetcher(files);
let view: View | null = null;
let rec: Rec | null = null;
let runInfo: any = null;
let mapName = '';
let T = 0, t0 = 0, t1 = 0;
let playing = false, speed = 1;
let mode: CamMode = 'eye';
const pose: Pose = newPose();
let orbitYaw = 0, orbitPitch = 20, orbitDist = 160;
let pathIdx: Int32Array | null = null;
let maxSpeed = 1;

// ---- loading ---------------------------------------------------------------

async function fetchJSON(url: string): Promise<any> {
    const r = await fetch(url, { credentials: 'omit' });
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.json();
}

async function loadRunFromBoard(rid: number): Promise<void> {
    status('Loading the run…', true);
    runInfo = await fetchJSON(`api/run/${rid}`);
    showInfo(runInfo);
    const track = await fetchJSON(`api/run/${rid}/track`);
    setRec(parseRec(track.rec));
}

function setRec(r: Rec): void {
    rec = r;
    t0 = r.n > 0 ? Math.max(r.t[0], -1) : 0;
    t1 = r.end ?? (r.n > 0 ? r.t[r.n - 1] : 0);
    T = Math.max(t0, 0);
    mapName = r.head.get('map') ?? '';
    maxSpeed = 1;
    for (let i = 0; i < r.n; i++)
        maxSpeed = Math.max(maxSpeed, Math.hypot(r.v[i * 3], r.v[i * 3 + 1]));
    const stride = Math.max(1, Math.ceil(r.n / PATH_POINTS));
    pathIdx = new Int32Array(Math.ceil(r.n / stride));
    for (let i = 0, j = 0; i < r.n; i += stride) pathIdx[j++] = i;
    buildTimeline();
    if (runInfo === null) showInfoFromRec(r);
}

async function bspBytes(name: string): Promise<ArrayBufferSlice> {
    const local = await files.findMap(name);
    if (local !== null) {
        status(`Reading ${name}.bsp from your game files…`, true);
        return new ArrayBufferSlice(await local.arrayBuffer());
    }
    status(`Downloading ${name}.bsp…`, true);
    const r = await fetch(MAP_URL(name), { credentials: 'omit' });
    if (!r.ok) throw new Error(`map download: ${r.status}`);
    const total = Number(r.headers.get('content-length') ?? 0);
    const reader = r.body!.getReader();
    const parts: Uint8Array[] = [];
    let got = 0;
    for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        parts.push(value);
        got += value.byteLength;
        if (total > 0) status(`Downloading ${name}.bsp… ${Math.round(got / total * 100)}% of ${(total / 1048576).toFixed(1)} MB`, true);
    }
    const buf = new Uint8Array(got);
    let off = 0;
    for (const p of parts) { buf.set(p, off); off += p.byteLength; }
    return new ArrayBufferSlice(buf.buffer);
}

async function loadMap(): Promise<void> {
    if (view === null || mapName === '') return;
    let bytes: ArrayBufferSlice;
    try {
        bytes = await bspBytes(mapName);
    } catch (e) {
        status(`${mapName}.bsp could not be downloaded here. Pick your game folder below and it is read from your disk instead.`);
        $('wfiles').classList.add('ask');
        return;
    }
    status(`Building ${mapName}…`, true);
    await new Promise((r) => setTimeout(r, 0));

    const fs = new MapFileSystem(fetcher);
    for (const m of files.mounts)
        for (const stem of m.vpks)
            await fs.createVPKMount(stem);
    const bsp = new BSPFile(bytes, mapName);
    if (bsp.pakfile !== null) fs.addPakFile(bsp.pakfile);

    const loadContext = new SourceLoadContext(fs);
    const renderContext = new SourceRenderContext(view.device, loadContext);
    const renderer = new SourceRenderer(view.context, renderContext);
    if (bsp.cubemaps[0] !== undefined)
        await renderContext.materialCache.bindLocalCubemap(bsp.cubemaps[0]);
    const bspRenderer = new BSPRenderer(renderContext, bsp);
    const worldspawn = bspRenderer.getWorldSpawn();
    if (worldspawn.skyname)
        renderer.skyboxRenderer = new SkyboxRenderer(renderContext, worldspawn.skyname);
    renderer.bspRenderers.push(bspRenderer);

    if (view.scene !== null) view.scene.destroy(view.device);
    view.scene = renderer;
    status('');
}

// ---- game files ------------------------------------------------------------

function showMounts(): void {
    const ul = $('wmounts');
    ul.textContent = '';
    for (const m of files.mounts) {
        const li = el('li', null, m.game);
        li.append(el('span', 'dim', m.vpks.length ? ` — ${m.vpks.length} content pack${m.vpks.length > 1 ? 's' : ''}` : ' — maps'));
        ul.append(li);
    }
}

async function addedFiles(found: Mount[]): Promise<void> {
    showMounts();
    if (found.length === 0) return;
    $('wfiles').classList.remove('ask');
    await loadMap();
}

async function pickFolder(): Promise<void> {
    const w = window as any;
    if (typeof w.showDirectoryPicker === 'function') {
        try {
            const h = await w.showDirectoryPicker({ id: 'steamcommon', mode: 'read' });
            await addedFiles(await files.addHandle(h));
        } catch (e) {
            if ((e as Error).name !== 'AbortError') status(String(e));
        }
    } else {
        $('wdir').click();
    }
}

// ---- playback, camera, overlay --------------------------------------------

function stageAt(t: number): number {
    if (rec === null) return 0;
    let s = 0;
    for (const e of rec.events)
        if (e.t <= t && (e.kind === 'stage' || e.kind === 'stagestart')) s = e.n;
    return s;
}

function placeCamera(v: View): void {
    if (mode === 'free') return;
    if (mode === 'eye') {
        v.placeEye(pose.x, pose.y, pose.eyeZ, pose.pitch, pose.yaw);
        return;
    }
    if (mode === 'top') {
        v.placeEye(pose.x, pose.y, pose.z + 900, 89.9, orbitYaw);
        return;
    }
    // Chase: behind the player's yaw, the mouse turns it about the player.
    const yaw = pose.yaw + orbitYaw, pit = orbitPitch;
    const r = Math.PI / 180;
    const fx = Math.cos(pit * r) * Math.cos(yaw * r), fy = Math.cos(pit * r) * Math.sin(yaw * r), fz = -Math.sin(pit * r);
    const cz = pose.z + 48;
    v.placeEye(pose.x - fx * orbitDist, pose.y - fy * orbitDist, cz - fz * orbitDist, pit, yaw);
}

const scratch = vec3.create(), scratch2 = vec3.create();

function speedColour(sp: number): string {
    // The run line's ramp: slow is blue, fast is gold.
    const f = Math.min(1, sp / Math.max(maxSpeed, 1));
    const h = 210 - f * 170;
    return `hsl(${h} 90% 60%)`;
}

function drawOverlay(v: View): void {
    const c = $<HTMLCanvasElement>('woverlay');
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = c.clientWidth, h = c.clientHeight;
    if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) {
        c.width = Math.round(w * dpr);
        c.height = Math.round(h * dpr);
    }
    const g = c.getContext('2d')!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    if (rec === null || pathIdx === null || !($<HTMLInputElement>('wpath').checked)) return;

    g.lineWidth = 2;
    g.lineCap = 'round';
    let prev: vec3 | null = null;
    for (let k = 0; k < pathIdx.length; k++) {
        const i = pathIdx[k];
        if (rec.t[i] < T - PATH_BEHIND || rec.t[i] > T + PATH_AHEAD) { prev = null; continue; }
        const p = v.project(rec.o[i * 3], rec.o[i * 3 + 1], rec.o[i * 3 + 2] + 2, k & 1 ? scratch : scratch2);
        if (p !== null && prev !== null && rec.fit[pathIdx[k - 1]] !== 0) {
            g.strokeStyle = speedColour(Math.hypot(rec.v[i * 3], rec.v[i * 3 + 1]));
            g.globalAlpha = rec.t[i] <= T ? 0.35 : 0.9;
            g.beginPath();
            g.moveTo(prev[0], prev[1]);
            g.lineTo(p[0], p[1]);
            g.stroke();
        }
        prev = p === null ? null : vec3.clone(p);
    }
    g.globalAlpha = 1;
    if (mode !== 'eye') {
        // The player: a hull outline would need depth; a marker reads fine.
        const p = v.project(pose.x, pose.y, pose.z + 36, scratch);
        if (p !== null) {
            const rpx = Math.max(4, Math.min(28, 9000 / p[2]));
            g.fillStyle = '#59bfff';
            g.strokeStyle = '#00131f';
            g.lineWidth = 2;
            g.beginPath();
            g.arc(p[0], p[1], rpx, 0, Math.PI * 2);
            g.fill();
            g.stroke();
        }
    }
}

function updateHud(): void {
    if (rec === null) return;
    $('htime').textContent = fmt(Math.min(T, t1));
    $('hspeed').textContent = String(Math.round(Math.hypot(pose.vx, pose.vy)));
    $('hvz').textContent = (pose.vz >= 0 ? '+' : '') + Math.round(pose.vz);
    const st = stageAt(T);
    $('hstage').textContent = st > 0 ? `Stage ${st}` : (T < 0 ? 'Start' : '');
    const k = pose.keys;
    const on = (id: string, b: boolean) => $(id).classList.toggle('on', b);
    on('kw', !!(k & KEY_FORWARD)); on('ka', !!(k & KEY_LEFT)); on('ks', !!(k & KEY_BACK)); on('kd', !!(k & KEY_RIGHT));
    on('kj', !!(k & KEY_JUMP)); on('kc', !!(k & KEY_DUCK) || !!(pose.fl & FL_DUCKED));
    on('kg', !!(pose.fl & FL_ONGROUND));
    $<HTMLInputElement>('wseek').value = String(T);
    $('wclock').textContent = `${fmt(Math.max(T, t0))} / ${fmt(t1)}`;
}

function buildTimeline(): void {
    if (rec === null) return;
    const s = $<HTMLInputElement>('wseek');
    s.min = String(t0);
    s.max = String(t1);
    s.step = '0.001';
    const ticks = $('wticks');
    ticks.textContent = '';
    const span = t1 - t0;
    if (span <= 0) return;
    for (const e of rec.events) {
        if (e.kind !== 'stage' && e.kind !== 'cp') continue;
        const m = el('span', e.kind === 'stage' ? 'tick stage' : 'tick');
        m.style.left = `${((e.t - t0) / span) * 100}%`;
        m.title = e.kind === 'stage' ? `Stage ${e.n} at ${fmt(e.t)}` : `Checkpoint ${e.n} at ${fmt(e.t)}`;
        ticks.append(m);
    }
}

let last = 0, frames = 0;
// What the page says it did, for tools/shot.mjs (and anyone's console).
(window as any).watchState = () => ({
    frames, T, mode, playing, map: mapName, samples: rec?.n ?? 0, scene: view?.scene !== null,
    mounts: files.mounts.map((m) => m.game), status: $('wstatus').hidden ? '' : $('wstatus').textContent,
    eye: [pose.x, pose.y, pose.eyeZ, pose.pitch, pose.yaw],
});
(window as any).watchSeek = (t: number, m?: CamMode) => { T = t; if (m) setMode(m); };

function loop(now: number): void {
    const dt = last === 0 ? 0 : Math.min(now - last, 100);
    last = now;
    if (view !== null && rec !== null) {
        if (playing) {
            T += dt / 1000 * speed;
            if (T >= t1) { T = t1; setPlaying(false); }
        }
        poseAt(rec, T, pose);
        if (mode === 'chase' && view.input.buttons & 1) {
            orbitYaw = wrap(orbitYaw - view.input.getMouseDeltaX() * 0.25);
            orbitPitch = Math.max(-80, Math.min(85, orbitPitch + view.input.getMouseDeltaY() * 0.25));
        }
        placeCamera(view);
        view.frame(dt, Number($<HTMLSelectElement>('wfov').value));
        drawOverlay(view);
        updateHud();
        frames++;
    }
    requestAnimationFrame(loop);
}

function setPlaying(p: boolean): void {
    playing = p;
    $('wplay').textContent = p ? 'Pause' : 'Play';
    $('wplay').setAttribute('aria-pressed', p ? 'true' : 'false');
}

function setMode(m: CamMode): void {
    mode = m;
    for (const b of Array.from(document.querySelectorAll<HTMLButtonElement>('[data-cam]')))
        b.setAttribute('aria-pressed', b.dataset.cam === m ? 'true' : 'false');
    if (view !== null) {
        view.freeOn = m === 'free';
        if (m === 'free') view.placeEye(pose.x, pose.y, pose.eyeZ, pose.pitch, pose.yaw);
    }
    if (m === 'chase') { orbitYaw = 0; orbitPitch = 20; }
}

// ---- the info panel ----------------------------------------------------------

function dlRow(dl: HTMLElement, k: string, v: string): void {
    dl.append(el('dt', null, k), el('dd', null, v));
}

const TIER_NAMES: Record<string, string> = { ranked: 'World of Surf', momentum: 'Momentum Mod', ksf: 'KSF', imported: 'Imported' };

function showInfo(r: any): void {
    $('wtitle').textContent = `${plain(r.name)} on ${r.disp || r.map}`;
    $('wtime').textContent = fmt(r.ms / 1000);
    const dl = $('winfo');
    dl.textContent = '';
    dlRow(dl, 'player', plain(r.name));
    dlRow(dl, 'map', r.disp || r.map);
    dlRow(dl, 'board', (TIER_NAMES[r.tr] ?? r.tr) + (r.style && r.style !== 'clean' ? ` · ${r.style}` : '') +
        (r.leg > 0 ? ` · stage ${r.leg}` : r.track > 0 ? ` · bonus ${r.track}` : ''));
    if (r.when) dlRow(dl, 'date', new Date(r.when * 1000).toISOString().slice(0, 10));
    if (r.stats) {
        dlRow(dl, 'top speed', `${Math.round(r.stats.max_speed)} u/s`);
        dlRow(dl, 'average speed', `${Math.round(r.stats.avg_speed)} u/s`);
    }
    const back = $<HTMLAnchorElement>('wback');
    back.href = `./#r=${r.rid}`;
    const sp = $('wsplits');
    sp.textContent = '';
    const rate = Number(r.rate) || 0.015;
    let prev = 0;
    for (const [seg, ticks] of (r.splits || []) as [number, number][]) {
        const tr = el('tr', null);
        const t = ticks * rate;
        tr.append(el('td', null, `Stage ${seg}`), el('td', 'num', fmt(t)), el('td', 'num dim', '+' + (t - prev).toFixed(3)));
        tr.addEventListener('click', () => { T = Math.max(t0, t - 1); });
        sp.append(tr);
        prev = t;
    }
    $('wsplitbox').hidden = (r.splits || []).length === 0;
}

function showInfoFromRec(r: Rec): void {
    $('wtitle').textContent = `${r.head.get('owner') ?? 'A run'} on ${r.head.get('map') ?? '?'}`;
    $('wtime').textContent = r.end !== null ? fmt(r.end) : '';
    const dl = $('winfo');
    dl.textContent = '';
    dlRow(dl, 'map', r.head.get('map') ?? '?');
    dlRow(dl, 'samples', String(r.n));
    $('wsplitbox').hidden = true;
}

function computeStats(r: Rec): void {
    // Jumps and strafes from the sample stream: a jump is a ground-to-air step
    // with the jump key held, a strafe a change of the held side key.
    let jumps = 0, strafes = 0, lastSide = 0, air = 0, total = 0;
    for (let i = 1; i < r.n; i++) {
        if (r.t[i] < 0 || (r.end !== null && r.t[i] > r.end)) continue;
        const dt = r.t[i] - r.t[i - 1];
        total += dt;
        if (!(r.fl[i] & FL_ONGROUND)) air += dt;
        if ((r.fl[i - 1] & FL_ONGROUND) && !(r.fl[i] & FL_ONGROUND) && (r.keys[i] & KEY_JUMP)) jumps++;
        const side = r.keys[i] & (KEY_LEFT | KEY_RIGHT);
        if (side !== 0 && side !== (KEY_LEFT | KEY_RIGHT) && side !== lastSide) { strafes++; lastSide = side; }
    }
    const dl = $('winfo');
    dlRow(dl, 'jumps', String(jumps));
    dlRow(dl, 'strafes', String(strafes));
    if (total > 0) dlRow(dl, 'in the air', `${Math.round(air / total * 100)}%`);
}

// ---- wiring -------------------------------------------------------------------

function seekBy(d: number): void { T = Math.max(t0, Math.min(t1, T + d)); }

function wire(): void {
    $('wplay').addEventListener('click', () => {
        if (T >= t1) T = Math.max(t0, 0);
        setPlaying(!playing);
    });
    $<HTMLInputElement>('wseek').addEventListener('input', (e) => { T = Number((e.target as HTMLInputElement).value); });
    $<HTMLSelectElement>('wspeed').addEventListener('change', (e) => { speed = Number((e.target as HTMLSelectElement).value); });
    for (const b of Array.from(document.querySelectorAll<HTMLButtonElement>('[data-cam]')))
        b.addEventListener('click', () => setMode(b.dataset.cam as CamMode));
    $('wpick').addEventListener('click', () => { void pickFolder(); });
    $<HTMLInputElement>('wdir').addEventListener('change', async (e) => {
        const list = (e.target as HTMLInputElement).files;
        if (list && list.length) await addedFiles(await files.addList(list));
    });
    $<HTMLInputElement>('wrecfile').addEventListener('change', async (e) => {
        const f = (e.target as HTMLInputElement).files?.[0];
        if (!f) return;
        runInfo = null;
        setRec(parseRec(await f.text()));
        computeStats(rec!);
        await loadMap();
    });
    $('wfull').addEventListener('click', () => {
        const s = $('wstage');
        if (document.fullscreenElement) void document.exitFullscreen();
        else void s.requestFullscreen();
    });
    document.addEventListener('keydown', (e) => {
        if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
        if (e.code === 'Space') { e.preventDefault(); $('wplay').click(); }
        else if (e.code === 'ArrowLeft') seekBy(e.shiftKey ? -1 : -5);
        else if (e.code === 'ArrowRight') seekBy(e.shiftKey ? 1 : 5);
        else if (e.code === 'Digit1') setMode('eye');
        else if (e.code === 'Digit2') setMode('chase');
        else if (e.code === 'Digit3') setMode('top');
        else if (e.code === 'Digit4') setMode('free');
        else if (e.code === 'Comma' || e.code === 'Period') {
            const i = SPEEDS.indexOf(speed) + (e.code === 'Comma' ? -1 : 1);
            if (i >= 0 && i < SPEEDS.length) { speed = SPEEDS[i]; $<HTMLSelectElement>('wspeed').value = String(speed); }
        }
    });
    $('wgl').addEventListener('wheel', (e) => {
        if (mode === 'chase') orbitDist = Math.max(40, Math.min(1200, orbitDist * (e.deltaY > 0 ? 1.1 : 0.9)));
    }, { passive: true });
}

async function main(): Promise<void> {
    wire();
    try {
        view = new View($<HTMLCanvasElement>('wgl'), fetcher);
    } catch (e) {
        status(String((e as Error).message));
        return;
    }
    requestAnimationFrame(loop);

    const hash = new URLSearchParams(location.hash.slice(1));
    if (LOCAL_DEV && hash.has('steam')) {
        await files.add(new HttpSource('/steam/'));
        showMounts();
    }
    const rid = Number(hash.get('r'));
    if (!(rid > 0)) {
        status('Open a run from the board, or a .rec file from your disk below.');
        return;
    }
    try {
        await loadRunFromBoard(rid);
        computeStats(rec!);
        const at = Number(hash.get('t'));
        if (Number.isFinite(at) && hash.has('t')) T = Math.max(t0, Math.min(t1, at));
        poseAt(rec!, T, pose);
        sampleAt(rec!, T);
        await loadMap();
    } catch (e) {
        status(`This run could not be loaded (${(e as Error).message}).`);
    }
}

void main();
