# Proposed bounded native retirement protocol — 2026-10-14

**Design and executable-model acceptance only. NOT implemented in the engine.**
The P692 native orphan follow-up remains open. No engine patch/pin/build/version
bump, new native deletion, deployment, release or power-loss acceptance follows
from these model tests.

## Source problem and proposed decision

Inspected engine `195dc58e9054b421dc9c76530a0715df64864183`,
`engine/common/qkupdate.c`:

- `QKU_WriteJournal` 1587–1589 drops live DONE rows at deferred publication;
  `QKU_ReplayJournal` 2186–2188 drops cold installed/preserved rows. Purging comes
  afterward, so process interruption can strand objects outside the reduced
  journal. Native provenance is already measured in
  `p692native_journal_deferred_interrupt.md`/`p692native_journal_interrupt.md`.
- `QKU_PurgeStaging` 1616–1618 and replay completion 2215–2217 remove journal
  authority before purging. `QKU_FSPurgeObject` returns no deletion outcome.
  Completion interruption and held-stage removal failure need new native actors;
  these additional loss windows are source observations, not new native results.

Prefer **one bounded full row superset in the existing journal**, not a storage
scan or a second candidate sidecar. Keep every original transaction row (including
resolved DONE/preserved rows) across live deferred and cold pending publication.
Resolution is recomputed from current destination identity and protected-file
policy; a stored "resolved" flag must not grant permission to delete.

Proposed availability policy: after actual signed content completion, cleanup-only
retries are nonfatal for held/corrupt/unreadable staged objects and do not spend or
reset the content retry budget. Retain the same journal and signed manifest until
all its named staged objects were removed or OS-confirmed absent. A later in-game
apply may not overwrite that retained transaction; return launcher-required rather
than losing candidates. This is a conservative design decision, not a shipped
availability change. Launcher handoff/repair behavior itself still needs checking.
Linked paths/metadata and unreadable destination classification remain fail-closed;
nonfatal cleanup is not a relaxation of those preflight boundaries.

## Invariants and ordering

1. Before any content/retirement mutation, validate the signed envelope, release
   version/floor, bounded nonempty row count (at most8192), unique paths, exact
   signed path/hash/size/exec tuples, no-link metadata/object paths and whole-batch
   protected-file classifications. No journal means **no retirement authority**.
   A legacy reduced journal cannot adopt an outside orphan, even if its hash is in
   the signed release.
2. Unresolved content retains the existing three-attempt budget and exhaustion
   refusal BEFORE content mutation. Repairing only a staged input at attempts3
   does not authorize another content install. A validated already-complete set
   may retry retirement without changing attempts; it cannot enter content apply.
3. Partial publication writes/closes a sibling temp and atomically replaces the
   journal WITHOUT prior unlink. Preserve the full original row superset, version
   and the correct next content attempt. An admitted content pass must publish
   its bumped attempt even if it has now completed content but cleanup remains
   outstanding. Failed publication leaves old authority and ALL stage objects
   unchanged. Temp alone is not authority.
4. Retirement occurs only after successful partial publication, or after complete
   signed installation/ledger/offline-certificate acceptance under existing policy.
   Keep authoritative rows during the entire retirement pass. Recheck an object's
   regular/no-link identity, exact hash/size and absence of any pending shared-hash
   reference at the destructive seam. A preserved destination does not enter the
   ledger as the signed bytes.
5. Distinguish removed/OS-confirmed missing from held, failed open/hash/remove,
   same-size wrong hash and wrong-size objects. Only the first two discharge a
   candidate. Missing candidates after a previous interrupted removal are
   idempotent. Corrupt and unreadable bytes survive and remain named; they may
   retain a cleanup transaction indefinitely rather than authorizing destruction.
6. Drop completed journal authority LAST and check its removal result, only once
   every named candidate is discharged. Failed journal unlink keeps a nonfatal,
   idempotent cleanup transaction. Interruption before or between removals leaves
   all survivors named.
   Unrelated valid/corrupt objects, `.part`/`.install` siblings, failed journal
   temps and displaced-backup policy are not adopted by this retirement protocol.
7. Never overwrite retained transaction metadata during subsequent live apply.
   Check the exact launcher ownership/repair contract before selecting a handoff.
   Do not replay an obsolete release as a content update after a newer install.

Both live and cold completion paths need the same ordering; changing just one
writer or just pending reduction is incomplete. Keep legacy Quakers policy and
ordinary FS_Rename semantics unchanged. These invariants assume serialized,
trusted task roots: they do not establish hostile ancestor-swap/hardlink safety
or file-data/directory flush ordering under power loss.

## Executable proposal and falsifiers

`update_retirement_protocol.py` is an in-memory state-machine model. It does NOT
open/remove files, verify signatures, install content, run clients, implement
launcher behavior or model persistence on disk. Its signed-row table and protected
classifications are trusted test inputs; staged/destination byte identity is
computed with real BLAKE2b-256. Events label process-interruption cuts only.
The iterator starts AFTER content classification/installation; native installation,
ledger-write success, version ordering, initial live publication and signed crypto
must be tested separately. `content_admitted=True` represents the native
read-only admission/budget decision made BEFORE the unmodeled content installation;
its completion still publishes the bumped attempt before retirement. Cleanup-only
replay has no admission and does not increment. This is not an extra increment at
the live deferred writer. Actual content-budget admission must remain native
read-only preflight, not a boolean accepted from an untrusted journal.

`test_update_retirement_protocol.py` exercises:

- 168 cuts: 44 across completion/partial, shared/unique hashes and both row orders,
  plus 92 with held/corrupt/unreadable/missing candidates and 32 during admitted
  content completion with/without a held candidate; each restart discards
  volatile iteration state, checks survivor authority with an independent oracle
  and uses separate destination/stage repair actors for completion;
- valid removal and shared-pending retention ACT, publication failure preserves
  authority/stage bytes, missing candidates are idempotent;
- held cleanup at attempts3 remains nonfatal/named through repeated passes;
  admitted content completion persists its increment before held cleanup, failed
  final journal unlink retains authority, and unresolved content at attempts3
  refuses before mutation even with repaired stage;
- same-size wrong hash, wrong size and unreadable candidates stay named/byte-exact;
  unique valid removal is the positive control;
- signed tuple/exec/count/duplicate/generation rejection, full signed closure before
  completion, unreadable destination and linked-candidate batch refusal. The full
  closure must reject unreadable signed destinations OUTSIDE a legacy reduced
  journal too, including preserved paths; cached bytes cannot establish readability;
- no authority/legacy reduced authority cannot delete outside objects; failed temps,
  unmanaged objects and partial/install siblings survive;
- independent source-shaped legacy reduction and unlink-before-purge actors FAIL
  the safety oracle. The shared-hash oracle derives pending identities directly
  from fixture rows, destination bytes and protection inputs, not `pending()` or
  `matches()`; an injected always-empty implementation predicate still cannot
  hide an unsafe shared removal. These are model counterexamples, NOT native baselines.

Command from the QC root:

```text
python -B -m unittest discover -s tools -p test_update_retirement_protocol.py -v
```

## Minimal native rollout gates (still open)

| Gate | Reuse and required extension |
|---|---|
| Unique/shared/preserved/corrupt staged rows | `test_update_native_staging_windows.py` prepare/grade; keep exact full stage map, old partial ledger/no certificate, both row orders and same-size wrong-hash ACT control. Add full-superset subject expectations without changing the legacy reduced-orphan outside-object predicate. |
| Cold before/after reduction | `test_update_native_journal_interrupt.py`; preserve real native return/thread/path events and fresh repair/corrupt/exhaustion branches. Old after-commit orphan must remain a failing before control; subject restart must retire through carried rows. |
| Deferred live before/after | `test_update_native_journal_deferred_interrupt.py`; keep both writer ordinals/callers and all cold HTTP censuses. Exact full attempt1 authority must remain named after deferred publication. |
| Held staged deletion | NEW actor: hold the signed `ingame/staged/<hash>` leaf rather than the destination. Prove actual readable/writable identity and native delete refusal; another valid candidate must ACT removal. Release/restart must retire the held candidate with authority still present. |
| Mid-retirement/final authority drop | NEW source-bound debugger hooks before first removal, after one actual successful removal and before/after final journal unlink; actual API outcomes, no forced success. Restart must accept missing retired candidates and revisit named survivors. Add real final-journal unlink failure/retry. |
| Exhausted content versus cleanup | Reuse existing cold/deferred exhaustion actors unchanged for unresolved content. NEW completed-at-attempt3 retained-cleanup actor, plus admitted content completion that persists the bumped budget before held cleanup. |
| Damaged/absent authority | NEW native full-inventory arms for no-journal + orphan temp, malformed/unsigned/version-mismatched candidates, duplicate and tampered tuples. No scan, no temp adoption, no silent budget reset. |
| Retained generation/new apply | NEW live actor before object downloads AND before manifest replacement: old authority, signed manifest and staged candidates must remain exact when a new apply is routed to launcher-required. Validate launcher repair/supersession separately. |

Build an isolated exact-source before/subject pair; freshly verify immutable
client/companion PE text, helper bytes and the existing signed selected-platform
object closure before launching. Existing retained-input provenance and staging
commands are in `native_staging_windows.md`; never invoke an old wrapper unchanged
because it writes into that task's now-retired root. Require signed certificates,
protected/unmanaged hashes and full exported inventories with observed natural
pre/post-cleanup job0. Existing pending-only expectations remain historical
controls, not claims that the proposed engine already exists.
