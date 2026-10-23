#!/usr/bin/env python3
"""Patch 854: the Story list's grammar and the medals worked out from WOS rows.

Real Flask routes on an isolated database; the map library is patched, no HTTP."""
from contextlib import closing
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
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

    def test_lobby_population_freshness_contract(self):
        self.db.execute("DELETE FROM lobbies")
        for node, age, players in (("fresh", 0, 1), ("old", S.LOBBY_TTL, 99)):
            self.db.execute("INSERT INTO lobbies(node,map,players,maxplayers,addr,name,last_seen)"
                            " VALUES(?, 'surf_one', ?, 128, '127.0.0.1:27510', 'Fixture', ?)",
                            (node, players, self.now - age))
        self.db.commit()
        reply = self.client.get("/lobbies.json").get_json()
        self.assertEqual(reply["ttl"], S.LOBBY_TTL)
        self.assertEqual([(r["players"], r["age"]) for r in reply["lobbies"]], [(1, 0)])
        self.assertNotIn("node", reply["lobbies"][0])

    def test_lobby_directory_failure_is_not_fresh_empty(self):
        with patch.object(S, "live_rows", side_effect=sqlite3.OperationalError("fixture unavailable")):
            reply = self.client.get("/lobbies.json").get_json()
        self.assertEqual((reply["ttl"], reply["lobbies"]), (0, []))
        with patch.object(S, "live_rows", return_value=[]):
            reply = self.client.get("/lobbies.json").get_json()
        self.assertEqual((reply["ttl"], reply["lobbies"]), (S.LOBBY_TTL, []))

    def test_story_list_exports_local_criteria_for_every_matching_level(self):
        text = Path(__file__).with_name("story.txt").read_text()
        (HOME / "story.txt").write_text(text)
        S._story_conf()
        lists, problems = S.story_parse(text)
        self.assertFalse(problems)
        maps = {lv["map"] for L in lists for c in L["chapters"] for lv in c["levels"] if lv["map"]}
        with patch.object(S, "map_index", lambda now=None: ({m: m for m in maps}, maps)):
            calc = S._story_calc(self.db, lists, self.now)
        with S._story_lock:
            S._story_install(calc, S._story["rev"], self.now, S._story["seq"])
        body = self.get(story="list")[1]
        matches = [(L["id"], lv) for L in body["lists"] for lv in L["levels"]
                   if lv["map"] == "surf_cyberwave" and lv["track"] == 0]
        self.assertEqual({lid for lid, _ in matches}, {"story", "events"})
        for _, lv in matches:
            for ch in lv["ch"]:
                self.assertTrue({"m", "t", "live", "k", "v", "w"} <= ch.keys())
        # Full finish locally decides Story bronze and Events gold independently;
        # the HTTP toast's best-medal choice is not the local task payload.
        finish_medals = {lid: [ch["m"] for ch in lv["ch"] if ch["k"] == "finish"]
                         for lid, lv in matches}
        self.assertEqual(finish_medals, {"story": ["b"], "events": ["g"]})

    def test_shipped_story_gate_curve_is_reachable(self):
        text = Path(__file__).with_name("story.txt").read_text()
        lists, problems = S.story_parse(text)
        self.assertFalse(problems)
        # Source-marked unzoned maps must not be needed to open later chapters.
        unzoned = {line.split()[1] for line in text.splitlines()
                   if line.startswith("level ") and "no zones yet" in line}
        maps = {lv["map"] for L in lists for c in L["chapters"] for lv in c["levels"]
                if lv["map"]} - unzoned
        with patch.object(S, "map_index", lambda now=None: ({m: m for m in maps}, maps)):
            calc = S._story_calc(self.db, lists, self.now)
        ladder = calc["lists"][0]
        bars = ladder["bars"]
        self.assertEqual(bars, [0, 9, 18, 27, 29, 38, 47, 51, 58, 60, 69,
                                86, 99, 110, 112, 120, 122, 131, 141, 147])
        avail = 0
        for j, bar in enumerate(bars):
            self.assertLessEqual(bar, avail, (j, bar, avail))
            if j:
                self.assertGreater(bar, bars[j - 1])
            if j >= 11:
                pct = 65 if j == 11 else 70
                self.assertEqual(bar, -(-avail * pct // 100))
            avail += sum(max(S.STORY_POINTS[ch["m"]] for ch in lv["ch"]
                             if S._story_live(ch, lv))
                         for lv in ladder["levels"] if lv["chap"] == j and lv["timed"])

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

    def test_pending_progress_until_inflight_recompute_installs(self):
        self.assertEqual(self.get(story="player", who=handle(A))[1]["pending"], 0)
        self.run_row("surf_two", A, 61000)
        with S._story_lock:
            S._story["seq"] += 1
        started, release = threading.Event(), threading.Event()
        original = S._story_calc

        def held_calc(db, lists, now):
            started.set()
            if not release.wait(10):
                raise AssertionError("test did not release Story recompute")
            return original(db, lists, now)

        with patch.object(S, "_story_calc", held_calc):
            try:
                old = self.get(story="player", who=handle(A))[1]
                self.assertTrue(started.wait(5))
                self.assertEqual((old["pending"], old["lists"][0]["t"]), (1, 0))
                # Repeated reads neither wait nor call the stale snapshot fresh.
                again = self.get(story="player", who=handle(A))[1]
                self.assertEqual((again["pending"], again["lists"][0]["t"]), (1, 0))
            finally:
                release.set()
                for _ in range(5):
                    workers = [t for t in threading.enumerate() if t.name == "story"]
                    for t in workers:
                        t.join(10)
                    if not workers:
                        break
        fresh = self.get(story="player", who=handle(A))[1]
        self.assertEqual((fresh["pending"], fresh["lists"][0]["t"]), (0, 3))

    def test_pending_uses_served_snapshot_if_worker_installs_during_response(self):
        self.mine(A)
        old = S._story["calc"]
        with S._story_lock:
            S._story["seq"] += 1
        replacement = dict(old)
        original_avatars = S.avatars

        def install_during_response(now, db):
            with S._story_lock:
                S._story_install(replacement, S._story["rev"], now, S._story["seq"])
            return original_avatars(now, db)

        with patch.object(S, "_story_kick"), patch.object(S, "avatars", install_during_response):
            served = self.get(story="player", who=handle(A))[1]
        self.assertIsNot(old, S._story["calc"])
        self.assertEqual(served["pending"], 1)
        self.assertEqual(self.get(story="player", who=handle(A))[1]["pending"], 0)

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
             spots="", runid="", pub="", leg=0, replay_id=0, maxfog=-1):
        self.db.execute("INSERT INTO story_runs(map,track,leg,player,pub,name,millis,prevms,at,runid,"
                        "replay_id,fails,inmask,top,spots,maxfog) VALUES(?,?,?,?,?,'n',?,?,?,?,?,?,?,?,?,?)",
                        (mapname, track, leg, player, pub, ms, prevms,
                         self.now if at is None else at, runid, replay_id, fails, inmask, top, spots,
                         maxfog))
        self.db.commit()

    def settle(self):
        """Work the ladder out again and wait for the thread."""
        self.now += S.STORY_TTL + 1
        self.get(story="list")
        # Until the pass kicked at this clock is installed: a previous test's thread
        # can clear `busy` under this one (setUp resets the shared state).
        for _ in range(200):
            if not S._story["busy"] and S._story["at"] == self.now:
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

    def test_maxfog_schema_preserves_legacy_rows_and_stays_idempotent(self):
        with sqlite3.connect(":memory:") as db:
            column = " maxfog INTEGER NOT NULL DEFAULT -1,"
            legacy = S.STORY_RUNS_DDL.replace(column, "")
            self.assertNotEqual(legacy, S.STORY_RUNS_DDL)
            db.executescript(legacy)
            db.execute("INSERT INTO story_runs(id,map,track,player,millis,at)"
                       " VALUES(42,'surf_two',0,'fixture',90000,7)")
            before = db.execute("SELECT * FROM story_runs").fetchone()
            self.assertNotIn("maxfog", {r[1] for r in db.execute("PRAGMA table_info(story_runs)")})
            S.story_schema(db)
            S.story_schema(db)
            after = db.execute("SELECT * FROM story_runs").fetchone()
            self.assertEqual(after[:-1], before)
            self.assertEqual(after[-1], -1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM story_runs").fetchone()[0], 1)

    def test_maxfog_schema_serializes_concurrent_importers(self):
        def old_schema(db):
            db.executescript(S.STORY_RUNS_DDL)
            if "maxfog" not in {r[1] for r in db.execute("PRAGMA table_info(story_runs)")}:
                db.execute("ALTER TABLE story_runs ADD COLUMN maxfog INTEGER NOT NULL DEFAULT -1")

        def race(migrate):
            ready = threading.Barrier(2)
            observed_old_schema = threading.Barrier(2)
            errors, writers = [], []
            with tempfile.TemporaryDirectory(dir=HOME, prefix="story-schema-race-") as home:
                path = Path(home) / "legacy.db"
                with closing(sqlite3.connect(path)) as db, db:
                    db.executescript(S.STORY_RUNS_DDL.replace(
                        " maxfog INTEGER NOT NULL DEFAULT -1,", ""))
                    db.execute("INSERT INTO story_runs(id,map,track,player,millis,at)"
                               " VALUES(42,'surf_two',0,'fixture',90000,7)")

                class Importer:
                    def __init__(self, conn):
                        self.conn = conn

                    def executescript(self, sql):
                        result = self.conn.executescript(sql)
                        ready.wait(timeout=5)
                        return result

                    def execute(self, sql, *args):
                        result = self.conn.execute(sql, *args)
                        if sql == "BEGIN IMMEDIATE":
                            writers.append(True)
                        if sql == "PRAGMA table_info(story_runs)" and not self.conn.in_transaction:
                            # Force the old unlocked importers to observe the same old schema.
                            rows = result.fetchall()
                            observed_old_schema.wait(timeout=5)
                            return rows
                        return result

                    def __enter__(self):
                        self.conn.__enter__()
                        return self

                    def __exit__(self, *args):
                        return self.conn.__exit__(*args)

                def worker():
                    conn = sqlite3.connect(path, timeout=5)
                    try:
                        migrate(Importer(conn))
                    except Exception as exc:
                        errors.append(exc)
                    finally:
                        conn.close()

                threads = [threading.Thread(target=worker, daemon=True) for _ in range(2)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=10)
                self.assertFalse(any(thread.is_alive() for thread in threads))
                with closing(sqlite3.connect(path)) as db:
                    self.assertEqual(db.execute("SELECT id,map,millis,at,maxfog FROM story_runs").fetchall(),
                                     [(42, "surf_two", 90000, 7, -1)])
            return errors, len(writers)

        old_errors, old_writers = race(old_schema)
        self.assertEqual(old_writers, 0)
        self.assertEqual(len(old_errors), 1)  # the control actually reproduces the unsafe ALTER race
        self.assertIsInstance(old_errors[0], sqlite3.OperationalError)
        self.assertIn("duplicate column", str(old_errors[0]))
        errors, writers = race(S.story_schema)
        self.assertEqual(errors, [])
        self.assertEqual(writers, 2)

    def test_maxfog_needs_an_explicit_complete_trusted_fact(self):
        known = (0, 1, 900)
        for raw in ("", "-1", "2", "1.0", "true", "x"):
            with self.subTest(raw=raw):
                self.assertEqual(S.story_maxfog({"smaxfog": raw}, True, known), -1)
        self.assertEqual(S.story_maxfog({"maxfog": "1"}, True, known), -1)
        for flag in (0, 1):
            form = {"smaxfog": str(flag)}
            self.assertEqual(S.story_maxfog(form, True, known), flag)
            self.assertEqual(S.story_maxfog(form, False, known), -1)
            for partial in ((-1, 1, 900), (0, -1, 900), (0, 1, -1)):
                self.assertEqual(S.story_maxfog(form, True, partial), -1)

    def test_maxfog_mode_is_explicit_not_a_map_name_or_gold_inference(self):
        text = ('list story "S"\nchapter\nlevel surf_two\n mode maxfog\n gold maxfog\n'
                'level surf_two\n gold finish\n')
        lists, problems = S.story_parse(text)
        self.assertEqual(problems, [])
        levels = lists[0]["chapters"][0]["levels"]
        self.assertEqual([lv.get("mode", "") for lv in levels], ["maxfog", ""])
        self.assertEqual(levels[0]["ch"][0]["t"], "Finish with Max Fog for the whole run")
        (HOME / "story.txt").write_text(text)
        _, body = self.get(story="list")
        self.assertEqual([lv["mode"] for lv in body["lists"][0]["levels"]], ["maxfog", ""])
        _, problems = S.story_parse('list a\n mode maxfog\nlevel surf_two\n mode other\n mode\n')
        self.assertEqual(len(problems), 3)

    def test_maxfog_finish_answer_and_ladder_agree_without_legacy_backfill(self):
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_two\n'
                                       ' mode maxfog\n bronze finish\n gold maxfog\n')
        self.get(story="list")
        self.assertEqual(self.post("surf_two", G3, 90000, sfails=0, smask=1, stop=900),
                         [("b", 1, "Complete the map", 1, "")])
        self.assertEqual(self.post("surf_two", G3, 91000, sfails=0, smask=1, stop=900, smaxfog=0), [])
        self.assertEqual(self.post("surf_two", G3, 92000, sfails=0, smask=1, smaxfog=1), [])
        self.assertEqual(self.post("surf_two", G3, 93000, sfails=0, smask=1, stop=900, smaxfog=1),
                         [("g", 1, "Finish with Max Fog for the whole run", 3, "")])
        self.assertEqual(self.post("surf_two", G3, 94000, leg=1,
                                   sfails=0, smask=1, stop=900, smaxfog=1), [])
        # A duplicate cannot replace its original latched fact with the caller's current mode.
        self.assertEqual(self.post("surf_two", G3, 93000, sfails=0, smask=1, stop=900, smaxfog=0), [])
        self.assertEqual([r[0] for r in self.db.execute("SELECT maxfog FROM story_runs ORDER BY id")],
                         [-1, 0, -1, 1])
        # The stage POST acted on the board, but this undated full-run level does not log it.
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM runs WHERE leg=1").fetchone()[0], 1)
        self.settle()
        self.assertEqual(self.mine(G3)[2][0], (3, 90000))

    def test_dated_maxfog_needs_a_full_finish_in_its_window(self):
        (HOME / "story.txt").write_text('list events "E"\ndates 2027-01-10 2027-01-20\n'
                                       'chapter\nlevel surf_two\n gold maxfog\n')
        self.srun("surf_two", A, 90000, at=self.now - 30 * 86400, maxfog=1)
        self.srun("surf_two", B, 90000, maxfog=1)
        self.srun("surf_two", G2, 90000, leg=1, maxfog=1)
        self.srun("surf_two", G3, 90000)    # a legacy complete finish is not evidence of fog
        self.assertEqual([self.mine(w, "events")[2].get(0, (0,))[0] for w in (A, B, G2, G3)],
                         [0, 3, 0, 0])

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

    def test_a_finish_whose_log_never_completed_keeps_its_place(self):
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_one\n  gold first\n'
                                        '  bronze finish\n')
        self.settle()
        with patch.object(S, "story_finish", side_effect=sqlite3.OperationalError("busy")):
            self.post("surf_one", G3, 40000)                    # reserved before the board, never done
        self.assertEqual(self.db.execute("SELECT player, done FROM story_runs").fetchall()[0][:],
                         (G3, 0))
        self.post("surf_one", G2, 45000)
        self.settle()
        self.assertEqual((self.mine(G2)[2][0][0], self.mine(G3)[2][0][0]), (1, 3))

    def test_a_re_post_completes_the_run_its_first_answer_lost(self):
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_one\n  bronze finish\n'
                                        '  gold nofail\n')
        self.settle()
        with patch.object(S, "story_finish", side_effect=sqlite3.OperationalError("busy")):
            self.post("surf_one", G3, 40000, runid="r-again", sfails=0, smask=1)
        self.now += 3
        self.post("surf_one", G3, 40000, runid="r-again", sfails=0, smask=1)
        self.assertEqual([tuple(r) for r in self.db.execute("SELECT done, fails FROM story_runs")],
                         [(1, 0)])
        self.settle()
        self.assertEqual(self.mine(G3)[2][0][0], 3)

    def test_a_run_the_board_refused_holds_no_first(self):
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_one\n  gold first\n'
                                        '  bronze finish\n')
        self.settle()
        with patch.object(S, "_runs_full", lambda db, leg: True):
            r = self.client.post("/api/run", data={
                "key": "testkey", "map": "surf_one", "track": "0", "leg": "0", "player": G3,
                "name": "Proto", "ticks": "4000", "tickrate": "100", "flags": "0",
                "node": "p27510", "runid": "r-full"})
        self.assertEqual(r.status_code, 429)                    # reserved, never on the board
        self.assertEqual(self.post("surf_one", G2, 45000), [("g", 1, "Be the first to finish", 3, "")])
        self.settle()
        self.assertEqual(self.mine(G2)[2][0][0], 3)

    def test_a_post_from_outside_the_lobbies_takes_nothing_back(self):
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_one\n  gold first\n'
                                        '  bronze finish\n')
        self.settle()
        self.assertEqual(self.post("surf_one", G2, 45000), [("g", 1, "Be the first to finish", 3, "")])
        self.post("surf_one", G3, 40000, src="203.0.113.5")     # keyed, untrusted: not logged
        self.settle()
        self.assertEqual(self.mine(G2)[2][0][0], 3)

    def test_a_busy_ledger_write_does_not_withhold_first(self):
        (HOME / "story.txt").write_text('list story "S"\nchapter\nlevel surf_one\n  gold first\n')
        with patch.object(S, "_story_track_began", side_effect=sqlite3.OperationalError("busy")):
            self.post("surf_one", G3, 40000)                    # logged, untold, no ledger row
        self.settle()                                           # the pass writes it: G3 is logged
        self.assertEqual(tuple(self.db.execute("SELECT prior FROM story_tracks").fetchone()), (0,))
        self.assertEqual(self.mine(G3)[2][0][0], 3)

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
