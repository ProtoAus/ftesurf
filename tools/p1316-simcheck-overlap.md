# P1316 — preserve one diagnostic observation across collector overlap

## Problem

Selection excludes an already-observed pair in either order, but another collector
can finish while the first reads the files. The old final insert only excludes the
same order. Reversed overlap can therefore store/count two observations of one
pair. SQLite's connection context also does not itself open a transaction for a
legacy autocommit connection; a failed flush could leave a cursor and partial rows.

## Change

The existing short flush explicitly owns its SQL transaction, preserving configured
IMMEDIATE/EXCLUSIVE modes and handling legacy autocommit. A fresh idle check refuses
a transaction opened by a reader callback without borrowing, committing or rolling
it back. The checkpoint acquires the write lock before a final two-order point
lookup for each insert. The first participating flush wins; cursor and actual new
observations commit or roll back together. File comparisons remain outside.

There is **no schema, capture, input, identity, format, API, verdict, badge, consent,
default, threshold or ranking-policy change**. No lease/reservation or historical
row rewrite/deduplication. Existing stored duplicates stay as recorded. Native
source/pin/tag and QC Build are unchanged by P1316; published P1314/P1315 are retained.

## Verification and current state

- Untreated exact published writer: original **13** cases have exactly **3**
  predicted reversed-overlap failures; the other **10** controls pass. Additional
  **4** ownership/mode cases have exactly **3** predicted failures and the
  configured-mode positive passes. Original failures remain retained.
- Subject **17/17** pass. Two real independent SQLite connections and the real
  bounded parser act on synthetic 80-row/short sources, including an actual
  reversed competing collector. Original winner captures/values remain exact;
  all-lost work advances its checkpoint without reporting a new observation.
  Real insert-abort/cursor/transaction traces, caller-owned work, legacy duplicates
  and configured isolation modes provide acting positive/negative counterparts.
- Supported Linux Python 3.11.2 / SQLite 3.40.1: all **25 existing similarity
  programs** pass through their standalone entrypoints, **202 unit cases** with
  no typed-SQLite skips, plus the executable legacy checks. The untreated writer
  reproduces exactly six predicted failures across the combined 17-case suite.
- Reader **949/0** on Linux, after adding the exact committed QC file required by
  its static source-contract check. Fresh RUNS byte/presence/meaningful-stat sweep
  matches the prior classified **544 recordings / 168 views** and unchanged parser
  helpers: existing **344 record / 7 view** faults preserved, **zero drift**, NOT a
  clean corpus or a new raw reparse. No SAVES claim or player-data writes.
- Two independent read-only source/evidence reviews return **OK with notes**, no
  blocking counterexample. The reviewed implementation/tests remain byte-identical
  through published-upstream integration. Actual three-VM c24 NoDeploy compilation
  reports zero warnings; no native build/deployment is implied.
- Publication and guarded backend delivery remain **pending** until separately
  recorded. Original Windows discovery failure, 120-second reader timeout and
  Linux missing-test-dependency abort are retained, not regraded. The legacy
  executable test exits successfully at import and is not a unittest-discovery
  module; its printed checks never made that discovery invocation green.

This is store-only diagnostic consistency. It does not establish complete fleet
coverage, work reservation, a hard whole-job time/RSS/SQL bound, current-source
freshness, or uniqueness against old/external writers and arbitrary DB triggers.
Selected admission-read budgets and historical snapshot semantics are unchanged.
No numerical performance, human/ranked or broader native-bank acceptance claim.
