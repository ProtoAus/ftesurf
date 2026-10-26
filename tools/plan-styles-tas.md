# Styles on the boards, and a TAS category: the plan (Lex, 25 Oct 2026)

Asked in Lex's third list of 25 Oct: submit runs of different styles, detected automatically;
a TAS category; whether segmented or TAS runs can be spoofed as regular. P1011 (live with this
list) does the detection only, as a timer word. This is what filing them takes.

## 1. What KSF's styles are, measured

45 imported KSF replays (tmp/ksfstyles.py in task root lexlist27-20261025T0530Z), airborne at
400+ u/s. "Facing" is the view against the direction of travel:

| style | facing, median | keys |
|---|---|---|
| forward (normal) | ~1 deg | A/D alone ~90% of key ticks |
| sideways | ~89.5 | W/S only; A/D never alone (0.0% in 12 runs) |
| half-sideways | ~44 | W/S together with A/D 91-100%; A/D never alone (0.0% in 12) |
| backwards | ~179 | A/D alone, like forward |

Two surf_kepler backwards runs faced backwards on only 64-81% of their fast air, so "always
backwards" would refuse KSF's own runs. 108 KSF backwards replays are imported: 63 full runs
(surf_summit 10, surf_tendies 9, surf_network2008_final 8, surf_boreas 7, surf_demise 6,
surf_garden 6, and fewer on seven more maps) and stage runs -- on surf_kitsune only stages 1, 6
and 9, though its board lists 13 full-run backwards times without replays.

P1011's reading: the most common quarter of the facing angle over the run's fast air, and for
the two sideways styles no lone strafe key (0.5% slack). Keys held at the start exit alone
would call a forward prestrafe (W+A) half-sideways, so the whole run is read instead.

## 2. Filing a run under its style

surfd takes the board from the flags word, never from the submitter (style_of), so the style
travels as flags:

1. Two TF bits (2^20, 2^21: forward / sw / hsw / bw), set by the server at the finish from the
   P1011 reading, written into the .rec flags line and the submission.
2. Readers: reccheck.py, hidcheck.py, recsim and heldmeta accept the bits; reccheck re-derives
   the style from the rows (yaw, velocity, fl, keys columns -- all already recorded per move)
   and faults a mismatch, so a lobby cannot claim a style its own recording does not show.
3. surfd: style_of maps the bits to sw/hsw/bw; segmented_* already exist in its vocabulary.
   No schema change (runs.style is text).
4. Boards: the web board already shows KSF's sw/hsw/bw; the in-game board needs a style chip.
5. Review: evidence-format change, so the three-lens review before deploy.

Decisions for Lex: majority reading (as P1011) or per-tick enforcement like KSF's plugin (a
violation drops the run to forward); whether W-only or low-gravity are styles too.

## 3. A TAS category

Updated 26 Oct: [the full TAS/project/contributor plan](plan-tas.md) supersedes the
short outline below. P1052 starts explicit local TAS practice and inherited labeling;
frame advance, input editing, signed contribution history and board admission remain
separate stages. This first stage does not certify authorship or human input.

What exists: per-player slow motion (host_timescale 0.1-1, marked cheat today), save states
and rewind (segmented), and recordings that hold every move's inputs (fwd/side/up, angles,
buttons) per tick. The mover is deterministic given those inputs: pm_verify (engine) and
recsim re-simulate a recording, and CSQC can run the same mover (runstandardplayerphysics).

Plan:

1. TAS mode (private games first): slow motion and saves allowed, plus frame advance (pause the
   mover, step N ticks) and an opt-in strafe optimiser (per tick, the wish angle that gains most
   speed for the current velocity -- the standard autostrafe formula). Everything done in TAS
   mode marks the run TF_TAS; such a run can only be filed as TAS.
2. Line editing: pick a stretch of the run line, change a parameter (turn rate, jump tick,
   strafe sync), re-simulate forward in CSQC with the edited inputs and draw the new line
   beside the old one; keep or discard. A preview only -- the client is never trusted.
3. Submission as inputs: a TAS run is submitted as its input stream. The server re-simulates it
   from the map's start in one pass, with no save states, and the board time is the server's
   own tick count from that re-simulation. Valid iff its simulation finishes. Nothing the
   client claims about time or position is used.
4. Boards: style "tas" beside clean and segmented.

Order: 3 first (the verifier is what makes TAS runs mean anything; pm_verify already does most
of it), then 1, then 2.

## 4. Can segmented or TAS runs be passed off as regular?

- The official segmented path: save loads happen on the server, which sets TF_SEGMENT
  and records the stitch. That preserves observed loads; it is not a universal proof
  against modified clients, untrusted servers or hidden input automation.
- Slow motion: host_timescale is the server's own setting (cheat, never ranked); a slowed client
  clock without it is measured (TF_SLOWCLOCK, Patch 840) and the run demoted.
- Time: runs are already timed from the server's tick counter (the counted clock), not from
  anything the client says, and every row of a recording is stamped by the server.
- The real gap is input automation: a client that sends machine-perfect strafes in real time.
  Its usercmds look like a human's in kind, so no server-side timestamp can catch it. What
  catches it is evidence about the inputs: the HID input journal (hidcheck.py: raw device input
  against the view changes it should explain) and statistical checks (strafestats.py, reccheck's
  strafe tests). A TAS category also gives that ambition an honest board.
