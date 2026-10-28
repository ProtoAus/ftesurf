"""P1091: surfd/tasrevd.py, the TAS revision and statement service (plan 5.3) and its credit (5.4)."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import ed25519
import tasrev as tr
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tasrevd as svc

ALICE, BOB, CAROL = (bytes([n]) * 32 for n in (1, 2, 3))
SID_A, SID_B, SID_C = '76561190000000001', '76561190000000002', '76561190000000003'
CODE = 'c0de' * 16
PIN = 'pmsrcver=11 physmode=1'


def row(t, k=0): return (t % 5, k, 0, (t * 7) % 360, 0, 0, t % 2)


def revision(base, rows, parent=None, supply=None, mp='bhop_eazy'):
    """Canonical version 2 bytes and their hash; `rows` is a list of 7-tuples for base+1.."""
    head = base + len(rows)
    lines = ['tasproject 2', 'map %s' % mp, 'mapcrc 7f53da5d', 'zonecrc b305f211', 'pmpin %s' % PIN, 'assist tas',
             'origin local', 'saved 2026-10-29T00:00:00', 'revision 1']
    if parent: lines.append('parentsha %s' % parent)
    if parent is None: supply = (base + 1, head)
    lines.append('supply none' if supply is None else 'supply %d %d' % supply)
    lines += ['base 1 %s %d' % ('ab' * 32, base), 'baseat 0 0 64 0 0 0', 'head %d' % head]
    lines += ['i %s' % ' '.join(str(v) for v in r) for r in rows]
    lines.append('end %d' % len(rows))
    body = ('\n'.join(lines) + '\n').encode()
    h = tr.revhash(body)[0]
    return body + ('revsha %s\n' % h).encode(), h


def statement(seed, sha, parent, first, last, code=CODE):
    msg = tr.statement(sha, parent or '-', '7f53da5d', first, last, code)
    pub = ed25519.publickey(seed).hex()
    sig = ed25519.sign(seed, msg).hex()
    return 'tasrev 1 %s %s 7f53da5d %d %d %s %s %s' % (sha, parent or '-', first, last, code, pub, sig)


class Service(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); root = Path(self.tmp.name)
        self.store, self.main, self.codes = root / 'tasrev.db', root / 'accounts.db', root / 'codes.txt'
        svc.initialize(self.store)
        db = sqlite3.connect(self.main)
        db.executescript('CREATE TABLE accounts(steamid TEXT PRIMARY KEY, banned_at INTEGER);'
                         'CREATE TABLE keylinks(pub TEXT, steamid TEXT);')
        for sid in (SID_A, SID_B, SID_C): db.execute('INSERT INTO accounts VALUES (?, 0)', (sid,))
        for seed, sid in ((ALICE, SID_A), (BOB, SID_B)): db.execute('INSERT INTO keylinks VALUES (?, ?)', (ed25519.publickey(seed).hex(), sid))
        db.commit(); db.close()
        self.codes.write_text(CODE + '\n')
        self.now = [1000]
        self.c = svc.create_app(self.store, self.main, self.codes, clock=lambda: self.now[0]).test_client()

    def tearDown(self): self.tmp.cleanup()

    def put_rev(self, body): return self.c.post('/api/tasrev/revision', data=body, content_type='text/plain').get_json()
    def put_st(self, line): return self.c.post('/api/tasrev/statement', json={'line': line}).get_json()
    def credit(self, sha): return [(c['first'], c['last'], c['who']) for c in self.c.get('/api/tasrev/rev/%s' % sha).get_json()['credit']]

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
        (a, ha), _, _ = self.chain()
        bad = a.replace(b'revsha ' + ha.encode(), b'revsha ' + b'0' * 64)
        self.assertIn('revsha is not its hash', self.put_rev(bad)['error'])
        self.assertEqual(self.put_rev(b'tasproject 2\n')['ok'], 0)
        self.assertEqual(self.put_rev(a.replace(b'\n', b'\r\n'))['ok'], 0)
        line = statement(ALICE, ha, None, 21, 40)
        self.assertEqual(self.put_st(line[:-2] + ('00' if line[-2:] != '00' else '11'))['ok'], 0)
        self.assertEqual(self.put_st('tasrev 1 junk')['ok'], 0)
        self.assertEqual(self.c.get('/api/tasrev/rev/zz').get_json()['ok'], 0)

    def test_credit_follows_the_earliest_holder_and_reverts_do_not_launder(self):
        (a, ha), (b, hb), (c, hc) = self.chain()
        for body in (a, b, c): self.put_rev(body)
        self.put_st(statement(ALICE, ha, None, 21, 40))
        self.put_st(statement(BOB, hb, ha, 31, 35))
        self.put_st(statement(CAROL, hc, hb, 33, 33))   # Carol's key is not linked
        self.assertEqual(self.credit(hc), [(21, 30, SID_A), (31, 32, SID_B), (33, 33, SID_A), (34, 35, SID_B), (36, 40, SID_A)])

    def test_unknown_ancestry_and_unsigned(self):
        (a, ha), (b, hb), _ = self.chain()
        self.put_rev(b); self.put_st(statement(BOB, hb, ha, 31, 35))
        # Without the parent nobody can check what B changed, so B's claim waits for it.
        self.assertEqual(self.credit(hb), [(21, 40, 'unknown-ancestry')])
        self.put_rev(a)
        self.assertEqual(self.credit(hb), [(21, 30, 'unsigned'), (31, 35, SID_B), (36, 40, 'unsigned')])

    def test_a_key_linked_after_its_statement_is_credited_then_keeps_it(self):
        (a, ha), _, _ = self.chain()
        self.put_rev(a); self.put_st(statement(CAROL, ha, None, 21, 40))
        self.assertEqual(self.credit(ha), [(21, 40, 'unattributed')])
        db = sqlite3.connect(self.main); db.execute('INSERT INTO keylinks VALUES (?, ?)', (ed25519.publickey(CAROL).hex(), SID_C)); db.commit()
        self.now[0] += 10
        self.assertEqual(self.credit(ha), [(21, 40, SID_C)])
        db.execute('UPDATE keylinks SET steamid = ? WHERE pub = ?', (SID_A, ed25519.publickey(CAROL).hex())); db.commit(); db.close()
        self.now[0] += 10
        self.assertEqual(self.credit(ha), [(21, 40, SID_C)])   # a relink later does not move it

    def test_unreleased_code_and_wrong_ticks_earn_nothing(self):
        (a, ha), (b, hb), _ = self.chain()
        self.put_rev(a); self.put_rev(b)
        self.put_st(statement(ALICE, ha, None, 21, 40, code='beef' * 16))
        self.put_st(statement(BOB, hb, ha, 32, 35))          # a span that is not the revision's supply
        self.assertEqual(self.credit(hb), [(21, 30, 'unattributed'), (31, 35, 'unsigned'), (36, 40, 'unattributed')])
        show = self.c.get('/api/tasrev/rev/%s' % hb).get_json()
        self.assertEqual([s['about_this_revision'] for s in show['statements']], [False])

    def test_statement_first_seen_is_kept_and_map_lists(self):
        (a, ha), _, _ = self.chain()
        line = statement(ALICE, ha, None, 21, 40)
        s1 = self.put_st(line); self.now[0] += 99; s2 = self.put_st(line)
        self.assertEqual((s1['ok'], s1['revision'], s2['first_seen']), (1, False, s1['first_seen']))
        self.put_rev(a)
        listed = self.c.get('/api/tasrev/map/bhop_eazy').get_json()['revisions']
        self.assertEqual([(r['sha'], r['statements']) for r in listed], [(ha, 1)])


if __name__ == '__main__':
    unittest.main()
