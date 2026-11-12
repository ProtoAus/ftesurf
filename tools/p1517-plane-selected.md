# P1517 — select the only possible strict alpha halfspace

## Implemented / source published

Engine feature `9aa225a8f3c19070b9b7a18fd004603a98604a1d`, tag `patch-1517`.
Only `GLBE_BlendPlaneSide`, its isolated test adapter/cases and the patch ledger
change. No quality reduction, geometry/projection change, new cache or relaxed
admission/budget. The charged work still uses original vertex counts.

P1511 already exits when a band vertex or opposing signs make the result unknown.
A strict survivor nevertheless maintained both minimum and maximum distance.
The first vertex now chooses the only halfspace that could prove separation;
remaining vertices test that side alone. Empty faces remain unknown. The exact
zero-initialized double accumulation/component order, epsilon and eye mapping
are retained, including the zero-eye result mapping.

## Verified — finite semantics and actual native work

- Both the actual P1511 beforeimage and subject match the independent frozen
  full-scanner oracle on1312 existing plus84 added finite cases, ordinary and
  fast-math builds. Added boundaries include empty faces, strict3/4/64vertices,
  both signs/eyes including zero, first/late band and opposite-side cases.
- Mixed64vertex subject visits2; strict64still visits64. Compiled frozen full
  scanner agrees on return values then intentionally fails the acted64/64
  visit-reduction control. All three subject evaluation sites are counted;
  the reference implementation is not rewritten to agree with the subject.
- Independent source/oracle review found no finite correctness must-fix.
  The small math fixture uses synthetic types, not native ABI qualification.
- Native layout was separately checked: aligned16byte XYZ vertices and actual
  mesh-prefix offsets. Optimized raw helpers and the actual linked renderer
  translation unit remove MINSD/MAXSD from this helper. The native function
  grows202->274bytes: this is not a smaller-code or fewer-static-instructions
  claim. Shared-load helper timings do not establish stable cycles or game FPS.
- One supported incremental diagnostic build/link completed with unchanged
  headers/flags and zero new warnings. Its changed native GL object consumes the
  exact reviewed source, not stale objects or a standalone-stub replacement.
- Baseline and subject each ACT in real moving Fairy replay views: positive
  admitted transparent commands, graph edges/work and moved output, with memo
  disabled for this control. Both produce nonblank1920x1200 RGB world images;
  no detected renderer/VM fatal. Their nonclient actors/VMs remain identical.

The moving trace's documented128command output cap does not invalidate its
acting metadata, but is not a complete command-list comparison. A separate
paused-camera comparison did **not** qualify: the subject reader later reported
another clock/playing state. Images/orders are not claimed equal. This is not
owner visual acceptance, an all-maps pass, nonfinite proof or measured0.1% gain.

Reproduce the finite seam from the engine checkout, with the supported UCRT64
compiler/DLL directory on PATH:

```text
python -B tools/test_gl_blend_planes.py --side-only --cc C:/msys64/ucrt64/bin/gcc.exe --output <owned-task-artifact-directory>
```

Only `--side-only` is qualified here, not the older wider memo/clipper suite.
Do not execute the assertions under `python -O`.

## Kitsune investigation — not a speculative gameplay fix

A full warm and one full diagnostic pass of the correct cached Kitsune main
replay each reached its actual last sample151.351s, beyond the old35.6second
prefix. The earlier spontaneous large game-code hitch was not reproduced.
The largest captured155.65ms interval instead coincided with the test's endpoint
`replay status`: Watch_Status prints28lines. Snapshot data before that control
on future captures; do not silently remove the actual reader coverage check.
This does not globally clear the original hitch or justify a speculative GC/QC
change. No exclusive GPU/CPU root or numerical frame gain follows from TANDEM.

## Production / rollout — pending

Clean normally stamped production Full, final-image/dependency smoke and guarded
dual-Windows client-only promotion remain pending. Diagnostic images are not
shipping payloads. The unchanged upstream native dependency received two bounded
independent source reviews; no backend/HID reader rollout is cleared by them.

No native server/plugin/VM/Pi/backend release or QC Build bump is part of this
renderer-only delivery. Owner glass/feel checks are pending in `lextest.md`.
A controlled frame-tail A/B still needs the shared rig's actual quiet window;
no isolated FPS or0.1%-low improvement is claimed here.
