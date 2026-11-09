# P1452 — native keyboard-registration accuracy (claimed)

Claimed9November2026 after refreshing both repositories and inspecting published
headings/claims and canonical untracked pNNN paths. Maximum1451. The earlier
unpublished P1451 native draft collided with ftesurf-1d's published GC claim;
that historical draft/review is retained privately, not a second P1451 release.
Current baselines engine74d27b5bd / QCa669a32b. One number only:1452.

Scope: existing Windows keyboard registration/observer lifecycle, input-thread
ownership and exactly-once dispatch, including successful and refused Windows
transitions and real production teardown/reinitialization resource lifetime.
Evidence-integrity/input-safety maintenance, not new capture/privacy/blocking,
thresholds/ranking, human attribution or calibration. P1450 fixed reader claims
ONLY; native remainder is not yet qualified.

Initial native helper controls passed but two independent reviews BLOCKED the
first implementation's retained-binding/free-resource restart interaction;
that is being corrected with acting lifecycle controls. Normal build is still
blocked by its dependency environment, no native exe/install/push/tag claimed.
Full build, independent updated-source reviews, commit/tag/pin and actual dual
Windows deployment remain. The separate paused compiler/file-writer audit is
not part of this patch. Backend P1447+P1448 queue is tools/backend-pending.md;
its coupled files go in the next guarded backend generation, not this native fix.
