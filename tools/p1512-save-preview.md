# P1512 ordinary save-load preview acknowledgement

Implemented, independently source-reviewed and deployed on 11 November 2026 UTC
to both Windows installs and all 12 lobbies. Human/Mark acceptance remains pending.

## Change

The ordinary registered console `sl_load` path predicted the saved view without
binding that preview to its own sent acknowledgement. An old ACK of zero could
begin refusal settling and expire the render preview before the load reply. This
is a demonstrated source defect, not a proved explanation of Mark's complete
wrong-position, prediction-error or native-crash report.

The actual sender now counts after context cleanup and binds an immediate load
preview to that command's own ACK. A busy FIFO does not arm a new preview; the
existing real load still queues and dispatches without borrowing a newer preview.
The fallback key path no longer assigns a target after returning from load/hold
admission. Charge ordering, clean-return fence, hold release and modern WarpOp
ownership remain intact. No new queue/ticket protocol, server/body physics,
recording/evidence format, native rebuild, engine pin/tag or QC Build bump.

## Verification

Independent source and acting-artifact review cleared final product SHA256
`58ee3d95a32a29ab14b79e5c00744ebe36fda95b73ea7ac3200b47dbb1b31373`
and test-tool SHA256
`e65385d1152c726907d16eb8aaae66108544d097d8ba72de40ff4013ddce76dd`.
The review checked 16 extracted production functions in both subject and actual
prepatch helpers, their identical assertion tail, real sender/queue/camera
ownership, conditional cleanup/re-entry and finite test boundaries.

The existing `tools/test_warpop_reset_order.py` runs an isolated dedicated CPU-QC
fixture. Engine stats, property sinks and selected service boundaries are doubles;
the console, sender, FIFO admission/dispatch, counter and camera are production
functions. This is not a full graphical client or real network-latency test.

| Arm | Retained result |
|---|---|
| Final ordinary console load, injected300ms ACK |71 checks /0 failures|
| Actual prepatch helpers, `--baseline-ref abc8cafbd5a575caa1e42e5f748e9b78bbd2d4e9` |56 checks /9 expected failures,8 labels|
| One-line old-ACK mutation |56 /9 expected failures, same8 labels|
| Existing modern reset controls |100 /0|
| Existing rewind controls |36 /0|

Actual prepatch and mutation controls emit the real load before grading. They
expose early pre-reply expiry, own-ACK refusal settling, nested send ordering,
downward reset, advanced raw ACK, same-frame hold release and fallback ownership.
The unchanged subject oracle deliberately returns driver1 for the prepatch
control; its dedicated process exits0. Missing camera writes explain56 rather
than71 checks. No detector was weakened to turn the baseline green.

Fixture compiles have zero warnings. After rebinding the owned build to the
already-qualified published P1505 compiler, SHA256
`1f2efd0616f60e2c3d29372cb7c32f8cad1f15cb0831d8e2490e5468048550bc`,
subject71/0, actual prepatch56/9, normal100/0 and rewind36/0 were confirmed again.
The documented `src/build.ps1 -Jobs 8 -NoDeploy -PassThru` entrypoint compiled all
three production VMs with zero warnings. Both installs' existing three programs
were byte-identical before and after that NoDeploy build.

Use unique output directories under an owned task root when rerunning the helper.
`--baseline-ref` selects actual Git helper bytes only for plain-load controls;
failed runs preserve their actual source/helper hashes before oracle assertions.
The old `--control` mode remains the separate historical reset control.

## Limits and delivery status

Timeout1.5s, refusal settle0.15s and arrival8 remain unchanged. Camera writes only
view origin/angles; these controls do not measure authoritative body placement,
wire ACK delivery, framebuffer behavior, all Watch/SaveLead integration, arbitrary
counter permutations, rare native exits or real high-ping feel.

Human standalone-load acceptance and Mark's exact bind/map/error remain pending
in `lextest.md`. The P1508 snapshot transport repair is a separate deployed fix;
neither its packet checks nor these CPU controls establish Mark's root cause.

## Development deployment -- 11 November 2026 UTC

Published inspected QC source `20ee7283dcfb7c70a572ea00250bde3110571c81` and engine
documentation `1df81b79185706f0331277de4630c9884596758a`. Deployment reused that
clean source's qualified NoDeploy artifacts, not a later source rebuild. Native
pin/tag remain `041181a7b`/`patch-1508` and QC Build 89; no release is claimed.

| Program | SHA256 |
|---|---|
| qwprogs.dat |`de63efd32542f6b03bb4469abb9d2c0a9b8221285697e8c7754041efe9467867`|
| csprogs.dat |`957ddec338dbd0591d7af0ccb63807eccc2803ad9cc44ba5265d1aaf6d3de75d`|
| menu.dat |`c00ab9456a9735fd2838929b5cbc4cb49b269acbb5050ab4fda86f968694530e`|

- Windows receipt 23:12:55.7835722Z: DAT+LNO for all three VMs match the qualified
  artifacts in BOTH installs, all12 targets independently rehashed. Current and
  prior-previous preimages were retained and verified; all27 bounded protected
  files remain equal. Only the existing build.ps1 Deploy function performed the
  swaps. Its caller's old hardcoded qualification ref was made explicit and
  includes ENGINE.txt in the unchanged-input check; no quality gate was removed.
- Pi postflight 23:19:09.944252Z: the unchanged inspected build.ps1 -Pi block warned
  every lobby and used its default10-second countdown, then swapped only QW/CSQC
  and restarted all12, none skipped. Menu/native/backend/configs were not shipped.
  Both destination hashes match above and both `.prev` hashes match actual prior
  current bytes. Twelve actual new native actor epochs/hashes were observed.
- Before ANY canonical Pi staging/restart, all 216 recorder/resume payloads
  (326,906,867 bytes:9 parts+207 resume members) and all4 current/prior-previous
  progs preimages were archived, on-box verified and independently rehashed
  off-box. Raw identity/nanosecond inventories and resume archive metadata were
  retained. Fresh boundary and postflight use the original strict guards; all216
  rows/payload/recorded metadata remain equal. Backend actor epochs, native and
  bounded configs remain unchanged. No player-data restoration was performed.
- The first immediate post-restart UDP postflight timed out after all swaps and
  restarts had succeeded. It is retained as a failed check, not regraded. All12
  readiness/actor checks then passed and ONLY the same read-only postflight was
  completed; no second swap or extra restart occurred.
- Subsequent live serverinfo on all12 actual new actors advertises folded-MD4
  `0x1d67ca2e` and 5,317,994 bytes, matching the qualified CSQC. The first metadata
  reader missed native^2/^7 color prefixes; that failed reader and the bounded
  format diagnostic are preserved. Correcting only color decoding (including
  hexadecimal size) gave all12 matches without any server/file change. This is
  live advertisement proof, NOT a cold-client download or graphical-camera pass.

The HUD's P1493 title shows the editable local game/menu release version, not this
QC patch identifier. Reconnecting and retrying ordinary `sl_load` and the usual
binding is the small pending human check; do not infer P1512 loading from that
release label or turn deployment into a claim that Mark's entire report is fixed.
