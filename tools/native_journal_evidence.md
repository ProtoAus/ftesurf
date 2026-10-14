# Native journal runner evidence lifecycle — 2026-10-13

Test-harness hardening only. No engine/QC/product change, patch/pin/build/version
bump, deployment, release, signing-key or default-HTTPS claim. The 2026-10-14
follow-up closes deferred live process-interruption coverage separately in
`p692native_journal_deferred_interrupt.md`; file-data/directory-flush power-loss
acceptance remains open. The historical results below are not strengthened.

## Contract

`test_update_native_journal.snapshot` is the shared **post-containment** exporter
for cold, legacy live, deferred live, cold interruption, initial live and deferred
live interruption drivers.
It captures current bytes/identities, not the intended final state:

- Raw updater `.json` **and `.tmp`** metadata and all runtime `.log` files.
- BLAKE2b staged-object identities, including retained resolved-object orphans.
- SHA-256 of every regular file under the owned synthetic runtime, including
  metadata, staging, lock/control files, manifest and non-gamedir files in
  `all-runtime-files.sha256.json`. `runtime-files.sha256.json` preserves the
  gamedir-only inventory interface. Content bytes are identified, not copied;
  signed object stores and fixture source must remain available for reconstruction.
- Byte-exact copies verified against the read source bytes; a completed
  `full-export.json` receipt. Missing runtime, linked/reparse/special file,
  read/copy/hash/inventory/receipt failure cannot become an empty passing export.

Each export has an independent `UNCONFIRMED_PHASES` guard. Its release follows
complete export AND receipt write. A failed target refuses reuse BEFORE touching
its outputs, preserving the original FAIL/partial evidence. A separately named
successful export cannot clear an earlier guard. The initial caller's outer
guard has a distinct name, so it cannot collide with the exporter's guard.

Traversal uses checked `os.scandir`, propagating root/subtree listing errors and
checking links/reparse/special files before descending. Python 3.10 `rglob`
suppresses some listing PermissionErrors and can otherwise certify an incomplete
or empty inventory. Both root and staged-subtree omissions acted on frozen04;
the revised exporter stores FAIL/retains its guard for the same injected denials. Each process phase separately guards job/group
containment, full export and process receipt. Grading-after-mutation, timeout,
export/containment/handle-cleanup failure retain FAIL. A negative assertion
passing never relabels that injected failed phase PASS. On unknown containment
or incomplete evidence, runtime retirement refuses instead of swallowing errors.

On Windows, natural successful phases require **observed job0 before AND after
cleanup**, independently, without terminating a job to manufacture success.
Failure cleanup terminates only the recorded owned job, then observes zero.
Receipts include `full_export`, `containment_confirmed`, and the actual exit;
cleanup failure is recorded before guard release. Shared retirement writes its
result/authorization before deletion, so a receipt-write failure there leaves
the runtime. Filesystem deletion and the final retirement receipt are not an
atomic transaction; if final writing fails after deletion, the earlier complete
phase/export/authorization evidence remains. Never retroactively strengthen
historical receipts that only recorded a pre-cleanup census.

All driver entry points require fresh, resolved, disjoint runtime/evidence roots
before fixture creation. These are trusted serialized synthetic roots, not an
adversarial ancestor-swap/hardlink/TOCTOU boundary or a durable crash-proof
transaction. A hash export taken while containment is unconfirmed is not a
retirement certificate; the independent process guard still blocks deletion.

## The active initial-publication exception is not a full export

`QKU_FSLock` exclusively byte-locks `.ftesurf-updater/install.lock` while the
client lives. A full runtime read at that point fails on Windows, even after a
separate journal source lock is released. Initial source-lock acceptance must
capture authority/temp/staging/content **before same-game retry**, so it calls
`publication_snapshot`, not the full exporter. This exact-purpose capture:

- excludes ONLY `.ftesurf-updater/install.lock`, explicitly listing that path;
- emits `active-runtime-files.sha256.json` and `active-export.json` with
  `active_export: true`, **`full_export: false`**;
- still refuses an unreadable authority/content/staged file, and still guards
  incomplete export/receipt writing;
- cannot substitute for the mandatory complete post-containment export.

Legacy initial-failure saves its refused-state log before retry; its full export
is after client containment. Three early native attempts that requested a full
export while a client held the install lock remain recorded FAIL, with job0 and
retained runtime rather than partial-export deletion. This failure acted the new
preservation guard, not a product failure.

## Verification

Owned root: `C:/FTESurf-worktrees/wjaudit-20261013T225700Z/`.
Base QC `55b2d162af8aa4acddc59f57db7e09b68e6f85cc`; immutable accepted external
engine control27c58e / subject195dc58e, not canonical/fleet binaries.

- **69 client-free Windows tests** (`units-05.log`), no skips: fresh/disjoint
  preflight, real post-mutation fixture bytes, grading/early-exit,
  read/copy/hash/inventory/receipt/handle/containment and final-export refusal;
  root/subtree enumeration denial; exact initial/interruption duplicate callsites
  with one-shot read/hash/receipt failures. Reusing a failed target cannot alter
  its receipt or release its guard, nor can a complete separate-target fallback.
  The separate legacy harness has three Windows passes/four POSIX-only skips
  (`harness-02.log`); its synthetic unit now explicitly verifies then discards
  only its own retained copy-failure guard before fixture disposal. Mock process tests are not
  native process-interruption acceptance.
- Acting baseline/current mock-native protected-content grading probe04:
  both phase receipts remain FAIL and both runtimes retire; the baseline loses
  landed/protected content identities, while the current runner retains exact
  hashes in complete phase and fallback exports. Earlier malformed probe actors
  and an incorrect baseline status prediction are preserved, not accepted.
- Fresh frozen matrix05 (after both review fixes; matrix04 retained separately): **10 old/subject native driver matrices**, unchanged
  semantic outcomes/attempt budgets; **94 PASS phase receipts**, each with full
  export and independently observed natural job0 before/after cleanup.
  **130 full inventories**, **528 independently byte-hashed raw exports**, and
  two explicitly non-full active initial-refusal captures pass the raw audit.
  Signed plans, native replacement/error/interruption actors, HTTP counts,
  metadata/certificates/staging and protected sentinels retain existing graders.
- Direct client-free review probes: frozen04 same-target retry overwrites FAIL
  and releases the guard; fixed retry refuses with the original receipt unchanged.
  Exact Python3.10 frozen04 directory-listing denials produce omitted staged data
  or an empty full PASS; fixed traversal records FAIL and retains evidence.
  These are harness fault injections, not native product failure actors.
- Unchanged signed-feed tests:12 pass; recorder tests306 checks/0 failures;
  read-only canonical corpus273 runs/91 views has173 faults in BOTH baseline and
  subject (reader bytes unchanged), no increased faults or exported raw owner
  filenames/GUIDs. This is not a clean-corpus claim.
- Three unchanged native helpers rebuilt with
  `gcc -Wall -Wextra -Werror -municode -static`; zero compiler diagnostics.
  Python LSP diagnostics alone are not these native gates.

Reproduce client-free controls with an existing owned scratch directory:

```text
set FTESURF_TEST_SCRATCH=<owned>/tmp
python -B -m unittest discover -s tools -p test_update_native_journal*_unit.py -v
```

Native inputs/commands remain the driver-specific contracts in
`p692native_journal.md`, `p692native_journal_deferred.md`,
`p692native_journal_interrupt.md`, `p692native_journal_initial.md` and the separate
`p692native_journal_deferred_interrupt.md` follow-up.
The task artifacts retain exact commands, signed-fixture paths, frozen sources,
source/helper/binary hashes, failed histories, raw audits and review dispositions.
No helper belongs in a shipped client/archive.
