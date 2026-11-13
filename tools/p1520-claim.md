# P1520 claim (ftesurf-16, Claude Code, 12 Nov 2026)

Jargon follow-ups to P1519 (QC only): the 2D lines (replay path, world lines, trails, Jargon's) draw under the HUD and
every panel (Lex: they covered it); the start back-off (tas_jargon_startfix) acts on heading error only (stage 5's
433 u lateral start lost its jump); and, if the stage 6 bench shows it, boards that must be landings on THAT ramp --
near-twin faces told apart (surf_tensor2 stage 6's ramps 2 and 3 are 7 deg apart) and a slide-on not counted.
After fetch: origin/main 98b2b5b8 (max P1519, no P152x in remotes, worktrees or untracked claims) => 1520.
Root C:\FTESurf-worktrees\jargon-courses-1111a (qc5 jargon-catch, delivery worktree deliver2).

Delivered 12 Nov 09:20Z (20:20 local) from main 24e5ff38 (compiler 1f2efd06, 0 warnings): the lines-under-HUD change,
its review fix (the lines' labels, Line_FrameEnd, go under the HUD with them), the start back-off on heading only, and
comments. The board rules (near-twin faces, landed-only, boardway) are NOT in it: still test cvars on the experiment line.
Reviews: round 1 (full diff) found the labels left over the HUD, a one-frame energy-zero lag (known, kept) and a stale
engine citation; round 2 (the fix) found no code defect, only the citation (now engine function names).
Checks on this exact build (cs 5f4536d3): the stream stress (rigs stream5: every panel step passed) and a trail run
(stream6, hud_trail 1): the trail's numbered marks draw, and the speedometer's digits cover the trail where it crosses
them (cropped 1:1). Its one fail, stage 1's stretch 1 inside 150 s, is that search's own variance: stream5, same build,
passed it; P1520 changes no search with tas_jargon_startfix off.
Deployed: both installs via install_qc.sh (.prev/.pre1520 = P1519's qw 7c80108b / cs c4772add; C:/FTEQuake's .prev
restored from .pre1520 after -Pi's sync overwrote it), 12 lobbies via build.ps1 -Pi (all empty; all restarted), live
qw aff0f1eb / cs 5f4536d3 on both sides; tasrevd codes.txt 126 -> 127 (.pre1520).
