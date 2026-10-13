# P692 — Windows initial full live journal publication controls

Test-only source acceptance for the first `QKU_Apply` journal write, separate
from cold pending-only and deferred live rewrites. No product/pin/tag change,
signing, canonical deployment, release or power-loss acceptance. Deferred live
process interruption remains a separate gate.

## Real native actors

`native_journal_initial.c` is an external x64 Windows debugger, never linked or
shipped into the engine. `test_update_native_journal_initial.py` matches complete
client/companion PE `.text`, inspects the two `QKU_Apply` direct calls and binds the
first one. The observed first writer must have that exact initial return PC. It
then binds the actual `FS_Rename` (old) or `MoveFileExW` import (P692) instruction
and following return instruction, verifies exact paths and flags/root, and
requires the same thread. P692's inspected stack frame, stack-probe target, tail
wrappers and live commit return PC at `RSP+0x1848` are checked; native import and
direct-call displacements must target the inspected symbols. Wrong symbols,
companion, allocation, caller, native bytes, paths, actor or exit refuse.
Original bytes and RIP are restored; there is no simulated native return.

Every first native call exports its complete attempt1 `journal.tmp` before
publication and verifies absent `journal.json`. Modes:

- `none`: real unlocked native success, actual install completion and final
  signed installed certificate/version/hash ledger. This proves the boundary ACTS.
- `source-lock`: after the native writer completes, hold its temp readable with
  read/write sharing but no delete sharing. An independent writable OPEN succeeds;
  exact source-to-fresh-probe `MoveFileExW` fails with sharing error32. The actual
  engine rename then returns zero. This is not a sampled product TEB error. The
  full temp and initial-error/stateerror prove publication failure, not failed
  writer OPEN. Release the lock only after that observed return. Export unchanged
  destinations/ledger, absent authority/certificate and intact staging before a
  separately marked successful same-game check/apply retry.
- `crash-before`: terminate only the owned debug child with86 before executing
  the real native call. Its complete full temp remains, authority is absent,
  selected destinations/ledger remain old and selected staging is intact. A fresh
  cold launch must ACT startup and leave that state unchanged.
- `crash-after`: execute the real successful native call and terminate the owned
  child86 at its return instruction, before any initial install-loop mutation.
  Full attempt1 authority exists, temp is consumed, all selected destinations and
  ledger remain old. Separate fresh fixtures cover direct cold completion at the
  next attempt, and corrupt pending refusal followed by repaired completion.

Both old27c58e and subject195dc58e have the same expected initial-boundary safety:
there is **no prior authority to lose**. Before-publication cold startup with all
old content is NOT a mixed-startup regression and does not differentiate P692.
Do not fabricate prior authority for this gate. P692's demonstrated authority-loss
fix remains the cold and deferred rewrite controls in their separate documents.

## Signed fixture and grading

The retained loopback archive is verified with the real production verifier; the
full win64/all closure is resolved from verified union object stores. No signing
key or trust-pin edit is needed. Every existing non-target object already matches
its signed hash. Exactly two ordinary content rows need updating:
`ftesurf/gfx/crosshairs/xhair1.png`, then `ftesurf/gfx/updater_fixture.txt` in signed
manifest plan order. The corrupt fixture targets the first row; the later valid
updater-fixture row advances. This is not an earlier-valid-before-corrupt control. One protected local zone is edited and skipped. Settings,
recording and unmanaged sentinels stay byte-exact. Exact manifest and selected
object HTTP request counts prove separate source-lock retry downloads.

The native attempt1 temp must exactly equal the signed version and both planned
rows (path/hash/size/exec), not a synthetic model writer. Before/failure fixtures
retain the full staged manifest and selected objects. After-commit corrupt retry
installs the later valid row but refuses before startup with the exact pending
error; attempt2 authority contains only the corrupt sibling, prior ledger version
remains, resolved hash advances and pending hash stays old, and no installed
certificate exists. Repair then completes. Successful arms require both new
content hashes, signed installed envelope, final version and selected-object
retirement, absent journal/temp and unchanged protected/unmanaged sentinels.

## Owned lifecycle / local verification

Fresh resolved runtime/evidence roots must be disjoint in both directions before
any mutation. A helper starts suspended, joins the parent's kill-on-close job,
then resumes; its debug child inherits that job. Exact ordered writer/before/after/
interrupt/exit receipts include child PID/thread/native result. Success requires
exact helper/child exits and observed empty-job census before AND after cleanup.
Any containment/export failure retains the retirement guard and FAIL receipt.
Cold phases keep an independent full-export guard beyond the imported runner's
log/job guard: even a post-mutation grading error snapshots current runtime-file
hashes, and hash/receipt export failure cannot fall through to legacy retirement.
Metadata INCLUDING `.tmp`, game logs, full runtime file hashes and staged hashes
export before owned synthetic fixture retirement. The loopback listener uses
exclusive binding, includes a real busy-port negative, and is closed/thread joined.

```text
gcc -Wall -Wextra -Werror -municode -static tools/native_journal_initial.c -o <owned>/helper.exe
python -B tools/test_update_native_journal_initial_unit.py
python -B tools/test_update_native_journal_initial.py --engine <client> --symbols <matching.db> --helper <helper.exe> --feed <signed-loopback-update.json> --objects <verified-union-store1> --objects <verified-union-store2> --runtime-root <fresh-owned-root> --evidence <fresh-owned-evidence>
```

Set `FTESURF_TEST_SCRATCH` to an existing owned scratch path for client-free tests;
add `--expect-before` for old27c58e. Source/companion/input hashes and raw receipts
are retained under the task artifacts root rather than published as bulky binary
fixtures. The native wrong-entry-byte negative must exit helper90, never reach
startup/publication, export exact authority/temp/stage sentinels and observe job0;
its phase result remains FAIL even when the negative assertion passes.

Limits: trusted synthetic roots only, no hostile ancestor-swap/hardlink/mount
contract. Debugger-owned process/thread event handles remain owned by the exit
lifecycle. Only helper-created processes can be interrupted. No file-data/directory
flush ordering, crash-durable power-loss certificate, orphan staged-object GC,
other journal-call coverage, fleet behavior or release acceptance is implied.
