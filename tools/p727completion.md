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
Final subject: **34 checks, zero failures**. Both web/game populations and counts,
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

## Verified source, NOT deployed — guarded-runtime blocker

Feature `22eedb8449b1a92c243ae8dc0727e7c9e115ca99` and inspected merge
`6727635357614d582303c6688107f491a9889451` are published on main. The merge
retains the portal author's published engine pin/tag; this task did not build
or ship any native/QC artifact. The tested backend bytes are unchanged by that
merge. Patch-log documentation: `ebe8fd44166745fb29c8ba3477ddb3510610bd67`.

- Offline deployment tooling:20 tests PASS, including matched map generation,
  missing committed dependency, transfer-byte mutation, lock/acceptance/cleanup
  and legacy-ref controls.
- Exact main-source Pi stage:all24 backend suites plus codec PASS, including
  native admin (no Windows UDP failures) and initial completion31 checks.
  Node was unavailable there; its syntax assertion passed on Windows. MOM video
  conversion lacked its external `.mtv` fixture and remains an explicit skip.
- The ordinary deployer made its mode600 SQLite recovery copy, then REFUSED the
  real process-identity gate BEFORE source copy, reload, schema migration,
  scheduler/config/pool changes. No successful deployment/acceptance receipt
  exists. Raw live operational metadata is kept private, not in this report.
- Investigation found production is a sealed guarded schema19 generation, not
  the ordinary canonical application launch. Main's schema20 is separate work.
  Do NOT relabel pinned hashes/locks, overwrite that immutable runtime, start a
  second OPEN guard or replay the completed schema18-to19 transition.

A minimal compatibility candidate was therefore prepared on the EXACT inspected
live source base `a9dce85f27f94b6c89672b6b63fc5659801ebe4c` without schema20,
portal QC/native or unrelated features. Runtime candidate
`7d8bad7a4aacf04d6700e0fbe326405f55fe10fd` is published on
`agent/completion-p727-schema19-1015` (not main, to avoid a schema downgrade).
The final test/docs commit on that branch is
`bf054235bc2ec73b4d9a2cd685f3bc228f5978bf`; its runtime modules are unchanged from
`7d8bad7`. Its actual pristine generation19 control passes5; compatible subject34 passes.
All23 generation19 backend suites plus codec PASS in an isolated Pi stage. An
initial older `test_ksfgrab` invocation omitted its required `--out`; that failed
staging premise was retained, corrected, and only the remaining7 suites rerun.
Expanded installed-admin-vs-feed scope checks then pass33 natively (34 Windows,
minus the explicitly skipped Node assertion). Runtime modules are byte-identical
to the full native-suite candidate; only extra tests/docs follow it.

Synthetic actual UI proof: Chrome's real board DOM contains exactly the expected
five have/not-beaten maps and3/5 completion; a REAL dedicated-socket game client
using the compatible API reports tier2 maps5/5 done3 and draws the SAME five
entries. Both screenshots inspected. The historical9 runs remain separately
visible: preserving history is intentional, not completion leakage. Owned client,
server and browser handles were reaped. Initial fixture setup attempted to add a
Flask route after requests (refused); the next game arm used outdated consent4
and correctly refused profile networking. Final fixture uses current consent5,
without touching owner consent/configs. A late scope check incorrectly assumed
uninstalled maps belong in the admin manifest; the original installed-only
runtime contract was restored unchanged, and new tests pin both that omission
and the disabled uninstalled feed row. Failed logs are retained, not passed.

A read-only live API control still reproduces the bug:1762 completion entries,
including8 bhop without a zone file and22 other-mode entries, while all385 zoned
bhop were manually off. On that captured population the requested automatic
policy would retain1347 surf plus385 zoned bhop (1732); this is a target, NOT a
claimed live readback. No pool reconciliation was performed without the code.

## Authorized guarded handover prepared — live hold remains

The owner subsequently authorized the separate guarded same-schema19 handover.
Its operator implementation has passed independent implementation review with
limits: no remaining critical ordering, lock, ownership or promotion defect was
found. This is readiness evidence, NOT live acceptance.

- **42** authored Linux operator checks PASS, including actual CLI lock contention,
 schema19 backup, all-table preservation/refusal, compatible source provenance,
 effective dependency/configuration checks and pre-promotion refusal sequencing.
- Three real distro Gunicorn/gthread product-worker arms PASS in isolated homes
 and databases: full closure accepted, foreign dependency origin rejected, and
 incorrect proof-tool pin rejected despite valid six-module witnesses. Each arm
 now measures whole-schema19 preservation. A fourth arm deliberately alters an
 isolated fixture row and correctly REFUSES preservation rather than reporting
 it passed; this corrects an evidence overclaim found during review.
- The new generation is staged CLOSED. It is limited to four inspected P727
 application/template overlays; all other executable/resource paths match the
 compatible source, with old ancillary tests explicitly pinned separately.
- The latest read-only preflight refuses ONLY connected player/spectator presence.
 No native gate/config/cvar/service, scheduler, forwarding wrapper, live runtime,
 database or pool setting has changed. The old generation remains OPEN.

**Remaining blocker:** the fleet must be empty before this reviewed handover can
act. Do not disconnect players, weaken the ordinary deployer's refusal, or
mistake preparation/review for an accepted serving worker. Recheck current
fleet/source provenance and coordinate other pending fleet work before resuming.
After guarded acceptance, reset only the owner's prior bulk bhop exclusions to
automatic policy with snapshot/CAS, verify385 zoned/195 unzoned outcomes (or a
fresh census), and repeat the live public-site/actual-game proof. No unrelated
schema20 upgrade, old-runtime mutation or automatic DB rollback is authorized.
BACKLOG.md retains the end-to-end closing falsifier.

Owned local evidence: C:/FTESurf-worktrees/completion-1015102256/.
Owned remote synthetic evidence: /srv/nvme/agent-work/completion-1015102256/.
The refused normal deployment's separate surfdship ownership receipt is retained;
those copies are not a serving runtime. Disposable copies are archived/retired
where verified safe; no other session's runtime root is a cleanup target.
