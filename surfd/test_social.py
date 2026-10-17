#!/usr/bin/env python3
"""Friends controls: real Flask routes/schema/proofs, isolated DB, no external HTTP."""
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

HOME = Path(tempfile.mkdtemp(prefix="surfd-social-"))
(HOME / "surfd.env").write_text("SURFD_KEY=testkey\n")
GAME_BYTES = b"synthetic social test CSQC\n"
(HOME / "csprogs.dat").write_bytes(GAME_BYTES)
os.environ.update(SURFD_HOME=str(HOME), SURFD_DB=str(HOME / "test.db"),
                  SURFD_ENV=str(HOME / "surfd.env"), SURFD_LINK_HOSTS="127.0.0.1",
                  SURFD_GAME_CODE=str(HOME / "csprogs.dat"),
                  SURFD_BOARD_URL="https://proto.bar/ftesurf/board",
                  SURFD_TOOLS=str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import ed25519
import accounts as A
import surfd as S
import social as F

IDS = ["76561198000000001", "76561198000000002", "76561198000000003"]
PUBS = [ed25519.publickey(bytes([i]) * 32).hex() for i in (1, 2, 3, 4)]
GAME = hashlib.sha256(GAME_BYTES).hexdigest()


class Friends(unittest.TestCase):
    def setUp(self):
        self.now = 1800000000
        self.clock = patch.object(S.time, "time", lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        S._rate.clear()
        self.client = S.app.test_client()
        self.db = S.connect()
        self.addCleanup(self.db.close)
        for table in ("social_messages", "social_friends", "social_sessions", "keylinks", "accounts", "lobbies"):
            self.db.execute("DELETE FROM " + table)
        for sid, name in zip(IDS, ("Alice", "Bob", "Third")):
            self.db.execute("INSERT INTO accounts(steamid,name,created_at) VALUES(?,?,?)", (sid, name, self.now))
        for pub, sid in zip(PUBS, IDS + [IDS[0]]):
            self.db.execute("INSERT INTO keylinks(pub,steamid,linked_at) VALUES(?,?,?)", (pub, sid, self.now))
        self.db.commit()
        # Capabilities are minted by the REAL verified /api/account path, not a fixture session insert.
        self.tokens = [self.hello(i + 1)["social"] for i in range(4)]
        self.heartbeat("p27510", 27510, "surf_test")
        self.heartbeat("p27511", 27511, "surf_elsewhere")

    def post(self, path, **form):
        return self.client.post(path, data=dict(key="testkey", node="p27510", **form))

    def hello(self, i, **extra):
        nonce = "%032x" % i
        seed = bytes([i]) * 32
        form = dict(key="testkey", node="p27510", pub=PUBS[i - 1], nonce=nonce,
                    server="127.0.0.1:27510", game=GAME, keyed="0", ip="127.0.0.1:27001")
        form.update(extra)
        msg = (A.STATEMENT % (form["server"], form["nonce"], A.TICKS_HELLO, 0, form["game"])).encode()
        if "sig" not in extra:
            form["sig"] = ed25519.sign(seed, msg).hex()
        return self.client.post("/api/account", data=form).get_json()

    def heartbeat(self, node, port, mapname):
        r = self.client.post("/api/heartbeat", data=dict(key="testkey", node=node, port=port,
            map=mapname, name="Test lobby", players=1, max=64, zoned=1), environ_base={"REMOTE_ADDR": "127.0.0.1"})
        self.assertEqual(r.status_code, 200)

    def poll(self, indices=(0, 1, 2, 3), hashes=None, ack=0, node="p27510"):
        roster = [dict(token=self.tokens[i], hash=(hashes or {}).get(i, ""), ack=ack) for i in indices]
        r = self.client.post("/api/social/poll", data=dict(key="testkey", node=node, roster=json.dumps(roster)))
        self.assertEqual(r.status_code, 200)
        return r.get_json()["players"]

    def action(self, i, op, other=1, **extra):
        r = self.post("/api/social/action", token=self.tokens[i], op=op, who=A.who_of(IDS[other]), **extra)
        return r

    def befriend(self):
        self.assertEqual(self.action(0, "add").status_code, 200)

    def legacy_request(self):
        # A request a pre-P770 service stored: Alice asked, Bob never accepted.
        self.db.execute("INSERT INTO social_friends(lo,hi,asker) VALUES(?,?,?)", (*F.pair(IDS[0], IDS[1]), IDS[0]))
        self.db.commit()

    def test_proof_mint_and_wrong_proof_no_capability(self):
        r = self.hello(1, old_social=self.tokens[0])
        self.assertEqual(r["social_who"], A.who_of(IDS[0]))
        self.assertNotIn("social", self.hello(1, sig="0" * 128))
        self.assertNotIn("social", self.hello(1, pub=PUBS[1]))
        self.assertNotIn("social", self.hello(1, game="0" * 64))
        self.assertEqual(F.digest(r["social"]), self.db.execute("SELECT token FROM social_sessions WHERE pub=?", (PUBS[0],)).fetchone()[0])
        self.assertNotEqual(r["social"], F.digest(r["social"]))

    def test_add_is_mutual_at_once_and_cross_install_identity(self):
        self.assertEqual(self.action(0, "add").status_code, 200)
        rows = self.poll()
        self.assertEqual(rows[0]["friends"], rows[3]["friends"])
        self.assertEqual(rows[0]["friends"][0]["relation"], 3)
        self.assertEqual((rows[1]["friends"][0]["relation"], rows[1]["friends"][0]["online"]), (3, 1))
        self.assertEqual(self.action(0, "add").status_code, 409)
        self.assertEqual(self.action(1, "add", 0).status_code, 409)
        self.assertEqual(self.action(1, "accept", 0).status_code, 409)
        self.assertEqual(self.action(3, "remove").status_code, 200)
        self.assertEqual(self.poll()[0]["friends"], [])
        self.assertEqual(self.poll()[1]["friends"], [])

    def test_legacy_request_becomes_friendship_by_add_or_poll(self):
        self.legacy_request()
        self.assertEqual(self.action(1, "add", 0).status_code, 200)
        self.assertEqual(self.poll()[0]["friends"][0]["relation"], 3)
        self.assertEqual(self.action(0, "remove").status_code, 200)
        self.legacy_request()
        rows = self.poll()
        self.assertEqual((rows[0]["friends"][0]["relation"], rows[1]["friends"][0]["relation"]), (3, 3))
        self.assertEqual(self.db.execute("SELECT count(*) FROM social_friends WHERE accepted=0").fetchone()[0], 0)

    def test_block_ends_friendship_refuses_add_and_messages_and_is_hidden(self):
        self.befriend(); self.poll()
        self.assertEqual(self.action(1, "block", 0).status_code, 200)
        rows = self.poll()
        self.assertEqual(rows[0]["friends"], [])                      # Alice no longer sees Bob
        self.assertEqual((rows[1]["friends"][0]["relation"], rows[1]["friends"][0]["online"]), (4, 0))
        self.assertEqual(self.action(0, "add").status_code, 409)
        self.assertEqual(self.action(0, "message", text="hello?").status_code, 403)
        self.assertEqual(self.action(0, "join").status_code, 403)
        self.assertEqual(self.action(0, "remove").status_code, 200)   # cannot lift Bob's block
        self.assertEqual(self.action(0, "add").status_code, 409)
        self.assertEqual(self.action(1, "add", 0).status_code, 409)   # unblock first
        self.assertEqual(self.poll()[1]["friends"][0]["relation"], 4)  # a poll does not convert it
        self.assertEqual(self.action(0, "unblock").status_code, 409)
        self.assertEqual(self.action(1, "unblock", 0).status_code, 200)
        self.assertEqual(self.poll()[1]["friends"], [])
        self.assertEqual(self.action(0, "add").status_code, 200)

    def test_block_purges_queued_messages_and_a_stranger_can_be_blocked(self):
        self.befriend(); self.poll()
        self.assertEqual(self.action(0, "message", text="queued").status_code, 200)
        self.assertEqual(self.action(1, "block", 0).status_code, 200)
        self.assertEqual(self.poll()[1]["messages"], [])
        self.assertEqual(self.action(2, "block", 0).status_code, 200)  # never friends
        self.assertEqual(self.action(0, "add", 2).status_code, 409)
        self.assertEqual([r["relation"] for r in self.poll()[2]["friends"]], [4])

    def test_mutual_blocks_each_stand_until_their_own_unblock(self):
        self.assertEqual(self.action(0, "block").status_code, 200)        # the harasser first
        self.assertEqual(self.action(1, "block", 0).status_code, 200)     # the victim's still counts
        rows = self.poll()
        self.assertEqual((rows[0]["friends"][0]["relation"], rows[1]["friends"][0]["relation"]), (4, 4))
        self.assertEqual(self.action(0, "unblock").status_code, 200)
        self.assertEqual(self.action(0, "add").status_code, 409)          # Bob's block stands
        self.assertEqual(self.poll()[0]["friends"], [])
        self.assertEqual(self.poll()[1]["friends"][0]["relation"], 4)
        self.assertEqual(self.action(0, "remove").status_code, 200)       # cannot lift Bob's either
        self.assertEqual(self.action(0, "add").status_code, 409)
        self.assertEqual(self.action(1, "remove", 0).status_code, 200)    # Bob's Remove is his unblock
        self.assertEqual(self.poll()[1]["friends"], [])
        self.assertEqual(self.action(0, "add").status_code, 200)

    def test_being_blocked_takes_no_friend_slot(self):
        for i in range(F.MAX_FRIENDS):
            blocker = "765611982%08d" % i
            self.db.execute("INSERT INTO social_friends(lo,hi,asker,accepted) VALUES(?,?,?,-1)",
                            (*F.pair(IDS[1], blocker), blocker))
        self.db.commit()
        self.assertEqual(self.poll()[1]["friends"], [])
        self.assertEqual(self.action(1, "add", 2).status_code, 200)

    def test_menu_list_omits_my_blocks_for_older_menus(self):
        self.assertEqual(self.action(0, "block").status_code, 200)
        self.poll()
        self.assertEqual(self.menu_read(self.menu_form())["friends"], [])

    def test_copied_key_connections_do_not_revoke_each_other(self):
        copied = self.hello(1, nonce="bc" * 16)["social"]
        self.tokens.append(copied)
        rows = self.poll((0, 4))
        self.assertFalse(any(r.get("invalid") for r in rows))
        self.assertEqual(rows[0]["friends"], rows[1]["friends"])
        # Refresh one connection, retiring only its own capability.
        self.tokens[0] = self.hello(1, old_social=self.tokens[0])["social"]
        self.assertFalse(any(r.get("invalid") for r in self.poll((0, 4))))

    def test_full_profile_handle_and_wrong_suffix(self):
        full = hashlib.sha256(IDS[1].encode()).hexdigest()[:12]
        r = self.post("/api/social/action", token=self.tokens[0], op="add", who=full)
        self.assertEqual(r.status_code, 200)
        r = self.post("/api/social/action", token=self.tokens[0], op="add", who=full[:8] + "0000")
        self.assertEqual(r.status_code, 400)

    def test_banned_or_deleted_friend_can_still_be_removed(self):
        self.befriend(); self.poll()
        self.db.execute("UPDATE accounts SET banned_at=? WHERE steamid=?", (self.now, IDS[1])); self.db.commit()
        row = self.poll((0,))[0]["friends"][0]
        self.assertEqual((row["name"], row["online"]), ("Unavailable account", 0))
        self.assertEqual(self.action(0, "remove").status_code, 200)
        self.db.execute("UPDATE accounts SET banned_at=0 WHERE steamid=?", (IDS[1],)); self.db.commit()
        self.befriend()
        self.db.execute("DELETE FROM accounts WHERE steamid=?", (IDS[1],)); self.db.commit()
        self.assertEqual(self.poll((0,))[0]["friends"][0]["name"], "Unavailable account")
        self.assertEqual(self.action(0, "remove").status_code, 200)

    def test_game_transport_keeps_refusal_text_without_weakening_auth(self):
        r = self.action(0, "join", game="1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.get_json()["ok"], r.get_json()["status"]), (0, 403))
        self.assertEqual(r.get_json()["error"], "Add them as a friend first")
        r = self.client.post("/api/social/action", data=dict(game="1", node="p27510", op="join"))
        self.assertEqual(r.status_code, 403)

    def test_fresh_presence_and_join_revalidated(self):
        self.befriend(); self.poll()
        row = self.poll()[0]["friends"][0]
        self.assertEqual((row["online"], row["map"], row["addr"]), (1, "surf_test", "127.0.0.1:27510"))
        self.assertEqual(self.action(0, "join").get_json()["addr"], row["addr"])
        self.now += F.PRESENCE_TTL + 1
        self.assertEqual(self.action(0, "join").status_code, 409)
        self.assertEqual(self.poll((0,))[0]["friends"][0]["online"], 0)

    def test_snapshot_disconnect_and_other_install_still_online(self):
        self.befriend(); self.poll()
        # Bob sees Alice through install4 after install1 drops.
        row = self.poll((1, 3))[0]["friends"][0]
        self.assertEqual(row["online"], 1)
        self.assertEqual(self.poll((1,))[0]["friends"][0]["online"], 0)

    def test_directory_staleness_and_map_switch(self):
        self.befriend(); self.poll()
        self.heartbeat("p27510", 27510, "surf_new")
        self.assertEqual(self.poll()[0]["friends"][0]["map"], "surf_new")
        self.db.execute("UPDATE lobbies SET last_seen=0"); self.db.commit()
        self.assertEqual(self.poll()[0]["friends"][0]["online"], 0)
        self.assertEqual(self.action(0, "join").status_code, 409)

    def test_incremental_hash_omits_unchanged_list(self):
        self.befriend()
        initial = self.poll()
        rows = self.poll(hashes={i: r["hash"] for i, r in enumerate(initial)})
        self.assertTrue(all("friends" not in r for r in rows))
        self.action(0, "remove")
        rows = self.poll(hashes={i: r["hash"] for i, r in enumerate(initial)})
        self.assertEqual(rows[0]["friends"], [])

    def test_message_private_only_to_recipient_with_retry_and_ack(self):
        self.befriend(); self.poll()
        text = 'hello; "quoted" $cvar and café'
        self.assertEqual(self.action(0, "message", text=text).status_code, 200)
        rows = self.poll()
        self.assertEqual([len(r["messages"]) for r in rows], [0, 1, 0, 0])
        self.assertEqual(rows[1]["messages"][0]["text"], text)
        self.assertEqual(self.poll()[1]["messages"], rows[1]["messages"])
        mid = rows[1]["messages"][0]["id"]
        self.assertEqual(self.poll((1,), ack=mid)[0]["messages"], [])

    def test_message_friend_requirement_control_then_remove_purges(self):
        self.poll()
        self.assertEqual(self.action(0, "message", text="not friends").status_code, 403)
        self.befriend(); self.poll()
        self.assertEqual(self.action(0, "message", text="private").status_code, 200)
        self.assertEqual(self.action(1, "remove", 0).status_code, 200)
        self.assertEqual(self.poll()[1]["messages"], [])
        self.assertEqual(self.db.execute("SELECT count(*) FROM social_messages").fetchone()[0], 0)

    def test_message_controls_length_and_expiry(self):
        self.befriend(); self.poll()
        for text in ("", "x" * 161, "x\nnewline", "x\rreturn", "x\tTAB", "\x04"):
            self.assertEqual(self.action(0, "message", text=text).status_code, 400)
        self.assertEqual(self.action(0, "message", text="x" * 160).status_code, 200)
        self.now += F.MESSAGE_TTL + 1
        self.assertEqual(self.poll()[1]["messages"], [])
        self.assertEqual(self.db.execute("SELECT count(*) FROM social_messages").fetchone()[0], 0)

    def test_invalid_wrong_node_rotated_and_expired_token(self):
        self.assertTrue(all(r.get("invalid") for r in self.poll(node="p27511")))
        r = self.post("/api/social/action", token="0" * 64, op="add", who=A.who_of(IDS[1]))
        self.assertEqual(r.status_code, 403)
        old = self.tokens[0]; self.tokens[0] = self.hello(1, old_social=old)["social"]
        self.assertNotEqual(old, self.tokens[0])
        self.assertEqual(self.post("/api/social/action", token=old, op="add", who=A.who_of(IDS[1])).status_code, 403)
        self.assertEqual(self.action(0, "add").status_code, 200)
        self.now += F.SESSION_TTL + 1
        self.assertTrue(all(r.get("invalid") for r in self.poll()))

    def test_relinked_key_and_ban_revoke_immediately(self):
        self.befriend(); self.poll()
        self.db.execute("UPDATE keylinks SET steamid=? WHERE pub=?", (IDS[2], PUBS[0]))
        self.db.execute("UPDATE accounts SET banned_at=? WHERE steamid=?", (self.now, IDS[1]))
        self.db.commit()
        rows = self.poll()
        self.assertTrue(rows[0]["invalid"] and rows[1]["invalid"])
        self.assertEqual(self.action(0, "join").status_code, 403)
        self.assertNotIn("social", self.hello(2))

    def test_unknown_self_import_only_and_colliding_mark_refuse(self):
        for mark in (A.who_of(IDS[0]), "0" * 8, "bad\";x"):
            self.assertEqual(self.post("/api/social/action", token=self.tokens[0], op="add", who=mark).status_code, 400)
        with patch.object(A, "who_of", lambda sid: "f" * 8):
            self.assertEqual(self.post("/api/social/action", token=self.tokens[0], op="add", who="f" * 8).status_code, 400)

    def test_presence_across_two_nodes_and_source_disconnect(self):
        self.befriend(); self.poll()
        elsewhere = self.hello(2, node="p27511", server="127.0.0.1:27511")["social"]
        r = self.client.post("/api/social/poll", data=dict(key="testkey", node="p27511",
            roster=json.dumps([dict(token=elsewhere)])))
        self.assertEqual(r.status_code, 200)
        # Drop Bob's old connection; his other node remains a live join target.
        self.poll((0, 3))
        row = self.poll((0, 3))[0]["friends"][0]
        self.assertEqual((row["online"], row["addr"], row["map"]),
                         (1, "127.0.0.1:27511", "surf_elsewhere"))

    def test_ids_past_float32_and_bounded_delivery(self):
        self.befriend(); self.poll()
        self.db.execute("INSERT INTO social_messages(id,sender,recipient,body,sent) VALUES(?,?,?,?,?)",
                        (16777217, IDS[0], IDS[1], "one", self.now))
        for text in ("two", "three"):
            self.db.execute("INSERT INTO social_messages(sender,recipient,body,sent) VALUES(?,?,?,?)",
                            (IDS[0], IDS[1], text, self.now))
        self.db.commit()
        messages = self.poll()[1]["messages"]
        self.assertEqual([m["id"] for m in messages], ["16777217", "16777218"])
        self.assertEqual(self.poll((1,), ack="16777218")[0]["messages"][0]["id"], "16777219")

    def test_friend_limit_rejects_new_but_allows_remove(self):
        self.assertEqual(self.action(0, "add").status_code, 200)
        for i in range(F.MAX_FRIENDS - 1):
            other = "765611981%08d" % i
            self.db.execute("INSERT INTO social_friends(lo,hi,asker) VALUES(?,?,?)",
                            (*F.pair(IDS[0], other), IDS[0]))
        self.db.commit()
        self.assertEqual(self.action(3, "add", 2).status_code, 409)
        self.assertEqual(self.action(0, "remove").status_code, 200)
        self.assertEqual(self.action(3, "add", 2).status_code, 200)

    def test_no_public_or_wrong_secret_reader_and_bad_roster(self):
        self.assertEqual(self.client.get("/api/social/poll").status_code, 405)
        self.assertEqual(self.client.post("/api/social/poll", data=dict(node="p27510", roster="[]")).status_code, 403)
        for roster in ("{}", "broken", json.dumps([dict(token="0" * 64)] * 65),
                       json.dumps([dict(token=self.tokens[0])] * 2),
                       json.dumps([dict(token=self.tokens[0], ack=-1)])):
            self.assertEqual(self.post("/api/social/poll", roster=roster).status_code, 400)

    def test_friend_and_inbox_caps_and_per_account_rate(self):
        self.befriend(); self.poll()
        for i in range(32):
            self.db.execute("INSERT INTO social_messages(sender,recipient,body,sent) VALUES(?,?,?,?)",
                            (IDS[0], IDS[1], "busy", self.now))
        self.db.commit()
        self.assertEqual(self.action(0, "message", text="full").status_code, 429)
        S._rate.clear()
        for _ in range(20): self.action(0, "join")
        self.assertEqual(self.action(3, "join").status_code, 429) # second install shares budget

    def menu_form(self, i=0, op="list", who="-", ip=None):
        args = {} if ip is None else {"environ_overrides": {"REMOTE_ADDR": ip}}
        challenge = self.client.get("/api/social/menu/challenge", query_string=dict(op=op, who=who), **args)
        data = challenge.get_json()
        self.assertEqual(data["ok"], 1, data)
        self.assertEqual(challenge.headers["Cache-Control"], "no-store")
        form = {k: data[k] for k in ("nonce", "expires", "ticket")}
        form.update(op=op, who=who, pub=PUBS[i])
        msg = (F.MENU_STATEMENT % (form["nonce"], op, who)).encode("ascii")
        form["sig"] = ed25519.sign(bytes([i + 1]) * 32, msg).hex()
        return form

    def menu_read(self, form, ip=None):
        args = {} if ip is None else {"environ_overrides": {"REMOTE_ADDR": ip}}
        r = self.client.post("/api/social/menu", data=form, **args)
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        return r.get_json()

    def test_menu_list_and_join_use_private_proof_not_lobby_token(self):
        self.befriend(); self.poll()
        sessions = list(self.db.execute("SELECT * FROM social_sessions"))
        row = self.menu_read(self.menu_form())
        self.assertEqual(row["ok"], 1, row)
        self.assertEqual(row["friends"][0]["name"], "Bob")
        target = A.who_of(IDS[1])
        join = self.menu_read(self.menu_form(op="join", who=target))
        self.assertEqual((join["ok"], join["addr"], join["map"]), (1, "127.0.0.1:27510", "surf_test"))
        self.assertEqual(list(self.db.execute("SELECT * FROM social_sessions")), sessions)
        self.assertNotIn("token", row)
        self.assertNotIn("messages", row)

    def test_menu_legacy_request_redacts_presence_until_a_poll(self):
        self.legacy_request()
        row = self.menu_read(self.menu_form())["friends"][0]
        self.assertEqual((row["relation"], row["online"], row["addr"]), (1, 0, ""))
        self.assertEqual(self.menu_read(self.menu_form(op="join", who=A.who_of(IDS[1])))["status"], 403)
        self.poll()
        S._rate.clear()
        row = self.menu_read(self.menu_form())["friends"][0]
        self.assertEqual((row["relation"], row["online"]), (3, 1))

    def test_menu_invalid_fields_ticket_and_signature_fail_closed(self):
        self.befriend(); self.poll()
        form = self.menu_form()
        for key, value in (("nonce", "A" * 32), ("expires", "9" * 20), ("ticket", "0" * 64),
                           ("pub", "z" * 64), ("sig", "0" * 128), ("who", "12345678"),
                           ("op", "link"), ("op", "remove"), ("op", "message")):
            with self.subTest(key=key, value=value[:12]):
                self.assertEqual(self.menu_read(dict(form, **{key: value}))["ok"], 0)
        self.assertEqual(self.menu_read(form)["ok"], 1) # positive control with same nonce
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM social_friends").fetchone()[0], 1)

    def test_menu_challenge_is_peer_bound_and_expires(self):
        form = self.menu_form(ip="198.51.100.11")
        self.assertEqual(self.menu_read(form, ip="198.51.100.12")["status"], 403)
        self.assertEqual(self.menu_read(form, ip="198.51.100.11")["ok"], 1)
        self.now += F.MENU_TTL + 1
        self.assertEqual(self.menu_read(form, ip="198.51.100.11")["status"], 403)
        self.assertEqual(self.menu_read(self.menu_form())["ok"], 1)

    def test_menu_rechecks_links_bans_and_live_presence_each_read(self):
        self.befriend(); self.poll()
        form = self.menu_form()
        join = self.menu_form(op="join", who=A.who_of(IDS[1]))
        self.assertEqual(self.menu_read(join)["ok"], 1)
        self.db.execute("UPDATE accounts SET banned_at=1 WHERE steamid=?", (IDS[0],)); self.db.commit()
        self.assertEqual(self.menu_read(form)["status"], 403)
        self.db.execute("UPDATE accounts SET banned_at=0 WHERE steamid=?", (IDS[0],)); self.db.commit()
        self.assertEqual(self.menu_read(form)["ok"], 1)
        self.db.execute("DELETE FROM keylinks WHERE pub=?", (PUBS[0],)); self.db.commit()
        self.assertEqual(self.menu_read(form)["status"], 403)
        # A formerly valid request from a different linked install rechecks a
        # friend's disconnect rather than trusting the previously displayed row.
        join = self.menu_form(i=3, op="join", who=A.who_of(IDS[1]))
        self.assertEqual(self.menu_read(join)["ok"], 1)
        self.poll((0, 3))
        self.assertEqual(self.menu_read(join)["status"], 409)

    def test_menu_domain_and_join_target_cannot_be_substituted(self):
        self.befriend(); self.poll()
        form = self.menu_form(op="join", who=A.who_of(IDS[1]))
        self.assertEqual(self.menu_read(form)["ok"], 1)
        other = self.menu_form(op="join", who=A.who_of(IDS[2]))
        other["sig"] = form["sig"]
        self.assertEqual(self.menu_read(other)["ok"], 0)
        # An account statement signed by the same fixture key is not a menu proof.
        form = self.menu_form()
        msg = (A.STATEMENT % ("127.0.0.1:27510", form["nonce"], A.TICKS_HELLO, 0, GAME)).encode()
        form["sig"] = ed25519.sign(bytes([1]) * 32, msg).hex()
        self.assertEqual(self.menu_read(form)["status"], 403)

    def test_menu_real_proxy_identity_is_bound_but_untrusted_header_is_not(self):
        def challenge(peer, claimed):
            return self.client.get("/api/social/menu/challenge?op=list&who=-",
                                   environ_overrides={"REMOTE_ADDR": peer}, headers={"X-Real-IP": claimed}).get_json()
        def submit(form, peer, claimed):
            return self.client.post("/api/social/menu", data=form,
                                    environ_overrides={"REMOTE_ADDR": peer}, headers={"X-Real-IP": claimed}).get_json()
        def signed(ch):
            form = {k: ch[k] for k in ("nonce", "expires", "ticket")}
            form.update(op="list", who="-", pub=PUBS[0])
            form["sig"] = ed25519.sign(bytes([1]) * 32, (F.MENU_STATEMENT % (form["nonce"], "list", "-")).encode()).hex()
            return form
        form = signed(challenge("127.0.0.1", "198.51.100.11"))
        self.assertEqual(submit(form, "127.0.0.1", "198.51.100.12")["status"], 403)
        self.assertEqual(submit(form, "127.0.0.1", "198.51.100.11")["ok"], 1)
        form = signed(challenge("203.0.113.21", "198.51.100.11"))
        # A direct untrusted caller cannot choose its source bucket via a header.
        self.assertEqual(submit(form, "203.0.113.21", "198.51.100.12")["ok"], 1)
        self.assertEqual(submit(form, "203.0.113.22", "198.51.100.11")["status"], 403)
        for _ in range(30): challenge("127.0.0.1", "198.51.100.31")
        self.assertEqual(challenge("127.0.0.1", "198.51.100.31")["status"], 429)
        self.assertEqual(challenge("127.0.0.1", "198.51.100.32")["ok"], 1)

    def test_menu_configured_verifier_in_deployed_service_layout(self):
        import importlib.util
        import types
        from flask import Flask
        game = HOME / "deployed-game"
        tools = game / "tools"
        tools.mkdir(parents=True)
        shutil.copy2(Path(__file__).resolve().parent.parent / "tools/ed25519.py", tools / "ed25519.py")
        service = HOME / "deployed-service"
        service.mkdir()
        shutil.copy2(Path(F.__file__), service / "social.py")
        spec = importlib.util.spec_from_file_location("deployed_social", service / "social.py")
        deployed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deployed)
        for settings in ({"SURFD_TOOLS": str(tools)}, {"SURFD_GAME": str(game)}):
            with self.subTest(settings=settings):
                app = Flask("deployed-social")
                deployed.register(app, types.SimpleNamespace(setting=settings.get, secret=lambda: "testkey",
                    clock=lambda: self.now, rate_key=lambda: "127.0.0.1", rate_ok=lambda *a: True,
                    get_db=lambda: self.db, game_json=S.game_json, clean_text=S.clean_text, lobby_ttl=S.LOBBY_TTL))
                self.client = app.test_client()
                self.assertEqual(self.menu_read(self.menu_form())["ok"], 1)

    def test_menu_rate_caps_and_missing_service_secret(self):
        form = self.menu_form()
        for _ in range(20):
            self.assertEqual(self.menu_read(form)["ok"], 1)
        self.assertEqual(self.menu_read(form)["status"], 429)
        S._rate.clear()
        with patch.object(S, "SECRET", ""):
            self.assertEqual(self.client.get("/api/social/menu/challenge?op=list&who=-").get_json()["ok"], 0)
        for _ in range(30):
            self.client.get("/api/social/menu/challenge?op=list&who=-")
        self.assertEqual(self.client.get("/api/social/menu/challenge?op=list&who=-").get_json()["status"], 429)


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        logging.shutdown()
        shutil.rmtree(HOME)
