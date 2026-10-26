#!/usr/bin/env python3
"""Exercise the authored site snippet with real nginx + isolated real surfd.

python tools/test_site_routes.py --nginx /path/to/nginx --work-root /owned/tmp
Requires Flask, Werkzeug and nginx. No download, privileged port, live home,
Steam request or deployment. --snippet allows an original-source negative control.
"""
import argparse
import http.client
import importlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ARGS = None


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class SiteRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from werkzeug.serving import make_server, WSGIRequestHandler

        # Close everything even if setup/nginx -t fails before the first test.
        cls.home = Path(tempfile.mkdtemp(prefix='site-routes-', dir=ARGS.work_root))
        cls.nginx_stopped = True
        cls.addClassCleanup(cls.retire_fixture)
        env = dict(os.environ)
        cls.addClassCleanup(lambda: (os.environ.clear(), os.environ.update(env)))
        for key in list(os.environ):
            if key.startswith('SURFD_'):
                del os.environ[key]
        for name in ('maps', 'zones', 'zones_local', 'runs', 'webshots', 'temp'):
            (cls.home / name).mkdir()
        (cls.home / 'surfd.env').write_text('SURFD_KEY=local-test-only\n', encoding='utf-8')
        (cls.home / 'csprogs.dat').write_bytes(b'local fixture, not game code\n')
        os.environ.update(SURFD_HOME=str(cls.home), SURFD_DB=str(cls.home / 'test.db'),
                          SURFD_ENV=str(cls.home / 'surfd.env'),
                          SURFD_BOARD_URL='https://proto.bar/ftesurf/board',
                          SURFD_RANKED_LINKED='0', SURFD_STEAM_KEY='',
                          SURFD_GAME=str(cls.home), SURFD_GAME_CODE=str(cls.home / 'csprogs.dat'),
                          SURFD_MAPS=str(cls.home / 'maps'), SURFD_ZONES=str(cls.home / 'zones'),
                          SURFD_ZONES_LOCAL=str(cls.home / 'zones_local'),
                          SURFD_RUNS=str(cls.home / 'runs'), SURFD_WEBSHOTS=str(cls.home / 'webshots'),
                          SURFD_MOMENTUM=str(cls.home / 'momentum'),
                          SURFD_MOMTRACKS=str(cls.home / 'absent.tsv'))
        sys.path.insert(0, str(ROOT / 'surfd'))
        cls.appmod = importlib.import_module('surfd')
        cls.addClassCleanup(logging.shutdown)  # close the Windows log before rmtree
        cls.seen = []
        app = cls.appmod.app

        @app.before_request
        def observe():
            from flask import request
            cls.seen.append((request.path, request.query_string,
                             request.method, request.headers.get('X-Real-IP'),
                             request.headers.get('X-Forwarded-For')))

        class Quiet(WSGIRequestHandler):
            def log_request(self, *args, **kwargs):
                pass

        backend = make_server('127.0.0.1', 0, app, request_handler=Quiet)
        thread = threading.Thread(target=backend.serve_forever, daemon=True)
        thread.start()
        cls.addClassCleanup(lambda: (backend.shutdown(), thread.join(5), backend.server_close()))
        cls.static = cls.home / 'static'
        cls.static.mkdir()
        cls.files = {
            'index.html': (ROOT / 'src/release/page.template.html').read_bytes(),
            'anticheat.html': (ROOT / 'src/release/site/anticheat.html').read_bytes(),
            'site.css': (ROOT / 'src/release/site/site.css').read_bytes(),
            'site.js': (ROOT / 'src/release/site/site.js').read_bytes(),
            'favicon.svg': (ROOT / 'src/release/site/favicon.svg').read_bytes(),
            'BebasNeueRegular.ttf': (ROOT / 'ftesurf/gfx/fonts/BebasNeueRegular.ttf').read_bytes(),
            'update.json': b'{"fixture":"not a signed feed","game":"ftesurf"}\n',
            'version.json': b'{"version":"0.1.32","fixture":"rolling public receipt"}\n',
        }
        cls.releases = cls.home / 'releases'
        cls.receipts = {}
        for version in ('0.1.30', '0.1.31'):
            folder = cls.releases / version
            folder.mkdir(parents=True)
            data = json.dumps({'version': version, 'fixture': 'retained public metadata'}).encode()
            cls.receipts[version] = data
            (folder / 'version.json').write_bytes(data)
            # Prove the route cannot expose neighbors that really exist.
            (folder / 'index.html').write_bytes(b'RETAINED PAGE NOT A RECEIPT')
            (folder / 'update-verified.json').write_bytes(b'PRIVATE PUBLICATION PROOF SENTINEL')
        for name, data in cls.files.items():
            (cls.static / name).write_bytes(data)
        cls.port = free_port()
        snippet = ARGS.snippet.read_text(encoding='utf-8')
        # Only deployment addresses change. All location/method/cache policy is
        # the authored snippet, not a Python emulation or regenerated config.
        snippet = snippet.replace('/srv/nvme/ftesurf-site/static/', cls.static.as_posix() + '/')
        snippet = snippet.replace('/srv/nvme/ftesurf-site/releases/', cls.releases.as_posix() + '/')
        snippet = snippet.replace('127.0.0.1:8084', '127.0.0.1:%d' % backend.server_port)
        (cls.home / 'site.conf').write_text(snippet, encoding='utf-8')
        # Deliberately omit ttf like the production host. Other types come from
        # nginx's distribution, not guesses in the grader.
        mime = ARGS.mime_types or ARGS.nginx.parent / 'conf/mime.types'
        if not mime.is_file():
            mime = Path('/etc/nginx/mime.types')
        user = ''
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            import pwd
            user = 'user %s;' % pwd.getpwuid(os.geteuid()).pw_name
        (cls.home / 'nginx.conf').write_text('''
%s
daemon off;
worker_processes 1;
pid nginx.pid;
error_log error.log notice;
events { worker_connections 128; }
http {
    include "%s";
    access_log off;
    client_body_temp_path temp/client_body;
    proxy_temp_path temp/proxy;
    fastcgi_temp_path temp/fastcgi;
    uwsgi_temp_path temp/uwsgi;
    scgi_temp_path temp/scgi;
    limit_req_zone $binary_remote_addr zone=surfdboard:1m rate=10000r/s;
    server {
        listen 127.0.0.1:%d;
        server_name proto.bar;
        include site.conf;
        location / { return 200 "UNRELATED FILEBROWSER SENTINEL"; }
    }
}
''' % (user, mime.as_posix(), cls.port), encoding='utf-8')
        cls.cmd = [str(ARGS.nginx), '-p', cls.home.as_posix() + '/', '-c', 'nginx.conf',
                   '-e', (cls.home / 'error.log').as_posix()]
        syntax = subprocess.run(cls.cmd + ['-t'], capture_output=True, text=True, timeout=15)
        if syntax.returncode or '[warn]' in syntax.stderr or '[emerg]' in syntax.stderr:
            raise AssertionError(syntax.stdout + syntax.stderr)
        cls.proc = subprocess.Popen(cls.cmd, cwd=cls.home, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        cls.nginx_stopped = False
        cls.addClassCleanup(cls.stop_nginx)
        for _ in range(100):
            try:
                if cls.request('/')[2] == b'UNRELATED FILEBROWSER SENTINEL':
                    break
            except OSError:
                time.sleep(.05)
        else:
            raise AssertionError('nginx did not act: ' + (cls.home / 'error.log').read_text())
        # Foreground mode makes Popen own the serving master on POSIX too.
        if int((cls.home / 'nginx.pid').read_text()) != cls.proc.pid:
            raise AssertionError('retained process is not the nginx master')
        if ARGS.lifecycle_control == 'setup':
            raise AssertionError('intentional setup failure after master acted')

    @classmethod
    def retire_fixture(cls):
        if not cls.nginx_stopped:
            raise AssertionError('nginx shutdown unproved; fixture retained: ' + str(cls.home))
        shutil.rmtree(cls.home)

    @classmethod
    def stop_nginx(cls):
        # Signal only this prefix's pidfile; never a global process-name kill.
        graceful = False
        try:
            if ARGS.lifecycle_control != 'shutdown':
                result = subprocess.run(cls.cmd + ['-s', 'quit'], capture_output=True, timeout=10)
                if result.returncode == 0:
                    cls.proc.wait(timeout=15)
                    graceful = True
        except (OSError, subprocess.TimeoutExpired):
            pass  # bounded forced-stop fallback below, not a passing shutdown
        if not graceful:
            subprocess.run(cls.cmd + ['-s', 'stop'], capture_output=True, check=True, timeout=10)
            cls.proc.wait(timeout=15)
        # A reaped foreground master has already reaped its workers. Also prove
        # its listener is closed before allowing temporary-tree retirement.
        with socket.socket() as sock:
            sock.settimeout(1)
            if sock.connect_ex(('127.0.0.1', cls.port)) == 0:
                raise AssertionError('nginx listener still active; fixture retained')
        cls.nginx_stopped = True
        if not graceful:
            raise AssertionError('graceful shutdown failed; owned master stopped and reaped')

    @classmethod
    def request(cls, path, method='GET', headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', cls.port, timeout=10)
        try:
            conn.request(method, path, headers={'Host': 'proto.bar', **(headers or {})})
            resp = conn.getresponse()
            return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read()
        finally:
            conn.close()

    def test_static_and_direct_feed(self):
        types = {'index.html': 'text/html', 'anticheat.html': 'text/html',
                 'site.css': 'text/css', 'site.js': 'application/javascript',
                 'favicon.svg': 'image/svg+xml', 'BebasNeueRegular.ttf': 'font/ttf',
                 'update.json': 'application/json', 'version.json': 'application/json'}
        for base in ('ftesurf', 'worldofsurf'):
            for name, expected in self.files.items():
                with self.subTest(base=base, file=name):
                    status, headers, body = self.request('/%s/%s' % (base, name))
                    self.assertEqual(status, 200)
                    self.assertEqual(body, expected)  # not a redirect or SPA
                    self.assertEqual(headers.get('x-ftesurf-site'), '1')
                    self.assertEqual(headers.get('content-type'), types[name])
                    self.assertEqual(headers.get('cache-control'),
                                     'public, max-age=2592000' if name.endswith('.ttf') else 'no-cache')
            self.assertEqual(self.request('/%s/' % base)[2], self.files['index.html'])
            status, headers, _ = self.request('/%s/absent.css' % base)
            self.assertEqual(status, 404)
            self.assertEqual(headers.get('x-ftesurf-site'), '1')

    def test_version_pinned_public_receipts(self):
        for base in ('ftesurf', 'worldofsurf'):
            for version, expected in self.receipts.items():
                path = '/%s/releases/%s/version.json' % (base, version)
                status, headers, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertEqual(body, expected)
                self.assertNotEqual(body, self.files['version.json'])
                self.assertEqual(headers.get('x-ftesurf-site'), '1')
                self.assertEqual(headers.get('x-content-type-options'), 'nosniff')
                self.assertEqual(headers.get('content-type'), 'application/json')
                self.assertEqual(headers.get('cache-control'), 'public, max-age=31536000, immutable')
                status, head, body = self.request(path, 'HEAD')
                self.assertEqual(status, 200)
                self.assertEqual(body, b'')
                self.assertEqual(int(head['content-length']), len(expected))
                before = len(self.seen)
                for method in ('POST', 'PUT', 'DELETE'):
                    self.assertEqual(self.request(path, method)[0], 403)
                self.assertEqual(len(self.seen), before)
                for name in ('index.html', 'update-verified.json'):
                    self.assertTrue((self.releases / version / name).is_file())
                    self.assertEqual(self.request('/%s/releases/%s/%s' % (base, version, name))[0], 404)
            for suffix in ('0.1.99/version.json', '0.1.31/', '0.1.31/version.json/extra',
                           'not-a-version/version.json', '0.1.31/update.json'):
                status, headers, _ = self.request('/%s/releases/%s' % (base, suffix))
                self.assertEqual(status, 404)
                self.assertNotIn('immutable', headers.get('cache-control', ''))

    def test_slashes_preserve_queries(self):
        for base in ('ftesurf', 'worldofsurf'):
            for suffix in ('', '/board'):
                path = '/' + base + suffix
                status, headers, _ = self.request(path + '?q=a%2Fb&n=2')
                self.assertEqual(status, 301)
                self.assertEqual(headers['location'], 'https://proto.bar' + path + '/?q=a%2Fb&n=2')

    def test_real_board_and_private_boundaries(self):
        for base in ('ftesurf', 'worldofsurf'):
            prefix = '/' + base + '/board'
            status, headers, body = self.request(prefix + '/api/maps?probe=a%2Fb&x=2', headers={
                'X-Real-IP': '198.51.100.99', 'X-Forwarded-For': '198.51.100.99'})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['maps'], [])
            self.assertEqual(headers.get('x-ftesurf-site'), '1')
            self.assertEqual(self.seen[-1], ('/board/api/maps', b'probe=a%2Fb&x=2',
                                            'GET', '127.0.0.1', '127.0.0.1'))
            for suffix in ('/admin', '/api/run', '/api/secret', '/unknown.js'):
                self.assertEqual(self.request(prefix + suffix)[0], 404, suffix)
            self.assertIn(b'World of Surf', self.request(prefix + '/')[2])
            self.assertEqual(self.request(prefix + '/api/maps', 'HEAD')[0], 200)
            before = len(self.seen)
            for suffix, method in [('/api/maps', 'POST'), ('/link/steam', 'POST'),
                                   ('/api/map', 'PUT'), ('/api/map/', 'POST')]:
                self.assertEqual(self.request(prefix + suffix, method)[0], 403)
            self.assertEqual(len(self.seen), before)  # denied by nginx, never app
            # Missing ksfmore is intentionally rejected by the real app, proving
            # the one permitted POST traversed nginx (without enqueue/network).
            self.assertEqual(self.request(prefix + '/api/map', 'POST')[0], 400)
            self.assertEqual(self.seen[-1][0:3], ('/board/api/map', b'', 'POST'))

    def test_staged_accounts_use_legacy_callback(self):
        for base in ('ftesurf', 'worldofsurf'):
            prefix = '/' + base + '/board'
            opener = 'a' * 24
            page = self.request(prefix + '/link?k=' + opener)[2]
            self.assertIn(b'World of Surf', page)
            self.assertIn(('link/steam?k=' + opener).encode(), page)
            self.assertEqual(self.request(prefix + '/link.css')[2],
                             (ROOT / 'surfd/web/link.css').read_bytes())
            status, headers, _ = self.request(prefix + '/link/steam?k=' + opener)
            self.assertEqual(status, 302)
            q = parse_qs(urlsplit(headers['location']).query)
            self.assertEqual(q['openid.realm'], ['https://proto.bar'])
            callback = q['openid.return_to'][0]
            self.assertTrue(callback.startswith('https://proto.bar/ftesurf/board/link/return?s='))
            self.assertEqual(parse_qs(urlsplit(callback).query)['k'], [opener])
            self.assertEqual(headers.get('cache-control'), 'no-store')
            cookie = headers['set-cookie']
            for part in ('__Host-ftl=', 'Secure', 'HttpOnly', 'Path=/', 'SameSite=Lax'):
                self.assertIn(part, cookie)
            self.assertNotIn('Domain=', cookie)
            path = urlsplit(callback).path + '?' + urlsplit(callback).query + '&openid.mode=cancel'
            status, headers, body = self.request(path)
            self.assertEqual(status, 200)
            self.assertNotIn('location', headers)  # callback was not redirected
            self.assertIn(b'Sign-in was cancelled.', body)
            self.assertEqual(self.seen[-1][0], '/board/link/return')
            self.assertIn(b'openid.mode=cancel', self.seen[-1][1])
            # Old callbacks and unlink bookmarks must not be caught in a broad
            # redirect; encoded and duplicate fields must reach app validation.
            for suffix, query in [('/link/return', 's=' + 'b' * 32 + '&openid.mode=cancel&openid.mode=cancel&probe=a%2Fb%26c'),
                                  ('/link/unlink', 't=invalid%2Ftoken&x=1')]:
                status, headers, _ = self.request(prefix + suffix + '?' + query)
                self.assertEqual(status, 400)
                self.assertNotIn('location', headers)
                self.assertEqual(self.seen[-1][0:2], ('/board' + suffix, query.encode()))

    def test_installer_probe_detector(self):
        source = (ROOT / 'src/release/install.sh').read_text(encoding='utf-8')
        probe = re.search(r"<<'PY'\n(.*?)\nPY\n", source, re.S).group(1)
        self.assertIn('for BASE in ftesurf worldofsurf; do', source)
        headers = self.home / 'probe-headers'
        body = self.home / 'probe-body'
        cases = [
            ('Content-Type: application/json\nX-FTESurf-Site: 1\n', '{"v":1,"maps":[]}', True),
            ('Content-Type: text/html\n', '<html>filebrowser</html>', False),
            ('Content-Type: application/json\n', '{"v":1,"maps":[]}', False),
            ('Content-Type: application/json\nX-FTESurf-Site: 1\n', '{"ok":true}', False),
        ]
        for head, data, want in cases:
            headers.write_text(head, encoding='utf-8')
            body.write_text(data, encoding='utf-8')
            result = subprocess.run([sys.executable, '-c', probe, str(headers), str(body)],
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode == 0, want, result.stderr)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nginx', required=True, type=Path)
    parser.add_argument('--work-root', required=True, type=Path)
    parser.add_argument('--mime-types', type=Path, help='nginx distribution MIME table')
    parser.add_argument('--lifecycle-control', choices=('setup', 'shutdown'),
                        help='intentional fixture failure; must exit nonzero without leaking nginx')
    parser.add_argument('--snippet', type=Path, default=ROOT / 'src/release/ftesurf.nginx')
    ARGS, rest = parser.parse_known_args()
    ARGS.nginx = ARGS.nginx.resolve()
    ARGS.work_root.mkdir(parents=True, exist_ok=True)
    unittest.main(argv=[sys.argv[0]] + rest)
