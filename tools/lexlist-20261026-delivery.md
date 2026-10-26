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

## P1037 -- contexts on by default; the client leaves context-filtered triggers to the server (ftesurf-2c)

| | |
|---|---|
| QC | FTESurf main `7b3074f1` (engine log entry `3073ba6b0`; ENGINE.txt pin unchanged, comment line added). Built in a clean worktree at that commit, fteqcc `c24ede65`, 0 warnings: qwprogs `6c7adb36`, csprogs `8b8731c4`; menu `d0eb3e8a` unchanged. The commit message's `<shipping-build line>` placeholder is this table and the Verified list below. |
| Installs | 07:02Z both, no game running: qwprogs `6c7adb36` (.prev `6e28eed6`), csprogs `8b8731c4` (.prev `0e222115`); C:\FTESurf by hand copy, C:\FTEQuake by build.ps1's sync; seeded `downloads/csprogsvers/d58fbc72.dat` in both. |
| Lobbies | ~07:04Z `build.ps1 -Pi -QuakeDir <absent>` from the clean worktree: nobody on, all 12 restarted on the pair. All 12 report `fs_contexts 1` (rcon `serverinfo` on the Pi's localhost, 07:05:39Z; it read 0 on all 12 before). Smoke, lobby 1, exe `9d009302`: served csprogs `8b8731c4`, board drew, no QC error, 0 failures. |

`vbsp_contexts` is registered with default 1 beside its one read; `set vbsp_contexts 0` in a cfg turns it
off. A server process that ran P1036's progs holds the cvar as "" until restarted (its unregistered read
created it), which is why the lobbies restart. The client judges each filter twice at load and skips a
slot that passes only with contexts ignored while serverinfo `fs_contexts` is not "0" (read per frame:
the key can land after CSQC's world load); a slot with rows of its own is demoted instead.

Verified (rig, shipping build, exe `9d009302`, sv_minping 60, 3 reps each, server default unless noted):
- Control, live csprogs `0e222115` with contexts on: tealbox (walking inside the spawn teleport) 24
  prederr lines and 2516 client teleports the server refused; whitebox, 2 of 2 crossings from setspeed
  *138 into *14 predicted a (0 260 300) launch the server did not give (vz 0.00 at the crossing).
- tealbox: 0 prederr, 0 client teleports; trig summary "47 left to the server while it judges contexts".
- whitebox *138 -> *14: `ent_io` reports `vbsp_contexts 1` (the default landed), 0 setspeed fires, 0 prederr.
- Contexts 0: tealbox 0 prederr with 2712 client teleports (client and server both fail open); whitebox's
  wall-walk prederr is the old client's too (4 lines each: setspeed re-fires neither client predicts).
- A load-time read of `fs_contexts` (an earlier cut) failed exactly here: absent at world load while the
  server had it on, 2628 refused client teleports. Hence the per-frame read.
- Reviews: five rounds by an independent reviewer. A full client mirror of the contexts (ab8faa69) was
  dropped on round 1's findings: unmirrorable writers, OnJump/OnEndTouch timing, TIO_MAX overflow on 24
  maps. Then the minimal rule, its mid-map reload (removed), the per-frame gate (N1: the first replay
  precedes Trig_Frame, fixed) and the rebase. Nothing open.

Limits: those triggers act one round trip late; on servers older than P1036 (no key) the client leaves them
to the server as well. BACKLOG's P1036 section keeps the mirror's checklist. Not owner-checked (lextest).

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

## P1042-P1048 -- hourglass water and frame rate, goldsrc2 crates/spark/panel, orgrimmar smoke

| | |
|---|---|
| Engine | ftequakers main `c7dc90bd3`, annotated tag `patch-1047` (P1045 plugin, P1047 GL client; log entries for P1042-P1048). Built from the tag: exe `e28907a1` (`git-7899-patch-1047-0-gc7dc90bd3`, 16 hits, one string), hl2 plugin `36cea9c8`. |
| QC | FTESurf main `b39aa42a` (pin, notes, lextest). Built in the clean worktree, 0 warnings: qwprogs `53f0eddd` (P1048), csprogs `7bdd49b1` (P1044, P1046), menu `d0eb3e8a` unchanged. |
| Installs | 07:52:15Z exe/plugin both (backups `*.pre1047-20261026T075215Z` = `9d009302` / `2bfd4b97`); 07:53:59Z qwprogs/csprogs both (.prev `6c7adb36` / `8b8731c4`), csprogs cache seeded (`f569cde9.dat`), `cfg/maps/entfix_bhop_goldsrc2.cfg` `8e2233e4` in both. `C:\FTESurf\ftesurf\data\mapdeps.txt` +29 lines through tools/mapdeps.py --update-map (25 maps; backup in the p1035deploy root). |
| Lobbies | 07:54:10Z entfix on the Pi (game `cfg/maps`, under the sweeper's flock; no lobby on goldsrc2); then `build.ps1 -Pi -QuakeDir <absent>`: nobody on, all 12 restarted on `53f0eddd`/`7bdd49b1`. Smoke, lobby 2, the new exe and plugin: 0 failures. |

Verified (rig; binaries or progs swapped and restored per arm):
- P1047: hourglass s3 at Lex's r_renderscale 2: 80 -> 407 fps (frame 12.49 -> 2.45 ms, GPU 10.1 -> 1.1),
  r_instancing 2 "cannot join" 81 -> 0; props pixel-identical CPU against GPU skinned and instancing on
  against off; surf_imaginarium (153 animated props) 178 -> 191 fps, same picture; knife and USP identical.
- P1045 + P1042: hourglass saves 1 and 4 at hl2_refract 1: without TF2 the old plugin streaks the screen edge
  and ghosts the rocks, the new one is clean; with TF2 mounted (fs_automount_state 1) the water ripples.
- P1046 + P1048: goldsrc2 at the spark: the panel is on the wall and sparks continuously; the deployed build
  showed bare wall and a spark every few seconds.
- P1044: orgrimmar save 3: grey smoke columns over the braziers (emit_list: 1 look, answering) where the
  deployed build drew dots.
- P1043: 39 func_physbox removed (engine applier on the real lump and in the rig), nothing else.
- Reviews: P1043 one round (no route opens); P1044 two; P1045 four; P1046 two; P1047 three; P1048 none yet
  (two maps, collision moves to where Source has it).

Limits: SKELETAL|INSTANCED is only proven on this PC's RTX 2080 SUPER (a failure turns skinned runs off, not
instancing); spark timing is a fixed beat; orgrimmar's smoke waits on a Momentum comparison. Not owner-checked.

P1048 review (after deploy): nothing to roll back. Correction to the commit's wording: only goldsrc2's *80
(no origin key) turned about the world origin; deathrun_forest's 8 have origin keys and turned about their
own. There, *149 now stands 16x192x96 on the tp28->tp29 line, as in Source. The review's follow-ups are P1049:
func_conveyor (18 rotated solid on 6 maps; direction comes from movedir) and func_illusionary (25 on 2 maps)
drop their angles as Source's do, and ent_view's hull overlay draws those classes unrotated. The browser run
viewer still applies map angles to every entity (BACKLOG).
P1049 deployed 08:08:58Z both installs (qwprogs d6497c53, csprogs ad9f518c, .prev 53f0eddd/7bdd49b1, cache
seeded), then all 12 lobbies (nobody on); smoke, lobby 2: 0 failures. Main 6b59573a.
