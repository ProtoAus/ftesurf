# P1412: csprogs without per-element array defs (8 Nov 2026, ftesurf-3a + helper)

Lex: "is there any smart 'compression' we can do -- not slowing down the game but saving space?"
csprogs wrote a named global def per array element (132,157 of 161,078 defs; their names 1.90 MB of the
2.24 MB string table) for engine savegames, which CSQC has none of. fteqcc -Fomitarraydefs (engine
600bcd24e, merged e6e14a703) leaves them out, keeping string/pointer/field/function elements (the
loader fixes those up through defs). build.ps1 probes the compiler and passes it for cl_progs.src only.

- csprogs 8,050,298 -> 4,940,606 bytes; defs 161,078 -> 42,652; strings 2,240,804 -> 552,236.
  Statements, functions and globals byte-identical with the flag on and off.
- Compiler 73f9a1a4 (git-8545-patch-1398-3-g600bcd24e) is a drop-in for c24ede65: all three progs
  identical but the version string. Shared copy: C:\FTESurf-worktrees\compilers\fteqcc64-p1412-73f9a1a4.exe.
- Def-table headroom: a scratch float[4000] fails "Too many globals - 165079" without the flag (limit
  163,840 in src/qcc.cfg) and builds at 42,653 defs with it.
- Review: nothing serious (loader readers enumerated; probe checked on both compilers).
- Offline QC VM needs -KeepArrayDefs input (finds arrays by name[0]).

## Delivery

LIVE 8 Nov ~14:35 local: 12 lobbies (3 players warned), qw 5618b824 / cs fa957ba9, main 20eebbfd, all
booted with 0 QC errors; codes.txt 94 -> 95 (.pre1412). Both installs (rig.lock), csprogsvers 1b608f0a.
