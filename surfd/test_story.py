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
        S._story.update(stat=None, conf=None, at=None, rev="", calc=None, calc_rev="", busy=False,
                        again=False, seq=0, recent={})
        (HOME / "story.txt").write_text(STORY)
        self.client = S.app.test_client()
        self.db = S.connect()
        self.addCleanup(self.db.close)
        for t in ("runs", "replays", "reviews", "accounts", "keylinks", "pubkeys", "receipts",
                  "story_runs", "story_tracks", "runpins"):
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
        # Chapter 2's bar is set by hand; surf_dark has no zones.
        self.assertEqual([c["bar"] for c in story["chapters"]], [0, 4])
        self.assertEqual(story["levels"][3]["timed"], 0)
        self.assertEqual(story["levels"][1]["hold"], [1, 1, 1])
        self.assertEqual([c["live"] for c in story["levels"][0]["ch"]], [1, 1, 1])   # P856: nofail

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


# Patch 856: challenges about one run, dates, places and the finish's answer.
# self.now is 2027-01-15 08:00 UTC.
STORY2 = """list story "Story"
chapter "One"
level surf_two
  bronze finish
  silver nofail
  gold   wonly
level surf_one
  bronze nojump
  silver speed 3000
  gold   via ramp
  spot ramp 100 200 300 64
level surf_three
  bronze stage 2 0:10
  silver rank 2
  gold   first
level surf_two bonus 1
  gold improve 10%
chapter "Two" unlock 3
level surf_dark
list events "Events"
dates 2027-01-10 2027-01-20
chapter
level surf_three
  gold time 0:30
level surf_one
  dates 2026-12-01 2026-12-31
  gold finish
"""


class Story2(Story):
    def setUp(self):
        super().setUp()
        (HOME / "story.txt").write_text(STORY2)

    def post(self, mapname, guid, ms, pub=None, src="127.0.0.1", track=0, runid=None, leg=0,
             **facts):
        form = {"key": "testkey", "map": mapname, "track": str(track), "leg": str(leg),
                "player": guid,
                "name": "Proto", "ticks": str(ms // 10), "tickrate": "100", "flags": "0",
                "node": "p27510", "runid": runid or "r%d-%s-%d" % (ms, guid[:3], track)}
        if pub:
            form["pub"] = pub
        form.update({k: str(v) for k, v in facts.items()})
        r = self.client.post("/api/run", data=form, environ_base={"REMOTE_ADDR": src})
        self.assertEqual(r.status_code, 200, r.get_data(True))
        return [(e["m"], e["n"], e["t"], e["tot"], e["ch"]) for e in r.get_json().get("story", [])]

    def srun(self, mapname, player, ms, at=None, track=0, prevms=0, fails=-1, inmask=-1, top=-1,
             spots="", runid="", pub="", leg=0, replay_id=0):
        self.db.execute("INSERT INTO story_runs(map,track,leg,player,pub,name,millis,prevms,at,runid,"
                        "replay_id,fails,inmask,top,spots) VALUES(?,?,?,?,?,'n',?,?,?,?,?,?,?,?,?)",
                        (mapname, track, leg, player, pub, ms, prevms,
                         self.now if at is None else at, runid, replay_id, fails, inmask, top, spots))
        self.db.commit()

    def settle(self):
        """Work the ladder out again and wait for the thread."""
        self.now += S.STORY_TTL + 1
        self.get(story="list")
        for _ in range(200):
            if not S._story["busy"]:
                break
            threading.Event().wait(0.05)

    def test_grammar(self):
        lists, problems = S.story_parse(STORY2)
        self.assertEqual(problems, [])
        lv = [x for c in lists[0]["chapters"] for x in c["levels"]]
        self.assertEqual([(c["k"], c.get("v"), c.get("w")) for x in lv for c in x["ch"]], [
            ("finish", None, None), ("nofail", None, None), ("wonly", None, None),
            ("nojump", None, None), ("speed", 3000, None), ("via", "ramp", None),
            ("stage", 2, 10000), ("rank", 2, None), ("first", None, None),
            ("improve", 10, None), ("finish", None, None)])
        self.assertEqual(lv[1]["spots"], {"ramp": (100.0, 200.0, 300.0, 64.0)})
        self.assertEqual([x["t"] for x in lv[2]["ch"]],
                         ["Stage 2 under 0:10", "Top 2 on the WOS board", "Be the first to finish"])
        ev = [x for c in lists[1]["chapters"] for x in c["levels"]]
        self.assertEqual(ev[0]["win"], (1799539200, 1800489600))     # 10 Jan 00:00 to 21 Jan 00:00
        self.assertEqual(ev[1]["win"], (1796083200, 1798761600))     # its own December
        self.assertEqual(lv[0]["win"], None)
        lists, problems = S.story_parse(
            'list a "A"\nchapter\nspot x 1 2 3\nlevel surf_a\n  spot y 1 2\n  spot z 1 2 3 9000\n'
            '  dates 2027-01-05 2027-01-01\n  gold improve 0%\n  silver via Bad-Name\n'
            '  bronze via other\nchapter\ndates 2027-01-01 2027-01-02\n')
        self.assertEqual([p[:8] for p in problems],
                         ["line 3: ", "line 5: ", "line 6: ", "line 7: ", "line 8: ", "line 9: ",
                          "line 12:"], problems)
        self.assertEqual(S.story_unspotted(lists), [("a", "surf_a", "other")])

    def test_a_finish_answers_the_medal_it_earned(self):
        # A cold process logs the first finish untold and works the ladder out
        # on a thread: the run's answer never waits on a pass.
        self.assertEqual(self.post("surf_two", G3, 92000, sfails=1, smask=5), [])
        self.settle()
        self.db.execute("DELETE FROM story_runs")
        self.db.execute("DELETE FROM runs")
        self.db.commit()
        self.settle()
        # Unlinked, no key: a community run of the install's guid.
        self.assertEqual(self.post("surf_two", G3, 90000, sfails=1, smask=1 | 4, stop=900),
                         [("b", 1, "Complete the map", 1, "")])
        self.assertEqual(self.post("surf_two", G3, 95000, sfails=0, smask=1 | 4, stop=900),
                         [("s", 1, "First try every stage", 2, "")])
        self.assertEqual(self.post("surf_two", G3, 99000, sfails=0, smask=1 | 16 | 32, stop=900),
                         [("g", 1, "W only", 3, "Two")])                  # 3 opens chapter Two
        self.assertEqual(self.post("surf_two", G3, 98000, sfails=0, smask=1), [])  # held already
        self.assertEqual(self.post("surf_two", G3, 98000, sfails=0, smask=1), [])  # the same post
        self.settle()                    # the ladder agrees once it is worked out again
        t, opened, lv = self.mine(G3)
        self.assertEqual((t, opened, lv[0]), (3, 2, (3, 90000)))
        self.assertEqual(S._story["recent"], {})
        rows = self.db.execute("SELECT player, fails, inmask, top FROM story_runs ORDER BY id").fetchall()
        self.assertEqual([tuple(r) for r in rows], [(G3, 1, 5, 900), (G3, 0, 5, 900),
                                                   (G3, 0, 49, 900), (G3, 0, 1, -1)])

    def test_facts_need_a_trusted_lobby_and_a_key_names_the_account(self):
        self.get(story="list")
        self.assertEqual(self.post("surf_two", "d" * 32, 90000, src="203.0.113.5", sfails=0,
                                   smask=1), [])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM story_runs").fetchone()[0], 0)
        # PUB[1] is linked to Bob: the run is his account's.
        self.assertEqual(self.post("surf_two", G1, 91000, pub=PUB[1], sfails=0, smask=1),
                         [("g", 1, "W only", 3, "Two")])
        self.assertEqual(tuple(self.db.execute(
            "SELECT player, pub FROM story_runs WHERE millis = 91000").fetchone()), (B, PUB[1]))

    def test_a_key_linked_later_takes_its_own_runs_only(self):
        self.srun("surf_two", G2, 90000, fails=0, pub=PUB[2])
        self.srun("surf_two", G2, 90000, inmask=1, pub=PUB[3])       # another key under that guid
        self.db.execute("INSERT INTO keylinks(pub,steamid,player,linked_at) VALUES(?,?,?,?)",
                        (PUB[2], A, G2, self.now))
        self.db.commit()
        self.assertEqual(self.mine(A)[2][0], (2, 90000))             # nofail moved, wonly did not
        self.assertEqual(self.mine(G2)[2][0], (3, 90000))

    def test_one_run_challenges_places_and_dates(self):
        self.srun("surf_one", A, 50000, inmask=1)                        # no jump: bronze
        self.srun("surf_one", B, 50000, inmask=17, top=3000)             # 3000 u/s: silver
        self.srun("surf_one", G2, 50000, spots="ramp")                   # via ramp: gold
        self.run_row("surf_three", A, 0, leg=2)                          # stage 2 time not known
        self.run_row("surf_three", B, 9000, leg=2)                       # stage 2 under 0:10
        self.srun("surf_three", A, 40000, at=self.now - 100)             # the first finisher
        self.srun("surf_three", B, 30000, at=self.now - 50)
        self.srun("surf_three", G2, 35000, at=self.now - 10)
        self.srun("surf_two", A, 89000, track=1, prevms=100000)          # 11% better
        self.srun("surf_two", B, 95000, track=1, prevms=100000)          # 5%: no
        self.srun("surf_two", G2, 50000, track=1, prevms=0)              # no best before it: no
        _, _, a = self.mine(A)
        _, _, b = self.mine(B)
        _, _, g = self.mine(G2)
        self.assertEqual((a[1][0], b[1][0], g[1][0]), (1, 2, 3))
        self.assertEqual((a[2][0], b[2][0], g[2][0]), (3, 2, 2))       # A first; B, G2 top 2
        self.assertEqual((a[3][0], b[3][0], g[3][0]), (3, 0, 0))
        # Events: open 10-20 Jan.  A run before the dates counts nothing.
        self.srun("surf_three", C, 20000)                                # banned
        self.srun("surf_three", "e" * 32, 20000, at=self.now - 30 * 86400)
        self.srun("surf_three", "f" * 32, 29000)
        self.srun("surf_one", "f" * 32, 50000, at=1797000000)            # in its December
        self.srun("surf_one", "e" * 32, 50000)                           # after it ended
        self.settle()
        _, _, e = self.mine("e" * 32, "events")
        _, _, f = self.mine("f" * 32, "events")
        self.assertEqual((e, f), ({}, {0: (3, 29000), 1: (3, 50000)}))
        _, body = self.get(story="list")
        ev = body["lists"][1]["levels"]
        self.assertEqual([(x["from"], x["to"], x["in"]) for x in ev],
                         [(1799539200, 1800489600, [1799539200 - self.now, 1800489600 - self.now]),
                          (1796083200, 1798761600, [1796083200 - self.now, 1798761600 - self.now])])
        self.assertNotIn("in", body["lists"][0]["levels"][0])

    def test_styles_read_the_lobby_bits(self):
        lists, problems = S.story_parse('list a "A"\nchapter\nlevel surf_two\n  bronze sw\n'
                                        '  silver hsw\n')
        self.assertEqual((problems, [c["t"] for c in lists[0]["chapters"][0]["levels"][0]["ch"]]),
                         ([], ["Sideways: W and S only", "Half-sideways: two keys at once"]))
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_two\n  bronze sw\n'
                                        '  silver hsw\n')
        self.srun("surf_two", A, 50000, inmask=1 | 2 | 1024)          # W and S: sideways
        self.srun("surf_two", B, 50000, inmask=1 | 4 | 1024)          # A alone once: neither
        self.srun("surf_two", G2, 50000, inmask=1 | 8)                # W+D only: half-sideways
        self.assertEqual([self.mine(w)[2].get(0, (0,))[0] for w in (A, B, G2)], [1, 0, 2])

    def test_a_ladder_that_fails_still_logs_the_finish(self):
        with patch.object(S, "_story_conf", side_effect=RuntimeError("boom")):
            self.assertEqual(self.post("surf_two", G3, 90000, sfails=0, smask=1), [])
        self.assertEqual(self.db.execute("SELECT COUNT(*), MIN(fails) FROM story_runs").fetchone()[:],
                         (1, 0))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)

    def test_first_is_the_first_logged_finish_and_nobody_after_older_times(self):
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_two\n  gold first\n'
                                        'level surf_one\n  gold first\n')
        # surf_two: D (A here) finished before the log began, E (B) after it: unknown.
        self.run_row("surf_two", A, 70000)
        self.db.execute("UPDATE runs SET submitted = ? WHERE player = ?", (self.now - 500, A))
        self.db.commit()
        self.srun("surf_two", B, 80000, at=self.now - 100)
        # surf_one: logged only.  B first, A second; A improving later changes nothing.
        self.srun("surf_one", B, 60000, at=self.now - 90)
        self.srun("surf_one", A, 61000, at=self.now - 80)
        self.srun("surf_one", A, 50000, at=self.now - 10)
        _, _, a = self.mine(A)
        _, _, b = self.mine(B)
        self.assertEqual((a.get(0, (0,))[0], b.get(0, (0,))[0], a[1][0], b[1][0]), (0, 0, 0, 3))
        # The finish's answer agrees: a later finisher is not told first.
        self.settle()
        self.assertEqual(self.post("surf_one", G3, 40000), [])

    def test_first_stays_unknown_when_an_older_time_moves(self):
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_two\n  gold first\n')
        self.run_row("surf_two", A, 70000)                      # on the board before the log
        self.settle()                                           # the ledger: logged from now, prior
        self.srun("surf_two", B, 80000, at=self.now + 100)
        self.db.execute("UPDATE runs SET submitted = ? WHERE player = ?", (self.now + 500, A))
        self.db.commit()                                        # A improved since
        self.settle()
        self.assertEqual((self.mine(A)[2], self.mine(B)[2]), ({0: (0, 70000)}, {0: (0, 80000)}))

    def test_first_is_in_logged_order_in_the_answer_and_the_ladder(self):
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_three\n  gold first\n'
                                        '  bronze finish\n')
        self.settle()                                           # empty board: prior 0
        self.srun("surf_three", C, 30000, at=self.now - 9)      # banned: holds nothing
        self.srun("surf_three", G2, 31000, at=self.now + 5)     # logged first, later clock
        self.srun("surf_three", G3, 32000, at=self.now)
        self.settle()
        self.assertEqual((self.mine(G2)[2][0][0], self.mine(G3)[2][0][0]), (3, 1))
        # A banned account's earlier row does not stop the answer telling the first.
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_one\n  gold first\n'
                                        '  bronze finish\n')
        self.settle()
        self.srun("surf_one", C, 30000)
        self.assertEqual(self.post("surf_one", G1, 40000, pub=PUB[1]),
                         [("g", 1, "Be the first to finish", 3, "")])
        self.settle()
        self.assertEqual(self.mine(B)[2][0][0], 3)

    def test_the_ledger_is_written_before_the_finish_touches_the_board(self):
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_one\n  gold first\n')
        with patch.object(S, "_story_kick", lambda *a: None):      # no pass to race it
            self.post("surf_one", G3, 40000)
        self.assertEqual(tuple(self.db.execute("SELECT began, prior FROM story_tracks").fetchone()),
                         (self.now, 0))
        self.settle()
        self.assertEqual(self.mine(G3)[2][0][0], 3)

    def test_first_looks_past_any_number_of_banned_finishers(self):
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_one\n  gold first\n')
        self.settle()
        for _ in range(25):
            self.srun("surf_one", C, 30000)
        self.srun("surf_one", G2, 31000)
        self.settle()
        self.assertEqual(self.mine(G2)[2][0][0], 3)

    def test_dated_first_needs_the_log_to_cover_the_dates(self):
        (HOME / "story.txt").write_text('list ev "E"\ndates 2027-01-10 2027-01-20\nchapter\n'
                                        'level surf_two\n  gold first\n  bronze finish\n')
        self.srun("surf_two", G2, 50000)
        for prior, want in ((1, 1), (0, 3)):
            self.db.execute("DELETE FROM story_tracks")
            self.db.execute("INSERT INTO story_tracks VALUES ('surf_two', 0, ?, ?)",
                            (self.now - 10, prior))             # began after the dates opened
            self.db.commit()
            self.settle()
            self.assertEqual(self.mine(G2, "ev")[2][0][0], want)

    def test_a_dated_stage_keeps_its_medal_when_bettered_later(self):
        (HOME / "story.txt").write_text('list ev "E"\ndates 2027-01-10 2027-01-20\nchapter\n'
                                        'level surf_two\n  bronze stage 2 0:10\n')
        self.settle()
        self.assertEqual(self.post("surf_two", G3, 9000, leg=2), [])   # a stage: logged, untold
        self.assertEqual(self.db.execute("SELECT leg, millis FROM story_runs").fetchone()[:],
                         (2, 9000))
        self.now = 1800500000                                           # after the dates
        self.post("surf_two", G3, 8000, leg=2)                          # not logged: closed
        self.settle()
        self.assertEqual(self.mine(G3, "ev")[2][0][0], 1)

    def test_a_reject_reaches_a_row_by_its_replay_too(self):
        self.receipt("r-x", PUB[3], G3, 100)
        rid = self.db.execute("SELECT id FROM replays WHERE runid = 'r-x'").fetchone()[0]
        self.db.execute("INSERT INTO reviews(replay_id, decision, at) VALUES(?, 'reject', ?)",
                        (rid, self.now))
        self.db.commit()
        self.srun("surf_two", G3, 50000, inmask=1, replay_id=rid)       # no runid on the row
        self.assertEqual(self.mine(G3)[2], {})

    def test_an_edit_forgets_the_told_medals(self):
        S._story["recent"][(G3, "story", 0)] = (1, 99)
        (HOME / "story.txt").write_text(STORY2 + "\n")
        self.get(story="list")
        self.assertEqual(S._story["recent"], {})

    def test_a_rejected_recording_earns_nothing_here_either(self):
        self.receipt("r-bad", PUB[3], G3, 100)
        self.db.execute("UPDATE replays SET map = 'surf_two' WHERE runid = 'r-bad'")
        rid = self.db.execute("SELECT id FROM replays WHERE runid = 'r-bad'").fetchone()[0]
        self.db.execute("INSERT INTO reviews(replay_id, decision, at) VALUES(?, 'reject', ?)",
                        (rid, self.now))
        self.db.commit()
        self.srun("surf_two", G3, 50000, inmask=1, fails=0, runid="r-bad")
        self.srun("surf_two", G3, 60000, runid="r-ok")
        self.assertEqual(self.mine(G3)[2][0], (1, 60000))

    def test_a_recording_is_read_for_its_spots(self):
        rec = HOME / "spots.rec"
        rec.write_text("FTESURF-REC 11\nmap surf_one\nbegin\n"
                       "-0.1 100 200 300 0 0 0 0 0 1 0\n"            # in the spot, before the start
                       "0.0 0 0 0 0 0 0 0 0 1 0\n"
                       "in 1 2 3 0 0 0 0 0 0 0 0\n"
                       "0.1 400 0 0 0 0 0 0 0 1 0\n"                 # passes (100,200) 200 off: no
                       "0.2 5000 5000 0 0 0 0 0 0 1 0\n"             # a teleport's jump: no segment
                       "0.3 5000 5000 280 0 0 0 0 0 1 0\n"
                       "0.4 5100 5000 280 0 0 0 0 0 1 0\n"
                       "end 1 2 3\n")
        self.assertEqual(S._story_spot_read(str(rec), {"ramp": (100.0, 200.0, 300.0, 64.0)}), set())
        self.assertEqual(S._story_spot_read(str(rec), {"far": (5050.0, 5040.0, 290.0, 64.0)}),
                         {"far"})
        self.assertEqual(S._story_spot_read(str(rec), {"jump": (2500.0, 2500.0, 0.0, 64.0)}), set())
        self.srun("surf_one", A, 50000)
        rowid = self.db.execute("SELECT id FROM story_runs").fetchone()[0]
        S._story_spot_queue(rowid, str(rec), {"ramp": (5050.0, 5000.0, 280.0, 64.0)})
        for _ in range(100):
            if self.db.execute("SELECT spots FROM story_runs").fetchone()[0]:
                break
            threading.Event().wait(0.05)
        self.assertEqual(self.db.execute("SELECT spots FROM story_runs").fetchone()[0], "ramp")
        self.now += S.STORY_TTL + 1
        self.assertEqual(self.mine(A)[2][1][0], 3)


for _n in [n for n in vars(Story) if n.startswith("test_")]:
    setattr(Story2, _n, None)           # Story2 inherits the helpers, not the tests


if __name__ == "__main__":
    try:
        unittest.main(verbosity=1)
    finally:
        shutil.rmtree(HOME, ignore_errors=True)
