"""Gunicorn entry point for the TAS revision service (P1091): loopback only, behind nginx."""
import os
import re
from werkzeug.middleware.proxy_fix import ProxyFix
from tasrevd import create_app

app = create_app(os.environ['TASREVD_STORE'], os.environ['TASREVD_ACCOUNTS'], os.environ['TASREVD_CODES'])
# The nginx location replaces X-Forwarded-For with its connection's address.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
source = os.environ['TASREVD_SOURCE']
if not re.fullmatch('[0-9a-f]{40}', source): raise ValueError('Expected inspected tasrevd source SHA')


@app.after_request
def source_header(response):
    response.headers['X-Tasrevd-Source'] = source
    return response
