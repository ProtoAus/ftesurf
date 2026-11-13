# P1540 — independent prefix timing survives unsupported closing shape

## Problem

A recognized but unsupported closing-record width set global clock-quality loss,
removing finite accepted-prefix timing observations as well as unavailable whole
closure timing. Lifecycle exclusion must remain effective without conflating those
independent quantities.

## Change

Keep a boundary-only timing-availability flag for the two width-failure paths.
Withhold unsupported whole duration and cap endpoint while retaining independently
finite prefix timing. Preserve all recognized boundary/order/partial rules and
all pre-existing unusable body/base/full-width-clock gates. No recording schema,
consumer projection, policy/threshold/rank, native pin, tag or QC Build change.

## Verified

Existing HID fixture adds20assertions. Actual expanded fixture against unchanged
P1539:1623checks/exactly2prefix-rate-loss failures; same fixture with repair1623/0.
Healthy finite/absent-end controls act, malformed records stay faults and publish
no whole timing, body tails remain excluded, and old unusable-clock controls
continue withholding timing. Ordinary CLI and captured receipt behavior checked.
REC949/0, receipt800/0, structured32/0, snapshots12/0, stored receipt suite0fail.
Fresh134HID/751REC-VIEW reports and input hashes unchanged, existing faulty counts
3/356unchanged. Original fixture/collector/argument failures remain private proof,
not passed controls. Independent review and actual deployment remain separate.

Final native image qualification is P1538, unchanged: Windows/ARM1814/0 and clean
patch1538stamp with zero new same-target warnings. Reader correction does not
qualify hardware/calibration/full-world/HFR, a new Root, deferred audit or the
postponed human check. No data regrade or writes.
