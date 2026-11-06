# P1341: clearing teleports clear the predicted push carrier

## Problem and bounded fix

Successful ordinary non-landmark teleports in VelocityMode1,2or3 change velocity
and call SV_ClearCarrier on the server. TG_FireTeleport changed predicted velocity
but left the client's held carrier untouched, allowing an old boost after arrival.
Mode0 and landmark teleports deliberately preserve the carrier and remain so.
This source mismatch is independently reproducible; it does NOT establish the
cause of any historical save/load prediction report.

TG_ClearCarrier shares the existing relative-teleport zero-carrier write and
clears the current touch pass's queued push/accumulator. A later continuous push
cancels that queued zero and arms its own carrier, rather than being erased by
the native adapter's push-then-bvset application order. A once-push remains an
ordinary velocity impulse. The helper is gated by the existing BVSET capability;
no new native API, protocol, server physics, recorder/verifier/evidence format,
report threshold/suppression, backend, native pin/tag or QC Build change.

## Verified so far

- Exact production teleport/push/relative helpers and SV_ClearCarrier, plus the
  literal server VelocityMode arm, compiled and executed in an actual dedicated
  CPU-only QC VM. Synthetic tables/IO lookup/health and command stubs are explicit.
- Baseline42checks/8intended failures; subject42/0, exit0. Failures cover the three
  ordinary clearing modes, noclip-alone clear, discarding an earlier queued push,
  summing an old push after clear, replacing a refilled unarmed carrier, and a
  later push after a relative clear. Keep/landmark/destination/health/bypass/
  spawnflag/old-engine and velocity controls ACT, not silence-only checks.
- Actual src/build.ps1 -Jobs8 -NoDeploy: THREE VMs, zero warnings, qualified
  compiler SHA256c24ede65af01d6c7e20d5d1dbd2190a9295a38fb0e109843f75e52166da22f74.
- Public p1341carrier.py entrypoint independently executes the same42/0 fixture.
- Fixture setup initially missed two declarations and copied unused globals;
  original compile failures retained, fixture declarations corrected. They were
  test setup failures, not product progress or waived warnings.

This is functional helper/adapter-contract evidence, NOT a full native network
replay, measured correction distance, historical cause or owner-feel acceptance.
The native consumer itself is unchanged and is not executed by this QC fixture.
Delivery and human checks are separate; deployment is pending at this checkpoint.

## Reproduce

Run tools/p1341carrier.py with --compiler, --server and --pak paths to an existing
qualified fteqcc executable, dedicated-server executable and id1/pak0.pak, plus
--out pointing to a NEW directory under an owned task root. It never writes an
install and stops only its own child handle. Default --source is this checkout;
--source can select the prefeature checkout and --expect-failures8 proves the
acting control. Preserve logs/source hashes rather than recycling an output path.

## Small manual acceptance

After delivery, cross a familiar push-fed velocity-reset teleport: the exit
should not briefly retain its old boost. Keep-velocity/landmark transitions must
still carry speed. Record actual owner feedback in lextest.md; do not require
replaying the whole stream or treat a missing popup as acceptance.
