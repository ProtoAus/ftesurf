# P1643 + P1645 + P1652 + P1657 delivery -- lobbies LIVE 20 Nov 2026 10:18Z, Claude Code worldofsurf-4b

## Lobby QC + config: qwprogs 4a72a384 -> cc68c0e2, csprogs 18e26fa6 -> 8c9fe803, lobby.cfg 7b62a4a9 -> 7b3be3d4

- Built with fteqcc (ftequakers engine/release/fteqcc64, git-8916-patch-1660) from game main 4dcc1ec0, 0 warnings,
  qcframes 0 frame globals: qwprogs cc68c0e21b84157da1c602078d0f5167b459885d23a9c331c4cfb7e9c7c8b6bf,
  csprogs 8c9fe8038ff1a5ed2b6bd52538a3fcd128eedcc29c8f4a5c1378912f4cffbc0f. The arms ran on the same sources built
  by the previous fteqcc (git-8905): the progs differ only in the compiler's version string (24 bytes).
- Carries, besides P1643 (start rest + placement latch), P1645 (input report platform, csprogs), P1652 (lobby.cfg
  `set run_slowclock 1`) and P1657 (bhop/ahop run-up): everything else on main at 4dcc1ec0 -- worldofsurf-ed's
  P1648/P1649 (live since 10:14Z in 4a72a384/18e26fa6) and worldofsurf-4a's P1655 GoldSrc QC (gated on BSP 30;
  confirmed lobby-safe by 4a, first run on the 1604 lobby engine here) and bb's P1641 cl_hud (0.1.49-safe, bb).
- Script: FTESurf-private/worktrees/acfin-20261120-4b/artifacts/deploy1645.sh (deploy1635.sh's shape + lobby.cfg,
  a running-tournament refusal, a one-lobby canary with automatic restore, and a readback). Plan 10:16:18Z: 12
  lobbies, 0 players, 0 matches. Live files swapped 10:17:07Z (backups qwprogs.dat.pre1645-20261120T101633Z,
  csprogs.dat.pre1645-..., cfg/lobby/lobby.cfg.pre1645-...; codes.txt +8c9fe803, 161 lines, backup
  codes.txt.pre1645-...). Canary ftesurf@1 restarted 10:17:09Z: "Server spawned." after "Loaded progs", no QC error.
  The script then stopped (its error count `grep -c` exits 1 on zero under `set -e`; fixed with `|| true`), so
  ftesurf@2..12 were restarted by hand, one at a time, 10:18:21-42Z.
- Readback: 12/12 active; each lobby has "Server spawned." after its last "Loaded progs" and no QC error; directory
  12 rows; live hashes as above; lobby9/10/11.cfg keep `set tournament_enable 1`; tools/tournament_preflight.py ALL
  GO (3 of 3 tournament servers free).
- Rollback: `cd /srv/nvme/ftesurf-server/game/ftesurf && S=20261120T101633Z && cp -p qwprogs.dat.pre1645-$S
  qwprogs.dat.rb && cp -p csprogs.dat.pre1645-$S csprogs.dat.rb && cp -p cfg/lobby/lobby.cfg.pre1645-$S
  cfg/lobby/lobby.cfg.rb && mv -f qwprogs.dat.rb qwprogs.dat && mv -f csprogs.dat.rb csprogs.dat && mv -f
  cfg/lobby/lobby.cfg.rb cfg/lobby/lobby.cfg`, then restart ftesurf@1..12 one at a time (sudo -n systemctl restart).
  That returns worldofsurf-ed's P1648/P1649 lobby build. codes.txt may keep the extra line (an allow list).
  Saves written meanwhile carry a `placed` key; the older progs skip unknown keys.

## Not live

- P1646 (script guard: engine + csprogs): built and tested on Linux, not reviewed; ships only with a release
  (task root, qc5/ and eng/).
