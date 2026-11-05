# P1330: phase availability and truthful prediction diagnostics

## Problem and bounded correction

Source timing is one existing owner/command/carry string at stat179. With
replacement-delta stats, numeric changes can consume all32resend entries before
strings are attempted. If the phase is superseded, later delivery of a newer tag
cannot seed the older acknowledgment. Priority now attempts that existing string
first, only for advertised Source physics, under the SAME byte, resend-entry,
seat, pending-bit and current-value rules. The ordinary loops remain. A full
packet/frame or an earlier split seat can still consume the shared budget.
No new protocol/channel, simulation formula, recorder/verifier or policy.

This is a demonstrated scheduling weakness, NOT retrospective proof that it
caused an old save-time correction. A long command crossing a carried15ms tick
boundary can expose a phase disagreement; the old reports did not record the
phase actually supplied to the prediction. Do not mute saves to hide that gap.

## Native dump v2

The first25numeric columns keep their meaning. Eight fields follow:

| Field | Meaning |
|---|---|
| cmdvalid | Outgoing ring tag matched this acknowledged move/local seat. |
| predvalid | The saved prediction's diagnostic identity matches this row. |
| predpm | Movement mode stored with that prediction. |
| seedseq | FIRST replay anchor used to create this saved prediction. |
| seedcarry | Carry in seconds supplied at that anchor, after phase lookup. |
| phasehit | An exact owner/sequence phase lookup applied at that first anchor. |
| parts | CUMULATIVE native movement calls from anchor to saved prediction. |
| ticks | CUMULATIVE native reported ticks over those calls. |

The first anchor survives later replay commands; later authoritative/cache
contents cannot rewrite its saved provenance. An unavailable/mismatched/reset
prediction clears the fields and leaves predvalid0. phasehit0 is NOT a measured
queue-deferral flag: unsupported capability, neutral prepared seeds and missing
cache tags also return0. Intermediate phase overrides are not a full per-command
journal. Metadata remains client-reported diagnostics, not integrity attestation.

The existing error counter/cvar tuple and QC raw-file upload path are unchanged.
The reader accepts v1/v2, preserving legacy positions/context/SV observations.
Legacy command-input fields are warned as unqualified without the declared
ack-seat identity marker; old data is not regraded by a new native executable.

## Reader fixes

- A gap is between retained comparison samples, not proof of packet loss or ACK
  absence. Multiple received frames can be read between rendered comparisons.
- Frozen SV rows are bounded. Missing tagged identities are unknown, not proof
  that the server never ran a command. Kind0 is not uniquely a loss fill.
- SV body/mode is sampled at next PreThink and can cross a control transition.
- Piece durations are input time, not measured simulation time. Median native
  command duration is not a measurement of missing commands or predicted time.
- Stall counters are not window-local; do not turn an all-time zero/nonzero
  into a measurement of the frozen row span.
- Engine/reporter/schema and validity are shown before interpreting inputs.
- Default headers omit account/address lines. Raw reports/context remain private;
  this is not a promise that arbitrary report contents are safe to publish.
- Failed fetch/read/unsupported schema returns failure even when older local
  reports remain. An empty/ungraded ring is not a successful analysis.

## Verification and remaining limits

- Production replacement-stat branch/helper compiled in a bounded wire decoder:
  baseline2availability failures; candidate44checks/0. Byte/slot boundaries,
  split seat, ordinary/inactive controls, pending/resend identity and newer-tag
  requeue act. This is NOT an actual live-save/network reproduction.
- Actual saved-anchor/cache/counter helpers and actual native writer compiled:
  15checks/0, then two33column positive/unknown rows parsed by the current reader.
- Existing acknowledged-command regression25/0, including poisoned stale tag.
- Reader15tests/0 versus12legacy failures. Existing real legacy reports retain
  their numeric/context/SV rows and original errors; unsupported conclusions go.
- Two independent frozen-source reviews clear. Full tagged Windows native build
  is clean git-8417-patch-1330-0-g538de9265 (the Makefile uses HEADcount+29).
  Seven matching native/plugin outputs are frozen;74existing native warnings
  unchanged with zero additions/removals; all3QC VMs0warnings. NoDeploy leaves
  all19340old installed paths exact, zero new paths, and13shared dependency
  sentinels exact. Initial caller MSYS argv-exclusion failure retained and fixed
  only at that environment boundary with an acting compiler control.
  Installation, ARM qualification and live/owner acceptance remain separate.

No blanket save/TAS/noclip reporting suppression was added. Old save corrections
remain causally unresolved; control-transition context alone is not a general
excuse for unrelated errors. Follow-up is BACKLOG.md and pending lextest.md.

Tests require new caller-owned output directories (do not overwrite evidence):

```
python tools/test_prederr_triage.py --output <owned-root>/reader
python <engine>/tools/test_sourcephase_stats.py --output <owned-root>/phase --cc <gcc>
python <engine>/tools/test_prederr_provenance.py --reader tools/prederr_triage.py --output <owned-root>/provenance --cc <gcc>
python <engine>/tools/test_prederr_cmd.py --output <owned-root>/command --cc <gcc>
```
