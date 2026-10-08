# Patch 598 — minimal Dear ImGui draw-list service

## Scope / pre-registered falsifiers

Inspected engine base `200e688c23b683a2c8426ae97e532c082de16a90` (P594,
docs-only after `bed572f50`), game base `8df760b`. Work only in the clean
`C:/msys64/home/Lex/fteqw-ui-bridge` and `C:/FTESurf-ui-integration` trees;
primary checkouts contain unrelated peer work. Fetched both origins; current
maximum product heading/test claim is 594. Provisional single claim: 595.

Native C++ plugin, pinned MIT Dear ImGui 1.91.9b, no raw graphics hooks or engine
C++ linkage. The existing `NativeUI/1` and `2DMesh/1` C ABIs remain unchanged.
Distinct MQC/CSQC contexts, immutable per-context RGBA atlas, physical-pixel
layout, ini/log writes disabled. Only explicitly opened diagnostic gallery
owner IDs are accepted; real panels are not migrated. No Tick/Sbar/Menu drawing,
input capture, widget/model/QC-pointer transport or automatic panel activation.

Pre-register before implementation/testing:

- Real Dear ImGui draw lists must reach bounded mesh Submit through QC's draw
  site in both VMs. Text, rounded controls, child/table clipping and tooltip
  pixels must be visible; logged intent alone is insufficient.
- Missing plugin must execute visibly usable QC fallback. Plugin loaded with
  owners closed must execute zero additional ImGui frames/uploads/submissions.
- Physical gallery images at two different virtual scales must agree. QC
  before/after overlap and inherited-clip sentinels must retain exact ordering,
  caller colour and clipping. Font is the embedded 13px physical default;
  this is not Apple-like quality or broader font/DPI acceptance.
- Adapter tests use real generated and crafted ImDrawData: DisplayPos/scale,
  RGBA packing, nonzero IdxOffset/VtxOffset, 16-bit and 32-bit index variants,
  reset callback, >64K vertices and bounded multi-submit splitting. Malformed
  later commands, unknown callbacks/textures, non-finite/overflow data and
  total budgets reject before any Submit. Submission failure returns false.
- Failed atlas/open/draw releases partial context resources once, and permits
  QC fallback. Explicit close, VM teardown/disconnect, renderer restart and
  unload/reload release both contexts; stale tokens/handles never alias.
- Existing 170 bridge-host assertions, 24 bridge/33 mesh graders and acting
  P594/P589 galleries remain green. Native/plugin compilation adds zero new
  warnings; standalone adapter/host builds use -Wall -Wextra -Werror.

## Initial verified implementation

Engine feature `61393769e`; byte-provenance correction `38413ccdf704265c46b99507bbd0d7094e4388f9`
was the provisional local `patch-595` candidate (later publication/collision is
recorded below). Game baseline advanced by
fast-forward to published `4f06647` before docs/pin edits. Dear ImGui tag
`v1.91.9b` resolves to `f5befd2d29e66809cd1110a152e375a7f1981f06`;
11 upstream files are unmodified, MIT license included, vendor SHA256.json pins
raw bytes. Fresh clean `fteqw-ui-imgui-bytes` checkout at `38413ccdf` verifies all
pins and builds the plugin with -Werror clean (`rig/p595-build/fresh-checkout`). `vendor/* -text` preserves those bytes in Windows autocrlf checkouts.
No runtime fetches. Adapter/gallery are documented in engine plugins/ui_imgui.

Commands (from C:/FTESurf-ui-integration; fresh output dirs retained in rig/):

```
python tools/p595build.py --host --out rig/p595-build/host16
rig/p595-build/host16/host.exe
python tools/p595build.py --host --index32 --out rig/p595-build/host32
rig/p595-build/host32/host32.exe
python tools/p595imgui.py --plugin <engine>/engine/release/fteplug_ui_imgui_x64.dll --engine <engine>/engine/release/fteqw64.exe
python tools/test_p595imgui_unit.py rig/p595-imgui-opmsq03z
python tools/test_p595nodeploy.py --log rig/p595-build/nodeploy-fixed-5.log
python tools/test_p590bridge_unit.py
python tools/test_p589mesh_unit.py
python tools/p590bridge.py --fte <engine> --engine <engine>/engine/release/fteqw64.exe
python tools/p589mesh.py --fte <engine> --engine <engine>/engine/release/fteqw64.exe --control rig/p589-mesh-4jpv7z06/control/ftesurf64.exe
```

Results: 107 host assertions per 16/32-bit index arm, zero failed. Runtime
`p595-imgui-opmsq03z`: 23 screenshots, zero failed; all 16 grader controls pass.
Actual bridge host 170, bridge graders 24, mesh graders 33 all pass; valid bridge
`p590-bridge-_20fr43l` and mesh `p589-mesh-n0p5_nc6` regressions zero failed.
Three real QC compiles zero warnings, standalone/plugin make builds -Werror
clean. Existing native compiler warnings in the initial build match frozen P594
texts; full frozen fingerprint comparison remains a separate final gate.
Both plugin source files pass standalone clangd --check with their actual C++17
compilation db, exact g++ query-driver allowlist and --tweaks=. The live session's
cached C-only/gcc-only server diagnoses wrong MSVC C++11 headers for these files;
that is not the actual compiler/parser gate. No user LSP settings changed.

### Retained failed controls / build safety repair

- Initial GCC 16 -O2 vendor warning: upstream mouse-array range analysis after
  assertions. Keep vendor bytes unmodified, compile vendor -O1, adapter -O2;
  -Wall -Wextra -Werror, no suppression and no cost acceptance.
- Initial 32-bit macro `unsigned int(...)` cast did not parse; use ImU32 variant.
- Initial rounded-control sample was under the inherited clip, not the corner;
  corrected to a visible corner/centre pair after inspecting the actual image.
- Initial plugin imported libwinpthread-1.dll; static link now leaves Windows
  OS imports only, no new MinGW/C++/pthread runtime deployment dependency.
- Bare make inherited an invalid Windows temp path; mandatory pwsh build works.
- Crucially, **-NoDeploy was not a declared build.ps1 parameter**. PowerShell
  silently accepted it as an extra argument; the initial working-tree build
  copied native binaries to the integration tree and FTEQuake. All touched native
  destination/rollback hashes were captured; prior natives were hash-guard restored
  from .prev, and newly created ui_imgui DLLs parked in this owned rig. No owner
  process was terminated. QC outputs in the integration tree were rebuilt;
  no primary-install/second-install progs or Pi/config/player-data swap was invoked.
  The now-declared switch isolates QC output and gates native copies, while
  CmdletBinding refuses typos and NoDeploy+Pi/Run. -o changed old-style .src
  interpretation, and absolute manifest inputs also failed; same-directory
  manifests preserving declaration order/relative inputs act. The successful
  real control (`nodeploy-fixed-5.log` plus before/after hash receipt) proves 65
  install/rollback/progs/cfg byte/path witnesses unchanged, native branch marker,
  three zero-warning QC builds and early refusal controls.
- A previous retained P581 control path had disappeared; use the still-present,
  inspected acting P581 control from `p589-mesh-4jpv7z06`, not the P589+ bridge
  baseline which would not be a missing-mesh falsifier.

## Canonical claim correction and immutable history

During final fetch, another session had published surfd-only P595-597. Exact
main pushes were blocked by ancestry checks, but the provisional native tag
`patch-595` at `38413ccdf` had already been published. Do NOT delete/rewrite it.
Canonical native feature is **P598**, engine merge `d5e828f03a9ca58a12ce70a753ac952b215e38e5`
and local tag `patch-598`; peer P595-597 entries/code are preserved by
merging origin/main, not reverted or deployed as part of this client-only work.
After fetching both origins and checking headings/untracked claims, max was 597.
An owned marker `C:/FTESurf/tools/p598imgui.md` exposes this active isolated claim
to other sessions until publication. No unrelated primary-tree files are changed.
Canonical tooling/fixtures were renamed p598; imports/fixture paths follow that
rename. Existing diagnostic command/cvar/log/rig prefixes remain p595 so retained
controls still grade. They are not real-panel activation or product patch claims.
The above commands/results are the exact **provisional** runs; current equivalents
are tools/p598build.py, tools/p598imgui.py, tools/test_p598imgui_unit.py,
tools/test_p598nodeploy.py and tools/fixtures/p598imgui_host.cpp / p598imgui.qc.

Provisional clean full build at `38413ccdf` + game `ef3ad1d` is byte-verified as
`git-7121-patch-595-0-g38413ccdf`: 74 compiler warning occurrences / 49 distinct
fingerprints, identical to frozen P594, zero new; all three QC builds zero warnings.
Frozen native hashes are in rig/p595-build/frozen-hashes.json. Its final galleries
`p595-imgui-_8z3ga91`, `p590-bridge-arlnqfci`, `p589-mesh-v8g6aft8` pass, but are
NOT canonical P598 delivery proof. Initial wrapper FTEBUILDNO/FTEBUILDVERSION
variables were not consumed and the Makefile's .git-directory check misses
worktree .git files; that unstamped build was rejected by binary-byte inspection.
The repaired wrapper uses actual SVN_VERSION/SVNREVISION inputs and FTE's +29
revision offset. Canonical P598 build must re-prove its own embedded stamp.

## Remaining final gates / explicit limits

Publish the exact inspected engine/game SHAs only after clean frozen build,
provenance and valid-gallery regression. Guarded native-only dual deployment
must preserve progs, configs, data, server and unrelated DLL hashes and retain
rollback. No progs/Pi/config/data changes are needed for this service.
No performance, input/device, non-GL, Linux/package, real-panel/modern appearance,
release or Build-number approval. The 13px embedded-default physical font and
triangle expansion are prototypes, not accepted font/DPI/cost policy. Multi-batch
backend failure can leave earlier valid batches drawn; covering QC fallback is
required. Next work is bounded widget/model/input transport + isolated interactive
panel tests, not scoreboard/default migration.
