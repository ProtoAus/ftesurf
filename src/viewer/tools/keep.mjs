// Patch 834's arm: one browser profile across reloads, so what the page keeps
// survives them. Grades the page's own watchState: where the map came from
// (mapSource), what it kept, what it read back (fromKept), what is missing.
//   PUPPETEER_DIR=<dir with puppeteer-core> node tools/keep.mjs URL OUT [GAME_FOLDER]
// OUT gets the profile (delete it after) and normal/panel/clean screenshots.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const puppeteer = createRequire(path.join(process.env.PUPPETEER_DIR ?? '.', 'x.js'))('puppeteer-core');
const [url, out, folder] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const pick = (s) => ({ status: s.status, scene: s.scene, map: s.map, mounts: s.mounts, kept: s.kept, fromKept: s.fromKept,
  missing: s.missing, mapSource: s.mapSource, builds: s.builds, energy: s.energy, clean: s.settings.clean, error: s.error });
(async () => {
  const b = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true,
    userDataDir: out + '/profile', args: ['--use-angle=d3d11', '--window-size=1400,1000'], defaultViewport: { width: 1400, height: 1000 } });
  const ready = async (p, what) => {
    const t = Date.now();
    for (let i = 0; i < 240; i++) {
      const s = await p.evaluate(() => window.watchState && window.watchState());
      if (s && s.scene && s.status === '') {
        // Textures stream in after the scene: wait until what was found and not found stops moving.
        let a = '', same = 0;
        for (let j = 0; j < 60 && same < 4; j++) {
          await new Promise((r) => setTimeout(r, 500));
          const q = await p.evaluate(() => { const w = window.watchState(); return `${w.missing}|${w.fromKept}|${w.kept.game.count}`; });
          same = q === a ? same + 1 : 0; a = q;
        }
        const f = await p.evaluate(() => window.watchState());
        console.log(what, Date.now() - t, 'ms', JSON.stringify(pick(f)));
        return f;
      }
      await new Promise((r) => setTimeout(r, 250));
    }
    const s = await p.evaluate(() => window.watchState && window.watchState());
    console.log(what, 'NOT READY', JSON.stringify(s && pick(s)));
    return s;
  };
  try {
    const p = await b.newPage();
    p.on('pageerror', (e) => console.log('pageerror', String(e).slice(0, 200)));
    await p.goto(url, { waitUntil: 'load' });
    await ready(p, 'first load');
    await new Promise((r) => setTimeout(r, 2500));   // the map's put and the manifest's save
    await p.reload({ waitUntil: 'load' });
    await ready(p, 'reload (map kept)');
    // A newer build on the server: the kept copy's version no longer matches.
    await new Promise((r) => setTimeout(r, 2000));
    const staled = await p.evaluate(() => new Promise((res, rej) => {
      const q = indexedDB.open('ftesurf-viewer', 2);
      q.onerror = () => rej(q.error);
      q.onsuccess = () => {
        const os = q.result.transaction('meta', 'readwrite').objectStore('meta');
        const keys = [];
        const c = os.openCursor();
        c.onsuccess = () => {
          const cur = c.result;
          if (cur === null) { res(keys); return; }
          if (String(cur.key).startsWith('ftesurf-maps-v1\n')) {
            keys.push(String(cur.key).split('\n')[1]);
            cur.update({ ...cur.value, v: 'an older build' });
          }
          cur.continue();
        };
      };
    }));
    await p.reload({ waitUntil: 'load' });
    await ready(p, `reload (kept version made stale: ${staled})`);
    // Two tabs keeping different maps at once: each keeps its own records.
    if (process.env.KEEP_SECOND) {
      const q = await b.newPage();
      await Promise.all([q.goto(process.env.KEEP_SECOND, { waitUntil: 'load' }), p.reload({ waitUntil: 'load' })]);
      await Promise.all([ready(q, 'second tab'), ready(p, 'first tab again')]);
      await new Promise((r) => setTimeout(r, 2500));
      await q.close();
      await p.reload({ waitUntil: 'load' });
      await ready(p, 'after two tabs');
    }
    if (folder) {
      const input = await p.$('#wdir');
      const b0 = await p.evaluate(() => window.watchState().builds);
      const t = Date.now();
      await input.uploadFile(folder);
      for (let i = 0; i < 240; i++) {
        const s = await p.evaluate(() => window.watchState());
        if (s.mounts.length > 0 && s.builds > b0 && s.status === '') break;
        await new Promise((r) => setTimeout(r, 500));
      }
      await ready(p, `after the folder (${Date.now() - t} ms from the pick)`);
      await new Promise((r) => setTimeout(r, 5000));
      console.log('kept after the folder', JSON.stringify(await p.evaluate(() => window.watchState().kept)));
      await p.reload({ waitUntil: 'load' });
      await ready(p, 'reload (no folder, textures kept)');
    }
    await p.evaluate(() => { window.watchSeek(12, 'chase'); });
    await new Promise((r) => setTimeout(r, 1500));
    await p.screenshot({ path: out + '/normal.png' });
    await p.evaluate(() => window.watchSet('graph', 'energy'));
    await new Promise((r) => setTimeout(r, 500));
    await p.evaluate(() => { document.getElementById('wsetbtn').click(); });
    await new Promise((r) => setTimeout(r, 500));
    await p.screenshot({ path: out + '/panel.png' });
    await p.keyboard.press('Escape');
    await p.keyboard.press('KeyH');
    await new Promise((r) => setTimeout(r, 800));
    const s = await p.evaluate(() => window.watchState());
    console.log('after H', JSON.stringify({ clean: s.settings.clean, graph: s.settings.graph }));
    await p.screenshot({ path: out + '/clean.png' });
    await p.keyboard.press('KeyH');
  } finally { await b.close(); }
})();
