# P1576 / P1577 delivery record (16 Nov 2026, ftesurf-31)

Owner decision 16 Nov: "block all injects". P1576 drops input Windows reports as made by another program and
keeps a run whose protection was off or lapsed off the ranked board; P1577 lists DLLs loaded from outside the
game and Windows folders in the `.hid`. Root C:\FTESurf-worktrees\acguard-20261116-c5 (OWNER.md).

## What is live

| Where | What | How |
|---|---|---|
| Engine main | 648dfb366 (tag patch-1577), under P1572's dad3668be | pushed by ftesurf-31 |
| Both installs | client exe 4fffcfb1 (C:\FTESurf\ftesurf64.exe = C:\FTEQuake\fteqw64.exe), stamp git-8791-patch-1572-0-gdad3668be; fteqwsv64 a34a3459 | ftesurf-dc's P1572 install, 16 Nov ~13:53 local |
| Both installs | qwprogs 56f3de88, csprogs 92f9604e | ftesurf-06's combined deploy |
| 12 lobbies | qwprogs 56f3de88, csprogs 92f9604e (.prev 52f3c098 / 71f708cf), all restarted | ftesurf-06's combined deploy from main 8b5d560e (P1572 + P1576 + P1582), ~03:18Z |
| tasrevd codes.txt | + 71f708cf (P1573's csprogs) and fc726221 (install-only, 13:53 until the combined deploy); backup .pre1576 | ftesurf-31 |

Checked from the files: both install exes carry `in_keyguard`, `in_guard_live`, `in_guard_lapses`, the
`modules`/`module+` journal lines and the evaluator's refusal text, with one stamp string (16 hits); the lobby
and install qwprogs carry `inguard %g` and the `keys`/`keyguard` words; csprogs carries `in_guard_lapses`.

## Not yet done

- DONE 16 Nov ~07:45Z: `sv_rank_keyguard 1` on all 12 lobbies (release 0.1.47 public 07:33:59Z with engine
  patch-1581, which carries 1576). Set live by rcon on each port and read back "1"; lobby.cfg (main e9b31a30,
  Pi 84cbf035, `.pre-keyguard` kept) carries it across restarts. A run on an older engine (no 8 bit in its
  `.rec` `inguard` line) now reads `keyguard` and does not rank. Undo: rcon `set sv_rank_keyguard 0` + the backup.
- The Pi's tools (hidcheck, reccheck) still read the new `.hid`/`.rec` lines as notes (unknown key/kind);
  they learn them with the next tools deploy. No fault either way (checked against origin/main's readers).
- Owner check (lextest.md): normal play, every key and button works.

## Verification

Rig arms (posted WM_KEYDOWN, origin 0): tools/p1576keys.py 13/13; tools/p1573guard.py --live 8/8, --latch --live
2/2 (the P1573 map-lock fixture locks on the installed engine, not on 1576); P1576 QC on the pre-1576 engine passes
P1573's 8 cases and reads `keyguard` under sv_rank_keyguard 1; tools/p1577journal.py 6/6 (one outside module on the
PC: OBS's graphics-hook64.dll) + control 3/3. test_reccheck 975/0, test_hidcheck 1643/0. Six review rounds
(predicate/threading, config-level completeness, honest players and evidence; each fix re-reviewed): debugger
writes into CSQC, the -plugin stdin pipe and WM_COPYDATA, the low-level hook's keys, UIAccess SendInput and
minimized-window sampling were all found and closed there. `in_dinput 1` crashes the client at input init on this
build and the one before it (BACKLOG).
