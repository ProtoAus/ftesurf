# P1643 start rest -- arms and results (20 Nov 2026, worldofsurf-4b)

Rig: one dedicated server + one client from an owned game copy, client in a headless nested labwc, driven over the
client's stdin; engine as installed 20 Nov (ftesurf64 9b2565db, fteqw-sv64 295bfab8), map surf_ace, sv_cheats 0.
Control = QC at the base commit; fixed = this patch (qwprogs c8294e59 before the records commit); "rule off" = the
first cut with `+set run_startrest 0`. Verdicts are `cmd timer`'s own lines (`timer: <state>`, `practice N`,
`armstate`, `dirty`, `rest: rule R rested N placed N unrested N prerest N`) and the server's `starts:` line. The
driver and the zone fixtures are kept in the private task root.

| Arm | Gesture | Control | Fixed |
|---|---|---|---|
| H | `!r`, walk off the start platform | running, practice 0 | running, practice 0 |
| U | `!r`, walk on; the body later falls through a second start region and leaves it without landing | running, practice 0 | armed `unrested 1`, then running, practice 1, "unrested start"; after the map's fail teleport armed, practice 0, rested 1 |
| S | a start region over the spawn room; hold jump and respawn | -- | first poll armed, `rested 1` (the first cut read `rested 0 unrested 1` here) |
| M1 | noclip on/off in the box, then `!r` | -- | placed 1; after `!r` placed 0, dirty 0 |
| M2 | setpos out of the box and back (run_prestrafe_time 5) | armed, armstate 1, dirty 0 | armed, armstate 3, dirty 1, placed 1 |
| M3 | `startmark set` there, then `!r` | "set zone 0"; `!r` there dirty 0 | "set zone 0 ... (after noclip or a teleport: runs from it are practice)"; `!r` there dirty 1 |
| M4 | setpos out and back again, `sl_save`, `!r` | `!r` lands on the save (x -1500), dirty 0 | state.txt `dirty 1`, `placed 1`; `!r` lands on the map's spot (x -1632), dirty 0 |
| M5 | 6 s standing | dirty 0 | dirty 0, placed 0 |
| T | tools/tournament_playtest.py --smoke --round-end (hold -> GO -> run) | starts happen | 4 starts, each `rested 1 ... unrested 0` |

| L1 | walk a little from the `!r` spot, `sl_save` (B); setpos out and back, `sl_save` (C); `!r` | lands on C (x -1500) | B's state.txt `placed 0`, C's `placed 1`; `!r` lands on B |
| L2 | jump (restarts the ground clock), load C | -- | loads (the review-2 build: "that save changed on disk"); placed 1 |
| L3 | `!r`, noclip on/off, load B | -- | placed stays 1 (the review-2 build: 0) |
| L4 | delete B, `!r` | -- | the map's spot (x -1632): C's column moved with its row |
| L5 | `sl_saveview` at a typed spot, load it | -- | state.txt `placed 1` (position-only); placed 1 |
| L6 | `zone_goto` an END, then `!m` | -- | placed 1; after `!m` placed 0 |
| L7 | `sl_saveat` in a clean run; again after a setpos in the run | -- | state.txt `placed 0`; `placed 1` |
| L8 | run_startrest 0, `startmark set` in the air | -- | set (the review-2 build: "stand on the ground") |
| K | save B on the floor a short walk from the `!r` spot, A in the air (z 3281) and an sl_saveview point V, delete all three `placed` lines, reload the map, `!r`, load A, B, V | round 4: `!r` at the map's spot, every load raises; round 5: V loads clean | `!r` lands at A snapped to the floor (z 3232); load A says "not a clean start spot", placed 1; B clean, placed 0; V raises, placed 1 |
| P | hop in place in the start (hopped start: practice, no latch), run out, `sl_saveat 6` while running | the row reads `placed 1` | the row reads `placed 0` |

The first cut (rule off) read as control in U and M2 (practice 0, dirty 0), so the cvar is the whole rule.
Both builds print "run cancelled (back in the start)" in U, so the second region did arm on each.

Arms that measured nothing, and why: U read once after the fall saw the attempt the map's fail teleport had
re-armed (now it polls); S with a region round one spawn point missed when another spawn was drawn (now it covers
the room); M4 first saved after the 5 s rest had already cleared the latch -- its state.txt said `placed 0` (now it
re-raises the latch just before the save). T's own check round_end_hold_voids_run is False on control too.

L rows: review round 3 (driver p1643r4.py in the private task root; "the review-2 build" = c8294e59). K and P:
round 4 (K's control = the round-3 fix, P's = the round-2 fix, which wrote a rewind row's dirty-or-cheat as the
latch). The delivered build (qwprogs 99d0ad13, the rebased tree before the records commit) reads every L row, K, P, H,
U, S and M as listed. Two L steps first measured nothing: the
load of C was forgiven at once ("start re-armed": under run_prestrafe_time 5 the rest counts from the last landing
and a load does not restart it; now the arm jumps first), and `!r` after `zone_goto` an END returns to the END (the
leg zone is latched; now `!m`).

Two K/P cuts first measured nothing: the map reload never re-prints the welcome line (now the driver waits for the
client's `spawn`), and a hopped run on surf_ace leaves the box about 4 s after hopping in place and meets the fail
teleport within a second (now it polls with sleeps and saves the moment it is running).

Not measured: a bhop-mode map (P1657's arms), a stage box, a retry or Multi-Session restore, the practice return and
its message, the keep-window demotion, a shared save, save sync's add, the per-command noclip line (two commands in
one packet), a match spectator's refusal, a second player, a real lobby. qcframes: qwprogs clean.
