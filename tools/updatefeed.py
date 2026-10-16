#!/usr/bin/env python3
"""Build FTESurf's signed content-addressed update feed from VERIFIED release stages.

Never run this over a player's install. The release script supplies its allowlisted stage.
The private seed is read from a file, never an argument value or subprocess output.
Objects are immutable; publish all objects BEFORE swapping the no-cache update.json.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import ed25519

PUBLIC_KEY = "18c7c332f5bbc913a0fceef38eab9494ce79cf60771fdda093a2d5eabef86cb6"
MAX_FEED = 2 * 1024 * 1024
ROOT = {
    "default.fmf", "ftesurf.bat", "ftesurf.sh", "ftesurf_debug.bat", "LICENSE", "INSTALL.txt",
    "VERSION.txt", "SOURCE.txt", "THIRD-PARTY.txt", "ftesurf64.exe", "ftesurf64",
    "fteplug_hl2_x64.dll", "fteplug_ui_imgui_x64.dll", "fteplug_hl2_amd64.so",
}
GAME = {"ftesurf/csprogs.dat", "ftesurf/qwprogs.dat", "ftesurf/menu.dat",
        "ftesurf/fs_addons.default.txt", "ftesurf/fs_addons.txt", "ftesurf/maps/tiers.txt"}
DATA = {f"ftesurf/data/{name}.txt" for name in ("mapmeta", "mapdeps", "mapmeta_override", "mapparticles", "mapwr", "mapdl", "mapmanifest")}
PREFIXES = ("ftesurf/gfx/", "ftesurf/glsl/", "ftesurf/particles/", "ftesurf/scripts/", "ftesurf/models/", "ftesurf/sound/")


def managed(p: str) -> bool:
    if not p or not p.isascii() or len(p) >= 240 or any(c in p for c in '\\:"*<>?|'):
        return False
    if any(not s or s in (".", "..") or s.endswith((".", " ")) or any(ord(c) < 32 for c in s) for s in p.split("/")):
        return False
    for segment in p.split('/'):
        base = segment.split('.')[0].upper()
        if base in ('CON', 'PRN', 'AUX', 'NUL') or re.fullmatch(r'(COM|LPT)[1-9]', base):
            return False
    if p.startswith('notices/'):
        return '/' not in p[8:] and p.endswith('.txt')
    if p in ROOT | GAME | DATA or p == "ftesurf/cfg/default.cfg":
        return True
    prefix = "ftesurf/maps/zones/local/"
    if p.startswith(prefix):
        tail = p[len(prefix):]
        return "/" not in tail and (tail.endswith(".json") or tail == "manifest.txt")
    prefix = "ftesurf/cfg/"
    if p.startswith(prefix):
        tail = p[len(prefix):]
        return (tail.endswith(".cfg") and not tail.startswith(("test/", "testrun/", "build", "fs_"))
                and "lobby_local" not in tail and tail != "settings.cfg"
                and ("/" not in tail or tail.startswith(("maps/", "lobby/"))))
    return p == "ftesurf/textures/no_texture.png" or p.startswith(PREFIXES)


def no_link(p: Path) -> None:
    for part in (p, *p.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError(f"linked stage/output path: {part}")


def envelope(payload: dict, seed: bytes, public_key: str = PUBLIC_KEY) -> bytes:
    if len(seed) != 32 or ed25519.publickey(seed).hex() != public_key:
        raise ValueError("signing key does not match the pinned update public key")
    text = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    sig = ed25519.sign(seed, text.encode()).hex()
    result = json.dumps({"payload": text, "signature": sig}, ensure_ascii=True, separators=(",", ":")).encode() + b"\n"
    if len(result) > MAX_FEED:
        raise ValueError("update feed exceeds reader limit")
    return result


def verify(data: bytes, public_key: str = PUBLIC_KEY) -> dict:
    if len(data) > MAX_FEED:
        raise ValueError("update feed exceeds reader limit")
    signed = json.loads(data)
    text = signed["payload"]
    if not isinstance(text, str) or "\0" in text or not ed25519.verify(bytes.fromhex(public_key), text.encode(), bytes.fromhex(signed["signature"])):
        raise ValueError("update manifest signature is invalid")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("update payload must be an object")
    return payload


def validate(payload: dict) -> dict[str, int]:
    """Validate descriptors before using signed paths as filesystem/network operands."""
    if (payload.get("schema") != 2 or payload.get("game") != "ftesurf"
            or payload.get("channel") != "stable" or payload.get("hash_algo") != "blake2b-256"
            or payload.get("object_layout") != "objects/{h0h1}/{hash}"
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", payload.get("version", ""))):
        raise ValueError("unsupported update feed")
    files = payload.get("files")
    if not isinstance(files, list) or not files or len(files) > 8192:
        raise ValueError("invalid update file set")
    objects, paths = {}, {}
    for f in files:
        platform = f.get("platform")
        p, h, size = f.get("path"), f.get("hash"), f.get("size")
        if (platform not in ("win64", "linux64") or not isinstance(p, str) or not managed(p)
                or not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h)
                or type(size) is not int or not 0 <= size <= 32 * 1024 * 1024
                or type(f.get("exec")) is not bool):
            raise ValueError("invalid update file descriptor")
        platform_paths = paths.setdefault(platform, set())
        if p.lower() in platform_paths:
            raise ValueError("duplicate update path")
        platform_paths.add(p.lower())
        if h in objects and objects[h] != size:
            raise ValueError("inconsistent object size")
        objects[h] = size
    if sum(f["size"] for f in files) > 160 * 1024 * 1024:
        raise ValueError("feed exceeds small-install limits")
    for platform, names in paths.items():
        exe = "ftesurf64.exe" if platform == "win64" else "ftesurf64"
        if not {exe, "default.fmf", "ftesurf/menu.dat", "ftesurf/csprogs.dat", "ftesurf/qwprogs.dat"} <= names:
            raise ValueError("feed missing required updater file")
        if payload.get("exec_by_platform", {}).get(platform) != {"cmd": exe, "args": ["-manifest", "default.fmf"]}:
            raise ValueError("invalid platform executable")
    return objects


def object_bytes(root: Path, h: str, size: int) -> bytes:
    p = root / h[:2] / h
    no_link(p)
    if not p.is_file():
        raise ValueError(f"missing referenced object: {h}")
    data = p.read_bytes()
    if len(data) != size or hashlib.blake2b(data, digest_size=32).hexdigest() != h:
        raise ValueError(f"corrupt referenced object: {h}")
    return data


def verify_objects(root: Path, payload: dict) -> dict[str, int]:
    objects = validate(payload)
    for h, size in objects.items():
        object_bytes(root, h, size)
    return objects


def check_publication(feed: Path, receipt: Path, version: str, previous: Path,
                      expected_previous: str, public_key: str = PUBLIC_KEY) -> None:
    no_link(feed)
    no_link(receipt)
    data = feed.read_bytes()
    payload = verify(data, public_key)
    objects = validate(payload)
    proof = json.loads(receipt.read_bytes())
    if (payload["version"] != version or proof != {
            "version": version, "feed_sha256": hashlib.sha256(data).hexdigest(),
            "objects": len(objects), "verification": "r2-roundtrip-blake2b-256"}):
        raise ValueError("feed verification receipt does not match")
    if expected_previous == "none":
        if previous.exists() or previous.is_symlink():
            raise ValueError("first feed refuses an existing published feed")
        if {f["platform"] for f in payload["files"]} != {"win64", "linux64"}:
            raise ValueError("first feed requires both supported platforms")
    else:
        if not re.fullmatch(r"[0-9a-f]{64}", expected_previous):
            raise ValueError("explicit previous feed SHA256 required")
        old_data = previous.read_bytes()
        if hashlib.sha256(old_data).hexdigest() != expected_previous:
            raise ValueError("published prior feed changed; refusing stale publication")
        old = verify(old_data, public_key)
        validate(old)
        if tuple(map(int, payload["version"].split('.'))) <= tuple(map(int, old["version"].split('.'))):
            raise ValueError("update version must advance (no rollback or same-version replacement)")
        if not {f["platform"] for f in old["files"]} <= {f["platform"] for f in payload["files"]}:
            raise ValueError("update dropped a supported platform")


def build(stages: dict[str, Path], output: Path, version: str, mirrors: list[str], seed: bytes,
          public_key: str = PUBLIC_KEY, previous: bytes | None = None,
          previous_objects: Path | None = None) -> dict:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("version must be MAJOR.MINOR.PATCH")
    no_link(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("output must be empty (do not reuse another release's objects)")
    output.mkdir(parents=True, exist_ok=True)
    old = verify(previous, public_key) if previous is not None else None
    if old is not None:
        validate(old)
        if tuple(map(int, old["version"].split('.'))) >= tuple(map(int, version.split('.'))):
            raise ValueError("rollback or same-version release: version must advance")
    files = []
    # A Windows-only release must not drop the previous Linux installation's entries.
    if old is not None:
        files.extend(f for f in old["files"] if f["platform"] not in stages)
    executables = dict(old.get("exec_by_platform", {})) if old is not None else {}
    omitted = []
    for platform, stage in stages.items():
        if platform not in ("win64", "linux64"):
            raise ValueError("unknown platform")
        no_link(stage)
        if not stage.is_dir():
            raise ValueError(f"missing stage: {stage}")
        paths = set()
        for source in sorted(stage.rglob("*")):
            no_link(source)
            if not source.is_file():
                continue
            p = source.relative_to(stage).as_posix()
            if not managed(p):
                # Ordinary distribution docs and the launcher itself are not self-managed.
                # Anything player-owned in a stage is still a fatal publishing mistake.
                if p in ("ftesurf-launcher.exe", "ftesurf-launcher"):
                    omitted.append(p)
                    continue
                raise ValueError(f"stage contains an unmanaged file: {p}")
            if p.lower() in paths:
                raise ValueError(f"case-folded duplicate stage path: {p}")
            paths.add(p.lower())
            content = source.read_bytes()
            if len(content) > 32 * 1024 * 1024:
                raise ValueError(f"file exceeds small-install limit: {p}")
            h = hashlib.blake2b(content, digest_size=32).hexdigest()
            obj = output / "objects" / h[:2] / h
            obj.parent.mkdir(parents=True, exist_ok=True)
            if not obj.exists():
                obj.write_bytes(content)
            files.append({"path": p, "hash": h, "size": len(content), "platform": platform,
                          "exec": platform == "linux64" and (p == "ftesurf64" or p.endswith(".sh"))})
        exe = "ftesurf64.exe" if platform == "win64" else "ftesurf64"
        for required in (exe, "default.fmf", "ftesurf/menu.dat", "ftesurf/csprogs.dat", "ftesurf/qwprogs.dat"):
            if required.lower() not in paths:
                raise ValueError(f"stage missing required updater file: {required}")
        executables[platform] = {"cmd": exe, "args": ["-manifest", "default.fmf"]}
    payload = {"schema": 2, "hash_algo": "blake2b-256", "game": "ftesurf", "channel": "stable",
               "version": version, "object_layout": "objects/{h0h1}/{hash}", "mirrors": mirrors,
               "files": sorted(files, key=lambda f: (f["path"], f["platform"])),
               "exec": {"cmd": "ftesurf64.exe", "args": ["-manifest", "default.fmf"]},
               "exec_by_platform": executables, "removed": []}
    objects = validate(payload)
    # Retained platforms need their bytes too, not only descriptors in the new feed.
    for h, size in objects.items():
        obj = output / "objects" / h[:2] / h
        if not obj.exists():
            if previous_objects is None:
                raise ValueError(f"missing retained object cache: {h}")
            data = object_bytes(previous_objects, h, size)
            obj.parent.mkdir(parents=True, exist_ok=True)
            obj.write_bytes(data)
    verify_objects(output / "objects", payload)
    data = envelope(payload, seed, public_key)
    # Transport uses only this full referenced closure, never a remote-prefix listing.
    (output / "objects.txt").write_text(''.join(f"{h[:2]}/{h}\n" for h in sorted(objects)), encoding='ascii')
    (output / "update.json").write_bytes(data)
    return {"version": version, "files": len(files), "objects": len(objects),
            "bytes": sum(f["size"] for f in files), "omitted": omitted}


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "verify-objects":
        p = argparse.ArgumentParser(description="Verify the full referenced object closure downloaded from R2")
        p.add_argument("--feed", type=Path, required=True)
        p.add_argument("--objects", type=Path, required=True)
        p.add_argument("--receipt", type=Path, required=True)
        p.add_argument("--inventory", type=Path)
        p.add_argument("--roundtrip", action="store_true")
        a = p.parse_args(sys.argv[2:])
        data = a.feed.read_bytes()
        payload = verify(data)
        objects = verify_objects(a.objects, payload)
        if a.inventory:
            a.inventory.write_text(''.join(f"{h[:2]}/{h}\n" for h in sorted(objects)), encoding='ascii')
        a.receipt.write_text(json.dumps({"version": payload["version"], "feed_sha256": hashlib.sha256(data).hexdigest(),
            "objects": len(objects), "verification": "r2-roundtrip-blake2b-256" if a.roundtrip else "local-blake2b-256"}, sort_keys=True) + '\n', encoding='ascii')
        print(f"verified {len(objects)} referenced objects")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "check-publication":
        p = argparse.ArgumentParser(description="Check candidate feed, verified receipt and exact live predecessor")
        p.add_argument("--feed", type=Path, required=True)
        p.add_argument("--receipt", type=Path, required=True)
        p.add_argument("--version", required=True)
        p.add_argument("--previous", type=Path, required=True)
        p.add_argument("--expected-previous", required=True)
        a = p.parse_args(sys.argv[2:])
        check_publication(a.feed, a.receipt, a.version, a.previous, a.expected_previous)
        print("update publication checks passed")
        return
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--windows", type=Path)
    p.add_argument("--linux", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--mirror", action="append", required=True)
    p.add_argument("--seed-file", type=Path, default=Path(os.environ.get("FTESURF_UPDATE_SEED_FILE", "C:/FTESurf-private/keys/ftesurf-updates/seed")))
    policy = p.add_mutually_exclusive_group(required=True)
    policy.add_argument("--previous", type=Path)
    policy.add_argument("--first-release", action="store_true")
    p.add_argument("--previous-objects", type=Path, help="read-only objects/ cache for retained platform bytes")
    a = p.parse_args()
    if not a.windows and not a.linux:
        p.error("at least one verified platform stage is required")
    stages = {k: v for k, v in (("win64", a.windows), ("linux64", a.linux)) if v}
    if a.first_release and set(stages) != {"win64", "linux64"}:
        p.error("first feed requires verified Windows AND Linux stages")
    # Do not echo seed bytes or exceptions containing private file contents.
    result = build(stages, a.output, a.version, a.mirror, a.seed_file.read_bytes(),
                   previous=a.previous.read_bytes() if a.previous else None, previous_objects=a.previous_objects)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
