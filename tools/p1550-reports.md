# P1550-P1552 -- the story-mode crash, the 8-13 Nov prederror reports, and uploads that stopped

Owner: ftesurf-e7 (Claude Code), 14 Nov 2026. Task root C:/FTESurf-worktrees/reports-20261114 (OWNER.md; arms in
arms/, runs in runs/). Raw reports and crash records stay private (scratchpad copies), never in the repo.

Lex (14 Nov): "see if you can fix the crash, and prederrors ... and if the report system is broken? ... fix that
too so we can have accurate/helpful reports".

## What was on the Pi (read 14 Nov 08:20Z)

- data/crash: 3 records, all Akatosh, 10 Nov, engine patch-1476 (has P1417/P1421): "BZ_Malloc: Failed on
  allocation of 18446744071578836992 bytes", each right after finishing a map while story mode moved to the next
  map's lobby. MetalGio reported the same number on 8 Nov "on every story-mode map switch while downloading".
- data/prederr: 95 files, 39 since the 8 Nov triage (P1394-P1397): Akatosh 14, Proto 15, Markbeaton54 5,
  MetalGio 3, Renga 2, nodsnot 1. 8 of the 35 before 11 Nov arrived with only the lobby's half.
- reportd (F3): one row, the 7 Nov install check. No player reports.

## P1550: the crash is a temp-string table, not a file

0x80FFE000 = 131072 slots (PR_GC_MINTEMPS) grown by doubled+1024 eleven times, 8 bytes a slot, passed to
memalloc(int) and sign-extended (initlib.c PR_ExpandTempStrings; found by a read-only search agent, the
arithmetic checked: 270,531,584 slots, 2,164,252,672 bytes). P1417's file-length reading only matched because its
reproduction built a 0x80FFDFFF-byte file. A VM collects only when PR_ExecuteProgram returns at depth 0; a
longjmp to host_abort (Host_EndGame) out of a menu builtin leaves menu.dat's pr_depth, exitdepth and inmenuprogs
up for the rest of the session (CL_Disconnect frees CSQC, SV_UnspawnServer the server; menu.dat survives). The
one builtin found that can run Host_EndGame inside menu QC: downloadmap -> CL_RequestNextDownload, which during a
signon (cl.sendprespawn) runs CL_LoadModels -- the state of a story-mode switch to a map being downloaded.

Change (engine f1e6a75d5): Host_Frame's host_abort landing unwinds menu.dat (qclib PR_ResetExecution, every frame
to depth 0; Host_Frame is never re-entered, so no menu call is live there) and says so on the console;
downloadmap no longer pumps the queue during a signon (Host_Frame does every frame); the table grows in size_t and
past 32M slots stops with a Sys_Error naming the VM, its depths and collector state, printing one line a step from
4M -- so a future record's console tail names the VM.

Measured (arms/p1550menu.py): test-only builds (never shipped; runs/p1550bin control 53852f89 = the fix without
the MP_HostAbort call, subject ee972d45) make downloadmap("p1550abort") Host_EndGame inside the builtin; the
real menu.dat's `ui_dlmap p1550abort` drives it over stdin (-plugin). Control: Host_EndGame, then the menu's table
grew 261k -> 523k -> 1.05M -> 2.10M slots in 90 s, exit depth stuck at 2 (warning threshold lowered to 2^17 in
both). Subject: Host_EndGame, "menu.dat: the game ended inside one of its calls (depth 2); its call stack is
reset", no growth in 90 s. Both menus answered `ui_dlmap` afterwards. Three earlier cuts measured nothing and
are kept (runs/menu_control..3): a cfg's deferred `ui_dlmap` is an insecure line the menu turns away (P667), and
a test menu.dat's m_draw hook never ran. The real trigger (downloadmap during a signon with the map missing) was
not reproduced; the downloadmap guard is by reading.

## P1551: the prederror reports

Seven of the ten largest player snaps (sodacity 33k, demise 18-19k, mesa 15k, dragonfall 9.5k, zoomathon 7.8k,
colin_blaster 6.5k, borderlands_h 4.1k; 7-10 Nov) are an `!r` (warp op 201): the client predicted the published
destination while the server did not take the op on its command and ran the 0.25 s fallback stringcmd a ping
later; the ops' acks were stale (mesa 39,000 commands, zoomathon 8,800). Lobby 11's log at the sodacity report:
the server's published `!r` destination was the one the client predicted, then "warpop: 202 at command 41416 /
SZ_GetSpace: overflow (1429+2 bytes of 1430) / WARNING: msg overflowed for Akatosh" -- a QW snapshot discarded
whole. P1508 (live on the Pi 11 Nov 19:09Z) names this root cause: discarded snapshots retired unsent stat and
entity records. Lobby logs, all 12: before P1508 995 "msg overflowed" against ~96,000 warp ops (~1%); after it
0 against 18,500 (the old rate predicts ~190). No new code for this class.

Local arms (arms/p1551reset.py, surf_sodacity with its zones, 10 `!r` each): current build 10/10 ops taken, no
prederr over 50 units, at 0 ms, 350 ms/250 fps and 350 ms + 3% loss. The pre-P1508 server (patch-1505) also
passed with 0 overflows: one loopback client cannot raise the overflow, so these arms show no regression, not the
fix -- the log counts are the discriminating measurement.

Reports after P1508 (4): surf_ace (MetalGio, 10.8k: the server parked him at a MOVETYPE_NONE spot ~14 s after
joining with a 221 ms server stall; cause not established), surf_fiellu (nodsnot, 172: `!r` to "your startmark"
7 commands after "back in the start" re-armed it -- the republished destination was still in flight; a residual
race, BACKLOG), surf_null and bhop_1n5an3 (Proto: a save-load release 53 units, before P1544/P1547; a server move
at a bhop start with no client trigger, 376 units -- BACKLOG).

## P1552: uploads that stopped

The 8 empty client halves: one is a disconnect ("Akatosh dropped" 20 lines after the begin; its file holds 14 KB);
colin_blaster's is a retry of the same report 20 s later; the rest show nothing in the lobby logs, and nothing
recorded the client's side. Locally the upload works whole at 0 ms, 350 ms and 450 ms + 3% loss (arms/p1552arm.py:
116-119 KB client halves); 0 of the 4 reports after P1508 is empty (MetalGio's at 449 ms included).

Change (QC dbda9b7f): the lobby writes "== abandoned <why> after chunk K of N" when a new begin supersedes an open
upload, the player disconnects, or 30 s pass with no chunk; the client notes each upload's course (begin, first
answer and its delay, sent, refused, no answer in 10 s), which rides in the player's next report; the triage
prints an "upload:" verdict and those notes. arms/p1552arm2.py at 350 ms: report 1 whole (115 KB, 157 chunks in
55.5 s); report 2 with a disconnect 4 s in ends "== abandoned the player disconnected after chunk 10 of 162" and
carries report 1's notes.

A full report takes ~55 s at 350 ms (one 800-byte chunk a round trip); a map change inside that window now reads
as "no end line". Several chunks in flight would not fit a non-fragmented 1430-byte reliable message: left as is.

Client notes live in CSQC's ring, so they reach the next report only on the same map (3 a map); an upload cut
by a map change gets no client note and reads "no end line" (review B4). The reviewed build's arm needed a
second cut: a snap back onto the spawn was 22 units (under cl_prederr_report's 32) after a blocked walk, so no
second report; the snap is now 240 units up. Rerun: report 1 whole (114 KB), report 2 "abandoned as the player
left (...) after chunk 11 of 161" with report 1's notes.

## Review

One independent reviewer, two lenses (A: control flow and memory safety; B: stored evidence and a hostile
client). No high finding. Fixed (engine ece785175, QC f7798570): A1 inmenuprogs cleared even when the menu VM is
gone; A2 the unwind zeroes a stack that does not add up instead of raising PR_RunError into a dead mp_abort;
A3/A4 the cap's comment (it trips at the step from 16.9M) and message (no "none collected" claim; two other
growth sites stay uncapped, noted); B1 the triage reads only the last line as the lobby's marker (a client chunk
can spell "== end" -- reproduced with synthetic text); B2/B3 the abandon labels cover kicks, timeouts and server
stops, and a begin that may itself be refused. Rendering-independent, not ranked: one round.

## Delivery

14 Nov 2026 (~20:50 local, 09:50Z):
- Engine patch-1550 (ftequakers 8d153a462, tag patch-1550), both installs: exe 796f5019
  (git-8751-patch-1550-0-g8d153a462, one stamp, check_tls_refptr 10 symbols 0 uses; .prev 8aec53e8 = P1548),
  fteplug_hl2 82fd0d3d, ui_imgui de07e2cf; C:\FTEQuake cod cb228506, box3d b3d3f227, ode c44256f6. Smoke: the
  P1548 sky case 0 magenta, all games 0 colour actions. fteqwsv64 and the Pi's server engine unchanged (the qclib
  cap reaches server VMs at their next build). Players get P1550 with the next release.
- Lobbies, all 12: build.ps1 -Pi from deploy/p1552-upload = deploy/p1547-opsave 30a0d41a (the live source; live
  hashes 1ff3e138/ab0e1948 checked first, nobody on) + P1552's two commits; qwprogs f81ae75b, csprogs 9ee96c1d,
  .prev = P1547's pair; all 12 active and spawned, 0 QC errors in the logs.
- Both installs' QC from main + P1552 (src diff = P1552 only): qwprogs c2cfd261, csprogs 5d7c3d30, menu 5b709a6d,
  .prev kept; the lobby csprogs seeded as csprogsvers 984978d9 in both. tasrevd codes.txt 135 -> 137 (.pre1552).

# P1554-P1556 (14 Nov, the same day)

Lex: "that's crazy? why so slow? can it be faster?" and the three leftovers -- chose HTTP via reportd, and
"fix 2, wait on surf_ace".

## P1554: the client half over HTTP

The chunked path is stop-and-wait (one 800-byte chunk a round trip) under a reliable channel that carries
at most ~1.4 KB a round trip anyway (net_mtu 1440; a bigger sendevent can overflow cls.netchan.message, a fatal
disconnect), so ~30 s at 350 ms was the in-game ceiling. Change (d3d7ec82): the lobby's begin writes "token
<32 hex>" into its file header and sends it in "prederr_ack 0"; the client POSTs its whole half as text/plain to
cl_report_url?prederr=<token> (online consent tier; plain text because strreplace stops at 4096 bytes); reportd
stores it as <stem>.client beside the lobby file, once, for a token in the header of a lobby file touched in the
last 15 min; the client then sends a -1 event (the lobby file ends "== http"); any refusal or 15 s of silence
falls back to the chunks. No nginx change (the exact-match /api/report location ignores the query string).

Measured: surfd/test_reportd.py 36/36 (4 new: stored once then 409, no report row, no .part left; refusals
400/404/413 incl. path-like and upper-case tokens and NUL; stale file 404; token outside a lobby header 404).
arms/p1554arm.py at 350 ms with a local reportd: both reports "== http" + .client, triage joins and grades them,
report 2 notes "upload: sent by http in 0.4 s" (local HTTP: over the internet expect ~1.5 s); without reportd
both whole by chunks (~58 s) after "http answered 0 (); sending it in-game".

## P1555: `!r` across a startmark flip

(fa020687) The server flags `!r`'s published angle with WOPD_FLIP when the leg has a usable startmark or a
start-zone save (SV_WarpOpResetMayFlip mirrors SV_MovePrepReset's gates); with the flag the client sends `!r`
blind if a predicted teleport is unacknowledged (tg_teleseq > servercommandframe) or start/stage box membership
differs between pmove_org and the server origin. Measured (arms/p1551reset.py, surf_sodacity, 350 ms/250 fps):
no startmark, 10 resets all to Stage1, no prederr over 50 (the server logged 9 of the 10 ops this run, 10/10 in
sz350; unexplained, not this path); a startmark set ("startmark: set zone 0"), 10 resets land on "your
startmark", predicted. The one 20,000-unit line in that run is a 9 s client freeze during which the server
walked the player into the map's teleport, not `!r`. The flip itself (a fail teleport into the start from a
later stage, then `!r` within a round trip) was not reproduced: the blind decision is by reading.

## P1556: bhop_1n5an3's start (Proto, 14 Nov) -- not established

The lobby's own rows: at command 315 the server moved the player from (-304 -754 64.03), grounded and sliding
on func_door *3 (a touch-opens bhop block, top z 64; doors do not move in FTESurf), to t1 (-256 -384 97) --
trigger_teleport *136's destination, whose brush tops out at z 58, 6 units under the player. Not reproduced
locally on the same map with the same bhop ruleset (cfg/lobby/mode_bhop.cfg loaded): standing on the block's
edge and middle and sliding onto it at two speeds (arms/p1556arm.py) touched nothing. Not tried: the lobby's
zone file (its start zone's teleDest is t1) and run state, and the lobby's arm64 patch-1538 engine. BACKLOG.
