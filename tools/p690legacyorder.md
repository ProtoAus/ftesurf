# Legacy batch-list order at registration/rescan (P685/P690 follow-up)

This is tooling/source-seam evidence, **not a product fix or native cause**.
Default `r_gl_blend_faces 1` and all rejected brush gates remain unchanged.
See [p690brushfixture.md](p690brushfixture.md) for the native failure history.

## Source-proven mechanism

Production P688 `73322dff5b6898511d62ed775286b23a91b8aad0` and merged
`a8e705787fad1b60661da5e8dd43c9138cc69b1b` have identical `gl_model.c`,
`gl_shader.c`, and `gl_model.h` text after ordinary Git/checkout newline
translation. Do not compare the retained observer edits to production source.

- `Mod_LoadModel` queues CPU preparation on WG_LOADER. Synchronous verbosity
  waits while pumping WG_MAIN; it does not put material registration on a loader.
- `Mod_LoadBrushModel` queues `ModBrush_LoadGLStuff` on WG_MAIN for world/inline
  models. The world callback finishes shared textures, then builds batches.
  `Mod_FinishTexture` reaches `R_LoadShader`, which asserts main-thread execution.
  `Mod_ModelLoaded` publishes MLS_LOADED. Worker settings can affect readiness
  and callback timing, but this is not evidence of a concurrent shader-table race.
- `Mod_Batches_Generate` walks BSP surfaces in increasing order and prepends new
  batches. Distinct same-band red then blue faces produce blue→red; compatible
  repeated faces reuse the existing batch. `Mod_SortShaders` earlier in loading
  only sorts texture pointers when their shaders already exist—not batch lists.
- `CL_MakeActive` calls `Shader_DoReload`. While connecting, reload work is
  deferred. A rescan flushes/enumerates the script cache, then reloads live
  shaders. A change in **any used shader's** numeric sort calls
  `Mod_ResortShaders`, including successful parsed and generated paths.
- `Mod_ResortShaders` checks **only MLS_LOADED**, not model type. It snapshots
  every old bucket, clears lists, drains old buckets/lists, and prepends nodes
  into current shader buckets. Same-band order reverses even when that band's
  shaders did not change. Merged bands are also order-sensitive. It calls
  `Surf_ClearSceneCache` afterwards. Loading models are skipped.

Thus identical final shader sorts need not imply identical legacy lists: a world
built/published before an unrelated sort-changing reload can be reversed, while
one built after it, or built but still MLS_LOADING during it, can keep initial
order. This is a controlled source counterexample, **not an observed production
startup schedule**. It does not propose forcing a reload, flush, or resort.

Source navigation in merged: `gl_model.c:472–503,1169–1179,1635–1666,
3610–3795,6201–6286,7051–7084`; `gl_shader.c:8619–8654,9352–9469`;
`common.c:6202–6270,6611–6686`; `cl_main.c:456–481`;
`common/gl_q2bsp.c:185–204`.

## Executable source test

`test_p690legacyorder.py` compiles complete, unchanged production
`Mod_Batches_Generate`, `Mod_ResortShaders`, and `Shader_DoReload` function text,
plus the actual shader-sort enum, with **controlled host stubs**. Extraction is
comment/string-aware and rejects ambiguous signatures. Explicit predicates work
under ordinary and optimized Python; acceptance does not depend on assertions.

Run with a C99 compiler and a **new owned** output directory, from any cwd:

```text
python -B tools/test_p690legacyorder.py --engine-root <inspected-engine-worktree> --cc <gcc.exe> --output <owned-artifacts>/legacy-normal
python -O -B tools/test_p690legacyorder.py --engine-root <same-worktree> --cc <gcc.exe> --output <owned-artifacts>/legacy-optimized
```

With MSYS2 UCRT GCC, put `C:\msys64\ucrt64\bin` on the inherited PATH as well as
supplying its gcc executable. Otherwise GCC may fail to launch its compiler
subprocess with no diagnostic. Such failure is not a passing control.

Eleven cases run at C `-O0` and `-O2`, with `-Wall -Wextra -Werror`:
initial head insertion/compatible reuse; global same-band reversal (including
loaded nonbrush synthetic list and unloaded exclusion); bucket migration;
connecting defer/active consumption; equal-sort reload; unrelated generated
sort change; parsed sortcheck; unused/null slots; world built after rescan;
built-but-unpublished world; rescan-only scheduling. Both Python modes produced
byte-identical valid result JSON on the inspected merged source.

Six source mutants each compile successfully and exit1 at their named predicate
under both C optimizations: missing rebucket, unconditional unchanged-sort
rebucket, lost connecting defer, lost parsed sortcheck, unused-slot reload, and
incomplete bucket drain. These establish that the tests distinguish today's
semantics. They do **not** argue against a future deliberately stable rebucket.

Stubs do not execute a scheduler, BSP/image loader, real parser, GL backend or
rasterizer. `MAXRLIGHTMAPS=1` and reduced structures are explicit host-test
choices, not production layouts. Failed setup/compiler attempts are retained
separately from successful reports; no failed stdout was relabelled acceptance.

## Production-bound observation: prerequisite partly recovered, still OPEN

A read-only source audit and independent observation-design review agree that
inherited diagnostic events cannot describe the differing production boot.
The production's matching unstripped companion was retired; an earlier retained
candidate has COFF function symbols but no `model_t` type debug information.
Candidate/diagnostic absolute addresses must not be substituted.

An **offline-only** recovery subsequently found unique complete-function
normalized matches in production
`aa1d9e1bc2f167520538bb24423c6e690081b943026186de79269d90b7944668`:
`Mod_ResortShaders` at RVA `0xbdf77` and `Mod_BatchList_f` at `0xbb11b`.
Only RIP disp32 and external direct call/jump rel32 destinations were masked;
opcodes, field displacements, internal branches and immediates stayed exact.
Independent references from both matched functions agree on `mod_known` RVA
`0x1aede48` and `mod_numknown` RVA `0x1aede40`, inside production `.bss`.
Candidate roots are `0x1000` different: blindly borrowing them would be wrong.
Parent inspected production disassembly corroborating the narrow list fields.
Two positive anchors and seven specific offline guard/matcher controls pass
normal/-O: wrong module, truncated bytes, candidate disassembly/file mismatch,
wrong field displacement, nonunique match, independent root disagreement, and
root outside .bss. These are anchor controls, **not graph-decoder controls**.
This is addressed machine-code evidence, not recovered type-debug information,
a live-memory decoder acceptance, or registration history. The recovery script
and addressed-byte receipts remain owned artifacts, not a public runtime tool.

Next bounded gate: a fail-closed minimal decoder, with wrong-module/offset,
partial read, pointer, cycle, missing-material and changed-link controls, then
one preregistered **late loaded-memory batch/material snapshot** of the actual
ordinary-worker production boot. Freeze module/PID+creation identity, actual
image base, field/RVA binding, requested/read byte counts and limits first.
Read fixture world/inline chains only, with query/read rights, no debugger,
breakpoints, suspension, injection, body loads or forced worker flush.
Capture exact repeated full frames before opening the read handle and after
closing it; the known failure must manifest first, and reader OFF/ON/OFF plus
P688 return must remain exact. Stop on graph instability or any binding/control
failure. Two agreeing traversals are repeatable **late** state, not an atomic
same-frame view or overwritten startup trace. Model lists need not equal final
backend/GPU submission order.

Exclude `mod_batchlist`, `mod_texturelist`, `r_showshader`, `shader_here`, and
`r_showshaders`: they obtain shader bodies and can reparse/regenerate/rebucket.
`r_shaderpasses` reads loaded fields but does not show model list order; reserve
it for an optional late cross-check outside the principal pixel/read window.

Retained evidence root: `C:\FTESurf-worktrees\mapvisual-01a13061\artifacts\brush-registration-20261014`.
No engine product code, patch number, Build number, default, native binary,
deployment or release was changed by this audit.
