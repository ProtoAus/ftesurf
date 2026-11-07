# P1391 -- F3 report panel and the report service (reportd)

Owner: ftesurf-3a (Claude Code session 5e4b2e2d), 8 Nov 2026. Root C:/FTESurf-worktrees/report-20261108.

## Ask (Lex)

A report panel people bring up with F3: subject and body, the screenshot shown, hint text asking them to
be specific, map name, save lock, position and anything else useful attached; subject presets such as
Poor performance, Bad rendering, Feature request; read, sort and delete them on the admin site.

## Client (src/client/cl_report.qc)

- `report` (bind f3: default.cfg, and Report_Init once per config when F3 is free, `_report_f3`).
  Takes `screenshot report_<utc>_<n>.jpg` with scr_sshot_compression 60 (the player's value restored in
  the same command buffer) the frame before the panel draws. SCR_ScreenShot does not add the file to
  the engine's file index, so neither fopen nor drawpic finds it: the panel issues `fs_flush` once when
  the shot is not found after 0.3 s. The next map load rehashes (arm: 2386 ms against 3946 ms for the
  first load, hash valid).
- Modal sui panel: subject field, six preset chips (perf, render, bug, map, feature, other; a preset
  fills an empty subject), body wrapped at the box width (512 lines, at most 200 newlines, 4000 chars)
  with placeholder lines, preview + include toggle, a list of what goes with it, Send/Cancel, Tab,
  Ctrl+Enter, Ctrl+V (engine paste prompt), AltGr typing. Fields are printable ASCII. Read-only while
  a report is sending; no answer in 60 s frees Send.
- Send: one JSON object {v, subject, category, body, meta, shot} to cl_report_url
  (https://play.proto.bar/api/report). meta: map, server/addr, origin, angles, velocity, timer, save
  cursor (index/count/folder/ticks), fps (running average), ping/loss, player, *ahash, build, csprogs,
  screen, utc, settings (17 cvars). Strings escaped 1000 characters at a time (strreplace stops at a
  4096-byte result); the shot base64 (<= 1.4 MiB JPEG). The engine hands a 200 reply to QC as code 0.

## Service (surfd/reportd.py, its own unit)

surfd runs as a guarded generation whose runtime file list is fixed, so the report backend is a separate
gunicorn service like zonepub: /srv/nvme/ftesurf-ops/reportd/app, state
/srv/nvme/ftesurf-ops/reportd-state (reports.sqlite3, shots/<id>.jpg), 127.0.0.1:8095, User=proto,
ProtectSystem=strict, MemoryMax=256M. nginx (surfd/report.nginx): `location = /api/report` (POST, 2m,
surfdhid rate zone) and `location ^~ /admin/reports`. Admin pages reuse the admin site's Flask session
cookie (same secret from surfd.env, re-read when the file changes) for login and CSRF.
Limits: Content-Length required (411), 2 MiB; JSON with at most 2000 brackets; subject 1-80, body 4000,
meta 8 KiB, JPEG FF D8 FF ... FF D9 <= 1.45 MiB; per network prefix (IPv4 /24, IPv6 /56) 6/min,
6/hour, 20/day; 300/day globally; 5000 reports or 1 GiB of shots. Admin: sortable list, category
filter, search, detail with meta table and screenshot, delete selected, delete by source tag (an HMAC
of the prefix; the IP is never shown).

## Verified

- Builds 0 warnings x3 (fteqcc c24ede65; build.ps1 now passes -max_strings 4194304: csprogs' string
  table passed the 2 MiB default).
- tools/p1391report.py (hosted surf_dune): against a stand-in, then against a local reportd: a
  124166-byte POST, stored with subject, category, body, player, map, server and its 92394-byte JPEG;
  the client prints "received by the service" and clears the draft. Admin list/item/shot with an admin
  session cookie, 401 without. Panel screenshots looked at.
- surfd/test_reportd.py (30+ cases, each break of the code fails one); surfd's own tests unchanged.
- Reviews: client (13 findings fixed: escaping, stale close timer, late reply wiping new text, line cap,
  wheel, AltGr, F3 repeat, scoreboard/spectator, size note, prefix slashes, repeated names, rebind per
  map, pasted newlines); backend security x2 (chunked bodies, non-finite numbers, prefix caps, parse
  before limits, secret rotation, nested-JSON cost, delete-by-tag scope, selection, bidi characters).

## Limits

- An attacker with many IPv6 prefixes can still use up a day's global cap (BACKLOG).
- surfd's admin nav has no link to /admin/reports until the next surfd generation.
- The report-time fs_flush stays until the engine indexes screenshots (BACKLOG).

## Delivery (8 Nov 2026)

- Game code LIVE from main 2e3333d5 (fteqcc c24ede65, -max_strings 4194304): build.ps1 -Pi, nobody
  on, 12/12 lobbies restarted on qwprogs 0a406f51 / csprogs 61771392 (sha256); serverinfo *csprogs
  0xa36cd845 size 0x757b36. tasrevd codes.txt 87 -> 88 (.pre1391). Both installs the same (menu
  ed59a330 unchanged), csprogsvers/a36cd845.dat seeded.
- reportd staged, NOT yet running: /srv/nvme/ftesurf-ops/reportd/app (reportd.py 2ce39a3f, wsgi
  50a887af, templates), state /srv/nvme/ftesurf-ops/reportd-state (0700). Smoke on the Pi (Flask/
  Werkzeug 2.2.2, gunicorn 20.1, temp state, 127.0.0.1:18095): admin on, a report stored, 401/302
  without a login; stopped and removed. The root step is Lex's:
  `sudo sh /srv/nvme/agent-work/report-1391-3a/install_reportd.sh` (unit pinned to 2e3333d5, start,
  answer check, nginx snippet + include after zonepub, nginx -t, reload; undoes on failure). Until
  then F3 reports answer "the service answered 404" and keep the draft.
- reportd LIVE 7 Nov 21:12Z (UTC; 8 Nov local): Lex ran install_reportd.sh -- unit enabled and active
  (source 2e3333d5, "admin on"), nginx snippet included after zonepub, nginx -t ok, reloaded. From
  outside: POST /api/report {} -> 400 (reportd), GET -> 403, /admin/reports -> 302 to the login,
  /lobbies.json 200. A report with a 92394-byte JPEG through https://play.proto.bar/api/report was
  stored as report 1 ("Install check from Claude (delete me)"), shot file 0600.
- Installer slip: it kept its backup of play.proto.bar.conf INSIDE sites-enabled/, which nginx
  includes (`sites-enabled/*`), so the backup loads as a second play.proto.bar server and is ignored
  ("conflicting server name" warnings; the live file sorts first). Harmless as it stands; moving it
  out needs root (owner step in lextest).

