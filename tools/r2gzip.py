#!/usr/bin/env python3
"""Gzip companions for r2mirror's verified map bodies (Patch 981).

For each map r2mirror has verified, uploads objects/maps/<sha>.bsp.gz with
Content-Encoding: gzip -- only where gzip saves at least --min-saving, since
most Momentum BSPs are already LZMA-packed inside. r2gateway redirects a client
that accepts gzip to the companion; the raw object stays for everyone else.

Reads r2mirror's state read-only and never writes its keys; keeps its own state
and writer lock in --work, so it runs beside the uploader (cron, flock).
"""
import argparse
import contextlib
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import zlib

import r2mirror as m


def connect(path):
    db = sqlite3.connect(Path(path).absolute(), timeout=30)
    # Not WAL: r2gateway opens this read-only under ProtectSystem=strict, and a
    # WAL database with no -shm beside it cannot be opened that way.
    db.execute("PRAGMA journal_mode=DELETE")
    db.execute("""CREATE TABLE IF NOT EXISTS gz (
        alias TEXT PRIMARY KEY, sha TEXT NOT NULL, bytes INTEGER NOT NULL,
        state TEXT NOT NULL, gz_key TEXT NOT NULL DEFAULT '', gz_sha TEXT NOT NULL DEFAULT '',
        gz_bytes INTEGER NOT NULL DEFAULT 0, verified_at TEXT NOT NULL DEFAULT '',
        error TEXT NOT NULL DEFAULT '')""")
    db.commit()
    db.row_factory = sqlite3.Row
    return db


def verified_maps(state):
    with contextlib.closing(m.connect(state, readonly=True)) as db:
        return db.execute("SELECT * FROM assets WHERE present=1 AND state='verified' "
                          "AND group_name='maps' ORDER BY bytes, alias").fetchall()


class Rclone(m.Rclone):
    def put_gzip(self, source, key, sha):
        command = self.common + ["copyto", str(source), self.remote + "/" + key,
                                 "--bwlimit", self.upload_limit, "--metadata",
                                 "--metadata-set", "sha256=" + sha,
                                 "--metadata-set", "content-type=application/octet-stream",
                                 "--metadata-set", "content-encoding=gzip",
                                 "--metadata-set", "cache-control=public, max-age=31536000, immutable",
                                 "--size-only", "--immutable"]
        p = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1200)
        if p.returncode:
            raise m.TransferError("Upload failed")

    def digest_both(self, key):
        """(sha, size) of the stored bytes and of what they gunzip to, in one read."""
        command = self.common + ["cat", self.remote + "/" + key]
        raw, size, plain, plain_size = hashlib.sha256(), 0, hashlib.sha256(), 0
        inflate = zlib.decompressobj(16 + zlib.MAX_WBITS)
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as p:
            try:
                while True:
                    block = p.stdout.read(1024 * 1024)
                    if not block:
                        break
                    raw.update(block)
                    size += len(block)
                    out = inflate.decompress(block)
                    plain.update(out)
                    plain_size += len(out)
                if p.wait(timeout=1200):
                    raise m.TransferError("Verification read failed")
                if not inflate.eof:
                    raise m.TransferError("Truncated gzip body")
            except zlib.error:
                p.kill()
                p.wait()
                raise m.TransferError("Body is not gzip")
            except BaseException:
                p.kill()
                p.wait()
                raise
        return (raw.hexdigest(), size), (plain.hexdigest(), plain_size)


SAMPLE = 4 * 1024 * 1024


def sample_saving(body):
    """What gzip saves on the first 4 MB: an LZMA-packed BSP shows ~0 there, so
    the full -9 pass is skipped for it (most Momentum maps)."""
    with open(body, "rb") as f:
        head = f.read(SAMPLE)
    if not head:
        return 0.0
    return 1 - len(zlib.compress(head, 6)) / len(head)


def compress(body, work):
    fd, name = tempfile.mkstemp(prefix="gz-", suffix=".part", dir=work)
    path = Path(name)
    with os.fdopen(fd, "wb") as out, open(body, "rb") as inp:
        # mtime 0 and no name: the same body always gives the same bytes.
        with gzip.GzipFile(filename="", mode="wb", fileobj=out, compresslevel=9, mtime=0) as z:
            shutil.copyfileobj(inp, z, 1024 * 1024)
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(block)
    return path, sha.hexdigest(), path.stat().st_size


def one(db, row, work, transport, min_saving):
    done = db.execute("SELECT state FROM gz WHERE alias=? AND sha=? AND state IN ('verified','skip')",
                      (row["alias"], row["sha"])).fetchone()
    if done:
        return done["state"]
    with m.snapshot(row, work) as (body, sha):
        if sha != row["sha"]:
            raise m.TransferError("Source is not the verified body")
        if sample_saving(body) < min_saving / 2:
            with db:
                db.execute("INSERT OR REPLACE INTO gz (alias,sha,bytes,state) VALUES (?,?,?,?)",
                           (row["alias"], sha, row["bytes"], "skip"))
            return "skip"
        gzpath, gzsha, gzbytes = compress(body, work)
        try:
            if gzbytes > row["bytes"] * (1 - min_saving):
                with db:
                    db.execute("INSERT OR REPLACE INTO gz (alias,sha,bytes,state,gz_bytes) VALUES (?,?,?,?,?)",
                               (row["alias"], sha, row["bytes"], "skip", gzbytes))
                return "skip"
            key = "objects/maps/" + sha + ".bsp.gz"
            transport.put_gzip(gzpath, key, gzsha)
            stored, plain = transport.digest_both(key)
            if stored != (gzsha, gzbytes) or plain != (sha, row["bytes"]):
                raise m.TransferError("Remote gzip body mismatch")
            with db:
                db.execute("INSERT OR REPLACE INTO gz (alias,sha,bytes,state,gz_key,gz_sha,gz_bytes,verified_at) "
                           "VALUES (?,?,?,?,?,?,?,?)",
                           (row["alias"], sha, row["bytes"], "verified", key, gzsha, gzbytes, m.utc()))
            return "verified"
        finally:
            gzpath.unlink(missing_ok=True)


def status(db):
    r = db.execute("SELECT SUM(state='verified') AS v, SUM(state='skip') AS s, SUM(state='error') AS e, "
                   "SUM(CASE WHEN state='verified' THEN bytes ELSE 0 END) AS raw, "
                   "SUM(CASE WHEN state='verified' THEN gz_bytes ELSE 0 END) AS gz FROM gz").fetchone()
    return {"gzip": r["v"] or 0, "skipped": r["s"] or 0, "errors": r["e"] or 0,
            "raw_bytes": r["raw"] or 0, "gzip_bytes": r["gz"] or 0}


def run(db, state, work, transport, min_saving, limit=None, only=None):
    attempted = failed = 0
    for row in verified_maps(state):
        if limit is not None and attempted >= limit:
            break
        if only and row["alias"] != only:
            continue
        before = db.execute("SELECT 1 FROM gz WHERE alias=? AND sha=? AND state IN ('verified','skip')",
                            (row["alias"], row["sha"])).fetchone()
        if before:
            continue
        attempted += 1
        try:
            one(db, row, work, transport, min_saving)
        except (OSError, m.TransferError, subprocess.SubprocessError) as exc:
            failed += 1
            with db:
                db.execute("INSERT OR REPLACE INTO gz (alias,sha,bytes,state,error) VALUES (?,?,?,?,?)",
                           (row["alias"], row["sha"], row["bytes"], "error", type(exc).__name__))
        print(json.dumps({"utc": m.utc(), "event": "gzip", "alias": row["alias"],
                          "attempted": attempted, "failed": failed, **status(db)}), flush=True)
    return attempted, failed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["run", "status"])
    p.add_argument("--config", required=True, help="r2mirror's private JSON config (remote, rclone)")
    p.add_argument("--state", required=True, help="r2mirror's state.sqlite, read only")
    p.add_argument("--work", required=True, help="Owned private directory: this tool's state and lock")
    p.add_argument("--min-saving", type=float, default=0.10)
    p.add_argument("--limit", type=int)
    p.add_argument("--only", help="one alias, e.g. ftesurf/maps/surf_x.bsp")
    a = p.parse_args()
    if not 0 < a.min_saving < 1 or (a.limit is not None and a.limit < 0):
        p.error("min-saving must be in (0,1), limit nonnegative")
    os.umask(0o077)
    work = m.check_directory(a.work)
    config = m.load_config(a.config)
    with contextlib.closing(connect(work / "gzip.sqlite")) as db:
        if a.command == "status":
            print(json.dumps({"utc": m.utc(), **status(db)}))
            return 0
        with m.writer_lock(work):
            # A failed pass is retried next time: errors are not 'done'.
            with db:
                db.execute("DELETE FROM gz WHERE state='error'")
            _, failed = run(db, a.state, work, Rclone(config), a.min_saving, a.limit, a.only)
        print(json.dumps({"utc": m.utc(), "event": "pass", **status(db)}), flush=True)
        return int(bool(failed))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, m.TransferError,
            subprocess.SubprocessError, sqlite3.Error) as exc:
        print(json.dumps({"utc": m.utc(), "event": "fatal", "error_class": type(exc).__name__}), flush=True)
        raise SystemExit(1)
