# P1492 — bunnyrace doors and local bhop platform landing counts

## Actual map facts / root causes

- bhop_bunnyrace current BSP SHA1 25c0ae5ff2c98a4683090118cecb714ee662033f,
  SHA256015fe4700c8adc0260b610430dad067d0a554837319528ec709f318740bc681a,
  engine mapcrc431ee83e. Two glassdoor brushes *17/*18 receive trigger6135's
  OnStartTouch→Open, but the old QC only changed internal door state.
- kz_bhop_avantura is a VBSP20 HL1-origin authoring port, NOT the similarly
  named bhop_avantura and NOT an original HL1 BSP. Published SHA1
  5b631070b5002ff9c632755339e4cc808396f5af matched the inspected file;
  SHA256c4b09e1670dc32dcbb7a77197ff08218655598de53dcfcd99d067d006622b345.
  It has103func_bhop and22fail teleports. LandingLimit1 makes a non-lobby bug
  visible: airborne frames clear vbsp_bhop_on, so the previous block's count
  could not be reset on landing elsewhere.

## Change

For the exact bunnyrace map+CRC+complete entity fingerprint only, use existing
SOLID_BSP/MOVETYPE_PUSH and ltime mover scheduling. The two doors really move at
600u/s over248units, wait3seconds and close; do not remove/de-solidify them. Other
func_door behavior remains unchanged. Obstruction retains native stall-until-clear
behavior; this is not a new general Source crush/reversal implementation.

Retain the previous bhop block through air. Clear its resettable count on the next
other landing, consuming an ordinary-ground reset once. Check retained class to
avoid touching an unrelated recycled entity. ResetOnOtherBlock=false accumulation
and the existing lobby per-player branch remain unchanged. No teleport, checkpoint,
recorder/evidence format, current mover, engine pin/tag or QC Build change.

## Verification

- Native dedicated production SSQC + test-only StartFrame wrapper: final subject
  22PASS/0failures; named02e58218 baseline7expectedfailures. Open input ACTED in
  BOTH arms. Only subject reached real brush endpoints/open trace, preserved
  solidity, waited3seconds and closed/reblocked. Wrong-map/CRC/entity guards and
  counter true/false/repeat/ordinary-ground/stale-class cases pass.
- Review found repeated grounded reset and manifest ownership issues; both fixed.
  Existing-manifest sentinel refused before compiler/game and retained exact bytes.
  Manifest is exclusively created and finally removed only if still unchanged.
- Final native compiler logs0warnings; combined standard build.ps1 -NoDeploy -Jobs8
  builds all3VMs0warnings (qc/rig/build-nodeploy-cb4e67b77f6848ebb2a639ae6d47224b).
  Compiler SHA25673f9a1a471d603a8d0ee5a83432229ba2dd10affbf358ba41d345c8c15af68c4.
- Independent review clear after fixes. Evidence under owned task maps/:
  runtime-final-{subject,control}, artifacts/final-*.log, manifest-refusal.log.
  Earlier13/20case receipts and corrected stdout/stderr observer refusal stay
  historical; no claim those were the final22case acceptance.
- Worker native run timed out after earlier proofs; parent inspected partial source,
  took sole writing ownership, completed guards/review/tests and integrated exact
  accepted bytes. No owner/peer process killed or shared fixtures edited.

## Explicit limits / remaining user reports

Point traces/solid motion are NOT actual player traversal, pushing/camera feel,
ranked-run verification or obstruction acceptance. Small human checks in lextest.md.
Online platform resets remain a separate falsifier because the lobby branch was
already distinct; do not claim this local-only counter fix explains all reports.

The preliminary teleport-default theory was falsified: actual default already
preserves velocity. Checkpoint callbacks inspected write stats/receipt, not body.
No speculative checkpoint/teleport change. Need exact first crossing/video or
real-player reproduction; tracked in BACKLOG.md.

P1492 was claimed before parallelP1493; keep the already-higher combined ENGINE
marker rather than decrement it. Delivery hashes/UTC must follow actual promotion;
source/build/review are not deployed or human accepted.
