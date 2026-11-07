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

## The reload cost (owner asked, 8 Nov)

Trail_Frame's SLOP_LOADED Trail_Load rebuilt the live line from the whole trail.txt in the answer's
frame -- with a remote ping that is mid-travel. Bench (rig/bench_trail.py, hosted, gettime(1) ms) on
Lex's own trails: 45835 rows (5.7 MB, bhop_monster_jam save012) 300-325 ms, 6416 rows (p90 of 482
trails) 44-47 ms, 1358 rows (median) 10 ms; a press-time cache miss read 76-80 ms on the big one.
Now Trail_Load and Trail_Trim fill tr_raw and the line catches up TR_CATCH (400) rows a frame,
held from drawing until whole (ln_holdslot); Trail_Take only records meanwhile; Trail_Settle finishes
it before rewind, a stop, a stage-box restart and at the raw cap. Bench after: Trail_Load 30-53 / 9-11 /
3-4 ms, catch-up 277-287 ms over 114 frames (~2.5 ms a frame) for the big one, cache miss 3-4 ms (the
file's last 96 KiB). Arm with a 45000-row picture (--bigpic) at 0/150 ms: control froze 318/296 ms
mid-hold with a 60-63 u view lurch; subject one 38-39 ms frame, no lurch.

## Reviews

Three rounds (state/predicates, prediction/fairness, then the catch-up, then the round-2 diff).
Fixed: a held step lost its travel (late test from the hold's press); a second travel after a short
press travel; the first visibility eye reached the server before its hold; a press travel bound an
earlier load's event; stale cached picture after a save sync; a 1 s lead-in let go at a round trip
over 1 s released blind; the settle per save event brought the stall back; a cut last row zeroed the
practice clock; per-frame repaints while catching; a load in a rewind countdown lost its latch; step
key repeats kept the late clock fresh; a held step left the old travel running; the kept early event
could be a step's. Prediction review: release-before-answer agrees tick for tick (load and release
ride ordered usercmds); no new capability (a client can always send its release); the new stat
carries only the player's own cursor folder. P1227's snap was measured on the hosted stringcmd path,
which keeps its answer wait.

## Not done / limits

- Trail_Load still reads the file in one frame (30-53 ms at 45835 rows); BACKLOG.
- The travel's visibility eye starts once the server's answer binds it, so for that round trip
  entities near the travel's start may be missing; the world draws.
- A load right behind an unanswered step, or a blind load, gets no travel (the late start is skipped).

## Final build, measured (rig/round3b.out, subbig3, subfix3 in the task root)

Same rig. Taps and holds at 0/150/300 ms: travel on the press frame, release 1.01-1.02 s / 2.51-2.53 s,
no eye jumps, no frame gaps, no prederr. Lead-in 0: released inside the press frame at 0 and 300 ms.
45000-row picture with hud_trail 1: one 39-41 ms frame at the answer (the file read), no other gap
(holding the whole Line_End to the end of the catch had made a 46-52 ms frame there; it now builds a
step at a time while held). Held step (two saves, hold the second, sl_prev at 0.4 s): the travel ends
on the step press and the view goes to the stepped save (two steps of 150-340 u in consecutive frames:
held body, then the predicted step), the same at every ping; control main: a late travel at 0.17 s
and another at 0.57 s at 150 ms. A held step now gets no travel even on a LAN (its answer reads as
pending a frame: WarpOp_StepPending); before, a LAN step got one.

## Delivery

LIVE 8 Nov 2026 (main e52e01da, fteqcc c24ede65): build.ps1 -Pi, 10 s warning (one player on Lobby 5),
all 12 lobbies restarted on qwprogs 711089de / csprogs 993e0e3f (sha256); live serverinfo on lobbies
1, 6 and 12: fs_savelead 2, *csprogs 0x6aa33429, *csprogssize 0x734d56. tasrevd codes.txt 85 -> 86
lines (backup codes.txt.pre1384). Both Windows installs: qwprogs 711089de, csprogs 993e0e3f, menu
ed59a330 (unchanged), .prev kept; downloads/csprogsvers/6aa33429.dat seeded in both.
