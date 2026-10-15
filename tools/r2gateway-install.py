#!/usr/bin/env python3
"""One-time privileged install of a preverified R2 gateway bundle.

--check is read-only. --apply needs root, preserves the old nginx snippet and
refuses changed predecessors/existing service units. Never touches surfd/lobbies.
"""
import argparse
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time

SNIPPET = Path("/etc/nginx/snippets/ftesurf-maps.conf")
UNIT = Path("/etc/systemd/system/ftesurf-r2gateway.service")
SERVICE = "ftesurf-r2gateway.service"
RUNTIME_PARENT = Path("/srv/nvme/ftesurf-ops")
LOCK = Path("/run/lock/ftesurf-r2gateway-install.lock")
FILES = {"r2gateway.py", "gateway.json", "ftesurf-r2gateway.service", "ftesurf-maps.conf"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ordinary(p):
    return stat.S_ISREG(p.lstat().st_mode)


def checked(bundle):
    b = json.loads(bundle.read_text())
    root = Path(b["runtime"])
    if (root.parent != RUNTIME_PARENT or not re.fullmatch(r"r2gateway-[a-z0-9-]+", root.name) or
            any(p.is_symlink() or not p.is_dir() for p in [root, *root.parents])):
        raise ValueError("Invalid runtime root")
    if set(b["files"]) != FILES:
        raise ValueError("Unexpected bundle file set")
    for name, digest in b["files"].items():
        p = root / name
        if not ordinary(p) or sha(p) != digest:
            raise ValueError("Bundle hash mismatch")
    if not ordinary(SNIPPET) or sha(SNIPPET) != b["nginx_before_sha256"]:
        raise ValueError("Installed nginx predecessor changed; re-inspect")
    if UNIT.exists() or UNIT.is_symlink():
        raise ValueError("Service unit already exists; inspect rather than overwrite")
    if not isinstance(b["port"], int) or not 1024 <= b["port"] <= 65535:
        raise ValueError("Invalid loopback port")
    if not re.fullmatch(r"/ftesurf/maps/[A-Za-z0-9_-]+\.bsp", b["probe_path"]):
        raise ValueError("Invalid public map probe")
    return b, root


def run(*args):
    # Do not emit raw process output: configs/headers may contain private values.
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45)
    if p.returncode:
        raise RuntimeError("Command failed: " + Path(args[0]).name)


def replace(path, body, mode=0o644):
    fd, name = tempfile.mkstemp(prefix=".r2gateway-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            os.fchmod(f.fileno(), mode)
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def probe(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        location = response.getheader("Location", "")
        response.read()
        return (response.status == 302 and response.getheader("X-R2-Route") == "r2" and
                bool(re.match(r"https://[0-9a-f]{32}\.r2\.cloudflarestorage\.com/", location)))
    except OSError:
        return False
    finally:
        conn.close()


def apply(b, root):
    # Only this install's lock; never take over another app's guard or launcher.
    with LOCK.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        checked(root / "bundle.json")
        run("/usr/sbin/nginx", "-t")
        before = SNIPPET.read_bytes()
        backup = SNIPPET.with_name(SNIPPET.name + ".pre-r2-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
        # Exclusive creation: never replace a previous operator recovery copy.
        with backup.open("xb") as f:
            f.write(before)
            f.flush()
            os.fsync(f.fileno())
        installed = False
        replaced = False
        new = (root / "ftesurf-maps.conf").read_bytes()
        try:
            # Prove readiness before changing the public route.
            replace(UNIT, (root / "ftesurf-r2gateway.service").read_bytes())
            installed = True
            run("/usr/bin/systemctl", "daemon-reload")
            run("/usr/bin/systemctl", "start", SERVICE)
            end = time.monotonic() + 15
            while not probe(b["port"], b["probe_path"]):
                if time.monotonic() >= end:
                    raise RuntimeError("Gateway did not prove a verified redirect")
                time.sleep(0.25)
            if sha(SNIPPET) != b["nginx_before_sha256"]:
                raise RuntimeError("Nginx predecessor changed during install")
            replace(SNIPPET, new)
            replaced = True
            run("/usr/sbin/nginx", "-t")
            run("/usr/bin/systemctl", "reload", "nginx")
            run("/usr/bin/systemctl", "enable", SERVICE)
            if sha(SNIPPET) != b["files"]["ftesurf-maps.conf"]:
                raise RuntimeError("Installed snippet hash mismatch")
            print("R2 gateway installed; nginx syntax/reload and loopback redirect PASS.")
            print("Original nginx backup:", backup)
            print("Public URL and fresh-client postflight still required; do not delete local maps.")
        except BaseException:
            # Roll back only our exact bytes, never a concurrent replacement.
            if replaced:
                if sha(SNIPPET) != hashlib.sha256(new).hexdigest():
                    raise RuntimeError("Concurrent nginx replacement: retained recovery, no automatic overwrite")
                replace(SNIPPET, before)
                run("/usr/sbin/nginx", "-t")
                run("/usr/bin/systemctl", "reload", "nginx")
            if installed:
                run("/usr/bin/systemctl", "disable", "--now", SERVICE)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    a = parser.parse_args()
    b, root = checked(a.bundle)
    if not a.apply:
        print("Bundle and unchanged nginx predecessor verified. No changes made.")
        return
    if os.geteuid() != 0:
        raise PermissionError("One-time sudo/root install required")
    apply(b, root)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print("INSTALL REFUSED/FAILED:", type(exc).__name__, str(exc) if isinstance(exc, (ValueError, RuntimeError)) else "Inspect private state; no raw output published")
        raise SystemExit(1)
