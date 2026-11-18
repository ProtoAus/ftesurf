# Patch 1606 claim (Claude Code worldofsurf-43, 18 Nov 2026)

The angle cross-check's sweep rules (tools/reccheck.py angle_join) judge each joined move against the SMALLER of the
recorded and the drawn step, not the recorded step alone: an assist's own jump no longer widens its own allowance.
Measured first on the Pi's lobby evidence at P1599's join (506 pairs, 417 passing the reader): no honest pair newly
faults (worst 2.91% vs the 5% line), dense one-tick snaps caught 1 -> 403, every recorded-step catch kept. Verifier
change: lens reviews, the corpus sweep and an old-vs-new fleet comparison before it rides the next surfd generation.

PARKED 18 Nov, not merged: see BACKLOG's P1599 section ("The sweep rules normalise by the RECORDED angle's motion").
Review rounds 1-4 each found honest network shapes it newly faults (one cause: the label join); branch
p1606-stepnorm keeps 7d2317fd..c4a4c32c and the round-5 rate prototype 502875b3. Reader unchanged on main.
