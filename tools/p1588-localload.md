# P1588 -- local games predict save loads and holds (ftesurf-06, 16 Nov 2026)

Lex, after 0.1.47: `map colinblaster` from the console, then a load: "Loading save" flashed every time, and with
`sv_minping 300` the body froze before it could move. P1582's measurements were all dedicated server + UDP client;
a game this PC hosts takes another path.

## Cause

Patch 862 opened the CSQC trigger mirror on a listen server but kept the warp-op pre-move hook and the predicted
hold gated on `sv.state` (engine pr_csqc.c). So in a hosted game WarpOp_HookAlive was false, every load went as an
`sl_load` stringcmd whose release waits for the server's answer (P1227), and P1582 r1 had made "Loading save" show
for any load waiting on the server -- every local load.

## Change

- Engine (patch-1588, aa3294bab): CSQC_PredictListenOpsGated, cvar `cl_predict_listenops` 1; both hooks run on a
  listen server when `cl_predict_listen` is on too. Arguments, review and limits: ENGINE_PATCHES.md "Patch 1588".
- QC: SaveLoc_LeadText shows "Loading save" only once `cltime - rec_sl_holdt0 >= 0.3`; wop_why and prederr texts
  no longer say a hosting PC predicts nothing.

## Measured (tmp/listen_arm.py: one client hosting surf_dune, real 0.2 s +sl_hold press, P1384 probe rows)

| build | sv_minping | rows predicted | text | body moving after press | prederr |
|---|---:|---|---|---:|---:|
| 0.1.47 exe d3b7d673 + main QC | 0 | 0/20 | "Loading save" | 0.223 s | 1 |
| 0.1.47 exe d3b7d673 + main QC | 300 | 0/30 | "Loading save" | 0.613 s | 1 |
| P1588 final | 0 | 20/20 | none | 0.223 s | 0 |
| P1588 final | 300 | 20/20 | none | 0.215 s | 0 |
| P1588, `cl_predict_listenops 0` | 300 | 0/30 | none | 0.615 s | 2 |
| P1588 final, `cl_predict_listen 0` | 300 | 0/30 | none | 0.613 s | 2 |

The press is 0.2 s, so "moving at ~0.21 s" is moving as the key comes up. The predicted rows hold the body at the
save from the first frame (+0.01 s); the game's own "save N -- run resumed" line lands in each round. The first
(pre-review) subject showed the teleport as one 242 u step at +0.017 s at minping 300.

## Review

Two reviewers (in-process state; behaviour and recorded runs), then a re-review of the fixes. Fixed: the ops gate
also needs cl_predict_listen (a save could capture a stale posture), field list, stale texts. Not a bug: TAS
(loads/resets cancel a TAS pause on both paths). Known limit (BACKLOG): a paused server drops an op pressed in the
first ~0.5 s of the pause.

## Delivery

Engine main aa3294bab (tag patch-1588); QC main with this record. Players: release 0.1.48 (Lex approved). The lobbies
need nothing (their games are remote: loads were already predicted there).
