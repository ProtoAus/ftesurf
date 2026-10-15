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
                  SURFD_BOARD_URL="https://proto.bar/ftesurf/board")
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

    def accept(self):
        self.assertEqual(self.action(0, "add").status_code, 200)
        self.assertEqual(self.action(1, "accept", 0).status_code, 200)

    def test_proof_mint_and_wrong_proof_no_capability(self):
        r = self.hello(1, old_social=self.tokens[0])
        self.assertEqual(r["social_who"], A.who_of(IDS[0]))
        self.assertNotIn("social", self.hello(1, sig="0" * 128))
        self.assertNotIn("social", self.hello(1, pub=PUBS[1]))
        self.assertNotIn("social", self.hello(1, game="0" * 64))
        self.assertEqual(F.digest(r["social"]), self.db.execute("SELECT token FROM social_sessions WHERE pub=?", (PUBS[0],)).fetchone()[0])
        self.assertNotEqual(r["social"], F.digest(r["social"]))

    def test_requests_acceptance_and_cross_install_identity(self):
        self.assertEqual(self.action(0, "add").status_code, 200)
        rows = self.poll()
        self.assertEqual(rows[0]["friends"], rows[3]["friends"])
        self.assertEqual(rows[0]["friends"][0]["relation"], 1)
        self.assertEqual(rows[1]["friends"][0]["relation"], 2)
        self.assertEqual(rows[1]["friends"][0]["online"], 0)
        self.assertEqual(self.action(0, "accept").status_code, 409)
        self.assertEqual(self.action(1, "accept", 0).status_code, 200)
        self.assertEqual(self.poll()[3]["friends"][0]["relation"], 3)
        self.assertEqual(self.action(3, "remove").status_code, 200)
        self.assertEqual(self.poll()[0]["friends"], [])

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
        self.accept(); self.poll()
        self.db.execute("UPDATE accounts SET banned_at=? WHERE steamid=?", (self.now, IDS[1])); self.db.commit()
        row = self.poll((0,))[0]["friends"][0]
        self.assertEqual((row["name"], row["online"]), ("Unavailable account", 0))
        self.assertEqual(self.action(0, "remove").status_code, 200)
        self.db.execute("UPDATE accounts SET banned_at=0 WHERE steamid=?", (IDS[1],)); self.db.commit()
        self.accept()
        self.db.execute("DELETE FROM accounts WHERE steamid=?", (IDS[1],)); self.db.commit()
        self.assertEqual(self.poll((0,))[0]["friends"][0]["name"], "Unavailable account")
        self.assertEqual(self.action(0, "remove").status_code, 200)

    def test_game_transport_keeps_refusal_text_without_weakening_auth(self):
        r = self.action(0, "join", game="1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.get_json()["ok"], r.get_json()["status"]), (0, 403))
        self.assertEqual(r.get_json()["error"], "Accept the friend request first")
        r = self.client.post("/api/social/action", data=dict(game="1", node="p27510", op="join"))
        self.assertEqual(r.status_code, 403)

    def test_fresh_presence_and_join_revalidated(self):
        self.accept(); self.poll()
        row = self.poll()[0]["friends"][0]
        self.assertEqual((row["online"], row["map"], row["addr"]), (1, "surf_test", "127.0.0.1:27510"))
        self.assertEqual(self.action(0, "join").get_json()["addr"], row["addr"])
        self.now += F.PRESENCE_TTL + 1
        self.assertEqual(self.action(0, "join").status_code, 409)
        self.assertEqual(self.poll((0,))[0]["friends"][0]["online"], 0)

    def test_snapshot_disconnect_and_other_install_still_online(self):
        self.accept(); self.poll()
        # Bob sees Alice through install4 after install1 drops.
        row = self.poll((1, 3))[0]["friends"][0]
        self.assertEqual(row["online"], 1)
        self.assertEqual(self.poll((1,))[0]["friends"][0]["online"], 0)

    def test_directory_staleness_and_map_switch(self):
        self.accept(); self.poll()
        self.heartbeat("p27510", 27510, "surf_new")
        self.assertEqual(self.poll()[0]["friends"][0]["map"], "surf_new")
        self.db.execute("UPDATE lobbies SET last_seen=0"); self.db.commit()
        self.assertEqual(self.poll()[0]["friends"][0]["online"], 0)
        self.assertEqual(self.action(0, "join").status_code, 409)

    def test_incremental_hash_omits_unchanged_list(self):
        self.accept()
        initial = self.poll()
        rows = self.poll(hashes={i: r["hash"] for i, r in enumerate(initial)})
        self.assertTrue(all("friends" not in r for r in rows))
        self.action(0, "remove")
        rows = self.poll(hashes={i: r["hash"] for i, r in enumerate(initial)})
        self.assertEqual(rows[0]["friends"], [])

    def test_message_private_only_to_recipient_with_retry_and_ack(self):
        self.accept(); self.poll()
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
        self.accept(); self.poll()
        self.assertEqual(self.action(0, "message", text="private").status_code, 200)
        self.assertEqual(self.action(1, "remove", 0).status_code, 200)
        self.assertEqual(self.poll()[1]["messages"], [])
        self.assertEqual(self.db.execute("SELECT count(*) FROM social_messages").fetchone()[0], 0)

    def test_message_controls_length_and_expiry(self):
        self.accept(); self.poll()
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
        self.accept(); self.poll()
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
        self.accept(); self.poll()
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
        self.accept(); self.poll()
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
        self.accept(); self.poll()
        for i in range(32):
            self.db.execute("INSERT INTO social_messages(sender,recipient,body,sent) VALUES(?,?,?,?)",
                            (IDS[0], IDS[1], "busy", self.now))
        self.db.commit()
        self.assertEqual(self.action(0, "message", text="full").status_code, 429)
        S._rate.clear()
        for _ in range(20): self.action(0, "join")
        self.assertEqual(self.action(3, "join").status_code, 429) # second install shares budget


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        logging.shutdown()
        shutil.rmtree(HOME)
