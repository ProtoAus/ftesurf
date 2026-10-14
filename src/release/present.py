#!/usr/bin/env python3
"""Publish a complete presentation tree, never a release. Linux/POSIX only.

Caller stages .incoming/<generation>, supplies a saved whole-file SHA256 manifest
and exact static predecessor. Rendering remains Get-ReceiptTokens' responsibility.
All writers must honor .publish.lock; staging must be quiescent during this call.
No history is pruned. A failed swap may retain an unadvertised generation.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid

PUBLIC_PRESENTATION = frozenset({
    "index.html", "anticheat.html", "site.css", "apple-touch-icon.png",
    "favicon.svg", "og-worldofsurf.png", "worldofsurf-192.png",
    "worldofsurf-512.png", "worldofsurf-wordmark.svg",
})
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
POINTER = re.compile(r"(?:releases/[0-9]+\.[0-9]+\.[0-9]+|presentations/[A-Za-z0-9][A-Za-z0-9_-]{0,79})\Z")
TOKEN = re.compile(rb"@@[^@\s]+@@")
PROTECTED = {"version.json", "update.json", "update-verified.json"}


class PublicationError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise PublicationError(message)


def ordinary(path, directory=True):
    """Check each lexical ancestor without resolving links away."""
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "path must be ordinary and absolute")
    for part in [*reversed(path.parents), path]:
        mode = part.lstat().st_mode
        require(stat.S_ISDIR(mode) if part != path or directory else stat.S_ISREG(mode),
                "linked or nonordinary path refused")
    return path


def walk_error(error):
    raise error


def manifest(root):
    root = ordinary(root)
    result = {}
    for base, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        for name in dirs + files:
            path = Path(base) / name
            info = path.lstat()
            require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode),
                    "linked or special tree entry refused")
            if stat.S_ISREG(info.st_mode):
                require(info.st_nlink == 1, "hardlinked file refused")
                with path.open("rb") as stream:
                    digest = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                result[path.relative_to(root).as_posix()] = digest.hexdigest()
    return result


def current(site, expected, hashes):
    pointer = site / "static"
    require(stat.S_ISLNK(pointer.lstat().st_mode), "static must be a symlink")
    target = os.readlink(pointer)
    require(POINTER.fullmatch(target) is not None, "static target outside supported history")
    require(target == expected, "stale static predecessor")
    require(manifest(site / target) == hashes, "stale whole-file manifest")
    return target


def rename_generation(source, destination):
    # rename(2) can overwrite an empty directory; immutable generations need NOREPLACE.
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        raise OSError(ctypes.get_errno(), "generation rename failed")


def publish(site, generation, expected_pointer, expected_manifest, dry_run=False):
    import fcntl
    site = ordinary(Path(site))
    require(SAFE_ID.fullmatch(generation) is not None, "invalid generation")
    require(POINTER.fullmatch(expected_pointer) is not None, "invalid predecessor")
    require(isinstance(expected_manifest, dict) and PROTECTED <= expected_manifest.keys(),
            "whole manifest must include receipt and both feeds")
    require(all(isinstance(k, str) and isinstance(v, str) and
                re.fullmatch(r"[0-9a-f]{64}", v) for k, v in expected_manifest.items()),
            "invalid SHA256 manifest")
    # Setup is explicit. Opening an existing lock keeps dry runs mutation-free.
    ordinary(site / ".incoming")
    ordinary(site / "presentations")
    lock = ordinary(site / ".publish.lock", directory=False)
    fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        require(os.fstat(fd).st_nlink == 1, "hardlinked publication lock refused")
        fcntl.flock(fd, fcntl.LOCK_EX)
        require((os.fstat(fd).st_dev, os.fstat(fd).st_ino) ==
                (lock.lstat().st_dev, lock.lstat().st_ino), "publication lock replaced")
        for parent in [site / "presentations", site, *site.parents]:
            ordinary(parent)
            require(parent.lstat().st_mode & stat.S_IXOTH, "site traversal permissions failed")
        source = site / ".incoming" / generation
        destination = site / "presentations" / generation
        require(not os.path.lexists(destination), "generation already exists")
        rollback = current(site, expected_pointer, expected_manifest)
        proposed = manifest(source)
        require("index.html" in proposed, "index.html missing")
        require(not (expected_manifest.keys() - proposed.keys()), "file removals refused")
        changed = sorted(k for k, v in proposed.items() if expected_manifest.get(k) != v)
        require(set(changed) <= PUBLIC_PRESENTATION, "non-public presentation change refused")
        for name in PUBLIC_PRESENTATION & proposed.keys():
            if name.endswith((".html", ".css", ".svg")):
                require(not TOKEN.search((source / name).read_bytes()), "unresolved presentation token")
        summary = {"dry_run": dry_run, "target": "presentations/" + generation,
                   "rollback_pointer": rollback, "file_count": len(proposed),
                   "changed": {k: proposed[k] for k in changed}}
        if dry_run:
            return summary
        for base, dirs, files in os.walk(source, onerror=walk_error):
            os.chmod(base, 0o755)
            for name in files:
                os.chmod(Path(base) / name, 0o644)
        for base, dirs, files in os.walk(source, onerror=walk_error):
            require(stat.S_IMODE(Path(base).lstat().st_mode) == 0o755, "directory permissions failed")
            for name in files:
                require(stat.S_IMODE((Path(base) / name).lstat().st_mode) == 0o644,
                        "file permissions failed")
        require(manifest(source) == proposed, "staged tree changed")
        current(site, expected_pointer, expected_manifest)
        temporary = site / (".static.present-" + uuid.uuid4().hex)
        identity = None
        try:
            os.symlink(summary["target"], temporary)
            identity = temporary.lstat()
            rename_generation(source, destination)
            require(manifest(destination) == proposed, "generation changed")
            current(site, expected_pointer, expected_manifest)
            now = temporary.lstat()
            require((now.st_dev, now.st_ino, now.st_ctime_ns) ==
                    (identity.st_dev, identity.st_ino, identity.st_ctime_ns) and
                    stat.S_ISLNK(now.st_mode) and os.readlink(temporary) == summary["target"],
                    "temporary pointer replaced")
            os.replace(temporary, site / "static")
        finally:
            if identity is not None and os.path.lexists(temporary):
                now = temporary.lstat()
                if (now.st_dev, now.st_ino, now.st_ctime_ns) == (
                        identity.st_dev, identity.st_ino, identity.st_ctime_ns):
                    temporary.unlink()
        return summary
    except (OSError, AttributeError) as exc:
        raise PublicationError("filesystem publication gate failed (errno %s)" %
                               getattr(exc, "errno", "unsupported")) from exc
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--generation", required=True)
    parser.add_argument("--expected-pointer", required=True)
    parser.add_argument("--manifest", required=True, help="saved JSON {relative file: SHA256}")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        with ordinary(Path(args.manifest).absolute(), directory=False).open() as stream:
            hashes = json.load(stream)
        print(json.dumps(publish(args.site, args.generation, args.expected_pointer,
                                 hashes, args.dry_run), sort_keys=True))
        return 0
    except (PublicationError, OSError, ValueError, ImportError) as exc:
        # Do not echo filesystem paths or supplied file contents.
        message = str(exc) if isinstance(exc, PublicationError) else "invalid input or filesystem setup"
        print("presentation refused: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
