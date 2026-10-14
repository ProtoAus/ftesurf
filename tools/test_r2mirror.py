#!/usr/bin/env python3
"""Offline falsifiers for public-only staging, snapshots, verification and resumption."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
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
