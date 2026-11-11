# P1494 — held load/reset ordering and camera ownership

## Root / change

ResetTry refused a local save hold, so reset used reliable string commands while
an older load could still arrive on WOP. The delayed load then revived the server
hold after reset, and local preview/angle ownership remained active.

Admit held resets onto the existing ordered WOP queue, blind while prior motion is
pending. Clear local hold/preview only after successful admission, suppressing a
still-held physical key until release. Keep earlier admitted operations. Following
loads can recognize a pending reset despite stale HOLD stats. Existing busy/full/
missing-destination/reliable-in-flight refusal keeps local ownership intact.

Cancellation alone was insufficient: lost/nondecoded or ACKed-but-refused reset
could strand the server hold. Track a reset-specific queue identity and actual
command sequence. Recover only after server progression and0.3s settled coherent
HOLD, not from a dispatch ACK alone or from older free stats. Never emit a reliable
release immediately at admission. New load ownership cancels the obligation.

A rewind-go request retains the old obligation while unresolved and fences recovery;
successful Rewind_Answer adopts the new hold and cancels old recovery. Refusal resumes
the old obligation, timeout retains existing abandonment recovery. This prevents an
old reset's delayed release from cancelling a newer rewind countdown. Other audited
TAS temporary save holds release synchronously. Raw user cmd strings still deliberately
bypass client ownership handlers as before.

No server policy, recorder/reader/evidence format, native code/pin/tag, physics mode
or QC Build change. Existing authoritative server validation remains unchanged.

## Proof and limits

- Actual production-QC helper/Frame/InputFrame/ACK and server WOP dispatch fixture:
  normal100checks/0; reset-release omission100/11 exact expected failures. Original
  pre-fix17/8 acting contrast retained. No repeated count-only reruns.
- Production rewind Go/Answer/Abandon/Waiting and serverSaveLocGo fixture:36/0;
  handoff omission36/4 exact expected failures. Native/practice request spellings,
  split-event/ACK wait, adoption, refusal, timeout and busy admission covered.
- Engine/stat delivery, command emission and zone/hold/event services are explicit
  doubles. These are deterministic control-flow proofs, NOT real300ms transport,
  full server validation, UpdateView or camera-feel acceptance.
- Both P1 review findings (lost hold obligation, rewind adoption) fixed; final
  independent review clear. Earlier refusals/control artifacts remain retained.
- Parent integrated exact accepted client source and BOTH test dependencies, then
  combined standard build.ps1 -NoDeploy -Jobs8: three VMs0warnings. Actual output
  qc/rig/build-nodeploy-9d19e6b484464b2b9a8ee68e8f3bdc17 under owned task root.
  Qualified compiler73f9a1a471d603a8d0ee5a83432229ba2dd10affbf358ba41d345c8c15af68c4.
- Relevant source base02e58218; accepted source/receipts under task camera/artifacts/
  camera-source-rewind.patch, REWIND-HANDOFF.md and rewind-handoff/acceptance.
  All source is in parent integration; no canonical peer dirty file was shipped.

Small owner high-ping/rewind countdown check is pending in lextest.md. A shared
performance session held the graphics interval, so no GUI or owner process was
interfered with. This patch does not claim the separate checkpoint-body report is
resolved. Actual Windows/fleet hashes/UTC must be recorded after promotion; no
release publication or deployment is implied by this source checkpoint.
