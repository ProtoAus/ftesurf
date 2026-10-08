# Patch 601 — counted native widget/model snapshots (diagnostic only)

Reserved after fetching game/engine origins and inspecting both shared checkouts
and isolated worktrees: maximum patch heading/ENGINE patch/untracked pNNN is 600.
Base game 9ba5cb2bb51ee3faeb2864467234e25f4da037d0, engine
c61458c94f23b2cf1552301d1232dde33e04274a. Shared source/install work is untouched.

## Pre-registered contract and falsifiers

- New optional exact-size `NativeUIModel/1` table from the same draw/input provider.
  QC stages an explicit counted immutable snapshot; native deep-copies it. No QC
  pointers retained. Up to 64 widgets, 95 UTF-8 label bytes plus NUL each; text,
  button, checkbox only. Scalar widget/row/revision IDs are exact positive QC
  integers <=16777215; widget IDs are unique. Rows may contain multiple widgets.
- Begin/widget/commit is draw-bracket/VM/generation guarded and atomic. Missing,
  duplicate, malformed or oversized data cannot publish a partial model. Invalid
  staged entries poison the transaction. Revisions strictly increase per owner.
  Empty count clears the model. Native callback failure releases once to fallback.
- Typed actions bind generation/revision/widget/row, never array offsets or label
  hashes. Poll needs successful draw and the caller's current revision. Host
  validates membership, type/value and identity; no command strings cross back.
  Replacement resets pending/held input and both action queues and revokes draw
  authority until redraw. Reorder/delete cannot retarget a previous press/action.
- Absent/old input/draw-only providers keep their prior behavior. No automatic
  input route, production panel, preference/default, progs/install/Pi/Build change.

Controls: actual native button/checkbox clicks must yield matching typed actions
exactly once; renamed/reordered labels keep IDs. Subjects: replace with queued
press, held press and unpolled action; stale revision/generation/VM, removed row,
malformed UTF-8/numeric/count/duplicate ID, callback failure, action overflow,
close/reopen and provider loss. Regress existing passive/input/mesh host controls
in both 16/32-bit ImDrawIdx builds. Compile real engine/plugins with -Full and QC
-NoDeploy; retain logs and distinguish the known final-summary failure from actual
compiler output. Runtime diagnostic VM probes must ACT; screenshots/fallback and
old-provider arms must be explicit, not silence.

## Implementation and measured results

Host `cl_plugin_ui_model.inc`, copied ABI/grammar in `plugins/plugin.h` and
`plugins/ui_model.h`, real ImGui `model.inc`, and shared optional QC wrappers
implement the contract above. Owners remain the existing diagnostic 103/204.
`NUI_ModelWidget(handle,index,identity,value,label)` identity is vector(widget,
row,type). Type 1=text, 2=button, 3=checkbox. Snapshot values are QC-owned; respond
to checkbox actions by publishing a new revision. Model poll returns widget/row/
value; generation and requested current revision are checked inside the host.
All polling shares the existing 16-attempt host-frame budget. A replacement after
a Draw intentionally cannot authorize polling until the next successful Draw.

- `python tools/test_p601model.py --out rig/p601-model-controls`: 463 model host
  plus 172 passive assertions; 184 actual model assertions per 16/32-bit arm.
  All zero failures, with acting button/checkbox controls before stale subjects.
  Existing input regression: 929 host, 700 actual interactive and 109 passive
  assertions per relevant arm, zero failures. Native controls compile -Werror.
- `pwsh -NoProfile -Command 'Set-Location C:/FTESurf-imgui-input/src;
  ./build.ps1 -Engine -Full -NoDeploy -Jobs 8
  -FteRoot C:/msys64/home/Lex/fteqw-imgui-input'`: all three QC programs zero
  warnings; client/server compiler stages completed. `rig/p601-build/build.log`
  records unrelated plugin ZIP busy/permission errors. Same command without Full
  at Jobs 1 retries those outputs: `rig/p601-build/retry.log` completes native
  stages. The known missing installed-progs NoDeploy summary still exits 1 AFTER
  the builds; no successful wrapper exit or install-seeding workaround is claimed.
- `python tools/p601model.py --plugin
  C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteplug_ui_imgui_x64.dll`:
  `rig/p601-model-wdqq9sjv`, 42 screenshots across absent, draw-only, input-only,
  scale1 and scale2, zero failed. Both actual MQC/CSQC emit button/checkbox actions
  at revision 1, retained button/row at revision 3 after reorder/rename, and new
  widget/row at revision 4 after deletion. Old press releases emit nothing.
  Both fallback providers ACT; no optional-model builtin is called on them.
  Screenshot reviewed: checked QC-owned checkbox, replacement row, literal ##
  label, inherited clip and restored outer sentinel. Physical output is identical
  across virtual scales. No implicit files, leaked owners or closed recurring work.
- `python tools/test_p601model_unit.py rig/p601-model-wdqq9sjv`: 21 acting/mutated
  reader controls, all pass. Bridge grader: 24 controls, zero failures. Earlier
  failed diagnostic compiles are retained: initialized QC globals are const,
  sprintf limit counts the format argument, and locals require explicit defaults;
  corrected fixtures compile zero warnings. These are not silent passes.
- Refreshed clangd resolves the real ModelRegister table and actual plugin macros;
  no new parser errors. Its early missing-include/G_STRING cache was stale until
  parent TUs refreshed; actual implementation uses PR_GetStringOfs. Existing
  unrelated TU advisories and necessary global-include lint remain, not suppressed.

## Publication/freeze checkpoint

Concurrent published Patch 602 was fast-forwarded intact into both isolated
branches; 601 stays its earlier reservation. ENGINE.txt retains highest patch 602
rather than downgrading peer metadata; engine pin/tag advances for this native work.
Engine source/tag: `35370f0387b94eefb95fa506f28ccd24c6693f6e` / `patch-601`.
Game source/test commit and final clean-source verification are being recorded.
No deployment/release/Build decision has been made, and no installed binary, DLL,
progs, cfg, data or Pi swap was performed. Follow-up is a separately chosen real
panel with explicit input ownership, covering fallback and measured budgets;
physical device/minus/modifier/cursor, non-GL/font/DPI and cost acceptance remain
unverified. No production migration is implied by these diagnostic controls.
