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
      test_surfd.py     the falsifier for the address derivation and the rate
                        limit (see below)
      test_board.py     the falsifier for the leaderboard (schema 2) -- who
                        may write to it, which board a run lands on, and the
                        rate bucket that keeps submissions out of the
                        heartbeat's budget
      run.sh            start under gunicorn, detached
      stop.sh           stop it
      surfd.service     systemd unit  -- INSTALLED and enabled (see below)
      surfd.nginx       nginx snippet -- installed as snippets/surfd.conf
      admin.py          the fleet control panel, a blueprint at /admin
      rcon.py           the panel's only channel to the game servers
      templates/        the panel's pages
      web/              the public leaderboard page (static; served at /board/)
      mkadminpw.py      generates the panel's credentials
      admin.nginx       the panel's OWN nginx block -- installed as
                        snippets/surfd-admin.conf
      surfd-admin.sudoers  a record of the systemctl grant (already installed)
      play.nginx        the public vhost for play.proto.bar -- installed
      setup_public.sh   installs that vhost + TLS, then the advertise switch
      sweep.py          the replay verifier (cron), see below
      test_admin.py     the falsifier for the panel
      test_web.py       the falsifier for the web leaderboard
      server/           the five game servers' scripts, from
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
  -> 200 "ok"                    nothing to do
  -> 200 "map <name>"            changelevel to <name>   -- schema 4

The lobby address is `<source IP>:<port>`. There is no address field, and
X-Forwarded-For is not trusted, so a heartbeat cannot advertise a lobby on
another host.

**The reply is also the control channel** (build 67). A lobby that `/api/join`
has claimed is told, in its next heartbeat reply, which map to move to; the
spelling is the one on DISK, because the other end puts it straight into
`changelevel` and the filesystem is case-sensitive. The body was the literal
`ok` from Patch 270 until schema 4 and a lobby running older QC reads anything
else as a successful heartbeat and does nothing -- which is a directory with
fewer maps, not a broken one.

Not rcon, and that is the decision worth keeping: FTE's amplification guard
gates rcon *before* the password check with no loopback exemption, and fifteen
packets in thirty seconds is a self-extending 24-hour block that only a restart
clears. It would also put the rcon password in this process's reach for
something that is not administration, and it would only work for a lobby on
this machine -- the assumption `replays.node` exists to stop us baking in.

```
GET /api/join?map=<name>                                    -- schema 4
  -> 200 {"map","timed","state","wait","addr","name","players","max","why"}
  -> 400 bad map        the name is not one we will put in a path
  -> 404 not installed  no such .bsp in SURFD_MAPS
  -> 429 rate limited   JOIN_RATE_MAX per RATE_WINDOW per source
  -> 503 every server is busy   (carries `lobbies`: what people ARE playing)
```

"Where do I play this map?" -- the endpoint behind the map list's Start button.
Three outcomes, in order: a live lobby is already on that map and is handed
back (`state: "ready"`, nothing is written); one is already on its way there
(`state: "loading"`); or an idle one is claimed and told to move on its next
heartbeat (`state: "loading"`, `why: "starting"`).

`timed` is REPORTED, NEVER ENFORCED. Only 531 of the Pi's 1312 maps have a zone
file; the rest load perfectly and can never be timed, because with no start,
end or checkpoints the run timer never arms. Refusing to host one would be
surfd deciding a player may not walk around a map they own. Saying "yes, and
you cannot set a time here" is the honest answer, and the menu prints it.

**This is the only public endpoint that causes work on a game server, and it is
unauthenticated** -- it has to be, because the menu calls it before the player
has connected to anything. The structural answer is the idle rule: **a lobby
with anybody on it is never moved**, at either end (surfd will not claim one,
and sv_lobby.qc refuses the instruction if anyone is connected). So the worst a
stranger can do is park idle servers on unpopular maps, which the next real
request and the rotation undo. Nobody is ever thrown out of a run. On top of
that: a per-source rate bucket, a claim that expires after `ASSIGN_TTL`, and
`assignments.src` so the log can say who. It is **not** a defence against a
distributed nuisance; if that happens the answer is a token from the game
client, and the claim table is where it would be checked.

```
POST /api/run         (application/x-www-form-urlencoded)   -- schema 3
    key       shared secret; 403 if wrong or missing
    map       map name, <=64 chars of [A-Za-z0-9_.+-]; REFUSED if longer
    track     0 main, 1+ bonus            (sh_zones.qc: zone_track)  REQUIRED
    leg       0 the full track, k stage k (sh_defs.qc:  FS_LegOf)    REQUIRED
    player    stable player id, the board key
    name      display name at the time of the run
    ticks     1..1e8, the run's tick count
    tickrate  1..10000, in HERTZ (66.6667), NOT seconds per tick
    flags     the TF_* word AT THE FINISH (the .rec header's `flags`)
    tier      "ranked" (default) or "community"; may only be lowered
    node      which server witnessed it
    runid     accepted and stored, but NOTHING SENDS IT and it does not name
              a recording.  sv_lobby.qc's body has no runid field, so every
              real submission stores "".  The .rec header does carry one, but
              it is <YYYYMMDD>-<HHMMSS>-<slot> written at run START, with no
              node component, across five processes that all number slots from
              zero -- its own grammar block calls it "unique-ish".  This line
              used to say it was how the evidence is found later; that has
              never been true.  `rec` is.
    rec       the BASENAME of the .rec the server just closed, e.g.
              0000279_lex-3eb1bd43_run.rec.  OPTIONAL: a run that left no
              keepable recording sends nothing and its row honestly reports no
              replay.  Ignored from an untrusted source -- a path is only
              evidence for a node we own -- and checked three ways before it is
              stored: the grammar FS_RunLeaf can emit, the 7-digit stamp
              against `ticks` (SV_RecClose stamps with the same value it
              submits), and the 8 hex against sha256(player).  A failed check
              drops the leaf and logs it; it NEVER refuses the run.
    recbytes  the recording's size as the recorder reported at close, or -1
    rectrunc  1 if the run hit FS_RECMAX and the recording is short
  -> 200 {"ok":true,"stored":true|false,"best":<ms>,"rank":n,"of":n,"rep":<id>,
          "tier":"ranked"|"community","prevms":<ms>}
        `tier` is the board the run LANDED on (after certifiable() demotion);
        `prevms` is this player's standing row before the submit, 0 if none.
  -> 204        the run has no board at all (practice or cheated)

GET /api/board?map=&track=&leg=&tier=&style=&limit=&offset=
    track/leg default 0; tier defaults "ranked"; style defaults "clean"
  -> 200 {"v":1,"t":..,"map":..,"track":..,"leg":..,"tier":..,"style":..,
          "counts":{"ranked":n,"community":n},"offset":n,
          "rows":[{"r":1,"player":..,"name":..,"ticks":..,"rate":..,
                   "ms":..,"flags":..,"when":..,"rep":..,"ver":0|1}]}
```

`rep` is a row in `replays`, or 0 when nothing is indexed for that row.
`ver` (schema 5) is 1 when that replay's latest current non-ERROR verdict is
PASS or the owner approved it, else 0; "current" means recorded at or after the replay
row's `submitted`. Rows carry no verdict word, reason or review.

```
GET /api/replay/<id>            <id> being a row's `rep`
  -> 200 the recording itself, text/plain, Content-Disposition: attachment
  -> 404 {"ok":false,"error":"no such replay"}        no row with that id
  -> 404 {"ok":false,"error":"replay not on this node"}   row exists, file does not
  -> 429 rate limited (REPLAY_RATE_MAX per RATE_WINDOW per source)
```

`rep` IS the `has_replay` flag -- an integer is strictly more informative than
a boolean would be, and 0 is the "nothing to click" case that a Community row,
a pre-feature row, and a run whose recording was never kept all land on.

**`rep` says a ROW exists, not that the file does.** Nothing prunes any more,
so in the normal case they agree; they can disagree if the archive is restored
from an older backup than the database, or -- the one that will actually happen
-- once a keyed game server runs on a machine that is not this one. `replays`
already records `node` per recording and this route does not consult it yet:
that is the seam to pull when the second node appears.

**The handle is the ledger id and never a path.** The caller names a row and
surfd decides which file that row means, so there is no attacker-supplied path
component in the route at all. `SURFD_RUNS` (default
`/srv/nvme/ftesurf-server/game/ftesurf/data/runs`) is the only root it will
read from, and a resolved path outside it is refused even though nothing
validated should be able to produce one.

**There is no upload half, and that is the whole reason this is cheap.** The
five lobbies and surfd are the same machine, so a `.rec` is already on the disk
surfd serves from. Only the download is new.

THE TWO TABLES ANSWER TWO DIFFERENT QUESTIONS and neither can answer the
other's.  `runs` is the BOARD: one row per player per board, their best, and
an improvement overwrites the row that described the run it beat.  `replays`
is the LEDGER: one row per recording on disk, appended at every finish that
kept a file -- faster, slower and tied alike -- and never rewritten except to
re-describe bytes that were genuinely replaced.

Since build 66 the lobbies delete nothing (`rec_runs_keep 0`), so without the
ledger a beaten run's file would survive on disk with nothing left anywhere to
say whose run it was, under what name, on which board.  A kept file that
cannot be attributed is not kept in any useful sense.  The board still shows
one time per player; the ledger is what stands behind it.

`track` and `leg` are **required on POST and defaulted to 0 on GET**, and the
asymmetry is deliberate. Defaulting them on a read is a convenience -- most
reads want the main track's full run. Defaulting them on a write would mean a
client that forgot the field files every bonus and every stage run silently
onto the main board, and nothing downstream could tell. A 400 is loud; a
misfiled leaderboard is not.

**One row per player per board, not one per run.** The board answers "players'
best times ranked", so the primary key is `(map, track, leg, tier, style,
player)` and a submission replaces a row only on an improvement. A tie keeps
the earlier claim.

**`millis` is the rank key, not `ticks`.** A tick is only a duration at a
tickrate. 4000 ticks at 100 Hz is 40 s and 3000 at 50 Hz is 60 s -- ranked on
ticks the slower run wins. `pm_ticrate` is locked on a conforming server, but
the board is not the thing that gets to assume so.

**`tickrate` IS IN HERTZ AND THIS IS A REAL TRAP.** `millis = ticks * 1000 /
tickrate`, so 66.6667 is what goes on the wire. But the game's own
`pm_ticrate` is **seconds per tick** (0.015), and so is the parameter
`sh_time.qc`'s `Time_TickString` takes -- despite being *called* `tickrate`
there too. Three things share the name and one of them is inverted.

Submitting `0.015` does not silently corrupt the board: the `1..10000` bound
rejects it with a 400, which is the guard. But reading the field back and
handing it straight to `Time_TickString` **does** — it printed 3500 ticks as
`64:48:53.328` instead of `0:52.500`, a factor of 4444, caught only because
`cfg/test/b64board.cfg` registered the expected times before the run.
Convert at the point of use and keep the server's units everywhere else.

**`style` is derived from `flags` here, never taken from the submitter**, as a
mirror of `FS_RunClass` including its precedence (cheat outranks segment
outranks practice). `clean` and `segmented` are peer boards -- a player may
hold a PB on each -- and practice and cheated runs are refused a board
entirely, with a 204 rather than an error, because they are real runs that
simply have nowhere to stand.

**`tier` is decided by who holds the key.** A leaderboard fed by player-hosted
servers is forgeable by the host with no cheating skill at all: on a listen
server the host owns `sv.time`, the movement cvars, the progs and the timer.
Requiring the shared secret to POST is what makes "Ranked = official servers
only" true without a line of policy code -- a player-hosted server holds no
key, gets a 403, and keeps its times locally, which is the Local tab and is
already built (`cl_scores.qc`).

A submitter may ask for a *lower* tier than it is entitled to, and never a
higher one. A run carrying `TF_NOJOURNAL` or `TF_NORULESET` is demoted to
community whatever it asked for: both describe a hole in the *certification*
rather than something the player did, so neither may call anyone a cheat, and
a demotion is the quiet gate this tree prefers to an accusation. **This is the
first consumer of either bit** -- they have been recorded, archived and
reported since QC builds 58 and 62 with nothing downstream acting on them.

**What this does NOT do is authenticate the player.** surfd has no player
identity yet; `player` is whatever id the client generates for itself and a
keyed server vouches for it. A row therefore means "an official server saw
this player finish", not "this human finished". The local-keypair work is what
upgrades that, and it is a *value* change in this column rather than a schema
change -- which is why the column exists now and is separate from `name`.

Run submissions and board reads each get **their own rate bucket**. `rate_ok`
keys on the source IP and every lobby on the Pi posts from `127.0.0.1`, so a
shared bucket would let a busy evening of finishes spend the heartbeat's
budget and drop live lobbies out of `/lobbies.json` -- the failure the
`RATE_MAX` essay in `surfd.py` spends twenty lines establishing.
`test_board.py` section 8 floods submissions and asserts a heartbeat still
gets through, with the shared-bucket case as its control.

Run submissions are themselves split: leg 0 posts use the `run` bucket and
stage legs the `stage` bucket, so a main run posting its stages can never
spend the finishes' budget. Trusted sources get `RUN_RATE_MAX_TRUSTED`,
everyone else `RUN_RATE_MAX`. Stage rows also have their own row cap
(`MAX_STAGE_RUNS`). Section 13 pins all three.

### The one exception: SURFD_PUBLIC_HOST

surfd and the five game servers run on the same Pi, so `REMOTE_ADDR` for a
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

Twenty-one checks, and the two that matter most are the two that must NOT
change: an untrusted source still keeps its own address, and with the option
unset nothing changes at all. The last three hold the per-IP rate limit to the
Pi's own traffic -- five lobbies heartbeating from one address for two
simulated minutes -- with a control that plays the same traffic against the old
cap of 60 and must draw a 429.

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
  * 150 heartbeats/minute per **untrusted** source IP; over that gets 429. Not
    60: all five lobbies beat from 127.0.0.1 every 5 s, which is exactly 60 a
    minute, so at that cap any early beat is refused, and enough refusals in a
    row drop a running lobby out of the list. `RATE_MAX` in surfd.py has the
    arithmetic.
  * **1920/minute for a TRUSTED source** (`RATE_MAX_TRUSTED`), which is 2.5x
    64 nodes beating every 5 s. Under FTE's `mapcluster` there is one server
    process per live map and each one heartbeats, so the load is 12 x N and
    the old flat 150 capped the cluster at **12 nodes** — below the box's own
    RAM ceiling of 8–16 heavy maps (~24–30 curated to the median). This uses
    the existing `TRUSTED_SOURCES`, which already governs the strictly more
    sensitive question of whether a heartbeat may advertise itself as
    `PUBLIC_HOST`, so it adds no new trust surface: with trust unconfigured,
    behaviour is unchanged. Safe because nothing proxies to 8084 — verify that
    before putting surfd behind nginx, or every request becomes "trusted".
  * Request body capped at 16 KiB.
  * Strings stripped of control characters and truncated to 64 -- except the
    map name, which is **refused** when it is too long rather than trimmed.
    It is the board key, and trimming an identifier to fit merges two
    leaderboards into one without a word.
  * 120 run submissions/minute and 120 board reads/minute per source IP, each
    in its own bucket, separate from the heartbeat's 150. See the API section.
  * At most 200,000 board rows; a *new* row beyond that gets 429. One row per
    player per board keeps this far from binding: 1,312 maps would each need
    150 players on every leg to reach it.
  * A board page returns at most 200 rows (default 50). An over-large `limit`
    is clamped rather than refused.

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
session secret, copies the lobbies' `rcon_password` out of `cfg/lobby/lobby.cfg` so it
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
    from `lobby_master_key`, because five game-server configs hold that one
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
spinning. The panel's start/stop/restart and `src/build.ps1 -Pi` drive these
units.

Instances 4 and 5, the bhop lobbies (QC build 57), need three things on the
Pi, in this order: their 17 rotation BSPs in
`/srv/nvme/ftesurf-server/game/momentum/maps/`, because a lobby started before
its default map is there has no map to load; the six `ftesurf@4`/`ftesurf@5`
lines appended to `/etc/sudoers.d/ftesurf` (see `surfd-admin.sudoers`); and,
once, by hand:

    sudo systemctl enable --now ftesurf@4 ftesurf@5

### Growing the pool past five (build 68)

Lobbies **6..12** are prepared but **not started**, and that is the intended
resting state until there is demand for them. `cfg/lobby/lobby6.cfg` .. `lobby12.cfg`
exist (ports 27560..27620, all-timeable rotations, 6..11 surf and **12 the kz /
df / ahop maps no lobby has ever rotated to**), `run.sh` takes any N that has a
cfg, and `runall.sh`/`stopall.sh`/`build.ps1 -Pi` discover the fleet rather than
listing it — so nothing in the tooling has to be edited again.

Two things are still required, once, and only one of them is a decision:

    # 1. let unattended tooling operate them (a grant, NOT permission --
    #    proto already has (ALL:ALL) ALL; this is about not being PROMPTED)
    sudo install -m 0440 -o root -g root \
         /srv/nvme/surfd/ftesurf-pool.sudoers /etc/sudoers.d/ftesurf-pool
    sudo visudo -c                       # must print "parsed OK"

    # 2. enable the ones you actually want, one at a time the first time
    sudo systemctl enable --now ftesurf@6
    systemctl status ftesurf@6 --no-pager | head -20

**Forward UDP for a port before enabling its lobby.** surfd advertises
`play.proto.bar:<port>` the instant that lobby first beats, and a row pointing
at a port nobody can reach is worse than no row — the player picks it, waits,
and times out.

**Do not enable more than there is demand for.** Each idle instance costs about
100–260 MB and ~2.3% of one core (measured), which the Pi has plenty of; what it
actually costs is the *picker*, where twelve rows at 0 players reads as a deader
game than five. Since build 67 a player reaches a map by asking the directory,
not by finding a lobby already sitting on it, so more lobbies buys concurrent
*different* maps and nothing else.

Still absent: a **heartbeat watchdog**. `Restart=always` cannot see a *hang* --
a process that is running but has stopped beating. surfd already knows the
last-beat age per node, and the panel shows it, so the missing piece is only
the alerting.

## Replay verification (sweep.py)

`sweep.py` runs engine `pm_verify` (Patch 349) over every row in `replays`
that has not been checked yet, and stores one verdict per attempt in the
`verdicts` table (surfd schema 5): PASS, HOLD (a reason for a human), REFUSE
(out of scope, e.g. a pre-v9 file), or ERROR (no verdict printed; retried up
to 3 times since the replay's last submission or re-check). A PASS as the latest
current non-ERROR verdict sets the public `ver` badge (an ERROR never changes
it); nothing else reads verdicts, and reasons and HOLD appear only on the
owner's review pages. Verdicts are stamped with the time the sweep started, so a
tie resubmitted or a re-check asked mid-run stays pending. It starts one
headless verifier per map on port 27698, with `nice 19`, idle IO and
`oom_score_adj 1000`. Installed in proto's crontab:

    */5 * * * * cd /srv/nvme/surfd && flock -n /tmp/surfd-sweep.lock python3 sweep.py --limit 20 >> /srv/nvme/surfd/logs/sweep.log 2>&1

`python3 sweep.py --dry-run` lists what is pending. `test_sweep.py` stubs out the
engine (use a throwaway `SURFD_HOME`), and `cfg/test/p349verify.cfg` tests the
verifier itself.

## Web leaderboard (/board/)

A static page (`web/board.html`, `board.js`, `board.css`) and two JSON routes,
proxied from `https://proto.bar/ftesurf/board/` by `src/release/ftesurf.nginx`.
URLs in the page are relative because the browser's prefix is not surfd's.

```
GET /board/                     the page; /board/board.js and board.css only
GET /board/api/maps             zoned maps with a BSP, plus maps with ranked runs:
  -> {"v":1,"t":..,"maps":[{"map","runs","last","wr":{"name","ms","ver"}|null}]}
GET /board/api/map?map=&track=&leg=&style=&offset=
  -> {"v":1,"t":..,"map","disp","boards":[{"track","leg","style","n"}],
      "track","leg","style","n","offset","limit":50,"rows":[..]}
```

RANKED ONLY, like the in-game board since Patch 355: community runs are never
counted or listed, and a `tier` parameter (old links) is ignored. `wr` is the
main clean board's row 1 (`BOARD_ORDER`). With no board parameters a map opens
on main clean, else main segmented, else its first board. Rows are
`/api/board`'s minus `player`. Both API routes share the `web` rate bucket
(`WEB_RATE_MAX`, 120/min per `rate_key()`); the maps list is rebuilt at most
every 60 s. Every `/board/` response carries a strict CSP (no inline script or
style) and sets no cookie.

## Run review (/admin/runs)

Behind the admin login (`admin.py`, only when surfd injects its replay helpers).

```
GET  /admin/runs                 list page          (logged out: login redirect)
GET  /admin/run/<rid>            one replay's page  (logged out: login redirect)
GET  /admin/api/runs?state=&q=&offset=   state: queue hold pass refuse error
                                 pending approved rejected all      (401)
GET  /admin/api/run/<rid>        details, verdict history with reasons,
                                 review, standing, download + watch commands (401)
GET  /admin/api/run/<rid>/path   recplot.parse() of the file, 404 if unusable (401)
POST /admin/api/review           rid, action=approve|reject|clear|recheck,
                                 submitted, note (<= 200 chars)      (401/400/403/409)
```

The list shows each replay's latest current non-ERROR verdict (what the badge
reads), an ERROR flag for a last attempt that printed nothing, the review and
whether the run stands on a board. The queue is current HOLDs with no review;
pending is what the next sweep picks (`checked=0`, under the ERROR cap).

Actions: approve (shows VERIFIED), reject (hides the run; reversible), clear,
and re-check (`checked=0`, `recheck_at`). Approve, reject and clear call
`restand()`, which rewrites that player's board row from their best
non-rejected replay, so public reads need no hidden filter. A review counts only
while it is at or after the replay's `submitted`; the page posts the
`submitted` it showed, and a replay resubmitted since answers 409 ("the run
changed -- reload").

Every POST goes through `control()`: a session, the CSRF token, and
`Sec-Fetch-Site` absent or `same-origin` (else 403). proto.bar and
play.proto.bar are one site, so SameSite=Strict alone does not separate them.

## Not done on purpose

  * No catch-all proxy. The public routes are exactly `surfd.nginx`'s
    manifest, `/admin` (admin.nginx) and `/board/` (proxied from
    proto.bar/ftesurf/board/); `/api/heartbeat` and `/api/run` are not proxied.
  * The shared secret travels in clear over HTTP. Fine on a trusted LAN,
    not fine once this is public - terminate TLS first.
  * `SURFD_PUBLIC_HOST` is not set. It is the last switch before the ports
    open, and an advertised address that is not reachable yet is worse than a
    LAN one — the player gets a lobby row, clicks it, and waits for a timeout
    instead of seeing an empty list. `setup_public.sh --advertise` is the
    switch, and it refuses to run until you confirm the router forwards.

## Going public

The ports are **27510 / 27520 / 27530** for the three surf tiers (renumbered
from 27500/27510/27520) and **27540 / 27550** for bhop easy and hard (QC build
57), so the router forwards **UDP 27510-27550**. Nothing listens between the
five yet -- the gaps are kept for mapcluster children at sv_port+N -- so
forwarding only the five ports is the tighter equivalent until those exist.
The range starts at 27510 so that **27500 is never forwarded**: it is what an
unconfigured QuakeWorld server binds, so anything that ends up listening there
— a test server, a listen server, a mistake — would otherwise be exposed
without anyone choosing to expose it.

Three things must all be true before a stranger can play, and they fail in
different ways:

| | what | who |
|---|---|---|
| 1 | the directory is **readable** at `https://play.proto.bar` | `setup_public.sh` (needs sudo) |
| 2 | the game ports are **reachable** — UDP 27510-27550 → 192.168.1.102 (27500 stays closed) | the router; nothing here can do it |
| 3 | the directory **advertises** the public host, not the LAN one | `setup_public.sh --advertise` |
| 4 | the shipped client **points** at that directory by default | `lobby_dir`, Patch 290 in the game |

**Do them in that order.** Step 3 before step 2 is the one that actively makes
things worse. Step 4 before step 1 empties the lobby list on every install
including the developer's own, because `play.proto.bar` has no vhost until
step 1 runs.

    cd /srv/nvme/surfd && sudo ./setup_public.sh              # 1
    # ... forward UDP 27510-27550 at the router, never 27500 ... # 2
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
