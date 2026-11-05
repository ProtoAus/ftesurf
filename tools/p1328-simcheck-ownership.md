# P1328 - participating collector ownership

## Problem and scope

The short atomic flush protects an existing observation, but it cannot prevent two
collectors from measuring the same pair before either flushes. A real-reader
control runs a reverse comparison on a second connection during the first:
both perform80aligned opportunities, an independent SQLite writer commits, and
only the first completed observation is inserted. Stored uniqueness is not unique
concurrent work.

Both collection entrypoints now acquire nonblocking, host-local OS ownership of
the canonical SQLite database for their pass. A competing participating caller
abstains before schema/admission/source resolution/reader work. The pass calls its
already-owned comparison primitive rather than reacquiring its own ownership.
File comparison holds NO SQLite transaction or write lock; independent API writes
remain possible. Existing atomic same/reverse first-winner protection remains
necessary for older or nonparticipating callers and is unchanged.

For ordinary single-link disk databases the persistent EMPTY sidecar is
`<canonical database filename>.simcheck.lock`, mode0600 on POSIX. Windows uses a
nonblocking byte-range lock beyond the empty file's EOF; Linux uses flock. Handles
are noninheritable. Closing the last owning handle releases kernel ownership,
including process exit. NEVER unlink the sidecar after release: another open
handle could otherwise own a different inode from a later caller. No player
content, PID, identity or recording is stored in this file.

Unsafe/nonregular/multilink/nonempty or changed-name sidecars, unsupported database
aliases and unknown OS capabilities abstain, never silently compare unlocked.
Anonymous in-memory databases conservatively serialize within this imported
module. This is participating trusted-host scheduling, NOT a cross-host lock,
untrusted-process fence, arbitrary-import-alias guarantee, durable per-pair lease,
completion record, or proof that admitted work finished. Crash-lost unflushed work
can be retried on later rotation. Whole-pass time/RSS and coverage remain partial.

No new SQL schema/index/player capture, evidence format, native/game program,
pin/tag/qcbuild, detector threshold, default allowance, badge, tier, ranking or
consent change. Read-only pending/summary paths and disabled collection create no
sidecar. The existing selected-read VM allowance does not claim to budget OS
metadata/locking, schema writes, native work, global I/O or wall time.

## Verification

- Acting exact old source: outer and reverse actual readers each measure80;
  independent writer commits; one stored first winner. Fixed source: only outer
  reader measures80, reverse explicitly busy/no read, same writer commits, same
  one observation and exact compared-buffer capture.
- Windows235unittest cases,0failures/errors,6explicit existing/platform skips;
  actual Linux Python3.11 same235cases,0failures/errors/skips. Legacy script exits0
  separately on Linux. Same final module SHA256
  `afc9f3c8d6bf6e3b8705e986dea6d4016d704d660e0532fdb8ebba6ead6ab750`.
-18new controls: repeated contenders do not release another owner's lock; busy
  pass has no loader/schema/cursor work; read-only paths stay usable; independent
  DB succeeds while an alias of the same DB contends; zero/invalid/caller-owned
  paths preserve their prior behavior; unsafe files fail closed without chmod,
  truncation or target writes; exception recovery and actual child abrupt exit.
- A child ACTUALLY measures80after durable source admission but before flush,
  holds no SQLite transaction, then exits abruptly. Parent normal writer commits
  while child is held; contender abstains; later actual collection stores all
  three finite fixture pairs, including the unflushed pair,80opportunities each.
  This finite crash control is not a complete-fleet or exactly-once-work proof.
- Existing first-winner controls intentionally call the already-owned primitive
  to model old/nonparticipating writers. Fault-injection seams target that same
  primitive. Real flush uniqueness and transaction-ownership controls remain.
- Fresh reader949checks/0failures. Corpus548records/168views retains344faulted
  records and7faulted views, NOTclean. Prior546record/168view bytes exact; the two
  new actual records parsed clean. No player files changed.

Initial broad unittest discovery imported the legacy script's SystemExit0 and old
fault-injection seams missed the new owned primitive. Original failures remain;
correct underscore discovery/explicit nonparticipant seams do not weaken gates.
The passed234-case source/receipts remain preserved before final nonblocking-FIFO
and repeated-contender controls. A corpus importlib caller initially omitted the
existing tools import path; corrected caller, unchanged reader/helpers.

## Delivery state

Source and acting controls qualified. Independent review/publication and guarded
backend-only delivery are still pending; this document does not claim deployment.
The current live P1322 runtime and its rollback/history remain untouched.
