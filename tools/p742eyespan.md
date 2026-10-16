# P742 — farther-right Kitsune eye-spanning panes

## Observed failure, not another centroid adjustment

The owner reports P739 fixed most switching, but new slots004/005 still flip
farther right (`surf_kitsune_161.png`, `surf_kitsune_162.png`). The normal live
trace has362 raw/357 gathered commands,4 admitted planes,status-3,6 edges and75
work. Stock wire annotations are correctly after the15 world commands: P739's
layer fix ACTED and stays. World command3 is a planar ramp fan crossing behind
the eye; its geometry rejection leaves an unsupported slot between two admitted
surfaces. Further right, additional visible ramp fans cross the eye plane.

The existing20-face BSP fixture at the EXACT traced camera reproduces all15
world face identities/depths and the4/6/75/status-3 failure. It does NOT pretend
to reproduce the342 procedural annotations or the full native pixel frame.

## Scoped change and controls

Mode2 only admits a validated planar eye span using conservative unbounded
projected bounds, never dividing a behind-eye vertex. Full original vertices
still prove every half-space relationship; broader bounds cannot falsely prove
disjoint coverage. No GPU clipping, mesh, blend/depth or drawing state changes.
A homogeneous triangle-winding proof recognizes empty backfaces through
positive-w clipping; marginal, nonfinite and unsupported cases abstain. Unknown
materials/dynamics still prohibit crossings. Default1's original raster and
submission functions are byte-identical; modes0/1 behavior stays unchanged.

The same actual-C scene now retains all four ramp contributors in the intended
order at both new saves and the traced angle. The traced world result is8
retained/8 admitted/status1/28 edges/350 work, with4 moves (HOST result, not a
new native trace). Every omitted triangle is independently checked with an
explicit positive-w polygon-clip/projected-area reference across39 views.

All4 normal/HEXEN2/fast-math collector variants and23 acting mutants pass.
Removing either new eye-span admission or near winding fails the named
`near_camera_order_ok` oracle. Existing annotation retention/once-only callback,
opaque preservation, conservative unknowns, shader/remap/capture/budget and
128 effective-cull contexts remain exercised. No new native harness/framework.
The older plane wrapper failed twice on its P739 trace-extraction contract;
those setup failures are excluded. After inspecting both extraction slices,
its actual plane C was directly compiled/run successfully with fast-math and
warnings-as-errors; the whole older wrapper mutant campaign was not rerun.

## Exact source, build and installation

- Clean feature/tag: `c75d7a5ea2b28af748001c7ba2bebe9c103618da`, `patch-742`.
- Native stamp: `git-7333-patch-742-0-gc75d7a5ea`.
- All7 native products build;74 baseline compiler warnings,0 new. All5890
  shared dependency files retain their original pre-P737 fingerprint.
- Both normal Windows clients hash-verified at2026-10-16T16:37:40.9320877Z:
  `C:\FTESurf\ftesurf64.exe`, `C:\FTEQuake\fteqw64.exe`.
- Both new SHA256:
  `37eecf1e5b3e5fb7dfb5bd8d2b7e8f7d0bb6f16f1403ed956e4741361c47f0fb`.
- Both `.prev` SHA256, known published P741:
  `4e01424eb032f2afc09bfb4161badd341248833c2fb1959033f747d319a2bbb6`.

The first gate required owner exit; no process was stopped. A subsequent
predecessor guard caught an incoming P741 bundle BEFORE staging/transaction.
Both current client hashes matched P741's PUBLIC immutable clean stage exactly
(`tools/p741menufriends.md`). P742 directly includes its published engine parent
23cbdc9a7 and changes no plugin/header ABI. The old snapshot/failure was retained,
then the proven current predecessor was recorded. Same transaction kernel and
target paths; no failed transaction bypass, DLL/server revert or foreign source
ship. All8 current DLL/server destinations remain byte-unchanged. This task
shipped no progs/config/saves, QC Build, Pi or release update.

## Human result: stage3 section fixed; general ordering still open

Owner confirms the stage3 section is fixed, but new stage1 saves5/6 still flip
(screenshots163/164). That trace has all12 world planes admitted,status-2,
48 edges and546 work: a graph cycle, NOT the old unsupported-span failure.
The general algorithm's unproved centre-order constraints need investigation;
do not issue another surface exemption or call the overall feature accepted.
No more giant dumps needed. Keep the BACKLOG open. Original save data was read
only, never restored or edited.

Detailed owned build/source/control/rollback evidence is deliberately retained
pending that verdict at `C:\FTESurf-worktrees\mapvisual-01a13061\ramp-centre\`:
`residual-p739-native-match.log`, `residual-scene.log`, `p742-face-controls.log`,
`p742-plane-direct.log`, `build-p742-review.json`, `prebuild-p742.json`,
`p742-predecessor-change.json`, `delivery-p742/deployment.json`. Private/raw
console/player/session output is not exported in this public note.
