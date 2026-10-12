# P682 — inert warm rewind-go body preparation

This is an **SSQC-only movement policy**, not instant rewind, cache activation,
request admission, native prediction, or a promise that a save/prefix can be
persisted. No production command or client export consumes it.

## Shared canonical read

`SV_RewindSelectRead(e, tick, near, usenear)` returns a physical ring row base
(>=0), missing (-1), or bad domain (-2). Slot, finite request, boolean near flag,
count, head and stored ticks are checked before indexed use. It never allocates
a ring, resets a run, publishes `rw_*`/`rw_statebase`, scans a list, writes a file,
or touches a timer/recorder/pin. `SV_RewindFind` calls this half and retains its
existing authoritative publication effects.

The existing selector is **not nearest/clamped-to-head**. With `near`, it searches
both sides of the requested tick within `RW_NEAR/run_t_tick` (fallback 33 ticks),
choosing smallest spatial distance, then smallest tick distance, then newest
on an equal tie. Without `near`, it chooses the latest at-or-before request in
that window. Outside the window is missing, not a clamp. The predecessor audit's
`SV_RewindPeek`/`SV_RewindAlloc`/`rw_count` names did not exist in inspected source;
the real names are `SV_RewindFind`, lazy allocation in `SV_RewindSample`, and
`rw_n`. P682's selection tests directly exercise the compiled source.

Malformed metadata/requests now make the authoritative Find refuse rather than
index unchecked memory. Valid existing ring selection is unchanged. Supported
exact stored ticks are 0..16777215; the read helper accepts finite fractional
requests (as Find previously did), while the inert go builder requires an exact
nonnegative integer request. Near positions are bounded by the existing save
origin contract; an unused near vector is not a gate.

## Builder and explicit limits

`SV_MovePrepRewind(e, tick, near, usenear, go, out)` clears the old descriptor
before any check. It only describes a successful fresh warm held `go` from a
spawned player slot, positively acknowledged rewind/watch pin, walking release
mode, quiet save gate and at least TWO available rate tokens (general sl_*
charge plus the go-specific charge), fresh attributed non-full list,
and current recording attachment/generation with a valid retained sample mark.
No ID, sequence, list row or file is reserved: descriptor id/seq remain zero.

The call-local subject/map/owner/block, selected tick and ring base/serial are
identity **for this answer only**. They do not provide reuse, connection, map,
recorder-generation or ring-wrap epochs. Same serial does not authorize replaying
an old descriptor. Alloc/Free own descriptor strings; callers must not log owners.

Terminal answers:

- **READY:** body policy for the supported warm successful-go branch only.
- **MISSING:** no allocated/qualifying retained ring sample.
- **STALE:** malformed ring/list/identity or older/forked recorder attachment.
- **REFUSED:** bad request/body, unspawned/unowned pin, save hold, quiet save/rate
  refusal, or active save sweep.
- **UNSUPPORTED:** pure save-only gesture (it does not move), replay/spectate/
  ghost/resume transition, non-walking release, ended recorder/run, full list,
  or any previous-go replacement state. Cold prefix reads and cut-chain walks
  are deliberately not attempted.

READY does not prove disk success, copy/attachment success, evidence acceptance,
rate availability on a later call, or client/native admission. The authoritative
`SV_SaveLocCreateAt -> SV_SaveWriteAt -> SV_SaveReadLight -> SV_SaveLocGo ->
SV_SaveLocLoad/Hold` remains responsible for all those effects and refusals.
`run_inserver` was only moved earlier in QC declaration order; its spawn/
disconnect writes remain in `sv_player.qc`.

## Body policy

Origin, velocity and angles are numerically normalized through the existing
writer's four-decimal `sprintf`/`stof` roundtrip, without writing a row. Rewind
pitch is **not** start-save-reset's pitch clamp. Final held velocity is zero,
mode NONE, and release velocity is the normalized retained sample. Saved duck
forces stand/duck. Ground and carrier clear; Source ducktime/ducking clear,
ducked replaces from forced duck. Every other carried Source member, gravity
and jump history explicitly KEEP. This is a policy mask, not a complete native
snapshot, and no native movement/renderer/input/evidence source changed.

## Acting tests

Build an owned overlay with `python tools/test_rewindprep.py --engine <engine>
--out <owned-output>`; weak variants add `--weak selection`, `--weak held`,
or `--weak rate`.
Use `tools/runlines_smoke.py` with `ftesurf/cfg/test/p682rewindprep.cfg`, a real
dedicated server, an owned mounted overlay, and explicit server cvars
`rec_stream 0`, `rec_enable 1`, `lobby_enable 0` and a non-secret fixture-only
`sv_guidkey`. Freeze/runtime-hash inputs. Do not touch install saves/player data.

The cfg walks out of the start and invokes the fixture during a running
recording, not after falling into a start rearm. The QC fixture pins through the
real dispatcher, exercises synthetic window/tie/wrap/full-cap/domain controls,
restores the genuine ring, and goes through real write/read/load/hold/release.
It also probes cold/no-allocation, stale ownership/no-scan, full/no-delete,
rate/no-charge, malformed rows, old/forked/ended attachments, IEEE NaN/infinity,
READY invalidation, identity and body/movement-policy mutation controls.

Reviewed candidate subject was **91/0**, but independent source review found
that its rate gate admitted one token even though the actual go dispatch charges
twice. No publication followed. Final corrected subject: **98 checks, 0 failed**,
including same-time one-token and just-below-two-token authoritative refusals,
no preparation bucket mutation/output leakage, and exactly-two-token actual go.
One-factor rollback to the old one-token gate: **4/98 expected failures**,
including `one token pre-dispatch go refused without charge`. Spatial mutant:
**7/98 expected failures**, including `spatial window winner beats nearer tick`.
Held-velocity mutant: **2/98 expected failures**, including
`actual go held release velocity parity`. These are acting assertion failures,
not absent output or crashes. Grading requires the exact complete count, one
completion, matching failure markers, client CSQC/completion, and no runtime
fault before or after completion. Existing native menu-builtin compatibility
warnings are separate from movement faults.

Retained evidence: `C:/FTESurf-worktrees/rewindprep-20261012-1352/artifacts/`.
The setup/compile/assertion failures preceding these runs are retained too.
Final frozen-commit proofs, independent reviews, existing load/reset controls,
reader/corpus checks and publication/deployment states are recorded in that
root's checkpoint; none are implied merely by the initial subject result.

## Remaining prerequisite

Prepare cold/replay/new-save-only/replacement branches only with explicit
persistence/attachment availability or safe abstention. Before activating any
consumer, design lifecycle epochs, request/outcome tokens, native admission and
whole-native-state policy application, authoritative baseline reconciliation
and acting refused/cold/reordered network controls. This patch enables none.
