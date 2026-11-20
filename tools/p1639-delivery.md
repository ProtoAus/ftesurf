# Tournaments ON -- P1634 + P1639 backend and switch-on, 20 Nov 2026, Claude Code worldofsurf-ed

Lex asked for the rollout ("please start the process!", then "switch it on and get it working please!"). Lobbies had
P1635 since 00:44Z (tools/p1635-delivery.md) and 0.1.49 was published at 05:12Z (tools/release-0.1.49.md).

## What went live

- **Backend, guarded generation gen1635** (packet FTESurf-private/worktrees/gen1635-20261120-ed, OWNER.md log).
  - Primary `ef0d1c7c` (guard profile tour91-v1, 91 files): the live 806b8c35 files with surfd.py plus P1634's 36
    lines, and the four added modules party_lobbies / tournaments / tournament_rules / tournament_pool at game
    448c6832. Fallback `0e525eca` = the old 87 files.
  - Nine tournament tables were created by hand at 00:53Z (46 -> 55, user_version 26).
  - Timeline: Lex's Root install at 04:34Z; an independent review token came back CLEAR; launched 05:54:15Z;
    returned rc 0 at 06:05Z; POSTFLIGHT PASS.
  - surfd.py is otherwise the live file: **P1615 and P1622 are still pending** (backend-pending.md).
- **Switch-on**, 06:06-06:11Z, artifacts/enable1639.sh in FTESurf-worktrees/lobbyui-20261120-ed.
  - Registry installed at /srv/nvme/surfd/data/tournament-qualifications.json.
  - surfd.env gained `SURFD_TOURNAMENTS=1` and `SURFD_TOURNAMENT_QUALIFICATIONS=<that path>`. Backup:
    /srv/nvme/agent-work/enable1639-ed/surfd.env.pre1639-20261120T060646Z. It lives outside /srv/nvme/surfd, whose
    files the drop-in lists one by one.
  - surfd was stopped and started: down 06:06:52-06:10:50Z. The guarded startup's ExecStartPre checks take about
    4 minutes.
  - `/api/tournaments` answers `enabled:1`.
- **Lobbies**, 06:11:35-48Z.
  - qwprogs `47745243` (0.1.49's, = main 448c6832's QC); csprogs `2d0320d9` unchanged.
  - `set tournament_enable 1` appended to lobby9/10/11.cfg.
  - Backups `*.pre1639-20261120T060646Z`; 10 s warning, then ftesurf@1..12 restarted one at a time.
  - Readback (artifacts/readback1639.post.txt): 12/12 active, no QC error since load, directory 12 rows.
  - `/api/tournaments` slots: p27590 / p27600 / p27610 (Open Lobby #9-#11).
- **Map registry**, 06:14Z, swapped without a restart (surfd reads it on each request): 1509 maps.
  - `/api/tournament-map-pool` over all tiers: surf 1104 qualified / 1 unqualified at tick 15000; bhop 405 / 9 at
    tick 10000.
  - Qualification runs, Pi root /srv/nvme/agent-work/tq1635-ed:

    | Run | Window | Result |
    |---|---|---|
    | surf | 01:00-04:08Z | 1071 valid + 3 reused; 30 lost to the qualifier's MAX_MOD_KNOWN |
    | bhop | 04:39-05:44Z | 397 valid; 8 lost the same way |
    | fixup | from 06:05Z | 38/38 valid with 76429c23's recycling tool |

  - Six real refusals stay out of the bhop pool: the lobby runs them as bhop-hl1 (df_kool_haster03,
    kz_8b1_hellinashop, kz_bhop_avantura), df-cpm (df_kool_rs) or df-vq3 (df_ori-dorado, df_zeel-recapture).

- **Public routes**, 06:24:11Z (Lex ran the owner command). Until then the 0.1.49 menu got nginx 404 on
  play.proto.bar and hid the tab: P1634 never added its routes to nginx's allowlist.
  - `/etc/nginx/snippets/surfd.conf` = the live file (baea834f) + four exact locations (sha 4b6edb0d):
    `/api/tournament-lobbies` and `/challenge` (GET), `/action` (POST, 8k body), `/api/tournament-map-pool` (GET).
    Zone surfdboard; X-Real-IP as /api/board; no-store.
  - Kept off the internet: `/api/tournaments/game` (the lobbies' keyed route), `/api/tournaments` and `/api/heartbeat`.
  - Tested first with the Pi's nginx 1.22.1, unprivileged on 127.0.0.1:18639 (/srv/nvme/agent-work/enable1639-ed/
    nginxtest): menu routes reached surfd, wrong verbs 403, the closed routes 404, the board 200, a 9000-byte action 413.
  - Installed by artifacts/install-tournament-routes.sh (7998580d: predecessor and staged hashes, backup
    `surfd.conf.pre1639-20261120T062411Z`, nginx -t, reload). Public check: 200 200 200 404 404.
  - The repo copy surfd/surfd.nginx carries the same block.

## Rollback

- **Feature off.** Restore the surfd.env backup above (or delete its two SURFD_TOURNAMENT* lines), then
  `sudo -n systemctl stop surfd.service && sudo -n systemctl start surfd.service` (about 4 min).
- **Lobby side.** In /srv/nvme/ftesurf-server/game/ftesurf, put back `qwprogs.dat.pre1639-20261120T060646Z` (= P1635
  0beaf120) and `cfg/lobby/lobby{9,10,11}.cfg.pre1639-20261120T060646Z`, then restart ftesurf@1..12.
- **Public routes.** As root: `cp -p /etc/nginx/snippets/surfd.conf.pre1639-20261120T062411Z
  /etc/nginx/snippets/surfd.conf && nginx -t && systemctl reload nginx`.
- **Backend code.** Only a NEW guarded generation. Never replay the execute, restore the DB, or delete the gen1635 /
  gen1622 roots.

## Known

- `Tour_Reply` calls `find()` with the empty pending token on every state poll. In server9-11.log that prints
  "PF_FindString: empty string" plus a trace under developer 1; the behaviour is correct. A small QC patch is
  queued (BACKLOG).
- With the feature OFF or ON, P1634's surfd.py writes `lobby_handoffs` on every ordinary join (additive; reviewer
  note).
- A zone republish or BSP change takes that map out of tournaments, and a match drafted on it aborts at arrival.
  Re-run the qualifier (incremental), then reinstall the registry; no restart is needed.
- Postflight's functional mapwatch/mapnew grading waits for their next runs (06:23Z / 06:28Z).
- In-game check: two accounts, in `lextest.md`.
