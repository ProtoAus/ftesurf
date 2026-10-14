# Windows actual staged-removal interruption gate

This is a **test-only external debugger**, never linked into or shipped with the
client. It adds process-interruption evidence to the separate bounded-retirement
cold matrix. Historical graders/helpers and the model remain immutable.

## Boundary and independent actors

`test_update_native_retirement_interrupt.py` verifies executable/companion PE
`.text` equality. It binds exactly one real `FS_Remove` call inside the inspected
`QKU_FSPurgeObject`/`.part.0` body, validates call displacement against the unique
real function symbol, instruction bytes, and the x64 `FS_SYSTEM=3` argument.
The helper restores the original instruction and register context; it never
replaces an API, native return, file result, policy predicate or production code.

At the pre-call boundary the helper checks the exact signed staged leaf, present
file, retained journal, and real root argument. At the post-call boundary it
requires the **actual nonzero native removal return**, OS-confirmed leaf absence,
and journal presence. It then terminates only its owned debug child with code86.
The guarded parent runner requires the exact same-thread before/after event order,
child identity and code86, natural job0 before and after cleanup, full export,
then an independent semantic receipt. Any unknown containment, export, handle or
receipt failure retains its guard and cannot authorize fixture retirement.

Two transaction orders (content first and preserved zone first), each interrupted
immediately **before** and **after** the first real successful removal, are
followed by a separately recorded fixture repair and ordinary cold restart.
The raw-byte oracle requires:
- exactly zero/one object removed at interruption; every other object unchanged;
- exact original signed-row superset at attempt2, naming every surviving candidate;
- exact partial ledger version/hash map and consent, the full signed installed
  closure, protected edits and unrelated `.part`/`.install` siblings unchanged;
- exact before-completion ledger/closure/stage bytes while deliberately detecting
  the historical outside-authority valid orphans;
- completed repaired restart at persisted attempt3, including idempotent handling
  of the already absent candidate and final journal retirement.

The acting before client must instead publish reduced authority and leave valid
resolved orphans after completion. This characterizes the previous behavior; it
is not accepted as a subject pass or used to weaken historical expectations.

## Build/run

Build the helper in a uniquely owned task root (UCRT64 tools on PATH):

```
gcc -municode -O2 -Wall -Wextra -Werror tools/native_retirement_interrupt.c -o <owned>/native_retirement_interrupt.exe
python -B -m unittest discover -s tools -p test_update_native_retirement_interrupt_unit.py -v
python -B tools/test_update_native_retirement_interrupt.py --engine <client> --symbols <client.exe.db> --helper <helper> --feed <retained-production-signed-update.json> --objects <closure-a> --objects <closure-b> --runtime-root <fresh-owned-runtime> --evidence <fresh-owned-evidence>
```

Append `--expect-before` only for the independently inspected before client.
Inputs are existing production-signed bytes; there is no signer or pin override.
Process startup uses consent0/update_autocheck0. Unlike the main cold matrix this
interruption extension does not install a signed HTTP census mirror: it makes
**no all-network-silence or mirror-GET-count claim**.

## Measured 2026-10-14 result and limits

Owned root `C:/FTESurf-worktrees/wjnative-20261014T062856Z/` retains exact command,
source/build/binary bindings, event logs, full exported states and native receipts.
- Before: clean engine base `caeb0b951000e97a9bb6e57136113d68f954959d`,
  client SHA256 `f9ba9842a5a138cfcffcd1c826488fad6dfbecbc2e3588b18a4d7cc067f514bc`.
- Corrected candidate: qkupdate.c SHA256
  `7321da290913f67c047f1cf86103203ad79327d05dbacb44fe7ca9da695ec5d3`,
  client SHA256 `b566bf46b17a2f7cb4e95599e2089ad7fabff4dc9397ac5bc982ed6210480596`.
- Each passes four order/boundary arms and four repaired ordinary restarts.
  Before03 and subject02 use the exact same corrected driver; interruption helper
  builds with `-Werror`, and sixteen binder/receipt/ledger/consent/closure/stage
  unit falsifiers pass. Earlier before02/subject01 observations remain historical:
  review found a ledger/closure oracle omission, corrected with explicit mutation
  negatives and a fresh native comparison pair, not relabelled as full acceptance.

This is process interruption, not power loss, fsync durability, hostile path swaps
or hardlink/TOCTOU coverage. It does not cover live/deferred publication-interruption,
new-apply retained-generation refusal or launcher supersession. The separate
Windows partial-read/protected byte-range-lock actor remains unexecuted after a
provider-side child failure. Neither these passes nor the corrected candidate
are a product publication/deployment/release acceptance.
