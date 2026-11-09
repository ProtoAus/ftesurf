# P1442 -- the activation warm-up budget: 2 -> 6 s, with the window kept responsive

**Engine** (ftequakers main a48d1d2ba, tag patch-1442 = df1444c99; ENGINE_PATCHES.md "Patch 1442"): Sys_KeepAlive
peeks the window queue (PM_NOREMOVE) at most every 0.25 s inside GLSLWarm_MapActive and MapReady_Drain;
`r_mapready_budget` defaults to 6 and its description names Patch 1442.
**QC** (cl_hudedit.qc HE_MigrateDefaults): `r_mapready_rev` 1442 -- a config still on 2 takes 6, only when the
engine's description names Patch 1442 (older engines keep 2: their warm-up frame cannot be made longer safely).

## Why

P1441's list warms more at load (surf_quarantine: 199 permutations, 1.96 s on a cold NVIDIA cache on the PC,
i9-9900K / RTX 2080 SUPER). Under a 2 s budget a slower CPU leaves the rest to compile mid-run: a 1 s budget on the
PC (a CPU half as fast) left 93 pending -- 32 late compiles, 0.1% low 137 -> 60 fps, worst frame 25 -> 54 ms.

The budget could not simply rise: CL_MakeActive runs Shader_DoReload (0.64 s cold) and the warm-up in one frame,
and Windows ghosts a window that has not checked its queue for 5 s. Every saved config also holds the old value
(the engine writes every archived cvar, Cvar_WriteVariables), so an engine default alone reached nobody.

## Measured

`artifacts/run_hangtest.py` (HG_THROTTLE=0 HG_LIST=warmseed-stress-hang.txt, budget 10): a renamed exe (cold driver
cache) changes level to surf_quarantine with a 29,673-entry stress list, IsHungAppWindow sampled every 0.1 s:

| exe | warm-up | compiled / pending | hung during the warm-up | other hung period |
|---|---|---|---|---|
| patch-1413 | 10.0 s | 1143 / 347 | 5.4 s (5 s into the frame to its end) | 2.5 s, map load |
| patch-1442 | 10.0 s | 1120 / 370 | 0 | 2.2 s, map load |

The map-load period (CS:GO VPK mount + BSP load, ~7 s in one call for surf_quarantine's first load) is outside
this patch -- BACKLOG.

A first cut pinned the whole client to one CPU with busy loops: that starved the loader's worker threads ("receiving
map info" 61 s) and the window read hung through most of the load, so it could not isolate the warm-up.

`artifacts/run_migtest.py` (the build's csprogs/qwprogs in the fixture, r_mapready_rev 0 each arm):
P1442 exe + saved 2 -> 6, rev 1442; P1442 exe + saved 3 -> 3, rev 1442; patch-1413 exe + saved 2 -> 2, rev 0.

## Delivered

Both installs: client exe 7e7564ae (git-8569-patch-1442-0-gdf1444c99), .prev kept, 19,268 protected files
unchanged (`artifacts/delivery-p1442/`); fteqwsv64 and the hl2 plugin unchanged. The engine rides the next release;
the QC migration acts only where that engine runs.
