# P1529 — bounded landing gravity-use observation

## Status and scope

Implemented and source-qualified; **independent frozen-source review and deployment
remain pending**. Native commit `2274050a985f82a0e72e7fada681dae034b3972e`,
tag `patch-1529`. Neither Windows install nor any lobby/backend was deployed by
this qualification. QC Build89, recording formats, readers, ranking rules and
thresholds are unchanged. This is not a complete retained-state bank, calibration
or anti-cheat sign-off.

## Bounded correction

The clear-air observer previously discarded a confirmed gravity-use signal when
final categorization landed only the non-default-gravity path. Four native
controls establish an actual body difference and an independently airborne default
endpoint, but the untouched runtime misses their use signals.

Retain the existing command-local signal only when the default-gravity endpoint
independently passes the existing clear-air/ground probes and an acted vertical
body difference survives. This includes the bounded water-jump path. Possession or
admission of a retained setting is not use. Shared ordinary landings, obstructed
paths and unavailable comparisons do not become positive witnesses. No movement,
new evidence field or policy is introduced.

## Verification

- Final clean, tagged Windows source: supported
  `src/build.ps1 -Engine -Full -NoDeploy -Jobs 8 -FteRoot <isolated-engine>`
  succeeds. All three QC VMs: **zero warnings**. Native client/server and five
  plugin build: **74 inherited warnings, zero new**, compared by warning-message
  multiset with the qualified control. No warning in `pm_source.c`.
- Final version-stamped Windows dedicated output (`git-8719-patch-1529-0-g2274050a9`):
  actual map-free `pm_selftest`, explicit fresh native logging, **1773 checks,
  zero failures**. The pre-publication Windows subject also passes1773/0.
- ARM64 normal `make -C engine sv-rel FTE_TARGET=linux CC=gcc BITS=arm64 -j3`:
  actual native **1773 checks, zero failures**. All768 canonical source files were
  verified before compilation. Runtime source equals the final native commit;
  the only overlay over its parent is `pm_source.c`. This pre-publication binary
  is source-qualified, not a final version-stamped deployment image.
- The final fixture adds **83 assertions**. With the untouched runtime it fails
  exactly **four acted landing-use assertions**. Observer on/off agrees on the
  complete `playermove` and `movevars` bytes. Shared-landing, expiration,
  obstruction and command-reset controls actually act; silence is not a pass.
- `python tools/test_reccheck.py`: **949 checks, zero failures**.
- Current captured corpus: **568REC +183VIEW**, all751 input hashes and every
  per-file report identical to the qualified control. The supported paired sweep
  still reports **356 existing faults**; no increase. Existing faults are not
  clean evidence, new findings or player verdicts.
- The same owned, frozen1399-file Windows SDK is unchanged after the full build.
  No canonical build objects, live fixtures or player data were borrowed.
- clangd consumes the regenerated database: no source errors, one inherited
  unused-header diagnostic. This is not a substitute for the actual builds.

## Preserved failed controls and limits

The first ARM source export omitted the required canonical plugins source tree;
its failed compiler log/result are retained. Completing that same source closure
fixes the missing-header seam, not product behavior. The completed ARM build has
16 inherited warnings across the initial and resumed compilation, none in PM.
An observer initially searched for `PASS` rather than the native literal `ok`
labels. Its failed receipt is retained; correction rereads the same completed
1773-check log without rebuilding or repeating the test. Neither failure was
promoted as a successful transaction.

The normal build regenerates a header comment containing the generator path;
its sole generated diff is retained privately and restored to the exact Git
comment after qualification. There is no generated code change. A pre-existing
release-note point without its heading remains an independent release parser
blocker; no release or unrelated repair was attempted.

Source publication is not independent review or deployment. Rollout awaits the
required actual source-scoped reviews, then clean version-stamped images and the
normal guarded dual-Windows/native fleet procedure with previous binaries,
recorder/resume preservation, actor/dependency checks, destination hashes and UTC
provenance. Hardware, genuine labelled data, calibration, complete supported-world
coverage and policy decisions retain their separate acceptance gates. The deferred
native/compiler/filewriter audit stays deferred. No maintenance gate was acquired
or left held during this offline qualification.
