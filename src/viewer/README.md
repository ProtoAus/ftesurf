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
  textures nobody provided, `zones.ts` reads the map's zone file and infers stage
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

## Checks

    python tools/lzma_ref.py MAP.bsp > ref.txt
    npx esbuild tools/lzma_check.ts --bundle --platform=node --outfile=<tmp>/c.cjs
    node <tmp>/c.cjs MAP.bsp ref.txt            # TS LZMA against Python's

    npx esbuild tools/zones_check.ts --bundle --platform=node --outfile=<tmp>/z.cjs
    node <tmp>/z.cjs RUN.rec ZONES.json [RUN.rec ZONES.json ...]

    python tools/serve.py --maps <dir of .bsp> --rec ID=run.rec --info ID=run.json [--zones <dir of zone .json>] [--steam <steamapps/common>]
    PUPPETEER_DIR=<dir with puppeteer-core> node tools/shot.mjs "http://127.0.0.1:8825/board/watch.html#r=ID" <out> 20,eye 20,chase

`surfd/test_web.py` section 6b2 covers the route, its gate and the page's CSP.
