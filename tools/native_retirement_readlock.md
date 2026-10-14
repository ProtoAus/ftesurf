# Native Windows retirement readability seam

`test_update_native_retirement_readlock.py` adds a separate gate; all previously
accepted helpers/graders remain immutable. It verifies the retained signed
821-row win64/all closure, binary/build receipts and PE text companion. Fixtures
are complete at attempt3 with a >6MiB protected local zone edit, three valid named
staged objects, unreferenced objects, and failed-temp/part/install siblings.

The owned first-byte LockFileEx lock shares READ/WRITE opens. A separate handle
must open successfully and fail ReadFile with error33 before launch and after
natural job0; after release it must read the authored first byte. This is not
share-denial. Full exports occur only after release and job0. Failed phase guards
remain retained even if containment/export succeeds.

Predictions: source87326b33 wrongly boots and retires despite failed reads;
source7321da29 refuses with `Unreadable signed recovery content; nothing installed.`,
without the startup actor and without changing any seed bytes. Released cleanup
must boot with the actor and remove exactly the journal and its three signed
staged objects. Complete file and directory namespaces are compared, including siblings;
completion permits only JSON-equivalent state.json reformatting. Exact captured
`ftesurf/logs/journal-locked.log` and `journal-released.log` additions are the
only log allowance. Install lock is preseeded empty and remains byte-graded.

## Invocation

Use native UCRT Python with its bin directory on PATH, under the external
immutable serialized-native.py named-mutex wrapper. Set FTESURF_TEST_SCRATCH,
TEMP and TMP to owned scratch under the task root. Required arguments:
`--engine --symbols --build-receipt --feed --objects` (repeatable),
`--runtime-root --evidence`; runtime/evidence must be disjoint fresh paths.
Add `--expect-defective` only for the blocked87326b33 receipt. Runtime and
full exports are retained; the driver does not deploy or delete fixtures.

`test_update_native_retirement_readlock_unit.py` has portable mutations for
refusal versus actual retirement, required retirement action, raw refusal
ledger immutability, semantic completion ledger, edit preservation, added files,
missing siblings, empty extra directories, and release/export/job0 ordering. Set FTESURF_TEST_SCRATCH
before running. Units are not native acceptance.

Bounds: first-byte readability and namespace/process behavior, not power-loss,
hostile path races, exhaustive lock offsets, or product deployment acceptance.
