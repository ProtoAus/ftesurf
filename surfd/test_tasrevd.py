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


def legal_revision(rows, parent=None, supply=None, startat=3):
    """P1100: canonical version 3 bytes and their hash; rows are ticks 1.. from the placement."""
    head = len(rows)
    lines = ['tasproject 3', 'map bhop_eazy', 'mapcrc 7f53da5d', 'zonecrc b305f211', 'pmpin %s' % PIN, 'assist tas',
             'origin local', 'saved 2026-10-29T00:00:00', 'revision 1']
    if parent: lines.append('parentsha %s' % parent)
    if parent is None: supply = (1, head)
    lines.append('supply none' if supply is None else 'supply %d %d' % supply)
    lines += ['start 0', 'baseat -416 -352 64.03125 0 0 0', 'startat %d' % startat, 'head %d' % head]
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
    def credit(self, sha):
        self.drain()
        return [tuple(c) for c in self.c.get('/api/tasrev/rev/%s' % sha).get_json()['credit']]
    def drain(self):
        with svc.connect(self.store) as db, svc.writing(db): svc.drain(db, 60)
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

    def test_a_legal_start_child_is_supply_checked_and_credited(self):
        a, ha = legal_revision([row(t) for t in range(1, 21)])
        b_rows = [row(t, 9) if 11 <= t <= 15 else row(t) for t in range(1, 21)]
        bad, _ = legal_revision(b_rows, parent=ha, supply=(1, 20))
        b, hb = legal_revision(b_rows, parent=ha, supply=(11, 15))
        self.assertEqual(self.put_rev(a)['ok'], 1)
        self.assertEqual(self.put_rev(bad)['ok'], 0)             # claims ticks it did not change
        self.put_st(statement(BOB, hb, ha, 11, 15)); self.assertEqual(self.put_rev(b)['ok'], 1)
        self.assertEqual(self.credit(hb), [(1, 10, 'unsigned'), (11, 15, SID_B), (16, 20, 'unsigned')])

    def test_a_legal_start_and_a_base_save_are_not_one_line(self):
        rows = [row(t) for t in range(1, 21)]
        v2, h2 = revision(0, rows)                              # base 0: the same ticks by number
        same = [row(t, 9) if t == 5 else row(t) for t in range(1, 21)]
        child, hc = legal_revision(same, parent=h2, supply=(5, 5))
        self.put_rev(v2)
        self.assertEqual(self.put_rev(child)['ok'], 0)
        # The other order: the child first, its base-save parent later -- still cannot tell.
        v2b, h2b = revision(0, [row(t, 3) for t in range(1, 21)])
        child2, hc2 = legal_revision([row(t, 3) if t != 7 else row(t, 4) for t in range(1, 21)], parent=h2b, supply=(7, 7))
        self.put_st(statement(BOB, hc2, h2b, 7, 7)); self.put_rev(child2)
        self.put_st(statement(ALICE, h2b, None, 1, 20)); self.put_rev(v2b)
        self.assertEqual(self.credit(hc2), [(1, 20, 'unknown-ancestry')])

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

    def test_a_same_inputs_copy_of_a_waiting_revision_takes_nothing(self):
        # Review 2 (F1/C1): X waits for its parent P; Y has X's map, base and rows (a re-rooted copy,
        # or a re-save) and arrives later. When P arrives X is credited, and Y takes X's credit.
        (a, ha), (b, hb), _ = self.chain()
        b_rows = [row(t, 9) if 31 <= t <= 35 else row(t) for t in range(21, 41)]
        root_copy, hcopy = revision(20, b_rows, baseat='0 0 64 0 0 1')
        resave, hres = revision(20, b_rows, parent=ha, supply=(31, 35), baseat='0 0 64 0 0 2')
        self.put_st(statement(ALICE, ha, None, 21, 40)); self.put_st(statement(BOB, hb, ha, 31, 35))
        self.put_rev(b); self.put_st(statement(MALLORY, hcopy, None, 21, 40))
        self.put_rev(root_copy); self.put_rev(resave)
        self.assertEqual(self.credit(hcopy), [(21, 40, 'unknown-ancestry')])
        self.put_rev(a)
        want = [(21, 30, SID_A), (31, 35, SID_B), (36, 40, SID_A)]
        self.assertEqual((self.credit(hb), self.credit(hcopy), self.credit(hres)), (want, want, want))

    def test_a_gap_in_the_earlier_copy_is_cannot_tell(self):
        # Review 2 (F2): root P, Z truncates it, Y restores it exactly; order Y, P, Z.
        p_rows = [row(t) for t in range(21, 61)]
        p, hp = revision(20, p_rows)
        z, hz = revision(20, p_rows[:20], parent=hp, supply=None)
        y, hy = revision(20, p_rows, parent=hz, supply=(41, 60))
        self.put_st(statement(ALICE, hp, None, 21, 60))
        self.put_rev(y); self.put_rev(p)
        self.assertEqual(self.credit(hp), [(21, 60, 'unknown-ancestry')])     # Y may descend from P: unseen Z
        self.put_rev(z)
        self.assertEqual((self.credit(hp), self.credit(hy)), ([(21, 60, SID_A)], [(21, 60, SID_A)]))

    def test_a_revert_deeper_than_any_cut_still_credits_the_first_supplier(self):
        # Review 2 (F3): 34 revisions between Alice's rows and their restoration.
        base_rows = [row(t) for t in range(21, 41)]
        a, ha = revision(20, base_rows); self.put_st(statement(ALICE, ha, None, 21, 40)); self.put_rev(a)
        cur, rows, prev = ha, [row(t, 1) for t in range(21, 41)], None
        m, hm = revision(20, rows, parent=cur, supply=(21, 40)); self.put_rev(m); cur = hm
        for k in range(2, 36):
            rows = rows[:19] + [row(40, k)]
            m, hm = revision(20, rows, parent=cur, supply=(40, 40)); self.put_rev(m); cur = hm
        rows = base_rows[:19] + [rows[19]]
        last, hl = revision(20, rows, parent=cur, supply=(21, 39)); self.put_rev(last)
        self.assertEqual(self.credit(hl)[0], (21, 39, SID_A))

    def test_a_long_chain_before_its_root_is_all_credited_once_drained(self):
        # Review 2 (F4): 70 descendants uploaded before their root.
        a_rows = [row(t) for t in range(21, 121)]
        a, ha = revision(20, a_rows); self.put_st(statement(ALICE, ha, None, 21, 120))
        cur, rows, revs = ha, list(a_rows), []
        for k in range(70):
            rows = rows[:k] + [row(21 + k, 5)] + rows[k + 1:]
            m, hm = revision(20, rows, parent=cur, supply=(21 + k, 21 + k)); revs.append((m, hm)); cur = hm
        self.put_st(statement(BOB, revs[-1][1], revs[-2][1], 90, 90))
        for m, hm in revs: self.put_rev(m)
        self.put_rev(a)
        self.assertEqual(self.credit(revs[-1][1]), [(21, 89, 'unsigned'), (90, 90, SID_B), (91, 120, SID_A)])

    def test_a_statement_in_the_same_second_after_publication_takes_nothing(self):
        # Review 2 (F5/C2): one clock second; the arrival sequence decides.
        (a, ha), _, _ = self.chain()
        self.put_st(statement(ALICE, ha, None, 21, 40)); self.put_rev(a)
        r = self.put_st(statement(MALLORY, ha, None, 21, 40))
        self.assertEqual((r['ok'], r['before_revision']), (1, False))
        self.assertEqual(self.credit(ha), [(21, 40, SID_A)])

    def test_a_body_that_is_not_the_revision_is_refused_even_when_the_hash_is_known(self):
        # Review 2 (F6).
        (a, ha), _, _ = self.chain()
        self.put_rev(a)
        self.assertEqual(self.put_rev(b'garbage\nrevsha %s\n' % ha.encode())['ok'], 0)

    def test_rows_at_or_before_the_parents_base_are_never_the_childs(self):
        # Review 2 (F8): a child with an earlier base than its parent.
        p, hp = revision(20, [row(t) for t in range(21, 41)])
        x, hx = revision(10, [row(t, 3) for t in range(11, 21)] + [row(t) for t in range(21, 41)], parent=hp, supply=None)
        self.put_st(statement(ALICE, hp, None, 21, 40)); self.put_rev(p); r = self.put_rev(x)
        self.assertEqual(r['ok'], 1, r)
        self.assertEqual(self.credit(hx), [(11, 20, 'unknown-ancestry'), (21, 40, SID_A)])

    def test_a_stored_statement_is_still_ok_when_the_store_is_full(self):
        # Review 2 (F9).
        (a, ha), _, _ = self.chain()
        line = statement(ALICE, ha, None, 21, 40)
        self.assertEqual(self.put_st(line)['ok'], 1)
        old = svc.STATEMENT_CAP; svc.STATEMENT_CAP = 1
        try: self.assertEqual(self.put_st(line)['ok'], 1)
        finally: svc.STATEMENT_CAP = old

    def test_a_fragmented_revision_is_cheap_to_read(self):
        # Review 2 (H1): a child that changes every other tick of 20000.
        rows = [row(t) for t in range(21, 20021)]
        a, ha = revision(20, rows); self.put_st(statement(ALICE, ha, None, 21, 20020)); self.put_rev(a)
        alt = [row(t, 7) if t % 2 else r for t, r in zip(range(21, 20021), rows)]
        b, hb = revision(20, alt, parent=ha, supply=(21, 20019)); self.put_st(statement(BOB, hb, ha, 21, 20019)); self.put_rev(b)
        self.drain()
        t0 = time.monotonic(); first = self.c.get('/api/tasrev/rev/%s' % hb).get_json(); t1 = time.monotonic()
        again = self.c.get('/api/tasrev/rev/%s' % hb).get_json(); t2 = time.monotonic()
        self.assertEqual(len(first['credit']), 20000)        # 21..20020, one range a tick
        self.assertEqual(first['credit'], again['credit'])
        self.assertLess(t1 - t0, 1.5); self.assertLess(t2 - t1, (t1 - t0) / 2 + 0.05)

    def test_a_late_ancestor_reaches_every_descendant(self):
        # Review 3 (F1): P -> M -> N -> C -> D; C restores P's rows (the copy rule), D edits tick 25.
        # M arrives last: C's credit does not change, but D read M's gap and must be recomputed.
        p_rows = [row(t) for t in range(21, 41)]
        p, hp = revision(20, p_rows)
        m_rows = [row(t, 1) if 31 <= t <= 35 else r for t, r in zip(range(21, 41), p_rows)]
        m, hm = revision(20, m_rows, parent=hp, supply=(31, 35))
        n_rows = [row(t, 2) if 36 <= t <= 40 else r for t, r in zip(range(21, 41), m_rows)]
        n, hn = revision(20, n_rows, parent=hm, supply=(36, 40))
        c, hc = revision(20, list(p_rows), parent=hn, supply=(31, 40))
        d_rows = [row(t, 3) if t == 25 else r for t, r in zip(range(21, 41), p_rows)]
        d, hd = revision(20, d_rows, parent=hc, supply=(25, 25))
        self.put_st(statement(ALICE, hp, None, 21, 40)); self.put_st(statement(BOB, hd, hc, 25, 25))
        for body in (p, n, c, d, m): self.put_rev(body)
        self.assertEqual(self.credit(hd), [(21, 24, SID_A), (25, 25, SID_B), (26, 40, SID_A)])

    def test_rebuild_repairs_a_store(self):
        (a, ha), (b, hb), _ = self.chain()
        self.put_st(statement(ALICE, ha, None, 21, 40)); self.put_rev(a); self.put_rev(b)
        with svc.connect(self.store) as db: db.execute("UPDATE revisions SET credit = '[]' WHERE sha = ?", (hb,))
        import subprocess
        out = subprocess.run([sys.executable, '-B', svc.__file__, '--store', str(self.store), 'rebuild'], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.credit(hb), [(21, 30, SID_A), (31, 35, 'unsigned'), (36, 40, SID_A)])

    def test_large_credits_are_cached_by_bytes_and_cost_reads(self):
        # Review 3 (attacker): a 96000-range credit read many times cannot grow the cache past its bytes.
        rows = [row(t) for t in range(21, 20021)]
        a, ha = revision(20, rows); self.put_st(statement(ALICE, ha, None, 21, 20020)); self.put_rev(a)
        shas = []
        for k in range(6):
            alt = [row(t, 7 + k) if t % 2 else r for t, r in zip(range(21, 20021), rows)]
            b, hb = revision(20, alt, parent=ha, supply=(21, 20019)); self.put_st(statement(BOB, hb, ha, 21, 20019)); self.put_rev(b)
            shas.append(hb)
        self.drain()
        app = self.c.application
        for i, h in enumerate(shas):
            self.now[0] += 60
            self.assertEqual(len(self.c.get('/api/tasrev/rev/%s' % h).get_json()['credit']), 20000)
            self.assertLessEqual(app.tasrevd_cache_bytes(), svc.CACHE_BYTES)
        # One 20000-range read costs about 15 of the minute's 60.
        self.now[0] += 60
        codes = [self.c.get('/api/tasrev/rev/%s' % shas[0]).get_json().get('status', 200) for _ in range(6)]
        self.assertEqual(codes[:3], [200, 200, 200]); self.assertEqual(codes[-1], 429)

    def test_a_flood_of_unlinked_statements_cannot_block_a_linked_signer(self):
        # Review 3 (attacker): 32 junk statements from free keys fill the unlinked cap only.
        (a, ha), _, _ = self.chain()
        for k in range(8):
            for c in range(4):
                self.assertEqual(self.put_st(statement(bytes([90 + k]) * 32, ha, None, 21, 40, code=('%02x' % c) * 32))['ok'], 1)
        self.assertEqual(self.put_st(statement(CAROL, ha, None, 21, 40))['ok'], 0)      # unlinked: the cap
        self.assertEqual(self.put_st(statement(ALICE, ha, None, 21, 40))['ok'], 1)      # linked: still takes
        self.put_rev(a)
        self.assertEqual(self.credit(ha), [(21, 40, SID_A)])

    def test_stored_bytes_count_against_the_store_and_the_day(self):
        # Review 4 (attacker): a fragmented credit is several times its body; both caps see it.
        rows = [row(t) for t in range(21, 4021)]
        a, ha = revision(20, rows); self.put_rev(a)
        alt = [row(t, 7) if t % 2 else r for t, r in zip(range(21, 4021), rows)]
        b, hb = revision(20, alt, parent=ha, supply=(21, 4019)); self.put_st(statement(BOB, hb, ha, 21, 4019)); self.put_rev(b)
        with svc.connect(self.store) as db:
            st = db.execute('SELECT size, stored FROM revisions WHERE sha = ?', (hb,)).fetchone()
            day = db.execute('SELECT SUM(bytes) FROM uploads').fetchone()[0]
        self.assertGreater(st['stored'], 2 * st['size'])
        self.assertGreaterEqual(day, st['stored'])
        old = svc.STORE_CAP; svc.STORE_CAP = st['stored'] + len(a) + 100
        try:
            c, hc = revision(20, [row(t, 8) if t % 2 else r for t, r in zip(range(21, 4021), rows)], parent=ha, supply=(21, 4019))
            self.assertEqual(self.put_rev(c)['status'], 507)
        finally: svc.STORE_CAP = old

    def test_statements_whose_revision_never_arrives_are_dropped(self):
        # Review 4 (attacker): invented shas cannot fill the statement store for good.
        (a, ha), _, _ = self.chain()
        for k in range(5): self.put_st(statement(bytes([60 + k]) * 32, 'ab' * 32, None, 21, 40))
        self.put_st(statement(ALICE, ha, None, 21, 40))
        self.now[0] += svc.ORPHAN_DAYS * 86400 + 10
        self.put_rev(a)
        self.put_st(statement(CAROL, 'cd' * 32, None, 21, 40))       # any POST prunes a slice
        with svc.connect(self.store) as db:
            left = db.execute('SELECT sha FROM statements ORDER BY seq').fetchall()
        self.assertEqual([r['sha'] for r in left], [ha, 'cd' * 32])
        self.assertEqual(self.credit(ha), [(21, 40, SID_A)])

    def test_far_apart_bases_cost_only_the_rows_held(self):
        # Review 4 (flow): the row diff walked every tick between two bases.
        p, hp = revision(15999990, [row(t) for t in range(15999991, 15999993)])
        c, hc = revision(0, [row(1)], parent=hp, supply=None)
        self.put_rev(p)
        t0 = time.monotonic(); r = self.put_rev(c); dt = time.monotonic() - t0
        self.assertEqual(r['ok'], 1, r); self.assertLess(dt, 1.0)

    def test_subtract_matches_a_set(self):
        import random
        rnd = random.Random(5)
        for _ in range(500):
            xs = sorted(rnd.sample(range(60), rnd.randint(0, 40))); ys = sorted(rnd.sample(range(60), rnd.randint(0, 40)))
            got = [t for a, z in svc.subtract(svc.to_ranges(xs), svc.to_ranges(ys)) for t in range(a, z + 1)]
            self.assertEqual(got, sorted(set(xs) - set(ys)))

    def test_odd_digits_in_before_are_ignored(self):
        self.assertEqual(self.c.get('/api/tasrev/map/bhop_eazy?before=\u00b2').get_json()['ok'], 1)

    def test_reads_are_limited_per_peer(self):
        codes = [self.c.get('/api/tasrev/map/bhop_eazy').get_json().get('status', 200) for _ in range(svc.PEER_READS + 1)]
        self.assertEqual((codes[0], codes[-1]), (200, 429))
        self.now[0] += 60
        self.assertEqual(self.c.get('/api/tasrev/map/bhop_eazy').get_json()['ok'], 1)

    def test_map_lists_signed_counts(self):
        (a, ha), _, _ = self.chain()
        self.put_st(statement(ALICE, ha, None, 21, 40)); self.put_rev(a)
        listed = self.c.get('/api/tasrev/map/bhop_eazy').get_json()['revisions']
        self.assertEqual([(r['sha'], r['signers']) for r in listed], [(ha, 1)])
        self.assertNotIn('pub', str(self.c.get('/api/tasrev/rev/%s' % ha).get_json()))


if __name__ == '__main__':
    unittest.main()
