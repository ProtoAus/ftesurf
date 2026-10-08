# Patch 600 — optional explicit native input/action prerequisite

## Start checkpoint / preregistered falsifiers

2026-10-08 continuation of `tools/p598imgui.md`; owned clean worktrees:
`C:/FTESurf-imgui-input` at game `0eafc34` and
`C:/msys64/home/Lex/fteqw-imgui-input` at engine `d3625b570`.
Both origins fetched before starting; maximum published heading/test claim 598.
A second pre-commit fetch found the concurrently published verifier Patch 599;
its commits were inspected by path and fast-forwarded intact. This work claims
600 only. Disposable fixture cvar/command/log markers retain their initial
p599/P599 names for replay of the preregistered controls, not as a patch claim.
Shared original trees contain peer changes and will not be built or staged.
No installed/progs/config/data changes are authorized by this test stage.

Scope: additive exact-size `NativeUIInput/1` C interface, optional MQC/CSQC
named input/status/poll builtins, guarded QC wrappers and diagnostic owners
103/204. Preserve NativeUI/1 byte layout, existing passive owners 101/202 and
legacy fallback. No production panel, cursor claimant, command interception,
movement/chat binding or scoreboard default changes.

Events carry only finite bounded scalar data (physical mouse coordinates,
buttons, wheel, compact navigation keys, Unicode scalar, explicit reset).
Caller must already own a live VM-local handle; native code never receives
engine scancodes/binds and never claims engine input. Host and plugin queues are
bounded independently. Reset clears queued and held input immediately and
remains usable at the event limit. Close/restart/unload destroys the context.
Actions are bounded scalar records, consumed only after successful explicit
Draw in the same VM's draw bracket; owner generation accompanies every result.
Previous unread frame actions expire. This static gallery protocol is NOT a
model/snapshot generation protocol for real browser rows or engine entities.

Predictions/falsifiers:

- Existing P598 passive glyph/scale/lifecycle gallery and old bridge controls
  remain acting and unchanged. Missing extension preserves passive drawing;
  interactive owners refuse rather than pretend to accept input.
- Real-source host input performs button click, checkbox toggle and ASCII text
  edit; each corresponding action must be polled once with the correct owner
  generation. Empty poll, stale/foreign owner and malformed values yield zero.
- Queued press + reset + release cannot click; held button/key/text and action
  state do not survive reset, close/reopen or another VM. Controls must first
  prove a non-reset click/key event acted.
- ABI size/version/capability/callback/provider errors reject before callback.
  Numeric/Unicode/key/budget violations reject before plugin callbacks where
  host-owned; callback failure/malformed action releases the owner once.
- Closed init/status work does not render/upload/allocate per frame. All atlases
  balance; unrelated external ImGui context restored after every callback.
- Real MQC/CSQC disposable runtime dispatch must produce nonzero action witnesses
  and visible changed widget state, not only status counters. Missing provider
  must render the usable fixture fallback. Synthetic QC events do not establish
  device routing or movement-minus/modifier/cursor acceptance for real panels.

## Implemented / acting evidence

- Additive exact-size NativeUIInput/1, same-provider registration, guarded optional
  QC wrappers; NativeUI/1 unchanged. No implicit engine input hooks or commands.
- Host events: 128/frame even across reopen. Plugin accepted events and actual
  trickled residual queue: 128. Poll: 16/successful explicit Draw/VM/frame; action
  generations validated. Reset remains callable at the event limit and clears
  held/queued input, widget focus, actions and host polling authority.
- Static button/checkbox/text gallery; fixed 128-byte UTF-8 edit buffer. All
  upstream/adapter units use IMGUI_USE_WCHAR32. Exact supplementary UTF-8 and
  whole-scalar backspace are source-tested; default atlas glyph coverage is NOT
  non-Latin font/DPI acceptance. Clipboard/OS IME callbacks disabled.

Commands (from owned game worktree, Windows Python / pwsh 7):

```
python tools/test_p600input.py --out rig/input-bounded-controls
python tools/p600input.py --plugin C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteplug_ui_imgui_x64.dll run
python tools/test_p600input_unit.py rig/p600-input-2o5kvepm
python tools/p598imgui.py --fte C:/msys64/home/Lex/fteqw-imgui-input --engine C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteqw64.exe --server C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteqwsv64.exe --plugin C:/msys64/home/Lex/fteqw-imgui-input/engine/release/fteplug_ui_imgui_x64.dll --progs C:/FTESurf/ftesurf/qwprogs.dat run
python tools/test_p598imgui_unit.py rig/p595-imgui-sr8ipr6f
python tools/test_p590bridge_unit.py --fte C:/msys64/home/Lex/fteqw-imgui-input
python tools/test_p589mesh_unit.py
# From src/:
pwsh -NoProfile -Command "./build.ps1 -Engine -Full -NoDeploy -Jobs 8 -FteRoot C:/msys64/home/Lex/fteqw-imgui-input"
```

Results: 929 new bridge + 171 passive assertions; 699 interactive + 108 passive
assertions per 16/32-bit arm, zero failed. Includes an ACTING trickled backlog and
repeated cross-frame refill limits, actual typing at the 127-byte edit limit,
queued/held reset, VM/owner/stale-generation/failure/malformed-number/Unicode
controls, two independent contexts and balanced atlases.

Standalone DLL runtime `p600-input-2o5kvepm` and native Makefile DLL runtime
`p600-input-gmbbkb_b`: 33 screenshots each, zero failed, both MQC and CSQC actual
button/toggle/ASCII-text/backspace actions and changed visible state. New provider,
missing provider and older draw-only engine controls act; simultaneous VMs,
reset/no latent activation, reopen, plugin and renderer release, covering fallback,
closed-work balance and physically identical virtual-scale arms pass. Runtime
probe events are synthetic QC dispatch, not OS/device-input injection. 17 mutation
controls reject missing/false action/input/capability/resource/pixel witnesses.

Passive P598 regressions `p595-imgui-sr8ipr6f` and native DLL `-t3dyszct`: 23 shots,
zero failed; 16 grader controls pass. Bridge grader 24 and mesh grader 33 pass.
Frozen source will repeat runtime after final metadata stamping.

Full compiler stages complete in `rig/full-final.log`: three zero-warning QC
programs, native outputs, same 74 compiler-warning occurrences / 49 distinct
fingerprints as P598, zero new (`rig/warning-final.json`). FIRST cold dependency
build also rebuilt untouched ODE and emitted its existing deprecation diagnostics;
the warm Full control matches the baseline exactly. No warning suppression or
unrelated-source repairs. The whole build command still exits 1 AFTER native/QC
stages because the preexisting final NoDeploy summary reads absent installed
progs (BACKLOG.md). Do NOT report a successful wrapper exit, seed the install to
hide it, or conflate retained outputs with installed binaries.

Engine clangd database regenerated from actual Makefile flags, then supplemented
with actual plugin commands. Standalone checks with exact driver/TMP/PATH and
`--tweaks=`: native bridge C and plugin C++ zero parser errors. Early cached Pi LSP
errors came from opening the new checkout before its database/driver environment;
CSQC refresh/definition resolves PF_ui_native_input to cl_plugin_ui_input.inc.
Real compilers and runtime remain the authority; no clean-cache-only claim.

## Commit/frozen/push/deployment boundary

Canonical engine source/tag: `c61458c94f23b2cf1552301d1232dde33e04274a` / `patch-600`.
It contains native feature `41c807539`, inspected concurrent Patch 599 notes
(`ce5ae6a86`) and the include-scope correction (`c61458c94`); no peer native source
changes. The initial local `ce5ae6a86` freeze and its host controls FAILED because
late header cleanup moved library declarations inside FteImGui. Retained logs:
`rig/frozen-build.log` (native plugin stage), `rig/frozen-host-controls/host16/compile.log`.
No silent substitution: external headers restored to global scope, fragment scope
comment added, and `rig/fixed-host-controls` repeats all 929/699 plus passive
controls successfully. The unpushed local tag was corrected before publication;
no bad tag/binary was published or installed. This is a real newly introduced
compile failure, NOT the earlier cached missing-database issue or summary bug. Game base advanced intact
to `9ba5cb2` (committed peer tooling/notes only; no QC source delta). Patch 599
number/history/tag remains untouched. Native tag/pin changes are appropriate for
this engine work; qcbuild remains unchanged.

Game source/test `3e1f643` plus corrected pin/scope receipt `365f43f` are committed.
Corrected clean frozen game `365f43f7f8fef589254352db3f5161210050a134` and engine
`c61458c94f23b2cf1552301d1232dde33e04274a` / local `patch-600`:

- `rig/frozen-fixed-build.log` completes all native/compiler stages; expected
  preexisting summary-only exit 1 remains, not a successful wrapper exit.
- Exact `SVN_VERSION` / `SVNREVISION` inputs and +29 offset produce
  `git-7134-patch-600-0-gc61458c94`, verified IN BOTH native client/server bytes.
  The ImGui DLL has its own upstream/service version rather than this engine
  stamp; clean-source compile/link provenance and its hash are retained in
  `rig/frozen-fixed-input.json` / `frozen-fixed-hashes.json`.
- `frozen-fixed-warning-comparison.json`: 74 baseline occurrences / 49 distinct,
  zero new, three zero-warning QC programs. No dirty-source deploy workaround.
- Final native Makefile DLL/engine runtime `p600-input-23k5d1j6`: 33 screenshots,
  zero failed; its 17 mutation controls pass. Passive frozen regression
  `p595-imgui-jbozvwpc`: 23 screenshots and 16 controls, zero failed.
- Corrected source host `rig/fixed-host-controls`: all 929 bridge / 699 interactive
  plus 171/108 passive assertions pass for the relevant 16/32-bit arms. Standalone
  corrected C++ parser check: zero errors; refreshed Pi reports no new parser
  errors (one necessary-global-include lint advisory, existing CSQC advisories).
- At 2026-10-08T16:23:08Z, `installed-binary-preservation.json` proves both actual
  installed client paths (`C:/FTESurf/ftesurf64.exe`, `C:/FTEQuake/fteqw64.exe`)
  still match the OLD draw-only control hash from before these builds. No source
  or fixture has been copied into either install.

Only exact-SHA publication and this docs-only verification receipt remain at this
checkpoint. No installed/native/progs/config/player-data, Pi, server, release or
Build-number change has been made by this workstream. Native dual deployment is
NOT claimed: test-stage artifacts stay in the owned trees until separately gated.

Next implementation: bounded counted model/widget snapshots plus stable row/action
identity and freshness rejection; do not substitute owner generation for model
revision. Then wire ONE opt-in real panel through existing QC-owned input/cursor
chain, with movement-minus/modifier/focus acceptance before default changes.
Non-GL/device/font/DPI/cost, real-panel rollout and any guarded native-only dual
delivery remain separate gates. Current isolated gallery never claims platform
input or alters a production binding.
