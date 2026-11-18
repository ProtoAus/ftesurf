# P1614-P1616 delivery -- lobbies LIVE 18 Nov 2026 17:57Z (19 Nov AEDT), Claude Code worldofsurf-15

## Lobby QC: qwprogs 3495dc51 -> 14f1aa82, csprogs 6495ce80 -> 9f0ea093 (game main 3e4c19f7)

- Built with fteqcc (ftequakers engine/release/fteqcc64) from main 3e4c19f7 in FTESurf-worktrees/asks-20261119-15/qc,
  0 warnings: qwprogs 14f1aa827cdc5491300d536eaa827426dda8b300fe98ae2a94dfdc6763323236,
  csprogs 9f0ea093f5ef862ccaa33d47c0bb98b1ecf13de42bfe092b3fefeeadb3a6eb33.
- Carries, besides P1614 (prederror caps), P1615 (TAB-board `segs` tooltip; inert until surfd sends `segs`) and
  P1616 (look store data/looks/, knife -> lobby_master): P1613's recorder (38298aeb, worldofsurf-58's request:
  `cseq` records, header `cmdseq 1`) and P1608/P1612's csprogs changes, on main since the previous lobby build but
  never deployed.
- Script: artifacts/deploy1616.sh in the task root (lex-90's deploy-step2.sh shape): live pair checked as the
  expected predecessors, .new hash-checked, csprogs appended to tasrevd codes.txt (backup codes.txt.pre1616-S),
  lobby_announce on 12 ports, 10 s, copies qwprogs.dat.pre1616-20261118T175700Z / csprogs.dat.pre1616-20261118T175700Z,
  mv -f, ftesurf@1..12 restarted one at a time (1 player on). `.prev` (lex-90's P1603 rollback) left as it was.
- Readback: 12/12 active, ActiveEnter 17:57:33-17:57:58Z, directory 12 rows, no QC error after any lobby's last
  "Loaded progs". P1616 live check (a linked player's "look: ... loaded|saved" lines) waits on Lex (lextest).
- Rollback: `cd /srv/nvme/ftesurf-server/game/ftesurf && cp -p qwprogs.dat.pre1616-20261118T175700Z qwprogs.dat.rb &&
  cp -p csprogs.dat.pre1616-20261118T175700Z csprogs.dat.rb && mv -f qwprogs.dat.rb qwprogs.dat && mv -f
  csprogs.dat.rb csprogs.dat`, then restart ftesurf@1..12. data/looks/ can stay (an older lobby never reads it).

## This PC's install (~/Projects/WorldofSurf/ftesurf, at main 3e4c19f7)

- wos-build.sh: qwprogs 14f1aa82, csprogs 9f0ea093, menu.dat b71575aa (P1615's menu tooltip). Previous files in the
  task root's artifacts/install-prev1616/ (qwprogs e073eecc, csprogs b100034b, menu 2b0597ec).

## Not live

- P1615's surfd/web part: next guarded generation (tools/backend-pending.md).

## Found on the way (not changed)

- Every lobby log grows ~3 KB/s with "Extension FTESURF_QC_FILESTREAM_HASH is supported": FS_StreamFiles()
  (sh_streamfile.qc) calls checkextension on every use, sv_archive_stream.qc does so per frame, and the engine
  Con_DPrintf's each answer at the lobbies' developer level. Since the P1604 lobby engine (17 Nov 21:34Z), when the
  extension became supported. server1..12.log were 1.1-2.1 GB each on 18 Nov 18:00Z.
  Fixed in P1617 (tools/p1617-claim.md), QC only, for the next lobby restart.
