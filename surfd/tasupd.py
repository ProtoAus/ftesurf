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
  GET  /tasup/api/health              reads the store and surfd.db as the service (install probe)
A run that reaches the best known time on its course (surfd's clean record in a trusted tier, or the
best upload shown here), or the first on a course, is held: the checker cannot see the map's walls.
  GET  /tasup/steam, /tasup/steam/return
  POST /tasup/upload                  multipart: rec (file), tool (text), csrf
  POST /tasup/signout
"""
import argparse
import bisect
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
import urllib.error
import urllib.request
import zlib
from array import array
from contextlib import contextmanager
from flask import Flask, Response, g, jsonify, redirect, request
import steam

MAX_REC = 8 * 1024 ** 2             # ~10 minutes of a native .rec (~200 B a sample); a KSF/sparse export runs longer
MAX_FORM = MAX_REC + 64 * 1024
TICK = 0.015                        # the board is the game's 66.67 Hz; another rate is another board
MAX_TRACK = 99
USER_DAY, DAY_ITEMS, DAY_BYTES = 30, 1000, 1024 ** 3   # uploads an account / everyone a day
HELD_CAP = 10                       # an account's runs waiting for the owner
STORE_CAP = 4 * 1024 ** 3
SESSION_TTL, STATE_TTL = 12 * 3600, 600
PEER_READS, PEER_SIGNINS = 120, 10  # a minute, per address (an IPv6 /64)
REC_PEER_BYTES, REC_ALL_BYTES = 32 * 1024 ** 2, 128 * 1024 ** 2   # .rec downloads a minute: an address / everyone
STEAM_ATONCE, STEAM_MINUTE = 2, 30  # Steam confirmations in flight / a minute, everyone (surfd: OUT_ATONCE 2)
FORM_PARTS = 8                      # multipart boundaries in an upload: Werkzeug 2.2.2 does not cap parts
SIGNOUT_BODY = 4096
HEAVY_WAIT = 30                     # s an upload waits for the one checker slot (a long course's copy phase: 15-25 s)
DUPLICATE = ('That exact file has been uploaded before. If it is your own run, add any line to its header'
             ' (for example `comment mine`) and upload it again.')   # review 7: the author of a removed copy's file
UPLOADS_AT_ONCE = 2                 # gunicorn has 4 threads: pages and sign-in keep the other two (review 6)
NAME_TTL = 300
TOOL_MAX = 64
REASONS_MAX = 40                    # kept and shown per run; a bad file can give one a tick
# Pages never load `sig` (up to MBs a row): these columns only.
ROW = ('id, sha, steamid, map, track, ticks, verdict, state, reasons, stats, tool, size, uploaded_at,'
       ' reviewed_at, note')
LIST = 'id, steamid, map, track, ticks, verdict, state, tool, uploaded_at, note'
COPY_CANDIDATES, COPY_PER_PLAYER = 60, 10   # per upload; per other account (review 8: 3 of a victim's own nearer runs hid the copied one)
COPY_BUDGET = 20.0                  # s per copy_of call (up to four an upload), then a person looks (review 7: ~60-100 s on the Pi worst case)
COPY_TICKS, COPY_FULL = 3000, 5     # ticks compared per pass; full passes per upload before a person looks
COPY_SHIFTS = 16                    # ticks either way: past the start-zone leave the checker allows (review 7: +9 hid a copy)
HEADER_MAX = 65536                  # the header (up to `begin`) is read from this prefix
BEGIN_LINE = re.compile(rb'\n[ \t]*begin(?=[ \t\r\n])')   # review 5: find(b'\nbegin') also cut at `begintick`
PEER_STEAM = 3                      # Steam confirmations a minute per address
HITS_MAX = 50000                    # rate-limit keys a minute; past it new addresses go uncounted
# The course record a PASS must not reach: trusted tiers' clean runs only. Community rows are demoted,
# banned:* hidden, and surfd marks any TF_TAS run style tas (cheat or practice history too).
TIERS_RECORD, STYLES_RECORD = ('ranked', 'momentum', 'ksf'), ('clean',)
SCHEMA = 2                          # PRAGMA user_version `init` leaves; a release needs at least its own (2: P1696)
MAPNAME = re.compile(r'[a-z0-9_][a-z0-9_.+-]{0,63}')
STATE_RE = re.compile(r'[0-9a-f]{32}')
_CTRL = re.compile(r'[\x00-\x1f\x7f]')
# accounts._NAME_PUNCT: a tool name may be shown in game one day, so nothing the engine reads as markup.
TOOL_PUNCT = frozenset(" ._-!?()[]+=*#@'~,|")
STATES = ('shown', 'held', 'rejected', 'removed')
# Header keys only surfd's KSF/Momentum importers write (117 imports against 164 of our recordings).
IMPORT_KEYS = frozenset(('foreign', 'demodata', 'ksfdemo', 'ksfground', 'ksfmoves', 'ksftime', 'mapbuild',
                         'momdemo', 'momquality'))
# P1696: the game posts to /upload as GAME_MIME, the linked key's proof before the file (cl_tasupload.qc). Signed as zone
# publishing signs (acct_sign kind -6, the site fixed) but over game_nonce(): this purpose and the file's hash, so neither
# service takes the other's proof and no game code before P1696 can make one.
GAME_MIME = 'application/x-ftesurf-tasup'
GAME_HEAD = re.compile(rb'FTESURF-TASUP 1\nnonce ([0-9a-f]{32})\nsha ([0-9a-f]{64})\npub ([0-9a-f]{64})\nsig ([0-9a-f]{128})\n'
                       rb'game ([0-9a-f]{64})\n')
GAME_HEAD_LEN = 16 + 39 + 69 + 69 + 133 + 70     # the proof is read and checked before the file (P1696 ops review)
GAME_SITE, GAME_KIND = 'play.proto.bar:443', -6
ACCT_STATEMENT = 'FTESURF-ACCT 1\nserver %s\nnonce %s\nkind %d\nkey %d\ncode %s\n'   # surfd accounts.STATEMENT (a test pins it)
GAME_TOOL = 'sent from the game'    # how it came, not what made it: any linked key can sign any file (attack review 2)
CHALLENGE_TTL = 600                 # s a code is good for; it is the service's own MAC, stored only once used
PEER_GAME, GAME_ALL = 20, 1200      # game requests a minute per address; verified game uploads a minute, everyone
GAME_ACCOUNT = 10                   # verified game uploads a minute per account
RELEASES_KEPT = 10                  # the newest releases whose csprogs may sign (a TAS run is made in a local game)
CODE_PATHS = ('ftesurf/csprogs.dat', 'worldofsurf/csprogs.dat')   # its path in a manifest, before and after the rename
CODE_MARK = b'ftesurf-tasup '      # in a csprogs with this upload flow (cl_tasupload.qc TASUp_Signed): no other signs here
CODE_TRIES = 3                      # fetches that gave other bytes than the manifest's before that object is given up
CODE_MAX = 32 * 1024 ** 2
CODE_RETRY, CODE_RETRY_MAX = 600, 3600   # s before a failed release fetch is tried again, doubling to an hour
CODE_FETCH_S = 90                   # s a release object may take in all (urllib's timeout is a read's)
LOBBY_BACKUPS = 2                   # newest csprogs.dat.pre* kept by lobby deploys: a player still on the last build
MANUAL, DENIED = 'manual-', 'deny-' # codes.blake of a build the owner allowed / refused (`allow-code`, `deny-code`)
SQL = '''
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY AUTOINCREMENT, sha TEXT NOT NULL UNIQUE,
 samples_sha TEXT NOT NULL, steamid TEXT NOT NULL, map TEXT NOT NULL, track INTEGER NOT NULL,
 ticks INTEGER NOT NULL, verdict TEXT NOT NULL, state TEXT NOT NULL, reasons TEXT NOT NULL,
 stats TEXT NOT NULL, tool TEXT NOT NULL, size INTEGER NOT NULL, uploaded_at INTEGER NOT NULL,
 reviewed_at INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', sig BLOB NOT NULL);
CREATE INDEX IF NOT EXISTS runs_board ON runs(map, track, state, ticks);
CREATE INDEX IF NOT EXISTS runs_course ON runs(map, track, ticks);
CREATE INDEX IF NOT EXISTS runs_owner ON runs(steamid, id);
CREATE INDEX IF NOT EXISTS runs_recent ON runs(state, id);
CREATE INDEX IF NOT EXISTS runs_motion ON runs(samples_sha);
CREATE TABLE IF NOT EXISTS nonces(nonce TEXT PRIMARY KEY, seen_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS spend(who TEXT NOT NULL, day INTEGER NOT NULL, n INTEGER NOT NULL,
 bytes INTEGER NOT NULL, PRIMARY KEY(who, day));
CREATE TABLE IF NOT EXISTS codes(blake TEXT PRIMARY KEY, sha TEXT NOT NULL, version TEXT NOT NULL, got_at INTEGER NOT NULL);
'''


class Unavailable(Exception):
    """Something this service reads (the account list) could not be read."""


def load_tasplaus():
    tools = os.environ.get('SURFD_TOOLS', str(Path(__file__).resolve().parent.parent / 'tools'))
    if tools not in sys.path: sys.path.insert(0, tools)
    import tasplaus
    return tasplaus


def load_ed25519():
    load_tasplaus()   # the same tools directory on the path
    import ed25519
    return ed25519


def ed25519_verifier():
    """verify(pub, msg, sig) -> bool: the cryptography library's when it is there (python3-cryptography on the Pi: 0.17 ms
    a check against tools/ed25519.py's 5-19 ms, ops review 4), ed25519.py's small-order refusal kept beside it; else
    ed25519.py's own."""
    ed = load_ed25519()
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return ed.verify
    def fast(pub, msg, sig):
        # a key ed25519.py cannot decode is refused too: OpenSSL reduces non-canonical encodings of small-order points
        # mod p and then takes the textbook forgery (review 5)
        if len(pub) != 32 or len(sig) != 64 or ed._point_decompress(pub) is None or ed.small_order(pub): return False
        try:
            Ed25519PublicKey.from_public_bytes(pub).verify(sig, msg)
            return True
        except (InvalidSignature, ValueError):
            return False
    return fast


def game_nonce(nonce, sha):
    """What the game signs for an upload of the file `sha` under the service's `nonce` (cl_tasupload.qc TASUp_Send)."""
    return hashlib.sha256(('ftesurf-tasup %s %s' % (nonce, sha)).encode()).hexdigest()[:32]


def fetch_https(url, cap, timeout=20, total=CODE_FETCH_S):
    """At most cap + 1 bytes of an https URL (a release object) within `total` seconds; no other scheme."""
    if not url.startswith('https://'): raise ValueError('not https')
    end, out = time.monotonic() + total, bytearray()
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'tasupd'}), timeout=timeout) as r:
        if not r.geturl().startswith('https://'): raise ValueError('redirected off https')
        while len(out) <= cap:
            chunk = r.read1(65536)   # one socket read (each within `timeout`): read() waits for the whole 64 KB (ops review 2)
            if not chunk: break
            out += chunk
            if time.monotonic() > end: raise TimeoutError('slower than %d s' % total)
    return bytes(out)


@contextmanager
def connect(path, readonly=False, immutable=False):
    uri = Path(path).resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw') + ('&immutable=1' if immutable else '')
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
    db = sqlite3.connect(path, timeout=15)   # as the service's own connections (an upgrade's init beside the live store)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        with db: db.executescript(SQL)
        with db: db.execute("INSERT OR IGNORE INTO meta(k, v) VALUES ('secret', ?)", (secrets.token_hex(32),))
        if db.execute('PRAGMA user_version').fetchone()[0] < SCHEMA: db.execute('PRAGMA user_version = %d' % SCHEMA)
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


def motion_series(run, mask=None, pos=None):
    """Velocity on the tick grid from the start to the finish, flat [vx, vy, vz, ...]: a sample is taken
    as it is at its nearest tick, ticks between samples are interpolated by time. So the run's motion
    whatever its position offset, header, or samples added, dropped, spaced out or all moved by part
    of a tick (P1640 review 4). At most 2 ticks a sample plus 600 (a sparser file HOLDs for its gaps).
    `mask` (a bytearray) gets 1 for the ticks a sample sits on: only those are compared (interpolation
    across a ramp hit misses: r_34061 at every 2nd sample, 32 of 523 ticks). `pos` (an array) gets
    the positions on the same grid, relative to the first sample: the path itself."""
    s, out, j = run.samples, array('f'), 0
    last = min(run.end, 2 * len(s) + 600)
    near = {}
    for x in s:
        n = math.floor(x[0] / TICK + 0.5 - 1e-7)
        if 0 <= n <= last and n not in near:
            near[n] = x
    o0 = s[0][1]
    for n in range(last + 1):
        t, x = n * TICK, near.get(n)
        if x is not None:
            v, o = x[2], x[1]
        else:
            while j + 1 < len(s) and s[j + 1][0] <= t + 1e-6:
                j += 1
            a = s[j]
            b = s[j + 1] if j + 1 < len(s) else a
            w = min(1.0, (t - a[0]) / (b[0] - a[0])) if b[0] > a[0] and a[0] <= t else 0.0
            v = [a[2][c] + (b[2][c] - a[2][c]) * w for c in range(3)]
            o = [a[1][c] + (b[1][c] - a[1][c]) * w for c in range(3)]
        out.extend(v)
        if pos is not None:
            pos.extend(o[c] - o0[c] for c in range(3))
        if mask is not None:
            mask.append(1 if x is not None else 0)
    return out


def _thin(seq, stride, cap):
    step = max(stride, -(-len(seq) // cap)) if cap else stride
    return seq[::step] if step > 1 else seq


def same_motion(a, b, shifts=8, stride=1, share=0.95, mask=None, sampled=None, cap=COPY_TICKS):
    """b is a's motion, give or take a few ticks: velocity within 2 u/s + 1% on `share` of the overlap,
    on a's sampled ticks (`mask`, or `sampled` built once by the caller), every `stride`th and at most
    `cap` of them (8 with share 0.85 is the cheap first pass)."""
    na, nb = len(a) // 3, len(b) // 3
    if sampled is None:
        sampled = [i for i in range(na) if mask is None or mask[i]]
    for sh in range(-shifts, shifts + 1):
        lo, hi = max(0, sh), min(na, nb + sh)
        if hi - lo < 20 or hi - lo < 0.9 * min(na, nb):
            continue
        ticks = sampled[bisect.bisect_left(sampled, lo):bisect.bisect_left(sampled, hi)]
        if len(ticks) < 10:
            continue
        ticks = _thin(ticks, stride if len(ticks) >= 10 * stride else 1, cap)
        allowed, bad = int(len(ticks) * (1 - share)), 0
        for i in ticks:
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


def path_steps(sampled):
    """Steps between consecutive sampled ticks at most 8 apart: what same_path compares."""
    return [(i, j) for i, j in zip(sampled, sampled[1:]) if j - i <= 8]


def same_path(a, b, shifts=8, stride=1, share=0.95, mask=None, steps=None, cap=COPY_TICKS):
    """b travels a's path, give or take a few ticks: each step between a's sampled ticks moves within
    (2 u/s + 1%) x its time of b's, on `share` of them. Positions only: velocities edited on their own
    (P1640 review 3: 1 deg on 6% of ticks) do not hide it, nor does a constant offset."""
    na, nb = len(a) // 3, len(b) // 3
    if steps is None:
        steps = path_steps([i for i in range(na) if mask is None or mask[i]])
    starts = [i for i, _ in steps]
    for sh in range(-shifts, shifts + 1):
        lo, hi = max(0, sh), min(na, nb + sh)
        if hi - lo < 20 or hi - lo < 0.9 * min(na, nb):
            continue
        use = [st for st in steps[bisect.bisect_left(starts, lo):bisect.bisect_left(starts, hi)] if st[1] < hi]
        if len(use) < 10:
            continue
        use = _thin(use, stride if len(use) >= 10 * stride else 1, cap)
        allowed, bad = int(len(use) * (1 - share)), 0
        for i, j in use:
            g = (j - i) * TICK
            da = [a[3 * j + c] - a[3 * i + c] for c in range(3)]
            db = [b[3 * (j - sh) + c] - b[3 * (i - sh) + c] for c in range(3)]
            tol = 2.0 * g + 0.01 * math.sqrt(sum(x * x for x in da))
            if sum((da[c] - db[c]) ** 2 for c in range(3)) > tol * tol:
                bad += 1
                if bad > allowed:
                    break
        else:
            return True
    return False


def unpack_sig(blob):
    """(velocities, positions) from a stored sig."""
    both = array('f', zlib.decompress(blob))
    half = len(both) // 2
    return both[:half], both[half:]


def copy_of(series, path, mask, rows):
    """(row, why) for the first row (id, steamid, state, sig) whose motion `series` or path `path` is,
    (None, why) when more candidates than COPY_FULL passed the cheap pass and failed the full one (a
    person looks), (None, None) otherwise. Rows may be a cursor. Either matching is a copy."""
    sampled = [i for i in range(len(mask)) if mask[i]]
    steps, full, t0 = path_steps(sampled), 0, time.monotonic()
    for r in rows:
        if time.monotonic() - t0 > COPY_BUDGET:
            return None, 'the copy check ran out of time on this course: the owner compares it'

        vel, pos = unpack_sig(r['sig'])
        for same, mine, theirs, kw in ((same_motion, series, vel, dict(sampled=sampled)),
                                       (same_path, path, pos, dict(steps=steps))):
            if not same(mine, theirs, shifts=COPY_SHIFTS, stride=8, share=0.85, cap=400, **kw):
                continue
            if same(mine, theirs, shifts=COPY_SHIFTS, **kw):
                return r, None
            full += 1
            if full > COPY_FULL:
                return None, 'close to more than %d runs on this course: the owner compares them' % COPY_FULL
    return None, None


_MAXVEL = re.compile(r'^\s*(?:seta?\s+)?sv_maxvelocity\s+"?([0-9]+(?:\.[0-9]+)?)"?', re.M)


def mapcfg_maxvel(dirs, mapname):
    """sv_maxvelocity from the map's cfg/maps/map_<map>.cfg (the first that exists), or None. Never the
    upload's header: that is the uploader's."""
    for d in dirs:
        try:
            with open(os.path.join(d, 'map_%s.cfg' % mapname), 'rb') as fh: body = fh.read(65536)
        except FileNotFoundError:
            continue
        except OSError:
            return None
        body = '\n'.join(l for l in body.decode('utf-8', 'replace').splitlines() if not l.lstrip().startswith('//'))
        got = _MAXVEL.findall(body)
        return float(got[-1]) if got else None
    return None


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


def create_app(store, account_db, zone_dirs, base_url, http=steam.http, clock=time.time, map_cfg_dirs=(),
               game_files=(), releases=None, fetch=fetch_https, verify=None):
    """game_files: csprogs the lobbies serve; releases: the site's releases/ (<version>/update.json) -- the game code
    whose proofs are taken (P1696). verify: an ed25519 module (tests), else tools/ed25519.py."""
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
        if db.execute('PRAGMA user_version').fetchone()[0] < SCHEMA:
            raise RuntimeError('%s is older than this release: run `tasupd.py --store ... init`' % store)
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

    def limited(kind, cap, who=None, n=1):
        minute = int(clock() // 60)
        k = (kind, peer() if who is None else who, minute)
        with hits_lock:
            if len(hits) > HITS_MAX:
                for old in [x for x in hits if x[2] < minute]: del hits[old]
                # Still full: this minute's flood came from that many addresses. A new one goes uncounted
                # rather than everyone being refused; the shared 'everyone' budgets are always counted.
                if len(hits) > HITS_MAX and k not in hits and who != 'everyone': return False
            hits[k] = hits.get(k, 0) + n
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

    def read_surfd(sql, args=()):
        """Rows from surfd.db (accounts, the board's runs), read-only. P1618 (AGENT_NOTES): once surfd's last close deletes -wal/-shm this
        sandbox cannot recreate them and a plain read-only open fails; with no -wal the file is whole, so read
        it immutable (tools/r2gateway.py read_row)."""
        try:
            try:
                with connect(account_db, readonly=True) as adb: return adb.execute(sql, args).fetchall()
            except sqlite3.OperationalError:
                if Path(str(account_db) + '-wal').exists(): raise
            with connect(account_db, readonly=True, immutable=True) as adb: return adb.execute(sql, args).fetchall()
        except sqlite3.Error as e:
            raise Unavailable('surfd.db cannot be read (%s)' % type(e).__name__)

    def course_record(mapname, track):
        """surfd's best whole-course time (ms) on this course in any tier, or None; raises Unavailable."""
        got = read_surfd('SELECT MIN(millis) FROM runs WHERE map = ? AND track = ? AND leg = 0 AND millis > 0'
                         ' AND tier IN (%s) AND style IN (%s)' % (','.join('?' * len(TIERS_RECORD)), ','.join('?' * len(STYLES_RECORD))),
                         (mapname, track) + TIERS_RECORD + STYLES_RECORD)
        return got[0][0] if got and got[0][0] else None

    def accounts_of(steamids):
        """{steamid: (name, banned)} for the ones World of Surf knows; raises Unavailable."""
        want = sorted(set(steamids))
        out, now = {}, clock()
        with names_lock:
            miss = [s for s in want if s not in names or names[s][1] < now - NAME_TTL]
            out.update({s: names[s][0] for s in want if s not in miss and names[s][0] is not None})
        if miss:
            rows = {}
            for i in range(0, len(miss), 500):
                chunk = miss[i:i + 500]
                rows.update({r['steamid']: (r['name'] or '', bool(r['banned_at'])) for r in read_surfd(
                    'SELECT steamid, name, banned_at FROM accounts WHERE steamid IN (%s)' % ','.join('?' * len(chunk)), chunk)})
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
        return g.get('game') or request.path.startswith(base + '/api/') or (
            request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json')

    def refuse(message, status, reasons=None):
        # P1696: the game's HTTP client drops a non-200 reply's body (zonepub.py P826): the status goes inside. A body
        # still unread is read first, whichever path refuses (the error handlers too: ops review 3)
        if g.get('game'):
            if not g.get('read'):
                g.read = True
                try:
                    while request.stream.read(65536): pass
                except Exception: pass
            return jsonify(ok=0, error=message, status=status, reasons=reasons or []), 200
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
        if request.method == 'POST' and request.path == base + '/api/game/challenge':
            g.game = True
            if limited('game', PEER_GAME): return refuse('Too many requests; try again in a minute.', 429)   # codes cost nothing
        if request.method == 'POST' and request.path == base + '/upload' and request.mimetype == GAME_MIME:
            g.game = True   # the proof is in the body: game_upload reads it
            # Werkzeug 2.2.2's get_data does not hold MAX_CONTENT_LENGTH (zonepub.py body_budget); nginx sends the length
            size = request.content_length
            if size is None or size <= 0: return refuse('Request length required.', 411)
            if size > MAX_FORM: return drained('That file is over %d MB.' % (MAX_REC // 1024 ** 2), 413)
            if limited('game', PEER_GAME): return drained('Too many requests; try again in a minute.', 429)
            return None
        if request.method == 'POST' and request.path == base + '/upload':
            if not session(): return refuse('Sign in with Steam first.', 401)   # before reading 8 MB
            # Read the body once and count its parts before Werkzeug parses it (2.2.2: no part cap).
            boundary = request.mimetype_params.get('boundary', '')
            if request.mimetype != 'multipart/form-data' or not boundary:
                return refuse('Upload the file with the form.', 400)
            if request.get_data(cache=True).count(b'--' + boundary.encode('latin-1', 'replace')) > FORM_PARTS:
                return refuse('That form has too many parts.', 400)

    def drained(message, status):
        """refuse() of a game request whose body is unread: refuse reads it first (nginx may still be sending it, and a
        reply then can reach the game as a 502: ops review 2), bounded by nginx's client_max_body_size."""
        return refuse(message, status)

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
        rows = db.execute("SELECT " + LIST + " FROM runs WHERE map = ? AND track = ? AND state = 'shown'"
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
        rows = db.execute("SELECT " + LIST + " FROM runs WHERE state = 'shown' ORDER BY id DESC LIMIT ?", (limit * 2,)).fetchall()
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
            mine = db.execute('SELECT ' + LIST + ' FROM runs WHERE steamid = ? ORDER BY id DESC LIMIT 50', (sid,)).fetchall() if sid else []
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

    @app.get(base + '/api/health')
    def api_health():
        try:
            with connect(store) as db: db.execute('SELECT COUNT(*) FROM runs').fetchone()
            read_surfd('SELECT steamid, name, banned_at FROM accounts LIMIT 1')
            read_surfd('SELECT map, track, leg, style, millis FROM runs LIMIT 1')
        except (sqlite3.Error, Unavailable) as e:
            return jsonify(ok=0, why=str(e) if isinstance(e, Unavailable) else type(e).__name__), 503
        return jsonify(ok=1, store=1, accounts=1)

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
        with connect(store) as db: r = db.execute('SELECT ' + ROW + ' FROM runs WHERE id = ?', (rid,)).fetchone()
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
        # 8 MiB a file on the lobbies' uplink: budgeted in bytes, not requests.
        if limited('recbytes', REC_PEER_BYTES, n=r['size']) or limited('recbytes', REC_ALL_BYTES, who='everyone', n=r['size']):
            return refuse('Too many downloads; try again in a minute.', 429)
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
                db.execute("DELETE FROM nonces WHERE seen_at < ? AND nonce NOT LIKE 'game %'", (now - 4 * steam.NONCE_SKEW,))
                try: db.execute('INSERT INTO nonces(nonce, seen_at) VALUES (?, ?)', (nonce, now))
                except sqlite3.IntegrityError: raise steam.Refused('nonce seen')
            if limited('steampeer', PEER_STEAM):   # one address cannot spend everyone's minute
                return refuse('Too many sign-ins; try again in a minute.', 429)
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

    def unspend(sid, now):
        with spend_lock, connect(store) as db, writing(db):
            db.execute('UPDATE spend SET n = MAX(0, n - 1) WHERE who = ? AND day = ?', (sid, int(now // 86400)))

    def stored(db):
        return db.execute('SELECT COALESCE(SUM(size + LENGTH(sig)), 0) FROM runs').fetchone()[0]

    def kept(db, sid, size, now):
        db.execute('UPDATE spend SET bytes = bytes + ? WHERE who = ? AND day = ?', (size, sid, int(now // 86400)))

    uploading = threading.BoundedSemaphore(UPLOADS_AT_ONCE) if UPLOADS_AT_ONCE else None
    inflight, inflight_lock = set(), threading.Lock()   # one upload at a time per account (review 7: two held both slots)

    # ---- P1696: the game's upload. The csprogs that may sign: the lobbies' files, and released ones, whose manifests
    # name them by BLAKE2b (updatefeed.py) -- fetched once from the release mirror and kept by SHA-256 in `codes`. ----
    file_codes, codes_lock, fetching = {}, threading.Lock(), threading.Lock()
    fetch_failed = {}

    def lobby_files():
        """game_files, a pattern among them as its newest LOBBY_BACKUPS matches (csprogs.dat.pre*: the deploys' copies)."""
        out = []
        for f in game_files:
            if '*' not in f: out.append(Path(f)); continue
            try: got = sorted(Path(f).parent.glob(Path(f).name), key=lambda p: p.stat().st_mtime, reverse=True)
            except OSError: continue
            out += got[:LOBBY_BACKUPS]
        return out

    def lobby_codes():
        """(the SHA-256s of the lobby files that carry the upload flow, whether any file could be read at all)"""
        out, seen = set(), False
        for p in lobby_files():
            try:
                # No links; read once, and only if it did not change while read (zonepub.py known_game).
                if p.is_symlink() or not p.is_file(): continue
                st = p.stat()
                ident = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
                with codes_lock: got = file_codes.get(str(p))
                if got and got[0] == ident:
                    seen = True
                    if got[1]: out.add(got[1])
                    continue
                if st.st_size > CODE_MAX: continue
                with p.open('rb') as f:
                    before = os.fstat(f.fileno()); data = f.read(CODE_MAX + 1); after = os.fstat(f.fileno())
                same = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
                if same(before) != ident or same(after) != ident or len(data) > CODE_MAX: continue
                h = hashlib.sha256(data).hexdigest() if CODE_MARK in data else ''   # an older build signs nothing here
                with codes_lock: file_codes[str(p)] = (ident, h)
                seen = True
                if h: out.add(h)
            except OSError:
                continue
        return out, seen

    manifests = {}

    def release_list():
        """[(version, blake2b of its csprogs, object url)] for the newest RELEASES_KEPT manifests; unreadable ones skipped.
        Parsed again only when a manifest file changes (each is ~250 KB: attack review)."""
        if not releases: return []
        try: dirs = [d for d in Path(releases).iterdir() if re.fullmatch(r'[0-9]{1,4}(\.[0-9]{1,6}){2}', d.name)]
        except OSError: return []
        dirs = sorted(dirs, key=lambda d: tuple(int(x) for x in d.name.split('.')), reverse=True)[:RELEASES_KEPT]
        try: key = tuple((d.name, (d / 'update.json').stat().st_mtime_ns) for d in dirs if (d / 'update.json').is_file())
        except OSError: key = None
        with codes_lock:
            if key is not None and manifests.get('key') == key: return manifests['found']
        found = []
        for d in dirs:
            try:
                with (d / 'update.json').open('rb') as f: raw = f.read(8 * 1024 ** 2 + 1)
                pay = json.loads(json.loads(raw)['payload'])
                if pay.get('hash_algo') != 'blake2b-256' or pay.get('object_layout') != 'objects/{h0h1}/{hash}': continue
                # one csprogs, or one a platform (a Windows-only release keeps Linux's older one: flow review 2)
                cs = {x.get('hash') for x in pay.get('files', []) if isinstance(x, dict) and x.get('path') in CODE_PATHS}
                mirror = next((m for m in pay.get('mirrors', []) if isinstance(m, str) and m.startswith('https://')), None)
                if mirror and 1 <= len(cs) <= 4 and all(isinstance(h, str) and re.fullmatch('[0-9a-f]{64}', h) for h in cs):
                    found += [(d.name, h, '%s/objects/%s/%s' % (mirror.rstrip('/'), h[:2], h)) for h in sorted(cs)]
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue
        if key is not None:
            with codes_lock: manifests.update(key=key, found=found)
        return found

    def missing_releases():
        rel = release_list()
        if not rel: return rel, [], []
        with connect(store) as db:
            have = {r['blake'] for r in db.execute('SELECT blake FROM codes WHERE blake IN (%s)' % ','.join('?' * len(rel)),
                                                   [b for _v, b, _u in rel])}
        # (rel, not learned and not given up, of those the ones due a fetch). fetch_failed: blake -> (when, network fails,
        # wrong-bytes fails); only the mirror serving other bytes gives up -- a network outage never does (ops review 2)
        now = clock()
        todo = [x for x in rel if x[1] not in have and fetch_failed.get(x[1], (0, 0, 0))[2] < CODE_TRIES]
        due = lambda f: f is None or now - f[0] >= min(CODE_RETRY_MAX, CODE_RETRY * 2 ** max(0, f[1] + f[2] - 1))
        return rel, todo, [x for x in todo if due(fetch_failed.get(x[1]))]   # one read: the learner pops (ops review 3)

    def learn_releases():
        """Fetch the csprogs of releases not yet known, one caller at a time (a challenge's thread, in the background)."""
        if not fetching.acquire(blocking=False): return
        try:
            done = set()
            for version, blake, url in missing_releases()[2]:
                if blake in done: continue     # two releases with one csprogs: fetched once (ops review 4)
                _when, net, wrong = fetch_failed.get(blake, (0, 0, 0))
                try: data = fetch(url, CODE_MAX)
                except urllib.error.HTTPError as e:
                    # the mirror answered: an object it says is not there counts as given-up-able (flow review 3: a 404
                    # said "try again" forever, never "update your game"); its other errors are an outage
                    gone = e.code in (404, 410)    # a 403 can be the CDN's bot wall: an outage (ops review 4)
                    fetch_failed[blake] = (clock(), net + (not gone), wrong + gone)
                    app.logger.warning('tasupd: release %s csprogs: the mirror answered %d', version, e.code)
                    continue
                except Exception as e:
                    fetch_failed[blake] = (clock(), net + 1, wrong)
                    app.logger.warning('tasupd: release %s csprogs not fetched (%s); tried again later', version, type(e).__name__)
                    continue
                if len(data) > CODE_MAX or hashlib.blake2b(data, digest_size=32).hexdigest() != blake:
                    fetch_failed[blake] = (clock(), net, wrong + 1)
                    app.logger.warning('tasupd: release %s csprogs: the mirror gave other bytes (%d of %d)', version, wrong + 1, CODE_TRIES)
                    continue
                # a release without this upload flow is known too (not fetched again), and matches nothing
                marked = CODE_MARK in data
                try:
                    with connect(store) as db, writing(db):
                        db.execute('INSERT OR REPLACE INTO codes(blake, sha, version, got_at) VALUES (?, ?, ?, ?)',
                                   (blake, hashlib.sha256(data).hexdigest() if marked else '', version, int(clock())))
                except sqlite3.Error as e:   # the store, not the mirror: the next challenge tries again
                    app.logger.warning('tasupd: release %s csprogs not kept (%s)', version, type(e).__name__)
                    continue
                fetch_failed.pop(blake, None)
                done.add(blake)                # learned: a failed one may still come from another release's mirror
                app.logger.info('tasupd: release %s csprogs learned%s', version, '' if marked else ' (no upload flow)')
        finally:
            fetching.release()

    def known_game(code):
        """True, False, or None when nothing could be read to say (no lobby file, no release known or waiting)."""
        with connect(store) as db:
            if db.execute('SELECT 1 FROM codes WHERE blake = ?', (DENIED + code,)).fetchone(): return False   # the owner's word
        lob, seen = lobby_codes()
        if code in lob: return True
        rel, unknown, waiting = missing_releases()
        if rel:
            with connect(store) as db:
                if db.execute('SELECT 1 FROM codes WHERE sha = ? AND blake IN (%s)' % ','.join('?' * len(rel)),
                              [code] + [b for _v, b, _u in rel]).fetchone():
                    return True
        with connect(store) as db:
            if db.execute('SELECT 1 FROM codes WHERE sha = ? AND blake = ?', (code, MANUAL + code)).fetchone(): return True
        # A release not learned yet (or whose fetch failed, up to CODE_TRIES) may be this one: "try again", never
        # "update your game" to a player on the newest release (flow review)
        if waiting: threading.Thread(target=learn_releases, daemon=True).start()
        if unknown: return None
        return False if (seen or rel) else None

    verifier = []

    def signature(pub, signed, code, sig):
        if not verifier:
            try: verifier.append(verify.verify if verify is not None else ed25519_verifier())
            except ImportError: return None
        message = (ACCT_STATEMENT % (GAME_SITE, signed, GAME_KIND, 1, code)).encode()
        try: return bool(verifier[0](bytes.fromhex(pub), message, bytes.fromhex(sig)))
        except Exception: return False

    def key_account(pub):
        """(steamid, banned) the linked key answers to, or ('', False); raises Unavailable."""
        rows = read_surfd('SELECT k.steamid, a.banned_at FROM keylinks k JOIN accounts a ON a.steamid = k.steamid'
                          ' WHERE k.pub = ?', (pub,))
        return (rows[0]['steamid'], bool(rows[0]['banned_at'])) if rows else ('', False)

    def game_token(stamp, salt, sha):
        return '%08x%s%s' % (stamp, salt, mac('game', '%08x' % stamp, salt, sha)[:16])

    @app.post(base + '/api/game/challenge')
    def game_challenge():
        """A code for one file: its time, 8 hex of salt and the service's MAC over them and the file's hash. Nothing is
        stored here (ops review: a table of them was 32 addresses from full); a use is recorded once it proves an account."""
        data = request.get_json(silent=True)
        sha = data.get('sha') if isinstance(data, dict) else None
        if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha): return refuse('Invalid request.', 400)
        if missing_releases()[2]: threading.Thread(target=learn_releases, daemon=True).start()   # ready by the press
        return jsonify(ok=1, nonce=game_token(int(clock()), secrets.token_hex(4), sha), sha=sha)

    def game_upload():
        head = request.stream.read(GAME_HEAD_LEN)
        m = GAME_HEAD.fullmatch(head)
        if not m: return drained('That upload carries no account proof: update your game.', 400)
        nonce, sha, pub, sig, code = (x.decode('ascii') for x in m.groups())
        now, stamp = int(clock()), int(nonce[:8], 16)
        if not (0 <= now - stamp <= CHALLENGE_TTL and hmac.compare_digest(nonce, game_token(stamp, nonce[8:16], sha))):
            return drained('That upload\'s confirmation expired or is not this file\'s: press Upload again.', 409)
        burned = 'game ' + nonce
        with connect(store) as db:
            if db.execute('SELECT 1 FROM nonces WHERE nonce = ?', (burned,)).fetchone():
                return drained('That upload\'s confirmation was used: press Upload again.', 409)
        known = known_game(code)
        if known is None: return drained('The upload service is still reading the game versions; try again in a minute.', 503)
        if not known: return drained('Update your game before uploading from it.', 403)
        # the key's account before its signature: an unlinked key costs a query, not a pure-Python verify (attack review 4)
        sid, banned = key_account(pub)
        if not sid: return drained('Link your Steam account first (play.proto.bar/board/link), then upload again.', 403)
        good = signature(pub, game_nonce(nonce, sha), code, sig)
        if good is None: return drained('The upload service cannot check account proofs right now.', 503)
        if not good: return drained('The account proof did not check out.', 403)
        if banned: return drained('This Steam account cannot upload.', 403)   # after the proof: a ban is not anyone's to probe
        # an account's own minute, then everyone's: proofs that verified only (review 4), and one account from many
        # addresses cannot fill everyone's (review 5)
        if limited('gameacct', GAME_ACCOUNT, sid) or limited('game', GAME_ALL, 'everyone'):
            return drained('The upload service is busy; try again in a minute.', 429)
        try:
            with connect(store) as db, writing(db):
                db.execute("DELETE FROM nonces WHERE nonce LIKE 'game %' AND seen_at < ?", (now - CHALLENGE_TTL - 60,))   # past its code's life
                db.execute('INSERT INTO nonces(nonce, seen_at) VALUES (?, ?)', (burned, now))
        except sqlite3.IntegrityError:
            return drained('That upload\'s confirmation was used: press Upload again.', 409)
        # Only now the file: an account has proved it, and the one code is spent
        data = request.stream.read(MAX_REC + 1)
        g.read = len(data) <= MAX_REC     # more: the rest is drained by the refusal
        if len(data) > MAX_REC: return drained('That file is over %d MB.' % (MAX_REC // 1024 ** 2), 413)
        if not hmac.compare_digest(hashlib.sha256(data).hexdigest(), sha):
            return refuse('The file is not the one confirmed: press Upload again.', 409)
        return one_at_a_time(sid, lambda: accept(sid, data, None))

    def one_at_a_time(sid, work):
        with inflight_lock:
            if sid in inflight: return refuse('Your other upload is still being checked; wait for it.', 429)
            inflight.add(sid)
        try:
            if uploading is None or not uploading.acquire(blocking=False):
                return refuse('Two uploads are being checked; try again in a minute.', 503)
            try: return work()
            finally: uploading.release()
        finally:
            with inflight_lock: inflight.discard(sid)

    @app.post(base + '/upload')
    def upload():
        if g.get('game'): return game_upload()
        sid = session()
        if not sid: return refuse('Sign in with Steam first.', 401)
        return one_at_a_time(sid, lambda: upload_signed_in(sid))

    def upload_signed_in(sid):
        if not post_ok(): return refuse('That form is out of date; reload the page.', 403)
        acct = accounts_of([sid]).get(sid)
        if acct is None or acct[1]: return refuse('This Steam account cannot upload.', 403)
        f = request.files.get('rec')
        if f is None: return refuse('Choose a .rec file.', 400)
        body = f.read(MAX_REC + 1)
        if len(body) > MAX_REC: return refuse('That file is over %d MB.' % (MAX_REC // 1024 ** 2), 413)
        tool = clean_tool(request.form.get('tool'))
        if tool.lower() == GAME_TOOL: tool += ' (typed)'   # the game's own label is the game route's (attack review 3)
        return accept(sid, body, tool)

    def accept(sid, body, tool):
        """Check, compare and keep one upload of `sid`'s, from the form or the game (tool None)."""
        now = int(clock())
        with spend_lock, connect(store) as db, writing(db):
            over = spend(db, sid, now)
        if over: return refuse(over, 429)
        if b'\x00' in body or not body.startswith(b'FTESURF-REC '): return refuse('That is not a FTESURF-REC recording.', 400)
        # The header from a bounded prefix, the samples plain ASCII: one wide character would otherwise
        # make the whole 8 MB text 4 bytes a character (review 4: four at once past MemoryMax).
        m = BEGIN_LINE.search(body, 0, HEADER_MAX)   # a line whose first word is begin, as tasplaus reads it
        cut = m.start() if m else -1
        if cut < 0: return refuse('The recording has no header (no begin line in its first %d KB).' % (HEADER_MAX // 1024), 400)
        try: head = body[:cut + 1].decode('utf-8')
        except UnicodeDecodeError: return refuse('That is not a text .rec file.', 400)
        if not body[cut + 1:].isascii(): return refuse('After the header a .rec is plain ASCII.', 400)
        pre = tp.read(text=head + 'begin\n', header_only=True)   # the checker's own header reader
        text = head.encode('ascii', 'replace').decode('ascii') + body[cut + 1:].decode('ascii')
        if not pre.has_body: return refuse('The recording has no header (no begin line).', 400)
        if pre.dups: return refuse('The header gives %s twice.' % ', '.join(sorted(pre.dups)), 400)
        if pre.odd_breaks: return refuse('The file has line breaks or spaces other than newline, space and tab.', 400)
        hdr = pre.hdr
        if tool is None: tool = GAME_TOOL
        mapname = (hdr.get('map') or '').strip().lower()
        if not MAPNAME.fullmatch(mapname): return refuse('The header names no usable map.', 400)
        track = tp.hdr_int(hdr, 'track', -1) if 'track' in hdr else 0
        if not 0 <= track <= MAX_TRACK: return refuse('The header names no usable track.', 400)
        if tp.hdr_int(hdr, 'leg') or tp.hdr_int(hdr, 'startseg'):
            return refuse('This board takes whole courses: a stage leg (leg or startseg in the header) cannot be uploaded.', 400)
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
            dup = db.execute('SELECT id, steamid, state FROM runs WHERE sha = ?', (sha,)).fetchone()
            if dup:   # review 8: the usual duplicate is the uploader's own double submit or retry
                return refuse(('You uploaded this file already: run %d%s.' % (dup['id'], ', which the owner removed' if dup['state'] == 'removed'
                               else '')) if dup['steamid'] == sid else DUPLICATE, 409)
        if not heavy.acquire(timeout=HEAVY_WAIT):
            unspend(sid, now)   # not the uploader's attempt
            return refuse('The checker is busy; try again in a minute.', 503)
        try:
            run = tp.read(text=text)
            del text   # the parse holds what is needed; 8 MB of str less while the check runs
            if run.end is None or not 0 < run.end <= tp.MAX_TICKS or len(run.samples) < 3:
                res = tp.check(run, None)   # refuses it, saying why
            else:
                try:
                    zones = zones_for(zone_dirs, mapname)
                    caps = [x for x in ((zones or {}).get('maxVelocity'), mapcfg_maxvel(map_cfg_dirs, mapname))
                            if isinstance(x, (int, float)) and x > 0]
                    res = tp.check(run, zones, maxvel=max(caps) if caps else None)
                except Exception as e:   # e.g. a zone file with the wrong types: cannot see, so a person looks
                    app.logger.exception('tasplaus failed on an upload for %s', mapname)
                    res = {'verdict': tp.HOLD, 'stats': {}, 'reasons': [
                        {'level': tp.HOLD, 't': None, 'what': 'the checker could not finish (%s)' % type(e).__name__}]}
            # Only these leave the slot: the parsed samples go before the next upload's check starts.
            end = run.end
            if res['verdict'] != tp.FAIL:
                mask, trail = bytearray(), array('f')
                vel = motion_series(run, mask, trail)
                digest, sig = samples_digest(run), zlib.compress(vel.tobytes() + trail.tobytes())
                del vel, trail
            del run
        finally:
            heavy.release()
        reasons, unlisted = res['reasons'], res.get('unlisted', 0)
        more = max(0, len(reasons) - REASONS_MAX) + unlisted
        if more:
            reasons = reasons[:REASONS_MAX] + [{'level': tp.FAIL if res['verdict'] == tp.FAIL else tp.HOLD,
                                                't': None, 'what': '%d more not listed' % more}]
        if res['verdict'] == tp.FAIL:
            return refuse('The physics check refused it.', 422, reasons)
        series, trail = unpack_sig(sig)
        state = 'shown' if res['verdict'] == tp.PASS else 'held'
        lo, hi = end - max(30, end // 10), end + max(30, end // 10)
        # At most COPY_PER_PLAYER nearest in length per other account, shown and removed ones first: a few
        # accounts' parked runs cannot push the run being copied out of the candidates (review 4).
        # Without sig: selected under ORDER BY ... LIMIT the blobs went to a temp file (review 6: 60 x 7 MB); with_sigs
        # reads them one at a time as copy_of goes.
        course_sql = ('SELECT r.id, r.steamid, r.state FROM (SELECT id, ticks, state, ROW_NUMBER() OVER'
                      ' (PARTITION BY steamid ORDER BY ABS(ticks - ?), id) AS rk FROM runs WHERE map = ? AND track = ?'
                      " AND ticks BETWEEN ? AND ? AND (steamid != ? OR state = 'removed') AND id > ?) c"
                      ' JOIN runs r ON r.id = c.id WHERE c.rk <= %d'
                      " ORDER BY c.state IN ('shown', 'removed') DESC, ABS(c.ticks - ?), c.id LIMIT %d"
                      % (COPY_PER_PLAYER, COPY_CANDIDATES))

        def with_sigs(db, rows):
            for r in [tuple(x) for x in rows]:
                x = db.execute('SELECT id, steamid, state, sig FROM runs WHERE id = ?', (r[0],)).fetchone()
                if x is not None: yield x

        def own_rows(db, states, after=0, earliest=False):
            order = 'id' if earliest else 'ABS(ticks - ?), id'   # earliest: the first match is the oldest (review 9)
            return with_sigs(db, db.execute('SELECT id FROM runs WHERE steamid = ? AND map = ? AND track = ? AND ticks BETWEEN ? AND ?'
                                            ' AND state IN (%s) AND id > ? ORDER BY %s LIMIT ?' % (','.join('?' * len(states)), order),
                                            (sid, mapname, track, lo, hi) + states + (after,) + (() if earliest else (end,)) + (COPY_PER_PLAYER,)))

        def owns_motion(db):
            """(shown, held id): whether the uploader has a SHOWN run of this motion (the same samples, or a copy match
            among their nearest runs on the course), and the earliest held one. Another account's removed or rejected
            copy does not refuse an owner of the motion, whatever the order (review 6); a held run counts only against
            copies made after it (review 7: a held offset copy unlocked the removed samples; review 8: the author's own
            first upload, held as the course's first, was refused once a copier's later run was removed)."""
            if db.execute("SELECT 1 FROM runs WHERE samples_sha = ? AND steamid = ? AND state = 'shown'", (digest, sid)).fetchone():
                return True, None
            if copy_of(series, trail, mask, own_rows(db, ('shown',)))[0] is not None:
                return True, None
            h = db.execute("SELECT MIN(id) FROM runs WHERE samples_sha = ? AND steamid = ? AND state = 'held'", (digest, sid)).fetchone()[0]
            if h is None:
                m = copy_of(series, trail, mask, own_rows(db, ('held',), earliest=True))[0]
                h = m['id'] if m is not None else None
            return False, h

        def copied(db, after, owns):
            """A refusal (motion the owner removed), a reason to hold it (another player's motion, the uploader's own
            rejected motion, or too close to too many runs to tell), or None. Own runs are the uploader's to improve or
            re-export. A match is held, not refused: two bots on one course may converge, and the owner decides."""
            rej = db.execute("SELECT id FROM runs WHERE samples_sha = ? AND steamid = ? AND state = 'rejected' AND id > ?",
                             (digest, sid, after)).fetchone()
            if rej is None:     # review 6: a sample past the finish, or one moved 0.06 u, slipped past the hash
                rej = copy_of(series, trail, mask, own_rows(db, ('rejected',), after))[0]
            if rej is not None:
                return 'the same motion as your run %d, which the owner rejected' % rej['id']
            # another account's removed or rejected run of motion the uploader owns is no claim on it (review 7: after an
            # unblock the copier's rejected row held every later upload of the approved author)
            shown_own, held_id = owns
            def theirs_removed(x):   # (id, steamid, state) rows of another account the uploader's motion came first
                return (x[2] in ('removed', 'rejected') and x[1] != sid
                        and (shown_own or (held_id is not None and held_id < x[0])))
            r = next((x for x in db.execute("SELECT id, steamid, state FROM runs WHERE samples_sha = ? AND (steamid != ? OR"
                                            " state = 'removed') AND id > ? ORDER BY state = 'removed' DESC", (digest, sid, after))
                      if not theirs_removed(x)), None)
            why = None
            if r is None:
                cand = [tuple(x) for x in db.execute(course_sql, (end, mapname, track, lo, hi, sid, after, end))]
                cand = [x for x in cand if not theirs_removed(x)]
                r, why = copy_of(series, trail, mask, with_sigs(db, cand))
            if r is not None and r['state'] == 'removed':
                return refuse('That is the motion of run %d, which the owner removed: if it is your own run, ask the owner.'
                              % r['id'], 409)
            if r is not None:
                return 'the motion of run %d (another player\'s), with small changes: the owner decides whose it is' % r['id']
            return why

        # Compared before the write lock (P1640 review: a long course could hold it past SQLite's
        # timeout) and in the checker's slot (four at once took 1 GB); inside the lock only the rows
        # added meanwhile.
        if not heavy.acquire(timeout=HEAVY_WAIT):
            unspend(sid, now)
            return refuse('The checker is busy; try again in a minute.', 503)
        try:
            with connect(store) as db:
                seen = db.execute('SELECT COALESCE(MAX(id), 0) FROM runs').fetchone()[0]
                owns = owns_motion(db)
                copy = copied(db, 0, owns)
        finally:
            heavy.release()
        if copy is not None and not isinstance(copy, str): return copy
        record, record_why = None, None
        try: record = course_record(mapname, track)
        except Unavailable as e: record_why = str(e)
        path = rec_path(store, sha)
        path.parent.mkdir(mode=0o700, exist_ok=True)
        committed = placed = False
        try:
            with connect(store) as db, writing(db):
                again = copied(db, seen, owns)
                if again is not None and not isinstance(again, str): return again
                for why in (copy, again):
                    if isinstance(why, str):
                        state = 'held'
                        reasons = reasons + [{'level': tp.HOLD, 't': None, 'what': why}]
                # Without the map's walls a made-up path can pass the physics: a time that reaches the best
                # known (surfd's record, or the best upload shown here) waits for the owner. A run held for
                # physics carries the note too, so an approval knows it makes a record.
                mine = end * TICK * 1000
                shown = db.execute("SELECT MIN(ticks) FROM runs WHERE map = ? AND track = ? AND state = 'shown'",
                                   (mapname, track)).fetchone()[0]
                known = [x for x in (record, shown * TICK * 1000 if shown else None) if x]
                best = min(known) if known else None
                # The uploader's own shown motion again is not a new time -- unless it claims a faster finish
                # than that run showed: the same samples may end anywhere the end-zone slack allows (review 5).
                again_ticks = db.execute("SELECT MIN(ticks) FROM runs WHERE steamid = ? AND samples_sha = ? AND state = 'shown'"
                                         " AND map = ? AND track = ?", (sid, digest, mapname, track)).fetchone()[0]
                if again_ticks is not None and end >= again_ticks:
                    record_why, best = None, mine - 1
                why = ('the course record could not be read (%s)' % record_why if record_why else
                       'no other time on this course to compare with: the first upload waits for the owner' if best is None else
                       '%s the best known time on this course (%s): a new record waits for the owner'
                       % ('matches' if mine > best - 0.5 else 'faster than', fmt_time(best / 1000)) if mine <= best + 0.5 else None)
                if why:
                    state = 'held'
                    reasons = reasons + [{'level': tp.HOLD, 't': None, 'what': why}]
                if state == 'held' and db.execute("SELECT COUNT(*) FROM runs WHERE steamid = ? AND state = 'held'",
                                                  (sid,)).fetchone()[0] >= HELD_CAP:
                    # the attempt counts (review 7: refunded, an account at the cap looped full checks past the day's 30)
                    return refuse('You have %d runs waiting for review; wait for those first.' % HELD_CAP, 429)
                if stored(db) + len(body) + len(sig) > STORE_CAP:   # the motion blob is on the same disk
                    app.logger.warning('tasupd store full (%d bytes): uploads refused until runs are removed', STORE_CAP)
                    return refuse('The upload store is full; try again later.', 507)
                cur = db.execute('INSERT INTO runs(sha, samples_sha, steamid, map, track, ticks, verdict, state, reasons,'
                                 ' stats, tool, size, uploaded_at, sig) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                 (sha, digest, sid, mapname, track, end, res['verdict'], state,
                                  json.dumps(reasons), json.dumps(res['stats']), tool, len(body), now, sig))
                rid = cur.lastrowid
                kept(db, sid, len(body) + len(sig), now)
                tmp = path.with_name(path.name + '.%s.tmp' % secrets.token_hex(4))
                try:
                    with open(tmp, 'xb') as fh:
                        fh.write(body); fh.flush(); os.fsync(fh.fileno())
                    os.replace(tmp, path)
                    placed = True
                    dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                    try: os.fsync(dfd)   # the name too, before the row commits
                    finally: os.close(dfd)
                finally:
                    if tmp.exists(): tmp.unlink()
            committed = True
        except sqlite3.IntegrityError:
            return refuse(DUPLICATE, 409)
        except OSError:
            app.logger.exception('tasupd could not store an upload')
            return refuse('The file could not be stored; try again later.', 503)
        finally:
            if not committed and placed and path.exists():
                # Only a file this request put there (one that timed out waiting must not delete another's);
                # content-addressed, so kept if a committed row (a concurrent upload of these bytes) names it.
                with connect(store) as db:
                    if not db.execute('SELECT 1 FROM runs WHERE sha = ?', (sha,)).fetchone(): path.unlink()
        if wants_json():
            return jsonify(ok=1, id=rid, state=state, verdict=res['verdict'], reasons=reasons, time=round(end * TICK, 3),
                           map=mapname, track=track, page='%s/run/%d' % (base_url.rstrip('/'), rid))
        return redirect('%s/run/%d' % (base, rid), 303)

    return app


def main(argv=None):
    ap = argparse.ArgumentParser(description='Owner tools for the TAS upload store.')
    ap.add_argument('--store', required=True)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init')
    ls = sub.add_parser('list'); ls.add_argument('--state', default='held', choices=STATES + ('all',)); ls.add_argument('--limit', type=int, default=50)
    sh = sub.add_parser('show'); sh.add_argument('id', type=int)
    for name in ('approve', 'reject', 'remove', 'unblock'):
        p = sub.add_parser(name); p.add_argument('id', type=int); p.add_argument('--note', default='')
    # P1696: a build whose game uploads are taken besides the lobbies' and the releases' (an owner's dev install)
    ac = sub.add_parser('allow-code'); ac.add_argument('sha'); ac.add_argument('--note', default='')
    dc = sub.add_parser('deny-code'); dc.add_argument('sha')
    sub.add_parser('codes')
    a = ap.parse_args(argv)
    if a.cmd == 'init':
        initialize(a.store); print('initialized', a.store); return 0
    if not Path(a.store).is_file():
        print('no store at', a.store); return 1
    with connect(a.store) as db:
        if a.cmd in ('allow-code', 'deny-code'):
            sha = a.sha.lower()
            if not re.fullmatch('[0-9a-f]{64}', sha): print('a csprogs.dat SHA-256: 64 hex digits'); return 1
            with writing(db):
                if a.cmd == 'allow-code':
                    db.execute('DELETE FROM codes WHERE blake = ?', (DENIED + sha,))
                    db.execute('INSERT OR REPLACE INTO codes(blake, sha, version, got_at) VALUES (?, ?, ?, ?)',
                               (MANUAL + sha, sha, 'manual: ' + _CTRL.sub('', a.note)[:80], int(time.time())))
                    print('game uploads signed by csprogs %s are taken' % sha[:16])
                else:
                    # any build, a learned release too (attack review 2: a release with a bad upload flow must be stoppable)
                    db.execute('DELETE FROM codes WHERE blake = ?', (MANUAL + sha,))
                    db.execute('INSERT OR REPLACE INTO codes(blake, sha, version, got_at) VALUES (?, ?, ?, ?)',
                               (DENIED + sha, sha, 'denied', int(time.time())))
                    print('game uploads signed by csprogs %s are refused (allow-code undoes it)' % sha[:16])
            return 0
        if a.cmd == 'codes':
            for r in db.execute('SELECT * FROM codes ORDER BY got_at'):
                print('%s  %-24s %s' % (r['sha'][:16], r['version'][:24], day_of(r['got_at'])))
            return 0
        if a.cmd == 'list':
            q = 'SELECT * FROM runs' + ('' if a.state == 'all' else ' WHERE state = ?') + ' ORDER BY id DESC LIMIT ?'
            for r in db.execute(q, ((a.state,) if a.state != 'all' else ()) + (a.limit,)):
                print('%5d %-8s %-4s %s %-28s %-8s %9s  %s  %s' % (
                    r['id'], r['state'], r['verdict'], day_of(r['uploaded_at']), r['map'], course(r['track']),
                    fmt_time(r['ticks'] * TICK), r['steamid'], r['tool']))
            return 0
        r = db.execute('SELECT ' + ROW + ', samples_sha FROM runs WHERE id = ?', (a.id,)).fetchone()
        if r is None: print('no run', a.id); return 1
        if a.cmd == 'show':
            for k in r.keys():
                if k not in ('reasons', 'stats'): print('%-12s %s' % (k, r[k]))
            print('file         %s' % rec_path(a.store, r['sha']))
            for x in json.loads(r['reasons']): print('  %s t=%s %s' % (x['level'], x['t'], x['what']))
            print('  stats', r['stats'])
            return 0
        # unblock: a removed run's motion is held as another player's again instead of refused, so its real author can
        # upload it (review 6); the run stays out of sight (rejected) and its file is gone, so it cannot be approved.
        to = {'approve': 'shown', 'reject': 'rejected', 'remove': 'removed', 'unblock': 'rejected'}[a.cmd]
        allowed = {'approve': ('held', 'rejected'), 'reject': ('held', 'shown'), 'unblock': ('removed',),
                   'remove': tuple(x for x in STATES if x != 'removed')}[a.cmd]   # approve undoes a reject
        if r['state'] not in allowed: print('run %d is %s; %s needs %s' % (a.id, r['state'], a.cmd, '/'.join(allowed))); return 1
        if a.cmd == 'approve' and not r['size']: print('run %d has no file (it was removed): it cannot be shown' % a.id); return 1
        with writing(db):
            # approve shows the run with only its own note (a reject's note was public after approval: review 7);
            # reject and unblock keep an earlier note without --note
            changed = db.execute("UPDATE runs SET state = ?, reviewed_at = ?, note = CASE WHEN ? THEN ? ELSE COALESCE(NULLIF(?, ''),"
                                 ' note) END WHERE id = ? AND state = ?',
                                 (to, int(time.time()), a.cmd == 'approve', a.note[:200], a.note[:200], a.id, r['state'])).rowcount
            if changed == 1 and to == 'removed':
                db.execute('UPDATE runs SET size = 0 WHERE id = ?', (a.id,))   # the store cap counts kept files
        if changed != 1: print('run %d changed meanwhile; nothing done' % a.id); return 1
        if to == 'removed':
            # The row stays (its motion is still refused as a copy); the file goes, unless another row has it.
            if not db.execute("SELECT 1 FROM runs WHERE sha = ? AND state != 'removed'", (r['sha'],)).fetchone():
                try: rec_path(a.store, r['sha']).unlink()
                except FileNotFoundError: pass
        print('run %d: %s -> %s' % (a.id, r['state'], to))
        if a.cmd == 'unblock':
            print('its motion is held as another player\'s now, not refused: approve the real author\'s upload of it'
                  ' (an identical file needs one more header line)')
        if to == 'removed':
            # Remove is for good (the file is gone; reject keeps it). Other uploads of the same motion stay.
            same = [x[0] for x in db.execute("SELECT id FROM runs WHERE samples_sha = ? AND id != ? AND state != 'removed'",
                                             (r['samples_sha'], a.id))]
            if same: print('the same motion is also run(s) %s: check which is the original (a copier can upload first) before'
                           ' removing any of them' % ', '.join(map(str, same)))
        return 0


if __name__ == '__main__':
    sys.exit(main())
