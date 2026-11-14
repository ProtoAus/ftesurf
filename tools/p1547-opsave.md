# P1547 -- predicted saves: a load right after a save is instant too

Owner: ftesurf-e7 (Claude Code), 14 Nov 2026. Task root C:/FTESurf-worktrees/opsave-20261114 (OWNER.md).

## Report

Lex (14 Nov), after P1544: "Does this fix take 2 loads to fix? can we make it so the system works on the
first load somehow?" P1544 left one wait (its BACKLOG): a load pressed within a round trip of a save waited
for the save's answer (rig, 500 ms: 0.38-0.53 s), because sl_save was a reliable stringcmd and a later
command's op can reach the server before an unanswered reliable (one reliable in flight, see
reliable-stringcmd ordering in tools/p1544-savelock.md). Every other first load was already instant.

## Change

- WOP_SAVE (impulse 200, below WOP_RESET so an older server ignores it; sent only under serverinfo
  `fs_wopsave 1`). SV_WarpOpCommand runs sl_save's preamble and SV_SaveLocCreate at that command: answer
  ticket FS_SaveOpTag(command) (no stringcmd carries one), terminal answer even when refused, the rate
  charge, no STAT_FS_SLACK count (no stringcmd was sent).
- The client sends the live body's queued sl_save as WOP_SAVE (SaveLoc_Cmd -> WarpOp_Save) when nothing
  blind and no sl_ stringcmd is unanswered ahead of it and it is not held; otherwise sl_save as before.
  Its row is taken at the same command from prediction: pre-move origin and speed rounded %.4f as
  state.txt is, duck from the move before it (STAT_FS_PMFLAGS for a replay's first command), the
  command's angles.
- A load pressed before that save's answer is no longer held in the trail FIFO (Trail_RequestOpSave):
  it rides the next command, predicted from that row (WarpOp_Row), released on key-up. A step behind a
  pending save, or a row not taken yet, goes as before (blind or queued). No run-up for that load (the
  cursor picture is still the previous save's).
- The FIFO still waits for the save's answer before any stringcmd queued after it, and holds queued
  stringcmds while any op is unanswered; the ticket is bound when a command carries the op
  (Trail_OpSaveCarried). An op no command carries in 0.25 s goes as the stringcmd (WarpOp_SaveExpired).
- Not under TAS states (an impulse escapes a TAS pause), not held unless this client's release is in
  flight, not within 1 s of a body-moving stringcmd (wop_strat: reset fallbacks, zone_goto, ms_resume,
  tp_player, zone_edit_goto, `!r N`...), and only when the predicted hull is one of the engine's two.
- A reset behind a pending save rides a command too (blind: a save can move `!r`'s destination, P415).
- A carried save acked but unanswered 0.3 s + 3 round trips past the ack is reported ("no answer from
  the server"), not resent: a timeout cannot tell a dropped op from an answer lost twice, and the resend
  doubled saves (round 4 below). The queue behind it goes on.

## Measured (rig on the PC)

tools/p1547opsave.py = P1544's arm (dedicated fteqwsv64 5c98d0ac + ftesurf64 be8b03d4, surf_dune,
`cl_delay_packets`, +forward 200 u/s, three taps 1.2 s apart) plus a per-frame body trace from the save
on; landing.py (task root) grades how close the body comes to where the save key was pressed, and when.
P1547 qwprogs 9c1ed4b5 (src 587e0e28); control = main 505bcec0 (qwprogs bcb6f7c6).

| arm | main | P1547 |
|---|---|---|
| tap 0.15 s after a save, 250 ms | held 0.19 s; lands 31 u from the save spot | released in the press frame; lands 1.5-1.7 u from it at +0.016 s; the op-save was pending at the press |
| same, 500 ms | held 0.48 s; lands 31-64 u from it | released in the press frame; 1.5-1.7 u at +0.016 s |
| tap 2 s after a save, 250 / 500 ms | instant; the save itself 1.5 / 95 u along the path from the press | instant; 0.02-0.74 u |
| hold 0.8 s, 0 / 500 ms, 2 s and 0.15 s after a save | -- | parked to key-up (0.81-0.85 s), "Release to play", 0.74-1.45 u |

prederr 0 and no eye jumps in every P1547 tap; no "pending save lost its acknowledgement"; saves numbered
1..6 in order; no server errors. The main column's distances are the stringcmd save landing late: it
waited behind another reliable (up to a round trip), so the body had moved on (95 u = ~0.47 s at
200 u/s at 500 ms). A save on a command is taken where it was pressed.

After review round 1 (src 2fb5fbda, qwprogs from build 3037c264), the same arms plus three new ones:
- taps 0/250/500 x 2 s/0.15 s: all released in the press frame, landings 0.74-3.75 u, prederr 0;
  holds 0/500: parked to key-up 0.81-0.85 s, prederr 0.
- `--duck` (+duck through save and taps), 250/500: instant, landings 0.01-1.34 u, prederr 0.
- `--reset-after` (`reset` 0.05 s after the save, then the taps), 250/500: the first tap lands 0.54 /
  0.01 u from the saved spot (the reset spot is 360 u away), prederr 0: the reset ran after the save.
- `--dropsave` (ARM-ONLY server build dropping each round's WOP_SAVE before answering it), 250/500: the
  server dropped 4, the client resent each as sl_save (WarpOp_SaveFrame), saves 1-4 all made, no "lost its
  acknowledgement". Those saves land where the server has the body at the resend (158-208 u on at 2 s);
  a tap 0.15 s after the dropped save was predicted from the capture and corrected once (prederr 1).

Final build (src 9677dd5e, qwprogs build e008afd8): taps 0/250/500 x 2 s/0.15 s all released in the press
frame, landings 0.09-4.9 u, prederr 0; `--loss 0.3` at 500 ms, 12 presses: 11 saves and one "no answer
from the server" for the save that was lost, no duplicate (the round-1 build made 15 saves for 12, the
round-4 build doubled one); `--dropsave`: 4 dropped, 4 reported, 0 saves. Holds, crouched saves and
`--reset-after` were last run on the round-3 build (unchanged since but for the backstop): parked to
key-up 0.81-0.85 s; crouched landings 0.07-1.03 u; the reset (now blind) corrected once, the load after
it 0.42-2.36 u from the saved spot.

Not measured: a save the server refuses after the client predicted it (list full at 999, resume phase,
lobby_nosaveloc): the load behind it is corrected, as in the dropped case. TAS states are refused by
reading the same stats cl_savelead.qc does, not run.

## Review

Four rounds, read not run; none found anything that could rank a run, change a recording or harm a server
(every server refusal of sl_save also refuses WOP_SAVE; a save writes no .rec record and impulses are not
recorded; same rate bucket; TAS steps and redundant usercmd copies cannot double it).
- Round 1 (ordering/prediction; evidence/abuse): an impulse escapes a TAS pause; a carried-but-dropped op
  save was lost and the FIFO reset after 5 s; resets falling back to stringcmds could land on the other
  side of the save; a hard-coded duck height; a save after a lost release; queued stringcmds overtaking a
  load behind the save; captures refreshing after the ack; prederr replay, the .rec grammar block, the
  answer before the placed check. Fixed in 2fb5fbda; measured (duck, reset-after, dropped op).
- Round 2: the backstop could double a save whose answer was lost with its packet (resent a round trip
  later); `!r`'s destination is the newest idle save in the start zone (P415), so a reset behind a save
  must stay blind. Fixed in 2b3ba349. The loss arm then reproduced the double save on the round-1 build:
  15 saves for 12 presses at 500 ms with net_fakeloss 0.3.
- Round 3: the round-trip measure included outages and menus, so the FIFO's 5 s could beat the backstop;
  an op carried after a dropped save makes the resend copy the old save. Fixed in 4ebdc125.
- Round 4: the scoreboard ping is only as fresh as its last `pings` request; a body-moving stringcmd or a
  queued op after the save should refuse the resend too. Fixed in ea0f409e.
- Then the round-4 build's loss arm still doubled one press (answer and requeue both lost): the resend
  was removed (9677dd5e), which also retires rounds 3-4's refusal logic. Remaining edges, each needing
  lost packets or a rare order, are in BACKLOG rather than another round (review-depth rule).

## Delivery

DELIVERY
