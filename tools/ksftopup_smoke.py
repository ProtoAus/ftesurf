#!/usr/bin/env python3
"""Acting style selectors and POST queue: two VMs, real private socket/HTTP.
No public requests, install swaps, owner accounts/data or shared log names.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--qc-artifacts', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    a = ap.parse_args()
    out = a.output_dir.resolve()
    if not any((p/'OWNER.md').is_file() for p in (out, *out.parents)):
        raise ValueError('output-dir requires an owned task root')
    out.mkdir(exist_ok=False, parents=True)
    home = out/'surfd'; home.mkdir()
    os.environ.update(SURFD_HOME=str(home), SURFD_DB=str(home/'fixture.db'),
                      SURFD_MAPS=str(home/'maps'), SURFD_ZONES=str(home/'zones'),
                      SURFD_ENV=str(home/'no-secrets.env'), SURFD_ADMIN_HASH='',
                      SURFD_BOARD_URL='', SURFD_RANKED_LINKED='0', SURFD_PUBLIC_HOST='')
    sys.path.insert(0, str(ROOT/'surfd'))
    import surfd as S
    from werkzeug.serving import make_server
    from flask import request
    hits = []

    @S.app.after_request
    def record(resp):
        hits.append([request.method, request.path, dict(request.args), resp.status_code])
        return resp

    db = S.connect()
    with db:
        for i, (style, name, ms) in enumerate([('clean','ForwardFixture',1500),
                                             ('sw','SidewaysFixture',500),
                                             ('hsw','HalfSideFixture',600),
                                             ('bw','BackwardFixture',700)]):
            db.execute("INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,"
                       "flags,node,runid,submitted,replay_id) VALUES('surf_dune',0,0,'ksf',?,?,?,?,100,?,?,"
                       "'ksf','',1,0)", (style,str(76561197960265729+i),name,ms//10,ms,0))
    db.close()
    consent = out/'consent.txt'
    consent.write_text('version 5\n// synthetic local fixture consent, not owner acceptance\n')
    server = make_server('127.0.0.1', 19869, S.app)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        cmd = [sys.executable,str(ROOT/'tools/runlines_smoke.py'),
               str(ROOT/'ftesurf/cfg/test/p699ksf.cfg'), '--output-dir',str(out),
               '--mount','--dedicated','--port','27617','--timeout','130',
               '--put','data/consent.txt='+str(consent)]
        for flag, file in [('--ssqc','qwprogs.dat'),('--csqc','csprogs.dat'),('--mqc','menu.dat')]:
            cmd += [flag,str(a.qc_artifacts/file)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        (out/'runtime.log').write_text(result.stdout+result.stderr)
        if result.returncode:
            raise RuntimeError('runtime failed; see '+str(out/'runtime.log'))
    finally:
        server.shutdown(); worker.join(); server.server_close()
        (out/'http.json').write_text(json.dumps(hits,indent=2))
    gets = {q.get('style') for method,path,q,code in hits if method == 'GET' and path == '/api/board' and code == 200}
    posts = {q.get('style') for method,path,q,code in hits if method == 'POST' and path == '/api/board' and code == 202}
    assert {'clean','sw','hsw','bw'} <= gets, ('styles did not act', gets)
    assert {'sw','hsw'} <= posts, ('both VMs must enqueue their selected style', posts)
    db = S.connect()
    try:
        keys = db.execute('SELECT map,track,leg,style,state FROM ksftopup ORDER BY style').fetchall()
        assert [tuple(r) for r in keys] == [('surf_dune',0,0,'hsw','queued'),('surf_dune',0,0,'sw','queued')], keys
    finally:
        db.close()
    text = next(out.glob('ftesurf-runlines-*/ftesurf/logs/runlines_smoke.log')).read_text(errors='replace')
    assert 'scores: KSF top-up queued (code 202)' in text
    assert 'board: KSF top-up queued (code 202)' in text
    print('PASS acting Forward/SW/HSW/BW GETs; CSQC SW and menu HSW POSTs; durable style-isolated queues')
    print('Screenshots retained in', out)


if __name__ == '__main__':
    main()
