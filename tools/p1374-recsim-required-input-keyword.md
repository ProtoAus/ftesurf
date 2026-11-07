# P1374 — own ordinary input keywords before payload validation

Source/test acceptance at this boundary, not installation or live promotion.

## Problem and change

The existing recorder grammar defines one `in` row per simulated move, not per
packet. The similarity projection already owns malformed required rows and returns
unavailable rather than measuring their surviving prefix. Its exact token dispatch
protected `fzin`, but ordinary `in` still depended on a literal trailing space.
Thus bare `in` or `in\tbad` could disappear as unknown records in the older ordinary
path: an80-row input with one malformed row became a measured79/79 match.

Use the already-computed exact whitespace token for ordinary `in` admission too.
Both known keywords now reach their existing payload check. Valid ordinary tabs and
leading whitespace retain all rows; unknown `input`, `inert`, `in-extra` stay unknown.
Do not broaden this to all unknown events or change encoding/invalid-byte policy.

Headers, numeric conversion/ranges, clocks, bounds, offset selection, match/support,
minima, captures, schemas, history, thresholds and default enforcement are unchanged.
Native REC13/15 validation still runs later. The reproduced gap is an old ordinary
projection dispatch error, NOT proof of a native-witness bypass or complete native
validation. No new source signal, cutoff, accusation, authenticity or tier follows.
No stored observation is repaired, re-read, regraded or backfilled.

## Acting original control and fixed subject

The existing ordinaryREC9 synthetic factory supplies80 distinct move rows. The new
case first proves valid80/80 matching and existing malformed `in 0` abstention.
Replace ONLY the final row with bare `in` or `in\tbad`. The exact predecessor15e
performs79 actual comparisons, matches79/79, reports moves79/80 and preserves raw
SHA/byte/source captures and buffers BEFORE each final required-row verdict fails.
The same selected testcase has exactly two expected failures, not setup/import errors.

Fixed subject: all ten existing parsing cases pass on Windows3.10 and actual ARM
3.11.2/aarch64. The same predecessor/test pairing reproduces the two targeted final
verdict failures on ARM. Malformed inputs now return textual unavailable detail and
`parse_rec` returnsNone, not metrics or a measured zero. Valid whitespace variants
keep80 rows with exact captures. Unknown-word controls, fractional conversion, fzin,
legacy behavior, supported native13/15 comparisons, bad witness and unsupported
viewing-clock cases keep their meaning. No actual metric is mocked by this testcase.
Independent source review CLEAR; no MUSTFIX.

## Existing banks and corpus

All36 Windows programs return0: five recsim programs/27 unittest cases pass;30
similarity programs/273 cases yield267 passes and six old platform skips, plus68
standalone checks; reader executable949 checks/zero failed. Aggregate300 unittest
cases/294pass/6skip is separate from those68 and949. Skips remain four unavailable
SQLite result-code attributes and two POSIX ownership/FIFO controls, not passes.

Current source checkerA221c7ee was used for the bank/corpus. Actual Windows installed
checker remains3eab465a; that is not silently upgraded or implied by source testing.
Same732 raw files:554REC/178VIEW/zeroPART, exact before/after hashes/sizes and input
domain. One working in-process checker sweep receives564 primary/standalone-view
CLI inputs, with paired views included automatically, and returns1 for the same351
existing faults(344REC/7VIEW). All732 report blocks match the prior multiset after
private absolute-path/CR normalization; diagnostics are not suppressed or regraded.
The771-Python-file source inventory stays exact throughout validation.

ARM contains only small source overlays/fixtures, not an install, native executable,
application/DB process or listener. Own subprocesses are reaped; tmp empty/cache
prefix absent. Only three exact Windows test-created temporary homes were individually
retired after child exit; no player or unrelated data was cleaned up. Original
observer/authoring failures are retained privately, not reclassified as passes.

## Delivery limits

P1370's15e reader and checker3eab/heldmetaA3f7 were the last confirmed dual-Windows
installation before this source fix. P1374 installation must be recorded separately
with inspected source, exact preimage/ACL/index and actual installed-path checks.
NanoPi reader changes remain serialized after P1368's actual owner cutover output,
namespace/current-data proof and a freshly bound reader plan. No source review or
synthetic result establishes that live state, a hard resource bound, genuine/current
client coverage, calibration, enforcement, historical freshness or whole-fleet pass.
Native pin/tag, VM and QC Build stay unchanged.
