#!/usr/bin/env python3
"""
test_accounts.py -- the falsifier for Steam accounts (accounts.py, steam.py).

    python3 test_accounts.py

Steam is a fake that records every request (`m.STEAM_HTTP`), so a refusal is
graded on what surfd ASKED Steam as well as on what it answered the browser:
a sign-in refused locally must cost Steam nothing.  The only sockets opened
are to a server this file starts on 127.0.0.1, for steam.http's own cases.
"""

import hashlib
import importlib
import json
import os
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

import accounts     # noqa: E402  (stateless; surfd imports the same module)
import steam        # noqa: E402

BOARD = "https://proto.bar/ftesurf/board"
SID = "76561198000000001"
SID2 = "76561198000000002"
START = 1800000000
TABLES = ["accounts", "linkcodes", "linknonces", "links"]


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


def fresh(board_url=BOARD, steam_key="STEAMKEY", home=None):
    home = home or tempfile.mkdtemp(prefix="surfd-acct-")
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=testkey\n")
    os.environ.update(SURFD_HOME=home, SURFD_DB=os.path.join(home, "test.db"),
                      SURFD_ENV=os.path.join(home, "surfd.env"),
                      SURFD_RUNS=os.path.join(home, "runs"),
                      SURFD_MAPS=os.path.join(home, "maps"),
                      SURFD_WEBSHOTS=os.path.join(home, "webshots"))
    for k in ("SURFD_PUBLIC_HOST", "SURFD_TRUSTED", "SURFD_PROXIES",
              "SURFD_ADMIN_HASH", "SURFD_ADMIN_SECRET", "SURFD_BOARD_URL",
              "SURFD_STEAM_KEY", "SURFD_MOMENTUM", "SURFD_MOMTRACKS"):
        os.environ.pop(k, None)
    if board_url:
        os.environ["SURFD_BOARD_URL"] = board_url
    if steam_key:
        os.environ["SURFD_STEAM_KEY"] = steam_key
    for mod in ("surfd", "admin", "rcon"):
        sys.modules.pop(mod, None)
    m = importlib.import_module("surfd")
    m.time = FakeClock()
    m.STEAM_HTTP = FakeSteam()
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


def start(m, ip="198.51.100.1"):
    """GET /board/link/steam -> (the cookie pair, return_to)."""
    r = get(m, "/board/link/steam", ip=ip)
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


def signin(m, sid=SID, ip="198.51.100.1", mutate=None, extra=()):
    cookie, return_to = start(m, ip)
    fields = assertion(m, return_to, sid)
    if mutate:
        mutate(fields)
    return back(m, cookie, return_to, fields, ip, extra)


def code_of(resp):
    t = text(resp)
    at = t.find('class="linkcode">link ')
    return t[at + 22:at + 31] if at >= 0 else ""


def count(m, table):
    return rows(m, "SELECT COUNT(*) FROM " + table)[0][0]


def link(m, player, code, **kw):
    return body(post(m, "/api/link", key="testkey", player=player, code=code, **kw))


print("\n--- 1. schema ----------------------------------------------------")

m = fresh()
names = {r[0] for r in rows(m, "SELECT name FROM sqlite_master WHERE type='table'")}
check("a fresh database has the four account tables", sorted(names & set(TABLES)), TABLES)
check("...and is stamped schema 12",
      (rows(m, "PRAGMA user_version")[0][0], m.SCHEMA_VERSION), (12, 12))

# An 11 database: the same file with the tables gone and the stamp put back.
home = m._home
conn = sqlite3.connect(m._test_db)
conn.executescript("".join("DROP TABLE %s;" % t for t in TABLES)
                   + "PRAGMA user_version=11;")
conn.close()
m = fresh(home=home)
names = {r[0] for r in rows(m, "SELECT name FROM sqlite_master WHERE type='table'")}
check("a schema-11 database gains them on the next start",
      (sorted(names & set(TABLES)), rows(m, "PRAGMA user_version")[0][0]), (TABLES, 12))

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
check("...links to the sign-in and the board's stylesheet, relatively",
      ('href="link/steam"' in text(r), 'href="board.css"' in text(r)), (True, True))
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
check("...and a sign-in still completes there", len(code_of(signin(mh))), 9)

print("\n--- 4. a sign-in Steam confirms ----------------------------------")

m = fresh()
m.STEAM_HTTP.personas[SID] = ('<b>Lex</b> & "co"', "a" * 40)
r = signin(m)
code = code_of(r)
check("the page shows a code", (r.status_code, len(code), code[4:5]), (200, 9, "-"))
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
      ('href="../board.css"' in text(r), 'href="../../"' in text(r)), (True, True))
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
      (r.status_code, len(code_of(r)), len(m.STEAM_HTTP.calls)), (200, 9, 2))
r = signin(m, ip="198.51.101.4",
           mutate=lambda f: f.__setitem__("openid.response_nonce",
                                          stamp(START - steam.NONCE_SKEW) + "e"))
check("CONTROL a nonce exactly at the window's edge is accepted",
      (r.status_code, len(code_of(r)), len(m.STEAM_HTTP.calls)), (200, 9, 4))

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
           rows(m, "SELECT name FROM accounts")), (200, 9, True, [("",)]))
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
      (200, 9, [("ab?",)]))

mk = fresh(steam_key=None)
r = signin(mk)
check("no SURFD_STEAM_KEY: one request, and no profile asked for",
      (r.status_code, len(code_of(r)), len(mk.STEAM_HTTP.calls)), (200, 9, 1))

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
check("the superseded code does not link", link(m, "g1", first), {"ok": 0, "why": "code"})

run(m, "UPDATE accounts SET banned_at = ? WHERE steamid = ?", (START, SID))
r = signin(m, ip="198.51.100.8")
check("a banned account signs in and gets no code",
      (r.status_code, "is banned" in text(r), code_of(r),
       rows(m, "SELECT COUNT(*) FROM linkcodes WHERE used_at = 0")[0][0]),
      (403, True, "", 1))

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

print("\n--- 10. the lobby redeems a code ---------------------------------")

m = fresh()
code = code_of(signin(m))
check("no key, a wrong key, a non-ASCII key",
      [post(m, "/api/link", player="g1", code=code, **kw).status_code
       for kw in ({}, {"key": "nope"}, {"key": "\u043a\u043b\u044e\u0447"})],
      [403, 403, 403])
check("the right key from an untrusted address",
      post(m, "/api/link", addr="203.0.113.9", key="testkey", player="g1",
           code=code).status_code, 403)
check("...and none of those spent the code",
      rows(m, "SELECT used_at FROM linkcodes"), [(0,)])
check("no player", post(m, "/api/link", key="testkey", code=code).status_code, 400)
for bad in ("", "ABCD", "ABCD-EFG0", "ABCD-EFGHJ", "'; DROP TABLE links;--"):
    check("code %r" % bad, link(m, "shape", bad), {"ok": 0, "why": "code"})
    m.time.now += 11
check("a well-formed code nobody was given", link(m, "g0", "ABCDEFGH"),
      {"ok": 0, "why": "code"})

r = post(m, "/api/link", key="testkey", player="guid-one", node="p27510",
         code=" " + code.lower() + " ")
check("the code as typed (lower case, dash, spaces) links the install",
      (r.status_code, r.mimetype, body(r)),
      (200, "application/json",
       {"ok": 1, "steamid": SID, "name": "Lex", "avatar": "a" * 40, "banned": 0}))
check("...stored against the install, with the lobby",
      rows(m, "SELECT player, steamid, pub, node FROM links"),
      [("guid-one", SID, "", "p27510")])
check("...and the code is spent, marked with the install's public id",
      rows(m, "SELECT used_at > 0, used_by FROM linkcodes"),
      [(1, hashlib.sha256(b"guid-one").hexdigest()[:8])])
check("a spent code links nobody else", link(m, "guid-two", code),
      {"ok": 0, "why": "code"})

m.time.now += 61
code = code_of(signin(m, ip="198.51.100.20"))
m.time.now += accounts.CODE_TTL
check("a code is good at exactly ten minutes", link(m, "guid-two", code)["ok"], 1)
code = code_of(signin(m, ip="198.51.100.21"))
m.time.now += accounts.CODE_TTL + 1
check("...and not a second later", link(m, "guid-three", code), {"ok": 0, "why": "code"})
check("one account now holds two installs",
      rows(m, "SELECT player FROM links WHERE steamid = ? ORDER BY player", (SID,)),
      [("guid-one",), ("guid-two",)])
code = code_of(signin(m, ip="198.51.100.25"))
check("an install linking to the account it already has spends the code and stays",
      (link(m, "guid-two", code)["ok"],
       rows(m, "SELECT steamid FROM links WHERE player='guid-two'")), (1, [(SID,)]))

m.STEAM_HTTP.personas[SID] = ("Lex2", "c" * 40)
signin(m, ip="198.51.100.27")
check("a later sign-in refreshes the stored persona and avatar",
      rows(m, "SELECT name, avatar FROM accounts WHERE steamid = ?", (SID,)),
      [("Lex2", "c" * 40)])
m.STEAM_HTTP.personas[SID] = ("Lex", "a" * 40)
signin(m, ip="198.51.100.28")

print("\n--- 11. moving an install, and bans ------------------------------")

m.time.now += 61
code = code_of(signin(m, sid=SID2, ip="198.51.100.22"))
check("a linked install does not move on the code alone: it is told from and to",
      (link(m, "guid-two", code), rows(m, "SELECT steamid FROM links WHERE player='guid-two'"),
       rows(m, "SELECT used_at FROM linkcodes WHERE code = ?", (code.replace("-", ""),))),
      ({"ok": 0, "why": "move", "from": "Lex", "to": "Other"}, [(SID,)], [(0,)]))
r = link(m, "guid-two", code, confirm="1")
check("...and moves when the same code comes back confirmed",
      (r["ok"], r["steamid"], rows(m, "SELECT steamid FROM links WHERE player='guid-two'")),
      (1, SID2, [(SID2,)]))
check("confirm on a first link is simply a link",
      link(m, "guid-nine", code_of(signin(m, ip="198.51.100.26")), confirm="1")["ok"], 1)

m.time.now += 61
code = code_of(signin(m, sid=SID2, ip="198.51.100.23"))
run(m, "UPDATE accounts SET banned_at = ? WHERE steamid = ?", (START, SID2))
check("a code for an account banned since it was issued does not link",
      link(m, "guid-four", code), {"ok": 0, "why": "banned"})
check("...and is not spent by the attempt",
      rows(m, "SELECT used_at FROM linkcodes WHERE code = ?", (code.replace("-", ""),)),
      [(0,)])
check("a banned account's install says so",
      body(post(m, "/api/account", key="testkey", player="guid-two")),
      {"linked": 1, "steamid": SID2, "name": "Other", "avatar": "b" * 40, "banned": 1})
# guid-two was talked into a stranger's code, and the stranger got banned.
code = code_of(signin(m, sid=SID, ip="198.51.100.24"))
check("...and its owner can still take it back to their own account",
      (link(m, "guid-two", code)["why"], link(m, "guid-two", code, confirm="1")["ok"],
       body(post(m, "/api/account", key="testkey", player="guid-two"))["banned"]),
      ("move", 1, 0))

print("\n--- 12. what a lobby is told about an install --------------------")

check("no key / untrusted address",
      [post(m, "/api/account", player="guid-one").status_code,
       post(m, "/api/account", addr="203.0.113.9", key="testkey",
            player="guid-one").status_code], [403, 403])
check("no player", post(m, "/api/account", key="testkey").status_code, 400)
check("an install nobody linked",
      body(post(m, "/api/account", key="testkey", player="stranger")), {"linked": 0})
check("a linked install",
      body(post(m, "/api/account", key="testkey", player="guid-one")),
      {"linked": 1, "steamid": SID, "name": "Lex", "avatar": "a" * 40, "banned": 0})

m = fresh()
m.STEAM_HTTP.personas[SID] = ('^1Lex";quit\\', "a" * 40)
code = code_of(signin(m))
check("a hostile persona reaches the lobby as a safe name, on both routes",
      (link(m, "guid-six", code)["name"],
       body(post(m, "/api/account", key="testkey", player="guid-six"))["name"],
       rows(m, "SELECT name FROM accounts")),
      ("1Lexquit", "1Lexquit", [('^1Lex";quit\\',)]))

m = fresh()
code = code_of(signin(m))
tries = [link(m, "guesser", "ABCDEFGH")["why"] for _ in range(accounts.TRY_RATE_MAX + 1)]
check("%d guesses a minute per install, then it is told to slow down"
      % accounts.TRY_RATE_MAX,
      (tries[:-1] == ["code"] * accounts.TRY_RATE_MAX, tries[-1]), (True, "slow"))
check("...even with the right code", link(m, "guesser", code), {"ok": 0, "why": "slow"})
check("...while another install links with it", link(m, "honest", code)["ok"], 1)

m = fresh()
code = code_of(signin(m))
run(m, "ALTER TABLE links RENAME TO links_gone")
r = post(m, "/api/link", key="testkey", player="unlucky", code=code)
run(m, "ALTER TABLE links_gone RENAME TO links")
check("a storage error is a 500, and the code is still good afterwards",
      (r.status_code, rows(m, "SELECT used_at FROM linkcodes"),
       link(m, "unlucky", code)["ok"]), (500, [(0,)], 1))

for raw, want in (("abcd-efgh", "ABCDEFGH"), (" AB CD-EF GH ", "ABCDEFGH"),
                  ("ABCDEFG0", ""), ("ABCDEFGI", ""), ("ABCDEFG", ""),
                  ("ABCDEFGHJ", ""), ("ABCDEFGH\n", "ABCDEFGH"), ("", ""), (None, "")):
    check("clean_code %r" % (raw,), accounts.clean_code(raw), want)

m = fresh()
got = [post(m, "/api/account", key="testkey", player="p%d" % i).status_code
       for i in range(accounts.ACCT_RATE_MAX + 1)]
check("%d account queries a minute from one address, then 429" % accounts.ACCT_RATE_MAX,
      (got[:-1] == [200] * accounts.ACCT_RATE_MAX, got[-1]), (True, 429))

m = fresh()
code = code_of(signin(m))
tries = [post(m, "/api/link", key="testkey", player="hammer", code="ABCDEFGH")
         for _ in range(accounts.LINK_RATE_MAX + 1)]
check("one install hammering link is told to slow down, not counted against the lobbies",
      ([r.status_code for r in tries] == [200] * len(tries),
       [body(r)["why"] for r in tries].count("slow"), link(m, "bystander", code)["ok"]),
      (True, len(tries) - accounts.TRY_RATE_MAX, 1))

m = fresh()
got = [post(m, "/api/link", key="testkey", player="p%d" % i, code="ABCDEFGH").status_code
       for i in range(accounts.LINK_RATE_MAX + 1)]
check("%d link calls a minute from one address, then 429" % accounts.LINK_RATE_MAX,
      (got[:-1] == [200] * accounts.LINK_RATE_MAX, got[-1]), (True, 429))
got = [post(m, "/api/account", key="testkey", player="p%d" % i).status_code
       for i in range(accounts.ACCT_RATE_MAX)]
check("...which costs the lobbies none of their %d account queries" % accounts.ACCT_RATE_MAX,
      got == [200] * accounts.ACCT_RATE_MAX, True)

m = fresh()
got = [post(m, "/api/link", player="p", code="ABCDEFGH").status_code
       for _ in range(accounts.LINK_FLOOD_MAX + 1)]
check("%d keyless link calls a minute are refused one by one, then unread"
      % accounts.LINK_FLOOD_MAX,
      (got[:-1] == [403] * accounts.LINK_FLOOD_MAX, got[-1]), (True, 429))

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
