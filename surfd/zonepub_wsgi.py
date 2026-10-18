"""Gunicorn entry point for the independent, non-migrating zone upload service."""
import json
import os
import re
import threading
import time
from werkzeug.middleware.proxy_fix import ProxyFix
from zonepub import create_app
import zonepub_publish

app = create_app(os.environ['ZONEPUB_STORE'], os.environ['ZONEPUB_ACCOUNTS'],
                 json.loads(os.environ['ZONEPUB_GAMES']),
                 publish_dirs=json.loads(os.environ.get('ZONEPUB_PUBLISH', '[]')),
                 sweep_log=os.environ.get('ZONEPUB_SWEEPLOG', '/srv/nvme/surfd/logs/sweep.log'))
# This listener is LOOPBACK ONLY. The dedicated nginx location replaces, rather
# than appends, X-Forwarded-For with its connection's remote address.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
source = os.environ['ZONEPUB_SOURCE']
if not re.fullmatch('[0-9a-f]{40}', source): raise ValueError('Expected inspected zonepub source SHA')


@app.after_request
def source_header(response):
    response.headers['X-Zonepub-Source'] = source
    return response


def _applier(interval=60):
    # P815: hears the lobbies every minute and publishes what has become quiet.
    while True:
        try: app.config['ZONEPUB_APPLY'](int(time.time()))
        except Exception as e: zonepub_publish.log('tick failed:', e)
        time.sleep(interval)


if json.loads(os.environ.get('ZONEPUB_PUBLISH', '[]')) and os.environ.get('ZONEPUB_NO_TICK') != '1':
    threading.Thread(target=_applier, name='zonepub-apply', daemon=True).start()
