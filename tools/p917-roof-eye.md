# P917 — render-consistent ceiling eye limit

Owner confirmed P916 head lowering and water exit on 2026-10-22; tiny roof-view
jitter at both 50 and 1000+ FPS remained. Manual acceptance lives in lextest.md.
Engine commit 91cc20489e4f98f30017607e3b110dd98b37214a, annotated patch-917.

## Prediction/falsifier (registered in task WORKLIST before editing)

P916 summed a clipped offset sampled at the mover endpoint with feet interpolated
to a different time. Under a fixed roof, `renderfeet + movereye` therefore varies
by the feet delta. Keep the roof's absolute eye limit fixed, then reconstruct
the offset after final render/stair interpolation. No smoothing lag, extra
trace, physical movement, recorded state or mover-version change.

## Implemented / verified

- Capture unclipped current posture and clipped world eye limit only for a
  predicting Source v11 normal player whose eye really clipped. After
  CL_CalcCrouch, reconstruct the offset using rendered feet + stair offset.
  Legacy categorization overwrites pmove.origin, so do not derive the limit there.
- Ordinary unclipped views, old movers, death and noclip retain the old path.
- Full existing build: `src/build.ps1 -Engine -Full -NoDeploy -Jobs 8 -FteRoot
  C:/FTESurf-worktrees/source-polish-20261022T0746Z/engine`.
  Client, dedicated and all shipped plugins pass; zero new warnings vs the
  inspected P916 native control. No peer dirty source used.
- The real native pm_selftest passes all prior tests, the 36 P916 checks and 21
  new roof/render checks. A real hull trace establishes the ceiling; old formula
  demonstrably drifts 2.5 units at a chosen render offset, while 16 distinct
  render positions retain one absolute eye. Includes below-contact ordinary
  height, stair offset and nonnegative discontinuity bounds.
- These are mathematical/native checks, not measured 50/1000-FPS camera captures
  or human feel confirmation. Owner's small roof-jump check remains pending.

Source committed/pushed; clean stamped client deployment/readback will be recorded
with the next client artifact set. No Pi server restart is needed for this
render-only change. Remaining requested features remain tracked in task WORKLIST.
