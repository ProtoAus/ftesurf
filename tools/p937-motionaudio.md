# P937 — optional height tone and A/D drums

## Preregistered scope / controls

Base QC9b31c300, engine documentation24a84fd2a; fetched both repos and scanned
published headings/untracked p-tests: max936, claim937 only.

Interpret the requested "Sin wave based on ramp height" as a continuous sine
whose pitch follows the local body's altitude, not camera bob or inferred ramp
material. Recenter on enabling/warps; 1024 units per octave, 220Hz reference,
configurable. A is a synthesized kick, D a synthesized snare. Both off by default,
with independent enable switches and a shared gentle volume. No sample assets,
network traffic, input rebinding or movement/timer/evidence/reader changes.
A native audio-only ownership fix is now required, described below.

Reuse native `queueaudio`/`getqueuedaudiotime` with integer ABI arguments and
packed signed16 mono samples. One CSQC stream, bounded heap buffer and bounded
lookahead/fill work. Observe A/D only after existing input consumers decline;
release latches even when UI consumes keyup. No input or body writes. Observe
`pmove_org` under the existing local-body/ownership/watch/rewind/spectator gates.
Disable and observer transitions leave only a bounded fading tail, never a
stored sequence of later beats. No global RNG use.

Predictions/falsifiers:
- Default/disabled: no generated stream or hits; volume0 also suppresses it.
- Enabled: Native API accepts signed16 data; native queue progresses if a sound
  device is available. Pitch target matches the SAME captured native body height
  and differs after an acted jump; phase/sample amplitudes stay bounded.
- A/D gameplay presses each make the appropriate hit, held/repeated downs do not
  make repeated hits, release allows another; typing/UI does not make hits.
- Disable becomes quiescent after one fade block; native queue drains rather
  than accumulating a hidden backlog. No run/consent/player-data writes.
- Reuse the owned fixture/content/Windows-key helpers and a real dedicated
  socket. Keep the test process muted/background-only, not the owner's apps.
  No clipboard use. Actual listening/pitch/volume balance requires the owner;
  sample counters or queue success are NOT audible acceptance or performance.

Implementation is present; NOT DEPLOYED. Initial three-VM NoDeploy build
`6c84923560f64498ac63c84ca52041d6` is zero-warning. The first native real-socket
fixture passes all eleven controls (artifacts/p937-audio.log): actual A/D and
held/released keys, typed draft, body jump/pitch mapping, generated amplitudes,
positive native mixer queue and drained/quiescent disable. The test process
alone was muted; no consent or run file was written and both actors stopped.
This is functional evidence, NOT listening or independent safety review.

Final build `35dd3c163b464c62ad979e798f6f3a0c` also has zero warnings;
`artifacts/p937-audio-final.log` adds a passing acted volume0 control (all twelve
native checks pass). No native/builtin/VM error; both registered actors stopped.

Independent reviews of snapshot7ae7a80e: input/frame invariant OK. Audio review
found P1 native EOF buffer ownership and P2 a separate switch-off control gap.
Accepted both. S_Raw_Ended now frees/clears retained data before marking its
stream reusable; existing callers invoke it only after the last channel stops.
The exact-callback C ownership unit ACTS: old control4096 allocations/1 free
(4095 orphaned after final purge); subject4096 allocations/frees and0 orphaned,
including repeated EOF callbacks. This is not full mixer concurrency/RSS proof.
The first unit invocation failed before launching a compiler (obsolete mingw
path); the same seam now uses the documented ucrt64 compiler/owned TMP and
passes. Failed log retained.

The switch-off test reenables positive-volume tone and snapshots its active
counter immediately before disabling in the SAME command-buffer pass. Final
`artifacts/p937-audio-fixed-native.log` passes all13 controls: one accepted fade
block from an ACTIVE instrument, stable later counters/drain, plus3 repeated
native drain/restart cycles. Actors stopped; no run/consent files.

Final native source5fd6c6790 / tagpatch-937 is clean and required by ENGINE.txt.
Incremental make retained934 version objects, so the supported Full path was
used (not a new wrapper). `p937-native-full.log` builds all3VMs with0 warnings;
native has74, EXACTLY the same74 baseline warnings,0 new/removed. Both PEs carry
`git-7722-patch-937-0-g5fd6c6790`; full hashes/stamps in p937-native-proof.json.
Clangdb regenerated229TUs after revision-flag change. No unrelated warnings fixed.

Independent follow-up explicitly closes P1/P2, no findings, merge OK. It checked
all-card last-reference/mixer contracts, EOF/purge null safety and control limits.
No audio module or input/frame wiring changed from the first reviewed snapshot.
Actual listening remains owner-only; native ABI/recorder/physics semantics stay
fixed. These controls do NOT establish concurrency/RSS/latency/performance.

Implemented, independently reviewed, published and delivered22Oct2026 23:18UTC
with P936. tools/p936-p937-delivery.md records matching compatible progs/backend,
fixed native images, all12lobbies, hashes/fresh live client and preservation.
P932/P933 and REC13/schema20/lobby native are preserved. Listening remains pending.
