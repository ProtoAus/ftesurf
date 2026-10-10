#!/usr/bin/env python3
"""
test_accounts.py -- the falsifier for Steam accounts (accounts.py, steam.py).

    python3 test_accounts.py

Steam is a fake that records every request (`m.STEAM_HTTP`), so a refusal is
graded on what surfd ASKED Steam as well as on what it answered the browser:
a sign-in refused locally must cost Steam nothing.  The only sockets opened
are to a server this file starts on 127.0.0.1, for steam.http's own cases.
"""

import atexit
import hashlib
import importlib
import json
import logging
import os
import shutil
import socket
import socketserver
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.parse

FAILED = []
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# The game's readers (ed25519.py) live in tools/; a sweep that copies only
# surfd/ says where they are.
TOOLS = os.environ.get("ACCOUNTS_TEST_TOOLS") or os.path.join(os.path.dirname(HERE), "tools")
sys.path.insert(0, TOOLS)

import accounts     # noqa: E402  (stateless; surfd imports the same module)
import ed25519      # noqa: E402
import steam        # noqa: E402

BOARD = "https://proto.bar/ftesurf/board"
SID = "76561198000000001"
SID2 = "76561198000000002"
START = 1800000000
TABLES = ["accounts", "keylinks", "linkcodes", "linknonces"]
HERE_ADDR = "127.0.0.1:27510"       # what a client on this box signs for lobby p27510
KEY1, KEY2, KEY3 = (bytes([n]) * 32 for n in (1, 2, 3))     # three installs' seeds


def check(label, got, want):
    ok = got == want
    # ascii(): a Windows console cannot print half of section 13's personas.
    print("%-4s %-66s %s" % ("ok" if ok else "FAIL", ascii(label)[1:-1], ascii(got)))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


class FakeClock(object):
    def __init__(self, now=START):
        self.now = float(now)

    def time(self):
        return self.now

    def monotonic(self):
        return self.now


class FakeSteam(object):
    def __init__(self):
        self.calls = []
        self.timeouts = []
        self.during = None
        self.verdict = b"ns:http://specs.openid.net/auth/2.0\nis_valid:true\n"
        self.down = False
        self.profile = None         # an exception to raise for the profile call
        self.personas = {SID: ("Lex", "a" * 40), SID2: ("Other", "b" * 40)}

    def __call__(self, url, data=None, timeout=None):
        self.calls.append((url, data))
        self.timeouts.append(timeout)
        if self.during:
            hook, self.during = self.during, None
            hook()
        if self.down:
            raise steam.Unavailable("down")
        if data is not None:
            return self.verdict
        if self.profile:
            raise self.profile
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        players = [{"steamid": s, "personaname": self.personas[s][0],
                    "avatarhash": self.personas[s][1]}
                   for s in q["steamids"][0].split(",") if s in self.personas]
        return json.dumps({"response": {"players": players}}).encode("utf-8")

    def posts(self):
        return sum(1 for _, data in self.calls if data is not None)


HOMES = []


@atexit.register
def tidy():
    """Every case makes a home (238 KiB) and a mutant sweep runs 89 suites: one
    day of that left 9,950 of them, 2.3 GiB, in the temp dir."""
    logging.shutdown()                  # the logger holds the first home's file
    for home in HOMES:
        shutil.rmtree(home, ignore_errors=True)


GAME_BYTES = b"FTESurf test csprogs, build 1\n"
GAME = hashlib.sha256(GAME_BYTES).hexdigest()   # what an honest client's proof names


def fresh(board_url=BOARD, steam_key="STEAMKEY", home=None, hosts="127.0.0.1",
          public_host=None, tools=TOOLS):
    home = home or tempfile.mkdtemp(prefix="surfd-acct-")
    if home not in HOMES:
        HOMES.append(home)
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=testkey\n")
    os.environ.update(SURFD_HOME=home, SURFD_DB=os.path.join(home, "test.db"),
                      SURFD_ENV=os.path.join(home, "surfd.env"),
                      SURFD_RUNS=os.path.join(home, "runs"),
                      SURFD_MAPS=os.path.join(home, "maps"),
                      SURFD_WEBSHOTS=os.path.join(home, "webshots"))
    for k in ("SURFD_PUBLIC_HOST", "SURFD_TRUSTED", "SURFD_PROXIES",
              "SURFD_ADMIN_HASH", "SURFD_ADMIN_SECRET", "SURFD_BOARD_URL",
              "SURFD_STEAM_KEY", "SURFD_MOMENTUM", "SURFD_MOMTRACKS",
              "SURFD_LINK_HOSTS", "SURFD_GAME"):
        os.environ.pop(k, None)
    # The lobbies' csprogs, where surfd is told to read it; no .prev yet.
    served = os.path.join(home, "csprogs.dat")
    with open(served, "wb") as fh:
        fh.write(GAME_BYTES)
    if os.path.exists(served + ".prev"):
        os.remove(served + ".prev")
    os.environ["SURFD_GAME_CODE"] = served + "," + served + ".prev"
    os.environ["SURFD_TOOLS"] = tools
    if hosts:
        os.environ["SURFD_LINK_HOSTS"] = hosts
    if public_host:
        os.environ["SURFD_PUBLIC_HOST"] = public_host
    if board_url:
        os.environ["SURFD_BOARD_URL"] = board_url
    if steam_key:
        os.environ["SURFD_STEAM_KEY"] = steam_key
    for mod in ("surfd", "admin", "rcon"):
        sys.modules.pop(mod, None)
    m = importlib.import_module("surfd")
    m.time = FakeClock()
    m.STEAM_HTTP = FakeSteam()
    m.LOOKUPS = []

    def resolve(name):                  # no case may ask the real resolver
        m.LOOKUPS.append(name)
        raise OSError("no resolver in this test")
    m.RESOLVE = resolve
    m._home = home
    m._test_db = os.environ["SURFD_DB"]
    return m


def get(m, path, ip="198.51.100.1", cookie=None, method="GET"):
    """`cookie` is the whole `name=value` pair a browser would send back."""
    headers = {"X-Real-IP": ip}
    if cookie:
        headers["Cookie"] = cookie
    # use_cookies=False: the client's own jar would replace the header, and the
    # cookie's PUBLIC path never matches the /board/ path surfd is asked for.
    return m.app.test_client(use_cookies=False).open(
        path, method=method, headers=headers,
        environ_base={"REMOTE_ADDR": "127.0.0.1"})


def post(m, path, addr="127.0.0.1", **form):
    return m.app.test_client().post(path, data=form,
                                    environ_base={"REMOTE_ADDR": addr})


def body(resp):
    return json.loads(resp.get_data(as_text=True))


def text(resp):
    return resp.get_data(as_text=True)


def rows(m, sql, args=()):
    conn = sqlite3.connect(m._test_db)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def run(m, sql, args=()):
    conn = sqlite3.connect(m._test_db)
    try:
        conn.execute(sql, args)
        conn.commit()
    finally:
        conn.close()


def stamp(at):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(at))


SERIAL = [0]


def start(m, ip="198.51.100.1", k=""):
    """GET /board/link/steam -> (the cookie pair, return_to).  `k` is the
    opener of a start, as the address the game opened carries it."""
    r = get(m, "/board/link/steam" + ("?k=" + k if k else ""), ip=ip)
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(r.headers["Location"]).query)
    return r.headers["Set-Cookie"].split(";")[0], q["openid.return_to"][0]


def assertion(m, return_to, sid=SID):
    SERIAL[0] += 1
    claimed = "https://steamcommunity.com/openid/id/" + sid
    return {
        "openid.ns": steam.NS, "openid.mode": "id_res",
        "openid.op_endpoint": steam.OPENID,
        "openid.claimed_id": claimed, "openid.identity": claimed,
        "openid.return_to": return_to,
        "openid.response_nonce": stamp(m.time.now) + "n%d" % SERIAL[0],
        "openid.assoc_handle": "1234567890",
        "openid.signed": "signed,op_endpoint,claimed_id,identity,return_to,"
                         "response_nonce,assoc_handle",
        "openid.sig": "c2lnbmF0dXJlLi4uLi4uLi4uLi4uLi4=",
    }


def back(m, cookie, return_to, fields, ip="198.51.100.1", extra=(), method="GET"):
    """The browser coming back from Steam with `fields`."""
    path = "/board/link/return?" + urllib.parse.urlsplit(return_to).query
    pairs = list(fields.items()) + list(extra)
    return get(m, path + "&" + urllib.parse.urlencode(pairs), ip=ip, cookie=cookie,
               method=method)


def signin(m, sid=SID, ip="198.51.100.1", mutate=None, extra=(), k=""):
    cookie, return_to = start(m, ip, k)
    fields = assertion(m, return_to, sid)
    if mutate:
        mutate(fields)
    return back(m, cookie, return_to, fields, ip, extra)


def code_of(resp):
    t = text(resp)
    at = t.find('class="linkcode">')
    return t[at + 17:t.find("<", at + 17)] if at >= 0 else ""


def count(m, table):
    return rows(m, "SELECT COUNT(*) FROM " + table)[0][0]


PROOFS = {}
PIN = "482913"


# What engines before Patch 625 signed for an account proof: a run receipt's
# statement with a negative tick count, from the console command.
OLD_STATEMENT = "FTESURF-RCPT 1\nserver %s\nnonce %s\nticks %d\nhid - 0 0\nview -\n"


def proof(seed, nonce, ticks, server=HERE_ADDR, keyed=None, old=False, game=None,
          signed_game=None):
    """What the engine's acct_sign returns for this key: pub, sig, the address
    it signed, whether a key was being pressed (a connect's is not; a link's
    kinds are) and the game code that asked (`game`; `signed_game` when what
    was signed is another).  `old`: signed the way engines before 625 did."""
    if keyed is None:
        keyed = 0 if ticks == accounts.TICKS_HELLO else 1
    game = GAME if game is None else game
    signed_game = game if signed_game is None else signed_game
    k = (seed, nonce, ticks, server, keyed, old, game, signed_game)
    if k not in PROOFS:
        if old:
            msg = (OLD_STATEMENT % (server, nonce, ticks)).encode("utf-8")
        else:
            msg = (accounts.STATEMENT % (server, nonce, ticks, keyed, signed_game)).encode("utf-8")
        PROOFS[k] = {"pub": ed25519.publickey(seed).hex(), "keyed": str(keyed),
                     "sig": ed25519.sign(seed, msg).hex(), "server": server, "game": game}
    return dict(PROOFS[k])


def bare(code):
    return code.replace("-", "")


SALT = "5a17c0de5a17c0de"               # what a client draws for one ask


def salted(code, salt=SALT):
    """A typed code's tag as the game sends it: the salt, then the digest under it."""
    return salt + accounts.typed_tag(salt, bare(code))


def ask(m, seed, code, **kw):
    """A code typed into the box, as lobby p27510 posts it: a salted digest of
    the code, and the key's signature for asking.  Each install has an address
    of its own."""
    form = dict(key="testkey", node="p27510", player="guid-%d" % seed[0],
                ip="10.0.0.%d:27001" % seed[0], tag=salted(code))
    form.update(proof(seed, accounts.ask_nonce(bare(code)), accounts.TICKS_ASK,
                      kw.pop("server", HERE_ADDR), kw.pop("signed_keyed", None),
                      kw.pop("old", False), kw.pop("game", None), kw.pop("signed_game", None)))
    form.update(kw)
    return body(post(m, "/api/link", **form))


def confirm(m, seed, code, pin=PIN, opener=None, number=None, **kw):
    """Enter on the question: the same, signed over the number the lobby
    showed.  For a START (`opener`: the one its client made) the lobby names
    the code by its plain digest, and the sign-in page's `number` goes as the
    client's digest of it with that opener and the pin."""
    form = dict(key="testkey", node="p27510", player="guid-%d" % seed[0],
                ip="10.0.0.%d:27001" % seed[0], pin=pin,
                tag=salted(code) if opener is None else accounts.code_tag(bare(code)))
    if number is not None:
        form["shown"] = accounts.number_proof(opener, pin, number)
    form.update(proof(seed, accounts.confirm_nonce(bare(code), kw.pop("signed_pin", pin)),
                      accounts.TICKS_CONFIRM, kw.pop("server", HERE_ADDR),
                      kw.pop("signed_keyed", None), kw.pop("old", False),
                      kw.pop("game", None), kw.pop("signed_game", None)))
    form.update(kw)
    return body(post(m, "/api/link", **form))


def link(m, seed, code, **kw):
    """Both steps; the confirm's answer, or the ask's if it was not `confirm`."""
    r = ask(m, seed, code, **dict(kw))
    if r.get("why") != "confirm":
        return r
    return confirm(m, seed, code, **kw)


def hello(m, seed, nonce="ab" * 16, **kw):
    """A connect: the lobby's nonce and the client's signature over it."""
    form = dict(key="testkey", node="p27510", nonce=nonce, ip="10.0.0.%d:27001" % seed[0])
    form.update(proof(seed, kw.pop("signed", nonce), kw.pop("ticks", accounts.TICKS_HELLO),
                      kw.pop("server", HERE_ADDR), kw.pop("signed_keyed", None),
                      kw.pop("old", False), kw.pop("game", None), kw.pop("signed_game", None)))
    form.update(kw)
    return body(post(m, "/api/account", **form))


def keys(m):
    return rows(m, "SELECT substr(pub, 1, 8), steamid, node FROM keylinks ORDER BY linked_at, pub")


def verified(m):
    """How many signatures surfd has checked this minute (its own limiter's count)."""
    return sum(len(m._rate.get((b, "*"), ())) for b in ("verify-hello", "verify-link"))


def unspent(m):
    return rows(m, "SELECT used_at, claim FROM linkcodes ORDER BY rowid")


PUB1, PUB2, PUB3 = (ed25519.publickey(k).hex() for k in (KEY1, KEY2, KEY3))
YES = {"acct": 1, "ok": 1, "name": "Lex", "banned": 0}


def no(why, **more):
    return dict({"acct": 1, "ok": 0, "why": why}, **more)


print("\n--- 1. schema ----------------------------------------------------")

m = fresh()
names = {r[0] for r in rows(m, "SELECT name FROM sqlite_master WHERE type='table'")}
check("a fresh database has the four account tables", sorted(names & set(TABLES)), TABLES)
check("...and is stamped schema 15, without 12's guid-keyed `links`",
      (rows(m, "PRAGMA user_version")[0][0], m.SCHEMA_VERSION, "links" in names),
      (15, 15, False))

# An 11 database: the same file with the tables gone and the stamp put back.
home = m._home
conn = sqlite3.connect(m._test_db)
conn.executescript("".join("DROP TABLE %s;" % t for t in TABLES)
                   + "PRAGMA user_version=11;")
conn.close()
m = fresh(home=home)
names = {r[0] for r in rows(m, "SELECT name FROM sqlite_master WHERE type='table'")}
check("a schema-11 database gains them on the next start",
      (sorted(names & set(TABLES)), rows(m, "PRAGMA user_version")[0][0]), (TABLES, 15))

# A 12 database as Patch 612 left it: `links` present, no `keylinks`.
LINKS_12 = """
CREATE TABLE IF NOT EXISTS links (
    player    TEXT    PRIMARY KEY,
    steamid   TEXT    NOT NULL,
    pub       TEXT    NOT NULL DEFAULT '',
    node      TEXT    NOT NULL DEFAULT '',
    linked_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS links_steamid ON links (steamid);
"""
home = m._home
conn = sqlite3.connect(m._test_db)
conn.executescript("DROP TABLE linkcodes; DROP TABLE keylinks;" + accounts.SQL + LINKS_12
                   + "PRAGMA user_version=12;")
conn.close()
m = fresh(home=home)
names = {r[0] for r in rows(m, "SELECT name FROM sqlite_master WHERE type='table'")}
check("a schema-12 database swaps its empty `links` for `keylinks`, and codes learn to be claimed",
      ("links" in names, "keylinks" in names, rows(m, "PRAGMA user_version")[0][0],
       "claim" in [r[1] for r in rows(m, "PRAGMA table_info(linkcodes)")],
       "shown" in [r[1] for r in rows(m, "PRAGMA table_info(linkcodes)")]),
      (False, True, 15, True, True))
conn = sqlite3.connect(m._test_db)
conn.executescript(accounts.SQL + LINKS_12 + "INSERT INTO links (player, steamid, linked_at)"
                   " VALUES ('g', '%s', 1); DROP TABLE keylinks; PRAGMA user_version=12;" % SID)
conn.close()
m = fresh(home=home)
check("...but a `links` somebody filled is left as it was",
      (rows(m, "SELECT player FROM links"), rows(m, "PRAGMA user_version")[0][0]),
      ([("g",)], 15))

# gunicorn and a cron tool do start together on a deploy, and a script commits
# between its statements.  So: an 11 database, and at each CREATE of the
# account steps in turn (step 12's four, and the link table's two, which every
# start makes) ANOTHER process runs them all to the end first.  The Pi's
# two-thread arm met this by luck (test_board.py); here it is every boundary.
m = fresh()
real_connect = m.connect
RACED = []


def finish_elsewhere(what):
    other = sqlite3.connect(m._test_db)
    try:
        other.executescript(accounts.SQL)
        accounts.upgrade_13(other)
        accounts.upgrade_14(other)
        accounts.links_now(other)
        other.execute("PRAGMA user_version=15")
        other.commit()
        RACED[-1][1] = what
    finally:
        other.close()


def racing_connect():
    conn = real_connect()
    seen = []

    def spy(sql):
        # Counted from step 12's first statement: migrate() runs CREATEs of its
        # own before it, and a count from the connection's start raced those.
        words = sql.split()
        if words[:1] != ["CREATE"] or (not seen and "accounts" not in words):
            return
        seen.append(words[words.index("ON") + 1] if words[1] == "INDEX" else words[5])
        if len(seen) == RACED[-1][0]:
            finish_elsewhere(seen[-1])
    conn.set_trace_callback(spy)
    return conn


outcomes = []
for at in range(1, 7):                  # step 12 has four CREATEs, links_now two
    conn = sqlite3.connect(m._test_db)
    conn.executescript("".join("DROP TABLE IF EXISTS %s;" % t for t in TABLES + ["links"])
                       + "PRAGMA user_version=11;")
    conn.close()
    RACED.append([at, "never raced"])
    m.connect = racing_connect
    try:
        m.migrate()
        outcomes.append("ok")
    except Exception as exc:            # noqa: BLE001  (the finding IS the exception)
        outcomes.append(repr(exc))
    finally:
        m.connect = real_connect
names = {r[0] for r in rows(m, "SELECT name FROM sqlite_master WHERE type='table'")}
check("another process finishing the account steps at any of their six statements breaks neither",
      (outcomes, sorted(names & set(TABLES)), "links" in names,
       rows(m, "PRAGMA user_version")[0][0]),
      (["ok"] * 6, TABLES, False, 15))
check("...and those six were the statements raced: each table, and each index by its table",
      [r[1] for r in RACED],
      ["accounts", "linkcodes", "linkcodes", "linknonces", "keylinks", "keylinks"])

print("\n--- 2. off unless SURFD_BOARD_URL is set -------------------------")

m = fresh(board_url=None)
check("no board URL: the three pages are 404",
      [get(m, p).status_code for p in
       ("/board/link", "/board/link/steam", "/board/link/return?s=" + "0" * 32)],
      [404, 404, 404])
check("...and nothing asked Steam", len(m.STEAM_HTTP.calls), 0)
check("...while the lobby routes still exist (403 without a key)",
      [post(m, p, player="g").status_code for p in ("/api/account", "/api/link")],
      [403, 403])
check("...and nothing asked a resolver", m.LOOKUPS, [])


class Quiet(object):
    def error(self, *_a):
        pass


for raw, want in (
        ("https://proto.bar/ftesurf/board", "https://proto.bar/ftesurf/board"),
        ("https://proto.bar/ftesurf/board/", "https://proto.bar/ftesurf/board"),
        ("http://127.0.0.1:8084/board", "http://127.0.0.1:8084/board"),
        ("http://192.168.1.102:8084/board", "http://192.168.1.102:8084/board"),
        ("http://localhost:8084/board", "http://localhost:8084/board"),
        ("http://proto.bar/ftesurf/board", ""),         # a Secure cookie needs https
        ("http://8.8.8.8/board", ""),
        ("proto.bar/ftesurf/board", ""),
        ("https://proto.bar/board?x=1", ""),
        ("https://user@proto.bar/board", ""),
        ("https://proto.bar/board#x", ""),
        ("https://proto.bar/board\n", "https://proto.bar/board"),   # stripped, not matched
        ("https://proto.bar/bo\nard", ""),
        ("javascript:alert(1)", ""),
        ("", "")):
    check("board URL %r" % raw, accounts.load_board_url(raw, Quiet()), want)

print("\n--- 3. the pages -------------------------------------------------")

m = fresh()
r = get(m, "/board/link")
check("the first page is html, uncached, under the board's CSP",
      (r.status_code, r.mimetype, r.headers.get("Cache-Control"),
       "form-action 'none'" in r.headers.get("Content-Security-Policy", "")),
      (200, "text/html", "no-store", True))
check("...links to the sign-in and its own stylesheet, relatively",
      ('href="link/steam"' in text(r), 'href="link.css"' in text(r)), (True, True))
r2 = get(m, "/board/link.css", ip="198.51.100.77")
check("...which is served, as a stylesheet, and asks for no script",
      (r2.status_code, r2.mimetype, "<script" in text(r)), (200, "text/css", False))
check("...and sets no cookie", r.headers.get("Set-Cookie"), None)

r = get(m, "/board/link/steam")
loc = urllib.parse.urlsplit(r.headers["Location"])
q = {k: v[0] for k, v in urllib.parse.parse_qs(loc.query).items()}
setc = r.headers["Set-Cookie"]
cname, token = setc.split(";")[0].split("=", 1)
state = hashlib.sha256(token.encode()).hexdigest()[:32]
check("the sign-in redirects to Steam's OpenID endpoint",
      (r.status_code, "%s://%s%s" % (loc.scheme, loc.netloc, loc.path)),
      (302, steam.OPENID))
check("...asking for any Steam identity, for this site",
      (q["openid.mode"], q["openid.realm"], q["openid.identity"], q["openid.ns"]),
      ("checkid_setup", "https://proto.bar", steam.NS + "/identifier_select", steam.NS))
check("...to come back to the PUBLIC return URL carrying the cookie's digest",
      q["openid.return_to"], BOARD + "/link/return?s=" + state)
attrs = sorted(a.strip().lower() for a in setc.split(";")[1:]
               if not a.strip().lower().startswith("expires"))
check("the state cookie is __Host-, short, Secure, HttpOnly and Lax", (cname, attrs),
      ("__Host-ftl", ["httponly", "max-age=600", "path=/", "samesite=lax", "secure"]))
check("two sign-ins get two tokens", start(m)[0] != start(m)[0], True)

mh = fresh(board_url="http://127.0.0.1:8084/board")
setc = get(mh, "/board/link/steam").headers["Set-Cookie"].lower()
check("a loopback http board gets a plain, path-scoped cookie that is NOT Secure",
      (setc.split("=")[0], "path=/board/link;" in setc, "secure" in setc),
      ("ftl", True, False))
check("...and a sign-in still completes there", len(code_of(signin(mh))), accounts.CODE_LEN + 2)

print("\n--- 4. a sign-in Steam confirms ----------------------------------")

m = fresh()
m.STEAM_HTTP.personas[SID] = ('<b>Lex</b> & "co"', "a" * 40)
r = signin(m)
code = code_of(r)
check("the page shows a code, in fours", (r.status_code, len(code), code[4:5], code[9:10]),
      (200, accounts.CODE_LEN + 2, "-", "-"))
check("...and the persona, escaped",
      "Signed in as <b>&lt;b&gt;Lex&lt;/b&gt; &amp; &quot;co&quot;</b>" in text(r), True)
gone = r.headers.get("Set-Cookie", "").split(";")
check("...uncached, with the state cookie removed under the name and path it was set",
      (r.headers.get("Cache-Control"), gone[0],
       sorted(a.strip().lower() for a in gone[1:]
              if not a.strip().lower().startswith("expires"))),
      ("no-store", "__Host-ftl=",
       ["httponly", "max-age=0", "path=/", "samesite=lax", "secure"]))
check("...and its links resolve from /board/link/return",
      ('href="../link.css"' in text(r), 'href="../../"' in text(r)), (True, True))
calls = m.STEAM_HTTP.calls
check("Steam was asked exactly twice", len(calls), 2)
sent = {k: v[0] for k, v in urllib.parse.parse_qs(calls[0][1].decode()).items()}
check("...first to confirm the assertion: Steam's ten fields, nothing else",
      (calls[0][0], sent["openid.mode"], sent["openid.claimed_id"][-17:],
       sent["openid.sig"], set(sent) == steam.FIELDS),
      (steam.OPENID, "check_authentication", SID,
       "c2lnbmF0dXJlLi4uLi4uLi4uLi4uLi4=", True))
pq = urllib.parse.parse_qs(urllib.parse.urlsplit(calls[1][0]).query)
check("...then for the profile, with the key",
      (calls[1][0].startswith(steam.SUMMARIES), calls[1][1], pq["key"], pq["steamids"]),
      (True, None, ["STEAMKEY"], [SID]))
check("...each given a socket timeout, the two summing under nginx's 5 s",
      (None not in m.STEAM_HTTP.timeouts, sum(m.STEAM_HTTP.timeouts) < 5.0), (True, True))
check("the account is stored with its persona and avatar",
      rows(m, "SELECT steamid, name, avatar, banned_at FROM accounts"),
      [(SID, '<b>Lex</b> & "co"', "a" * 40, 0)])
check("...and the code, unredeemed, against that account",
      rows(m, "SELECT code, steamid, used_at FROM linkcodes"),
      [(code.replace("-", ""), SID, 0)])
check("...and the assertion, as seen", count(m, "linknonces"), 1)

print("\n--- 5. refusals that must cost Steam nothing ---------------------")


def drop(key):
    return lambda f: f.pop(key)


def put(key, value):
    return lambda f: f.__setitem__(key, value)


def both(value):
    return lambda f: f.update({"openid.claimed_id": value, "openid.identity": value})


def signed_without(name):
    def go(f):
        f["openid.signed"] = ",".join(
            n for n in f["openid.signed"].split(",") if n != name)
    return go


ID = "https://steamcommunity.com/openid/id/"
SIGNED = "signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle"
CASES = [
    ("another OpenID provider's endpoint",
     put("openid.op_endpoint", "https://evil.example/openid/login"), 400),
    ("a claimed_id on another host", both("https://evil.example/openid/id/" + SID), 400),
    ("a claimed_id that is not the identity", put("openid.claimed_id", ID + SID2), 400),
    ("an id outside the account universe", both(ID + "12345678901234567"), 400),
    ("a claimed_id with a suffix", both(ID + SID + "/x"), 400),
    ("a claimed_id with a trailing newline", both(ID + SID + "\n"), 400),
    ("a return_to for another site",
     put("openid.return_to", "https://evil.example/link/return?s=" + "0" * 32), 400),
    ("a signature that does not cover claimed_id", signed_without("claimed_id"), 400),
    ("a signature that does not cover return_to", signed_without("return_to"), 400),
    ("a signature that does not cover the nonce", signed_without("response_nonce"), 400),
    ("a signed list naming a field twice", put("openid.signed", SIGNED + ",identity"), 400),
    ("a signed list with a name too many", put("openid.signed", SIGNED + ",sig"), 400),
    ("a signed list naming a field Steam does not send",
     put("openid.signed", SIGNED.replace("assoc_handle", "assoc.handle")), 400),
    ("a field Steam signs that is absent", drop("openid.assoc_handle"), 400),
    ("no signature", drop("openid.sig"), 400),
    ("no namespace", drop("openid.ns"), 400),
    ("OpenID 1.1's namespace", put("openid.ns", "http://openid.net/signon/1.1"), 400),
    ("a mode that is not an assertion", put("openid.mode", "setup_needed"), 400),
    ("a nonce a second past the window",
     lambda f: f.__setitem__("openid.response_nonce",
                             stamp(START - steam.NONCE_SKEW - 1) + "x"), 400),
    ("a nonce a second ahead of the window",
     lambda f: f.__setitem__("openid.response_nonce",
                             stamp(START + steam.NONCE_SKEW + 1) + "x"), 400),
    ("a nonce that is not a timestamp", put("openid.response_nonce", "yesterday"), 400),
    ("a nonce with a 65-character tail",
     lambda f: f.__setitem__("openid.response_nonce", stamp(START) + "t" * 65), 400),
    ("a nonce with a trailing newline",
     lambda f: f.__setitem__("openid.response_nonce", f["openid.response_nonce"] + "\n"), 400),
    ("a field holding a space", put("openid.assoc_handle", "12 34"), 400),
    ("a field over %d characters" % steam.MAX_VALUE,
     put("openid.sig", "A" * (steam.MAX_VALUE + 1)), 400),
    ("an empty field", put("openid.assoc_handle", ""), 400),
    ("a cancelled sign-in", put("openid.mode", "cancel"), 200),
]
m = fresh()
for n, (label, mutate, want) in enumerate(CASES):
    r = signin(m, ip="198.51.100.%d" % (10 + n), mutate=mutate)
    check(label, (r.status_code, code_of(r), len(m.STEAM_HTTP.calls),
                  count(m, "linkcodes"), count(m, "linknonces")), (want, "", 0, 0, 0))

# A name Steam's own parser might fold onto a real field must never reach it.
for n, extra in enumerate((("openid.claimed.id", ID + SID2), ("openid.Claimed_id", ID + SID2),
                           ("openid.identity\x00x", ID + SID2),
                           ("openid.invalidate_handle", "h"), ("openid.x", "1"))):
    r = signin(m, ip="198.51.101.%d" % (10 + n), extra=[extra])
    check("an extra field %r" % extra[0],
          (r.status_code, code_of(r), len(m.STEAM_HTTP.calls)), (400, "", 0))
r = signin(m, ip="198.51.101.1", extra=[("openid.claimed_id", ID + SID2)])
check("a field sent twice",
      (r.status_code, code_of(r), len(m.STEAM_HTTP.calls)), (400, "", 0))

cookie, return_to = start(m, "198.51.101.3")
fields = assertion(m, return_to)
r = get(m, "/board/link/return?s=nothex&" + urllib.parse.urlencode(fields),
        ip="198.51.101.3", cookie=cookie)
check("a malformed state", (r.status_code, len(m.STEAM_HTTP.calls)), (400, 0))
r = get(m, "/board/link/return?s=" + urllib.parse.urlsplit(return_to).query[2:]
        + "%0A&" + urllib.parse.urlencode(fields), ip="198.51.101.3", cookie=cookie)
check("a state with a trailing newline", (r.status_code, len(m.STEAM_HTTP.calls)), (400, 0))
r = back(m, cookie, return_to, fields, "198.51.101.3", method="HEAD")
check("a HEAD is refused and spends nothing",
      (r.status_code, len(m.STEAM_HTTP.calls), count(m, "linknonces")), (405, 0, 0))

# The controls: the same harness, unmutated and at the edge of the window.
r = back(m, cookie, return_to, fields, "198.51.101.3")
check("CONTROL that same assertion, as a GET, is accepted and Steam is asked",
      (r.status_code, len(code_of(r)), len(m.STEAM_HTTP.calls)), (200, accounts.CODE_LEN + 2, 2))
r = signin(m, ip="198.51.101.4",
           mutate=lambda f: f.__setitem__("openid.response_nonce",
                                          stamp(START - steam.NONCE_SKEW) + "e"))
check("CONTROL a nonce exactly at the window's edge is accepted",
      (r.status_code, len(code_of(r)), len(m.STEAM_HTTP.calls)), (200, accounts.CODE_LEN + 2, 4))

print("\n--- 6. the browser that comes back must be the one that left -----")

# A victim signs in through a link the attacker started, lands without the
# attacker's cookie, and is talked into sending the address back.
m = fresh()
cookie, return_to = start(m, "203.0.113.66")
fields = assertion(m, return_to, SID2)             # the victim's own, valid, assertion
r = back(m, None, return_to, fields, "198.51.100.77")
check("no state cookie: refused, unasked, and the assertion is burned",
      (r.status_code, len(m.STEAM_HTTP.calls), count(m, "linknonces")), (400, 0, 1))
r = back(m, cookie, return_to, fields, "203.0.113.66")
check("...so the cookie's owner cannot finish it with the address handed back",
      (r.status_code, "already been used" in text(r), code_of(r),
       len(m.STEAM_HTTP.calls)), (400, True, "", 0))

cookie, return_to = start(m, "203.0.113.67")
other, _ = start(m, "203.0.113.67")
fields = assertion(m, return_to)
r = back(m, other, return_to, fields, "203.0.113.67")
check("another sign-in's cookie: refused, unasked, burned",
      (r.status_code, len(m.STEAM_HTTP.calls), count(m, "linknonces")), (400, 0, 2))

# Made-up strays may fill half the table and no more: the rest is for sign-ins.
m = fresh(steam_key=None)
conn = sqlite3.connect(m._test_db)
conn.executemany("INSERT INTO linknonces (nonce, seen_at) VALUES (?,?)",
                 [("s%d" % i, START) for i in range(accounts.NONCE_STRAY - 1)])
conn.commit()
conn.close()
strays = []
for n in range(3):
    cookie, return_to = start(m, "203.0.119.%d" % n)
    strays.append(back(m, None, return_to, assertion(m, return_to), "203.0.119.%d" % n))
check("strays are recorded up to half the table, and not past it",
      ([r.status_code for r in strays], count(m, "linknonces")),
      ([400, 400, 400], accounts.NONCE_STRAY))
check("...so they cannot close sign-in, however many arrive",
      (signin(m, ip="203.0.119.9").status_code, count(m, "linknonces")),
      (200, accounts.NONCE_STRAY + 1))
check("a record is kept for as long as its nonce could still pass, and not for an hour",
      2 * steam.NONCE_SKEW <= accounts.NONCE_KEEP <= 600, True)

print("\n--- 7. what Steam answers: yes, no, and nothing ------------------")

m = fresh()
m.STEAM_HTTP.verdict = b"ns:http://specs.openid.net/auth/2.0\nis_valid:false\n"
r = signin(m, ip="198.51.100.2")
check("Steam says no: refused, asked once, nothing stored",
      (r.status_code, "did not confirm" in text(r), len(m.STEAM_HTTP.calls),
       count(m, "linkcodes"), count(m, "accounts")), (400, True, 1, 0, 0))
for n, (label, reply, want) in enumerate((
        ("is_valid must be exactly true", b"is_valid:truely\n", 400),
        ("a reply with no verdict is UNAVAILABLE, not a refusal", b"<html>busy</html>", 503),
        ("two verdicts that disagree are UNAVAILABLE",
         b"is_valid:false\ninvalidate_handle:h\nis_valid:true\n", 503),
        ("...in either order", b"is_valid:true\nis_valid:false\n", 503),
        ("a reply that is not text", b"\xff\xfe", 503))):
    m.STEAM_HTTP.verdict = reply
    r = signin(m, ip="198.51.100.%d" % (30 + n))
    check(label, (r.status_code, "could not be reached" in text(r),
                  count(m, "linkcodes")), (want, want == 503, 0))
m.STEAM_HTTP.verdict = b"is_valid:true\n"
m.STEAM_HTTP.down = True
r = signin(m, ip="198.51.100.5")
check("Steam unreachable is UNAVAILABLE too",
      (r.status_code, "could not be reached" in text(r), count(m, "linkcodes")),
      (503, True, 0))
m.STEAM_HTTP.down = False
for n, (label, exc) in enumerate((("unavailable", steam.Unavailable("status 500")),
                                  ("an error nobody planned for", RuntimeError("k=SECRET")))):
    m.STEAM_HTTP.profile = exc
    r = signin(m, ip="198.51.100.%d" % (40 + n))
    check("no profile (%s): the code is still issued, named by the id" % label,
          (r.status_code, len(code_of(r)), "Steam account " + SID in text(r),
           rows(m, "SELECT name FROM accounts")), (200, accounts.CODE_LEN + 2, True, [("",)]))
# The logger outlives a re-import, so its file is the FIRST case's, not m._home's.
logged = open(m.log.handlers[0].baseFilename).read()
check("...and the unplanned error is logged by its type, never its text",
      ("no profile for %s (RuntimeError)" % SID in logged, "k=SECRET" in logged),
      (True, False))
m.STEAM_HTTP.profile = None
m.STEAM_HTTP.personas[SID] = ("ab\ud83d", "a" * 40)       # half of a surrogate pair
r = signin(m, ip="198.51.100.6")
check("a persona that is not valid Unicode is stored as something that is",
      (r.status_code, len(code_of(r)), rows(m, "SELECT name FROM accounts")),
      (200, accounts.CODE_LEN + 2, [("ab?",)]))

mk = fresh(steam_key=None)
r = signin(mk)
check("no SURFD_STEAM_KEY: one request, and no profile asked for",
      (r.status_code, len(code_of(r)), len(mk.STEAM_HTTP.calls)), (200, accounts.CODE_LEN + 2, 1))

print("\n--- 8. one assertion, one code; one account, one live code -------")

m = fresh()
cookie, return_to = start(m)
fields = assertion(m, return_to)
r1 = back(m, cookie, return_to, fields)
asked = len(m.STEAM_HTTP.calls)
r2 = back(m, cookie, return_to, fields)
check("the same assertion again is refused without asking Steam",
      (r1.status_code, r2.status_code, "already been used" in text(r2),
       len(m.STEAM_HTTP.calls) - asked, count(m, "linkcodes")), (200, 400, True, 0, 1))
first = code_of(r1).replace("-", "")
second = code_of(signin(m, ip="198.51.100.7")).replace("-", "")
check("a second sign-in supersedes the first code, and keeps its row",
      rows(m, "SELECT code, used_by FROM linkcodes ORDER BY rowid"),
      [(first, accounts.SUPERSEDED), (second, "")])
check("the superseded code does not link", link(m, KEY1, first), no("code"))

run(m, "UPDATE accounts SET banned_at = ? WHERE steamid = ?", (START, SID))
r = signin(m, ip="198.51.100.8")
check("a banned account signs in and gets no code: none shown, none made, none retired",
      (r.status_code, "is banned" in text(r), code_of(r),
       rows(m, "SELECT code FROM linkcodes WHERE used_at = 0"), count(m, "linkcodes")),
      (403, True, "", [(second,)], 2))

m = fresh(steam_key=None)
m.STEAM_HTTP.down = True
cookie, return_to = start(m)
fields = assertion(m, return_to)
r = back(m, cookie, return_to, fields)
m.STEAM_HTTP.down = False
check("an assertion Steam could not be asked about is spent all the same",
      (r.status_code, back(m, cookie, return_to, fields).status_code), (503, 400))

print("\n--- 9. limits ----------------------------------------------------")

m = fresh()
hits = [get(m, "/board/link", ip="203.0.113.5").status_code for _ in range(11)]
check("ten page hits a minute per source, then 429", (hits[:10], hits[10]),
      ([200] * 10, 429))
check("...another source is unaffected",
      get(m, "/board/link", ip="203.0.113.6").status_code, 200)
hits = [get(m, "/board/link/steam", ip="203.0.113.10").status_code for _ in range(11)]
check("the same limit on the redirect", (hits[:10], hits[10]), ([302] * 10, 429))
hits = [get(m, "/board/link/return?s=x", ip="203.0.113.11").status_code for _ in range(11)]
check("...and on the return", (hits[:10], hits[10]), ([400] * 10, 429))

m = fresh(steam_key=None)
got = [signin(m, ip="203.0.113.7").status_code for _ in range(accounts.OUT_SOURCE_MAX + 1)]
check("one source may have Steam asked %d times a minute" % accounts.OUT_SOURCE_MAX,
      (got, m.STEAM_HTTP.posts()), ([200] * accounts.OUT_SOURCE_MAX + [503],
                                    accounts.OUT_SOURCE_MAX))
m.time.now += 61
m.STEAM_HTTP.verdict = b"is_valid:false\n"
r1 = signin(m, ip="203.0.113.8")
m.STEAM_HTTP.verdict = b"is_valid:true\n"
r2 = signin(m, ip="203.0.113.8")
check("a source Steam refused waits out the minute, unasked",
      (r1.status_code, r2.status_code, m.STEAM_HTTP.posts()),
      (400, 503, accounts.OUT_SOURCE_MAX + 1))
m.time.now += 61
check("...and is welcome after it", signin(m, ip="203.0.113.8").status_code, 200)

# Three addresses forging returns as fast as the page limit lets them.
m = fresh(steam_key=None)
m.STEAM_HTTP.verdict = b"is_valid:false\n"
forged = []
for a in range(3):
    for _ in range(5):
        forged.append(signin(m, ip="203.0.118.%d" % a).status_code)
m.STEAM_HTTP.verdict = b"is_valid:true\n"
check("15 forged returns from 3 addresses cost Steam 3 questions, not 15",
      (forged.count(400), forged.count(503), m.STEAM_HTTP.posts()), (3, 12, 3))
check("...and an honest sign-in in the same minute goes through",
      signin(m, ip="203.0.118.9").status_code, 200)

m = fresh(steam_key=None)
got = [signin(m, ip="203.0.114.%d" % i).status_code
       for i in range(accounts.OUT_RATE_MAX + 1)]
check("Steam is asked at most %d times a minute, whoever is asking"
      % accounts.OUT_RATE_MAX,
      (got[:-1] == [200] * accounts.OUT_RATE_MAX, got[-1], len(m.STEAM_HTTP.calls)),
      (True, 503, accounts.OUT_RATE_MAX))
m.time.now += 61
check("...and again once the minute has passed",
      signin(m, ip="203.0.115.1").status_code, 200)

# Two sign-ins held open inside Steam, and a third arriving while they are.
m = fresh(steam_key=None)
third = []


def second():
    m.STEAM_HTTP.during = lambda: third.append(signin(m, ip="203.0.117.3"))
    third.append(signin(m, ip="203.0.117.2"))


m.STEAM_HTTP.during = second
first = signin(m, ip="203.0.117.1")
check("%d sign-ins may be waiting on Steam at once; the next is turned away unasked"
      % accounts.OUT_ATONCE,
      (first.status_code, [r.status_code for r in third], len(m.STEAM_HTTP.calls)),
      (200, [503, 200], 2))
check("...and the gate is released afterwards",
      signin(m, ip="203.0.117.4").status_code, 200)
cookie, return_to = start(m, "203.0.117.5")
fields = assertion(m, return_to)
m.STEAM_HTTP.during = lambda: third.append(back(m, cookie, return_to, fields, "203.0.117.5"))
r = back(m, cookie, return_to, fields, "203.0.117.5")
check("one assertion arriving twice at once yields one code",
      (r.status_code, third[-1].status_code, "already been used" in text(third[-1])),
      (200, 400, True))

m = fresh(steam_key=None)
conn = sqlite3.connect(m._test_db)
conn.executemany("INSERT INTO linkcodes (code, steamid, issued_at) VALUES (?,?,?)",
                 [("C%07d" % i, SID2, START) for i in range(accounts.CODE_LIVE_MAX)])
conn.commit()
conn.close()
r = signin(m)
check("with %d codes outstanding a sign-in waits, unasked" % accounts.CODE_LIVE_MAX,
      (r.status_code, len(m.STEAM_HTTP.calls)), (503, 0))
m.time.now += accounts.CODE_KEEP + 1
r = signin(m, ip="203.0.116.1")
check("a day on, the old rows are pruned by the next sign-in",
      (r.status_code, count(m, "linkcodes")), (200, 1))

m = fresh(steam_key=None)
conn = sqlite3.connect(m._test_db)
conn.executemany("INSERT INTO linknonces (nonce, seen_at) VALUES (?,?)",
                 [("n%d" % i, START) for i in range(accounts.NONCE_MAX)])
conn.commit()
conn.close()
r = signin(m)
check("with %d assertions on record a sign-in waits, unasked" % accounts.NONCE_MAX,
      (r.status_code, len(m.STEAM_HTTP.calls)), (503, 0))
m.time.now += accounts.NONCE_KEEP + 1
r = signin(m, ip="203.0.116.2")
check("an hour on, they are pruned by the next sign-in",
      (r.status_code, count(m, "linknonces")), (200, 1))

print("\n--- 10. asking: the key signs for the code and claims it ---------")

m = fresh()
code = code_of(signin(m))
good = dict(key="testkey", node="p27510", player="guid-1", ip="10.0.0.1:27001",
            tag=salted(code),
            **proof(KEY1, accounts.ask_nonce(bare(code)), accounts.TICKS_ASK))
check("no key, a wrong key, a non-ASCII key",
      [post(m, "/api/link", **dict(good, **kw)).status_code
       for kw in ({"key": ""}, {"key": "nope"}, {"key": "ключ"})],
      [403, 403, 403])
check("the right key from an untrusted address",
      post(m, "/api/link", addr="203.0.113.9", **good).status_code, 403)
for n, bad in enumerate(("", bare(code), "ab" * 15, "AB" * 16, "ab" * 16 + "\n", "'; DROP TABLE x;--")):
    check("a tag that is not 32 hex: %r" % bad[:12],
          body(post(m, "/api/link", **dict(good, tag=bad, ip="10.9.0.%d" % n))), no("code"))
check("a well-formed tag of a code nobody was given",
      body(post(m, "/api/link", **dict(good, tag=salted("ABCDEFGHJKLM"), ip="10.9.1.1"))),
      no("code"))
check("...and none of those had a signature checked or touched the code",
      (verified(m), unspent(m)), (0, [(0, "")]))

other = accounts.ask_nonce("ABCDEFGH")
BAD = [
    ("no proof at all", dict(pub="", sig="", server=""), "proof"),
    ("a key that is not 64 hex", dict(pub=PUB1[:62]), "proof"),
    ("a signature that is not hex", dict(sig="z" * 128), "proof"),
    ("a signature with a trailing newline", dict(sig=good["sig"] + "\n"), "proof"),
    ("an address with a space in it", dict(server="127.0.0.1:27510 x"), "proof"),
    ("another key's signature under this key's name", dict(pub=PUB2), "proof"),
    ("this key's signature over another code", dict(sig=proof(KEY1, other, -3)["sig"]), "proof"),
    ("a CONNECT's signature over the right nonce: the wrong kind",
     dict(sig=proof(KEY1, accounts.ask_nonce(bare(code)), accounts.TICKS_HELLO)["sig"]), "proof"),
    ("a CONFIRM's signature in an ask's place",
     dict(sig=proof(KEY1, accounts.ask_nonce(bare(code)), accounts.TICKS_CONFIRM)["sig"]), "proof"),
    ("a run receipt's shape (ticks 0) over the right nonce",
     dict(sig=proof(KEY1, accounts.ask_nonce(bare(code)), 0)["sig"]), "proof"),
    ("the right nonce and kind, signed the way engines before Patch 625 signed",
     dict(sig=proof(KEY1, accounts.ask_nonce(bare(code)), -3, old=True)["sig"]), "proof"),
    ("the engine's own signature, made with no key pressed",
     proof(KEY1, accounts.ask_nonce(bare(code)), -3, keyed=0), "proof"),
    ("...and that signature with its flag turned on by somebody on the way",
     dict(proof(KEY1, accounts.ask_nonce(bare(code)), -3, keyed=0), keyed="1"), "proof"),
    ("a flag that is neither 0 nor 1", dict(keyed="yes"), "proof"),
    ("the code's digest with no salt, as before Patch 625",
     dict(tag=accounts.code_tag(bare(code))), "code"),
    ("a key of small order, which anybody can sign under",
     dict(pub="01" + "00" * 31, sig="01" + "00" * 63), "proof"),
    ("a signature made on somebody else's server",
     proof(KEY1, accounts.ask_nonce(bare(code)), -3, "203.0.113.7:27510"), "server"),
    ("...or for another of our ports",
     proof(KEY1, accounts.ask_nonce(bare(code)), -3, "127.0.0.1:27520"), "server"),
    ("...or posted by a lobby on another port", dict(node="p27520"), "server"),
    ("...or by a lobby that names no port, for an address with none",
     dict(node="p", **proof(KEY1, accounts.ask_nonce(bare(code)), -3, "127.0.0.1:")), "server"),
    ("an address that is a name, not a number",
     proof(KEY1, accounts.ask_nonce(bare(code)), -3, "play.proto.bar:27510"), "server"),
    ("an address with no port", dict(server="127.0.0.1"), "server"),
]
for n, (label, change, why) in enumerate(BAD):
    r = body(post(m, "/api/link", **dict(good, ip="10.9.2.%d" % n, **change)))
    check(label, (r, keys(m), unspent(m)), (no(why), [], [(0, "")]))

r = post(m, "/api/link", **good)
check("CONTROL the same request untampered is answered: confirm, and who it is for",
      (r.status_code, r.mimetype, body(r)),
      (200, "application/json", no("confirm", to="Lex", **{"from": ""})))
check("...the code is CLAIMED by that key, and still unspent, and nothing is linked",
      (unspent(m), keys(m)), ([(0, PUB1)], []))
check("asking again with the same key is the same answer", ask(m, KEY1, code),
      no("confirm", to="Lex", **{"from": ""}))
check("another key asking with a claimed code is told it is no good",
      (ask(m, KEY2, code), unspent(m)), (no("code"), [(0, PUB1)]))

print("\n--- 11. confirming: the key signs the number it was shown --------")

check("another key cannot confirm what it did not ask for",
      (confirm(m, KEY2, code), keys(m)), (no("code"), []))
for label, kw, why in (
        ("a number that is not six digits", dict(pin="12345"), "code"),
        ("...or has a letter in it", dict(pin="12345a"), "code"),
        ("...or a seventh digit, though the key signed all seven", dict(pin=PIN + "0"), "code"),
        ("a signature over a different number than the one posted",
         dict(signed_pin="000000"), "proof"),
        ("an ASK's signature in a confirm's place",
         dict(sig=proof(KEY1, accounts.confirm_nonce(bare(code), PIN), accounts.TICKS_ASK)["sig"]),
         "proof"),
        ("the ask's own signature, replayed with a number",
         dict(sig=good["sig"]), "proof")):
    check(label, (confirm(m, KEY1, code, **kw), keys(m), unspent(m)), (no(why), [], [(0, PUB1)]))
m.time.now += 61            # the refusals above were install 1's eight steps for the minute
r = confirm(m, KEY1, code)
check("CONTROL the claiming key, signing the number, links", r, YES)
check("...stored against the key, with the guid and lobby it came from",
      rows(m, "SELECT pub, steamid, player, node FROM keylinks"),
      [(PUB1, SID, "guid-1", "p27510")])
check("...and the code is spent, marked with the key that spent it",
      rows(m, "SELECT used_at > 0, used_by FROM linkcodes"), [(1, PUB1[:16])])
m.time.now += 61            # this section spent install 1's eight steps for the minute
check("a spent code answers nobody, not even its own key",
      (ask(m, KEY1, code), confirm(m, KEY1, code), ask(m, KEY2, code)),
      (no("code"), no("code"), no("code")))

m.time.now += 61
code = code_of(signin(m, ip="198.51.100.20"))
m.time.now += accounts.CODE_TTL
check("a code is good at exactly ten minutes", link(m, KEY2, code), YES)
code = code_of(signin(m, ip="198.51.100.21"))
ask(m, KEY3, code)
m.time.now += accounts.CODE_TTL + 1
check("...and not a second later, even claimed", confirm(m, KEY3, code), no("code"))
check("one account now holds two installs", keys(m),
      [(PUB1[:8], SID, "p27510"), (PUB2[:8], SID, "p27510")])
m.time.now += 61
code = code_of(signin(m, ip="198.51.100.30"))
check("an install asking with a new code for its own account is not told it would move",
      ask(m, KEY1, code), no("confirm", to="Lex", **{"from": ""}))
m.STEAM_HTTP.personas[SID] = ("Lex2", "c" * 40)
signin(m, ip="198.51.100.27")
check("a later sign-in refreshes the stored persona and avatar",
      rows(m, "SELECT name, avatar FROM accounts WHERE steamid = ?", (SID,)),
      [("Lex2", "c" * 40)])
m.STEAM_HTTP.personas[SID] = ("Lex", "a" * 40)
signin(m, ip="198.51.100.28")

print("\n--- 12. moving a key, bans, and what a guid is worth -------------")

m.time.now += 61
code = code_of(signin(m, sid=SID2, ip="198.51.100.22"))
check("asking with another account's code says where the key is and where it would go",
      (ask(m, KEY2, code), keys(m)[1]),
      (no("confirm", to="Other", **{"from": "Lex"}), (PUB2[:8], SID, "p27510")))
r = confirm(m, KEY2, code)
check("...and confirming moves it, dated now",
      (r, rows(m, "SELECT steamid, linked_at FROM keylinks WHERE pub = ?", (PUB2,))),
      (dict(YES, name="Other"), [(SID2, int(m.time.now))]))

# An attacker who harvested install 1's guid presents it with their own key.
m.time.now += 61
code = code_of(signin(m, sid=SID2, ip="198.51.100.29"))
r = link(m, KEY3, code, player="guid-1")
check("a harvested guid moves nothing but the key that signed",
      (r["ok"], rows(m, "SELECT steamid FROM keylinks WHERE pub = ?", (PUB1,)),
       rows(m, "SELECT steamid, player FROM keylinks WHERE pub = ?", (PUB3,))),
      (1, [(SID,)], [(SID2, "guid-1")]))

m.time.now += 61
code = code_of(signin(m, sid=SID2, ip="198.51.100.23"))
check("(asked, before the ban)", ask(m, KEY1, code)["why"], "confirm")
run(m, "UPDATE accounts SET banned_at = ? WHERE steamid = ?", (START, SID2))
check("a code for an account banned since it was asked for does not link",
      (confirm(m, KEY1, code), ask(m, KEY1, code)), (no("banned"), no("banned")))
check("...and is not spent by the attempt",
      rows(m, "SELECT used_at FROM linkcodes WHERE code = ?", (bare(code),)), [(0,)])
check("a banned account's install is told so when it connects", hello(m, KEY2),
      {"acct": 1, "linked": 1, "name": "Other", "banned": 1})
# KEY2 was talked into a stranger's code, and the stranger got banned.
code = code_of(signin(m, sid=SID, ip="198.51.100.24"))
check("...and its owner can still take it back to their own account",
      (ask(m, KEY2, code), confirm(m, KEY2, code), hello(m, KEY2)["banned"]),
      (no("confirm", to="Lex", **{"from": "Other"}), YES, 0))

print("\n--- 12a. who a connection is -------------------------------------")

check("no key / untrusted address",
      [post(m, "/api/account", nonce="ab" * 16).status_code,
       post(m, "/api/account", addr="203.0.113.9", key="testkey",
            nonce="ab" * 16).status_code], [403, 403])
check("a nonce that is not the lobby's 32 hex",
      [post(m, "/api/account", key="testkey", nonce=n).status_code
       for n in ("", "ab" * 15, "AB" * 16, "ab" * 16 + "\n")], [400, 400, 400, 400])
before = verified(m)
check("a key nobody linked", hello(m, bytes([9]) * 32), {"acct": 1, "linked": 0})
check("...was checked before that was said", verified(m) - before, 1)
check("a linked key, and nothing about the account but its name and standing",
      hello(m, KEY1), {"acct": 1, "linked": 1, "name": "Lex", "banned": 0})
check("a signature over some other nonce (a replayed connect)",
      hello(m, KEY1, nonce="cd" * 16, signed="ab" * 16), {"acct": 1, "linked": 0, "why": "proof"})
check("an ASK's or a run's signature over the lobby's nonce: the wrong kind",
      [hello(m, KEY1, ticks=t)["why"] for t in (accounts.TICKS_ASK, accounts.TICKS_CONFIRM, 0, -1)],
      ["proof"] * 4)
check("a signature made on somebody else's server",
      hello(m, KEY1, server="203.0.113.7:27510"), {"acct": 1, "linked": 0, "why": "server"})
check("another key's signature under a linked key's name",
      hello(m, bytes([9]) * 32, pub=PUB1), {"acct": 1, "linked": 0, "why": "proof"})
check("no proof", body(post(m, "/api/account", key="testkey", node="p27510",
                           nonce="ab" * 16)), {"acct": 1, "linked": 0, "why": "proof"})

m = fresh()
m.STEAM_HTTP.personas[SID] = ('^1Lex";quit\\', "a" * 40)
code = code_of(signin(m))
check("a hostile persona reaches the lobby as a safe name, on all three answers",
      (ask(m, KEY1, code)["to"], confirm(m, KEY1, code)["name"], hello(m, KEY1)["name"],
       rows(m, "SELECT name FROM accounts")),
      ("1Lexquit", "1Lexquit", "1Lexquit", [('^1Lex";quit\\',)]))

# The addresses a client may sign: SURFD_LINK_HOSTS, and what the public name resolves to.
m = fresh(hosts="192.168.1.102", public_host="play.proto.bar")
answers = [{"203.0.113.50"}]


def resolver(name):
    m.LOOKUPS.append(name)
    if not answers:
        raise OSError("resolver down")
    return answers[0]


m.RESOLVE = resolver
code = code_of(signin(m))
NOBODY = {"acct": 1, "linked": 0}
check("the public name's address, v4 or v4-in-v6, and the LAN's are ours",
      [hello(m, KEY1, server=a) for a in
       ("203.0.113.50:27510", "[::ffff:203.0.113.50]:27510", "192.168.1.102:27510")],
      [NOBODY] * 3)
check("...loopback is not, unless it is listed", hello(m, KEY1),
      dict(NOBODY, why="server"))
check("...and the name was looked up once for all of that", m.LOOKUPS, ["play.proto.bar"])
answers.pop()
m.time.now += accounts.HOSTS_TTL + 1
check("a lookup that fails later keeps the last answer",
      (hello(m, KEY1, server="203.0.113.50:27510"), len(m.LOOKUPS)), (NOBODY, 2))
check("...is not repeated for every question while it fails",
      ([hello(m, KEY1, server="203.0.113.50:27510") for _ in range(3)], len(m.LOOKUPS)),
      ([NOBODY] * 3, 2))
m.time.now += accounts.HOSTS_RETRY + 1
check("...is tried again after a while", (hello(m, KEY1, server="203.0.113.50:27510"),
                                         len(m.LOOKUPS)), (NOBODY, 3))
check("...and a link works through it",
      link(m, KEY1, code, server="203.0.113.50:27510")["ok"], 1)
m.time.now += accounts.HOSTS_STALE
check("a day of failed lookups: the old answer is no longer believed, and that is not a no",
      hello(m, KEY1, server="203.0.113.50:27510"), dict(NOBODY, why="later"))

m = fresh(hosts="192.168.1.102", public_host="play.proto.bar")
code = code_of(signin(m))
check("a name that has NEVER resolved: not a refusal, try later; nothing spent",
      (hello(m, KEY1, server="203.0.113.50:27510"),
       ask(m, KEY1, code, server="203.0.113.50:27510"), unspent(m), verified(m)),
      (dict(NOBODY, why="later"), no("later"), [(0, "")], 0))
check("...while a listed address needs no lookup", hello(m, KEY1, server="192.168.1.102:27510"),
      NOBODY)

m = fresh(hosts=None)
check("no address configured at all: every signature is for somebody else's server",
      hello(m, KEY1), dict(NOBODY, why="server"))

m = fresh(tools=tempfile.mkdtemp(prefix="surfd-acct-"))
HOMES.append(os.environ["SURFD_TOOLS"])
sys.modules.pop("ed25519", None)
sys.path.remove(TOOLS)
r1 = hello(m, KEY1)
sys.path.insert(0, TOOLS)
import ed25519          # noqa: E402,F811  (back for the rest of the file)
check("a host with no ed25519.py cannot check a signature, and says later, not no",
      r1, dict(NOBODY, why="later"))

print("\n--- 12b. limits are per player, as the LOBBY saw them ------------")

m = fresh()
got = [hello(m, KEY1).get("why", "") for _ in range(accounts.ACCT_PEER_MAX + 1)]
check("%d connects a minute from one client address, then later" % accounts.ACCT_PEER_MAX,
      (got[:-1] == [""] * accounts.ACCT_PEER_MAX, got[-1]), (True, "later"))
check("...another address is unaffected, whatever guid either states",
      hello(m, KEY1, ip="10.0.5.5:1").get("why", ""), "")
check("...and the port the client came from is not part of who it is",
      hello(m, KEY1, ip="10.0.0.1:9999").get("why", ""), "later")

m = fresh()
code = code_of(signin(m))
tries = [ask(m, KEY1, "ABCDEFGH")["why"] for _ in range(accounts.TRY_RATE_MAX + 1)]
check("%d link steps a minute per client address, then it is told to slow down"
      % accounts.TRY_RATE_MAX,
      (tries[:-1] == ["code"] * accounts.TRY_RATE_MAX, tries[-1]), (True, "slow"))
check("...even with the right code", ask(m, KEY1, code), no("slow"))
check("...which another player cannot do TO it by stating its guid",
      [ask(m, KEY2, "ABCDEFGH", player="guid-3")["why"] for _ in range(accounts.TRY_RATE_MAX + 1)][-1],
      "slow")
check("...the third player, whose guid that was, links untroubled", link(m, KEY3, code), YES)

m = fresh()
junk = dict(key="testkey", node="p27510", nonce="ab" * 16, pub="ab" * 32, sig="cd" * 64,
            server=HERE_ADDR, keyed="0", game=GAME)
got = [body(post(m, "/api/account", ip="10.7.%d.%d" % (i // 250, i % 250), **junk)).get("why")
       for i in range(accounts.HELLO_VERIFY_MAX + 1)]
check("%d connect signatures a minute are checked for everyone; the next is asked back later"
      % accounts.HELLO_VERIFY_MAX,
      (got[:-1] == ["proof"] * accounts.HELLO_VERIFY_MAX, got[-1]), (True, "later"))
code = code_of(signin(m))
check("...and a flood of connects cannot spend the budget links are checked from",
      link(m, KEY1, code), YES)

m = fresh()
got = [post(m, "/api/account", key="testkey").status_code
       for i in range(accounts.ACCT_RATE_MAX + 1)]
check("%d account posts a minute from one source, then 429" % accounts.ACCT_RATE_MAX,
      (got[:-1] == [400] * accounts.ACCT_RATE_MAX, got[-1]), (True, 429))
check("...which costs the lobbies none of their link steps",
      post(m, "/api/link", key="testkey", ip="10.8.0.1", tag="ab" * 16).status_code, 200)

m = fresh()
got = [post(m, "/api/link", key="testkey", ip="10.8.%d.%d" % (i // 250, i % 250),
            tag="ab" * 16).status_code for i in range(accounts.LINK_RATE_MAX + 1)]
check("%d link steps a minute from all lobbies, then 429" % accounts.LINK_RATE_MAX,
      (got[:-1] == [200] * accounts.LINK_RATE_MAX, got[-1]), (True, 429))
check("...which costs the lobbies none of their account queries",
      post(m, "/api/account", key="testkey").status_code, 400)

m = fresh()
got = [post(m, "/api/link", tag="ab" * 16).status_code
       for _ in range(accounts.LINK_FLOOD_MAX + 1)]
check("%d keyless link calls a minute are refused one by one, then unread"
      % accounts.LINK_FLOOD_MAX,
      (got[:-1] == [403] * accounts.LINK_FLOOD_MAX, got[-1]), (True, 429))

for given, want in (("203.0.113.9:27001", "203.0.113.9"), ("203.0.113.9", "203.0.113.9"),
                    ("[2001:db8::1]:27001", "2001:db8::1"), ("2001:db8::1", "2001:db8::1"),
                    ("", "?"), ("nonsense", "?"), (None, "?")):
    check("peer_of %r" % (given,), accounts.peer_of(given), want)

print("\n--- 12c. two lobbies, one code; a storage error -------------------")

m = fresh()
code = code_of(signin(m))
ask(m, KEY1, code)
real_verify = ed25519.verify


def racing(pub, msg, sig):
    run(m, "UPDATE linkcodes SET used_at = ?, used_by = 'the other lobby' WHERE code = ?",
        (START, bare(code)))
    return real_verify(pub, msg, sig)


ed25519.verify = racing
r = confirm(m, KEY1, code)
ed25519.verify = real_verify
check("a code spent while its signature was being checked links nobody",
      (r, keys(m), rows(m, "SELECT used_by FROM linkcodes")),
      (no("code"), [], [("the other lobby",)]))

m = fresh()
code = code_of(signin(m))


def claiming(pub, msg, sig):
    run(m, "UPDATE linkcodes SET claim = ? WHERE code = ?", (PUB2, bare(code)))
    return real_verify(pub, msg, sig)


ed25519.verify = claiming
r = ask(m, KEY1, code)
ed25519.verify = real_verify
check("a code claimed by another key while this one's signature was being checked stays theirs",
      (r, unspent(m)), (no("code"), [(0, PUB2)]))

m = fresh()
code = code_of(signin(m))
ask(m, KEY1, code)
real_connect = m.connect
BAN = []


def watched():
    """surfd's connection, with a second writer that tries to ban the account
    between a link step's read of it and the step's write."""
    conn = real_connect()

    def spy(sql):
        if sql.startswith("SELECT k.steamid, a.name FROM keylinks") and not BAN:
            other = sqlite3.connect(m._test_db, timeout=0)
            try:
                other.execute("UPDATE accounts SET banned_at = ? WHERE steamid = ?", (START, SID))
                other.commit()
                BAN.append("landed")
            except sqlite3.OperationalError as exc:
                BAN.append(str(exc))
            finally:
                other.close()
    conn.set_trace_callback(spy)
    return conn


m.connect = watched
r = confirm(m, KEY1, code)
m.connect = real_connect
check("a ban cannot land between a link step's read and its write: the step holds the lock",
      (BAN, r, rows(m, "SELECT banned_at FROM accounts WHERE steamid = ?", (SID,))),
      (["database is locked"], YES, [(0,)]))

m = fresh()
code = code_of(signin(m))
ask(m, KEY1, code)
run(m, "ALTER TABLE keylinks RENAME TO keylinks_gone")
r = post(m, "/api/link", key="testkey", node="p27510", ip="10.0.0.1", pin=PIN,
         tag=salted(code),
         **proof(KEY1, accounts.confirm_nonce(bare(code), PIN), accounts.TICKS_CONFIRM))
run(m, "ALTER TABLE keylinks_gone RENAME TO keylinks")
check("a storage error is a 500, and the code is still good afterwards",
      (r.status_code, unspent(m), confirm(m, KEY1, code)), (500, [(0, PUB1)], YES))

check("the statement a key signs is acct_sign's, byte for byte (cl_receipt.c)",
      accounts.STATEMENT % ("1.2.3.4:27510", "ab" * 16, -3, 1, "cd" * 32),
      "FTESURF-ACCT 1\nserver 1.2.3.4:27510\nnonce " + "ab" * 16 + "\nkind -3\nkey 1\ncode "
      + "cd" * 32 + "\n")
check("the four kinds are four numbers",
      (accounts.TICKS_HELLO, accounts.TICKS_ASK, accounts.TICKS_CONFIRM, accounts.TICKS_START),
      (-2, -3, -4, -5))
check("the digests are tagged, 32 hex, and what the client computes",
      (accounts.code_tag("ABCDEFGH"), accounts.ask_nonce("ABCDEFGH"),
       accounts.confirm_nonce("ABCDEFGH", "482913"), accounts.typed_tag("0011223344556677", "ABCDEFGH"),
       accounts.number_proof("00112233445566778899aabb", "482913", "0421")),
      (hashlib.sha256(b"ftesurf-code ABCDEFGH").hexdigest()[:32],
       hashlib.sha256(b"ftesurf-link ABCDEFGH").hexdigest()[:32],
       hashlib.sha256(b"ftesurf-confirm ABCDEFGH 482913").hexdigest()[:32],
       hashlib.sha256(b"ftesurf-code 0011223344556677 ABCDEFGH").hexdigest()[:32],
       hashlib.sha256(b"ftesurf-number 00112233445566778899aabb 482913 0421").hexdigest()[:32]))
check("a code is twelve characters, shown in fours",
      (accounts.CODE_LEN, accounts.show_code("ABCDEFGHJKLM")), (12, "ABCD-EFGH-JKLM"))

print("\n--- 12e. the game starts a link; the page's number ties the two ---")

# Openers, as game clients make them: one a start, never sent to a lobby.
K = ["%024x" % (0xA11CE000 + i) for i in range(16)]


def begin(m, seed, opener, **kw):
    """POST /api/link/start as a lobby would: the start's code (the client made
    it from its opener) and the key's signature over code AND opener, made
    under a key press.  -> the reply."""
    code = accounts.start_code_of(opener)
    form = dict(key="testkey", node="p27510", player="guid-%d" % seed[0],
                ip="10.0.0.%d:27001" % seed[0], code=kw.pop("code", code))
    form.update(proof(seed, accounts.start_nonce(kw.pop("signed_code", code),
                                                 kw.pop("signed_opener", opener)),
                      kw.pop("ticks", accounts.TICKS_START), kw.pop("server", HERE_ADDR),
                      kw.pop("signed_keyed", None), kw.pop("old", False),
                      kw.pop("game", None), kw.pop("signed_game", None)))
    form.update(kw)
    return body(post(m, "/api/link/start", **form))


def begun(m, seed, opener, **kw):
    """A start that surfd took.  -> its code."""
    r = begin(m, seed, opener, **kw)
    assert r == {"acct": 1, "ok": 1}, r
    return accounts.start_code_of(opener)


def waiting(m, seed, code, **kw):
    form = dict(key="testkey", node="p27510", ip="10.0.0.%d:27001" % seed[0],
                tag=accounts.code_tag(bare(code)))
    form.update(kw)
    return body(post(m, "/api/link/wait", **form))


def started(m, code):
    return rows(m, "SELECT steamid, claim, shown, used_by FROM linkcodes WHERE code = ?",
                (code,))


WAIT, GONE = {"acct": 1, "state": "wait"}, {"acct": 1, "state": "gone"}
m = fresh()
code = code_of(signin(m, ip="198.51.100.78"))
check("a typed code is not waited for, by either of its digests",
      (waiting(m, KEY1, code), waiting(m, KEY1, code, tag=salted(code))), (GONE, GONE))
AGAIN = "Start again from the game"
number_of = code_of                     # the page shows it in the same tile

check("a start's code is what the client computes: one of 32 from each of a digest's first twelve bytes",
      accounts.start_code_of(K[0]),
      "".join(accounts.CODE_ALPHABET[b % 32]
              for b in hashlib.sha256(("ftesurf-id " + K[0]).encode()).digest()[:12]))
check("a start's code is twelve of the alphabet, made from its opener and nothing else",
      (len(accounts.start_code_of(K[0])), set(accounts.start_code_of(K[0])) <= set(accounts.CODE_ALPHABET),
       accounts.start_code_of(K[0]) == accounts.start_code_of(K[0]),
       accounts.start_code_of(K[0]) != accounts.start_code_of(K[1])),
      (accounts.CODE_LEN, True, True, True))

m = fresh()
r = begin(m, KEY1, K[0])
C = accounts.start_code_of(K[0])
check("a start is taken, kept for that key under the code its client made, with no account",
      (r, started(m, C)), ({"acct": 1, "ok": 1}, [("", PUB1, accounts.NOT_YET, "")]))
check("...the lobby is told to wait", waiting(m, KEY1, C), WAIT)
check("...and nobody can ask or confirm with it, its own key included",
      (ask(m, KEY1, C)["why"], ask(m, KEY1, C, tag=accounts.code_tag(C))["why"],
       confirm(m, KEY1, C, opener=K[0], number="0000"), confirm(m, KEY2, C, opener=K[0])),
      ("code", "code", no("code"), no("code")))
check("the page a start's address opens hands the opener to its button, and only an opener",
      ('href="link/steam?k=%s"' % K[0] in text(get(m, "/board/link?k=" + K[0])),
       "steam?k=" in text(get(m, "/board/link?k=%3Cscript%3E")),
       "steam?k=" in text(get(m, "/board/link?k=" + K[0][:-1]))), (True, False, False))

m.time.now += 61
# The code crosses the wire.  Somebody who read it there can do two things
# with it, and neither gets them anything.
check("a second start under a code that is taken is refused, whoever brings it",
      (begin(m, KEY2, K[9], code=C, signed_code=C), started(m, C)),
      (no("code"), [("", PUB1, accounts.NOT_YET, "")]))
r = signin(m, sid=SID2, ip="203.0.113.40", k=K[9])
check("a sign-in with another opener names another start: nothing attaches, nothing ends",
      (AGAIN in text(r), code_of(r), started(m, C), waiting(m, KEY1, C)),
      (True, "", [("", PUB1, accounts.NOT_YET, "")], WAIT))
# ...and the other order: the watcher gets the code in FIRST, under their own key.
V = accounts.start_code_of(K[8])
check("CONTROL a code registered first by a key whose client did not make its opener is kept",
      (begin(m, KEY2, K[9], code=V, signed_code=V), started(m, V)),
      ({"acct": 1, "ok": 1}, [("", PUB2, accounts.NOT_YET, "")]))
r = signin(m, ip="203.0.113.41", k=K[8])
check("...and the sign-in its real opener brings opens nothing: that key never signed for it",
      (begin(m, KEY3, K[8]), AGAIN in text(r), started(m, V)),
      (no("code"), True, [("", PUB2, accounts.NOT_YET, "")]))

m.time.now += 61
cookie, rt = start(m, ip="198.51.100.60", k=K[0])
r = get(m, "/board/link/return?" + urllib.parse.urlsplit(rt.replace("k=" + K[0], "k=" + K[9])).query
        + "&" + urllib.parse.urlencode(assertion(m, rt)), ip="198.51.100.60", cookie=cookie)
check("the opener rides in what Steam signed: swapped on the way back, the reply is refused",
      (r.status_code, started(m, C)[0][0]), (400, ""))

r = signin(m, ip="203.0.113.50", k=K[0])
N = number_of(r)
check("a sign-in at its own address, from ANYWHERE, is shown a four-digit number and attached",
      (r.status_code, len(N), N.isdigit(), "Type this number into the game" in text(r),
       started(m, C)),
      (200, accounts.SHOWN_LEN, True, True, [(SID, PUB1, N, "")]))
check("...the lobby's wait now names the account",
      waiting(m, KEY1, C), {"acct": 1, "state": "ready", "to": "Lex", "from": ""})
r = signin(m, ip="203.0.113.51", k=K[0])
check("...the same account signing in again sees the same number, and the start lives",
      (number_of(r), started(m, C)), (N, [(SID, PUB1, N, "")]))
check("...another key cannot confirm it, number and all",
      confirm(m, KEY2, C, opener=K[0], number=N), no("code"))
m.time.now += 61
check("...the key that started it links by signing the lobby's number, with the page's "
      "number as a digest under ITS opener",
      (confirm(m, KEY1, C, opener=K[0], number=N), keys(m), started(m, C)[0][3]),
      (YES, [(PUB1[:8], SID, "p27510")], PUB1[:16]))
check("...after which the start is gone", waiting(m, KEY1, C), GONE)

m = fresh()
C = begun(m, KEY1, K[0])
N = number_of(signin(m, ip="203.0.113.52", k=K[0]))
wrong = "%04d" % ((int(N) + 1) % 10000)
check("a wrong number links nothing and SPENDS the start: one try",
      (confirm(m, KEY1, C, opener=K[0], number=wrong), keys(m), started(m, C)[0][3],
       waiting(m, KEY1, C)),
      (no("number"), [], accounts.MISMATCH, GONE))
check("...so the right one, afterwards, is too late",
      confirm(m, KEY1, C, opener=K[0], number=N), no("code"))
m = fresh()
C = begun(m, KEY1, K[0])
signin(m, ip="203.0.113.53", k=K[0])
check("no number at all is a wrong number",
      (confirm(m, KEY1, C, opener=K[0]), started(m, C)[0][3]), (no("number"), accounts.MISMATCH))
# THE NUMBER DOES NOT CROSS THE WIRE.  What does is a digest of it with the
# opener of the game it was typed into and that confirm's pin, so:
for label, shown in (
        ("the number itself, in the clear", lambda n: n),
        ("the right number typed into ANOTHER game: a digest under that game's opener",
         lambda n: accounts.number_proof(K[5], PIN, n)),
        ("the right digest for another confirm's pin",
         lambda n: accounts.number_proof(K[0], "111111", n))):
    m = fresh()
    C = begun(m, KEY1, K[0])
    N = number_of(signin(m, ip="203.0.113.53", k=K[0]))
    check("%s links nothing, and spends the start" % label,
          (confirm(m, KEY1, C, opener=K[0], shown=shown(N)), keys(m), started(m, C)[0][3]),
          (no("number"), [], accounts.MISMATCH))

m = fresh()
C = begun(m, KEY1, K[0])
N = number_of(signin(m, ip="203.0.113.54", k=K[0]))
r = signin(m, sid=SID2, ip="203.0.113.55", k=K[0])
check("a second ACCOUNT signing in for one start ends it for both, and is given nothing",
      (AGAIN in text(r), code_of(r), started(m, C)[0][3], waiting(m, KEY1, C),
       rows(m, "SELECT COUNT(*) FROM linkcodes WHERE steamid = ?", (SID2,))),
      (True, "", accounts.CONTESTED, GONE, [(0,)]))
check("...and the first account's number no longer confirms",
      confirm(m, KEY1, C, opener=K[0], number=N), no("code"))

m = fresh()
C = begun(m, KEY1, K[0])
m.time.now += accounts.CODE_TTL + 1
r = signin(m, ip="203.0.113.56", k=K[0])
check("a start older than ten minutes is gone; a sign-in with it gets no number and no code",
      (waiting(m, KEY1, C), AGAIN in text(r), code_of(r), count(m, "linkcodes")),
      (GONE, True, "", 1))
r = signin(m, ip="203.0.113.57", k=K[1])
check("...nor does one with an opener nobody started", (AGAIN in text(r), code_of(r)), (True, ""))
typed = bare(code_of(signin(m, sid=SID2, ip="203.0.113.58")))
check("a typed code is not something a lobby waits on", waiting(m, KEY1, typed), GONE)
# An opener cannot be chosen to name a typed code (that is a 50-bit search),
# so the row is put there: a code that is not a start, under an opener's name.
run(m, "UPDATE linkcodes SET code = ? WHERE code = ?", (accounts.start_code_of(K[2]), typed))
r = signin(m, ip="203.0.113.59", k=K[2])
check("...and a typed code that an opener happens to name is not a start: nothing attaches",
      (r.status_code, AGAIN in text(r), started(m, accounts.start_code_of(K[2]))),
      (200, True, [(SID2, "", "", "")]))

m = fresh()
typed = bare(code_of(signin(m, ip="203.0.113.60")))
first = begun(m, KEY1, K[0])
signin(m, ip="203.0.113.61", k=K[0])
check("signing in for a start retires the account's typed code: one live code an account",
      started(m, typed)[0][3], "superseded")
second = begun(m, KEY1, K[1])
check("a key's second start does not end its first until somebody signs in for it",
      (started(m, first)[0][3], waiting(m, KEY1, second)), ("", WAIT))
signin(m, sid=SID2, ip="203.0.113.62", k=K[1])
check("...and then it does: one start per key, the one that was signed in for",
      (started(m, first)[0][3], waiting(m, KEY1, first)), ("superseded", GONE))

# A start's signature is not checked when it arrives: it is over an opener
# surfd has not seen.  So a wrong one is ACCEPTED there, and opens nothing.
m = fresh()
for i, (label, kw) in enumerate((
        ("a connect's kind in a start's place", dict(ticks=accounts.TICKS_HELLO, signed_keyed=1)),
        ("an ask's", dict(ticks=accounts.TICKS_ASK)),
        ("a signature over another code", dict(signed_code="ABCDEFGHJKLM")),
        ("a signature over another opener", dict(signed_opener=K[15])),
        ("a signature made the way engines before Patch 625 made them", dict(old=True)))):
    bad = begun(m, KEY3, K[i], **kw)
    r = signin(m, ip="203.0.113.63", k=K[i])
    check("a start with %s is kept, and no sign-in opens it" % label,
          (AGAIN in text(r), started(m, bad)), (True, [("", PUB3, accounts.NOT_YET, "")]))
    m.time.now += 61
bad = begun(m, KEY3, K[6], signed_keyed=0, keyed="1")
r = signin(m, ip="203.0.113.63", k=K[6])
check("a start signed with no key pressed, its flag turned on by somebody on the way, is kept "
      "and never opens",
      (AGAIN in text(r), started(m, bad)), (True, [("", PUB3, accounts.NOT_YET, "")]))
m.time.now += 61
run(m, "INSERT INTO linkcodes (code, steamid, issued_at, claim, shown, seal) VALUES (?,'',?,?,?,?)",
    (accounts.start_code_of(K[7]), m.time.now, PUB3, accounts.NOT_YET,
     "cd" * 16 + " " + "ab" * 64 + " 127.0.0.1:27510"))
r = signin(m, ip="203.0.113.63", k=K[7])
check("a seal of the three parts Patch 619 kept opens nothing, and breaks nothing",
      (r.status_code, AGAIN in text(r)), (200, True))
n = count(m, "linkcodes")
check("a start the engine signed with no key pressed is refused at once",
      (begin(m, KEY3, K[10], signed_keyed=0), begin(m, KEY3, K[10], keyed="0"),
       count(m, "linkcodes") - n), (no("proof"), no("proof"), 0))
check("...and so is one signed on somebody else's server",
      (begin(m, KEY3, K[10], server="203.0.113.7:27510"), count(m, "linkcodes") - n),
      (no("server"), 0))
check("a start with a code that is not twelve of the alphabet is a 400",
      [post(m, "/api/link/start", key="testkey", node="p27510", ip="10.0.0.9", code=c,
            **proof(KEY3, accounts.start_nonce("ABCDEFGHJKLM", K[0]),
                    accounts.TICKS_START)).status_code
       for c in ("xyz", "", "ABCDEFGHJKL0", "ABCDEFGHJK")], [400, 400, 400, 400])
check("...and without the lobby's key a start and a wait are both 403",
      (post(m, "/api/link/start", code="ABCDEFGHJKLM").status_code,
       post(m, "/api/link/wait", tag="ab" * 16).status_code), (403, 403))
C = begun(m, KEY1, K[11])
spent = m._rate.setdefault(("verify-link", "*"), [])
spent.extend([m.time.now] * accounts.LINK_VERIFY_MAX)
begun(m, KEY2, K[12])
r = signin(m, ip="203.0.113.66", k=K[12])
check("with the LINK steps' signature checks spent, a sign-in for a start still opens",
      len(number_of(r)), accounts.SHOWN_LEN)
spent = m._rate.setdefault(("verify-open", "*"), [])
spent.extend([m.time.now] * accounts.OPEN_VERIFY_MAX)
r = signin(m, ip="203.0.113.64", k=K[11])
check("with its OWN minute's checks spent, a sign-in for a start is asked to come back",
      (r.status_code, "cannot check that right now" in text(r), started(m, C)),
      (503, True, [("", PUB1, accounts.NOT_YET, "")]))
m.time.now += 61
check("...and a minute later it opens",
      len(number_of(signin(m, ip="203.0.113.65", k=K[11]))), accounts.SHOWN_LEN)

m = fresh()
signin(m, sid=SID2, ip="198.51.100.63")
run(m, "UPDATE accounts SET banned_at = ? WHERE steamid = ?", (START, SID2))
C = begun(m, KEY1, K[0])
r = signin(m, sid=SID2, ip="198.51.100.64", k=K[0])
check("a banned account signing in for a game's start attaches nothing",
      (r.status_code, "banned" in text(r), started(m, C)),
      (403, True, [("", PUB1, accounts.NOT_YET, "")]))

m = fresh()
C = begun(m, KEY1, K[0])
N = number_of(signin(m, sid=SID2, ip="198.51.100.65", k=K[0]))
run(m, "UPDATE accounts SET banned_at = ? WHERE steamid = ?", (START, SID2))
check("an account banned AFTER it was attached: the wait says so, and nothing confirms",
      (waiting(m, KEY1, C), confirm(m, KEY1, C, opener=K[0], number=N), keys(m)),
      ({"acct": 1, "state": "gone", "why": "banned"}, no("banned"), []))

m = fresh()
link(m, KEY1, code_of(signin(m, ip="198.51.100.66")))
m.time.now += 61
C = begun(m, KEY1, K[0])
signin(m, sid=SID2, ip="198.51.100.67", k=K[0])
check("a start for a key that is linked elsewhere says where it would move from",
      waiting(m, KEY1, C), {"acct": 1, "state": "ready", "to": "Other", "from": "Lex"})
C = begun(m, KEY1, K[1])
signin(m, ip="198.51.100.68", k=K[1])
check("...and one for the account it is already on does not call that a move",
      waiting(m, KEY1, C), {"acct": 1, "state": "ready", "to": "Lex", "from": ""})

m = fresh()
C = begun(m, KEY1, K[0])
got = [waiting(m, KEY1, C)["state"] for _ in range(accounts.WAIT_RATE_MAX)]
N = number_of(signin(m, ip="198.51.100.69", k=K[0]))
check("%d waits a minute per client address; past it the answer is still wait"
      % accounts.WAIT_RATE_MAX,
      (set(got), waiting(m, KEY1, C)), ({"wait"}, WAIT))
check("...and they spent none of that player's link steps",
      confirm(m, KEY1, C, opener=K[0], number=N), YES)
m.time.now += 61
check("...a minute later a wait is the truth again (the start is spent)", waiting(m, KEY1, C), GONE)

m = fresh()
got = {post(m, "/api/link/wait", tag="ab" * 16).status_code
       for _ in range(accounts.LINK_FLOOD_MAX + 1)}
check("%d keyless waits are refused one by one, and cost the link steps' allowance nothing"
      % (accounts.LINK_FLOOD_MAX + 1),
      (got, post(m, "/api/link", tag="ab" * 16).status_code), ({403}, 403))

m = fresh()
conn = sqlite3.connect(m._test_db)
conn.executemany("INSERT INTO linkcodes (code, steamid, issued_at, claim, shown) VALUES (?,'',?,?,?)",
                 [("S%07d" % i, START, "%064x" % i, accounts.NOT_YET)
                  for i in range(accounts.CODE_LIVE_MAX)])
conn.commit()
conn.close()
check("with more than %d starts nobody has signed in for, a start is told to come back"
      % accounts.START_LIVE_MAX,
      (begin(m, KEY1, K[0]), count(m, "linkcodes") == accounts.CODE_LIVE_MAX > accounts.START_LIVE_MAX),
      ({"acct": 1, "ok": 0, "why": "later"}, True))
check("...but %d of them are not codes outstanding: sign-in is open" % accounts.CODE_LIVE_MAX,
      len(bare(code_of(signin(m, ip="198.51.100.70")))), accounts.CODE_LEN)
m.time.now += accounts.CODE_KEEP + 1
check("...and a day on, a start prunes the old rows itself",
      (begin(m, KEY1, K[1]).get("ok"), count(m, "linkcodes")), (1, 1))

m = fresh()
got = [begin(m, KEY1, K[i % 16], code="ABCDEFGHJK%s%s" % ("23456789"[i // 8], "23456789"[i % 8]),
             signed_code="ABCDEFGHJKLM").get("why", "")
       for i in range(accounts.TRY_RATE_MAX + 1)]
check("starts count as link steps: %d a minute per client address" % accounts.TRY_RATE_MAX,
      (got[:-1] == [""] * accounts.TRY_RATE_MAX, got[-1]), (True, "slow"))

for raw, want in (("ABCDEFGHJKLM", "ABCDEFGHJKLM"), ("ABCD-EFGH-JKLM", "ABCDEFGHJKLM"),
                  ("abcdefghjklm", ""), ("ABCDEFGHJKL", ""), ("ABCDEFGHJKLM0", ""),
                  ("ABCDEFGHIJ0L", ""), ("ABCDEFGHJK", ""), ("", ""), (None, "")):
    check("start_code %r" % (raw,), accounts.start_code(raw), want)

# A 13 database: the same file without the columns, and the stamp put back.
m = fresh()
home = m._home
conn = sqlite3.connect(m._test_db)
conn.executescript("ALTER TABLE linkcodes DROP COLUMN shown;"
                   "ALTER TABLE linkcodes DROP COLUMN seal; PRAGMA user_version=13;")
conn.close()
m = fresh(home=home)
cols = [r[1] for r in rows(m, "PRAGMA table_info(linkcodes)")]
check("a schema-13 database gains both columns on the next start",
      ("shown" in cols, "seal" in cols, rows(m, "PRAGMA user_version")[0][0]), (True, True, 15))
conn = sqlite3.connect(m._test_db)
conn.executescript("ALTER TABLE linkcodes DROP COLUMN seal; PRAGMA user_version=13;")
conn.close()
m = fresh(home=home)
check("...and one that already has the first gains the second",
      "seal" in [r[1] for r in rows(m, "PRAGMA table_info(linkcodes)")], True)

m = fresh()
code = code_of(signin(m, ip="198.51.100.74"))
ask(m, KEY1, code)
check("a confirm the engine signed with no key pressed is refused, flag honest or not",
      (confirm(m, KEY1, code, signed_keyed=0), confirm(m, KEY1, code, signed_keyed=0, keyed="1"),
       confirm(m, KEY1, code, keyed="0"), keys(m)),
      (no("proof"), no("proof"), no("proof"), []))
check("CONTROL ...and the same confirm under a key press links", confirm(m, KEY1, code), YES)

# A 14 database with a link in it, made before the engine could say a key was
# pressed.  Its table is not this code's: the link is gone, the account and a
# ban on it stay.  The table itself stays, empty, for older code to start on.
OLD_KEYS = accounts.SQL_KEYS.replace("keylinks", accounts.OLD_LINKS)
OLD_ROW = "INSERT INTO linkkeys (pub, steamid, player, node, linked_at) VALUES (?,?,?,?,?)"


def tables(m):
    return [r[0] for r in rows(m, "SELECT name FROM sqlite_master WHERE type = 'table'")]


m = fresh()
home = m._home
signin(m, sid=SID, ip="198.51.100.71")
signin(m, sid=SID2, ip="198.51.100.72")
run(m, "UPDATE accounts SET banned_at = ? WHERE steamid = ?", (START, SID2))
conn = sqlite3.connect(m._test_db)
conn.executescript("DROP TABLE keylinks;" + OLD_KEYS + "PRAGMA user_version=14;")
conn.execute(OLD_ROW, (PUB1, SID, "guid-1", "p27510", START))
conn.commit()
conn.close()
m = fresh(home=home)
check("a schema-14 database loses its links on the way to 15, and keeps its accounts",
      (count(m, "linkkeys"), "keylinks" in tables(m), keys(m), count(m, "accounts"),
       rows(m, "SELECT COUNT(*) FROM accounts WHERE banned_at > 0"),
       hello(m, KEY1).get("linked"), rows(m, "PRAGMA user_version")[0][0]),
      (0, True, [], 2, [(1,)], 0, 15))
link(m, KEY1, code_of(signin(m, ip="198.51.100.73")))
m = fresh(home=home)
check("...a link made at 15 survives the next start", [k[:2] for k in keys(m)], [(PUB1[:8], SID)])
# What a rollback leaves.  Code from before 625 writes the table it knows: a
# new key's link, and a NEW ACCOUNT for a key this code linked (the review's
# case: an upsert that knows nothing of a newer column).
run(m, OLD_ROW, (PUB2, SID, "guid-2", "p27510", START))
run(m, OLD_ROW, (PUB1, SID2, "guid-1", "p27510", START))
check("what older code writes is not a link here, even before the next start",
      (hello(m, KEY2).get("linked"), hello(m, KEY1, nonce="cd" * 16).get("name"),
       [k[:2] for k in keys(m)]),
      (0, "Lex", [(PUB1[:8], SID)]))
m = fresh(home=home)
check("...and the next start empties that table, keeps it for older code to start on, and "
      "leaves the proven link alone",
      (count(m, "linkkeys"), [k[:2] for k in keys(m)]), (0, [(PUB1[:8], SID)]))
# A file an earlier cut of this patch stamped 15: no `keylinks` at all.
conn = sqlite3.connect(m._test_db)
conn.executescript("DROP TABLE keylinks;")
conn.close()
m = fresh(home=home)
check("a database stamped 15 with no link table gets one at the next start, and links",
      ("keylinks" in tables(m), rows(m, "PRAGMA user_version")[0][0],
       link(m, KEY1, code_of(signin(m, ip="198.51.100.77")))), (True, 15, YES))
m = fresh()
check("a fresh database has no table for older code, and starting twice is no trouble",
      ("linkkeys" in tables(m), "linkkeys" in tables(fresh(home=m._home))), (False, False))

# THE GAME CODE A PROOF NAMES.  surfd reads what its lobbies serve.
m = fresh()
code = code_of(signin(m, ip="198.51.100.75"))
FOREIGN = hashlib.sha256(b"somebody else's csprogs").hexdigest()
for label, kw, why in (
        ("a proof that names game code no lobby of ours serves", dict(game=FOREIGN), "game"),
        ("our game code named, and another's signed", dict(signed_game=FOREIGN), "proof"),
        ("no game code named", dict(game=""), "proof"),
        ("a game code that is not 64 hex", dict(game=GAME[:62]), "proof")):
    check("%s is refused, asking" % label,
          (ask(m, KEY1, code, ip="10.9.4.%d" % len(label), **kw), unspent(m)),
          (no(why), [(0, "")]))
check("CONTROL the same ask under our game code is answered",
      ask(m, KEY1, code)["why"], "confirm")
check("...and so is a connect under foreign game code: not linked is not what it says",
      (hello(m, KEY1, game=FOREIGN), hello(m, KEY1, signed_game=FOREIGN)),
      ({"acct": 1, "linked": 0, "why": "game"}, {"acct": 1, "linked": 0, "why": "proof"}))
check("...and a start", begin(m, KEY1, K[0], game=FOREIGN), no("game"))
bad = begun(m, KEY3, K[2], signed_game=FOREIGN)
r = signin(m, sid=SID2, ip="203.0.113.65", k=K[2])
check("a start that names our game code over another's signature is kept, and never opens",
      (AGAIN in text(r), started(m, bad)[0][2]), (True, accounts.NOT_YET))
C = begun(m, KEY1, K[1])
check("a start's kept signature carries the game code it was made under",
      rows(m, "SELECT seal FROM linkcodes WHERE code = ?", (C,))[0][0].split(" ")[2], GAME)
run(m, "UPDATE linkcodes SET seal = replace(seal, ?, ?) WHERE code = ?", (GAME, FOREIGN, C))
r = signin(m, ip="203.0.113.64", k=K[1])
check("...and with another's in its place the sign-in opens nothing",
      (AGAIN in text(r), started(m, C)[0][2]), (True, accounts.NOT_YET))
# A deploy: the lobbies serve new code, and keep the old beside it.
path = os.environ["SURFD_GAME_CODE"].split(",")[0]
NEXT = b"FTESurf test csprogs, build 2, and longer\n"
C2 = begun(m, KEY2, K[3])
os.replace(path, path + ".prev")
with open(path, "wb") as fh:
    fh.write(NEXT)
code = code_of(signin(m, ip="198.51.100.76"))
check("after a deploy the new game code is ours, and so is the one kept beside it",
      (ask(m, KEY2, code, game=hashlib.sha256(NEXT).hexdigest())["why"],
       hello(m, KEY1).get("why", ""), hello(m, KEY1, game=FOREIGN).get("why")),
      ("confirm", "", "game"))
# A start made under the build before the one before: its kept signature is
# asked again when a sign-in opens it, and is no longer ours.
os.remove(path + ".prev")
r = signin(m, sid=SID2, ip="203.0.113.66", k=K[3])
check("a start whose game code has since left the lobbies opens nothing",
      (AGAIN in text(r), started(m, C2)[0][2], hello(m, KEY1).get("why")),
      (True, accounts.NOT_YET, "game"))
# One file there and unreadable (a directory in its place), the other read: a
# proof naming neither is not called foreign, because it might be the first's.
os.mkdir(path + ".prev")
check("with one file unreadable, a proof naming the readable one is taken and any other "
      "cannot be checked",
      (hello(m, KEY1, game=hashlib.sha256(NEXT).hexdigest()).get("why", ""),
       hello(m, KEY1, game=FOREIGN).get("why")), ("", "later"))
os.rmdir(path + ".prev")
# An EMPTY file where the game code should be (a deploy that died) is not game
# code whose name is the hash of nothing.
with open(path + ".prev", "wb"):
    pass
check("an empty game code file is one that cannot be read, not one to be named",
      hello(m, KEY1, game=hashlib.sha256(b"").hexdigest()).get("why"), "later")
os.remove(path + ".prev")
os.remove(path)
check("with no game code file to read nothing is called foreign: it cannot be checked",
      (hello(m, KEY1), ask(m, KEY3, code, game=FOREIGN)),
      ({"acct": 1, "linked": 0, "why": "later"}, no("later")))
with open(path, "wb") as fh:
    fh.write(GAME_BYTES)
check("...and it can again as soon as there is", hello(m, KEY1).get("why", ""), "")

print("\n--- 12d. the sign-in page lists installs, and unlinks one --------")


def page_cookie(resp, name="__Host-ftu"):
    """The `name=value` the page set for unlinking, or ""."""
    for c in resp.headers.getlist("Set-Cookie"):
        if c.startswith(name + "=") and "max-age=0" not in c.lower():
            return c.split(";")[0]
    return ""


def token_of(resp):
    t = text(resp)
    at = t.find('href="unlink?t=')
    return t[at + 15:t.find('"', at + 15)] if at >= 0 else ""


def unlink(m, token, browser, ip="198.51.102.1", method="GET"):
    return get(m, "/board/link/unlink?t=" + token, ip=ip, cookie=browser, method=method)


m = fresh()
r = signin(m)
check("an account with nothing linked is told so",
      ("No install is linked" in text(r), token_of(r)), (True, ""))
link(m, KEY1, code_of(r))
link(m, KEY2, code_of(signin(m, sid=SID2, ip="198.51.100.2")))
r = signin(m, ip="198.51.100.3")
mine = page_cookie(r)
ask_t = token_of(r)
uc = [c for c in r.headers.getlist("Set-Cookie") if c.startswith("__Host-ftu=")][0]
check("after linking, the page names the install by its key, lobby and day, with a link",
      ("<code>%s</code> linked %s on p27510" % (PUB1[:16], stamp(START)[:10]) in text(r),
       ask_t.startswith("ask.%d.%s.%s." % (START, SID, PUB1[:16])), PUB2[:16] in text(r)),
      (True, True, False))
check("...and marks the browser that may use it",
      sorted(a.strip().lower() for a in uc.split(";")[1:] if not a.strip().lower().startswith("expires")),
      ["httponly", "max-age=600", "path=/", "samesite=lax", "secure"])
r = unlink(m, ask_t, mine)
do_t = token_of(r)
check("the link asks first, and changes nothing",
      (r.status_code, "Unlink install <code>%s</code>" % PUB1[:16] in text(r),
       "<b>Lex</b>" in text(r), do_t.startswith("do."), len(keys(m))), (200, True, True, True, 2))
check("the asking link cannot be turned into the doing one",
      (unlink(m, "do" + ask_t[3:], mine).status_code, len(keys(m))), (400, 2))
check("a HEAD on the doing link is refused",
      (unlink(m, do_t, mine, method="HEAD").status_code, len(keys(m))), (405, 2))
other_browser = page_cookie(signin(m, sid=SID2, ip="198.51.100.4"))
forged = [
    ("another account's id", do_t.replace(SID, SID2), mine),
    ("another install's key", do_t.replace(PUB1[:16], PUB2[:16]), mine),
    ("a later time", do_t.replace(str(START), str(START + 1)), mine),
    ("a changed signature", do_t[:-1] + ("0" if do_t[-1] != "0" else "1"), mine),
    ("a trailing newline", do_t + "%0A", mine),
    ("nothing", "", mine),
    ("no browser cookie: somebody who only has the address", do_t, None),
    ("another browser's cookie", do_t, other_browser),
]
for n, (label, t, browser) in enumerate(forged):
    check("a doing link with %s" % label,
          (unlink(m, t, browser, ip="198.51.102.%d" % (10 + n)).status_code, len(keys(m))),
          (400, 2))
check("...and the asking link is as closed to a stranger",
      unlink(m, ask_t, None, ip="198.51.102.29").status_code, 400)
old_secret, m.SECRET = m.SECRET, "another-secret"
check("...or one signed under another secret",
      (unlink(m, do_t, mine, ip="198.51.102.30").status_code, len(keys(m))), (400, 2))
m.SECRET = old_secret
m.time.now += accounts.UNLINK_TTL + 1
check("a link older than ten minutes has expired",
      (unlink(m, do_t, mine, ip="198.51.102.31").status_code, len(keys(m))), (400, 2))
m.time.now -= 1
r = unlink(m, do_t, mine, ip="198.51.102.32")
check("CONTROL at exactly ten minutes the doing link unlinks that install and no other",
      (r.status_code, "no longer linked to Lex" in text(r), keys(m)),
      (200, True, [(PUB2[:8], SID2, "p27510")]))
check("...after which the key is nobody's", hello(m, KEY1), {"acct": 1, "linked": 0})

m = fresh()
link(m, KEY1, code_of(signin(m)))
r = signin(m, ip="198.51.100.3")
mine = page_cookie(r)
do_t = token_of(unlink(m, token_of(r), mine))
check("(unlinked once)", unlink(m, do_t, mine, ip="198.51.102.33").status_code, 200)
m.time.now += 61
link(m, KEY1, code_of(signin(m, ip="198.51.100.5")))
r = unlink(m, do_t, mine, ip="198.51.102.34")
check("a used unlink link does not unlink the install again once it has been re-linked",
      (r.status_code, len(keys(m))), (400, 1))
hits = [unlink(m, "x", mine, ip="198.51.102.40").status_code for _ in range(11)]
check("the page limit covers unlink too", (hits[:10], hits[10]), ([400] * 10, 429))

print("\n--- 13. a persona as a player name -------------------------------")

for raw, want in (
        ("Lex", "Lex"),
        ("^1Red^7 Name", "1Red7 Name"),
        ("^[click\\cmd\\quit^]", "[clickcmdquit]"),
        ('a\\b"c;d$e\nf', "abcdef"),
        ("  spaced   out  ", "spaced out"),
        ("&cf00SERVER&r", "cf00SERVERr"),               # ezQuake colour, no caret
        ("Lex: i cheat", "Lex i cheat"),                # the engine strips ':'
        ("100% <b>", "100 b"),
        ("console", "player"), ("CONSOLE", "player"),   # reserved by the engine
        ("Fl\u00f8ppy\u2122", "Fl\u00f8ppy"),
        ("e\u0301", "\u00e9"),                          # composed, not stripped
        ("\u65e5\u672c\u8a9e", "\u65e5\u672c\u8a9e"),
        ("a\u202eb\u200bc\ufeff", "abc"),               # bidi override, zero width
        ("\ue000\ue1ffok", "ok"),                       # the engine's glyph range
        ("\u3164", "player"), ("\u2800\u200b", "player"),   # draws nothing
        ("a\u3164b", "a b"),
        ("x" * 40, "x" * 31),
        ("\u00e9" * 20, "\u00e9" * 15),                 # 31 BYTES, on a character
        ("^^^", "player"), ("", "player"), (None, "player")):
    got = accounts.game_name(raw)
    check("persona %r" % (raw,), (got, len(got.encode("utf-8")) <= 31), (want, True))

print("\n--- 14. steam.py on its own --------------------------------------")

check("is_steamid64", [steam.is_steamid64(s) for s in
                       (SID, "12345678901234567", "7656119800000000", SID + "1", "", None)],
      [True, False, False, False, False, False])


def fake(payload):
    return lambda url, data=None, timeout=None: payload


good = json.dumps({"response": {"players": [
    {"steamid": SID, "personaname": "A\x00B\n", "avatarhash": "F" * 40},
    {"steamid": SID2, "personaname": 7, "avatarhash": "c" * 40 + "\n"},
    {"steamid": "76561198000000009", "personaname": "uninvited", "avatarhash": ""},
    "junk"]}}).encode()
check("a profile reply is filtered field by field",
      steam.summaries("k", [SID, SID2], fake(good)),
      {SID: {"name": "AB", "avatar": ""}, SID2: {"name": "", "avatar": ""}})
for label, payload in (("not JSON", b"<html>"), ("no response", b"{}"),
                       ("players not a list", b'{"response":{"players":{}}}'),
                       ("a list at the top", b"[]"), ("not UTF-8", b"\xff\xfe"),
                       ("nested past the parser's depth", b"[" * 60000)):
    try:
        steam.summaries("k", [SID], fake(payload))
        got = "returned"
    except steam.Unavailable:
        got = "unavailable"
    check("profile reply: %s" % label, got, "unavailable")
check("no key, or no valid id, asks nothing",
      (steam.summaries("", [SID], None), steam.summaries("k", ["nope"], None)), ({}, {}))


# steam.http against a server on loopback that answers by path.
REPLIES = {
    b"/ok": b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nConnection: close\r\n\r\nhello",
    b"/moved": b"HTTP/1.1 302 Found\r\nLocation: /ok\r\nContent-Length: 0\r\n"
               b"Connection: close\r\n\r\n",
    b"/error": b"HTTP/1.1 500 Oops\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
    b"/big": b"HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n" + b"x" * (steam.HTTP_LIMIT + 1),
    b"/short": b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n"
               b"ff\r\nhel",
    b"/garbage": b"not http at all\r\n\r\n",
}


class Canned(socketserver.BaseRequestHandler):
    def handle(self):
        path = self.request.recv(4096).split(b" ")[1]
        if path != b"/silent":
            self.request.sendall(REPLIES[path])
        else:
            time.sleep(1.0)


server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Canned)
server.daemon_threads = True
threading.Thread(target=server.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % server.server_address[1]
check("steam.http returns a 200's body", steam.http(base + "/ok"), b"hello")
closed = socket.socket()
closed.bind(("127.0.0.1", 0))
dead = "http://127.0.0.1:%d/ok" % closed.getsockname()[1]
closed.close()
for label, url, want in (
        ("a redirect is not followed", base + "/moved", "status 302"),
        ("a 500", base + "/error", "status 500"),
        ("a body over the limit", base + "/big", "oversized reply"),
        ("a body cut short", base + "/short", "IncompleteRead"),
        ("a reply that is not HTTP", base + "/garbage", "BadStatusLine"),
        ("a server that says nothing", base + "/silent", "TimeoutError"),
        ("a port nobody listens on", dead, "URLError")):
    try:
        steam.http(url, timeout=0.3)
        got = "returned"
    except steam.Unavailable as exc:
        got = str(exc)
    except Exception as exc:
        got = "ESCAPED " + type(exc).__name__
    check("steam.http: %s" % label, got, want)
server.shutdown()

print("")
if FAILED:
    print("%d FAILURE(S):" % len(FAILED))
    for f in FAILED:
        print("  " + f)
    sys.exit(1)
print("all account checks passed")
