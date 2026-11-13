# P1539 — preserve availability and recognized journal boundaries

## Problem

Rejected touchpad quantities could cancel into a measured zero; kind-only source
rows could skip existing availability guards. Unusable keyboard observation still
supported cause prose, and touchpad mode attribution differed from native integer
semantics. Recognized closing/cap records lost lifecycle meaning when their clocks
or shape were unusable. Two existing snapshot suites also had stale expectations
for an already-retained partial-coverage boolean.

## Change

Reuse per-quantity availability and pointer completeness guards, independently
retain usable sibling counters, and withhold unsupported causal prose. Reuse the
native-compatible integer parser for touchpad mode. Track recognized cap/end
boundaries separately from usable clocks, preserving body/closing order, duplicate
checks, partial lower-bound direction and present-but-unusable versus absent end.
Reconcile stale snapshot expectations without exposing withheld numerical totals.
No capture/schema/profile/threshold/ranking, historical regrade or QC Build change.

## Verified

Existing HID fixture gains77assertions: final original matched product1603/50fail,
subject with the same fixture1603/0. Earlier pre-edit1590/39control and all actual
fixture/collector failures are retained privately, not relabelled. REC949/0,
receipt800/0, journal diagnostics32/0, snapshot12/0. The two baseline stored-receipt
expectation failures reproduce unchanged against the original product, then pass
with only the same partial-boolean expectations corrected (zero production code
change in that suite). Ordinary CLI and captured receipt metrics preserve healthy
comparisons and real zero while rejected quantities become unavailable.

Fresh original/subject134HID and751REC/VIEW reports and input hashes are identical;
existing faulty-file counts3and356are unchanged, not valid-data certification.
No historical data written. Independent re-review, ARM/final deployment
qualification and live data-preservation gates remain separate. Human test stays
postponed; deferred vulnerability audit remains out of scope.
