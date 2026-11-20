# P1613 command rule on real runs (21 Nov 2026, worldofsurf-6f)

The reader on branch p1613-cseq (541165ed, now merged to main), run read-only over every real pair of a `cseq`
recording and its client's .view: the owner's local install (three runs with a .rec kept beside the .view) and the
Pi's evidence uploads since the 20 Nov 10:18Z lobby deploy that carried the recorder (each .view paired with its
run's .rec by the header runid). The driver is kept in the private task root.

| Run | Source | Joined to own command | On no drawn path | Worst | Frame / between |
|---|---|---|---|---|---|
| surf_borderlands_css 0007653 (owner) | local | 7651 of 7653 | 0.00% | 0.00 deg | 56% / 44% |
| surf_borderlands_css 0009557 (owner) | local + evidence | 9538 of 9541 | 0.00% | 0.00 deg | 68% / 32% |
| surf_happyhands 0004873 (owner) | local + evidence | 4873 of 4873 | 0.00% | 0.00 deg | 57% / 43% |
| 0000640 (another player) | evidence | 637 of 640 | 0.00% | 0.00 deg | 52% / 48% |
| 0000432 (another player) | evidence | 405 of 432 | 0.00% | 0.00 deg | 96% / 4% |

Every pair was judged (>= 100 joined moves) and none faults; `reccheck` reports all files ok. The rule FAULTs past
1% on no drawn path. Only four evidence uploads arrived in the window (about ten a day, most before the recorder
deploy), so the fleet is small; the next generation's sweep is the wider check.

Merged with one fix: the verbose printer's key list lacked `angle_cmd`, so the rule's figure was computed and never
shown. Tests: test_reccheck 1081 checks 0 failed (29 new), AG 7/7; test_rcptcheck 827/827 on the Pi (Flask).
