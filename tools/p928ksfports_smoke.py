#!/usr/bin/env python3
"""Bounded actual-client P928 controls, reusing runlines_smoke's owned overlay.

No upstream fetch or canonical fixture changes. The normalized/original inputs
are retained public KSF bytes; all edited headers are explicit counterfactuals.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--recording', type=Path, required=True)
p.add_argument('--original', type=Path, required=True)
p.add_argument('--manifest', type=Path, required=True)
p.add_argument('--board', type=Path, help='online mode: retained exact-map board containing replay21517')
p.add_argument('--out', type=Path, required=True)
p.add_argument('--csqc', type=Path, required=True)
p.add_argument('--ssqc', type=Path, required=True)
p.add_argument('--mqc', type=Path, required=True)
p.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
p.add_argument('--expect', choices=['linked', 'legacy', 'online'], required=True)
a = p.parse_args()
if a.expect == 'online' and not a.board:
    p.error('--expect online requires --board from the retained public response')
if not any((x / 'OWNER.md').is_file() for x in [a.out, *a.out.parents]):
    p.error('--out requires an ancestor OWNER.md')
a.out.mkdir(parents=True, exist_ok=False)
text = a.recording.read_text(encoding='utf-8')
assert '\nmap surf_chateau_fix\n' in text
assert hashlib.sha256(a.original.read_bytes()).hexdigest() == re.search(
    r'^foreign ksf ([0-9a-f]{64})$', text, re.M).group(1)
fixtures = {
    'source': text,
    'same': text.replace('\nmap surf_chateau_fix\n', '\nmap surf_chateau\n'),
    'unrelated': text.replace('\nmap surf_chateau_fix\n', '\nmap surf_not_linked\n'),
    'suffix': text.replace('\nmap surf_chateau_fix\n', '\nmap surf_chateau_v999\n'),
    'missing': text.replace('\nmap surf_chateau_fix\n', '\n'),
    'native-wrong': re.sub(r'^foreign ksf [^\n]+\n', '', text, flags=re.M),
}
for name, body in fixtures.items():
    (a.out / (name + '.rec')).write_bytes(body.encode())
(a.out / 'blank-mapdl.txt').write_bytes(b'FTESURF-MAPDL 1\n')
cmd = ['cfg_save_auto 0', 'name KsfPortControl', 'log_enable 1', 'log_dir logs',
       'log_name runlines_smoke', 'cl_idlefps 0', 'cl_maxfps 100', 'con_notifytime 0',
       'set rec_hid 0', 'set rec_upload 0', 'waitms 1500', 'map surf_chateau',
       'waitmap 60', 'waitms 6000', 'menu_restart', 'ui_close',
       'hud_watch_skipidle 0', 'hud_watch_path 1', 'hud_watch_info 1']
expectations = {}

def case(name, command, yes, advance=False):
    cmd.extend(['echo P928CASE ' + name, command, 'wait 5', 'replay pause'])
    if advance:
        cmd.extend(['replay seek 10', 'replay status', 'replay trace frames 40',
                    'replay play', 'wait 60', 'replay pause'])
    cmd.extend(['replay status', 'echo P928END ' + name])
    expectations[name] = dict(open=yes, advance=advance)

server = None
requests = []
if a.expect == 'online':
    # Empty local lists make the pre-board failure an acting metadata control.
    case('NO-FAMILY', 'replay cfg/test/p925-source.rec', False)
    row = next(r for r in json.loads(a.board.read_text(encoding='utf-8'))['rows'] if r['rep'] == 21517)
    row = dict(row, map='surf_chateau_fix', tr='ksf')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            u = urlsplit(self.path)
            q = parse_qs(u.query)
            requests.append(u.path + ('?maps=1' if q.get('maps') else ''))
            if u.path == '/api/board' and not q.get('maps'):
                body = dict(v=1, t=1700000000, map='surf_chateau', track=0, leg=0,
                            tier=q.get('tier', ['ksf'])[0], style='clean', name='',
                            rows=[row], counts={'ksf': 1, 'ranked': 0, 'momentum': 0},
                            family=['surf_chateau', 'surf_chateau_fix'])
                data = json.dumps(body).encode()
            elif u.path == '/api/replay/21517':
                data = text.encode()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream' if 'replay' in u.path else 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    terms = re.search(r'^#define FS_TERMS_ONLINE\s+(\d+)',
                      (ROOT / 'src/shared/sh_defs.qc').read_text(encoding='utf-8'), re.M).group(1)
    cmd.extend(['set rec_terms ' + terms,
                'lobby_dir "http://127.0.0.1:%d"' % server.server_port,
                'board_fetch 0 0 ksf clean', 'waitms 1800', 'board_status',
                'board_replay row 0', 'waitms 1800', 'board_status'])
    case('ONLINE', 'replay online 21517', True, True)
    cmd.extend(['board_replay row 0', 'wait 10', 'board_status'])
else:
    case('LINKED', 'replay cfg/test/p925-source.rec', a.expect == 'linked', True)
    cmd.append('screenshot p925-linked.png')
    case('EXACT-CONTROL', 'replay cfg/test/p925-same.rec', True, True)
    case('UNRELATED', 'replay cfg/test/p925-unrelated.rec', False)
    case('SUFFIX', 'replay cfg/test/p925-suffix.rec', False)
    case('MISSING', 'replay cfg/test/p925-missing.rec', False)
    case('NATIVE-WRONG', 'replay cfg/test/p925-native-wrong.rec', False)
case('RAW-LINKED', 'replay ksf cfg/test/p925-original.rec surf_chateau_fix 0 FW',
     a.expect != 'legacy', True)
case('RAW-UNRELATED', 'replay ksf cfg/test/p925-original.rec surf_not_linked 0 FW', False)
case('RAW-MISSING', 'replay ksf cfg/test/p925-original.rec "" 0 FW', False)
if a.expect != 'legacy':
    cmd.extend(['replay ksf cfg/test/p925-original.rec surf_chateau_fix 0 FW', 'wait 10',
                'map surf_null', 'waitmap 60', 'waitms 2000',
                'echo P928CASE MAPCHANGE', 'replay status', 'echo P928END MAPCHANGE'])
    expectations['MAPCHANGE'] = dict(open=False, advance=False)
cmd.extend(['echo RUNLINES COMPLETE', 'wait 3', 'quit'])
(a.out / 'control.cfg').write_bytes(('\n'.join(cmd) + '\n').encode())
args = [sys.executable, str(ROOT / 'tools/runlines_smoke.py'), str(a.out / 'control.cfg'),
        '--content', str(a.content), '--output-dir', str(a.out), '--mount',
        '--dedicated', '--map', 'surf_chateau',
        '--csqc', str(a.csqc), '--ssqc', str(a.ssqc), '--mqc', str(a.mqc)]
for name in fixtures:
    args += ['--also', 'p925-' + name + '.rec=' + str(a.out / (name + '.rec'))]
args += ['--also', 'p925-original.rec=' + str(a.original)]
manifest = a.out / 'blank-mapdl.txt' if a.expect == 'online' else a.manifest
for path in ['data/mapdl.net.txt', 'data/mapdl.txt']:
    args += ['--put', path + '=' + str(manifest)]
try:
    result = subprocess.run(args, capture_output=True, text=True, timeout=150)
    (a.out / 'harness.log').write_bytes((result.stdout + result.stderr).encode())
    if result.returncode:
        raise RuntimeError('runlines actor failed; inspect owned harness/log before retry')
finally:
    if server:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
rig = sorted(a.out.glob('ftesurf-runlines-*'))[-1]
log = (rig / 'ftesurf/logs/runlines_smoke.log').read_text(encoding='utf-8', errors='replace')
clean = re.sub(r'\^[0-9]|[\x80-\x9f]', '', log)
assert not re.search(r'QC runtime error|CSQC_Abort|Menu_Abort|Unknown command', clean)
checks = []
for name, expected in expectations.items():
    block = clean.split('P928CASE ' + name, 1)[1].split('P928END ' + name, 1)[0]
    states = re.findall(r'watch state open (\d) on (\d)', block)
    times = [float(x) for x in re.findall(r'  t ([\d.-]+)', block)]
    # Watch_Status prints the explicit state tuple only when NOTHING is open.
    # Its open branch prints the owner, clock and imported identity instead.
    if expected['open']:
        assert times and '  owner ' in block and 'nothing loaded' not in block, name
        assert 'import ksf' in block and 'not native verified' in block, name
        assert 'map build unknown' in block, name
        if expected['advance']:
            assert len(times) >= 2 and times[-1] > times[0] + .2, (name, times)
    else:
        assert states and states[-1] == ('0', '0'), (name, states)
        assert 'watch state open 0 on 0 cursor 0' in block, name
    checks.append(dict(case=name, states=states, times=times, passed=True))
if a.expect == 'online':
    assert requests.count('/api/replay/21517') == 1, requests
    files = list((rig / 'ftesurf/data/online/surf_chateau_fix').rglob('*.rec'))
    assert len(files) == 1 and files[0].read_bytes() == text.encode()
report = dict(expect=a.expect, cases=checks, requests=requests,
              input_sha256=hashlib.sha256(a.recording.read_bytes()).hexdigest(),
              original_sha256=hashlib.sha256(a.original.read_bytes()).hexdigest(),
              csqc_sha256=hashlib.sha256(a.csqc.read_bytes()).hexdigest(),
              actors_stopped=True, no_canonical_fixture_changes=True)
(a.out / 'result.json').write_bytes(json.dumps(report, indent=2).encode())
print('%s: %d acted cases PASS; input identities retained' % (a.expect, len(checks)))
