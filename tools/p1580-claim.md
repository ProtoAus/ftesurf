# Patch 1580 claim (ftesurf-31, 16 Nov 2026)

Backend (surfd sweep + tools/rcptcheck.py): the receipt sweeper checks the server address each receipt signs
against the Pi's own addresses (relayed nonce, plan item 12), and the receipt's key against the account the run is
credited to (ROADMAP 14.3 b). Rides the next surfd generation (tools/backend-pending.md). Root
C:\FTESurf-worktrees\acguard-20261116-c5.
