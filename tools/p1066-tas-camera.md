# P1066: TAS camera ownership and safe streamed-recording refusal

P1065's final source review found three real failures after its first Windows
installation. They were reproduced with the preserved P1065 executable/progs
control, not accepted from source reasoning alone.

## Corrections

- Native warm restore keeps the historical model/body angles, but sends the full
  restored view angle directly through the ordinary reliable fixed-angle sender.
  It does not leave its own fixangle pending for the next movement command.
- Replay supplies the selected command aim without manufacturing an early
  fixangle. Genuine QC corrections retain their ordinary angle ownership.
- Replay sends its camera correction after the mover has published its resulting
  view, including a portal rotation. Body/model pitch is never used as camera
  pitch by this replay notification.
- Current-format REC14 streamed edits, replay and `tas back` refuse before taking
  the request, watch pin, prefix save, placement or recording cut. Buffered warm
  REC14 history remains supported. The generic warm preflight also rejects these
  incomplete stream snapshots.

The stream limitation is deliberate. Historical rewind snapshots do not contain
all the mover-command metadata required to restore REC14 streams. Copying current
head values into an older snapshot would not be a valid restoration. Full support
is still on ROADMAP; ordinary non-TAS streamed rewind remains in BACKLOG.

## Acting checks

Owned headless clients connected to a real dedicated socket. A read-only SSQC
observer reported recorder state and native portal counters; it was not added as
a production command or shipped. Client `weapon_info` already reports the actual
`VF_CL_VIEWANGLES` as `input-angles`.

- Unchanged retained nonzero-pitch replay: same resulting body, velocity and server
  view; actual client view agrees within normal angle-wire quantization.
- Edit a retained row to pitch30, then edit the last two rows to pitch30 and
  rewind one tick: both the replay and the restored tick retain the full view
  pitch rather than the historical model-pitch scaling/sign.
- An actual linked pair rotates travel/view by90 degrees. Direct and replayed
  portal-counter increments prove both crossings; replay matches the direct
  body's position, velocity and view. The old binary preserves body movement but
  leaves stale aim/camera, so a position-only check would have missed this.
- A live current-format stream with retained input refuses editing/replay and
  tick-back while serial, row count, running/recording state, byte extent,
  body/velocity, step request and pin stay unchanged. The P1065 replay control
  instead enters restore and cancels recording.

## Committed-source qualification and Windows delivery

Product QC `3dcca2870bea4439fcd9e838c0239a35aa109a6b` pins native
`b7eef87303dd8f734c5796661b1eb8dd366540a1` / `patch-1066`. A clean full native
and QC build passed with zero new warnings; both executables and all five plugin
ZIP metadata stamps match the clean native tag. The930 recorder checks pass.
The current corpus has503 REC,167 paired VIEW and10 unpaired VIEW; both the
unchanged P1065 reader control and current reader report311 existing findings on
that SAME corpus (zero increase). The earlier497/306 corpus is not silently
compared to a later larger corpus as though the input set were unchanged.

At2026-10-27T15:38:26Z the qualified cohort was installed to `C:\FTESurf` and
`C:\FTEQuake`:14 native/progs destinations match qualification hashes, with
predecessors preserved. CS caches were seeded without deleting other downloads.
MENU, configs and install lists were unchanged. All14 real-socket edit/replay
checks then passed using the actual installed primary client and secondary
server. The first installed smoke legitimately reached the fixture's short END
before listing input; retained as a failed arm, then corrected by extending only
the test END and rerunning from a real recording start. No product guard was
weakened. No other running game or Desktop install was changed.

No rendering/feel, performance or arbitrary-world deterministic claim follows from
these headless checks. Normal rendered camera feel is still a human acceptance
item in `lextest.md`. Existing bounded warm-history/unsupported-context restrictions
from [P1065](p1065-tas-inputs.md) still apply. No Build number/release bump or lobby
service change is part of this correction.
