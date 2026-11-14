# P1553 claim — JARGON ramp-first openings and TAS presentation

14 Nov 2026, pi.dev session 01a1d34e, owned root jargon-sol-1113a.

Owner request: prefer a single opening jump toward ramp 1 rather than returning
to the start platform to bhop; preserve explicitly authored bhop regions such as
surf_prosurf bonus 4. Show the full Tool Assisted Speedrun status and purple TAS
completions for JARGON and per-player host_timescale assistance.

Scope: src/server/sv_tasautosurf.qc, sv_timer.qc, sv_saveloc.qc,
sv_rewindstate.qc; src/shared/sh_defs.qc; src/client/cl_timer.qc, cl_banner.qc,
cl_results.qc; ENGINE.txt, PATCHNOTES.md, AGENT_NOTES.md, lextest.md and one
engine ENGINE_PATCHES.md entry. No native engine implementation, ranked-admission
relaxation, REC grammar/version, release or qcbuild change. Slow-only assistance
must not gain native-control ancestry through local save restoration.

P1550-P1552 remain reserved by the published ftesurf-e7 report/crash claim.
This claim reserves only P1553. Implementation/testing is in progress; this is
not a verification or deployment receipt. Canonical peer trees remain untouched.
