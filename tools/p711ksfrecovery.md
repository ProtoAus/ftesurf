# P711 — exact-current KSF retained-original recovery

Source-only continuation of `p706ksf.md` and `ksf-deployment.md`. No game/GPU,
network crawling, remote installation, reload, cron edit or live Watch claim.

## Change

The backend already retained originals before transactional replay indexing,
but interrupted indexing and missing normalized files fetched them again. New
installs write `.originals/job-<binding-sha256>.json`, a direct lookup for the
exact map/course/style/player/runid/millis/date/advertised-file binding. Raw
originals remain content-digest named; provenance is bounded to 16 KiB and the
whole original is hash checked before the unchanged codec/transaction can act.
Neither JSON nor guessed filenames choose a path. Symlink provenance/originals
refuse. An archive without new lookup metadata is a cache miss: no scan or
implicit migration of older provenance.

Each tick may read/reconvert at most two retained originals, including attempts
whose original is missing or corrupt. A third known retained job waits rather
than falling through to a redundant download. Repair works during shared host
cooldown and with a zero network maximum; existing per-job retry delays still
apply. Missing original bytes may use the ordinary remaining request allowance;
corrupt/mismatched local data defers only that job, not the whole upstream host.
Admission rotates in the persisted queue even when original bytes are missing,
so two leading misses cannot starve a later intact original during cooldown.
Deeply nested, sub-cap JSON is also a local deferral, not a whole-tick failure.
The existing `(requests, linked)` result still counts only actual network calls.

A related exact-current-binding correction distinguishes seed metadata without
an advertised file from metadata without a record identity. Equal raw time with
unchanged/unknown ID/date preserves the known board binding. A known different
ID/date invalidates the old demo until authoritative board/file metadata arrives.
Older, slower and rounded-only seed updates remain non-authoritative. Retained
bytes never override either current-PB check or turn imports into native evidence.

## Predictions and controls

Task-owned evidence root:
`C:/FTESurf-worktrees/ksfrecover-20261014T1657Z/artifacts/`.

- `recovery-red.log`: the pre-change collector fails both interrupted-index and
  missing-normalized controls, returning `(0, 0)` instead of `(0, 1)` with zero
  network allowance and a parked host. This proves the controls distinguish
  the added recovery path from the old downloader-only retry.
- `seed-red.log`: the pre-change seed guard fails all three equal-time replacement
  subcases (changed ID, date, or both), retaining the previous runid/replay.
- Full collector suite requires replay ID reuse, zero download/sleep for local
  repair, two-of-three recovery fairness, budgeted missing-original fallback,
  actual cold downloader calls, same-length digest corruption rejection,
  mismatched/oversized/invalid metadata refusal, real synthetic link refusal,
  replacement rejection, unchanged/unknown/older/slower seed preservation and
  board-driven restoration. Each test has its own archive to prevent cache-hit
  contamination.
- The first integrated binding run (`ksfgrab-final.log`) is a retained FAILED
  harness run: dated replacement board fixtures kept the old filename timestamp.
  The collector correctly rejected those inconsistent fixtures. Correcting only
  their advertised timestamp makes the fixture test the intended binding path.
- Review found two leading missing originals could monopolize the local slots.
  `fairness-repro.log` removes the rotation fix and fails the second zero-network
  tick's required link, after the first tick reads exactly two missing files.
  `review-red.log` separately reproduces the uncaught nested-JSON RecursionError.
  Earlier fairness-control setup failures used the wrong synthetic frame offset
  or inspector attribute; those logs are retained but are not product controls.
- `collector-accepted.log`: all **23 collector/index/API tests pass**, including
  repeated-tick missing-original fairness, metadata depth and the corrected seed
  fixture. Codec **9**, import **106 assertions / 0 failed**, top-up **8**,
  board **351**, replay-ledger **119**, web **268** also pass in the focused
  `test_*-final.log` files. Python `compile()` passes for all three changed modules;
  LSP reports no recorded diagnostics (not execution proof), diff whitespace clean.

Repro commands from repository root, with `TEMP`, `TMP`, `TMPDIR` set to an owned
scratch directory and `PYTHONDONTWRITEBYTECODE=1`:

```sh
python surfd/test_ksfgrab.py --out <owned-root>/artifacts/collector -v
python tools/test_ksfconvert.py
python surfd/test_ksfimport.py
python surfd/test_ksftopup.py
python surfd/test_board.py
python surfd/test_replays.py
python surfd/test_web.py
python tools/test_surfd_deploy.py --ref <exact-commit> --out <owned-root>/artifacts/deploy -v
```

## Committed gate and review

Source candidate `d20b579fb6ace569227e700497755f876cce4489` is cleanly committed
on top of inspected published `80618e5`. All **seven exact-commit deployment
falsifier groups pass** (`deploy-final.log`), including the real flattened
collector/index/Flask API suite at **23 tests, OK** (`deploy/flattened-collector.log`).
Both missing-codec controls and collector/converter shell-failure controls act.
No SSH or service/game/network process is started by those offline checks.
A subsequent documentation-only verification receipt does not alter those source
bytes. Independent reviewer identified the old seed bug and then the candidate's
missing-byte fairness issue; both have acting controls and fixes. Targeted final
closure returned **OK / PASS**, limited to read-only source/log inspection.

No QC/native source or normalized format/codec change in this patch; no QC/native
rebuild, engine pin/tag or QC Build bump. Main/bonus CSS66 only; stages, CSS100,
unproven BSP identity and fleet delivery remain the existing explicit gates.
