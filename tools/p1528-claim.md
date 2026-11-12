# P1528 claim (ftesurf-16, Claude Code, 13 Nov 2026)

Jargon, after Lex's 13 Nov feedback ("the TAS menu is bad... do not add features that do not work"): one Jargon panel (the
waypoints in order with editable X Y Z, air points in the list, undo/redo, how Jargon takes over -- at my jump, when I
leave the start zone, by itself -- Start/Arm, Stop, Continue, Camera); Continue read by the server (CSQC may not open
data/tasproj/); the keys HUD shows what a tape or Jargon pressed; one jump off the start platform; portal waypoints (a
guide's teleport between stages is flown into and through -- surf_colin_blaster_69000's main run stopped at stage 1's
portal); a stuck run names a waypoint the player moved; the finish fixes and two board rules on by default. QC only.
After fetch: origin/main has P1523-P1526; P1527 is claimed (untracked tools/p1527-legacy-movement-claim.md) => 1528.
Root C:\FTESurf-worktrees\jargon-courses-1111a (qc5 jargon-catch).

Delivered 12 Nov 22:13Z (13 Nov 09:13 local) from p1528 rebased on main 2f889242 (compiler 1f2efd06, 0 warnings):
the one Jargon panel (course and guide-run dropdowns, the waypoints as a table with typed X Y Z, air points, undo/redo,
Reset asked twice, the take-over modes, Continue read from the server, Back to playing), portal waypoints, the keys HUD
under TAS, one jump off the start, the start back-off on by default (rule 524288), the finish fixes and the two board
rules on by default, Jargon's lines at 1/8 unit, and `tas jargon field|guide|guides|drop` for binds and the harness.
Not in it: copying the human's crouch -- both test cvars (startduck: tensor2 stage 1's first ramp unreachable; rowkeys:
colin_blaster's first portal 0 of 3 with it, 2 of 2 without, probed: the cut trigger was the fall teleport).
Reviews: round 1 (server, client) found 6 + 4 defects, round 2 found 3 + 5; all fixed (deferred quirks in BACKLOG).
Checks on this build or one whose src differs only by the crouch-copy line (that arm measured separately): panel 27/27
and keys 11/11 on the task exe and on the 0.1.44 release exe (2c585d12); stream 15/0/1 on both and on the final bytes;
a key-input control with the old field input failed K3/K4 and crashed at K5 (Progs boundcheck 515), the fix passed all;
six courses at 900 s -- tensor2 stage 1 finished 0:10.905, stage 2 0:12.330, stage 5 3/7, stage 6 7/12, sandtrap2 b4 5/5
(finish missed, as its seed did before), anubis stage 1 3/6; colin_blaster main with the final settings went through
its first portal (arm K, 450 s).
Deployed: both installs via install_qc.sh (.prev/.pre1528 = P1520's qw aff0f1eb / cs 5f4536d3; C:/FTEQuake's .prev
restored from .pre1528 after -Pi's sync overwrote it), 12 lobbies via build.ps1 -Pi (nobody on any; all restarted),
live qw 9693e177 / cs 2bfa1db8 on both sides; tasrevd codes.txt 127 -> 128 (.pre1528).
