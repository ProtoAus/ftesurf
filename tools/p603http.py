#!/usr/bin/env python3
"""Loopback-only actual HTTP/parser/identity/replay/refresh scoreboard gate.

The authoritative spawn wrapper supplies a synthetic *phash input. Nothing
sets ob_mine or replaces URI_Get_Callback, Online_Parse or action handlers.
This is not a production service, external downloader or device-input test.
"""
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlparse

from p598build import ROOT

PLAYER = 'p603-http-synthetic-player'
PHASH = hashlib.sha256(PLAYER.encode()).hexdigest()[:8]  # FS_WHO_IDLEN
REP = 996041


def compile_server(rig):
    src = ROOT / 'src'
    lines = (src / 'sv_progs.src').read_text().splitlines()
    output = [os.path.relpath(rig / 'qwprogs.dat', src).replace('\\', '/')]
    for line in lines[1:]:
        if line.strip() == 'server/sv_player.qc':
            output.append('../tools/fixtures/p603http_server_prefix.qc')
        output.append(line)
    output.append('../tools/fixtures/p603http_server.qc')
    manifest = src / (rig.name + '-sv_progs.src')
    if manifest.exists(): raise RuntimeError('server manifest already exists')
    manifest.write_text('\n'.join(output) + '\n')
    shutil.copy2(manifest, rig / 'sv_progs.src')
    log = rig / 'compile-server.log'
    try:
        with log.open('w') as stream:
            result = subprocess.run([str(src / 'fteqcc64.exe'), '-srcfile', manifest.name],
                                    cwd=src, stdout=stream, stderr=subprocess.STDOUT)
    finally:
        manifest.unlink()
    if result.returncode or 'Done. 0 warnings' not in log.read_text(errors='replace'):
        raise RuntimeError('synthetic identity server compile failed: ' + str(log))


def board(query, mode):
    rows = [{'r': i + 1, 'name': f'HTTP Row{i}', 'player': PLAYER if i == 7 else f'http-peer-{i}',
             'ticks': 100 + i, 'rate': (100 + i) * 1000 / (1500 + i * 100), 'ms': 1500 + i * 100,
             'flags': 0, 'when': 1000, 'rep': REP if i == 0 else 0, 'ver': 1 if i == 0 else 0}
            for i in range(8)]
    #Different rates: native time/delta must not subtract unrelated tick counts.
    rows[1].update(ticks=160, rate=100, ms=1600)
    if mode == 'reorder': rows[0], rows[1] = rows[1], rows[0]
    if mode in ('imported', 'demoerror', 'verifiedimported', 'verifiederror'):
        rows[0].update(tr='momentum', rep=0, get='60401/' + 'a' * 40,
                       ver=int(mode.startswith('verified')))
        rows[1].update(tr='ksf')
        if mode in ('demoerror', 'verifiederror'): rows[0]['get'] = '60402/' + 'b' * 40
    if mode == 'segment': rows[0].update(flags=128)
    result = {'map': query['map'], 'track': int(query['track']), 'leg': int(query['leg']),
              'tier': query['tier'], 'style': query['style'], 't': 2000,
              'counts': {'ranked': 8, 'imported': 8}, 'rows': rows}
    if mode == 'wrongleg': result['leg'] = 1
    if mode == 'empty': result['rows'] = []
    return json.dumps(result, separators=(',', ':')).encode()


def replay():
    head = ('FTESURF-REC 5\nmap p603scores.map\nowner "HTTP Row0"\ntrack 0\n'
            'startseg 0\nleg 0\ntickrate 0.015\nflags 0\nbegin\n')
    samples = ''.join(f'{i} {i} 0 80 100 0 0 0 0 0 0 1 0 0 0\n' for i in range(20))
    return (head + samples + 'end 100 20 0 0\n').encode()


def start_stub(root, board_factory=None):
    if board_factory is None: board_factory = board
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            url = urlparse(self.path)
            if '/api/momentum/' not in url.path:
                self.send_error(404); return
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            failed = url.path.startswith(('/demoerror/', '/verifiederror/'))
            data = json.dumps({'state': 'failed' if failed else 'queued',
                               'why': 'synthetic demo absent' if failed else '', 'rep': 0}).encode()
            self.respond(200, data)

        def do_GET(self):
            url = urlparse(self.path)
            mode = url.path.split('/')[1]
            code = 200
            if url.path.endswith('/api/board'):
                query = {k: v[0] for k, v in parse_qs(url.query).items()}
                if mode == 'slow': time.sleep(1.5)
                code = {'busy': 429, 'missingboard': 404, 'servererror': 500}.get(mode, 200)
                data = b'{"error":"busy"}' if code != 200 else board_factory(query, mode)
            elif url.path.endswith(f'/api/replay/{REP}'):
                data = replay()
            else:
                code, data = 404, b'{"error":"fixture route absent"}'
            self.respond(code, data)

        def respond(self, code, data):
            self.send_response(code)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(data)
            with self.server.evidence_lock:
                with (root / 'http.jsonl').open('a') as stream:
                    stream.write(json.dumps({'method': self.command, 'path': self.path, 'code': code,
                                             'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}) + '\n')

        def log_message(self, *args): pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.evidence_lock = threading.Lock()
    server.worker = threading.Thread(target=server.serve_forever, name='p603-loopback-http')
    server.worker.start()
    return server


def extend_config(cfg, arm, port):
    lines = ['scores lines clear', 'replay off', '-showscores', 'set rec_terms 4',
             f'set lobby_dir "http://127.0.0.1:{port}/normal"', 'scores tab online',
             '+showscores', 'scores open', 'board_fetch 0 0 ranked clean', 'waitms 1500']

    def probe(name, shot=False):
        lines.extend(['p603http probe ' + name, 'wait 2'])
        if shot: lines.append('screenshot http_' + name)

    def fetch(mode, tier='ranked', style='clean', wait=700):
        lines.extend([f'set lobby_dir "http://127.0.0.1:{port}/{mode}"',
                      f'board_fetch 0 0 {tier} {style}', f'waitms {wait}'])

    def click(target):
        lines.extend(['p603 move ' + target, 'waitms 200', 'p603 down',
                      'waitms 200', 'p603 up', 'waitms 800'])

    probe('ready', True)
    click('missing'); probe('missing')
    if arm.startswith('native'):
        click('next'); probe('page6')
        fetch('normal'); probe('page_refresh')
        click('previous')
        click('line')
    else:
        lines += ['scores line 0', 'waitms 1000']
    probe('line', True)
    lines += ['scores lines', 'scores lines clear', 'waitms 200']
    click('watch')
    probe('watch')
    lines += ['replay status', 'replay off', '-showscores', 'waitms 200',
              '+showscores', 'scores open', 'waitms 500']
    probe('stale_control')
    if arm.startswith('native'):
        lines += ['p603 move watch', 'waitms 200', 'p603 down', 'waitms 200']
        fetch('normal')
        lines += ['p603 up', 'waitms 500']
        probe('identical', True)
        #Reset to establish another acting native control even if mutant watched.
        lines += ['replay off', '-showscores', 'waitms 200', '+showscores', 'scores open', 'waitms 500']
        probe('reorder_control')
        lines += ['p603 move watch', 'waitms 200', 'p603 down', 'waitms 200']
        fetch('reorder')
        lines += ['p603 up', 'waitms 500']
        probe('reorder', True)
    fetch('wrongleg'); probe('wrongleg', True)
    fetch('slow', wait=300); probe('loading')
    lines += ['waitms 1800']; probe('loaded')
    fetch('empty'); probe('empty', True)
    fetch('wrongleg')
    fetch('busy'); probe('busy', True)
    #Use production source/filter commands, not a parser seam.
    lines += [f'set lobby_dir "http://127.0.0.1:{port}/imported"', 'scores tab imported', 'waitms 1000']
    probe('imported', True)
    if arm.startswith('native'): click('line')
    else: lines += ['scores line 0', 'waitms 800']
    probe('demo_queued', True)
    lines += ['scores lines clear', 'waitms 200']
    fetch('demoerror', tier='imported')
    if arm.startswith('native'): click('line')
    else: lines += ['scores line 0', 'waitms 800']
    probe('demo_error', True)
    lines += ['scores lines clear', 'waitms 200']
    lines += [f'set lobby_dir "http://127.0.0.1:{port}/segment"', 'scores tab segmented', 'waitms 1000']
    probe('segmented', True)
    #Exercise actual denied/unconfigured states without mutating the row store.
    lines += ['set rec_terms 0']
    fetch('noterms', tier='segmented'); probe('noterms', True)
    lines += ['set rec_terms 4', 'set lobby_dir ""', 'board_fetch 0 0 segmented clean', 'waitms 700']
    probe('nodir', True)
    lines += [f'set lobby_dir "http://127.0.0.1:{port}/normal"', 'scores tab online']
    fetch('normal'); probe('terms_back')
    fetch('missingboard'); probe('http404', True)
    fetch('servererror'); probe('http500', True)
    lines += [f'set lobby_dir "http://127.0.0.1:{port}/verifiedimported"', 'scores tab imported', 'waitms 1000']
    probe('verified_get', True)
    if arm.startswith('native'): click('line')
    else: lines += ['scores line 0', 'waitms 800']
    probe('verified_queued', True)
    lines += ['scores lines clear', 'waitms 200']
    fetch('verifiederror', tier='imported')
    if arm.startswith('native'): click('line')
    else: lines += ['scores line 0', 'waitms 800']
    probe('verified_retry', True)
    lines += ['scores lines clear', '-showscores', 'replay off', 'waitms 500']
    if arm != 'absent': lines += ['ui_imgui_status', 'waitms 400', 'ui_imgui_status']
    lines += ['echo P603 HTTP FINISHED', 'echo P603 FINISHED', 'quit']
    return cfg.replace('echo P603 FINISHED\nquit\n', '\n'.join(lines) + '\n')


def grade_http(rig, report):
    errors = []
    basic = ('ready', 'missing', 'line', 'watch', 'stale_control', 'wrongleg', 'loading', 'loaded',
             'empty', 'busy', 'imported', 'demo_queued', 'demo_error', 'segmented')
    v2 = report.get('http_version', 1) >= 2
    if v2:
        basic += ('noterms', 'nodir', 'terms_back', 'http404', 'http500',
                  'verified_get', 'verified_queued', 'verified_retry')
    native_names = ('page6', 'page_refresh', 'identical', 'reorder_control', 'reorder')
    fields = {'HTTP': {'state', 'rows', 'mine', 'epoch', 'revision', 'page'},
              'ROUTE': {'painted', 'handle', 'watch', 'samples', 'lines', 'ready'}}
    for arm in report['planned_arms']:
        def need(condition, why):
            if not condition: errors.append(arm + ': http ' + why)
        native = arm.startswith('native')
        planned = basic + (native_names if native else ())
        text = '\n'.join(p.read_text(errors='replace') for p in (rig / arm / 'ftesurf/logs').glob('scores*.log'))
        need(text.count('P603 HTTP FINISHED') == 1, 'completion marker')
        need('P603 HTTP ERROR' not in text, 'fixture error')
        captures, cells, hashes = {}, {}, {}
        for kind, name, tail in re.findall(r'P603 (HTTP|ROUTE) (\w+) ([^\r\n]+)', text):
            if name not in planned: continue
            need((kind, name) not in captures, 'duplicate ' + kind + '/' + name)
            pairs = re.findall(r'(\w+)=(-?[0-9]+(?:\.[0-9]+)?)', tail)
            need(len(pairs) == len(fields[kind]) and {k for k, v in pairs} == fields[kind], 'field set ' + kind + '/' + name)
            captures[kind, name] = {k: float(v) for k, v in pairs}
        for name, value in re.findall(r'P603 PHASH (\w+): ([^\r\n]*)', text):
            need(name not in hashes, 'duplicate phash ' + name); hashes[name] = value
        for name, slot, value in re.findall(r'P603 CELL (\w+) (\d+): ?([^\r\n]*)', text):
            need((name, int(slot)) not in cells, 'duplicate cell'); cells[name, int(slot)] = value
        for name in planned:
            for kind in fields:
                need((kind, name) in captures, 'missing ' + kind + '/' + name)
            need(hashes.get(name) == PHASH, 'synthetic authoritative identity ' + name)
        if any((kind, name) not in captures or set(captures[kind, name]) != fields[kind]
               for name in planned for kind in fields): continue
        def get(kind, name, key): return captures[kind, name][key]
        need(get('HTTP', 'ready', 'state') == 2 and get('HTTP', 'ready', 'rows') == 8 and
             get('HTTP', 'ready', 'mine') == 7, 'actual callback/parser/FindMine did not act')
        for name in ('ready', 'stale_control', 'loaded', 'empty', 'imported', 'segmented'):
            need(get('ROUTE', name, 'painted') == int(native), 'native/fallback route ' + name)
        for name in ('wrongleg', 'loading', 'busy'):
            need(get('ROUTE', name, 'handle') == 0 and get('ROUTE', name, 'painted') == 0,
                 'unready native allocation ' + name)
        need(get('HTTP', 'loading', 'state') == 1, 'loading subject inert')
        need(get('HTTP', 'busy', 'state') == 3, '429 subject inert')
        need(get('HTTP', 'empty', 'rows') == 0, 'empty reply inert')
        if v2:
            for name, state in (('noterms', 5), ('nodir', 4)):
                need(get('HTTP', name, 'state') == state and get('ROUTE', name, 'handle') == 0 and
                     get('ROUTE', name, 'painted') == 0, 'denied/unconfigured route ' + name)
            for name in ('terms_back', 'http404', 'http500', 'verified_get', 'verified_queued', 'verified_retry'):
                need(get('ROUTE', name, 'painted') == int(native), 'usable route ' + name)
            for name in ('http404', 'http500'):
                need(get('HTTP', name, 'state') == 3 and get('HTTP', name, 'rows') == 8,
                     'same-board failed refresh did not preserve usable rows ' + name)
            need(get('HTTP', 'terms_back', 'state') == 2, 'terms/root recovery inert')
            need(get('ROUTE', 'verified_queued', 'lines') == 6 and
                 get('ROUTE', 'verified_retry', 'lines') == 5, 'verified demo states inert')
        need(get('ROUTE', 'missing', 'watch') == 0 and
             text.count('no recording was kept for that run') == 1, 'missing replay click explanation')
        need(get('ROUTE', 'demo_queued', 'lines') == 6 and
             get('ROUTE', 'demo_error', 'lines') == 5, 'actual demo POST/callback states')
        need(get('ROUTE', 'line', 'lines') == 4 and get('ROUTE', 'line', 'ready') == 20,
             'actual downloaded line did not load')
        need(get('ROUTE', 'watch', 'watch') == 1 and get('ROUTE', 'watch', 'samples') == 20,
             'actual watch did not open downloaded replay')
        need(re.search(r'replay: data/online/[^\r\n]+\s+HTTP Row0\s+0:01\.500\s+20 samples', text),
             'watch identity/body mismatch')
        if native:
            need(get('HTTP', 'page6', 'page') == 6 and get('HTTP', 'page_refresh', 'page') == 6,
                 'refresh changed selected page')
            for before, after in (('stale_control', 'identical'), ('reorder_control', 'reorder')):
                need(get('ROUTE', before, 'painted') == 1, 'held-click acting control ' + before)
                need(get('HTTP', after, 'epoch') > get('HTTP', before, 'epoch'), 'refresh did not replace rows ' + after)
                need(get('HTTP', after, 'revision') > get('HTTP', before, 'revision'), 'refresh retained old action authority ' + after)
                need(get('ROUTE', after, 'watch') == 0, 'held old click watched after ' + after)
            expected = {('ready', 6): '0:01.500', ('ready', 9): 'watch (verified)',
                        ('ready', 15): '0:01.600', ('ready', 16): '+0:00.100',
                        ('page6', 17): 'HTTP Row7 (you)', ('imported', 9): 'Get demo',
                        ('imported', 12): 'momentum', ('imported', 21): 'ksf',
                        ('segmented', 11): 'segmented', ('demo_queued', 9): 'queued',
                        ('demo_queued', 13): 'queued', ('demo_error', 9): 'retry',
                        ('demo_error', 13): 'failed'}
            if v2:
                expected.update({('verified_get', 9): 'Get demo (verified)',
                                 ('verified_queued', 9): 'queued (verified)',
                                 ('verified_retry', 9): 'retry (verified)'})
            for key, value in expected.items(): need(cells.get(key) == value, 'cell parity ' + repr(key))
        shots = ('ready', 'line', 'wrongleg', 'empty', 'busy', 'imported', 'demo_queued', 'demo_error', 'segmented')
        if native: shots += ('identical', 'reorder')
        if v2: shots += ('noterms', 'nodir', 'http404', 'http500', 'verified_get', 'verified_queued', 'verified_retry')
        for name in shots:
            need(len(list((rig / arm / 'ftesurf/screenshots').glob('http_' + name + '.*'))) == 1,
                 'missing/duplicate screenshot ' + name)
        try: exchanges = [json.loads(line) for line in (rig / arm / 'http.jsonl').read_text().splitlines()]
        except (OSError, ValueError): exchanges = []; need(False, 'missing HTTP evidence')
        normal = [x for x in exchanges if x.get('path', '').startswith('/normal/api/board')]
        need(len(normal) >= (3 if native else 1) and len({x.get('sha256') for x in normal}) == 1,
             'byte-identical actual HTTP refresh not established')
        downloads = [x for x in exchanges if x.get('path', '').endswith(f'/api/replay/{REP}')]
        need(len(downloads) == 1 and downloads[0].get('code') == 200 and downloads[0].get('bytes') == len(replay()),
             'cold body transfer/cache identity')
        need(any(x.get('code') == 429 for x in exchanges), 'HTTP 429 not delivered')
        if v2:
            need(not any(x.get('path', '').startswith('/noterms/') for x in exchanges),
                 'denied terms leaked an HTTP request')
            need(all(any(x.get('code') == code for x in exchanges) for code in (404, 500)),
                 'HTTP 404/500 did not act')
            for mode, token in (('verifiedimported', '60401/' + 'a' * 40), ('verifiederror', '60402/' + 'b' * 40)):
                need(sum(x.get('method') == 'POST' and x.get('path') == '/' + mode + '/api/momentum/' + token
                         and x.get('code') == 200 for x in exchanges) == 1, 'actual verified demo request ' + mode)
        for mode, token in (('imported', '60401/' + 'a' * 40), ('demoerror', '60402/' + 'b' * 40)):
            need(sum(x.get('method') == 'POST' and x.get('path') == '/' + mode + '/api/momentum/' + token
                     and x.get('code') == 200 for x in exchanges) == 1, 'actual demo request ' + mode)
    return errors
