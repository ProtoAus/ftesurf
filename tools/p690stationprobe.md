# Fixed-station eligibility for ordinary rendering (diagnostic only)

`p690stationprobe.py` answers a narrower question than `p690ordinary.py`: can a
specific existing map/camera satisfy an **exact full-frame stationary** protocol?
It never accepts production service/cadence, changes a rendering default, or
labels authored animation a defect. Native PNGs, logs and frozen drivers remain
in the operator-owned task artifacts, not public Git.

```text
python -B tools/test_p690stationprobe.py --output <fresh-owned-controls-dir>
python -B -O tools/test_p690stationprobe.py --output <different-fresh-dir>
python -B tools/p690stationprobe.py <station-capture-dir>
python -B -O tools/p690stationprobe.py <station-capture-dir>
```

Normal and optimized Python use the same explicit gates. The CLI prints JSON:
- `ELIGIBLE exact stationary probe`, exit0: structurally complete evidence and
  all exact-pixel/action eligibility conditions pass; still NOT performance proof.
- `INELIGIBLE exact stationary protocol`, exit1: structurally complete probe, but
  at least one exact repeat/HUD return/action condition failed. Full-frame change
  counts and inclusive bounds are retained; no masks or relaxed tolerances.
- `INVALID station probe evidence`, exit1: missing/malformed/stale evidence,
  wrong camera/state, incomplete activity or failed stop/restoration closure.

## Frozen stations and contract

The registry pins the existing Kitsune, Tensor2 and Demise camera sextuples;
changing a station requires a new protocol, not silently accepting the observed
pose. Body/angle tolerance .06 covers rounded console `info` values. Diagnostic
eye tolerance .15 covers wire quantization plus the standing64-unit eye height;
all increasing postdraw eye/angle strings must agree **exactly**, across both
modes. `timer` may be idle, armed or running on the correct map: zero body velocity
and exact fixture restoration are required regardless of incidental practice
recording. This is not a recorder/verifier test.

GL960x720 RGB PNGs, exact known mv11 diagnostic bundle hashes/stamp, cache0 and
Source/fromgame4 are mandatory. Registered quiet HUD/input/prediction/HDR settings
inherit the accepted ordinary gate. Water2, envmap1, reflection/refraction scale1,
and per-map glare interval are additionally explicit/read back. Authored live
animation is not frozen. Both mode1 and2 must each have fixed-eye uncached draws
advancing >=128 and exact full-frame before/after PNGs, plus mode1 HUD on/off/on
with >1000 changed pixels and exact on-return. An on/off delta alone is NOT causal
HUD proof when the on-return changes too.

Two ticketed ordinary cost-channel samples per mode verify **activity only**:
complete100-frame buckets, positive actual world/transparent/draw counts,
complete128-swap cadence rings, nonoverlapping windows, fresh bucket fingerprints,
current-send BEGIN/footer primaries and timestamp-exact hashed successful waits.
The primary/wait reader is shared with `p690ordinary.py`; no archive reconstruction.
Snapshot/staged probe native8/install/config/data/map/script receipts and rc0 stops
must close exactly. SHA256 receipts/protocol identifiers support auditability;
these self-contained offline files are not authenticated runtime attestations.

## Native eligibility results — 2026-10-13 UTC

All native probes serialized and finished/restored before image/hash/test/review
work. Two modes and seven full-frame PNGs per completed attempt. The known-stable
Kitsune station is the positive control, not an additional-map timing expansion.

| Station | Evidence status | Mode1 repeat changed pixels | Mode2 repeat changed pixels | HUD-on return changed pixels |
|---|---|---:|---:|---:|
| Kitsune | ELIGIBLE | 0 | 0 | 0 |
| Tensor2 | INELIGIBLE | 286,088 | 283,347 | 344,091 |
| Demise, first attempt | INVALID: wrong settled camera | excluded | excluded | excluded |
| Demise, preregistered second attempt | INELIGIBLE | 24,701 | 21,166 | 24,467 |

Kitsune HUD on/off changed16,215 pixels and returned exactly. Tensor2 mode1/2
repeat bounds both `[0,273,959,719]`; contact sheets show the affected lower water
area. Demise second-attempt bounds both `[161,0,959,319]`; contact sheets show the
upper sky/scene area. These are observed changing regions, **not isolated shader
causation or engine regressions**. Rendered-eye/aim strings stayed fixed across
both modes; each draw counter advanced314–315, requested/inuse/cached0. Every
valid attempt contains four complete cost-channel reports. Their numbers remain
diagnostics, not production cost acceptance or cross-map performance comparison.

The first Demise `cmd setpos` printed the requested pose but settled about1.1
units off it. A separately frozen retry split noclip activation from placement,
then placed again after settling and validated `info` before screenshots. The
same authored target passed camera validation; no body/eye tolerance was widened.
The original attempt remains INVALID. No further native retries were used.

**Conclusion:** neither additional station qualifies for the current exact
stationary gate. No production P688/merged/P688-return timing was run there. The
published Kitsune result remains unchanged; broad-map/moving-camera service/tail,
scene-time synchronization, native actor fixtures and default2 promotion remain
open. Next work must preregister a suitable moving/time-aligned protocol or a
new representative station; masking animated pixels is not an acceptance path.

## Offline verification

The synthetic suite passes31 tests under normal and `-O`, including three-station
positive controls, one-pixel ineligibility, stale/missing/tampered tickets/waits,
wrong body/eye/world/cache/HUD state, incomplete cadence rings, reused PNG paths,
wrong native/closure, and existing-output refusal without writes. Constructed
pixels are detector controls, never native proof. `test_reccheck.py` passes306
checks; the canonical273-recording/91-view corpus and existing fault counts remain
unchanged. Parent source/evidence review completed; the attempted independent
review timed out and is **not** claimed as completed.
