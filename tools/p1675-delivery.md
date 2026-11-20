# P1675 delivery -- lobby deploy, 21 Nov 2026 (worldofsurf-6f)

Game main 35b19662 (P1675 start lag + worldofsurf-41's P1688 !hide/!show, OK'd by 41), built on Linux with
src/build.ps1 -NoDeploy; qcframes: qwprogs 0 frame globals; csprogs 2 (Line_Alloc holds ln_nath / ln_nat), the same
in the source deployed before (9ccec5dc) -- old (Patch 645 layout), not from this deploy; BACKLOG.

| File | Before (worldofsurf-e3, P1672, 17:55Z) | Live 18:52Z |
|---|---|---|
| qwprogs.dat | 124129386e1d52bc... | d1716e7935dc93844cfd330edcd77701b33362dbf18ab3d41bd024b19192cc00 |
| csprogs.dat | 7efb318d1e572ae0... | 6f3d489bb6bfc5829fbf8868a1bd2987087578a049e1061639cfb5f546057dce |

- Lobby-only: no surfd, crontab, surfd.env or SURFD_TOOLS (worldofsurf-e3's gen1674 had not started; e3 cleared it).
  No cfg changed: run_startlag defaults to 0.06 in the QC; lobby9/10/11.cfg keep `set tournament_enable 1`.
- The lobbies' server engine is patch-1604: run_movetick / run_movetickrate date from Patch 325.
- Procedure (private deploy1675.sh, deploy1645.sh without the cfg leg): predecessor hashes matched, 12 active
  lobbies all in the directory, 0 players, no tournament match; staged hashes checked; csprogs appended to tasrevd's
  codes.txt; 10 s warning; swap with .pre1675-20261120T185128Z backups; ftesurf@1 canary (active, spawned, 0 QC
  errors); 2-12 restarted; readback 12/12 active, directory 12/12, every lobby's new log spawned with 0 QC errors.
- Rollback: copy qwprogs.dat.pre1675-20261120T185128Z and csprogs.dat.pre1675-20261120T185128Z back, restart
  ftesurf@N one at a time.
- Next on top: worldofsurf-9b's P1676-P1685 csprogs (with these hashes as predecessors).
