# P1486 — guarded identity-counter publication

## Existing-value integrity, not a new detector

The five journal identity cvars were published before P1485's ordinary Frame
exclusion. Their seven unsigned source scalars can be updated by the admitted
physics worker's CheckIdentity, so even an empty main input drain could read them
without exclusion. Putting the whole setter inside that lock would instead
carry ownership into callback-capable code.

P1486 calls Ready before **each** desired expression. A small by-value helper
preserves the old int comparison and unsigned-to-float setter conversion, releases
only the token it owns, then calls the entire setter with its captured value.
The next expression rechecks current state; it does not use a frozen five-value
tuple across callbacks. Existing numeric precision/range behavior is not changed.

The complete never-measured branch retains `-1`, ordering and inequality checks.
Ready returning false after Drop does **not** suppress the last capture's retained
measurements: no buffer is distinct from never measured. Begin remains the reset
point. Unchanged mirrors reuse their token into Frame/relative work. Active empty
publication now costs one bounded exclusion group, not zero; inactive retained and
worker-disabled publication add no OS mutex acquisition. Changed setters split
bounded groups per drain, not a real lock per relative event. Actual callback
ownership and the inherited off-main editor route retain P1485's qualifications.

No new captured field, capture/consent/grammar, API-table/VM layout, detector,
threshold, ranking, enforcement or QC Build change. Individual reads/sums are
protected; atomicity of all five cvars across a callback is not promised.

## Acting source control

The existing `tools/test_input_journal_append.py` now also compiles the complete,
unchanged actual CheckIdentity body before actual View. Two small host additions
supply pitch bounds and r_xflip; shared fixture declarations now match all seven
real unsigned counter types. Identity is no longer a no-op adapter in this test.
Backend diagnostics and Cvar/game callback dependencies remain explicit hosts.

- Published P1485 source `8131f3a4f` control: **982 checks / 42 failures**.
  Thirty-eight failures are repeated ownership assertions, not cheat cases.
- P1486 subject: **971 checks / zero failures**. All three previously existing
  worker/drain/paste arms pass in both versions.
- The primary actual OS worker/controller is joined after its actual View has
  advanced governed/ghost/bad counters and emitted a View row. The unsafe control
  is stopped before its unprotected load, not allowed to manufacture C data-race
  output. The complete writer action succeeds in both accepted executions.
- Actual violation and skip writer branches also act. Seven unsigned getter
  checkpoints verify that product values are loaded before releasing for setters.
- The Cvar host updates its value before modeled callbacks. Cases cover replacement
  Begin, Drop with retained values, next-field freshness, deliberately retained
  false ownership, unknown-branch callbacks, unchanged active-empty publication,
  inactive retained values and disabled workers. They do not run Cvar_SetCore.
- Pure-relative budget cases normalize unchanged fake mirrors; changed-setter
  cases are explicit. This distinguishes relative grouping from legitimate cvar
  callback splits rather than hiding their extra acquisitions.
- Initial subject **968/4** and control **982/44** are retained failed evidence.
  A synthetic prior angle left by earlier cases made the actual writer take its
  quiet return. Only that arm's previous-angle precondition was corrected; no
  product identity or quiet-return logic changed. Those initial runs are not the
  accepted acting control.
- The same three diagnostics remain visible in the exact frozen, unchanged
  dispatch body; new helper/journal/host code stays `-Wall -Wextra -Werror`.
  Typed dependency regressions: lifecycle **18 / zero**, actual-crypto close
  **136 / zero**, with its five separate existing crypto warnings unchanged.
- Independent frozen-diff review: no issues; build/promotion gates not waived.

This is source correctness with actual OS threads/mutexes, not measured native
latency, physical input, Cvar_SetCore, gameplay or detector calibration. Native
backend/ring, arbitrary foreign producers, broader lifecycle/platform affinity,
and cross-capture synthetic influence remain unqualified.

## Clean build and linked image

Clean source `b5c841c0164ebd21ebf0ba8bd3a69b46790ab92e`, tag `patch-1486`, includes
all qualified P1485 and published P1477/P1481/P1482 plus P1479/P1480/P1484.

An initial standard incremental build succeeded but its required actual staged
`--version` still reported P1485. It was rejected **before deployment**. The changed
input object had rebuilt, but the unchanged version-holding object still carried
old command-line revision/tag macros. Silent make/QC success is not native-source
provenance. The supported standard `-Engine -Full -NoDeploy -FteRoot <owned engine>
-Jobs 8` rebuilt from the same clean commit; the rejected payload was not used.

Qualified Full build: client, dedicated server, five default plugins, three QC
programs. Native **74 existing warnings**, exact normalized diagnostic multiset of
qualified P1485 Full, **zero new**, compiler errors zero. QC three zero-warning
programs. Seven full outputs were frozen, and actual staged version exited zero
with `FTE git-8664-patch-1486-0-gb5c841c01`. The explicit owned-engine clangd database
was refreshed; the same six unrelated input warnings remained.

Reader regression: **949 / zero**. Reader blob and all **568** corpus input hashes
and membership were rechecked unchanged. The completed **356 pre-existing fault**
baseline is reused, not called a clean corpus or a fresh whole-corpus measurement.

## Installed 10 Nov 2026, 22:35:15Z

The existing Deploy function promoted only the two Windows client EXEs, with
exact full-build candidate and qualified predecessor guards plus idle-actor checks.

- `C:\FTESurf\ftesurf64.exe` and `C:\FTEQuake\fteqw64.exe`:
  `5abafcdb1e04a8f1a986113cb5bd09e08117f33ece21cdb5bf9f2efdd60d1901`.
- Both `.prev` files retain qualified P1485
  `76da219f43bbd4131eab96998df4678f74370f5ea8ed2d4c67a260ec16cd7d18`;
  original preimages and previous `.prev` images were archived separately.
- All **20** protected server/plugin/VM/config membership/hash observations stayed
  exact. No process was killed; no player data, progs, fleet/backend or Root action.
- Actual **both installed** version processes exited zero with the same clean
  `git-8664-patch-1486-0-gb5c841c01` stamp.

Linked version/hash proves image/startup identity, not live recording acceptance.
Normal-play human checks remain pending in `lextest.md`; the separate genuine
parked-run/explicit UI prerequisite is not replaced by these controls.
