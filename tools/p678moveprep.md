# P678: inert save-load / hold-release movement policies

This is one prerequisite slice of the requested instant body prediction.
**Normal CSQC still has no `CSQC_PredictPlayerPreMove` export.** No real command
calls these builders; no descriptor/request is transmitted, admitted or applied.

## Contract

`SV_MovePrepAlloc()` returns caller-owned, zero-initialized `moveprep_t *`.
`SV_MovePrepLoad(player, stable_id, sequence, out)` and
`SV_MovePrepRelease(player, stable_id, sequence, out)` clear previous output,
then return READY, MISSING, STALE, REFUSED or UNSUPPORTED. Only READY sets
`out->version = 1`. Use `SV_MovePrepFree(out)`, not raw `memfree`; the descriptor
owns its zoned map and owner strings. Never copy the struct's string ownership
or pass arbitrary/uninitialized memory. Independent outputs do not alias.

Preparation resolves the existing fresh player block using **id + sequence**,
not the selected cursor/index. It requires a real player slot and existing
save-policy/owner gates, complete allocated row tables and a bounded fresh
count. It never allocates/scans a row block, calls Begin/RootFor/ApplyState,
creates a save, loads/moves a body or changes gameplay/timer/recorder/list state.
It uses read-only file handles and `tokenize` scratch. A caller needing the
original command argv afterward must retokenize that command.

Load rereads the interpreted movement content from the subject's current map
and scope. Required keys are version 1, map, seq, ticks, origin, velocity,
angles, duck. Missing/torn keys, duplicates, invalid numeric tokens/domains,
lines over 1023 characters or input over 8192 lines refuse conservatively.
Unknown keys remain additive. Like the existing reader, an empty `fgets` result
ends the read. Values are bounded to the open interval +/-10,000,000; origin
also passes the existing +/-65,536 sanity check. IDs are integral in
1..FS_MAXSAVES; sequences in 0..16,777,215. Wider/legacy cases abstain rather
than pretend float32 is exact. Numeric checks reject NaN/Inf/junk before stof.

Parsed **origin, velocity, pitch, yaw, duck, ticks and sequence** must equal the
indexed row. Each is checked independently. Rewound rows use `rwvel` exactly
as ReadLight does, not paused-body `velocity`. Presence of `demoted` maps ticks
to SL_DEMOTED as before. These are movement policies only: they do not promise
recorder/timer restore will be accepted. Existing Load remains the authority.
Resume-copy, ghost/replay/spectate-hold and sweeper load modes are unsupported.

Release resolves the **current holdrow** with both block bounds and stable
identity; it does not consult the cursor or reread disk. This matches existing
Release's row-based velocity rule, including zero speed and the zero-original-
mode fallback to WALK. Only WALK release is modeled. Non-WALK abstains. The
existing operation is unchanged, including its historical weaker row checks.

## Explicit policy, not fabricated native history

| State | Save load | Hold release |
|---|---|---|
| Body origin | replace with row | preserve |
| Body velocity | row, or zero if already held | row |
| Separately resolved release velocity | row | row |
| View angles | row pitch/yaw | preserve current aim |
| Movement mode | preserve, including held NONE | original WALK / WALK fallback |
| Ground | clear | preserve |
| Armed carrier/base-Z state | clear through existing ClearCarrier semantics | preserve |
| Gravity | preserve | preserve |
| jump_held, jump_msec, waterjumptime | preserve | preserve |
| Native ducked | replace with row completed stance | preserve |
| Native ducking, ducktime | clear | preserve |
| surfacefriction, msec_carry, oldbuttons, stamina, rampoff, boardcount, rampcontact, srcladder, srcladdernormal | preserve | preserve |

The last three rows explicitly cover **all 12 fields of pmsourcestate_t**;
`test_moveprep.py --engine` checks the table against the actual engine header.
Future native fields must cause a failing contract check, not silent omission.
This descriptor is NOT a serialized pmsourcestate_t seed. Its KEEP policies
require the real baseline's carried state; zero output storage does not mean
zero native history. BODY/DUCK/CLEARCARRIER intentions do not perform an edit.

## Freshness limit / remaining prerequisites

READY describes this preparation call only. Identity strings, map name,
player slot and stable id/seq are **not** connection, map-content, save-content,
hold, rewind-selection or ruleset epochs. No persistent cache or freshness
promise is made. Do not use this result later or send it to a client until an
owned epoch/invalidation and transport contract exists. This deliberately
avoids mistaking an unchanged sequence for unchanged movement file content.

Reset and rewind-go canonical builders, generation invalidation, exact-P675
bounded usercmd admission and PEXT2_REPLACEMENTDELTAS operation-bearing BODY
baseline reconciliation remain unbuilt. STAT_FS_SLACK/processed-count ACKs
cannot retire an operation. No new save/evidence format, recording time,
ranked policy, native engine binary, pin/tag or qcbuild number is introduced.
The development installs and fleet were not swapped for this inert slice.

## Reproduction / evidence

In an owned isolated QC worktree with the normal compiler staged in `src/`:

```text
pwsh -NoProfile -Command "cd <qc>/src; ./build.ps1 -NoDeploy -Jobs 8"
python <qc>/tools/test_moveprep.py --engine <engine> --out <artifacts>/subject
python <qc>/tools/test_moveprep.py --out <artifacts>/weak --weak
```

Use `runlines_smoke.py` with `ftesurf/cfg/test/p678moveprep.cfg`, a real
dedicated socket, explicit --client/--server, --ssqc subject/qwprogs.dat,
--mount and a uniquely owned output directory. Stage the normal NoDeploy progs
for the harness; never deploy fixture progs. This server-only fixture requires
`cl_sendguid 1` for the acting attributed-player block controls. It neither
prints nor stores owner values in public evidence.

Grade the resulting logs:

```text
python <qc>/tools/test_moveprep.py --log <rig>/ftesurf/logs/runlines_server.log --client-log <rig>/ftesurf/logs/runlines_smoke.log
# Repeat with weak/weak-qwprogs.dat, then grade with --weak.
```

Verified 2026-10-12 in isolated source based on QC fc447605 and engine d78f2288:
- All three normal VMs and both final fixtures: **zero warnings**.
- Subject dedicated runtime: **66 checks, 0 failed**. Positive preparation,
  independent disk/row mutations, invalidation of prior READY, stable identity
  after compaction, bounds/owner gates, malformed/oversized input, held live vs
  release velocity, all Source policies and actual unchanged Load/Hold/Release
  parity controls ACT. This is not native collision/baseline/network acceptance.
- Weak validation control reads the same file but forces READY: **23/66 checks
  fail as expected**, including the required independent velocity-staleness
  marker; the negative-control grader accepts only an acting failure.
- Reader suite: **306 checks, 0 failed**. Canonical corpus: 270 recordings,
  91 views, 170 existing faults; reader bytes are identical to inspected base,
  no increased source-induced fault count or evidence semantics change.

Retained failures, not passes: initial build missing the compiler; fixture
pointer declaration incompatibility; an initial owner/block rig with 3/52
failures (forced userinfo did not alter engine attribution); an absolute QC
include path rejected at the Windows drive colon. Final fixtures fix these.
No claim of generation freshness, future request admission or instant movement.
