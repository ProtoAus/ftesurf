#!/usr/bin/env python3
"""Read-only R2 redirect gateway for r2mirror assets; never imports surfd.

Use behind r2gateway.nginx. HTTP409 requests a rate-limited local fallback.
Only a current, verified content-addressed public asset receives a signed URL.
"""
import configparser
import contextlib
import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading
import time
from urllib.parse import quote, urlsplit
import urllib.request

FORMATS = {
    "maps": (r"/(?:ftesurf/)?maps/([A-Za-z0-9_-]+)\.bsp", "ftesurf/maps/", ".bsp"),
    "zones": (r"/ftesurf/maps/zones/local/([A-Za-z0-9_-]+)\.json", "ftesurf/maps/zones/local/", ".json"),
    "mapshots": (r"/board/shot/([A-Za-z0-9_-]+?)(?:\.jpg)?", "board/shot/", ".jpg"),
}


def regular(path, directory=False):
    s = Path(path).lstat()
    if getattr(s, "st_file_attributes", 0) & 0x400:
        return False
    return stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)


def directory(path):
    p = Path(path).absolute()
    if any(not regular(q, directory=True) for q in [p, *p.parents]):
        raise ValueError("Linked or non-directory source/config ancestor")
    return p


def signature(s):
    # Same five-field observation as r2mirror.signature; no file content reads.
    return json.dumps([s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns])


def signed_url(endpoint, bucket, access, secret, key, method, now=None, expires=300):
    host = urlsplit(endpoint).netloc
    now = now or datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    date = stamp[:8]
    scope = date + "/auto/s3/aws4_request"
    encode = lambda v: quote(str(v), safe="-_.~")
    path = "/" + encode(bucket) + "/" + quote(key, safe="/-_.~")
    params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": access + "/" + scope,
        "X-Amz-Date": stamp,
        "X-Amz-Expires": str(expires),
        "X-Amz-SignedHeaders": "host",
    }
    query = "&".join(encode(k) + "=" + encode(v) for k, v in sorted(params.items()))
    canonical = method + "\n" + path + "\n" + query + "\nhost:" + host + "\n\nhost\nUNSIGNED-PAYLOAD"
    message = "AWS4-HMAC-SHA256\n" + stamp + "\n" + scope + "\n" + hashlib.sha256(canonical.encode()).hexdigest()
    digest = lambda k, v: hmac.new(k, v.encode(), hashlib.sha256).digest()
    signing = digest(("AWS4" + secret).encode(), date)
    for part in ("auto", "s3", "aws4_request"):
        signing = digest(signing, part)
    sig = hmac.new(signing, message.encode(), hashlib.sha256).hexdigest()
    return endpoint.rstrip("/") + path + "?" + query + "&X-Amz-Signature=" + sig


class Gateway:
    def __init__(self, config, reachability=None):
        self.state = directory(Path(config["state"]).parent) / Path(config["state"]).name
        self.groups = {k: directory(v) for k, v in config["groups"].items()}
        if not self.groups or not set(self.groups) <= set(FORMATS):
            raise ValueError("Only public maps/zones/mapshots are supported")
        credentials = Path(config["rclone_config"])
        directory(credentials.parent)
        if not regular(credentials):
            raise ValueError("Credential config is not regular")
        cp = configparser.ConfigParser(interpolation=None)
        cp.read(credentials, encoding="utf-8")
        section, self.bucket = config["remote"].split(":", 1)
        c = cp[section]
        self.endpoint = c["endpoint"].rstrip("/")
        if not re.fullmatch(r"https://[0-9a-f]{32}\.r2\.cloudflarestorage\.com", self.endpoint):
            raise ValueError("Expected a standard Cloudflare R2 HTTPS endpoint")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.bucket):
            raise ValueError("Invalid explicit bucket")
        self.access, self.secret = c["access_key_id"], c["secret_access_key"]
        if not self.access or not self.secret:
            raise ValueError("Missing object credentials")
        self.reachability = reachability or self.head_probe
        self.probe_lock = threading.Lock()
        self.probe_until = 0.0
        self.probe_ok = False

    def head_probe(self, key):
        url = signed_url(self.endpoint, self.bucket, self.access, self.secret, key, "HEAD")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=2) as r:
                return r.status == 200
        except (OSError, ValueError):
            return False

    def r2_available(self, key):
        now = time.monotonic()
        if now < self.probe_until:
            return self.probe_ok
        # One bounded signed HEAD per worker/15s; other cold/stale callers use disk.
        if not self.probe_lock.acquire(blocking=False):
            return False
        try:
            if now >= self.probe_until:
                self.probe_ok = bool(self.reachability(key))
                self.probe_until = time.monotonic() + (15 if self.probe_ok else 2)
            return self.probe_ok
        finally:
            self.probe_lock.release()

    def resolve(self, path):
        for group, (pattern, prefix, suffix) in FORMATS.items():
            match = re.fullmatch(pattern, path)
            if group in self.groups and match:
                leaf = match[1] + suffix
                return group, prefix + leaf, self.groups[group] / leaf, suffix
        return None

    def ready_key(self, resolved):
        group, alias, source, suffix = resolved
        # No database creation, schema migration, write PRAGMA, or shared app import.
        if not regular(self.state) or not regular(source):
            return None
        with contextlib.closing(sqlite3.connect(self.state.as_uri() + "?mode=ro", uri=True, timeout=0.25)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM assets WHERE alias=? AND present=1 AND state='verified'", (alias,)).fetchone()
        if not row or row["group_name"] != group or row["source"] != str(source):
            return None
        sha = row["sha"]
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            return None
        expected = "objects/" + group + "/" + sha + suffix
        s = source.lstat()
        if (row["object_key"] != expected or not isinstance(row["bytes"], int) or row["bytes"] <= 0 or
                not stat.S_ISREG(s.st_mode) or row["bytes"] != s.st_size or row["sig"] != signature(s)):
            return None
        return expected

    def __call__(self, environ, start_response):
        method, path = environ.get("REQUEST_METHOD", ""), environ.get("PATH_INFO", "")
        headers = [("Cache-Control", "no-store"), ("Referrer-Policy", "no-referrer")]
        body = b""
        if method not in ("GET", "HEAD"):
            status = "405 Method Not Allowed"
            headers.append(("Allow", "GET, HEAD"))
        elif path == "/r2gateway-health":
            status, body = "200 OK", b"ok\n" if method == "GET" else b""
        else:
            resolved = self.resolve(path)
            if resolved is None:
                status = "404 Not Found"
            else:
                try:
                    key = self.ready_key(resolved)
                except (OSError, ValueError, sqlite3.Error):
                    key = None
                if key and self.r2_available(key):
                    status = "302 Found"
                    headers += [("Location", signed_url(self.endpoint, self.bucket, self.access, self.secret, key, method)),
                                ("X-R2-Route", "r2")]
                else:
                    status = "409 Conflict"
                    headers.append(("X-R2-Route", "origin"))
        headers.append(("Content-Length", str(len(body))))
        start_response(status, headers)
        return [body]


def create_app():
    config = Path(os.environ["R2GATEWAY_CONFIG"])
    directory(config.parent)
    if not regular(config):
        raise ValueError("Gateway config is not regular")
    return Gateway(json.loads(config.read_text(encoding="utf-8")))
