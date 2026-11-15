# P1569 helped runs on the segmented board -- delivery (15 Nov 2026, ftesurf-16)

Lex, 15 Nov: a P1567 "with help" run "should go under segmented ... list the complete as '<name of player> +2'
and then slightly colour hint it, and when hovered over, display all the names of the runners."
Task root C:\FTESurf-worktrees\lexlist3-20261115-16.

## What is on main (d9e2161b; reviews 855a1658, 71b3c9ef, bde3c126)

- surfd: style_of already files TF_HELPED+TF_SEGMENT as segmented. submit_run reads a helped run's runners
  from its own recording (rec_runners: header owner, then each `takeover`; outside the write lock, 16 MB),
  stores the others (helpers_of: not the finisher, once each, max 8) in run_helpers by replay id (its own
  table, created idempotently, no schema bump); a non-helped re-filing clears it. board_rows adds `helpers`
  only to helped rows. simcheck stores a pair with a helped run as skip "helped" (admin labels it); recsim
  drops rows before the last takeover. _EVLEAF_OK and the evidence port parse take the copy's letter form.
- Web: " +N" in the foreign accent, every runner in its title. In-game board: " +N" in soft blue after the
  name (fitted), hover lists every runner.
- QC: the takeover keys the run to the receiver's proven account (run_pub, run_own); P1567's copy runid is
  the gift's date-time with the receiver's slot letter in place of the port's 'p' (never collides with
  SV_RecNewId). The lobby still holds TF_HELPED runs (lobby_helped 0).

## Verified

- surfd/test_helped.py 15/15; test_board (TF_HELPED pinned), simcheck suites, test_web pass; test_admin's
  packet count and test_replays' FS_TagArchived fail identically on main (not this patch).
- tools/p1567share.py 20/20 on the delivered build. Reviews: three rounds; round 3 found no defect.

## Delivery

- main bde3c126. Both installs: qwprogs `63013a6e`, csprogs `a2637027`, menu `7833995c` (.prev = P1567's
  `b0d8b93c`/`cfde4c59`); csprogsvers `82602c0` seeded in both.
- build.ps1 -Pi: nobody on, 12 lobbies restarted on qw `63013a6e` / cs `a2637027`, all active, 0 QC errors
  since spawn; tasrevd codes.txt 141 -> 142 (.pre1569). pi_lobby_smoke 27510: PASS.

## Not live yet (superseded: LIVE 15 Nov 09:18Z, below)

- The surfd half needs a guarded generation (with P1564's TAS board, also pending): Lex installs the new
  generation's sandbox drop-in; then `set lobby_helped 1` in the lobby cfg makes lobbies post helped runs.

## Rework (no schema change)

The guarded transition admits no new schema object, so `run_helpers` is gone: board_rows reads a helped
row's runners from its recording at show time (row_helpers: replay -> replay_file -> rec_runners ->
helpers_of), cached by replay id, path, size and mtime (512 entries). A late or re-filed file is read again.

## surfd LIVE (15 Nov 2026)

- Generation backend-15665948 (surfd.py 9e70a287 = main 15665948): primary 6ec84932, fallback 7ab1c10c.
  Waited for pi.dev's native1568 rollout (FINAL STATUS 04:45Z, no locks; native 0200f519 is its result).
- Operator binding (successor/transition/binding) fixed S1-S3 and took 9 review rounds plus a final
  integrity review; harm-class findings were fixed each round. Round 9's one harm-class finding (a cron job
  that is never parked and starts in the ~2 s gap between the last busy check and the close, then outlives
  the 240 s drain, leaves surfd down) is inherited from the shared sequence and was ACCEPTED with a launch
  slot (hh:MM:05, MM in 01/11/16/21/26/31/46/51/56; measured job lifetimes max 12 s; ksfimport parked to
  17 Nov). BACKLOG: park ksfimport and both momgrab routes before the last busy check next time.
- Incident during the binding work: surfd stopped 07:32:55-07:36:04Z because a test run on the Pi reached a
  real `sudo -n systemctl stop`. Restarted on the same generation, nothing else changed. Since then the tests
  guard run/service and Pi test runs use a fake sudo/systemctl/crontab first on PATH.
- Lex ran owner_install.py (c5b2ac72) at 08:42:58Z: three root files and a daemon-reload only, no restart.
- Execute started 09:11:05Z with no players on and exited 09:18:15Z: ACTUAL_TRANSITION_RETURNED,
  completed.json active primary, no hold-records. Admission closed (503s) 09:11:10-09:18:02Z, partly
  up around 09:14. f443f6cf CLOSED; cron 4 lines on the new primary; momrequests (a user unit) restarted
  09:18:04Z on the new stubs; /health and /lobbies.json 200; heartbeats 200 from 09:18:02Z, no tracebacks.
- Lobbies: `set lobby_helped 1` in cfg/lobby/lobby.cfg (main b4379a06; Pi copy fcb68641, .pre1569-20261115T091959Z)
  and set live over loopback rcon on all 12 ports (read back 12/12), no restart. Runs held before this
  were not queued (Lobby_RunBody returns ""), so the first "+N" row is the first helped finish from now on.
- Not yet observed: a real helped run on the live board. Faking one would put a test row on the public
  segmented board, so I did not post one. The path is covered by test_helped (15) and p1567share (20).
