# Patch 1605 claim (Claude Code worldofsurf-ed, 18 Nov 2026)

Linux 0.1% lows: the QC tempstring collector's start copies the whole QC hunk and slot table on Linux every
collection (~1.0 ms on surf_beginner, ~2.0-2.4 ms on surf_fairy; one collection every ~1.5 s at 1000 fps), because
P1481's incremental copy uses Windows' MEM_WRITE_WATCH only. Port it to Linux with userfaultfd write-protect
(WP_ASYNC) + the PAGEMAP_SCAN ioctl (kernel 6.7+; unprivileged via UFFD_USER_MODE_ONLY); older kernels and
sandboxes keep the full copy. Engine qclib (initlib.c, progsint.h). Root FTESurf-worktrees/lows5-20261118-ed.

## Status (18 Nov 2026): merged -- engine main ae43b1c24 (tag patch-1605). Installed on the Linux PC's game
(~/Projects/WorldofSurf/ftesurf: ftesurf64 ea2d5414, fteqw-sv64 484e2cdd, git-8855-patch-1605-0-gae43b1c24). Windows
binaries unchanged (the Windows path is byte-for-byte the same code). The lobbies' server engine picks it up with the
next Pi engine build (the NanoPi's kernel decides: below 6.7 it keeps the full copy).

Verified: pr_gc_writewatch 2 on client and server, 0 differing bytes over ~460 checks; a mutant is caught; userfaultfd
refused by seccomp falls back; quiet A/B on surf_beginner (3 a side): slowest collector phase 1.25 -> 0.24 ms, 0.1%
428 -> 463 fps. One review round (kernel 6.7/6.8 fast path, forked server child, ioctl probe, page size: all fixed).
Record: engine ENGINE_PATCHES.md "Patch 1605". What it leaves: BACKLOG "Linux 0.1% lows (lows5)".
