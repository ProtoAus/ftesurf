# Patch 1577 claim (ftesurf-31, 16 Nov 2026)

Engine: DLL tripwire. The .hid journal notes modules loaded into the game process that are not the game's own or
Windows' (a new dt-0 record kind), and hidcheck reports them as a note, never a fault. Root
C:\FTESurf-worktrees\acguard-20261116-c5.
