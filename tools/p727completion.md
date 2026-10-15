# P727 — surf / zoned-bhop completion scope

## Problem and policy

The owner's admin map disables were real, but completion's population was an
independent union of playable maps and main boards, without reading the pool.
Thus both the website and in-game have/not-beaten lists still counted those maps.

One effective pool now admits `surf_` and `bhop_` with an actual authoritative
online/local JSON zone file. Other modes and bhop without a file are automatically
off. Embedded BSP timers alone do not satisfy the requested bhop-file rule.
An explicit admin disable still excludes an otherwise eligible map. The admin
UI shows automatic-disable reasons and refuses an enable that cannot be honoured.
Both numerator and denominator, both profile map-list APIs, the admin, map feed
and lobby allocator use the same policy. No generic historical board/run row is
deleted. Surf's previous untimed/manual-console behavior remains; configured
rotations and occupied lobbies are not rewritten or interrupted.

Completion retains its old base population (held main board OR installed+timed),
then applies the policy. It does not invent beatable entries for unzoned surf
with no board. No player records, evidence, recorder, native/QC code or Build
number change. HTTP freshness remains30 seconds; file discovery uses the existing
five-minute library TTL. Manual disables are read on every completion request,
even if profile/main-board caches are warm.

## Acting controls

Clean product base `2de3726fa566fdf343ef79ffd1bc51b896deb319`; engine documentation
base `a528fb76e07647504789b2cdc436ec08e23f1d99`. No canonical peer edits built.

`surfd/test_completion_pool.py --source <pristine-base>/surfd --control`:
**5 checks, zero failures**, including positive eligible controls and actual
leakage of admin-disabled, unrelated-mode, unzoned and embedded-only bhop maps.
Subject: **32 checks, zero failures**. Both web/game populations and counts,
local-only zone file, warm disable/re-enable, schema migration preservation,
automatic file add/remove, manual disable precedence, admin refusal, feed,
allocator and non-deletion all acted. Admin JavaScript parses via Node.

Targeted web, board, join, map-pool, variants and KSF top-up suites pass on Windows.
Join's previous unzoned-bhop acceptance assertion was deliberately updated for
the requested policy and retains an acting untimed-surf control. Windows admin
has two UDP timing/cache failures; the untouched source reproduces EXACTLY those
two failures. They are not hidden, fixed or counted as passing. No UI pixels or
Linux-only deploy properties are inferred from those Windows tests.

Deployment planning now closes app/admin/mapmanifest/template together (including
other already-required KSF/social groups). A synthetic committed dependency test
requires all four, and a missing committed template must fail even if its working
file exists. The regular Pi deploy suite also includes the new completion test.

## Fleet census and requested state reconciliation

Read-only 2026-10-15 census:2082 BSPs;1432 surf,580 bhop,70 other-mode maps.
Bhop385 have actual zone files and195 do not. The previous bulk admin overrides
had ALL385 zoned bhop disabled plus142 unzoned bhop. The new rule therefore needs
both code and reconciliation of those earlier bhop-only overrides, not just a
fresh UI. This is not permission to override future per-map admin disables.
Only the prior bhop bulk exclusions will be reset to automatic policy, with a
mode600 exact map-pool snapshot and conditional rollback; unrelated overrides
remain unchanged. All run/map/zone files and history remain in place.

Investigation correction: an initial SQLite read addressed a nonexistent
`data/directory.db`, creating an empty zero-byte file. It was verified as created
by that exact immediately preceding command and removed; all real DB reads used
`mode=ro`. No existing DB/table was removed.

Full Pi/native suite, exact delivery, policy reconciliation and live/UI receipts
follow after execution. Owned root: C:/FTESurf-worktrees/completion-1015102256/.
