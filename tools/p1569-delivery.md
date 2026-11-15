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

## Not live yet

- The surfd half needs a guarded generation (with P1564's TAS board, also pending): Lex installs the new
  generation's sandbox drop-in; then `set lobby_helped 1` in the lobby cfg makes lobbies post helped runs.

## Rework (no schema change)

The guarded transition admits no new schema object, so `run_helpers` is gone: board_rows reads a helped
row's runners from its recording at show time (row_helpers: replay -> replay_file -> rec_runners ->
helpers_of), cached by replay id, path, size and mtime (512 entries). A late or re-filed file is read again.
