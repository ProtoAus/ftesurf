# Patch 581 — plugin memory-image draw handles

The original claim 577 collided with concurrent reader work. Product entry,
engine pin and tag move forward to 581; published patch-577 history is retained.
These P577-named files/commands preserve the original pre-registered probes,
not the unrelated reader P577-580 implementation.

## Pre-registered scope and falsifiers

Repair the existing `2D` memory-image path before the new indexed-2D/QC
bridge. No ImGui, indexed mesh, clipping, new ABI, widgets or performance
acceptance is claimed by this patch.

Control: unmodified P570 client (`60dfdc102`), copied into a disposable rig.
Subject: same engine source plus this patch. Disabled-plugin arm uses the
subject with `-noplugins`. No install/player config is used by the harness.

- Valid 2x2 TGA via LoadImageData: control returns zero and draws nothing,
  while disk and same-name lookup controls visibly act. Fixed subject returns
  a drawable handle, reports 2x2 dimensions and matches those crops exactly.
- Replacement at the same texture name must visibly change all three panels;
  the subject's second returned shader reference is explicitly released.
- vid_restart must recreate/reacquire images and preserve the replaced pixels;
  the old integer handle is NOT reused as a persistence/generation guarantee.
- A temporary returned handle, released once, must not draw/query as a live
  shader before any slot reuse. Reloading that texture must act again.
- Fixed-subject calls with NULL/empty/short/invalid encoded input, missing name
  and a length above INT_MAX must return zero, leave the live atlas unchanged,
  and reach their post-call marker. Encoded length is size_t but the decoder's
  length parameter is int. No general hostile-image decoder/RSS bound claimed.
- Invalid/zero/non-live handle query, draw, quad and unload calls must fail
  closed without dereferencing before the shader table or double freeing.
- No-renderer subject must reject valid data before decoder/upload work and
  retain a reached post-call marker. This is not dedicated movement acceptance.
- Disabled-plugin arm reaches captures/quit, rejects fixture commands and
  has no magenta sentinel. It cannot be accepted as an active subject.

Every visual phase needs a positive MenuEvent frame count/sentinel, explicit
physical/virtual dimensions, positive disk/reference rendering and retained
logs/screenshots. The grader needs mutations for missing markers, hidden
returned image, unchanged replacement, malformed size/alpha and bad lifecycle
results. Silence, a nonzero return without pixels, or the old zero-asserting
preflight is not a repair test.

## Contract limits

Existing `2D` IDs are renderer shader-table handles. Acquire/release each
successful returned reference exactly once. Renderer restart discards them;
plugins must reacquire via UpdateVideo. A freed slot can be reused, so these
are not generation-safe, plugin-owned texture capabilities. The separate
indexed-2D interface must establish that stronger ownership contract itself.
No production module/fallback or real-panel migration in this prerequisite.

## Run and grade

Requires Windows/GCC and Pillow to launch; grading and mutations are portable:

```text
python tools/p577atlas.py --engine <fixed-client.exe> --control <inspected-P570-client.exe> --fte-root <engine-source>
python tools/p577atlas.py grade <rig/p577-atlas-dir>
python tools/test_p577atlas_unit.py
```

`--control` is explicit: preserve an unmodified client before deployment.
The four owned child copies are control, subject, disabled plugin and normal
startup autoload before graphics. Every subprocess has a disposable CWD,
manifest/no-home settings, cfg_save_auto=0, and only its own PID is stopped
on a timeout. Root autoload runs before logs initialize; the harness assigns
an absolute owned `P577_NONE_MARKER` path for flushed reached markers and
requires a normal exit. Initial client `-dedicated` reached rejection but
faulted in unrelated teardown; that run was rejected/retained, not accepted
by ignoring its exit status. Do not use it as a movement/dedicated-server test.

The fixture is ignored by the repo's blanket `*.c` pattern and deliberately
tracked as this one explicit file, not by sweeping the ignore rules/index.
Source, compile command, copied-engine hashes, cfg hashes, exit codes, logs
and captures are retained in the unique rig. LSP must use the engine context
for this C fixture; standalone-header errors are not a failed GCC build.

Thirty mutation tests falsify silent/missing controls, forged handles without
pixels, frozen phases, wrong alpha/size/dimensions, replacement/restart,
non-live slots, reload pixels, invalid probes and no-renderer shutdown faults.
