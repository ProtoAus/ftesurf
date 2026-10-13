# P692 — Windows cold journal process-interruption controls

This closes a **cold pending-only replacement** process-interruption gate. It is
NOT a power-loss/file-data/directory-flush acceptance, initial full live journal,
deferred live journal interruption, shipped release, or deployment.

## Preregistered control and subject

Retained immutable PE clients and matching `.exe.db` symbols:

- Old engine `27c58e07a993636aa6d5f75064174518c8cea5c2`, client SHA-256
  `10a0216c290abc871d34f0fd962c7fe1a4eb0e5fa083783743aaee5b8e1cc7e9`.
- Accepted P692 engine `195dc58e9054b421dc9c76530a0715df64864183`, client SHA-256
  `db9ee5b058740bc5346547510667249dc72681413f9d3dc8cba972e292e610c5`.
- Existing coherent signed Windows 0.1.25 feed and full object closure. The driver
  checks the signature, every selected object's digest and size, and records feed,
  client, symbol companion, helper and driver SHA-256. No private signing key.

Before launch, complete PE `.text` must equal its symbol companion. `nm` and
`objdump` must locate unique cold/native commit sites and exact native call bytes.
The old breakpoint is on the unique `FS_Rename` call after `FS_Remove` inside
`QKU_ReplayJournal`. P692's is on the unique `MoveFileExW` import call in
`QKU_CommitJournal.part.0`; the inspected stack-frame prologue and wrapper tail
jump bind its cold return address at RSP+0x1848. The post breakpoint is precisely
the next instruction after the call.

`native_journal_interrupt.c` is an external x64 Windows debugger, never linked or
shipped. It changes only transient breakpoint bytes and restores the original
instruction/RIP before normal call/return execution. It verifies actual native
source/destination paths, root/replace flags and P692 cold caller. The after actor
must observe a nonzero native result on the same thread. Interruption terminates
only its owned child with exit86; no result/register is forced. Raw JSONL records
PID, thread, RVA, hit count, real return and exit. Unlocked debugger control
executes the same boundaries and continues to the native pending refusal.

## Exact state and retry claims

Both row orders include ordinary content that actually installs, an edited
protected local zone that is skipped, and corrupt unresolved ordinary content.
Settings, recording and unmanaged asset sentinels remain byte-exact. Each launch
must either emit its own startup marker or its exact refusal actor—not silence.

- **Before rename:** complete pending-only attempt2 temp exists, partial managed
  ledger exists, installed envelope is absent, all staged inputs remain. Old
  control has already unlinked full attempt1 authority; its next corrupt launch
  reaches startup with mixed content. Only AFTER detecting this, restore its
  original full authority for explicit control-only repaired completion. P692
  retains the original byte-exact full attempt1 journal, refuses the next corrupt
  launch, publishes attempt2 pending-only authority, then completes repaired
  attempt3 without retouching settings/recording/protected/unmanaged sentinels.
- **After successful rename:** pending-only attempt2 authority exists, temp is
  gone, native nonzero return has acted, all staged inputs still exist because
  execution stopped BEFORE resolved-input retirement. A separate fresh repaired
  fixture completes at attempt3. A different fresh corrupt fixture publishes
  attempt3/refuses; repairing its object and trying again must refuse exhaustion
  without rewriting authority, installing pending content, recording completion,
  or removing staged inputs. No budget reset to make an assertion pass.
- **Known limit:** after-interruption pending-only authority no longer names
  resolved staged objects. Successful repaired retry leaves those unreferenced
  objects. The harness asserts this limit explicitly; it does not certify cleanup
  or garbage collection.

## Ownership and falsifiers

Helper starts suspended, is assigned to the parent-owned kill-on-close Windows
job, then resumed. Child must inherit that job. Receipts require exact helper and
child exits and observed empty job both before and after cleanup. On any failure,
metadata (including `.tmp`), logs, staged identities and synthetic `ftesurf/`
file SHA-256 identities export before retirement; unknown containment/export
retains an unconfirmed guard and prevents deletion. Preflight resolves runtime
and evidence roots and rejects equality/ancestry in either direction before
mutation, so retirement cannot delete exported evidence.
Trusted owned synthetic roots only; this is not general hostile-path, mount or
hardlink coverage. No owner/peer process or installed player data authority.

Twenty client-free controls cover companion mismatch, unique symbols, exact
stack allocation/tail shape, real replace import, native bytes, trapped return,
old preceding unlink, missing/wrong/reordered/unknown path/thread/RVA/exit/result
actors, disjoint/fresh path admission, retained sentinel/content hashes, timeout
export, export failure and containment failure. A native wrong-byte helper control must fail with
exit90 and job0, preserve sentinel authority/temp and retain FAIL receipts.

First native subject01 failed because expected helper paths did not normalize
Windows separators; helper rejected before rename. Its FAIL history remains.
Corrected helper02 and subject/control02 exercised the complete native matrix;
subject/control03 repeated that pre-review source. Independent review identified
a real overlapping-root deletion gap; disjoint-root preflight plus retained file
hashes/exact event/frame checks were added. Final frozen subject/control04 and 05
each passed all eight cases/twenty native launches per binary (80 final-source
phases total). Independent audit verifies exported authority, attempts, exact
actors/exits/job0, sentinel hashes and retirement; review/recheck and checkpoint
retain the full histories.
A regression command initially passed an existing root where the old harness
requires a fresh one; its rejection remains recorded and was corrected by a new
owned subroot, not by editing the old harness.

## Commands

From Bash, compiler only (do not ship helper):

```sh
export PATH=/c/msys64/ucrt64/bin:$PATH
export TMP=C:/FTESurf-worktrees/<owned>/tmp TEMP=$TMP TMPDIR=$TMP
gcc.exe -Wall -Wextra -Werror -municode -static \
  C:/FTESurf-worktrees/<owned>/qc/tools/native_journal_interrupt.c \
  -o C:/FTESurf-worktrees/<owned>/artifacts/native-journal-interrupt.exe
```

Windows Python; inputs outside this task are read-only:

```text
python -B tools/test_update_native_journal_interrupt.py
  --engine <retained-client.exe> --symbols <matching-client.exe.db>
  --helper <owned-helper.exe> --feed <retained-update.json>
  --objects <retained-object-closure> --runtime-root <fresh-owned-runtime>
  --evidence <fresh-owned-evidence> [--expect-before]
```

New client-free controls use an **existing owned scratch**:

```text
FTESURF_TEST_SCRATCH=<owned>/tmp
python -B tools/test_update_native_journal_interrupt_unit.py
```

Retained evidence root:
`C:/FTESurf-worktrees/wjcut-20261013T172400Z/artifacts/`.
See `PLAN.md`, `review-interrupt-*.md`, exported binding disassemblies and final
checkpoint for exact frozen validation commands, phases, hashes and limits.
