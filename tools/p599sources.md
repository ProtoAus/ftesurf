# Patch 599 — verifier source stability

## Outcome

New verifier results must refer to recording bytes that agree before and after
an attempt. A known-current filing SHA must agree before runner admission.
Evidence requires agreement between the lobby copy read by the engine and the
KEEP copy read by row/stage checks. Source read failure, replacement or removal
stores retryable ERROR, unknown ticks and no counts snapshot. It does not invent
a cheating verdict or a new Verified badge.

Unknown/stale filing digests remain supported without backfill. Hashing is
streaming and outside writer transactions; existing retry caps and explicit
refile/recheck admission remain. No schema, receipt-reader, detector threshold,
owner-review, engine/QC/progs/Build or release change.

This is a **before/after fence**, not immutable engine input, historical verdict
source provenance, or hostile-host intermediate change-and-restore detection.
Existing ERROR policy deliberately retains historical PASS/owner approvals.
No retroactive revocation or corpus recalibration is claimed.

## Controls and checks

Frozen game source: `d1355dbde7faaf9d056341c1b58fcc981c8a093d`, based on clean
published `0eafc347cb567b65791ef8f02ed53e85de61c4ed`. Shared dirty checkouts were
not built, reverted, staged or shipped. Engine changelog-only commit:
`6497442bae773cf40865fab8ca962d421580d010`; engine pin/tag unchanged.

From the clean game worktree:

```powershell
python surfd/test_verifier_sources.py
python surfd/test_sweep.py
python surfd/test_verifier_counts.py
python surfd/test_replays.py
python surfd/test_board.py
python -W error -m py_compile surfd/sweep.py surfd/test_verifier_sources.py
```

The new suite uses synthetic verifier stdout but real source files, SQLite,
counts storage and badge SQL. Controls positively observe the runner and file
replacement. It does not test engine physics or detector calibration. The first
eight correctly constituted controls have six failures on untouched baseline;
honest and legacy controls pass. The final 15 cases pass, including both evidence
copies, read/hash-time failure, same-size replacement, disappearance, metadata-
only changes, grouped companion independence, retry recovery/exhaustion/refiling,
no hash-time writer transaction and retained historical PASS policy. Independent
read-only review found no blockers; optional evidence assertions were strengthened.

Full boundary: all fixture-free `surfd/test_*.py` except the fixture-dependent
`test_momindex.py`, plus these eleven tools programs:

- `test_hidcheck`, `test_rcptcheck`, `test_reccheck`, `test_injrn`
- `test_recsim_limits`, `test_recsim_opportunities`, `test_recsim_parsing`
- `test_recsim_sources`, `test_recsim_unreadable`
- `test_journal_snapshots`, `test_journal_diagnostics`

Windows: 70 programs, 69 pass. Only `test_admin` fails its two preexisting UDP/
RCON assertions; both reproduce on clean untouched baseline. Linux: all 70 pass
after four staging-only failed gates are corrected and rerun: include the exact-
commit `src/client` fixtures, use a neutral stage name (a legacy sweep assertion
searches stdout for `evidence`), and place temporary download fixtures on storage
with more than the existing 20 GB floor. No source or guard changes for these
controls. A development counts test crossed a wall-clock second and passed its
controlled retry. Strict compilation covers owned files; legacy HID fixture
escape warnings are not silently repaired or declared new regressions.

Required recorder sweep uses an immutable fresh copy of runs **and sidecars**:
269 REC / 440 files; 164 existing fault files / 164 faults. Reader blob
`9b1537b3351d55d440e889fcfd7e8b337e860eff` is identical in baseline and subject;
no increase in corpus faults. No QC/engine rebuild is necessary for this
sweeper-only change; unrelated clean NoDeploy build-summary failure is untouched.

## Deployment

Verified at **2026-10-08T15:29:27Z**, rechecked **15:31:14Z**. Selected Pi ship set
is only `sweep.py` and its new `test_verifier_sources.py` control. Canonical sweep
lock held; exact predecessor and staged hashes checked; completed stable SQLite
backup and old source retained for rollback. A first deferred-read backup attempt
timed out before any swap; the corrected backup pins a real read snapshot and
completes before copying. No web reload is needed for a sweeper-only update.

Installed SHA-256:

- `sweep.py`: `aa865b1cb375633ce4897cc3c9a09ce32042224696e8123192e622570cdbb6e2`
- `test_verifier_sources.py`: `463dc416d5019b720b279c9ceb7a1ff158ddde69d9e0b93227be0b178a52761c`

All 15 source controls also pass with the test harness resolving the actual
installed sweeper module, using isolated temporary fixtures rather than the live
DB. Protected 125 support/static/template/reader files, complete stored verdict/
review/receipt table fingerprints, and web worker identities remain unchanged.
Health is OK with 12 lobbies. Stage-module restoration is verified. No game,
engine, Windows install, progs, configuration, player data, reader, detector,
release or Build-number swap. Other live sweeper support bytes remain protected;
only these owned files were copied.

Private operational logs, snapshots, backup/rollback paths and procedures remain
in the private checkpoint. Remaining work includes immutable verifier-input and
historical source binding, plus the existing practice-hold/calibration blockers;
this patch does not turn those unknowns into enforcement.
