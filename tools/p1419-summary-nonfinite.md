# P1417 â€” stored numeric infinity is not a measured sample maximum

## Problem

The authenticated detail projection already withholds a stored non-finite MATCH.
The existing offline `simcheck.summary`/`summary_line` instead aggregated a
historical compared `+Inf` row into `same_max=inf` and the notable notice. The
new-comparison finite guard is already delivered and is unchanged; this fix is
about reading historical data, not collecting a new signal or rewriting rows.

## Change / representation boundary

If any compared row contains a persisted **numeric infinity**, withhold the whole
summary using fixed state `nonfinite`, existing fields `None`, and a fixed
unavailable line. Do not filter away that row and call the remaining sample clean,
return a measured zero, reclassify verdicts/skips or mutate/backfill history.

One internal aggregate flag is added to the same existing grouped sample query.
`typeof(match)` restricts the predicate to SQLite numeric storage classes;
comparison against the exact binary64 finite extrema detects both infinities.
These are representability bounds, **not similarity thresholds or a new MATCH
range policy**. Existing finite values (including large/out-of-range values),
measured zero, skipped rows, identity grouping, NOTABLE, other metrics, legacy
codes, sample query count/result-row bound and explicit SQL read budgets remain.
NULL/TEXT/other-metric eligibility is not newly defined or made equivalent to the
stricter detail projection. No new schema, storage/output counter or evidence type.

A first MIN/MAX prototype passed the pure-numeric matrix but was independently
falsified with mixed SQLite storage classes: legacy TEXT sorts above numbers and
can hide numeric +Inf from both extrema. Its result/failure is retained, not
credited as final evidence. The final per-row flag handles that case without
projecting the legacy text or extending its acceptance contract.

## Acting validation

- Unchanged published source: actual authenticated detail withholds a compared80
  `+Inf` row, while the real summary prints `inf` and the at-or-over notice.
  Finite `.75` and positive-opportunity zero controls pass. Protected history
  tables and schemas remain value-for-value unchanged across the reads.
- Genuine sign/identity matrix: all six target subcases fail before correction;
  skip-infinity and finite-extreme controls pass. The initial matrix's assumed
  reset of AUTOINCREMENT caused five fixture errors; those are retained and NOT
  counted as product failures. The corrected fixture addresses its explicit
  synthetic source id, never resets the sequence or changes schema.
- Corrected source: **32 Windows methods pass** across the existing authenticated
  detail7, summary9, SQL-budget6 and finite-collector10 programs. Covers mixed
  TEXT masking, whole-sample withholding, history/schema preservation, finite
  recovery, fixed group count, owned budget cleanup and distinct SQL limitation.
  Baseline existing test ResourceWarnings/proxy warning are retained; no unrelated
  fixture/logging repair is claimed.
- The complete module AST outside `summary` and `summary_line` is unchanged.
  No comparator/parser/new-observation/cursor/ranking/threshold or recorder change.

## Delivery boundary â€” operator-only, 8 Nov 2026 05:54:25 UTC

Independent read-only source review is CLEAR. The exact module/test bytes were
verified in their clean owned qualification checkout and match the reviewed
Windows execution inputs. Publication uses P1419 after relinquishing a conflicting
unpublished 1417 label; published peer reservations 1417/1418 are preserved. A post-commit
receipt check initially rejected only the reservation document's Git CRLF-to-LF
normalization; its identical normalized content was verified without another commit
or test run. Product/test/ENGINE bytes were exact throughout.

Actual aarch64/Python 3.11: selected-module import, synthetic stored `+Inf` and the
real SQL summary entrypoint acted. All **nine pure summary methods pass**. The
unchanged module running the identical nine methods has the expected seven target
failure entries (six sign/identity subcases and the TEXT masking case, across two
methods), with seven other methods passing. These are nine ARM methods, not the
32-method Windows authenticated/collector/budget bank. No bytecode or fixtures left.

The explicit operator module is retained at:

`/srv/nvme/agent-work/ac-summary-1417-20261108-01a1/subject/simcheck.py`

SHA256: `34627c0060b140891007a3dc4a8970431dd3ba94a0a16c476d88cd45e497895c`.

The retained directory's `1417` is the original qualification label, **not this
product's patch number**. Its source, paths, logs and qualification clock were not
renamed, restaged, rerun or redated for the reservation correction. The original
local claim was recorded at 05:27 UTC; the conflicting peer publication is dated
05:40 UTC, which does not establish when the peer first reserved it. We yielded
the unpublished label rather than disturb the published reservation.

The only non-test caller is the existing sweep `--dry-run` diagnostic; normal
collector/daemon execution does not call this summary. **No backend or canonical
runtime is updated.** Its existing pinned module remains deliberate. Selecting
the new operator-only copy avoids perturbing a healthy backend merely for an
unused-in-daemon helper body. For an authorized operator who intentionally wants
to read the existing production sample, this explicitly selected, read-only command
is available; qualification did **not** execute it or inspect production contents:

```sh
/usr/bin/python3.11 -I -B - <<'PY'
import sqlite3, sys
sys.path.insert(0, '/srv/nvme/agent-work/ac-summary-1417-20261108-01a1/subject')
import simcheck
conn = sqlite3.connect('file:/srv/nvme/surfd/data/surfd.db?mode=ro', uri=True)
conn.row_factory = sqlite3.Row
try:
    print(simcheck.summary_line(conn, read_budget=simcheck.ReadBudget(conn, 1000000)))
finally:
    conn.close()
PY
```

Before/after qualification, canonical helper metadata, the default runtime module,
all 159 backend bindings and actual actor, unit/namespace policy and database
inode/mode/owner were unchanged; admission stayed OPEN. Database contents were
not opened or claimed frozen; no app/namespace-import probe or service restart.
The three-file operator/control/test copy and evidence are intentionally retained;
no full install/map/player-data copy or task process remains there.

No production database or corpus has been inspected for this change. No production
prevalence, calibration, performance, live backend promotion or new collection,
identity/retention permission, native binary/pin/tag or QC Build change is claimed.
The extra aggregate adds SQL work: an existing explicit VM budget can exhaust
sooner, honestly returning limited rather than a partial measurement. No unchanged
runtime, hard time/RSS or full metric-validity bound is claimed. The `ENGINE.txt`
ledger counter advances independently of its native pins.
