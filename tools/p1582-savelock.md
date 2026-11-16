# P1582 -- save-lock loads: lead-in off by default; the load latency audit

Owner: ftesurf-06 (Claude Code), 16 Nov 2026. Task root C:/FTESurf-worktrees/savelock-audit-20261116 (OWNER.md).

## Report

Lex (16 Nov): players' videos show a 200-300 ms lag/stutter on every save-lock load. Asked for the lead-in at 0 by
default and for loads that need the server to happen client-side too.

## Measured (rig, before the change)

tools/p1384lead.py (dedicated fteqwsv64 0f69250e + ftesurf64 27697bbc, surf_dune, `cl_delay_packets`), main
f5d4450f (qwprogs 56f3de88), new `--holdfor 0.2`: the load key held 0.2 s like a real press (the old tap was
down and up in one frame, so it never showed the lead-in). `--bigpic 45000`: a 45k-row trail.

| 0.2 s press | lead-in 1 (shipping) | lead-in 0 |
|---|---|---|
| camera on the press | 1 s back up the saved path, travelling | at the save (+0.018 s, one frame) |
| camera on key-up | snaps 158 u (0 ms) / 211 u (250 ms) to the save | no jump |
| release | key-up (0.22 s) | key-up (0.20 s) |
| frame at the server's answer, 45k rows | 38-50 ms (Trail_Load) | same |

prederr 0 everywhere; 0 and 250 ms identical. The stutter in the videos is the lead-in: a real press shows 0.1-0.3 s of
the path before the save, then a ~200 u snap. The load itself does not wait for the server at 250 ms: it rides the
press's next command (P753/P1547) and releases on key-up before the server's answer arrives (+0.28 s at 250 ms).

## Change

- `cl_sl_leadin` registers 0. FTE saves every archived cvar, so HE_MigrateDefaults moves a config still on exactly 1
  to 0 once (`cl_sl_leadin_rev 1582`) and says so; any other value is the player's and stays. HUD edit's reset writes 0.
- WarpOp_Load names each refusal in `wop_why`, and a load key press it refused notes "load not on a command: <why>"
  in the prederror ring, so an F6 report shows when a player's load took a server-waiting path. Verified by build and
  reading only (not run).

After (P1582 build 015e7752 for the note; the default/migration runs used e179a445, identical but for the note):
- config pinned `seta cl_sl_leadin 1`, rev 0: read back `cl_sl_leadin 0`, rev 1582, message printed; 0/250 ms loads:
  no travel, the teleport at +0.018 s, no jump at key-up, released 0.21 s, prederr 0.
- config `seta cl_sl_leadin 0.5`, rev 0: kept 0.5, no message, rev 1582; the run-up plays (62 u snap on key-up).

One unattributed 57 ms frame mid-hold in one round (no log line between the frames, not at the answer, absent in the
rerun); another session was busy on the shared machine.

## Paths that still wait for the server (audit; unchanged)

A load is predicted when WarpOp_Load queues it with a known row. Otherwise:
- **Stringcmd pair** (sl_load + sl_hold) when WarpOp_Able says no -- hosting the game yourself (no CSQC prediction
  hook), spectating/watching/rewinding/ghost replay, no input frame for 0.25 s, `cl_warpop 0`, a server without
  `fs_wop` -- or a save is waiting for its answer on the stringcmd path, the server holds a save with no release in
  flight, or an sl_ stringcmd is unanswered. The camera goes to the save at once (P430) when the row is current; the
  body waits, and a key let go waits for the answer (P1227) or the 1 s backstop. Not predictable: a reliable runs at a
  command the client cannot know (one reliable in flight, resent after loss: reliable-stringcmd ordering, P1544).
- **Blind op**: rides a command but its row is not published (cursor string a packet behind the numeric ack, behind
  a blind load, or behind a save whose row is not captured): no body prediction, the release waits for the answer.
- In every arm at 250-500 ms (P1544/P1547 taps after saves, reload loops, holds; these runs) loads took the predicted
  path; Lex's three 15 Nov reports: 40 loads, all predicted, one mispredicted by a command (46239). The lobby logs
  record nothing per load, hence the note above.

## Not changed

- Trail_Load still reads the whole trail at the answer (BACKLOG "A save load still reads its whole trail file in one
  frame"): Lex's 1721 trail files are median ~940 rows, p90 ~5200, p99 ~21700, max ~38000 -- about 1 ms, 3-6 ms,
  13-24 ms at 0.6-1.1 us a row on this i9 (45k rows: 28-40 ms over a 10 ms frame here, 30-53 ms in P1384).
- The hold itself (frozen at the save while the key is down) is the save-lock design.

## Review

Two rounds, read. Round 1 (9876bac1): no control-flow bug; "Loading save" was hidden at lead-in 0 (a server-waiting
load froze with no word) and the note mislabelled a press queued behind a save -- fixed in 8b5d560e. Round 2: no
bug; the note missed two stringcmd paths (now noted where sl_load is sent, SaveLoc_Cmd); at lead-in 0 the held-row
wait now starts at the answer (BACKLOG round-3 R2 closed).

## Delivery

LIVE 16 Nov 2026 ~03:18Z, one lobby deploy agreed with ftesurf-dc and ftesurf-31: `build.ps1 -Pi` from main
8b5d560e (P1572 + P1576 + P1582; fteqcc 1f2efd06, 0 warnings). Nobody on; warned, swapped, 12 restarted, active.
- Lobbies: qwprogs 56f3de88 / csprogs 92f9604e (.prev 52f3c098 / 71f708cf, P1573).
- Both installs: csprogs 92f9604e (.prev fc726221); qwprogs 56f3de88 and menu 76d94dfd unchanged; csprogsvers
  a05e0981 seeded in both. tasrevd codes.txt 143 -> 144 (backup .pre1582).
- tools/pi_lobby_smoke.py against 27510: PASS (served csprogs 92f9604e, board drew, no QC error).
- The round-2 note move rides the next deploy (diagnostic only).

