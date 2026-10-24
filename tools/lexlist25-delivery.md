# Lex's list of 25 Oct 2026 -- delivery record (P973-P984)

Session ftesurf-7e (Claude Code), task root `C:\FTESurf-worktrees\lexlist25-20261024T1740Z`.
Hashes are SHA-256 prefixes. Times UTC, 24 Oct 2026.

## What the list asked, and where it went

| Item | Patch | State |
|---|---|---|
| Friends list in a private (local) game | P975 | live (menu, csprogs) |
| R2 compression, automatic for new maps; the 1 MB/s limit | P981, P983 | live (gateway, r2gzip cron, natives) |
| CS:S/KSF builds get Momentum zones; surf_axiom_css | P984 | 31 builds given on the Pi; mapwatch rule ships with the next surfd generation |
| Story levels / demos / everything on Momentum builds | P980, local move | live; 6 Beta Story levels in BACKLOG |
| r_mirrorworld | P982 | live in both installs |
| host_timescale | P954 (peer, 24 Oct) | already live; nothing new |
| Resume run does nothing / card style | P973 | live |
| sv_cheats movement cvars; list on sv_cheats 0 | P977 | live in both installs |
| Stage toast switch in hud_edit | P974 | live |
| KSF tier in the map info box | P976 | live (tiers.txt) |
| bindlist | P934 (peer) + P979 | live in both installs |
| Paste dialog | P939 (peer, 23 Oct) | already live; nothing new |
| Double-click select-all | P933 (peer) + P974 | live |

## Deployed

- 18:41Z Pi lobbies 1-12: qwprogs cd43fde2 / csprogs 3950fda9 (P973-P976), tiers.txt 1a033e53
  (backup tiers.txt.pre976-20261024T184126Z); both installs the same progs + menu 139a1851 + tiers.
  Lobby smoke 27520: served csprogs = build, board drew.
- 19:36Z, 19:53Z Pi ops: /srv/nvme/ftesurf-ops/r2gzip-7e (OWNER.md, cron 17,47), gateway
  r2gateway.py b5a25027 + gateway.json gzip_state (backups *.pre981-*). Companion surf_beginner_css
  17,958,137 -> 7,175,481 bytes.
- 19:46Z Pi zones: 31 CS:S/KSF builds given Momentum zone files (zones/online + site), receipt in the
  Pi root's tmp/p984-apply-*.log.
- 20:00Z Pi lobbies 1-12: qwprogs 3fc7e8b9 / csprogs 5d03cbd6 (P977 publish fix, P980). Both installs
  got menu 2ccef27b only: their csprogs/qwprogs are a peer's newer local build (6506cb2c, 19:37Z,
  not on main) and were left. hidcheck c62b7e6e on the Pi (game/tools, backup *.pre982-*) and both
  installs. Lobby smoke 27530: pass.
- 20:05Z both installs: ftesurf64.exe / fteqw64.exe 495c188e (git-7826-patch-983-0-g1b2227972),
  fteqwsv64 6a93d8c9, plugins (hl2 6a8995ec, ui_imgui 4f8b0166); .prev = ff8e38e4 (P970). Lobby smoke
  on 27520 with the installed exe: pass. Pi native not rebuilt: nothing here changes a lobby.
- Local, no patch: ftesurf/maps/{surf_fantasy,surf_kairo,surf_disneyland}.bsp (each = the Pi's _css
  build) moved to ftesurf/maps/.old-ksf-20261025/ with a README.

## Not done / limits

- Pi's nginx origin limit_rate stays 1m (sudo); with P981 it is reached only when R2 is down or a
  map is not mirrored yet.
- P984's rule reaches the cron's mapwatch only with the next surfd generation (BACKLOG).
- Six Story/Event levels are Beta maps held at KSF's or an older build (BACKLOG).
- r_mirrorworld HUD cues (strafe bar, trainer, mouse pad) draw world sides (BACKLOG).
- None of it is owner-checked: lextest.md has one line per patch.
