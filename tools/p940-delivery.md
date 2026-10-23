# P940 development delivery — verified23Oct2026 04:54UTC

Implemented, published, built, installed and live-served are separate checks here.
This was a development progs update, not a release or Build-number change.

## Immutable source and scope

- QC feature:0a7c638296b38670a99039bff82d85b04c8d9238 (published main).
- Engine patch ledger:c057759ad8f976c03822b4a4f89841912f605b4d (docs only).
- Native pin/tag remain P939; no native/plugin rebuild or replacement.
- Only viewmodel presentation, default FOV and local material Foley changed.
  No camera/aim/body, server movement, recorder/collection or evidence semantics.
- Clean baseline8e897d9c reproduced the then-active Pi QW/CSQC and BOTH Windows
  CSQCs exactly. This identified the actual newer serving source rather than
  downgrading it to the older REC13 compatibility control. That older control
  compiled0warnings and retained its server DAT exactly, but was NOT deployed.

## Windows promotion — 2026-10-23T04:44:45.2198033Z

Exact inspected, zero-warning build CSQC DAT/LNO copied to BOTH C:/FTESurf and
C:/FTEQuake. Four destinations hash to the frozen artifact. Existing .prev
versions retained/archived. An acted wrong-predecessor control refused BEFORE
creating a transaction; actual promotion required both prior DAT hashes below.

- Previous CSQC:530589a6506eee68467e82dbd9e7d2def963c4cb8c3a99eab21cba9f25ec2e7f
- New CSQC:aa961fddd4fd74a58921595bb60e88b360e61dadeeb244f6c9da976942bb518b

Before/after hashes prove native executables, all five plugins, QW/MENU DAT/LNO,
protected configs and install metadata unchanged. No owner process was stopped,
and no owner config or player data was edited. Source-stage and destination hashes
are recorded under the owned source-polish-20261022T0746Z artifacts/ root.

The ACTUAL installed new DAT then ran on the installed P939 native pair and a
real dedicated socket, with fresh unset FOV->70, visible USP screenshots and
nonzero bob at260u/s. Same real metal-named floor with four controlled VMT
properties emitted wood_06, metal_grate_08, glass_13 and concrete_ct_08. Two more
concrete cues kept metadata reads12 while hits1->3;135.2u/s walking kept total
calls11. Real map reload reset the database/reads/hits to0. All actors stopped;
the exact owned real-floor override was removed, restoring original absence.
Idle/moving screenshots were inspected: model renders normally, not an ear/feel
or exact CSS-parity acceptance. Earlier motion/lag/FOV81 controls remain valid.

## Pi promotion and cold download — 04:50–04:54UTC

Directory access first refused on LAN and loopback8084; NO force, restart or
Pi swap occurred during that block. It later recovered and all12rows had0players.
Fresh exact predecessor hashes and absence of another staged swap were checked;
existing .prev programs were copied to unique pre940 backups before promotion.

Ran the existing clean-source entrypoint from qc/src with pwsh7:

    ./build.ps1 -Jobs 8 -FteRoot <owned-engine> -QuakeDir <same-qc-root> -Pi

No -Engine, -ForcePi or -NoDeploy. Self-sink prevented unrelated Windows/MENU
replacement. Three VMs0warnings; the script verified12empty rows, upload hashes,
ordinary .prev swap, destination hashes, then restarted all12lobbies successfully.

04:52:52UTC readback:12active units; live and .prev QW are byte-identical:

- QW:a4fb3f183478a460abc98dd1192ef6d2562cb93a873c91990a99890c0ff71f07
- Live CSQC:aa961fddd4fd74a58921595bb60e88b360e61dadeeb244f6c9da976942bb518b
- .prev CSQC:530589a6506eee68467e82dbd9e7d2def963c4cb8c3a99eab21cba9f25ec2e7f

A fresh `tools/pi_lobby_smoke.py` client, with NO local CSQC, joined27510 and
quit normally. Its downloads/csprogsvers/292caad3.dat hashes to the new full CSQC
hash; drawn board9columns/type14, no QC fault, screenshot captured:0failures.
The same exact client DAT is therefore in both Windows installs and served by
the Pi, not merely present in a build folder. Native live-socket feature controls
plus this cold-hash/actual-draw check establish the delivered code path.

## Remaining acceptance and retention

Owner visual/ear acceptance remains PENDING in lextest.md: reconnect, equip a
weapon, walk/turn/airborne, and hear material changes with cl_game_sfx1. No claim
of exact CS:S parity or measured FPS improvement. Actual warp/replay appearance
is not newly tested. No recorder/reader/evidence change or separate release.

Owned source/build logs, frozen artifacts, screenshots, transaction/rollback
receipts and the cold-download rig remain under
C:/FTESurf-worktrees/source-polish-20261022T0746Z. Newly created baseline control
worktree is retired after preserving its generated-artifact evidence. No active
owned actors or maintenance gates remain; earlier task evidence is not cleaned.
