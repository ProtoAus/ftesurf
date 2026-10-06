#!/usr/bin/env python3
"""Authenticated snapshot API + actual receipt DOM; no live data or network."""
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile

import admin
import test_admin as at
import test_sweep as suite

check = at.check
CONNECTIONS = []


def case_api():
    m = at.fresh(SURFD_ADMIN_HASH=admin.hash_password('test password only', n=2**10),
                 SURFD_ADMIN_SECRET='temporary-test-secret-not-a-real-secret', SURFD_ADMIN_INSECURE_COOKIE='1')
    import admin as a
    c = m.connect()
    CONNECTIONS.append(c)
    rid = suite.add_replay(c, m.RUNS_DIR, 'bhop_eazy', 'fixture.rec')
    c.execute('UPDATE replays SET runid = ? WHERE id = ?', ('synthetic', rid))
    c.execute("INSERT INTO receipts(runid,map,pub,verdict,angles,reason,at,journal,journal_reason)"
              " VALUES('synthetic','bhop_eazy','key','VALID','OK','',1,'OK','measured')")
    c.commit()
    route = '/admin/api/run/%d' % rid
    anon = m.app.test_client()
    before = anon.get('/api/board?map=bhop_eazy').get_json()
    check('API: unauthenticated caller refused', anon.get(route).status_code, 401)
    client = m.app.test_client()
    check('API: login CONTROL ACTS', at.login(client, 'test password only').status_code, 302)
    snap = {'version': 1, 'metrics': {'identity_judged': 5, 'identity_mouse_frames': 0,
                                    'identity_yaw_exclusions': {'seed': 1},
                                    'join_declared_transform_profile': False}}
    for raw, expected in (
            ('', None), (json.dumps(snap), snap), ('{broken', None),
            ('{"version":2,"metrics":{}}', None), ('{"version":true,"metrics":{}}', None),
            ('{"version":1,"metrics":{"identity_mouse_pct":NaN}}', None),
            ('{"version":1,"metrics":{"identity_mouse_pct":Infinity}}', None),
            ('{"version":1,"metrics":{"identity_judged":true}}', None),
            ('{"version":1,"metrics":{"identity_judged":10000000000000}}', None),
            ('{"version":1,"metrics":{"identity_judged":-1}}', None),
            ('{"version":1,"metrics":{"identity_mouse_frames":"<script>bad</script>"}}', None),
            ('{"version":1,"metrics":{"identity_yaw_exclusions":{"<img>":1}}}', None),
            ('{"version":1,"metrics":{"nonce":1}}', None), (' '*8193, None),
            ('{"version":1,"metrics":{}}', {'version': 1, 'metrics': {}})):
        c.execute('UPDATE receipts SET journal_metrics=?', (raw,));c.commit()
        reply = client.get(route)
        check('API: malformed/historical snapshot cannot break detail', reply.status_code, 200)
        check('API: bounded typed snapshot or explicit unknown', reply.get_json()['receipt'].get('journal_metrics'), expected)
        check('API: journal/signature/angles unchanged',
              tuple(reply.get_json()['receipt'][k] for k in ('journal','verdict','angles')), ('OK','VALID','OK'))
    check('API: public board unchanged', anon.get('/api/board?map=bhop_eazy').get_json(), before)
    check('API: public board exposes no metrics', 'journal_metrics' in json.dumps(before), False)
    c.execute('ALTER TABLE receipts DROP COLUMN journal_metrics');c.commit()
    reply = client.get(route)
    check('API: unmigrated receipt answered', reply.status_code, 200)
    check('API: unmigrated snapshot explicitly unknown', reply.get_json()['receipt'].get('journal_metrics'), None)
    check('parser: unavailable has typed field', hasattr(a, 'receipt_metrics'), True)
    c.close()


def case_dom():
    text = open(os.path.join(os.path.dirname(__file__), 'templates', 'admin_run.html'), encoding='utf-8').read()
    block = text[text.index('  const card = document.getElementById("rcptcard");'):text.index('  renderKey(j);')]
    harness = r'''
const j={receipt:JSON.parse(process.argv[2])};
class Element {
 constructor(tag,cls,text) {this.tag=tag;this.text=text || '';this.children=[];}
 append(...items) {this.children.push(...items);}
 replaceChildren() {this.children=[];}
 set innerHTML(v) {throw Error('untrusted HTML');}
}
const nodes={rcptcard:new Element('div'),rcpt:new Element('dl')};
const document={getElementById:id=>nodes[id]};
const el=(tag,cls,text)=>new Element(tag,cls,text);
const pill=(text,cls)=>el('span',cls,text);
const RCPT_CLS={},ANG_CLS={},JRN_CLS={}; const fmtDate=()=> 'date';
let summary; const summarise=(id,bad)=>{summary=bad;};
'''+block+r'''
const flat=n=>n.text+n.children.map(flat).join('');
console.log(JSON.stringify({text:flat(nodes.rcpt),summary}));
'''
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'render.js')
        with open(path,'w',encoding='utf-8') as f:f.write(harness)
        for snap, phrase in (
                (None, 'unavailable (no stored metric snapshot)'),
                ({'version':1,'metrics':{}}, 'reader ran; no numeric measurements available'),
                ({'version':1,'metrics':{'identity_yaw_judged':5,'identity_yaw_mouse_frames':0,
                                       'identity_yaw_exclusions':{'seed':1},'join_checked':4}},
                 'yaw judged frames5')):
            receipt = dict(journal_metrics=snap, journal='FAULT', journal_reason='<img> & <script>bad</script>',
                           verdict='VALID', angles='OK', pub='key', at=1, identity_bound=True)
            p = subprocess.run(['node',path,json.dumps(receipt)],capture_output=True,text=True)
            check('DOM: real renderer ACTS without HTML sinks',p.returncode,0)
            if p.returncode:continue
            result=json.loads(p.stdout)
            check('DOM: snapshot/unknown displayed',phrase in result['text'],True)
            check('DOM: content FAULT never changes signature summary',result['summary'],False)
            check('DOM: diagnostic prose stays literal','<img> & <script>bad</script>' in result['text'],True)
            if snap and snap['metrics']:
                check('DOM: measured zero remains zero','identity yaw mouse frames0' in result['text'],True)
                check('DOM: exclusion ledger/denominator visible',
                      ('seed: 1' in result['text'], 'counts-join checked windows4' in result['text']), (True,True))


def main():
    cases=[case_api]
    if shutil.which('node'):cases.append(case_dom)
    else:print('SKIP DOM: Node unavailable')
    first_home = len(at.HOMES)
    try:
        for case in cases:
            try:case()
            except Exception as e:check(case.__name__, '%s: %s' % (type(e).__name__,e), 'no exception')
    finally:
        for c in CONNECTIONS:
            c.close()
        CONNECTIONS.clear()
        for home in at.HOMES[first_home:]:
            for h in logging.getLogger('surfd').handlers[:]:
                if getattr(h, 'baseFilename', '').startswith(os.path.abspath(home) + os.sep):
                    logging.getLogger('surfd').removeHandler(h)
                    h.close()
            try:
                shutil.rmtree(home)
                check('cleanup: owned synthetic home removed', os.path.exists(home), False)
            except OSError as e:
                check('cleanup: owned synthetic home removal', type(e).__name__, 'removed')
    print('%d failed' % len(at.FAILED))
    return int(bool(at.FAILED))


if __name__ == '__main__':
    sys.exit(main())
