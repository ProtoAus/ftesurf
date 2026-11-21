"""surfd/tasupd.py: Steam sign-in, the upload refusals, the physics verdicts, the board and the owner CLI.

Needs Flask (2.2.2 on the Pi). Steam is a fake `http`; the run is tools/test_tasplaus.py's simulator.
"""
import contextlib
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import time
import unittest
import urllib.parse
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import test_tasplaus as fx
sys.path.insert(0, str(Path(__file__).resolve().parent))
import steam
import tasupd as svc

ALICE, BOB, BANNED, STRANGER = '76561198000000001', '76561198000000002', '76561198000000003', '76561198000000004'
BASE = 'http://localhost/tasup'


class Clock:
    def __init__(self): self.t = float(int(time.time()))
    def __call__(self): return self.t


def rec(rows=None, fin=None, extra='', mapname='synth'):
    if rows is None: rows, fin = fx.simulate()
    return fx.text(rows, fin, extra=extra).replace('map synth', 'map ' + mapname).encode()


def edited_speed():
    rows, fin = fx.simulate()
    rows = [(t, list(o), list(v)) for t, o, v in rows]
    i0 = next(i for i, r in enumerate(rows) if r[0] >= 0.3)
    for j in range(i0, len(rows)):
        rows[j][2][0] *= 1.05; rows[j][2][1] *= 1.05
    for j in range(i0 + 1, len(rows)):
        dt = rows[j][0] - rows[j - 1][0]
        for c in range(3): rows[j][1][c] = rows[j - 1][1][c] + (rows[j - 1][2][c] + rows[j][2][c]) * 0.5 * dt
    return rec(rows, fin)


XE = fx.ZONES['tracks']['main']['zones']['end']['regions'][0]['points'][0][0]


def variant(vw=2.0, cap=250.0):
    """fx.simulate with another strafe (v.w = vw: less gain a tick as vw grows) and prestrafe cap;
    finishes where it enters the end box. Each (vw, cap) is a different motion."""
    R = fx.RATE
    o, v, rows, t, tick, jumped, fin = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [], -0.6, 0, False, None
    while fin is None or tick < fin + 40 + 60:
        rows.append((t, list(o), list(v)))
        if fin is None and t >= 0 and o[0] >= XE:
            fin = round(t / R)
        vo, h = list(v), math.hypot(v[0], v[1])
        if not jumped and t >= -0.105:
            v[2], jumped = 289.99, True
        elif not jumped:
            v[0], v[1] = min(cap, max(0.0, h - max(h, 100.0) * 4.0 * R) + 18.0), 0.0
        else:
            side = 1 if tick % 40 < 20 else -1
            ang = math.atan2(v[1], v[0]) + side * math.acos(vw / max(h, vw))
            wx, wy = math.cos(ang), math.sin(ang)
            add = 30.0 - (v[0] * wx + v[1] * wy)
            v[0] += add * wx; v[1] += add * wy; v[2] -= 800.0 * R
        for i in range(3):
            o[i] += (vo[i] + v[i]) * 0.5 * R if jumped else v[i] * R
        t = round(t + R, 6); tick += 1
    return rows, fin


SURFD_RUNS = ('CREATE TABLE runs (map TEXT NOT NULL, track INTEGER NOT NULL, leg INTEGER NOT NULL, tier TEXT NOT NULL,'
              ' style TEXT NOT NULL, player TEXT NOT NULL, name TEXT NOT NULL, ticks INTEGER NOT NULL, tickrate REAL NOT NULL,'
              ' millis INTEGER NOT NULL, flags INTEGER NOT NULL, node TEXT NOT NULL, runid TEXT NOT NULL,'
              ' submitted INTEGER NOT NULL, PRIMARY KEY (map, track, leg, tier, style, player))')


class Service(unittest.TestCase):
    def record(self, db, mapname, track, millis, leg=0, style='clean', player='p'):
        db.execute("INSERT INTO runs VALUES (?, ?, ?, 'ranked', ?, ?, 'n', ?, 0.015, ?, 0, 'node', 'r', 1)",
                   (mapname, track, leg, style, player, round(millis / 15), millis))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = Path(self.tmp.name)
        self.store = d / 'state' / 'tasup.sqlite3'
        svc.initialize(self.store)
        self.accounts = d / 'surfd.db'
        with contextlib.closing(sqlite3.connect(self.accounts)) as db, db:
            db.execute("CREATE TABLE accounts (steamid TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '', avatar TEXT NOT NULL"
                       " DEFAULT '', seen_at INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL, banned_at INTEGER NOT NULL"
                       " DEFAULT 0, ban_note TEXT NOT NULL DEFAULT '')")
            db.executemany('INSERT INTO accounts (steamid, name, created_at, banned_at) VALUES (?, ?, 1, ?)',
                           [(ALICE, 'Alice <b>', 0), (BOB, 'Bob', 0), (BANNED, 'Mallory', 5)])
            db.execute(SURFD_RUNS)
            # synth's record: 0.5 s, under every simulated run (fin ~1.2 s), so they are not new records.
            self.record(db, 'synth', 0, 500)
        zdir = d / 'zones'; zdir.mkdir()
        (zdir / 'synth.json').write_text(json.dumps(fx.ZONES))
        self.zdirs = [str(d / 'nozones'), str(zdir)]
        self.steam_says = b'ns:http://specs.openid.net/auth/2.0\nis_valid:true\n'
        self.steam_calls = []
        self.clock = Clock()
        self.app = svc.create_app(self.store, self.accounts, self.zdirs, BASE, http=self.fake_http, clock=self.clock)
        self.nonce = 0

    def tearDown(self): self.tmp.cleanup()

    def fake_http(self, url, data=None, timeout=None):
        self.steam_calls.append((url, data))
        if isinstance(self.steam_says, Exception): raise self.steam_says
        return self.steam_says

    def assertion(self, sid, return_to, **over):
        self.nonce += 1
        a = {'openid.ns': steam.NS, 'openid.mode': 'id_res', 'openid.op_endpoint': steam.OPENID,
             'openid.claimed_id': 'https://steamcommunity.com/openid/id/' + sid,
             'openid.identity': 'https://steamcommunity.com/openid/id/' + sid, 'openid.return_to': return_to,
             'openid.response_nonce': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(self.clock.t)) + 'n%d' % self.nonce,
             'openid.assoc_handle': '1234567890', 'openid.sig': 'c2lnbmF0dXJl',
             'openid.signed': 'signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle'}
        a.update(over)
        return a

    def sign_in(self, sid, client=None, **over):
        """The whole Steam round trip; returns (client, the return reply)."""
        c = client or self.app.test_client()
        r = c.get('/tasup/steam')
        self.assertEqual(r.status_code, 302)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(r.headers['Location']).query)
        return_to = q['openid.return_to'][0]
        self.assertEqual(q['openid.realm'][0], 'http://localhost')
        args = self.assertion(sid, return_to, **over)
        self.last_args = args
        back = c.get(urllib.parse.urlsplit(return_to).path + '?' + urllib.parse.urlsplit(return_to).query + '&'
                     + urllib.parse.urlencode(args))
        return c, back

    def csrf(self, c):
        page = c.get('/tasup/').get_data(as_text=True)
        m = re.search(r'name="csrf" value="([0-9a-f]{32})"', page)
        return m.group(1) if m else ''

    def upload(self, c, body, tool='bot v1', csrf=None, headers=None, json_reply=True):
        data = {'rec': (io.BytesIO(body), 'run.rec'), 'tool': tool, 'csrf': self.csrf(c) if csrf is None else csrf}
        h = dict(headers or {})
        if json_reply: h['Accept'] = 'application/json'
        return c.post('/tasup/upload', data=data, content_type='multipart/form-data', headers=h)

    def assertCopyHeld(self, r, rid):
        """Another player's motion is kept for the owner, never shown (review 4: held, not refused)."""
        j = r.get_json()
        self.assertEqual((r.status_code, j.get('state')), (200, 'held'), j)
        self.assertIn("the motion of run %d (another player's)" % rid, json.dumps(j['reasons']))

    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out): code = svc.main(['--store', str(self.store)] + list(args))
        return code, out.getvalue()

    # sign-in

    def test_sign_in_sets_a_session(self):
        c, back = self.sign_in(ALICE)
        self.assertEqual(back.status_code, 303, back.get_data(as_text=True))
        self.assertEqual(len(self.steam_calls), 1)
        self.assertIn(b'openid.mode=check_authentication', self.steam_calls[0][1])
        page = c.get('/tasup/').get_data(as_text=True)
        self.assertIn('Signed in as <b>Alice &lt;b&gt;</b>', page)
        self.assertIn('name="rec"', page)

    def test_unknown_account_must_link_first(self):
        c, back = self.sign_in(STRANGER)
        self.assertEqual(back.status_code, 403)
        self.assertIn('Link your Steam account first', back.get_data(as_text=True))
        self.assertNotIn('name="rec"', c.get('/tasup/').get_data(as_text=True))

    def test_banned_account_refused(self):
        c, back = self.sign_in(BANNED)
        self.assertEqual(back.status_code, 403)
        self.assertNotIn('name="rec"', c.get('/tasup/').get_data(as_text=True))

    def test_steam_says_no(self):
        self.steam_says = b'ns:http://specs.openid.net/auth/2.0\nis_valid:false\n'
        c, back = self.sign_in(ALICE)
        self.assertEqual(back.status_code, 400)
        self.assertNotIn('name="rec"', c.get('/tasup/').get_data(as_text=True))

    def test_steam_unreachable_is_not_a_refusal(self):
        self.steam_says = steam.Unavailable('down')
        _, back = self.sign_in(ALICE)
        self.assertEqual(back.status_code, 503)

    def test_replayed_assertion_refused(self):
        c, back = self.sign_in(ALICE)
        self.assertEqual(back.status_code, 303)
        nonce = self.last_args['openid.response_nonce']
        c2, back2 = self.sign_in(ALICE, **{'openid.response_nonce': nonce})
        self.assertEqual(back2.status_code, 400)
        self.assertEqual(len(self.steam_calls), 1)   # refused before asking Steam

    def test_sign_in_from_another_browser_refused(self):
        c = self.app.test_client()
        r = c.get('/tasup/steam')
        return_to = urllib.parse.parse_qs(urllib.parse.urlsplit(r.headers['Location']).query)['openid.return_to'][0]
        other = self.app.test_client()   # no state cookie
        back = other.get(urllib.parse.urlsplit(return_to).path + '?' + urllib.parse.urlsplit(return_to).query + '&'
                         + urllib.parse.urlencode(self.assertion(ALICE, return_to)))
        self.assertEqual(back.status_code, 400)
        self.assertEqual(self.steam_calls, [])

    def test_repeated_openid_field_refused(self):
        c = self.app.test_client()
        r = c.get('/tasup/steam')
        return_to = urllib.parse.parse_qs(urllib.parse.urlsplit(r.headers['Location']).query)['openid.return_to'][0]
        q = urllib.parse.urlencode(self.assertion(ALICE, return_to)) + '&openid.claimed_id=' + urllib.parse.quote(
            'https://steamcommunity.com/openid/id/' + BOB)
        back = c.get(urllib.parse.urlsplit(return_to).path + '?' + urllib.parse.urlsplit(return_to).query + '&' + q)
        self.assertEqual(back.status_code, 400)
        self.assertEqual(self.steam_calls, [])

    def test_assertion_for_another_return_to_refused(self):
        _, back = self.sign_in(ALICE, **{'openid.return_to': BASE + '/steam/return?s=' + 'a' * 32})
        self.assertEqual(back.status_code, 400)

    def test_forged_session_cookie_ignored(self):
        c = self.app.test_client()
        c.set_cookie('localhost', 'ftup', '%s.%d.%s' % (ALICE, int(self.clock.t) + 3600, '0' * 32))
        self.assertNotIn('name="rec"', c.get('/tasup/').get_data(as_text=True))
        self.assertEqual(self.upload(c, rec(), csrf='0' * 32).status_code, 401)

    def test_session_expires(self):
        c, _ = self.sign_in(ALICE)
        self.clock.t += svc.SESSION_TTL + 1
        self.assertEqual(self.upload(c, rec(), csrf='x').status_code, 401)

    # uploads

    def test_clean_run_is_shown(self):
        c, _ = self.sign_in(ALICE)
        body = rec()
        r = self.upload(c, body)
        j = r.get_json()
        self.assertEqual((r.status_code, j['ok'], j['verdict'], j['state']), (200, 1, 'PASS', 'shown'), j)
        board = self.app.test_client().get('/tasup/api/board?map=synth&track=0').get_json()
        self.assertEqual([x['id'] for x in board['runs']], [j['id']])
        self.assertEqual(board['runs'][0]['name'], 'Alice <b>')
        self.assertEqual(board['runs'][0]['tool'], 'bot v1')
        self.assertAlmostEqual(board['runs'][0]['time'], round(fx.simulate()[1] * 0.015, 3))
        anon = self.app.test_client()
        self.assertEqual(anon.get('/tasup/run/%d.rec' % j['id']).get_data(), body)
        page = anon.get('/tasup/board?map=synth&track=0').get_data(as_text=True)
        self.assertIn('Alice &lt;b&gt;', page)
        self.assertNotIn('Alice <b>', page)
        self.assertIn('physics checked', anon.get('/tasup/run/%d' % j['id']).get_data(as_text=True))
        self.assertEqual([x['id'] for x in anon.get('/tasup/api/recent').get_json()['runs']], [j['id']])

    def test_html_upload_redirects_to_the_run(self):
        c, _ = self.sign_in(ALICE)
        r = self.upload(c, rec(), json_reply=False)
        self.assertEqual(r.status_code, 303)
        self.assertRegex(r.headers['Location'], r'/tasup/run/\d+$')

    def test_edited_run_is_held_for_review(self):
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, edited_speed()).get_json()
        self.assertEqual((j['verdict'], j['state']), ('HOLD', 'held'), j)
        anon = self.app.test_client()
        self.assertEqual(anon.get('/tasup/api/board?map=synth&track=0').get_json()['runs'], [])
        self.assertEqual(anon.get('/tasup/run/%d' % j['id']).status_code, 404)
        self.assertEqual(anon.get('/tasup/run/%d.rec' % j['id']).status_code, 404)
        mine = c.get('/tasup/run/%d' % j['id']).get_data(as_text=True)
        self.assertIn('waiting for review', mine)
        self.assertIn('energy', mine)
        self.assertEqual(len(j['reasons']), svc.REASONS_MAX + 1)   # one a tick, cut to the first few
        self.assertRegex(j['reasons'][-1]['what'], r'^\d+ more not listed$')
        self.assertIn('more not listed', mine)
        # the owner approves it
        self.assertEqual(self.cli('approve', str(j['id']), '--note', 'booster at 0.3s')[0], 0)
        self.assertEqual([x['id'] for x in anon.get('/tasup/api/board?map=synth&track=0').get_json()['runs']], [j['id']])
        self.assertIn('booster at 0.3s', anon.get('/tasup/run/%d' % j['id']).get_data(as_text=True))

    def test_impossible_run_refused_and_not_kept(self):
        c, _ = self.sign_in(ALICE)
        rows, fin = fx.simulate()
        r = self.upload(c, rec(rows[:len(rows) // 2], fin))   # samples stop before the finish
        self.assertEqual(r.status_code, 422)
        self.assertIn('samples stop', json.dumps(r.get_json()['reasons']))
        self.assertEqual(self.cli('list', '--state', 'all')[1], '')

    def test_duplicates_refused(self):
        c, _ = self.sign_in(ALICE)
        body = rec()
        self.assertEqual(self.upload(c, body).status_code, 200)
        r = self.upload(c, body)
        self.assertEqual(r.status_code, 409)
        self.assertIn('You uploaded this file already', r.get_json()['error'])   # refused before the checker runs
        c2, _ = self.sign_in(BOB)   # the same motion under another header, by somebody else
        self.assertCopyHeld(self.upload(c2, body.replace(b'track 0\n', b'track 0\nowner bob\n')), 1)

    def test_header_refusals(self):
        c, _ = self.sign_in(ALICE)
        cases = [(rec(extra='foreign ksf 1 2 3'), 'imported'),
                 (rec(extra='momdemo 4017998251465ca2'), 'imported'),
                 (rec(extra='runid mom-4017998251465ca2'), 'imported'),
                 (rec().replace(b'tickrate 0.015', b'tickrate 0.01'), '66.67 tick'),
                 (rec().replace(b'tickrate 0.015', b'tickrate nan'), 'not a number'),
                 (rec().replace(b'track 0\n', b'track 0\ntrack 1\n'), 'twice'),
                 (rec().replace(b'track 0\n', b'track 0\x0bmovetickrate 0.02\n'), 'other than newline, space and tab'),
                 (rec().replace(b'track 0\n', b'track 0\nleg\xc2\xa04\n'), 'other than newline, space and tab'),
                 (rec(mapname='../etc'), 'no usable map'),
                 (rec().replace(b'track 0', b'track -1'), 'no usable track'),
                 (b'MZ\x00' + rec(), 'not a FTESURF-REC'),
                 (rec().replace(b'begin\n', b''), 'no header'),
                 (b'\xff\xfe' + rec(), 'not a FTESURF-REC'),
                 (rec().replace(b'map synth', b'map synth\nplayer \xff\xfe'), 'not a text'),
                 (rec().replace(b'\nend ', '\n0.5 1 2 3 4 5 6 7 8 9 10 11 12 13 \u00e9\nend '.encode(), 1), 'plain ASCII'),
                 (b'FTESURF-REC 9\n' + b'x' * 70000 + b'\nbegin\n', 'no begin line in its first')]
        for body, why in cases:
            r = self.upload(c, body)
            self.assertEqual(r.status_code, 400, why)
            self.assertIn(why, r.get_json()['error'])

    def test_movetickrate_zero_means_absent(self):
        c, _ = self.sign_in(ALICE)
        r = self.upload(c, rec().replace(b'movetickrate 0.015', b'movetickrate 0'))
        self.assertEqual(r.get_json().get('state'), 'shown', r.get_json())

    def test_copies_refused(self):
        c, _ = self.sign_in(ALICE)
        rows, fin = fx.simulate()
        a = self.upload(c, rec(rows, fin)).get_json()
        self.assertEqual(a['state'], 'shown')
        b, _ = self.sign_in(BOB)
        extra = rec(rows, fin).replace(b'\nend ', b'\n9.0000 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0\nend ', 1)
        moved = rec([(t, [o[0], o[1] + 3.0, o[2]], v) for t, o, v in rows], fin)
        late = rec([(round(t + fx.RATE, 6), o, v) for t, o, v in rows], fin + 1)
        noisy = rec([(t, [x + 0.3 for x in o], [x + 0.4 for x in v]) for t, o, v in rows], fin)
        for body in (extra, moved, late, noisy):
            self.assertCopyHeld(self.upload(b, body), a['id'])
        board = self.app.test_client().get('/tasup/api/board?map=synth&track=0').get_json()
        self.assertEqual([x['id'] for x in board['runs']], [a['id']])   # none of them shown
        other, ofin = variant(14.0)
        self.assertEqual(self.upload(b, rec(other, ofin)).get_json()['state'], 'shown')

    def test_failed_commit_leaves_no_file(self):
        c, _ = self.sign_in(ALICE)
        real, calls = svc.writing, []

        @contextlib.contextmanager
        def failing(db):
            calls.append(1)
            with real(db):
                yield db
                if len(calls) == 2:   # the upload's insert, after its file is written
                    raise sqlite3.OperationalError('disk I/O error')
        svc.writing = failing
        try:
            r = self.upload(c, rec())
        finally:
            svc.writing = real
        self.assertEqual(r.status_code, 503)
        self.assertEqual(list((self.store.parent / 'recs').rglob('*.rec')), [])
        self.assertEqual(self.upload(c, rec()).get_json()['state'], 'shown')   # and the run can come again

    def test_checker_error_is_held_not_500(self):
        z = json.loads(json.dumps(fx.ZONES))
        z['tracks']['main']['zones']['end']['regions'][0]['bottom'] = None
        Path(self.zdirs[1], 'synth.json').write_text(json.dumps(z))
        c, _ = self.sign_in(ALICE)
        r = self.upload(c, rec())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['state'], 'held')
        self.assertIn('could not finish', json.dumps(r.get_json()['reasons']))

    def test_too_many_form_parts(self):
        c, _ = self.sign_in(ALICE)
        data = {'rec': (io.BytesIO(rec()), 'run.rec'), 'tool': 'x', 'csrf': self.csrf(c)}
        for i in range(10): data['f%d' % i] = 'x'
        r = c.post('/tasup/upload', data=data, content_type='multipart/form-data', headers={'Accept': 'application/json'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('too many parts', r.get_json()['error'])

    def test_steam_confirmations_capped(self):
        old = svc.STEAM_MINUTE
        svc.STEAM_MINUTE = 2
        try:
            codes = [self.sign_in(ALICE)[1].status_code for _ in range(3)]
        finally:
            svc.STEAM_MINUTE = old
        self.assertEqual(codes, [303, 303, 429])
        self.assertEqual(len(self.steam_calls), 2)

    def test_head_counts_as_a_read(self):
        anon = self.app.test_client()
        codes = [anon.head('/tasup/api/recent').status_code for _ in range(svc.PEER_READS + 1)]
        self.assertEqual(codes[-1], 429)

    def test_tool_name_loses_markup(self):
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, rec(), tool='^1red&link\\"bot";$x  v2').get_json()
        run = self.app.test_client().get('/tasup/api/run/%d' % j['id']).get_json()['run']
        self.assertEqual(run['tool'], '1redlinkbotx v2')   # ^ & \\ " ; $ dropped, spaces collapsed

    def test_remove_frees_the_file(self):
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, rec()).get_json()
        self.assertEqual(len(list((self.store.parent / 'recs').rglob('*.rec'))), 1)
        self.assertEqual(self.cli('remove', str(j['id']))[0], 0)
        self.assertEqual(list((self.store.parent / 'recs').rglob('*.rec')), [])
        with contextlib.closing(sqlite3.connect(self.store)) as db:
            self.assertEqual(db.execute('SELECT size, state FROM runs').fetchone(), (0, 'removed'))
        self.assertEqual(self.upload(c, rec()).status_code, 409)   # still refused as the same motion

    def test_refused_bytes_do_not_spend_the_day(self):
        c, _ = self.sign_in(ALICE)
        for _ in range(3): self.upload(c, b'FTESURF-REC 5\n' + b'x' * 1000)
        self.upload(c, rec())
        with contextlib.closing(sqlite3.connect(self.store)) as db:
            n, size = db.execute('SELECT n, bytes FROM spend').fetchone()
            kept = db.execute('SELECT size + LENGTH(sig) FROM runs').fetchone()[0]
        self.assertEqual((n, size), (4, kept))   # the file and its motion blob, nothing for the refused
        self.assertGreater(kept, len(rec()))

    def test_owner_approved_label(self):
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, edited_speed()).get_json()
        self.cli('approve', str(j['id']))
        page = self.app.test_client().get('/tasup/board?map=synth&track=0').get_data(as_text=True)
        self.assertIn('owner approved', page)
        self.assertNotIn('physics checked', page)

    def test_no_zones_is_held(self):
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, rec(mapname='surf_nozones')).get_json()
        self.assertEqual(j['state'], 'held')
        self.assertIn('no zones', json.dumps(j['reasons']))

    def test_post_guards(self):
        c, _ = self.sign_in(ALICE)
        self.assertEqual(self.upload(c, rec(), csrf='').status_code, 403)
        self.assertEqual(self.upload(c, rec(), headers={'Origin': 'https://evil.example'}).status_code, 403)
        self.assertEqual(self.upload(self.app.test_client(), rec(), csrf='').status_code, 401)
        self.assertEqual(self.upload(c, rec(), headers={'Origin': 'http://localhost'}).status_code, 200)

    def test_csrf_is_per_session(self):
        c, _ = self.sign_in(ALICE)
        token = self.csrf(c)
        c2, _ = self.sign_in(BOB)
        self.assertEqual(self.upload(c2, rec(), csrf=token).status_code, 403)

    def test_banned_after_sign_in(self):
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, rec()).get_json()
        token = self.csrf(c)   # the page drops the form once banned; a held token must not work either
        with contextlib.closing(sqlite3.connect(self.accounts)) as db, db:
            db.execute('UPDATE accounts SET banned_at = 9 WHERE steamid = ?', (ALICE,))
        self.clock.t += svc.NAME_TTL + 1   # the name cache lapses
        anon = self.app.test_client()
        self.assertEqual(anon.get('/tasup/api/board?map=synth&track=0').get_json()['runs'], [])
        self.assertEqual(anon.get('/tasup/run/%d' % j['id']).status_code, 404)
        r = self.upload(c, edited_speed(), csrf=token)
        self.assertEqual(r.status_code, 403)
        self.assertIn('cannot upload', r.get_json()['error'])

    def test_best_per_player(self):
        c, _ = self.sign_in(ALICE)
        (fast, ff), (slow, sf) = sorted([variant(2.0), variant(17.0)], key=lambda x: x[1])
        self.assertGreater(sf, ff)
        a = self.upload(c, rec(slow, sf)).get_json()
        b = self.upload(c, rec(fast, ff)).get_json()
        self.assertEqual((a['state'], b['state']), ('shown', 'shown'), (a, b))
        runs = self.app.test_client().get('/tasup/api/board?map=synth&track=0').get_json()['runs']
        self.assertEqual([(x['id'], x['ticks']) for x in runs], [(b['id'], ff)])

    def test_daily_and_held_caps(self):
        c, _ = self.sign_in(ALICE)
        held = 0
        for vw in (2, 9, 12.5, 15, 17.5, 19.5, 21.5, 23, 24.5, 26):   # ten motions (v.w), each with a speed edit
            rows, fin = variant(vw)
            rows = [(t, list(o), [v[0] * 1.05, v[1] * 1.05, v[2]] if t >= 0.3 else list(v)) for t, o, v in rows]
            r = self.upload(c, rec(rows, fin)).get_json()
            held += r.get('state') == 'held'
        self.assertEqual(held, svc.HELD_CAP)
        self.assertEqual(self.upload(c, rec()).get_json()['state'], 'shown')   # the cap is on the owner's queue only
        spent = lambda: sqlite3.connect(self.store).execute('SELECT n FROM spend WHERE who = ?', (ALICE,)).fetchone()[0]
        before = spent()
        r = self.upload(c, edited_speed())
        self.assertEqual(r.status_code, 429)
        self.assertIn('waiting for review', r.get_json()['error'])
        self.assertEqual(spent(), before + 1)   # refused at the held cap after a full check: the attempt counts (review 7)
        for _ in range(svc.USER_DAY):
            last = self.upload(c, b'not a rec')
        self.assertEqual(last.status_code, 429)
        self.assertIn('today', last.get_json()['error'])
        self.clock.t += 86400
        c, _ = self.sign_in(ALICE)   # the session outlives no day
        self.assertEqual(self.upload(c, b'not a rec').status_code, 400)

    def test_oversize_refused(self):
        c, _ = self.sign_in(ALICE)
        r = self.upload(c, b'FTESURF-REC 5\n' + b'x' * (svc.MAX_REC + 10))
        self.assertEqual(r.status_code, 413)

    def test_owner_cli(self):
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, rec()).get_json()
        code, out = self.cli('list', '--state', 'shown')
        self.assertIn('synth', out)
        self.assertEqual(self.cli('approve', str(j['id']))[0], 1)   # only a held run
        self.assertEqual(self.cli('reject', str(j['id']), '--note', 'stolen')[0], 0)
        self.assertEqual(self.app.test_client().get('/tasup/api/board?map=synth&track=0').get_json()['runs'], [])
        self.assertIn('stolen', c.get('/tasup/run/%d' % j['id']).get_data(as_text=True))
        self.assertEqual(self.cli('remove', str(j['id']))[0], 0)
        self.assertEqual(c.get('/tasup/run/%d' % j['id']).status_code, 404)
        self.assertIn('file', self.cli('show', str(j['id']))[1])

    def test_probe_and_bad_course(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get('/tasup/api/board?map=tasupd_install_probe&track=0').get_json(),
                         {'ok': 1, 'map': 'tasupd_install_probe', 'track': 0, 'runs': []})
        self.assertEqual(anon.get('/tasup/api/board?map=../x&track=0').status_code, 400)
        self.assertEqual(anon.get('/tasup/board?map=synth&track=999').status_code, 400)
        self.assertEqual(anon.get('/tasup').status_code, 301)
        self.assertIn("default-src 'none'", anon.get('/tasup/').headers['Content-Security-Policy'])

    def test_health_reads_both_stores(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get('/tasup/api/health').get_json(), {'ok': 1, 'store': 1, 'accounts': 1})
        self.accounts.rename(self.accounts.with_suffix('.gone'))
        r = anon.get('/tasup/api/health')
        self.assertEqual((r.status_code, r.get_json()['ok']), (503, 0))

    def test_closed_wal_accounts_read_without_side_files(self):
        # P1618: surfd's last close deleted -wal/-shm and this sandbox cannot write beside surfd.db.
        d = Path(self.tmp.name) / 'ro'; d.mkdir()
        acc = d / 'surfd.db'
        with contextlib.closing(sqlite3.connect(acc)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            with db: db.execute("CREATE TABLE accounts (steamid TEXT PRIMARY KEY, name TEXT, banned_at INTEGER)")
            with db: db.execute("INSERT INTO accounts VALUES (?, 'Alice', 0)", (ALICE,))
            with db: db.execute(SURFD_RUNS)
        self.assertEqual(sorted(x.name for x in d.iterdir()), ['surfd.db'])
        d.chmod(0o555)
        try:
            try:
                with svc.connect(acc, readonly=True) as db: db.execute('SELECT 1 FROM accounts').fetchall()
                self.skipTest('this SQLite reads a closed WAL file read-only without side files: condition not made')
            except sqlite3.OperationalError:
                pass
            app = svc.create_app(self.store, acc, self.zdirs, BASE, http=self.fake_http, clock=self.clock)
            self.assertEqual(app.test_client().get('/tasup/api/health').get_json()['ok'], 1)
            self.app = app
            _, back = self.sign_in(ALICE)
            self.assertEqual(back.status_code, 303)
            self.assertEqual(sorted(x.name for x in d.iterdir()), ['surfd.db'])
        finally:
            d.chmod(0o755)

    def test_downloads_are_budgeted_in_bytes(self):
        c, _ = self.sign_in(ALICE)
        body = rec()
        rid = self.upload(c, body).get_json()['id']
        saved = svc.REC_PEER_BYTES, svc.REC_ALL_BYTES
        svc.REC_PEER_BYTES, svc.REC_ALL_BYTES = int(len(body) * 2.5), int(len(body) * 3.5)
        try:
            a = self.app.test_client()
            self.assertEqual([a.get('/tasup/run/%d.rec' % rid).status_code for _ in range(3)], [200, 200, 429])
            b = self.app.test_client()
            got = [b.get('/tasup/run/%d.rec' % rid, environ_base={'REMOTE_ADDR': '10.0.0.2'}).status_code for _ in range(2)]
            self.assertEqual(got, [200, 429])   # everyone's budget: 3 files a minute here
        finally:
            svc.REC_PEER_BYTES, svc.REC_ALL_BYTES = saved

    def test_unlisted_reasons_are_counted(self):
        tp = svc.load_tasplaus()
        body = edited_speed()
        n = len(tp.check(tp.read(text=body.decode()), fx.ZONES)['reasons'])
        keep, tp.REASON_KEEP = tp.REASON_KEEP, 3   # the checker lists 3, the service shows 2 of them
        saved, svc.REASONS_MAX = svc.REASONS_MAX, 2
        try:
            c, _ = self.sign_in(ALICE)
            j = self.upload(c, body).get_json()
        finally:
            tp.REASON_KEEP, svc.REASONS_MAX = keep, saved
        self.assertEqual(j['state'], 'held')
        self.assertEqual(len(j['reasons']), 3, j['reasons'])
        self.assertEqual(j['reasons'][-1]['what'], '%d more not listed' % (n - 2))

    def test_an_older_store_is_refused(self):
        with contextlib.closing(sqlite3.connect(self.store)) as db: db.execute('PRAGMA user_version = 0')
        with self.assertRaisesRegex(RuntimeError, 'older than this release'):
            svc.create_app(self.store, self.accounts, self.zdirs, BASE)
        svc.initialize(self.store)   # init is the schema step and keeps the secret
        svc.create_app(self.store, self.accounts, self.zdirs, BASE)

    def surfd(self, sql, *args):
        with contextlib.closing(sqlite3.connect(self.accounts)) as db, db: db.execute(sql, args)

    def test_new_records_wait_for_the_owner(self):
        c, _ = self.sign_in(ALICE)
        self.surfd('UPDATE runs SET millis = 5000')                     # synth's record: 5 s
        self.surfd("INSERT INTO runs VALUES ('synth', 0, 1, 'ranked', 'clean', 'q', 'n', 1, 0.015, 100, 0, 'n', 'r', 1)")
        self.surfd("INSERT INTO runs VALUES ('synth', 0, 0, 'ksf', 'sw', 'q', 'n', 1, 0.015, 100, 0, 'n', 'r', 1)")
        for tier, style in (('banned:ranked', 'clean'), ('community', 'clean'), ('ranked', 'tas'), ('ranked', 'segmented')):
            self.surfd("INSERT INTO runs VALUES ('synth', 0, 0, ?, ?, 'z', 'n', 1, 0.015, 300, 0, 'n', 'r', 1)", tier, style)
        j = self.upload(c, rec()).get_json()   # 1.2 s: legs, sideways, banned, community, tas, segmented do not count
        self.assertEqual((j['verdict'], j['state']), ('PASS', 'held'), j)
        self.assertIn('faster than the best known time on this course (5.000)', j['reasons'][-1]['what'])
        self.assertEqual(self.cli('approve', str(j['id']))[0], 0)
        b, _ = self.sign_in(BOB)
        slower, sfin = variant(2.0, cap=230.0)                            # 1.29 s, behind the approved 1.2
        self.assertEqual(self.upload(b, rec(slower, sfin)).get_json()['state'], 'shown')
        faster, ffin = variant(17.0)                                     # 1.11 s
        j = self.upload(b, rec(faster, ffin)).get_json()
        self.assertEqual(j['state'], 'held')
        self.assertIn('faster than the best known time on this course (1.200)', j['reasons'][-1]['what'])
        tie = self.upload(b, rec(*variant(6.0, cap=240.0))).get_json()   # another 1.2 s, Bob's own
        self.assertEqual(tie['state'], 'held', tie)                      # a tie with the best waits too
        self.assertIn('matches the best known time', tie['reasons'][-1]['what'])
        again = self.upload(c, rec() + b'\n').get_json()               # Alice's own 1.2 s, re-exported
        self.assertEqual(again['state'], 'shown', again)                 # her own shown run again: no new time

    def test_the_first_upload_on_a_course_waits(self):
        self.surfd('DELETE FROM runs')
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, rec()).get_json()
        self.assertEqual(j['state'], 'held')
        self.assertIn('the first upload waits for the owner', j['reasons'][-1]['what'])

    def test_an_unreadable_record_holds(self):
        self.surfd('DROP TABLE runs')
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, rec()).get_json()
        self.assertEqual(j['state'], 'held')
        self.assertIn('the course record could not be read', j['reasons'][-1]['what'])
        self.assertEqual(self.app.test_client().get('/tasup/api/health').status_code, 503)

    def test_own_runs_can_be_uploaded_again(self):
        c, _ = self.sign_in(ALICE)
        rows, fin = fx.simulate()
        first = self.upload(c, rec(rows, fin)).get_json()
        sharper = fx.text(rows, fin).replace('map synth', 'map synth').replace('\nend ', '\n\nend ', 1).encode()
        again = self.upload(c, sharper)                                  # a re-export: same motion, new bytes
        self.assertEqual(again.status_code, 200, again.get_json())
        b, _ = self.sign_in(BOB)
        self.assertCopyHeld(self.upload(b, sharper + b'\n'), first['id'])   # someone else's motion
        self.cli('remove', str(first['id'])); self.cli('remove', str(again.get_json()['id']))
        r = self.upload(c, sharper + b'\n\n')
        self.assertEqual(r.status_code, 409)                             # removed by the owner: not even its uploader
        self.assertIn('which the owner removed', r.get_json()['error'])

    def test_thinned_and_gapped_copies_refused(self):
        c, _ = self.sign_in(ALICE)
        rows, fin = variant(9.0)
        a = self.upload(c, rec(rows, fin)).get_json()
        self.assertEqual(a['state'], 'shown', a)
        b, _ = self.sign_in(BOB)
        thin = [r for i, r in enumerate(rows) if i % 2 == 0 or r[0] >= fin * fx.RATE]
        i0 = next(i for i, r in enumerate(rows) if r[0] >= 0.3)
        gaps = [r for i, r in enumerate(rows) if not i0 <= i < i0 + 3]   # 3 of 76 ticks (a5: 15 of ~520)
        for body in (rec(thin, fin), rec(gaps, fin)):
            self.assertCopyHeld(self.upload(b, body), a['id'])

    def test_kicked_copies_compare_on_their_own_samples(self):
        # Velocity kicks every 4 ticks (ramp hits): interpolating a thinned copy across them misses
        # a quarter of the ticks, so only the ticks it has samples on can be compared.
        rows, fin = variant(9.0)
        kicked = [(t, o, [v[0], v[1], v[2] + (150.0 if i % 4 == 1 and t > 0 else 0.0)]) for i, (t, o, v) in enumerate(rows)]
        c, _ = self.sign_in(ALICE)
        a = self.upload(c, rec(kicked, fin)).get_json()
        self.assertIn(a['state'], ('shown', 'held'), a)
        b, _ = self.sign_in(BOB)
        thin = [r for i, r in enumerate(kicked) if i % 2 == 0]
        self.assertCopyHeld(self.upload(b, rec(thin, fin)), a['id'])

    def test_a_copy_that_claims_a_later_finish_is_compared(self):
        c, _ = self.sign_in(ALICE)
        rows, fin = variant(9.0)
        self.assertEqual(self.upload(c, rec(rows, fin)).get_json()['state'], 'shown')
        b, _ = self.sign_in(BOB)
        self.assertCopyHeld(self.upload(b, rec([(t, [o[0], o[1] + 3.0, o[2]], v) for t, o, v in rows], fin + 6)), 1)

    def test_a_sparse_file_has_a_bounded_series(self):
        tp = svc.load_tasplaus()
        run = tp.read(text=fx.text([(i * 2.0, [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]) for i in range(50)], 10000))
        self.assertEqual(len(svc.motion_series(run)) // 3, 2 * 50 + 600 + 1)

    def test_a_copy_with_edited_velocities_is_seen_by_its_path(self):
        # Positions untouched, the recorded velocity turned 3 deg on every 4th sample (review 3).
        c, _ = self.sign_in(ALICE)
        rows, fin = variant(9.0)
        self.assertEqual(self.upload(c, rec(rows, fin)).get_json()['state'], 'shown')
        ca, sa = math.cos(math.radians(3)), math.sin(math.radians(3))
        bent = [(t, o, [v[0] * ca - v[1] * sa, v[0] * sa + v[1] * ca, v[2]] if i % 4 == 0 else v) for i, (t, o, v) in enumerate(rows)]
        tp = svc.load_tasplaus()
        mine, theirs = (svc.motion_series(tp.read(text=rec(x, fin).decode())) for x in (bent, rows))
        self.assertFalse(svc.same_motion(mine, theirs))                  # the velocities alone no longer match
        b, _ = self.sign_in(BOB)
        self.assertCopyHeld(self.upload(b, rec(bent, fin)), 1)

    def test_a_record_held_for_physics_says_so(self):
        self.surfd('UPDATE runs SET millis = 5000')
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, edited_speed()).get_json()
        self.assertEqual(j['verdict'], 'HOLD')
        self.assertIn('faster than the best known time', json.dumps(j['reasons']))

    def test_the_store_cap_counts_the_motion_blob(self):
        c, _ = self.sign_in(ALICE)
        self.assertEqual(self.upload(c, rec()).status_code, 200)
        with contextlib.closing(sqlite3.connect(self.store)) as db:
            size1, sig1 = db.execute('SELECT size, LENGTH(sig) FROM runs').fetchone()
        b, _ = self.sign_in(BOB)
        body = rec(*variant(14.0))
        # Room for the new file and a blob like the first, not for the first run's blob as well.
        saved, svc.STORE_CAP = svc.STORE_CAP, size1 + sig1 // 2 + len(body) + sig1
        try:
            r = self.upload(b, body)
        finally:
            svc.STORE_CAP = saved
        self.assertEqual(r.status_code, 507, r.get_json())

    def test_an_upload_without_a_session_is_refused_before_its_body(self):
        anon = self.app.test_client()
        parts = {'f%d' % i: 'x' for i in range(20)}                     # would be "too many parts" if read
        r = anon.post('/tasup/upload', data=parts, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 401)

    def test_a_refused_upload_leaves_another_requests_file(self):
        # Another request has put these bytes in place and not committed yet; this one is refused in the
        # write transaction (store full) and must not delete that file.
        body = rec()
        path = svc.rec_path(self.store, svc.hashlib.sha256(body).hexdigest())
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
        saved, svc.STORE_CAP = svc.STORE_CAP, 10
        try:
            c, _ = self.sign_in(ALICE)
            self.assertEqual(self.upload(c, body).status_code, 507)
        finally:
            svc.STORE_CAP = saved
        self.assertTrue(path.exists())

    def test_a_copy_moved_by_part_of_a_tick_is_seen(self):
        # Every sample's time moved by less than a tick (review 4): samples count at their nearest tick.
        c, _ = self.sign_in(ALICE)
        rows, fin = variant(9.0)
        self.assertEqual(self.upload(c, rec(rows, fin)).get_json()['state'], 'shown')
        b, _ = self.sign_in(BOB)
        for k, dt in enumerate((0.0006, -0.0075)):
            moved = [(round(t + dt, 6), [o[0], o[1] + k, o[2]], v) for t, o, v in rows]
            self.assertCopyHeld(self.upload(b, rec(moved, fin)), 1)

    def test_parked_runs_cannot_push_the_original_out(self):
        # The original is held (a new record), and another account parks four runs nearer in length to the
        # copy: at most 3 per account keeps the original among 4 candidates.
        self.surfd('UPDATE runs SET millis = 5000')
        c, _ = self.sign_in(ALICE)
        rows, fin = variant(9.0)
        self.assertEqual(self.upload(c, rec(rows, fin)).get_json()['state'], 'held')
        self.surfd("INSERT INTO accounts (steamid, name, created_at, banned_at) VALUES ('76561198000000009', 'Carol', 1, 0)")
        carol, _ = self.sign_in('76561198000000009')
        for vw in (12.0, 14.0, 17.0, 20.0):
            self.assertEqual(self.upload(carol, rec(variant(vw)[0], fin + 6)).status_code, 200)
        saved = svc.COPY_CANDIDATES, svc.COPY_PER_PLAYER
        svc.COPY_CANDIDATES, svc.COPY_PER_PLAYER = 4, 3
        try:
            b, _ = self.sign_in(BOB)
            self.assertCopyHeld(self.upload(b, rec([(t, [o[0], o[1] + 2.0, o[2]], v) for t, o, v in rows], fin + 6)), 1)
        finally:
            svc.COPY_CANDIDATES, svc.COPY_PER_PLAYER = saved

    def test_too_many_near_misses_hold_for_a_person(self):
        a = svc.array('f', [float(i % 7) * 40.0 for i in range(3 * 400)])
        rows = []
        for n in range(3):
            b = svc.array('f', a)
            for i in range(0, len(b), 30): b[i] += 50.0 + n   # a tenth of the ticks off: cheap pass yes, full no
            rows.append({'id': n + 1, 'steamid': BOB, 'state': 'held',
                         'sig': svc.zlib.compress(b.tobytes() + svc.array('f', [float(i) for i in range(len(b))]).tobytes())})
        saved, svc.COPY_FULL = svc.COPY_FULL, 1
        try:
            r, why = svc.copy_of(a, svc.array('f', [float(i) * 3.0 for i in range(len(a))]), bytearray([1]) * 400, rows)
        finally:
            svc.COPY_FULL = saved
        self.assertIsNone(r)
        self.assertIn('close to more than 1 runs', why)

    def test_one_address_cannot_spend_everyones_steam_minute(self):
        codes = [self.sign_in(sid)[1].status_code for sid in (ALICE, BOB, ALICE, BOB)]
        self.assertEqual(codes, [303, 303, 303, 429])

    def test_the_map_cfg_speed_cap_counts(self):
        cfgdir = Path(self.tmp.name) / 'cfgmaps'; cfgdir.mkdir()
        (cfgdir / 'map_synth.cfg').write_text('// set sv_maxvelocity 100\nset sv_maxvelocity 4000\nset sv_maxvelocity 5000\n')
        self.assertEqual(svc.mapcfg_maxvel([str(Path(self.tmp.name) / 'none'), str(cfgdir)], 'synth'), 5000.0)
        self.assertIsNone(svc.mapcfg_maxvel([str(cfgdir)], 'other'))
        rows, fin = fx.simulate()
        k = next(i for i, r in enumerate(rows) if r[0] >= 0.5)
        fast = [(t, o, [3600.0 if i == k else v[0], v[1], v[2]]) for i, (t, o, v) in enumerate(rows)]
        c, _ = self.sign_in(ALICE)
        why = json.dumps(self.upload(c, rec(fast, fin)).get_json()['reasons'])
        self.assertIn('past sv_maxvelocity 3500', why)
        self.app = svc.create_app(self.store, self.accounts, self.zdirs, BASE, http=self.fake_http, clock=self.clock,
                                  map_cfg_dirs=[str(cfgdir)])
        c, _ = self.sign_in(ALICE)
        why = json.dumps(self.upload(c, rec(fast, fin) + b'\n').get_json()['reasons'])
        self.assertNotIn('sv_maxvelocity', why)

    def test_stage_legs_refused(self):
        c, _ = self.sign_in(ALICE)
        for extra in (b'leg 1\n', b'startseg 2\n'):
            r = self.upload(c, rec().replace(b'track 0\n', b'track 0\n' + extra))
            self.assertEqual(r.status_code, 400)
            self.assertIn('whole courses', r.get_json()['error'])

    def test_a_flood_of_addresses_does_not_refuse_everyone(self):
        saved, svc.HITS_MAX = svc.HITS_MAX, 5
        try:
            a = self.app.test_client()
            for i in range(10):
                a.get('/tasup/api/recent', environ_base={'REMOTE_ADDR': '10.1.0.%d' % i})
            r = a.get('/tasup/api/recent', environ_base={'REMOTE_ADDR': '192.0.2.7'})
            self.assertEqual(r.status_code, 200)
        finally:
            svc.HITS_MAX = saved

    def test_a_file_that_cannot_be_stored_is_503(self):
        recs = self.store.parent / 'recs'
        c, _ = self.sign_in(ALICE)
        body = rec()
        sub = svc.rec_path(self.store, svc.hashlib.sha256(body).hexdigest()).parent
        sub.mkdir(mode=0o500)
        try:
            r = self.upload(c, body)
        finally:
            sub.chmod(0o700)
        self.assertEqual(r.status_code, 503, r.get_json())
        with contextlib.closing(sqlite3.connect(self.store)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM runs').fetchone()[0], 0)

    def test_a_busy_checker_does_not_spend_the_attempt(self):
        tp = svc.load_tasplaus()
        import threading
        inside, release = threading.Event(), threading.Event()
        real = tp.check
        def slow(*a, **k):
            inside.set(); release.wait(5); return real(*a, **k)
        tp.check, saved = slow, svc.HEAVY_WAIT
        svc.HEAVY_WAIT = 0.05
        try:
            c, _ = self.sign_in(ALICE)
            b, _ = self.sign_in(BOB)
            first_body, other_body = rec(), rec(*variant(14.0))
            ctoken, btoken = self.csrf(c), self.csrf(b)
            t = threading.Thread(target=lambda: self.upload(c, first_body, csrf=ctoken)); t.start()
            self.assertTrue(inside.wait(5))
            r = self.upload(b, other_body, csrf=btoken)
            self.assertEqual(r.status_code, 503)
            release.set(); t.join(5)
        finally:
            tp.check, svc.HEAVY_WAIT = real, saved
            release.set()
        with contextlib.closing(sqlite3.connect(self.store)) as db:
            self.assertEqual(db.execute('SELECT n FROM spend WHERE who = ?', (BOB,)).fetchone()[0], 0)

    def test_read_rate_limit(self):
        anon = self.app.test_client()
        codes = [anon.get('/tasup/api/recent').status_code for _ in range(svc.PEER_READS + 1)]
        self.assertEqual(codes[-1], 429)
        self.assertEqual(set(codes[:-1]), {200})


    # review 5
    def test_a_shown_decoy_does_not_make_a_record(self):
        # The same samples may end anywhere the end-zone slack allows: shown as a slower time, they must not
        # come back as a record through the own-run exemption.
        rows, fin = fx.simulate()
        self.surfd('UPDATE runs SET millis = ?', (fin + 5) * 15)
        c, _ = self.sign_in(ALICE)
        decoy = self.upload(c, rec(rows, fin + 12)).get_json()
        self.assertEqual(decoy['state'], 'shown', decoy)
        j = self.upload(c, rec(rows, fin)).get_json()
        self.assertEqual(j['state'], 'held', j)
        self.assertIn('faster than the best known time', j['reasons'][-1]['what'])
        again = self.upload(c, rec(rows, fin + 12) + b'\n').get_json()   # the same time again stays exempt
        self.assertEqual(again['state'], 'shown', again)

    def test_a_rejected_run_stays_rejected_for_its_uploader(self):
        c, _ = self.sign_in(ALICE)
        rows, fin = fx.simulate()
        j = self.upload(c, rec(rows, fin)).get_json()
        self.assertEqual(self.cli('reject', str(j['id']))[0], 0)
        back = self.upload(c, rec(rows, fin, extra='comment 1')).get_json()
        self.assertEqual(back['state'], 'held', back)
        self.assertIn('which the owner rejected', json.dumps(back['reasons']))
        self.assertEqual(self.cli('approve', str(j['id']))[0], 0)          # a reject can be undone

    def test_a_removed_copy_does_not_lock_out_its_author(self):
        c, _ = self.sign_in(ALICE)
        rows, fin = fx.simulate()
        a = self.upload(c, rec(rows, fin)).get_json()
        b, _ = self.sign_in(BOB)
        copy = self.upload(b, rec(rows, fin, extra='comment 2'))
        self.assertCopyHeld(copy, a['id'])
        code, out = self.cli('remove', str(copy.get_json()['id']))
        self.assertIn('check which is the original', out)
        again = self.upload(c, rec(rows, fin) + b'\n')
        self.assertEqual((again.status_code, again.get_json().get('state')), (200, 'shown'), again.get_json())
        noisy = self.upload(c, rec([(t, [x + 0.3 for x in o], [x + 0.4 for x in v]) for t, o, v in rows], fin))
        self.assertNotEqual(noisy.status_code, 409, noisy.get_json())
        stolen = self.upload(b, rec(rows, fin) + b'\n\n')                 # the copier still cannot have it
        self.assertEqual(stolen.status_code, 409, stolen.get_json())

    def test_begin_is_a_whole_word(self):
        c, _ = self.sign_in(ALICE)
        r = self.upload(c, rec().replace(b'map synth', b'beginning 1\nmap synth', 1))
        self.assertEqual((r.status_code, r.get_json().get('state')), (200, 'shown'), r.get_json())
    # review 6
    def test_the_author_the_owner_approved_keeps_their_motion(self):
        rows, fin = fx.simulate()
        thief, _ = self.sign_in(BOB)
        stolen = self.upload(thief, rec(rows, fin)).get_json()                # uploaded first, by someone else
        alice, _ = self.sign_in(ALICE)
        mine = self.upload(alice, rec(rows, fin, extra='comment 3'))
        self.assertCopyHeld(mine, stolen['id'])
        self.cli('remove', str(stolen['id'])); self.cli('approve', str(mine.get_json()['id']))
        again = self.upload(alice, rec(rows, fin) + b'\n')
        self.assertEqual((again.status_code, again.get_json().get('state')), (200, 'shown'), again.get_json())

    def test_an_earlier_run_of_other_motion_does_not_unlock_removed_motion(self):
        rows, fin = fx.simulate()
        b, _ = self.sign_in(BOB)
        self.assertEqual(self.upload(b, rec(*variant(14.0))).get_json()['state'], 'shown')   # Bob's own, different
        c, _ = self.sign_in(ALICE)
        m = self.upload(c, rec(rows, fin)).get_json()
        self.cli('remove', str(m['id']))
        r = self.upload(b, rec(rows, fin, extra='comment 4'))
        self.assertEqual(r.status_code, 409, r.get_json())

    def test_rejected_motion_with_a_sample_past_the_finish_is_held(self):
        rows, fin = fx.simulate()
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, rec(rows, fin)).get_json()
        self.cli('reject', str(j['id']))
        t, o, v = rows[-1]
        back = self.upload(c, rec(rows + [(round(t + 1.0, 4), list(o), list(v))], fin)).get_json()
        self.assertEqual(back['state'], 'held', back)
        self.assertIn('which the owner rejected', json.dumps(back['reasons']))

    def test_unblock_lets_the_real_author_upload_for_review(self):
        rows, fin = fx.simulate()
        b, _ = self.sign_in(BOB)
        stolen = self.upload(b, rec(rows, fin)).get_json()
        self.cli('remove', str(stolen['id']))
        c, _ = self.sign_in(ALICE)
        self.assertEqual(self.upload(c, rec(rows, fin, extra='comment 5')).status_code, 409)   # never uploaded it
        self.assertEqual(self.cli('unblock', str(stolen['id']))[0], 0)
        self.assertCopyHeld(self.upload(c, rec(rows, fin, extra='comment 6')), stolen['id'])
        code, out = self.cli('approve', str(stolen['id']))
        self.assertEqual(code, 1); self.assertIn('has no file', out)

    def test_two_uploads_at_once_at_most(self):
        saved = svc.UPLOADS_AT_ONCE
        svc.UPLOADS_AT_ONCE = 0   # the semaphore is made with the app
        try:
            self.app = svc.create_app(self.store, self.accounts, self.zdirs, BASE, http=self.fake_http, clock=self.clock)
        finally: svc.UPLOADS_AT_ONCE = saved
        c, _ = self.sign_in(ALICE)
        r = self.upload(c, rec())
        self.assertEqual(r.status_code, 503, r.get_json())
        self.assertEqual(self.app.test_client().get('/tasup/api/recent').status_code, 200)

    def test_a_track_in_other_digits_is_refused(self):
        c, _ = self.sign_in(ALICE)
        r = self.upload(c, rec().replace(b'track 0', 'track ٤'.encode()))
        self.assertEqual(r.status_code, 400); self.assertIn('no usable track', r.get_json()['error'])

    # review 7
    def test_unblock_restores_the_author_with_the_same_bytes(self):
        rows, fin = fx.simulate()
        body = rec(rows, fin)
        b, _ = self.sign_in(BOB)
        stolen = self.upload(b, body).get_json()                         # Alice's file, unchanged
        self.cli('remove', str(stolen['id'])); code, out = self.cli('unblock', str(stolen['id']))
        self.assertIn('approve the real author', out)
        c, _ = self.sign_in(ALICE)
        same = self.upload(c, body)
        self.assertEqual(same.status_code, 409); self.assertIn('add any line to its header', same.get_json()['error'])
        mine = self.upload(c, rec(rows, fin, extra='comment mine'))
        self.assertCopyHeld(mine, stolen['id'])
        self.cli('approve', str(mine.get_json()['id']))
        later = self.upload(c, rec(rows, fin, extra='comment again')).get_json()   # no longer "another player's"
        self.assertEqual(later['state'], 'shown', later)

    def test_approve_drops_the_reject_note(self):
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, rec()).get_json()
        self.cli('reject', str(j['id']), '--note', 'looks like a copy')
        self.cli('approve', str(j['id']))
        self.assertNotIn('looks like a copy', self.app.test_client().get('/tasup/run/%d' % j['id']).get_data(as_text=True))

    def test_the_copy_check_has_a_time_budget(self):
        c, _ = self.sign_in(ALICE)
        self.assertEqual(self.upload(c, rec(*variant(14.0))).get_json()['state'], 'shown')
        b, _ = self.sign_in(BOB)
        keep, svc.COPY_BUDGET = svc.COPY_BUDGET, -1.0
        try: j = self.upload(b, rec()).get_json()
        finally: svc.COPY_BUDGET = keep
        self.assertEqual(j['state'], 'held', j)
        self.assertIn('ran out of time', json.dumps(j['reasons']))

    def test_a_held_copy_does_not_unlock_removed_motion(self):
        # Review 7: a held offset copy counted as owning the motion, and the exact removed samples came back shown.
        rows, fin = fx.simulate()
        c, _ = self.sign_in(ALICE)
        m = self.upload(c, rec(rows, fin)).get_json()
        self.cli('remove', str(m['id']))
        b, _ = self.sign_in(BOB)
        late = self.upload(b, rec([(round(t + 12 * fx.RATE, 6), o, v) for t, o, v in rows], fin + 12))
        self.assertIn((late.status_code, late.get_json().get('state')), ((409, None), (200, 'held')), late.get_json())
        r = self.upload(b, rec(rows, fin, extra='comment 7'))
        self.assertEqual(r.status_code, 409, r.get_json())

    # review 8
    def test_a_victims_own_nearer_runs_do_not_hide_the_copied_one(self):
        rows, fin = variant(9.0)
        c, _ = self.sign_in(ALICE)
        self.surfd('UPDATE runs SET millis = 500')
        orig = self.upload(c, rec(rows, fin)).get_json()
        for vw in (12.0, 14.0, 17.0, 20.0):     # four more of Alice's own, nearer the copy's claimed finish
            self.upload(c, rec(variant(vw)[0], fin + 4))
        b, _ = self.sign_in(BOB)
        self.assertCopyHeld(self.upload(b, rec(rows, fin + 4)), orig['id'])

    def test_an_own_duplicate_names_the_run(self):
        c, _ = self.sign_in(ALICE)
        j = self.upload(c, rec()).get_json()
        r = self.upload(c, rec())
        self.assertEqual(r.status_code, 409); self.assertIn('You uploaded this file already: run %d' % j['id'], r.get_json()['error'])


import hashlib
import threading
import ed25519 as ed

SEED_ALICE, SEED_BOB, SEED_BANNED, SEED_NOBODY = (bytes([i]) * 32 for i in (1, 2, 3, 4))
CODE_BYTES = b'csprogs of a lobby, P1696: ' + svc.CODE_MARK + b'...'


class GameUpload(Service):
    """P1696: the game's signed upload (cl_tasupload.qc): a challenge, then the proof and the file in one body."""

    def setUp(self):
        super().setUp()
        d = Path(self.tmp.name)
        with contextlib.closing(sqlite3.connect(self.accounts)) as db, db:
            db.execute('CREATE TABLE keylinks (pub TEXT PRIMARY KEY, steamid TEXT NOT NULL)')
            db.executemany('INSERT INTO keylinks VALUES (?, ?)', [(ed.publickey(SEED_ALICE).hex(), ALICE),
                           (ed.publickey(SEED_BOB).hex(), BOB), (ed.publickey(SEED_BANNED).hex(), BANNED)])
        self.lobby = d / 'csprogs.dat'; self.lobby.write_bytes(CODE_BYTES)
        self.code = hashlib.sha256(CODE_BYTES).hexdigest()
        self.releases = d / 'releases'; self.releases.mkdir()
        self.fetched = []
        self.app = self.game_app()

    def game_app(self, **over):
        kw = dict(http=self.fake_http, clock=self.clock, game_files=[str(self.lobby)], releases=str(self.releases),
                  fetch=self.fake_fetch, verify=ed)
        kw.update(over)
        return svc.create_app(self.store, self.accounts, self.zdirs, BASE, **kw)

    def fake_fetch(self, url, cap):
        self.fetched.append(url)
        return self.objects[url]

    def challenge(self, c, body):
        r = c.post('/tasup/api/game/challenge', json={'sha': hashlib.sha256(body).hexdigest()})
        self.assertEqual(r.status_code, 200)
        return r.get_json()

    def game_body(self, body, nonce, seed=SEED_ALICE, code=None, signed=None, sha=None, head_sha=None):
        code = code or self.code
        sha = sha or hashlib.sha256(body).hexdigest()          # the file the proof names
        signed = signed or svc.game_nonce(nonce, sha)
        sig = ed.sign(seed, (svc.ACCT_STATEMENT % (svc.GAME_SITE, signed, svc.GAME_KIND, 1, code)).encode())
        return b'FTESURF-TASUP 1\nnonce %s\nsha %s\npub %s\nsig %s\ngame %s\n' % (
            nonce.encode(), (head_sha or sha).encode(), ed.publickey(seed).hex().encode(), sig.hex().encode(), code.encode()) + body

    def post(self, c, data):
        return c.post('/tasup/upload', data=data, content_type=svc.GAME_MIME)

    def send(self, body=None, **kw):
        c = self.app.test_client()
        body = rec() if body is None else body
        n = self.challenge(c, body)['nonce']
        return self.post(c, self.game_body(body, n, **kw))

    def refused(self, r, status, words):
        j = r.get_json()
        self.assertEqual((r.status_code, j['ok'], j['status']), (200, 0, status), j)   # the game reads 200 bodies only
        self.assertIn(words, j['error'])

    def test_statement_is_surfds(self):
        text = (Path(__file__).resolve().parent / 'accounts.py').read_text()
        self.assertIn('STATEMENT = %s' % json.dumps(svc.ACCT_STATEMENT), text)

    def test_a_signed_upload_is_checked_and_kept_as_the_linked_account(self):
        r = self.send()
        j = r.get_json()
        self.assertEqual((r.status_code, j['ok'], j['state'], j['verdict']), (200, 1, 'shown', 'PASS'), j)
        self.assertEqual(j['page'], BASE + '/run/%d' % j['id'])
        with contextlib.closing(sqlite3.connect(self.store)) as db:
            self.assertEqual(db.execute('SELECT steamid, tool FROM runs WHERE id = ?', (j['id'],)).fetchone(), (ALICE, svc.GAME_TOOL))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM nonces WHERE nonce LIKE 'game %'").fetchone()[0], 1)   # spent

    def test_a_confirmation_is_used_once(self):
        c, body = self.app.test_client(), rec()
        n = self.challenge(c, body)['nonce']
        self.assertEqual(self.post(c, self.game_body(body, n)).get_json()['ok'], 1)
        self.refused(self.post(c, self.game_body(body, n)), 409, 'was used')

    def test_a_confirmation_expires(self):
        c, body = self.app.test_client(), rec()
        n = self.challenge(c, body)['nonce']
        self.clock.t += svc.CHALLENGE_TTL + 1
        self.refused(self.post(c, self.game_body(body, n)), 409, 'expired')

    def test_a_code_is_the_services_and_this_files(self):
        c, body = self.app.test_client(), rec()
        n = self.challenge(c, body)['nonce']
        other = rec(extra='comment other\n')
        self.refused(self.post(c, self.game_body(other, n)), 409, 'not this file')                       # another file's proof
        forged = '%08x' % int(self.clock.t) + n[8:16] + '0' * 16
        self.refused(self.post(c, self.game_body(body, forged)), 409, 'not this file')                   # not the service's MAC
        self.assertEqual(self.post(c, self.game_body(body, n)).get_json()['ok'], 1)   # neither refusal spent it
        n = self.challenge(c, body := rec(extra='comment third\n'))['nonce']
        # a proof that checks out spends the code before the file is read: another file then is refused, and the code gone
        self.refused(self.post(c, self.game_body(other, n, sha=hashlib.sha256(body).hexdigest())), 409, 'not the one confirmed')
        self.refused(self.post(c, self.game_body(body, n)), 409, 'was used')

    def test_a_build_without_the_upload_flow_signs_nothing(self):
        """Only a csprogs carrying the upload code (CODE_MARK) is taken: a lobby file or a release without it is not."""
        self.lobby.write_bytes(b'an older lobby build')
        self.refused(self.send(code=hashlib.sha256(b'an older lobby build').hexdigest()), 403, 'Update your game')
        rel = b'csprogs of release 0.1.50, no upload flow'
        blake = hashlib.blake2b(rel, digest_size=32).hexdigest()
        (self.releases / '0.1.50').mkdir()
        pay = {'hash_algo': 'blake2b-256', 'object_layout': 'objects/{h0h1}/{hash}', 'mirrors': ['https://dl.example/u'],
               'files': [{'path': 'worldofsurf/csprogs.dat', 'hash': blake, 'size': len(rel), 'platform': 'all', 'exec': False}]}
        (self.releases / '0.1.50' / 'update.json').write_text(json.dumps({'payload': json.dumps(pay), 'signature': 'x'}))
        self.objects = {'https://dl.example/u/objects/%s/%s' % (blake[:2], blake): rel}
        c, body = self.app.test_client(), rec()
        n = self.challenge(c, body)['nonce']
        for _ in range(300):
            with contextlib.closing(sqlite3.connect(self.store)) as db:
                if db.execute('SELECT 1 FROM codes WHERE blake = ?', (blake,)).fetchone(): break
            time.sleep(0.01)
        self.refused(self.post(c, self.game_body(body, n, code=hashlib.sha256(rel).hexdigest())), 403, 'Update your game')
        self.assertEqual(len(self.fetched), 1)                  # known now: not fetched again

    def test_the_tool_is_named_by_the_runs_tas_flag(self):
        j = self.send(body=rec(extra='flags %d\n' % (svc.TF_TAS | 256 | 1))).get_json()
        with contextlib.closing(sqlite3.connect(self.store)) as db:
            self.assertEqual(db.execute('SELECT tool FROM runs WHERE id = ?', (j['id'],)).fetchone()[0], svc.GAME_TOOL_TAS)

    def test_codes_are_not_stored(self):
        c = self.app.test_client()
        for i in range(5): self.assertEqual(self.challenge(c, b'%d' % i)['ok'], 1)
        with contextlib.closing(sqlite3.connect(self.store)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM nonces').fetchone()[0], 0)

    def test_unknown_game_code_is_told_to_update(self):
        self.refused(self.send(code='ab' * 32), 403, 'Update your game')

    def test_a_wrong_signature_is_refused(self):
        c, body = self.app.test_client(), rec()
        n = self.challenge(c, body)['nonce']
        good = self.game_body(body, n)
        bad = good.replace(b'sig ' + good.split(b'sig ')[1][:4], b'sig 0000', 1)
        self.refused(self.post(c, bad), 403, 'did not check out')

    def test_a_zone_publish_style_proof_is_not_an_upload_proof(self):
        """The raw nonce signed (as zone publishing signs its own) is no proof here: game_nonce names the purpose."""
        c, body = self.app.test_client(), rec()
        n = self.challenge(c, body)['nonce']
        self.refused(self.post(c, self.game_body(body, n, signed=n)), 403, 'did not check out')

    def test_the_proof_names_the_file(self):
        """A signature made for one file does not carry another (the header and code name the second)."""
        c, a, b = self.app.test_client(), rec(), rec(extra='comment b\n')
        n = self.challenge(c, b)['nonce']
        self.refused(self.post(c, self.game_body(b, n, sha=hashlib.sha256(a).hexdigest(), head_sha=hashlib.sha256(b).hexdigest())),
                     403, 'did not check out')

    def test_a_refused_proof_does_not_spend_the_code(self):
        c, body = self.app.test_client(), rec()
        n = self.challenge(c, body)['nonce']
        for _ in range(3): self.refused(self.post(c, self.game_body(body, n, code='ab' * 32)), 403, 'Update')
        self.refused(self.post(c, self.game_body(body, n, seed=SEED_NOBODY)), 403, 'Link')
        self.assertEqual(self.post(c, self.game_body(body, n)).get_json()['ok'], 1)

    def test_unlinked_and_banned_keys(self):
        self.refused(self.send(seed=SEED_NOBODY), 403, 'Link your Steam account first')
        self.refused(self.send(seed=SEED_BANNED), 403, 'cannot upload')

    def test_no_proof_and_web_form_unchanged(self):
        c = self.app.test_client()
        self.refused(self.post(c, rec()), 400, 'no account proof')
        r = self.upload(c, rec())                    # the form still needs a Steam session
        self.assertEqual(r.status_code, 401)

    def test_refusals_from_the_checker_come_back_as_200(self):
        r = self.send(body=edited_speed())
        j = r.get_json()
        self.assertEqual((r.status_code, j['ok']), (200, 1), j)
        self.assertEqual(j['state'], 'held')
        self.refused(self.send(body=b'not a recording'), 400, 'not a FTESURF-REC')

    def test_a_released_csprogs_is_learned_from_its_manifest(self):
        rel = b'csprogs of release 0.1.60 ' + svc.CODE_MARK
        blake = hashlib.blake2b(rel, digest_size=32).hexdigest()
        (self.releases / '0.1.60').mkdir()
        pay = {'hash_algo': 'blake2b-256', 'object_layout': 'objects/{h0h1}/{hash}', 'mirrors': ['https://dl.example/u'],
               'files': [{'path': 'ftesurf/csprogs.dat', 'hash': blake, 'size': len(rel), 'platform': 'all', 'exec': False}]}
        (self.releases / '0.1.60' / 'update.json').write_text(json.dumps({'payload': json.dumps(pay), 'signature': 'x'}))
        url = 'https://dl.example/u/objects/%s/%s' % (blake[:2], blake)
        self.objects = {url: rel}
        code = hashlib.sha256(rel).hexdigest()
        c, body = self.app.test_client(), rec()
        n = self.challenge(c, body)['nonce']        # starts learning it in the background
        for _ in range(200):
            with contextlib.closing(sqlite3.connect(self.store)) as db:
                if db.execute('SELECT sha FROM codes WHERE blake = ?', (blake,)).fetchone(): break
            time.sleep(0.01)
        self.assertEqual(self.fetched, [url])
        j = self.post(c, self.game_body(body, n, code=code)).get_json()
        self.assertEqual((j['ok'], j['state']), (1, 'shown'), j)

    def test_a_release_object_with_other_bytes_is_not_learned(self):
        rel = b'csprogs of release 0.1.61 ' + svc.CODE_MARK
        blake = hashlib.blake2b(rel, digest_size=32).hexdigest()
        (self.releases / '0.1.61').mkdir()
        pay = {'hash_algo': 'blake2b-256', 'object_layout': 'objects/{h0h1}/{hash}', 'mirrors': ['https://dl.example/u'],
               'files': [{'path': 'ftesurf/csprogs.dat', 'hash': blake, 'size': len(rel), 'platform': 'all', 'exec': False}]}
        (self.releases / '0.1.61' / 'update.json').write_text(json.dumps({'payload': json.dumps(pay), 'signature': 'x'}))
        self.objects = {'https://dl.example/u/objects/%s/%s' % (blake[:2], blake): b'something else'}
        c, code = self.app.test_client(), hashlib.sha256(rel).hexdigest()
        def settle(k):
            for _ in range(300):
                if len(self.fetched) >= k and not any(t.name != 'MainThread' and t.is_alive() for t in threading.enumerate()): return
                time.sleep(0.01)
        for k in range(1, svc.CODE_TRIES + 1):
            body = rec(extra='comment try %d\n' % k)
            n = self.challenge(c, body)['nonce']; settle(k)
            # flow review: a release that could not be read yet is "try again", not "update your game"
            if k < svc.CODE_TRIES: self.refused(self.post(c, self.game_body(body, n, code=code)), 503, 'still reading')
            self.clock.t += svc.CODE_RETRY + 1
        self.assertEqual(len(self.fetched), svc.CODE_TRIES)
        body = rec(extra='comment last\n')
        n = self.challenge(c, body)['nonce']
        self.refused(self.post(c, self.game_body(body, n, code=code)), 403, 'Update your game')   # given up on it

    def test_an_oversized_body_is_refused_before_it_is_read(self):
        c = self.app.test_client()
        r = c.post('/tasup/upload', data=b'x' * 16, content_type=svc.GAME_MIME,
                   environ_overrides={'CONTENT_LENGTH': str(svc.MAX_FORM + 1)})   # the client would send 16
        self.refused(r, 413, 'over 8 MB')

    def test_the_owner_allows_and_denies_a_build(self):
        dev = hashlib.sha256(b'an owner dev build').hexdigest()
        self.refused(self.send(code=dev), 403, 'Update your game')
        self.assertEqual(self.cli('allow-code', dev.upper(), '--note', 'lex dev')[0], 0)
        self.assertIn('manual: lex dev', self.cli('codes')[1])
        self.assertEqual(self.send(code=dev, body=rec(extra='comment dev\n')).get_json()['ok'], 1)
        self.assertEqual(self.cli('deny-code', dev)[0], 0)
        self.refused(self.send(code=dev, body=rec(extra='comment dev2\n')), 403, 'Update your game')
        self.assertEqual(self.cli('allow-code', 'nothex')[0], 1)

    def test_lobby_backups_are_the_newest_two(self):
        """csprogs.dat.pre* (a lobby deploy's copy of the build it replaced): the newest LOBBY_BACKUPS of them sign."""
        import os
        d = self.lobby.parent
        olds = []
        for i, name in enumerate(('csprogs.dat.pre321-x', 'csprogs.dat.pre1685-y', 'csprogs.dat.pre1692-z')):
            (d / name).write_bytes(b'lobby build %d ' % i + svc.CODE_MARK); os.utime(d / name, (1000 + i, 1000 + i))
            olds.append(hashlib.sha256(b'lobby build %d ' % i + svc.CODE_MARK).hexdigest())
        self.app = self.game_app(game_files=[str(self.lobby), str(d / 'csprogs.dat.pre*')])
        self.refused(self.send(code=olds[0]), 403, 'Update your game')                  # the oldest: not taken
        for k, code in enumerate(olds[1:]):
            self.assertEqual(self.send(code=code, body=rec(extra='comment %d\n' % k)).get_json()['ok'], 1)

    def test_game_requests_are_rate_limited_per_address(self):
        c = self.app.test_client()
        for i in range(svc.PEER_GAME): self.assertEqual(self.challenge(c, b'%d' % i)['ok'], 1)
        j = self.challenge(c, b'one more')
        self.assertEqual((j['ok'], j['status']), (0, 429))
        self.clock.t += 60
        self.assertEqual(self.challenge(c, b'next minute')['ok'], 1)

    def test_a_used_code_outlives_the_steam_nonce_prune(self):
        """The sign-in route prunes its nonces after 480 s; a game code is good for 600 s and stays spent."""
        c, body = self.app.test_client(), rec()
        n = self.challenge(c, body)['nonce']
        self.assertEqual(self.post(c, self.game_body(body, n)).get_json()['ok'], 1)
        self.clock.t += 500
        self.sign_in(BOB)
        self.refused(self.post(c, self.game_body(body, n)), 409, 'was used')

if __name__ == '__main__':
    unittest.main()
