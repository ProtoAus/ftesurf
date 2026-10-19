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
import { DebugDraw } from '../vendor/noclip/src/gfx/helpers/DebugDraw.js';
import { View } from './view.js';
import { drawBody, drawRunLine, drawZones, zoneLabelPoint } from './world.js';
import { inferSplits, parseZones, Zone } from './zones.js';
import { energy, equivSpeed, gravityOf, runZero, zeros, Zeros } from './energy.js';
import { folderPermission, forgetFolders, rememberFolder, savedFolders } from './handles.js';
import { bindSettings, loadSettings, saveSettings, Settings, showSettings } from './settings.js';
import { GB, gameFiles, maps } from './store.js';

// The R2-backed routes the game downloads from (cfg/default.cfg cl_download_mapsrc,
// cl_download_zonesrc); a page served from this machine reads src/viewer/tools/serve.py's.
const LOCAL_DEV = location.hostname === '127.0.0.1' || location.hostname === 'localhost';
const MAP_URL = (name: string) => (LOCAL_DEV ? `/maps/${name}.bsp` : `https://play.proto.bar/maps/${name}.bsp`);
const ZONE_URL = (name: string) => (LOCAL_DEV ? `/zones/${name}.json` : `https://play.proto.bar/ftesurf/maps/zones/local/${name}.json`);
const SPEEDS = [0.25, 0.5, 1, 2, 4];
const PLAYER = { r: 0.35, g: 0.75, b: 1, a: 1 }, GHOST = { r: 0.91, g: 0.77, b: 0.42, a: 1 };

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
let maxSpeed = 1;
// The run raced against: the combined board's record (or its second, when this
// is the record), drawn at the same run time.
let ghost: { rec: Rec; info: any } | null = null;
const gpose: Pose = newPose();
let graph: HTMLCanvasElement | null = null;   // the speed traces, drawn once
let graphShown: HTMLCanvasElement | null = null;   // the traces now on the page's canvas
let zones: Zone[] = [];
// Each run's stage splits (1-based stage -> seconds): recorded, or inferred from
// the zones for a run that recorded none (imports), which `approx` marks.
interface Splits { t: Map<number, number>; approx: boolean }
let runSplits: Splits = { t: new Map(), approx: false };
let ghostSplits: Splits = { t: new Map(), approx: false };
const settings: Settings = loadSettings();
// Energy (energy.ts): this run's gravity and its two zeros at every sample.
let grav = 800, zs: Zeros | null = null;
let lastFs: MapFileSystem | null = null;
let mapSource = '', builds = 0;   // where the last BSP came from; scenes built
let contextLost = false;          // the browser took the GPU back: every draw is a no-op after

// ---- loading ---------------------------------------------------------------

// surfd builds one track at a time and says 503 to the next caller (Patch 825);
// nginx says 504 when a request outlasts 5 s.
async function fetchJSON(url: string): Promise<any> {
    for (let tries = 0; ; tries++) {
        const r = await fetch(url, { credentials: 'omit' });
        if ((r.status === 503 || r.status === 504) && tries < 3) {   // each try spends one of the route's rate
            await new Promise((res) => setTimeout(res, 1000 * (Number(r.headers.get('Retry-After')) || 2)));
            continue;
        }
        if (!r.ok) throw new Error(`${url}: ${r.status}`);
        return r.json();
    }
}

async function loadRunFromBoard(rid: number): Promise<void> {
    status('Loading the run…', true);
    runInfo = await fetchJSON(`api/run/${rid}`);
    showInfo(runInfo);
    const track = await fetchJSON(`api/run/${rid}/track`);
    setRec(parseRec(track.rec));
}

function setRec(r: Rec): void {
    if (r.n === 0) throw new Error('this recording has no samples');
    rec = r;
    t0 = r.n > 0 ? Math.max(r.t[0], -1) : 0;
    t1 = r.end ?? (r.n > 0 ? r.t[r.n - 1] : 0);
    T = Math.max(t0, 0);
    mapName = r.head.get('map') ?? '';
    maxSpeed = 1;
    for (let i = 0; i < r.n; i++)
        maxSpeed = Math.max(maxSpeed, Math.hypot(r.v[i * 3], r.v[i * 3 + 1]));
    if (runInfo === null) showInfoFromRec(r);
    zones = [];
    grav = gravityOf(r);
    zs = zeros(r, []);
    graph = null;
    computeSplits();
}

// The zone file the game downloads (maps/zones/local). Most maps have none, and
// that is silent: the page works without zones, it just draws and infers less.
async function loadZones(): Promise<void> {
    zones = [];
    const map = mapName, of = rec;
    if (map === '') return;
    let got: Zone[] = [];
    try {
        const r = await fetch(ZONE_URL(map), { credentials: 'omit' });
        if (r.ok) got = parseZones(await r.json(), Number(of?.head.get('track') ?? 0));
    } catch {
        got = [];
    }
    if (of !== rec) return;   // another recording was opened meanwhile
    zones = got;
    if (rec !== null) zs = zeros(rec, zones);
    graph = null;
    computeSplits();
}

function recordedSplits(info: any): Map<number, number> {
    const rate = Number(info?.rate) || 0.015;
    return new Map(((info?.splits || []) as [number, number][]).map(([seg, ticks]) => [seg, ticks * rate]));
}

function splitsFor(r: Rec | null, info: any): Splits {
    const recorded = info ? recordedSplits(info) : new Map(r?.splits.map((s) => [s.seg, s.t]) ?? []);
    if (recorded.size > 0 || r === null || zones.length === 0) return { t: recorded, approx: false };
    const inferred = new Map(inferSplits(r, zones).map((s) => [s.seg, s.t]));
    return { t: inferred, approx: inferred.size > 0 };
}

// Splits for both runs, and, for a run that recorded no stage events, stage
// events from the inferred splits so the HUD and timeline can name the stage.
function computeSplits(): void {
    runSplits = splitsFor(rec, runInfo);
    ghostSplits = ghost ? splitsFor(ghost.rec, ghost.info) : { t: new Map(), approx: false };
    if (rec !== null && runSplits.approx && !rec.events.some((e) => e.kind === 'stage' || e.kind === 'stagestart'))
        for (const [seg, t] of runSplits.t) rec.events.push({ kind: 'stage', t, n: seg });
    rec?.events.sort((a, b) => a.t - b.t);
    buildTimeline();
    showSplits();
}

async function bspBytes(name: string): Promise<ArrayBufferSlice> {
    const local = await files.findMap(name);
    const fromFolder = async () => {
        status(`Reading ${name}.bsp from your game files…`, true);
        mapSource = 'folder';
        return new ArrayBufferSlice(await local!.arrayBuffer());
    };
    status(`Downloading ${name}.bsp…`, true);
    // A kept copy is used when the download's length and date say it is the
    // same build (the route redirects to a new signed URL each time, so the
    // browser's own cache never matches); the download is then dropped.
    const ac = new AbortController();
    let r: Response;
    try {
        r = await fetch(MAP_URL(name), { credentials: 'omit', signal: ac.signal });
        if (!r.ok) throw new Error(`map download: ${r.status}`);
    } catch (e) {
        if (local !== null) return fromFolder();
        const any = await maps.get(name);
        if (any === null) throw e;
        status(`Offline: using the copy of ${name}.bsp kept on this PC…`, true);
        mapSource = 'kept offline';
        return new ArrayBufferSlice(any);
    }
    const total = Number(r.headers.get('content-length') ?? 0);
    // A game folder's copy, when it is the size of the server's build: another
    // build of the same name (a Momentum or CS:S install's) is not the run's map.
    if (local !== null && (local as File).size === total) {
        ac.abort();
        return fromFolder();
    }
    const ver = `${total}|${r.headers.get('last-modified') ?? ''}`;
    const kept = total > 0 ? await maps.get(name, ver) : null;
    if (kept !== null && kept.byteLength === total) {
        ac.abort();
        status(`Using the copy of ${name}.bsp kept on this PC…`, true);
        mapSource = 'kept';
        return new ArrayBufferSlice(kept);
    }
    mapSource = 'download';
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
    if (settings.keepMaps && total > 0 && got === total)
        void maps.put(name, buf, ver).then(showStore);
    return new ArrayBufferSlice(buf.buffer);
}

let mapLoads = 0;   // a newer load wins; an older one finishing late is dropped

async function loadMap(): Promise<void> {
    if (view === null || mapName === '') return;
    const mine = ++mapLoads;
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
    try {
        await buildScene(view, bytes, mine);
    } catch (e) {
        status(`${mapName} could not be drawn (${(e as Error).message}).`);
    }
}

async function buildScene(view: View, bytes: ArrayBufferSlice, mine: number): Promise<void> {
    const fs = new MapFileSystem(fetcher, gameFiles, settings.keepGame);
    for (const m of files.mounts) {
        for (const stem of m.vpks)
            await fs.createVPKMount(stem);
        if (m.loose !== null) fs.addLoose(m.loose.base, m.loose.files);
    }
    lastFs = fs;
    const bsp = new BSPFile(bytes, mapName);
    if (bsp.pakfile !== null) fs.addPakFile(bsp.pakfile);

    const loadContext = new SourceLoadContext(fs);
    const renderContext = new SourceRenderContext(view.device, loadContext);
    // noclip asserts on a VTF it cannot read (Strata's 7.6, an unknown format) and
    // the material is lost; the flat stand-in is drawn instead.
    const mc = renderContext.materialCache as any;
    const fetchVTF = mc.fetchVTFInternal.bind(mc);
    mc.fetchVTFInternal = async (name: string, srgb: boolean, key: string) => {
        try {
            return await fetchVTF(name, srgb, key);
        } catch {
            fs.missing.add(`materials/${name}.vtf (unreadable)`);
            return fetchVTF(`__missing/${name}`, srgb, key);
        }
    };
    const renderer = new SourceRenderer(view.context, renderContext);
    if (bsp.cubemaps[0] !== undefined)
        await renderContext.materialCache.bindLocalCubemap(bsp.cubemaps[0]);
    const bspRenderer = new BSPRenderer(renderContext, bsp);
    const worldspawn = bspRenderer.getWorldSpawn();
    if (worldspawn.skyname)
        renderer.skyboxRenderer = new SkyboxRenderer(renderContext, worldspawn.skyname);
    renderer.bspRenderers.push(bspRenderer);
    renderer.onWorldPasses = (builder, colour, depth) => {
        const dd = renderer.renderHelper.debugDraw;
        const mv = renderer.mainViewRenderer.mainView;
        dd.beginFrame(mv.clipFromViewMatrix, mv.viewFromWorldMatrix, view.canvas.width, view.canvas.height);
        drawWorld(dd, mv.cameraPos);
        dd.pushPasses(builder, colour, depth);
    };

    if (mine !== mapLoads) { renderer.destroy(view.device); return; }
    if (view.scene !== null) view.scene.destroy(view.device);
    view.scene = renderer;
    builds++;
    status('');
    setTimeout(showStore, 3000);   // the textures it kept land as they load
}

// ---- the 3D overlay: zones, the run line, the bodies ---------------------------

function drawWorld(dd: DebugDraw, cam: vec3): void {
    if (rec === null) return;
    const s = settings;
    if (s.zones && !s.clean) drawZones(dd, zones, cam);
    if (s.line && !s.clean) drawRunLine(dd, rec, T, cam, maxSpeed);
    if (!s.bodies) return;
    if (ghost !== null && T <= ghost.rec.t[ghost.rec.n - 1]) drawBody(dd, gpose, cam, GHOST);
    if (mode !== 'eye') drawBody(dd, pose, cam, PLAYER);
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
    if (found.every((m) => m.vpks.length === 0) && !(await files.findMap(mapName))) {
        status(`No game content in that folder. Choose Counter-Strike Source (or Half-Life 2, or Momentum Mod Playtest) inside steamapps\\common.`);
        return;
    }
    $('wfiles').classList.remove('ask');
    await loadMap();
}

// The folder input first: Chrome's and Edge's folder picker refuses anything
// under Program Files ("contains system files"), which is where Steam keeps its
// default library. The picker stays for a library on another drive.
async function pickNative(): Promise<void> {
    const w = window as any;
    if (typeof w.showDirectoryPicker !== 'function') {
        $('wdir').click();
        return;
    }
    try {
        const h = await w.showDirectoryPicker({ id: 'steamgame', mode: 'read' });
        const found = await files.addHandle(h);
        if (found.some((m) => m.game !== 'maps folder')) void rememberFolder(h);
        await addedFiles(found);
    } catch (e) {
        if ((e as Error).name !== 'AbortError') status(String(e));
    }
}

// Folders remembered from the picker: mounted at once if the browser kept the
// permission, else a button, since asking needs a click.
async function reconnectFolders(): Promise<void> {
    const box = $('wreconnect');
    const saved = await savedFolders();
    $('wforget').hidden = saved.length === 0;
    for (const h of saved) {
        if (await folderPermission(h, false) === 'granted') {
            try {
                await files.addHandle(h);
            } catch {
                // A folder that cannot be read now: the page goes on without it.
            }
            continue;
        }
        const b = el('button', 'wbtn', `Use ${h.name} again`) as HTMLButtonElement;
        b.type = 'button';
        b.addEventListener('click', async () => {
            if (await folderPermission(h, true) !== 'granted') return;
            b.remove();
            await addedFiles(await files.addHandle(h));
        });
        box.append(b);
    }
    showMounts();
}

function mb(bytes: number): string {
    return bytes >= GB ? `${(bytes / GB).toFixed(1)} GB` : `${Math.round(bytes / 1048576)} MB`;
}

function showStore(): void {
    const m = maps.info(), g = gameFiles.info();
    $('wmapstore').textContent = !maps.usable ? '(this browser keeps nothing here)'
        : `${m.count} map${m.count === 1 ? '' : 's'}, ${mb(m.bytes)}`;
    $('wgamestore').textContent = !gameFiles.usable ? '' : `${g.count} file${g.count === 1 ? '' : 's'}, ${mb(g.bytes)}`;
}

// ---- playback, camera, overlay --------------------------------------------

// The stage the run is on, 1-based; 0 on a map without stages. `stage <seg>` and
// `stagestart <seg>` name the 0-based segment entered (`!s n` is seg n-1).
function stageAt(t: number): number {
    if (rec === null || !rec.events.some((e) => e.kind === 'stage' || e.kind === 'stagestart')) return 0;
    let s = 0;
    for (const e of rec.events)
        if (e.t <= t && (e.kind === 'stage' || e.kind === 'stagestart')) s = e.n;
    return s + 1;
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

// Labels in 2D over the 3D: the record's name above its body, zone names.
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
    if (rec === null) return;
    g.font = '600 12px system-ui, sans-serif';
    g.textAlign = 'center';
    g.lineWidth = 3;
    g.strokeStyle = 'rgba(0,0,0,.75)';
    const label = (text: string, p: vec3 | null, colour: string) => {
        if (p === null) return;
        g.fillStyle = colour;
        g.strokeText(text, p[0], p[1]);
        g.fillText(text, p[0], p[1]);
    };
    if (settings.clean) return;
    if (settings.ghostName && ghost !== null && T <= ghost.rec.t[ghost.rec.n - 1])
        label(plain(ghost.info.name), v.project(gpose.x, gpose.y, gpose.z + 80, scratch), '#E8C56A');
    if (settings.zones && settings.zoneNames) {
        for (const z of zones) {
            const at = zoneLabelPoint(z, scratch2);
            const p = v.project(at[0], at[1], at[2] + 16, scratch);
            if (p === null || p[2] > 6000) continue;
            const name = z.kind === 'start' ? 'Start' : z.kind === 'end' ? 'End'
                : z.kind === 'stage' ? `Stage ${z.seg + 1}` : `Checkpoint ${z.cp}`;
            label(name, p, z.kind === 'end' ? '#ff8a7a' : z.kind === 'stage' ? '#E8C56A' : z.kind === 'start' ? '#7be38f' : '#8fd4ff');
        }
    }
}

const shown = new Map<string, string>();
function setText(id: string, s: string): void {
    if (shown.get(id) === s) return;
    shown.set(id, s);
    $(id).textContent = s;
}

// The zero energy is measured from at T (energy.ts).
// NaN when it is the start zone's and the feet have been in none yet.
function energyZero(): number {
    if (rec === null || zs === null) return NaN;
    const i = sampleAt(rec, T);
    return settings.energyZero === 'jump' && zs.jump !== null ? zs.jump[i] : zs.anchor[i];
}

function energyText(e: number): string {
    if (Number.isNaN(e)) return '— energy (no start zone yet)';
    const sp = settings.energyUnits === 'speed';
    const v = Math.round(sp ? equivSpeed(e, grav) : e);
    return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v)} ${sp ? 'u/s' : 'u'} energy`;
}

function updateHud(): void {
    if (rec === null) return;
    setText('wclock', `${fmt(Math.max(T, t0))} / ${fmt(t1)}`);
    $<HTMLInputElement>('wseek').value = String(T);
    if (settings.clean) return;
    setText('htime', fmt(Math.min(T, t1)));
    setText('hspeed', String(Math.round(Math.hypot(pose.vx, pose.vy))));
    setText('hvz', (pose.vz >= 0 ? '+' : '') + Math.round(pose.vz));
    setText('henergy', energyText(energy(pose.z, pose.vx, pose.vy, pose.vz, grav) - energyZero()));
    const st = stageAt(T);
    setText('hstage', st > 0 ? `Stage ${st}` : (T < 0 ? 'Start' : ''));
    let gap = '';
    const d = ghostGap();
    if (d !== null) {
        gap = `${d <= 0 ? '−' : '+'}${Math.abs(d).toFixed(2)} vs ${plain(ghost!.info.name)}`;
        $('hgap').classList.toggle('ahead', d <= 0);
    }
    setText('hgap', gap);
    const k = pose.keys;
    const on = (id: string, b: boolean) => $(id).classList.toggle('on', b);
    on('kw', !!(k & KEY_FORWARD)); on('ka', !!(k & KEY_LEFT)); on('ks', !!(k & KEY_BACK)); on('kd', !!(k & KEY_RIGHT));
    on('kj', !!(k & KEY_JUMP)); on('kc', !!(k & KEY_DUCK) || !!(pose.fl & FL_DUCKED));
    on('kg', !!(pose.fl & FL_ONGROUND));
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
        m.title = e.kind === 'stage' ? `Stage ${e.n + 1} at ${fmt(e.t)}` : `Checkpoint ${e.n} at ${fmt(e.t)}`;
        ticks.append(m);
    }
}

let last = 0, frames = 0;
// What the page says it did, for tools/shot.mjs (and anyone's console).
(window as any).watchState = () => ({
    frames, T, mode, playing, map: mapName, samples: rec?.n ?? 0, scene: view?.scene !== null,
    ghost: ghost ? { name: ghost.info.name, samples: ghost.rec.n, at: [gpose.x, gpose.y, gpose.z], gap: ghostGap() } : null,
    mounts: files.mounts.map((m) => m.game), status: $('wstatus').hidden ? '' : $('wstatus').textContent,
    eye: [pose.x, pose.y, pose.eyeZ, pose.pitch, pose.yaw],
    zones: zones.length, splits: [...runSplits.t].map(([s, t]) => [s, +t.toFixed(3)]), approx: runSplits.approx,
    ghostSplits: [...ghostSplits.t].map(([s, t]) => [s, +t.toFixed(3)]), error: renderError, missingObjects,
    settings: { ...settings }, energy: shown.get('henergy') ?? '', kept: { maps: maps.info(), game: gameFiles.info() },
    fromKept: lastFs?.fromKept ?? 0, missing: lastFs?.missing.size ?? 0, mapSource, builds, contextLost,
});
(window as any).watchSet = (k: keyof Settings, v: any) => { (settings as any)[k] = v; showSettings(document, settings); applySettings(k); };
(window as any).watchSeek = (t: number, m?: CamMode) => { T = t; if (m) setMode(m); };
(window as any).watchGhost = () => toggleGhost();
(window as any).watchHold = (ms: number | null) => { if (view !== null) view.holdTime = ms; };

// One bad frame must not stop the page: the loop always schedules the next, and
// a renderer that keeps throwing says so once instead of leaving a black view.
let renderError = '', missingObjects = 0;
function loop(now: number): void {
    try {
        step(now);
    } catch (e) {
        if (renderError === '') {
            renderError = String((e as Error)?.message ?? e);
            console.error(e);
            status(`The 3D view failed on this map (${renderError}). The run's numbers below still work.`);
        }
    }
    requestAnimationFrame(loop);
}

function step(now: number): void {
    const dt = last === 0 ? 0 : Math.min(now - last, 100);
    last = now;
    if (view !== null && rec !== null) {
        if (playing) {
            T += dt / 1000 * speed;
            if (T >= t1) { T = t1; setPlaying(false); }
        }
        poseAt(rec, T, pose);
        if (ghost !== null) poseAt(ghost.rec, T, gpose);
        if (mode === 'chase' && view.input.buttons & 1) {
            orbitYaw = wrap(orbitYaw - view.input.getMouseDeltaX() * 0.25);
            orbitPitch = Math.max(-80, Math.min(85, orbitPitch + view.input.getMouseDeltaY() * 0.25));
        }
        placeCamera(view);
        view.frame(dt, Number($<HTMLSelectElement>('wfov').value));
        drawOverlay(view);
        updateHud();
        drawGraph();
        frames++;
    }
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
}

function showSplits(): void {
    const sp = $('wsplits');
    sp.textContent = '';
    const mine = runSplits.t, theirs = ghostSplits.t;
    const approx = runSplits.approx || (ghost !== null && ghostSplits.approx);
    $('wsplitvs').textContent = (ghost ? `vs ${plain(ghost.info.name)}` : '') + (approx ? ' · ≈ from the zones' : '');
    let prev = 0, prevSeg = 0;
    for (const [seg, t] of mine) {
        const tr = el('tr', null);
        tr.append(el('td', null, `Stage ${seg}`), el('td', 'num', (runSplits.approx ? '≈' : '') + fmt(t)),
            el('td', 'num dim', seg === prevSeg + 1 ? '+' + (t - prev).toFixed(3) : '—'));
        const g = theirs.get(seg);
        if (ghost) {
            const d = g === undefined ? null : t - g;
            tr.append(el('td', 'num ' + (d === null ? 'dim' : d <= 0 ? 'ahead' : 'behind'),
                d === null ? '—' : (d <= 0 ? '−' : '+') + Math.abs(d).toFixed(3)));
        }
        tr.addEventListener('click', () => { T = Math.max(t0, t - 1); });
        sp.append(tr);
        prev = t;
        prevSeg = seg;
    }
    $('wsplitbox').hidden = mine.size === 0;
}

async function toggleGhost(): Promise<void> {
    const b = $<HTMLButtonElement>('wghost');
    if (ghost !== null) {
        ghost = null;
        b.textContent = 'Race the record';
        $('wghostinfo').textContent = '';
        computeSplits();
        graph = null;
        return;
    }
    if (runInfo === null) return;
    const of = runInfo;
    b.disabled = true;
    try {
        const q = new URLSearchParams({ map: of.map, track: String(of.track), leg: String(of.leg),
            style: of.style || 'clean', tier: 'combined' });
        const board = await fetchJSON(`api/map?${q}`);
        if (of !== runInfo) return;   // another recording was opened meanwhile
        const row = (board.rows || []).find((x: any) => x.rep > 0 && x.rep !== of.rid);
        if (row === undefined) {
            $('wghostinfo').textContent = 'No other recorded run on this board.';
            return;
        }
        const [info, track] = await Promise.all([fetchJSON(`api/run/${row.rep}`), fetchJSON(`api/run/${row.rep}/track`)]);
        if (of !== runInfo) return;   // another recording was opened meanwhile
        ghost = { rec: parseRec(track.rec), info };
        b.textContent = 'Stop racing';
        $('wghostinfo').textContent = `Racing ${plain(info.name)} (#${row.r}, ${fmt(info.ms / 1000)}${info.tr !== of.tr ? ', ' + (TIER_NAMES[info.tr] ?? info.tr) : ''}).`;
        computeSplits();
        graph = null;
    } catch (e) {
        $('wghostinfo').textContent = `The record could not be loaded (${(e as Error).message}).`;
    } finally {
        b.disabled = false;
    }
}

// Horizontal speed, or energy from the start, against run time: this run blue,
// the ghost gold. The playhead is drawn over it each frame.
function drawGraph(): void {
    const c = $<HTMLCanvasElement>('wgraph');
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(c.clientWidth * dpr)), h = Math.max(1, Math.round(c.clientHeight * dpr));
    if (rec === null) return;
    const span = Math.max(t1 - t0, 1e-3);
    if (graph === null || graph.width !== w || graph.height !== h) {
        graph = document.createElement('canvas');
        graph.width = w; graph.height = h;
        const g = graph.getContext('2d')!;
        const en = settings.graph === 'energy';
        const runs = ghost ? [rec, ghost.rec] : [rec];
        const zero = en ? runs.map((r) => runZero(r, r === rec && zs !== null ? zs : zeros(r, zones))) : [0, 0];
        const gr = runs.map((r) => gravityOf(r));
        const val = (k: number, i: number) => {
            const r = runs[k], v = r.v;
            return en ? energy(r.o[i * 3 + 2], v[i * 3], v[i * 3 + 1], v[i * 3 + 2], gr[k]) - zero[k] : Math.hypot(v[i * 3], v[i * 3 + 1]);
        };
        let lo = en ? Infinity : 0, hi = 1;
        for (let k = 0; k < runs.length; k++)
            for (let i = 0; i < runs[k].n; i++) {
                const y = val(k, i);
                if (y < lo) lo = y;
                if (y > hi) hi = y;
            }
        const range = Math.max(hi - lo, 1);
        const trace = (k: number, colour: string) => {
            const r = runs[k];
            g.strokeStyle = colour;
            g.lineWidth = dpr;
            g.beginPath();
            const stride = Math.max(1, Math.floor(r.n / (w * 2)));
            for (let i = 0; i < r.n; i += stride) {
                const x = (r.t[i] - t0) / span * w, y = h - (val(k, i) - lo) / range * (h - 2) - 1;
                if (i === 0) g.moveTo(x, y); else g.lineTo(x, y);
            }
            g.stroke();
        };
        if (en && lo < 0) {                 // the start's level, when the run goes below it
            g.fillStyle = 'rgba(255,255,255,.18)';
            g.fillRect(0, Math.round(h - (0 - lo) / range * (h - 2) - 1), w, 1);
        }
        if (ghost) trace(1, 'rgba(232,197,106,.7)');
        trace(0, en ? '#c9b8ff' : '#59bfff');
    }
    // The traces go onto the page once per change; the playhead is its own element,
    // moved by a transform, so a frame repaints one pixel column and not the canvas.
    if (graphShown !== graph || c.width !== w || c.height !== h) {
        if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
        const g = c.getContext('2d')!;
        g.clearRect(0, 0, w, h);
        g.drawImage(graph, 0, 0);
        graphShown = graph;
    }
    // As the canvas line was: at a whole canvas pixel, max(1, dpr) of them wide, and off
    // the canvas (not shown) at the run's very end.
    const xc = Math.round((T - t0) / span * w);
    const ph = $('wplayhead');
    ph.hidden = xc >= w;
    const tr = `translateX(${xc / dpr}px)`, wd = `${Math.max(1, 1 / dpr)}px`;
    if (ph.style.transform !== tr) ph.style.transform = tr;
    if (ph.style.width !== wd) ph.style.width = wd;
}

// The time between this run and the ghost at the same PLACE: T minus when the
// ghost was nearest to where the player is now, searched within GAP_WINDOW s of
// T so a map that doubles back cannot match the wrong pass. Splits need not
// exist (imports have none). Null when the ghost was never near.
const GAP_WINDOW = 30, GAP_NEAR = 256;

function ghostGap(): number | null {
    if (ghost === null || rec === null || T < 0) return null;
    const g = ghost.rec;
    const hi = sampleAt(g, T + GAP_WINDOW);
    let best = -1, bd = GAP_NEAR * GAP_NEAR;
    for (let j = sampleAt(g, T - GAP_WINDOW); j <= hi; j++) {
        const dx = g.o[j * 3] - pose.x, dy = g.o[j * 3 + 1] - pose.y, dz = g.o[j * 3 + 2] - pose.z;
        const dd = dx * dx + dy * dy + dz * dz;
        if (dd < bd) { bd = dd; best = j; }
    }
    return best < 0 ? null : T - g.t[best];
}

function showInfoFromRec(r: Rec): void {
    $('wtitle').textContent = `${r.head.get('owner') ?? 'A run'} on ${r.head.get('map') ?? '?'}`;
    $('wtime').textContent = r.end !== null ? fmt(r.end) : '';
    const dl = $('winfo');
    dl.textContent = '';
    dlRow(dl, 'map', r.head.get('map') ?? '?');
    dlRow(dl, 'samples', String(r.n));
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
    // Some imports carry no ground flag (KSF before ksfground) or no keys at all;
    // a stat from a column that is zero throughout is not a stat.
    let anyGround = false, anyKeys = false;
    for (let i = 0; i < r.n && !(anyGround && anyKeys); i++) {
        anyGround = anyGround || (r.fl[i] & FL_ONGROUND) !== 0;
        anyKeys = anyKeys || r.keys[i] !== 0;
    }
    const dl = $('winfo');
    if (anyGround) dlRow(dl, 'jumps', String(jumps));
    if (anyKeys) dlRow(dl, 'strafes', String(strafes));
    if (anyGround && total > 0) dlRow(dl, 'in the air', `${Math.round(air / total * 100)}%`);
}

// ---- wiring -------------------------------------------------------------------

function seekBy(d: number): void { T = Math.max(t0, Math.min(t1, T + d)); }

const HIDE: (keyof Settings)[] = ['timer', 'stage', 'gap', 'speed', 'vz', 'energy', 'keys'];

function applySettings(key: keyof Settings | null): void {
    const st = $('wstage');
    for (const k of HIDE) st.classList.toggle(`hide-${k}`, !settings[k]);
    st.classList.toggle('clean', settings.clean);
    $('wclean').setAttribute('aria-pressed', settings.clean ? 'true' : 'false');
    if (key === 'graph') graph = null;
    if (key === 'storeGB' || key === null) {
        void maps.setBudget(settings.storeGB * GB).then(showStore);
        void gameFiles.setBudget(settings.storeGB * GB).then(showStore);
    }
    shown.clear();     // a shown element may have been hidden and changed meanwhile
}

function toggleClean(): void {
    settings.clean = !settings.clean;
    saveSettings(settings);
    applySettings('clean');
}

function showPanel(open: boolean): void {
    $('wset').hidden = !open;
    $('wsetbtn').setAttribute('aria-expanded', open ? 'true' : 'false');
}

function wire(): void {
    bindSettings(document, settings, (k) => applySettings(k));
    applySettings(null);
    $('wsetbtn').addEventListener('click', () => showPanel($('wset').hidden));
    $('wsetbar').addEventListener('click', () => showPanel($('wset').hidden));
    $('wclean').addEventListener('click', toggleClean);
    document.addEventListener('pointerdown', (e) => {
        const t = e.target as Node;
        if (!$('wset').hidden && !$('wset').contains(t) && t !== $('wsetbtn') && t !== $('wsetbar')) showPanel(false);
    });
    $('wforget').addEventListener('click', async () => {
        await forgetFolders();
        $('wreconnect').textContent = '';
        $('wforget').hidden = true;
    });
    $('wclearstore').addEventListener('click', async () => {
        if (!confirm('Clear the maps and textures kept in this browser?')) return;
        await Promise.all([maps.clear(), gameFiles.clear()]);
        showStore();
    });
    $('wplay').addEventListener('click', () => {
        if (T >= t1) T = Math.max(t0, 0);
        setPlaying(!playing);
    });
    $<HTMLInputElement>('wseek').addEventListener('input', (e) => { T = Number((e.target as HTMLInputElement).value); });
    $<HTMLSelectElement>('wspeed').addEventListener('change', (e) => { speed = Number((e.target as HTMLSelectElement).value); });
    for (const b of Array.from(document.querySelectorAll<HTMLButtonElement>('[data-cam]')))
        b.addEventListener('click', () => setMode(b.dataset.cam as CamMode));
    $('wpick').addEventListener('click', () => $('wdir').click());
    $('wnative').addEventListener('click', (e) => { e.preventDefault(); void pickNative(); });
    $('wcopy').addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText($('wsteampath').textContent ?? '');
            $('wcopy').textContent = 'Copied';
        } catch {
            $('wcopy').textContent = 'Select and copy it';
        }
    });
    $('wghost').addEventListener('click', () => { void toggleGhost(); });
    const gc = $<HTMLCanvasElement>('wgraph');
    const seekGraph = (e: PointerEvent) => {
        const r = gc.getBoundingClientRect();
        T = t0 + Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * (t1 - t0);
    };
    gc.addEventListener('pointerdown', (e) => { gc.setPointerCapture(e.pointerId); seekGraph(e); });
    gc.addEventListener('pointermove', (e) => { if (gc.hasPointerCapture(e.pointerId)) seekGraph(e); });
    $<HTMLInputElement>('wdir').addEventListener('change', async (e) => {
        const list = (e.target as HTMLInputElement).files;
        try {
            if (list && list.length) await addedFiles(await files.addList(list));
        } catch (err) {
            status(`That folder could not be read (${(err as Error).message}).`);
        }
    });
    $<HTMLInputElement>('wrecfile').addEventListener('change', async (e) => {
        const f = (e.target as HTMLInputElement).files?.[0];
        if (!f) return;
        try {
            const r = parseRec(await f.text());
            runInfo = null;
            ghost = null;
            graph = null;
            setRec(r);
            computeStats(r);
            await Promise.all([loadZones(), loadMap()]);
        } catch (err) {
            status(`That recording could not be played (${(err as Error).message}).`);
        }
    });
    $('wfull').addEventListener('click', () => {
        const s = $('wstage');
        if (document.fullscreenElement) void document.exitFullscreen();
        else void s.requestFullscreen();
    });
    document.addEventListener('keydown', (e) => {
        if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
        if (e.ctrlKey || e.metaKey || e.altKey) return;     // the browser's own shortcuts
        if (e.code === 'Space') { e.preventDefault(); $('wplay').click(); }
        else if (e.code === 'ArrowLeft') seekBy(e.shiftKey ? -1 : -5);
        else if (e.code === 'ArrowRight') seekBy(e.shiftKey ? 1 : 5);
        else if (e.code === 'Digit1') setMode('eye');
        else if (e.code === 'Digit2') setMode('chase');
        else if (e.code === 'Digit3') setMode('top');
        else if (e.code === 'Digit4') setMode('free');
        else if (e.code === 'KeyH' && mode !== 'free') toggleClean();
        else if (e.code === 'Escape') showPanel(false);
        else if (e.code === 'Comma' || e.code === 'Period') {
            const i = SPEEDS.indexOf(speed) + (e.code === 'Comma' ? -1 : 1);
            if (i >= 0 && i < SPEEDS.length) { speed = SPEEDS[i]; $<HTMLSelectElement>('wspeed').value = String(speed); }
        }
    });
    $('wgl').addEventListener('wheel', (e) => {
        if (mode === 'chase') orbitDist = Math.max(40, Math.min(1200, orbitDist * (e.deltaY > 0 ? 1.1 : 0.9)));
    }, { passive: true });
    // A prop whose model could not be loaded rejects a promise noclip never
    // awaits (assertExists, "Missing object"): the prop is skipped, which is what
    // we want. Counted in watchState, since the same text is any assertExists.
    window.addEventListener('unhandledrejection', (e) => {
        if (/^Missing object/.test(String(e.reason?.message ?? ''))) { e.preventDefault(); missingObjects++; }
    });
}

async function main(): Promise<void> {
    wire();
    await Promise.all([maps.open(), gameFiles.open()]);
    applySettings('storeGB');
    showStore();
    await reconnectFolders().catch(() => undefined);
    try {
        view = new View($<HTMLCanvasElement>('wgl'), fetcher);
    } catch (e) {
        status(String((e as Error).message));
        return;
    }
    // A lost WebGL context (the browser freeing GPU memory, a driver reset) leaves a
    // black view that still "renders" thousands of empty frames a second. Say so.
    view.canvas.addEventListener('webglcontextlost', (e) => {
        e.preventDefault();
        contextLost = true;
        status('The 3D view lost the graphics card (the browser can take it back when memory runs short). Reload the page to bring it back.');
    });
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
        await Promise.all([loadZones(), loadMap()]);
    } catch (e) {
        status(`This run could not be loaded (${(e as Error).message}).`);
    }
}

void main();
