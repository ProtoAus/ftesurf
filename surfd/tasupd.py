#!/usr/bin/env python3
"""Uploaded TAS records (Lex, 20 Nov 2026): a .rec from any tool, judged by the game's physics.

An isolated service beside surfd, like tasrevd: its own store, read-only use of surfd's
`accounts` (name, ban), no surfd schema change. tools/tasplaus.py judges each upload on arrival:
  PASS  shown on this board ("physics checked")
  HOLD  kept for the owner (`tasupd.py --store S list|approve|reject`); its uploader sees why
  FAIL  refused with the reasons and not kept
Uploaders are Steam accounts World of Surf knows (signed in once at /board/link, which says names
are shown publicly) and has not banned (Lex, 20 Nov: Steam-linked only). Sign-in here is Steam's
OpenID through steam.py; each assertion's nonce is burned in this store.

  GET  /tasup/                        sign in, upload, recent runs, your runs
  GET  /tasup/board?map=&track=       one course, best per player
  GET  /tasup/run/<id>                one upload: verdict, reasons, numbers
  GET  /tasup/run/<id>.rec            the file (shown runs; held ones to their uploader)
  GET  /tasup/api/board?map=&track=   JSON; also /tasup/api/run/<id>, /tasup/api/recent
  GET  /tasup/steam, /tasup/steam/return
  POST /tasup/upload                  multipart: rec (file), tool (text), csrf
  POST /tasup/signout
"""
import argparse
import hashlib
import hmac
import html
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import threading
import time
import urllib.parse
import zlib
from array import array
from contextlib import contextmanager
from flask import Flask, Response, jsonify, redirect, request
import steam

MAX_REC = 8 * 1024 ** 2             # an hour of samples at 66.67 Hz is ~2.5 MB
MAX_FORM = MAX_REC + 64 * 1024
TICK = 0.015                        # the board is the game's 66.67 Hz; another rate is another board
MAX_TRACK = 99
USER_DAY, DAY_ITEMS, DAY_BYTES = 30, 1000, 1024 ** 3   # uploads an account / everyone a day
HELD_CAP = 10                       # an account's runs waiting for the owner
STORE_CAP = 4 * 1024 ** 3
SESSION_TTL, STATE_TTL = 12 * 3600, 600
PEER_READS, PEER_SIGNINS = 120, 10  # a minute, per address (an IPv6 /64)
STEAM_ATONCE, STEAM_MINUTE = 2, 30  # Steam confirmations in flight / a minute, everyone (surfd: OUT_ATONCE 2)
FORM_PARTS = 8                      # multipart boundaries in an upload: Werkzeug 2.2.2 does not cap parts
SIGNOUT_BODY = 4096
HEAVY_WAIT = 30                     # s an upload waits for the one checker slot
NAME_TTL = 300
TOOL_MAX = 64
REASONS_MAX = 40                    # kept and shown per run; a bad file can give one a tick
MAPNAME = re.compile(r'[a-z0-9_][a-z0-9_.+-]{0,63}')
STATE_RE = re.compile(r'[0-9a-f]{32}')
_CTRL = re.compile(r'[\x00-\x1f\x7f]')
# accounts._NAME_PUNCT: a tool name may be shown in game one day, so nothing the engine reads as markup.
TOOL_PUNCT = frozenset(" ._-!?()[]+=*#@'~,|")
STATES = ('shown', 'held', 'rejected', 'removed')
# Header keys only surfd's KSF/Momentum importers write (117 imports against 164 of our recordings).
IMPORT_KEYS = frozenset(('foreign', 'demodata', 'ksfdemo', 'ksfground', 'ksfmoves', 'ksftime', 'mapbuild',
                         'momdemo', 'momquality', 'moves'))
SQL = '''
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY AUTOINCREMENT, sha TEXT NOT NULL UNIQUE,
 samples_sha TEXT NOT NULL UNIQUE, steamid TEXT NOT NULL, map TEXT NOT NULL, track INTEGER NOT NULL,
 ticks INTEGER NOT NULL, verdict TEXT NOT NULL, state TEXT NOT NULL, reasons TEXT NOT NULL,
 stats TEXT NOT NULL, tool TEXT NOT NULL, size INTEGER NOT NULL, uploaded_at INTEGER NOT NULL,
 reviewed_at INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', sig BLOB NOT NULL);
CREATE INDEX IF NOT EXISTS runs_board ON runs(map, track, state, ticks);
CREATE INDEX IF NOT EXISTS runs_course ON runs(map, track, ticks);
CREATE INDEX IF NOT EXISTS runs_owner ON runs(steamid, id);
CREATE INDEX IF NOT EXISTS runs_recent ON runs(state, id);
CREATE TABLE IF NOT EXISTS nonces(nonce TEXT PRIMARY KEY, seen_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS spend(who TEXT NOT NULL, day INTEGER NOT NULL, n INTEGER NOT NULL,
 bytes INTEGER NOT NULL, PRIMARY KEY(who, day));
'''


class Unavailable(Exception):
    """Something this service reads (the account list) could not be read."""


def load_tasplaus():
    tools = os.environ.get('SURFD_TOOLS', str(Path(__file__).resolve().parent.parent / 'tools'))
    if tools not in sys.path: sys.path.insert(0, tools)
    import tasplaus
    return tasplaus


@contextmanager
def connect(path, readonly=False):
    uri = Path(path).resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw')
    db = sqlite3.connect(uri, uri=True, timeout=15.0, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


@contextmanager
def writing(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        yield db
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


def initialize(path):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    (path.parent / 'recs').mkdir(mode=0o700, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        with db: db.executescript(SQL)
        with db: db.execute("INSERT OR IGNORE INTO meta(k, v) VALUES ('secret', ?)", (secrets.token_hex(32),))
    finally:
        db.close()


def rec_path(store, sha):
    return Path(store).parent / 'recs' / sha[:2] / (sha + '.rec')


def samples_digest(run):
    """The motion, rounded (0.001 s, 0.1 u, 0.1 u/s): a reprint or a new header is the same run."""
    h = hashlib.sha256()
    for t, o, v in run.samples:
        h.update(('%.3f %.1f %.1f %.1f %.1f %.1f %.1f\n' % ((t,) + tuple(o) + tuple(v))).encode())
    return h.hexdigest()


def motion_series(run):
    """Velocity at each sample from the start to the finish, flat [vx, vy, vz, ...]: the run's motion
    whatever its position offset, header or extra samples."""
    fin = run.end * TICK + 1e-6
    return array('f', [c for t, o, v in run.samples if -1e-6 <= t <= fin for c in v])


def same_motion(a, b, shifts=8):
    """b is a's motion, give or take a few ticks: velocity within 2 u/s + 1% on 95% of the overlap."""
    na, nb = len(a) // 3, len(b) // 3
    for sh in range(-shifts, shifts + 1):
        lo, hi = max(0, sh), min(na, nb + sh)
        n = hi - lo
        if n < 20 or n < 0.9 * min(na, nb):
            continue
        allowed, bad = n // 20, 0
        for i in range(lo, hi):
            j = 3 * (i - sh)
            ax, ay, az = a[3 * i], a[3 * i + 1], a[3 * i + 2]
            dx, dy, dz = ax - b[j], ay - b[j + 1], az - b[j + 2]
            if dx * dx + dy * dy + dz * dz > (2.0 + 0.01 * math.sqrt(ax * ax + ay * ay + az * az)) ** 2:
                bad += 1
                if bad > allowed:
                    break
        else:
            return True
    return False


def course(track): return 'Main' if track == 0 else 'Bonus %d' % track
def fmt_time(s): return '%d:%06.3f' % divmod(s, 60) if s >= 60 else '%.3f' % s
def day_of(t): return time.strftime('%Y-%m-%d', time.gmtime(t))


def clean_tool(s):
    s = ''.join(ch for ch in (s or '') if ch.isalnum() or ch in TOOL_PUNCT)
    return ' '.join(s.split())[:TOOL_MAX]


def zones_for(dirs, mapname):
    """The first effective zone file, in surfd._story_course_zoned's order; never falls past a
    file that exists. None when there is none or it cannot be read."""
    for d in dirs:
        try:
            with open(os.path.join(d, mapname + '.json'), 'rb') as fh: body = fh.read(262145)
        except FileNotFoundError:
            continue
        except OSError:
            return None
        try:
            data = json.loads(body) if len(body) <= 262144 else None
        except (ValueError, RecursionError):
            return None
        return data if isinstance(data, dict) and isinstance(data.get('tracks'), dict) else None
    return None


CSS = '''
:root{--bg:#f6f7f9;--card:#fff;--ink:#14171c;--muted:#5b6370;--line:#dde1e7;--acc:#0b6bcb;--ok:#137a3a;--hold:#9a5b00;--bad:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--card:#171b21;--ink:#e8ebef;--muted:#9aa3ae;--line:#2a3039;--acc:#5aa9ff;--ok:#5cc983;--hold:#e0a54a;--bad:#ff7b72}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:920px;margin:0 auto;padding:24px 16px 48px}a{color:var(--acc)}
.mark{font-weight:600;text-decoration:none;color:var(--ink)}.mark b{color:var(--acc)}
h1{font-size:26px;margin:12px 0 4px}h2{font-size:18px;margin:28px 0 8px}.lede{color:var(--muted);margin:0 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:500;font-size:13px}td.n{text-align:right}.wrap{overflow-x:auto}
.b{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid currentColor;white-space:nowrap}
td:last-child,td.n{white-space:nowrap}.stats{max-width:460px}
.shown{color:var(--ok)}.held{color:var(--hold)}.rejected,.removed,.FAIL{color:var(--bad)}.HOLD{color:var(--hold)}.PASS{color:var(--ok)}
.go,button{display:inline-block;background:var(--acc);color:#fff;border:0;border-radius:8px;padding:9px 16px;font:inherit;text-decoration:none;cursor:pointer}
input[type=text],input[type=number]{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--ink);max-width:100%}
form.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.fine{color:var(--muted);font-size:13px}
ul.why{padding-left:18px}code{font-size:13px}button.link{background:none;color:var(--acc);padding:0}
'''

LABEL = {'shown': 'physics checked', 'held': 'waiting for review', 'rejected': 'rejected', 'removed': 'removed'}


def label(r):
    return 'owner approved' if r['state'] == 'shown' and r['verdict'] != 'PASS' else LABEL[r['state']]


def create_app(store, account_db, zone_dirs, base_url, http=steam.http, clock=time.time):
    tp = load_tasplaus()
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = MAX_FORM
    store, account_db = Path(store), Path(account_db)
    parts = urllib.parse.urlsplit(base_url.rstrip('/'))
    base = parts.path                                   # '/tasup'
    origin = '%s://%s' % (parts.scheme, parts.netloc)   # the OpenID realm
    secure = parts.scheme == 'https'
    # __Host- (Secure, Path=/, no Domain): this origin is shared with surfd's own pages.
    sess_cookie, state_cookie = ('__Host-ftup', '__Host-ftups') if secure else ('ftup', 'ftups')
    with connect(store) as db:
        secret = bytes.fromhex(db.execute("SELECT v FROM meta WHERE k = 'secret'").fetchone()['v'])
    heavy = threading.BoundedSemaphore(1)
    steam_slots = threading.BoundedSemaphore(STEAM_ATONCE)
    spend_lock = threading.Lock()
    hits, hits_lock = {}, threading.Lock()
    names, names_lock = {}, threading.Lock()

    def mac(*fields):
        return hmac.new(secret, '\x1f'.join(fields).encode(), hashlib.sha256).hexdigest()[:32]

    def peer():
        addr = request.remote_addr or ''
        try:
            ip = ipaddress.ip_address(addr)
            if ip.version == 6: addr = str(ipaddress.ip_network('%s/64' % ip, strict=False))
        except ValueError:
            pass
        return mac('peer', addr)[:24]

    def limited(kind, cap, who=None):
        minute = int(clock() // 60)
        k = (kind, peer() if who is None else who, minute)
        with hits_lock:
            if len(hits) > 50000:   # drop past minutes; a flood inside one minute is refused, not reset
                for old in [x for x in hits if x[2] < minute]: del hits[old]
                if len(hits) > 50000: return True
            hits[k] = hits.get(k, 0) + 1
            return hits[k] > cap

    def session():
        """The signed-in SteamID, or ''."""
        v = request.cookies.get(sess_cookie, '')
        f = v.split('.')
        if len(f) != 3 or not steam.is_steamid64(f[0]) or not f[1].isdigit(): return ''
        if int(f[1]) < clock() or not hmac.compare_digest(f[2], mac('session', f[0], f[1])): return ''
        return f[0]

    def csrf():
        return mac('csrf', request.cookies.get(sess_cookie, ''))

    def accounts_of(steamids):
        """{steamid: (name, banned)} for the ones World of Surf knows; raises Unavailable."""
        want = sorted(set(steamids))
        out, now = {}, clock()
        with names_lock:
            miss = [s for s in want if s not in names or names[s][1] < now - NAME_TTL]
            out.update({s: names[s][0] for s in want if s not in miss and names[s][0] is not None})
        if miss:
            try:
                with connect(account_db, readonly=True) as adb:
                    rows = {}
                    for i in range(0, len(miss), 500):
                        chunk = miss[i:i + 500]
                        rows.update({r['steamid']: (r['name'] or '', bool(r['banned_at'])) for r in adb.execute(
                            'SELECT steamid, name, banned_at FROM accounts WHERE steamid IN (%s)'
                            % ','.join('?' * len(chunk)), chunk)})
            except sqlite3.Error as e:
                raise Unavailable('the account list cannot be read (%s)' % type(e).__name__)
            with names_lock:
                if len(names) > 20000: names.clear()
                for s in miss:
                    names[s] = (rows.get(s), now)
            out.update(rows)
        return out

    def who(steamid, accts):
        name = (accts.get(steamid) or ('', False))[0]
        return name or 'Steam ' + steamid[-4:]

    def page(title, inner, status=200, sid=None):
        top = ('<a class="mark" href="%s/">World of <b>Surf</b> &middot; TAS uploads</a>' % base)
        doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
               '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
               '<meta name="color-scheme" content="light dark">\n<title>%s - World of Surf</title>\n'
               '<style>%s</style>\n</head>\n<body>\n<main>\n%s\n%s\n</main>\n</body>\n</html>\n'
               % (html.escape(title), CSS, top, inner))
        return Response(doc, status=status, mimetype='text/html')

    def wants_json():
        return request.path.startswith(base + '/api/') or (
            request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json')

    def refuse(message, status, reasons=None):
        if wants_json():
            return jsonify(ok=0, error=message, reasons=reasons or []), status
        inner = '<h1>Not uploaded</h1>\n<p class="lede">%s</p>' % html.escape(message)
        if reasons:
            inner += '\n<ul class="why">%s</ul>' % ''.join(
                '<li><span class="%s">%s</span>%s %s</li>' % (
                    r['level'], r['level'], '' if r.get('t') is None else ' at %.3fs' % r['t'], html.escape(r['what']))
                for r in reasons)
        inner += '\n<p><a href="%s/">Back</a></p>' % base
        return page('Not uploaded', inner, status)

    @app.errorhandler(413)
    def too_big(e): return refuse('That file is over %d MB.' % (MAX_REC // 1024 ** 2), 413)

    @app.errorhandler(sqlite3.Error)
    def busy(e): return refuse('The upload service is busy; try again in a minute.', 503)

    @app.errorhandler(Unavailable)
    def unavailable(e): return refuse('The upload service cannot tell right now: %s.' % e, 503)

    @app.before_request
    def budgets():
        if request.method in ('GET', 'HEAD') and limited('read', PEER_READS):
            return refuse('Too many requests; try again in a minute.', 429)
        if request.method == 'POST' and request.path == base + '/signout' and (request.content_length or 0) > SIGNOUT_BODY:
            return refuse('That form is too large.', 413)
        if request.method == 'POST' and request.path == base + '/upload':
            # Read the body once and count its parts before Werkzeug parses it (2.2.2: no part cap).
            boundary = request.mimetype_params.get('boundary', '')
            if request.mimetype != 'multipart/form-data' or not boundary:
                return refuse('Upload the file with the form.', 400)
            if request.get_data(cache=True).count(b'--' + boundary.encode('latin-1', 'replace')) > FORM_PARTS:
                return refuse('That form has too many parts.', 400)

    @app.after_request
    def headers(resp):
        resp.headers['Cache-Control'] = 'no-store'
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['Referrer-Policy'] = 'same-origin'
        resp.headers['Content-Security-Policy'] = (
            "default-src 'none'; style-src 'unsafe-inline'; form-action 'self';"
            " frame-ancestors 'none'; base-uri 'none'")
        return resp

    def row_json(r, accts):
        return dict(id=r['id'], map=r['map'], track=r['track'], course=course(r['track']), ticks=r['ticks'],
                    time=round(r['ticks'] * TICK, 3), steamid=r['steamid'], name=who(r['steamid'], accts),
                    tool=r['tool'], state=r['state'], verdict=r['verdict'], uploaded=r['uploaded_at'],
                    note=r['note'], file='%s/run/%d.rec' % (base, r['id']) if r['state'] == 'shown' else None)

    def board_rows(db, mapname, track):
        rows = db.execute("SELECT * FROM runs WHERE map = ? AND track = ? AND state = 'shown'"
                          ' ORDER BY ticks, id LIMIT 5000', (mapname, track)).fetchall()
        accts = accounts_of(r['steamid'] for r in rows)
        best, seen = [], set()
        for r in rows:
            a = accts.get(r['steamid'])
            if a is None or a[1] or r['steamid'] in seen: continue   # unknown or banned since
            seen.add(r['steamid']); best.append(r)
            if len(best) >= 100: break
        return best, accts

    def recent_rows(db, limit=25):
        rows = db.execute("SELECT * FROM runs WHERE state = 'shown' ORDER BY id DESC LIMIT ?", (limit * 2,)).fetchall()
        accts = accounts_of(r['steamid'] for r in rows)
        return [r for r in rows if r['steamid'] in accts and not accts[r['steamid']][1]][:limit], accts

    def course_args():
        mapname = (request.args.get('map') or '').strip().lower()
        try: track = int(request.args.get('track', '0'))
        except ValueError: track = -1
        if not MAPNAME.fullmatch(mapname) or not 0 <= track <= MAX_TRACK: return None, None
        return mapname, track

    def runs_table(rows, accts, ranked=False, mine=False):
        if not rows: return '<p class="fine">Nothing yet.</p>'
        head = ('<tr>%s<th>Map</th><th>Course</th><th class="n">Time</th>%s<th>Tool</th><th>%s</th><th>Uploaded</th></tr>'
                % ('<th class="n">#</th>' if ranked else '', '' if mine else '<th>Player</th>',
                   'State' if mine else 'Check'))
        body = []
        for i, r in enumerate(rows):
            player = '' if mine else '<td><a href="https://steamcommunity.com/profiles/%s" rel="nofollow noopener">%s</a></td>' % (
                r['steamid'], html.escape(who(r['steamid'], accts)))
            body.append('<tr>%s<td><a href="%s/board?map=%s&amp;track=%d">%s</a></td><td>%s</td>'
                        '<td class="n"><a href="%s/run/%d">%s</a></td>%s<td>%s</td><td><span class="b %s">%s</span></td><td>%s</td></tr>' % (
                            '<td class="n">%d</td>' % (i + 1) if ranked else '', base, urllib.parse.quote(r['map']), r['track'],
                            html.escape(r['map']), course(r['track']), base, r['id'], fmt_time(r['ticks'] * TICK), player,
                            html.escape(r['tool']) or '&ndash;', r['state'], label(r), day_of(r['uploaded_at'])))
        return '<div class="wrap"><table>%s%s</table></div>' % (head, ''.join(body))

    @app.get(base)
    def bare(): return redirect(base + '/', 301)

    @app.get(base + '/')
    def index():
        sid = session()
        with connect(store) as db:
            recent, accts = recent_rows(db)
            mine = db.execute('SELECT * FROM runs WHERE steamid = ? ORDER BY id DESC LIMIT 50', (sid,)).fetchall() if sid else []
        me = accounts_of([sid]).get(sid) if sid else None
        out = ['<h1>Uploaded TAS records</h1>',
               '<p class="lede">Made a run with your own bot, a fork, or by hand? Upload its <code>.rec</code>. '
               'It is checked against the game\'s movement physics (gravity, air acceleration, ground speed, '
               'start, checkpoints and end zone). Runs that check out are listed here; anything the check '
               'cannot clear waits for review. TAS runs stay off the normal leaderboards.</p>']
        if sid and me and not me[1]:
            out.append('<div class="card"><form class="row" method="post" action="%s/signout">'
                       '<span>Signed in as <b>%s</b></span><input type="hidden" name="csrf" value="%s">'
                       '<button class="link" type="submit">Sign out</button></form>' % (base, html.escape(who(sid, {sid: me})), csrf()))
            out.append('<form method="post" action="%s/upload" enctype="multipart/form-data">'
                       '<input type="hidden" name="csrf" value="%s"><p><label>Recording (.rec, up to %d MB)<br>'
                       '<input type="file" name="rec" accept=".rec,text/plain" required></label></p>'
                       '<p><label>Tool or bot (optional)<br><input type="text" name="tool" maxlength="%d" '
                       'placeholder="e.g. my search bot v2" size="40"></label></p><p><button type="submit">Upload and check</button></p>'
                       '<p class="fine">The board is 66.67 tick (tickrate 0.015). Map and course come from the file\'s header. '
                       'Your Steam name is shown with the run and anyone can download the file.</p></form></div>'
                       % (base, csrf(), MAX_REC // 1024 ** 2, TOOL_MAX))
        else:
            out.append('<div class="card"><p><a class="go" href="%s/steam">Sign in with Steam to upload</a></p>'
                       '<p class="fine">Uploading needs a Steam account linked to World of Surf. First time? '
                       '<a href="%s/board/link">Link your Steam account</a> once (about twenty seconds), then sign in here.</p></div>'
                       % (base, origin))
        out.append('<h2>Find a course</h2><form class="row" method="get" action="%s/board">'
                   '<input type="text" name="map" placeholder="surf_sandtrap2" required>'
                   '<input type="number" name="track" min="0" max="%d" value="0" style="width:6em" aria-label="Course (0 main, 1+ bonus)">'
                   '<button type="submit">Show board</button></form>' % (base, MAX_TRACK))
        if mine:
            out.append('<h2>Your uploads</h2>' + runs_table(mine, accts, mine=True))
        out.append('<h2>Recently checked</h2>' + runs_table(recent, accts))
        return page('TAS uploads', '\n'.join(out))

    @app.get(base + '/board')
    def board_page():
        mapname, track = course_args()
        if mapname is None: return refuse('Name a map (letters, digits, _ . + -) and a course number.', 400)
        with connect(store) as db: rows, accts = board_rows(db, mapname, track)
        return page('%s %s' % (mapname, course(track)), '<h1>%s <span class="lede">%s</span></h1>\n'
                    '<p class="lede">Uploaded TAS runs, best per player. Times are the file\'s own clock at 66.67 tick.</p>\n%s'
                    % (html.escape(mapname), course(track), runs_table(rows, accts, ranked=True)))

    @app.get(base + '/api/board')
    def board_api():
        mapname, track = course_args()
        if mapname is None: return refuse('map and track required', 400)
        with connect(store) as db: rows, accts = board_rows(db, mapname, track)
        return jsonify(ok=1, map=mapname, track=track, runs=[row_json(r, accts) for r in rows])

    @app.get(base + '/api/recent')
    def recent_api():
        with connect(store) as db: rows, accts = recent_rows(db)
        return jsonify(ok=1, runs=[row_json(r, accts) for r in rows])

    def visible(rid):
        """The run if this viewer may see it: shown, or held/rejected to its uploader."""
        with connect(store) as db: r = db.execute('SELECT * FROM runs WHERE id = ?', (rid,)).fetchone()
        if r is None or r['state'] == 'removed': return None
        if r['state'] != 'shown' and r['steamid'] != session(): return None
        accts = accounts_of([r['steamid']])
        if r['state'] == 'shown' and (r['steamid'] not in accts or accts[r['steamid']][1]): return None
        return r, accts

    @app.get(base + '/api/run/<int:rid>')
    def run_api(rid):
        got = visible(rid)
        if got is None: return refuse('no such run', 404)
        r, accts = got
        return jsonify(ok=1, run=row_json(r, accts), reasons=json.loads(r['reasons']), stats=json.loads(r['stats']))

    @app.get(base + '/run/<int:rid>')
    def run_page(rid):
        got = visible(rid)
        if got is None: return refuse('There is no such run, or it is not public.', 404)
        r, accts = got
        reasons = json.loads(r['reasons']); st = json.loads(r['stats'])
        why = ''.join('<li><span class="%s">%s</span>%s %s</li>' % (
            x['level'], x['level'], '' if x.get('t') is None else ' at %.3fs' % x['t'], html.escape(x['what'])) for x in reasons)
        nums = ''.join('<tr><th>%s</th><td>%s</td></tr>' % (html.escape(k.replace('_', ' ')), html.escape(str(v)))
                       for k, v in st.items())
        inner = ['<h1>%s <span class="lede">%s &middot; %s</span></h1>' % (
                     fmt_time(r['ticks'] * TICK), html.escape(r['map']), course(r['track'])),
                 '<p>By <a href="https://steamcommunity.com/profiles/%s" rel="nofollow noopener">%s</a>%s, uploaded %s. '
                 '<span class="b %s">%s</span></p>' % (
                     r['steamid'], html.escape(who(r['steamid'], accts)),
                     ' with ' + html.escape(r['tool']) if r['tool'] else '', day_of(r['uploaded_at']), r['state'], label(r))]
        if r['note']: inner.append('<p>Review note: %s</p>' % html.escape(r['note']))
        inner.append('<div class="card"><b>Physics check: <span class="%s">%s</span></b>%s</div>' % (
            r['verdict'], r['verdict'], '<ul class="why">%s</ul>' % why if why else
            '<p class="fine">Every checked tick is inside the movement limits and the zones were visited in order.</p>'))
        inner.append('<div class="card wrap stats"><table>%s</table></div>' % nums)
        inner.append('<p><a href="%s/run/%d.rec">Download the .rec</a> &middot; <a href="%s/board?map=%s&amp;track=%d">Course board</a></p>'
                     % (base, r['id'], base, urllib.parse.quote(r['map']), r['track']))
        inner.append('<p class="fine">Compare it with another run: <code>python3 tools/runcompare.py ref.rec this.rec</code> '
                     '(World of Surf repository).</p>')
        return page('%s %s' % (r['map'], fmt_time(r['ticks'] * TICK)), '\n'.join(inner))

    @app.get(base + '/run/<int:rid>.rec')
    def run_file(rid):
        got = visible(rid)
        if got is None: return refuse('no such run', 404)
        r = got[0]
        try: body = rec_path(store, r['sha']).read_bytes()
        except OSError: return refuse('That file is missing.', 404)
        resp = Response(body, mimetype='text/plain')
        resp.headers['Content-Disposition'] = 'attachment; filename="tas-%d-%s.rec"' % (r['id'], r['map'])
        return resp

    def return_to(state): return '%s%s/steam/return?s=%s' % (origin, base, state)

    @app.get(base + '/steam')
    def steam_start():
        if limited('signin', PEER_SIGNINS): return refuse('Too many sign-ins; try again in a minute.', 429)
        token = secrets.token_urlsafe(18)
        state = hashlib.sha256(token.encode()).hexdigest()[:32]
        resp = redirect(steam.login_url(origin, return_to(state)), 302)
        resp.set_cookie(state_cookie, token, max_age=STATE_TTL, path='/', secure=secure, httponly=True, samesite='Lax')
        return resp

    @app.get(base + '/steam/return')
    def steam_return():
        if limited('signin', PEER_SIGNINS): return refuse('Too many sign-ins; try again in a minute.', 429)
        now = int(clock())
        state, token = request.args.get('s', ''), request.cookies.get(state_cookie, '')
        if not STATE_RE.fullmatch(state) or not token or not hmac.compare_digest(
                hashlib.sha256(token.encode()).hexdigest()[:32], state):
            return refuse('That sign-in did not start in this browser, or took longer than ten minutes.', 400)
        args = {}
        for k in request.args:
            if k.startswith('openid.'):
                vals = request.args.getlist(k)
                if len(vals) != 1: return refuse('Steam did not confirm that sign-in.', 400)
                args[k] = vals[0]
        try:
            sid, nonce = steam.precheck(args, return_to(state), now)
            with connect(store) as db, writing(db):
                db.execute('DELETE FROM nonces WHERE seen_at < ?', (now - 4 * steam.NONCE_SKEW,))
                try: db.execute('INSERT INTO nonces(nonce, seen_at) VALUES (?, ?)', (nonce, now))
                except sqlite3.IntegrityError: raise steam.Refused('nonce seen')
            if limited('steam', STEAM_MINUTE, who='everyone'):
                return refuse('Too many sign-ins right now; try again in a minute.', 429)
            if not steam_slots.acquire(blocking=False):
                return refuse('Too many sign-ins right now; try again in a moment.', 503)
            try:
                steam.confirm(args, http)
            finally:
                steam_slots.release()
        except steam.Refused:
            return refuse('Steam did not confirm that sign-in.', 400)
        except steam.Unavailable:
            return refuse('Steam could not be reached. Try again in a minute.', 503)
        acct = accounts_of([sid]).get(sid)
        if acct is None:
            return page('Link first', '<h1>Link your Steam account first</h1><p class="lede">World of Surf does not know '
                        'this Steam account yet. <a href="%s/board/link">Link it</a> once (it says how your name is shown), '
                        'then <a href="%s/steam">sign in here again</a>.</p>' % (origin, base), 403)
        if acct[1]:
            return refuse('This Steam account cannot upload.', 403)
        exp = str(now + SESSION_TTL)
        resp = redirect(base + '/', 303)
        resp.set_cookie(sess_cookie, '%s.%s.%s' % (sid, exp, mac('session', sid, exp)), max_age=SESSION_TTL,
                        path='/', secure=secure, httponly=True, samesite='Lax')
        resp.delete_cookie(state_cookie, path='/', secure=secure, httponly=True, samesite='Lax')
        return resp

    def post_ok():
        """Same-origin form with this session's token."""
        o = request.headers.get('Origin')
        if o is not None and o != origin: return False
        return hmac.compare_digest(request.form.get('csrf', ''), csrf())

    @app.post(base + '/signout')
    def signout():
        if not post_ok(): return refuse('That form is out of date; reload the page.', 403)
        resp = redirect(base + '/', 303)
        resp.delete_cookie(sess_cookie, path='/', secure=secure, httponly=True, samesite='Lax')
        return resp

    def spend(db, sid, now):
        """Counts the attempt (refused ones too) before any work; a reason string when over. Bytes are
        counted when a run is kept (`kept`), so refused junk cannot fill everyone's day."""
        day = int(now // 86400)
        tot = db.execute('SELECT COALESCE(SUM(n), 0), COALESCE(SUM(bytes), 0) FROM spend WHERE day = ?', (day,)).fetchone()
        mine = db.execute('SELECT n FROM spend WHERE who = ? AND day = ?', (sid, day)).fetchone()
        if mine is not None and mine['n'] >= USER_DAY: return 'You have uploaded %d runs today; try again tomorrow.' % USER_DAY
        if tot[0] >= DAY_ITEMS or tot[1] >= DAY_BYTES: return 'The upload service is full for today; try again tomorrow.'
        db.execute('INSERT INTO spend(who, day, n, bytes) VALUES (?, ?, 1, 0) ON CONFLICT(who, day)'
                   ' DO UPDATE SET n = n + 1', (sid, day))
        db.execute('DELETE FROM spend WHERE day < ?', (day - 2,))
        return None

    def kept(db, sid, size, now):
        db.execute('UPDATE spend SET bytes = bytes + ? WHERE who = ? AND day = ?', (size, sid, int(now // 86400)))

    @app.post(base + '/upload')
    def upload():
        sid = session()
        if not sid: return refuse('Sign in with Steam first.', 401)
        if not post_ok(): return refuse('That form is out of date; reload the page.', 403)
        acct = accounts_of([sid]).get(sid)
        if acct is None or acct[1]: return refuse('This Steam account cannot upload.', 403)
        f = request.files.get('rec')
        if f is None: return refuse('Choose a .rec file.', 400)
        body = f.read(MAX_REC + 1)
        if len(body) > MAX_REC: return refuse('That file is over %d MB.' % (MAX_REC // 1024 ** 2), 413)
        tool = clean_tool(request.form.get('tool'))
        now = int(clock())
        with spend_lock, connect(store) as db, writing(db):
            over = spend(db, sid, now)
        if over: return refuse(over, 429)
        try: text = body.decode('utf-8')
        except UnicodeDecodeError: return refuse('That is not a text .rec file.', 400)
        if '\x00' in text or not text.startswith('FTESURF-REC '): return refuse('That is not a FTESURF-REC recording.', 400)
        pre = tp.read(text=text, header_only=True)   # the checker's own header reader: one reading of it
        if not pre.has_body: return refuse('The recording has no header (no begin line).', 400)
        if pre.dups: return refuse('The header gives %s twice.' % ', '.join(sorted(pre.dups)), 400)
        if pre.odd_breaks: return refuse('The file breaks lines with something other than a newline.', 400)
        hdr = pre.hdr
        mapname = (hdr.get('map') or '').strip().lower()
        if not MAPNAME.fullmatch(mapname): return refuse('The header names no usable map.', 400)
        track = tp.hdr_int(hdr, 'track', -1) if 'track' in hdr else 0
        if not 0 <= track <= MAX_TRACK: return refuse('The header names no usable track.', 400)
        if IMPORT_KEYS.intersection(hdr) or (hdr.get('runid') or '').startswith(('mom-', 'ksf-')):
            return refuse('That is an imported run (KSF or Momentum): it is its player\'s, not an upload.', 400)
        rates = []
        for k in ('movetickrate', 'tickrate'):   # movetickrate 0 is "no engine value" (grammar)
            try: x = float((hdr.get(k) or '0').split()[0])
            except (ValueError, IndexError): x = float('nan')
            if not math.isfinite(x) or x < 0: return refuse('The header\'s %s is not a number.' % k, 400)
            if x > 0: rates.append(x)
        if not rates or any(abs(x - TICK) > 1e-6 for x in rates):
            return refuse('This board is 66.67 tick: the header must say tickrate %s.' % TICK, 400)
        sha = hashlib.sha256(body).hexdigest()
        with connect(store) as db:
            if db.execute('SELECT 1 FROM runs WHERE sha = ?', (sha,)).fetchone():
                return refuse('That file has already been uploaded.', 409)
        if not heavy.acquire(timeout=HEAVY_WAIT): return refuse('The checker is busy; try again in a minute.', 503)
        try:
            run = tp.read(text=text)
            if run.end is None or not 0 < run.end <= tp.MAX_TICKS or len(run.samples) < 3:
                res = tp.check(run, None)   # refuses it, saying why
            else:
                try:
                    res = tp.check(run, zones_for(zone_dirs, mapname))
                except Exception as e:   # e.g. a zone file with the wrong types: cannot see, so a person looks
                    app.logger.exception('tasplaus failed on an upload for %s', mapname)
                    res = {'verdict': tp.HOLD, 'stats': {}, 'reasons': [
                        {'level': tp.HOLD, 't': None, 'what': 'the checker could not finish (%s)' % type(e).__name__}]}
            series = motion_series(run) if res['verdict'] != tp.FAIL else None
        finally:
            heavy.release()
        reasons = res['reasons']
        if len(reasons) > REASONS_MAX:
            rest = reasons[REASONS_MAX:]
            reasons = reasons[:REASONS_MAX] + [{'level': tp.FAIL if any(x['level'] == tp.FAIL for x in rest) else tp.HOLD,
                                                't': None, 'what': '%d more not listed' % len(rest)}]
        if res['verdict'] == tp.FAIL:
            return refuse('The physics check refused it.', 422, reasons)
        digest = samples_digest(run)
        sig = zlib.compress(series.tobytes())
        state = 'shown' if res['verdict'] == tp.PASS else 'held'
        path = rec_path(store, sha)
        path.parent.mkdir(mode=0o700, exist_ok=True)
        committed = False
        try:
            with connect(store) as db, writing(db):
                # Inside the write transaction: concurrent uploads cannot both pass a cap.
                if state == 'held' and db.execute("SELECT COUNT(*) FROM runs WHERE steamid = ? AND state = 'held'",
                                                  (sid,)).fetchone()[0] >= HELD_CAP:
                    return refuse('You have %d runs waiting for review; wait for those first.' % HELD_CAP, 429)
                if db.execute('SELECT COALESCE(SUM(size), 0) FROM runs').fetchone()[0] + len(body) > STORE_CAP:
                    return refuse('The upload store is full; the owner has been told.', 507)
                lo, hi = run.end - max(30, run.end // 33), run.end + max(30, run.end // 33)
                for other in db.execute('SELECT id, steamid, sig FROM runs WHERE map = ? AND track = ? AND ticks BETWEEN ? AND ?',
                                        (mapname, track, lo, hi)).fetchall():
                    if same_motion(series, array('f', zlib.decompress(other['sig']))):
                        return refuse('That is the motion of run %d%s, with small changes.' % (
                            other['id'], '' if other['steamid'] == sid else ' (another player\'s)'), 409)
                cur = db.execute('INSERT INTO runs(sha, samples_sha, steamid, map, track, ticks, verdict, state, reasons,'
                                 ' stats, tool, size, uploaded_at, sig) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                 (sha, digest, sid, mapname, track, run.end, res['verdict'], state,
                                  json.dumps(reasons), json.dumps(res['stats']), tool, len(body), now, sig))
                rid = cur.lastrowid
                kept(db, sid, len(body), now)
                tmp = path.with_name(path.name + '.%s.tmp' % secrets.token_hex(4))
                try:
                    tmp.write_bytes(body)
                    os.replace(tmp, path)
                finally:
                    if tmp.exists(): tmp.unlink()
            committed = True
        except sqlite3.IntegrityError:
            return refuse('That run has already been uploaded (the same motion, maybe under another header).', 409)
        finally:
            if not committed and path.exists():
                # Content-addressed: keep it if a committed row (a concurrent upload of these bytes) names it.
                with connect(store) as db:
                    if not db.execute('SELECT 1 FROM runs WHERE sha = ?', (sha,)).fetchone(): path.unlink()
        if wants_json():
            return jsonify(ok=1, id=rid, state=state, verdict=res['verdict'], reasons=reasons, time=round(run.end * TICK, 3))
        return redirect('%s/run/%d' % (base, rid), 303)

    return app


def main(argv=None):
    ap = argparse.ArgumentParser(description='Owner tools for the TAS upload store.')
    ap.add_argument('--store', required=True)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init')
    ls = sub.add_parser('list'); ls.add_argument('--state', default='held', choices=STATES + ('all',)); ls.add_argument('--limit', type=int, default=50)
    sh = sub.add_parser('show'); sh.add_argument('id', type=int)
    for name in ('approve', 'reject', 'remove'):
        p = sub.add_parser(name); p.add_argument('id', type=int); p.add_argument('--note', default='')
    a = ap.parse_args(argv)
    if a.cmd == 'init':
        initialize(a.store); print('initialized', a.store); return 0
    with connect(a.store) as db:
        if a.cmd == 'list':
            q = 'SELECT * FROM runs' + ('' if a.state == 'all' else ' WHERE state = ?') + ' ORDER BY id DESC LIMIT ?'
            for r in db.execute(q, ((a.state,) if a.state != 'all' else ()) + (a.limit,)):
                print('%5d %-8s %-4s %s %-28s %-8s %9s  %s  %s' % (
                    r['id'], r['state'], r['verdict'], day_of(r['uploaded_at']), r['map'], course(r['track']),
                    fmt_time(r['ticks'] * TICK), r['steamid'], r['tool']))
            return 0
        r = db.execute('SELECT * FROM runs WHERE id = ?', (a.id,)).fetchone()
        if r is None: print('no run', a.id); return 1
        if a.cmd == 'show':
            for k in r.keys():
                if k not in ('reasons', 'stats'): print('%-12s %s' % (k, r[k]))
            print('file         %s' % rec_path(a.store, r['sha']))
            for x in json.loads(r['reasons']): print('  %s t=%s %s' % (x['level'], x['t'], x['what']))
            print('  stats', r['stats'])
            return 0
        to = {'approve': 'shown', 'reject': 'rejected', 'remove': 'removed'}[a.cmd]
        allowed = {'approve': ('held',), 'reject': ('held', 'shown'), 'remove': STATES}[a.cmd]
        if r['state'] not in allowed: print('run %d is %s; %s needs %s' % (a.id, r['state'], a.cmd, '/'.join(allowed))); return 1
        with writing(db):
            changed = db.execute('UPDATE runs SET state = ?, reviewed_at = ?, note = ? WHERE id = ? AND state = ?',
                                 (to, int(time.time()), a.note[:200], a.id, r['state'])).rowcount
            if changed == 1 and to == 'removed':
                db.execute('UPDATE runs SET size = 0 WHERE id = ?', (a.id,))   # the store cap counts kept files
        if changed != 1: print('run %d changed meanwhile; nothing done' % a.id); return 1
        if to == 'removed':
            # The row stays (its motion is still refused as a copy); the file goes, unless another row has it.
            if not db.execute("SELECT 1 FROM runs WHERE sha = ? AND state != 'removed'", (r['sha'],)).fetchone():
                try: rec_path(a.store, r['sha']).unlink()
                except FileNotFoundError: pass
        print('run %d: %s -> %s' % (a.id, r['state'], to))
        return 0


if __name__ == '__main__':
    sys.exit(main())
