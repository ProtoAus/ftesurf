# Patch 1576 claim (ftesurf-31, 16 Nov 2026)

Owner decision 16 Nov: block all injected input. Engine: `in_keyguard` (default 1) drops keyboard messages Windows
does not report as hardware (GetCurrentInputMessageSource), the click/touchpad/key guard cvars refuse map locks
(CVAR_NOTFROMSERVER), and a read-only `in_guard_live` publishes what the engine applies. QC: the ranked profile
reads `in_guard_live` where it exists and demotes a run with the key block off. Root
C:\FTESurf-worktrees\acguard-20261116-c5.
