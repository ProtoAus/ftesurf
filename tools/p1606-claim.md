# Patch 1606 claim (Claude Code worldofsurf-43, 18 Nov 2026)

The angle cross-check's sweep rules (tools/reccheck.py angle_join) judge each joined move against the SMALLER of the
recorded and the drawn step, not the recorded step alone: an assist's own jump no longer widens its own allowance.
Measured first on the Pi's lobby evidence at P1599's join (506 pairs, 417 passing the reader): no honest pair newly
faults (worst 2.91% vs the 5% line), dense one-tick snaps caught 1 -> 403, every recorded-step catch kept. Verifier
change: lens reviews, the corpus sweep and an old-vs-new fleet comparison before it rides the next surfd generation.
