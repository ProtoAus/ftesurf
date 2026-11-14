# P1560: no warning for materials a map never shipped (15 Nov 2026)

Lex: surf_ferros prints "2 material(s) did not resolve" -- "figure out why the texture isn't resolving and fix it,
or remove the error", and automated reporting if we need it. Task root C:/FTESurf-worktrees/reports-20261114
(arms/: bspmdl.py, mdlmesh.py, propwhere.py, meshwhere.py, misscross.py, mmrcross.py, shots1560.py, pxdiff.py,
chain19-23.sh; runs/p1560*). Engine ftequakers afe2be9ec..800f91a1d; game repo cae3eb3a..(this commit).

## Why it does not resolve

luna_tag_0.mdl, one static prop at (2842 5444 -12554), has two $cdmaterials paths (lunatag2/greek/ and
lunatag2/ELDEN RING/NORMAL AND USABLE/) and three textures: greek_rockwall01 (packed, 418 verts) and two Elden Ring
textures AET001_078_A and AET001_020_A (12 and 4 verts) that neither surf_ferros nor surf_ferros_css packs and no game
supplies. Nothing on our side can bring them back. From two corrected cameras on each panel (meshwhere.py: the
model's vertexindex is at 84, not 80 -- the first cameras were aimed by the wrong offset) control and subject frames
match apart from the banner: the panels are not a visible checker from there, so the console block (and the banner,
for players with fs_missingwarn 1 -- Lex's config has 0) was the whole symptom.

The class: tools/mapdeps.py --audit on 15 Nov, 2303 library maps: 1104 have visible content no pack supplies -- the
warning printed on about half of all maps.

## Reporting already exists

- data/missing/<map>.txt (P1460): each player's full list, local.
- The lobby report (P1382): cl_matreport sends one line a map to the lobby, data/matreport/ on the Pi (43 lines 8-14
  Nov, 30 files; three from surf_ferros).
- Offline, mapdeps.py proves per map what no pack supplies. No new reporting path; P1560 feeds that proof to the game.

## Change

- tools/mapdeps.py --unshipped PATH writes data/unshipped.txt: "<map>\t<key>" byte-sorted, every material (key as
  mat_vmt.c's VMT_ColourKey) and texture (key keeps ".vtf") no pack, mount or pakfile supplies; a model's every
  $cdmaterials candidate (mod_hl2.c names the last it tried) and a texdata name as the engine spells it, each only
  when that spelling is absent everywhere. Refuses unless every known pack is installed, indexes files and (addons)
  has its VPK. 15 Nov: 6053 names, 1196 maps, 325 KB. Gitignored generated data like matcolours.txt; release.ps1
  ships it and the Gates step refuses without it (src/release/README.md).
- hl2 plugin: mat_vmt.c loads the list (Mat_VMT_SetMap at each VBSP load, Mat_VMT_Unshipped). mod_vbsp.c's
  map-load block is developer-only when every load-time miss is listed, fs_automount_state is 0 or 1 and every game
  was found; then hl2_unresolved_visible publishes 0, which takes down cl_gfx.qc's red banner and its lobby report.
  Anything unlisted stays loud, now saying how many are unlisted instead of claiming "never shipped" (state 0 is any
  map that wants no pack, censused or not). With no list installed the pre-P1560 wording prints unchanged.
- Not shipped: drawing a listed prop skin neutral grey (nothing for "nodraw" names) instead of the checker. Built
  and reviewed, then removed: no listed skin could be shown in pixels (BACKLOG).

## Measured

- Against players' engines (mmrcross.py over the 43 lobby lines): 9 listed (surf_beyond, surf_fairy, surf_ferros,
  surf_quirky, surf_aquaflow, surf_lo_tek, surf_minimumwage); 16 unlisted with a game missing or the wanted pack
  absent; 18 unlisted in states 0/1, which stay loud -- CS:S/HL2 materials on players' installs, a map not in the
  library, surf_road_to_hell's doubled maps/ patch name, and three "materials/..." names mapdeps never meets
  (entity keys; BACKLOG).
- Lex's 5 data/missing names (misscross.py): 0 that mapdeps resolves -- no engine lookup gap seen; a thin sample.
- Rig, installed exe 796f5019, private homedirs, surf_ferros then surf_beyond:
  - list-gated build 28907f71 (chain21): with the list, no load-time block at developer 0 on either map,
    hl2_unresolved_visible 0; at developer 1 the block and "None of these ever shipped"; without the list the
    pre-P1560 wording and visible 1, the same console and cvars as the installed plugin 82fd0d3d.
  - banner, fs_missingwarn 1 (chain22): without the list the red block ("2 materials did not resolve on this map",
    "1 material ... TOOLSNODRAW") differs by 9358 / 7562 px at two fixed cameras; with it, absent.
  - shipped build e360c363 with the list (chain23, run 1): no block, visible 0; its frames match chain22's list
    frames to the FPS counter (71 / 161 px) and differ from the no-list frames by the banner (9357 / 7577 px).
    Its no-list, developer 1 and control runs were stopped by the system for low memory and not re-run.
- Reviews: four rounds (lenses: control flow, visual consequences, diagnostics; then key agreement, behaviour of
  anything unlisted, the tool). Round 1: state 0 is not "proven never shipped" (the first cut silenced engine lookup
  faults too) and particle-script names reach the same loader -- redesigned around the list. Round 2: the list did
  not ship, states 2/3 could go half quiet, a list made short of a pack, key collisions, the banner. Round 3: a dead
  8-byte missing-game test, an unguarded alias, empty packs, the release Gates step. Round 4: no medium or high.
