#!/usr/bin/env python3
"""Shared game/web completion and automatic pool policy; synthetic data only.

--source selects a pristine control's surfd directory without copying live data.
--control requires the original stale-policy defects AND positive eligible rows.
"""
import argparse
import logging
from pathlib import Path
import shutil
import sys

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source', type=Path)
ap.add_argument('--control', action='store_true')
args = ap.parse_args()
if args.source:
    sys.path.insert(0, str(args.source.resolve()))

import admin
import test_admin as A

FAIL = []
CHECKS = 0


def check(label, got, want):
    global CHECKS
    CHECKS += 1
    ok = got == want
    print(('PASS ' if ok else 'FAIL ') + label)
    if not ok:
        FAIL.append(f'{label}: {got!r} != {want!r}')


def main():
    S = A.fresh(SURFD_ADMIN_HASH=admin.hash_password('completion fixture', n=2**10),
                SURFD_ADMIN_SECRET='s'*48, SURFD_ADMIN_INSECURE_COOKIE='1')
    names = ['surf_done', 'surf_next', 'surf_disabled', 'surf_unzoned',
             'bhop_done', 'bhop_next', 'bhop_nozones', 'bhop_embedded',
             'bhop_manual', 'df_other', 'de_other']
    zones = {'surf_done', 'surf_next', 'surf_disabled', 'bhop_done', 'bhop_next',
             'bhop_manual', 'df_other', 'de_other'}
    for folder in (S.MAPS_DIR, S.ZONES_DIR, S.ZONES_LOCAL_DIR):
        Path(folder).mkdir()
    for name in names:
        (Path(S.MAPS_DIR)/(name+'.bsp')).write_bytes(b'fixture only')
        if name in zones:
            directory = S.ZONES_LOCAL_DIR if name == 'bhop_done' else S.ZONES_DIR
            (Path(directory)/(name+'.json')).write_text('{}')
    # An independently acknowledged embedded timer must not imply a zone FILE.
    S.zonefit.has_timer = lambda p: Path(p).stem == 'bhop_embedded'
    S.maps_reset()
    bsp, timed = S.map_index()
    check('embedded-timer double actually reports a timed map', 'bhop_embedded' in timed, True)
    home = Path(S.DATA_DIR)
    tracks = home/'momtracks.tsv'
    tracks.write_text(''.join(f'{n}\t1\t2\t1\t0\t1\n' for n in names))
    S.MOMTRACKS_PATH = str(tracks)
    S._mt['at'] = -1e9
    watch = home/'mapwatch'; watch.mkdir()
    (watch/'mapdl.txt').write_text('FTESURF-MAPDL 1\n'+''.join(
        f'dl {n} {n.split("_")[0]} m 2 1 2026-10-15 0 2 0\n'
        for n in names if n.startswith(('surf_', 'bhop_'))) +
        'dl bhop_uninstalled bhop m 2 1 2026-10-15 0 2 0\n')
    db = S.connect()
    completed = {'surf_done', 'surf_disabled', 'surf_unzoned', 'bhop_done',
                 'bhop_nozones', 'bhop_embedded', 'bhop_manual', 'df_other', 'de_other'}
    for name in completed:
        db.execute("INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,submitted,replay_id) "
                   "VALUES(?,0,0,'momentum','clean','fixture-person','Fixture',100,100,1000,0,'fixture','',1,0)", (name,))
    db.execute("INSERT INTO map_pool VALUES('surf_disabled',0,1)")
    db.execute("INSERT INTO map_pool VALUES('bhop_manual',0,1)")
    db.commit()
    original_rows = db.execute('SELECT count(*) FROM runs').fetchone()[0]
    db.close()
    S.people_reset()
    c = S.app.test_client()
    handle = S.web_handle('fixture-person')
    expected = {'surf_done', 'surf_next', 'surf_unzoned', 'bhop_done', 'bhop_next'}

    def web_maps():
        data = c.get(f'/board/api/player/{handle}/maps').get_json()
        return data, {m['map'] for t in data['tiers'] for m in t['maps']}

    data, listed = web_maps()
    profile = c.get(f'/board/api/player/{handle}').get_json()
    game = c.get('/api/board', query_string={'player':handle}).get_json()
    check('eligible surf and local/online zoned bhop controls actually appear', expected <= listed, True)
    if args.control:
        check('CONTROL disabled maps still leak into completion', {'surf_disabled','bhop_manual'} <= listed, True)
        check('CONTROL non-surf and unzoned bhop still leak', {'df_other','de_other','bhop_nozones','bhop_embedded'} <= listed, True)
        check('CONTROL old total actually counts those forbidden maps', profile['completion']['of'], len(names))
        return
    check('website lists only eligible population', listed, expected)
    check('website bars count only eligible main-map finishes',
          (profile['completion']['done'], profile['completion']['of']), (3, 5))
    check('website per-tier lists and bars have one denominator',
          [(t['tier'],t['done'],t['of']) for t in data['tiers']],
          [(t['tier'],t['done'],t['of']) for t in profile['completion']['tiers']])
    check('in-game summary has the same completion', game.get('completion'), profile['completion'])
    gm = c.get('/api/board',query_string={'player':handle,'ct':'2'}).get_json()
    check('in-game completion list is the website population', {m['map'] for m in gm.get('maps',[])}, expected)
    check('in-game done and total match website', (gm.get('done'),gm.get('total')), (3,5))
    check('admin login acts', A.login(c,'completion fixture').status_code,302)
    with c.session_transaction(path='/admin') as ss:
        csrf = ss['csrf']
    def setmap(name, enabled):
        return c.post('/admin/api/maps',data={'map':name,'enabled':str(enabled),'csrf':csrf})
    manifest = {m['map']:m for m in c.get('/admin/api/maps').get_json()['maps']}
    check('admin effective state includes both automatic and manual disables',
          {n for n,m in manifest.items() if m['enabled']}, {'surf_done','surf_next','surf_unzoned','bhop_done','bhop_next'})
    check('admin explains the automatic bhop disable', bool(manifest['bhop_nozones'].get('policy')), True)
    check('admin manifest remains installed-build-only', 'bhop_uninstalled' in manifest, False)
    check('admin cannot enable a bhop without its zone file', setmap('bhop_nozones',1).status_code,400)
    check('admin cannot enable unrelated modes', setmap('df_other',1).status_code,400)
    check('manual disable acts after profiles and lists are warm', setmap('surf_done',0).status_code,200)
    check('manual disable removes a completed map without cache reset', web_maps()[1], expected-{'surf_done'})
    p = c.get(f'/board/api/player/{handle}').get_json()['completion']
    check('warm summary updates numerator AND denominator', (p['done'],p['of']), (2,4))
    check('in-game warm list also updates',
          c.get('/api/board',query_string={'player':handle,'ct':'2'}).get_json().get('total'),4)
    S.migrate()
    check('manual disable survives migration', web_maps()[1], expected-{'surf_done'})
    check('manual re-enable acts',setmap('surf_done',1).status_code,200)
    check('manual re-enable restores list',web_maps()[1],expected)
    feed = c.get('/api/board?maps=1').get_data(as_text=True)
    for name, enabled in [('bhop_nozones',0),('bhop_embedded',0),('bhop_uninstalled',0),('bhop_done',1),('surf_disabled',0)]:
        row = next(r for r in feed.splitlines() if r.startswith('dl '+name+' '))
        check('game feed effective policy: '+name,int(row.split()[-1]),enabled)
    check('join blocks automatic disable',c.get('/api/join?map=bhop_nozones').status_code,403)
    check('join blocks other mode',c.get('/api/join?map=df_other').status_code,403)
    check('join admits zoned bhop to allocator',c.get('/api/join?map=bhop_done').status_code,503)
    # New files change automatic policy, but never override a deliberate manual 0.
    (Path(S.ZONES_LOCAL_DIR)/'bhop_nozones.json').write_text('{}')
    S.maps_reset()
    check('a newly zoned bhop becomes eligible',web_maps()[1],expected|{'bhop_nozones'})
    check('manual-disabled zoned bhop remains excluded','bhop_manual' in web_maps()[1],False)
    (Path(S.ZONES_LOCAL_DIR)/'bhop_nozones.json').unlink()
    S.maps_reset()
    check('losing the zone file disables bhop again',web_maps()[1],expected)
    db = S.connect()
    remaining_rows = db.execute('SELECT count(*) FROM runs').fetchone()[0]
    db.close()
    check('map and run history is never deleted',
          (len(list(Path(S.MAPS_DIR).glob('*.bsp'))), remaining_rows),
          (len(names),original_rows))
    parsed=A.js_parses('admin_maps.html')
    if parsed is None:
        print('SKIP Node unavailable: admin JavaScript syntax')
    else:
        check('admin map JavaScript parses',parsed,True)


if __name__ == '__main__':
    try:
        main()
        print(f'\n{CHECKS} checks, {len(FAIL)} failed')
        for failure in FAIL:
            print(failure)
        sys.exit(bool(FAIL))
    finally:
        logging.shutdown()
        for home in A.HOMES:
            shutil.rmtree(home)
