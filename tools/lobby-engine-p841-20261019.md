# Lobby and install deployment — P841 (zone-file speed caps, trusted ruleset reads), 2026-10-19

Lex 19 Oct: "use momentums", "who cares if they are faster, do it", publish carries the cap ("why
not?"). Deploy order per the review: QC first (Multi-Session stamps the cap), then the native.

## Source and builds

ftequakers main `67b4f252a` (merge of P841 `a1a7ca4c7`, tag `patch-841`, with 843-845 `b02bc5ae8`);
FTESurf main `6c006453` (P841 `3cf01777` + records, on 843-845 `4569d279`). Stamp
`git-7531-patch-841-0-ga1a7ca4c7` (one string per binary).

| Binary | SHA-256 | Built |
| --- | --- | --- |
| fteqw64.exe (client) | `50191398...` | worktree, make m-rel, ARCHLIBS given |
| fteqwsv64.exe | `e08989ee...` | worktree, make sv-rel |
| fteqw-svarm64 | `05006df6...` | Pi `/srv/nvme/agent-work/zonecap-20261019T1612Z`, sv-rel arm64 |
| qwprogs.dat / csprogs.dat | `10eac633...` / `e2b7936e...` | build.ps1 -Pi from 6c006453 (841 + 843-845) |

## Gates

- tools/p841caps.py (dedicated, seven maps, planted files) subject PASS and the patch-816 control
  PASS on the final exe and the combined QC; cfg/test/p841editor.cfg 18/18; surfd/test_zonepub 50/50.
- Pi gate (`pi_gate841.py`, new native against the live patch-816 `26e5b189`, owned overlay, port
  27619): pm_dettest equal on bhop_eazy and surf_ace; surf_boreas and colin_blaster differ only by
  the cap -- the crossover (`pi_gate841x.py`, each native at the other's cap planted before spawn)
  reproduces the other's mover hashes exactly. pm_verify PASS on both natives: colin_blaster 9194
  (cap 5000, maps/zones/local), surf_demise 3140 (5000, Momentum mount), bhop_sandtrap 5136 (10000).
  bhop_eazy still loads cfg/lobby/mode_bhop.cfg (6 cvars). No ruleset refusal on any lobby map.

## Deploy (UTC)

- 17:51 build.ps1 -Pi: 12 lobbies, nobody on; qwprogs/csprogs swapped (.prev kept), all restarted.
  Same three .dat in both Windows installs (C:\FTESurf by hand, .prev = 68's b69cae2b/d08cf6ff;
  C:\FTEQuake by the build), csprogs seeded in both.
- 17:52 C:\FTEQuake fteqw64.exe 50191398 (.prev ff0f0a2d) and fteqwsv64.exe e08989ee (.prev
  100ef138). C:\FTESurf\ftesurf64.exe was in use (a plain launch at 17:50, Lex's); a watcher
  installs 50191398 with .prev once it has been closed for a minute.
- 17:52:26 `pi_swap841.py`: guarded by an empty fleet and the live native being 26e5b189; rollback
  `fteqw-svarm64.pre841-20261019T175226Z`. 17:53:40 every unit a new pid on 05006df6, plugin
  77d0b11a mapped, UDP status, `version` patch-841-0-ga1a7ca4c7, pm_sourceversion 8; health ok/12;
  cfgs, plugin and the runs/evidence/resume/saves/receipts trees unchanged by aggregate hash.
- Live read: lobby 27610 moved to surf_apollo over loopback rcon (empty): `sv_maxvelocity` 10000,
  `movement` per-map maps/zones/online/surf_apollo.json, maxvel 10000/axis.

## Not done

- No client connect (tools/pi_lobby_smoke.py): Lex's game was running on this PC. Served-csprogs
  check owed.
- The zonepub service's validator change (maxVelocity bounded, refused by name) needs Lex's sudo:
  `tools/install_zonepub.py --upgrade` (dry run as proto first). The editor never sends an
  out-of-range cap meanwhile.
- NEVER ROLL THE SWEEPER BELOW 813 (see AGENT_NOTES); 841's rollback copy is patch-816.
