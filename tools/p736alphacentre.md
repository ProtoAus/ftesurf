# P736 — stable mode2 transparent-face centres

## Problem and narrow change

The owner supplied a saved surf_kitsune position and two frames where a small
view change swaps the ramp/floor grid appearance. The paired ramp is world
geometry. BSP edge splits add collinear vertices: taking their arithmetic mean
moves a draw's depth key even though the surface itself is unchanged. On these
faces the bias can reverse the physical layer order.

Mode2's eligible indexed meshes now use a triangle-area-weighted centre before
the existing world transform/depth projection. Collinear edge splits, triangle
subdivision and duplicate vertex references no longer change that key. Missing,
invalid or wholly degenerate indexed geometry keeps the previous depth fallback.

Modes0/1, default1, existing plane/cull proofs, cached/coarse/capture handling,
materials, map geometry and gameplay are unchanged. This is not triangle splitting,
order-independent transparency or a guarantee for intersecting meshes/custom
vertex deformation. No numerical performance improvement is claimed.

## Acting controls

The existing engine tools/test_gl_blend_faces.py compiles the actual collector,
not another renderer model. A quad/collinear-split pair must retain the same
order against a reference pane; actual Kitsune faces2047/2070 must order correctly
when plane refinement is deliberately unavailable. Four normal/HEXEN2/fast-math
variants pass under -Wall -Wextra -Werror; a mutant restoring the old per-face key
ACTS and fails the new ordering assertion. Existing17 falsifiers also reject.

The first authored test had an uninitialised synthetic world's axes, making all
keys zero; its new old-key mutant did NOT reject. That failed setup is retained
and excluded. Initialising the actual world transform makes the falsifier act.
No GPU/image/performance pass is inferred from these portable controls.

## Exact build and delivery

Engine source/tag: `50c24acf33bb34f3e43a65dd3fa37e618613944e` / `patch-736`.
Both executables embed `git-7352-patch-736-0-g50c24acf3`. Built from that clean
isolated commit with pwsh7, src/build.ps1 -Engine -Full -NoDeploy -Jobs8;
borrowed existing native dependencies, owned TMP/TEMP/TMPDIR and explicit
SVN_VERSION/SVNREVISION protect the worktree build stamp.

All three QC compiles report0 warnings; those progs were NOT shipped. The full
native build has74 pre-existing compiler warning occurrences with exactly the
same normalized messages/multiplicity as the prior P734 full build,0 NEW.
The349 pre-existing Make warnings also match. All20 fixed installed-file guards
and5890 dependency-cache file hashes remain unchanged during isolated building.

Guarded dual drop completed **2026-10-16T07:51:51.3555115Z**. Held all10 native
destination files exclusively through backup/copy/hash verification, then read
all10 destination hashes again after releasing handles. No process was stopped.

- C:\FTESurf: ftesurf64.exe, hl2 and ui_imgui plugins.
- C:\FTEQuake: fteqw64.exe, fteqwsv64.exe, hl2/cod/box3d/ode/ui_imgui plugins.
- Each changed destination keeps its immediate predecessor as `.prev`.
  Older `.prev` copies and independent before/subject bytes are retained under
  the owned task's `delivery/` directory. No owner config/save/player data,
  installed progs, NanoPi native/progs, QC Build number or release was changed.

| Source native product | SHA-256 |
| --- | --- |
| fteqw64.exe / ftesurf64.exe | 35279ed0a71bf0e2094ea6bdc0db2f028cf70d0cbcfde87a9c107777fdf02845 |
| fteqwsv64.exe | b0778282d1ee70fb780c89ed4fc57936572b7c858d509fe99aa1d7c495a00ac9 |
| hl2 plugin | 1e0e7e44e0550344aef34d9bd9c5b4c5efb3d05b41ea85b7ea65040fef02e6f0 |
| cod plugin | d11efb677caf8a647ec9d79e241909ac82cbb96926fb841588846ab27da7c2cf |
| box3d plugin | f2b39553860fd70f2dffc71fb6be02288adf3a3b43820c93a0b7e31ebbafdf09 |
| ode plugin | c522fb943a60af5bc8be2bf7076b3bc920908cf37087787ffa82ac1e99c200f5 |
| ui_imgui plugin | 20ea06bb82dfda405189d6642d42d275d0501f23009e3d05096f293853208e67 |

## Human acceptance and retention

Owner confirms P736 fixes the original saved angle and save2 is good; turning
right into save3 still reorders ramp surfaces. That partial acceptance exposed
a separate mode2 cull-induced cycle, reproduced and addressed under P737.
Current pending visual gate: `tools/p737alphacull2.md`. No new screenshot rig is
needed. Original screenshots contain temporary links and must not be exported.

Clean paired sources/build output, controls, failed-setup evidence and rollback
bytes are retained pending that visual gate at
`C:\FTESurf-worktrees\mapvisual-01a13061\ramp-centre\` (OWNER.md records scope).
The dependency junction is borrowed: future retirement must remove ONLY the
junction, never the canonical cache. No task-owned game processes remain.
