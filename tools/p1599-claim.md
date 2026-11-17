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

## Status (17 Nov 2026, later): SHIPPING as v3 -- Lex chose to ship v2's trade (branch p1599-ship)

Lex accepted the round-2 loss on exactly-aligned dense clients (BACKLOG, "Angle cross-check after P1599").
v3 fixes the other round-2 findings:
- Only moves the join can cover (inside the run's clock, outside ghost windows) vote for the sweep's offset,
  and the sweep must join at least ANG_LAG_VOTE_MIN moves there (`sweep_offset`). An empty sweep join used to
  return before the one-frame rule ran, so a sidecar padded with post-end moves' angles lost its fault.
- Stored detail: `angle_off` ends "joined at +N ticks: of M sampled matched moves, K name it exactly and J lie
  within a tick of it; the one-frame figures are at +0 (P1599)" (round 3's wording; v3 said "which K of M
  matched moves name"), `angle_solo` ends "one-frame join at +0 ticks"; `angle_joined`/`angle_dev` say they are
  the sweep's join (and that its first N moves have no frame).
- A tie between +k and -k goes to +k. `vlag != lag` dropped: the gate only opens when the lag is 0.
- Every gate predicate and the in-range vote filter has a test that fails without it (mutation run, 11
  mutants). test_reccheck 1005/0, test_rcptcheck 827/0; test_receipt_angle_reasons has its known `epoch`
  failure (also on main, BACKLOG).

## Status (18 Nov 2026): reviews closed, merged (Claude Code, Linux PC)

Round 3 (three lenses on v3) and its fixes (ba39ae76):
- Evidence: `angle_off` counted moves within a tick as naming the offset (one lobby run: 1,592 near, 1,020
  exact); it now gives both counts.
- Control flow: the ghost-window part of the vote filter had no test; on pre-v9 `.v_angle` sources the sweep
  moved too and the stored text named one-frame figures that source never measures (the move is now v9 only);
  `angle_lag` credited +0 with a rejected winner's vote share.
- Cheater: exact matches confined to a short stretch of a run named a far offset at which the sweep joined
  only that stretch (v3 took 10 moves; main's lag search took 50). A moved join or an accepted lag must now
  join ANG_LAG_COVER (0.75) of what offset 0 joins. Details private.

Round 4 (integrity lens on ba39ae76) found that floor faulting honest delayed pairs: the client draws until it
sees the finish, so offset 0 joins the first S moves and +S cannot (ratio about 1 - S/E). On a short run or one
mostly in ghost windows it fell under 0.75 and the join fell back to 0 -- including a 128-tick run at +34 that
main passes. Fix (105830f3): the floor applies only past ANG_LAG_FREE = 50 ticks; within it the shortfall is the
delay's residue. When the floor alone turns an aligned offset down, the CLI report now says so.

Round 5 (cheater lens on 105830f3): no input goes from FAULT on main or ba39ae76 to OK. The exemption only turns
ba39ae76's FAULT into BLIND, on short (under ~200 judged moves) or ghost-heavy runs, by leaving up to 50 ticks at
the start unjudged -- the residue an honest client at that delay has (and ba39ae76 faulted both). Residue left
to BACKLOG ("Angle cross-check after P1599").

Verified (Linux PC, rebased on main 85d663f9):
- Mutation: round 3 17/17; round 4 6/6 (each exemption, the 50-tick boundary, the CLI note, and each floor).
- test_reccheck 1040/0, test_rcptcheck 827/0; test_receipt_angle_reasons only its known `epoch` failure
  (identical on main).
- Pi lobby evidence, main vs 105830f3, read-only (18 Nov): 521 same-run pairs -- 150 FAULT -> BLIND, 90 FAULT
  stay, 279 BLIND and 2 OK unchanged, none newly faulted; 203 other-run sidecars -- all 199 main faults still
  FAULT; 0 exceptions. Identical, pair for pair and offset for offset, to ba39ae76 and (where both have the pair)
  to v3.
- Local sweep (the Windows install's data/, 1,026 .rec): files with faults 469 -> 467; both are local saves
  going FAULT -> BLIND (a clock step moved the offset; saves never become receipts).

Deploy: reccheck.py rides the next surfd generation (backend-pending.md); P1580's export and
`--reread-receipts` then apply it to stored rows.
