# P1596 claim (ftesurf-64, 17 Nov 2026)

Lex: under the HL movement modes teleports put the player half into the ground; and bhop platforms that are
func_door/func_button should not move but reset you if you do not hop off, when a reset trigger is below.
1. Teleports place Source's feet point; a GoldSrc profile's origin is the hull centre, so every placement adds
   -mins_z (trigger_teleport, _relative, point_teleport, AddOutput origin, func_bhop) -- server and client mirror.
2. A Touch Opens func_door / Touch Activates func_button moving straight down over a teleport trigger within its
   travel (~1,444 doors and buttons on 9 of 597 bhop/kz/ahop maps here) fires that teleport (timing below). Doors stay put. QC only (qwprogs + csprogs). Root C:\FTESurf-worktrees\lexlist-pool-20261117-64.

## Delivery (17 Nov 2026, LIVE)

QC main c26bcfd2. Lobbies 12/12 restarted (build.ps1 -Pi, 10 s warning): qw 931d6c00, cs ac1837fe (.prev 78a5f4c5 /
bb7e209e); both installs the same, menu f43460fe unchanged (.prev kept); tasrevd codes.txt 152 -> 153 (.pre1596).
pi_lobby_smoke on the released 0.1.48 exe against lobby 1: PASS (served cs ac1837fe, board drew, no QC error).

What shipped (after three review rounds and a delta check):
- GoldSrc profiles (ag-100/250/1000, cs16): every map placement lifts by -mins_z -- trigger_teleport, _relative,
  point_teleport, AddOutput origin, func_bhop, Momentum onehop/multihop/progress, and zone moves (SV_ZoneDestRead
  now returns the body's origin: !r, !s, !b, !m, stage resets, the destination published for prediction).
  cl_triggers.qc mirrors the teleport lift; cl_prederr's landmark rows stay unlifted. Source/HL2 hulls unchanged.
- Bhop doors as Momentum's mom_blockfix (bhop-mode maps only): a Touch Opens func_door / Touch Activates func_button
  moving straight down whose trigger brushes meet the sinking feet; reset 0.22 s after the first touch standing, at
  once on the same door again within ~1.1 s; the clock counts mover ticks (22 at 100 Hz, 15 at 66.67, any start
  tick). Held bodies skip it. Recorded as a `bhop` warp; .rec header `bhopdoors 1`; reccheck knows the key.

Measured (tools/p1596tele.py, bhop_1n5an3, door *1 -> t1 at z 96):
- ag-100: landings z 133 (feet on t1+1); `!r` stands at 100; walks off. main: teleport z 97 stuck (0.0 u walked),
  `!r` z 64 (centre on the floor). default: 97 / 64 on both builds.
- door: a 0.1 s touch keeps you; the same door again 0.3 s later resets at once; `--gamemode surf` never resets;
  main never resets.
- rendered ag-100: the teleport is predicted with 0 errors (counter live 0 -> 7); the same server with main's
  csprogs mispredicts it (1).
