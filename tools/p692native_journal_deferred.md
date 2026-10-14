# P692 — Windows deferred live journal replacement failure

Test-only continuation, 2026-10-13. Production engine P692/source
`195dc58e9054b421dc9c76530a0715df64864183` is unchanged. This is native signed
loopback-fixture acceptance, not a release, canonical/fleet deployment, default
HTTPS gate or power-loss certificate. Public version0.1.25 / QC Build89 unchanged.

## Boundary and instrumentation

`QKU_Apply` writes complete authority before installation, publishes successful
rows to the partial ledger, then calls `QKU_WriteJournal(1)` again when a real
held destination remains. Initial journal failure and successful deferred
replacement were already covered; this continuation faults specifically that
second live writer.

`test_update_native_journal_deferred.py` accepts external immutable x64 clients,
matching unstripped `.exe.db` companions and a retained signed loopback feed plus
object-closure union. It verifies every object, compares complete PE `.text`
bytes between client/companion, resolves the unique optimized writer with `nm`,
and requires exactly two direct initial/deferred call sites in `objdump`.
Receipts bind client, companion, code, helper, harness and signed-feed hashes.

The test-only `native_journal_live_fault.c` debugger temporarily writes one INT3
byte in its OWNED child's memory at the writer entry. First call restores the
original byte, executes it with a single-step, restores flags and rearms. At the
second call it snapshots the existing full journal, verifies the first temp was
consumed, permanently restores the original instruction and resumes unmodified
native writer execution. Both caller RVAs and the same writer thread must match
the inspected live call sites. The disk executable is rehashed afterward.

At invocation2 only, the helper creates/holds sibling `journal.tmp` with read/
write sharing but NO delete sharing. An independent native probe proves OPEN/
truncate/write is allowed and source rename really fails with Win32 error32.
The original writer then normally opens, writes and closes that same file;
its complete pending-only contents plus exact product rewrite-error actor prove
this was NOT the old failed-OPEN gate. No native API result/register is forced.
The probe's error32 is NOT claimed as a sampled product TEB/MoveFileExW result.
This is transient debugger memory instrumentation, not an untouched-process
claim. The unlocked debugger arm proves the instrumentation itself permits the
normal native replacement and cold completion.

## Acted predictions

Both external binaries run both arms:

- **Unlocked control:** full two-row initial journal exists; one ordinary file
  installs, the held destination remains old; second writer replaces authority
  with exactly the pending row/attempt1. Old version and truthful partial ledger
  remain, no installed completion certificate. A separate cold process completes.
- **Pre-P692 detector** (`27c58e07a993636aa6d5f75064174518c8cea5c2`): second-writer
  source lock leaves a native pending-only temp but loses `journal.json`; live
  caller falsely prints deferred success. Corrupting the remaining object then
  cold-launching ACTS the startup marker with that destination still old. Only
  AFTER this detector is graded do we restore saved full authority and repair
  the object for an explicit control-only successful retry. Its failed temp
  remains an observed legacy orphan; it is exported, not credited as cleanup.
- **P692 subject:** exact deferred rewrite error/stateerror, no deferred-success
  actor; original full authority is byte-exact, signed envelope/all staged inputs
  retained; one destination and partial ledger ACTED, unresolved destination old.
  With both locks released, a new corrupt cold retry refuses before startup and
  publishes accurate attempt2/pending-only authority. Repairing the object lets
  attempt3 complete, record truthful final version/hashes, retain signed installed
  envelope, remove journal/temp and ACT a fresh startup marker.

Settings, recording, an unmanaged asset and an edited protected local zone remain
byte-exact. The listener binds exclusive loopback with an occupied-port negative;
only the two required object paths and one signed-feed request are accepted.
All live helpers/clients start under parent-owned kill-on-close jobs before
native startup; cold phases use the existing native helper. Receipts require raw
helper/native exits and observed ZERO active job members before any cleanup.
Debug EXIT_PROCESS delivery precedes final kernel exit accounting: a bounded
natural-quiescence census records intermediate counts and fails if not empty;
it never kills an otherwise successful arm to make that arm pass.

## Failure-path controls and lifecycle

Client-free tests cover PE/symbol/code/callsite mismatches, an already-patched
writer, natural exit-accounting race, persistent nonempty job rejection, nested
native-log/temp/authority/staging export and early-exit export failure retaining
the unconfirmed retirement guard. Set an existing owned scratch directory;
these tests never start a native client or listener.

Native logs, debug events, initial and pending-only authority, phase-specific
metadata, staging hashes and exits are exported before retirement. Any uncertain
containment/export blocks retirement. A failure remains FAIL; no missing ordinal,
actor or authority counts as an unexercised pass. Only verified synthetic owned
runtimes are removed; prior inputs, player data and owner/peer processes stay
untouched. Failed setup/grading histories are retained in the local checkpoint.

## Verification and review

Fresh corrected old-control/current-subject matrices and their frozen-byte repeat
pass both modes. Existing native Windows cold publication controls (ten grader
checkpoints each) and live initial-failure/same-game retry/deferred-success controls
also pass on both binaries after the common cold cleanup correction. Final audit:
46 normal native phases with exact raw exits and pre-cleanup job0, plus the native
wrong-prologue early-failure control. All synthetic runtime roots are retired.

New client-free controls: Windows14 pass; existing harness/feed/clangdb19 pass
with four explicit POSIX skips. Combined Linux unit regression:36 pass/one explicit
Windows-branch skip. The helper compiles `-Wall -Wextra -Werror` with no diagnostics;
no engine build/change is involved. Recorded accepted input SHA256:

- P692 client: `db9ee5b058740bc5346547510667249dc72681413f9d3dc8cba972e292e610c5`.
- Before client: `10a0216c290abc871d34f0fd962c7fe1a4eb0e5fa083783743aaee5b8e1cc7e9`.

Independent review first BLOCKED on premature debugger thread-handle closure,
cold failure cleanup without observed empty-job census, missing failed-temp export,
an overstated mount guard and malformed-helper preflight. All five corrected,
negative controls acted, fresh matrices/regressions repeated; focused re-review:
no issues, OK with notes subject to exact parent hash/provenance audit (now PASS).
The handle-reuse failure remains FAIL, not reclassified by a later successful run.

Local small evidence and failed histories remain under owned root
`C:/FTESurf-worktrees/wjlive-20261013T164000Z/artifacts/`: matrix07/08 results,
regressions, unit logs, debug/native receipts, reviews and `final-audit.json`.
Raw runtime logs and synthetic authority are not committed to public Git.

## Reproduction

```sh
# Required on Windows: GCC's own DLL directory on PATH; owned compiler scratch.
export PATH=/c/msys64/ucrt64/bin:$PATH
export TMP=C:/owned/task/tmp TEMP=$TMP TMPDIR=$TMP
# Test-only helper; never link or ship this into a client/archive.
gcc.exe -Wall -Wextra -Werror -municode -static \
  tools/native_journal_live_fault.c -o C:/owned/task/debug-helper.exe
python -B tools/test_update_native_journal_deferred.py \
  --engine C:/retained/native-client.exe \
  --symbols C:/retained/native-client.exe.db \
  --helper C:/owned/task/debug-helper.exe \
  --feed C:/retained/signed-loopback/update.json \
  --objects C:/retained/production-objects \
  --objects C:/retained/fixture-objects \
  --runtime-root C:/owned/task/fresh-runtime \
  --evidence C:/owned/task/fresh-evidence
# --expect-before ONLY for the independently pinned pre-P692 detector binary.
FTESURF_TEST_SCRATCH=C:/owned/task/tmp \
  python -B tools/test_update_native_journal_deferred_unit.py
```

The companion and tools are deliberate prerequisites. A differently optimized
binary lacking the exact symbol/two direct call sites refuses before launch; do
not silently fall back to timing polling, a rebuilt product or simulated errors.

## Limits

No separate Windows process-interruption/power-loss injection, file-data or
directory flush ordering, crash-after unreferenced-object cleanup, hostile
ancestor swaps/hardlink acceptance or general metadata durability is certified.
No default-HTTPS coverage is inferred from this explicitly permitted loopback
fixture. The release remains the earlier P687 runtime; source/test acceptance
and exact inspected native binaries do not certify any owner's/fleet install.
