# P1645 -- the input report's platform (20 Nov 2026, worldofsurf-4b)

csprogs only: `src/client/cl_replay.qc` `Rec_IsWin`, used by `Rec_InputCvarWin`.

Before: the Windows-only settings (in_rawinput and the guard cvars) were reported only while `sys_platform` read
"Win". That cvar has no read-only flag, so a Windows game whose owner changed it reported like the Linux game.
Now a read-only `in_guard_live` (the Windows engine's own cvar since 1576) also means Windows.

Measured, Linux rig (headless server + client, engine as installed 20 Nov), `cmd timer`'s lines:

| Build | sys_platform | inprof ev | plat |
|---|---|---|---|
| main | Linux | "14 0 0 0 1 0" | wouldplat 1 |
| P1645 | Linux | "14 0 0 0 1 0" | wouldplat 1 |
| main, launched `+set sys_platform Win` | reads "Win" | "14 0 0 0 1 0" | wouldplat 1 |
| P1645, launched `+set sys_platform Win` | reads "Win" | "14 0 0 0 1 0" | wouldplat 1 |

So nothing changes for a Linux game, and the cvar is settable from the launch line.

NOT measured: the Windows half (no Windows game on this PC). It rests on code and on live behaviour:
- `set` returns "variable ... is readonly" for a CVAR_NOSET cvar before it touches the flags (engine common/cmd.c),
  and Cvar_Register replaces a cvar the launch line pre-set with the engine's own struct and flags (common/cvar.c),
  so `in_guard_live` reads read-only on every Windows engine from 1576 whatever the player typed.
- The live keyguard rule (sv_rank_keyguard 1, since 16 Nov) already ranks a Windows run only when csprogs sees
  `in_guard_live` as engine-made and read-only, so every ranked Windows run since then has had that flag.
- For a Windows game that has not changed sys_platform, Rec_IsWin is true by its first test, as before.
A Windows engine older than 1576 has no `in_guard_live` and can still report as Linux; it cannot rank as Windows.
Owed: one Windows check (set sys_platform, join a lobby, `cmd timer` should still show `have` with the raw bit).
