# P689 — protected native recovery and bounded staged-object retirement

Source acceptance only, 2026-10-13. No QC Build/public version, release archive,
signed feed/site, canonical install or fleet deployment changed by this work.

## Source and concurrent integration

- QC starting point: `13972d90587d894e99bd5f98dce23916f258dbc4` (page retention).
- Engine starting point: `73322dff5b6898511d62ed775286b23a91b8aad0` (P688).
- Reviewed recovery feature: `c325d045dd3dcdd3494e3da4731571efcbf781d4`, public
  `patch-689`. Only qkupdate.c and its one Problem/Change/Verified entry change.
- A peer concurrently published blend sorting under P689, then reconciled its
  metadata forward to P690 at `7598b4c4d454db73774fdbc7ebea27ec45a9dba1`.
  Preserve both public histories/tags; no force push or tag rewrite.
- Integrated accepted source: `a8e705787fad1b60661da5e8dd43c9138cc69b1b`,
  `patch-690-with-p689`. This is a merge/tag, **not another product patch**.
  Recovery source is identical to reviewed P689; peer renderer/tests are identical
  to inspected P690. Native integration ends at P690; ENGINE.txt also preserves
  the later QC-only P691 counter/notes without inferring a new native build.

The isolated roots contain no owner/peer uncommitted source. No claim about the
peer's build/deployment is inferred from this merge or from the QC source pin.

## Root cause and change

A failed protected-file hash was interpreted as absence. A real unprivileged
Linux client replaced an existing mode000 local zone/mounts file with signed
bytes. Inaccessible ancestors caused late refusal after earlier content installed.
The shared planner/replay policy now returns install/preserve/unreadable; only
OS-confirmed missing file/path permits installation after a failed hash. Planning
classifies before moving/freeing candidate paths, and replay classifies the whole
signed journal against an unchanged ledger before replacing any row.

Mixed recovery rewrites only unresolved rows. After a successful rewrite, remove
only verified resolved staged objects that no unresolved destination still needs.
Corrupt and unreferenced objects survive. A journal write failure refuses without
retiring objects. Readable protected edits, genuinely missing files, signed state
semantics and ordinary Quakers policy remain unchanged.

## Acted native acceptance

`tools/test_update_native_recovery_posix.py` accepts a retained signed Linux feed,
object closure and external client. No seed, private key, pin override or dedicated
server. Run driver AND native child as an unprivileged uid on tmpfs/ext4. The
harness first proves mode000 read refusal; inaccessible-ancestor controls also
prove search refusal. A private mount/network namespace and consent=0 prevent
production traffic. +quit exits before graphics initialization; no Xvfb needed.

Sixteen before controls (`before-03`) and sixteen subject controls
(`subject-03`, then **subject-final on the integrated commit**) pass:

- Existing mode000 zones and mounts, each protected-first and protected-later:
  old signed overwrite ACTS; subject refuses before any earlier row changes.
- Two genuinely missing protected-file positives actually install and complete.
- Two inaccessible-ancestor orders: old earlier installation/late refusal ACTS;
  subject leaves content, local bytes, ledger and journal unchanged.
- Corrupt outstanding content, corrupt resolved protected object, and locked
  outstanding destination sharing a staged hash with a resolved row: truthful
  partial ledger/version, unresolved-only attempt-2 journal, no installed-envelope
  certificate, bounded retirement, and protected bytes preserved.
- Repaired retries really complete, commit the verified version/certificate and
  retire the pending object. Shared hashes survive until their last consumer.
- Forced journal OPEN refusal retains original journal and every staged object;
  retry exhaustion keeps the ledger/version/destination intact.

Every partial/completed phase has its own raw log, state/journal and staging-hash
snapshot. `NATIVE_RECOVERY_ACTED` is required for completion; an expected fatal
message plus nonzero owned-client exit is required for refusal. Silence is not a
pass. Results record engine/feed/harness SHA-256, uid/gid/groups and retirement.

Eight existing Windows cold-recovery controls pass on the fresh integrated
client (`win-recovery-final`): actual install, edited/unrecorded zones in both
orders/protected-only, corrupt-ledger and linked-ledger-temp refusal. Player cfg
and recording sentinels are synthetic and preserved; owned Windows jobs/modal
handling come from the existing harness.

## Reproduction and retained provenance

Owned root: `C:/FTESurf-worktrees/nrecover-20261013T094240Z/`.
`OWNER.md`, `artifacts/PLAN.md` and the checkpoint bind ownership and operations.
Raw evidence stays there; public Git contains this summary and test source.

```sh
# Linux: run in an owned private mount/network namespace with tmpfs runtime,
# setpriv --reuid=65534 --regid=65534 --clear-groups (NOT a root client).
python3 -B tools/test_update_native_recovery_posix.py \
  --engine /owned/external/client --feed /retained/signed/update.json \
  --objects /retained/objects --runtime-root /owned/tmpfs/fresh-fixtures \
  --evidence /owned/artifacts/fresh-evidence
# Add --expect-before ONLY for the old classifier/leaked-object detector control.

python -B tools/test_update_native_recovery.py \
  --engine C:/owned/fteqw64.exe --feed C:/retained/signed/update.json \
  --objects C:/retained/objects --work-root C:/owned/fresh-windows-fixtures

python -B tools/test_updatefeed.py --work-root C:/owned/fresh-feed-controls
python -B tools/test_clangdb.py
```

Exact task scripts/commands: `artifacts/build-linux-final.sh` (WSL Ubuntu-22.04,
private namespaces, bullseye chroot and dependency cache read-only),
`artifacts/build-win-final.ps1` (fresh m-rel, explicit RELEASE_DIR/ARCHLIBS),
`artifacts/run-posix.sh` (setpriv/private tmpfs/network), and final build/runtime
logs/results. No canonical build/deploy script or library cache writes.

Final SHA-256:

| Input/output | SHA-256 |
|---|---|
| Linux integrated client | `a65d5c428ab4cc10b187c66fc7fcdb9ee2dea38312443902ec94c32bc60395eb` |
| Windows integrated client | `e9e992469ebb622bff68ac55774f83d81f3ca86a8513c102361fef04466f1c49` |
| qkupdate.c working checkout, both builds | `c3a206fc65e90310ae565e422837e09e1f33e85cd3dfea5ec6f766fc59077fd7` |
| qkupdate.c committed LF content | `dab0308e0a2442554ffba489da10adfd2ff3c3f898745947a02bebadb7c455e9` |
| P690 gl_backend.c, control and subject | `c614650d462518d6369e4b1f75a1a4aee84f631804704220be096e4e7fb09c4b` |
| Production 0.1.25 signed Linux feed | `1568a34c99ffca799db6ddb70dee9fde941d38038f7bdff32afbedd99386bb9f` |

`commit-source-binding-final.json` proves the only source/commit byte difference
is checkout CRLF normalization. Actual feed/object hashes are verified before
fixtures are populated. Windows uses the retained P687 signed fixture, recorded
separately by its result; it is not represented as the production Linux closure.

Both fresh Windows builds (P690 control versus P689+P690 subject) have the same
259 compiler/Make warning occurrences, zero new (`warnings-final.json`). This is
not a zero-total-warning claim. Linux final has no compiler warnings. Standalone
clangd with the exact UCRT driver allowlist, configured DLL PATH/Windows TMP/TEMP
and --tweaks= reports zero errors (`clangd-check-02.log`); cached diagnostics alone
were not accepted. Unit controls: 12 feed tests and 4 clangdb tests pass.

Two native read-only reviews found no P0/P1/source defect; follow-up closed the
Windows-rerun, ancestor and phase-evidence notes. Its documentation P2 (missing
this record during review) is closed by adding this file. No private key/output
or real player data belongs in public Git.

## Failed attempts and retention

Do not count failed infrastructure as acceptance:

- First build wrappers guessed unsupported profile/output/library flags: builds
  failed before action. Corrected against retained scripts and actual Makefile.
- Successful Windows compilation initially had a wrapper's wrong executable
  filename; another CLI used --root instead of --work-root. Fresh corrected
  wrapper/reruns provide acceptance.
- Expanded before/subject-02 predicted a written attempt-4 journal, but the limit
  is checked after increment and refuses before that write. Failure export also
  hit unprivileged DrvFS copystat EPERM. Corrected expectation, copyfile-only
  export and nested-finally retirement; fresh -03/final runs supply acceptance.
- Initial standalone clangd lacked its driver DLL environment; the configured
  rerun is the parse result. Reviewer launch rejected an option before a child
  ran; corrected native reviewer was used, no external CLI/provider fallback.
- An unpublished local tag briefly named the pre-feature base after a commit CLI
  ordering error. Its absent remote and exact local target were verified before
  correction. The later public patch-689 tag was preserved untouched.
- Pre-push ancestry guard stopped on peer publication; preserved public tags and
  merged/rebuilt/reran the integrated source instead of force-pushing.

Synthetic Linux runtimes retire before result writing. Windows fixtures retain
logs/results/ledger/journal/manifest and an all-files/link hash inventory before
retirement. Disposable compiler objects/PCH/dependency files and clean worktrees
are retired; needed native binaries/symbols, source commits, exact scripts and
unique failure/acceptance evidence remain under the owned root. Checkpoint/OWNER
record exact final paths and any blocked cleanup; other sessions' roots stay
read-only and are not cleanup targets.

## Not certified

The later Windows continuation in `tools/p689native_windows.md` closes live
unreadable-candidate planning and leaf ACL/share-mode refusal with acted native
controls. Actual default-HTTPS menu/restart handoff, Windows ancestor denial,
hostile concurrent ancestor swaps/hardlink aliases, and crash-safe journal
replacement remain separate falsifiers; no such guarantees are inferred.
The preexisting remove-then-rename journal gap is NOT fixed by a guarded purge.
No new native map/rendering/sorter correctness, release or deployment is inferred
from these cold-recovery controls or from a source pin.
