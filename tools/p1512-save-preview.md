# P1512 ordinary save-load preview acknowledgement

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
The review checked16 extracted production functions in both subject and actual
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

Product publication and dual-Windows/all-lobby deployment are the next execution
steps. This preparation record is not yet a deployment receipt; actual source,
UTC, hashes, restart/preservation and served-client readbacks will be recorded
when complete. Ordinary progs deployment retains `.prev`; no release is claimed.
