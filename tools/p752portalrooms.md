# P752 — portal rooms: the door seen through a door opens

The owner asked to "extend the portal vision", with a setting for how many rooms
you can see through portals, like Portal: two, the door you see and the door in
that door's room.

## Cause

That setting already exists, `r_portalrecursion` (default.cfg sets 2), but on
linked-portal maps the second level never opened. The engine recurses into any
portal entity in the scene, from whichever eye that level has
(`CSQC_SetupToRenderPortal`), but `FS_PortalPredraw` offered a door to the scene
only if it faced the PLAYER's eye, was within `vbsp_portal_dist` of it and in its
PVS. A door in the room behind a door is none of those, so it was never in the
scene. The cvar was also not saved, so a console change was lost on restart.

## Change

- FTESurf `cl_portal.qc`: `Portal_Offer` walks the views once per frame: the
  player's eye, then the far-side eye of each door it offers (`FS_PortalWarp`,
  forward through `FS_PortalRotate`), with PVS sampled at the exit doorway as the
  renderer samples it, up to `r_portalrecursion` levels. Only the
  `r_portalmaxviews` largest doors in front of an eye carry the walk deeper (the
  engine renders no more), at most 32 eyes. `vbsp_portal_dist` still bounds the
  doors the player sees directly.
- Engine `renderer.c`: `r_portalrecursion` is archived and its description reads
  in rooms (0 closes every portal, 1 the room behind a door, 2 that room's door
  open too).

## Evidence

- Native A/B on the P748 engine, Kitsune hub in front of `portal_hub_exit`,
  latest-main progs against P752 progs: the old progs offer `portal_hub_exit`
  only and the engine renders 1 door at depth 1; P752 also offers
  `portal_s1_exit` at view level 1, the engine renders 2, and through the hub
  door stage 1's far exit now shows stage 2's door frame (17 pixels wide at
  960x720) instead of closed. The bounded walk renders the same frames (0 px at
  5 poses) as an unbounded first cut.
- Engine half: a view budgets only doors in its own PVS. Before it, the hub door
  seen from inside stage 1 (behind walls) was rendered at depth 1 by the old build
  and took a slot; with the walk's extra offers it could have closed a visible
  door. Final build at the hub: depth 1 renders stage 1's exit only.
- Cost, `timerefresh 2 720` (a full turn, world rendering only, FBO portals):
  final build at the hub 0.39 s at recursion 1 and 1.55 s at recursion 2, against
  the old build's 0.48 and 0.59 (first cut without the PVS budget: 1.65 at 2).
  Inside stage 1, 2000 units from its exit, the first cut: 0.66 -> 0.98 s.
- Final build: the five hub frames equal the first cut's (0 px); QC 0 warnings.
  One review (QC semantics clean, eyes match the renderer's): its five findings
  are fixed (PVS budget, engine ranking metric, level and width clamps, cltime
  cache cleared by Portal_Refresh) or in BACKLOG (half-space ranking, cost).

## Limits

- The extra level costs about 1.6 ms a frame at the hub (averaged over a full
  turn, against recursion 1 in the same run); `r_portalrecursion 1` turns it off.
  A depth-2 FBO view costs several times a depth-1 one here; not profiled.
- `r_portalrecursion` is saved, so the value in ftesurf.cfg wins over a later
  default.cfg change, as for every saved setting.
- Owner live verdict PENDING (lextest.md).
