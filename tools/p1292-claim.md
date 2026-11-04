# P1292 claim

ftesurf-ac, 20261104, Lex (4 Nov: "remove all dips, next will be the 1% and 0.1% lows"): the QC tempstring
collector. Measured (P1277 probe with GC timings, surf_boreas/voyager/monolith replays): each collection copies
7-12 MB on the main thread (1.4-3.5 ms) every 2-10 s, and a full table waits for the collector (up to 6.7 ms here,
a 30 ms frame in the dip survey). Plan: the worker hands back the slots it freed so the table can grow during a
collection (no main-thread wait), and a larger table floor so collections are rarer. Threaded path only.
Files: engine/qclib/initlib.c (engine repo); ENGINE_PATCHES.md.
State: live: both installs (exe 16408c21); tag patch-1292, engine main 640c931e6.
