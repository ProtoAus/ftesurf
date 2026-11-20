# P1675 start lag -- arms and results (21 Nov 2026, worldofsurf-6f)

Rig as tools/p1643-arms.md (one dedicated server, one headless client, owned game copy, engine as installed), map
surf_ace (bhop cases under `sv_gamemode bhop`). Fixed = this patch: final build qwprogs 1e7a12b8; some 0.01 s,
0.005 s and off rows ran on the review-1 build 050f6f54 (the same rule; default 0.1, no record at 0 ticks).
Graded on the server's own line, `timer: <name> startlag <ticks> (<s> s, max <limit>)`, `cmd timer`'s practice and
the chat line. The driver is kept in the private task root.

| Case | Client | run_startlag | Measured | Result |
|---|---|---|---|---|
| walk out | normal | 0.06 (default) | 0 ticks | practice 0 |
| walk out | cl_c2spps 1 (drops up to a third of packets) | 0.06 | 0 once, 2 ticks / 0.030 s once | practice 0 both |
| walk out | cl_c2spps 1 | 0.01 | 2 ticks / 0.030 s (three of five runs; the other two 0) | practice 1 + "start packet too long" on each 2 |
| walk out | cl_c2spps 1 | 0 (off) | 2 ticks / 0.030 s once, 0 twice | practice 0 |
| bhop launch | normal | 0.06 | 0 | practice 0 |
| bhop launch | cl_c2spps 1 | 0.01 | 1 tick / 0.010 s (= the limit) | practice 0 |
| bhop launch | cl_c2spps 1 | 0.005 | 1 tick / 0.010 s (three runs) | practice 1 + the chat line |

The first cut (ticks since the last tick seen inside the box, or since the jump command) read the same on these
cases; its review found a walk-out before a bhop jump uncounted, a booster launch measured from a stale jump, a tick
limit that every AG start broke, and re-entry hiding an excursion -- hence per-packet first-outside and first-rise
notes and a limit in seconds. Review 2 found no correctness bug; it set the default to 0.06 s (the free allowance
was larger than some world-record margins), the record is written at every measured start, a handover is -1.

Measured nothing first: cl_maxfps 4 (input still runs at cl_netfps 66.7, one tick a command) and cl_netfps 4 (the
ruleset puts it back). Not measured: the `startlag` record in a kept `.rec`, AG/GoldSrc profiles, a real batched
client. Honest packet sizes (300 lobby REC 14 runs, 21 Nov): 99.49% one tick, 6-7 ticks 0.27% (frame hitches across
many players), 8+ about 0.002%.
