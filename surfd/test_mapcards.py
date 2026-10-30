#!/usr/bin/env python3
"""P1062: small public map batches keep source/build/style/identity boundaries.

Run with TEMP/TMP/TMPDIR under an owned task root. Synthetic DB only; no packets,
production credentials, evidence files or live fleet admission are involved.
"""
import logging
import shutil
import test_admin as A


def main():
    S = A.fresh()
    db = S.connect()
    counter = 0

    def row(mapname, tier, player, ms, track=0, leg=0, style='clean'):
        nonlocal counter
        counter += 1
        db.execute(
            'INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,submitted,replay_id) '
            'VALUES(?,?,?,?,?,?,?,100,100,?,0,?,?,1,0)',
            (mapname, track, leg, tier, style, player, 'Synthetic player', ms,
             'fixture', 'fixture-run-'+str(counter)))

    me, other = 'fixture-me', 'fixture-other'
    row('surf_a', 'ranked', me, 10000)
    row('surf_a', 'ranked', other, 8000)
    row('surf_a', 'momentum', me, 7000)
    row('surf_a', 'momentum', other, 6000)
    row('surf_a', 'ksf', me, 9000)
    row('surf_a', 'community', me, 1)        # must not beat the requested sources
    row('surf_a', 'held', me, 2)
    row('surf_a', 'ranked', me, 3, style='tas')
    row('surf_a', 'momentum', me, 4, track=1)
    row('surf_a', 'ranked', me, 5, leg=1)
    row('surf_a_css', 'ranked', me, 12000)
    row('surf_a_css', 'ranked', other, 11000)
    row('surf_b', 'ksf', me, 20000)
    row('surf_c', 'ranked', other, 15000)
    row('surf_d', 'momentum', me, 2096300012)  # no float32 round-trip
    db.commit(); db.close(); S.people_reset()
    original_variant = S.variant_base
    S.variant_base = lambda n: 'surf_a' if n == 'surf_a_css' else original_variant(n)
    c = S.app.test_client(); who = S.web_handle(me)
    checks = 0

    def check(label, got, want):
        nonlocal checks
        assert got == want, (label, got, want)
        checks += 1
        print('PASS', label)

    def get(names, player=who):
        q = {'cards': names}
        if player is not None:
            q['player'] = player
        response = c.get('/api/board', query_string=q)
        assert response.status_code == 200, response.status_code
        return response.get_json()

    data = get('surf_a,surf_a_css,surf_b,surf_c,surf_missing,surf_d')
    cards = {r['map']: r for r in data['cards']}
    check('visible batch route acts before single-player profile dispatch',
          (data['v'], data['track'], data['leg'], data['style'], len(cards)), (1, 0, 0, 'clean', 6))
    check('public identity resolves and is echoed, no internal player key returned',
          (data['requested_player'], data['who'], data['player_known'], me in str(data), other in str(data)),
          (who, who, True, False, False))
    check('four minima exclude community, held, TAS, bonuses and stages',
          tuple(cards['surf_a'][k] for k in ('mine_wos','mine_all','wr_wos','wr_all','complete')),
          (10000, 7000, 8000, 6000, True))
    check('native build is distinct while imports use the established base scope',
          tuple(cards['surf_a_css'][k] for k in ('mine_wos','mine_all','wr_wos','wr_all')),
          (12000, 7000, 11000, 6000))
    check('import-only completion is valid, not invented as a WOS PB',
          (cards['surf_b']['mine_wos'], cards['surf_b']['mine_all'], cards['surf_b']['complete']),
          (None, 20000, True))
    check('known incomplete differs from unknown player',
          (cards['surf_c']['mine_all'], cards['surf_c']['wr_wos'], cards['surf_c']['complete']),
          (None, 15000, False))
    check('unrecorded map has explicit null times, not zero or a fabricated WR',
          cards['surf_missing'], dict(map='surf_missing', mine_wos=None, mine_all=None,
                                      wr_wos=None, wr_all=None, complete=False))
    check('integer milliseconds survive above float32 exact range', cards['surf_d']['mine_all'], 2096300012)
    for token in (None, 'f'*12, '1234abcd'):
        data = get('surf_a', token)
        item = data['cards'][0]
        check('unknown/unlinked token gives public WRs, not somebody else\'s records: '+str(token),
              (data['player_known'], data['who'], item['mine_wos'], item['mine_all'], item['complete'], item['wr_all']),
              (False, '', None, None, None, 6000))
    check('case normalization and duplicates do not multiply the batch',
          [r['map'] for r in get('SURF_A,surf_a')['cards']], ['surf_a'])
    for query in ({'cards':''}, {'cards':'bad/path'}, {'cards':'a'*65},
                  {'cards':','.join('surf_'+str(i) for i in range(17))},
                  {'cards':'surf_a','player':'not-a-public-handle'}):
        check('invalid/oversized identifiers refused', c.get('/api/board', query_string=query).status_code, 400)

    # P1080: the completed list is the cards' `complete`, for every map at once.
    db = S.connect()
    row('surf_e', 'community', me, 30000)    # community/held/TAS/bonus only: not complete
    row('surf_e', 'ranked', me, 30000, style='tas')
    row('surf_e', 'momentum', me, 30000, track=2)
    row('surf_z_css', 'ranked', me, 31000)  # native completion never leaks to its base
    db.commit(); db.close()
    import time
    S._variants.update(at=time.monotonic(), ports={},
                       of={'surf_a_css': 'surf_a', 'surf_b_css': 'surf_b', 'surf_z_css': 'surf_z',
                           'surf_a': 'surf_a', 'surf_b': 'surf_b'})

    def completed(token, source=None):
        query = {'completed': token}
        if source is not None:
            query['source'] = source
        response = c.get('/api/board', query_string=query)
        return response.status_code, response.get_json()

    code, data = completed(who)
    check('completed route acts before the profile dispatch, own identity only',
          (code, data['v'], data['player_known'], data['who'], data['style'], me in str(data)),
          (200, 1, True, who, 'clean', False))
    check('native, import-only and a variant complete through its base KSF run; no other player',
          data['maps'], ['surf_a', 'surf_a_css', 'surf_b', 'surf_b_css', 'surf_d', 'surf_z_css'])
    names = 'surf_a,surf_a_css,surf_b,surf_b_css,surf_c,surf_d,surf_e,surf_missing,surf_z,surf_z_css'
    cards = {r['map']: r for r in get(names)['cards']}
    check('legacy completed list equals each card\'s all-source complete flag',
          {n: n in data['maps'] for n in names.split(',')},
          {n: r['complete'] for n, r in cards.items()})
    check('explicit all preserves the legacy union', completed(who, 'all')[1]['maps'], data['maps'])
    code, data = completed(who, 'wos')
    check('P1130 source is echoed and only exact-build ranked main finishes count',
          (code, data['source'], data['maps']), (200, 'wos', ['surf_a', 'surf_a_css', 'surf_z_css']))
    check('WOS completed sort agrees with WOS card times, not imported complete flags',
          {n: n in data['maps'] for n in names.split(',')},
          {n: r['mine_wos'] is not None and r['mine_wos'] > 0 for n, r in cards.items()})
    check('bad completed source is refused', completed(who, 'ksf')[0], 400)
    check('empty completed source is refused', completed(who, '')[0], 400)
    for token in ('', 'f'*12, '1234abcd'):
        for source in (None, 'wos'):
            code, data = completed(token, source)
            check('unknown player is unknown, not "nothing completed": '+repr((token, source)),
                  (code, data['player_known'], data['who'], data['maps']), (200, False, '', []))
    check('malformed completed token refused',
          c.get('/api/board', query_string={'completed': 'bad/one'}).status_code, 400)
    print('PASS map cards:', checks, 'checks; synthetic DB only')


if __name__ == '__main__':
    try:
        main()
    finally:
        logging.shutdown()
        for home in A.HOMES:
            shutil.rmtree(home)
