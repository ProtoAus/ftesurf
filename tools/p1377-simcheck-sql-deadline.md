# P1377 — selected similarity reads observe the pass deadline

Source acceptance, not installed/live-backend or whole-resource-bound acceptance.

## Change and contract

The existing similarity pass has a monotonic admission deadline. Its explicit,
connection-owned SQLite ReadBudget previously checked selected VM instruction work
only. It could finish a selected statement after that deadline before the next
cooperative admission check. This was the documented cooperative contract, not a
previously promised hard timeout that was silently broken.

Bind the earlier of the existing read/pass deadlines while public collection owns
the pass; restore the prior value in finally. A selected statement checks before
starting and at its existing SQLite progress callbacks. Deadline interruption is a
ReadDeadline subtype of ReadLimit, distinguished from VM exhaustion. The existing
conservative instruction-quantum reservation is preserved. If stopping predicates
coincide, branch order chooses the reported cause, not measured physical precedence.

Execute/fetch stay inside one owned handler scope: return a complete result or
raise, never selected prefixes. Callback/cursor teardown remains statement-scoped.
Late deadline cancellation prevents new admission but retains completed comparisons
and their existing short atomic flush. Its time cause propagates even when a prior
read deadline is stricter than the normal pass deadline. No-budget borrowers do not
acquire, replace or clear an arbitrary foreign callback. Production sweep already
constructs this opted-in budget; no new command/config/schema/process is required.

No metric, source capture, threshold, rank, retention, identity, raw field, parser,
clock model, historical row, recovery format or default enforcement changes.
Legitimate metadata retirement before expiration is not rolled back or called a
measurement. No source snapshot is re-read/regraded/backfilled by this change.

## Acting controls and independent review

The existing ordinary REC9 synthetic factory and real parser first store three
80-opportunity comparisons. After actual metadata-retirement preparation, an owned
SQLite fixture grows and advances a fake monotonic clock inside the real selected
query progress callback, with a one-million-step VM allowance still unexhausted. The exact ffed2432
predecessor completes the query and fails only the required callback-return1
assertion after positive controls act. The new source interrupts it, reports time
rather than VM exhaustion, preserves the full prepared SQL snapshot and resolves or
admits no partial work. The same budget subsequently executes a real recursive sum
of500500 beyond the old deadline, showing scope/handler cleanup rather than silence.
This is a recorded SQL string at execution plus callback observation, not an SQLite
authorizer, exhaustive query-boundary coverage or a numerical elapsed measurement.

Other controls cover real VM exhaustion, foreign callbacks/connection rejection,
SQL error, nested tighter scopes, BaseException restoration and unchanged ordinary
comparison. The stricter-deadline time case preserves one completed80-opportunity
flush while stopping further admission. That time case uses a mock reader with
synthetic metrics; it is not a second real-recording/native-performance proof.
Two independent reviews, predicate/ownership and evidence/data flow, are CLEAR.

Windows: all30 existing similarity programs return0;276 unittest executions yield
270 passes and six existing platform skips, plus68 standalone checks. Skips remain
four unavailable SQLite error-attribute cases and two POSIX cases, not passes.
Existing isolated-admin warnings remain visible; this is not globally warning-free.
Actual ARM Python3.11.2/aarch64: SQL8 and time15 pass, zero skips; identical predecessor
targetcase has exactly one expected interruption failure, not an import/setup error.
The15 time executions include imported/inherited controls, not15 newly written tests.

Original fixture-observer failures are retained privately: normal retirement slot2
needed preparation before the preservation snapshot; all30 Windows programs passed
but a global empty-TMP/cache assumption found three old test-created homes and the
intentional explicit-py_compile stale-PYC control. Their four exact disposable files
were individually verified/retired after child exit, without repeating the bank.
First ARM transport copied an old embedded packet and ran no tests; one bounded
same-prefix packet repair produced the current-hash-bound23-pass/control proof.
Mistaken small source overlays and original errors are retained, not qualified data.

## Limits and delivery

Only opted-in selected SQLite VM work observes this deadline. Small statements may
finish between callbacks; blocked I/O, lock waits, user-defined functions, schema,
writes/flushes, comparisons, total RSS and total pass time are not hard-bounded here.
This does not close the resource leaf or establish hardware/calibration/fleet proof.
No reader949/corpus/native build was repeated: this patch changes none of those
reader/parser bytes. Older A221 reader/corpus evidence remains that older scope;
upstream header-admission changes are not qualified by these SQL tests.

Reviewed collector SHA256:
`ebbb8d0fab50862e3093c2336ec2ab2b90da26926ec66284fbd801b7bf8f9c0d`.
Installation and live provenance must be recorded separately. The owner completed
P1368's prerequisite and its READ-ONLY actual-runtime audit passed at2026-11-07T14:29:19Z
(see tools/p1368-simcheck-source-reader.md). That live collector is stillffed, NOT this
ebbb source. This feature needs a fresh source-bound candidate; never edit P1368's
serving package or repeat its healthy activation.
Native pin/tag, VM and QC Build remain unchanged by P1377.
