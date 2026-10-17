# P756 — walking through a Kitsune portal no longer sticks

The owner: walking through a surf_kitsune portal sticks the player in the
doorway; jumping through works, and tapping duck frees a stuck player.

## Cause (measured)

A per-tick diagnostic build (mover prints, never shipped) on the hub door shows a
grounded walker crossing on the hull CENTRE plane (the mover-4 design) and landing
3.4 units past the exit plane with half the hull still inside the wall behind the
exit door. Every trace then starts in solid, and `PM_PortalCSG`'s linked branch
returns the six window planes' best fraction. Its bottom plane is offset to the
box centre, so it lies 31 units under the sill: the 2-unit ground probe passed
through the floor (classed airborne), gravity's move ended 0.18 inside the real
floor, `PMSrc_TryPlayerMove`'s validity check refused it and cleared the
velocity, every tick. A jump or a duck's airborne lift leaves the window before
landing. The reverse door (stage 1 back to the hub) never crossed at all.

A first hypothesis, from reading the code, blamed the 1/8-unit landing snap for
putting the feet exactly on the sill. Measured: with an exact landing (feet
816.031) the walker still stopped 3.9 units past the plane.

## Change (engine, mover 5)

- `PMSRC_VERSION` 5. Under mover 5, `PM_PortalCSG` adds a seventh sweep plane for
  a linked door: the player box's lowest corner against the opening's own bottom
  edge (Patch 216's start-only gate, applied to the sweep). A carved trace stops
  there, so the sill is ground and a fall stops on it; a walk out is still carved.
- Under mover 5 a linked landing keeps its exact position instead of the 1/8
  snap (`PM_PortalTransform`, `PM_PlayerTracePortals`), so settled feet arrive
  1/32 above the far floor rather than in contact with it.
- Movers 1-4 are unchanged, so recordings pinned to them replay as before;
  `SV_PMSrcVer` accepts pin 5 and an older verifier refuses it.

## Evidence

- FTESurf `tools/test_portal_collision.py` (actual `PM_PortalCSG`): 21 checks;
  under mover 5 the sill is ground, a walk out is carved, a fall stops on it;
  under mover 4 the probe still passes through; a control without the plane fails
  `sill_ground_ok`. `tools/test_portal_landing.py` (actual `PM_PortalTransform`,
  `PM_PlayerTracePortals`, `SV_PMSrcVer`): mover 5 lands at 816.03125, mover 4 at
  816.0, pin 5 accepted, 6 refused; snap controls fail.
- Native arm (listen server, latest-main progs, walking from settled on the
  floor, eye probed by `r_blendtrace`):

  | Arm | mover 4 | mover 5, exact landing only | mover 5 |
  | --- | --- | --- | --- |
  | walk hub -> stage 1 | stuck 4.4 past the exit | stuck 3.9 past | 232 units past |
  | walk stage 1 -> hub | never crosses | never crosses | crosses |
  | jump through | 295 past | | 290 past |
  | walk, duck tap | 148 past | | 325 past |

- Timeline (eye every 300 ms through each door, settled walk):

  | Build | hub -> stage 1 | stage 1 -> hub |
  | --- | --- | --- |
  | mover 4 | crosses, then frozen 3 units past the exit | frozen 7 units short of the door |
  | mover 5, final (`git-7358-patch-756-0-g99e69da32`) | crosses at an unbroken ~225 u/s | crosses at an unbroken ~215 u/s |

- Review, three lenses. Cheater: no gain for an unearned run (the plane can only
  stop a move, never start a crossing; players cannot choose the mover). Evidence:
  movers 1-4 replay unchanged; two commits both pinning 5 were squashed into one;
  an old verifier REFUSEs pin 5, so the Pi swaps the binary (the sweeper's) before
  restarting lobbies and never rolls it back below 756. Flow: the walker is ground
  and walks out; tilted doors now keep mover 4's sweep (the plane would have made
  a pitched door's edge a ramp); the rest is in BACKLOG.

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

- Lobbies: the Pi native is P679 (mover 3); mover 5 waits for a native fleet
  catch-up, the owner's call (BACKLOG).

## Limits

- Only upright doors get the sill; door rectangles that reach below the floor
  still stall a walker under both movers (BACKLOG).

- Lobbies run mover 4 until the Pi servers and the sweeper are rebuilt; until then
  the stick remains there and v5 clients predict with the server's 4.
- Owner live verdict PENDING (lextest.md).
