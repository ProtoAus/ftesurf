// Frames per second with the camera held, page against page, alternated (Patch 835).
// The frame rate is uncapped (vsync off), so a page that is CPU-bound shows its cost.
// GRADE THE STATE IT PRINTS: a lost WebGL context renders nothing thousands of times a
// second and reads as a huge win (it did once on 19 Oct, under memory pressure).
//   PUPPETEER_DIR=<dir with puppeteer-core> node tools/fps.mjs REC_FILE PAGE [PAGE ...]
// PAGE is a page under http://127.0.0.1:8825/board/ (tools/serve.py), e.g. watch.html and a
// copy pointing at a control bundle.
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const puppeteer = createRequire(path.join(process.env.PUPPETEER_DIR ?? '.', 'x.js'))('puppeteer-core');
const [recFile, ...pages] = process.argv.slice(2);
(async () => {
  const out = [];
  for (const page of pages) {
    const b = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true,
      userDataDir: path.join(process.env.TEMP ?? '.', 'fps-profile-' + Date.now()),
      args: ['--use-angle=d3d11', '--window-size=1400,1000', '--disable-gpu-vsync', '--disable-frame-rate-limit'], defaultViewport: { width: 1400, height: 1000 } });
    try {
      const p = await b.newPage();
      await p.goto('http://127.0.0.1:8825/board/' + page, { waitUntil: 'load' });
      await (await p.$('#wrecfile')).uploadFile(recFile);
      for (let i = 0; i < 240; i++) {
        const s = await p.evaluate(() => window.watchState());
        if (s.scene && s.status === '' && s.samples > 0) break;
        await new Promise((r) => setTimeout(r, 250));
      }
      const row = { page };
      for (const t of [1, 15, 30]) {
        await p.evaluate((t) => window.watchSeek(t, 'eye'), t);
        await new Promise((r) => setTimeout(r, 3000));       // textures settle
        const f0 = await p.evaluate(() => window.watchState().frames), t0 = Date.now();
        await new Promise((r) => setTimeout(r, 6000));
        const f1 = await p.evaluate(() => window.watchState().frames);
        row['T' + t] = Math.round((f1 - f0) / ((Date.now() - t0) / 1000));
      }
      const st = await p.evaluate(() => window.watchState());
      row.error = st.error || '';
      row.state = { contextLost: st.contextLost, map: st.map, mapSource: st.mapSource, status: st.status, eye: st.eye.map((x) => Math.round(x)), missing: st.missing, builds: st.builds, T: st.T };
      out.push(row);
      console.log(JSON.stringify(row));
    } finally { await b.close(); }
  }
})();
