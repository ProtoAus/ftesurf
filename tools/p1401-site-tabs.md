# P1401: the same tabs on every site page (8 Nov 2026, ftesurf-3a)

Lex: "my site having pages without other pages tabs on them, I can't click through to that menu, also
I need like a login button on the main site, or the leaderboard section; ensure all pages have all tabs."

- Public pages: Overview, Leaderboard, Players, Zoning, Anti-Cheat, Download, and a quieter "Log in"
  pill to https://play.proto.bar/admin/ (`.pill-quiet`). The leaderboard also lacked Zoning.
- Admin pages: Fleet, Maps, Runs, Accounts, Reports, Site on every page (Accounts/Run/Runs lacked
  Maps; none had Reports or a way back to the site).

## Delivery

- LIVE 7 Nov 21:43Z (8 Nov local): /srv/nvme/ftesurf-site/static index.html, anticheat.html, zoning.html,
  site.css edited in place by the same script that made the repo edit (backups `*.pre-p1401`
  beside them); reportd's templates/reportd_reports.html in place + HUP of its gunicorn master
  (backup in /srv/nvme/agent-work/report-1391-3a/). Checked: the three pages serve the pill,
  /admin/reports answers 302 to the login, home page header looked at in headless Chrome.
- NOT live: the leaderboard (surfd web/board.html, board.css) and surfd's admin templates. They are
  in the guarded generation's pinned runtime; pi.dev had a successor root of the live generation in
  preparation (ac-reader-next-20261107T170730Z-01a1), so a second generation was not started.
  BACKLOG (screenshots/report entry) asks the next generation to carry them.
- The next site publish (src/release) carries the public-page change from the repo sources.

Rollback: copy each `*.pre-p1401` back over its file (static pages need no reload).
