"""P1091: surfd/tasrevd.py, the TAS revision and statement service (plan 5.3) and its credit (5.4)."""
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import ed25519
import tasrev as tr
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tasrevd as svc

ALICE, BOB, CAROL, MALLORY = (bytes([n]) * 32 for n in (1, 2, 3, 4))
SID_A, SID_B, SID_C, SID_M = '76561190000000001', '76561190000000002', '76561190000000003', '76561190000000004'
CODE = 'c0de' * 16
PIN = 'pmsrcver=11 physmode=1'


def pub(seed): return ed25519.publickey(seed).hex()
def row(t, k=0): return (t % 5, k, 0, (t * 7) % 360, 0, 0, t % 2)


def revision(base, rows, parent=None, supply=None, mp='bhop_eazy', baseat='0 0 64 0 0 0'):
    """Canonical version 2 bytes and their hash; `rows` is a list of 7-tuples for base+1.."""
    head = base + len(rows)
    lines = ['tasproject 2', 'map %s' % mp, 'mapcrc 7f53da5d', 'zonecrc b305f211', 'pmpin %s' % PIN, 'assist tas',
             'origin local', 'saved 2026-10-29T00:00:00', 'revision 1']
    if parent: lines.append('parentsha %s' % parent)
    if parent is None: supply = (base + 1, head)
    lines.append('supply none' if supply is None else 'supply %d %d' % supply)
    lines += ['base 1 %s %d' % ('ab' * 32, base), 'baseat %s' % baseat, 'head %d' % head]
    lines += ['i %s' % ' '.join(str(v) for v in r) for r in rows]
    lines.append('end %d' % len(rows))
    body = ('\n'.join(lines) + '\n').encode()
    h = tr.revhash(body)[0]
    return body + ('revsha %s\n' % h).encode(), h


def statement(seed, sha, parent, first, last, code=CODE):
    msg = tr.statement(sha, parent or '-', '7f53da5d', first, last, code)
    return 'tasrev 1 %s %s 7f53da5d %d %d %s %s %s' % (sha, parent or '-', first, last, code, pub(seed), ed25519.sign(seed, msg).hex())


class Service(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); root = Path(self.tmp.name)
        self.store, self.main, self.codes = root / 'tasrev.db', root / 'accounts.db', root / 'codes.txt'
        svc.initialize(self.store)
        db = sqlite3.connect(self.main)
        db.executescript('CREATE TABLE accounts(steamid TEXT PRIMARY KEY, banned_at INTEGER);'
                         'CREATE TABLE keylinks(pub TEXT, steamid TEXT);')
        for sid in (SID_A, SID_B, SID_C, SID_M): db.execute('INSERT INTO accounts VALUES (?, 0)', (sid,))
        for seed, sid in ((ALICE, SID_A), (BOB, SID_B), (MALLORY, SID_M)): db.execute('INSERT INTO keylinks VALUES (?, ?)', (pub(seed), sid))
        db.commit(); db.close()
        self.codes.write_text(CODE + '\n')
        self.now = [1000]
        self.c = svc.create_app(self.store, self.main, self.codes, clock=lambda: self.now[0]).test_client()

    def tearDown(self): self.tmp.cleanup()

    def put_rev(self, body, ctype='text/x-tasrev'): return self.c.post('/api/tasrev/revision', data=body, content_type=ctype).get_json()
    def put_st(self, line): return self.c.post('/api/tasrev/statement', json={'line': line}).get_json()
    def credit(self, sha): return [(c['first'], c['last'], c['who']) for c in self.c.get('/api/tasrev/rev/%s' % sha).get_json()['credit']]
    def relink(self, seed, sid):
        db = sqlite3.connect(self.main); db.execute('DELETE FROM keylinks WHERE pub = ?', (pub(seed),))
        if sid: db.execute('INSERT INTO keylinks VALUES (?, ?)', (pub(seed), sid))
        db.commit(); db.close()

    def chain(self):
        """A: Alice's root, ticks 21..40. B: Bob changes 31..35. C: Carol reverts 33 to A's row."""
        a_rows = [row(t) for t in range(21, 41)]
        a, ha = revision(20, a_rows)
        b_rows = [row(t, 9) if 31 <= t <= 35 else row(t) for t in range(21, 41)]
        b, hb = revision(20, b_rows, parent=ha, supply=(31, 35))
        c_rows = [row(t) if t == 33 else r for t, r in zip(range(21, 41), b_rows)]
        c, hc = revision(20, c_rows, parent=hb, supply=(33, 33))
        return (a, ha), (b, hb), (c, hc)

    def test_revision_is_kept_by_its_hash_once(self):
        (a, ha), _, _ = self.chain()
        r1 = self.put_rev(a); self.now[0] += 50; r2 = self.put_rev(a)
        self.assertEqual((r1['ok'], r1['sha'], r1['parent_known']), (1, ha, True))
        self.assertEqual(r2['first_seen'], r1['first_seen'])
        self.assertEqual(self.c.get('/api/tasrev/rev/%s/file' % ha).data, a)

    def test_refusals(self):
        (a, ha), (b, hb), _ = self.chain()
        self.assertIn('text/x-tasrev', self.put_rev(a, ctype='text/plain')['error'])     # no cross-site form post
        bad = a.replace(b'revsha ' + ha.encode(), b'revsha ' + b'0' * 64)
        self.assertIn('revsha is not its hash', self.put_rev(bad)['error'])
        self.assertEqual(self.put_rev(b'tasproject 2\n')['ok'], 0)
        self.assertEqual(self.put_rev(a.replace(b'\n', b'\r\n'))['ok'], 0)
        line = statement(ALICE, ha, None, 21, 40)
        self.assertEqual(self.put_st(line[:-2] + ('00' if line[-2:] != '00' else '11'))['ok'], 0)
        self.assertEqual(self.put_st('tasrev 1 junk')['ok'], 0)
        self.assertEqual(self.c.get('/api/tasrev/rev/zz').get_json()['ok'], 0)
        # A child whose supply is not exact against its known parent.
        self.put_rev(a)
        b_rows = [row(t, 9) if 31 <= t <= 35 else row(t) for t in range(21, 41)]
        wide, _ = revision(20, b_rows, parent=ha, supply=(21, 40))
        self.assertIn('supply', self.put_rev(wide)['error'])

    def test_credit_follows_the_earliest_holder_and_reverts_do_not_launder(self):
        (a, ha), (b, hb), (c, hc) = self.chain()
        self.put_st(statement(ALICE, ha, None, 21, 40)); self.put_rev(a)
        self.put_st(statement(BOB, hb, ha, 31, 35)); self.put_rev(b)
        self.put_st(statement(CAROL, hc, hb, 33, 33)); self.put_rev(c)   # Carol's key is not linked
        self.assertEqual(self.credit(hc), [(21, 30, SID_A), (31, 32, SID_B), (33, 33, SID_A), (34, 35, SID_B), (36, 40, SID_A)])

    def test_unknown_ancestry_until_the_parent_arrives(self):
        (a, ha), (b, hb), _ = self.chain()
        self.put_st(statement(BOB, hb, ha, 31, 35)); self.put_rev(b)
        self.assertEqual(self.credit(hb), [(21, 40, 'unknown-ancestry')])
        self.put_rev(a)                           # the parent arrives: B is recomputed
        self.assertEqual(self.credit(hb), [(21, 30, 'unsigned'), (31, 35, SID_B), (36, 40, 'unsigned')])

    def test_a_truncated_revision_over_an_unseen_parent_lends_its_child_nothing(self):
        p_rows = [row(t) for t in range(21, 61)]
        p, hp = revision(20, p_rows)
        z, hz = revision(20, p_rows[:20], parent=hp, supply=None)
        y, hy = revision(20, p_rows, parent=hz, supply=(41, 60))
        self.put_st(statement(BOB, hy, hz, 41, 60)); self.put_rev(z); self.put_rev(y)
        self.assertEqual(self.credit(hy), [(21, 60, 'unknown-ancestry')])
        self.put_st(statement(ALICE, hp, None, 21, 60)); self.put_rev(p)
        # P supplied 21..60; Z cut it; Y restored 41..60 exactly: P's rows, Alice's, never Bob's.
        self.assertEqual(self.credit(hy), [(21, 60, SID_A)])

    def test_the_account_is_the_one_linked_when_the_statement_arrived(self):
        (a, ha), (b, hb), _ = self.chain()
        self.put_st(statement(ALICE, ha, None, 21, 40))
        self.put_st(statement(CAROL, hb, ha, 31, 35))          # Carol unlinked when she signed
        self.put_rev(a); self.put_rev(b)
        self.relink(ALICE, SID_M); self.relink(CAROL, SID_C)   # a relink, and a late link
        self.now[0] += 10
        self.assertEqual(self.credit(hb), [(21, 30, SID_A), (31, 35, 'unattributed'), (36, 40, SID_A)])

    def test_a_statement_after_publication_takes_nothing_and_junk_first_blocks_nothing(self):
        (a, ha), _, _ = self.chain()
        self.put_st(statement(MALLORY, ha, None, 21, 40, code='beef' * 16))   # first, but unreleased code
        self.put_st(statement(ALICE, ha, None, 21, 40))
        self.put_rev(a)
        self.now[0] += 5
        late = self.put_st(statement(MALLORY, ha, None, 21, 40))
        self.assertEqual((late['ok'], late['before_revision']), (1, False))
        self.assertEqual(self.credit(ha), [(21, 40, SID_A)])

    def test_a_copy_resaved_as_a_new_root_credits_the_original(self):
        (a, ha), _, _ = self.chain()
        self.put_st(statement(ALICE, ha, None, 21, 40)); self.put_rev(a)
        self.now[0] += 5
        copy, hcopy = revision(20, [row(t) for t in range(21, 41)], baseat='0 0 64 0 0 1')   # same rows and base, new hash
        self.put_st(statement(MALLORY, hcopy, None, 21, 40)); self.put_rev(copy)
        self.assertNotEqual(ha, hcopy)
        self.assertEqual(self.credit(hcopy), [(21, 40, SID_A)])

    def test_cannot_tell_is_not_a_verdict(self):
        (a, ha), _, _ = self.chain()
        self.put_rev(a)
        self.codes.write_bytes(b'\xef\xbb\xbf' + CODE.upper().encode() + b'\n')     # BOM, uppercase: still read
        self.assertEqual(self.c.get('/api/tasrev/rev/%s' % ha).get_json()['ok'], 1)
        self.codes.write_text('')
        r = self.c.get('/api/tasrev/rev/%s' % ha).get_json()
        self.assertEqual((r['ok'], r['status']), (0, 503))
        self.main.unlink()
        r = self.put_st(statement(ALICE, ha, None, 21, 40))
        self.assertEqual((r['ok'], r['status']), (0, 503))
        with svc.connect(self.store) as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM statements').fetchone()[0], 0)

    def test_reads_stay_cheap(self):
        rows = [row(t) for t in range(21, 4021)]
        body, h = revision(20, rows)
        for i in range(20):   # junk that verifies but claims the wrong ticks
            self.put_st(statement(bytes([50 + i]) * 32, h, None, 21, 22))
        self.put_st(statement(ALICE, h, None, 21, 4020)); self.put_rev(body)
        t0 = time.monotonic(); cr = self.credit(h); dt = time.monotonic() - t0
        self.assertEqual(cr, [(21, 4020, SID_A)])
        self.assertLess(dt, 0.5)

    def test_simultaneous_duplicates_are_not_errors(self):
        (a, ha), _, _ = self.chain()
        line = statement(ALICE, ha, None, 21, 40)
        out = []
        def go(fn, arg): out.append(fn(arg)['ok'])
        ts = [threading.Thread(target=go, args=(f, x)) for f, x in ((self.put_rev, a), (self.put_rev, a), (self.put_st, line), (self.put_st, line))]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertEqual(sorted(out), [1, 1, 1, 1])

    def test_map_lists_signed_counts(self):
        (a, ha), _, _ = self.chain()
        self.put_st(statement(ALICE, ha, None, 21, 40)); self.put_rev(a)
        listed = self.c.get('/api/tasrev/map/bhop_eazy').get_json()['revisions']
        self.assertEqual([(r['sha'], r['signed']) for r in listed], [(ha, 1)])
        self.assertNotIn('pub', str(self.c.get('/api/tasrev/rev/%s' % ha).get_json()))


if __name__ == '__main__':
    unittest.main()
