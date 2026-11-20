# P1657 bhop/ahop start rest -- arms and results (20 Nov 2026, worldofsurf-4b)

Rig as tools/p1643-arms.md (one dedicated server, one headless client, owned game copy, engine as installed 20 Nov),
map surf_ace with `+set sv_gamemode bhop` (`cmd timer`: "start on jump", tick 0.01; the server's run_starthop reads
0, mode_bhop.cfg). Control = P1643 alone (qwprogs 2bad568f); fixed = this patch, last on the delivered build (qwprogs
99d0ad13: the rebased tree with the final review fixes, before the records commit), which reads every row below as
listed. Graded on the server's line per start, `timer: <name> starts: rested R placed P dirty D hopped H
cheat C unrested U` (its stdout), and `cmd timer`'s `practice N`. "Caps 100" = run_rearmspeed 100 and
run_bhoprestspeed 100 (an exact override of the bound), so a 260 u/s ground run stands in for a body over it. The
computed bound reads 299.946 on bhop and 504.089 on ahop in `cmd timer`. The driver and the zone
fixture are kept in the private task root.

| Arm | Gesture | Control | Fixed |
|---|---|---|---|
| leave100 | caps 100: `!r`, run out of the START on the ground | rested 1 unrested 0, practice 0 | rested 0 unrested 1, practice 1 |
| leave | default caps: the same walk-out | -- | rested 1 unrested 0, practice 0 |
| through100 | caps 100; the only START is thin curtains across the spawn room; spawn idle, run through one | rested 0 unrested 0, practice 0 | rested 0 unrested 1, practice 1, "unrested start" |
| through | default caps, the same | -- | rested 1 unrested 0, practice 0 |
| relaunch 1 | caps 100: `!r`, jump in place | rested 1 unrested 0 | the same |
| relaunch 2 | land, run 0.45 s, jump in the START (the run is live: arm and start in one tick) | rested 0 unrested 0, practice 0 | rested 0 unrested 1, practice 1 |
| relaunch 3 | `!r`, jump, land, stand, jump | rested 0 unrested 0 | rested 1 unrested 0 |
| honest 1-3 | default caps: `!r` jump; land, run 0.45 s, jump; `!r`, run 0.45 s, jump | rested 1/0/1, practice 0 | each rested 1 unrested 0, practice 0 |
| off | fixed with `+set run_bhoprest 0`: relaunch, honest | -- | identical to control, rested values included |
| ahop leave100 | `sv_gamemode ahop` (start on leave), bound 100: `!r`, run out on the ground at 190 | rested 1 unrested 0, practice 0 | rested 0 unrested 1, practice 1 |
| ahop leave | ahop, computed bound (cmd timer: cap 504.089): the same | -- | rested 1 unrested 0, practice 0 |
| ahop sprint | ahop, computed bound: `!r`, +speed +forward, out at 320 (viewpos horizontal 320.0) | -- | rested 1 unrested 0, practice 0 |

leave100 is the review's finding in miniature: a rest the armed attempt saw at `!r` is not what the start is judged on.

Arms that measured nothing: a START slab over the spawn floor (zones arm on the point and are left on the hull, so a
jump from the floor cannot enter and leave one); curtains every 150 units (one sat on a spawn column, so control runs
spawned armed); hopout (hold +jump and +forward, `!r` in the air, hop out): after the `!r` the body stood, with the
client's run_prestrafe on or off -- no start in either build. It exercises the same leave check as leave100.

Not measured: a real bhop map, a real fast landing, an airborne exit, bhop-hl1, a booster in a START, overlapping
STARTs, a second player, a real lobby. The lobbies' 69 bhop and kz starts with a `seed` (read-only, 20 Nov): median
265 u/s, 287 at the honest maximum, and one at (0, 1200, 460) on bhop_sandtrap, that map's launcher.
