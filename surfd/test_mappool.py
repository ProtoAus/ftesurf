#!/usr/bin/env python3
"""Map manifest/pool + bidirectional imported boards. No network or live data."""
import json
import logging
import os
import shutil
import sys

import admin
import test_admin as A

FAILED = []

def check(label, got, want):
    print(('ok  ' if got == want else 'FAIL') + ' ' + label)
    if got != want:
        FAILED.append('%s: %r != %r' % (label, got, want))


def main():
    S = A.fresh(SURFD_ADMIN_HASH=admin.hash_password('manifest test password', n=2**10),
                SURFD_ADMIN_SECRET='s'*48, SURFD_ADMIN_INSECURE_COOKIE='1')
    import mapwatch as W
    W.S = S
    import test_zonefit as TZ
    fixture = os.path.join(S.DATA_DIR, 'donor-fixture')
    os.makedirs(fixture)
    bsp = TZ.vbsp((-4096,-4096,-4096), (4096,4096,4096), ('start_dest',))
    raw = TZ.zones()
    import hashlib
    with open(os.path.join(fixture,'surf_beta.bsp'),'wb') as f:
        f.write(bsp)
    with open(os.path.join(fixture,'surf_beta.json'),'wb') as f:
        f.write(raw)
    extra = {'surf_beta':{'sha':hashlib.sha1(bsp).hexdigest()}}
    inventory = {'surf_beta':'surf_beta'}
    check('held extra zones become donors only after hash and geometry checks',
          W.held_extra_donors(extra,inventory,inventory,fixture,fixture,{}), {'surf_beta'})
    extra['surf_beta']['sha'] = '0'*40
    check('wrong beta build cannot donate zones',
          W.held_extra_donors(extra,inventory,inventory,fixture,fixture,{}), set())
    extra['surf_beta']['sha'] = hashlib.sha1(bsp).hexdigest()
    with open(os.path.join(fixture,'surf_beta.json'),'wb') as f:
        f.write(b'{}')
    check('invalid beta zones cannot donate',
          W.held_extra_donors(extra,inventory,inventory,fixture,fixture,{}), set())
    os.makedirs(S.MAPS_DIR)
    os.makedirs(S.ZONES_DIR)
    watch = os.path.join(S.DATA_DIR, 'mapwatch')
    os.makedirs(watch)
    names = ('surf_aircontrol', 'surf_aircontrol_ksf', 'surf_aircontrol_fix',
             'surf_aircontrol_css', 'surf_aircontrol_v2', 'surf_other')
    for name in names:
        with open(os.path.join(S.MAPS_DIR, name+'.bsp'), 'wb') as f:
            f.write(b'held build')
    with open(os.path.join(S.ZONES_DIR, 'surf_aircontrol.json'), 'w') as f:
        f.write('{}')
    cat = {n: {'name': n, 'mode':'surf', 'src':'m' if n == names[0] else 'k', 'ktier':1}
           for n in names}
    cat[names[0]] = dict(name=names[0], mode='surf', src='m', mtier=2)
    cat[names[3]]['of'] = names[0]  # archive-compared _css, never guessed
    inv = {n:n for n in names}
    W.link_ports(cat, inv, {names[0]})
    check('known KSF suffix links to held Momentum root', cat[names[1]].get('of'), names[0])
    check('_fix links too', cat[names[2]].get('of'), names[0])
    check('version suffix never collapsed', cat[names[4]].get('of'), None)
    check('root inherits independent KSF rating', cat[names[0]].get('ktier'), 1)
    own = {'surf_a':{'src':'m'}, 'surf_a_ksf':{'src':'km'}}
    W.link_ports(own, {n:n for n in own}, set(own))
    check('a Momentum map of its own is not folded', own['surf_a_ksf'].get('of'), None)
    with open(os.path.join(watch, 'catalogue.json'), 'w') as f:
        json.dump({'maps':cat}, f)
    with open(os.path.join(watch, 'mapdl.txt'), 'w') as f:
        f.write('FTESURF-MAPDL 1\n')
        for n in names:
            f.write('dl %s surf %s 2 1 2026-10-14 0 %d %d%s\n' %
                    (n,cat[n]['src'],cat[n].get('mtier',0),cat[n].get('ktier',0),
                     ' '+cat[n]['of'] if cat[n].get('of') else ''))
    S.maps_reset()
    S._variants['at'] = None
    c = S.app.test_client()
    check('anonymous manifest is private', c.get('/admin/api/maps').status_code, 401)
    check('anonymous page redirects to login', c.get('/admin/maps').status_code, 302)
    check('login acts', A.login(c, 'manifest test password').status_code, 302)
    with c.session_transaction(path='/admin') as session:
        csrf = session['csrf']
    def setmap(name, value, token=csrf, **kw):
        return c.post('/admin/api/maps', data={'map':name,'enabled':value,'csrf':token}, **kw)
    data = c.get('/admin/api/maps').get_json()['maps']
    check('manifest lists every held build', len(data), len(names))
    check('enabled default and missing-zone flag differ',
          [(r['enabled'],r['zoned']) for r in data[:2]], [(True,True),(True,False)])
    check('new page renders', c.get('/admin/maps').status_code, 200)
    check('fleet links manifest', b'/admin/maps' in c.get('/admin/').data, True)
    parsed = A.js_parses('admin_maps.html')
    if parsed is None:
        print('skip page JavaScript parse (Node is absent; exercised on Windows)')
    else:
        check('page JavaScript parses', parsed, True)
    check('missing CSRF refused', setmap(names[0],'0',token='').status_code, 400)
    check('cross-origin refused despite token', setmap(names[0],'0',headers={'Sec-Fetch-Site':'same-site'}).status_code, 403)
    check('invalid enabled flag refused', setmap(names[0],'false').status_code, 400)
    check('unknown map refused', setmap('surf_absent','0').status_code, 404)
    check('path traversal refused', setmap('../surf_aircontrol','0').status_code, 400)
    check('disable acts', setmap(names[0],'0').get_json()['ok'], True)
    check('disabled join denied', c.get('/api/join?map='+names[0]).status_code, 403)
    S.migrate()
    check('policy survives migration/restart', c.get('/api/join?map='+names[0]).status_code, 403)
    body = c.get('/api/board?maps=1').get_data(as_text=True)
    check('disabled row retained to override mounted maps',
          next(x for x in body.splitlines() if x.startswith('dl '+names[0]+' ')).endswith(' - 1 0'), True)
    check('missing zone flag is per build',
          next(x for x in body.splitlines() if x.startswith('dl '+names[1]+' ')).endswith(' '+names[0]+' 0 1'), True)
    check('enable reverses policy', setmap(names[0],'1').get_json()['ok'], True)
    check('enabled join reaches allocator (no lobbies)', c.get('/api/join?map='+names[0]).status_code, 503)
    check('files untouched', os.path.isfile(os.path.join(S.MAPS_DIR,names[0]+'.bsp')), True)
    db = S.connect()
    for mp,tier,player,ms in ((names[0],'momentum','mom',41000),
                              (names[1],'ksf','ksf',40000),
                              (names[0],'ranked','native-root',50000),
                              (names[1],'ranked','native-port',45000),
                              (names[4],'ksf','version-only',20000)):
        db.execute("INSERT INTO runs (map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,submitted,replay_id) VALUES (?,0,0,?,'clean',?,?,?,100,?,0,'p1','',1,0)",
                   (mp,tier,player,player,ms//10,ms))
    db.commit()
    db.close()
    for mp, native in ((names[0],'native-root'), (names[1],'native-port'), (names[3],None)):
        game = c.get('/api/board',query_string={'map':mp,'tier':'combined'}).get_json()
        web = c.get('/board/api/map',query_string={'map':mp,'tier':'combined'}).get_json()
        expected = ['ksf','mom'] + ([native] if native else [])
        check(mp+' game imports shared / natives isolated', [r['name'] for r in game['rows']], expected)
        check(mp+' website uses same scope', [r['name'] for r in web['rows']], expected)
        check(mp+' website counts same rows', web['n'], len(expected))
        check(mp+' website links held builds', web['builds'], sorted(names[:4]))
    check('unrelated version keeps own board',
          [r['name'] for r in c.get('/board/api/map?map='+names[4]+'&tier=combined').get_json()['rows']], ['version-only'])
    setmap(names[1], '0')
    check('disable preserves board history', c.get('/board/api/map?map='+names[1]).status_code, 200)
    print('\n%d failed' % len(FAILED))
    for fail in FAILED:
        print(fail)
    return bool(FAILED)


if __name__ == '__main__':
    try:
        sys.exit(main())
    finally:
        logging.shutdown()
        for home in A.HOMES:
            shutil.rmtree(home)
