# P1103: native closing-clock diagnostic qualification

Claim reserved at a58b7540 after fetching both origins and checking patch
headings/untracked test claims (previous maximum 1102).

## Current status — 29 October 2026

Implemented, reviewed, pushed and **deployed native-only to both Windows installs**
at 07:21:39 UTC. No QC/menu/config/player-data deployment or Build/release change.
ARM dedicated/HL2 build, all 58 clock controls and all 60 full-fixture physics rows
pass; **ARM lobby/backend promotion remains held at the legacy compatibility gate**.

## Implemented and published

Engine `85b1d383896b6ef205c9665f983422fdd093de01`, tag `patch-1103`.
The native verifier now distinguishes exact writer-emitted unsupported closing
modes from malformed/incomplete viewing-clock declarations. Parsed physical-clock
refusals retain their reason instead of being hidden by the closing equation.
Acceptance, timing arithmetic and unsupported held/parked replay remain unchanged.

## Verified

- Three independent source/contract reviews. The test reviewer caught missing
  assertions and non-acting count controls; those findings were fixed and closed.
- Exact clean base `105901357` and candidate dedicated Windows builds: 58
  identical-input pairs with unchanged map/plugin/progs/config bytes. Zero
  verdict changes, four PASS references retain 45 ticks/45 rows, 30 diagnostic
  changes. Matching-count missing/duplicate clocks and mixed-mode ordering act;
  malformed, positive frozen/viewing and zero/positive parked clocks still refuse.
- Exact committed/tagged source rebuilt with the normal native revision/date
  arguments: all 58 native cases pass again.
- Recording reader: initial source 945 checks/zero failures; after upstream reader
  additions, commit `0e420a5e` passes 949 checks/zero failures. All 504 same-byte recording /
  paired-sidecar inputs retain their fault counts (zero increases).
- Baseline/candidate incremental dedicated compilations: no warnings. LSP reports
  only existing warnings outside the edited seam. No QC source changes by P1103.
- Full matching Windows engine/HL2 pair: all 58 clock cases pass. ARM dedicated /
  HL2 pair: all 58 match Windows exactly, normal owned-process exit.
- Existing full-content platform gate: all 60 named rows on the five prescribed
  maps match Windows/ARM, including acting prop and wrapped-hull branches. The
  first ARM arm used the minimal clock-smoke manifest/config subset and mismatched
  10 mover rows; it stays excluded. Matching the Windows full manifest/config
  closure restores exact parity, without weakening the comparator or attributing
  the old mismatch to a product defect or one isolated input.
- Actual installed Windows server image and loaded HL2 DLL paths verified; all
  58 native cases pass from those exact installed paths after deployment.

## Resolved build prerequisites

The normal `src/build.ps1 -Engine -Full -NoDeploy -Jobs 8 -FteRoot <owned-engine>`
first hit an empty historical static cache, then missing system audio headers.
Both failures remain retained. The documented `make -j1 makelibs FTE_TARGET=win64`
with existing exact-version archives, entirely under the owned worktree, repairs
those prerequisites; the normal full entrypoint then passes. No shared toolchain
or unrelated product source was changed. The generated shader header's only
change was an absolute-path banner; it was verified and restored to the inspected
source before deployment. Stamps were read back, not inferred from a make command.

ARM initially failed real ZIP metadata finalization because `zip` is absent. A
vendor package was downloaded/extracted only under the owned scratch root; the
measured partial plugin was removed and the real recipe rerun successfully. No
fake-success ZIP shim and no system package installation. The final artifact is
qualified, not the earlier partial shared object.

## Deployment and remaining gate

Windows: all 10 native destinations and `.prev` predecessors verified; immutable
predecessor copies retained. The fresh process guard first stopped before writes
when the game started. After it closed, the same preflight was explicitly resumed
only after rechecking all original predecessor/source hashes; no new transaction
name bypassed it. All 17 protected progs/menu/config files remained identical.
Client SHA256 `51771d77840c8db78579b02ca54d1f7cccbb0f919f27357ecbda5879ba8512ed`;
server `626b43d6264b6653974d25c4dd0230b9e30ec776baaca03c7e0e1d1717f8683e`;
HL2 `5f229e3c4ad4b2768f087864a7b8a05b51b53a5a7c509eb0e175876b7846bc06`.

ARM is **built/tested, not deployed**. The older public `p492voy.rec` compatibility
fixture currently HOLDs on physents under both the exact installed predecessor
bundle and P1103 with the same fixture. It is not a passing promotion control in
that state. Preserve the failure and recover a qualified compatible fixture /
acting legacy PASS before any native lobby/backend promotion; do not lower the
gate or repair unrelated code just to pass. No backend generation, schema,
threshold, release or general held/parked replay change is claimed. Private
fixtures, raw logs and the operational checkpoint remain private.
