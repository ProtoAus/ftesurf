# Lobby engine deployment — P813 (mover 8), 2026-10-18

Lex: deploy tested fixes to the lobbies ("always yes"); "continue" after the low-memory pause.
Carries ftesurf-89's P812 (already live at 21:12Z) under P813. QC and the plugin untouched.

## Source and build

Engine main `408ab2244` (tag `patch-813`; P812 at `92f020ed3`), sent with
`git -c core.autocrlf=false archive` to `/srv/nvme/agent-work/p813-20261018T2125Z/`; blob
hashes of pm_source.c, pmove.h and net_chan.c equal the commit's. `nice -n 19 make sv-rel
FTE_TARGET=linux CC=gcc BITS=arm64 SVN_VERSION=git-7488-patch-813-0-g408ab2244`: no errors,
no warnings in the P813 files. Native `06fee9ab`.

## Gate (owned overlay of links into game/, port 27619; `pi_gate813.py`)

Every `pm_dettest` line equals the Windows build of the same code (fteqwsv64 `057de43b`) on
bhop_eazy, surf_ace, surf_boreas and surf_colin_blaster_69000, mapcrc and the new
`pinmover` included (pinmover = propmover on all four). `pm_verify`: p492voy.rec PASS
4418, Lex's colin_blaster 0009194 (pin 7) PASS 9194. surf_boreas 0003107 HOLDs
(physents, 18 rows from 1945) on this native AND on the live P812 one, so not P813.

## Swap and readback (`pi_swap813.py`)

Guarded by a fresh empty directory, 12 empty status replies and the live native being
P812's `7c72bbdf`. Swapped 2026-10-18T21:20:26Z; the 12 units restarted one at a time.

| File | SHA-256 | Rollback |
| --- | --- | --- |
| fteqw-svarm64 | `06fee9ab53ab...` | `fteqw-svarm64.pre813-20261018T212026Z` (`7c72bbdf`) |

At 21:21:34Z every unit had a new PID running the new native, the plugin `77d0b11a`
mapped, a UDP status answer, `version` with `patch-813-0-g408ab2244` and
`pm_sourceversion` 8; health ok/12; configs, progs, plugin and the runs/evidence/resume/
saves/receipts trees unchanged by aggregate hash. The sweeper runs the same file. NEVER
ROLL IT BELOW 813: an older verifier REFUSEs pin 8.

## Windows

21:20:08Z: both installs' client `219c737c` (`.prev` P812's `7f8e25fb`), C:\FTEQuake's
fteqwsv64 `c6dbcef3` (`.prev` `3ff93982`), built `-Engine -Full -NoDeploy` from a worktree
at `408ab2244` and copied by hand (the worktree's plugins-rel lacked cod/ode inputs; the
plugins are unchanged, as at P805 and P812).

## Client

`tools/pi_lobby_smoke.py` against 27510 (bhop_ambience) with the installed client
`219c737c`: the downloaded csprogs is the served `b7c29da0`, the board drew (cols 8 type 14),
no QC error, screenshot read (the key strip shows P Player). Failures 0. 2026-10-19 14:30 local.

## Limits

The census behind ENGINE_PATCHES.md 813 stopped at 42 of 57 maps (low-memory reaping); its
probe build is retired (`notes/stopprobe-diag.patch` in the task root rebuilds it).
No human has played on mover 8 yet. An old client exe (0.1.27) on a mover-8 lobby predicts
the old stop where the server now recovers, and is corrected.
