#!/usr/bin/env python3
"""Linux synthetic controls of the exact generated legacy-entrypoint wrapper.

OPEN is authored by this fixture, not a real transition acceptance receipt.
No owner application, database, service, package installation or SSH is used.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

import surfd_import_dispatch as dispatch


OUT = None
GUARD = Path(__file__).with_name("surfd_transition_guard.py").resolve()
DISPATCH = Path(dispatch.__file__).resolve()
GENERATION = "a" * 40


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wait_file(path):
    end = time.monotonic() + 5
    while not path.exists():
        if time.monotonic() > end:
            raise AssertionError("fixture did not act: " + str(path))
        time.sleep(0.02)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.root = OUT / self._testMethodName
        self.root.mkdir(mode=0o700)
        self.home = self.root / "immutable"
        self.home.mkdir()
        (self.home / "tools").mkdir()
        self.legacy = self.root / "legacy"
        self.legacy.mkdir()
        (self.legacy / "tools").mkdir()
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        self.marker = self.root / "app-imported"
        for relative in dispatch.FILES:
            (self.home / relative).write_text(
                "from pathlib import Path\nPath(%r).write_text(__file__)\nVALUE = 42\n" %
                str(self.marker))
        self.files = set(dispatch.FILES)
        self.manifest = {"generation": GENERATION, "source_home": str(self.home),
                         "hashes": {}, "routes": {"fixture": [str(Path(sys.executable).resolve()), "-V"]}}
        self.state_write("OPEN")
        (self.state / "admission.lock").write_text("")
        (self.state / "controller.lock").write_text("")
        (self.state / "candidate.lock").write_text("")
        for path in self.state.iterdir():
            path.chmod(0o600)
        self.refresh()
        self.install()

    def state_write(self, admission, generation=GENERATION):
        path = self.state / "state.json"
        path.write_text(json.dumps({"admission": admission, "generation": generation,
                                    "closure": "b" * 32}))
        path.chmod(0o600)

    def refresh(self):
        self.manifest["hashes"] = {name: digest(self.home / name) for name in self.files}
        path = self.state / "manifest.json"
        path.write_text(json.dumps(self.manifest))
        path.chmod(0o600)

    def install(self, **overrides):
        options = dict(dispatch_path=str(DISPATCH), dispatch_sha256=digest(DISPATCH),
                       guard_path=str(GUARD), guard_sha256=digest(GUARD),
                       state_dir=str(self.state), generation=GENERATION)
        options.update(overrides)
        for relative in dispatch.FILES:
            data = dispatch.render_wrapper(source_relative=relative, **options)
            path = self.legacy / relative
            path.write_bytes(data)
            self.assertEqual(path.read_bytes(), data)

    def run_code(self, code, success=True):
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=self.legacy,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def refused(self, message='admission not OPEN'):
        result = self.run_code("import surfd", False)
        self.assertIn(message, result.stderr)
        self.assertFalse(self.marker.exists(), "application ran before gate")

    def schema20(self):
        self.manifest["target_schema"] = 20
        for name in ("accounts", "social"):
            path = self.home / (name + ".py")
            path.write_text("from pathlib import Path\nPath(%r).write_text(__file__)\n" %
                            str(self.root / (name + "-acted")))
            self.files.add(name + ".py")
        target = self.home / "surfd.py"
        target.write_text(target.read_text() + "import accounts, social\n")
        self.refresh()

    def test_schema20_dependency_origins(self):
        self.schema20()
        self.run_code("import surfd\nassert surfd.VALUE == 42\n")
        self.assertTrue(self.marker.exists())
        for name in ("accounts", "social"):
            self.assertEqual((self.root / (name + "-acted")).read_text(),
                             str(self.home / (name + ".py")))

    def test_explicit19(self):
        self.manifest["target_schema"] = 19
        self.refresh()
        self.run_code("import surfd\nassert surfd.VALUE == 42\n")
        self.assertTrue(self.marker.exists())

    def test_schema20_dependency_hash_refusals(self):
        self.schema20()
        for name in ("accounts.py", "social.py"):
            path = self.home / name
            original = path.read_bytes()
            for changed in (None, b"# stale dependency\n"):
                path.unlink()
                if changed is not None:
                    path.write_bytes(changed)
                self.refused('No such file or directory' if changed is None else
                             'raw helper/source hash mismatch')
                for dependency in ("accounts", "social"):
                    self.assertFalse((self.root / (dependency + "-acted")).exists())
                if path.exists():
                    path.unlink()
                path.write_bytes(original)
        self.run_code("import surfd")
        self.assertTrue(self.marker.exists(), "restored schema20 dispatch never acted")

    def test_schema20_closed(self):
        self.schema20()
        self.state_write("CLOSED")
        self.refused()

    def test_schema20_incomplete_manifest(self):
        self.schema20()
        self.files.remove("social.py")
        self.refresh()
        self.refused('exact schema20 raw hash set required')

    def test_closed(self):
        self.state_write("CLOSED")
        self.refused()

    def test_missing_state(self):
        (self.state / "state.json").unlink()
        self.refused('No such file or directory')

    def test_wrong_generation(self):
        self.install(generation="c" * 40)
        self.refused('wrong fixed generation')

    def test_wrong_state_generation(self):
        self.state_write("OPEN", "c" * 40)
        self.refused()

    def test_changed_source(self):
        # A different member, not just the requested entrypoint, must be checked.
        (self.home / "tools/ksfconvert.py").write_text("raise AssertionError('changed')\n")
        self.refused('raw helper/source hash mismatch')

    def test_dispatch_hash(self):
        self.install(dispatch_sha256="0" * 64)
        self.refused('raw dispatch hash mismatch')

    def test_source_fifo_refused_without_blocking(self):
        path = self.home / 'tools/ksfconvert.py'
        path.unlink()
        os.mkfifo(path, 0o600)
        self.refused('unsafe helper/source')

    def test_source_symlink_refused(self):
        path = self.home / 'tools/ksfconvert.py'
        path.unlink()
        path.symlink_to(self.home / 'surfd.py')
        self.refused('noncanonical helper/source path')

    def test_guard_hash(self):
        self.install(guard_sha256="0" * 64)
        self.refused('raw helper/source hash mismatch')

    def test_private_state_required(self):
        self.state.chmod(0o755)
        self.refused('requires owner-only modes')

    def test_stale_runtime_refused(self):
        (self.home / "unchanged.py").write_text("VALUE = 42\n")
        (self.legacy / "unchanged.py").write_text("VALUE = 'stale'\n")
        result = self.run_code("import unchanged; import surfd", False)
        self.assertIn('preloaded runtime module outside source_home: unchanged', result.stderr)
        self.assertFalse(self.marker.exists())

    def test_open_origins_namespace_and_dependencies(self):
        (self.home / "unchanged.py").write_text("VALUE = 42\n")
        (self.legacy / "unchanged.py").write_text("raise AssertionError('legacy dependency')\n")
        target = self.home / "surfd.py"
        target.write_text(target.read_text() + "import unchanged, ksfprofile\n"
                          "def namespace_identity():\n    return globals()\n")
        self.refresh()
        self.run_code("import surfd, sys, os\n"
                      "assert sys.modules['surfd'] is surfd\n"
                      "assert surfd.namespace_identity() is surfd.__dict__\n"
                      "assert surfd.__name__ == 'surfd'\n"
                      "assert surfd.__package__ == ''\n"
                      "assert surfd.__file__ == %r\n"
                      "assert surfd.__spec__.origin == surfd.__file__\n"
                      "assert surfd.__loader__.get_filename('surfd') == surfd.__file__\n"
                      "assert surfd.ksfprofile.__file__ == %r\n"
                      "assert surfd.unchanged.__file__ == %r\n"
                      "assert os.getcwd() == %r\n" %
                      (str(target), str(self.home / "ksfprofile.py"),
                       str(self.home / "unchanged.py"), str(self.home)))
        self.assertTrue(self.marker.exists())
        self.assertFalse(list(self.legacy.rglob("*.pyc")))

    def test_all_six_script_main_argv(self):
        for relative in sorted(dispatch.FILES):
            path = self.home / relative
            path.write_text("import sys\nassert __name__ == '__main__'\n"
                            "assert __spec__ is None\nassert sys.argv[1:] == ['fixed', 'argument']\n"
                            "assert sys.argv[0] == %r\n"
                            "assert __file__ == %r\nprint('SCRIPT ACTED')\n" %
                            (str(self.legacy / relative), str(path)))
        self.refresh()
        for relative in sorted(dispatch.FILES):
            result = subprocess.run([sys.executable, "-B", str(self.legacy / relative),
                                     "fixed", "argument"], cwd=self.legacy,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SCRIPT ACTED", result.stdout)

    def exclusive_blocked(self):
        import fcntl
        fd = os.open(self.state / "admission.lock", os.O_RDONLY)
        try:
            with self.assertRaises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)

    def test_read_only_lock_lifetime_failed_close(self):
        # A real controller closes durably but cannot drain the imported module.
        script = "import surfd; print('LOADED', flush=True); input()"
        proc = subprocess.Popen([sys.executable, "-B", "-c", script], cwd=self.legacy,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), "LOADED")
            self.exclusive_blocked()
            # Inspect Linux fd flags: access mode must really be O_RDONLY.
            matched = []
            for link in Path('/proc/%d/fd' % proc.pid).iterdir():
                if os.readlink(link) == str(self.state / 'admission.lock'):
                    info = Path('/proc/%d/fdinfo/%s' % (proc.pid, link.name)).read_text()
                    flags = int(next(line.split()[1] for line in info.splitlines()
                                     if line.startswith('flags:')), 8)
                    self.assertEqual(flags & os.O_ACCMODE, os.O_RDONLY)
                    self.assertFalse(flags & os.O_CLOEXEC)
                    matched.append(link.name)
            self.assertEqual(len(matched), 1)
            result = subprocess.run([sys.executable, "-B", str(GUARD), "--state-dir",
                                     str(self.state), "--timeout", "0.1", "close"],
                                    capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("CLOSED DURABLE", result.stdout)
            self.assertEqual(json.loads((self.state / "state.json").read_text())["admission"],
                             "CLOSED")
            self.exclusive_blocked()
            self.marker.unlink()  # The admitted process already proved its import acted.
            self.refused()
        finally:
            stdout, stderr = proc.communicate("done\n", timeout=5)
            self.assertEqual(proc.returncode, 0, stdout + stderr)

    def test_fork_child_retains_after_parent_exit(self):
        ready, release, done = [self.root / name for name in ('child-ready', 'release', 'child-done')]
        target = self.home / "surfd.py"
        target.write_text("import os, time\nfrom pathlib import Path\n"
                          "if os.fork() == 0:\n"
                          "    Path(%r).write_text(str(os.getpid()))\n"
                          "    while not Path(%r).exists(): time.sleep(0.02)\n"
                          "    Path(%r).write_text('done')\n"
                          "    os._exit(0)\n" % (str(ready), str(release), str(done)))
        self.refresh()
        with (self.root / 'fork.log').open('w') as log:
            proc = subprocess.Popen([sys.executable, "-B", "-c", "import surfd"],
                                    cwd=self.legacy, stdout=log, stderr=log)
            try:
                proc.wait(timeout=5)
                self.assertEqual(proc.returncode, 0)
                wait_file(ready)
                self.exclusive_blocked()
            finally:
                release.write_text('release')
                proc.wait(timeout=5)
                wait_file(done)
        import fcntl
        end = time.monotonic() + 5
        fd = os.open(self.state / 'admission.lock', os.O_RDONLY)
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    self.assertLess(time.monotonic(), end, 'child lock not released')
                    time.sleep(0.02)
        finally:
            os.close(fd)

    def test_application_failure_closes_fd(self):
        (self.home / 'surfd.py').write_text("raise RuntimeError('application acted')\n")
        self.refresh()
        self.run_code("from pathlib import Path\n"
                      "before = set(Path('/proc/self/fd').iterdir())\n"
                      "try: import surfd\n"
                      "except RuntimeError as error: assert str(error) == 'application acted'\n"
                      "else: raise AssertionError('application did not run')\n"
                      "assert set(Path('/proc/self/fd').iterdir()) == before\n")

    def test_admission_failure_closes_fd(self):
        self.state_write('CLOSED')
        self.run_code("from pathlib import Path\n"
                      "before = set(Path('/proc/self/fd').iterdir())\n"
                      "try: import surfd\n"
                      "except ValueError: pass\n"
                      "else: raise AssertionError('admitted')\n"
                      "assert set(Path('/proc/self/fd').iterdir()) == before\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Linux required for flock/fork/proc controls')
    OUT = args.out.resolve()
    OUT.mkdir(mode=0o700)  # Exclusive: do not reuse another run's fixtures.
    (OUT / 'OWNER.md').write_text(
        '# Dispatch synthetic controls\nOwner: dispatch implementation worker; UTC 2026-10-15.\n'
        'Source base a9dce85f27f94b6c89672b6b63fc5659801ebe4c.\n'
        'Owned: this root and exact Popen handles. No live state.\n'
        'Status: active; retain bounded fixtures/logs for review.\n')
    # DrvFS checkout permissions are not POSIX deployment metadata. Install the
    # exact helper bytes under this owned ext4 fixture with explicit modes.
    for variable in ('DISPATCH', 'GUARD'):
        original = globals()[variable]
        installed = OUT / original.name
        installed.write_bytes(original.read_bytes())
        installed.chmod(0o600)
        assert installed.read_bytes() == original.read_bytes()
        globals()[variable] = installed
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DispatchTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if list(OUT.glob('__pycache__/*.pyc')):
        raise AssertionError('pinned helpers unexpectedly generated bytecode')
    available = importlib.util.find_spec('gunicorn')
    print('Gunicorn local dependency: ' + ('available (distro-host gate still required)' if available
                                          else 'UNAVAILABLE; actual distro gunicorn gate required'))
    with (OUT / 'OWNER.md').open('a') as owner:
        owner.write('Status: retained; suite %s. Test Popen handles waited; fork child released '
                    'by fixture sentinel. No installed dependencies.\n' %
                    ('PASS' if result.wasSuccessful() else 'FAIL'))
    sys.exit(0 if result.wasSuccessful() else 1)
