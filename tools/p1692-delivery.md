# P1692 delivery -- lobby deploy, 21 Nov 2026 (worldofsurf-6f)

Game main d560a8ad (P1692 retry away time; P1646's csprogs reporting, inert until clients run an engine with
in_script_lapses; worldofsurf-41's P1690 GoldSrc door knockback, inert on lobbies, OK'd by 41), built on Linux with
src/build.ps1 -NoDeploy; qcframes: qwprogs 0 frame globals, csprogs the old Line_Alloc pair (BACKLOG, P1675).

| File | Before (worldofsurf-9b, P1685, 18:58Z) | Live 20:24Z |
|---|---|---|
| qwprogs.dat | d1716e7935dc9384... | 7845911f98812fa4f41c7204a068c1d927d53ff62850cb0f3b11c23e03722a8d |
| csprogs.dat | a49254bdead2f5ec... | 64f122928605c8dc44eb509462bd6e64789639ff630fed356a5b5da66370d7ba |

- Lobby-only, progs only: no cfg, surfd, crontab, surfd.env or SURFD_TOOLS. Lobby server engine patch-1604.
- Procedure as tools/p1675-delivery.md (private deploy1692.sh): predecessors matched, 12 lobbies in the directory,
  0 players, no tournament match; staged hashes checked; csprogs appended to tasrevd's codes.txt; 10 s warning; swap
  with .pre1692-20261120T202249Z backups; ftesurf@1 canary clean; 2-12 restarted; readback 12/12 active, directory
  12/12, every lobby's new log spawned with 0 QC errors.
- Rollback: copy qwprogs.dat.pre1692-20261120T202249Z and csprogs.dat.pre1692-20261120T202249Z back, restart
  ftesurf@N one at a time.
