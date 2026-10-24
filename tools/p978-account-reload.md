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

## Initial progs delivery (historical role)

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

## This workstream's progs and live account service

24 Oct2026: role `aa1fdc5367986ca10b29ed6ff678b61a0ee00342` integrates P978
with the published P973-P984 peer work. All three QC VMs build with zero warnings;
ten acted socket checks pass using the current native and actual compiled VMs.
Its menu equals the installed menu, which was preserved rather than promoted.
Both Windows installs received the four QC/lno files and matching CSQC cache at
20:27:59Z, preserving14,693 other files. All12Pi lobbies received the same progs
and cache after a positive direct all-connection census, including spectators.
Client SHA256 `7495db356d9d2187e6a5e47a8dac73824cb080c46a0609e6c8c9afc254d5e162`;
cache `58b40ab3.dat`. Later peer P985 integration retains this Reload fix; it is
not silently attributed to this artifact receipt or rolled back.

The account service schema23 handoff completed20:59:24Z and verified20:59:50Z.
Three fresh independent reviews approved the actual execution sources. The
closed-stage full comparison preserves all33 existing persistent tables, old
object definitions and typed values, except volatile lobby values; only the exact
new setup table/index are added. No historical data restore or installed-reader/
native replacement.
The backend operation leaves all12 game PID/birth/native identities, installed
configs and stopped AI unchanged; the earlier ordinary progs swap is separate.

Live health, board/API, current service/importer identity and all12 fresh lobby
entries verify. Public HTTPS health and lobby list return200, and the documented
browser board `https://proto.bar/ftesurf/board/` and its nonempty browser map API
return200. No Build bump or release was made.

Real linked-Steam Save/Reload and the small owner visual check remain pending
in lextest.md. Socket fixture authority is not a real Steam-account pass.
