# surfd - FTESurf lobby directory

Minimal Flask + SQLite lobby directory. Game servers POST heartbeats; the
game menu GETs a list of live lobbies.

**THIS DIRECTORY IS NOW THE SOURCE; the Pi holds a deployment.** Until it was
pulled into the repo, surfd existed only at `/srv/nvme/surfd` on the NanoPi --
no backup, no history, no review -- and the admin panel is about to give it a
login and shell-adjacent controls. Edit here, deploy from here, and never edit
the Pi copy in place.

    surfd/                      (this repo)          -> /srv/nvme/surfd/ (Pi)
      surfd.py          the app
      surfd.env.example the shape of the secret file, with no value in it
      test_surfd.py     the falsifier for the address derivation (see below)
      run.sh            start under gunicorn, detached
      stop.sh           stop it
      surfd.service     systemd unit  -- INSTALLED and enabled (see below)
      surfd.nginx       nginx snippet -- NOT INSTALLED (deliberate)
      admin.py          the fleet control panel, a blueprint at /admin
      rcon.py           the panel's only channel to the game servers
      templates/        the panel's two pages
      mkadminpw.py      generates the panel's credentials
      admin.nginx       the panel's OWN nginx block -- NOT INSTALLED
      surfd-admin.sudoers  a record of the systemctl grant (already installed)
      play.nginx        the public vhost for play.proto.bar -- NOT INSTALLED
      setup_public.sh   installs that vhost + TLS, then the advertise switch
      test_admin.py     the falsifier for the panel
      server/           the three game servers' scripts, from
                        /srv/nvme/ftesurf-server/ (run.sh, runall.sh, stopall.sh)

Not in the repo, and must never be -- `*.env` in the tree's `.gitignore`
enforces the first one:

      surfd.env         shared secret, mode 0600 (SURFD_KEY=...)
      data/surfd.db     SQLite store
      logs/surfd.log    app log (rotating, 2MB x 5)
      logs/gunicorn.log gunicorn stdout/stderr
      surfd.pid         gunicorn master pid

## Running

    /srv/nvme/surfd/run.sh     # start (idempotent)
    /srv/nvme/surfd/stop.sh    # stop

Listens on 0.0.0.0:8084. No venv, no pip: system python3 3.11.2 with
python3-flask 2.2.2, python3-werkzeug 2.2.2, gunicorn 20.1.0.

## API

POST /api/heartbeat   (application/x-www-form-urlencoded)
    key      shared secret; 403 if wrong or missing
    node     opaque server id, <=64 chars, upsert key
    map      map name, <=64 chars
    players  0..64   (clamped)
    max      1..64   (clamped)
    port     1..65535 (rejected with 400 if outside)
    name     <=64 chars
  -> 200 "ok"

The lobby address is `<source IP>:<port>`. There is no address field, and
X-Forwarded-For is not trusted, so a heartbeat cannot advertise a lobby on
another host.

### The one exception: SURFD_PUBLIC_HOST

surfd and the three game servers run on the same Pi, so `REMOTE_ADDR` for a
heartbeat is *structurally* private -- `192.168.1.102`, or `127.0.0.1` once
nginx is in front. Left alone, a public deployment therefore advertises a LAN
address to the whole internet and every row is unreachable. No game-side change
can fix it: the heartbeat deliberately sends no address at all.

    SURFD_PUBLIC_HOST=play.proto.bar
    SURFD_TRUSTED=127.0.0.0/8,::1/128,192.168.0.0/16,10.0.0.0/8   (the default)

A heartbeat **from a trusted source** is recorded at `SURFD_PUBLIC_HOST:<port>`.
Everything else keeps its own source address, exactly as before.

Note the trust direction, because it is the whole design: the **operator's own
config** supplies the public name, and the **socket** only decides whether this
heartbeat came from the operator's machine. The request body is still never
consulted for a host -- that is what would let a stranger advertise a lobby on
somebody else's machine, and it must stay impossible. What a stranger with a
valid key can still choose is the *port* half of their own address; the
client-side mitigation for that is the `lobby_hosts` allow-list in the game
menu, not anything here.

`SURFD_PUBLIC_HOST` is validated at start: a scheme, a port, a path, a space or
a name longer than the 64-character address the game menu accepts is logged and
ignored, falling back to today's behaviour rather than emitting rows nobody can
connect to. **Unset (the default), this file behaves exactly as it did before
the option existed** -- which is what `test_surfd.py` proves:

    SURFD_HOME=/tmp/surfd-test python3 test_surfd.py

Eighteen checks, and the two that matter most are the two that must NOT change:
an untrusted source still keeps its own address, and with the option unset
nothing changes at all.

Note that `SURFD_PUBLIC_HOST` and `SURFD_TRUSTED` are read from **the
environment first and then `surfd.env`**, because `surfd.service` has no
`EnvironmentFile=` line — so a value placed only in `surfd.env` used to be
ignored in silence. For `PUBLIC_HOST` that would have meant advertising a LAN
address to the internet at the exact moment of going public, with nothing
logged, because "unset" is a valid configuration. Also note that **present-but-
empty is not absent**: `SURFD_TRUSTED=` means "trust nothing", and collapsing
that into "use the default" would silently re-enable the rewrite the operator
just turned off. Both are checked.

GET /lobbies.json
    {"v":1,"t":<unix>,"lobbies":[{"map":...,"players":...,"max":...,
                                  "addr":"IP:PORT","name":...,"age":<sec>}]}
  Only lobbies whose last heartbeat is younger than 30s.
  Sorted by players descending, then map ascending.
  Always a JSON object with a lobbies array, even when empty.

GET /health
    {"ok":true,"lobbies":<live count>}

## Limits

  * 30s liveness window; rows reaped after 1h.
  * At most 200 distinct nodes stored; a new node beyond that gets 429.
  * 60 heartbeats/minute per source IP; over that gets 429.
  * Request body capped at 16 KiB.
  * Strings stripped of control characters and truncated to 64.

## Admin panel (/admin)

A fleet control panel: live map, uptime, player list, rotation, hostname,
announce, kick, and start/stop/restart for each lobby, plus the directory's own
table and a log tail. **Off unless configured** -- with `SURFD_ADMIN_HASH`
unset, surfd registers no `/admin` routes at all and behaves exactly as it did
before the panel existed. `test_admin.py` asserts that first, because "off by
default" is a claim until something checks it.

### Turning it on

    cd /srv/nvme/surfd && ./setup_admin.sh

One step. It prompts for a password (hidden, twice), hashes it, generates the
session secret, copies the lobbies' `rcon_password` out of `cfg/lobby.cfg` so it
is never typed, rewrites only its own three lines in `surfd.env` (backing the
file up and never touching `SURFD_KEY`), restarts surfd and checks `/health`.
Re-run it to **rotate** the password — it replaces its lines rather than
appending a second, shadowed copy.

`mkadminpw.py` is still there and does the hashing half only, printing the env
lines for you to paste. Use it if you want to place the values by hand.

**The path matters**: the scripts live in `/srv/nvme/surfd`, not in `~`.
`python3 mkadminpw.py` from a home directory just reports "No such file".

**It will not work over plain HTTP from a browser, deliberately.** The session
cookie is set `Secure`, because a login cookie sent in the clear is the whole
credential. For LAN testing before TLS, add `SURFD_ADMIN_INSECURE_COOKIE=1` to
`surfd.env` and restart; surfd logs a warning every boot so it cannot be left on
by accident. Take it out before the panel is reachable from anywhere else.

Then check the falsifier still passes:

    SURFD_HOME=/tmp/surfd-test python3 test_admin.py     # 80 checks

### The security shape, in one line

**The panel is public. rcon never is.**

rcon rides the same UDP port as the game and cannot be firewalled off by port,
so it is never exposed. surfd is on the same box as the servers, reaches them
on `127.0.0.1`, and `rcon.py` refuses any non-loopback host structurally rather
than by convention. Everything else follows from that:

  * scrypt-hashed password (stdlib -- the Pi has no argon2), a separate secret
    from `lobby_master_key`, because three game-server configs hold that one
    and compromising a config must not hand over the fleet;
  * signed session cookie, `HttpOnly` + `SameSite=Strict` + `Secure` + scoped
    to `/admin`, 30-minute idle and 12-hour absolute lifetimes;
  * CSRF token on every POST, login included;
  * five failed logins per IP per fifteen minutes, then a fifteen-minute
    lockout -- and the lockout applies to the *correct* password too, which is
    the point;
  * `/admin` in its own nginx location block, so a mistake in the panel cannot
    expose `/lobbies.json` or `/api/heartbeat`, or the reverse;
  * **no *player* IP addresses, anywhere.** Player names to an authenticated
    admin need no terms change; their addresses would. The status parser never
    reads the address line (it is identified structurally by its leading
    whitespace, not by pattern-matching its contents), and `redact()` scrubs
    rcon output and log tails as a second layer.

    The directory table *does* show each lobby's own advertised address, which
    is a different thing: that is the server's address, it is already public in
    `/lobbies.json`, and an operator who cannot see what address their lobby is
    advertising cannot diagnose the one failure mode that matters most before
    going public. Do not "fix" it by redacting there.

**The honest cost:** a public login is a permanent internet-facing surface on
the machine that runs the game servers. That was a deliberate choice of
convenience over the smaller attack surface, and everything above is what pays
for it.

### Three engine facts the panel is built around

**1. rcon arguments are re-joined without re-quoting, so a semicolon is a
second command.** `SVC_RemoteCommand` (`sv_main.c:4046-4068`) reassembles
`Cmd_Argv(i)` with spaces and hands the result to `Cbuf_AddText`. Verified live
on lobby 27520: `say "probe alpha"` returns nothing, and
`say "probe beta; echo INJECTED-SECOND-COMMAND"` returns
`INJECTED-SECOND-COMMAND` -- the text after the `;` ran as its own console
command at rcon privilege. `rcon.py` therefore refuses `;`, newline, quote,
`$`, backslash and control characters in *every* argument, and the panel has no
free-form command box at all.

**2. `sudo` matches the granted command literally, and the installed grant has
no `.service` suffix.** `/etc/sudoers.d/ftesurf` grants
`systemctl restart ftesurf@1`; asking for `ftesurf@1.service` does not match and
fails as *"a password is required"*, which is indistinguishable from the grant
being absent. systemd treats the two spellings as one unit; sudo does not.

**3. rcon counts against an anti-DDoS budget, and loopback is not exempt.**
`SV_ConnectionlessPacket` sends rcon through the same guard as an anonymous
`getstatus` (`sv_main.c:4441-4444`), *before* the password is validated, so
being authenticated buys nothing. The constants are compile-time, not cvars
(`sv_main.c:4197-4199`): **15 packets per 30 seconds earns a 24-hour block**,
and past the limit every further packet adds another 2 s to the deadline
(`:4236-4237`) — so a caller polling faster than one packet per two seconds
pushes the deadline away faster than the clock advances and the block becomes
*indefinite*. Only restarting that lobby clears it; the table is
process-lifetime static.

The panel's first version sent four commands per lobby every five seconds — 24
per window against a limit of 15 — and blocked all three lobbies in about
nineteen seconds, then reported them as *"server down"* while they were
heartbeating normally. Three things came out of that, and all three matter:

  * **The steady state is cached, not polled.** `STATUS_TTL` (20 s) bounds the
    real packet rate to ~1.5 per 30 s window; the three settings cvars have a
    600 s TTL and are refreshed *by the writer* — setting a hostname updates
    the cache with the value it just sent, so the page is current without
    asking. Do not lower the page's poll interval to make the player list feel
    faster; lower `STATUS_TTL`, having read `rcon.py` first.
  * **A token bucket in `rcon.py` is the backstop.** Eight packets per 30 s per
    port, enforced at the one place every packet passes through, so a future
    caller cannot re-earn the block by forgetting to cache. A sliding window is
    used deliberately: if no 30 s interval anywhere holds more than eight, then
    neither does whichever fixed window the engine is counting in.
  * **Liveness comes from the heartbeat, never from rcon.** The lobbies POST
    their map, player count and name to surfd every few seconds, so a card can
    show live values while the rcon channel is quiet. The panel now says "rcon
    quiet" beside a "beat 3s" pill instead of accusing a healthy server of
    being down.

### What it deliberately does not do

  * No free-form rcon console -- that would hand over the whole console to
    anyone with a session and defeat the argument checking by design.
  * No password change over the web. Rotation is `mkadminpw.py` on the Pi plus
    a restart, which keeps the credential in the 0600 env file and removes one
    authenticated write path.
  * No player IPs, ever.

## Supervision

**Installed and enabled** (`/etc/systemd/system/`, dated Sep 8 17:06):
`surfd.service` and `ftesurf@.service` (instances 1, 2, 3). `Restart=always`
with a five-in-five-minutes start limit, so a config error stops rather than
spinning. The panel's start/stop/restart drive these units.

Still absent: a **heartbeat watchdog**. `Restart=always` cannot see a *hang* --
a process that is running but has stopped beating. surfd already knows the
last-beat age per node, and the panel shows it, so the missing piece is only
the alerting.

## Not done on purpose

  * Not exposed publicly. Nothing in nginx points at surfd; making it public
    is a separate step, see the warnings in surfd.nginx and admin.nginx.
  * The shared secret travels in clear over HTTP. Fine on a trusted LAN,
    not fine once this is public - terminate TLS first.
  * `SURFD_PUBLIC_HOST` is not set. It is the last switch before the ports
    open, and an advertised address that is not reachable yet is worse than a
    LAN one — the player gets a lobby row, clicks it, and waits for a timeout
    instead of seeing an empty list. `setup_public.sh --advertise` is the
    switch, and it refuses to run until you confirm the router forwards.

## Going public

The ports are **27510 / 27520 / 27530** (renumbered from 27500/27510/27520).
The range starts at 27510 so that **27500 is never forwarded**: it is what an
unconfigured QuakeWorld server binds, so anything that ends up listening there
— a test server, a listen server, a mistake — would otherwise be exposed
without anyone choosing to expose it.

Three things must all be true before a stranger can play, and they fail in
different ways:

| | what | who |
|---|---|---|
| 1 | the directory is **readable** at `https://play.proto.bar` | `setup_public.sh` (needs sudo) |
| 2 | the game ports are **reachable** — UDP 27510/27520/27530 → 192.168.1.102 | the router; nothing here can do it |
| 3 | the directory **advertises** the public host, not the LAN one | `setup_public.sh --advertise` |
| 4 | the shipped client **points** at that directory by default | `lobby_dir`, Patch 290 in the game |

**Do them in that order.** Step 3 before step 2 is the one that actively makes
things worse. Step 4 before step 1 empties the lobby list on every install
including the developer's own, because `play.proto.bar` has no vhost until
step 1 runs.

    cd /srv/nvme/surfd && sudo ./setup_public.sh              # 1
    # ... forward UDP 27510/27520/27530 at the router ...     # 2
    cd /srv/nvme/surfd && sudo ./setup_public.sh --advertise  # 3

Phase 1 is safe to run at any time: it publishes a read-only directory whose
rows still say `192.168.1.102`, so nothing that works today stops working.
It also installs `surfd.nginx` and `admin.nginx` as snippets and puts the
`limit_req_zone` line in `conf.d`, which is where nginx will accept it — inside
a `location` it refuses to start, taking every other site on the box with it.

**`/api/heartbeat` is deliberately not on the public vhost, and there is no
catch-all `location /`.** surfd derives each lobby's advertised address from
the socket peer; proxied, every heartbeat would arrive from `127.0.0.1` and
every row would advertise an address nobody can reach. The game servers are on
the same box and post straight to `127.0.0.1:8084`.
