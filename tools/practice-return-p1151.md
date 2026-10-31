# P1151 practice-to-clean return qualification

## Behaviour

At an eligible grounded start, release movement/jump/duck and restore
`host_timescale 1`. A confirmed return arms a NEW attempt at the same pose; it
never converts an earlier practice attempt into a ranked run. Wait for the
server's `normal speed, clean new attempt armed here` message before moving.
Normal speed without that confirmation is not a successful clean return.
An old native client or disabled/missing CSQC remains practice.

## Frozen implementation

- Native: `68a8abc01e7848a5f03d10c0a2896c58f41609e0`, `patch-1151`.
- QQ executable sources: `8c8575779e27cfece82fe44fe75261fd571b356c`.
- Both fresh independent whole-patch reviews: no remaining findings.
- No mover-version or recording-grammar change; existing P1147 camera source
  and P1148 status work are retained. No Build number or release bump.

## Evidence and limits

| Check | Result / scope |
| --- | --- |
| Literal SSQC/CSQC/native helpers | PASS in controlled harnesses; not packet-runtime evidence |
| Zero-tick support identity | Retained pre-fix failure; fixed world/moving-support, missing-support and caller/writeback controls pass |
| Real dedicated socket | Same pose, confirmed clean epoch, charged old client landing carry 76 -> 0, fresh jump and later slow practice PASS |
| Old native client | Remains practice; no false success |
| Final-tag listen route | Same pose and clean completion PASS; not a dedicated prediction test |
| Final-tag missing CSQC | Actual joined client times out and remains practice |
| Builds | Header-full Windows baseline, actual final source and tag-only steps complete all seven official targets; ARM64 server and HL2 plugin compile |
| Five-map platform gate | All 60 named rows match exactly Windows/ARM; native selftests pass |
| Declared historical controls | Reconstructed public cb661-world context: pin2 4418 ticks/4418 rows and P813 replacement pin7 9194/9192 PASS on both platforms |
| Tag-only binding | Windows .text and ARM .text/.init/.fini equal qualified pre-tag images; all six QC program/line-number files byte-identical |
| Recording reader | 949 checks pass. Identical old inputs and unchanged reader produce the same 345 recording/88 view faults on the captured corpus, not zero faults |

The historical VM is source-reconstructed, NOT claimed byte-identical to an
unavailable archived image. The corpus result is a reader/outcome comparison,
not whole-corpus native trajectory replay or general codec interchangeability.
Earlier failed runtime/setup/reader arms are retained, not relabelled passes.
No packet-loss, split-seat, every start-bank runtime or human feel acceptance
is claimed. Main/stage/bonus and familiar geometry checks remain in `lextest.md`.

## Delivery

Qualification and source publication do not by themselves mean installation.
Destination hashes, installed-client cold checks and fleet activation are
recorded separately after guarded promotion. Do not deploy the historical test
VM as a runtime fix.
