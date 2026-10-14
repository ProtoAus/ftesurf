# KSF backend delivery preparation (source-only continuation)

P706 implements native original-file playback and automatic advertised-demo
import. See [p706ksf.md](p706ksf.md) for codec/clock/binding limits and its separate
runtime evidence. This continuation fixes delivery tooling only: it does not
alter the playback or collector, install files, enable cron, or claim GPU gates.
No engine/product patch, native pin/tag, QC Build or release increment.

## Exact-commit ship-set

`tools/surfd-deploy.ps1` resolves `-Ref` once to a full immutable commit SHA.
Archives and destination blob hashes use that SHA, not a mutable branch name.
A local plan is available without SSH, installation or workspace creation:

```powershell
pwsh -NoProfile -File tools/surfd-deploy.ps1 -Ref HEAD -PlanOnly
pwsh -NoProfile -File tools/surfd-deploy.ps1 -Ref HEAD -Only surfd/ksfimport.py -PlanOnly
```

Choose the exact inspected/approved commit before any real deployment. `HEAD`
above is only a planning example, not approval to ship a peer's feature. The
plan lists `Commit`, `Files`, `Destinations`, `AddedDependencies`, and `StageFiles`.
A normal full deploy now installs the two runtime codec files, rather than merely
staging them for tests:

| Commit source | Destination relative to the backend home |
|---|---|
| `surfd/surfd.py` | `surfd.py` |
| `surfd/ksfimport.py` | `ksfimport.py` |
| `surfd/ksfgrab.py` | `ksfgrab.py` |
| `tools/ksfconvert.py` | `tools/ksfconvert.py` |
| `tools/ksfreplay_info.py` | `tools/ksfreplay_info.py` |

On P706+ refs, selecting either importer or either codec with `-Only` expands to
this matched five-file set and reports the added dependencies. Selecting only
`surfd/surfd.py` remains a narrowly scoped app update; it does not implicitly
replace importers. For a complete KSF update, select an importer or use the full
deploy. Other tools are stage-only and cannot be selected for installation.
Unknown selections and missing committed dependencies fail; a working-tree file
cannot repair a dependency missing from the requested commit. Refs predating
`ksfgrab.py` retain their old runtime layout.

The entire app/tool/shared Python test set is staged even with `-Only`. The
stage keeps checkout-relative paths; the installed backend is flattened as
shown above. Progs still use `src/build.ps1 -Pi`, and crawler scheduling remains
a separate operator-approved operation. This script does not enable `--demos`.

## Gates and ownership

The backend deployment suite includes `test_ksfgrab.py --out <owned-stage>/tmp/ksfgrab`
and the offline codec suite `tools/test_ksfconvert.py`. Both failures propagate
to the suite's remote exit status. `TMPDIR` is exported before `mktemp` command
substitution, so test homes stay inside the owned stage.

A real deployment creates exclusive uniquely named roots under
`C:/FTESurf-worktrees/surfdship-.../` and
`/srv/nvme/agent-work/surfdship-.../`, with OWNER records before population. It
never reuses or deletes a preexisting stage at startup. The remote stage is
outside web-served/live backend paths. On failure, report and retain the exact
owned stage and its logs; on verified completion remove that disposable stage
and retain the local ownership/plan receipt. Live database/file backups are
NOT disposable scratch. Existing database backup, sweep lock, hash comparison,
reload and health gates remain required for an actual deployment.

## Offline reproduction and limits

```powershell
python tools/test_surfd_deploy.py --out C:/FTESurf-worktrees/<owned-task>/artifacts/shipping -v
```

Requires an ancestor `OWNER.md`, pwsh 7, git, sh (plus cygpath and WSL
`Ubuntu-22.04` on Windows), and backend Python dependencies. Uses only synthetic Git repositories, flattened
committed-file layouts, mocked transport functions, and owned shell fixtures.
No game, GPU, HTTP listener, upstream request or remote deployment is performed.

Measured in the source-only continuation:

- Seven deployment-tool test groups pass: complete/narrow/default sets and
  destination mapping; invalid path/ref refusal; transport-free/scratch-free
  PlanOnly; old-ref compatibility and missing committed codec refusal;
  flattened layout import controls and collector/API; the actual deployment
  suite shell's output arguments, owned test homes and two failure controls;
  PowerShell parser gates.
- Flattened-layout `test_ksfgrab.py`: 17 tests pass using real SQLite/index/API
  code and synthetic original bytes. Removing either installed codec fails
  module loading; restoring it acts and the collector/API suite passes.
- Existing offline codec (9 tests), KSF import/top-up, board and replay suites
  pass separately. No QC or native source/build changed.
- First run exposed two harness assertions, not product failures: the app-only
  selection was intentionally narrow, and the existing collector suite has
  17 tests rather than the harness's stale expectation of 16. Failed run evidence
  is retained; subsequent corrected runs are separate.

Evidence/checkpoint: `C:/FTESurf-worktrees/ksfship-20261014T1627Z/artifacts/`.
Native subagent tool was not exposed in this continuation; no independent-child
review or alternate runner/provider is claimed. GPU/performance gates belong
to the other bot. Live NanoPi staging, installation, worker reload and scheduler
enablement are **not verified by these offline gates** and remain deferred.

## P713 final-readiness follow-up

The original seven-group snapshot above is historical. The current offline
suite has10 groups, including fail-closed publication queries, raw installed
bytes despite Git text filters, and the actual reload shell. Reload now requires
the same master, all snapshotted old direct workers retired, one new worker,
that PID's fresh app-ready line and health plus a successful remote exit.
Log identity/offset handles rotation; a monotonic60s budget also limits health
and sleep. Global counts, historical boot lines or old health cannot pass.

Two read-only reviewers and pre-fix acted controls exposed/closed the collector
and delivery gaps. The final collector has28 offline tests; exact-commit and
flattened receipts, controls, commands and unverified live gates are recorded in
`tools/p713ksffinal.md` and its owned checkpoint. Nothing here approves unrelated
presentation/config/template/QC changes, a release or crawler enablement.

## P714 collector and tooling continuation

The collector now has31 offline tests. Explicit top-ups separate actual fresh
pages from durable whole-cache filing, and bounded retained priority corrects
pristine-cold queue saturation without evicting retry/strike records. Protected-
only queues remain conditional admission, recorded in BACKLOG.md.

The deployer carries executable modes from the same immutable Git tree as
bytes, installs those modes and verifies both at the destination. All five
documented direct `surfd/*.sh` entrypoints have mode-only Git100755 changes;
their bytes stay unchanged. Historical refs retain their own recorded modes
(including644), rather than deriving mode from a suffix.

A persistent remote flock covers backup, installation, raw-byte/mode checks,
worker/reload acceptance and final commit-specific receipt ACK. Cooperating B
cannot install between A's verification and acceptance. The ACK under flock
is the point-in-time acceptance, not a guarantee against later deployments or
noncooperating/manual writers. Acquisition, fresh ACKs and EOF teardown are
bounded; holder cleanup never unlinks a lock or signals a process.

Rollback tags include an invocation nonce; both SQLite and file backups reserve
names exclusively. Collisions refuse without replacing older rollback points.
Script-owned DB retention recognizes old and nonce-bearing tags, never handmade
backups. Success-only stage cleanup follows acceptance: pre-ACK failure retains
all stage/log evidence; post-ACK cleanup failure warns and reports an accepted
receipt with cleanup-unconfirmed status and an exact path to inspect. A lost
cleanup result cannot falsely claim that the remote stage still exists.

The actual-body offline suite adds mode/backup/interleaving/holder-loss and
receipt-cleanup controls (16 groups). Windows requires WSL for genuine flock,
SQLite and byte-copy controls, but install/stat shims prove mode forwarding and
predicates only: DrvFS cannot prove native executable permission. Native Linux
chmod/stat/direct-execution and approved live fleet/Watch gates remain separate.
Evidence and limits: `tools/p714ksfaccept.md`. No live transport, installed files,
actual reload, crawler, release or fleet Watch success is claimed here.
