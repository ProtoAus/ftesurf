# P935 shared-target delivery handoff — prepared, NOT deployed

## Immutable reviewed/integrated sources

- Native3afdd0fa313394854c56f83c1d6a3c6a597f1c67, public tagpatch-935.
  This includes the published P937 raw-buffer EOF ownership fix AND P935's
  buffered cold-save loader, viewmodel depth/eye sampling and v44/v48 events.
  The earlier frozen patch-937 native5fd6c6790 DOES NOT include P935; do not
  overwrite this combined native with that older artifact just because937>935.
  P935 was reserved before936/937; mainline ENGINE highest remains937.
- Windows/mainline QCdb701488d9fc0b288553615f85e3105197ca7fe6 contains P935
  and published P936/P937. P936's 64px frontend is STILL BACKEND-FIRST.
- REC13 compatibilityb2f55f7bd4c440fed7a44f4dc765ddb7ab1310f4, public branch
  `deploy/source-p935-rec13-20261022`, adds only reviewed P935 hunks to actual
  current P932/P933 predecessor1fdb668a. It preserves writer13, 32px portraits
  and current native servers; no held producer/native13/14/15 promotion.
  See p935-rec13-compatible.md ON THAT BRANCH. Its menu is NOT for Windows.

The mainline and compatible source are independently clean-built0/0/0 warnings.
P935 native/audio/weapon/server code blobs match the reviewed snapshots; the
only merged frame/key hooks are the published disjoint P937 observers. Both
independent focused follow-ups closed P1/P2 with no residual findings. Exact
acceptance/failed diagnostics and limits: p935-css-feel.md. No human listening,
visual feel, universal latency or new movement/producer qualification claim.

## Prepared local inputs (one owned task root)

Root `C:/FTESurf-worktrees/source-polish-20261022T0746Z`:
- Native7 shipping files: `engine/engine/release/` (combined3af source above).
- Mainline DAT/LNO: `qc/rig/build-nodeploy-d04890a6e95f4b5f8804e98c1d40f499/`.
- REC13 progs: `qc-pi/rig/build-nodeploy-b6fceb62183f4dd5af9f26d67c500156/`.
- `artifacts/p935-prepared-inputs.json`: source SHAs, sizes/SHA256s for the13
  Windows inputs (26 destinations) and2 compatible Pi DATs. No volatile gate,
  PID or epoch evidence is mixed with immutable artifacts. Verify before reuse.
- Existing guarded `artifacts/deploy-windows.ps1 -Patch 935 -EngineSource <above>
  -Progs <mainline output>` handles both installs, live process/predecessor
  guards, staged hashes, owned rollback, .prev/backups and protected configs.
  DO NOT INVOKE before P936 backend readiness and ONE shared swap owner.
- Fleet uses standard build.ps1 -Pi from the committed compatible source with
  QuakeDir pointing at its OWN tree/sink, never canonical Windows installs.
  It ships qwprogs/csprogs only, retains .prev and refuses occupied/unknown fleet.
  No -PiForce, disconnect approval, native replacement or consent activation.

## Coordination and remaining acceptance

Another workstream is preparing one combined P936/P937 backend/progs rollout.
The operator was asked which workstream owns the shared Windows/lobby swap;
no swap or maintenance gate is active here while that decision is pending.
Do not race stale frozen artifacts. Prefer one combined delivery: integrate
P935's published REC13 branch into the other compatible P936/P937 candidate,
then use native3af (or a later inspected descendant containing ALL these fixes).
The standalone b2f compatible progs are NOT a license to overwrite a later
combined cohort after it has advanced beyond the observed P933 predecessor.

At the actual boundary refresh exact predecessor/native hashes, all active
lobby rows/player counts and destination processes. Qualify/promote the P936
compatible backend FIRST, then coordinated dual-Windows and REC13 fleet progs;
verify every destination hash and a fresh live acted client. Record UTC and
preserved configs/player data. Do not ship mainline writer14 to the older fleet.
Source publication, reviews and prepared binaries are progress, not deployment.
Human FOV/lighting/sound balance checks remain in lextest.md after delivery.
No release, Build bump or NanoPi-native promotion is requested by this handoff.
