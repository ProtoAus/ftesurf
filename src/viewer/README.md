# The 3D run viewer (Patch 825)

`surfd/web/watch.html#r=<replay id>` plays a board run in the browser: the map
rendered by noclip.website's Source renderer, the camera driven by the run's
recording, and the run's numbers beside it. The board's run page links to it
("Watch in 3D").

## Build

    cd src/viewer
    npm ci
    npm run typecheck
    npm run build          # writes surfd/web/watch.js (committed: surfd ships it)

`node build.mjs --dev` writes an unminified bundle with an inline source map. The
build is deterministic for a given source tree and esbuild version (pinned in
package.json), and it prints the bundle's sha256.

## Where things come from

- `src/` is ours: `rec.ts` reads FTESURF-REC, `playback.ts` interpolates it as
  `tools/watchtrace.py` (cl_watch.qc's model) does, `view.ts` is the frame loop,
  `files.ts` reads the viewer's own game folder, `missing.ts` stands in for
  textures nobody provided, `store.ts`, `handles.ts`, `settings.ts` and `energy.ts` are
  Patch 834's (below), `zones.ts` reads the map's zone file and infers stage
  times from it, `world.ts` draws zones, the run line and the bodies into the 3D
  view (Patch 829), `main.ts` is the page.
- `vendor/noclip/` is a copy of the import closure of noclip's
  `SourceEngine/Main.ts` (MIT, LICENSE inside), made by
  `python tools/vendor.py <noclip checkout>`. `vendor/noclip/UPSTREAM.txt` names
  the commit and each file's digest. Do not edit it; change `stubs/` or the
  roots in `tools/vendor.py` and re-vendor.
- `stubs/` replaces upstream modules the viewer does not need (noclip's UI,
  debug panels, WebGPU backend, shader editor) and its Rust/wasm crate:
  `stubs/rustlib.ts` is TypeScript LZMA, inflate and a convex hull.

## What the server sends

`/board/api/run/<rid>/track` (surfd `web_run_track`, `recplot.track`) is a filtered
FTESURF-REC: the run page's header allowlist plus `eye`, 11 sample columns, the
timer/snap/ride records. Same gate as `/board/api/run/<rid>`. `src/rec.ts` reads it
and a whole .rec from disk alike.

## Maps and textures

The BSP comes from the viewer's game folder when one was picked, else from
`https://play.proto.bar/maps/<map>.bsp` (needs CORS there and on R2; see BACKLOG).
Valve content (CS:S, HL2) only ever comes from the viewer's own disk, read by VPK
slices. What is still missing is drawn as a flat colour from its name.

## Zones and stage times (Patch 829)

The zone file is the one the game downloads,
`https://play.proto.bar/ftesurf/maps/zones/local/<map>.json`; a map without one
draws no zones and infers nothing. A run whose recording has no `split` records
(every import) gets its stage times from the first touch of each stage zone in
order, shown with ≈; the touch test is the game's (`Zone_BoxInside`), because
one region in ten is concave. `tools/zones_check.ts` compares that inference with
the recorded splits: 52 of 52 within 0.05 s on 19 Oct, splits at a restart not
compared. The surf_666 AnnA/p426 harness fixtures were made on another zone set
and are left out.

World drawing goes through noclip's DebugDraw on the main view's colour and depth
(the `onWorldPasses` patch in `tools/vendor.py`), so what is behind the map is
drawn at 15%.

## Display settings, energy, what is kept (Patch 834)

`settings.ts` binds every `data-set="<key>"` control in watch.html (the Display panel
inside the stage, so it works in full screen, and the storage controls in the files card)
and remembers them in localStorage. The clean view (H) hides the HUD, labels, run line
and zones and keeps the bodies. Energy (`energy.ts`) is the game's `Strafe_Energy`,
z + |v|²/2g, from `hud_energy_ref`'s two zeros: the ground under the last jump (default;
before the first jump it follows the ground) or the start zone's floor; gravity 800 unless a
local .rec's `pmpin` says otherwise. A recording with no ground flags (some imports) can
only use the start.

`store.ts` keeps, in Cache Storage: downloaded maps (one version per map, matched to the
download's Content-Length and Last-Modified; both are readable after the redirect to R2, and
the signed URL changes per request, so the browser's own cache never matches) and every
file a map read from the visitor's games (`MapFileSystem`: pakfile, then the games, then
what was kept). Each store is trimmed least-recently-used to its budget. `handles.ts`
remembers folders picked with showDirectoryPicker (never under Program Files, which Chrome
refuses). Measured 19 Oct on the PC: picking Counter-Strike Source lists 21,845 files in
5.1 s; all of `common`, 300,487 files in 96 s, of which `files.ts`'s KEEP filter keeps
8,700.

## Frame time (Patch 835)

On heavy maps the viewer is CPU-bound in noclip's per-frame JavaScript: a canvas twice the
size costs at most 6%, and our own drawing (world, graph, HUD, labels) is about 0.45 ms a
frame. On surf_demise `gatherLiveSets` was 42% of the CPU. Five vendor patches (A-E in
tools/vendor.py) give the same visible sets from less work: +16% (surf_beginner) to +94%
(surf_boreas), surf_demise playback 62 -> 92 fps, pixels byte-identical on 12 views. Patch B
(the water check reusing the main view's set) only applies with one BSPRenderer, which is all
this viewer makes. `tools/fps.mjs` is the A/B: vsync off, camera held, pages alternated. GRADE
ITS STATE LINE: a lost WebGL context renders nothing thousands of times a second.
Patch 839 moves a static prop with no material proxy only when a view draws it (+11..+16%
on surf_demise); `tools/pixels.mjs` checks such a change pixel for pixel with the scene clock
pinned (`watchHold`).

## Checks

    python tools/lzma_ref.py MAP.bsp > ref.txt
    npx esbuild tools/lzma_check.ts --bundle --platform=node --outfile=<tmp>/c.cjs
    node <tmp>/c.cjs MAP.bsp ref.txt            # TS LZMA against Python's

    npx esbuild tools/zones_check.ts --bundle --platform=node --outfile=<tmp>/z.cjs
    node <tmp>/z.cjs RUN.rec ZONES.json [RUN.rec ZONES.json ...]

    python tools/serve.py --maps <dir of .bsp> --rec ID=run.rec --info ID=run.json [--zones <dir of zone .json>] [--steam <steamapps/common>]
    PUPPETEER_DIR=<dir with puppeteer-core> node tools/shot.mjs "http://127.0.0.1:8825/board/watch.html#r=ID" <out> 20,eye 20,chase

`surfd/test_web.py` section 6b2 covers the route, its gate and the page's CSP.
