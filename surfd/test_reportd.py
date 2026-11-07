#!/usr/bin/env python3
"""P1391 reportd: POST /api/report and /admin/reports, signed in by surfd's session.

    python -B test_reportd.py        (from surfd/)

Throwaway state dirs and Flask test clients; no network. One case imports surfd
to make a real /admin login cookie; reportd itself never imports surfd.
"""
import base64
import hashlib
import hmac
import importlib
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import reportd  # noqa: E402

SECRET = "s" * 48
ENV = "SURFD_KEY=not-for-reportd\nSURFD_ADMIN_HASH=scrypt$x\nSURFD_ADMIN_SECRET=%s\n" % SECRET
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + bytes(range(256)) * 8 + b"\xff\xd9"
PNG = b"\x89PNG\r\n\x1a\n" + bytes(64)
IP = "198.51.100.7"
TEMPS = []
TUNABLES = ("FLOOD_MAX", "HOUR_MAX", "DAY_MAX", "GLOBAL_DAY_MAX", "STORE_MAX_ROWS",
            "STORE_MAX_SHOT_BYTES", "MAX_SHOT")


class Clock(object):
    def __init__(self, now=1800000000.0):
        self.now = float(now)

    def time(self):
        return self.now


def make_app(env_text=ENV, environ=None, home=None, clock=None):
    home = home or tempfile.mkdtemp(prefix="reportd-test-")
    if home not in TEMPS:
        TEMPS.append(home)
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write(env_text)
    clock = clock or Clock()
    environ = {"SURFD_ADMIN_INSECURE_COOKIE": "1"} if environ is None else environ
    app = reportd.create_app(state=os.path.join(home, "state"),
                             env_file=os.path.join(home, "surfd.env"),
                             clock=clock.time, environ=environ)
    return app, home, clock


def tag(prefix, key=SECRET.encode()):
    return hmac.new(key, b"reportd-source\0" + prefix.encode(), hashlib.sha256).hexdigest()[:8]


def doc(**over):
    d = {"v": 1, "subject": "Frame drops on the second ramp", "category": "perf",
         "body": "line one\nline two\x07\r\n\tindented",
         "meta": {"map": "surf_kitsune", "server": "lobby 3", "player": "Lex",
                  "build": "0.1.41", "fps": 143.5, "origin": [1, 2, 3], "ok": True,
                  "utc": "2026-11-08T07:00:00Z"},
         "shot": base64.b64encode(JPEG).decode("ascii")}
    d.update(over)
    return d


def session_cookie(app, secret=None, **fields):
    if secret is not None:
        app = type("A", (), {"secret_key": secret, "config": app.config})()
    from flask.sessions import SecureCookieSessionInterface
    return SecureCookieSessionInterface().get_signing_serializer(app).dumps(fields)


def js_parses(template):
    """True/False from `node --check` over the template's inline script; None without node."""
    node = shutil.which("node")
    if not node:
        return None
    with open(os.path.join(HERE, "templates", template), encoding="utf-8") as f:
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


class Base(unittest.TestCase):
    def setUp(self):
        self.saved = {k: getattr(reportd, k) for k in TUNABLES}
        self.app, self.home, self.clock = make_app()
        self.state = os.path.join(self.home, "state")
        self.shots = os.path.join(self.state, "shots")
        self.c = self.app.test_client(use_cookies=False)
        self.csrf = "csrf-token-from-surfd"
        self.sess = self.cookie()

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(reportd, k, v)

    def cookie(self, **over):
        fields = {"ok": True, "born": self.clock.now, "seen": self.clock.now, "csrf": self.csrf}
        fields.update(over)
        return session_cookie(self.app, **fields)

    def post(self, d=None, ip=IP, raw=None, ctype="application/json", peer="127.0.0.1"):
        data = raw if raw is not None else json.dumps(doc() if d is None else d)
        headers = {"X-Real-IP": ip} if ip else {}
        return self.c.post("/api/report", data=data, content_type=ctype, headers=headers,
                           environ_base={"REMOTE_ADDR": peer})

    def get(self, path, cookie=True, **kw):
        headers = kw.pop("headers", {})
        if cookie:
            headers["Cookie"] = "surfd_admin=" + (self.sess if cookie is True else cookie)
        return self.c.get(path, headers=headers, **kw)

    def form(self, path, data, cookie=True, site=None):
        headers = {"Sec-Fetch-Site": site} if site else {}
        if cookie:
            headers["Cookie"] = "surfd_admin=" + (self.sess if cookie is True else cookie)
        return self.c.post(path, data=data, headers=headers)

    def sql(self, query, args=()):
        conn = sqlite3.connect(os.path.join(self.state, "reports.sqlite3"))
        try:
            return conn.execute(query, args).fetchall()
        finally:
            conn.close()

    def files(self):
        return sorted(os.listdir(self.shots))

    def refused(self, resp, code, error=None):
        self.assertEqual(resp.status_code, code, resp.get_data(as_text=True))
        j = resp.get_json()
        self.assertIs(j["ok"], False)
        if error is not None:
            self.assertEqual(j["error"], error)


class Submit(Base):
    def test_valid_report_is_stored_with_its_jpeg_and_no_address(self):
        r = self.post()
        self.assertEqual((r.status_code, r.get_json()), (200, {"ok": True, "id": 1}))
        row = self.sql("SELECT at, source, subject, category, body, meta, player, map, server,"
                       " build, shot, shot_bytes, seen FROM reports")
        self.assertEqual(len(row), 1)
        at, source, subject, cat, body, meta, player, mapname, server, build, shot, nbytes, seen = row[0]
        self.assertEqual((at, source, subject, cat),
                         (self.clock.now, tag("198.51.100.0/24"), doc()["subject"], "perf"))
        self.assertEqual(body, "line one\nline two\n\tindented")       # BEL and CR stripped
        self.assertEqual(json.loads(meta), doc()["meta"])
        self.assertEqual((player, mapname, server, build), ("Lex", "surf_kitsune", "lobby 3", "0.1.41"))
        self.assertEqual((shot, nbytes, seen), ("1.jpg", len(JPEG), 0))
        with open(os.path.join(self.shots, "1.jpg"), "rb") as fh:
            self.assertEqual(fh.read(), JPEG)
        self.assertNotIn("ip", [c[1] for c in self.sql("PRAGMA table_info(reports)")])
        stored = b""
        for suffix in ("", "-wal"):
            path = os.path.join(self.state, "reports.sqlite3" + suffix)
            if os.path.exists(path):
                with open(path, "rb") as fh:
                    stored += fh.read()
        self.assertIn(b"surf_kitsune", stored)                            # control: data is there
        self.assertNotIn(IP.encode(), stored)
        self.assertNotIn(b"198.51.100", stored)
        r = self.post(doc(shot="", category="", subject=" a\x00b\x1b[2J ",
                          meta={"pl\x01ayer": "x\x7f\u0085y\ud800", "map": 5, "build": True}),
                      ip="198.51.101.1")
        self.assertEqual(r.get_json(), {"ok": True, "id": 2})
        subject, meta, player, mapname, build, shot = self.sql(
            "SELECT subject, meta, player, map, build, shot FROM reports WHERE id = 2")[0]
        self.assertEqual((subject, json.loads(meta)), ("ab[2J", {"player": "xy", "map": 5, "build": True}))
        self.assertEqual((player, mapname, build, shot), ("xy", "5", "", ""))
        self.assertEqual(self.files(), ["1.jpg"])

    def test_bidi_and_zero_width_are_stripped(self):
        hidden = "\u061c\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff"
        r = self.post(doc(subject="evil" + hidden + "name", body="a" + hidden + "b",
                          meta={"k" + hidden: "v" + hidden}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.sql("SELECT subject, body, meta FROM reports"),
                         [("evilname", "ab", '{"k":"v"}')])
        self.assertEqual(reportd.clean("caf\u00e9 \u4e2d"), "caf\u00e9 \u4e2d")    # ordinary text kept

    def test_screenshot_must_be_a_jpeg(self):
        for i, (label, shot, error) in enumerate((
                ("png", base64.b64encode(PNG).decode(), "screenshot is not a JPEG"),
                ("no end marker", base64.b64encode(JPEG[:-2]).decode(), "screenshot is not a JPEG"),
                ("not base64", "@@@@", "screenshot is not base64"),
                ("not a string", 7, "bad screenshot"))):
            with self.subTest(label):
                self.refused(self.post(doc(shot=shot), ip="203.0.%d.1" % i), 400, error)
        reportd.MAX_SHOT = len(JPEG) - 1
        self.refused(self.post(doc(), ip="203.0.50.1"), 400, "screenshot too large")
        self.assertEqual((self.sql("SELECT COUNT(*) FROM reports"), self.files()), ([(0,)], []))
        reportd.MAX_SHOT = len(JPEG)                                       # control: at the cap
        self.assertEqual(self.post(doc(), ip="203.0.50.1").status_code, 200)
        wrapped = "\n".join(re.findall(".{1,76}", base64.b64encode(JPEG).decode()))
        self.assertEqual(self.post(doc(shot=wrapped), ip="203.0.51.1").status_code, 200)

    def test_field_shapes_and_sizes(self):
        pad = 8192 - len('{"pad":""}')
        cases = (
            ("subject 81", doc(subject="s" * 81), 400),
            ("subject 80", doc(subject="s" * 80), 200),
            ("subject blank", doc(subject=" \t\x01\u200b "), 400),
            ("subject missing", {k: v for k, v in doc().items() if k != "subject"}, 400),
            ("body 4001", doc(body="b" * 4001), 400),
            ("body 4000", doc(body="b" * 4000), 200),
            ("meta 8193 bytes", doc(meta={"pad": "m" * (pad + 1)}), 400),
            ("meta 8192 bytes", doc(meta={"pad": "m" * pad}), 200),
            ("meta 2-byte chars count as bytes", doc(meta={"pad": "\u00e9" * (pad // 2 + 1)}), 400),
            ("meta a list", doc(meta=[1, 2]), 400),
            ("meta too deep", doc(meta={"a": {"b": {"c": {"d": 1}}}}), 400),
            ("category unknown", doc(category="crash"), 400),
            ("category feature", doc(category="feature"), 200),
            ("version 2", doc(v=2), 400),
            ("version true", doc(v=True), 400),
        )
        for i, (label, d, code) in enumerate(cases):
            with self.subTest(label):
                self.assertEqual(self.post(d, ip="192.0.%d.1" % (i + 1)).status_code, code, label)
        base = json.dumps(doc())
        for i, (label, raw, ctype) in enumerate((
                ("not JSON", "{", "application/json"),
                ("an array", "[1]", "application/json"),
                ("NaN", base.replace("143.5", "NaN"), "application/json"),
                ("inf by overflow", base.replace("143.5", "1e400"), "application/json"),
                ("negative inf in a list", base.replace("[1, 2, 3]", "[1, -1e999, 3]"), "application/json"),
                ("form type", base, "text/plain"))):
            with self.subTest(label):
                self.refused(self.post(raw=raw, ctype=ctype, ip="192.0.%d.1" % (100 + i)), 400)
        self.assertEqual(self.post(raw=base.replace("143.5", "1e300"), ip="192.0.120.1").status_code, 200)
        # Brackets are counted before parsing: 2 MiB of [] peaks ~100 MB in json.loads.
        self.refused(self.post(raw="[" * 100000 + "]" * 100000, ip="192.0.121.1"), 400, "too complex")
        rest = json.dumps(doc(body=""))
        spare = reportd.MAX_BRACKETS - rest.count("[") - rest.count("{")
        self.assertEqual(self.post(doc(body="[" * spare), ip="192.0.122.1").status_code, 200)
        self.refused(self.post(doc(body="{" * (spare + 1)), ip="192.0.123.1"), 400, "too complex")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM reports"), [(6,)])
        self.assertTrue(all("Infinity" not in m for (m,) in self.sql("SELECT meta FROM reports")))

    def test_request_size(self):
        self.refused(self.post(raw=b"x" * (2 * 1024 * 1024 + 1)), 413, "request too large")
        self.refused(self.post(raw=b"x" * (2 * 1024 * 1024), ip="203.0.1.1"), 400, "bad JSON")
        # The largest shot, the largest meta and 4000 escaped characters still fit in 2m.
        big = b"\xff\xd8\xff" + os.urandom(reportd.MAX_SHOT - 5) + b"\xff\xd9"
        pad = 8192 - len('{"pad":""}')
        body = json.dumps(doc(shot=base64.b64encode(big).decode(), body="\u4e2d" * 4000,
                              meta={"pad": "m" * pad}))
        self.assertGreater(len(body), 2000000)
        self.assertLess(len(body), 2 * 1024 * 1024)
        self.assertEqual(self.post(raw=body, ip="203.0.2.1").status_code, 200)
        self.assertEqual(self.sql("SELECT shot_bytes FROM reports"), [(reportd.MAX_SHOT,)])

    def test_no_content_length_is_411_and_nothing_is_read(self):
        from werkzeug.test import EnvironBuilder, run_wsgi_app
        body = io.BytesIO(b"x" * (3 * 1024 * 1024))
        env = EnvironBuilder(path="/api/report", method="POST", input_stream=body,
                             content_type="application/json",
                             headers={"Transfer-Encoding": "chunked"}).get_environ()
        env.pop("CONTENT_LENGTH", None)
        env.update({"wsgi.input_terminated": True, "REMOTE_ADDR": "203.0.113.5"})
        out, status, _ = run_wsgi_app(self.app, env)
        self.assertEqual((status, json.loads(b"".join(out))),
                         ("411 LENGTH REQUIRED", {"ok": False, "error": "length required"}))
        self.assertEqual(body.tell(), 0)

    def test_length_checked_where_werkzeug_enforces_nothing(self):
        # Werkzeug 2.2 on the Pi: get_data()/stream enforce no MAX_CONTENT_LENGTH.
        self.app.config["MAX_CONTENT_LENGTH"] = None
        self.refused(self.post(raw=b"x" * (2 * 1024 * 1024 + 1)), 413, "request too large")
        self.refused(self.post(raw=b"x" * (2 * 1024 * 1024), ip="203.0.1.1"), 400, "bad JSON")

    def test_limits_come_before_the_body_and_the_file(self):
        for i in range(reportd.HOUR_MAX):
            self.assertEqual(self.post().status_code, 200)
            self.clock.now += 61
        with mock.patch.object(reportd.tempfile, "mkstemp", side_effect=AssertionError("wrote")):
            self.refused(self.post(raw="{"), 429, reportd.LIMITED)         # not 400: body unread
            self.refused(self.post(raw=b"x" * (3 * 1024 * 1024)), 429, reportd.LIMITED)
            reportd.STORE_MAX_ROWS = reportd.HOUR_MAX
            self.refused(self.post(ip="203.0.9.9"), 503, reportd.FULL)
        self.assertEqual(sorted(os.listdir(self.shots)), ["%d.jpg" % i for i in range(1, 7)])

    def test_rate_limits_key_on_the_network_prefix(self):
        for i in range(reportd.HOUR_MAX):
            self.assertEqual(self.post(ip="203.0.113.%d" % (i + 1)).status_code, 200, i)
            self.clock.now += 61
        self.refused(self.post(ip="203.0.113.200"), 429, "too many reports; try again later")
        self.refused(self.post(ip="::ffff:203.0.113.9"), 429)            # mapped counts as IPv4
        self.assertEqual(self.post(ip="203.0.114.1").status_code, 200)   # next /24
        for i in range(reportd.HOUR_MAX):
            self.clock.now += 61
            self.assertEqual(self.post(ip="2001:db8:1:2::%x" % (i + 1)).status_code, 200, i)
        self.clock.now += 61
        self.refused(self.post(ip="2001:db8:1:2:ffff::9"), 429)          # same /64
        self.refused(self.post(ip="2001:db8:1:ff::1"), 429)              # same /56
        self.assertEqual(self.post(ip="2001:db8:1:100::1").status_code, 200)   # next /56
        # The hour passes; the day cap then holds on its own.
        stored = reportd.HOUR_MAX
        while stored < reportd.DAY_MAX:
            self.clock.now += 3601 if stored % reportd.HOUR_MAX == 0 else 61
            self.assertEqual(self.post(ip="203.0.113.77").status_code, 200, stored)
            stored += 1
        self.clock.now += 3601
        self.refused(self.post(ip="203.0.113.78"), 429)
        self.clock.now += 86400
        self.assertEqual(self.post(ip="203.0.113.79").status_code, 200)

    def test_flood_guard_counts_refused_attempts(self):
        for i in range(reportd.FLOOD_MAX):
            self.refused(self.post(raw="{", ip="203.0.113.%d" % (i + 1)), 400, "bad JSON")
        self.refused(self.post(ip="203.0.113.99"), 429, reportd.LIMITED)
        self.assertEqual(self.post(ip="203.0.112.1").status_code, 200)
        self.clock.now += 61
        self.assertEqual(self.post(ip="203.0.113.99").status_code, 200)

    def test_global_day_cap(self):
        reportd.GLOBAL_DAY_MAX = 3
        for i in range(3):
            self.assertEqual(self.post(ip="203.0.%d.1" % (i + 1)).status_code, 200)
        self.refused(self.post(ip="203.0.99.1"), 429, reportd.LIMITED)
        self.clock.now += 86401
        self.assertEqual(self.post(ip="203.0.99.1").status_code, 200)

    def test_store_full_reads_a_running_total(self):
        reportd.STORE_MAX_ROWS = 2
        self.assertEqual(self.post(ip="203.0.1.1").status_code, 200)
        self.assertEqual(self.post(ip="203.0.2.1").status_code, 200)
        self.refused(self.post(ip="203.0.3.1"), 503, "report store full")
        reportd.STORE_MAX_ROWS = 5000
        reportd.STORE_MAX_SHOT_BYTES = 3 * len(JPEG) - 1
        self.refused(self.post(ip="203.0.4.1"), 503, "report store full")
        self.assertEqual(self.post(doc(shot=""), ip="203.0.5.1").status_code, 200)
        self.assertEqual(self.files(), ["1.jpg", "2.jpg"])
        self.assertEqual(self.sql("SELECT rows, shot_bytes FROM report_totals"), [(3, 2 * len(JPEG))])
        # The cap reads the total, not the rows: a wrong total is what it acts on...
        conn = sqlite3.connect(os.path.join(self.state, "reports.sqlite3"))
        with conn:
            conn.execute("UPDATE report_totals SET rows = 5000")
        conn.close()
        self.refused(self.post(doc(shot=""), ip="203.0.6.1"), 503)
        # ...and a restart sets it from the rows again.
        app, _, _ = make_app(home=self.home, clock=self.clock)
        self.assertEqual(self.sql("SELECT rows, shot_bytes FROM report_totals"), [(3, 2 * len(JPEG))])
        r = app.test_client().post("/api/report", data=json.dumps(doc(shot="")),
                                   content_type="application/json",
                                   headers={"X-Real-IP": "203.0.7.1"})
        self.assertEqual(r.status_code, 200)

    def test_startup_removes_only_old_temp_files(self):
        # A HUP starts a new worker while the old one may still be writing a .part.
        self.assertEqual(self.post().status_code, 200)
        for name, age in ((".shot-old.part", reportd.PART_AGE + 1), (".shot-new.part", 10)):
            path = os.path.join(self.shots, name)
            open(path, "wb").close()
            os.utime(path, (self.clock.now - age, self.clock.now - age))
        make_app(home=self.home, clock=self.clock)
        self.assertEqual(self.files(), [".shot-new.part", "1.jpg"])


class Schema(unittest.TestCase):
    def test_versioned_schema(self):
        app, home, _ = make_app()
        db = os.path.join(home, "state", "reports.sqlite3")
        conn = sqlite3.connect(db)
        try:
            self.assertEqual(conn.execute("SELECT version FROM report_schema").fetchall(), [(1,)])
            self.assertEqual(conn.execute("SELECT * FROM report_totals").fetchall(), [(1, 0, 0)])
            conn.execute("DROP TABLE report_schema")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaisesRegex(RuntimeError, "Unversioned report tables"):
            make_app(home=home)
        conn = sqlite3.connect(db)
        try:
            conn.executescript("CREATE TABLE report_schema (version INTEGER PRIMARY KEY);"
                               "INSERT INTO report_schema VALUES (2);")
        finally:
            conn.close()
        with self.assertRaisesRegex(RuntimeError, "Unsupported/incomplete report schema"):
            make_app(home=home)


class Admin(Base):
    def seed(self):
        rows = [("Zebra stripes on water", "render", "Bob", "surf_utopia", "srv b", "a", "10.0.1.1"),
                ("crash on load", "bug", "alice", "surf_kitsune", "srv a", "c", "10.0.2.1"),
                ("Add a map vote", "feature", "Carol", "bhop_arcane", "srv c", "b", "10.0.1.2"),
                ("no category here", "", "dave", "surf_mesa", "srv d", "d", "10.0.3.1")]
        for i, (subject, cat, player, mapname, server, build, ip) in enumerate(rows):
            meta = {"player": player, "map": mapname, "server": server, "build": build}
            shot = base64.b64encode(JPEG).decode() if i != 3 else ""
            r = self.post(doc(subject=subject, category=cat, meta=meta, shot=shot,
                              body="report %d needle\n" % i + "z" * 300), ip=ip)
            self.assertEqual(r.get_json(), {"ok": True, "id": i + 1})
            self.clock.now += 100
        self.sess = self.cookie()

    def listing(self, **args):
        r = self.get(reportd.PREFIX + "/api/list", query_string=args)
        return r.get_json() if r.status_code == 200 else {"code": r.status_code}

    def ids(self, **args):
        return [x["id"] for x in self.listing(**args)["rows"]]

    def test_logged_out_everything_refuses(self):
        self.seed()
        r = self.get("/admin/reports", cookie=False)
        self.assertEqual((r.status_code, r.headers["Location"].endswith("/admin/login")), (302, True))
        for path in ("/admin/reports/api/list", "/admin/reports/api/item/1"):
            self.assertEqual(self.get(path, cookie=False).status_code, 401, path)
        shot = self.get("/admin/reports/shot/1.jpg", cookie=False)
        self.assertEqual(shot.status_code, 302)
        self.assertNotIn(JPEG, shot.get_data())
        for path, data in (("/admin/reports/api/delete", {"ids": "1"}),
                           ("/admin/reports/api/delete_tag", {"tag": tag("10.0.1.0/24"), "upto": "9"})):
            self.assertEqual(self.form(path, dict(data, csrf=self.csrf), cookie=False).status_code, 401)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM reports"), [(4,)])

    def test_list_sort_filter_search(self):
        self.seed()
        j = self.listing()
        self.assertEqual([x["id"] for x in j["rows"]], [4, 3, 2, 1])   # newest first
        self.assertEqual(j["total"], 4)
        self.assertEqual(j["counts"], {"all": 4, "unseen": 4, "render": 1, "bug": 1,
                                       "feature": 1, "none": 1})
        row = j["rows"][0]
        self.assertNotIn("body", row)
        self.assertEqual((len(row["snippet"]), row["body_len"], row["source"]),
                         (160, 316, tag("10.0.3.0/24")))
        self.assertEqual(self.ids(sort="subject"), [3, 2, 4, 1])         # case-insensitive
        self.assertEqual(self.ids(sort="subject", dir="desc"), [1, 4, 2, 3])
        self.assertEqual(self.ids(sort="player"), [2, 1, 3, 4])
        self.assertEqual(self.ids(sort="map", dir="desc"), [1, 4, 2, 3])
        self.assertEqual(self.ids(sort="server"), [2, 1, 3, 4])
        self.assertEqual(self.ids(sort="build"), [1, 3, 2, 4])
        self.assertEqual(self.ids(sort="category"), [4, 2, 3, 1])
        self.assertEqual(self.ids(sort="at", dir="asc"), [1, 2, 3, 4])
        self.assertEqual(self.ids(category="bug"), [2])
        self.assertEqual(self.ids(category="none"), [4])
        self.assertEqual(self.ids(source=tag("10.0.1.0/24")), [3, 1])    # 10.0.1.1 and .2
        self.assertEqual(self.ids(q="KITSUNE"), [2])                     # map
        self.assertEqual(self.ids(q="ZEBRA"), [1])                       # subject
        self.assertEqual(self.ids(q="Carol"), [3])                       # player
        self.assertEqual(self.ids(q="report 3 needle"), [4])             # body
        self.assertEqual(self.ids(q="srv a"), [])                        # server is not searched
        self.assertEqual(self.listing(q="%")["total"], 0)                # literal
        self.assertEqual(self.listing(q="needle", category="render")["total"], 1)
        page = self.listing(limit="2", offset="1")
        self.assertEqual(([x["id"] for x in page["rows"]], page["total"]), ([3, 2], 4))
        for bad in ({"sort": "ip"}, {"dir": "up"}, {"category": "crash"}, {"limit": "201"},
                    {"limit": "0"}, {"offset": "-1"}, {"offset": "x"}, {"q": "q" * 101},
                    {"source": "10.0.1.1"}):
            self.assertEqual(self.listing(**bad), {"code": 400}, bad)

    def test_detail_marks_seen(self):
        self.seed()
        r = self.get("/admin/reports/api/item/2").get_json()
        self.assertIs(r["ok"], True)
        rep = r["report"]
        self.assertEqual((rep["id"], rep["seen"], rep["was_seen"], rep["has_shot"], rep["from_source"]),
                         (2, 1, 0, True, 1))
        self.assertEqual(rep["body"], "report 1 needle\n" + "z" * 300)
        self.assertEqual(rep["meta"], {"player": "alice", "map": "surf_kitsune",
                                       "server": "srv a", "build": "c"})
        self.assertEqual(self.get("/admin/reports/api/item/1").get_json()["report"]["from_source"], 2)
        self.assertEqual(self.sql("SELECT id FROM reports WHERE seen = 1 ORDER BY id"), [(1,), (2,)])
        self.assertEqual(self.get("/admin/reports/api/item/2").get_json()["report"]["was_seen"], 1)
        self.assertEqual(self.listing()["counts"]["unseen"], 2)
        self.assertEqual(self.get("/admin/reports/api/item/99").status_code, 404)

    def test_shot_served_only_when_logged_in(self):
        self.seed()
        r = self.get("/admin/reports/shot/1.jpg")
        self.addCleanup(r.close)
        self.assertEqual((r.status_code, r.mimetype, r.get_data()), (200, "image/jpeg", JPEG))
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        self.assertIn("img-src 'self'", r.headers["Content-Security-Policy"])
        self.assertEqual(self.get("/admin/reports/shot/4.jpg").status_code, 404)   # sent none
        self.assertEqual(self.get("/admin/reports/shot/99.jpg").status_code, 404)
        self.assertEqual(self.get("/admin/reports/shot/1.jpg", cookie=False).status_code, 302)

    def test_delete_needs_csrf_and_removes_rows_and_files(self):
        self.seed()
        path = "/admin/reports/api/delete"
        self.assertEqual(self.files(), ["1.jpg", "2.jpg", "3.jpg"])
        self.assertEqual(self.form(path, {"ids": "1,2"}).status_code, 400)
        self.assertEqual(self.form(path, {"ids": "1,2", "csrf": "wrong"}).status_code, 400)
        self.assertEqual(self.form(path, {"ids": "1,2", "csrf": self.csrf}, site="cross-site").status_code, 403)
        self.assertEqual(self.form(path, {"ids": "1,2", "csrf": self.csrf}, site="same-site").status_code, 403)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM reports"), [(4,)])
        os.unlink(os.path.join(self.shots, "2.jpg"))                     # a missing file is fine
        r = self.form(path, {"ids": "1, 2,4,99", "csrf": self.csrf}, site="same-origin")
        self.assertEqual((r.status_code, r.get_json()), (200, {"ok": True, "message": "deleted 3"}))
        self.assertEqual(self.sql("SELECT id FROM reports ORDER BY id"), [(3,)])
        self.assertEqual(self.files(), ["3.jpg"])
        self.assertEqual(self.sql("SELECT rows, shot_bytes FROM report_totals"), [(1, len(JPEG))])
        for bad in ("", "abc", "1,-2", ",".join(str(i) for i in range(1, 202))):
            self.assertEqual(self.form(path, {"ids": bad, "csrf": self.csrf}).status_code, 400, bad)
        # 4 was the highest id: AUTOINCREMENT does not hand it out again.
        self.assertEqual(self.post(ip="203.0.40.1").get_json()["id"], 5)

    def test_delete_every_report_from_one_source_up_to_what_was_loaded(self):
        self.seed()
        path, flood = "/admin/reports/api/delete_tag", tag("10.0.1.0/24")
        form = {"tag": flood, "upto": "4", "csrf": self.csrf}
        self.assertEqual(self.form(path, dict(form, csrf="")).status_code, 400)       # no CSRF
        self.assertEqual(self.form(path, form, site="cross-site").status_code, 403)
        for bad in ("", "10.0.1.0", "ABCDEF12", "abc"):
            self.assertEqual(self.form(path, dict(form, tag=bad)).status_code, 400, bad)
        for bad in ("", "0", "-1", "x", "1e3"):
            self.assertEqual(self.form(path, dict(form, upto=bad)).status_code, 400, bad)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM reports"), [(4,)])
        # A report from the same network arrives after the page loaded ids 1-4.
        self.assertEqual(self.post(doc(shot=""), ip="10.0.1.9").get_json()["id"], 5)
        r = self.form(path, form)
        self.assertEqual(r.get_json(), {"ok": True, "message": "deleted 2 (1 newer from this source kept)"})
        self.assertEqual(self.sql("SELECT id FROM reports ORDER BY id"), [(2,), (4,), (5,)])
        self.assertEqual(self.files(), ["2.jpg"])
        self.assertEqual(self.sql("SELECT rows, shot_bytes FROM report_totals"), [(3, len(JPEG))])
        r = self.form(path, dict(form, upto="5"))
        self.assertEqual(r.get_json(), {"ok": True, "message": "deleted 1"})

    def test_page_nav_and_csp(self):
        self.seed()
        r = self.get("/admin/reports")
        html = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 200)
        csp = r.headers["Content-Security-Policy"]
        self.assertTrue(csp.startswith("default-src 'none'") and "img-src 'self'" in csp)
        self.assertNotIn("img-src", self.get("/admin/reports/api/list").headers["Content-Security-Policy"])
        for link in ("/admin/", "/admin/maps", "/admin/runs", "/admin/accounts", "/admin/reports"):
            self.assertIn('href="%s"' % link, html)
        self.assertIn('value="%s"' % self.csrf, html)
        for name in ("X-Frame-Options", "Referrer-Policy", "X-Content-Type-Options"):
            self.assertIn(name, r.headers)
        self.assertIsNot(js_parses("reportd_reports.html"), False)


class Session(Base):
    def test_cookie_from_surfds_own_login_is_accepted(self):
        home = tempfile.mkdtemp(prefix="reportd-surfd-")
        TEMPS.append(home)
        with open(os.path.join(home, "surfd.env"), "w") as fh:
            fh.write("SURFD_KEY=testkey\n")
        saved = dict(os.environ)
        try:
            sys.modules.pop("admin", None)
            import admin
            pw = "report fixture password"
            os.environ.update(
                SURFD_HOME=home, SURFD_DB=os.path.join(home, "t.db"),
                SURFD_ENV=os.path.join(home, "surfd.env"), SURFD_RUNS=os.path.join(home, "runs"),
                SURFD_MAPS=os.path.join(home, "maps"), SURFD_ZONES=os.path.join(home, "z"),
                SURFD_ZONES_LOCAL=os.path.join(home, "zl"), SURFD_LOBBY_CFGS=os.path.join(home, "lc"),
                SURFD_RANKED_LINKED="0", SURFD_ADMIN_HASH=admin.hash_password(pw, n=2 ** 10),
                SURFD_ADMIN_SECRET=SECRET, SURFD_ADMIN_INSECURE_COOKIE="1")
            os.makedirs(os.path.join(home, "runs"))
            for name in ("surfd", "admin", "rcon"):
                sys.modules.pop(name, None)
            surfd = importlib.import_module("surfd")
            sc = surfd.app.test_client()
            page = sc.get("/admin/login").get_data(as_text=True)
            token = page.split('name="csrf" value="')[1].split('"')[0]
            login = sc.post("/admin/login", data={"csrf": token, "password": pw})
            self.assertEqual(login.status_code, 302)
            cookie = [h.split(";")[0].split("=", 1)[1] for h in login.headers.getlist("Set-Cookie")
                      if h.startswith("surfd_admin=")][-1]
            fleet = sc.get("/admin/").get_data(as_text=True)
            surfd_csrf = fleet.split('name="csrf" value="')[1].split('"')[0]
        finally:
            os.environ.clear()
            os.environ.update(saved)
            log = logging.getLogger("surfd")
            for handler in list(log.handlers):
                if isinstance(handler, logging.FileHandler):
                    handler.close()
                    log.removeHandler(handler)
        self.clock.now = __import__("time").time()                      # surfd stamped real time
        self.assertEqual(self.post().status_code, 200)
        r = self.get("/admin/reports", cookie=cookie)
        self.assertEqual(r.status_code, 200)
        self.assertIn('value="%s"' % surfd_csrf, r.get_data(as_text=True))   # one session, one token
        self.assertEqual(self.get("/admin/reports/api/list", cookie=cookie).get_json()["total"], 1)
        r = self.form("/admin/reports/api/delete", {"ids": "1", "csrf": surfd_csrf}, cookie=cookie)
        self.assertEqual(r.get_json(), {"ok": True, "message": "deleted 1"})

    def test_cookie_signed_with_another_secret_is_refused(self):
        forged = session_cookie(self.app, secret="t" * 48, ok=True, born=self.clock.now,
                                seen=self.clock.now, csrf=self.csrf)
        self.assertEqual(self.get("/admin/reports/api/list", cookie=forged).status_code, 401)
        self.assertEqual(self.get("/admin/reports", cookie=forged).status_code, 302)
        self.assertEqual(self.form("/admin/reports/api/delete", {"ids": "1", "csrf": self.csrf},
                                   cookie=forged).status_code, 401)
        self.assertEqual(self.get("/admin/reports/api/list").status_code, 200)       # control
        self.assertEqual(self.get("/admin/reports/api/list", cookie=self.cookie(ok=False)).status_code, 401)

    def test_idle_and_absolute_timeouts(self):
        now = self.clock.now
        idle = self.cookie(seen=now - reportd.SESSION_IDLE_MAX - 1)
        r = self.get("/admin/reports/api/list", cookie=idle)
        self.assertEqual(r.status_code, 401)
        self.assertTrue(any(h.startswith("surfd_admin=;") for h in r.headers.getlist("Set-Cookie")))
        self.assertEqual(self.get("/admin/reports/api/list",
                                  cookie=self.cookie(seen=now - reportd.SESSION_IDLE_MAX + 5)).status_code, 200)
        old = self.cookie(born=now - reportd.SESSION_ABS_MAX - 1)
        self.assertEqual(self.get("/admin/reports/api/list", cookie=old).status_code, 401)
        self.assertEqual(self.get("/admin/reports/api/list",
                                  cookie=self.cookie(born=now - reportd.SESSION_ABS_MAX + 5)).status_code, 200)
        self.assertEqual((reportd.SESSION_IDLE_MAX, reportd.SESSION_ABS_MAX), (1800, 43200))

    def test_no_admin_hash_or_short_secret_means_no_session(self):
        for env in ("SURFD_ADMIN_SECRET=%s\n" % SECRET,
                    "SURFD_ADMIN_HASH=scrypt$x\nSURFD_ADMIN_SECRET=short\n"):
            app, _, clock = make_app(env_text=env)
            cookie = session_cookie(self.app, ok=True, born=clock.now, seen=clock.now, csrf="x")
            r = app.test_client(use_cookies=False).get(
                "/admin/reports/api/list", headers={"Cookie": "surfd_admin=" + cookie})
            self.assertEqual(r.status_code, 401, env)

    def test_real_ip_only_from_our_proxy(self):
        def source_of(rid):
            return self.sql("SELECT source FROM reports WHERE id = ?", (rid,))[0][0]
        self.assertEqual(self.post(ip="198.51.100.1", peer="203.0.113.9").status_code, 200)
        self.assertEqual(source_of(1), tag("203.0.113.0/24"))
        self.assertEqual(self.post(ip="198.51.100.1").status_code, 200)
        self.assertEqual(source_of(2), tag("198.51.100.0/24"))
        self.assertEqual(self.post(ip="192.0.2.5", peer="::1").status_code, 200)
        self.assertEqual(source_of(3), tag("192.0.2.0/24"))
        self.assertEqual(self.post(ip="not-an-address").status_code, 200)
        self.assertEqual(source_of(4), tag("127.0.0.0/24"))
        app, home, _ = make_app(env_text=ENV + "SURFD_PROXIES=10.0.0.0/8\n")
        c = app.test_client()
        for peer in ("10.1.2.3", "127.0.0.1"):
            c.post("/api/report", data=json.dumps(doc()), content_type="application/json",
                   headers={"X-Real-IP": "198.51.100.1"}, environ_base={"REMOTE_ADDR": peer})
        conn = sqlite3.connect(os.path.join(home, "state", "reports.sqlite3"))
        got = [r[0] for r in conn.execute("SELECT source FROM reports ORDER BY id")]
        conn.close()
        self.assertEqual(got, [tag("198.51.100.0/24"), tag("127.0.0.0/24")])

    def test_source_tag_needs_the_secret(self):
        self.assertNotEqual(tag("198.51.100.0/24"), tag("198.51.100.0/24", b"t" * 48))
        self.assertNotEqual(tag("198.51.100.0/24"), hashlib.sha256(b"198.51.100.0/24").hexdigest()[:8])
        app, home, _ = make_app(env_text="")                              # no secret: a kept key
        key_path = os.path.join(home, "state", "source.key")
        with open(key_path, "rb") as fh:
            key = fh.read()
        self.assertEqual(len(key), 32)
        make_app(env_text="", home=home)
        with open(key_path, "rb") as fh:
            self.assertEqual(fh.read(), key)                              # stable across restarts
        app.test_client().post("/api/report", data=json.dumps(doc()), content_type="application/json",
                               headers={"X-Real-IP": IP})
        conn = sqlite3.connect(os.path.join(home, "state", "reports.sqlite3"))
        self.assertEqual(conn.execute("SELECT source FROM reports").fetchone()[0],
                         tag("198.51.100.0/24", key))
        conn.close()

    def test_rotated_secret_retires_old_cookies(self):
        old = self.sess
        self.assertEqual(self.get("/admin/reports/api/list", cookie=old).status_code, 200)
        self.assertEqual(self.post(ip="198.51.100.1").status_code, 200)
        new_secret = "n" * 48
        env = os.path.join(self.home, "surfd.env")
        with open(env, "w") as fh:
            fh.write("SURFD_ADMIN_HASH=scrypt$y\nSURFD_ADMIN_SECRET=%s\n" % new_secret)
        st = os.stat(env)
        os.utime(env, ns=(st.st_atime_ns, st.st_mtime_ns + 5 * 10 ** 9))
        # Stat'ed at most once a second: inside the second the old key still holds...
        self.assertEqual(self.get("/admin/reports/api/list", cookie=old).status_code, 200)
        self.clock.now += reportd.ENV_RECHECK
        # ...then the request that notices the change already uses the new key.
        self.assertEqual(self.get("/admin/reports/api/list", cookie=old).status_code, 401)
        fresh = session_cookie(self.app, secret=new_secret, ok=True, born=self.clock.now,
                               seen=self.clock.now, csrf=self.csrf)
        self.assertEqual(self.get("/admin/reports/api/list", cookie=fresh).status_code, 200)
        self.assertEqual(self.post(ip="198.51.100.2").status_code, 200)
        self.assertEqual([r[0] for r in self.sql("SELECT source FROM reports ORDER BY id")],
                         [tag("198.51.100.0/24"), tag("198.51.100.0/24", new_secret.encode())])
        # Removing the hash turns the pages off without a restart.
        with open(env, "w") as fh:
            fh.write("SURFD_ADMIN_SECRET=%s\n" % new_secret)
        os.utime(env, ns=(st.st_atime_ns, st.st_mtime_ns + 10 * 10 ** 9))
        self.clock.now += reportd.ENV_RECHECK
        self.assertEqual(self.get("/admin/reports/api/list", cookie=fresh).status_code, 401)

    def test_unit_and_nginx_name_port_8095(self):
        with open(os.path.join(HERE, "ftesurf-reportd.service")) as fh:
            unit = fh.read()
        with open(os.path.join(HERE, "report.nginx")) as fh:
            nginx = fh.read()
        self.assertIn("--bind 127.0.0.1:8095 ", unit)
        self.assertIn("MemoryMax=256M", unit)
        self.assertIn("WorkingDirectory=/srv/nvme/ftesurf-ops/reportd/app", unit)
        self.assertEqual(re.findall(r"proxy_pass (\S+);", nginx),
                         ["http://127.0.0.1:8095/api/report", "http://127.0.0.1:8095"])
        self.assertNotIn("8091", unit + nginx)

    def test_routes_live_only_under_admin_reports(self):
        rules = {r.rule for r in self.app.url_map.iter_rules()}
        self.assertEqual(rules, {"/api/report", "/admin/reports", "/admin/reports/api/list",
                                 "/admin/reports/api/item/<int:rid>",
                                 "/admin/reports/shot/<int:rid>.jpg",
                                 "/admin/reports/api/delete", "/admin/reports/api/delete_tag"})
        for path in ("/admin/", "/admin/login", "/admin/api/reports", "/admin/report/1/shot.jpg",
                     "/static/x"):
            self.assertEqual(self.get(path).status_code, 404, path)
        self.assertEqual(self.c.get("/api/report").status_code, 405)

    def test_env_file_parsing(self):
        home = tempfile.mkdtemp(prefix="reportd-env-")
        TEMPS.append(home)
        path = os.path.join(home, "surfd.env")
        with open(path, "w") as fh:
            fh.write("# comment\nSURFD_KEY=secret-not-read\nexport SURFD_ADMIN_SECRET='%s'\n"
                     "SURFD_ADMIN_HASH=\"scrypt$abc\"\nSURFD_PROXIES = 10.0.0.0/8\nnonsense\n" % SECRET)
        self.assertEqual(reportd.read_env_file(path),
                         {"SURFD_ADMIN_SECRET": SECRET, "SURFD_ADMIN_HASH": "scrypt$abc",
                          "SURFD_PROXIES": "10.0.0.0/8"})
        self.assertEqual(reportd.read_env_file(os.path.join(home, "missing")), {})
        # The file wins; the process environment fills what it lacks.
        app, _, clock = make_app(env_text="SURFD_ADMIN_HASH=x\n",
                                 environ={"SURFD_ADMIN_SECRET": SECRET, "SURFD_ADMIN_INSECURE_COOKIE": "1"})
        cookie = session_cookie(app, ok=True, born=clock.now, seen=clock.now, csrf="x")
        r = app.test_client(use_cookies=False).get("/admin/reports/api/list",
                                                   headers={"Cookie": "surfd_admin=" + cookie})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(make_app()[0].config["SESSION_COOKIE_SECURE"] is False)
        self.assertTrue(make_app(environ={})[0].config["SESSION_COOKIE_SECURE"] is True)
        self.assertEqual((self.app.config["SESSION_COOKIE_NAME"], self.app.config["SESSION_COOKIE_PATH"],
                          self.app.config["SESSION_COOKIE_SAMESITE"]), ("surfd_admin", "/admin", "Strict"))

    def test_deploy_set_alone_runs_and_imports_no_surfd_module(self):
        root = tempfile.mkdtemp(prefix="reportd-deploy-")
        TEMPS.append(root)
        app_dir = os.path.join(root, "app")
        os.makedirs(os.path.join(app_dir, "templates"))
        for rel in ("reportd.py", "reportd_wsgi.py", "templates/reportd_reports.html",
                    "templates/_admin_style.html"):
            shutil.copyfile(os.path.join(HERE, rel), os.path.join(app_dir, rel))
        with open(os.path.join(root, "surfd.env"), "w") as fh:
            fh.write(ENV)
        code = (
            "import json, sys, time; sys.path.insert(0, %r)\n"
            "import reportd_wsgi\n"
            "from flask.sessions import SecureCookieSessionInterface as S\n"
            "app = reportd_wsgi.app\n"
            "c = S().get_signing_serializer(app).dumps({'ok': True, 'born': time.time(),"
            " 'seen': time.time(), 'csrf': 'x'})\n"
            "r = app.test_client(use_cookies=False).get('/admin/reports',"
            " headers={'Cookie': 'surfd_admin=' + c})\n"
            "bad = sorted(m for m in sys.modules if m in ('surfd', 'admin', 'accounts', 'inventory',"
            " 'social', 'rcon', 'reports', 'hidupload'))\n"
            "print(json.dumps([r.status_code, 'Reports' in r.get_data(as_text=True), bad]))\n" % app_dir)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SURFD_", "REPORTD_"))}
        env.update(REPORTD_STATE=os.path.join(root, "state"), SURFD_ENV=os.path.join(root, "surfd.env"),
                   REPORTD_SOURCE="0123abcd", SURFD_ADMIN_INSECURE_COOKIE="1")
        p = subprocess.run([sys.executable, "-I", "-B", "-c", code], cwd=root, env=env,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout.strip().splitlines()[-1]), [200, True, []])
        self.assertIn("reportd source 0123abcd", p.stderr)


def tearDownModule():
    for path in TEMPS:
        shutil.rmtree(path, ignore_errors=True)
    left = [p for p in TEMPS if os.path.exists(p)]
    if left:
        print("left behind: %s" % left)


if __name__ == "__main__":
    unittest.main(verbosity=2)
