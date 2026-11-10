# P1480 — worker exclusion during journal replacement and dropping

## Useful outcome and exact boundary

An admitted independent-physics worker can no longer retain access to journal
storage while main-side Begin replaces it or Drop frees/resets it. Both complete
lifecycle transactions save/disable/restore the existing independent-send
permission. Nested Begin→Drop retains the outer ownership; an already-disabled
worker stays disabled. No new API or per-event lock was added.

This is evidence-integrity maintenance, NOT a new cheat detector or hardware
attestation. Collection, consent, evidence grammar, ranking and enforcement are
unchanged. Ordinary main/worker appends and counters, plus the complete
End/hash/write transaction, remain open. In particular End's filesystem write
can pump callbacks with nonlocal exits: do not hold this lifecycle guard across
that write and call it all-exit-safe. The eventual Drop is protected only while
it frees/resets storage, after the writer returns.

Engine source/tag `patch-1480`:
`5ce7c7602f985b9d99cd21495f462e03c142639d` (parent P1479).
Only9 product C lines added, plus regression and Problem/Change/Verified entry.
The same image retains P1479's false-terminal-truncation fix.

## Acting controls and review

`engine/tools/test_input_journal_lifecycle.py` compiles actual Raw/Line, whole
Begin/Drop and the actual permission helper. Whole End is compiled for dependency
closure, not executed by this concurrency test. The host uses real nonrecursive
pthread mutexes and OS threads; clock/cvar/device/hash/filesystem dependencies and
the worker's lock interval are explicit host stubs/model, not actual input or
the actual SendCmd loop.

A synthetic worker holds the real existing lock, enters the actual Raw growth
path and pauses BEFORE realloc/copy. The main actor calls actual Begin or Drop.
Pinned prechange3f45df7a5:12 checks/4 unsafe-admission failures. The host aborts
the unsafe operation BEFORE freeing storage—no intentional UAF is executed.
Subject:18/0. After releasing/joining the worker, dependent assertions also verify
completed worker-row bytes before exactly one old-buffer free and the actual
replacement header/begin or Drop storage reset. Those six dependent assertions
are skipped after the baseline's safe abort; no oracle was weakened.

Nested-owner and disabled-worker controls pass. Explicit main-role readiness
prevents recycled pthread IDs from masquerading as the new main actor. An
initial unused host-counter compile failure is preserved, not credited as an
acting product control. Strict C99 `-Wall -Wextra -Werror` with real pthreads;
independent source/callback/caller review approved the bounded change.

## Build and reader evidence

Normal isolated `src/build.ps1 -Engine -Full -NoDeploy -FteRoot <owned-engine>
-Jobs 8` compiled client, dedicated server, all five default plugins and all
three QC programs. QC0 warnings; native74 existing warning occurrences, exact
same normalized diagnostic multiset as P1479, zero new. Engine source is clean.
Clangd database refreshed with the existing `tools/clangdb.py`; inherited tidy
warnings are not new compiler warnings or runtime verification.

Reader949 checks/0. The retained complete current-reader568-file corpus result
has356 existing faults (NOT corpus-clean). Reader bytes and all original568
file hashes remain unchanged. An extra fresh sweep reached the execution timeout
before its summary and is NOT graded as another complete pass; the still-valid
same-reader/same-bytes complete result is reused. No recordings, protected saves,
configs or player data were edited. Cryptography, fatal exits, native backend
runtime delivery and universal thread safety are not established by host tests.

## Published and deployed — 10 Nov 2026 UTC

Both Windows clients installed18:17:11Z from the same clean qualified commit.
The original occupied-owner refusal is preserved; no game was killed/signaled.
The final real execution boundary was game-free. Existing `build.ps1` Deploy was
reused, with source/predecessor/actor guards, saved preimages and normal `.prev`.

- `C:/FTESurf/ftesurf64.exe` and `C:/FTEQuake/fteqw64.exe` SHA256:
  `8f013bd0f12af20783b709f9330581b1341bc9b6454be3fba97a7e10626e8cec`.
- Both `.prev` SHA256:
  `b0349be22bcf1ae6dc78eb64caccc0876806f73338075b1da30c5421554c23eb`.
- Both installed executables actually ran `--version` and exited0; smoke finished
  18:18:18Z, stamp `git-8649-patch-1480-0-g5ce7c7602`. This early-exit branch
  precedes game/filesystem/input initialization: it proves installed image/startup
  provenance, NOT actual gameplay, physical capture or in-game thread behavior.
- Server/plugin/VM/config presence and hashes stayed unchanged. No Pi/backend,
  lobby restart, ARM/server/progs deployment or qcbuild bump was required for
  this compatible client-only delta. No release/download publication is claimed.

Private receipts preserve exact image/source/build bindings, original failure
controls, rollback preimages, protected-file checks and UTC provenance.
