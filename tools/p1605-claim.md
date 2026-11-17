# Patch 1605 claim (Claude Code worldofsurf-ed, 18 Nov 2026)

Linux 0.1% lows: the QC tempstring collector's start copies the whole QC hunk and slot table on Linux every
collection (~1.0 ms on surf_beginner, ~2.0-2.4 ms on surf_fairy; one collection every ~1.5 s at 1000 fps), because
P1481's incremental copy uses Windows' MEM_WRITE_WATCH only. Port it to Linux with userfaultfd write-protect
(WP_ASYNC) + the PAGEMAP_SCAN ioctl (kernel 6.7+; unprivileged via UFFD_USER_MODE_ONLY); older kernels and
sandboxes keep the full copy. Engine qclib (initlib.c, progsint.h). Root FTESurf-worktrees/lows5-20261118-ed.

## Status (18 Nov 2026): claimed, in progress.
