"""P1595 follow-up: put maps an admin disabled back in the pool (the inverse of tools/p1112_disable.py).
usage: python3.11 -I p1595_enable.py <backup json> <map> [<map> ...] [--apply]
The same UPSERT admin.py's /api/maps runs, enabled=1; the backup holds every map_pool row before it.
ahop_coast, ahop_rainbow, ahop_trick_or_treat and agtricks were disabled together on 15 Oct 09:53Z (no
record says by whom or why); with P1595 the pool rule would admit the zoned ones, the explicit row did not."""
import json
import os
import sqlite3
import sys
import time

args = [a for a in sys.argv[1:] if a != "--apply"]
apply = "--apply" in sys.argv[1:]
backup, want = args[0], [n.strip().lower() for n in args[1:] if n.strip()]
DB = "/srv/nvme/surfd/data/surfd.db"
MAPS = "/srv/nvme/ftesurf-server/game/momentum/maps"
lib = {e[:-4].lower() for e in os.listdir(MAPS) if e.lower().endswith(".bsp")}
missing = [n for n in want if n not in lib]
db = sqlite3.connect(DB, timeout=30)
rows = db.execute("SELECT map, enabled, updated FROM map_pool").fetchall()
before = {m: e for m, e, _ in rows}
print("map_pool %d rows; wanted %s: %s; not in the library %s"
      % (len(rows), want, [(n, before.get(n, "none")) for n in want], missing))
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
                       " updated=excluded.updated", (n, 1, now))
after = {m: e for m, e in db.execute("SELECT map, enabled FROM map_pool")}
print("after: %s" % [(n, after.get(n)) for n in want])
