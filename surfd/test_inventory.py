#!/usr/bin/env python3
"""Real signed account/lobby routes plus persistent inventory controls."""
import json
import os
import logging
import sqlite3
from flask import Flask
from unittest.mock import patch
import admin
import unittest
import test_social as fixture
import inventory as I

S, IDS = fixture.S, fixture.IDS


class InventoryTests(unittest.TestCase):
    hello = fixture.Friends.hello
    heartbeat = fixture.Friends.heartbeat
    post = fixture.Friends.post

    def setUp(self):
        fixture.Friends.setUp(self)
        self.db.execute("DELETE FROM account_items")
        self.db.execute("DELETE FROM account_cosmetics")
        self.db.commit()

    def kit(self, index=0, op="get", **extra):
        return self.post("/api/social/inventory", token=self.tokens[index], op=op, **extra)

    def change(self, item, on, index=0, revision=None):
        if revision is None:
            revision = self.kit(index).get_json()["revision"]
        return self.kit(index, "equip", item=str(item), on=str(on), revision=str(revision))

    def test_starter_grant_control_persistent_colour_and_separate_equipment(self):
        a = self.kit().get_json()
        self.assertEqual((a["ok"], a["roles"], a["outline"], a["hat"], a["revision"]), (1, 1, 0, 0, 2))
        self.assertEqual([r["id"] for r in a["items"]], [1, 2])
        colour = a["items"][1]["colour"]
        self.assertIn(colour, range(12))
        self.assertEqual(self.change(1, 1).get_json()["outline"], 1)
        both = self.change(2, 1).get_json()
        self.assertEqual((both["outline"], both["hat"]), (1, colour + 1))
        off = self.change(1, 0).get_json()
        self.assertEqual((off["outline"], off["hat"]), (0, colour + 1))
        # Real second install proof, same Steam account, no recolour or regrant.
        self.assertEqual(self.kit(3).get_json(), self.kit().get_json())
        self.assertEqual(self.kit().get_json()["items"][1]["colour"], colour)
        self.assertEqual(self.kit(1).get_json()["outline"], 0)
        self.db.close()
        self.db = S.connect()
        self.addCleanup(self.db.close)
        self.assertEqual(I.public(self.db, IDS[0])["hat"], colour + 1)

    def test_public_inventory_includes_unequipped_owned_items_read_only(self):
        private = self.kit().get_json()
        before = list(map(tuple, self.db.execute("SELECT * FROM account_items ORDER BY steamid,item")))
        public = I.public(self.db, IDS[0])
        self.assertEqual(public["items"], private["items"])
        self.assertEqual([r["id"] for r in public["items"]], [1, 2])
        self.assertTrue(all(r["equipped"] == 0 for r in public["items"]))
        self.assertEqual((public["outline"], public["hat"]), (0, 0))
        self.assertEqual(set(public), {"roles", "outline", "hat", "items"})
        self.assertEqual(list(map(tuple, self.db.execute("SELECT * FROM account_items ORDER BY steamid,item"))), before)
        self.change(2, 1)
        self.assertEqual(I.public(self.db, IDS[0])["items"][1]["equipped"], 1)
        self.change(2, 0)
        self.assertEqual(len(I.public(self.db, IDS[0])["items"]), 2)

    def test_stale_revision_fails_no_optimistic_public_change(self):
        revision = self.kit().get_json()["revision"]
        self.assertEqual(self.change(1, 1, revision=revision).status_code, 200)
        self.assertEqual(self.change(2, 1, revision=revision).status_code, 409)
        self.assertEqual(self.kit().get_json()["hat"], 0)
        before = self.kit().get_json()["revision"]
        self.assertEqual(self.change(1, 1).get_json()["revision"], before)  # idempotent

    def test_no_client_role_grant_or_forged_items(self):
        before = self.kit().get_json()
        for item, on, revision in ((3, 1, 2), (1, 2, 2), (-1, 1, 2), ("1.0", 1, 2),
                                   (1, 1, "nan"), (1, 1, "2&steamid=other")):
            self.assertEqual(self.kit(op="equip", item=str(item), on=str(on), revision=str(revision)).status_code, 400)
        self.assertEqual(self.kit(op="grant", item="1", roles="7").status_code, 400)
        self.assertEqual(self.kit(roles="7", steamid=IDS[1]).get_json(), before)
        self.assertEqual(self.post("/api/social/inventory", token="0" * 64, op="get").status_code, 403)
        r = self.client.post("/api/social/inventory", data=dict(key="testkey", node="p27511", token=self.tokens[0], op="get"))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.post("/api/social/inventory", data=dict(op="get")).status_code, 403)

    def test_operator_badges_revoke_and_no_refill(self):
        self.kit()
        with self.db:
            I.administer(self.db, IDS[0], "add-role", "developer")
            I.administer(self.db, IDS[1], "add-role", "zoner")
        self.assertEqual(self.kit().get_json()["roles"], 5)
        self.assertEqual(self.kit(1).get_json()["roles"], 3)
        self.change(2, 1)
        with self.db:
            I.administer(self.db, IDS[0], "revoke", 2)
        self.assertEqual(self.kit().get_json()["hat"], 0)
        self.assertEqual([r["id"] for r in self.kit().get_json()["items"]], [1])
        self.assertEqual(self.change(2, 1).status_code, 400)
        with self.db:
            I.administer(self.db, IDS[0], "grant", 2)
            I.administer(self.db, IDS[0], "remove-role", "developer")
        self.assertEqual(self.kit().get_json()["roles"], 1)
        self.assertEqual(len(self.kit().get_json()["items"]), 2)
        for op, value in (("add-role", "admin"), ("grant", "models/hat.iqm"), ("grant", True)):
            with self.assertRaises(ValueError), self.db:
                I.administer(self.db, IDS[0], op, value)

    def test_poll_publishes_kit_only_to_owner_and_legacy_safe(self):
        roster = [dict(token=self.tokens[0], hash="", inventory=1), dict(token=self.tokens[1], hash="")]
        r = self.post("/api/social/poll", roster=json.dumps(roster)).get_json()
        self.assertEqual(r["players"][0]["inventory"]["roles"], 1)
        self.assertNotIn("inventory", r["players"][1])
        self.assertEqual(I.public(self.db, IDS[1])["roles"], 1)  # all linked get Tester
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM account_cosmetics").fetchone()[0], 1)
        self.change(1, 1)
        self.assertEqual(I.public(self.db, IDS[0])["outline"], 1)

    def test_unlink_ban_revision_overflow_fail_closed(self):
        self.kit()
        self.change(1, 1)
        with self.db:
            self.db.execute("DELETE FROM keylinks WHERE steamid=?", (IDS[0],))
        self.assertEqual(I.public(self.db, IDS[0]), {"roles": 0, "outline": 0, "hat": 0, "items": []})
        self.assertEqual(self.kit().status_code, 403)
        self.kit(1)
        with self.db:
            self.db.execute("UPDATE accounts SET banned_at=1 WHERE steamid=?", (IDS[1],))
        self.assertEqual(self.kit(1).status_code, 403)
        self.kit(2)
        with self.db:
            self.db.execute("UPDATE account_cosmetics SET revision=16777215 WHERE steamid=?", (IDS[2],))
        self.assertEqual(self.change(1, 1, index=2).status_code, 400)
        self.assertEqual(self.kit(2).get_json()["outline"], 0)

    def test_operator_route_requires_session_csrf_same_origin_and_exact_account(self):
        app = Flask("inventory-admin-fixture")
        config = dict(SURFD_ADMIN_HASH=admin.hash_password("inventory-fixture"),
                      SURFD_ADMIN_SECRET="s" * 48, SURFD_ADMIN_INSECURE_COOKIE="1")
        with patch.dict(os.environ, config):
            bp = admin.build_blueprint(app, logging.getLogger("fixture"), S.connect, 30,
                bans=dict(ban_list=fixture.A.ban_list, imported=S.TIERS_IMPORTED, ranked_linked=True))
        app.register_blueprint(bp)
        c = app.test_client()
        form = dict(steamid=IDS[0], action="add-role", value="developer")
        self.assertEqual(c.post("/admin/api/inventory", data=form).status_code, 401)
        c.get("/admin/login")
        with c.session_transaction(path="/admin") as sess:
            token = sess["csrf"]
        self.assertEqual(c.post("/admin/login", data=dict(password="inventory-fixture", csrf=token)).status_code, 302)
        self.assertEqual(c.post("/admin/api/inventory", data=form).status_code, 400)
        with c.session_transaction(path="/admin") as sess:
            form["csrf"] = sess["csrf"]
        self.assertEqual(c.post("/admin/api/inventory", data=form, headers={"Sec-Fetch-Site": "same-site"}).status_code, 403)
        self.assertEqual(c.post("/admin/api/inventory", data=form, headers={"Sec-Fetch-Site": "same-origin"}).get_json()["ok"], True)
        self.assertEqual(self.kit().get_json()["roles"], 5)
        self.assertEqual(self.kit(1).get_json()["roles"], 1)
        form["steamid"] = "Alice"
        self.assertEqual(c.post("/admin/api/inventory", data=form).status_code, 400)
        rows = c.get("/admin/api/accounts").get_json()
        self.assertTrue(rows["ok"])
        self.assertTrue(any(r["cosmetics"]["roles"] == 5 for r in rows["accounts"]))
        self.assertEqual(c.get("/admin/accounts").status_code, 200)

    def test_schema24_migration_transaction_cuts_preserve_accounts(self):
        before = list(map(tuple, self.db.execute("SELECT * FROM accounts ORDER BY steamid")))
        original_connect = S.connect
        for cut in ("CREATE TABLE IF NOT EXISTS account_items", "COMMIT"):
            with self.db:
                self.db.execute("DROP TABLE account_items")
                self.db.execute("DROP TABLE account_cosmetics")
                self.db.execute("PRAGMA user_version=24")
            acted = []

            class CutConnection:
                def __init__(self):
                    self.conn = original_connect()

                def __getattr__(self, name):
                    return getattr(self.conn, name)

                def executescript(self, sql):
                    if "account_cosmetics" not in sql:
                        return self.conn.executescript(sql)
                    for statement in sql.split(";"):
                        if statement.strip().startswith(cut):
                            acted.append(cut)
                            raise sqlite3.OperationalError("fixture migration cut")
                        if statement.strip():
                            self.conn.execute(statement)

            with patch.object(S, "connect", CutConnection):
                with self.assertRaisesRegex(sqlite3.OperationalError, "fixture migration cut"):
                    S.migrate()
            self.assertEqual(acted, [cut])
            self.assertEqual(self.db.execute("PRAGMA user_version").fetchone()[0], 24)
            names = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn("account_cosmetics", names)
            self.assertNotIn("account_items", names)
            self.assertEqual(list(map(tuple, self.db.execute("SELECT * FROM accounts ORDER BY steamid"))), before)
            S.migrate()
            self.assertEqual(self.db.execute("PRAGMA user_version").fetchone()[0], 26)
        self.assertEqual(self.kit().get_json()["roles"], 1)

    def test_schema_constraints_and_preservation(self):
        self.kit()
        self.assertEqual(self.db.execute("PRAGMA user_version").fetchone()[0], 26)
        for table in ("accounts", "keylinks", "runs", "lobbies"):
            before = list(map(tuple, self.db.execute("SELECT * FROM " + table)))
            with self.db:
                I.administer(self.db, IDS[0], "add-role", "zoner")
            self.assertEqual(list(map(tuple, self.db.execute("SELECT * FROM " + table))), before)
        for sql in ("UPDATE account_items SET colour=12", "UPDATE account_items SET equipped=2",
                    "UPDATE account_cosmetics SET badges=1", "UPDATE account_cosmetics SET revision=16777216"):
            with self.assertRaises(sqlite3.IntegrityError), self.db:
                self.db.execute(sql)


if __name__ == "__main__":
    unittest.main()
