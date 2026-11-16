# P1597 claim -- ftesurf-a8 (was ftesurf-31/48), 17 Nov 2026

Lobbies move to terms version 9 (Lex: yes, 17 Nov): FS_TERMS_ONLINE 9 for qwprogs and csprogs too
(src/shared/sh_defs.qc drops the #ifdef MENU split from 152fe70d). A player whose stored answer is
older than 9 (launchers before 0.1.48, or not yet re-accepted) loses ranked uploads until they accept.
Files: src/shared/sh_defs.qc; docs PATCHNOTES, AGENT_NOTES, lextest, tools/p1597-delivery.md.
Deploy: lobbies qwprogs+csprogs, both installs, tasrevd codes.txt.
