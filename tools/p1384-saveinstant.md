# P1384 -- save-load lead-in and tap release start on the press, at any ping

Owner: ftesurf-3a (Claude Code session 5e4b2e2d), 8 Nov 2026. Task root
C:/FTESurf-worktrees/saveload-20261108 (OWNER.md).

## Report

markbeaton54 (via Lex, 8 Nov): "when loading save locs it counts down from 500ms so every time you load
a save it feels stuttery and weird". Lex: players have more than zero latency to the server; it has to
be consistent and instant for them.

## Cause

P1366's travel (the camera runs up the save's own picture into the held save) began on the server's
load event: Trail_Frame's SLOP_LOADED -> SaveLead_Begin, then a wait for STAT_FS_SLLEAD. P1227's tap
release waited for the load's answer too. So at round trip R the view drew the predicted save for R,
said "Loading save", jumped back up the path when the event landed, and a tap let go at R + lead-in.
P1375's countdown then started at lead-in minus R: a 1 s lead-in at R ~0.5 s is the reported "500 ms".
On the Pi's LAN (R ~0) all of it falls in one frame, which is why it looked right there.

## Change

- Server: STAT_FS_SLCURID (208) carries the cursor save's folder number (SV_SaveLocSync);
  fs_savelead is "2".
- Client, on the press (SaveLoc_LoadKey): a predicted load (WarpOp_Load not blind, no step still
  unanswered) or the stringcmd path's SaveLoc_PredictLoad hands its target row to SaveLead_Press,
  which takes that folder's picture tail (SaveLead_Cache: kept from Trail_Save as written, or read
  once as Trail_Load reads it) and starts the travel now. The server's SLOP_LOADED for the same folder
  binds its seq (SaveLead_Begin); its STAT_FS_SLLEAD pose must be within 1 unit of the predicted row
  (SaveLead_Check), else the travel ends at the held position. Another folder, a refusal or a lost
  hold ends it as before.
- A predicted load's release no longer waits for the answer (SaveLoc_LeadDone, rec_sl_pred): load and
  release ride usercmds in order (SV_WarpOpCommand), and the client already predicts both. The
  stringcmd path keeps P1227's answer wait. The countdown no longer says "Loading save" for a
  predicted load.
- A travel the server's answer would start more than SL_LEAD_LATE (0.1 s) after the press is skipped:
  that late start was the jump.

## Measured (tools/p1384lead.py; dedicated server + client, cl_delay_packets; lead-in 1 s)

Control = main 2c102112 (no P1384), subject = this patch. Both: client 674e62fa, server 92327da4.
"travel" = press to the travel's first frame, "release" = press to the frame the hold ended,
"jumps" = eye steps over 30 u between held frames (the load's own teleport shows at 0.02 when the
first held frame still has the old view).

| ping added | control travel / release / jumps | subject travel / release / jumps |
|---|---|---|
| 0 ms tap | 0.03 / 1.05 / 236 u @0.02, 206 u @0.03 | 0.01 / 1.01-1.02 / none |
| 150 ms tap | 0.18 / 1.19 / 239 u @0.02, 233 u @0.18 | 0.01 / 1.01-1.02 / none |
| 300 ms tap | 0.33 / 1.34 / 239 u @0.02, 262 u @0.33 | 0.01 / 1.01 / none |
| 0/150/300 hold 2.5 s | travel 0.02/0.18/0.33, release 2.52 | travel 0.01, release 2.52 |
| lead-in 0, tap | release 0.04 / 0.18 / 0.33 | released inside the press frame (0 and 150 ms) |

Countdown: control's first text "Loading save" then "1000 ms"; subject's first frame "990 ms".
cl_prederror 4 printed nothing in any round of either build, including subject releases sent before
the server had the load (300 ms, and lead-in 0) -- P1227's snap does not come back on the predicted
path. One subject round (sub1 d0) had a 0.22 s frame stall mid-travel; its repeat (sub2) had none and
control rounds had 0.10-0.13 s stalls: machine noise, not attributed.

## Not done / limits

- The SLOP_LOADED Trail_Load (the live line) still reads the save's whole trail file when the answer
  lands; with a remote ping that is during the travel, not before it. Large pictures (5.7 MB, ~50k
  rows on long bhop maps) can cost a frame there. Not measured; BACKLOG.
- The server's visibility eye for the travel (rec_savepos) is accepted once its hold exists, so for
  the first half round trip entities near the travel's start may be missing; the world draws.
- A load right behind an unanswered step, or a blind load, gets no travel (the late start is skipped).
