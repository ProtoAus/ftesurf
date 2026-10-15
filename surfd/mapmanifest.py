"""Shared map-list grammar and reversible pool policy. No BSP/zone deletion.

Pool entries are per BUILD, not per display group. Defaults admit surf maps
and bhop maps with a zone file; explicit admin disables still take precedence.
The catalogue's explicit `of` links are separate from zone compatibility.
"""
import re

DDL = ("CREATE TABLE IF NOT EXISTS map_pool ("
       "map TEXT PRIMARY KEY, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),"
       "updated INTEGER NOT NULL)")
NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
MAX_LIST = 1000000


def read_list(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read(MAX_LIST + 1)
    if len(text) > MAX_LIST or not text.startswith("FTESURF-MAPDL 1\n"):
        raise ValueError("map list unavailable or too large")
    rows = []
    seen = set()
    for line in text.splitlines():
        a = line.split()
        if not a or a[0] != "dl":
            continue
        if (len(a) < 10 or not NAME.fullmatch(a[1].lower())
                or a[2] not in ("surf", "bhop") or a[3] not in ("k", "m", "km", "-")
                or not all(re.fullmatch(r"[0-9]{1,8}", a[i]) for i in (4, 5, 7, 8, 9))):
            raise ValueError("invalid map list row")
        name = a[1].lower()
        if name in seen:
            raise ValueError("duplicate map list row")
        seen.add(name)
        base = a[10].lower() if len(a) > 10 and a[10] != "-" else ""
        if base and not NAME.fullmatch(base):
            raise ValueError("invalid map link")
        rows.append(dict(map=name, disp=a[1], mode=a[2], src=a[3], tier=int(a[4]),
                         kb=int(a[5]), first=a[6], new=int(a[7]), mt=int(a[8]),
                         kt=int(a[9]), of=base, line=" ".join(a[:10])))
    if not rows:
        raise ValueError("empty map list")
    return rows


def pool_policy(name, zone_files):
    """Empty if eligible, otherwise the automatic disable explanation."""
    if name.startswith("surf_"):
        return ""
    if name.startswith("bhop_"):
        return "" if name in zone_files else "Bhop map has no zone file"
    return "Not a surf or zoned bhop map"


def disabled(db, names=(), zone_files=frozenset()):
    off = {r[0] for r in db.execute("SELECT map FROM map_pool WHERE enabled=0")}
    return off | {name for name in names if pool_policy(name, zone_files)}


def manifest(path, db, bsp, zoned, zone_files):
    """One row per held build, with the menu's independent tiers and links."""
    try:
        rows = read_list(path)
    except FileNotFoundError:
        rows = []
    byname = {r["map"]: r for r in rows}
    for name in sorted(bsp):
        if name not in byname:
            byname[name] = dict(map=name, disp=bsp[name], mode=name.split("_")[0],
                                src="-", tier=0, mt=0, kt=0, kb=0, first="", new=0, of="")
    off = disabled(db, bsp, zone_files)
    out = []
    for name, row in sorted(byname.items()):
        if name not in bsp:
            continue
        out.append(dict(row, enabled=name not in off, zoned=name in zoned,
                        policy=pool_policy(name, zone_files)))
        out[-1].pop("line", None)
    return out


def game_list(path, db, bsp, zoned, zone_files):
    """Append optional of / zones / enabled columns, keeping old clients valid.

    Disabled rows MUST stay in this list: omission cannot disable a mounted BSP.
    Older clients ignore the extension but /api/join still enforces the pool.
    """
    rows = read_list(path)
    off = disabled(db, (r["map"] for r in rows), zone_files)
    return ("FTESURF-MAPDL 1\n# of zoned enabled: pool state is per build\n" +
            "".join("%s %s %d %d\n" % (r["line"], r["of"] or "-",
                                       r["map"] in zoned, r["map"] not in off)
                    for r in rows))
