"""Gunicorn entry point for the TAS upload service: loopback only, behind nginx."""
import os
import re
from werkzeug.middleware.proxy_fix import ProxyFix
from tasupd import create_app

app = create_app(os.environ['TASUPD_STORE'], os.environ['TASUPD_ACCOUNTS'],
                 [d for d in os.environ['TASUPD_ZONES'].split(os.pathsep) if d], os.environ['TASUPD_URL'],
                 map_cfg_dirs=[d for d in os.environ.get('TASUPD_MAPCFG', '').split(os.pathsep) if d])
# The nginx location replaces X-Forwarded-For with its connection's address.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
source = os.environ['TASUPD_SOURCE']
if not re.fullmatch('[0-9a-f]{40}', source): raise ValueError('Expected inspected tasupd source SHA')


@app.after_request
def source_header(response):
    response.headers['X-Tasupd-Source'] = source
    return response
