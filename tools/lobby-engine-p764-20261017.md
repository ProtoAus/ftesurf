# Lobby engine deployment — P764 (and P680-P765), 2026-10-17

Lex, after confirming P764 offline: lobby deploys are "always yes". The fleet's native
server had been P679 since 2026-10-12, so this carried every engine patch from 680 to
765 (peers asked: c6 for 758/763, 89 for 765; no objection). QC was not touched.

## Source and build

- Engine main `8f0754006` (P764 code at tag `patch-764` = `31a45ac8e`, P765 on top),
  sent with `git -c core.autocrlf=false archive 8f0754006` to the owned ARM root
  `/srv/nvme/agent-work/rampkick-20261017T1448Z/`; blob hashes of com_bih.c,
  mod_vbsp.c and pmove.h checked on the Pi. `make sv-rel FTE_TARGET=linux CC=gcc
  BITS=arm64 SVN_VERSION=git-7408-patch-765-1-g8f0754006 SVN_DATE=2026-10-18`, then
  `plugins-rel NATIVE_PLUGINS=hl2` with zip from `apt-get download zip` + `dpkg -x`
  under the root (no system install). No warnings in the P764 files.

## Gate (owned overlay of links into game/, port 27619; `artifacts/pi_gate.py`)

Every `pm_dettest` line equals the Windows build of the same P764 code, on five maps,
mapcrc included: bhop_eazy trace f7958b04 mover 3d136f8d srctrace de0ed342; surf_ace
9ba6ebb0 / 2b575b87 / f89ef15d; surf_boreas e6ca2756 / cf92d729 / 765ec7ea; surf_leidenfrost
1d2090da / a8e9c1db / 9a7f00e1; surf_surreal 6d14235a / b41a739d / 62cbc1fe; `proptrace`
de0ed342, 1a212c68, 6e8775e5, 3c2bcd70, 489bdd26 with prop pieces deciding 0, 1, 3, 23
and 33 traces, `propmover` = `srcmover`, libm 5e749b8a and tick 93e8615d on all. So the
convex pieces are built bit-identically on arm64. `pm_verify`: p492voy.rec PASS 4418/4418,
the fleet's surf_boreas 0003107 PASS 3107/3107.

## Swap and readback (`artifacts/pi_swap.py`)

Guarded by a fresh empty directory and 12 empty UDP status replies, and by the live
binary being P679's `30af5da4`. Swapped 2026-10-17T19:36:29Z, then the 12 units
restarted one at a time in one ssh session.

| File | SHA-256 | Rollback |
| --- | --- | --- |
| fteqw-svarm64 | `f25fdd07aef3...` | `fteqw-svarm64.pre764-20261017T193629Z` (`30af5da4`) |
| fteplug_hl2_arm64.so | `f58371241428...` | `fteplug_hl2_arm64.so.pre764-20261017T193629Z` (`babc07f9`) |

At 19:37:38Z every unit had a new PID whose `/proc/PID/exe` is the new native, the new
plugin mapped, a UDP status answer, `version` with `patch-765-1-g8f0754006` and
`pm_sourceversion` 7; health ok/12; directory fresh; default/lobby-local/owner configs,
addon list, installed list, both progs and the runs/evidence/resume/saves/receipts trees
unchanged by aggregate hash. The sweeper runs the same file, so it verifies pin 7 from
the swap on. NEVER ROLL IT BELOW 764 now: an older verifier REFUSEs pins 5, 6 and 7.

## Client

`tools/pi_lobby_smoke.py` against 27510 (surf_kitsune) with the installed client
(`66e7748e`, main + 766): the downloaded csprogs is the served `781a125b`, the board drew
(cols 8 type 14), no QC error, screenshot inspected. Failures 0.

## Limits

No human has played a lobby on this engine yet. The lobbies' QC is still P760's
(csprogs `781a125b`); 758/763's QC is c6's to deploy. The owned root keeps the logs,
scripts and the staged pair; its source and objects are retired.
