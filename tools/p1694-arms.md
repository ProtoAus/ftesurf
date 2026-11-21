# P1694 controller tag -- arms and results (21 Nov 2026, worldofsurf-6f)

Rig as tools/p1643-arms.md (one dedicated server, one headless client, owned game copy), map surf_ace with a zone
fixture whose end box lies 300 u east of the start (x -1040..-860). Since the owner's compositor crashed on 21 Nov
within a second of a rig shutdown, the nested labwc renders with pixman and the client with Mesa llvmpipe (the client
log says `GL_RENDERER: llvmpipe`). Controller input is injected with `in_journal_synth 1 pad <v>` (right stick) and
`in_journal_synth 1 padkey [down|up] [dpad]` -- the IN_JoystickAxisEvent / IN_KeyEvent calls the XInput backend makes.
`cmd timer` prints the run's `pad` and the connection's `padin`. The driver is kept in the private task root.

| Step | What | Result (engine review 5-6, game review 5) |
|---|---|---|
| S0 | spawn | in_pad_frames 0, pad 0, padin 1 |
| S1 | stick 0.1 (inside the 0.19 dead zone) | in_pad_frames +0 |
| S2 | stick in the start box, zone_reset, walk out, finish | count moved; run pad 0; .rec tail `prof`, `plat 1` (no `pad`) |
| S3 | walk out, stick 0.8 / -0.8, finish | pad 0 -> 1; .rec tail `prof`, `plat 1`, `pad 1`; reccheck pad_end 1, 0 faults |
| S4 | walk out, A button (default bind impulse 10) | count +1; pad 0 -> 1 |
| S5 | sl_save in that run, !r, sl_goto 1 | state.txt `pad 1`; armed pad 0; loaded run pad 1; padin stays 1 |
| S6 | fresh run, 0.15 s stick burst, sl_save at once, !r, sl_goto 1 | state.txt `pad 1`; loaded run pad 1 |
| S7 | D-pad up (+forward) held from inside the start box, walking out | running, pad 1 |
| control | same engine, the P1692 lobby progs | the count moves; no mark, no `pad` |
| control | the released 0.1.53 client, these progs | padin 0, pad 0, .rec without `pad` |

Not measured: the stage mark and its box-exit reset (no stage post in the rig), the "not driven" predicate (spectate,
replay/rewind watch, save-lock hold, frozen, ghost), focus loss while holding a button, the review-6 key-number check
(rig busy: the owner's game was running), sv_rank_padcount (the headless client's `rawmice`
verdict comes first; `padin` staying 1 across loads is the proxy), a real XInput pad (the win64 build cross-compiles;
the injected calls are the backend's).

S6 is review 1's save-window case. The first cut (a throttled csprogs report) passed S0-S5; it was not re-run on S6
(by reading, its report could still be waiting when the save was written).
