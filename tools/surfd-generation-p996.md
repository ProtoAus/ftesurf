# Backend generation swap: P996 (25 Oct 2026) -- the procedure as run

> **Current P1352 tuple, verified 6 November 2026 at18:42 UTC:** generation
> `9b6cb7c0c48a14994fd08f6012643f668514153c`, collectors84-v1/schema26; exactly
> `simcheck.py` changed, other83 frozen runtime files and separate reader unchanged.
> Activated18:36:12UTC through the existing guarded route;44schemas/eightidentity
> digests/non-churn counts preserved,156bound-file checks and14installed feature
> tests pass. Health is good, primaryOPEN/fallbackCLOSED, shared installer restored.
> Runtime `/srv/nvme/agent-work/ac-cursor-20261106T1747Z/runtime`, primary `state/`;
> retain SAMEroot's `rollback-runtime`/CLOSED `control` for53b94a926f current-data
> rollback, with its installed namespace pins. Do not delete runtime dependencies
> or restore an old DB. See [p1352-simcheck-cursors.md](p1352-simcheck-cursors.md).
>
> **Historical P996 procedure below; not the current live tuple.** P1347 was
> activated 6 November 2026 at11:24:42UTC as generation
> `53b94a926f2a0089cb20e3b5b21808e61fd70a79`, collectors84-v1/schema26.
> Runtime `/srv/nvme/agent-work/ksf78-20261106T1020Z/runtime`, admission `state/`
> under that root; actual launcher/manifest subsequently verified OPEN. The SAME
> root retains CLOSED `rollback-runtime` and `control` for predecessor
> `40bd0587a63cff0f784f24864752f1c4e84a9198`. These are production/rollback
> dependencies, not scratch cleanup targets. Rollback uses CURRENT data through
> the qualified guarded route, never an old database or manual fence reopening.
> See [p1347-ksf-audit.md](p1347-ksf-audit.md) for pacing/control delivery and limits.
> Earlier P1346 activation/current-data rollback remain recorded in
> [p1346-simcheck-recovery.md](p1346-simcheck-recovery.md); its original
> `/srv/nvme/agent-work/ac-resume-20261106-0254` root is also retained history.
> Read the actual current launcher before operations: later generations may
> supersede this dated record. Do not replay the pre-systemd P996 cutover.

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
