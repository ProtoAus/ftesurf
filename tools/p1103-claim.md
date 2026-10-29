# P1103: native closing-clock diagnostic qualification

Claim reserved at a58b7540 after fetching both origins and checking patch
headings/untracked test claims (previous maximum 1102).

## Current status — 29 October 2026

Implemented, reviewed, pushed and **deployed native-only to both Windows installs**
at 07:21:39 UTC and **all 12 NanoPi lobbies**, verified at 09:05:36 UTC with live
version/diagnostic readback at 09:13:16 UTC. No QC/menu/config deployment, backend
generation/schema/threshold change, Build decision or release. The historical
legacy-world closure was recovered and qualified before ARM promotion; the
original incompatible-world HOLD remains retained, not relabelled.

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

## Deployment and recovered legacy-world gate

Windows: all 10 native destinations and `.prev` predecessors verified; immutable
predecessor copies retained. The fresh process guard first stopped before writes
when the game started. After it closed, the same preflight was explicitly resumed
only after rechecking all original predecessor/source hashes; no new transaction
name bypassed it. All 17 protected progs/menu/config files remained identical.
Client SHA256 `51771d77840c8db78579b02ca54d1f7cccbb0f919f27357ecbda5879ba8512ed`;
server `626b43d6264b6653974d25c4dd0230b9e30ec776baaca03c7e0e1d1717f8683e`;
HL2 `5f229e3c4ad4b2768f087864a7b8a05b51b53a5a7c509eb0e175876b7846bc06`.

The public `p492voy.rec` pin-2 HOLD was a world-profile mismatch: holding every
other Windows input fixed and substituting its qualified archived QW program
(SHA256 `df678374743a1351764d9ea6c7933eae8168c19f3a6172e77674bd8dd4246e98`)
restores PASS 4418 ticks/4418 rows under both exact predecessor and candidate.
ARM predecessor/candidate also pass that control and the documented P813 pin-7
replacement (9194 ticks/9192 rows). This is declared historical-world coverage,
NOT current-QW compatibility, pin-1 coverage or permission to ship the old QW.
The original HOLD logs remain failed; no recording was rewritten, gate weakened
or unrelated product code changed. Windows QW was restored after the falsifier.

ARM native SHA256 `4a085b778e29b4f307539af1e4408719baea9697b75b24cabd3b3e8653ebcab0`;
HL2 `2043eeb2debc79c8879c16affb7a69f71d24900f2ae771a9e75209303844c403`.
Only those two images were promoted, retaining exact predecessor/prior-prev
copies. All 12 positive status-7 empty boundaries included spectators; every
ordinary restart occurred once. All 12 new PID/birth/native hashes and actual
HL2 mapped inodes verified. 34,029 pre-existing protected files and all configs
stayed identical; six newly appearing files were preserved, not erased.

The initial transaction completed swaps/restarts, then hit a missing directory
method in its newer census helper. Its source/failure receipt remain retained;
the caller seam was corrected and read-only postflight independently verified
the original 12 new actors, without another swap/restart or verifier downgrade.
All 12 actual `version` replies match the qualified native. Two exact synthetic
early-clock REFUSE probes then act on the live installed native; the first file-
visibility failure remains retained. Source-reviewed `fs_flush` made the newly
external-created loose files visible without remount/restart/cvar change; exact
owned files were removed and the hash cache refreshed afterwards.

The current plain-API backend generation has no native dependency pins; its
manifest, launchers, systemd unit and health stayed unchanged. No coupled backend
handoff was needed or performed. Backend healthy/directory 12; AI untouched;
short sweep flock released, no maintenance gate. General held/parked replay is
still unsupported. Private fixtures, raw logs and operational checkpoints stay
private. These are documentation-only follow-ups to the unchanged source/tag.
