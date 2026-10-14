# P713 — KSF final collector and backend delivery gates

Claimed after fetching both public repositories on 2026-10-14: published engine
patch headings and canonical untracked pNNN tests both topped out at712. Work
started at published QC cd38708 and fast-forwarded the unrelated published P712
source to265e8b1 without touching either canonical checkout's peer changes.

## Problem / Change

- Older owed/cached boards could undo a known equal-time/same-date seed record
  replacement, making its superseded original linkable again. Cached rows are
  now marked separately; only exact row identities fetched THIS tick have board
  authority, including mixed owed/fresh boards and --from-maps. Tied cache-only
  identities cannot override a known replacement. No monotonic record-ID rule.
- Real --watch --go --demos with --max0/1/2 skipped local recovery when its demo
  reservation was zero. Opt-in controls invocation; the reserved allowance
  controls only network requests. Shared lock and original-read bounds remain.
- Failed normalized publication could strand a newly retained original without
  job lookup. Exact-job intent now publishes before original/normalized bytes;
  intent whose bytes never completed follows the existing missing-byte path.
- A sub-cap board may advertise a 5,000-digit numeric filename component,
  raising ValueError during discovery. The common ASCII leaf validator caps
  length at255 before candidate parsing, persisted admission or fixed-origin
  request construction. Malformed rows cannot request/park the host or block
  a following valid row.
- Backend delivery's publication query failed open and destination hashing
  could apply text filters. Query errors now refuse before scratch/transport;
  raw installed hashes explicitly use --no-filters --.
- Reload verification could accept the old worker, global process counts and
  historical readiness. It now snapshots direct workers under the inspected
  master, requires all old workers retired and exactly one new child, that PID's
  fresh ready line, health, remote exit and positive completion markers. Log
  identity/offset handles rotation; a monotonic deadline caps health/sleep to
  the remaining60-second budget. Raw app log tails are not printed.

## Verified: source and offline, not live installation

Owned evidence root:
C:/FTESurf-worktrees/ksffinal-20261014T172533Z/artifacts/

- VALIDATION_PLAN.md records predictions, acted controls and limits.
- oversized-red.log reproduces integer conversion crashes and oversized map
  filename admission on old source. Collector tests cover255/256 boundaries,
  all three oversized numeric fields, candidate/job/fetch refusal without
  transport, and successful valid-row linking without host parking.
- review-red.log reproduces all three collector findings. Real CLI cases cover
  maxima0/1/2 with zero requests; the publication fault recovers retained bytes
  while the host is parked. Original red failures are retained, not counted
  as suite successes.
- collector-precommit.log:28 final-source collector/index/API tests, OK. This includes an acted
  malformed --from-maps regression introduced during authority tagging and
  fixed before commit (malformed-frommaps-red.log).
- fresh-authority-corrected.log independently exercises mixed owed/fresh watch
  and --from-maps, requiring only the exact freshly fetched identity to gain
  board authority. fresh-authority-final.log repeats it against final source.
  fresh-context-red.log reproduces the additional validity/player-context gap;
  fresh authority requires valid rows AND matching player identity, not just
  a shared record key. fresh-authority.log retains a failed test-double invocation
  (positional vs keyword fetched argument), not a product failure.
- delivery-red.log: original committed script falsely accepts CRLF/LF filtered
  equivalence and stale readiness/worker scenarios; publication failure reaches
  the explicitly forbidden scratch actor. No SSH or workspace is created.
- delivery-operational-red-retry.log reproduces log-rotation refusal and a205s
  fake health/wait budget before the follow-up fixes. The first short dispatch
  timed out; its partial evidence is retained separately, not counted as pass.
- delivery-final.log:10 delivery groups, OK. Actual shipped shell bodies act
  against fresh/draining/rotated workers and stale/historical/wrong-PID/master/
  health/process/signal refusals. A slow-health actor grades the60s budget.
  Both missing-codec arms and collector/converter suite failures still propagate.
- Codec9, importer106 assertions/0 failed, top-up8, board, replay, web, variants,
  sweep and the other12 deployment backend suites return zero in separate owned
  homes. No canonical database, player data or upstream source is used.
- Two read-only reviewers each make an initial source pass and a retained-child
  follow-up. Their introduced malformed-row and operational findings are
  reproduced and closed with focused controls; their earlier reports remain
  unchanged and are not represented as independent execution of the final code.
- Final exact-source-commit delivery run, flattened28-test collector, inspected
  SHAs, publication readback and cleanup states are recorded in the owned
  CHECKPOINT.md. Working-tree tests and committed tests are distinct receipts.

## Deferred delivery / acceptance

No upstream crawl, game/GPU, QC/native build, SSH, install/reload, cron enablement
or live Watch acceptance is claimed. The KSF matched runtime set remains the
three backend Python files plus two allowlisted codecs. A selective delivery
must name the exact inspected committed/published SHA; first inspect PlanOnly:

```powershell
pwsh -NoProfile -File tools/surfd-deploy.ps1 -PlanOnly `
  -Ref <inspected-published-sha> -Only surfd/ksfimport.py
```

The resulting five-file plan must include ksfgrab.py, ksfimport.py, surfd.py,
ksfconvert.py and ksfreplay_info.py. Unrelated P710 presentation, templates,
configs, QC progs and release changes are not approval to ship here. Live work
still needs destination raw-hash verification, successful replacement-worker
acceptance and coordinated gradual --demos crawler enablement under the shared
lock/budget. Retain failed stages/backups; never infer service acceptance from
an offline fixture or a historical boot line.

Stages, CSS100, map-build identity, codec clocks and native evidence semantics
remain guarded. Engine pin/tag, native binary, QC Build and release unchanged.
