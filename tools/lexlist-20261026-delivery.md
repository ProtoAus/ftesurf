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
