// Screenshots of the run viewer in a real browser (Chrome or Edge, with its GPU).
//   node tools/shot.mjs URL OUTDIR [t,mode | ghost ...]     e.g. 12,eye ghost 30,chase
// Needs puppeteer-core installed in the directory PUPPETEER_DIR names (it is not
// a viewer dependency). Prints the page's console, watchState() after load and at each
// shot, and the WebGL renderer, so a black frame says why.
import { existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const puppeteer = createRequire(path.join(process.env.PUPPETEER_DIR ?? '.', 'x.js'))('puppeteer-core');

const [url, out, ...shots] = process.argv.slice(2);
// Chrome first: headless Edge 155 exits at once on this PC, with no output.
const browsers = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
];
const exe = browsers.find((p) => existsSync(p));
mkdirSync(out, { recursive: true });

const browser = await puppeteer.launch({
    executablePath: exe, headless: true, dumpio: !!process.env.SHOT_DUMPIO,
    userDataDir: path.join(out, `profile-${Date.now()}`),
    args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--window-size=1400,1000'],
    defaultViewport: { width: 1400, height: 1000 },
});
try {
const page = await browser.newPage();
page.on('console', (m) => console.log(`[console.${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => console.log(`[pageerror] ${e.stack ?? e.message}`));
page.on('requestfailed', (r) => console.log(`[requestfailed] ${r.url()} ${r.failure()?.errorText}`));
await page.goto(url, { waitUntil: 'load' });

const renderer = await page.evaluate(() => {
    const gl = document.createElement('canvas').getContext('webgl2');
    const ext = gl && gl.getExtension('WEBGL_debug_renderer_info');
    return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'no webgl2';
});
console.log(`renderer: ${renderer}`);

const t0 = Date.now();
let st;
for (;;) {
    st = await page.evaluate(() => window.watchState && window.watchState());
    if (st && st.status === '' && st.scene && st.frames > 30) break;
    if (Date.now() - t0 > 60000) break;
    await new Promise((r) => setTimeout(r, 500));
}
console.log(`loaded after ${Date.now() - t0} ms: ${JSON.stringify(st)}`);

for (const s of shots.length ? shots : ['5,eye']) {
    if (s === 'ghost') {   // race the record from here on
        await page.evaluate(() => window.watchGhost());
        await new Promise((r) => setTimeout(r, 2000));
        continue;
    }
    const [t, mode] = s.split(',');
    await page.evaluate((t, m) => window.watchSeek(Number(t), m), Number(t), mode);
    await new Promise((r) => setTimeout(r, 1500));
    const after = await page.evaluate(() => window.watchState());
    const file = path.join(out, `shot_${t}_${mode}.png`);
    await page.screenshot({ path: file });
    console.log(`${file}: ${JSON.stringify(after)}`);
}
} finally {
    await browser.close();   // a stray headless browser holds its profile and memory
}
