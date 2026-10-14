# P714 — KSF top-up authority and bounded retained admission

Source-only continuation of `p713ksffinal.md`. No live SSH/crawl/install/reload,
cron edits, game/GPU/native build or fleet Watch acceptance.

## Reproduced collector gaps and change

- Explicit top-ups discarded actual fetched pages and submitted the entire
  cached board as fresh, including a completed board needing no request. This
  bypassed the cache-only protection for a same-time/same-date seed replacement
  and could restore/relink its superseded demo from retained bytes.
- `topup_step` now retains actual page rows separately from whole-cache filing.
  The watch filer reads the whole top-up cache through `board_rows`, authorizing
  only exact identities present in this tick's page answers. Both initially
  owed and non-owed boards, no-page completion and interrupted acknowledgements
  keep durable owed intent. Refusals leave partial pages owed, not fresh.
- A queue of 256 current cold requests excluded a later retained repair forever
  at zero request allowance. At most two retained candidates per discovery pass
  may now displace unattempted cold intents; any retry or strike metadata stays.
  Provenance **presence is scheduling priority only**, not identity authority.
  The unchanged exact binding/hash/PB checks, 256-slot cap and two-original cap
  still gate installation. No retained-directory scan or network budget change.
- Priority is conditional: a queue containing only retained or previously
  deferred intents is not forcibly evicted. Per-job delays and bounds remain
  intentional; this is not a guarantee of repairing every archive in one tick.

## Acted offline collector controls

Owned evidence root:
`C:/FTESurf-worktrees/ksfaccept-20261014T181832Z/artifacts/`.

- `topup-red-control.log`: original-code no-page and unrelated-fresh-player
  subcases both restore stale A over current seed B. A genuinely fresh A passes
  the positive arm. `topup-red.log` is a retained earlier harness invocation:
  its larger demo reservation wrongly permitted unrelated cold-demo transport.
- Final top-up regression covers both initial owed states and all three page
  arms; zero demo allowance forbids transport while local retained recovery can
  act on the positive fresh binding. Fresh unrelated rows still file, and owed
  markers clear only after successful filing/acknowledgement.
- `coldqueue-red.log`: original source passes the 255-cold positive control,
  then fails the 256-cold case with `(0,0)` instead of the required `(0,1)`.
- `collector-frozen.log`: **31 tests, OK**. Includes one-original/zero-fetch/
  zero-sleep/ID-reuse saturation proof, admission/recovery 2+1 over three retained
  jobs, queue-cap checks and unchanged strike-only/future/expired retry records.
- `importer-final.log`: 106 assertions, 0 failed. `topup-final.log`: 8 tests, OK.
  `backend-final-status.tsv` records 19/20 existing backend scripts passing;
  untouched `test_admin` retains its two documented Windows closed-UDP/
  amplification/snapshot failures. Recplot skips the absent native corpus;
  mapwatch skips Windows mode/flock/SIGALRM arms. None is counted as green.
- `collector-closure-review.md`: independent frozen-source review returns
  **OK with notes**, limited to source/parent evidence inspection. It explicitly
  documents protected-queue conditional admission, not unconditional fairness.
  LSP records no diagnostics; Python tests are the execution evidence.
  Native replay grammar and evidence semantics are unchanged; no native/QC
  build, engine commit/tag pin or QC Build-number bump is needed.

## Immutable collector publication proof

Feature SHA `eaad87288f0c37699fc8b6602ed021f477224037` passes all ten existing
exact-commit delivery groups (`collector-committed-deploy.log`) and the real
flattened collector/index/API suite at 31 tests, OK. The feature is published
through inspected merge `f7f340ebd220a485c7e8e51e6e7cf1932cadf50c`; a concurrent
published R2 tooling commit advanced main during the first push. Only the three
R2 tool files were merged, and every KSF source/proof/deployer byte remains equal
to the verified feature. No history rewrite or uncommitted peer work was used.
Engine ledger-only SHA `fa85c3d9a91881bb0b66470b37760392982307a8` is published;
engine source/pin/tag and QC Build stay unchanged.

## Delivery and final acceptance

An isolated worker corrected three source-proven delivery gaps:

- Immutable Git modes are planned/installed/verified alongside raw bytes. The
  final tooling commit adds only executable bits, not byte edits, for all five
  documented direct `surfd/*.sh` entrypoints. Historical refs retain their own
  modes; same-suffix fixture files prove no permission guessing/working-index
  influence.
- A persistent remote flock excludes cooperating deployers through backup,
  installation, raw-byte/mode checks, replacement-worker acceptance and final
  invocation/full-commit-specific ACK. Fresh bounded phase ACKs refuse holder
  loss; final ACK under flock is point-in-time acceptance, not permanent state
  or exclusion of noncooperating/manual writers. EOF/wait/dispose is bounded
  and never signals another process or unlinks the lock.
- Rollback DB/file tags are invocation-unique and name creation is exclusive.
  Actual same-tag controls preserve older rollback bytes/SQLite witness; new
  tags act. Historical/new owned retention shapes exclude hand-made backups.

`delivery-fixes/RED.log` retains original actual-body failures. Windows mode
proof explicitly uses narrow install/stat shims; byte and SQLite behavior and
WSL flock/interleaving are real owned fixtures, not live operations. Worker
`FROZEN.log` has15 groups and flattened28 at the original assigned base; parent
`delivery-integrated.log` has15 groups and flattened31 at integrated collector
f7f340e. Independent `delivery-closure-review.initial.md` approved the three
original mechanisms but caught a P1 evidence-loss edge: stage cleanup before
final ACK removed failure logs without an accepted receipt.

`receipt-red.log` reproduces both old-tail refusal/lost-stage arms while the
positive success acts. Corrected code accepts before success-only cleanup;
pre-ACK failure retains suite logs and records no acceptance, while post-ACK
cleanup failure warns and records accepted/cleanup-unconfirmed with an exact
inspection path. The independent follow-up closes P1, then correctly notes that
a lost cleanup result cannot prove retention. `cleanup-wording-red.log` acts on
that distinction; the corrected extra arm removes the stage before transport
failure yet still reports unknown cleanup, never false retention.
`receipt-green.log` passes all three initial focused groups; final focused and
assembled16-group results exercise actual AST-extracted flow and guard with
owned naturally exited/echo helpers. Only stage transport is mocked; bounded
EOF finalization is unchanged. `delivery-assembled.log` has16 groups and nested
collector31, OK, before the final two-line status wording refinement. Immutable
candidate16-group controls are recorded in the owned checkpoint.

Requires pwsh7/git/sh and WSL Ubuntu-22.04 on Windows. DrvFS cannot prove POSIX
mode semantics; Windows mode shims prove manifest forwarding/predicates only.
Native Linux chmod/stat/direct-execution acceptance remains pending. No actual
SSH/transport/install/backup/reload/cron/game/GPU or fleet Watch ran. Future live
gates are preregistered in the owned `LIVE_ACCEPTANCE_PLAN.md`, not authorized
by these offline results.
