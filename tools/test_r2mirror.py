#!/usr/bin/env python3
"""Offline falsifiers for public-only staging, snapshots, verification and resumption."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest

import r2mirror as m


class FakeTransport:
    def __init__(self):
        self.objects = {}
        self.puts = []
        self.after_put = None
        self.corrupt = False
        self.fail = False

    def put(self, source, key, sha, content_type, immutable=True):
        if self.fail:
            raise m.TransferError("SECRET fixture URL must never be logged")
        raw = Path(source).read_bytes()
        self.puts.append((key, sha, content_type, immutable))
        self.objects[key] = b"wrong" if self.corrupt else raw
        if self.after_put:
            self.after_put()

    def digest(self, key):
        raw = self.objects[key]
        return hashlib.sha256(raw).hexdigest(), len(raw)


class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.maps = self.root / "maps"
        self.zones = self.root / "zones"
        self.work = self.root / "work"
        for p in (self.maps, self.zones, self.work):
            p.mkdir()
        self.config = {"remote": "task:ftesurf-public", "groups": {"maps": str(self.maps), "zones": str(self.zones)}}
        self.db = m.connect(self.work / "state.sqlite")
        self.t = FakeTransport()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def row(self, alias="ftesurf/maps/surf_test.bsp"):
        return self.db.execute("SELECT * FROM assets WHERE alias=?", (alias,)).fetchone()

    def seed(self):
        (self.maps / "surf_test.bsp").write_bytes(b"VBSP-original")
        m.scan(self.db, self.config)

    def copy(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = m.copy_pending(self.db, self.work, self.t, **kwargs)
        return result, output.getvalue()

    def test_allowlist_skips_partials_sidecars_old_and_private_extensions(self):
        self.seed()
        for name in ("surf_other.bsp.part", "private.rec", "secret.txt", "bad name.bsp", "zero.bsp"):
            (self.maps / name).write_bytes(b"" if name == "zero.bsp" else b"PRIVATE")
        (self.maps / ".old").mkdir()
        (self.maps / ".old" / "old.bsp").write_bytes(b"OLD")
        m.scan(self.db, self.config)
        self.assertEqual(m.status(self.db)["groups"]["maps"]["files"], 1)

    def test_actual_hash_named_pictures_and_game_copies_only(self):
        avatars = self.root / "avatars"
        avatars.mkdir()
        h = "ab" * 20
        for name in (h + ".jpg", h + ".txt", h + ".bad", "people.at",
                     "76561198000000001.jpg", "private.txt", h + ".jpg.part"):
            (avatars / name).write_bytes(b"fixture")
        c = {"groups": {"avatars": str(avatars), "avatar_rgba": str(avatars)}}
        m.scan(self.db, c)
        self.assertEqual(self.copy()[0], (2, 0))
        doc = m.publish(self.db, self.work, self.t, "manifests/avatars.json")
        self.assertEqual(set(doc["assets"]), {"avatars/" + h + ".jpg", "avatars/game/" + h + ".txt"})
        self.assertIn("manifests/avatars.json", self.t.objects)
        self.assertNotIn("manifests/public.json", self.t.objects)
        self.assertEqual({p[2] for p in self.t.puts[:-1]}, {"image/jpeg", "text/plain"})

    def test_ramp_allowlist_and_compound_encoded_suffix(self):
        ramps = self.root / 'ramps'
        ramps.mkdir()
        atlas = 'surf_case.' + 'a' * 64 + '.png'
        for leaf in ('surf_case.txt', atlas, atlas + '.b64', 'private.rec', 'surf_case.png', atlas + '.part'):
            (ramps / leaf).write_bytes(b'public-fixture')
        m.scan(self.db, {'groups': {group: str(ramps) for group in ('ramp_geometry', 'ramp_atlas', 'ramp_encoded')}})
        self.assertEqual(self.copy()[0], (3, 0))
        doc = m.publish(self.db, self.work, self.t, 'manifests/rampwear.json')
        self.assertEqual(set(doc['assets']), {'ftesurf/media/rampwear/' + leaf
                                             for leaf in ('surf_case.txt', atlas, atlas + '.b64')})
        encoded = doc['assets']['ftesurf/media/rampwear/' + atlas + '.b64']
        self.assertEqual(encoded['key'], 'objects/ramp_encoded/' + encoded['sha256'] + '.png.b64')
        self.assertTrue(doc['complete'])

    def test_parallel_workers_act_and_keep_one_ledger(self):
        self.seed()
        (self.maps / 'surf_second.bsp').write_bytes(b'VBSP-second')
        m.scan(self.db, self.config)
        barrier, lock = threading.Barrier(2), threading.Lock()
        active, peak = [0], [0]

        def overlap():
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            barrier.wait(timeout=10)  # serial execution cannot pass this control
            with lock:
                active[0] -= 1

        self.t.after_put = overlap
        self.assertEqual(self.copy(workers=2)[0], (2, 0))
        self.assertEqual(peak[0], 2)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM assets WHERE state='verified'").fetchone()[0], 2)
        self.assertFalse(list(self.work.glob('body-*.part')))

    def test_parallel_errors_remain_errors_and_worker_bounds_refuse(self):
        self.seed()
        (self.maps / 'surf_second.bsp').write_bytes(b'VBSP-second')
        m.scan(self.db, self.config)
        for workers in (0, 9):
            with self.assertRaises(ValueError):
                self.copy(workers=workers)
        self.assertEqual(self.t.puts, [])
        self.t.fail = True
        result, output = self.copy(workers=2)
        self.assertEqual(result, (2, 2))
        self.assertNotIn('SECRET', output)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM assets WHERE state='error'").fetchone()[0], 2)

    def test_manifest_path_is_allowlisted(self):
        p = self.root / "config.json"
        for bad in ("../private.json", "objects/maps/existing.bsp", "manifests/x.json\n"):
            p.write_text(json.dumps({**self.config, "manifest": bad}))
            with self.assertRaises(ValueError):
                m.load_config(p)

    def test_symlink_file_is_not_an_asset(self):
        self.seed()
        try:
            (self.maps / "linked.bsp").symlink_to(self.maps / "surf_test.bsp")
        except OSError:
            self.skipTest("OS does not permit symlink creation")
        m.scan(self.db, self.config)
        self.assertIsNone(self.row("ftesurf/maps/linked.bsp"))

    def test_symlink_source_directory_is_refused(self):
        try:
            (self.root / "linked").symlink_to(self.maps, target_is_directory=True)
        except OSError:
            self.skipTest("OS does not permit symlink creation")
        with self.assertRaises(ValueError):
            m.scan(self.db, {"groups": {"maps": str(self.root / "linked")}})

    def test_public_config_refuses_recordings_group(self):
        p = self.root / "config.json"
        p.write_text(json.dumps({"remote": "task:ftesurf-public", "groups": {"runs": str(self.maps)}}))
        with self.assertRaises(ValueError):
            m.load_config(p)

    def test_remote_must_name_explicit_bucket(self):
        p = self.root / "config.json"
        p.write_text(json.dumps({"remote": "task:", "groups": {"maps": str(self.maps)}}))
        with self.assertRaises(ValueError):
            m.load_config(p)

    def test_failed_enumeration_does_not_hide_previous_inventory(self):
        self.seed()
        old = dict(self.row())
        with self.assertRaises(OSError):
            m.scan(self.db, {"groups": {"maps": str(self.root / "absent")}})
        self.assertEqual(dict(self.row()), old)

    def test_inventory_minimum_refuses_empty_or_wiped_source(self):
        self.seed()
        config = {**self.config, "minimum_files": {"maps": 2}}
        before = dict(self.row())
        with self.assertRaises(ValueError):
            m.scan(self.db, config)
        self.assertEqual(dict(self.row()), before)

    def inventory(self):
        return [tuple(row) for row in self.db.execute("SELECT * FROM assets ORDER BY alias")]

    def test_selected_scan_new_stale_and_unchanged_verified(self):
        self.seed()
        self.assertEqual(self.copy()[0], (1, 0))
        alias = "ftesurf/maps/surf_test.bsp"
        before = dict(self.row())
        self.assertEqual(m.scan(self.db, self.config, only=[alias]), 1)
        self.assertEqual(dict(self.row()), before)
        (self.maps / "surf_test.bsp").write_bytes(b"VBSP-new-current-body")
        (self.maps / "surf_new.bsp").write_bytes(b"VBSP-new")
        self.assertEqual(m.scan(self.db, self.config,
                                only=[alias, "ftesurf/maps/surf_new.bsp"]), 2)
        for name in (alias, "ftesurf/maps/surf_new.bsp"):
            row = self.row(name)
            self.assertEqual(row["state"], "pending")
            self.assertEqual(row["present"], 1)
            self.assertEqual(row["sha"], "")
            self.assertEqual(row["object_key"], "")
            self.assertEqual(row["verified_at"], "")
            self.assertEqual(row["error"], "")
            self.assertEqual(row["sig"], m.signature(Path(row["source"]).stat()))
            self.assertEqual(row["bytes"], Path(row["source"]).stat().st_size)
        # A different configured source root also refreshes the selected row.
        replacement = self.root / "replacement"
        replacement.mkdir()
        (replacement / "surf_new.bsp").write_bytes(b"VBSP-other-root")
        config = {"groups": {"maps": str(replacement)}}
        m.scan(self.db, config, only=("ftesurf/maps/surf_new.bsp",))
        self.assertEqual(self.row("ftesurf/maps/surf_new.bsp")["source"],
                         str(replacement / "surf_new.bsp"))

    def test_selected_scan_preserves_every_unselected_column(self):
        self.seed()
        for name in ("surf_absent.bsp", "surf_changed.bsp", "surf_hidden.bsp"):
            (self.maps / name).write_bytes(b"VBSP-fixture")
        m.scan(self.db, self.config)
        self.assertEqual(self.copy()[0], (4, 0))
        with self.db:
            self.db.execute("UPDATE assets SET present=0, state='error', error='fixture-error' "
                            "WHERE alias='ftesurf/maps/surf_hidden.bsp'")
        before = {row[0]: row for row in self.inventory()}
        (self.maps / "surf_absent.bsp").unlink()
        (self.maps / "surf_changed.bsp").write_bytes(b"VBSP-changed-body")
        (self.maps / "surf_added.bsp").write_bytes(b"VBSP-added")
        with self.db:
            self.db.execute("UPDATE assets SET state='error' WHERE alias=?",
                            ("ftesurf/maps/surf_test.bsp",))
        self.assertEqual(m.scan(self.db, self.config,
                                only={"ftesurf/maps/surf_test.bsp"}), 1)
        self.assertEqual(self.row()["state"], "pending")
        after = {row[0]: row for row in self.inventory()}
        self.assertEqual(set(after), set(before))
        for alias in before:
            if alias != "ftesurf/maps/surf_test.bsp":
                self.assertEqual(after[alias], before[alias])

    def test_selected_scan_minimum_counts_full_inventory(self):
        self.seed()
        (self.maps / "surf_second.bsp").write_bytes(b"VBSP-second")
        config = {**self.config, "minimum_files": {"maps": 2}}
        self.assertEqual(m.scan(self.db, config,
                                only=frozenset({"ftesurf/maps/surf_test.bsp"})), 1)
        self.assertIsNone(self.row("ftesurf/maps/surf_second.bsp"))
        before = self.inventory()
        config["minimum_files"]["maps"] = 3
        with self.assertRaises(ValueError):
            m.scan(self.db, config, only=["ftesurf/maps/surf_test.bsp"])
        self.assertEqual(self.inventory(), before)

    def test_selected_scan_invalid_or_missing_aliases_never_write(self):
        self.seed()
        alias = "ftesurf/maps/surf_test.bsp"
        (self.maps / "zero.bsp").write_bytes(b"")
        (self.maps / "directory.bsp").mkdir()
        before = self.inventory()
        cases = ([], (), set(), alias, {alias: True}, 1, [1], [alias, alias],
                 ["surf_test.bsp"], ["maps/surf_test.bsp"], [alias + "\n"],
                 ["ftesurf/maps/../surf_test.bsp"], ["ftesurf/maps/sub/test.bsp"],
                 ["ftesurf/maps/zero.bsp"], ["ftesurf/maps/directory.bsp"],
                 [alias, "ftesurf/maps/missing.bsp"], ["avatars/" + "a" * 40 + ".jpg"],
                 ["ftesurf/maps/private.rec"], ["ftesurf/maps/Surf_test.bsp"])
        for only in cases:
            with self.subTest(only=only):
                with self.assertRaises(ValueError):
                    m.scan(self.db, self.config, only=only)
                self.assertEqual(self.inventory(), before)
        # Even a valid selection cannot hide a failing unselected root/group.
        for group, root, error in (("zones", self.root / "absent", OSError),
                                   ("private", self.maps, KeyError)):
            with self.subTest(group=group):
                config = {"groups": {"maps": str(self.maps), group: str(root)}}
                with self.assertRaises(error):
                    m.scan(self.db, config, only=[alias])
                self.assertEqual(self.inventory(), before)

    def test_default_scan_still_refreshes_global_presence(self):
        self.seed()
        (self.maps / "surf_test.bsp").unlink()
        (self.maps / "surf_new.bsp").write_bytes(b"VBSP-new")
        self.assertEqual(m.scan(self.db, self.config), 1)
        self.assertEqual(self.row()["present"], 0)
        self.assertEqual(self.row("ftesurf/maps/surf_new.bsp")["state"], "pending")

    def test_upload_and_whole_body_verification_control_acted(self):
        self.seed()
        (result, _) = self.copy()
        self.assertEqual(result, (1, 0))
        row = self.row()
        expected = hashlib.sha256(b"VBSP-original").hexdigest()
        self.assertEqual(row["state"], "verified")
        self.assertEqual(row["object_key"], "objects/maps/" + expected + ".bsp")
        self.assertEqual(self.t.objects[row["object_key"]], b"VBSP-original")
        self.assertEqual(len(self.t.puts), 1)
        self.assertTrue(m.status(self.db)["catalog_complete"])
        self.assertEqual(list(self.work.glob("*.part")), [])

    def test_wrong_download_never_marks_verified(self):
        self.seed()
        self.t.corrupt = True
        result, _ = self.copy()
        self.assertEqual(result, (1, 1))
        self.assertEqual(self.row()["state"], "error")
        self.assertFalse(m.status(self.db)["catalog_complete"])
        self.assertEqual(m.catalogue(self.db)["assets"], {})
        self.assertEqual(len(self.t.puts), 1)

    def test_transport_failure_is_sanitised_and_resumable(self):
        self.seed()
        self.t.fail = True
        result, log = self.copy()
        self.assertEqual(result, (1, 1))
        self.assertNotIn("SECRET", log)
        self.assertNotIn(str(self.maps), log)
        self.assertEqual(self.row()["error"], "TransferError")
        self.t.fail = False
        m.scan(self.db, self.config)
        self.assertEqual(self.copy()[0], (1, 0))

    def test_already_verified_body_is_not_reuploaded(self):
        self.seed()
        self.copy()
        m.scan(self.db, self.config)
        self.assertEqual(self.copy()[0], (0, 0))
        self.assertEqual(len(self.t.puts), 1)

    def test_source_changed_before_capture_is_refused(self):
        self.seed()
        (self.maps / "surf_test.bsp").write_bytes(b"VBSP-different")
        self.assertEqual(self.copy()[0], (1, 1))
        self.assertEqual(self.t.puts, [])

    def test_source_changed_during_upload_never_publishes_stale_alias(self):
        self.seed()
        self.t.after_put = lambda: (self.maps / "surf_test.bsp").write_bytes(b"VBSP-replaced")
        self.assertEqual(self.copy()[0], (1, 1))
        self.assertEqual(m.catalogue(self.db)["assets"], {})
        self.assertEqual(len(self.t.puts), 1)
        self.t.after_put = None
        m.scan(self.db, self.config)
        self.assertEqual(self.copy()[0], (1, 0))
        self.assertEqual(len(self.t.objects), 2)  # Retain the old immutable object.
        self.assertEqual(self.t.objects[self.row()["object_key"]], b"VBSP-replaced")

    def test_later_replacement_invalidates_export_and_keeps_old_body(self):
        self.seed()
        self.copy()
        oldkey = self.row()["object_key"]
        replacement = self.maps / "swap.part"
        replacement.write_bytes(b"VBSP-original")  # Same size/bytes, different inode.
        replacement.replace(self.maps / "surf_test.bsp")
        doc = m.catalogue(self.db)
        self.assertFalse(doc["complete"])
        self.assertEqual(doc["assets"], {})
        self.assertIn(oldkey, self.t.objects)

    def test_removed_source_is_not_exported_or_deleted_remotely(self):
        self.seed()
        self.copy()
        oldkey = self.row()["object_key"]
        (self.maps / "surf_test.bsp").unlink()
        m.scan(self.db, self.config)
        self.assertEqual(m.catalogue(self.db)["assets"], {})
        self.assertIn(oldkey, self.t.objects)

    def test_exact_case_and_both_engine_route_mapping_inputs(self):
        (self.maps / "Surf_Case.bsp").write_bytes(b"VBSP-case")
        (self.zones / "Surf_Case.json").write_bytes(b'{"tracks":[]}')
        m.scan(self.db, self.config)
        self.copy()
        doc = m.catalogue(self.db)
        self.assertIn("ftesurf/maps/Surf_Case.bsp", doc["assets"])
        self.assertIn("ftesurf/maps/zones/local/Surf_Case.json", doc["assets"])
        self.assertNotIn("ftesurf/maps/surf_case.bsp", doc["assets"])

    def test_manifest_has_only_public_fields_and_no_local_paths(self):
        self.seed()
        self.copy()
        doc = m.publish(self.db, self.work, self.t)
        raw = self.t.objects["manifests/public.json"].decode()
        self.assertTrue(doc["complete"])
        self.assertNotIn(str(self.root), raw)
        self.assertNotIn("source", raw)
        self.assertEqual(set(doc["assets"]["ftesurf/maps/surf_test.bsp"]), {"key", "sha256", "bytes", "type"})
        self.assertFalse(self.t.puts[-1][3])  # Catalogue is mutable, bodies are not.

    def test_no_false_ready_with_only_some_bodies_uploaded(self):
        self.seed()
        (self.maps / "surf_two.bsp").write_bytes(b"VBSP-two")
        m.scan(self.db, self.config)
        self.copy(limit=1)
        self.assertFalse(m.publish(self.db, self.work, self.t)["complete"])
        self.assertEqual(len(self.t.objects), 2)  # One body and the incomplete catalogue.

    def test_audit_finds_remote_corruption(self):
        self.seed()
        self.copy()
        self.assertEqual(m.audit(self.db, self.t), 0)
        self.t.objects[self.row()["object_key"]] = b"broken"
        self.assertEqual(m.audit(self.db, self.t), 1)
        self.assertFalse(m.status(self.db)["catalog_complete"])

    def test_working_set_and_group_limit(self):
        self.seed()
        (self.zones / "surf_test.json").write_bytes(b"{}")
        m.scan(self.db, self.config)
        self.assertEqual(self.copy(group="zones", limit=1)[0], (1, 0))
        self.assertEqual(self.row()["state"], "pending")
        self.assertEqual(list(self.work.glob("body-*")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
