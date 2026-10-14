# P692 — Windows deferred live journal process-interruption controls

Tooling/test source acceptance only. No engine/QC product patch, engine pin,
build/version bump, canonical/fleet deployment, release, default HTTPS, or
power-loss acceptance. Test-only debugger never belongs in a shipped archive.

## Provenance and admission

Owned root `C:/FTESurf-worktrees/wjdefer-20261014T005851Z/`; base QC
`e50f15cc607576928befff1e75948cf43e71ce13`. Read-only engine source
`195dc58e9054b421dc9c76530a0715df64864183`, `engine/common/qkupdate.c`:
`QKU_Apply` writes full attempt1 authority, installs ordinary rows, writes the
partial ledger, then rewrites deferred pending-only authority at attempt1.
Immutable retained native inputs (not canonical clients):

| Arm | SHA-256 of external client |
|---|---|
| old `27c58e` | `10a0216c290abc871d34f0fd962c7fe1a4eb0e5fa083783743aaee5b8e1cc7e9` |
| P692 `195dc58e` | `db9ee5b058740bc5346547510667249dc72681413f9d3dc8cba972e292e610c5` |

The driver reuses `bind_initial`: complete PE/companion executable text equality,
inspected initial/deferred direct-call bytes, native ABI/import/return/frame and
subject tail-wrapper checks. Existing malformed companion/call/prologue/frame
and wrong-byte unit controls remain mandatory; a matching filename is not proof.
The signed loopback feed and complete read-only object union are verified before
HTTP starts; an exclusive port/busy-port control refuses unintended services.
The exact live manifest/object counts **and unchanged counts after all cold
phases** are stored, preventing unexpected recovery requests from escaping grading.

## Real deferred boundary, not timing or result substitution

`native_journal_initial.c` keeps its existing 14-argument initial ABI. Supplying
an additional deferred-caller RVA and initial-authority snapshot selects the
second writer. It checks original entry/pre/post bytes before patching entry;
observes first caller; restores the original entry instruction and RIP;
single-steps that instruction, restores the saved trap flag, and rearms entry.
The second invocation must have the inspected deferred caller on the same thread.
It saves native full authority at second entry and requires first temp consumed.
At native publication it validates exact source/destination paths, flags/root
and subject commit caller; saves the complete native pending temp; observes old
missing authority versus subject retained authority. No API result is forced.
Before interruption restores the trapped instruction/RIP before terminating
only the owned child86. After interruption requires the actual positive native
rename return. Helper0, exact raw event order/call count/thread/ordinals/callers,
child exit and independently observed natural job0 before AND after cleanup are
required. Source/helper/engine disk hashes cannot change during a matrix.

A real held destination selects either the first or last of two ordinary signed
content rows. The other row must actually install before interruption. Both
objects must remain staged; exact partial ledger keeps old version, lacks the
installed certificate, and protected settings, recording, unmanaged asset and
locally edited zone bytes stay unchanged. This is not a simulated model writer.

## Separate fresh fixtures and attempt budgets

Both pending-row positions run each scenario independently, on each engine:

| Scenario | Required native and cold outcome |
|---|---|
| Uninterrupted control | Writers1+2 and actual successful native replace, pending-only attempt1 authority, temp gone, deferred/restart actors; next repaired cold launch completes. |
| Before replacement | Full initial attempt1 snapshot and complete pending attempt1 temp. Old loses authority and ACTS mixed-content cold startup with corrupt pending input/partial ledger. Only **after detection and full export**, restore saved initial authority explicitly control-only, repair, then complete. Subject retains full authority byte-exact, refuses corrupt retry and publishes pending-only attempt2; repair completes next. |
| After replacement/direct repair | Positive real native result, exact pending-only attempt1 authority, temp gone, installed sibling/partial ledger; fresh repaired next launch completes without an earlier corrupt retry consuming its budget. |
| After replacement/corrupt then repair | Separate fixture refuses before startup, publishes exact pending-only attempt2; repaired next launch completes. |
| After replacement/exhaustion | Separate fixture refuses corrupt retries at attempts2 and3. Repaired next launch still refuses exhaustion; attempt3 authority, all stage bytes, old pending destination, partial ledger and missing certificate remain unchanged. No budget reset. |

Completion requires exact final ledger/version, byte-exact signed installed
certificate, both selected destination bytes, no authority, pending-object
retirement and all protected sentinels unchanged. A reduced authority cannot
name the already installed live object's staged copy: it remains an observed
resolved-object orphan, not safe garbage-collection acceptance. Old before-
replacement control may also leave its failed temp orphan. Neither is silently
removed or converted into a power-loss certificate.

## Evidence, negatives, review and accepted results

All live/cold phases use shared guarded full post-containment exports: raw updater
JSON/TMP and logs, staged BLAKE2b identities, gamedir and all-runtime SHA-256
inventories, and full-export/process receipts. The new live outer guard is
distinct from its snapshot guard; containment/export/handle/receipt failure
retains FAIL and prevents retirement. No active install-lock exception is used
by this deferred interruption driver. Failed evidence targets remain immutable.

Preregistered `artifacts/PLAN.md`; frozen accepted matrix02 after review fix:

- **20 new native scenarios**: ten per engine, both pending positions; **56 new
  process phases**. Initial-publication regression runs add ten scenarios/18
  phases using the extended helper's unchanged default mode.
- **74 PASS process receipts** in total, full export and independently observed
  natural job0 before/after cleanup; independent raw audit checks **106 full
  inventories**, **482 byte-hashed raw exports** and two explicitly non-full
  initial-source-lock captures. All new scenarios store final offline HTTP counts.
- **81 Windows client-free tests**, no skips, including eleven existing new-driver
  actor/lifecycle tests and the review-added cold-request negative: malformed
  ordinal/caller/thread/path/RVA/authority/result/exit, missing/reordered/unknown
  actors, initial-only receipt, post-mutation early exit, hash/export,
  containment, handle and process-receipt denials. Mock faults are not native
  interruption acceptance.
- Actual native wrong-entry-byte control: helper90, observed job0, unchanged
  synthetic authority/temp/stage sentinels, full failed-state export. Its phase
  and result remain **FAIL**; the separate negative assertion passes. Runtime
  retirement occurs only after containment/evidence/receipt confirmation.
- Two fresh read-only reviews found no instrumentation/lifecycle defect. The
  evidence reviewer identified ungraded HTTP counts after cold recovery; fixed
  final counter assertion/receipt plus acted negative, then repeated both native
  arms and regressions with unchanged semantic outcomes. Earlier frozen01 and
  all command/audit failure history remain retained, not strengthened.
- Signed-feed tests12 pass; legacy harness3 Windows passes/4 POSIX-only skips.
  Recorder306 checks/0 failures; unchanged reader/corpus273 runs/91 views retains
  173 faults in both baseline/subject. No clean-corpus or new Linux native claim.
- `gcc -Wall -Wextra -Werror -municode -static tools/native_journal_initial.c`:
  zero compiler diagnostics; helper SHA-256
  `936c853f20d3dedc6ee333da6811537cd5b4170ce79f8732895e99c5a0fcb299`.

Reproduce with **fresh disjoint roots below an owned task root**, retained
verified signed inputs and matching native companion:

```text
set FTESURF_TEST_SCRATCH=<owned>/tmp
python -B -m unittest discover -s tools -p test_update_native_journal*_unit.py -v
python -B tools/test_update_native_journal_deferred_interrupt.py --engine <client> --symbols <matching.db> --helper <helper.exe> --feed <signed-loopback/update.json> --objects <ordinary-object-root> --objects <bootstrap-object-root> --runtime-root <fresh-owned/runtime> --evidence <fresh-owned/evidence>
```

Add `--expect-before` only for inspected old control. Exact accepted argv,
source freezes, raw receipts/audits, native negative and review dispositions are
retained under the owned root. Shared evidence contract:
`tools/native_journal_evidence.md`. Trusted serialized synthetic roots only;
no hostile ancestor-swap/hardlink guarantee, data/directory flush ordering,
hardware power-loss, new default-HTTPS or release/deployment acceptance.
