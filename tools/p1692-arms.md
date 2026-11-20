# P1692 retry away time -- arms and results (21 Nov 2026, worldofsurf-6f)

Rig as tools/p1643-arms.md (one dedicated server, one headless client, owned game copy), map surf_ace. `!r`, walk
out of the start (the run starts), stand, read `cmd timer`'s clock and the wall time; `cmd rec_retry` (the server
path -- a remote client's own `retry` reconnects, see AGENT_NOTES.md); wait for the run to come back; read both
again. The driver is kept in the private task root.

| Build | Case | Clock advanced | Wall advanced | Clock - wall | Chat | Practice |
|---|---|---|---|---|---|---|
| main 35b19662 (control) | retry ~3 s into the run | 3.71 s | 5.40 s | -1.70 s | run restored | 0 |
| P1692 (first cut) | same | 5.69 s | 5.40 s | +0.28 s | + "2 s away added to the clock" | 0 |
| P1692 (review 1) | same | 5.70 s | 5.40 s | +0.30 s | + "2 s away added" | 0 |
| P1692 (review 1) | retry 0.135 s into the run | 5.13 s | 4.70 s | +0.43 s | + "2 s away added" | 0 |

The positive remainder is the round-up to whole seconds (reccheck requires a whole `parkclock` gap). Review 2's two
changes (a replay refused while the charge is owed; at least 1 s) were not re-run. Not measured: the `parkclock` in
a kept `.rec` (the run never finishes), a listen-server retry through the client's own `retry`, Multi-Session after
a retry.

Reviews: three independent rounds. 1: a second retry before the charge dropped it; a two-clock bound gave an early
retry a false practice; Multi-Session could park an unrecorded run first; a missing stamp failed open. 2: a 0 s
charge from a lowered stamp; a replay could open before the charge. 3: low notes only (BACKLOG).
