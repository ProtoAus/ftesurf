# P1568 — bounded large completed-run acquisition

## Scope

Remove the old 8 MiB authenticated owner-archive cliff without changing the REC
grammar, movement, receipts, native certification, rank eligibility or ownership.
TAS remains assisted and unranked. This does not activate the separately staged
online TAS backend or retroactively assign historical unowned files to a player.

The new acquisition safety ceiling is **1,073,741,823 bytes**, not unlimited
storage. Original completed bodies remain on the server when acquisition is
unavailable. A failed copy is not a successful local save.

## Contract

- Native read-stream mode10 opens an ordinary loose gamedir file without the
  old first-read whole-file materialization. Existing modes and their sandbox
  remain unchanged. The stream uses a full-width native offset and is unmapped
  on Windows. Archive use is single-writer, with external writers excluded.
- Native `fsize64` returns an int64. VM-owned incremental SHA256 accepts bounded
  work per call; cancellation, close and VM shutdown discard its state. There is
  no successful-digest cache. The native hash ceiling is separate from the
  narrower archive admission ceiling.
- An actual successful recorder-completion hook may persist a private pending
  owner promise for a large body. It captures the already proven account, byte
  size and canonical path. The promise is neither a native verdict nor retrieval
  authority without the subsequent full content digest.
- Server list2/get2 creates a private on-disk snapshot with bounded copy/hash
  work. Its verified handle also supplies headers and transfer bytes. Existing
  v2 owner seals retain their full hash/size/path/account binding. No orphan
  backfill is inferred from a display name or readable header.
- Totals are canonical decimal integer strings, with integer byte counters.
  Fragments are at most880bytes, four per50ms sender tick, at most eight not yet
  acknowledged. These are bounds, not a measured transfer-rate promise.
- Client writes an owned part, closes it, independently hashes that persisted
  file, and only then promotes it. Uncached `fwritepathstatus` must confirm the
  write-path destination is absent both at acquisition and promotion. Occupied
  or inaccessible files, directories and unknown parts are retained. This is
  not an atomic reservation against arbitrary external writers.
- Progress belongs to the matching query, transfer and map/profile context. A
  healthy same-context foreground listing is not cancelled by the30-second
  cache-refresh clock; successful completion starts a new cache interval.
- Acquisition does not automatically play the recording. Local header indexing
  also uses bounded stream reads on a capable native engine.

Old clients keep the bounded legacy protocol. Updated CSQC requires the native
uncached path-status builtin before creating a part; unsupported native versions
fail closed with an update hint. Both ends need the new stream/hash/size support
for `fs_archive2=1` and v2 acquisition. Menu data is client-local, never a lobby
ship item.

## Qualification state

Implemented and independently reviewed, **not yet a deployment/release claim**.

- Native production-source controls: Python-matching SHA256 at1/4093/65536-byte
  work budgets, handle/VM/quota/error/seek/close controls, and a real unmapped
  Windows sparse4GiB+3 open/read/seek control. This is not a4GiB transfer claim.
- Clean tagged Windows client/server/five-plugin build passed. Matched baseline
  retained all74 warning occurrences exactly; no new warnings. The actual
  dedicated image reports `git-8769-patch-1568-0-gcc56219a3`; its map-free
  selftest passed1831checks with zero failures.
- Canonical Git-blob ARM64 source at the same commit built successfully and its
  actual map-free selftest passed1831checks with zero failures. All16 compiler
  warnings match the same published-base ARM build, with zero new diagnostics.
  Windows worktree bytes and canonical source bytes are separate hash domains.
- Three QC VMs compile with zero warnings. Fresh frozen integration review
  closes the long-list cache and failed-read-open/absence findings.
- A genuine154-tick TAS completion, authenticated account proof, positive get2
  transfer and31,822-byte identical local copy acted. No automatic replay.
- `python tools/test_reccheck.py`:952checks, zero failures. Actual paired CLI:
  578REC +174paired VIEW +10unpaired VIEW, same762input hashes,366faulty reports
  and368diagnostics under both pinned readers, zero new fault cases. Earlier
  standalone-VIEW365 counts are a different context; failed caller comparisons
  are retained, not silently regraded.
- A clearly synthetic17MiB+3 opaque body exercised production pending recovery,
  snapshot/hash, authenticated list2/get2/ack2, full reception, independent client
  hashing and promotion. Original, full part and final were all17825795bytes with
  identical SHA256. Only a modeled private pending promise was seeded; production
  created the full owner seal. This is byte-transport/recovery evidence, NOT a
  valid REC, genuine large completion, submission or native certification.
- A native unreadable-but-write-open-existing part sentinel caused the actual
  automatic acquisition to refuse locally without sending get2; its bytes and
  exact DACL survived. A separate late final sentinel survived a real transfer
  past8MiB, but that bounded observer stopped before full reception: full-body
  promotion refusal is unmeasured.
- Genuine >8MiB successful completion/native pending creation and a healthy same
  foreground query lasting over30seconds remain unmeasured. The genuine long
  capture was safety-interrupted, and its unfinished raw observation was neither
  resumed nor adopted. No arbitrary-size, memory-usage or performance claim.

Engine pins now name `cc56219a3c7e2a99128cc8ff02285d57a25e422b` / `patch-1568`.
Clean QC-commit qualification, dual Windows delivery and guarded native-then-QC
fleet delivery remain to be recorded.
The existing QC-only fleet transaction cannot replace a native executable. A
native swap also requires fresh selected-verifier/backend dependency evidence;
it must not silently invalidate or relabel the separately frozen backend plan.
