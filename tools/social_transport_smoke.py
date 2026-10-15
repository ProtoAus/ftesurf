#!/usr/bin/env python3
"""Actual dedicated QC HTTP encoder at 41/42/64 rows; synthetic transport only.

Creates a TEST-ONLY SSQC manifest/copies beneath an owned --out. Never alters
production sources/progs/installs, proves no account authority and launches no
GUI. --mutant restores the original whole-array escape; its grader must fail.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--mutant', action='store_true')
    ap.add_argument('--port', type=int, default=27617)
    ap.add_argument('--http-port', type=int, default=27638)
    a = ap.parse_args()
    out = a.out.resolve()
    if not any((p/'OWNER.md').is_file() for p in (out, *out.parents)):
        ap.error('--out requires an ancestor OWNER.md')
    out.mkdir(exist_ok=False)
    for kind, port in ((socket.SOCK_DGRAM, a.port), (socket.SOCK_STREAM, a.http_port)):
        with socket.socket(socket.AF_INET, kind) as probe:
            probe.bind(('127.0.0.1', port))
    from flask import Flask, request
    from werkzeug.serving import make_server, WSGIRequestHandler
    app = Flask(__name__)
    observed = {n: [] for n in (41, 42, 64)}
    errors = []

    @app.post('/api/social/poll')
    def poll():
        try:
            rows = json.loads(request.form['roster'])
            n = len(rows)
            assert n in observed, 'wrong count'
            assert {row['token'] for row in rows} == {f'{i:064d}' for i in range(1, n+1)}
            assert all(row['hash'] == 'a'*64 and row['ack'] == (16777217 if n == 64 else 0) for row in rows)
            observed[n].append(time.monotonic())
        except (ValueError, KeyError, AssertionError):
            errors.append('malformed or incomplete roster')
            return {'ok': False}, 400
        return {'ok': True, 'players': []}

    class Quiet(WSGIRequestHandler):
        def log(self, *args):
            pass
    web = make_server('127.0.0.1', a.http_port, app, request_handler=Quiet)
    thread = threading.Thread(target=web.serve_forever, daemon=True)
    thread.start()
    gd = out/'rig/ftesurf'
    (gd/'maps').mkdir(parents=True)
    shutil.copyfile('C:/FTESurf/ftesurf/maps/surf_dune.bsp', gd/'maps/surf_dune.bsp')
    shutil.copyfile(ROOT/'default.fmf', gd.parent/'default.fmf')
    # Substitute only the terminal nonce stuffcmd in a TEST copy: all gating,
    # nonce creation, budget/backoff and state teardown execute real Account QC.
    account = (ROOT/'src/server/sv_account.qc').read_text()
    terminal = r'stuffcmd(e, sprintf("acct_hello %s\n", n));'
    assert account.count(terminal) == 1
    account = 'float sf_hellos;\n'+account.replace(terminal, 'sf_hellos = sf_hellos + 1;')
    (out/'account.qc').write_text(account)
    fixture = out/'fixture.qc'
    fixture.write_text('''// TEST ONLY: fake edicts exercise the real full-node encoder, no authority.
float sf_n, sf_tested;
void() SocialFixture_Renewal =
{
 local entity e;
 e = spawn(); e.classname = "renewal_fixture";
 e.acct_here = TRUE; e.acct_state = ACCT_LINKED;
 e.acct_hellos = ACCT_HELLOS; e.social_refresh = TRUE;
 e.acct_pin = strzone("synthetic"); e.acct_pin_t = time + 90;
 e.acct_tag = strzone("synthetic");
 Account_Think(e);
 if (sf_hellos || !e.social_refresh) error("renewal fixture: unexpired prompt not deferred");
 e.acct_pin_t = time - 1;
 e.acct_rq = 999; e.acct_rq_t = time;
 Account_Think(e);
 if (sf_hellos || !e.social_refresh) error("renewal fixture: active request not deferred");
 e.acct_rq_t = time - ACCT_RQLIFE - 1;
 Account_Think(e);
 if (sf_hellos != 1 || e.acct_pin != "" || e.acct_tag != "") error("renewal fixture: stale pin/request stranded renewal");
 if (e.acct_hellos != ACCT_HELLOS || e.social_delay != 30) error("renewal fixture: budget/backoff wrong");
 // Model one unsuccessful proof/HTTP reply, with pending state retained.
 e.acct_want = 0; e.social_retry = time - 1;
 Account_Think(e);
 if (sf_hellos != 2 || e.social_delay != 60) error("renewal fixture: retry not issued");
 Account_Disconnect(e); remove(e);
 print("renewal fixture passed: live prompt/request defer, expired state retires, exhausted budget retries\\n");
};
void() SocialFixture_Frame =
{
 local float n, i;
 local entity e, next;
 if (!sf_tested) { sf_tested = TRUE; SocialFixture_Renewal(); }
 n = time < 25 ? 41 : (time < 50 ? 42 : 64);
 if (n == sf_n) return;
 e = find(world, classname, "social_fixture");
 while (e) { next = find(e, classname, "social_fixture"); Social_Clear(e); remove(e); e = next; }
 for (i = 1; i <= n; i = i + 1)
 {
  e = spawn(); e.classname = "social_fixture";
  e.social_here = TRUE;
  e.social_token = strzone(sprintf("%064.0f", i));
  e.social_hash = strzone("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
  e.social_ack = strzone(n == 64 ? "16777217" : "0");
 }
 sf_n = n; social_next = 0;
};
''', encoding='utf-8')
    social = (ROOT/'src/server/sv_social.qc').read_text()
    if a.mutant:
        social = social.replace('return uri_escape(sprintf(', 'return sprintf(', 1)
        social = social.replace('token, hash, ack != "" ? ack : "0"));', 'token, hash, ack != "" ? ack : "0");', 1)
        social = social.replace('roster = "%5B";', 'roster = "[";').replace('n ? "%2C" : ""', 'n ? "," : ""')
        social = social.replace('strcat(roster, "%5D")', 'strcat(roster, "]")')
        social = social.replace('"&roster=", roster)', '"&roster=", uri_escape(roster))')
    (out/'social.qc').write_text(social)
    main_src = (ROOT/'src/server/sv_main.qc').read_text()
    assert main_src.count('Social_Frame();') == 1
    (out/'main.qc').write_text(main_src.replace('Social_Frame();', 'SocialFixture_Frame(); Social_Frame();'))
    lines = [str(gd/'qwprogs.dat')]
    for line in (ROOT/'src/sv_progs.src').read_text().splitlines()[1:]:
        if not line.strip() or line.lstrip().startswith('//'):
            continue
        if line == 'server/sv_social.qc':
            lines.append(str(out/'social.qc'))
        elif line == 'server/sv_account.qc':
            lines.extend([str(out/'account.qc'), str(fixture)])
        elif line == 'server/sv_main.qc':
            lines.append(str(out/'main.qc'))
        else:
            lines.append(str(ROOT/'src'/line))
    # This fteqcc old-style reader requires relative, unquoted input paths
    # and a same-src manifest (the production NoDeploy procedure does too).
    manifest = ROOT/'src'/('build-social-'+uuid.uuid4().hex+'.src')
    manifest.write_text('\n'.join(os.path.relpath(x, ROOT/'src').replace('\\', '/') for x in lines)+'\n')
    shutil.copyfile(manifest, out/'test.src')
    process = None
    try:
        c = subprocess.run([str(ROOT/'src/fteqcc64.exe'), '-srcfile', manifest.name],
                           cwd=ROOT/'src', text=True, capture_output=True)
        (out/'compile.log').write_text(c.stdout+c.stderr)
        if c.returncode or not (gd/'qwprogs.dat').is_file() or '0 warnings' not in c.stdout+c.stderr:
            raise RuntimeError('fixture build failed; see compile.log')
        cmd = ['C:/FTEQuake/fteqwsv64.exe', '-basedir', str(gd.parent), '-manifest',
               str(gd.parent/'default.fmf'), '-port', str(a.port), '+set', 'sv_public', '0',
               '+set', 'lobby_enable', '1', '+set', 'lobby_mode', '2',
               '+set', 'lobby_master', f'http://127.0.0.1:{a.http_port}',
               '+set', 'lobby_master_key', 'synthetic-test-key', '+log_enable', '1',
               '+log_name', 'transport', '+set', 'cfg_save_auto', '0',
               '+set', 'plug_loaddefault', '3', '+plug_load', 'hl2', '+map', 'surf_dune']
        with (out/'server-console.log').open('w') as log:
            process = subprocess.Popen(cmd, cwd='C:/FTESurf', stdout=log, stderr=log)
            end = time.monotonic()+82
            while time.monotonic() < end:
                if process.poll() is not None:
                    raise RuntimeError('owned dedicated server stopped early')
                if all(len(v) >= 4 and v[-1]-v[0] > 16 for v in observed.values()):
                    break
                time.sleep(.2)
        checks = {f'{n} rows intact across >16s': len(v) >= 4 and v[-1]-v[0] > 16
                  for n, v in observed.items()}
        checks['No malformed snapshot'] = not errors
        server_log = gd/'transport.log'
        checks['Renewal busy/live/expired/budget controls acted'] = server_log.is_file() and 'renewal fixture passed:' in server_log.read_text(errors='replace')
        (out/'verdict.json').write_text(json.dumps({'checks': checks,
            'poll_counts': {n: len(v) for n, v in observed.items()}, 'bad_polls': len(errors)}, indent=2))
        for name, ok in checks.items():
            print(('ok   ' if ok else 'FAIL ')+name)
        return 0 if all(checks.values()) else 1
    finally:
        manifest.unlink(missing_ok=True)
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        web.shutdown()
        thread.join(timeout=10)
        # Only our plain copied BSP/progs are disposable; source/logs stay.
        shutil.rmtree(gd/'maps')


if __name__ == '__main__':
    raise SystemExit(main())
