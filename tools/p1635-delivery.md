# P1617-P1635 lobby delivery -- LIVE 20 Nov 2026 00:44Z, Claude Code worldofsurf-ed

Lex asked for the tournament (P1634) rollout to start. The lobbies were still at P1614-P1616 (qwprogs 14f1aa82,
csprogs 9f0ea093, game main 3e4c19f7). This delivery carries every lobby half on main since then.

## What went live

- Progs from game main 9e2c109d (built in FTESurf-worktrees/lobbyui-20261120-ed/p1635, clean at that commit,
  build.ps1 -NoDeploy, pinned fteqcc, 0 warnings):
  qwprogs 0beaf1206394cfa70cbf4de29aca0ae1cee23658cb30f37d20915b4097abfdc5,
  csprogs 2d0320d9c73a88ba8bed5b98c507f720e07cf5d0f116cd56c88a2980430246bf (appended to tasrevd codes.txt, 158 lines).
  Carries P1617 (log flood: the FILESTREAM extension line now appears once per load), P1619-P1622 (EpicOwl's boards,
  chat locations, Splits, Story targets; its own fleet deploy stalled 19 Nov 16:54Z), P1625/P1631/P1632 (worldofsurf-bb:
  missing-content banner, ahop finder/rules, chat emoji), P1634 (tournament QC, OFF: tournament_enable 0) and P1635.
- worldofsurf-bb's P1631 lobby half (their list, 20 Nov): cfg/lobby/mode_ahop.cfg (new) and 236 of the 237
  cfg/maps/map_*.cfg from acc0a569 (all `set sv_maxvelocity`; 233 new files, 3 replaced). HELD: map_surf_not_so_prosurf.cfg
  stays at its live 5000 (main says 3500, KSF's explicit value) until Lex rules (BACKLOG).
- data/mapmeta.txt: bb's 7 P1631 rows (ahop_coast 2->9; bhop_badwater/odyssey 9->2; bhop_bunnyrace/race18 3->2;
  bhop_canals 12->2; bhop_forevertranslucent tier 5->2, mode 3->2) applied to the LIVE file (ac1a21f2, stamp
  20261113101328 -- older than bb's base 4ca73e83); every base row matched, the live stamp kept.
  Result sha256 74aa0bc68c473f1fefcb9ff979979e3508aecb75486e7d0e44e9771fcc6afd48.
- No lobby engine change (fteqw-svarm64 189b33d5 / plugin unchanged; lobbies stay mover 12, which 1633+ clients follow).

## How

FTESurf-worktrees/lobbyui-20261120-ed/artifacts/deploy1635.sh (deploy1616.sh's shape): live predecessors checked
(both progs, mapmeta, no mode_ahop.cfg), directory vouched for all 12 ports (0 players), everything staged and
hash-checked, codes.txt backed up and appended, lobby_announce on 12 ports, 10 s, backups, cfg tar extracted, renames,
ftesurf@1..12 restarted one at a time (00:44:04-00:44:26Z). A first attempt stopped before staging anything (the
predecessor check's `test -e` failed under set -e); nothing on the Pi had changed.

Readback (readback1635.post.txt): 12/12 active, no QC error after each lobby's "Loaded progs", directory 12 rows,
mode_ahop.cfg present, 319 cfg/maps files.

## Rollback

```sh
cd /srv/nvme/ftesurf-server/game/ftesurf && S=20261120T004330Z
cp -p qwprogs.dat.pre1635-$S qwprogs.dat.rb && cp -p csprogs.dat.pre1635-$S csprogs.dat.rb && \
cp -p data/mapmeta.txt.pre1635-$S data/mapmeta.txt.rb && mv -f qwprogs.dat.rb qwprogs.dat && \
mv -f csprogs.dat.rb csprogs.dat && mv -f data/mapmeta.txt.rb data/mapmeta.txt
tar -tf cfg1635-$S.tar | grep -vxF -f cfg1635-$S.existing | xargs rm -f --   # the 234 new files (no links in the list)
tar -xf cfg1635-$S.pre.tar                                                       # the 3 replaced files
```
then restart ftesurf@1..12. codes.txt keeps the new csprogs line (harmless; .pre1635-$S is the old file).

## Not live yet

The tournament backend (guarded surfd generation gen1635, P1634's modules, feature OFF), the map qualification
registry, tournament_enable on any lobby, and the 0.1.49 client release that players need for the TOURNAMENT tab.
