# P1558 claim — JARGON ramp-first openings and TAS presentation

14 Nov 2026, pi.dev session 01a1d34e, owned root jargon-sol-1113a.

This is the one active feature number, replacing the historical P1553 claim:
P1557 published before this feature was committed. Both repositories were fetched;
published headings and canonical/owned untracked pNNN files were inspected before
claiming max+1. Original test artifact labels remain unchanged.

Owner request: prefer a single opening jump toward ramp 1 rather than returning
to the start platform to bhop; preserve explicitly authored bhop regions such as
surf_prosurf bonus 4. Show the full Tool Assisted Speedrun status and purple TAS
completions for JARGON and per-player host_timescale assistance.

Scope: src/server/sv_tasautosurf.qc, sv_timer.qc, sv_saveloc.qc,
sv_rewindstate.qc; src/shared/sh_defs.qc; src/client/cl_timer.qc, cl_banner.qc,
cl_results.qc; ENGINE.txt, PATCHNOTES.md, AGENT_NOTES.md, BACKLOG.md, lextest.md,
a verification note and one engine ENGINE_PATCHES.md entry. No native engine
implementation, ranked-admission relaxation, REC grammar/version, release or
qcbuild change. Slow-only assistance must not acquire native-control ancestry
through local save restoration. Published P1550-P1557 work remains intact;
uncommitted canonical peer work is not in this source tree.

Implementation and verification are complete: final integrated three-VM build
zero warnings, acting ordinary/authored opening checks, final12-check slow-only
smoke,949/1627reader assertions and unchanged571recording corpus. Product commit
and deployment are still pending; tools/p1558-jargon-start-tas.md is the evidence
and delivery-state authority. This claim is not a deployment receipt.
