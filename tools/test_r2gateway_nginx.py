#!/usr/bin/env python3
"""Real unprivileged nginx/gunicorn + R2 falsifier; explicit mirror config only.

Copies the smallest verified map/zone into an owned synthetic rig. Never writes
live source/state, installs anything, or imports surfd. No signed URL is logged.
"""
import argparse
import contextlib
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request

import r2gateway as g


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def request(port, path, method="GET", headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        c.request(method, path, headers=headers or {})
        r = c.getresponse()
        return r.status, dict(r.getheaders()), r.read()
    finally:
        c.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mirror-config", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--nginx", type=Path, default=Path("/usr/sbin/nginx"))
    a = p.parse_args()
    root = a.out.absolute()
    if sys.platform != "linux" or not any((d / "OWNER.md").is_file() for d in root.parents):
        p.error("Linux and owned --out ancestor required")
    root.mkdir(mode=0o700)
    original = json.loads(a.mirror_config.read_text())
    groups, rows = {}, {}
    with contextlib.closing(sqlite3.connect(a.state.absolute().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        for group in ("maps", "zones"):
            row = dict(db.execute("SELECT * FROM assets WHERE group_name=? AND present=1 AND state='verified' ORDER BY bytes LIMIT 1", (group,)).fetchone())
            source = Path(row["source"])
            if not g.regular(source) or row["sig"] != g.signature(source.stat()):
                raise RuntimeError("Chosen live asset changed")
            dest = root / group
            dest.mkdir()
            target = dest / source.name
            shutil.copyfile(source, target)
            if hashlib.sha256(target.read_bytes()).hexdigest() != row["sha"]:
                raise RuntimeError("Copied fixture hash mismatch")
            row.update(source=str(target), sig=g.signature(target.stat()))
            groups[group], rows[group] = str(dest), row
    state = root / "state.sqlite"
    with contextlib.closing(sqlite3.connect(state)) as db:
        db.execute("CREATE TABLE assets(alias TEXT PRIMARY KEY,group_name TEXT,source TEXT,sig TEXT,sha TEXT,object_key TEXT,bytes INTEGER,state TEXT,present INTEGER)")
        for row in rows.values():
            names = ("alias", "group_name", "source", "sig", "sha", "object_key", "bytes", "state", "present")
            db.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?)", tuple(row[n] for n in names))
        db.commit()
    config = dict(original, groups=groups, state=str(state))
    (root / "config.json").write_text(json.dumps(config))
    gateway_port, nginx_port = free_port(), free_port()
    while gateway_port == nginx_port:
        nginx_port = free_port()
    snippet = (Path(__file__).parent / "r2gateway.nginx").read_text().replace("@PORT@", str(gateway_port))
    snippet = snippet.replace("/srv/nvme/ftesurf-server/game/momentum", str(root)).replace("/srv/nvme/ftesurf-site/zones", groups["zones"])
    conf = "pid " + str(root / "nginx.pid") + ";\nerror_log " + str(root / "nginx.log") + " error;\nevents {}\nhttp { access_log off; limit_conn_zone $binary_remote_addr zone=ftesurf_maps:1m; server { listen 127.0.0.1:" + str(nginx_port) + ";\n" + snippet + "\nlocation / { return 404; } } }\n"
    (root / "nginx.conf").write_text(conf)
    env = dict(os.environ, R2GATEWAY_CONFIG=str(root / "config.json"))
    procs = []
    verdicts = []

    def check(ok, name):
        verdicts.append({"test": name, "pass": bool(ok)})
        if not ok:
            raise RuntimeError("Falsifier: " + name)
        print("PASS", name, flush=True)

    def stop(proc):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    try:
        with (root / "gateway.log").open("wb") as out:
            gateway = subprocess.Popen([sys.executable, "-m", "gunicorn", "--bind", "127.0.0.1:" + str(gateway_port), "--workers", "1", "--threads", "4", "--access-logfile", "/dev/null", "r2gateway:create_app()"], cwd=Path(__file__).parent, env=env, stdout=out, stderr=subprocess.STDOUT)
        procs.append(gateway)
        with (root / "nginx-start.log").open("wb") as out:
            nginx = subprocess.Popen([str(a.nginx), "-p", str(root), "-c", str(root / "nginx.conf"), "-e", str(root / "nginx.log"), "-g", "daemon off;"], stdout=out, stderr=subprocess.STDOUT)
        procs.append(nginx)
        map_path = "/" + rows["maps"]["alias"]
        zone_path = "/" + rows["zones"]["alias"]
        end = time.monotonic() + 15
        while True:
            try:
                if request(nginx_port, map_path)[0] == 302:
                    break
            except OSError:
                pass
            if time.monotonic() > end:
                raise RuntimeError("nginx/gateway did not start")
            time.sleep(0.1)
        for group, path in [("maps", map_path), ("zones", zone_path), ("maps", map_path.replace("/ftesurf/", "/"))]:
            status, headers, body = request(nginx_port, path)
            check(status == 302 and headers.get("X-R2-Route") == "r2" and headers.get("Cache-Control") == "no-store", group + " nginx302/no-store")
            with urllib.request.urlopen(headers["Location"], timeout=30) as r:
                blob = r.read()
                check(r.status == 200 and hashlib.sha256(blob).hexdigest() == rows[group]["sha"], group + " R2 full GET hash")
        _, h, _ = request(nginx_port, map_path, "HEAD")
        with urllib.request.urlopen(urllib.request.Request(h["Location"], method="HEAD"), timeout=20) as r:
            check(r.status == 200 and int(r.headers["Content-Length"]) == rows["maps"]["bytes"], "signed HEAD reaches R2")
        _, h, _ = request(nginx_port, map_path)
        with urllib.request.urlopen(urllib.request.Request(h["Location"], headers={"Range": "bytes=0-15"}), timeout=20) as r:
            check(r.status == 206 and len(r.read()) == 16, "R2 byte range206")
        for path in ["/maps/", "/ftesurf/maps/", "/ftesurf/maps/zones/local/", "/ftesurf/maps/missing.bsp", "/data/runs/private.rec"]:
            check(request(nginx_port, path)[0] == 404, "no listing/private/missing: " + path)
        changed = b"new current map bytes"
        Path(rows["maps"]["source"]).write_bytes(changed)
        status, h, body = request(nginx_port, map_path)
        check(status == 200 and body == changed and h.get("X-R2-Route") == "origin", "stale verified map serves NEW local bytes")
        status, h, body = request(nginx_port, map_path, headers={"Range": "bytes=0-3"})
        check(status == 206 and body == changed[:4], "local fallback range206")
        (Path(groups["maps"]) / "new_unmirrored.bsp").write_bytes(b"new asset")
        check(request(nginx_port, "/maps/new_unmirrored.bsp")[2] == b"new asset", "unmirrored map stays available")
        stop(gateway)
        for group, path in [("maps", map_path), ("zones", zone_path)]:
            status, h, body = request(nginx_port, path)
            check(status == 200 and body == Path(rows[group]["source"]).read_bytes() and h.get("X-R2-Route") == "origin", group + " dead gateway still serves origin")
    finally:
        for proc in reversed(procs):
            stop(proc)
        (root / "result.json").write_text(json.dumps({"verdicts": verdicts, "all_processes_exited": all(p.poll() is not None for p in procs)}, indent=2) + "\n")


if __name__ == "__main__":
    main()
