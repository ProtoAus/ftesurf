"""P1112: take the strays (maps in no Momentum category and not KSF's) out of the pool.
usage: python3.11 -I p1112_disable.py <names file> <backup json> [--apply]
The same UPSERT admin.py's /api/maps runs; reversible (enabled=1, or delete the rows)."""
import json
import os
import sqlite3
import sys
import time

names_file, backup, apply = sys.argv[1], sys.argv[2], sys.argv[3:] == ["--apply"]
DB = "/srv/nvme/surfd/data/surfd.db"
MAPS = "/srv/nvme/ftesurf-server/game/momentum/maps"
lib = {e[:-4].lower() for e in os.listdir(MAPS) if e.lower().endswith(".bsp")}
want = [n.strip().lower() for n in open(names_file) if n.strip()]
missing = [n for n in want if n not in lib]
print("names %d, in the library %d, missing %s" % (len(want), len(want) - len(missing), missing))
db = sqlite3.connect(DB, timeout=30)
rows = db.execute("SELECT map, enabled, updated FROM map_pool").fetchall()
print("map_pool before: %d rows" % len(rows))
if not apply:
    print("dry run: nothing written")
    sys.exit(0)
fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump({"at": int(time.time()), "rows": rows}, f)
now = int(time.time())
with db:
    for n in want:
        if n in lib:
            db.execute("INSERT INTO map_pool(map,enabled,updated) VALUES(?,?,?)"
                       " ON CONFLICT(map) DO UPDATE SET enabled=excluded.enabled,"
                       " updated=excluded.updated", (n, 0, now))
off = {r[0] for r in db.execute("SELECT map FROM map_pool WHERE enabled=0")}
print("map_pool after: %d disabled; all %d wanted are off: %s"
      % (len(off), len(want) - len(missing), all(n in off for n in want if n in lib)))
