# P727 — surf / zoned-bhop completion scope

**LIVE ACCEPTED — 2026-10-15T15:35:36Z.** Guarded schema19 cutover and the
requested prior-bulk-setting reset are complete. All12 lobbies are restored;
live completion is1752 maps:1367 surf plus385 file-zoned bhop, with no unzoned
bhop, unrelated-mode or manually disabled leakage. The NanoPi/deployment
coordination hold is released. Earlier refusals/holds below are historical;
see **Live acceptance** for final evidence and honest UI limits.

## Problem and policy

The owner's admin map disables were real, but completion's population was an
independent union of playable maps and main boards, without reading the pool.
Thus both the website and in-game have/not-beaten lists still counted those maps.

One effective pool now admits `surf_`, plus `bhop_` with an actual authoritative
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

## Pre-cutover fleet census and requested state reconciliation

Read-only 2026-10-15 census:2082 BSPs;1432 surf,580 bhop,70 other-mode maps.
Bhop385 have actual zone files and195 do not. The previous bulk admin overrides
had ALL385 zoned bhop disabled plus142 unzoned bhop. The new rule therefore needs
both code and reconciliation of those earlier bhop-only overrides, not just a
fresh UI. This is not permission to override future per-map admin disables.
The authorized plan was to reset only prior bhop bulk exclusions to automatic
policy, using a mode600 exact map-pool snapshot and conditional recovery while
preserving unrelated overrides. The completed reset is recorded below. All run/map/zone files and history remain in place.

Investigation correction: an initial SQLite read addressed a nonexistent
`data/directory.db`, creating an empty zero-byte file. It was verified as created
by that exact immediately preceding command and removed; all real DB reads used
`mode=ro`. No existing DB/table was removed.

## Historical ordinary-deployer refusal — resolved by guarded cutover

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
  scheduler/config/pool changes. At that stage no successful live acceptance
  receipt existed. Raw live operational metadata is kept private, not in this report.
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

The pre-cutover read-only live API control reproduced the bug:1762 completion entries,
including8 bhop without a zone file and22 other-mode entries, while all385 zoned
bhop were manually off. On that captured population the requested automatic
policy would retain1347 surf plus385 zoned bhop (1732); this is a target, NOT a
claimed live readback. No pool reconciliation was performed without the code.

## Historical preparation and player hold — resolved below

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
- The pre-cutover read-only preflight refused ONLY connected player/spectator presence.
 No native gate/config/cvar/service, scheduler, forwarding wrapper, live runtime,
 database or pool setting has changed. The old generation remains OPEN.

**Earlier blocker:** the fleet had to be empty before this reviewed handover
could act. Do not disconnect players, weaken the ordinary deployer's refusal, or
mistake preparation/review for an accepted serving worker. Recheck current
fleet/source provenance and coordinate other pending fleet work before resuming.
After guarded acceptance, reset only the owner's prior bulk bhop exclusions to
automatic policy with snapshot/CAS, verify385 zoned/195 unzoned outcomes (or a
fresh census), and repeat the live public-site/actual-game proof. No unrelated
schema20 upgrade, old-runtime mutation or automatic DB rollback is authorized.
That end-to-end falsifier is now closed by the live acceptance below.

## Live acceptance — guarded schema19 and requested setting reset

Final readback **2026-10-15T15:35:36Z**, serving compatible source
`bf054235bc2ec73b4d9a2cd685f3bc228f5978bf`:

- The owner-authorized guarded handover completed with old generation CLOSED,
  new generation OPEN and schema19 unchanged. CLOSED candidate acceptance
  measures exact logical equality of **all27 tables**. No player/run/board/zone
  history was discarded and no schema20 substitution or automatic DB restore
  was used.
- An unrelated transient process caused an initial strict-census park after
  native drain. Explicit forward recovery was separately reviewed and verified;
  the original journal was retained, not reset, and no foreign process was killed.
  This failure is retained as evidence, not relabelled a successful first attempt.
- The exact snapshot/CAS reset removed **only527** proven prior bulk bhop
  exclusions. **All4 unrelated setting rows remain unchanged.** Eligible zoned
  bhop follow automatic policy; fileless bhop stay automatically off (195 in
  the earlier library census). Future explicit per-map disables still take priority.
- All12 native services are running. Config bytes/modes, original runtime cvars
  and autosave settings are restored; all12 heartbeats were fresh (maximum age
  5.5 seconds at readback). Guarded cron, forwarding wrappers and launchers match.
  Backend health, lobby feed and profile-map routes return HTTP200.
- Final population is **1752 =1367 surf +385 file-zoned bhop**. Every returned
  map is checked against the zone-file rule and manual disables: zero forbidden
  entries. The earlier1732 figure was a projection from an older snapshot,
  not the accepted count.
- Real public Chrome DOM expands **all1752** completion entries and matches the
  public API map set. A real dedicated-socket game client using the existing
  fleet SSQC/CSQC bits shows the same1752 denominator and per-tier total/done
  counts; screenshots were inspected. No owner game, consent or config changed.
- Final observational boot controls retain exact CLOSED asset/credential pins,
  but attest ordinary shared progs/proof-reader/credential updates afresh on
  OPEN worker boots. Immutable application bytes/origins, critical paths,
  generation and schema remain strict. Both independent review findings were
  fixed and re-reviewed: current worker UID/argv/start/executable checks and
  binding the CAS/receipt to the exact validated master/worker/guard epoch.
  Final focused controls pass:39 serving/settings,6 real-file CAS,5 explicitly
  seam-mocked orchestration tests, plus10 isolated real Gunicorn worker arms.
  External-asset mismatch uses changed expected digests, not a new real verifier
  revision. Actual live CAS kept its worker unchanged; a subsequent ordinary
  worker rotation has emitted the new OPEN observation fields.

### Remaining limits, not claimed fixed

The real game client holds at most **1000 maps of one tier** (`PF_CTROWS`). Its
unrated tier is1341 here: counts match the web, but only1000 rows are held. This
pre-existing list-cap behavior is NOT full unrated-row browsing acceptance.
An initial public profile navigation also rendered **HTTP504**; an alternate
reference loaded successfully. The failed endpoint/root cause was not isolated,
so this is neither a universal profile-performance pass nor an attributed filter
regression. Both follow-ups have concrete falsifiers in BACKLOG.md.

### Ownership and cleanup

The coordination hold is released; normal deployment guards still apply. The
sealed serving runtime/control/recovery are deliberately retained and marked
LIVE/RETAIN, not disposable scratch.25 owned stopped Linux runtime/home controls,
8 Windows game rigs and4 anonymous browser caches were verified and retired;
unique source/config/DB/log/witness/screenshot evidence remains private. No
native/QC binary, engine pin/tag or Build number changed for this backend fix.

Owned local evidence: C:/FTESurf-worktrees/completion-1015102256/.
Owned remote synthetic evidence: /srv/nvme/agent-work/completion-1015102256/.
The refused normal deployment's separate surfdship ownership receipt is retained;
those copies are not a serving runtime. Disposable copies are archived/retired
where verified safe; no other session's runtime root is a cleanup target.
