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

## Delivery boundary

Windows/source qualification and independent source review are complete. Clean
exact-commit verification and actual ARM operator-only qualification/delivery are
pending.
The live backend pins its reader module's entire source hash. **Do not overwrite
that canonical module or repeat the healthy activation for this CLI summary fix.**
Any operator-only copy must be explicitly named and hash verified, with the live
default reader/checker/held metadata, services and namespace left untouched.
No current collector/default-reader deployment or new corpus calibration is claimed.
