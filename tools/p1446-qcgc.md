# P1446 -- the QC tempstring collector's spikes, found with r_spikes and halved

Lex, 9 Nov: "why is my 0.1% lows so low? can they be raised?" -- P1444's r_spikes put surf_nuclear's largest spikes
in pairs of frames; this patch finds what they were, fixes it for every map, and adds the detail to r_spikes.

**Engine** (ftequakers main 74d27b5bd, tag patch-1446; ENGINE_PATCHES.md "Patch 1446"). Both installs run client exe
838cad1c (git-8584-patch-1446-0-g74d27b5bd, on P1443 + P1450); server exe and plugins unchanged. Rides the next
release. No QC change.

## What the pairs were

Frame N: 5-8 ms in "prediction" (engine CL_PredictMove); frame N+1: 5-8 ms in "QC UpdateView" -- every 15-20 s, at
whatever place on the route that was. Ruled out one at a time with r_spikes counters: entity floods (0 CSQC entity
updates in those frames), a prediction backlog (1 predicted move), PM_PlayerMove and the CSQC trigger hook (0.01 /
0.02 ms), prediction-error reports (none logged). With `r_spikes 2` the frame's busiest QC function was 0.07 ms of
self time -- the time was engine work. It was the CSQC tempstring garbage collector (Patch 1292's threaded GC): its
start copies the VM's memory into a fresh ~25 MB malloc for the worker to mark (every page faulted in during the
copy), its finish walks ~130k dead slots into a fresh 1 MB list and frees the block. PR_RunGC runs at every outermost
QC exit, so the two phases land in whichever QC call is first: prediction's hook, a packet's event, UpdateView.

The 25 MB is the replay workload (cl_status: 7.0 MiB of CSQC memory at map start); in normal play the copy is
smaller, the finish (proportional to the temp strings made, ~130k per collection) the same.

## Fix and result

The snapshot block (with the dead list in it) and the free list are kept per VM and reused. Measured on the PC
(i9-9900K / RTX 2080 SUPER), surf_nuclear's best replay at 1x, Lex's settings, uncapped, alternating builds:

| | start | finish | slowest frame holding a phase |
|---|---|---|---|
| unfixed | 4.6-6.4 ms | 3.9-7.7 ms | 7.5-12 ms |
| P1446 | 2.2-3.5 ms | 1.7-3.9 ms | 4.5-6.4 ms |

(The first collection after a map load still allocates: 5.2 ms once.) Clearing in chunks across frames was built and
dropped -- during a map load QC allocated faster than chunks cleared and the table doubled to a million slots.
Two review rounds (round 1: a teardown wait that could sleep forever, which is what hung a test build after a load).

## r_spikes additions

Per slow frame: prediction split (solids / transition / move = pmove + qc hook), physents and moves, CSQC entity
spawns/updates, collector phases; a run summary listing every collector phase; `r_spikes 2` adds the frame's three
busiest CSQC functions by self time (engine work called from QC is excluded from QC self time).

## Left

The start's copy (2-3.5 ms with a replay loaded) is one spike per collection still; fewer collections means fewer
temp strings from the HUD (~13k a second here), or marking big QC arrays with memnostrings (P763). Next 0.1% causes on
the list: water-capture frames (4-6 ms on nuclear), rare swap/present stalls, draw-call-heavy views.
Drivers: artifacts/run_spikelog.py (SL_BIN, SL_SPIKES, SL_LINES), artifacts/delivery-p1446/.
