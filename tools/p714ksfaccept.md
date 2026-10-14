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

## Delivery and final acceptance

Collector source is independently approved and offline verified. A separate
isolated delivery worker is correcting executable manifests, transaction-wide
exclusion and rollback-tag collisions; that tooling work is not a collector
acceptance claim. Its final controls and exact-commit offline acceptance will
be recorded separately when complete. Native Linux mode acceptance remains
separate from Windows shell-manifest/shim tests. Live fleet deployment and
public Watch behavior remain explicitly deferred.
