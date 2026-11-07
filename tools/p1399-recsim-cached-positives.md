# P1399 — construct positive controls from acquired recordings

## Problem and change

The offline `pairs` census acquired and grouped recordings, then parsed each
pathname again when constructing its same-recording, shifted-epoch positive.
If a path disappeared, the tolerant reader returned `None` and the census aborted
at `b.mt`. Different later bytes also need not represent the acquired stream.

Use `copy.copy` on the acquired `Rec`, then replace only the copy's `mt` list.
The comparison reads the other shared fields without modifying them. This avoids
that extra pathname read and preserves the original acquired clock and moves.
No comparison predicate, threshold, acquisition filter or output category changes.

## Acting controls and falsified hypothesis

Two added methods in `tools/test_recsim_parsing.py` use eligible, owned synthetic
80-row files. A one-move difference compares at 79/80; actual `cmd_pairs` exercises
one negative and two shifted-epoch positives before any fault injection.

- Acquisition regression control: a third malformed file raises only under the
  existing `strict=True` interface. The default reader already records `SKIPPED`,
  returns `None`, and leaves the valid group comparable. This works on EB51 and
  subject: the suspected acquisition-exception bug was **falsified**, not fixed.
- Positive-source control: a wrapper delegates to the real parser, removing the
  first owned file only if its path is parsed a second time. EB51 actually rereads
  it, receives `None`, and aborts. Subject calls the real parser once per file,
  exercises both positive controls, leaves files present and preserves each
  acquired object's original `mt` and `moves`. It does not replace metric results
  or fabricate parsed recordings.

The final predecessor run executes both methods: acquisition passes and exactly
one controlled positive-reread failure remains. Initial failed control predictions
are retained separately: wholly different zero-match streams had 76-row support,
not the predicted 80; the final one-move-difference fixture fixes that ambiguity.
An initial `assertRaises` without `strict=True` was an incorrect API assumption.
No product metric, minimum or malformed-input policy was changed to fix a test.

## Validation and limits

- Full parsing16, numeric13, opportunities6, limits3, captured-source4,
  unreadable4 and held-reader15 methods pass without new warnings.
- Held metadata: 24 methods run, one existing skip.
- `python tools/test_reccheck.py`: 949 checks, zero failures.
- Same read-only runs CLI/procedure: 554 recordings, 168 paired views, identical
  722 input buffers and summary, 351 pre-existing faults before/after.

This is an offline diagnostic positive control, not a new detector, independent
human performance or field calibration. Historical numerical measurements are not
remeasured or regraded. The live collector uses `compare_paths`, not this loop.
Acquisition parse/hash/stat remain separate, non-atomic reads; avoiding a positive
reread is not a whole-pass immutable snapshot or resource ceiling. No source
capture, parser, defaults, storage/schema/history, enforcement, native pin/tag,
recording format or QC Build change. Deployment provenance is recorded separately.
