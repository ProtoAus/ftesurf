#!/usr/bin/env python3
"""Generate maps/tiers.txt: independent public MOM/KSF ratings by exact map/leg.

    python tools/maptiers.py --ksf-roster C:/FTESurf/ftesurf/data/ksf_roster.csv \
                             --maplist <FTESURF-MAPDL file, e.g. /api/board?maps=1>

Momentum's public MSML caches supply ranked/suggested MAIN, STAGE and BONUS
ratings (same gamemode/style selectors as mapmeta.py). Private testing and
disabled maps are excluded. No main tier is inherited by a stage, and no map
suffix is stripped. KSF's numeric main ratings come from maproster's roster,
then from the directory's map list (--maplist), whose KSF column rates each row
by its exact name -- the CS:S builds and maps KSF added after the roster, and
the catalogue's newer value where KSF re-tiered one.
The user's community bonus sheet uses LETTER tiers, not a numeric equivalent:
Unit and Strafe columns are retained separately, including split bonuses. Its
pending/to-add column has no actual tiers and is intentionally not imported.

Wire/file v1: tiers MAP v1;MAP;TRACK,LEG,MOM,SOURCE,KSF,UNIT,STRAFE;...
TRACK 0 = main, N = bonus N; LEG 0 = whole track, N = stage N.
'-' = unknown, SOURCE = rank/sugg/-. File is public metadata, never player data.
Server publishes only the current map's rows as short serverinfo values;
remote clients need no copy. The version/map marker rejects cross-map stale data.
Use --bonus-csv for an offline snapshot; network refresh fails closed.
"""
import argparse
import collections
import csv
import io
import pathlib
import re
import urllib.request
import uuid

import mapmeta

ROOT = pathlib.Path(__file__).resolve().parent.parent
BONUS_SHEET = ("https://docs.google.com/spreadsheets/d/"
               "1Hft-1XdK7lge5WWqP5hrNsSUJw_Ss2PS-t-c3CTawpQ/export?format=csv")
NAME = re.compile(r"[a-z0-9_\-]+", re.ASCII)
BONUS = re.compile(r"([a-z0-9_\-]+)\s+b([1-9][0-9]*)(?:\s+\([12]/2\))?", re.ASCII)
LETTERS = frozenset(("?", "Y", "X", "S", "A", "B", "C", "D", "F", "G"))
MAX_PAYLOAD = 2047


def tier(value):
    return value if type(value) is int and 1 <= value <= 10 else None


def slot(table, name, track=0, leg=0):
    if not NAME.fullmatch(name):
        raise ValueError("unsafe map name: %r" % name)
    return table.setdefault((name, track, leg), ["-", "-", "-", "-", "-"])


def momentum(table, maps):
    for m in maps:
        if m.get("status") not in (mapmeta.ST_APPROVED, mapmeta.ST_PUBLIC_TESTING,
                                   mapmeta.ST_CONTENT_APPROVAL, mapmeta.ST_FINAL_APPROVAL):
            continue
        name = m["name"].lower()
        lbs = m.get("leaderboards") or []
        gm = mapmeta.pick_gamemode(m, lbs, name)
        if m["status"] in mapmeta.IN_SUBMISSION:
            source = "sugg"
            candidates = [r for r in mapmeta.suggestions(m) if r.get("gamemode") == gm]
        else:
            source = "rank"
            # Select one canonical style, as mapmeta does. Never mix a sideways
            # bonus or another gamemode into the map's normal ratings.
            style = next((s for s in mapmeta.STYLE_MAIN
                          if any(tier(r.get("tier")) for r in mapmeta.main_rows(lbs, s, gm))),
                         mapmeta.ST_NORMAL)
            candidates = [r for r in lbs if r.get("gamemode") == gm and r.get("style") == style]
        seen = {}
        for r in candidates:
            value = tier(r.get("tier"))
            kind, num = r.get("trackType"), r.get("trackNum")
            if value is None or type(num) is not int or not 1 <= num <= 99:
                continue
            if kind == 0 and num == 1:
                track, leg = 0, 0
            elif kind == 1:
                track, leg = 0, num
            elif kind == 2:
                track, leg = num, 0
            else:
                continue
            key = (track, leg)
            if key in seen and seen[key] != value:
                raise ValueError("conflicting MOM tiers: %s %s" % (name, key))
            seen[key] = value
            row = slot(table, name, track, leg)
            rating = [str(value), source]
            if row[:2] not in (["-", "-"], rating):
                raise ValueError("conflicting MOM cache entries: %s %s" % (name, key))
            row[:2] = rating


def ksf_main(table, text):
    rows = csv.DictReader(io.StringIO(text))
    fields = set(rows.fieldnames or [])
    namefield = "Map name" if "Map name" in fields else "Map"
    if not {namefield, "Tier"} <= fields:
        raise ValueError("KSF roster lacks Map name/Tier headers")
    for r in rows:
        name = r[namefield].strip().lower()
        value = r["Tier"].strip()
        if name.startswith("surf_") and value.isdigit() and tier(int(value)):
            row = slot(table, name)
            if row[2] not in ("-", value):
                raise ValueError("conflicting KSF main tier: " + name)
            row[2] = value


def ksf_maplist(table, text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "FTESURF-MAPDL 1":
        raise ValueError("map list is not FTESURF-MAPDL 1")
    filled, moved = [], []
    for line in lines[1:]:
        f = line.split()
        # dl name type src dltier kb date - mom ksf ...; column 9 is KSF's tier
        if len(f) < 10 or f[0] != "dl" or not f[9].isdigit() or not tier(int(f[9])):
            continue
        name = f[1].lower()
        if not NAME.fullmatch(name):
            continue
        row = slot(table, name)
        if row[2] == "-":
            filled.append(name)
        elif row[2] != f[9]:
            moved.append("%s %s->%s" % (name, row[2], f[9]))
        row[2] = f[9]
    return filled, moved


def ksf_bonus(table, text):
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or rows[0][3:4] != ["Unit Bonuses"] or rows[0][7:8] != ["Strafe Bonuses"]:
        raise ValueError("bonus sheet layout changed (Unit/Strafe columns)")
    counts = collections.Counter()
    # Notes on the left share rows with the first real ratings on the right.
    # Only the column-header row is skippable.
    for r in rows[1:]:
        for col, field in ((3, 3), (7, 4)):
            if len(r) <= col + 1:
                continue
            label, value = r[col].strip().lower(), r[col + 1].strip()
            if not label and not value:
                continue
            if label == "bonus" and value == "Tier":
                continue
            match = BONUS.fullmatch(label)
            letter = value.removesuffix(" Tier")
            if not match or not value.endswith(" Tier") or letter not in LETTERS:
                raise ValueError("unrecognised rated bonus: %r / %r" % (label, value))
            name, num = match[1], int(match[2])
            if num > 99:
                raise ValueError("bonus number out of range: " + label)
            if not name.startswith("surf_"):
                name = "surf_" + name
            row = slot(table, name, num)
            if row[field] not in ("-", letter):
                raise ValueError("conflicting KSF bonus tier: " + label)
            row[field] = letter
            counts[field] += 1
    if not counts:
        raise ValueError("no rated bonuses in sheet")
    return counts


def render(table):
    grouped = collections.defaultdict(list)
    for (name, track, leg), values in sorted(table.items()):
        if values != ["-"] * 5:
            grouped[name].append(",".join([str(track), str(leg), *values]))
    lines = ["// Generated by tools/maptiers.py; public exact-map ratings, not numeric conversions.",
             "// MOM suggestions marked sugg; KSF numeric main roster; community bonus letters Unit/Strafe.",
             "// Bonus source: " + BONUS_SHEET,
             "// v1;map;track,leg,mom,source,ksf,unit,strafe;... (- means unknown)"]
    for name, rows in sorted(grouped.items()):
        prefix = "v1;" + name + ";"
        if len(prefix) >= 64 or any(len(r) >= 64 for r in rows):
            raise ValueError("rating exceeds short serverinfo value limit: " + name)
        payload = prefix + ";".join(rows) + ";"
        if len(payload) > MAX_PAYLOAD:
            raise ValueError("serverinfo payload too long: %s (%d)" % (name, len(payload)))
        lines.append('tiers %s "%s"' % (name, payload))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--momentum", type=pathlib.Path, default=pathlib.Path(mapmeta.MOMENTUM))
    ap.add_argument("--ksf-roster", type=pathlib.Path, required=True)
    ap.add_argument("--maplist", type=pathlib.Path, required=True)
    ap.add_argument("--bonus-csv", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "ftesurf/maps/tiers.txt")
    a = ap.parse_args()
    table = {}
    files = [max(paths, key=lambda p: (p.stat().st_mtime_ns, p.name))
             for kind in ("approved", "submission")
             if (paths := list((a.momentum / "_cache").glob(kind + "_*.dat")))]
    if not files:
        raise SystemExit("No Momentum public map caches; output unchanged")
    for path in files:
        momentum(table, mapmeta.read_msml(path))
    ksf_main(table, a.ksf_roster.read_text(encoding="utf-8-sig"))
    filled, moved = ksf_maplist(table, a.maplist.read_text(encoding="utf-8-sig"))
    print("map list: %d KSF main tiers filled, %d re-tiered: %s" %
          (len(filled), len(moved), ", ".join(moved) or "none"))
    if a.bonus_csv:
        text = a.bonus_csv.read_text(encoding="utf-8-sig")
    else:
        req = urllib.request.Request(BONUS_SHEET, headers={"User-Agent": "FTESurf-maptiers/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read(2**20 + 1)
        if len(data) > 2**20:
            raise ValueError("bonus sheet exceeds 1 MiB; output unchanged")
        text = data.decode("utf-8-sig")
    counts = ksf_bonus(table, text)
    output = render(table)  # validate everything before replacing the old catalogue
    a.out.parent.mkdir(parents=True, exist_ok=True)
    pending = a.out.with_name(a.out.name + ".new-" + uuid.uuid4().hex)
    try:
        pending.write_text(output, encoding="utf-8", newline="\n")
        pending.replace(a.out)
    finally:
        pending.unlink(missing_ok=True)
    print("%d rated maps, %d rated legs; bonus sheet Unit %d / Strafe %d -> %s" %
          (len({k[0] for k in table}), len(table), counts[3], counts[4], a.out))


if __name__ == "__main__":
    main()
