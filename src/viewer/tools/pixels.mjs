// The 3D canvas pixel for pixel, and frames per second, page against page (Patch 839).
// The scene clock is pinned (watchHold) and the clean view is on, so a difference is
// the renderer's: each view is shot twice a second apart (h1!=h2 means the scene still
// moves, and the comparison is void), and every view must hash differently from the others.
//   PUPPETEER_DIR=<dir with puppeteer-core> node tools/pixels.mjs REC_FILE PAGE [PAGE ...]
// PAGE is under http://127.0.0.1:8825/board/ (tools/serve.py): watch.html and a copy that
// loads a control bundle. Grade the state line as tools/fps.mjs says.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const puppeteer = createRequire(path.join(process.env.PUPPETEER_DIR ?? '.', 'x.js'))('puppeteer-core');
const [recFile, ...pages] = process.argv.slice(2);
(async () => {
  for (const page of pages) {
    const profile = path.join(process.env.TEMP ?? '.', 'pixels-profile-' + Date.now());
    const b = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true,
      userDataDir: profile,
      args: ['--use-angle=d3d11', '--window-size=1400,1000', '--disable-gpu-vsync', '--disable-frame-rate-limit'], defaultViewport: { width: 1400, height: 1000 } });
    try {
      const p = await b.newPage();
      await p.goto('http://127.0.0.1:8825/board/' + page, { waitUntil: 'load' });
      await (await p.$('#wrecfile')).uploadFile(recFile);
      let ready = false;
      for (let i = 0; i < 480 && !ready; i++) {
        const s = await p.evaluate(() => window.watchState());
        ready = s.scene && s.status === '' && s.samples > 0 && s.builds > 0;
        if (!ready) await new Promise((r) => setTimeout(r, 250));
      }
      if (!ready) {        // the map never finished building: nothing below would be a measurement
        console.log(JSON.stringify({ page, VOID: 'not ready after 120 s' }));
        continue;
      }
      await p.evaluate(() => { window.watchHold(1000); window.watchSet('clean', true); });
      const canvas = await p.$('#wgl');
      const row = { page, hashes: [], fps: {} };
      for (const mode of ['eye', 'chase']) {
        for (const t of [1, 15, 30]) {
          await p.evaluate((t, m) => window.watchSeek(t, m), t, mode);
          await new Promise((r) => setTimeout(r, 3000));
          const h1 = crypto.createHash('sha256').update(await canvas.screenshot()).digest('hex').slice(0, 12);
          await new Promise((r) => setTimeout(r, 1000));
          const h2 = crypto.createHash('sha256').update(await canvas.screenshot()).digest('hex').slice(0, 12);
          row.hashes.push(`${mode}${t}:${h1}${h1 === h2 ? '' : '!=' + h2}`);
          if (mode === 'eye') {
            const f0 = await p.evaluate(() => window.watchState().frames), t0 = Date.now();
            await new Promise((r) => setTimeout(r, 6000));
            const f1 = await p.evaluate(() => window.watchState().frames);
            row.fps['T' + t] = Math.round((f1 - f0) / ((Date.now() - t0) / 1000));
          }
        }
      }
      const st = await p.evaluate(() => window.watchState());
      row.state = { contextLost: st.contextLost, error: st.error, missing: st.missing };
      const distinct = new Set(row.hashes.map((h) => h.split(':')[1])).size;
      if (st.contextLost || distinct < row.hashes.length || row.hashes.some((h) => h.includes('!=')))
        row.VOID = `views not distinct and stable (${distinct} of ${row.hashes.length} distinct) or context lost`;
      console.log(JSON.stringify(row));
    } finally {
      await b.close();
      fs.rmSync(profile, { recursive: true, force: true });
    }
  }
})();
