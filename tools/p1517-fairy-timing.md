# P1517 Fairy timing — no demonstrated gain

## Result

The owner explicitly requested measurement alongside the other rig's tests.
Eight accepted warmed runs, four per build, were completed in ABBA then BAAB
order. **P1517 did not demonstrate a gain in this test.** All accepted runs are
included; no performance result was discarded.

| Mean of four per-run FPS readings | P1511 baseline A | P1517 candidate B | Change |
|---|---:|---:|---:|
| Average FPS | 295.4 | 267.2 | -9.5% |
| 1% low / tail mean FPS | 122.3 | 99.8 | -18.4% |
| 0.1% low / tail mean FPS | 95.2 | 78.6 | -17.4% |

These are **observed shared-rig differences**, not proof that P1517 causes a
precise9.5%/17.4% regression. Within-build variation and the different block
outcomes are large. Removing two extrema instructions is not sufficient evidence
of a whole-frame improvement. Do not describe P1517 as a measured performance win.

This isolates the **latest P1517 selected-side change versus P1511** in a matched
diagnostic build pair. It does not measure all cumulative changes or directly
benchmark the normally stamped production1799image. P1507's earlier bounded
sprite result is separate, not added to these percentages.

## All accepted runs

| Order / arm | Build | Average FPS | 1% low FPS | 0.1% low FPS | Frames | Frames in 0.1% tail |
|---|---|---:|---:|---:|---:|---:|
| A1c | Before | 308.7 | 120.5 | 96.9 | 10805 | 10 |
| B1 | After | 258.2 | 104.8 | 84.0 | 9039 | 9 |
| B2 | After | 217.3 | 52.2 | 36.4 | 7607 | 7 |
| A2 | Before | 282.4 | 113.5 | 75.6 | 9885 | 9 |
| B3 | After | 284.1 | 112.4 | 83.3 | 9945 | 9 |
| A3 | Before | 281.7 | 122.2 | 104.7 | 9859 | 9 |
| A4 | Before | 308.9 | 132.8 | 103.5 | 10814 | 10 |
| B4 | After | 309.3 | 129.9 | 110.9 | 10825 | 10 |

Machine-readable rounded readings: [p1517-fairy-timing.tsv](p1517-fairy-timing.tsv).
Total **78,779frames / 280.037sampled seconds**. Every accepted span is35seconds;
printed sampled durations are35.003–35.010seconds and focus-idle exclusions zero.

The initial ABBA block averaged295.5->237.7FPS and86.3->60.2FPS0.1% lows.
The mirrored BAAB block averaged295.3->296.7FPS (**+0.5%**) and104.1->97.1FPS
0.1% lows (**-6.8%**). That block was registered after observing the first block's
negative result, with bounded four-run extension and all-eight retention, not
an independently preregistered replication. The final pair alone shows+7.1%
0.1% low; selecting only that pair would misrepresent the complete result.

## Controls and metric definition

- Map `surf_fairy`, cached main replay33811. Actual warm coverage42.735seconds
  for every arm, actual reset clock0,35second measured window after1.5seconds
  settling. Snapshot BEFORE endpoint status; actual endpoint checks36.794–36.972s.
- Uncapped1920x1200, vsync0, pacing5, MSAA4, reflection MSAA2, render scale1;
  full-effects water/translucency and entities, sprites and lightglows enabled;
  blendsort2, certification/retry1. Actual effective cvar readbacks agree in all8.
- **Important correction:** `psv_lex.cfg` disables sprites AND lightglows. These
  runs explicitly re-enable both AFTER executing that file, confirmed by actual
  readbacks. Earlier smoke that merely executed fullfx before psv_lex was not
  established as full-FX and is not retroactively relabeled by this benchmark.
- Budgets, CSQC budget, profiling and spikes0; the common frame collector1 during
  the window. Identical common dedicated/plugin images, frozen own VMs/configs;
  same four collector source files. Real moving sort traces have admitted
  geometry/edges/work in every arm. No effects reduction between before/after.
- Diagnostic clients A SHA256
  `cf2b18e50d51584c715e28a973c398408bd995024752d59f1f467740a3637e1f`,
  B `f78b8073e1a3e01a1877b0a554463ddd88e16804dca9612ef08c5bc4198ed83a`.
- Average FPS = frame count / printed sampled seconds. Each low is1000 divided
  by the mean milliseconds of the slowest floor(N*fraction) frames, minimum1.
  Aggregate table is the arithmetic mean of FOUR per-run FPS values, **not** a
  pooled global percentile, percentile-threshold FPS or inverse of aggregate ms.
  Tail milliseconds are printed to2decimals; derived digits add no precision.
  Each0.1% tail has only7–10frames; four runs/build do not prove significance.
- Two foreign game processes were observed through most windows; A2 ended with
  zero. The peer benchmark changed between blocks. Matching process counts is
  not matching CPU/GPU pressure; ABBA/BAAB cannot remove nonlinear shared load.
  Report this requested shared-rig measurement, not isolated/portable acceptance.

## Evidence integrity and preservation

The initial A1 attempt stopped at actual warm clock41.7127before its timed
window. Its failed driver/logs/smoke remain retained. A bounded actual-clock
completion corrected that seam; no accepted timing run was excluded. The first
and second accepted-block driver hashes differ only by the authorized ORDER
extension, independently reconstructed. Preliminary resource analysis counted
own client/server as foreign; final analysis subtracts actual own Actor IDs.
The preliminary file remains retained, not silently rewritten.

A separate read-only reviewer reparsed every raw native summary and independently
reproduced the metrics, controls, hashes and conclusions. All8closure/exit
records passed: own fixture/config/cache/binaries exact, temporary CFG absent,
registered own bridge stopped. Console-only copy-disabled output acted in all8;
no clipboard data read/write/restore, foreign lock/HOLD/process changes, build,
source/product changes or deployment occurred during measurement.

P1517 remains installed as previously verified. This measurement does not itself
authorize acceptance, rollback, more repeats or a new release. It establishes
**no demonstrated gain**, not a new positive performance claim. Raw owner-retained
evidence and review stay private; aggregate tables contain no private identifiers.
