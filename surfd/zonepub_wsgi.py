"""Gunicorn entry point for the independent, non-migrating zone draft service."""
import json
import os
import re
from werkzeug.middleware.proxy_fix import ProxyFix
from zonepub import create_app

app = create_app(os.environ['ZONEPUB_STORE'], os.environ['ZONEPUB_ACCOUNTS'],
                 json.loads(os.environ['ZONEPUB_GAMES']))
# This listener is LOOPBACK ONLY. The dedicated nginx location replaces, rather
# than appends, X-Forwarded-For with its connection's remote address.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
source = os.environ['ZONEPUB_SOURCE']
if not re.fullmatch('[0-9a-f]{40}', source): raise ValueError('Expected inspected zonepub source SHA')

@app.after_request
def source_header(response):
    response.headers['X-Zonepub-Source'] = source
    return response
