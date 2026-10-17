# P755 — Steam pictures kept on disk and drawn at once

## What was wrong (read in the code and the owner's cache, 2026-10-17)

P715's disk cache (`cl_steampic.qc`) did keep pictures, three ways badly:

- **A copy was good for one day.** The header carries the date it was written
  (`strftime(TRUE)`: LOCAL time, `pr_bgcmd.c:5272`) and a load compared it with
  today's, so every picture was fetched again after local midnight. The owner's
  `data/cache/steampic` held stamps of 15, 16 and 17 Oct.
- **A disk copy waited its turn like a request.** `SteamPic_Frame` took one mark
  per `SP_GAP` (1.5 s), disk or HTTP, and nothing while a request was out; a CSQC
  VM starts empty every map. Measured: 13 pictures took 19.3 s from disk.
- **256 two-hex buckets.** Two marks sharing a key prefix evicted each other.

## Change (client QC only)

- One file per origin+mark SHA256 (`cache/steampic/<key>.txt`). A copy is drawn
  up to `SP_DISKDAYS` (30) days old; one from an earlier day is drawn at once and
  refreshed by a paced ask (`SP_OLD` -> `SP_FRESH`), which keeps it on screen if
  the refresh fails. A 404 deletes that mark's copy. P715 bucket files are still
  read (header key checked first), never written.
- Disk copies load `SP_DISKBURST` (2) a frame, before and regardless of the ask
  pacing, the in-flight request, the strike count and `_steampic_hold`. Only
  asks stay paced, and none goes out in a frame that hit the burst limit.
- Validation and upload moved into `SP_Upload`, shared by disk and HTTP; the
  `SteamPic_Draw`/`SteamPic_Of` contract is unchanged. No new builtin, limit or
  draw path, so released engines run it as they run P715.

## Verified

Three progs 0 warnings, same as the unpatched base. `tools/p755pics.py`, real
client, isolated rig under the rig lock, 13 pictured players on one board:

| Step | P755 | Unpatched |
|---|---|---|
| cold, no cache | 13 asks, drawn 19.3 s | same |
| warm, fresh VM | drawn 1.0 s, 13 from disk, 0 asks | 19.3 s, 0 asks |
| copies a day old | drawn 1.0 s from disk, then 13 refreshes | (bucket layout) |
| one copy 2000-01-01 | 12 from disk, 1 ask | |
| P715 bucket file only | 0 asks | |
| one copy truncated | 1 ask | |

The 1.0 s is the harness's 0.5 s polling, not the client. `vid_restart` ends the
test client on BOTH builds (same exe), so it is not this change (BACKLOG).

One review (state machine and control flow). Fixed: an origin change while a
request was out could file that answer under the new origin or another mark
(the reset now waits for the answer, as before P755); a failed refresh after
`vid_restart` lost a picture that was on disk (a failed ask re-reads the disk);
a 404 left the old copy flashing up for 30 days (it is deleted); disk burst 4
a frame was ~100k builtin calls (now 2, header checked before the body). The
fixes were not reviewed separately. The 404 deletion is NOT exercised by an
arm: a board row carries no mark for a player without a picture, so the client
never asks for one there; only a lobby's `*phash` mark could reach it.

Final run (fixed build, `artifacts/run-subject5` in the task root): every
cache arm above passes as tabled; only the two `vid_restart` checks fail, as
they do on the unpatched build.

## Delivery

Shipped in ftesurf-a2's P751/P753 fleet deploy, 2026-10-17T06:46Z: built from
main `b87c37b` (contains P755 `504d36b`) with P749 `da909c0`/`bca6577` reverted in
that deploy worktree only, at the P749 owner's request. Read back by a2: Pi
qwprogs `e5a29895`, csprogs `4e369446` (`.prev` `aca51849`/`b7d751ee`), all 12
lobbies restarted, a fresh client on 27510 served `4e369446` and drew the board.
Checked separately here: the Pi's and both Windows installs' `csprogs.dat` hash
`4e369446d36623c0` and contain P755's status text; 12 `ftesurf@` units active.
