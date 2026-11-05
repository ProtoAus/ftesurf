"""Explicit authenticated consistency requests; never rewrite historical evidence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from unittest import mock
import unittest

import test_admin_similarity as baseline


class Current(baseline.Similarity):
    def install_pair(self):
        self.peer = baseline.suite.add_replay(self.c, self.m.RUNS_DIR, 'bhop_eazy', '0000101_run.rec')
        self.pair(self.peer)
        self.paths = []
        capture = {'version': 1}
        for side, rid, body in (('a', self.rid, b'OPAQUE-A\r\n\x00'),
                                ('b', self.peer, b'DIFFERENT-OPAQUE-B\n')):
            row = self.c.execute('SELECT * FROM replays WHERE id=?', (rid,)).fetchone()
            path = Path(self.m.replay_file(row)[0])
            path.write_bytes(body)
            self.paths.append(path)
            capture[side] = {'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}
        self.c.execute('UPDATE sims SET source_capture=? WHERE b_id=?', (json.dumps(capture), self.peer))
        self.c.commit()
        self.pair_id = self.c.execute('SELECT id FROM sims WHERE b_id=?', (self.peer,)).fetchone()[0]
        # Cookie path is /admin; extract the real page's token like the existing controls.
        page = self.client.get('/admin/run/%d' % self.rid)
        self.assertEqual(page.status_code, 200)
        self.csrf = json.loads(page.get_data(as_text=True).split('const CSRF = ', 1)[1].split(';', 1)[0])
        return capture

    def current(self, rid=None, pair=None):
        response = self.client.post('/admin/api/run/%d/sources' % (rid or self.rid),
                                    data={'pair': str(self.pair_id if pair is None else pair), 'csrf': self.csrf},
                                    headers={'Sec-Fetch-Site': 'same-origin'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['ok'])
        return response.get_json()['message']

    def test_explicit_reads_match_both_buffers_no_database_or_public_change(self):
        self.install_pair()
        tables = ('sims', 'verdicts', 'reviews', 'replays', 'runs')
        before = {t: [tuple(r) for r in self.c.execute('SELECT * FROM ' + t)] for t in tables}
        public = self.m.app.test_client().get('/api/board?map=bhop_eazy').get_json()
        with mock.patch.object(self.a.os, 'read', wraps=os.read) as acted:
            result = self.current()
        self.assertGreaterEqual(acted.call_count, 4)  # Real bytes AND EOF for both sides.
        self.assertEqual((result['state'], result['a'], result['b']), ('matches', 'matches', 'matches'))
        self.assertTrue(result['historical_unchanged'])
        self.assertEqual({t: [tuple(r) for r in self.c.execute('SELECT * FROM ' + t)] for t in tables}, before)
        encoded = json.dumps(result)
        for protected in ('sha256', '0000100', '0000101', str(self.paths[0]), 'synthetic-owner'):
            self.assertNotIn(protected, encoded)
        self.assertEqual(self.m.app.test_client().get('/api/board?map=bhop_eazy').get_json(), public)
        self.assertFalse(self.detail()['similarity']['source_binding'])

    def test_default_anonymous_cross_origin_and_bad_csrf_never_read(self):
        self.install_pair()
        with mock.patch.object(self.a, '_current_source', side_effect=AssertionError('must not read')):
            self.assertEqual(self.detail()['similarity']['pairs'][0]['source_state'], 'captured')
            path = '/admin/api/run/%d/sources' % self.rid
            self.assertEqual(self.m.app.test_client().post(path, data={'pair': self.pair_id}).status_code, 401)
            self.assertEqual(self.client.get(path).status_code, 405)
            for fields, headers, status in (({'pair': self.pair_id, 'csrf': 'wrong'}, {}, 400),
                                             ({'pair': self.pair_id, 'csrf': self.csrf}, {'Sec-Fetch-Site': 'same-site'}, 403)):
                self.assertEqual(self.client.post(path, data=fields, headers=headers).status_code, status)

    def test_same_size_restored_mtime_change_preserves_ab_orientation(self):
        self.install_pair()
        before = self.paths[0].stat()
        original = self.paths[0].read_bytes()
        self.paths[0].write_bytes(b'X' + original[1:])
        os.utime(self.paths[0], ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual((self.paths[0].stat().st_size, self.paths[0].stat().st_mtime_ns),
                         (before.st_size, before.st_mtime_ns))
        result = self.current(self.peer)
        self.assertEqual((result['state'], result['a'], result['b']), ('differs', 'differs', 'matches'))

    def test_extra_byte_read_is_bounded_and_not_a_match(self):
        capture = self.install_pair()
        with self.paths[0].open('ab') as stream:
            stream.write(b'X' * 100000)
        count = 0
        largest = 0
        original = os.read

        def read(fd, size):
            nonlocal count, largest
            data = original(fd, size)
            count += len(data)
            largest = max(largest, size)
            return data

        with mock.patch.object(self.a.os, 'read', side_effect=read):
            result = self.current()
        self.assertEqual(result['a'], 'differs')
        self.assertEqual(result['b'], 'matches')
        self.assertEqual(count, capture['a']['bytes'] + 1 + capture['b']['bytes'])
        self.assertLessEqual(largest, 65536)

    def test_mutation_acts_then_is_unavailable_not_differs_or_matches(self):
        self.install_pair()
        inode = self.paths[0].stat().st_ino
        original = os.read
        changed = False

        def read(fd, size):
            nonlocal changed
            data = original(fd, size)
            if data and os.fstat(fd).st_ino == inode and not changed:
                changed = True
                with self.paths[0].open('ab') as stream:
                    stream.write(b'late')
            return data

        with mock.patch.object(self.a.os, 'read', side_effect=read):
            result = self.current()
        self.assertTrue(changed)
        self.assertEqual((result['state'], result['a'], result['b']), ('unavailable', 'unavailable', 'matches'))

    def test_missing_over_cap_and_expired_work_are_explicit(self):
        self.install_pair()
        self.paths[0].unlink()
        result = self.current()
        self.assertEqual((result['state'], result['a'], result['b']), ('unavailable', 'unavailable', 'matches'))
        with mock.patch.object(self.a, 'SIM_CURRENT_BYTES', 0), \
             mock.patch.object(self.a.os, 'read', side_effect=AssertionError('cap must precede read')):
            self.assertEqual(self.current()['state'], 'unavailable')
        with mock.patch.object(self.a, 'SIM_CURRENT_SECONDS', 0), \
             mock.patch.object(self.m, 'replay_file', side_effect=AssertionError('expired before resolution')):
            self.assertEqual(self.current()['state'], 'unavailable')

    def test_legacy_skip_invalid_off_panel_do_no_file_io(self):
        self.install_pair()
        for value, verdict in (('', 'compared'), ('{', 'compared'), (json.dumps({'version': 99}), 'compared'),
                               (json.dumps({'version': 1}), 'skip')):
            self.c.execute('UPDATE sims SET source_capture=?,verdict=?', (value, verdict)); self.c.commit()
            with mock.patch.object(self.m, 'replay_file', side_effect=AssertionError('unbound must not resolve')):
                self.assertEqual(self.current()['state'], 'unavailable')
        with mock.patch.object(self.a, '_current_source', side_effect=AssertionError('off-panel must not read')):
            self.assertEqual(self.current(pair=999999)['state'], 'unavailable')

    def test_borrowed_connection_does_not_replace_callers_progress_handler(self):
        self.install_pair()
        callbacks = []
        self.c.set_progress_handler(lambda: callbacks.append(1) or 0, 1)
        try:
            result = self.a.similarity_current(self.c, self.rid, self.pair_id, self.m.replay_file)
            self.assertEqual(result['state'], 'matches')
            before = len(callbacks)
            self.c.execute('SELECT COUNT(*) FROM replays').fetchone()
            self.assertGreater(len(callbacks), before)
        finally:
            self.c.set_progress_handler(None, 0)

    def test_actual_dom_click_posts_guarded_pair_and_keeps_historical_metrics(self):
        self.install_pair()
        if not shutil.which('node'):
            self.skipTest('Node absent; actual click exercised on supported Node host')
        template = Path(self.a.__file__).parent / 'templates/admin_run.html'
        text = template.read_text(encoding='utf-8')
        render = text[text.index('function renderSimilarity(value) {'):text.index('function renderKey(j) {')]
        post = text[text.index('async function post(path, fields, onReply) {'):text.index('// ---- the run, its review and its verdicts')]
        payload = self.detail()['similarity']
        js = r'''
class E {constructor(tag,cls,text){this.tag=tag;this.text=String(text??'');this.children=[];}
append(...x){this.children.push(...x);}replaceChildren(){this.children=[];}
set textContent(v){this.text=String(v);}set innerHTML(v){throw Error('HTML sink');}}
const box=new E('div'),document={getElementById:()=>box};
const el=(t,c,s)=>new E(t,c,s),fmtDate=n=>'date '+n;
const CSRF='fixture-token',RID=Number(process.argv[3]),calls=[];
const toast=()=>{},location={href:''};
const fetch=async(url,options)=>{calls.push([url,options.method,options.credentials,options.body.get('csrf'),options.body.get('pair')]);
return {status:200,json:async()=>({ok:true,message:{a:'matches',b:'differs',at:17,state:'differs',historical_unchanged:true}})};};
''' + post + render + r'''
(async()=>{renderSimilarity(JSON.parse(process.argv[2]));
const all=n=>typeof n==='string'?[]:[n,...n.children.flatMap(all)];
const button=all(box).find(n=>n.tag==='button');if(!button)throw Error('no action button');
await button.onclick();const flat=n=>typeof n==='string'?n:n.text+n.children.map(flat).join('');
console.log(JSON.stringify({calls,text:flat(box),enabled:button.disabled===false}));
})().catch(e=>{console.error(e);process.exit(1);});
'''
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / 'current-source-click.js'
            script.write_text(js, encoding='utf-8')
            result = subprocess.run(['node', str(script), json.dumps(payload), str(self.rid)],
                                    capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['calls'], [['/admin/api/run/%d/sources' % self.rid,
                                          'POST', 'same-origin', 'fixture-token', str(self.pair_id)]])
        self.assertTrue(value['enabled'])
        for phrase in ('A read bytes match', 'B read bytes differ', 'Historical measurements unchanged',
                       'not authenticity', 'rows compared', '80'):
            self.assertIn(phrase, value['text'])

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX nofollow/nonblocking FIFO control runs on actual Linux')
    def test_real_fifo_is_unavailable_without_blocking(self):
        capture = self.install_pair()
        self.paths[0].unlink()
        os.mkfifo(self.paths[0])
        started = time.monotonic()
        self.assertEqual(self.a._current_source(self.paths[0], capture['a'], started + 2), 'unavailable')
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(self.current()['b'], 'matches')


if __name__ == '__main__':
    unittest.main()
