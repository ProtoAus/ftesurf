# P937 — optional height tone and A/D drums

## Preregistered scope / controls

Base QC9b31c300, engine documentation24a84fd2a; fetched both repos and scanned
published headings/untracked p-tests: max936, claim937 only.

Interpret the requested "Sin wave based on ramp height" as a continuous sine
whose pitch follows the local body's altitude, not camera bob or inferred ramp
material. Recenter on enabling/warps; 1024 units per octave, 220Hz reference,
configurable. A is a synthesized kick, D a synthesized snare. Both off by default,
with independent enable switches and a shared gentle volume. No sample assets,
network traffic, input rebinding, movement/timer/evidence/reader/native changes.

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

Pending before publication: independent review of the audio math/queue lifecycle
and the input/frame wiring at the writer's callsite.
That wiring is kept immutable during review. No native or evidence semantic
change is intended or claimed. Actual appearance/listening remains owner-only.

Implementation / final validation / deployment: in progress. P936 is published but still
not deployed; prepare one compatible backend/progs delivery after offline audio
work, not a succession of redundant fleet swaps. Serving P933 remains untouched.
