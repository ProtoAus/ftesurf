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

IT TYPES TWO WAYS, AND THE DIFFERENCE IS THE TEST.  Console lines go in on
stdin (-plugin, conbridge.py's way).  KEYS go to the rig's window as WM_KEYDOWN,
the path a keyboard's take through the engine to CSQC_InputEvent.  A link is
made by keys and by nothing else (cl_account.qc), so every arm that links
presses keys, and K presses the same Enter from the console and must fail.

THE ARMS, in one client session:
  A  on connect the client proves its key and is told it is not linked
  L  two asks for a nonce in one packet get ONE: the second must not replace
     what the client is already signing (1 reconnect in 9 was refused this way
     before the client's ask timer left the game clock, which jumps at connect)
  N  the game starts the link (Patch 619): the prompt that came up by itself
     leaves the game its keys (Tab among them); an Enter fed from the console
     and a stuffed code start nothing; Enter on it starts a link, the address
     it shows is copied, and the wait for the browser leaves the keys too
  B  the code with an opener that is not this client's (all the wire shows)
     opens nothing; a "browser" at another address signs in with the address
     the box showed and is shown a number;
     the game asks "link to X?" and for that number by itself; Enter and Y
     without it link nothing; the number and Enter link, and an Esc right
     after cannot say "cancelled" over a confirm that is already with surfd
  Q  Esc on the wait cancels it, and a sign-in for that start raises no
     question; a wrong number says so and spends the start
  C  `cmd link` says who it is linked to
  D  a sign-in that did not start in the game: `link`, and another account's
     code typed into the box says where the install is and where it would go;
     Esc moves nothing; asking again and Enter moves it
  F  an unknown code is refused; G a code given as `link <code>` on the console
     is not sent, and one carrying a command does not run it
  K  CONTROLS for a link nobody at the keyboard made: with the question up, an
     Enter fed down the input chain from the console (`vote key`) does not
     link, nor do the SPACE presses the engine's `in_journal_synth` injects as
     real ones, nor a held Enter's auto-repeat; with no box open, a stuffed
     `acct_ask` raises no question; and no .qc file calls CSQC_InputEvent
  M  `zone_goto` and `ghost speed` no longer paste their argument into a console
     line (a quoted `1;rec_sign ...` ran as a second command at game code's level)
  H  CONTROL: the right code's digest with a signature over the WRONG nonce is
     refused and leaves the code unclaimed -- so B's yes was the signature's
  J  receipts shaped like a finish's (ticks 7) and a kept abandon's (ticks 0)
     go to the run's own handler while a link is owed, and the link completes
  I  after a reconnect the server knows who it is from the proof alone
--refuse-address runs surfd with an address list that omits this box: the same
`link` must be refused for the ADDRESS, which is the control for that check.
--taken sets a cvar named `link` before connecting, as a server the player was
on earlier can: the game code's command cannot be registered over it, so the
client must say so, and `link` opens no box.
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


def browser(port, sid, ip, c=""):
    """A browser at `ip` signing in through (a faked) Steam, with the code a
    game started in the address if `c`.  -> the page it ends on."""
    base = "http://127.0.0.1:%d/board/link" % port
    opener = urllib.request.build_opener(NoRedirect)
    try:
        opener.open(urllib.request.Request(base + "/steam" + ("?c=" + c if c else ""),
                                           headers={"X-Real-IP": ip}))
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
    return urllib.request.urlopen(urllib.request.Request(
        url, headers={"X-Real-IP": ip, "Cookie": cookie})).read().decode()


def code_on(page):
    """The code a sign-in page shows to be typed, or ""."""
    at = page.find('class="linkcode">')
    return page[at + 17:page.find("<", at + 17)] if at >= 0 else ""


def sign_in(port, sid, ip):
    """A sign-in that did not start in a game.  -> the code to type."""
    code = code_on(browser(port, sid, ip))
    if not code:
        raise RuntimeError("the sign-in page showed no code")
    return code


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


class Keys(object):
    """Key presses for one process's game window, as Windows delivers a
    keyboard's: WM_KEYDOWN and WM_KEYUP on its own queue.  Not the console."""
    VK = {"enter": 0x0D, "esc": 0x1B, "back": 0x08, "tab": 0x09, "w": 0x57}

    def __init__(self, pid):
        import ctypes
        from ctypes import wintypes
        self.u = ctypes.windll.user32
        self.u.MapVirtualKeyW.restype = ctypes.c_uint
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def each(hwnd, _lparam):
            owner = wintypes.DWORD()
            self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            name = ctypes.create_unicode_buffer(64)
            self.u.GetClassNameW(hwnd, name, 64)
            if owner.value == pid and name.value == "FTEGLQuake":
                found.append(hwnd)
            return True
        self.u.EnumWindows(each, 0)
        if len(found) != 1:
            raise RuntimeError("the client has %d game windows, not one" % len(found))
        self.hwnd = found[0]

    def _post(self, vk, down, repeat=False):
        scan = self.u.MapVirtualKeyW(vk, 0)
        lparam = 1 | (scan << 16)
        if repeat:
            lparam |= 1 << 30               # "was down before": an OS auto-repeat
        if not down:
            lparam |= (1 << 30) | (1 << 31)
        if not self.u.PostMessageW(self.hwnd, 0x0100 if down else 0x0101, vk, lparam):
            raise RuntimeError("PostMessage failed")

    def press(self, name):
        vk = self.VK[name]
        self._post(vk, True)
        time.sleep(0.06)
        self._post(vk, False)
        time.sleep(0.06)

    def hold(self, name, repeats):
        """Down, `repeats` auto-repeats, and NO release."""
        vk = self.VK[name]
        self._post(vk, True)
        for _ in range(repeats):
            time.sleep(0.04)
            self._post(vk, True, repeat=True)

    def release(self, name):
        self._post(self.VK[name], False)
        time.sleep(0.06)

    def type(self, text):
        for ch in text.upper():
            vk = ord(ch)                    # letters and digits are their own VK
            self._post(vk, True)
            time.sleep(0.03)
            self._post(vk, False)
            time.sleep(0.03)


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


# The address the box shows for a start: its code, and the opener the client made.
GO = r"sign in at proto\.bar/ftesurf/board/link\?c=([A-Z2-9]{10})&k=([0-9a-f]{24})"


def address(m):
    """What follows `?c=` in the address a start showed."""
    return "%s&k=%s" % (m.group(1), m.group(2)) if m else ""


def link_arm(a, send, keys, cl, sv, db, gport, codes):
    def rows(sql):
        conn = sqlite3.connect(db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def key():
        return rows("SELECT length(pub), steamid, length(player), node FROM linkkeys")

    def who():
        k = key()
        return k[0][1] if k else ""

    def opens(line):
        """A console line that should open the box.  -> it did, counted: an
        earlier box's "open" line is still in the log, and typing into a box
        that is not up yet loses the first key to the game (it did)."""
        n = cl.text().count("link box open")
        send(line)
        opened = cl.count("link box open", n + 1) > n
        cl.at = max(cl.at, cl.text().rfind("link box open"))
        return opened

    def box(code):
        """`link`, then the code typed into the box and Enter.  -> the box opened."""
        opened = opens("link")
        keys.type(code)
        keys.press("enter")
        return opened

    c1, c2, c3, c4 = (c.replace("-", "") for c in codes)
    hello = r"kind 1 answered for client 1: answered 1 ok 0 linked %d banned 0 why '%s'"
    asked = r"kind 2 answered for client 1: answered 1 ok 0 linked 0 banned 0 why '%s'"

    if a.taken:
        check("with `link` already a cvar the client says so, and asks for no nonce",
              (bool(cl.wait("another server changed this game's link command", 25)),
               sv.text().count("issued to client")), (True, 0))
        send("link")
        time.sleep(1.0)
        keys.type(c1)
        keys.press("enter")
        time.sleep(4)
        check("...and `link` opens no box, so a code typed anyway reaches no lobby",
              ("link box open" in cl.text(), sv.text().count("asked for client"), key(),
               rows("SELECT used_at, claim FROM linkcodes WHERE code = '%s'" % c1)),
              (False, 0, [], [(0, "")]))
        return

    if a.refuse_address:
        check("the connect's proof is refused for the address, and says nothing",
              bool(sv.wait(hello % (0, "server"))), True)
        opened = box(c1)
        check("CONTROL with this box's address unlisted: the link is refused for the ADDRESS",
              (opened, bool(cl.wait("does not know this server by the address")), key(),
               rows("SELECT used_at, claim FROM linkcodes WHERE code = '%s'" % c1)),
              (True, True, [], [(0, "")]))
        return

    check("A  the connect's proof was answered unasked: not linked, and the prompt came up",
          (bool(sv.wait(hello % (0, ""))), bool(cl.wait("not linked to a Steam account")),
           bool(cl.wait("press Enter to link your Steam account", 10))),
          (True, True, True))

    issued = sv.text().count("issued to client")
    send("cmd acct_hello; cmd acct_hello")  # one console line: both reach the server together
    check("L  two asks back to back get ONE nonce, and the answer is still the truth",
          (bool(sv.wait(hello % (0, ""))), sv.text().count("issued to client") - issued),
          (True, 1))

    # N: the game starts the link.  Enter on the prompt that came up by itself;
    # the address it shows is opened by a "browser", which is shown a number;
    # the game asks for that number by itself.
    time.sleep(3.2)                         # L's second ask is inside the lobby's gap
    # The prompt is not the keyboard's owner: W is the game's (it prints), and
    # Tab, which is how a player gets to a browser, is nobody's.
    send('bind w "echo gamekey-w"')
    time.sleep(0.5)
    keys.press("w")
    keys.press("tab")
    time.sleep(0.5)
    check("N  the prompt that came up by itself leaves the game its keys, and Tab is not its",
          (cl.text().count("gamekey-w"), "steam: starting" in cl.text(), "code sent" in cl.text()),
          (1, False, False))
    send("vote key 13 1")                   # Enter, fed down the chain from the console
    send("vote key 13 0")
    fed = bool(cl.wait(r"vote key: scan 13 down 1", 10))
    send("acct_go ABCDEFGHJK")              # ...and an address nobody started
    time.sleep(1.5)
    check("N  CONTROL an Enter fed from the console starts nothing, and a stuffed code shows no address",
          (fed, "steam: starting" in cl.text(), "sign in at" in cl.text()), (True, False, False))
    keys.press("enter")
    m = cl.wait(GO, 20)
    started = m.group(1) if m else ""
    check("N  Enter on the prompt starts a link: an address with a code surfd keeps for this key",
          (bool(m), "copied" in cl.text().split("sign in at")[-1][:120],
           rows("SELECT steamid, length(claim), shown, used_at FROM linkcodes WHERE code = '%s'"
                % started)),
          (True, True, [("", 64, "?", 0)]))
    keys.press("w")
    time.sleep(0.5)
    check("N  the wait for the browser leaves the game its keys too",
          cl.text().count("gamekey-w"), 2)
    # What the wire shows is the code.  With it and an opener that is not this
    # client's, a sign-in attaches nothing and the game is asked nothing.
    page = browser(a.hport, SIDS[0], "198.51.100.8", started + "&k=" + "0" * 24)
    time.sleep(3.0)
    check("B  CONTROL the code with another opener opens nothing, and no question is raised",
          ("Start again from the game" in page, code_on(page),
           rows("SELECT steamid FROM linkcodes WHERE code = '%s'" % started),
           "link this game to" in cl.text().split("sign in at")[-1]),
          (True, "", [("",)], False))
    page = browser(a.hport, SIDS[0], "198.51.100.9", address(m))
    number = code_on(page)
    asked_here = bool(cl.wait(r"link this game to Lex\? Type the number from the sign-in page", 15))
    check("B  a browser at ANOTHER address signs in with the address and is shown a number; the game asks for it",
          (len(number), number.isdigit(), "Type this number into the game" in page,
           asked_here, key()), (4, True, True, True, []))
    time.sleep(0.8)                         # the question ignores keys for 0.6 s
    keys.press("enter")                     # no number yet
    keys.type("y")                          # ...and Y is not an answer to this question
    time.sleep(1.0)
    check("B  CONTROL Enter and Y without the page's number link nothing",
          ("steam: linking" in cl.text().split("Type the number from the sign-in page")[-1],
           key()), (False, []))
    keys.type(number)
    keys.press("enter")
    keys.press("esc")                       # too late: the confirm is with surfd
    linked = bool(cl.wait("now linked to Lex"))
    check("B  the page's number and Enter link it; an Esc after does not claim to have cancelled",
          (linked, key(), "link cancelled" in cl.text().split("steam: linking")[-1]),
          (True, [(64, SIDS[0], 32, "p%d" % gport)], False))
    # Backspace, not Esc, to dismiss an ending: if the Esc above already closed
    # it, a second Esc is the GAME's and opens the menu, which then has the
    # keyboard and every later key in this arm goes nowhere (it did).
    keys.press("back")

    # Q: the ways a start ends without a link.
    time.sleep(3.2)
    opened = opens("link")
    keys.press("enter")
    m = cl.wait(GO, 20)
    dropped = m.group(1) if m else ""
    keys.press("esc")
    cancelled = bool(cl.wait("link cancelled", 10))
    browser(a.hport, SIDS[0], "198.51.100.9", address(m))
    time.sleep(5.0)                         # two of the lobby's waits, had it kept asking
    check("Q  Esc on the wait cancels it: a sign-in for that start raises no question here",
          (opened, bool(m), cancelled, "link this game to" in cl.text().split("link cancelled")[-1]),
          (True, True, True, False))
    opens("link")
    keys.press("enter")
    m = cl.wait(GO, 20)
    spent = m.group(1) if m else ""
    number = code_on(browser(a.hport, SIDS[0], "198.51.100.9", address(m)))
    up = bool(cl.wait(r"link this game to Lex\? Type the number from the sign-in page", 15))
    time.sleep(0.8)
    keys.type("%04d" % ((int(number or 0) + 1) % 10000))
    keys.press("enter")
    check("Q  a wrong number says so, and spends the start: one try",
          (up, bool(cl.wait("not the number on the page", 15)), key(),
           rows("SELECT used_by FROM linkcodes WHERE code = '%s'" % spent)),
          (True, True, [(64, SIDS[0], 32, "p%d" % gport)], [("mismatch",)]))
    keys.press("back")

    send("cmd link")
    check("C  cmd link says who", bool(cl.wait("this install is linked to Lex")), True)

    time.sleep(3.2)                         # the server's gap between one player's codes
    opened = box(c2)
    check("D  another account's code typed into the box says where it is and where it would go",
          (opened, bool(cl.wait(r"link this game to Other\? Enter to link")),
           bool(sv.wait(asked % "confirm"))), (True, True, True))
    time.sleep(0.8)
    keys.press("esc")
    check("D  Esc cancels, and moves nothing",
          (bool(cl.wait("link cancelled")), who()), (True, SIDS[0]))

    # K: with a question up, everything but a fresh key press.
    time.sleep(3.2)
    box(c2)
    up = bool(cl.wait(r"link this game to Other\? Enter to link"))
    time.sleep(0.8)
    send("vote key 13 1")                   # Enter, fed down the chain from the console
    send("vote key 13 0")
    fed = bool(cl.wait(r"vote key: scan 13 down 1", 10))
    time.sleep(2.0)
    check("K  CONTROL an Enter fed down the input chain from the console links nothing",
          (up, fed, who(), "linking" in cl.text().split("vote key: scan 13 down 1")[-1]),
          (True, True, SIDS[0], False))
    # The engine's own test command DOES reach CSQC_InputEvent: it injects SPACE
    # and mouse moves as if from a device (in_generic.c).  So SPACE answers nothing.
    send("in_journal_synth 64")
    real = bool(cl.wait(r"in_journal_synth: injected 64 mouse and 4 key events", 10))
    time.sleep(1.5)
    check("K  CONTROL the engine's injected SPACE presses reach the box and answer nothing",
          (real, who(), "linking" in cl.text().split("in_journal_synth: injected")[-1]),
          (True, SIDS[0], False))
    keys.press("esc")
    cl.wait("link cancelled")

    time.sleep(3.2)
    opens("link")
    keys.type(c2)
    before = cl.text().count("linking")
    keys.hold("enter", 40)                  # down, and forty repeats across the question's arrival
    held = bool(cl.wait(r"link this game to Other\? Enter to link"))
    keys.hold("enter", 30)                  # ...and thirty more, past its 0.6 s of deafness
    time.sleep(1.0)
    check("K  CONTROL a held Enter's repeats do not answer the question it sent",
          (held, cl.text().count("linking") - before, who()), (True, 0, SIDS[0]))
    keys.release("enter")
    keys.press("enter")
    check("D  ...and a fresh Enter moves it",
          (bool(cl.wait("now linked to Other")), who()), (True, SIDS[1]))
    keys.press("back")

    send('acct_ask 123456 "Mallory" ""')   # what a stuffed answer looks like, with no box waiting
    time.sleep(1.0)
    keys.press("enter")
    time.sleep(1.5)
    check("K  CONTROL an answer nobody asked for raises no question",
          ("Mallory" in cl.text().replace('acct_ask 123456 "Mallory"', ""), who()),
          (False, SIDS[1]))
    n = cl.text().count("sign in at")
    send("acct_go ABCDEFGHJK")              # ...and with no box at all
    send("acct_start " + "ab" * 16)
    time.sleep(1.0)
    check("K  CONTROL a start's answers, unasked, show no address",
          cl.text().count("sign in at") - n, 0)
    called = [p.name for p in sorted((ROOT / "src").rglob("*.qc"))
              if "CSQC_InputEvent(" in p.read_text(errors="replace")]
    check("K  no .qc file calls CSQC_InputEvent: only the engine says a key was real",
          called, [])

    time.sleep(3.2)
    opened = box("ABCDEFGHJK")
    check("F  an unknown code is refused",
          (opened, bool(cl.wait("not valid or has expired"))), (True, True))
    keys.press("back")

    time.sleep(3.2)
    n = sv.text().count("asked for client")
    hints = cl.text().count("a code is typed into the box")
    opens("link " + codes[2])
    keys.press("esc")
    opens('link "ABCDE;echo P615-INJECTED;FGHJK"')
    keys.press("esc")
    time.sleep(1.5)
    hint = cl.text().count("a code is typed into the box") - hints == 2
    check("G  a code given on the console is not sent, and nothing in one runs",
          (hint, sv.text().count("asked for client") - n,
           "P615-INJECTED" in cl.text().replace("ABCDE;echo P615-INJECTED;FGHJK", ""),
           "P615-INJECTED" in sv.text(),
           rows("SELECT used_at, claim FROM linkcodes WHERE code = '%s'" % c3)),
          (True, 0, False, False, [(0, "")]))

    # M: game-code commands that pasted their argument into a console line.  A
    # server can type these, and game code's own lines run where rec_sign obeys.
    send('zone_goto "1;echo P617-LAUNDERED-A"')
    send('ghost speed "1;echo P617-LAUNDERED-B"')
    time.sleep(2.0)
    seen = cl.text().replace('"1;echo P617-LAUNDERED', "")
    check("M  an argument to zone_goto or ghost speed is a number, not more commands",
          ("P617-LAUNDERED-A" in seen, "P617-LAUNDERED-B" in seen), (False, False))

    time.sleep(3.2)
    send("cmd link " + digest("ftesurf-code ", c3))
    send("rec_sign %s -3 - 0" % ("0" * 32))
    check("H  CONTROL the right code under a signature for the wrong nonce",
          (bool(sv.wait(asked % "proof")),
           rows("SELECT used_at, claim FROM linkcodes WHERE code = '%s'" % c3)),
          (True, [(0, "")]))

    # J by hand at the console: the player's own console may still sign, and
    # that is what lets this arm put run-shaped receipts between the two.
    time.sleep(3.2)
    before = sv.text().count("timer: receipt refused")
    send("cmd link " + digest("ftesurf-code ", c3))
    send("rec_sign %s 7 - 0" % ("1" * 32))
    send("rec_sign %s 0 - 0" % ("2" * 32))
    passed = sv.count("timer: receipt refused", before + 2) - before
    send("rec_sign %s -3 - 0" % digest("ftesurf-link ", c3))
    got = bool(sv.wait(asked % "confirm"))
    check("J  both run-shaped receipts reached the run's handler while a link was owed",
          (passed, got, rows("SELECT used_at, length(claim) FROM linkcodes WHERE code = '%s'" % c3)),
          (2, True, [(0, 64)]))
    time.sleep(3.2)
    box(c3)
    up = bool(cl.wait(r"link this game to Third\? Enter to link"))
    time.sleep(0.8)
    keys.press("enter")
    check("J  ...and the link it began is finished in the box",
          (up, bool(cl.wait("now linked to Third")), who()), (True, True, SIDS[2]))
    keys.press("back")

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
    check("...the three codes it spent are marked with that key (the first was the game's own);"
          " the typed first and the fourth are not",
          ([used.get(c) for c in (started, c2, c3)] == [pub16[0][0]] * 3 if pub16 else None,
           used.get(c1), used.get(c4)), (True, "superseded", ""))


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
        a.hport = hport
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
            # Keys reach game code only while nothing else has the keyboard, and
            # a client nobody is sitting at still has its menu up from boot.
            send("closemenu")
            link_arm(a, send, Keys(client.pid), cl, sv, db, gport, codes)
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
