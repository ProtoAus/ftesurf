# TAS uploads and bring-your-own bot — plan (20 Nov 2026)

## Lex's decision, 20 Nov 2026

> "I don't mind if the anti-cheat can't work 100% it's ok, as long as the run makes
> sense physics wise, it's fine."

This widens the 28 Oct rule (TAS boards admit only server re-simulated runs, no offline
TAS): a TAS record made anywhere — our TAS tools, someone's own bot, a fork such as
Rounin's — can be uploaded, and goes on the TAS board when its physics checks out.
TAS stays off the human and segmented boards; nothing here changes their admission.

## Verdict ladder for an uploaded `.rec`

| Verdict | How | Board |
|---|---|---|
| EXACT | native recording with `in` rows: `pm_verify` (sweep.py) re-simulates it in our engine and the zones finish it | TAS board, "re-simulated" badge |
| PLAUSIBLE | `tools/tasplaus.py` PASS: every tick within the measured movement bounds, start/checkpoints/finish visited | TAS board, "physics checked" badge |
| HOLD | tasplaus HOLD, or pm_verify disagrees and tasplaus cannot clear it | owner review queue, not shown |
| FAIL | cannot be a run (no samples, clock backwards, past sv_maxvelocity, samples stop before the finish) | refused with the reason |

tasplaus status (commit b7fab6e2): 117/117 honest KSF/Momentum replays PASS; 12 checks
each proven by a cheat test (speed edits, deleted ticks, teleports into the end, clock
edits, low gravity, start outside the zone, early finish claims). Not yet known to it:
collision (a wall clip at legal speed passes), map push/booster volumes (HOLD), stage
legs (HOLD). Before it gates a public board it gets the independent review that
evidence code requires (CLAUDE.md).

## Bring your own bot (what already works)

- **Any tool, any fork**: the upload takes a `.rec`, so whatever produced it — a fork of
  this public repo, an external optimiser, a hand-made input list — is judged by the
  same physics. A fork that changes movement gets PLAUSIBLE at best, never EXACT.
- **Your inputs, our physics**: `tas demo <file> [rows [from]]` plays a recording's
  input rows (moves, pitch, yaw, with a `ksfbuttons` line before each) as TAS tapes in
  a local game (sv_tasoptimize.qc, P1449). An external program can write that file;
  the game plays it under the real mover and records a native run that can reach EXACT.
- **Tweak Jargon**: every search weight is a `tas_jargon_w_*` cvar (Tuning tab, P1572).
  A preset is a `.cfg` of those lines that people share and `exec`.
- **Analysis**: `tools/runcompare.py REF.rec RUN.rec ...` splits runs at the reference's
  ramp boards, gives the loss per split, the sum of best splits and per-ramp board/leave
  numbers. First use: surf_sandtrap2 bonus 4 (WR 7.827, human-proven splits ≈ 7.765).

## Still to build

1. surfd upload route (POST `.rec`, size cap, rate limit, account binding) storing to a
   pending area; a worker that runs pm_verify / tasplaus and files EXACT/PLAUSIBLE rows
   as tier community, style tas. New tables need the guarded schema/generation path.
2. nginx location on play.proto.bar for the route (its default body cap is 16k):
   root on the Pi, so Lex runs it.
3. Web upload form on the board site; in-game "Upload to TAS board" after a TAS finish.
4. tasplaus: map push volumes from the entity lump; stage legs.
5. Optional: a short public "make your own bot" page describing the `tas demo` row format.

Open for Lex: may anyone upload, or Steam-linked accounts only (the 28 Oct signing rule
leaves unlinked players unattributed)?
