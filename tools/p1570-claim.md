# Patch 1570 claim — deferred owned similarity source selection

Claimed15November2026 after inspecting both fetched public repositories, engine
patch headings, active worktree untracked pNNN files and existing public claims.
P1569 is already reserved; this claim is P1570 only, not a range.

Scope: stop the owned store-only similarity collector spending a small selected
SQL allowance on source rows it cannot use before its first comparison. Keep the
independent source cap, later unresolved-source opportunities, rotation/recovery,
raw-byte observation capture and generic callers' existing semantics.

The source change and regression tests are independently reviewed and qualified
on Windows and Linux; a platform-specific new test expectation was corrected
against independently authored raw bytes, with the original failed test retained.
This reservation is NOT publication of the source fix or a live-delivery claim.
No new detector, calibration, global hard resource/fairness bound, capture/default,
retention, ranking or enforcement change; no native pin/tag or qcbuild bump.
