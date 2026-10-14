#!/usr/bin/env python3
"""Synthetic, offline presentation controls; --work-root must be a fresh owned path."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import present

WORK_ROOT = None


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.site = WORK_ROOT / self._testMethodName
        self.site.mkdir()
        (self.site / "OWNER.md").write_text("Synthetic presentation test; disposable after suite.\n")
        for directory in ("releases/0.1.25", "presentations", ".incoming"):
            (self.site / directory).mkdir(parents=True, exist_ok=True)
        (self.site / ".publish.lock").touch()
        self.old = self.site / "releases/0.1.25"
        for name, value in {"index.html": "old landing", "anticheat.html": "old policy",
                            "site.css": "old css", "version.json": "exact receipt",
                            "update.json": "exact signed feed", "update-verified.json": "exact verification",
                            "site.js": "unchanged script", "nested/keep.bin": "unchanged nested"}.items():
            path = self.old / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        self.expected = present.manifest(self.old)
        self.source = self.site / ".incoming" / "brand-01"
        shutil.copytree(self.old, self.source)
        (self.source / "index.html").write_text("World of Surf")
        (self.source / "favicon.svg").write_text("<svg/>")
        (self.site / "static").symlink_to("releases/0.1.25")

    def publish(self, **kwargs):
        return present.publish(self.site, "brand-01", "releases/0.1.25", self.expected, **kwargs)

    def refused(self):
        with self.assertRaises((present.PublicationError, OSError)):
            self.publish()
        self.assertEqual(os.readlink(self.site / "static"), "releases/0.1.25")
        self.assertFalse((self.site / "presentations/brand-01").exists())

    def test_success_and_second_generation_preserve_history(self):
        old_hashes = present.manifest(self.old)
        self.assertEqual((self.site / "static/index.html").read_text(), "old landing")
        result = self.publish()
        new = self.site / result["target"]
        self.assertEqual(result["rollback_pointer"], "releases/0.1.25")
        self.assertEqual((self.site / "static/index.html").read_text(), "World of Surf")
        self.assertFalse(self.source.exists())
        self.assertEqual(present.manifest(self.old), old_hashes)
        for name in present.PROTECTED | {"site.js", "nested/keep.bin"}:
            self.assertEqual((new / name).read_bytes(), (self.old / name).read_bytes())
        self.assertTrue(all((new / name).stat().st_mode & 0o444 == 0o444 for name in self.expected))
        previous = present.manifest(new)
        source2 = self.site / ".incoming/brand-02"
        shutil.copytree(new, source2)
        (source2 / "site.css").write_text("second css")
        result2 = present.publish(self.site, "brand-02", result["target"], previous)
        self.assertEqual(result2["rollback_pointer"], result["target"])
        self.assertEqual(present.manifest(new), previous)
        self.assertEqual(present.manifest(self.old), old_hashes)
        self.assertEqual((self.site / "static/site.css").read_text(), "second css")

    def test_dry_run_no_mutations(self):
        before = self.snapshot()
        result = self.publish(dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(before, self.snapshot())

    def snapshot(self):
        return {str(p.relative_to(self.site)): (p.lstat().st_mode, p.lstat().st_mtime_ns,
                os.readlink(p) if p.is_symlink() else p.read_bytes() if p.is_file() else None)
                for p in self.site.rglob("*")}

    def test_feed_receipt_and_unknown_changes(self):
        for name in (*present.PROTECTED, "site.js", "private.txt"):
            with self.subTest(name=name):
                path = self.source / name
                before = path.read_bytes() if path.exists() else None
                path.write_text("altered")
                self.refused()
                if before is None:
                    path.unlink()
                else:
                    path.write_bytes(before)

    def test_removal(self):
        (self.source / "site.js").unlink()
        self.refused()

    def test_tokens_and_missing_index(self):
        (self.source / "index.html").write_text("@@VERSION@@")
        self.refused()
        (self.source / "index.html").unlink()
        self.refused()

    def test_stale_whole_manifest(self):
        (self.old / "nested/keep.bin").write_text("concurrent change")
        self.refused()

    def test_stale_feed(self):
        (self.old / "update.json").write_text("concurrent feed")
        self.refused()

    def test_stale_pointer(self):
        (self.site / "static").unlink()
        (self.site / "static").symlink_to("releases/0.1.26")
        with self.assertRaisesRegex(present.PublicationError, "stale"):
            self.publish()
        self.assertEqual(os.readlink(self.site / "static"), "releases/0.1.26")

    def test_invalid_pointer(self):
        (self.site / "static").unlink()
        (self.site / "static").symlink_to("../outside")
        with self.assertRaises(present.PublicationError):
            self.publish()

    def test_same_generation(self):
        (self.site / "presentations/brand-01").mkdir()
        with self.assertRaises(present.PublicationError):
            self.publish()
        self.assertEqual(os.readlink(self.site / "static"), "releases/0.1.25")

    def test_link_descendant_and_hardlink(self):
        sentinel = self.site / "sentinel"
        sentinel.write_text("keep")
        link = self.source / "unknown"
        for kind in ("file", "directory", "dangling", "hard"):
            with self.subTest(kind=kind):
                if kind == "hard":
                    os.link(sentinel, link)
                else:
                    link.symlink_to(self.old if kind == "directory" else sentinel if kind == "file" else "missing")
                self.refused()
                link.unlink()
                self.assertEqual(sentinel.read_text(), "keep")

    def test_linked_incoming_root(self):
        parked = self.site / "parked"
        self.source.rename(parked)
        self.source.symlink_to(parked, target_is_directory=True)
        self.refused()
        self.assertEqual((parked / "index.html").read_text(), "World of Surf")

    def test_linked_site_and_ancestor(self):
        alias = WORK_ROOT / "site-alias"
        alias.symlink_to(self.site, target_is_directory=True)
        try:
            for site in (alias, alias / ".incoming/.."):
                with self.assertRaises(present.PublicationError):
                    present.publish(site, "brand-01", "releases/0.1.25", self.expected)
        finally:
            alias.unlink()

    def test_linked_setup_and_current_roots(self):
        for relative in ("presentations", ".incoming", "releases", ".publish.lock"):
            with self.subTest(relative=relative):
                original = self.site / relative
                parked = self.site / (relative + "-parked")
                original.rename(parked)
                original.symlink_to(parked, target_is_directory=parked.is_dir())
                self.refused()
                original.unlink()
                parked.rename(original)

    def test_special_file(self):
        os.mkfifo(self.source / "pipe")
        self.refused()

    def test_permission_and_setup_failure(self):
        with patch.object(present.os, "chmod", side_effect=PermissionError(13, "synthetic")):
            self.refused()
        (self.site / "presentations").rmdir()
        self.refused()

    def test_swap_failure_preserves_old_and_new_history(self):
        with patch.object(present.os, "replace", side_effect=PermissionError(13, "synthetic")):
            with self.assertRaises(present.PublicationError):
                self.publish()
        self.assertEqual(os.readlink(self.site / "static"), "releases/0.1.25")
        self.assertEqual(present.manifest(self.old), self.expected)
        self.assertEqual((self.site / "presentations/brand-01/index.html").read_text(), "World of Surf")
        self.assertFalse(list(self.site.glob(".static.present-*")))

    def test_foreign_temporary_link_is_never_deleted(self):
        temporary = self.site / ".static.present-fixed"
        temporary.symlink_to("releases/0.1.25")
        with patch.object(present.uuid, "uuid4") as identifier:
            identifier.return_value.hex = "fixed"
            self.refused()
        self.assertEqual(os.readlink(temporary), "releases/0.1.25")

    def test_generation_collision_during_rename(self):
        real_rename = present.rename_generation
        def collision(source, destination):
            destination.mkdir()
            (destination / "sentinel").write_text("foreign")
            real_rename(source, destination)
        with patch.object(present, "rename_generation", side_effect=collision):
            with self.assertRaises(present.PublicationError):
                self.publish()
        self.assertEqual(os.readlink(self.site / "static"), "releases/0.1.25")
        self.assertEqual((self.site / "presentations/brand-01/sentinel").read_text(), "foreign")
        self.assertTrue(self.source.exists())

    def test_empty_generation_collision_is_not_overwritten(self):
        real_rename = present.rename_generation
        def collision(source, destination):
            destination.mkdir()
            real_rename(source, destination)
        with patch.object(present, "rename_generation", side_effect=collision):
            with self.assertRaises(present.PublicationError):
                self.publish()
        self.assertTrue(self.source.exists())
        self.assertTrue((self.site / "presentations/brand-01").is_dir())
        self.assertEqual(os.readlink(self.site / "static"), "releases/0.1.25")

    def test_foreign_replacement_temporary_pointer_is_retained(self):
        real_rename = present.rename_generation
        def replace_pointer(source, destination):
            real_rename(source, destination)
            temporary, = self.site.glob(".static.present-*")
            temporary.unlink()
            temporary.symlink_to("releases/0.1.25")
        with patch.object(present, "rename_generation", side_effect=replace_pointer):
            with self.assertRaisesRegex(present.PublicationError, "temporary pointer replaced"):
                self.publish()
        temporary, = self.site.glob(".static.present-*")
        self.assertEqual(os.readlink(temporary), "releases/0.1.25")
        self.assertEqual(os.readlink(self.site / "static"), "releases/0.1.25")

    def test_permission_noop_fails_closed(self):
        self.source.chmod(0o700)
        with patch.object(present.os, "chmod", return_value=None):
            self.refused()

    def test_walk_errors_are_not_silently_ignored(self):
        def failed_walk(*args, **kwargs):
            kwargs["onerror"](PermissionError(13, "synthetic"))
            return iter(())
        with patch.object(present.os, "walk", side_effect=failed_walk):
            self.refused()

    def test_all_nine_public_presentation_files(self):
        for name in present.PUBLIC_PRESENTATION:
            (self.source / name).write_bytes(b"public presentation")
        result = self.publish()
        self.assertEqual(set(result["changed"]), present.PUBLIC_PRESENTATION)
        self.assertEqual(len(result["changed"]), 9)
        self.assertEqual(present.manifest(self.old), self.expected)

    def test_stale_concurrent_guard_after_validation(self):
        real_manifest = present.manifest
        calls = 0
        def changing(root):
            nonlocal calls
            result = real_manifest(root)
            if Path(root) == self.source:
                calls += 1
                if calls == 2:
                    (self.old / "update.json").write_text("concurrent feed")
            return result
        with patch.object(present, "manifest", side_effect=changing):
            self.refused()

    def test_lock_serializes_and_cli_errors_are_clear(self):
        import fcntl
        saved = self.site / "manifest.json"
        saved.write_text(json.dumps(self.expected))
        command = [sys.executable, "-B", str(Path(present.__file__).absolute()), "--site", str(self.site),
                   "--generation", "brand-01", "--expected-pointer", "releases/0.1.25", "--manifest", str(saved)]
        with (self.site / ".publish.lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                time.sleep(0.3)
                self.assertIsNone(process.poll(), "publisher bypassed held lock")
                self.assertEqual(os.readlink(self.site / "static"), "releases/0.1.25")
                (self.old / "update.json").write_text("concurrent feed")
                fcntl.flock(lock, fcntl.LOCK_UN)
                stdout, stderr = process.communicate(timeout=10)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(stdout, b"")
        self.assertIn(b"presentation refused: stale whole-file manifest", stderr)
        self.assertEqual(os.readlink(self.site / "static"), "releases/0.1.25")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", required=True)
    args = parser.parse_args()
    WORK_ROOT = Path(args.work_root).absolute()
    WORK_ROOT.mkdir(parents=True, exist_ok=False)
    (WORK_ROOT / "OWNER.md").write_text("Presentation tooling controls; no network/live data; retain results.\n")
    unittest.main(argv=[sys.argv[0]], verbosity=2)
