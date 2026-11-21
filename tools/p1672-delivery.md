# P1672-P1674 delivery: tournament fixes, Tournament tab, pool fold + standings (worldofsurf-e3 / -42, 20-21 Nov 2026 UTC)

Lex's 21 Nov tournament test list ("I tested the Tournaments and they are good!" plus eight items: one map per family
with the Momentum build, variants borrow the Momentum thumbnail, equal bubbles, overlaps, centre text, a proper hold
lock, invisible competitors, no pictures, vote spam, a leaderboard "elo style"), then "publish all the updates to the
servers and to the main so all the updates are pushed". Code: main ac477a4b..9ccec5dc (ENGINE_PATCHES P1672-P1674).

## Lobbies
- 20 Nov 17:55Z: P1672 QC (qwprogs 12412938 / csprogs 7efb318d from main 9ccec5dc), artifacts/deploy1672.sh in
  FTESurf-worktrees/tourfix-20261121-e3, backups *.pre1672-20261120T175438Z. Later peer deploys built on it (6f d560a8ad).
- 21 Nov 01:37:46-01:38:41Z: 0.1.54's exact stage bytes (release commit b7c5dd59: qwprogs 8a16f052, csprogs 42970496,
  already in tasrevd codes.txt from the release) TOGETHER with worldofsurf-41's gated lobby engine patch-1683
  (fteqw-svarm64 1753f9d4, fteplug_hl2_arm64.so 83f0ee16; tools/lobby-engine-p1683-20261121.md; 41's session had ended)
  in one 10 s warning and one restart of all 12 (artifacts/deploy0154.sh). Predecessors 7845911f / 64f12292 / 189b33d5 /
  efc72330; backups *.pre0154-20261121T013746Z and *.pre1683-20261121T013746Z in /srv/nvme/ftesurf-server/game.
- Readback: 12/12 active on the new exe (inode 20991428), plugin mapped, nothing deleted; every lobby answers
  `*version FTE git-8936-patch-1683-1-g723eb5b46`, pm_sourceversion 13; no console errors; tournament_preflight ALL GO.
  A software-GL client (Mesa EGL surfaceless, no compositor) of stage-linux-0.1.54 joined Open Lobby #4: map from the
  mirror, cached server csprogs == 42970496, welcome line, zones crc matched. Not driven: the ahop_coast ladder climb.
- Rollback: in /srv/nvme/ftesurf-server/game cp -p each *.pre0154-/*.pre1683-20261121T013746Z over a .rb name, mv -f into
  place, restart every ftesurf@N. Never roll the sweeper below patch 1630 once mover-13 runs exist (41's record).

## Backend: guarded generation gen1674 (packet FTESurf-private/worktrees/gen1674-20261121-e3, OWNER.md log)
- Primary cd1965f1 (tour91-v1, 91 files) = the live gen1650 f7243132 files with party_lobbies.py 37c26e6d, surfd.py
  033adbf5, tournament_pool.py a2da28ee, tournament_rules.py c1ae2079 from main 9ccec5dc; guard 32af9ea2 unchanged; no
  schema change; fallback = the gen1650 files. The consumer gives `systemctl start surfd.service` 900 s (gen1650 HOLDed
  when the 16-block ExecStartPre chain outlived 250 s; now 17 blocks).
- DB backup /srv/nvme/surfd/data/surfd.db.bak-pre1674-20261120T175713Z (sha256 a7a60ae9...). Lex's Root install
  00:21:16Z (owner-install.sh ea82da3e; backup .owner-backup-p1674-9726ls4z). Independent review token CLEAR (REV
  ec6be03c). Launched 01:24:15Z (a first driver died in the 01:13Z desktop crash before its gate: not launched),
  returned rc 0 01:36:31Z; surfd CLOSED ~12 min. POSTFLIGHT PASS (namespace, native/readers unchanged, crontab 5 rows on
  cd1965f1 + 3 producer rows, 55 tables, /api/tournaments, the ?stats=1 answer). Pending: --mapnew-only after a :28/:58
  run, --mapwatch-only after 06:23Z.
- Live: `GET /api/tournament-lobbies?stats=1` -> 2 rated matches (Proto 1031, 2 wins; Markbeaton54 969);
  /api/tournament-map-pool surf total 639 (was 1104), bhop 399 at tiers 255.
- The NEXT generation: CURRENT = cd1965f1, native 1753f9d4, keep the 900 s start (18 ExecStartPre blocks).

## Story (worldofsurf-9b's P1681, their session had ended)
- 21 Nov 01:42Z: tools/story_push.py --expected-live-sha256 896faf52 (the P1619-P1622 catalogue) put main's story.txt
  (84d58cc6) live; the board serves rev 84d58cc6aa73. Backup /srv/nvme/surfd/data/story.txt.pre1681-20261121T014239Z.

## Client
- 0.1.54 (worldofsurf-9e/-a5, tools/release-0.1.54.md) carries P1672's client half and P1673's menu.
