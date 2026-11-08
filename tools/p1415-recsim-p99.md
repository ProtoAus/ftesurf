# P1415 — report the upper-tail MATCH p99 in the offline pairs census

## Problem / change

`cmd_pairs` sorted negative-pair MATCH fractions in ascending order, labelled a
value `p99`, then indexed `int(n * 0.01) - 1` (clamped at zero). At 100 distinct
values it printed the minimum, not the upper tail. With two values it could print
p99 below its unchanged median.

Use the empirical **nearest-rank** definition: rank `ceil(99*n/100)`, computed
with exact integer arithmetic, and select that one-based rank minus one. This
explicit definition also handles small samples; merely changing `.01` to `.99`
while flooring would still pick the lower value of two. No general statistics
abstraction or detector threshold is introduced.

Pair acquisition/grouping/selection, duplicate filtering, comparison/scoring,
coverage, positive controls, other summary fields and output labels are unchanged.
This is an existing offline diagnostic, not a new signal, calibrated cutoff,
ranking decision, collection/identity/retention permission or enforcement change.

## Acting controls and validation

`tools/test_recsim_pairs_summary.py` invokes actual `cmd_pairs` with acquired
synthetic buffers and controlled comparison results. It checks exact acquisition,
negative/shifted-positive comparison counts and unchanged coverage output, so
suppressing the path cannot pass. These synthetic metrics are not corpus or human
calibration. The existing reader programs separately exercise real comparisons.

- Unchanged reader: 100 distinct fractions printed `.0100` instead of `.9900`;
  101 printed `.0099` instead of nearest-rank `.9901`; two values printed `.25`
  instead of `.9`. All three target assertions failed. Single, measured-zero,
  tied and no-comparable controls passed.
- Corrected source: all seven summary methods pass. The initial test-fixture run
  had wrong output-label/per-map-cap assumptions; its failures remain excluded
  from the genuine three-failure baseline and retained privately.
- Reader families: 40 recsim + 13 numeric + 15 held-reader + 24 held-metadata
  methods run, one existing held-metadata skip. `test_reccheck.py`: 949/0.
- Read-only required runs sweep: 559 recordings + 169 views, 728 acquired
  buffers, 351 pre-existing file faults (no increase over prior 351). The dataset
  grew since P1399; historical byte identity is not claimed. No raw copies kept.
  The first unintended saves expansion refused an owner-protected save; it was
  not skipped or regraded. The required runs-only sweep completed separately.
- The complete module AST outside `cmd_pairs` is identical to the predecessor.
  No parser/metric/recorder semantics, native pin/tag, VM or QC Build change.

- Independent read-only source review: CLEAR. Required clean exact-commit summary
  gate: seven pass, old control three target failures/four passes. An optional
  full parser-file invocation in the deliberately small source closure ran 15
  passes/one missing `test_held_readers` import error; it is retained NOT PASSED,
  not counted as full isolated parser coverage or repaired by expanding this task.
- Actual aarch64/Python 3.11 qualification: direct CLI `--help` acted, corrected
  seven pass, unchanged reader the same three target failures/four controls pass.
  Full source closure hashes stayed exact; no bytecode or fixtures remained.

## Delivery boundary — operator-only, 8 Nov 2026 04:53:08 UTC

Source commit `b98e5db04e1c7ca8f5192ddf1ac906e1d204b965` supplies the four-file
committed Python/test closure, plus its exact predecessor as the control. The
explicit NanoPi operator copy is:

```sh
/usr/bin/python3.11 -I -B /srv/nvme/agent-work/ac-p99-1415-20261108-01a1/tools/census/recsim.py --root /srv/nvme/ftesurf-server/game/data pairs
```

The corrected source SHA256 is
`2780da0b40cc927b0d8a3773eb2328f42afe63bac4d9c368be0c0727b2de66ce`.
The command is an explicit opt-in diagnostic, not a scheduled/new corpus scan;
qualification used synthetic metrics, not production corpus calibration.

Before/after: canonical reader/checker/held-metadata hashes and full file metadata,
all 159 backend bindings and the actual actor, unit/namespace policy and database
inode/mode/owner stayed unchanged; admission remained OPEN. Database contents were
not opened or claimed frozen. No service restart, live lease/gate or listener.
Two local artifact-copy refusals after remote success were preserved, then completed
only from the already-received immutable output; no remote action was repeated.

The live backend pins its reader module's entire source hash. **Do not overwrite
that canonical module or repeat the healthy activation for this CLI summary fix.**
No collector/default-reader deployment, new calibration, native binary/pin/tag or
QC Build update is claimed. The `ENGINE.txt` patch counter tracks this ledger
entry independently of its unchanged native commit/tag, as documented in that file.
The small operator source/evidence root is retained intentionally; no full install,
map library, player data copy or running task process is left there.
