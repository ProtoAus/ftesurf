# Patch 1586 claim (ftesurf-31, 16 Nov 2026)

A hook below the journal: the client checks, at journal open and at run end, that the game exe's code in memory
matches the file, that the Windows input functions it calls are unpatched and resolve where Windows put them, and
counts executable memory no loaded module accounts for; the `.hid` names what it finds (notes, never a verdict).
Root C:\FTESurf-worktrees\acguard-20261116-c5.
