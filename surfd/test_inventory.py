#!/usr/bin/env python3
"""Real signed account/lobby routes plus persistent inventory controls."""
import json
import hashlib
from pathlib import Path
import types
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
        event_env = patch.dict(os.environ, {"SURFD_CHRISTMAS_EVENT": "0"})
        event_env.start()
        self.addCleanup(event_env.stop)
        fixture.Friends.setUp(self)
        self.db.execute("DELETE FROM account_event_items")
        self.db.execute("DELETE FROM account_event_grants")
        self.db.execute("DELETE FROM account_items")
        self.db.execute("DELETE FROM account_cosmetics")
        self.db.commit()

    def kit(self, index=0, op="get", **extra):
        return self.post("/api/social/inventory", token=self.tokens[index], op=op, inventory_version="2", **extra)

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
        self.assertEqual(set(public), {"roles", "outline", "hat", "santa", "items"})
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
        self.assertEqual(I.public(self.db, IDS[0]), {"roles": 0, "outline": 0, "hat": 0, "santa": 0, "items": []})
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


    def event_poll(self, indices=(0,), inventory=True, modern=True):
        roster = [{"token": self.tokens[i], "inventory": int(inventory), "inventory_version": 2 if modern else 1} for i in indices]
        return self.post("/api/social/poll", roster=json.dumps(roster))

    def test_christmas_needs_active_trusted_game_presence_not_inventory_reads(self):
        self.assertEqual([r["id"] for r in self.kit().get_json()["items"]], [1, 2])
        self.event_poll()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM account_event_items").fetchone()[0], 0)
        with patch.dict(os.environ, {"SURFD_CHRISTMAS_EVENT": "1"}):
            self.kit(); I.public(self.db, IDS[0])
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM account_event_grants").fetchone()[0], 0)
            earned = self.event_poll().get_json()["players"][0]["inventory"]
        self.assertEqual([r["id"] for r in earned["items"]], [1, 2, 3])
        self.assertEqual(earned["items"][2], {"id": 3, "colour": 0, "equipped": 0})
        self.assertEqual(earned["santa"], 0, 'earning must not auto-equip')
        self.assertEqual(self.kit().get_json()["items"], earned["items"], 'event off must retain gift')

    def test_christmas_idempotent_across_tokens_reconnect_and_legacy_roster(self):
        with patch.dict(os.environ, {"SURFD_CHRISTMAS_EVENT": "1"}):
            reply = self.event_poll((0, 3), inventory=False).get_json()["players"]
            self.assertTrue(all("inventory" not in r for r in reply), 'legacy capability stays opt-in')
            a = self.kit().get_json()
            for i in range(3): self.event_poll((0, 3))
            self.assertEqual(self.kit().get_json(), a)
        self.assertEqual(self.kit(3).get_json(), a)
        self.db.close(); self.db = S.connect(); self.addCleanup(self.db.close)
        self.assertEqual(I.snapshot(self.db, IDS[0])["items"], a["items"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM account_event_items").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM account_event_grants").fetchone()[0], 1)

    def test_christmas_rejects_forged_crossnode_unlinked_and_banned_presence(self):
        roster = json.dumps([{"token": self.tokens[0], "inventory": 1}])
        with patch.dict(os.environ, {"SURFD_CHRISTMAS_EVENT": "1"}):
            bad = self.client.post('/api/social/poll', data=dict(key='not-testkey', node='p27510', roster=roster))
            self.assertEqual(bad.status_code, 403)
            cross = self.client.post('/api/social/poll', data=dict(key='testkey', node='p27511', roster=roster))
            self.assertTrue(cross.get_json()["players"][0].get("invalid"))
            with self.db:
                self.db.execute("UPDATE accounts SET banned_at=1 WHERE steamid=?", (IDS[1],))
                self.db.execute("DELETE FROM keylinks WHERE steamid=?", (IDS[2],))
            self.event_poll((1, 2))
            self.assertFalse(I.grant_christmas_presence(self.db, 'missing-account', 123))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM account_event_items").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM account_event_grants").fetchone()[0], 0)

    def test_christmas_one_head_slot_aura_independent_stale_revision_preserved(self):
        with patch.dict(os.environ, {"SURFD_CHRISTMAS_EVENT": "1"}): self.event_poll()
        self.change(1, 1); self.change(2, 1)
        old = self.kit().get_json()["revision"]
        santa = self.change(3, 1).get_json()
        self.assertEqual((santa["outline"], santa["hat"], santa["santa"]), (1, 0, 1))
        self.assertEqual([r["equipped"] for r in santa["items"]], [1, 0, 1])
        self.assertEqual(self.change(3, 1).get_json()["revision"], santa["revision"])
        self.assertEqual(self.change(2, 1, revision=old).status_code, 409)
        party = self.change(2, 1).get_json()
        self.assertEqual((party["outline"], party["santa"]), (1, 0))
        self.assertGreater(party["hat"], 0)
        self.assertEqual([r["equipped"] for r in party["items"]], [1, 1, 0])

    def test_christmas_legacy_ssqc_gets_only_supported_item_ids(self):
        with patch.dict(os.environ, {"SURFD_CHRISTMAS_EVENT": "1"}): self.event_poll()
        self.change(3, 1)
        legacy = self.event_poll(modern=False).get_json()['players'][0]['inventory']
        self.assertEqual([r['id'] for r in legacy['items']], [1, 2])
        self.assertNotIn('santa', legacy)
        self.assertEqual(legacy['hat'], 0)
        oldget = self.post('/api/social/inventory', token=self.tokens[0], op='get').get_json()
        self.assertEqual(oldget['items'], legacy['items'])
        oldequip = self.post('/api/social/inventory', token=self.tokens[0], op='equip',
                             item='1', on='1', revision=str(oldget['revision'])).get_json()
        self.assertEqual(oldequip['outline'], 1)
        self.assertNotIn('santa', oldequip)
        self.assertEqual(I.public(self.db, IDS[0])['santa'], 1)

    def test_christmas_revoke_does_not_refill_and_keeps_earn_time(self):
        with patch.dict(os.environ, {"SURFD_CHRISTMAS_EVENT": "1"}):
            self.event_poll()
            stamp = self.db.execute("SELECT recorded FROM account_event_grants").fetchone()[0]
            with self.db: I.administer(self.db, IDS[0], "revoke", 3)
            for i in range(3): self.event_poll()
            self.assertNotIn(3, [r["id"] for r in self.kit().get_json()["items"]])
            row = self.db.execute("SELECT recorded,revoked FROM account_event_grants").fetchone()
            self.assertEqual(tuple(row), (stamp, 1))
        with self.db: I.administer(self.db, IDS[0], "grant", 3)
        self.assertIn(3, [r["id"] for r in self.kit().get_json()["items"]], 'operator restore stays possible')

    def test_christmas_legacy_head_conflict_at_revision_limit_stays_read_only(self):
        with patch.dict(os.environ, {"SURFD_CHRISTMAS_EVENT": "1"}): self.event_poll()
        self.change(3, 1)
        with self.db:
            self.db.execute('UPDATE account_items SET equipped=1 WHERE steamid=? AND item=2', (IDS[0],))
            self.db.execute('UPDATE account_cosmetics SET revision=16777215 WHERE steamid=?', (IDS[0],))
        before = list(map(tuple, self.db.execute('SELECT * FROM account_event_items')))
        response = self.event_poll()
        self.assertEqual(response.status_code, 200)
        value = response.get_json()['players'][0]['inventory']
        self.assertEqual((value['revision'], value['santa']), (16777215, 0))
        self.assertEqual([r['equipped'] for r in value['items']], [0, 1, 0])
        self.assertEqual(list(map(tuple, self.db.execute('SELECT * FROM account_event_items'))), before)
        self.assertEqual(self.change(3, 1).status_code, 400)

    @staticmethod
    def core_state(db):
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'"
                  " AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'account_event_%' ORDER BY name")]
        schema = list(map(tuple, db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master"
                    " WHERE tbl_name NOT LIKE 'account_event_%' AND name NOT LIKE 'sqlite_%' ORDER BY type,name")))
        data = {t: sorted(map(tuple, db.execute('SELECT * FROM "' + t.replace('"', '""') + '"')), key=repr) for t in tables}
        return db.execute("PRAGMA user_version").fetchone()[0], schema, data

    def test_event_component_atomic_cuts_leave_all_old_schema_rows_exact(self):
        self.kit()
        for cut in range(6):  # begin, two ownership tables, version table, stamp, commit
            probe = sqlite3.connect(':memory:'); probe.row_factory = sqlite3.Row
            self.db.backup(probe)
            for t in ('account_event_items', 'account_event_grants', 'account_event_schema'):
                probe.execute('DROP TABLE ' + t)
            probe.commit()
            before = self.core_state(probe)

            class Cut:
                def __getattr__(self, name): return getattr(probe, name)
                def executescript(self, sql):
                    for index, statement in enumerate(x.strip() for x in sql.split(';') if x.strip()):
                        if index == cut: raise sqlite3.OperationalError('event component cut')
                        probe.execute(statement)

            with self.assertRaisesRegex(sqlite3.OperationalError, 'event component cut'):
                I.ensure_event_schema(Cut())
            self.assertEqual(self.core_state(probe), before)
            self.assertEqual(probe.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'account_event_%'").fetchone()[0], 0)
            I.ensure_event_schema(probe)
            self.assertEqual(self.core_state(probe), before)
            self.assertEqual(probe.execute('SELECT version FROM account_event_schema').fetchone()[0], 1)
            changes = probe.total_changes
            I.ensure_event_schema(probe)
            self.assertEqual(probe.total_changes, changes)
            probe.close()

    def test_event_component_refuses_future_or_incomplete_data_without_repair(self):
        with patch.dict(os.environ, {"SURFD_CHRISTMAS_EVENT": "1"}): self.event_poll()
        for mode in ('future', 'future-mixed', 'missing', 'missing-column'):
            probe = sqlite3.connect(':memory:'); probe.row_factory = sqlite3.Row
            self.db.backup(probe)
            if mode.startswith('future'):
                probe.executescript('DROP TABLE account_event_schema; CREATE TABLE account_event_schema(version INTEGER); INSERT INTO account_event_schema VALUES(2);')
                if mode == 'future-mixed': probe.execute('INSERT INTO account_event_schema VALUES(1)')
            elif mode == 'missing-column':
                probe.executescript('ALTER TABLE account_event_grants RENAME TO old_grants;'
                    'CREATE TABLE account_event_grants(steamid TEXT,event TEXT,recorded INTEGER);'
                    'INSERT INTO account_event_grants SELECT steamid,event,recorded FROM old_grants; DROP TABLE old_grants;')
            else: probe.execute('DROP TABLE account_event_grants')
            probe.commit()
            before = list(map(tuple, probe.execute('SELECT * FROM account_event_items')))
            names = list(map(tuple, probe.execute("SELECT name,sql FROM sqlite_master ORDER BY name")))
            with self.assertRaisesRegex(RuntimeError, 'Unsupported/incomplete'):
                I.ensure_event_schema(probe)
            self.assertEqual(list(map(tuple, probe.execute('SELECT * FROM account_event_items'))), before)
            self.assertEqual(list(map(tuple, probe.execute("SELECT name,sql FROM sqlite_master ORDER BY name"))), names)
            probe.close()

    def test_event_data_survives_actual_prior_inventory_consumer_and_core_guard(self):
        with patch.dict(os.environ, {"SURFD_CHRISTMAS_EVENT": "1"}): self.event_poll()
        self.change(3, 1)
        data = (Path(__file__).parent / 'testdata/inventory-before-santa.py.txt').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), 'c70f2598cf57f7ae656feb689bc5bc667134fb8287f24bec71f8c6dd907047e2')
        legacy = types.ModuleType('inventory_before_santa')
        exec(compile(data, 'inventory-before-santa.py.txt', 'exec'), legacy.__dict__)
        S._refuse_newer_schema(self.db)  # unchanged actual core guard accepts unchanged26
        self.assertEqual((S.SCHEMA_VERSION, self.db.execute('PRAGMA user_version').fetchone()[0]), (26, 26))
        before = {t: list(map(tuple, self.db.execute('SELECT * FROM ' + t))) for t in ('account_event_items', 'account_event_grants')}
        with self.db:
            legacy.ensure(self.db, IDS[0])
            legacy.equip(self.db, IDS[0], 1, 1, legacy.snapshot(self.db, IDS[0])['revision'])
            legacy.equip(self.db, IDS[0], 2, 1, legacy.snapshot(self.db, IDS[0])['revision'])
        self.assertEqual([r['id'] for r in legacy.snapshot(self.db, IDS[0])['items']], [1, 2])
        for t, rows in before.items(): self.assertEqual(list(map(tuple, self.db.execute('SELECT * FROM ' + t))), rows)
        revision = I.snapshot(self.db, IDS[0])['revision']
        with self.db: I.ensure(self.db, IDS[0])
        restored = I.snapshot(self.db, IDS[0])
        self.assertEqual(restored['revision'], revision + 1)
        self.assertEqual((restored['outline'], restored['santa']), (1, 0))
        self.assertGreater(restored['hat'], 0, 'honour the actual old consumer party-head choice')
        self.assertIn(3, [r['id'] for r in restored['items']], 'only reconcile equipment; gift remains permanent')
        self.assertEqual(list(map(tuple, self.db.execute('SELECT * FROM account_event_grants'))), before['account_event_grants'])
        with self.db: I.equip(self.db, IDS[0], 3, 1, restored['revision'])
        self.assertEqual(I.public(self.db, IDS[0])['santa'], 1)
        self.db.execute('PRAGMA user_version=27')
        with self.assertRaisesRegex(RuntimeError, 'newer than'):
            S._refuse_newer_schema(self.db)  # no weakening of ahead-core refusal
        self.db.execute('PRAGMA user_version=26')  # isolated fixture only; no live DB change


if __name__ == "__main__":
    unittest.main()
