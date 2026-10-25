# Backend generation swap: P996 (25 Oct 2026) -- the procedure as run

Lex, 25 Oct: "do it, and change the note to publish lobbies, we're in beta, and people can just
reconnect." Live backend now: generation `806d1484e0fbaecdf25e6e45c0ae5ece894e1304` (branch
`backend-gen-p996` = live c35fd034 + P996's surfd.py/social.py), root
`/srv/nvme/agent-work/p996-backend-20261025T0446Z`, fence OPEN since 04:48:30Z (downtime ~2 s).
The P970 root (`knife-resume-01a16c7f/p970-backend`, generation c35fd034) is CLOSED and drained;
retain it (history, backups), nothing launches through it.

## Shape of a code-only generation (same schema)

1. Source: a commit from the LIVE generation's source plus only the change (`git worktree add -b
   ... <live gen>`, apply the patch, run surfd/test_*.py; test_board's 13 schema-22 expectations
   fail on c35fd034 itself). The commit SHA is the generation.
2. Stage (`artifacts/backend/stage.sh` in task root lexlist26-20261025T0113Z, scripts copied to
   `/srv/nvme/agent-work/p996-incoming-20261025T0446Z`): new root with `runtime/` copied from the
   live runtime and the changed files replaced (mode 400), `control/` with the guard and dispatcher
   copied byte-identical and an empty gunicorn.conf.py, a manifest from the live one with paths
   rebound (`make_manifest.py`), then `guard init` (starts CLOSED).
3. Cutover (`cutover.sh`, run detached with setsid nohup): grant for the new closure; SIGTERM the old
   gunicorn master (pidfile /srv/nvme/surfd/surfd.pid); `guard candidate` on the new fence; health;
   receipt (pid, /proc stat field 22, cwd, manifest hashes, schema) and `reopen`; THEN close the old
   fence; regenerate the six stubs in /srv/nvme/surfd with the dispatcher's render_wrapper; rebind
   run.sh and the four guarded cron lines (backups `*.pre996-*`, crontab.before/after in control/).
   If the candidate is not healthy in 40 s the script kills it and starts the old one through
   run.sh -- the old fence stays OPEN until the new server is healthy.

## Traps met

- `/srv/nvme/agent-work` is setgid (2755): new dirs come out 2700 and the guard demands exactly
  0700 (`REFUSED: requires owner-only modes`). `chmod g-s` the root, control and state parent.
- The P970 server was not surfd:app but bootstrap_wsgi -> a sealed witness_wsgi that pins EVERY
  runtime file, surfd.env, the Pi's game/tools readers (hidcheck, reccheck, rcptcheck, recsim,
  heldmeta, ed25519) and the lobby native, re-checked on each gunicorn worker boot (max-requests
  recycles): a reader or native deploy would have failed the next worker. This generation's server
  route is plain `surfd:app` under the same guard (launch still checks the manifest's hashes).
- `momrequests.service` (systemd --user, `momgrab.py --watch-requests`) imports surfd through the
  stub and holds the fence's shared admission lock for its lifetime: the old fence's close drains
  only after `systemctl --user restart momrequests.service` (the new process takes the new fence).
- `guard init` after a refused attempt finds its own empty state dir: remove only that empty dir.
