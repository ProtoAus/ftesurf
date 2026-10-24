# P978 — accepted Reload is read-only

P970 component review found explicit Reload could retain `vm_unsaved`, then ACK
those stale local choices at the fresh revision and cause an implicit CAS write.

`VM_SVLoad` now distinguishes automatic rebind from explicit Reload without
changing the existing public commands. Only an accepted `begin` generation
carries the intent; a busy/rejected button press does not clear dirty protection.
The client applies the cloud value if its begin snapshot is unchanged, and keeps
post-begin edits. The server never auto-writes an explicit Reload ACK, including
an older client acknowledging differing data. Explicit Save still gets the
fresh revision and deliberately writes local choices.

## Evidence and falsifiers

- Three QC VMs, zero warnings; no native rebuild or pin/tag/Build change.
- Ten acted real-socket controls with actual nonce/proof/account/GET/ACK routes,
  delayed reply, own-value checks and an observed explicit-write positive
  control. The account authority/API is an isolated loopback fixture, NOT real
  Steam or live-cloud acceptance. No fixture rows/grants entered production.
- Social68 tests pass: genuine22 lacks the new table; migration/repeated startup
  preserves all old definitions/values; failures before23 stamp and after23
  commit are inspected and forward-completed on the same synthetic DB; revision
  CHECK constraints reject invalid stored values.
- Board migration tests retain independent `HEAD_SCHEMA`, now23. The initial13
  failures were precisely obsolete22 expectations, not ignored or waived.
- ARM rehearsal uses a private consistent copy of the effective22 DB and exact
  candidate runtime. All33 old persistent-table digests and all old schema
  objects survive; only volatile lobby VALUES are excluded. Assignments must be
  empty. The exact comparator rejects a changed pre-existing account value.
- New setup table/index must match the code's DDL exactly and remain empty
  before opening the successor; no existing evidence/record bindings change.

The fixture initially used an invalid finish4 (valid0..3); strict rejection was
correct. It also served old CSQC from the dedicated fixture, overriding the new
client file with its old cached CRC. Both negatives are retained; the reusable
fix was same new CSQC on SERVER and CLIENT, not a native debug workaround.

## Delivery boundary

Implementation/component proof is not installation. Qualification/deployment
must preserve the current approved MENU8/client role and already-delivered
retry fixes, without silently shipping a different in-progress menu cohort.
The account service needs a source-bound, independently reviewed22-to23 guarded
handoff; no old review, consent, epoch or frozen witness may be relabelled.
Actual role SHA, hashes, deployment and linked-install owner check are recorded
separately after those steps. Real owner acceptance remains pending lextest.md.

## Delivered progs, account-service gate still pending

24 Oct2026: clean role `4c65fd99a2aa8a61a043ed7522b2df5462dfed26`
combines the then-installed15f8d239 menu/client cohort with P978. Its Reload
VM/test blobs equal component `a7c38aba6cf5a1a841ee5e8aafebe50bfda7dc1b`;
all3VMs compile with zero warnings and its actual artifacts pass10 acted socket
checks. Progs/lno plus matching cache installed on both Windows installs and all12
Pi lobbies. Windows promotion preserves14,693 other files; no native, menu,
shader, config or player-data replacement. Ordinary progs delivery restarts
empty lobbies; it is separate from the proposed backend-only operation.

This receipt is not a claim that a later fleet deployment still uses those
bytes. Later main/menu/native work is preserved in the public integration,
not silently attributed to this qualified role or redeployed from it.

The account service remains at schema22. Three component/safety reviews passed,
but subsequent shared-cron and serving-checker drift invalidated the execution
preimage/dependency tuple. No live handoff, reader repin, database restore or
real Steam-account pass is claimed. The separately qualified schema23 promotion
and the small linked-install owner check remain pending.
