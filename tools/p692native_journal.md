# P692 — preserve native update recovery authority across journal replacement

Source/native acceptance, 2026-10-13. This is not a release or deployment
certificate. Public version 0.1.25, signed feeds/archives, QC Build89, canonical
Windows installs and fleet binaries are unchanged by this continuation.

## Reproduced defect and narrow fix

`QKU_ReplayJournal` removed `journal.json` before renaming its closed sibling
`journal.tmp`. Real Windows source sharing refusal and Linux rename EACCES or
process interruption before rename caused the current client to fail, but left
no authority for its next cold start. The unchanged control then reached a
startup marker while one ordinary content destination remained unresolved.
The original mixed rewrite OPEN-failure test did not exercise this boundary.

`QKU_CommitJournal` uses checked UTF-8 paths with Windows
`MoveFileExW(MOVEFILE_REPLACE_EXISTING)`, or POSIX `rename`, without a preceding
unlink or copy/delete fallback. Both live journal writes and cold unresolved
rewrite use it. Live initial commit failure returns before any installation;
live deferred commit failure is now reported and retains the prior superset
journal. Cold failure still refuses before resolved-object retirement. Existing
no-link preflights are rechecked at publication. Legacy Quakers remove/rename
policy and generic FS/Sys rename semantics do not change.

## Acted controls

The test drivers accept external native clients and retained signed feeds/object
closures, never a key, pin override or installed player's game. Every input
object is rehashed. Settings/recording/protected edits are synthetic sentinels.
Windows children launch suspended into owned kill-on-close jobs. New drivers
require zero active job members BEFORE cleanup; POSIX children use owned process
groups with an empty-group check. Refusal requires the exact error, nonzero exit
and no startup marker; completion requires zero exit and that launch's marker.

`test_update_native_journal.py`: both ordinary-content-first and protected-first
orders, with installed ordinary content proving recovery ACTED:

- Windows: independently prove journal.tmp writing/truncation is allowed while
  its actual rename fails with sharing error32. Control loses the original and
  next corrupt launch starts. Subject retains the original byte-for-byte and all
  staged objects; the next corrupt retry refuses; repairing the staged object
  completes, advances truthful state, saves the signed envelope and starts.
- Linux: exact native rename interposition forces EACCES, process exit86 before
  commit, or exit86 after successful real commit. Failure/before-interruption
  control starts mixed; subject retains old authority and refuses the next
  corrupt startup. After-commit interruption leaves valid attempt2 authority
  containing only the pending row, and direct repaired retry completes. Normal
  partial-publication controls also refuse, then complete on repair.

`test_update_native_journal_live.py`: existing signed Windows loopback fixture,
exclusive bind and an occupied-port control. Initial journal source-rename
failure installs nothing and leaves the old ledger intact, then an acted
same-client recheck/apply succeeds after unlocking. A held ordinary destination
forces a real deferred apply: one content file lands, the existing journal is
replaced with exactly its one unresolved row without a completion certificate,
and cold replay after releasing that destination completes. These two arms pass
on the unchanged control and subject; their purpose is live call-site acceptance,
not reproducing the cold missing-authority defect.

Regressions: all16 existing unprivileged Linux protected/corrupt/shared/locked/
rewrite-OPEN/retry controls, all8 existing Windows signed cold controls, and all16
Windows native live/cold share/ACL/edited/missing controls pass on the subject.
Full fresh Windows/Linux builds succeed with zero new compiler diagnostics
against their clean controls. Existing Windows compiler warnings are35 in each;
Makefile peer-target and a first Linux temporary-file clock-skew warning are
infrastructure observations, not hidden as compiler passes. Regenerated clangd
database plus standalone check with the configured GCC environment reports zero
parser errors. Harness C builds with `-Wall -Wextra -Werror` on Linux.

Independent read-only source review found no implementation issues; its verdict
was OK with explicit runtime/durability limits. A separate harness review blocked
acceptance on surviving POSIX descendants after leader exit, lost native logs on
early failure, and a PASS receipt after failed live retirement. Fixes terminate
and confirm the owned group independently of leader state, export every phase's
native logs even on failure, prevent retirement without confirmed containment/
evidence, and downgrade retirement failures to FAIL. Seven client-free negative
tests ACT on Linux (including real owned Python group survival); Windows runs
three applicable tests with four explicit POSIX skips. Full control/subject
native matrices are rerun on the corrected frozen harness, not grandfathered.
Raw logs and precise receipts remain in the owned task root, not public Git.

## Reproduction

```sh
# Linux only; build this harness library, never link it into the product.
gcc -Wall -Wextra -Werror -shared -fPIC tools/native_journal_fault.c \
  -ldl -o /owned/journal-fault.so
# Run driver/client unprivileged in an owned private network/mount namespace;
# use a fresh tmpfs fixture root and durable small evidence directory.
python3 -B tools/test_update_native_journal.py \
  --engine /owned/native-client --feed /retained/signed/update.json \
  --objects /retained/objects --fault-library /owned/journal-fault.so \
  --runtime-root /owned/tmpfs/fresh-cases --evidence /owned/fresh-evidence
# --expect-before is ONLY for the old missing-authority detector control.

# Windows source-sharing refusal + cold retry matrix, no listener:
python -B tools/test_update_native_journal.py \
  --engine C:/owned/native-client.exe --feed C:/retained/signed/update.json \
  --objects C:/retained/objects --runtime-root C:/owned/fresh-cases \
  --evidence C:/owned/fresh-evidence
# Windows live initial-failure/same-game retry and deferred/cold-completion:
python -B tools/test_update_native_journal_live.py \
  --engine C:/owned/native-client.exe --feed C:/retained/signed-loopback/update.json \
  --objects C:/retained/production-objects --objects C:/retained/fixture-objects \
  --runtime-root C:/owned/fresh-live --evidence C:/owned/fresh-live-evidence
```

## Limits and remaining gates

Atomic **namespace/process-interruption** replacement is not power-loss
persistence: no file-data/directory fsync or FlushFileBuffers ordering is
certified. Windows has real replacement-failure coverage, not a separate native
process-interruption injection. After-commit Linux interruption goes directly
to repaired retry, not an additional still-corrupt retry that would consume its
attempt budget. The live deferred writer's successful replacement is acted;
a separate failure specifically at that second live commit is not injected.

Interruption after pending-only publication but before retirement can strand
formerly resolved staged objects, because the next journal no longer names
them. Those objects remain bounded to the updater staging directory; this test
does NOT claim complete cleanup in that arm. General metadata-writer durability,
hostile ancestor swaps and hardlink safety remain outside this narrow change.
Linux default-HTTPS menu/restart acceptance remains an independent P689 gate.

## Local evidence provenance

Owned root: `C:/FTESurf-worktrees/jcommit-20261013T142535Z/`; OWNER/PLAN bind
repositories, inspected bases and exclusive writers. Engine base
`27c58e07a993636aa6d5f75064174518c8cea5c2`; QC base
`fe870b51575f9db4059b109daa767ab85e0b7bcd`. The subject adds only this journal
feature to those isolated sources; dirty canonical owner/peer work is excluded.
See that root's final checkpoint for the exact accepted commit/tag/pin and the
separate push/build/retirement/deployment states.

Failed setup attempts remain failures: Linux distro selection, MSYS argument
conversion, first wrong retained-feed path, legacy Windows recovery supplied a
production feed without its required synthetic content row, and an incomplete
build-log clangdb parse. These started no product clients where fixture loading
failed. The first standalone clangd check lacked its GCC environment/refactoring
flag; the correctly configured recheck passed. First retirement stopped before
fixture deletion because its expected linked-temp suffix was wrong; inspection
confirmed state.json.enginetmp, and the corrected explicit-path retirement is
separate. No failed run or blocked harness review is counted as a pass.
