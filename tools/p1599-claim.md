# P1599 claim -- ftesurf-a8, 17 Nov 2026

The .view/.rec angle cross-check stops accusing honest lobby runs: the reader joins at the tick offset the
frames' own angles vote for when that vote is decisive, and the 0.05 deg one-frame rule abstains when that
offset holds only to within a tick (network delay wobble). Fleet survey 17 Nov: 234 of 2,322 lobby receipts
carry an angle FAULT; at the voted offset none of them would (sweep rule max 3.4% vs the 5% fault line).
Files: tools/reccheck.py (angle_join), tools/test_reccheck.py; docs BACKLOG, AGENT_NOTES. Verifier change:
independent lens reviews before it goes to the Pi (with the follow-up backend generation's tools pass).

## Status (17 Nov 2026): PARKED -- not merged, not deployed (branch p1599-review: 01680065 v1, 156ce8ed v2)

Finding (fleet survey, copy of receipts+pubkeys only): 231 of 2,322 lobby receipts carry an angle FAULT (22
players); the deployed reader and main re-read 229 of them as FAULT. In each, the frames' exact angle matches
name one offset (+3..+34 ticks), and at that offset the sweep rule peaks at 3.4% (cut 5%); the join stays at 0
because no offset holds to 0.05 deg on these networked clients (2.6-88% of one-frame ticks miss it, any lag).
Angle verdicts are admin-only (`receipts.angles`); ranking reads only `sig`.

- v1 (the one-frame rule abstains when nothing aligns): rejected in review round 1. The miss rate that switched
  it off is what a silent assist raises, so an assist on >2% of ticks disabled its own detector; the offset-0
  guard read the client's own tick column; the vote share counted matched moves only, a move up to 3 times.
- v2 (only the sweep rules join at the named offset; one-frame rule unchanged): Pi corpus 235 -> 90 FAULT, all
  273 foreign-sidecar pairs still FAULT, no new faults. Round 2: on clients that DO align exactly but draw
  several frames a tick (124 BLIND pairs in the fleet), an assist that breaks the alignment used to fault via the
  offset-0 fallback while its honest twin passed; v2 passes it (the untouched moves name the true offset, and
  the sweep tolerance hides the assist). Plus a lost-fault path when the sweep join is empty, and stored detail
  naming one offset for two measurements.
- Gates tried for a v3 (exact-match share of sampled moves; share of joined moves off the drawn path within a
  tick): they stop dense assists and large isolated ones, not small ones, small blocks or a constant lead.

Conclusion: one pair cannot tell "aligned client + small lie" from "honest client whose delay wobbles". What
can: whether the same player's client aligns on its other runs (the per-player baselines leaf). Probes and
fleet numbers: private cheatanalysis/p1599-angle-wobble-limits.md.
