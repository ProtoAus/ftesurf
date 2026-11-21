# World of Surf 0.1.55 delivery

Published 21 Nov 2026, completing at **10:00 UTC** (21:00 local; worldofsurf-47) from the Linux PC, one sealed
candidate, no rebuild. Lex: "add all the updates and patches in recent and add them all the the latest build, and push
it and them to the release and lobbies please!" -- then "Release + lobbies now" (the backend generation follows).
Page: <https://proto.bar/ftesurf>.

- Version **0.1.55** (QC build 90). Frozen QC `71639cba` = main at the cut (branch `release-0.1.55` in
  release0155-47; tag `v0.1.55`). 7 patch entries (P1694, P1696, P1698, P1700, P1701, P1703, P1704) plus the
  unannounced P1697/P1699/P1702 work on main. P1698's long patch-note point was split at the 250-character limit
  (main 71639cba).
- Progs: qwprogs `7177ed74`, csprogs `f93beacb` (appended to tasrevd codes.txt, backup .pre0155-20261121T100152Z),
  menu `dd955de8`.
- Engine **d42a16515** (patch-1704 records): carries the engine halves of P1694 (controller tag), P1698 (Source sky as
  a hole, entity PVS), P1701 (void overview edge) and P1704 (views over HTTPS; httpq never a gamedir; csprogs may not
  change consent.txt; no server cfg_reset). Windows cross-built in the root's engine worktree (TLS check 0
  plain-address uses); Linux built in the Debian 11 rootfs (BUILDINFO gates all PASS); both stamp
  `git-8977-patch-1698-3-gd42a16515`.
- Launchers unchanged (Windows bootstrap source 8de1339 reused via `-ReuseWindowsBootstrap`, Linux 0.1.7 13e7327).
- Prepared `e13a9a5f786af102bbdf52eb4c63a757efa971afd7ddcc54ea64f151a3dfb13d`; publication record `7db81bba`; live feed
  `1cccf7cb` (prev 0.1.54 `1ec0d586`); 1290 objects. `-MaxTotalMB 130` (stage 128.4 MB).
- The seed from 0.1.54's stage brought back cfg/maps/render_surf_boreas.cfg and render_surf_kvas.cfg, which P1698
  deleted (they set r_sky_forcedepth 1, now the default): removed before prepare (release.ps1 refused them as dirty).

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.55.7z` | 79,335,290 | `a8ba778dc89c0cf166a996061cc8a85fde8a8266f7cb55c0ad331b6550bcb369` |
| `ftesurf-0.1.55-linux-x86_64.tar.xz` | 79,789,964 | `048c2f48a03b269044595e0f57fda1d2c3503218158312833eee33067b17bcfd` |
| `WOS-Launcher-0.1.55.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.55-linux-x86_64` | 4,091,480 | `7add78133cd4fd0ff1d716191c96ec70f4e81d9b1af553fed51401969c1b3bb9` |

## Acceptance

- Preflight PASS (7 patches); preparation gates 1-4 PASS, Linux gates PASS; `-PublishPrepared -DryRun` 1290 objects;
  `-VerifyFull` rc 0 (both archives, launchers and all 1290 objects round-tripped; page and feed served byte for byte);
  release_smoke linux64 1384 / win64 1383 managed files rehashed from the live feed.
- Wine smoke of the Windows stage: game rc 0, engine d42a16515, both screenshots, eye 64 then 28 (winsmoke.sh's own
  exit status is its last line's optional console-dump grep).
- Linux game smoke of the Linux stage: 5/5.

## Lobbies

- 10:02-10:03Z: all 12 lobbies on this release's qwprogs 7177ed74 / csprogs f93beacb (predecessors 8a16f052 / 42970496
  kept as *.pre0155-20261121T100226Z), one 10 s warning and one restart each (tools/deploy0155.sh in the root); 12
  active, 12 listed, no program errors. This carries the lobby halves of P1694, P1698 and P1699.
- NOT yet: the backend (surfd) generation (P1694 runs.pad, P1697 Top 10 page, P1699 no-evidence mark, P1703 journal
  date, P1704 /api/view), then nginx `--view-only`, then the patch-1704 lobby engine and lobby_local.cfg's
  sv_recupload_https 1 (tools/backend-pending.md). Until then controller tags on new-client runs are not recorded and
  views stay on the netchan.

## Scope and limits

Automated checks only; owner check pending (lextest.md). Root `FTESurf-worktrees/release0155-47` keeps qc/dist,
artifacts and inputs until the next release.
