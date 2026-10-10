#!/usr/bin/env python3
"""
p615link.py -- Patch 615's arm: a real client links itself through a real server.

    python tools/p615link.py --progs <dir with qwprogs.dat csprogs.dat menu.dat>
                             [--output-dir <dir>] [--refuse-address | --taken | --receipt]

WHAT RUNS.  A private rig (junctions into the install's content, as
runlines_smoke.py builds one; its own qkey and fskey, never the owner's), the
installed dedicated server and client, and THIS CHECKOUT'S surfd in a thread
with Steam faked.  So each signature is made by the engine's C and checked by
surfd's Python over a statement each built for itself: the one thing no
single-language test can show.

IT TYPES, AND READS WHAT COMES BACK.  The client runs with -plugin and takes
console lines on stdin (conbridge.py's way in), because a link is two commands
and the second is a number the SERVER prints: a cfg cannot know it.  Every step
waits for the subject's own line, never for a clock.

THE ARMS, in one client session:
  A  on connect the client proves its key and is told it is not linked
  L  two asks for a nonce in one packet get ONE: the second must not replace
     what the client is already signing (1 reconnect in 9 was refused this way
     before the client's ask timer left the game clock, which jumps at connect)
  B  `link <code>` (lower case, with a dash) is answered with the account's
     name and a number; `link <number>` links it
  C  `link` alone says who it is linked to
  D  another account's code says where it is and where it would go; a WRONG
     number is refused and moves nothing; asking again and the right one moves
  F  an unknown code is refused; G two malformed ones never leave the client,
     and the one carrying a command does not run it
  H  CONTROL: the right code's digest with a signature over the WRONG nonce is
     refused and leaves the code unclaimed -- so B's yes was the signature's
  J  receipts shaped like a finish's (ticks 7) and a kept abandon's (ticks 0)
     go to the run's own handler while a link is owed, and the link completes
  K  CONTROL for text left behind by another server: `link <code>` and then a
     guessed number, typed blind, links nothing
  I  after a reconnect the server knows who it is from the proof alone
--refuse-address runs surfd with an address list that omits this box: the same
`link` must be refused for the ADDRESS, which is the control for that check.
--taken sets a cvar named `link` before connecting, as a server the player was
on earlier can: the game code's command cannot be registered over it, so the
client must say so and a code typed anyway must reach no lobby.
--receipt runs cfg/test/p417sign.cfg (a whole run on a listen host) on these
progs instead, and has tools/rcptcheck.py read the receipt it leaves: the
dispatch this patch put in front of SV_RecRcpt must not cost a run its receipt.

Graded on the subject's own lines: the client's console, the server's
`account:` prints, and the rows surfd wrote.  Exit 1 on any miss.
"""
import argparse
import hashlib
import os
import pathlib
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT_DIRS = ("maps", "gfx", "glsl", "models", "particles", "scripts")
KEY = "p615-not-a-real-key"
SIDS = ("76561198000000001", "76561198000000002", "76561198000000003", "76561198000000004")
NAMES = dict(zip(SIDS, ("Lex", "Other", "Third", "Fourth")))
FAILED = []


def check(label, got, want):
    ok = got == want
    print("%-4s %-66s %s" % ("ok" if ok else "FAIL", label, ascii(got)))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


def digest(tag, text):
    return hashlib.sha256((tag + text).encode("ascii")).hexdigest()[:32]


def build_rig(a):
    rig = pathlib.Path(tempfile.mkdtemp(prefix="p615-", dir=a.output_dir))
    gd = rig / "ftesurf"
    gd.mkdir()
    junctions = []
    shutil.copyfile(ROOT / "default.fmf", rig / "default.fmf")
    for name in CONTENT_DIRS:
        source = a.content / "ftesurf" / name
        target = gd / name
        if name in ("glsl", "scripts"):
            if source.is_dir():
                shutil.copytree(source, target)
        elif source.is_dir():
            subprocess.run(["cmd", "/c", "mklink", "/J", str(target), str(source)],
                           check=True, capture_output=True)
            junctions.append(target)
    for name in ("qwprogs.dat", "csprogs.dat", "menu.dat"):
        shutil.copyfile(a.progs / name, gd / name)
        print("  %-12s %s" % (name, hashlib.sha256((gd / name).read_bytes()).hexdigest()[:16]))
    shutil.copyfile(ROOT / "ftesurf/fs_addons.default.txt", gd / "fs_addons.default.txt")
    for rel in subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "ftesurf/cfg"],
                                       text=True).splitlines():
        target = rig / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    (gd / "downloads/csprogsvers").mkdir(parents=True)
    subprocess.run([sys.executable, str(ROOT / "tools/seed_csprogs.py"), str(gd / "csprogs.dat")],
                   check=True, capture_output=True)
    return rig, gd, junctions


def start_surfd(rig, port, hosts):
    home = rig / "surfd-home"
    home.mkdir()
    (home / "surfd.env").write_text("SURFD_KEY=%s\n" % KEY)
    os.environ.update(SURFD_HOME=str(home), SURFD_DB=str(home / "p615.db"),
                      SURFD_ENV=str(home / "surfd.env"), SURFD_RUNS=str(home / "runs"),
                      SURFD_MAPS=str(home / "maps"), SURFD_WEBSHOTS=str(home / "shots"),
                      SURFD_TOOLS=str(ROOT / "tools"), SURFD_LINK_HOSTS=hosts,
                      SURFD_BOARD_URL="http://127.0.0.1:%d/board" % port)
    for k in ("SURFD_PUBLIC_HOST", "SURFD_TRUSTED", "SURFD_PROXIES", "SURFD_ADMIN_HASH",
              "SURFD_STEAM_KEY", "SURFD_GAME"):
        os.environ.pop(k, None)
    sys.path.insert(0, str(ROOT / "surfd"))
    import accounts
    import surfd
    from werkzeug.serving import make_server
    # One client here takes a dozen link steps in a minute; a player takes two.
    # The per-address limits have their own arms in test_accounts.py.
    accounts.TRY_RATE_MAX = accounts.ACCT_PEER_MAX = 1000

    def steam_says_yes(url, data=None, timeout=None):
        return b"ns:http://specs.openid.net/auth/2.0\nis_valid:true\n"
    surfd.STEAM_HTTP = steam_says_yes
    server = make_server("127.0.0.1", port, surfd.app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, home / "p615.db"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_a, **_k):
        return None


def sign_in(port, sid, ip):
    """Steam's side of a sign-in, played against the running surfd.  -> the code."""
    base = "http://127.0.0.1:%d/board/link" % port
    opener = urllib.request.build_opener(NoRedirect)
    try:
        opener.open(urllib.request.Request(base + "/steam", headers={"X-Real-IP": ip}))
        raise RuntimeError("/steam did not redirect")
    except urllib.error.HTTPError as r:
        cookie = r.headers["Set-Cookie"].split(";")[0]
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(r.headers["Location"]).query)
        return_to = q["openid.return_to"][0]
    claimed = "https://steamcommunity.com/openid/id/" + sid
    fields = {
        "openid.ns": "http://specs.openid.net/auth/2.0", "openid.mode": "id_res",
        "openid.op_endpoint": "https://steamcommunity.com/openid/login",
        "openid.claimed_id": claimed, "openid.identity": claimed,
        "openid.return_to": return_to,
        "openid.response_nonce": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + sid[-4:] + ip,
        "openid.assoc_handle": "1234567890",
        "openid.signed": "signed,op_endpoint,claimed_id,identity,return_to,"
                         "response_nonce,assoc_handle",
        "openid.sig": "c2lnbmF0dXJlLi4uLi4uLi4uLi4uLi4=",
    }
    url = return_to + "&" + urllib.parse.urlencode(fields)
    page = urllib.request.urlopen(urllib.request.Request(
        url, headers={"X-Real-IP": ip, "Cookie": cookie})).read().decode()
    at = page.find('class="linkcode">link ')
    if at < 0:
        raise RuntimeError("the sign-in page showed no code")
    return page[at + 22:at + 31]


class Log(object):
    """One engine's log, read from where the last wait left off."""
    def __init__(self, path):
        self.path, self.at = path, 0

    def text(self):
        try:
            return re.sub(r"\^[0-9a-zA-Z]", "", self.path.read_text(errors="replace"))
        except OSError:
            return ""

    def wait(self, pattern, timeout=25):
        """The first match after everything already waited for, or None."""
        end = time.time() + timeout
        while True:
            m = re.search(pattern, self.text()[self.at:])
            if m:
                self.at += m.end()
                return m
            if time.time() > end:
                return None
            time.sleep(0.25)

    def count(self, needle, want, timeout=10):
        end = time.time() + timeout
        while self.text().count(needle) < want and time.time() < end:
            time.sleep(0.25)
        return self.text().count(needle)


def receipt_arm(a, rig, gd):
    """A whole run on a listen host with these progs; its receipt, read back."""
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 7
    client = subprocess.Popen(
        [str(a.content / "ftesurf64.exe"), "-basedir", str(rig), "-manifest",
         str(rig / "default.fmf"), "-window", "+exec", "cfg/test/p417sign.cfg"],
        cwd=a.content, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)
    try:
        client.wait(timeout=a.timeout)
    finally:
        if client.poll() is None:
            client.terminate()
            client.wait(timeout=10)
    log = gd / "logs/p417sign.log"
    text = log.read_text(errors="replace") if log.is_file() else ""
    found = sorted((gd / "data/evidence/bhop_eazy").glob("*.rcpt")) if (
        gd / "data/evidence/bhop_eazy").is_dir() else []
    out = subprocess.run([sys.executable, str(ROOT / "tools/rcptcheck.py"),
                          str(gd / "data/evidence/bhop_eazy")],
                         capture_output=True, text=True, errors="replace").stdout
    print("")
    for line in out.splitlines():
        print("    " + line[:150])
    check("the run finished on these progs", "P417 S done" in text, True)
    check("it left exactly one receipt", len(found), 1)
    check("rcptcheck reads it: signature valid, no fault",
          ("signature VALID" in out, "1 receipt(s) checked, 0 with faults" in out), (True, True))
    return 1 if FAILED else 0


def link_arm(a, send, cl, sv, db, gport, codes):
    def rows(sql):
        conn = sqlite3.connect(db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def key():
        return rows("SELECT length(pub), steamid, length(player), node FROM linkkeys")

    c1, c2, c3, c4 = (c.replace("-", "") for c in codes)
    hello = r"kind 1 answered for client 1: answered 1 ok 0 linked %d banned 0 why '%s'"

    if a.taken:
        check("with `link` already a cvar the client says so, and asks for no nonce",
              (bool(cl.wait("another server changed this game's link command", 25)),
               sv.text().count("issued to client")), (True, 0))
        send("link " + codes[0])
        time.sleep(4)
        check("...and a code typed anyway reaches no lobby",
              (sv.text().count("asked for client"), key(),
               rows("SELECT used_at, claim FROM linkcodes WHERE code = '%s'" % c1)),
              (0, [], [(0, "")]))
        return

    if a.refuse_address:
        check("the connect's proof is refused for the address, and says nothing",
              bool(sv.wait(hello % (0, "server"))), True)
        send("link " + codes[0])
        check("CONTROL with this box's address unlisted: link is refused for the ADDRESS",
              (bool(cl.wait("does not know this server by the address")), key(),
               rows("SELECT used_at, claim FROM linkcodes WHERE code = '%s'" % c1)),
              (True, [], [(0, "")]))
        return

    check("A  the connect's proof was answered unasked: not linked, and how to link",
          (bool(sv.wait(hello % (0, ""))), bool(cl.wait("not linked to a Steam account"))),
          (True, True))

    issued = sv.text().count("issued to client")
    send("cmd acct_hello; cmd acct_hello")  # one console line: both reach the server together
    check("L  two asks back to back get ONE nonce, and the answer is still the truth",
          (bool(sv.wait(hello % (0, ""))), sv.text().count("issued to client") - issued),
          (True, 1))

    send("link " + codes[0].lower())
    m = cl.wait(r"link this install to Lex\? Type link ([0-9]{6}) to confirm")
    check("B  link <code> is answered with the account's name and a number",
          (bool(m), key(), rows("SELECT used_at, length(claim) FROM linkcodes WHERE code = '%s'" % c1)),
          (True, [], [(0, 64)]))
    send("link " + (m.group(1) if m else "000000"))
    check("B  link <number> links it",
          (bool(cl.wait("now linked to Lex")), key()),
          (True, [(64, SIDS[0], 32, "p%d" % gport)]))

    send("link")
    check("C  link alone says who", bool(cl.wait("this install is linked to Lex")), True)

    time.sleep(3.2)                         # the server's gap between one player's codes
    send("link " + codes[1])
    m = cl.wait(r"is linked to Lex\. To move it to Other type link ([0-9]{6})")
    check("D  another account's code says where it is and where it would go", bool(m), True)
    pin = m.group(1) if m else "000000"
    send("link " + ("%06d" % ((int(pin) + 1) % 1000000)))
    check("D  a wrong number is refused and moves nothing",
          (bool(cl.wait("that is not the number shown")), key()[0][1] if key() else ""),
          (True, SIDS[0]))
    time.sleep(3.2)
    send("link " + codes[1])
    m = cl.wait(r"To move it to Other type link ([0-9]{6})")
    send("link " + (m.group(1) if m else "000000"))
    check("D  asking again, and the right number, moves it",
          (bool(cl.wait("now linked to Other")), key()[0][1] if key() else ""),
          (True, SIDS[1]))

    time.sleep(3.2)
    send("link ABCD-EFGH")
    check("F  an unknown code is refused", bool(cl.wait("not valid or has expired")), True)

    send("link nonsense!")
    send('link "ABCD;echo P615-INJECTED;EFGH"')
    got = [bool(cl.wait("that is not a code")), bool(cl.wait("that is not a code"))]
    time.sleep(1.0)
    check("G  two malformed codes never leave the client, and nothing ran",
          (got, "P615-INJECTED" in cl.text().replace("ABCD;echo P615-INJECTED;EFGH", ""),
           "P615-INJECTED" in sv.text()), ([True, True], False, False))

    time.sleep(3.2)
    send("cmd link " + digest("ftesurf-code ", c3))
    send("rec_sign %s -3 - 0" % ("0" * 32))
    check("H  CONTROL the right code under a signature for the wrong nonce",
          (bool(cl.wait("could not sign for the code")),
           rows("SELECT used_at, claim FROM linkcodes WHERE code = '%s'" % c3)),
          (True, [(0, "")]))

    time.sleep(3.2)
    before = sv.text().count("timer: receipt refused")
    send("cmd link " + digest("ftesurf-code ", c3))
    send("rec_sign %s 7 - 0" % ("1" * 32))
    send("rec_sign %s 0 - 0" % ("2" * 32))
    passed = sv.count("timer: receipt refused", before + 2) - before
    send("rec_sign %s -3 - 0" % digest("ftesurf-link ", c3))
    m = cl.wait(r"To move it to Third type link ([0-9]{6})")
    pin = m.group(1) if m else "000000"
    send("cmd link " + pin)
    send("rec_sign %s -4 - 0" % digest("ftesurf-confirm ", c3 + " " + pin))
    check("J  both run-shaped receipts reached the run's handler while a link was owed",
          (passed, bool(m), bool(cl.wait("now linked to Third")), key()[0][1] if key() else ""),
          (2, True, True, SIDS[2]))

    time.sleep(3.2)
    send("link " + codes[3])                # what an `in` timer left by another server can do
    asked = bool(cl.wait(r"To move it to Fourth type link [0-9]{6}"))
    send("link 000000")                     # ...and what it cannot: read the number
    check("K  CONTROL text typed blind asks, guesses, and links nothing",
          (asked, bool(cl.wait("that is not the number shown")), key()[0][1] if key() else "",
           rows("SELECT used_at, length(claim) FROM linkcodes WHERE code = '%s'" % c4)),
          (True, True, SIDS[2], [(0, 64)]))

    send("disconnect")
    time.sleep(2.0)
    send("connect 127.0.0.1:%d" % gport)
    check("I  after a reconnect the proof alone says who it is",
          (bool(sv.wait(hello % (1, ""), 45)),
           bool(cl.wait("this install is linked to Third", 15))), (True, True))

    used = dict(rows("SELECT code, used_by FROM linkcodes"))
    pub16 = rows("SELECT substr(pub, 1, 16) FROM linkkeys")
    check("surfd holds one key, for the third account, from this lobby",
          key(), [(64, SIDS[2], 32, "p%d" % gport)])
    check("...the three codes it spent are marked with that key, the fourth is not spent",
          ([used.get(c) for c in (c1, c2, c3)] == [pub16[0][0]] * 3 if pub16 else None,
           used.get(c4)), (True, ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--content", type=pathlib.Path, default=pathlib.Path("C:/FTESurf"))
    ap.add_argument("--output-dir", type=pathlib.Path)
    ap.add_argument("--map", default="bhop_eazy")
    ap.add_argument("--refuse-address", action="store_true")
    ap.add_argument("--taken", action="store_true")
    ap.add_argument("--receipt", action="store_true")
    ap.add_argument("--timeout", type=int, default=240)
    a = ap.parse_args()
    # Absolute: the engines run with the install as their cwd, not this one.
    a.progs = a.progs.resolve()
    a.output_dir = (a.output_dir or pathlib.Path(tempfile.gettempdir())).resolve()

    rig, gd, junctions = build_rig(a)
    print("rig", rig)
    server = client = web = None
    try:
        if a.receipt:
            return receipt_arm(a, rig, gd)
        gport = None
        for cand in range(27601, 27620):        # a lobby-range port nobody holds
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                try:
                    probe.bind(("127.0.0.1", cand))
                    gport = cand
                    break
                except OSError:
                    continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            hport = probe.getsockname()[1]
        web, db = start_surfd(rig, hport, "192.0.2.1" if a.refuse_address else "127.0.0.1")
        codes = [sign_in(hport, sid, "198.51.100.%d" % (n + 1)) for n, sid in enumerate(SIDS)]
        conn = sqlite3.connect(db)
        for sid, name in NAMES.items():         # the fake has no profile to fetch
            conn.execute("UPDATE accounts SET name = ? WHERE steamid = ?", (name, sid))
        conn.commit()
        conn.close()

        common = ["-basedir", str(rig), "-manifest", str(rig / "default.fmf"),
                  "+set", "cfg_save_auto", "0", "+set", "log_enable", "1",
                  "+set", "log_dir", "logs"]
        server = subprocess.Popen(
            ["C:/FTEQuake/fteqwsv64.exe", *common, "+set", "log_name", "p615sv",
             "+set", "developer", "1",       # the server's account lines are dprints
             "+set", "sv_public", "0", "+set", "sv_port", str(gport),
             "+set", "sv_guidkey", "p615-probe", "+set", "sv_maxrate", "0",
             "+set", "sv_maxdownloadrate", "0",
             "+set", "lobby_master", "http://127.0.0.1:%d" % hport,
             "+set", "lobby_master_key", KEY, "+set", "lobby_master_rate", "30",
             "+map", a.map], cwd=a.content, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)
        if server.poll() is not None:
            raise RuntimeError("the server exited at start (code %s)" % server.returncode)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7                      # SW_SHOWMINNOACTIVE
        # -plugin: console lines on stdin, and the client quits when the pipe closes.
        client = subprocess.Popen(
            [str(a.content / "ftesurf64.exe"), "-plugin", *common, "+set", "log_name", "p615cl",
             "-window", "-nosound", "+set", "con_savehistory", "0", "+set", "cl_idlefps", "0",
             "+set", "cl_maxfps", "100", "+set", "rate", "2000000", "+set", "drate", "5000000"],
            cwd=a.content, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)

        def send(line):
            client.stdin.write(line.encode("ascii") + b"\n")
            client.stdin.flush()

        cl, sv = Log(gd / "logs/p615cl.log"), Log(gd / "logs/p615sv.log")
        time.sleep(8)                           # a line read while starting is dropped
        print("")
        if a.taken:
            send("set link taken")
        up = None
        for _ in range(3):
            send("connect 127.0.0.1:%d" % gport)
            up = cl.wait("FTESurf CSQC loaded", 40)
            if up:
                break
        check("the client connected and its game code loaded", bool(up), True)
        if up:
            link_arm(a, send, cl, sv, db, gport, codes)
        check("no VM error or unknown command in the client's log",
              [w for w in ("Unknown command", "QC VM error", "Cannot call", "stack overflow")
               if w in cl.text()], [])
        own = a.content / "fskey"
        # --taken signs nothing, so it makes no key.
        check("the rig made its own signing key and the owner's was not touched",
              ((rig / "fskey").is_file() or (gd / "fskey").is_file(),
               own.is_file() and own.stat().st_mtime > time.time() - 900),
              (not a.taken, False))
        try:
            send("quit")
            client.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return 1 if FAILED else 0
    finally:
        for process in (client, server):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        if web is not None:
            web.shutdown()
        for path in junctions:
            if not path.lstat().st_file_attributes & 0x400:
                raise RuntimeError("refusing removal: not our junction: %s" % path)
            path.rmdir()
        print("\nrig kept (junctions removed):", rig)
        if FAILED:
            print("%d FAILURE(S):" % len(FAILED))
            for f in FAILED:
                print("  " + f)


if __name__ == "__main__":
    raise SystemExit(main())
