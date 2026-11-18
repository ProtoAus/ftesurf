# Patch 1610 claim (Claude Code worldofsurf-58, 18 Nov 2026)

A new angle rule in tools/reccheck.py: each move is joined to the frames of the command that built it, by the
.view's `cmdframe` (the client's own usercmd counter) instead of the snapshot tick label, so network delay leaves
the join. A sent angle must equal one of its command's frames or lie on the drawn path between them (one command
either side). Measured on the Pi's 521 lobby pairs (move order as the command number, a voted offset, blocks free to
move): honest unexplained median 0, worst 0.74%, 0 pairs over 1%; 10/3 deg snaps on 2% of moves and +1 deg held lies
caught on 521 of 521. Where it judged and passed, the one-frame rule's contradicted fallback (P1609) stands aside.
Verifier change: lens reviews, corpus sweep and fleet comparison before it rides the next surfd generation.
