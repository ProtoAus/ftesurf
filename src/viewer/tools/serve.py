"""Serve the 3D run viewer on this machine, against recordings and maps on disk.

    python tools/serve.py --maps DIR --rec ID=FILE.rec [--info ID=FILE.json] [--steam DIR] [--port 8825]

Then open http://127.0.0.1:8825/board/watch.html#r=ID. /board/ is surfd/web,
/board/api/run/ID/track is surfd's rectrack over FILE.rec, /board/api/run/ID
is FILE.json (a saved copy of the live route) or 404, and /maps/NAME.bsp is
DIR/NAME.bsp. --steam serves a Steam `common` folder at /steam/ with HEAD and
Range, which watch.html#...&steam=1 mounts as if it had been picked (127.0.0.1
only). Sends the CSP surfd sends on /board/, so a page that needs more
fails here too.
"""
import argparse
import http.server
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SURFD = os.path.normpath(os.path.join(HERE, '..', '..', '..', 'surfd'))
sys.path.insert(0, SURFD)
import rectrack  # noqa: E402

TYPES = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
         '.svg': 'image/svg+xml', '.ttf': 'font/ttf'}
HEAD_KEYS = ('map', 'track', 'leg', 'startseg', 'tickrate', 'movetickrate', 'clock', 'flags', 'momdemo')


def csp():
    # Read from surfd.py so a change there is tested here without a copy.
    src = open(os.path.join(SURFD, 'surfd.py'), encoding='utf-8').read()
    m = re.search(r'^WEB_CSP = \((.*?)\)\n', src, re.S | re.M)
    return ''.join(re.findall(r'"([^"]*)"', m.group(1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--maps', required=True)
    ap.add_argument('--rec', action='append', default=[])
    ap.add_argument('--info', action='append', default=[])
    ap.add_argument('--steam')
    ap.add_argument('--board', help='a saved /board/api/map reply, answered to any query')
    ap.add_argument('--port', type=int, default=8825)
    a = ap.parse_args()
    recs = dict(x.split('=', 1) for x in a.rec)
    infos = dict(x.split('=', 1) for x in a.info)
    policy = csp()

    class H(http.server.BaseHTTPRequestHandler):
        def send(self, code, body, ctype, extra=()):
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            if self.path.startswith('/board/'):
                self.send_header('Content-Security-Policy', policy)
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            if not getattr(self, 'head_only', False):
                self.wfile.write(body)

        def do_HEAD(self):
            self.head_only = True
            self.do_GET()

        def steam(self, rel):
            root = os.path.realpath(a.steam)
            f = os.path.realpath(os.path.join(root, rel))
            if not f.startswith(root + os.sep) or not os.path.isfile(f):
                return self.send(404, b'', 'text/plain')
            size = os.path.getsize(f)
            rng = re.fullmatch(r'bytes=(\d+)-(\d+)', self.headers.get('Range', ''))
            start, end = (int(rng.group(1)), int(rng.group(2))) if rng else (0, size - 1)
            end = min(end, size - 1)
            if getattr(self, 'head_only', False):
                self.send_response(200)
                self.send_header('Content-Length', str(size))
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()
                return
            with open(f, 'rb') as fh:
                fh.seek(start)
                body = fh.read(end - start + 1)
            extra = [('Content-Range', 'bytes %d-%d/%d' % (start, end, size))] if rng else []
            self.send(206 if rng else 200, body, 'application/octet-stream', extra)

        def do_GET(self):
            p = self.path.split('#')[0].split('?')[0]
            if a.steam and p.startswith('/steam/'):
                from urllib.parse import unquote
                return self.steam(unquote(p[len('/steam/'):]))
            m = re.fullmatch(r'/board/api/run/(\d+)/track', p)
            if m and m.group(1) in recs:
                r = rectrack.track(recs[m.group(1)], HEAD_KEYS)
                if not r.get('ok'):
                    return self.send(422, b'{}', 'application/json')
                body = json.dumps({'v': 1, 'rid': int(m.group(1)), 'rec': r['rec'], 'thin': r['thin'],
                                   'truncated': r['truncated']}).encode()
                return self.send(200, body, 'application/json')
            if p == '/board/api/map' and a.board:
                return self.send(200, open(a.board, 'rb').read(), 'application/json')
            m = re.fullmatch(r'/board/api/run/(\d+)', p)
            if m:
                f = infos.get(m.group(1))
                if f is None:
                    return self.send(404, b'{"error":"no such run"}', 'application/json')
                return self.send(200, open(f, 'rb').read(), 'application/json')
            m = re.fullmatch(r'/maps/([A-Za-z0-9_.-]+)\.bsp', p)
            if m:
                f = os.path.join(a.maps, m.group(1) + '.bsp')
                if os.path.isfile(f):
                    return self.send(200, open(f, 'rb').read(), 'application/octet-stream')
                return self.send(404, b'', 'text/plain')
            m = re.fullmatch(r'/board/([A-Za-z0-9_.-]+)', p)
            if m:
                f = os.path.join(SURFD, 'web', m.group(1))
                ext = os.path.splitext(f)[1]
                if os.path.isfile(f) and ext in TYPES:
                    return self.send(200, open(f, 'rb').read(), TYPES[ext])
            self.send(404, b'', 'text/plain')

        def log_message(self, fmt, *args):
            sys.stderr.write('%s\n' % (fmt % args))

    print(f'http://127.0.0.1:{a.port}/board/watch.html#r={next(iter(recs), "")}', flush=True)
    http.server.ThreadingHTTPServer(('127.0.0.1', a.port), H).serve_forever()


if __name__ == '__main__':
    main()
