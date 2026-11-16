# P1599 claim -- ftesurf-a8, 17 Nov 2026

The .view/.rec angle cross-check stops accusing honest lobby runs: the reader joins at the tick offset the
frames' own angles vote for when that vote is decisive, and the 0.05 deg one-frame rule abstains when that
offset holds only to within a tick (network delay wobble). Fleet survey 17 Nov: 234 of 2,322 lobby receipts
carry an angle FAULT; at the voted offset none of them would (sweep rule max 3.4% vs the 5% fault line).
Files: tools/reccheck.py (angle_join), tools/test_reccheck.py; docs BACKLOG, AGENT_NOTES. Verifier change:
independent lens reviews before it goes to the Pi (with the follow-up backend generation's tools pass).
