# P689 continuation — Windows live/cold unreadability acceptance

Tooling and measured evidence only, 2026-10-13. P689 native product source is
unchanged. No engine patch, pin, QC Build/public version, release, signed public
feed, canonical install or fleet deployment changed. Production 0.1.25 remains
P687. This extends `tools/p689native_recovery.md`, not another product patch.

## Inspected inputs and ownership

Owned root: `C:/FTESurf-worktrees/winplan-20261013T105246Z/`; OWNER and artifacts/PLAN
record predictions, owned paths/processes and retention. QC starting HEAD/origin:
`ba56bf486c0cd911ee512c8a6a9aee34f9d45028`; clean engine inspection HEAD/origin:
`9c7737643edb65dc9dc3aa09016f4ae9b92edad6`. Canonical peer changes are untouched.
Prior update/nrecover roots are read-only inputs, not cleanup targets.

During publication the peer advanced QC to `839cf9578d2190df13b5cdc9829ecb83ee38de2a`
and engine notes to `27c58e07a993636aa6d5f75064174518c8cea5c2`, recording its own
integrated dual-Windows delivery. Those inspected documentation-only histories
are preserved, not redeployed or certified by this continuation. No harness or
native product source changed in the merge; ENGINE.txt changes here narrow only
the completed gate comments, not the peer's pin, patch counter or delivery record.

External native clients come from P689's retained, clean controlled builds:

| Input | Source / SHA-256 |
|---|---|
| Before: P690, no P689 recovery | `7598b4c4d454db73774fdbc7ebea27ec45a9dba1` / `0e362ffeb08ce6ed4a11abe72e2441e3d733c6cf76970c470442bbe955de61b4` |
| Subject: integrated P689+P690 | `a8e705787fad1b60661da5e8dd43c9138cc69b1b` / `e9e992469ebb622bff68ac55774f83d81f3ca86a8513c102361fef04466f1c49` |
| Retained signed Windows feed | `coherent-production-archive-win-04/http/update.json` / `35942d7284e7f57625d9cfacfd644eae75c2b296dfc9df775f80a04c110320f3` |
| Final Windows driver bytes | `fb4b16da86e6933bfb2cf4355140615c8c4ed0c63a44eae2017d7d7a5dad6dd1` |

Paths for native builds are under `nrecover-20261013T094240Z/build/win-control2`
and `build/win-final`. Earlier build/source-binding records establish source;
this continuation rehashes actual native bytes rather than claiming new builds.
The signed feed selects 821 win64/all entries (~58 MiB), including local
`agtricks.json`, `fs_addons.txt` and ordinary `gfx/updater_fixture.txt`. Production
objects are retained under `coherent-publication-live-04/update-0.1.25-06f57540b8354429ac1ee26d52f74f42/objects`;
the additional synthetic fixture object is under `bootstrap-archive-04/http/objects`.
All feed/objects are verified before fixture population. No signing seed/key or
pin override is read; archived payloads remain a matched set inside each synthetic
install while the independently inspected external client executes.

## Controls that ACTED

**Final paired runs:** `artifacts/before-05/result.json` and
`artifacts/subject-05/result.json`: **16 expected-before + 16 subject passes**,
all 16 disposable arms retired per run. Both results bind the final driver and
actual native/feed SHA-256s. Each phase has exported native logs, metadata,
staged bytes and all-files hash/link inventory; raw results remain in the owned
root, not public Git. `artifacts/provenance-final.json` independently rehashes the
current driver/inputs and records refs/status; whole new source is in
`artifacts/harness-untracked.diff`.

| Matrix | Before actor | Subject actor |
|---|---|---|
| Live zones/mounts, sharing lock or read-deny ACL (4) | Signed check reports two files AVAILABLE, not protected-file refusal | Exact protected-path refusal, state ERROR; apply reports nothing to apply |
| Live readable protected edit (2) | Same preserved-edit positive | Ordinary content installs; local edit and old ledger hash preserved |
| Live missing protected destination (2) | Same real-absence positive | Ordinary + protected signed objects install; version/hash ledger advances |
| Cold zones/mounts, sharing lock, both journal orders (4) | Ordinary content changes before late `Unfinished content update` fatal; target unchanged, unresolved-only attempt-2 journal | Early protected-file fatal, no destination/ledger/journal/staging change |
| Cold zones/mounts, read-deny ACL, both orders (4) | Signed bytes replace protected file and its read-deny ACE; startup ACTS | Early protected-file fatal, no destination/ledger/journal/staging change |

Denial is real Windows behavior: attributes prove the file exists; CreateFile read
must fail with sharing error32 or ACL error5 before launch. Sharing denial remains
held until exit. In the before/ACL bug actor, replacement discards the deny ACE
and makes the new file readable; requiring continuing denial would falsely reject
the reproduced bug. Subject/unchanged arms prove denial remains through exit.
Original DACL ACEs/defaulted/protection are restored afterward; a read probe and
file hashes confirm access/bytes. No real user ACLs or player files are touched.

Each live check uses exactly one manifest GET, zero object requests before its
terminal planner verdict. All four subject refusals also remain object-free after
attempted apply: no journal/staged payload or authoritative metadata mutation.
Positives actually download/install one or two signed objects and commit the
expected version. Both protected classes, row orders, synthetic player cfg/run
sentinels and every other managed destination have explicit byte invariants.
Cold fatal text names the protected target, nonzero exit is required, and normal
startup actor is forbidden. Echo-only, timeout and silent command failure fail.

Clients are suspended before assignment to kill-on-close owned Windows jobs.
Live trusted `-plugin` stdin runs after explicit readiness; headless rendering
avoids claiming any UI/menu acceptance. CWD remains C:/FTESurf, with explicit
owned basedir/manifest and cfg_save_auto0/cl_idlefps0/cl_maxfps100/autocheck0.
Consent is disk-seeded; server commands never grant it.

The unchanged signed mirror binds loopback port63139 only with
SO_EXCLUSIVEADDRUSE and address/port reuse disabled. An owned ephemeral busy-port
control proves duplicate bind rejection **before any client launch** (error10048
in both final runs). No occupied peer listener is probed or displaced.

## Reproduction

Run from the QC checkout; use a new owned task-root runtime/evidence directory.
Do not run the older signing harness or change an envelope's mirror URL.

```sh
python -B tools/test_update_native_windows_unreadable.py \
  --engine C:/owned/external/fteqw64.exe \
  --feed C:/retained/coherent-production-archive-win-04/http/update.json \
  --objects C:/retained/coherent-publication-live-04/update-0.1.25-06f57540b8354429ac1ee26d52f74f42/objects \
  --objects C:/retained/bootstrap-archive-04/http/objects \
  --runtime-root C:/owned/fresh-runtime --evidence C:/owned/fresh-evidence
# Repeat with the inspected pre-P689 client and --expect-before.
# --phase live or --phase cold limits the matrix; final acceptance used all.
python -B tools/test_updatefeed.py --work-root C:/owned/fresh-feed-unit-controls
```

Feed unit controls: 12 pass using the public RFC test vector, no production key.
Python syntax/import and LSP diagnostics have no errors recorded; these are not
native build verification. No native source/flags changed, so no new compiler
warning claim or engine rebuild is made.

## Failures, review and retirement

Failures remain failures, not successful acceptance:

- `subject-01/02` were preflight missing-object failures before root creation:
  archive HTTP held only the envelope, and production closure lacked its synthetic
  fixture object. Repeated read-only --objects supplies the verified union.
- `subject-03` rejected whole security-descriptor equality after restoration.
  Windows cleared an inheritance bookkeeping flag without changing ACEs. Actual
  DACL comparison + restored read probe is the corrected contract.
- `before-01/02` expected successful startup for sharing-denied partial recovery;
  the native client instead stopped at its mixed-install guard. A headless rerun
  did not fix that wrong expectation. `before-03` captured the exact owned fatal,
  still failing; final controls require that late fatal and earlier mutation.
- `before-04` required read denial after the old engine had replaced the file
  object/ACL. It reproduced the overwrite, then failed the wrong postcondition.
- Independent review blocked default Python SO_REUSEADDR binding and the cold
  share actor expectation. Both were corrected and final paired matrices rerun;
  final evidence is bound to the new driver, not the earlier subject-04 pass.
- Two scout launches failed at unsupported native model IDs before child action;
  an explicitly selected known-working native model completed recon/review. No
  external CLI/provider fallback occurred.
- A supplemental command named nonexistent test_update_protocol.py; it did not
  run a test. The actual test_updatefeed.py suite supplies the 12 unit passes.

Export succeeds before deleting any synthetic runtime. Failed runtime copies may
be retired only after separately verifying owned inventory, no links, restored
readability and preserved compact evidence. OWNER/checkpoint records their exact
retirement; needed source/history/input binaries in prior roots remain untouched.
No blanket install/worktree cleanup or owner/peer process termination.

## Still not certified

Actual default-HTTPS signed-feed check/menu/restart, Windows inaccessible ancestor
controls, hostile ancestor swaps/hardlinks and crash-safe mixed-journal replacement
remain separate falsifiers. The remove-then-rename journal gap is unchanged. No
rendering/sorter correctness, release, installed binary or fleet acceptance follows
from these headless signed-loopback and cold-recovery controls.
