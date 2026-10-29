# P1103: native closing-clock diagnostic qualification

Claim reserved at a58b7540 after fetching both origins and checking patch
headings/untracked test claims (previous maximum 1102).

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
- Recording reader: `python tools/test_reccheck.py`, 945 checks, zero failures.
  Same-byte corpus snapshots retain their per-file reader fault lists.
- Baseline/candidate incremental dedicated compilations: no warnings. LSP reports
  only existing warnings outside the edited seam. No QC source changes.

## Build and deployment limitation

The normal `src/build.ps1 -Engine -Full -NoDeploy -Jobs 8 -FteRoot <owned-engine>`
entrypoint was attempted first. The historical static dependency cache is empty;
using system dependencies resolves FreeType but the client then lacks Opus/Speex
headers. Both failures are retained. The supported dedicated `make sv-rel
FTE_TARGET=win64` target builds and runs successfully; this is not a full client
or plugin qualification. No unrelated source was changed to silence warnings or
remove audio features.

Source is pushed and the pin is updated, but **nothing from this patch is deployed**
to either Windows install, the lobbies or the backend. No Linux/release or general
held/parked replay claim. Required next delivery step: restore usable build
prerequisites, qualify the full build, then deploy the exact inspected artifacts
through the documented platform/fleet procedure. Private fixtures and raw logs
remain private.
