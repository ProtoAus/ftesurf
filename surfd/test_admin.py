#!/usr/bin/env python3
"""
test_admin.py -- the falsifier for the admin panel.

    SURFD_HOME=/tmp/surfd-test python3 test_admin.py

Runs entirely against throwaway home directories and Flask's test client. It
never touches a live surfd and never sends a packet: the rcon layer is checked
for what it REFUSES, which is the half that matters and the half that can be
tested without a server.

THE TWO CASES THAT MUST NOT CHANGE, and which a test of only the new features
would say nothing about:

    1. With SURFD_ADMIN_HASH unset, surfd registers no /admin routes at all.
       "Off by default" is a claim until something checks it.
    2. The public endpoints keep working with the panel enabled AND disabled.
       The panel and the directory share a process; they must not be able to
       break each other.

The scrypt cost parameter is lowered to 2**10 for the login cases. The real
default is 2**15 and each verification allocates 32 MB, which would make this
file take minutes on the Pi for no extra coverage -- verify_password reads N
back out of the stored string, so the code path is identical.
"""

import importlib
import os
import shutil
import sys
import tempfile

FAILED = []


def check(label, got, want):
    ok = got == want
    print("%-4s %-62s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


def check_true(label, got):
    check(label, bool(got), True)


HOMES = []


def fresh(_file=None, **env):
    """Import surfd with a clean home and the given admin settings.

    Keyword arguments go into the PROCESS ENVIRONMENT. `_file` is a dict whose
    entries go into surfd.env instead, which is the path that matters in the
    real deployment -- see the SURFD_ENV_FILE case in main().
    """
    home = tempfile.mkdtemp(prefix="surfd-admin-test-")
    HOMES.append(home)
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=testkey\n")
        for k, v in (_file or {}).items():
            fh.write("%s=%s\n" % (k, v))
    os.environ["SURFD_HOME"] = home
    os.environ["SURFD_DB"] = os.path.join(home, "test.db")
    os.environ["SURFD_ENV"] = os.path.join(home, "surfd.env")
    for k in ("SURFD_PUBLIC_HOST", "SURFD_TRUSTED", "SURFD_ADMIN_HASH",
              "SURFD_ADMIN_SECRET", "SURFD_RCON_PASSWORD",
              "SURFD_ADMIN_LOBBIES", "SURFD_ADMIN_INSECURE_COOKIE"):
        os.environ.pop(k, None)
    for k, v in env.items():
        if v is not None:
            os.environ[k] = v
    sys.modules.pop("surfd", None)
    sys.modules.pop("admin", None)
    sys.modules.pop("rcon", None)
    return importlib.import_module("surfd")


def login(client, password, csrf=None):
    if csrf is None:
        page = client.get("/admin/login").get_data(as_text=True)
        csrf = page.split('name="csrf" value="')[1].split('"')[0]
    return client.post("/admin/login", data={"csrf": csrf, "password": password})


def login_via(client, password, peer="127.0.0.1", real_ip=None, csrf=None):
    """login(), but saying explicitly who the socket peer and the proxy's
    claimed client are. Everything about the /admin lockout depends on the
    difference between those two, and the plain helper above cannot express
    it -- it sends neither, and Flask's default REMOTE_ADDR of 127.0.0.1
    happens to BE a trusted proxy source, which is what made the defect
    invisible to this suite for so long."""
    hdrs = {"X-Real-IP": real_ip} if real_ip else {}
    base = {"REMOTE_ADDR": peer}
    if csrf is None:
        page = client.get("/admin/login", headers=hdrs,
                          environ_base=base).get_data(as_text=True)
        csrf = page.split('name="csrf" value="')[1].split('"')[0]
    return client.post("/admin/login", headers=hdrs, environ_base=base,
                       data={"csrf": csrf, "password": password})


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import admin
    import rcon

    # ---- 1. OFF BY DEFAULT -------------------------------------------------
    m = fresh()
    c = m.app.test_client()
    check("no SURFD_ADMIN_HASH -> /admin is 404", c.get("/admin/").status_code, 404)
    check("no SURFD_ADMIN_HASH -> /admin/login is 404",
          c.get("/admin/login").status_code, 404)
    check("directory still works with the panel off",
          c.get("/lobbies.json").status_code, 200)

    # A hash but no session secret must ALSO stay off, rather than falling back
    # to a Flask default secret key and issuing forgeable sessions.
    m = fresh(SURFD_ADMIN_HASH=admin.hash_password("correct horse", n=2 ** 10),
              SURFD_ADMIN_SECRET="too-short")
    c = m.app.test_client()
    check("hash set but SECRET too short -> still 404", c.get("/admin/").status_code, 404)

    # ---- 1b. THE REGRESSION THAT SHIPPED BROKEN ---------------------------
    #
    # surfd.service has no EnvironmentFile=, so NOTHING puts surfd.env into the
    # process environment. surfd.py never noticed because it parses the file
    # itself for SURFD_KEY. admin.py originally used os.environ.get(), so a
    # correctly-filled surfd.env produced "admin panel disabled" forever with
    # the value plainly present in the file. Settings must therefore resolve
    # from the FILE with nothing whatsoever in the environment.
    PW0 = "file only password"
    m = fresh(_file={
        "SURFD_ADMIN_HASH": admin.hash_password(PW0, n=2 ** 10),
        "SURFD_ADMIN_SECRET": "f" * 48,
        "SURFD_ADMIN_INSECURE_COOKIE": "1",
    })
    c = m.app.test_client()
    check("settings read from surfd.env with an EMPTY environment",
          c.get("/admin/login").status_code, 200)
    check("...and the password from the file actually works",
          login(c, PW0).status_code, 302)

    # Environment must still win over the file, so a systemd Environment= line
    # or a test override is not silently ignored.
    m = fresh(_file={"SURFD_ADMIN_LOBBIES": "7:1111"},
              SURFD_ADMIN_HASH=admin.hash_password("x" * 12, n=2 ** 10),
              SURFD_ADMIN_SECRET="e" * 48,
              SURFD_ADMIN_LOBBIES="9:2222")
    check("environment overrides the file",
          [l["tier"] for l in admin.parse_lobbies(admin.setting("SURFD_ADMIN_LOBBIES"))],
          ["9"])

    # ---- 2. the enabled panel ---------------------------------------------
    PW = "correct horse battery"
    HASH = admin.hash_password(PW, n=2 ** 10)
    m = fresh(SURFD_ADMIN_HASH=HASH, SURFD_ADMIN_SECRET="s" * 48,
              SURFD_ADMIN_INSECURE_COOKIE="1")
    c = m.app.test_client()

    check("panel enabled -> / redirects to login", c.get("/admin/").status_code, 302)
    check("login page renders", c.get("/admin/login").status_code, 200)
    check("api/state without a session -> 401",
          c.get("/admin/api/state").status_code, 401)
    check("control without a session -> 401",
          c.post("/admin/api/say", data={"tier": "1", "text": "hi"}).status_code, 401)

    check("wrong password -> 401", login(c, "wrong").status_code, 401)
    check("missing CSRF -> 400",
          c.post("/admin/login", data={"password": PW}).status_code, 400)
    check("right password -> 302", login(c, PW).status_code, 302)
    check("session reaches the panel", c.get("/admin/").status_code, 200)
    check("session reaches the api", c.get("/admin/api/state").status_code, 200)

    # CSRF is enforced on controls too, not just on login.
    check("control without CSRF -> 400",
          c.post("/admin/api/say", data={"tier": "1", "text": "hi"}).status_code, 400)

    page = c.get("/admin/").get_data(as_text=True)
    csrf = page.split('name="csrf" value="')[1].split('"')[0]

    # ---- 3. validators refuse before anything reaches the network ----------
    def ctl(path, **fields):
        fields["csrf"] = csrf
        r = c.post(path, data=fields)
        return r.get_json() or {}

    check("unknown lobby refused",
          ctl("/admin/api/map", tier="9", map="surf_x").get("ok"), False)
    check("map name with a semicolon refused",
          ctl("/admin/api/map", tier="1", map="surf_x; quit").get("ok"), False)
    check("map name with a space refused",
          ctl("/admin/api/map", tier="1", map="surf x").get("ok"), False)
    check("uppercase map name refused",
          ctl("/admin/api/map", tier="1", map="Surf_X").get("ok"), False)
    check("cycle 30 refused (below the 60s floor)",
          ctl("/admin/api/cycle", tier="1", cycle="30").get("ok"), False)
    check("cycle 'abc' refused",
          ctl("/admin/api/cycle", tier="1", cycle="abc").get("ok"), False)
    check("say with a newline refused",
          ctl("/admin/api/say", tier="1", text="hi\nquit").get("ok"), False)
    check("say with a dollar refused",
          ctl("/admin/api/say", tier="1", text="$deathmatch").get("ok"), False)
    check("kick with a non-number refused",
          ctl("/admin/api/kick", tier="1", userid="1; quit").get("ok"), False)
    check("unit action 'reboot' refused",
          ctl("/admin/api/unit", tier="1", action="reboot").get("ok"), False)

    # No rcon password configured, so a WELL-FORMED control must still be
    # refused -- and refused with a reason, not by silently doing nothing.
    j = ctl("/admin/api/map", tier="1", map="surf_kitsune")
    check("valid map with no rcon password -> refused", j.get("ok"), False)
    check_true("...and says why", "SURFD_RCON_PASSWORD" in j.get("error", ""))

    # ---- 4. lockout --------------------------------------------------------
    m = fresh(SURFD_ADMIN_HASH=HASH, SURFD_ADMIN_SECRET="s" * 48,
              SURFD_ADMIN_INSECURE_COOKIE="1")
    # THE PEER IS NAMED, and that is new. This section used to call login(),
    # which sends Flask's default REMOTE_ADDR of 127.0.0.1 -- an address that
    # is in SURFD_PROXIES, i.e. the suite was unknowingly impersonating nginx
    # on every request. It therefore could not tell a per-client lockout from
    # a global one, which is precisely how the /admin lockout shipped keyed on
    # the proxy. A direct caller has to come from somewhere that is not one of
    # our own proxies for this to be testing what it says it tests.
    c2 = m.app.test_client()
    codes = [login_via(c2, "nope", peer="192.168.5.5").status_code
             for _ in range(admin.LOCKOUT_FAILS)]
    check("first %d bad logins all 401" % admin.LOCKOUT_FAILS,
          codes, [401] * admin.LOCKOUT_FAILS)
    check("next attempt is locked out (429)",
          login_via(c2, "nope", peer="192.168.5.5").status_code, 429)
    check("lockout applies to the RIGHT password too",
          login_via(c2, PW, peer="192.168.5.5").status_code, 429)

    # ---- 4b. THE LOCKOUT MUST NOT BE A WEAPON ------------------------------
    #
    # nginx fronts /admin (play.nginx includes snippets/surfd-admin.conf), so
    # every caller arrives from 127.0.0.1. Keying the lockout on that address
    # meant five wrong guesses from ANY stranger locked the OPERATOR out of
    # their own panel for fifteen minutes, repeatably, with no password. The
    # first check below is that exact attack, and it is the falsifier: revert
    # client_ip() to request.remote_addr and it goes 302 -> 429.
    m = fresh(SURFD_ADMIN_HASH=HASH, SURFD_ADMIN_SECRET="s" * 48,
              SURFD_ADMIN_INSECURE_COOKIE="1")
    atk, op = m.app.test_client(), m.app.test_client()
    codes = [login_via(atk, "nope", real_ip="203.0.113.9").status_code
             for _ in range(admin.LOCKOUT_FAILS)]
    check("proxied: attacker's %d bad logins all 401" % admin.LOCKOUT_FAILS,
          codes, [401] * admin.LOCKOUT_FAILS)
    check("proxied: the attacker IS locked out",
          login_via(atk, "nope", real_ip="203.0.113.9").status_code, 429)
    check("proxied: the OPERATOR still gets in",
          login_via(op, PW, real_ip="198.51.100.4").status_code, 302)

    # A caller who is NOT a trusted proxy cannot pick their own identity, so
    # they cannot shed a lockout by rotating the header. Without this, the fix
    # above would simply have moved the hole: every attacker would be
    # unlockoutable rather than every operator lockable.
    m = fresh(SURFD_ADMIN_HASH=HASH, SURFD_ADMIN_SECRET="s" * 48,
              SURFD_ADMIN_INSECURE_COOKIE="1")
    c4 = m.app.test_client()
    for i in range(admin.LOCKOUT_FAILS):
        login_via(c4, "nope", peer="192.168.5.5", real_ip="203.0.113.%d" % i)
    check("unproxied: rotating X-Real-IP does NOT evade the lockout",
          login_via(c4, "nope", peer="192.168.5.5",
                    real_ip="203.0.113.77").status_code, 429)

    # (that a genuinely direct caller is STILL locked out normally -- i.e. the
    # feature was fixed rather than deleted -- is section 4 above, which now
    # names its peer for the same reason.)

    # THE DELIBERATE GAP, pinned so it is a decision and not a surprise. A
    # proxy that sets no X-Real-IP leaves every caller sharing one identity,
    # and we decline to lock that identity out -- nginx's per-real-IP
    # `zone=surfdlogin` (12r/m) and scrypt are what hold the line there.
    m = fresh(SURFD_ADMIN_HASH=HASH, SURFD_ADMIN_SECRET="s" * 48,
              SURFD_ADMIN_INSECURE_COOKIE="1")
    c6, op6 = m.app.test_client(), m.app.test_client()
    for _ in range(admin.LOCKOUT_FAILS + 2):
        login_via(c6, "nope")                        # loopback, no header
    check("proxy with no X-Real-IP: no lockout is applied",
          login_via(c6, "nope").status_code, 401)
    check("proxy with no X-Real-IP: the operator is never locked out",
          login_via(op6, PW).status_code, 302)

    # ---- 5. cookie flags ---------------------------------------------------
    m = fresh(SURFD_ADMIN_HASH=HASH, SURFD_ADMIN_SECRET="s" * 48)  # no INSECURE
    c3 = m.app.test_client()
    r = login(c3, PW)
    setcookie = r.headers.get("Set-Cookie", "")
    check_true("cookie is HttpOnly", "HttpOnly" in setcookie)
    check_true("cookie is SameSite=Strict", "SameSite=Strict" in setcookie)
    check_true("cookie is Secure by default", "Secure" in setcookie)
    check_true("cookie is scoped to /admin", "Path=/admin" in setcookie)

    # ---- 6. rcon argument checking ----------------------------------------
    for bad, why in (("a; quit", "semicolon"), ("a\nb", "newline"),
                     ('a"b', "quote"), ("$x", "dollar"), ("a\\b", "backslash"),
                     ("a\x07b", "control character")):
        try:
            rcon.check_arg(bad)
            check("rcon refuses %s" % why, "accepted", "refused")
        except rcon.RconUnsafe:
            check("rcon refuses %s" % why, "refused", "refused")
    check("rcon allows an ordinary message",
          rcon.check_arg("welcome to surf_kitsune!"), "welcome to surf_kitsune!")

    try:
        rcon.Rcon("10.0.0.5", 27500, "x")
        check("rcon refuses a non-loopback host", "accepted", "refused")
    except rcon.RconError:
        check("rcon refuses a non-loopback host", "refused", "refused")

    # Known answer for the ezquake timestamp encoding (sv_main.c:3882-3888).
    check("timehex is little-endian bytes",
          rcon.hashed_password("x", [], 0x6123ABCD)[40:], "cdab2361")
    check("digest is 40 hex chars + 8 of time",
          len(rcon.hashed_password("x", ["status"], 1)), 48)

    # ---- 7. status parsing never yields an address ------------------------
    sample = (
        "cpu utilization  :   3%\n"
        "server uptime    : 4h 56m 40s\n"
        "public           : private\n"
        "map uptime       : 20m 19s\n"
        "current map      : surf_lux (Lux)\n"
        "gamedir          : ftesurf\n"
        "name               userid frags\n"
        "  address          rate ping drop\n"
        "  ---------------- ---- ---- -----\n"
        "Lex                    7     0\n"
        "  192.168.1.55       77   12  0.00\n"
        "somebody               8     0 (s)\n"
        "  203.0.113.9        77   30  0.00\n"
    )
    info = admin.parse_status(sample)
    check("map parsed without its long name", info["map"], "surf_lux")
    check("server uptime parsed", info["uptime"], "4h 56m 40s")
    check("two players parsed", len(info["players"]), 2)
    check("first player name", info["players"][0]["name"], "Lex")
    check("first player userid", info["players"][0]["userid"], 7)
    check("spectator flagged", info["players"][1]["spectator"], True)
    blob = repr(info)
    check_true("no IPv4 anywhere in the parsed result",
               "192.168" not in blob and "203.0.113" not in blob)
    check("redact() removes an address",
          rcon.redact("addr 192.168.1.55:27500 here"), "addr [addr] here")

    check("cvar echo parsed",
          admin.parse_cvar('"lobby_cycle" is "600"\n', "lobby_cycle"), "600")
    check("cvar echo for a different name is not confused",
          admin.parse_cvar('"lobby_maps" is "a b"\n', "lobby_cycle"), "")

    # ---- 8. password hashing ----------------------------------------------
    h = admin.hash_password("hunter2 hunter2", n=2 ** 10)
    check("correct password verifies", admin.verify_password("hunter2 hunter2", h), True)
    check("wrong password does not", admin.verify_password("hunter3 hunter2", h), False)
    check("malformed hash returns False, does not raise",
          admin.verify_password("x", "not-a-hash"), False)
    check("empty hash returns False", admin.verify_password("x", ""), False)
    check("two hashes of one password differ (salted)",
          admin.hash_password("a", n=2 ** 10) == admin.hash_password("a", n=2 ** 10),
          False)

    check("lobby list parses", admin.parse_lobbies("1:27500,2:27510"),
          [{"tier": "1", "port": 27500}, {"tier": "2", "port": 27510}])

    # ---- the packet budget -------------------------------------------------
    # The engine treats rcon as a possible amplification attack and blocks the
    # source for 24 HOURS at 15 packets per 30s, with no exemption for
    # loopback (sv_main.c:4197-4199, 4441-4444). The panel's first version sent
    # 24 per window and was blocked within twenty seconds. These checks exist
    # so that regression cannot happen silently a second time.

    check_true("our budget is under the engine's limit",
               rcon.BUDGET_PACKETS < rcon.ENGINE_DOS_LIMIT)
    check("budget window matches the engine's period",
          rcon.BUDGET_PERIOD, float(rcon.ENGINE_DOS_PERIOD))

    rcon.budget_reset()
    for i in range(rcon.BUDGET_PACKETS):
        rcon.budget_take("127.0.0.1", 27500, now=100.0 + i)
    check("budget is spent after BUDGET_PACKETS",
          rcon.budget_left("127.0.0.1", 27500, now=100.0), 0)
    try:
        rcon.budget_take("127.0.0.1", 27500, now=100.0)
        over = "did not raise"
    except rcon.RconThrottled:
        over = "raised"
    check("one packet past the budget is refused", over, "raised")

    # A refusal must not be mistakable for a transport failure: callers treat
    # RconError as "the server has a problem", and this is the opposite.
    check_true("RconThrottled is an RconError",
               issubclass(rcon.RconThrottled, rcon.RconError))

    # Ports are counted separately -- the engine's table is per server process,
    # so spending lobby 1's budget must not silence lobby 2.
    check("a second port has its own budget",
          rcon.budget_left("127.0.0.1", 27510, now=100.0), rcon.BUDGET_PACKETS)

    # The window slides. The packets above were spent one per second starting
    # at t=100, so the LAST one ages out a full period after t=107 -- not
    # after t=100. Getting this wrong is how you write a test that passes
    # while the budget silently never recovers.
    check("budget still partly spent one period after the FIRST packet",
          rcon.budget_left("127.0.0.1", 27500, now=100.0 + rcon.BUDGET_PERIOD + 1),
          2)
    check("budget fully recovers one period after the LAST packet",
          rcon.budget_left("127.0.0.1", 27500,
                           now=100.0 + rcon.BUDGET_PACKETS + rcon.BUDGET_PERIOD),
          rcon.BUDGET_PACKETS)
    rcon.budget_reset()

    # The steady-state rate the panel actually produces must fit, with margin.
    # One status packet per STATUS_TTL, plus three cvar reads per CVAR_TTL.
    per_window = (rcon.ENGINE_DOS_PERIOD / admin.STATUS_TTL
                  + 3 * rcon.ENGINE_DOS_PERIOD / admin.CVAR_TTL)
    check_true("steady-state polling is under half the engine's limit",
               per_window < rcon.ENGINE_DOS_LIMIT / 2)
    check_true("steady-state polling is under our own budget",
               per_window < rcon.BUDGET_PACKETS)

    # The block message the engine sends must be recognised, not shown to the
    # admin as an ordinary empty reply.
    check_true("the engine's block reply is recognised",
               "amplification" in rcon.DDOS_REPLY)

    # ---- a silent lobby is not a dead lobby --------------------------------
    # The panel used to print "no reply (server down...)" for three servers
    # that were heartbeating normally at that moment. Whatever it says now must
    # not assert the server is down.
    fresh(_file={"SURFD_ADMIN_HASH": admin.hash_password("x" * 12, n=2 ** 10),
                 "SURFD_ADMIN_SECRET": "s" * 40,
                 "SURFD_RCON_PASSWORD": "nobody-is-listening"})
    # fresh() replaced sys.modules["rcon"], so the `rcon` bound at the top of
    # main() is NOT the module admin2 talks to. Re-import both, or the budget
    # assertions below would inspect an object nothing is writing to.
    admin2 = importlib.import_module("admin")
    rcon2 = importlib.import_module("rcon")
    check_true("the re-imported rcon is the very object admin uses",
               admin2.budget_left is rcon2.budget_left)
    fleet = admin2.Fleet([{"tier": "1", "port": 1}], "pw")
    snap = fleet.snapshot("1")
    check("a lobby that does not answer is not reported up", snap["up"], False)
    check_true("...and the message does not assert the server is down",
               "server down" not in snap["error"])
    check_true("...and it names the amplification guard as a possible cause",
               "amplification" in snap["error"])

    # Cached: a second snapshot inside the TTL must not send anything.
    rcon2.budget_reset()
    fleet2 = admin2.Fleet([{"tier": "1", "port": 2}], "pw")
    fleet2.snapshot("1")
    spent_once = rcon2.BUDGET_PACKETS - rcon2.budget_left("127.0.0.1", 2)
    fleet2.snapshot("1")
    fleet2.snapshot("1")
    spent_thrice = rcon2.BUDGET_PACKETS - rcon2.budget_left("127.0.0.1", 2)
    check("three snapshots cost no more packets than one",
          spent_thrice, spent_once)
    check_true("...and one snapshot did send something", spent_once > 0)

    # A value we just SET is shown without asking the server for it back.
    fleet2.note_cvar("1", "hostname", "renamed by the test")
    check("a written cvar is served from cache",
          fleet2.snapshot("1")["hostname"], "renamed by the test")
    rcon2.budget_reset()

    for h in HOMES:
        shutil.rmtree(h, ignore_errors=True)

    print()
    if FAILED:
        print("%d FAILURE(S):" % len(FAILED))
        for f in FAILED:
            print("  " + f)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
