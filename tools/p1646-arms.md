# P1646 script guard -- arms and results (21 Nov 2026, worldofsurf-6f)

Rig: one dedicated server and one client under a headless Wayland compositor, keys typed with wtype (each tap a
press and release, held keys with -P/-p), the engine built from the P1646 branch (Linux client and server), csprogs
from this patch. Each step reads `in_script_lapses` before and after; `cmd timer` gives the server's jump count. The
driver is kept in the private task root.

| Step | Input | Lapses | Result |
|---|---|---|---|
| K | key "2" bound `+forward`, held 0.7 s | +0 | moved ~195 u |
| C | `+jump` / `-jump` typed at the console | +1 | jumped |
| F | `+forward 50` (a forged key number) | +1 | |
| A | key "3" bound to an alias that presses `+jump` | +1 | |
| M | key "4" bound `"+jump;+moveleft"` | +2 | |
| W | `wait`, then `waitms 10` | +1 each | |
| I | `in 0 echo x` | +1 | |
| WM | `waitmap` in a map | +1 | |
| N | noclip, key "5" bound `+jump` held 0.5 s | +0 | regression guard only (see below) |
| G | key "6" bound `+attack2` | +0 | was +1 before review 2 (engine alias) |
| AL | an alias at `aliaslevel 20` run from the console | +1 | body runs next frame |
| FI | `+fire` / `-fire` typed at the console | +1 | |
| P | `set sys_platform Win`, `set in_script_lapses 0` | refused | read-only |

Final build: 12 of 13 as expected after every review round; the one miss is step A's jump counter (the aliased jump
lands in step M's window), its lapse count is right. Step N cannot reach the smartjump branch in this rig: a control
client with that fix disabled also reads +0 (the game's noclip ignores the up key), so the fix is verified by reading.

Reviews: four independent rounds. 1: waitmap/in 0 uncounted, smartjump double count, ring eviction, sys_platform from
a map, cvar set off the main thread. 2: the engine's +attack2 alias, deferred alias bodies, +fire unjudged. 3: a note
could outlive its own press (now one frame; bare binds at a usable level only). 4: low residuals only (BACKLOG).
Not measured: Windows (win64 cross-compiles clean), a real gamepad or wheel in hand, touch. Owner check in lextest.
