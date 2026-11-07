# P1372 -- keep historical warm saves attached to their recorder

## Scope

QC-only repair for NEW ordinary historical streamed saves: capture the complete
recorder metadata with the selected rewind row and write that row's metadata,
not the current head's. Grow the dynamic row layout accordingly; an unavailable
modern tuple is rejected at the writer before new file/copy-queue operations.
No native source/pin/tag, QC Build, recording grammar, physics, credit policy,
backend, original player-data mutation or migration of old incomplete saves.

Claimed 7 Nov 2026 after fetching both repositories and checking patch headings
plus untracked pNNN claims (max1371). Reservation is in the real cfg/test namespace.
Integrated onto inspected public QCfcd4e03ae46d11df13b4c1ed6cea8bf7525d712a;
only sv_saveloc.qc and sv_rewindstate.qc product code differ. Both are byte-identical
to the independently source-reviewed subject used in the controlled warm run.

## Acting controls and limits

- Same existing dedicated-socket entrypoint, installed native client/server,
  unchanged4096MiB/full60quiet admission and exact shared fixture ownership.
- Subject22/0 checks: standing and crouched saved state, body/clock/loaded stance,
  actual client rewind/status/save route, selected sampled position rather than
  later run head, actual client hold/load and release continuing recording.
  The displayed request/native tick differ by one allowed sample at identical
  body coordinates; this is not fractional-cursor equality.
- Existing actual client helper26/0 and atomic loaded endpoint ACTED. The GUI
  initially stopped at its normal two-T confirmation; that retained fixture
  failure was corrected by issuing the normal second press, not bypassing it.
- Frozen public P1366 server DAT counterfactual ACTED on a real streamed run.
  It saved positive clocks but lacked the required metadata and lost recording
  after load. The prediction of ZERO saved clock was FALSE. The original failed
  grader is retained; its captures were read back without rerunning that native
  arm. This establishes recorder reattachment, NOT a general zero-clock repair.
- Nonzero changing native counter tuples, unavailable-state runtime mutation
  counters, full TAS continuation, arbitrary owner replay/cursor combinations,
  visual feel and the owner's specific original zero-clock case remain open.
  Source review/metadata presence alone is not native proof of those cases.
- Old incomplete saves are not rewritten. Missing historical cold-cut duration
  is not guessed or made valid; the existing unsupported boundary remains.

## Integration and delivery

Latest-public integration built all3VMs with zero warnings. Reader949checks/0failed;
unchanged canonical554REC/178VIEW domain (10standalone views) is564CLIinputs with
351existing faulty files, no increase. The first suite invocation reached its tool
limit; the completed same suite passed. The corpus import seam needed the existing
tools path for heldmeta; the corrected existing CLI kept identical input hashes.

Both MC product files are byte-identical to the qualified22/0 subject. All other
server code differences are inspected published changes: Source name filters
(the Q1 control has none), disconnected lobby colour updates (lobby disabled),
and an additive recorder header whose byte extents remain producer-calculated.
Shared definitions and source ordering are unchanged. Client product code is
unchanged by P1372; the qualified actual-client control remains valid for this delta.
A requested extra integrated native arm did NOT LAUNCH: full60quiet admission
refused12:19-12:34UTC (1794..4024MiB, intervening peer/game; last2819MiB). We did not
weaken4096MiB or steal the slot. This is reuse of still-valid scoped source/runtime
proof plus a clean integration build, NOT a claim that the new native arm passed.
Full TAS/nonzero-counter/unavailable-mutation/owner gates above remain explicit.

Pending clean-commit artifact build, exact-SHA publication and dual Windows/Pi
promotion. No delivery, owner acceptance, cold-cut repair or TAS completion implied.
