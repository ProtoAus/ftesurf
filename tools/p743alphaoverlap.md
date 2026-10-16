# P743 — mode2 alpha pairs ordered by their actual screen overlap

Finishes Sol's in-progress P743 (`r_blendsort 2`, Kitsune ramp/grid panes). The
owner had confirmed P742 fixed the stage3 section; stage1 saves 5/6 still flipped.

## Cause

At the logged stage1 camera all 12 world panes are admitted, then the plane
graph cycles (48 edges, 546 work, status -2) and the whole frame falls back to
centre-depth order. Pairs with no plane-side proof received a mandatory
centre-depth edge; on these long slanted ramp fans the centre orders such pairs
backwards, and one of those edges closes the cycle. The proof-only edges are
acyclic. Separately, a face wholly behind the eye stayed in the list as an
unadmitted barrier and forced status -3 when the player turned round.

## Change (engine `gl/gl_backend.c`, mode2 only)

- `GLBE_BlendOverlapOrder`: an unproved pair is intersected on screen (each face
  projected once per sort through `m_view`, clipped in homogeneous space) and
  decided by affine 1/w at the intersection vertices. Disjoint: no edge. One
  sign: that order. Mixed signs (a real crossing) or uncertainty: P742's
  baseline edge. Depths within 0.01 units tie, so seams give no sign.
- Opposite strict plane proofs cannot share a view ray and add no edge.
- A cycle or barrier crossing retries with every edge overlap-confirmed (pass
  1), then with P742's own graph (pass 2): never a fallback where P742 sorted.
  Overlap work has its own 65536 budget; once spent, pairs get P742's edges.
- `GLBE_BlendWorldRasterEmptyNear` drops a face whose every vertex is at least
  0.125 behind the eye: w < 0 everywhere, so no cull state can draw it.
- `ALPHATRACE result` now ends `pass=N`. No map, material or surface exemptions.
  Modes 0/1 and default1 use P742's graph unchanged.

## Evidence

- Actual-C suites: `tools/test_gl_blend_faces.py` (normal, HEXEN2, fast-math,
  both; 35 acting mutants) and `tools/test_gl_blend_planes.py` pass.
- Geometry sweep, graded by a separate Python reference against clipped screen
  overlap (a pane pair overlapping more than one 960x720 pixel must draw farther
  first), 360 yaws x 15 pitches (-30..40) at each saved eye, the same source with
  P743 compiled out as the control:

  | Scene (frozen fixture) | views with a nearer pane drawn first, P742 | P743 |
  | --- | --- | --- |
  | stage1, save 6 eye, 28 faces | 978 / 5400 (1358 cycles) | 0 / 5400 (0 fallbacks) |
  | stage3, save 5 eye, 20 faces | 475 / 5400 | 0 / 5400 |

  Geometry, not GPU pixels.
- Independent review, three rounds (lens: predicate and control flow). Round 1
  found budget abandonment on 40-face scenes, signed hinge-seam noise and new
  cycles; round 2 found the sliver cut dropping real thin overlaps and -3 not
  retried. All fixed, each with an acting control. In the reviewer's own ramp
  and wall scenes (16-52 faces, 400 views each) P742 was never better.
  Round 3 found nothing new. Its sweeps, wrong ray samples P742 -> P743: ramps
  of 16/19/29/38 faces 1524/1456/941/615 -> 0/0/0/125 (the 125 are the one view
  that falls back to P742's graph, same samples); walls of 28/40/52 faces
  772/1461/16768 -> 211/619/5908, -3 aborts 23/22/12 -> 0. Hinge seams with the
  tie alone: 2 signed of ~9250 pairs, sub-pixel and only able to cost a fallback.
- Native smoke, one boot per exe in the mapvisual subject basedir, same cfg,
  `r_blendtrace` at each pose (round-1 build against the installed P742 exe):

  | Pose | P742 installed exe | P743 | pixels differing (lower half) |
  | --- | --- | --- | --- |
  | save 6 trace camera | status -2, 48 edges, 546 work (the owner's failure) | status 1, 44 edges, moved 8 | 32334 |
  | save 6, yaw 60 | status -2 | status 1 | 30925 |
  | save 6 / yaw 105 / yaw 120 | status 1 | status 1 | 4 / 0 / 0 |
  | save 6 turned round | status 1 | status 1, one behind-eye face skipped, same order | 165 (thin-line edges) |
  | save 5 / save 4 (stage3) | status 1 | status 1, same draw order | camera drift / 0 |

  The final build (b9c66c501) gives the same status, edges and moves at every
  pose with about half the work, all pass 0; its frames match the round-1
  build at the stable-camera poses (0 px at save 6 trace, yaw 60, save 4).
  Logs and screenshots: `C:\FTESurf-worktrees\mapvisual-01a13061\subject\ftesurf\{logs,screenshots}\p743smoke_*`.

## Build and delivery

- Engine `b9c66c50114d9a21f39087f6409d07dfbb295e77`, tag `patch-743`, on public
  main (fast-forward over 75dc91c4c). Commits 3fc50f48d, c281a6d10 (review
  round 1), b9c66c501 (round 2).
- Stamp `git-7341-patch-743-0-gb9c66c501`. Full build with `-NoDeploy` in the
  mapvisual task root: the same 77 compiler warning lines as P742's build
  (normalised set identical), 0 new; the shared dependency cache (5890 files)
  unchanged.
- Client-only drop at 2026-10-16T23:09:51Z, Sol's `deploy.ps1 -Patch 743
  -ClientsOnly` (exclusive locks, backup, hash verify, rollback); no header or
  plugin change since P737, so the installed DLLs keep their ABI. No game
  process was running or stopped.

  | File | SHA-256 |
  | --- | --- |
  | `C:\FTESurf\ftesurf64.exe`, `C:\FTEQuake\fteqw64.exe` | `43918e2e7428e73b728afd03d73b2ef2980f1c01211488796816d4a6a32a95ac` |
  | both `.prev` (P742) | `37eecf1e5b3e5fb7dfb5bd8d2b7e8f7d0bb6f16f1403ed956e4741361c47f0fb` |

  DLLs, the dedicated server, progs, configs, saves, the Pi and releases are
  untouched. Receipt: `delivery-p743/deployment.json` under the task root.

## Limits

- Not order-independent transparency: panes that truly cross on screen keep the
  baseline order, and a frame whose proved constraints still cycle uses P742's.
- A pane seen exactly edge-on (eye within 0.25 of its plane) is not admitted and
  stays a barrier; pass 1 resolved all 6 such fixture views.
- P742's bounds and plane proofs still use `r_origin`/`vright`, which a portal
  pass rebuilds without screen roll or eye offsets (stereo/VR); the new overlap
  test uses `m_view`. Rare; BACKLOG.
- Dynamic/unsupported commands remain barriers as before.
- Owner live verdict PENDING (lextest.md).
