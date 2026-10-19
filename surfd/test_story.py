#!/usr/bin/env python3
"""Patch 854: the Story list's grammar and the medals worked out from WOS rows.

Real Flask routes on an isolated database; the map library is patched, no HTTP."""
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

HOME = Path(tempfile.mkdtemp(prefix="surfd-story-"))
(HOME / "surfd.env").write_text("SURFD_KEY=testkey\n")
os.environ.update(SURFD_HOME=str(HOME), SURFD_DB=str(HOME / "test.db"),
                  SURFD_ENV=str(HOME / "surfd.env"),
                  SURFD_STORY=str(HOME / "story.txt"),
                  SURFD_TOOLS=str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import ed25519
import surfd as S
import social as F

A, B, C = "76561198000000001", "76561198000000002", "76561198000000003"
G1, G2, G3 = "a" * 32, "b" * 32, "c" * 32
PUB = [ed25519.publickey(bytes([i]) * 32).hex() for i in (1, 2, 3, 4)]

STORY = """// a header comment
list story "Story"
unlock 60%
chapter "First waves"
level surf_one
  bronze reach 3        "Get to the last stage"
  silver finish         "Complete the map"
  gold   nofail
level surf_two
  bronze finish
  silver time 1:05
  gold   time 1:01.5
level soon
level surf_dark                 // no zones: never counted toward a bar
chapter "Second"  unlock 4
level surf_two bonus 2
level surf_three
list events "Events"
chapter
level surf_three
  gold time 0:30 "Beat it fast"
level surf_one
  bronze dance 3
  silver time 9:99
  gold wonly
"""


def handle(x):
    return hashlib.sha256(x.encode()).hexdigest()[:S.WEB_HANDLE_LEN]


class Story(unittest.TestCase):
    def setUp(self):
        self.now = 1800000000
        self.clock = patch.object(S.time, "time", lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.maps = patch.object(S, "map_index", lambda now=None: (
            {m: m for m in ("surf_one", "surf_two", "surf_three", "surf_dark")},
            {"surf_one", "surf_two", "surf_three"}))
        self.maps.start()
        self.addCleanup(self.maps.stop)
        S._rate.clear()
        S._story.update(stat=None, conf=None, at=None, rev="", calc=None, calc_rev="", busy=False)
        (HOME / "story.txt").write_text(STORY)
        self.client = S.app.test_client()
        self.db = S.connect()
        self.addCleanup(self.db.close)
        for t in ("runs", "replays", "reviews", "accounts", "keylinks", "pubkeys", "receipts"):
            self.db.execute("DELETE FROM " + t)
        for sid, name, ban in ((A, "Alice", 0), (B, "Bob", 0), (C, "Carl", 1)):
            self.db.execute("INSERT INTO accounts(steamid,name,created_at,banned_at) VALUES(?,?,?,?)",
                            (sid, name, self.now, ban))
        # G1 played unlinked, signing with its key PUB[1], later linked to Bob: the
        # runs PUB[1] signed are Bob's.  G2 is a stranger whose key PUB[2] is
        # linked to nobody.
        self.receipt("r-g1", PUB[1], G1, 100)
        self.receipt("r-g2", PUB[2], G2, 100)
        self.db.execute("INSERT INTO keylinks(pub,steamid,player,linked_at) VALUES(?,?,?,?)",
                        (PUB[1], B, G1, self.now))
        self.db.commit()

    def receipt(self, runid, pub, player, at):
        self.db.execute(
            "INSERT INTO replays(map,map_dir,track,leg,leaf,tier,style,player,name,ticks,tickrate,"
            "millis,flags,node,submitted,runid,kind) VALUES('surf_x','d',0,0,?,'community','clean',"
            "?,'n',1,66.667,1,0,'n',?,?,'run')", (runid + ".rec", player, at, runid))
        self.db.execute("INSERT INTO receipts(runid,pub,verdict,at,sig,signed_at) VALUES(?,?,'OK',?,1,?)",
                        (runid, pub, at, at))
        self.db.execute("INSERT OR IGNORE INTO pubkeys(pub,player,first_at,last_at) VALUES(?,?,?,?)",
                        (pub, player, at, at))
        self.db.commit()

    def run_row(self, mapname, player, ms, tier="ranked", style="clean", leg=0, track=0,
                name="n", replay=0, runid=""):
        self.db.execute(
            "INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,"
            "node,runid,submitted,replay_id) VALUES(?,?,?,?,?,?,?,?,?,?,0,'n',?,?,?)",
            (mapname, track, leg, tier, style, player, name, ms // 15, 66.667, ms, runid,
             self.now, replay))
        self.db.commit()

    def get(self, **q):
        r = self.client.get("/api/board", query_string=q)
        return r.status_code, r.get_json()

    def mine(self, who, lid="story"):
        code, body = self.get(story="player", who=handle(who))
        self.assertEqual(code, 200, body)
        L = next(L for L in body["lists"] if L["id"] == lid)
        return L["t"], L["open"], {i: (p, ms) for i, p, ms in L["lv"]}

    def players(self):
        return [(p["name"], p["t"]) for p in self.get(story="players", list="story")[1]["players"]]

    def ask_who(self, i):
        data = self.client.get("/api/social/menu/challenge?op=list&who=-").get_json()
        form = {k: data[k] for k in ("nonce", "expires", "ticket")}
        form.update(op="list", who="-", pub=PUB[i], story="1")
        form["sig"] = ed25519.sign(bytes([i + 1]) * 32, (F.MENU_STATEMENT % (
            form["nonce"], "list", "-")).encode()).hex()
        return self.client.post("/api/social/menu", data=form).get_json()

    def test_parse_grammar_and_problems(self):
        lists, problems = S.story_parse(STORY)
        self.assertEqual([L["id"] for L in lists], ["story", "events"])
        story = lists[0]
        self.assertEqual(story["pct"], 60)
        self.assertEqual([c["title"] for c in story["chapters"]], ["First waves", "Second"])
        self.assertEqual(story["chapters"][1]["unlock"], 4)
        lv = story["chapters"][0]["levels"]
        self.assertEqual([x["map"] for x in lv], ["surf_one", "surf_two", "", "surf_dark"])
        self.assertEqual([(c["m"], c["k"], c.get("v"), c["t"]) for c in lv[1]["ch"]],
                         [("b", "finish", None, "Complete the map"), ("s", "time", 65000, "Sub 1:05"),
                          ("g", "time", 61500, "Sub 1:01.5")])
        self.assertEqual(lv[0]["ch"][0]["t"], "Get to the last stage")
        self.assertEqual(lv[0]["ch"][2]["t"], "First try every stage")
        self.assertEqual(lv[3]["ch"], [{"m": "b", "k": "finish", "t": "Complete the map"}])
        self.assertEqual(story["chapters"][1]["levels"][0]["ch"][0]["t"], "Finish bonus 2")
        ev = lists[1]["chapters"][0]["levels"]
        self.assertEqual(ev[0]["ch"], [{"m": "g", "k": "time", "v": 30000, "t": "Beat it fast"}])
        # "dance" and 9:99 are refused and reported by line; the level keeps its gold.
        self.assertEqual([p[:8] for p in problems], ["line 23:", "line 24:"])
        self.assertEqual([c["k"] for c in ev[1]["ch"]], ["wonly"])

    def test_bad_lines_never_raise(self):
        lists, problems = S.story_parse('level x\nlist 9bad\nlist ok "T"\nchapter "a\n'
                                        'level ../etc\nlevel surf_a bonus\ngold time\n'
                                        'chapter "x" unlock ³\nlevel surf_b bonus ٣\n')
        self.assertEqual([L["id"] for L in lists], ["ok"])
        self.assertEqual(len(problems), 8, problems)

    def test_unlock_share_is_the_list_head_and_does_not_leak(self):
        lists, problems = S.story_parse('unlock 50%\nlist a "A"\nunlock 90%\nchapter "1"\n'
                                        'unlock 100%\nchapter "2" unlock 7\nlist b "B"\nchapter "x" unlock 3\n')
        self.assertEqual([(L["id"], L["pct"]) for L in lists], [("a", 90), ("b", 50)])
        self.assertEqual([p[:7] for p in problems], ["line 5:", "line 8:"], problems)
        self.assertEqual([c["unlock"] for c in lists[0]["chapters"]], [None, 7])
        self.assertEqual(lists[1]["chapters"][0]["unlock"], None)    # the first chapter is open

    def test_medals_from_wos_rows_only(self):
        self.run_row("surf_two", A, 61000)                       # under 1:01.5: gold
        self.run_row("surf_two", A, 50000, tier="momentum")      # imported: never counts
        self.run_row("surf_two", A, 40000, style="segmented")    # saves: never counts
        self.run_row("surf_one", A, 0, leg=2)                    # stage 2 done: reached stage 3
        t, opened, lv = self.mine(A)
        self.assertEqual(lv[1], (3, 61000))
        self.assertEqual(lv[0], (1, 0))
        self.assertEqual((t, opened), (4, 2))   # chapter 2's hand-set bar is 4
        _, body = self.get(story="list")
        story = body["lists"][0]
        # First chapter offers surf_one 2 (nofail is not live) + surf_two 3; surf_dark has no zones.
        self.assertEqual([c["bar"] for c in story["chapters"]], [0, 4])
        self.assertEqual(story["levels"][3]["timed"], 0)
        self.assertEqual(story["levels"][1]["hold"], [1, 1, 1])
        self.assertEqual([c["live"] for c in story["levels"][0]["ch"]], [1, 1, 0])

    def test_unlinked_rows_follow_their_own_key_and_strangers_stand_alone(self):
        self.run_row("surf_two", G1, 64000, tier="community", name="old guid name", runid="r-g1")
        self.run_row("surf_two", G2, 70000, tier="community", name="Stranger")
        self.run_row("surf_two", C, 30000)                       # banned account
        self.assertEqual(self.mine(B)[2][1], (2, 64000))
        self.assertEqual(self.players(), [("Bob", 2), ("Stranger", 1)])
        _, body = self.get(story="players", list="story")
        self.assertEqual(body["players"][1]["who"], handle(G2))
        self.assertNotIn(handle(C), [p["who"] for p in body["players"]])

    def test_a_link_naming_somebody_elses_guid_moves_nothing(self):
        # Round 1: a lobby files keylinks.player from the client's guid, so an
        # attacker links its own key "as" the stranger's guid.
        self.run_row("surf_two", G2, 61000, tier="community", name="Stranger", runid="r-g2")
        self.db.execute("INSERT INTO keylinks(pub,steamid,player,linked_at) VALUES(?,?,?,?)",
                        (PUB[0], A, G2, self.now))
        # ...and a banned throwaway does the same, to erase the stranger.
        self.db.execute("INSERT INTO keylinks(pub,steamid,player,linked_at) VALUES(?,?,?,?)",
                        (PUB[3], C, G2, self.now))
        # Round 2: it signs runs as that guid, even before the stranger's.  Its own
        # run counts for it; the banned key's run counts for nobody.
        self.receipt("r-spoof", PUB[0], G2, 50)
        self.receipt("r-ban", PUB[3], G2, 40)
        self.run_row("surf_one", G2, 90000, tier="community", name="Stranger", runid="r-spoof")
        self.run_row("surf_three", G2, 90000, tier="community", name="Stranger", runid="r-ban")
        self.db.commit()
        self.assertEqual(self.players(), [("Stranger", 3), ("Alice", 2)])
        self.assertEqual(self.mine(G2)[2], {1: (3, 61000)})
        self.assertEqual(self.ask_who(2)["who"], handle(G2))     # the stranger is still G2
        self.assertEqual(self.ask_who(0)["who"], handle(A))      # the attacker is only itself

    def test_unsigned_rows_stay_with_the_guid(self):
        self.run_row("surf_two", G1, 64000, tier="community", name="Bob old", runid="r-g1")
        self.run_row("surf_three", G1, 90000, tier="community", name="Bob old")    # no receipt
        self.receipt("r-nosig", PUB[1], G1, 300)                 # a signature that did not verify
        self.db.execute("UPDATE receipts SET sig = 0 WHERE runid = 'r-nosig'")
        self.run_row("surf_one", G1, 95000, tier="community", name="Bob old", runid="r-nosig")
        self.db.commit()
        self.assertEqual(sorted(self.players()), [("Bob", 2), ("Bob old", 3)])

    def test_rejected_run_earns_nothing(self):
        self.db.execute("INSERT INTO replays(id,map,map_dir,track,leg,leaf,tier,style,player,name,"
                        "ticks,tickrate,millis,flags,node,submitted) VALUES(7,'surf_two','d',0,0,"
                        "'x.rec','ranked','clean',?,'n',1,66.667,61000,0,'n',?)", (A, self.now - 5))
        self.db.execute("INSERT INTO reviews(replay_id,decision,at) VALUES(7,'reject',?)", (self.now,))
        self.run_row("surf_two", A, 61000, replay=7)
        _, body = self.get(story="player", who=handle(A))
        self.assertEqual(body["lists"][0]["lv"], [])

    def test_chapter_stays_shut_below_its_bar(self):
        self.run_row("surf_two", A, 61000)
        t, opened, _ = self.mine(A)
        self.assertEqual((t, opened), (3, 1))

    def test_events_are_their_own_ladder(self):
        self.run_row("surf_three", A, 29000)
        t, _, lv = self.mine(A, "events")
        self.assertEqual((t, lv[0]), (3, (3, 29000)))
        self.assertEqual(self.mine(A)[0], 1)            # the story's surf_three is a bronze

    def test_file_edits_apply_without_restart(self):
        self.run_row("surf_two", A, 63000)
        self.assertEqual(self.mine(A)[2][1][0], 2)
        (HOME / "story.txt").write_text(STORY.replace("silver time 1:05", "silver time 1:02"))
        os.utime(HOME / "story.txt", ns=(1, 1))         # a new stat, as any save makes
        self.assertEqual(self.mine(A)[2][1][0], 1)

    def test_stale_answer_is_served_while_a_thread_works_the_next(self):
        self.assertEqual(self.mine(A)[0], 0)
        self.run_row("surf_two", A, 61000)
        self.now += S.STORY_TTL + 1
        self.assertEqual(self.mine(A)[0], 0)            # the old answer, at once
        for t in threading.enumerate():
            if t.name == "story":
                t.join(10)
        self.assertEqual(self.mine(A)[0], 3)

    def test_names_never_publish_a_guid(self):
        self.run_row("surf_two", G2, 70000, tier="community", name=G2)
        self.assertEqual(self.players(), [("unnamed", 1)])

    def test_no_file_and_bad_asks(self):
        (HOME / "story.txt").unlink()
        self.assertEqual(self.get(story="list")[0], 404)
        (HOME / "story.txt").write_text(STORY)
        self.assertEqual(self.get(story="nope")[0], 400)
        self.assertEqual(self.get(story="player", who="xyz")[0], 400)
        self.assertEqual(self.get(story="players", list="nope")[0], 404)
        code, body = self.get(story="player", who="0" * 12)
        self.assertEqual((code, body["lists"][0]["t"], body["name"]), (200, 0, ""))

    def test_menu_proof_names_the_player(self):
        self.assertEqual(self.ask_who(1)["who"], handle(B))     # linked key: its account
        self.assertEqual(self.ask_who(2)["who"], handle(G2))    # unlinked key: its own guid
        self.assertEqual(self.ask_who(3), {"v": 1, "ok": 1, "who": "", "status": 200})
        bad = self.client.get("/api/social/menu/challenge?op=list&who=-").get_json()
        form = {k: bad[k] for k in ("nonce", "expires", "ticket")}
        form.update(op="list", who="-", pub=PUB[1], story="1", sig="00" * 64)
        self.assertEqual(self.client.post("/api/social/menu", data=form).get_json()["ok"], 0)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=1)
    finally:
        shutil.rmtree(HOME, ignore_errors=True)
