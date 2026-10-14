# Windows authority-bounded staged-object retirement — 2026-10-14

Tooling/test acceptance only. No engine/QC product change, patch/pin/build/version
bump, deployment, release, new orphan deletion or power-loss acceptance.

## Contract and provenance

`test_update_native_staging_windows.py` runs the existing native recovery code
against a retained production-signed loopback feed and fully verified read-only
object union. It never signs a fixture or overrides the key/pin. External client
source is P692 `195dc58e9054b421dc9c76530a0715df64864183`, SHA-256
`db9ee5b058740bc5346547510667249dc72681413f9d3dc8cba972e292e610c5`.
The accepted wrapper also checks complete executable-text equality with its
retained companion. Neither canonical/fleet clients nor the published P687
archive are replaced by this source acceptance. The driver records engine/feed
and Python-source hashes and rechecks client/source bytes before PASS.

Engine sites: `QKU_ReplayJournal` and `QKU_FSPurgeObject` in
`engine/common/qkupdate.c`. A successful pending-only journal commit permits
retirement of valid resolved objects, except hashes still referenced by pending
rows. Purging reopens and verifies both hash and size. Failed publication must
not retire any object. These are existing semantics, not a new cleanup algorithm.

Every cold phase uses the shared guarded job-contained runner, with independent
natural job0 before AND after cleanup, full post-containment exports and a
separate semantic receipt. Receipt-write failure retains its guard. Failed
native/export/semantic receipts remain FAIL; unknown containment/evidence blocks
runtime retirement. Shared evidence contract: `native_journal_evidence.md`.

The exclusive signed loopback mirror returns errors for any GET. Its final
counter is asserted/copied only **after** the serving thread and every accepted
non-daemon request worker have stopped; accepted sockets have bounded read
waits. A busy-port control acts before clients. Zero requests means zero observed
GETs to that signed mirror, not an all-network transport certificate.

## Native actors and exact predicates

All three-row cases run independently with the pending row first and last:

| Case | Partial recovery | Repaired completion |
|---|---|---|
| Unique valid objects | Ordinary replacement ACTS; edited local zone preserved; successful pending-only attempt2 commit removes both resolved stage objects | Pending replacement, signed certificate/current ledger, pending object removed |
| Same-size corrupt resolved zone | One-byte mutation has signed size but wrong hash; ordinary valid-object removal ACTS, corrupt zone object survives | Corrupt zone object still survives |
| Wrong-size corrupt resolved zone | Separate size mismatch, wrong digest; same ordinary deletion-positive control | Wrong-size object still survives |
| Shared staged object | Two signed destinations share exact hash/size; one is installed already, the other held with real no-delete sharing and independent MoveFileExW error32; shared hash survives pending-only reduction | Released destination installs from the same object, which is then removed |
| Journal rewrite failure | Writable temp/source lock gives real rename error32 and native refusal; original full attempt1 authority remains byte-exact, reduced attempt2 temp and ALL stage objects remain | Release/repair completes from full authority; failed temp orphan remains byte-exact |

A separate **seeded** reduced-authority case names only the pending row. A valid
resolved object outside that authority survives partial retry AND completion.
It is explicitly not a process-interruption actor: real reduced-authority orphan
provenance is already covered in `p692native_journal_deferred_interrupt.md`.
No unreferenced object is deleted. Valid and corrupt unrelated staged sentinels
survive every phase; settings, recording, unmanaged asset and edited-zone bytes
remain unchanged. Each phase grades the entire ledger/version, exact journal
path/hash/size/exec tuples and budget, signed manifest/certificate bytes, selected
destinations and complete stage-name-to-byte map. Partial recovery cannot publish
a completion certificate or advance the version/zone baseline.

## Verification and failure history

Owned root: `C:/FTESurf-worktrees/wjorphan-20261014T021841Z/`, QC base `1267ee3`.
Accepted frozen matrix02 after review fixes:

- **11 native scenarios / 22 PASS process phases**, each with full export and
  independently observed natural job0 before/after cleanup. Independent raw audit:
  **22 complete inventories / 81 rehashed raw metadata/log exports**, exact
  ledgers, authority/temp/certificate, protected/destination hashes and staged
  identities. All runtime fixtures retired only after evidence confirmation.
- **13 client-free tests**, no skips: acted deletion/retention mutations, shared
  hash, exact tuples/budget, version/ledger/certificate, protected bytes, unexpected
  GETs and semantic-receipt denial. Same-size corruption explicitly discriminates
  hash validation from size validation. An event-controlled real HTTP worker is
  held before incrementing its counter until teardown; final grading must reject
  that late request and preserve FAIL. These are harness controls, not native
  product fault injection or power-loss testing.
- Existing journal units81 pass; signed-feed12 pass; legacy harness3 Windows
  passes/4 POSIX-only skips. Recorder306 checks/0 failures. Reader bytes unchanged;
  read-only corpus273 runs/91 views retains173 faults in BOTH baseline and subject.
  No increased faults, no clean-corpus claim, no raw owner filenames/GUIDs exported.
- Fresh read-only reviews identified late HTTP-census ordering (fixed by joining
  workers before the final census) and different-size-only corrupt retention
  (fixed with separate same-size and wrong-size controls). Frozen matrix01 is
  retained, not retroactively strengthened. One predicate-review startup failed
  during worktree pi-lsp installation; same-protocol retry used the canonical
  package cwd with absolute read-only source paths, not another CLI/provider.
  Raw-audit script path/envelope/summary-schema mistakes remain in failed audit
  logs, followed by the corrected independent audit; they were not product faults.

Reproduce using fresh disjoint paths below an owned task root:

```text
set FTESURF_TEST_SCRATCH=<owned>/tmp
python -B -m unittest discover -s tools -p test_update_native_staging_windows_unit.py -v
python -B tools/test_update_native_staging_windows.py --engine <retained-client.exe> --feed <retained-signed/update.json> --objects <ordinary-object-root> --objects <bootstrap-object-root> --runtime-root <fresh-owned/runtime> --evidence <fresh-owned/evidence>
```

Exact argv, source freezes, hashes, raw receipts/audits, review/disposition and
failure history remain under the owned root. Inputs are trusted serialized
synthetic roots, not a hostile ancestor-swap/hardlink/TOCTOU boundary. Future
orphan GC still needs a bounded candidate/authority strategy that protects shared
pending hashes and corrupt/unmanaged data across interruption. Nothing here
proves file-data/directory flush ordering or hardware power-loss durability.
