# P748 — mode2 sorts translucent panes seen through portals and in the 3D sky

The owner confirmed P743 fixed the stage-1 views, then found two more flips on
surf_kitsune: save 8 (the hub, looking through `portal_hub_exit`: stage 1's floor
grid) flips against save 9 (0.04 degrees lower), and save 11 (stage 1's start
room: the skybox grid behind the left wall) flips against save 10 (0.04 degrees
left). Screenshots `surf_kitsune_165..168`.

## Cause

`GLBE_SubmitBlendedFaces` ran the raster-empty cull and the plane sort only when
`r_refdef.recurse == 0`. Every recursive view (portals, the skyroom, FBO
captures) drew its translucent panes in P736's centre-depth order, which swaps
overlapping panes with sub-degree view changes. A trace-only control build shows
it at the owner's poses: each portal or skyroom view gathers 30-136 commands,
admits 0 and returns status 0, and the portal view's draw order differs between
saves 8 and 9.

## Change (engine `gl/gl_backend.c`, mode2 only)

- Recursive views gather, cull and sort exactly as the main view does. Their
  `r_origin`/`vpn`/`vright`/`vup` and `m_view` come from one basis
  (`GLR_DrawPortal`, `R_DrawSkyroom`); the portal oblique near clip rewrites only
  the projection z row, which the eligibility check already allowed.
- `GLBE_BlendViewEyeAgrees` gates the plane sort: it solves `m_view` for GL's eye
  and requires it within 1/32 unit of `r_origin` on each axis. Plane-side proofs
  read only that eye, and ray-disjoint screen bounds hold in any image frame, so
  roll, mirrors and a spinning skyroom still sort; a stereo/VR eye offset falls
  back to the baseline.
- `r_blendtrace` traces every pass of the next frame drawn (begin lines carry
  `recurse=N` and `eye=`, result lines end `recurse=N`); a later frame's first
  pass disarms it. Modes 0/1 and default1 are unchanged.

## Evidence

- Actual-C suites `tools/test_gl_blend_faces.py` (normal, HEXEN2, fast-math, both;
  48 acting mutants) and `tools/test_gl_blend_planes.py` pass. New oracles: a
  portal view of the stage-1 fixture culls and orders exactly as the main view
  (39 poses); a 2-degree roll, a mirror and a 2-degree spin of GL's basis still
  sort; a 1-unit eye offset keeps the baseline; per-axis tolerance and a singular
  `m_view`; the trace stays armed through every pass of a frame, recursive ones
  included, and disarms on a later frame.
- Native A/B, one boot per exe in the mapvisual subject basedir, walking (portals
  draw nothing in noclip), the owner's portal settings (recursion 2, max views 2,
  FBO portals), 960x720:

  | Pose | trace-only control | P748 |
  | --- | --- | --- |
  | save 8, portal view | status 0, 136 gathered, 0 admitted; order differs from save 9 | status 1, 12 admitted, same order as save 9 |
  | save 10/11, skyroom | status 0, 30 gathered, 0 admitted | status 1, 8 admitted |
  | main views, all poses | status/edges/moves | identical |

  Frames: save 9 and save 10 are pixel-identical between builds (the owner's
  good views); save 8 differs in 7,400 pixels, all in the doorway, where the
  control draws thin grid lines over the bright band (the owner's broken shot)
  and P748 draws the save-9 layering; save 11 vs save 10 differ by 120,000 pixels
  in the control and 30,000 (0.04-degree camera motion) with P748. P743's
  stage-1 poses are pixel-identical.
- Final build (stamp `git-7358-patch-756-0-g99e69da32`, with P752's PVS budget
  and P754): every view status 1, frames within 1 px of the verified build at
  saves 8-11 and P743's trace pose (save 6: 73 px, the same against the control).
- Cost, `timerefresh 2 720` (a full turn, same camera path, two boots per build):
  +0.04 ms a frame at the hub, +0.07 at stage 1's start, +0.12 at save 6 (the
  skyroom sorts 38 panes there).
- Review, lens predicate/control flow of recursive views. Round 1: no crash,
  leak or dropped face; the first guard compared axes too and turned the sort off
  where it is correct (mirrors, a spun skyroom, the main view with
  `gl_screenangle` after a portal), and the trace stuck armed under
  `r_portalonly`. Round 2: no wrong-order path; a differential of the actual sort
  against ray-cast truth found 0 pairs worse than the baseline under roll, mirror
  and spin (5-24 per variant with the guard removed and the eye moved); test
  gaps and a frame-counter sentinel, all closed.

## Delivery

- Engine `469a69e46` on public main, tags `patch-748`, `patch-752`, `patch-756`
  (code `99e69da32`, the built commit). Full build, the same 74 warning lines as
  P743's, 0 new; shared dependency cache unchanged (`b35addf4...`).
- Both Windows installs at 2026-10-17T07:05:26Z by the task root's `deploy.ps1
  -Patch 756` (exclusive locks, backup, hash verify, rollback copies `.prev`);
  receipt `delivery-p756/deployment.json`. No game process was stopped.

| File | before -> after (SHA-256 prefix) |
| --- | --- |
| `C:\FTESurf\ftesurf64.exe`, `C:\FTEQuake\fteqw64.exe` | `fb3c90bf` (P754) -> `f669bc11` |
| `C:\FTEQuake\fteqwsv64.exe` | `49bd6081` -> `0cf5d306` |
| plugins (hl2, ui_imgui, cod, box3d, ode), both installs | rebuilt from the same tree |

- Lobbies: the Pi native is P679, so P748 is local-only there (BACKLOG).

## Limits

- Panes that truly cross on screen keep the baseline order (not OIT), as in P743.
- In a spinning skyroom the baseline key still runs along the unspun `vpn`
  (BACKLOG); the sort's proofs are unaffected.
- Mode 1 (default `r_blendsort 1`) has no eye guard and stays root-only.
- Owner live verdict PENDING (lextest.md).
