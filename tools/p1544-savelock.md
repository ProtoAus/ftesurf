# P1544 -- save loads at ping: no second-long lock on reloads

Owner: ftesurf-e7 (Claude Code), 14 Nov 2026. Task root C:/FTESurf-worktrees/savelock-20261114 (OWNER.md).

## Report

markbeaton54 (via Lex, 14 Nov): "save loc ... basically imp to practice maps currently, it could just be my
ping". Lex: players get locked in place on load.

## Cause (client; the server's hold is unchanged)

A load rides a usercmd and is predicted (P753/P1384) unless a gate sends it as the sl_load + sl_hold
stringcmd pair, whose key-up release waits for the server's answer. At 250-500 ms three things stacked:

1. A load pressed within a round trip of a save waited in the trail FIFO (cl_trailrequest.qc) and went as
   the stringcmd pair after the save's answer.
2. That pair's release was a stringcmd sl_holdoff; WarpOp_Load refuses while any sl_ command is unanswered,
   so the next load in that round trip was a stringcmd load too, and so on: a reload loop never got back.
3. SaveLoc_LeadDone's `answered = (a && b) || SaveLoc_LoadAnswered();` stored (a && b): `=` binds
   tighter than `||`. Since P1384 (8 Nov) every unpredicted load held to the backstop: 2 s until P1462,
   1 s since (rig: answered 0.32 s, released 1.03 s).

## Change

- A load pair at the FIFO's tail goes as one predicted command once the save is answered, when nothing
  sl_ is unanswered (waits up to 0.1 s for the count and the cursor string); released at once if the key
  was let go meanwhile, with no run-up.
- A stringcmd hold whose sl_load/sl_hold are answered, nothing else in flight, lets go on a WOP_RELEASE
  command instead of sl_holdoff, so the next load is predicted.
- LeadDone bracketed.
- Watch_OpenIn sends sl_holdoff after the release (a command-carried release is never carried once the
  replay stops input frames; P753's predicted holds had this too).

- A load pair waiting behind a save reports its own release on a command once answered (above); a
  hold answered a packet before its held row's speed waits up to 0.15 s so that release is predicted.

## Measured (rig on the PC, i9-9900K / RTX 2080 SUPER)

Driver `savelock.py` in the task root, on tools/p1384lead.py's fixture: dedicated fteqwsv64 (C:/FTEQuake,
sha256 b4dc8dca) + ftesurf64 client (854eb4ff), surf_dune end room, `cl_delay_packets` 0/250/500 (adds to
the round trip), +forward held throughout, a tap = down and up in one frame, three taps 1.2 s apart per
round. "Held" = press to the frame the client's hold ended; instant = released inside the press frame.
ARM-ONLY: `p1544_forcestr` makes one press's WarpOp_Load refuse (the stringcmd path a busy gate gives).

| arm | main ab9579d9 | P1544 final |
|---|---|---|
| tap 2 s after a save, then 2 reloads | instant at 0/250/500 | instant |
| tap 0.15 s after a save, then 2 reloads | 0: instant; 250 and 500: 1.01-1.03 s on all three, teleports at 0.06-1.74 s, eye jumps 56-212 u, prederr | 0: instant; 250: 0.13-0.17 s then instant; 500: 0.38-0.53 s then instant; no eye jumps, prederr 0 |
| forced stringcmd tap, then 2 reloads | 250 and 500: 1.02-1.03 s on all three, eye jumps 57-213 u | 0.31 / 0.56 s (the answer), then instant |
| hold 0.8 s (0, 500; 2 s and 0.15 s after a save) | -- | let go at key-up, 0.81-0.83 s; run-up plays; body parked at the save |

The load right after a save still waits for the save's answer (its round trip less the gap; 0.38-0.53 s at
500 ms across runs). The forced tap's one prederr is its unpredicted teleport (~400 u), a frame before the
release; the release itself is predicted (body moving within two frames).

## Reviews

Round 1 (two lenses: client state machine; server ordering/prediction/fairness) found the first cut's
relaxation unsafe -- both independently: a reliable stringcmd can wait behind another reliable while
usercmds go on, so an op is not ordered after an "unanswered" sl_holdoff/sl_load/sl_hold (late holdoff
releasing a new hold; the FIFO sending an op behind stringcmds it just sent). Reverted; the chain is broken
by releasing answered stringcmd holds on a command instead. Round 2: replay open (Watch_OpenIn) let a
command-carried release go uncarried (P753's predicted holds too) -> sl_holdoff there; releases at the
answer could go blind -> 0.15 s wait for the held row. Round 3: dropping the queued release left a queued
load behind it -> kept. Round 4 found nothing. Nothing a player gains: server unchanged, every load still
SV_TimerStitched, .rec/.view and run class unchanged (round-1 fairness lens).

## Limits

- Not measured on the real internet (loss, jitter) or with Mark's own bind/settings.
- A load within a round trip of a save waits for the save's answer; instant needs a predicted save (BACKLOG).
- hold -> save -> let go -> load inside one round trip takes the stringcmd path once (BACKLOG, review F4).
- A stringcmd hold released on a command predicts walk afterwards (noclip corrected once).
- 12 other `x = a && b` / `x = a || b` assignments elsewhere store only `a` (BACKLOG, not touched).

## Delivery

(filled in at deploy)
