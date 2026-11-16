# P1597 claim -- ftesurf-a8 (was ftesurf-31/48), 17 Nov 2026

Lobbies move to terms version 9 (Lex: yes, 17 Nov): FS_TERMS_ONLINE 9 for qwprogs and csprogs too
(src/shared/sh_defs.qc drops the #ifdef MENU split from 152fe70d). A player whose stored answer is
older than 9 (launchers before 0.1.48, or not yet re-accepted) loses ranked uploads until they accept.
Files: src/shared/sh_defs.qc; docs PATCHNOTES, AGENT_NOTES, lextest, tools/p1597-delivery.md.
Deploy: lobbies qwprogs+csprogs, both installs, tasrevd codes.txt.

## Delivery (17 Nov 2026, LIVE)

QC main f5efb712 (b2e600cc + sh_defs.qc's single FS_TERMS_ONLINE 9). Lobbies 12/12 restarted empty (build.ps1 -Pi
from the task worktree, 10 s warning): qw fb3df470, cs 76a4e222 (.prev 931d6c00 / ac1837fe); both installs the same
(copied into C:\FTESurf by hand with .prev), menu f43460fe unchanged; tasrevd codes.txt 153 -> 154 (.pre1597).
No backend change: social.py takes consent >= 8.

Measured (tools/p1597terms.py, local game per stored answer, the server's own `cmd timer` line):
- f5efb712 progs: answer 8 -> recorded 0 (needs 9); answer 9 -> 9 (needs 9); rec_terms read 8 / 9.
- control, the installed pre-1597 progs (931d6c00 / ac1837fe): 8 -> 8 (needs 8); 9 -> 8 (needs 8).
- pi_lobby_smoke on the released 0.1.48 exe (af6a445c) against lobby 1: served cs 76a4e222, board drew, no QC error.
- A real "Play online" in the 0.1.48 menu records 9: C:\FTESurf's data/consent.txt reads version 9, accepted
  20261117-003130. (So p647boot's unattended failure of that step on 16 Nov is in the arm, not the menu; its cause is not traced.)
