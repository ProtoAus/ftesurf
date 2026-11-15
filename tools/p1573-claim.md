# P1573 claim

Claude Code session acsteer-20261116-c5, 2026-11-15T18:45Z. Owner decision 16 Nov: no injected clicks, no
touchpads on the ranked board. Ranked input profile gains two reasons (in_rawinput_nolegacy must be 1,
in_rawinput_touchpad must be 0), reported by CSQC on a new `inguard` event; one-time defaults move; reccheck
knows the two new verdict words. Files: sh_defs.qc, cl_replay.qc, cl_hudedit.qc, sv_timer.qc, tools/reccheck.py.
