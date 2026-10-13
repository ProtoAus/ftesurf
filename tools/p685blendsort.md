# P685 — opt-in OpenGL transparency ordering

## Product / activation

Engine `f79ad12cc3ac3393188e7500592674454aedf97f`, tag `patch-685`.
Only engine C and its portable production-code test changed. QC Build stays
unchanged, and no generated programs/configs were deployed with this feature.
The partial envmap-space implementation is **not** in this commit or bundle.

Restart the client, then select `r_blendsort 2` to try the new order.
`r_blendsort 1` restores the legacy/default order; `0` retains emit order.
Default remains **1** pending broader capture/performance acceptance.
Mode 2 affects OpenGL, not the other backends.

## What it does / does not do

Plain transparent meshes across world/entity/scenetris sources join one stable
far-to-near stream, keyed by transformed vertex bounds along view forward.
Weapon/depthhack records follow ordinary geometry. Capture-capable records
stay on the immediate recursion-safe batch path. Cached/CPU-unavailable records
retain whole-batch coarse submission instead of disappearing. Per-face draws
copy batch descriptors; cached pointers/ranges are not permanently mutated.
Source scene caches are no longer globally forced off.

This is mesh sorting, not triangle splitting or a solution to intersecting panes.
Coarse cache records cannot establish internal face order. Recursion/capture,
rotated brush/model/weapon overlap, water and broad perf acceptance remain open.

## Portable falsifier

From any cwd, with the engine checkout and a GCC-compatible C99 toolchain:

```text
python <engine>/tools/test_gl_blend_faces.py --cc gcc
```

On MSYS2 put `C:/msys64/ucrt64/bin` on PATH (runtime DLLs are required even if
--cc names gcc.exe absolutely). Optional `--output <owned-artifact-dir>` retains
generated C, binaries and control logs. Default temporary outputs are removed.
Do not run Python with `-O`; assertions are the oracle.

The test extracts the actual production collector/guards/entity matrix and
compiles normal and HEXEN2 configurations, with and without fast-math, using
`-Wall -Wextra -Werror`. It covers stable ties, transformed bounds, scenetris,
weapon foreground, captures, cached-VBO/CPU-unavailable fallback and bitwise
NaN/Inf guards. Three generated mutants ACT and fail assertions: cached batch
drop, whole-world scenetris key and removed finite guard. This is production C
with submission stubs, not a GL pixel/driver test or performance measurement.

## Exact build / native acceptance

Owned clean worktree at the exact engine commit; full client/server/plugin build
via QC `src/build.ps1 -Engine -Full -NoDeploy -Jobs 8 -FteRoot <clean-engine>`.
NoDeploy kept canonical installs untouched until the guarded engine-only swap.
The build adapter passed canonical ARCHLIBS and explicit SVN_VERSION/SVN_DATE:
the current Makefile's `test -d .git` probe misses worktree `.git` files. Runtime
`version` reports `git-685-f79ad12cc3ac3393188e7500592674454aedf97f`.
The accepted P683 full-build and P685 exact stamped build each have **74 compiler
warnings with identical diagnostic payloads**, zero new payloads and zero errors.
Make pattern warnings are separate. A first cold dependency rebuild emitted
additional untouched ODE warnings; it is retained, not the comparison pass.

Real dedicated socket, port27620, OpenGL1280x720, RTX2080Super/NVIDIA591.86;
`cfg_save_auto 0`, idlefps0/maxfps100, vid_srgb0, renderscale2, crosshair and
hud_crosshair0, con_notifytime0, cache0. Isolated CSQC fixture adds two identical
screen footprints at view-forward distances256 (red) and512 (blue), each alpha
0.5, reversing only emit order. World rendering stays enabled. Capture a
fixture-off background per renderer mode, then a fixture-on image. Grade
`[592,688) x [312,408)`, independently using `0.25*background + (128,0,64)`;
tolerance two RGB levels for per-draw integer rounding.

| Exact committed binary arm | Pixels | Bad pixels >2 | Maximum error |
|---|---:|---:|---:|
| mode2, emit order1 | 9,216 | 0 | 1.5 |
| mode2, emit order2 | 9,216 | 0 | 1.5 |
| mode2, reverse view | 9,216 | 0 | 1.5 |
| legacy mode1, mixed order1 control | 9,216 | 9,216 | 65 |

Stationary Kitsune camera: eye `-13425.1318 -14684.4238 -442.3868`, angles
`45.6537 95.4932 0`; reverse angles `0 275.4932 0`. These are visual-fixture
setpos arms, not timer/prediction tests. Earlier native pane/model/sprite and
cache-material controls were retained; this final pass did not remeasure every
one. Cache1 readback remained1 on a loaded Source map and screenshot retained.
That is not a broad scene-cache FPS pass.

Failed harness arms remain excluded: unquoted PowerShell drive paths; inherited
MSYS argument-conversion exclusion; relative executable names that selected the
canonical client instead of the subject; world-disabled alpha-target fixture;
and missing fixture-world cvar registration before an explicit `set`. Native
acceptance uses absolute executable paths and explicit fixture-world1. The
fixture programs were restored after testing and never shipped.

## Windows deployment / rollback

Engine-only dual deployment completed **2026-10-13T03:39:37.6320090Z**. Ten
build-contract destinations match the exact clean build, and each `.prev`
matching its pre-swap hash is retained. No owner/other-session process stopped.
Protected configs, installed lists and qwprogs/csprogs/menu hashes and mtimes
were unchanged. The installed P684 program pair was copied to the isolated
subject only for compatibility smoke; both installed executable paths loaded the
matching program copies, drew the leaderboard via `+showscores`, reported default blendsort1,
and exited normally. Both board screenshots inspected. Unavailable `board`/
`ui_status` diagnostics were not treated as acted controls. Fixture/subject
program copies were restored after the smoke.

| Exact build file | SHA256 |
|---|---|
| fteqw64.exe | 995b3325250bf7b24cc480de5cc42e6cc837005c51ae0db61fdfbbdfb7425396 |
| fteqwsv64.exe | c579a93fc1f4f605d9818d5487fb2d7351cad1eb201afc31e9c97ef065b59f07 |
| fteplug_hl2_x64.dll | b86ffbe832eb739e19b3570dedd57acfa7e9a2f61ed35629aafdab716ceada08 |
| fteplug_cod_x64.dll | ff70a134cdcc5adbba39cb0793fcf1529f452a5bc30fb522ea0a43d00937b988 |
| fteplug_box3d_x64.dll | 8b091b5a093ae2a07a476c07323198c5e29046c511fb80f558ceb24112e73b5b |
| fteplug_ode_x64.dll | 504fe6c872679c9890cf17350cb67d8ad0f3f37a79dbc9fb26dd184d90f05b17 |
| fteplug_ui_imgui_x64.dll | c4ac208757c5221bfb868a311172e2bb2cdb5b09e25395fc1d30fac6a7447de3 |

FTESurf gets ftesurf64.exe, hl2 and ui_imgui; FTEQuake gets client/server and all
five matching plugins, per build.ps1's native deployment contract. No Linux
native/plugin, Pi program/config/lobby, QC Build-number or release change.

## Retained local evidence / remaining work

Task root `C:/FTESurf-worktrees/mapvisual-01a13061`,
`artifacts/followup-20261013`: p685-full-exact-stamped-build.txt,
p685-warning-comparison.json, p685-commit-tests.log,
p685-exact-commit-native-oracle.json, p685-stamped-staging.json,
p685-windows-deployment.json and owned native rollback. Subject screenshots
`p685-native-*` and `p685-installed-*-acted-board` are retained with fresh logs.
These local logs are not a public artifact bundle.

Envmap-space corrective source passed independent static review and offline
48-stage/24-link GLSL coverage, but is unbuilt/native-unverified and remains
uncommitted. WVT, FULLBRIGHT and sphere variants abstain. It requires separate
native sample/output-state, bit7/15, exact spec0, recursive/query/perf acceptance.
Tensor water/cold-load diagnostics likewise remain unresolved; they are not
credited as a sorter regression or renderer acceptance pass.
