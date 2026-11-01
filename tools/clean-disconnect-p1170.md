# P1170: clean lobby switch/quit; weapon Drop remains

## Scope/root cause

Native QW CL_Disconnect sends string command `drop` (repeated for UDP loss).
`SV_ParseClientCommand` intercepted it as weapon presentation, so native teardown
never ran. Server retained the old player until timeout. SSQC now reserves
`drop`/`disconnect` for native via existing `clientcommand`. Weapon presentation
uses `weapon_drop`; both actual CSQC emitters changed. User-facing Drop/key stays.
No timeout reduction, Native/header/API/recorder/physics/data/backend change.
Native runtime remains exact520/P1162. Current MENU6f maplist fix is unchanged.
Existing ClientDisconnect callback still handles its normal save/avatar cleanup.
Abrupt kill, network failure or lost disconnect packets still require fallback.

## Smallest adequate validation

Official NoDeploy exact whole actual control: all three current SV/CS/MENU
binaries reproduced, including public14aef133 time-readers/current actual feature
cohort, not stale noclip images. Candidate changes exactly sv_player, cl_weapon
and cl_weaponui. 0SS/0MENU errors; existing2CS F333, no new warning class.

One real old-control GUI/private dedicated localhost server: normal native quit
exits0 yet roster keeps ghost>1.2s. Reused healthy control, no repeated runs.
One real candidate GUI/two localhost dedicated servers: normal surf_weapon USP
picks2; user-facing Drop sends weapon_drop, actual type0 and rosterstill1;
A->B oldA0; B->B exactlyone; normalquitB0 without timeout or forced termination.
Five actual Native/QC logs clean. No production client/lobby/backend traffic.
BelowNormal2cores and existing shared quiet-machine GUI lease.

Failed first caller used native local impulse `weapon usp`, which never sent
weapon selection: expectedtype2 correctly failed on0. Same subject corrected to
normal CSQC surf_weapon alias plus actual server wire witness. Next caller was
blocked by owner game reopening and timed out BEFORE taking lease/creating actors;
owner game was not interrupted. All seven product checks then passed; final
reporter referenced nonexistent Peer.base. Corrected Peer.log reader and graded
same retained raw logs without rerunning healthy GUI cases. Original failures
retained; no product/expectation relaxation or new evidence namespaces.

Private source/whole-binary control, original failures, final smoke, input hashes
and protected dual-Windows/Pi receipts live under owner task artifacts
`timescale-20261030T1558Z/clean-disconnect`. No credentials/user data published.
Slot checks follow target signon/normal quit, not a numeric latency benchmark.

## Delivery contract

Keep exact Native520 and MENU6f; paired SSQC+CSQC and checksum cache only. Protect
CURRENT configs, saves, data, complete closed parts and all generated preimages
before any transaction. Empty native/directory lobby cohort and positive running
native/plugin identities required before the normal official guarded Pi QC-only
restart. Full current on/offbox archives; no restoring old snapshots to force PASS.
No unrelated pending native time-counter/TAS/API/backend activation or blanket
public-main build. Publish qualified release source without discarding separately
pending main work. No Native rebuild/performance/socket/ABI matrix warranted.

Owner acceptance: A->B, B->B and normal close should remove old avatar/slot promptly;
weapon Drop should still work. Do not expect immediate cleanup after crash/network
loss. Actual delivery status belongs to final handoff/receipts, not this source note.
