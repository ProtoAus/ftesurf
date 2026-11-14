# P1567 claim: a sent save carries its run ("With help")

Claimed by ftesurf-16 [338cfe], 2026-11-14T23:20Z. Task root C:\FTESurf-worktrees\lexlist2-20261115-16.

Lex, 15 Nov: a shared save always carries the sender's run (segments, demo line); a run finished from it
gets a "With help" status, and the sender's segment is tagged with their name (coloured on the demo
timeline). Design: ROADMAP.md "Sending a save with its run". Touches cmd share (server + client), the
save/resume path, the .rec header, reccheck.py, and the board's status.

Renumbered from P1565 (2026-11-14T23:45Z): P1565 was already the server angle-context patch (b723f1aa).
