#!/usr/bin/env python3
"""A local surfd for the Story screen's rig (Patch 854): the real story.txt, made-up players.

  python tools/story_fixture.py --home <owned scratch dir> [--port 18854]
      [--mapdl C:/FTESurf/ftesurf/data/mapdl.net.txt] [--story surfd/story.txt]

Serves this checkout's surfd on 127.0.0.1 with an isolated database, seeds six
players (one unlinked) with medals drawn from the list's own times, prints each
one's handle, and runs until killed.  The map library is patched from the
menu's copy of the Pi's list (read only): its zoned column says which levels
are timed.  Point a rig's `lobby_dir` at it, quoted (a cfg cuts at `//`).
"""
import argparse
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--home", type=Path, required=True)
ap.add_argument("--port", type=int, default=18854)
ap.add_argument("--mapdl", type=Path, default=Path("C:/FTESurf/ftesurf/data/mapdl.net.txt"))
ap.add_argument("--story", type=Path, default=ROOT / "surfd" / "story.txt")
a = ap.parse_args()

a.home.mkdir(parents=True, exist_ok=True)
(a.home / "surfd.env").write_text("SURFD_KEY=fixture\n")
os.environ.update(SURFD_HOME=str(a.home), SURFD_DB=str(a.home / "fixture.db"),
                  SURFD_ENV=str(a.home / "surfd.env"), SURFD_STORY=str(a.story.resolve()),
                  SURFD_TOOLS=str(ROOT / "tools"))
sys.path[:0] = [str(ROOT / "surfd"), str(ROOT / "tools")]
import surfd as S  # noqa: E402

zoned = set()
for ln in a.mapdl.read_text(errors="replace").splitlines():
    w = ln.split()
    if len(w) == 13 and w[0] == "dl" and w[11] == "1":
        zoned.add(w[1].lower())
S.map_index = lambda now=None: ({m: m for m in zoned}, zoned)
S.avatars = lambda now, db=None: {"game": {}, "who": {}, "site": {}, "handle": {}, "at": now}

lists, problems = S.story_parse(a.story.read_text(encoding="utf-8"))
assert not problems, problems
story = [lv for c in lists[0]["chapters"] for lv in c["levels"]]
events = [lv for c in lists[1]["chapters"] for lv in c["levels"]] if len(lists) > 1 else []

db = S.connect()
for t in ("runs", "accounts", "keylinks"):
    db.execute("DELETE FROM " + t)
now = 1792440000
# (name, steamid or guid, levels played, skill 0..1)
PLAYERS = [("Lex", "76561198000000101", 14, 0.55), ("lowgrav", "76561198000000102", 60, 0.9),
           ("rampwalker", "76561198000000103", 40, 0.75), ("edgebug", "76561198000000104", 26, 0.6),
           ("tealwave", "76561198000000105", 12, 0.4), ("Stranger (unlinked)", "f" * 32, 7, 0.5)]
rng = random.Random(854)


def row(mapname, track, leg, player, name, ms, tier):
    db.execute("INSERT OR REPLACE INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,"
               "flags,node,runid,submitted) VALUES(?,?,?,?,'clean',?,?,?,66.667,?,0,'fx','r',?)",
               (mapname, track, leg, tier, player, name, ms // 15, ms, now))


for name, pid, reach, skill in PLAYERS:
    linked = pid.isdigit()
    if linked:
        db.execute("INSERT INTO accounts(steamid,name,created_at) VALUES(?,?,?)", (pid, name, now))
    tier = "ranked" if linked else "community"
    played = 0
    for lv in story:
        if played >= reach:
            break
        if not lv["map"] or lv["map"] not in zoned:
            continue
        played += 1
        if rng.random() < 0.15:
            continue
        times = sorted(c["v"] for c in lv["ch"] if c["k"] == "time")
        q = skill + rng.uniform(-0.3, 0.3)
        if len(times) == 2:
            ms = times[0] - 400 if q > 0.65 else times[1] - 400 if q > 0.4 else times[1] + 9000
        else:
            ms = 95000 + rng.randrange(60000)
        row(lv["map"], lv["track"], 0, pid, name, ms, tier)
        if lv["map"] == "surf_colin_blaster_69000" and lv["track"] == 0:
            row(lv["map"], 0, 8, pid, name, 12000, tier)
    for lv in events[:6]:
        if lv["map"] in zoned and rng.random() < skill:
            row(lv["map"], lv["track"], 0, pid, name, 55500, tier)
db.commit()
for name, pid, _, _ in PLAYERS:
    print("%-20s %s" % (name, S.web_handle(pid)), flush=True)
S.app.run(host="127.0.0.1", port=a.port, threaded=True, use_reloader=False)
