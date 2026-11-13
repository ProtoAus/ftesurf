# P1519 claim (ftesurf-16, Claude Code, 12 Nov 2026)

Jargon's stream view and the 12 Nov batch on top of P1483: the simple panel (course buttons that stop a run to switch,
"Jargon surfs <course>", "I start it -- Jargon takes over at my jump" for a course, Continue, Stop, Back to playing,
Camera first person / chase / overview, Lines), the chase camera (tas_viz_cam 2), `tas jargon go|arm|stop|play|course|cam`,
a course start ending a run still going, prediction-error reports quiet under TAS/Jargon, and the day's opt-in
experiments (start fixes, start crouch, rideout, launch, zigzag, free, ...) off by default. QC only.
After fetch: QC origin/main 59a52adf (max P1516; untracked peer claim p1512) => 1517; P1517 (plane-selected) and P1518 (HID namespaces) then landed on main from other sessions while this claim sat untracked in C:\FTESurf	ools, so this patch is P1519.
Root C:\FTESurf-worktrees\jargon-courses-1111a (qc5 jargon-catch, delivery worktree deliver2).

Delivered 12 Nov 04:41Z from main e80f0351 (compiler 1f2efd06, 0 warnings) after five review rounds (round 1 a full read, rounds
2-5 each on the last fix commit) and the stream stress on the delivery build (12 pass; its 2 fails were stage 1's
seed-dependent stretch 1 under an unseeded test, the panel steps all passed): both installs via install_qc.sh
(.prev/.pre1519 = P1512's cs 957ddec3 / qw de63efd3), 12 lobbies via build.ps1 -Pi (nobody on; all restarted),
cs c4772add / qw 7c80108b live on both sides; tasrevd codes.txt 125 -> 126 (.pre1519).
