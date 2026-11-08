# P1420 — print measured opportunities in an offline pair detail row

## Problem / change

The existing `cmd_pairs` negative detail correctly computed MATCH using
`matched / compared`, but retained the longer source length under its printed
`compared` label. With 200-row inputs and 100 measured aligned opportunities, a
row could correctly print MATCH `.3700` yet incorrectly say `compared 200`.
The actual output format is `match ... cover ... prefix ... compared ...`;
it does not print a `matched/compared` fraction string.

Retain the measured `compared` count as appended display metadata and print it
under the unchanged label. Keep every old tuple field/index, including the longer
source length. Sorting explicitly uses the original ten fields, not the appended
metadata, preserving original ordering and stable ties. MATCH, nearest-rank p99,
cover/prefix, identity splits, pair selection/deduplication, positive controls and
all other output shape and statistical/eligibility contracts are unchanged.

No parser/recorder/capture/schema/new signal or threshold/ranking decision. This
is an existing operator diagnostic's honesty about what was compared, not corpus
calibration, enforcement or a new data-collection/identity/retention permission.

## Acting controls / validation

The existing standalone `tools/test_recsim_pairs_summary.py` executes actual
`cmd_pairs` with controlled acquired inputs and comparison results. It asserts
acquisition, negative and shifted-positive comparison counts and coverage; missing
or suppressed output cannot pass. Metrics are synthetic, not a real-corpus claim.

- Unchanged reader: `(matched=37, compared=100)` with 200-move inputs prints
  the correct MATCH `.3700` but incorrect detail count `200`. One genuine target
  fails, eight other methods pass, including the `(74,200)` full-length control
  and previous p99/zero/tie/unavailable controls. The scout's suggested literal
  fraction-format assertion was not used; the actual source format was inspected
  before writing the falsifier.
- Corrected source: all nine command-level methods pass. Existing real synthetic
  recording opportunity tests also pass six methods, independently exercising
  aligned 76/80 and 79/80 comparison/source-length distinctions and zero agreement.
  These are **15 Windows methods**, not native physics or production prevalence.
- Entire module AST outside `cmd_pairs` is identical to its predecessor. No reader
  grammar, comparison or collector dependency changed; earlier reader/corpus
  evidence is not rerun or newly claimed as validation of this display change.
- Sole reservation P1420 was published promptly before qualification, after both
  fetched-reference tracked reservations and all linked working-tree paths/ledgers
  were scanned. Reservation publication alone did not claim a product deployment.

## Review, immutable source and ARM delivery

Independent full source review is CLEAR. An isolated-index Git snapshot contains
only the reviewed four-path product diff; all five executable source/dependency
files were extracted from that Git tree into a minimal owned closure and re-proved
with the actual loader target asserted. All 15 Windows methods pass there too;
this is the same 15 methods, not another 15 distinct checks or peer-source evidence.

Actual aarch64 Python 3.11 qualification at **2026-11-08 06:53:27 UTC** passes all
nine command methods and all six opportunity methods. The old `2780` operator
reader fails the one target and passes the other eight command methods plus all
six opportunity methods. The direct isolated CLI `--help` and exact test-module
paths ACTED before qualification. Source and test bytes are unchanged from review:

- Reader SHA-256: `6c20126337e45f601a5823f4b07a48186d0aa52430e602e962e7d6a920842526`.
- Command test SHA-256: `4e2627f095039c6b2897ebd53f032683e64e22bdf5fd626b70a66448c7a4a860`.

The selected operator copy is retained at
`/srv/nvme/agent-work/ac-p99-1415-20261108-01a1/detail/tools/census/recsim.py`.
Its `qualification.json`, manifest, before/after snapshots and original failing
control logs are under that same `detail/` root. This is a separately owned child,
not an overwrite of the P1415 source or its earlier qualification clock/evidence.
The five committed source/dependency files and old-reader control were hash
verified at the destination. The local minimal source/evidence is retained too.

Before/after all 159 admitted source bindings, actual actor identity, unit,
launcher/manifest/runtime profile, canonical reader/checker/held-metadata helpers,
namespace policy and database inode/mode/owner are unchanged. Database content
was not opened or claimed unchanged. No bytecode or synthetic fixture remains;
no gate, listener, background process or maintenance hold was left active.

The initial guessed SSH hostname refused host-key verification before remote
execution. The same compiled source packet then used the documented already-pinned
route with strict host-key checking; no key was accepted or check bypassed. The
original transport refusal is retained, not a product failure or a qualification.

## Explicit operator-only boundary

The healthy backend pins the whole reader module: **do not overwrite its canonical
module, change the source pool or repeat activation for an offline detail line**.
The corrected CLI must be explicitly selected. Existing canonical `6c72` reader,
`3eab` checker, held metadata and admitted backend/default module stay unchanged.
The selected parent P1415 source files, manifest, owner/qualification records and
qualification clock are verified unchanged; other historical log files were not
re-hashed. Final publication
may update documentation/ledger metadata only; it does not rebuild or alter the
reviewed, qualified module or redate the ARM evidence. A final publication guard
refused a concurrent native-metadata change before staging. Only this patch's
comment/counter were applied to the newer metadata, preserving the published
P1417 native tag and provenance; the executable source/test/dependency bytes
remain exactly those already qualified.

No production database, recording corpus or game has been used for this change.
No default backend promotion, app/namespace probe, native binary/pin/tag, VM or
QC Build update is claimed. The ledger patch counter advances independently of
the unchanged native commit/tag. No time/RSS/performance or calibration claim.
