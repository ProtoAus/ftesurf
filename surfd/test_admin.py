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

import hashlib
import importlib
import logging
import os
import shutil
import sqlite3
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


def js_parses(template):
    """True/False from `node --check` on a template's inline scripts, or None
    when node is not on PATH -- reported as a skip, never as a pass."""
    import re
    import subprocess
    node = shutil.which("node")
    if not node:
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "templates", template), encoding="utf-8") as f:
        src = f.read()
    js = "\n".join(re.sub(r"\{\{.*?\}\}", "null", re.sub(r"\{%.*?%\}", "", b))
                   for b in re.findall(r"<script>(.*?)</script>", src, re.S))
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(js)
        return subprocess.run([node, "--check", path], capture_output=True).returncode == 0
    finally:
        os.unlink(path)


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
    # Never the live run tree or map library (their defaults are /srv paths).
    os.makedirs(os.path.join(home, "runs"))
    os.environ["SURFD_RUNS"] = os.path.join(home, "runs")
    os.environ["SURFD_MAPS"] = os.path.join(home, "maps")
    os.environ["SURFD_ZONES"] = os.path.join(home, "zones")
    os.environ["SURFD_LOBBY_CFGS"] = os.path.join(home, "lobbycfg")
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


# ---- run review (Patch 359) -------------------------------------------------

class FakeClock(object):
    """One clock for surfd AND admin: a review is current only at or after
    replays.submitted, so the two modules must agree on what "now" is."""

    def __init__(self, now=1800000000.0):
        self.now = float(now)

    def time(self):
        return self.now

    def monotonic(self):
        return self.now


# Three samples (t -0.01, 0, 0.01), a cp, and a trailer that agrees.
REC = ("FTESURF-REC 9\nmap surf_kitsune\ntickrate 0.01\nmovetickrate 0.01\n"
       "instart 100 100\npmpin trisoup=1 rotboxes=1 portalcsg=1\nbegin\n"
       "-0.0100 0.00 0.00 0.00 0.00 0.00 0.00 0.0 16.0 0\n"
       "0.0000 1.00 0.00 0.00 100.00 0.00 0.00 0.0 16.0 0\n"
       "0.0100 2.00 0.00 0.00 300.00 400.00 0.00 0.0 16.0 0\n"
       "cp 1 1\nend 2 3 1 1\n")

REVIEW_RULES = {"/admin/runs", "/admin/run/<int:rid>", "/admin/api/runs",
                "/admin/api/run/<int:rid>", "/admin/api/run/<int:rid>/path",
                "/admin/api/review"}
ROW_KEYS = {"id", "map", "map_dir", "track", "leg", "legdir", "tier", "style",
            "name", "ms", "submitted", "checked", "recheck_at", "verdict",
            "error", "pending", "decision", "public", "standing"}


def rec_leaf(ticks, player):
    return "%07d_%s_run.rec" % (ticks, hashlib.sha256(player.encode()).hexdigest()[:8])


def review_section(pw_hash, pw):
    print("\n--- 9. run review --")
    clock = FakeClock()
    m = fresh(SURFD_ADMIN_HASH=pw_hash, SURFD_ADMIN_SECRET="s" * 48,
              SURFD_ADMIN_INSECURE_COOKIE="1")
    adm = sys.modules["admin"]
    m.time = clock
    adm.time = clock
    sys.modules.pop("sweep", None)
    sweep = importlib.import_module("sweep")
    c = m.app.test_client()

    def submit(player, ticks, write=False):
        # A DISTINCT runid PER CALL, because every real one is distinct:
        # SV_RecOpen stamps wallclock+slot.  The ties below mean "a second run
        # that happened to tie", i.e. new evidence, and since 2026-09-20 that is
        # what decides whether `submitted` moves and lapses the verdict under
        # it -- an identical re-post is a no-op it must not be able to ride.
        leaf = rec_leaf(ticks, player)
        j = m.app.test_client().post("/api/run", data={
            "key": "testkey", "map": "surf_kitsune", "track": "0", "leg": "0",
            "player": player, "name": player.capitalize(), "ticks": str(ticks),
            "tickrate": "100", "flags": "0", "node": "p27510", "rec": leaf,
            "runid": "r-%s-%d" % (player, clock.now)},
            environ_base={"REMOTE_ADDR": "127.0.0.1"}).get_json()
        path = os.path.join(m.RUNS_DIR, "surf_kitsune", "main", leaf)
        if write:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", newline="\n") as fh:
                fh.write(REC)
        clock.now += 1
        return j["rep"], path

    def record(rid, verdict, at, reason="r"):
        conn = m.connect()
        try:
            with conn:
                sweep.record(conn, rid, verdict, reason, -1, "e" * 32, "p" * 64, at)
        finally:
            conn.close()

    def sql(query, args=()):
        conn = sqlite3.connect(m.DB_PATH)
        try:
            return conn.execute(query, args).fetchall()
        finally:
            conn.close()

    def snapshot():
        return (sql("SELECT * FROM reviews ORDER BY replay_id"),
                sql("SELECT * FROM runs ORDER BY player"),
                sql("SELECT id, checked, recheck_at FROM replays ORDER BY id"))

    def listing(**args):
        r = c.get("/admin/api/runs", query_string=args)
        return r.get_json() if r.status_code == 200 else {"code": r.status_code}

    def ids(**args):
        return [x["id"] for x in listing(**args)["rows"]]

    def detail(rid):
        return c.get("/admin/api/run/%d" % rid).get_json()

    def board():
        b = m.app.test_client().get("/api/board", query_string={
            "map": "surf_kitsune", "limit": "200"}).get_json()
        return {x["player"]: x for x in b["rows"]}

    def pending():
        conn = m.connect()
        try:
            return [r["id"] for r in sweep.pending(conn, 100)]
        finally:
            conn.close()

    # -- 9a. logged out, every /admin rule but login refuses -----------------
    rules = sorted((r.rule, meth) for r in m.app.url_map.iter_rules()
                   if r.rule.startswith("/admin")
                   and r.endpoint not in ("admin.login_form", "admin.login")
                   for meth in r.methods - {"HEAD", "OPTIONS"})
    wrong = []
    for rule, meth in rules:
        resp = c.open(rule.replace("<int:rid>", "1"), method=meth)
        got = resp.status_code
        if got == 302 and resp.headers.get("Location", "").endswith("/admin/login"):
            got = "login"
        if got != (401 if "/api/" in rule else "login"):
            wrong.append((meth, rule, resp.status_code))
    check("logged out: every /admin rule is 401 (api) or a login redirect",
          wrong, [])
    check("control: that sweep covered every review route",
          sorted(REVIEW_RULES - {r for r, _ in rules}), [])
    check("control: ...and the fleet controls",
          ("/admin/api/map", "POST") in rules, True)

    # -- seed: eve 50 s then 40 s, a HOLD, a PASS, three ERRORs ---------------
    slow, _ = submit("eve", 5000)
    fast, _ = submit("eve", 4000)
    hal, hal_path = submit("hal", 4500, write=True)
    pat, _ = submit("pat", 4600)
    err, _ = submit("err", 4700)
    T = int(clock.now)
    record(hal, "HOLD", T, reason="SENTINEL-REASON")
    record(pat, "PASS", T)
    for i in range(3):
        record(err, "ERROR", T + i, reason="no VERIFY line")

    check("login", login(c, pw).status_code, 302)
    page = c.get("/admin/runs")
    check("/admin/runs renders", page.status_code, 200)
    csrf = page.get_data(as_text=True).split('name="csrf" value="')[1].split('"')[0]
    check("the fleet page links to Runs",
          'href="/admin/runs"' in c.get("/admin/").get_data(as_text=True), True)
    rp = c.get("/admin/run/%d" % hal)
    check("/admin/run/<rid> renders with its rid",
          (rp.status_code, "const RID = %d;" % hal in rp.get_data(as_text=True)),
          (200, True))
    check("...under the admin CSP (no img-src)",
          rp.headers.get("Content-Security-Policy", "").startswith("default-src 'none'")
          and "img-src" not in rp.headers.get("Content-Security-Policy", ""), True)

    # -- 9b. the list ---------------------------------------------------------
    j = listing()
    check("the default view is the queue: the HOLD with no review",
          [x["id"] for x in j["rows"]], [hal])
    check("counts per state",
          j["counts"], {"queue": 1, "hold": 1, "pass": 1, "refuse": 0, "error": 1,
                        "pending": 2, "approved": 0, "rejected": 0, "all": 5})
    check("row keys", set(j["rows"][0]), ROW_KEYS)
    check("the HOLD row", {k: j["rows"][0][k] for k in
                           ("verdict", "decision", "public", "standing", "legdir")},
          {"verdict": "HOLD", "decision": None, "public": "plain",
           "standing": True, "legdir": "main"})
    check("all: queue first, then standing by newest, then the rest",
          ids(state="all"), [hal, err, pat, fast, slow])
    check("pending = no terminal verdict, under the ERROR cap", sorted(ids(state="pending")),
          sorted([slow, fast]))
    check("...exactly what sweep.pending() picks", sorted(ids(state="pending")),
          sorted(pending()))
    check("control: err (3 ERRORs, checked 0) is listed under error",
          ids(state="error"), [err])
    check("search by name", sorted(ids(state="all", q="EVE")), sorted([slow, fast]))
    check("search by replay id", ids(state="all", q=str(pat)), [pat])
    check("counts follow the search", listing(state="all", q="eve")["counts"]["all"], 2)
    check("a % in the search is literal", listing(state="all", q="%")["counts"]["all"], 0)
    for label, args in (("an unknown state", {"state": "bogus"}),
                        ("a negative offset", {"offset": "-1"}),
                        ("a word for an offset", {"offset": "x"})):
        check("%s -> 400" % label, listing(**args), {"code": 400})

    # -- 9c. CSRF and Sec-Fetch-Site ------------------------------------------
    before = snapshot()
    r = c.post("/admin/api/review", data={"rid": str(fast), "action": "reject"})
    check("review without a CSRF token -> 400", r.status_code, 400)
    r = c.post("/admin/api/review",
               data={"rid": str(fast), "action": "reject", "csrf": "forged"})
    check("review with a wrong token -> 400", r.status_code, 400)
    for site in ("cross-site", "same-site", "none"):
        r = c.post("/admin/api/review", headers={"Sec-Fetch-Site": site},
                   data={"rid": str(fast), "action": "reject", "csrf": csrf})
        check("Sec-Fetch-Site %s with a valid token -> 403" % site, r.status_code, 403)
    check("...and none of those changed the database", snapshot(), before)
    r = c.post("/admin/api/map", headers={"Sec-Fetch-Site": "cross-site"},
               data={"tier": "1", "map": "surf_kitsune", "csrf": csrf})
    check("the fleet controls get the same check", r.status_code, 403)

    def act(rid, action, note="", site="same-origin", submitted=None):
        if submitted is None:                    # what a fresh page load shows
            submitted = sql("SELECT submitted FROM replays WHERE id = ?", (rid,))[0][0]
        r = c.post("/admin/api/review",
                   headers={"Sec-Fetch-Site": site} if site else {},
                   data={"rid": str(rid), "action": action, "note": note,
                         "submitted": str(submitted), "csrf": csrf})
        j = r.get_json() or {}
        j["code"] = r.status_code
        return j

    # -- 9d. every action, end to end -----------------------------------------
    check("control: eve stands on her 40 s replay",
          (board()["eve"]["ms"], board()["eve"]["rep"]), (40000, fast))
    clock.now += 10
    j = act(fast, "reject", note="spliced")
    check("reject (same-origin) -> ok, and the board row moved",
          (j.get("ok"), "board row moved" in j.get("message", "")), (True, True))
    check("...the board shows her 50 s replay",
          (board()["eve"]["ms"], board()["eve"]["rep"]), (50000, slow))
    check("...the replay reads hidden", detail(fast)["public"], "hidden")
    check("...and lists under rejected", ids(state="rejected"), [fast])
    clock.now += 1
    j = act(fast, "approve", site=None)
    check("approve it (no Sec-Fetch-Site header) -> 40 s again, verified",
          (j.get("ok"), board()["eve"]["ms"], board()["eve"]["ver"]), (True, 40000, 1))
    clock.now += 1
    j = act(fast, "clear")
    d = detail(fast)
    check("clear -> kept, no review, no badge (it has no verdict)",
          (j.get("ok"), "board row kept" in j.get("message", ""), d["review"],
           d["public"], board()["eve"]["ver"]), (True, True, None, "plain", 0))
    j = act(hal, "approve", note="looked fine")
    check("approving the HOLD empties the queue",
          (j.get("ok"), listing()["counts"]["queue"],
           listing()["counts"]["approved"]), (True, 0, 1))
    check("...and hal's row is verified", board()["hal"]["ver"], 1)

    check("control: three ERRORs keep err out of pending()", err in pending(), False)
    check("control: pat has a PASS, not pending", pat in pending(), False)
    clock.now += 5
    j = act(err, "recheck")
    check("recheck -> ok", j.get("ok"), True)
    check("...checked 0 and recheck_at now",
          sql("SELECT checked, recheck_at FROM replays WHERE id = ?", (err,)),
          [(0, int(clock.now))])
    check("...and pending() offers it again, first", pending()[:1], [err])
    check("...and so does the pending list", err in ids(state="pending"), True)
    check("control: pat was not re-checked", pat in pending(), False)
    for i in range(3):
        record(err, "ERROR", int(clock.now) + 1 + i)
    check("three ERRORs after the recheck spend it again", err in pending(), False)
    check("...and it leaves the pending list", err in ids(state="pending"), False)

    # -- 9e. bad inputs and the note ------------------------------------------
    before = snapshot()
    shown = str(sql("SELECT submitted FROM replays WHERE id = ?", (pat,))[0][0])
    for label, fields in (("no rid", {"action": "approve"}),
                          ("a word for a rid", {"rid": "x", "action": "approve"}),
                          ("a negative rid", {"rid": "-1", "action": "approve"}),
                          ("an unknown replay", {"rid": "999999", "action": "approve"}),
                          ("an unknown action", {"rid": str(pat), "action": "delete"}),
                          ("no action", {"rid": str(pat)}),
                          ("no submitted", {"rid": str(pat), "action": "approve",
                                            "submitted": None}),
                          ("a word for submitted", {"rid": str(pat), "action": "approve",
                                                    "submitted": "x"})):
        fields.setdefault("submitted", shown)
        if fields["submitted"] is None:
            del fields["submitted"]
        fields["csrf"] = csrf
        r = c.post("/admin/api/review", data=fields)
        check("%s -> 400" % label, (r.status_code, (r.get_json() or {}).get("ok")),
              (400, False))
    check("...and none of them changed the database", snapshot(), before)
    raw = "line1\nline2\x00\x1b[31m\u202e" + "x" * 300
    check("a long, dirty note is accepted", act(pat, "approve", note=raw).get("ok"), True)
    note = sql("SELECT note FROM reviews WHERE replay_id = ?", (pat,))[0][0]
    check("...stored cleaned and capped at %d" % adm.NOTE_MAX,
          note, ("line1 line2 [31m " + "x" * 300)[:adm.NOTE_MAX])

    # -- 9f. the detail JSON --------------------------------------------------
    d = detail(hal)
    check("detail: the full reason", [v["reason"] for v in d["verdicts"]],
          ["SENTINEL-REASON"])
    check("...the download link", d["download"], "/api/replay/%d" % hal)
    check("...the watch commands", d["watch"],
          ["map surf_kitsune", "board_replay %d" % hal,
           "replay online %d" % hal])
    check("...the file, standing and review",
          (d["run"]["file"], d["standing"], d["review"]["note"], d["public"]),
          (True, {"on_board": True, "rank": 2, "of": 4}, "looked fine", "verified"))
    check("control: the public board never carries the reason",
          "SENTINEL" in m.app.test_client().get(
              "/api/board?map=surf_kitsune").get_data(as_text=True), False)
    check("an unknown replay -> 404",
          c.get("/admin/api/run/999999").status_code, 404)
    shown = detail(pat)["run"]["submitted"]       # the page loads...
    clock.now += 60
    submit("pat", 4600)                           # exact tie: same row, new bytes
    d = detail(pat)
    check("after an exact-tie resubmission the old PASS is not current",
          [v["current"] for v in d["verdicts"]], [False])
    check("...the approval lapses too", (d["review"]["current"], d["public"]),
          (False, "plain"))
    row = [x for x in listing(state="all")["rows"] if x["id"] == pat][0]
    check("...and the list agrees", (row["verdict"], row["decision"], row["public"]),
          (None, None, "plain"))
    before = snapshot()
    j = act(pat, "approve", submitted=shown)      # ...and is clicked after the tie
    check("approve from the pre-tie page -> 409, reload",
          (j["code"], j.get("error")), (409, "the run changed -- reload"))
    check("...and it changed nothing", snapshot(), before)
    j = act(pat, "approve")
    check("control: from a reloaded page -> ok, verified",
          (j["code"], detail(pat)["public"]), (200, "verified"))
    submit("pat", 4600)                           # a tie in the approval's own second
    check("a tie in the same second as the approval lapses it",
          (detail(pat)["review"]["current"], board()["pat"]["ver"]), (False, 0))

    # ERROR is not a verdict: it neither grants nor revokes the badge.
    ann, _ = submit("ann", 4900)
    hol, _ = submit("hol", 4950)
    t = int(clock.now)
    for rid, first in ((ann, "PASS"), (hol, "HOLD")):
        record(rid, first, t)
        record(rid, "ERROR", t + 1, reason="no VERIFY line")
    rows = {x["id"]: x for x in listing(state="all")["rows"]}
    check("PASS then ERROR: detail, list and board all read verified",
          (detail(ann)["public"], rows[ann]["public"], rows[ann]["verdict"],
           rows[ann]["error"], board()["ann"]["ver"]),
          ("verified", "verified", "PASS", True, 1))
    check("...and it lists under both pass and error",
          (ann in ids(state="pass"), ann in ids(state="error")), (True, True))
    check("HOLD then ERROR: plain, ver 0, and still in the queue",
          (detail(hol)["public"], board()["hol"]["ver"], hol in ids()),
          ("plain", 0, True))

    # -- 9g. the path route: replay_file() first, recplot only on a good path -
    calls = []
    real_parse = adm.recplot.parse
    adm.recplot.parse = lambda path, *a, **kw: (calls.append(path),
                                                real_parse(path, *a, **kw))[1]
    try:
        r = c.get("/admin/api/run/%d/path" % hal)
        p = r.get_json()
        check("path: 200, parsed", (r.status_code, p["ok"], p["n"],
                                    p["stats"]["max_speed"]), (200, True, 3, 500.0))
        check("...with the pin's trace cvars and the cp",
              ("trisoup=1" in p["head"]["pmpin"], [(k["k"], k["n"]) for k in p["marks"]]),
              (True, [("cp", 1)]))
        check("control: recplot.parse ran once, on the real file",
              calls, [os.path.realpath(hal_path)])

        outside = os.path.join(os.path.dirname(m.RUNS_DIR), "outside.rec")
        with open(outside, "w") as fh:
            fh.write(REC)
        bad_leaf, _ = submit("t1", 4801)
        bad_dir, _ = submit("t2", 4802)
        linked, link_path = submit("t3", 4803)
        missing, _ = submit("t4", 4804)
        conn = sqlite3.connect(m.DB_PATH)
        with conn:
            conn.execute("UPDATE replays SET leaf = '../../../outside.rec' WHERE id = ?",
                         (bad_leaf,))
            conn.execute("UPDATE replays SET map_dir = 'surf_kitsune/../..' WHERE id = ?",
                         (bad_dir,))
        conn.close()
        os.makedirs(os.path.dirname(link_path), exist_ok=True)
        os.symlink(outside, link_path)
        del calls[:]
        for label, rid in (("a bad leaf", bad_leaf), ("a map_dir with a slash", bad_dir),
                           ("a symlink out of the run tree", linked),
                           ("a missing file", missing), ("an unknown replay", 999999)):
            r = c.get("/admin/api/run/%d/path" % rid)
            check("path: %s -> 404" % label, (r.status_code, r.get_json()["ok"]),
                  (404, False))
        check("...and recplot.parse was never called", calls, [])
        check("control: the symlink target itself parses",
              real_parse(outside)["ok"], True)
    finally:
        adm.recplot.parse = real_parse

    # -- 9g2. the receipt panel ----------------------------------------------
    #
    # THE FIRST ARM IS THAT THE PAGE STILL WORKS WITHOUT THE TABLES.  sweep.py
    # creates them the first time it runs, so on any box there is a window where
    # the admin is newer than the database -- and the handler turns a
    # sqlite3.Error into a 500, which would take the whole review page down over
    # a panel that is not there yet.
    rid_r, _p = submit("rcpt", 700)
    conn = m.connect()
    try:
        with conn:
            conn.execute("DROP TABLE IF EXISTS receipts")
            conn.execute("DROP TABLE IF EXISTS pubkeys")
    finally:
        conn.close()
    d = detail(rid_r)
    check("no receipts table: the review page still answers", d["ok"], True)
    check("...and says there is no receipt", d["receipt"], None)

    conn = m.connect()
    try:
        with conn:
            conn.executescript(m.RECEIPTS_SQL)
    finally:
        conn.close()
    check("tables back, still no row for this run", detail(rid_r)["receipt"], None)

    runid = sql("SELECT runid FROM replays WHERE id = ?", (rid_r,))[0][0]
    check("control: the replay row carries a runid to join on", bool(runid), True)
    conn = m.connect()
    try:
        with conn:
            conn.execute("INSERT INTO receipts (runid, map, pub, verdict, angles,"
                         " reason, at) VALUES (?, 'surf_kitsune', ?, 'VALID',"
                         " 'OK', '', 100)", (runid, "ab" * 32))
            for who, n in (("rcpt", 3), ("someone_else", 1)):
                conn.execute("INSERT INTO pubkeys (pub, player, first_at, last_at,"
                             " runs) VALUES (?, ?, 1, 2, ?)", ("ab" * 32, who, n))
            conn.execute("INSERT INTO pubkeys (pub, player, first_at, last_at,"
                         " runs) VALUES (?, 'rcpt', 1, 2, 1)", ("cd" * 32,))
    finally:
        conn.close()
    d = detail(rid_r)["receipt"]
    check("the verdict reaches the page", (d["verdict"], d["angles"]), ("VALID", "OK"))
    check("both names this key has signed for, with their counts",
          sorted((p["player"], p["runs"]) for p in d["players"]),
          [("rcpt", 3), ("someone_else", 1)])
    check("and both keys this player has signed with",
          sorted(k["pub"][:2] for k in d["keys"]), ["ab", "cd"])
    # THE PAGE ITSELF, not only the JSON behind it: a payload nobody renders is
    # the same defect one layer down from the table nobody read.
    page = c.get("/admin/run/%d" % rid_r)
    body = page.get_data(as_text=True)
    check("the run page renders", page.status_code, 200)
    check("...and carries the receipt card", 'id="rcptcard"' in body, True)
    # AND ITS SCRIPT PARSES.  f19d477 redeclared `const dl` in renderRun; the
    # check above passed while the browser discarded the page's whole script.
    for name in ("admin.html", "admin_runs.html", "admin_run.html"):
        ok = js_parses(name)
        if ok is None:
            print("skip %-62s %s" % ("the %s script parses" % name, "no node on PATH"))
        else:
            check("the %s script parses" % name, ok, True)

    # -- 9h. runs=None registers no review routes -----------------------------
    import flask
    app = flask.Flask("standalone")
    bp = adm.build_blueprint(app, logging.getLogger("test_admin"), m.connect, 30)
    app.register_blueprint(bp)
    got = {r.rule for r in app.url_map.iter_rules()}
    check("runs=None: none of the review routes", sorted(got & REVIEW_RULES), [])
    check("control: the blueprint is there", "/admin/login" in got, True)
    sa = app.test_client()
    check("control: standalone login works", login(sa, pw).status_code, 302)
    check("...and its fleet page has no Runs link",
          "/admin/runs" in sa.get("/admin/").get_data(as_text=True), False)

    # -- 9i. panel off --------------------------------------------------------
    m = fresh()
    c = m.app.test_client()
    check("panel off: /admin/runs is 404", c.get("/admin/runs").status_code, 404)
    check("panel off: /admin/api/runs is 404", c.get("/admin/api/runs").status_code, 404)
    check("panel off: /board/ still works", c.get("/board/").status_code, 200)


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

    # The fleet comes from cfg/lobby/lobby<N>.cfg, numerically ordered.
    cfgdir = tempfile.mkdtemp(prefix="surfd-lobbycfg-")
    for name, text in (("lobby1.cfg", "// set sv_port 1\nset sv_port     27510\n"),
                       ("lobby12.cfg", "set  sv_port 27620 // twelve\n"),
                       ("lobby2.cfg", "set sv_port 27520\nset sv_port 9\n"),
                       ("lobby.cfg", "set sv_port 1\n"),          # shared, not a lobby
                       ("lobby7.cfg", "set hostname x\n"),         # no port: skipped
                       ("mode_bhop.cfg", "set sv_port 2\n")):
        with open(os.path.join(cfgdir, name), "w") as fh:
            fh.write(text)
    check("lobbies are discovered from lobby<N>.cfg",
          admin.discover_lobbies(cfgdir), "1:27510,2:27520,12:27620")
    check("a missing cfg dir discovers nothing",
          admin.discover_lobbies(os.path.join(cfgdir, "nope")), "")
    check("the fallback is all 12 lobbies",
          [l["port"] for l in admin.parse_lobbies(admin.DEFAULT_LOBBIES)],
          list(range(27510, 27630, 10)))
    m = fresh(SURFD_ADMIN_HASH=admin.hash_password(PW, n=2 ** 10),
              SURFD_ADMIN_SECRET="s" * 48, SURFD_ADMIN_INSECURE_COOKIE="1",
              SURFD_LOBBY_CFGS=cfgdir)
    c = m.app.test_client()
    login(c, PW)
    page = c.get("/admin/").get_data(as_text=True)
    check("the panel's fleet is the discovered one",
          'const TIERS = ["1", "2", "12"];' in page, True)
    shutil.rmtree(cfgdir, ignore_errors=True)

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

    review_section(HASH, PW)

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
