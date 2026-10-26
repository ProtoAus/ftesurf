# Lex's list of 26 Oct -- ftesurf-63's deliveries

Times UTC. Earlier items from this list (P1029 noclip speed, P1030 exit-sign depth test, P1034 animated
sprites) are recorded in tools/ceaseless-delivery.md beside ftesurf-2c's work.

## P1035 -- env_sprite flipbooks at their own framerate

| | |
|---|---|
| Engine | ftequakers main `a6b66bef3`, annotated tag `patch-1035` (on patch-1034 `1f1a1c29e`). hl2 plugin `dea76f87`; exe unchanged (`8815a19b`). |
| QC | FTESurf main `2c3e8028` (pin, notes), built in a clean worktree at that commit, fteqcc `c24ede65`, 0 warnings: csprogs `0e222115`; qwprogs `4fd0fa49` and menu `d0eb3e8a` unchanged (byte-identical to deployed). |
| Installs | 03:39:27Z both, no game running: fteplug_hl2_x64.dll `dea76f87` (.prev `b52fb356`), csprogs `0e222115` (.prev `9c249d01`), seeded `downloads/csprogsvers/46e83d63.dat`. |
| Lobbies | ~03:45Z `build.ps1 -Pi -QuakeDir <absent>` from the clean worktree: nobody on, csprogs `0e222115` live (previous pair .prev), all 12 restarted. Smoke `tools/pi_lobby_smoke.py`: lobby 2 on the current exe + P1035 plugin, lobby 3 on the 0.1.29 exe + plugin -- served csprogs hashes to the build, board drew, no QC error, 0 failures each. |

Verified (conbridge, hash-swapped plugin + csprogs, restored after each arm):
- bhop_goldsrc2: exit1's shader `vmt/animated#ANIMRATE=40`, `hl2_spranim` lists it; exit1 region diff 4.97
  against a static wall 0.01.
- A real `cfg_save` dump line (`set hl2_sprite_framerate "1"    //<description>`) exec'd on the patch-1034
  plugin: exit1 drawn and cycling at 10 (4.95 / 0.00). The first gate (cvar value, then description)
  failed exactly this; review found it. An alias named hl2_spranim on patch-1034: rate 10, no prefixed name.
- surf_tequila, matched shot (same setpos/angles): the prefixed single-frame glow04 (rate 20) is
  pixel-identical to the deployed build (mean 0.0).
- An apparent regression on surf_quarantine (a black box at a setpos) was the camera in the void: the
  matched control on the deployed build shows the same box.
- Reviews: two rounds by an independent reviewer (round 1: the dump-replay hole, framerate 0, miss census
  name; round 2: nothing blocking, the list-reset nit -> BACKLOG).

Limits: `hl2_spranim`'s list never resets; SF_SPRITE_ONCE loops (BACKLOG). Not owner-checked (lextest).

## P1036 -- response contexts (server half; default off)

| | |
|---|---|
| QC | FTESurf main 20b91e29, 4e7f66bf, dfd97d43, 7c59296c (ENGINE.txt patch 1036; engine log entry b35a02649). Built in a clean worktree at 7c59296c, 0 warnings: qwprogs `2884aeb7`; csprogs `0e222115` and menu `d0eb3e8a` unchanged. |
| Installs | 04:14:37Z both, no game running: qwprogs `2884aeb7` (.prev `4fd0fa49`). |
| Lobbies | `build.ps1 -Pi -QuakeDir <absent>` from the clean worktree: nobody on, all 12 restarted on `2884aeb7`. Smoke, lobby 2, current exe: 0 failures. |

`vbsp_contexts` defaults to 0, the fail-open that shipped: no player-visible change until ftesurf-2c's
P1037 client mirror ships and switches it on (BACKLOG). Then bhop_2shiny2shuckle's stage-2 door needs
flint and iron, and bhop_tealbox stops teleporting players at spawn every tick (P1037's measurement).

Verified (rig, bhop_2shiny2shuckle, qwprogs swapped and restored; the save the arm made was removed):
- `lump: last edict #1357` on the deployed build and the new one at 0 and 1 (no renumbering).
- Plates add rr and rl; respawn clears them; sl_load restores them; at 1 the stage-2 door stays shut
  (context filters 0 pass / 504 fail, no env_shake), at 0 it opens as before.
- serverinfo fs_contexts 0 / 1 (server console); a save at 0 has no `contexts` line, at 1 the marker and both entries.
- test_reccheck 924 checks, 0 failed. Three review rounds (fidelity; consequences): the edict renumbering
  at 0 (fixed by SV_LateStash), saves/rewinds/retry carry contexts, the .rec header key, matcher gaps.

Limits: contexts are not cleared at a run's arm (shared with targetname; BACKLOG); "@/" regex values.

## P1038, P1039, P1040 -- grass, untextured materials white, noclip speed prederr (engine)

| | |
|---|---|
| Engine | ftequakers main, annotated tag `patch-1040` at `b7e3a676f` (log entries; code a92dad4b7..c1caf049c), P1041's log entry `386b489b0`. Built from the tag with SVN_VERSION `git-7891-patch-1040-0-gb7e3a676f` (16 hits, one string): exe `9d009302`, hl2 plugin `2bfd4b97`. |
| Installs | 05:46:13Z both, no game running: `C:\FTESurf\ftesurf64.exe` and `C:\FTEQuake\fteqw64.exe` `9d009302` (backup `.pre1040-20261026T054613Z` = `8815a19b`), both `fteplug_hl2_x64.dll` `2bfd4b97` (backup = `dea76f87`). Lobbies need neither (all three are client-side). |

Verified (rig, binaries swapped and restored per arm):
- P1038: bhop_monster_jam 7,700 objects, 62 cells in 6 ms, 7 drawn at Lex's save; monster_jam ->
  bhop_blacktop -> monster_jam in one session 62 / 186 / 62 cells, drawn on return; vid_restart rebuilds;
  surf_castle 279,380 objects. Library: 66 maps, 864,045 objects. Four review rounds (shared cell names
  after per-map names hit Sys_Error on three dense maps; 1024-unit cells; fast-sprite centring; never
  building into a loaded entry; tag covers the material).
- P1039: surf_bossfight at Lex's save 2, the plugin's "draws the missing checker" lines 3 -> 0 on the
  final plugin. Three review rounds (the own-name check matches the image search; Modulate, self-illum,
  water ALPHA only on vmt/water).
- P1040: hosted bhop_monster_jam, noclip, +forward, pm_noclipspeed 4/6 sixteen times at 0.3 s: installed
  exe 18 prederr lines, this exe 0. A first cut (client reads the cvar) measured 19 -> 16 and was dropped.

Limits: model-type detail objects not drawn (1,342 on 2 maps), no sway; a material with no $basetexture
but a same-named texture still uses it; Shift+wheel on a remote lobby untested. Not owner-checked (lextest).

## P1041 -- props honour rendermode/renderamt and the Alpha input

| | |
|---|---|
| QC | FTESurf main 486e2f57 + 6115ff28 (follow-up), records 37bc2d39. Built in the clean worktree at 37bc2d39, 0 warnings: qwprogs `6e28eed6`; csprogs `0e222115` and menu `d0eb3e8a` byte-identical to deployed. |
| Installs | 05:59:22Z both, no game running: qwprogs `6e28eed6` (.prev `2884aeb7`). |
| Lobbies | `build.ps1 -Pi -QuakeDir <absent>` from the clean worktree: nobody on (a row for each of the 12, all 0), both .new files hash to the build, all 12 restarted on `6e28eed6`. |

Verified (rig, surf_hourglass at Lex's save 2, qwprogs swapped and restored): near-white pixels 15,093
-> 261 on the shipping build (15,103 -> 273 on the first cut); the vortex draws without the square. One
review round (control flow, consequences): no defect; nothing but drawing reads the state, collision is
set before it. Leftovers in BACKLOG (missing renderamt key, a Disabled solid prop's collision, func_brush).
