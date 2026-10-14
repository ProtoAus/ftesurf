#!/usr/bin/env python3
"""Resumable, verified PUBLIC asset staging; never changes the game or deletes R2 data.

Config/state/credentials belong outside web-served paths. See r2mirror.md.
Content-addressed bodies are published before the small compatibility catalogue.
The catalogue contains no local paths. A successful upload is not a CDN cutover.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import tempfile
import time

FORMATS = {
    "maps": (r"[A-Za-z0-9_-]+\.bsp", "ftesurf/maps/", "application/octet-stream"),
    "zones": (r"[A-Za-z0-9_-]+\.json", "ftesurf/maps/zones/local/", "application/json"),
    "mapshots": (r"[A-Za-z0-9_-]+\.jpg", "board/shot/", "image/jpeg"),
    "avatars": (r"[0-9a-f]{40}\.jpg", "avatars/", "image/jpeg"),
    "avatar_rgba": (r"[0-9a-f]{40}\.txt", "avatars/game/", "text/plain"),
}


class TransferError(Exception):
    """Safe to name, but transport output must not escape into reports."""


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def signature(s):
    return json.dumps([s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns])


def ordinary(path):
    s = path.lstat()
    return not (stat.S_ISLNK(s.st_mode) or
                getattr(s, "st_file_attributes", 0) & 0x400)


def check_directory(path):
    path = Path(path).absolute()
    for part in [path, *path.parents]:
        if not ordinary(part) or not part.is_dir():
            raise ValueError("Directory or ancestor is linked/non-directory")
    return path


def load_config(path):
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    if not re.fullmatch(r"[A-Za-z0-9_-]+:[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", c["remote"]):
        raise ValueError("Expected a named rclone remote and explicit bucket")
    if not c.get("groups"):
        raise ValueError("No public source groups")
    if not re.fullmatch(r"manifests/[a-z0-9_-]+\.json", c.get("manifest", "manifests/public.json")):
        raise ValueError("Expected a manifest in the fixed public namespace")
    for name, directory in c["groups"].items():
        if name not in FORMATS:
            raise ValueError("Only allowlisted public asset groups are accepted")
        check_directory(directory)
    return c


def connect(path, readonly=False):
    path = Path(path).absolute()
    if readonly:
        if not path.is_file():
            raise ValueError("No existing upload state")
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=30)
        db.execute("PRAGMA query_only=ON")
    else:
        db = sqlite3.connect(path, timeout=30)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS assets (
            alias TEXT PRIMARY KEY, group_name TEXT NOT NULL, source TEXT NOT NULL,
            sig TEXT NOT NULL, bytes INTEGER NOT NULL, present INTEGER NOT NULL,
            state TEXT NOT NULL, sha TEXT NOT NULL DEFAULT '',
            object_key TEXT NOT NULL DEFAULT '', verified_at TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '')""")
        db.commit()
    db.row_factory = sqlite3.Row
    return db


@contextlib.contextmanager
def writer_lock(work):
    """One writer, automatically released after a killed/crashed process."""
    lock = Path(work) / "writer.lock"
    with lock.open("a+b") as f:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            if not f.read(1):
                f.write(b"0")
                f.flush()
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == "nt":
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)


def scan(db, config):
    observed = []
    for group, root in config["groups"].items():
        root = check_directory(root)
        pattern, prefix, _ = FORMATS[group]
        # Do not recurse: excludes .old, zones below maps, partials and sidecars.
        for source in sorted(root.iterdir()):
            if not re.fullmatch(pattern, source.name):
                continue
            s = source.lstat()
            if not ordinary(source) or not stat.S_ISREG(s.st_mode) or not s.st_size:
                continue
            observed.append((prefix + source.name, group, str(source), signature(s), s.st_size))
    # A wiped/unmounted source must not silently become a complete empty mirror.
    for group, minimum in config.get("minimum_files", {}).items():
        if group not in config["groups"] or not isinstance(minimum, int) or minimum < 0:
            raise ValueError("Invalid source inventory minimum")
        if sum(row[1] == group for row in observed) < minimum:
            raise ValueError("Source inventory below its registered minimum")
    # Enumeration must finish successfully before changing presence/readiness.
    with db:
        db.execute("UPDATE assets SET present=0")
        for alias, group, source, sig, size in observed:
            old = db.execute("SELECT * FROM assets WHERE alias=?", (alias,)).fetchone()
            if old and old["sig"] == sig and old["source"] == source:
                db.execute("UPDATE assets SET present=1, state=CASE WHEN state='error' "
                           "THEN 'pending' ELSE state END WHERE alias=?", (alias,))
            else:
                db.execute("INSERT OR REPLACE INTO assets "
                           "(alias,group_name,source,sig,bytes,present,state) "
                           "VALUES (?,?,?,?,?,1,'pending')", (alias, group, source, sig, size))
    return len(observed)


def current(row):
    try:
        path = Path(row["source"])
        return ordinary(path) and signature(path.stat()) == row["sig"]
    except OSError:
        return False


@contextlib.contextmanager
def snapshot(row, work):
    """Capture one regular source handle; stage at most one asset, not the library."""
    fd, name = tempfile.mkstemp(prefix="body-", suffix=".part", dir=work)
    path = Path(name)
    try:
        source = Path(row["source"])
        if not current(row):
            raise TransferError("Source changed")
        # O_NOFOLLOW closes the path-symlink race on the upload host (Linux).
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        source_fd = os.open(source, flags)
        with os.fdopen(fd, "wb") as out, os.fdopen(source_fd, "rb") as inp:
            fd = None
            before = os.fstat(inp.fileno())
            if not stat.S_ISREG(before.st_mode) or signature(before) != row["sig"]:
                raise TransferError("Source changed")
            sha = hashlib.sha256()
            while True:
                block = inp.read(1024 * 1024)
                if not block:
                    break
                sha.update(block)
                out.write(block)
            out.flush()
            if signature(os.fstat(inp.fileno())) != row["sig"] or not current(row):
                raise TransferError("Source changed")
        yield path, sha.hexdigest()
    finally:
        if fd is not None:
            os.close(fd)
        path.unlink(missing_ok=True)


class Rclone:
    def __init__(self, config):
        self.remote = config["remote"]
        self.upload_limit = config.get("upload_limit", "3M")
        self.common = [config.get("rclone", "rclone"), "--config", config["rclone_config"],
                       "--bind", "0.0.0.0", "--log-level", "ERROR", "--contimeout", "15s",
                       "--timeout", "1m", "--retries", "2", "--low-level-retries", "2",
                       "--s3-no-check-bucket"]

    def put(self, source, key, sha, content_type, immutable=True):
        cache = "public, max-age=31536000, immutable" if immutable else "public, max-age=30"
        command = self.common + ["copyto", str(source), self.remote + "/" + key,
                                "--bwlimit", self.upload_limit, "--metadata",
                                "--metadata-set", "sha256=" + sha,
                                "--metadata-set", "content-type=" + content_type,
                                "--metadata-set", "cache-control=" + cache]
        command += ["--size-only", "--immutable"] if immutable else ["--ignore-times"]
        p = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=1200)
        if p.returncode:
            raise TransferError("Upload failed")

    def digest(self, key):
        command = self.common + ["cat", self.remote + "/" + key]
        sha, size = hashlib.sha256(), 0
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as p:
            try:
                while True:
                    block = p.stdout.read(1024 * 1024)
                    if not block:
                        break
                    sha.update(block)
                    size += len(block)
                if p.wait(timeout=1200):
                    raise TransferError("Verification read failed")
            except BaseException:
                p.kill()
                p.wait()
                raise
        return sha.hexdigest(), size


def upload_one(db, row, work, transport):
    with snapshot(row, work) as (body, sha):
        suffix = Path(row["alias"]).suffix
        key = "objects/" + row["group_name"] + "/" + sha + suffix
        transport.put(body, key, sha, FORMATS[row["group_name"]][2])
        if transport.digest(key) != (sha, row["bytes"]):
            raise TransferError("Remote body mismatch")
        if not current(row):
            raise TransferError("Source changed after upload")
        with db:
            db.execute("UPDATE assets SET state='verified',sha=?,object_key=?,verified_at=?,"
                       "error='' WHERE alias=? AND sig=?", (sha, key, utc(), row["alias"], row["sig"]))


def copy_pending(db, work, transport, group=None, limit=None):
    sql = "SELECT * FROM assets WHERE present=1 AND state='pending'"
    args = []
    if group:
        sql += " AND group_name=?"
        args.append(group)
    sql += " ORDER BY CASE group_name WHEN 'zones' THEN 0 WHEN 'maps' THEN 1 ELSE 2 END, bytes, alias"
    if limit is not None:
        sql += " LIMIT ?"
        args.append(limit)
    attempted = failed = 0
    for row in db.execute(sql, args).fetchall():
        attempted += 1
        try:
            upload_one(db, row, work, transport)
        except (OSError, TransferError, subprocess.SubprocessError) as exc:
            failed += 1
            # Never persist transport stdout, signed URLs, exception messages or paths.
            with db:
                db.execute("UPDATE assets SET state='error',error=? WHERE alias=?",
                           (type(exc).__name__, row["alias"]))
        print(json.dumps({"utc": utc(), "event": "body", "attempted": attempted,
                          "failed": failed, **status(db)}), flush=True)
    return attempted, failed


def status(db):
    groups = {}
    for r in db.execute("SELECT group_name,COUNT(*) AS files,SUM(bytes) AS bytes,"
                        "SUM(state='verified') AS verified_files,"
                        "SUM(CASE WHEN state='verified' THEN bytes ELSE 0 END) AS verified_bytes,"
                        "SUM(state='error') AS errors FROM assets WHERE present=1 GROUP BY group_name"):
        groups[r["group_name"]] = {k: r[k] for k in ("files", "bytes", "verified_files", "verified_bytes", "errors")}
    complete = bool(groups) and all(v["files"] == v["verified_files"] for v in groups.values())
    return {"groups": groups, "catalog_complete": complete}


def catalogue(db):
    # Re-check local readiness even if an upload/scan happened hours ago.
    items = {}
    with db:
        for row in db.execute("SELECT * FROM assets WHERE present=1 AND state='verified'").fetchall():
            if not current(row):
                db.execute("UPDATE assets SET state='pending',verified_at='' WHERE alias=?", (row["alias"],))
                continue
            items[row["alias"]] = {"key": row["object_key"], "sha256": row["sha"],
                                   "bytes": row["bytes"], "type": FORMATS[row["group_name"]][2]}
    return {"schema": 1, "generated_utc": utc(), "complete": status(db)["catalog_complete"], "assets": items}


def publish(db, work, transport, manifest="manifests/public.json"):
    doc = catalogue(db)
    fd, name = tempfile.mkstemp(prefix="catalogue-", suffix=".json", dir=work)
    path = Path(name)
    try:
        raw = (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode()
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        sha = hashlib.sha256(raw).hexdigest()
        transport.put(path, manifest, sha, "application/json", immutable=False)
        if transport.digest(manifest) != (sha, len(raw)):
            raise TransferError("Catalogue body mismatch")
        return doc
    finally:
        path.unlink(missing_ok=True)


def audit(db, transport):
    failed = 0
    for row in db.execute("SELECT * FROM assets WHERE present=1 AND state='verified'").fetchall():
        try:
            ok = current(row) and transport.digest(row["object_key"]) == (row["sha"], row["bytes"])
        except (OSError, TransferError, subprocess.SubprocessError):
            ok = False
        if not ok:
            failed += 1
            with db:
                db.execute("UPDATE assets SET state='error',error='AuditMismatch' WHERE alias=?", (row["alias"],))
    return failed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["scan", "run", "status", "audit"])
    p.add_argument("--config", required=True, help="Private JSON config, never secret values on CLI")
    p.add_argument("--work", required=True, help="Owned, private scratch/state directory")
    p.add_argument("--group", choices=sorted(FORMATS))
    p.add_argument("--limit", type=int)
    p.add_argument("--watch", type=int, default=0, help="Repeat after this many seconds; 0 is one pass")
    a = p.parse_args()
    if a.limit is not None and a.limit < 0 or a.watch < 0:
        p.error("Limit/watch must be nonnegative")
    os.umask(0o077)
    work = check_directory(a.work)
    config = load_config(a.config)
    with contextlib.closing(connect(work / "state.sqlite", readonly=a.command == "status")) as db:
        if a.command == "status":
            print(json.dumps({"utc": utc(), **status(db)}))
            return 0
        with writer_lock(work):
            transport = Rclone(config) if a.command != "scan" else None
            if a.command == "audit":
                failed = audit(db, transport)
                print(json.dumps({"utc": utc(), "audit_failures": failed, **status(db)}))
                return int(bool(failed))
            while True:
                scan(db, config)
                if a.command == "run":
                    _, failed = copy_pending(db, work, transport, a.group, a.limit)
                    publish(db, work, transport, config.get("manifest", "manifests/public.json"))
                    print(json.dumps({"utc": utc(), "event": "catalogue", **status(db)}), flush=True)
                else:
                    failed = 0
                    print(json.dumps({"utc": utc(), **status(db)}))
                if not a.watch:
                    return int(bool(failed))
                time.sleep(a.watch)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, TransferError,
            subprocess.SubprocessError, sqlite3.Error) as exc:
        print(json.dumps({"utc": utc(), "event": "fatal", "error_class": type(exc).__name__}), flush=True)
        raise SystemExit(1)
