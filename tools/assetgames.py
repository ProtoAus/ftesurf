#!/usr/bin/env python3
"""assetgames.py -- which Source game ships each materials/ and models/ directory (Patch 1625).

Writes ftesurf/scripts/assetgames.txt.  The hl2 plugin reads it when a map's textures or props do
not load, so the warning can say "CS:S: materials/de_train/train_cement_floor_02" instead of only
the name.  Directory granularity, not files: a directory's label is every game with a file anywhere
under it, and only the directories whose label differs from their parent's are written, so TF2's
thousands of workshop folders collapse into a few lines.  Longest prefix wins at lookup.

    python3 tools/assetgames.py [--steam ~/.local/share/Steam/steamapps/common] [--dry]

A game that is not installed here simply contributes nothing; the header names the ones read.
"""
import argparse
import os
import struct
import sys

#Label, game folder under steamapps/common, the *_dir.vpk names to read.  Label order is the print
#order for a directory several games share.  HL2 and Momentum last: nearly every install has them.
GAMES = [
    ("CS:S", "Counter-Strike Source/cstrike", ["cstrike_pak_dir.vpk"]),
    ("CS:GO", "csgo legacy/csgo", ["pak01_dir.vpk"]),
    ("CS:GO", "Counter-Strike Global Offensive/csgo", ["pak01_dir.vpk"]),
    ("TF2", "Team Fortress 2/tf", ["tf2_misc_dir.vpk", "tf2_textures_dir.vpk"]),
    ("Portal 2", "Portal 2/portal2", ["pak01_dir.vpk"]),
    ("Portal", "Portal/portal", ["portal_pak_dir.vpk"]),
    ("HL2", "Half-Life 2/hl2", ["hl2_misc_dir.vpk", "hl2_textures_dir.vpk", "hl2_pak_dir.vpk"]),
    ("HL2", "Momentum Mod Playtest/mount", ["hl2_dir.vpk"]),
]
ORDER = []
for _g in GAMES:
    if _g[0] not in ORDER:
        ORDER.append(_g[0])
ROOTS = ("materials", "models")


def vpk_dirs(path):
    """Every directory in a _dir.vpk that holds a file, lower case, '/' separated."""
    with open(path, "rb") as f:
        data = f.read()
    sig, ver, treesize = struct.unpack_from("<III", data, 0)
    if sig != 0x55AA1234:
        raise ValueError("%s is not a VPK" % path)
    pos = 12 + (16 if ver == 2 else 0)
    end = pos + treesize

    def cstr():
        nonlocal pos
        e = data.index(b"\0", pos)
        s = data[pos:e].decode("latin-1")
        pos = e + 1
        return s

    out = set()
    while pos < end:
        ext = cstr()
        if not ext:
            break
        while True:
            d = cstr()
            if not d:
                break
            while True:
                n = cstr()
                if not n:
                    break
                preload = struct.unpack_from("<H", data, pos + 4)[0]
                pos += 18 + preload
                if d != " ":
                    out.add(d.replace("\\", "/").strip("/").lower())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steam", default=os.path.expanduser("~/.local/share/Steam/steamapps/common"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                  "ftesurf", "scripts", "assetgames.txt"))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    owners = {}     #directory -> set of labels with a file anywhere under it
    read = []
    for label, folder, packs in GAMES:
        for pack in packs:
            p = os.path.join(a.steam, folder, pack)
            if not os.path.isfile(p):
                continue
            read.append("%s=%s/%s" % (label, folder, pack))
            for d in vpk_dirs(p):
                parts = d.split("/")
                if parts[0] not in ROOTS:
                    continue
                for i in range(1, len(parts) + 1):
                    owners.setdefault("/".join(parts[:i]), set()).add(label)
    if not owners:
        sys.exit("no game packs found under %s" % a.steam)

    def label(s):
        return ",".join(g for g in ORDER if g in s)

    lines = []
    for d in sorted(owners):
        parent = d.rsplit("/", 1)[0] if "/" in d else None
        if parent is None or owners[parent] != owners[d]:
            lines.append("%s %s" % (d, label(owners[d])))
    text = ("// FTESURF-ASSETGAMES 1 -- tools/assetgames.py (Patch 1625). <directory> <games>; longest prefix wins.\n"
            "// read: %s\n" % " ".join(read)) + "\n".join(lines) + "\n"
    print("%d directories, %d lines, %d bytes" % (len(owners), len(lines), len(text)))
    if not a.dry:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("wrote", a.out)


if __name__ == "__main__":
    main()
