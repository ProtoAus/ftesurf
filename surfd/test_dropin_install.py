#!/usr/bin/env python3
"""P1115: surfd_dropin_install refuses everything but one generation's change, and installs it
whole or not at all. Run from surfd/ with python -B; the filesystem cases need Linux (dir_fd).
On the Pi, REAL=1 also checks gen_dropin's real outputs (each backup against the next)."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import surfd_dropin_install as D

AW = "/srv/nvme/agent-work"
OLD = AW + "/lexmaps-gen1104b-20261029"
NEW = AW + "/lexmaps-gen1106-20261029"
G0, G1 = "8e32a46303cb3b3008a2f3fdcf397a37e761225e", "a70bbfb5710ef9a5c85d73cc322060b2099eaf78"


def live_text(old=OLD, gen=G0, aw=AW):
    return ("[Service]\nType=simple\nExecStart=\nExecStart=/srv/nvme/surfd/run.sh\n"
            "ReadWritePaths=%s/x %s/state %s/control\n"
            "ExecStartPre=/usr/bin/python3.11 -I -B -c \"folders=['%s/x', '%s/state', '%s/control']\\n"
            "record={'generation':'%s'}\\ntarget=Path('%s/control/service-filesystem-preflight.json')\"\n"
            "ReadOnlyPaths=\"%s/control/manifest.json\"\n" % (aw, old, old, aw, old, old, gen, old, old))


LIVE = live_text()


def slurp(path, mode="rb"):
    with open(path, mode) as f:
        return f.read()


def good(live=LIVE, new=NEW, gen=G1):
    return D.expected(live, new, gen, "P1106")


class Validate(unittest.TestCase):
    def ok(self, cand, live=LIVE):
        return D.validate(live.encode(), cand.encode())

    def refused(self, cand, live=LIVE, msg=None):
        with self.assertRaises(D.Refused) as cm:
            D.validate(live.encode(), cand.encode())
        if msg:
            self.assertIn(msg, str(cm.exception))

    def test_the_change_passes(self):
        self.assertEqual(self.ok(good()), (NEW, G1, "P1106"))
        c = good()
        self.assertIn("ReadWritePaths=%s/x %s/state %s/control %s/state %s/control\n" % (AW, OLD, OLD, NEW, NEW), c)
        self.assertIn("'generation':'%s'" % G1, c)
        self.assertEqual(c.count("ReadOnlyPaths="), 6)

    def test_any_other_line_refused(self):
        for bad in ("ExecStartPre=+/bin/sh -c id\n", "User=root\n", "ExecStart=/bin/sh\n", "\n", "[Install]\n"):
            c = good()
            i = c.index("ReadWritePaths")
            self.refused(c[:i] + bad + c[i:], msg="differs")
        self.refused(good().replace("Type=simple", "Type=forking"), msg="differs")
        self.refused(good() + "ExecStartPre=+/bin/true\n")

    def test_roots_and_ids(self):
        for root in (AW + "/a b", AW + "/x'y", "/tmp/x", AW + "/a/b", AW + "/%n", AW + "/..",
                     AW + "/.x", AW + "/x-", OLD, AW + "/" + "a" * 90):
            with self.assertRaises(D.Refused, msg=root):
                D.expected(LIVE, root, G1, "P1106")
        with self.assertRaises(D.Refused):
            D.expected(LIVE, NEW, G1.upper(), "P1106")
        with self.assertRaises(D.Refused):
            D.expected(LIVE, NEW, G1, "X1")

    def test_prefix_root_and_same_generation_pass(self):       # review 1: substring tests refused these
        self.assertEqual(self.ok(good(new=OLD[:-9]))[0], OLD[:-9])
        self.assertEqual(self.ok(good(gen=G0))[1], G0)

    def test_tail_tampering(self):
        c = good()
        self.refused(c.replace('%s/state/manifest.json"' % NEW, '%s/state/other.json"' % NEW), msg="pin")
        self.refused(c.replace('ReadOnlyPaths="%s/control/gunicorn.conf.py"' % NEW,
                               'ReadOnlyPaths="%s/other/control/gunicorn.conf.py"' % AW), msg="more than one root")
        self.refused(c.rstrip("\n"))
        self.refused(c.replace("P1106 generation", "P1106  generation"), msg="generation comment")
        self.refused(c.replace("\n", "\r\n"))
        # Another generation everywhere is still the change; the root's manifest refuses it (FS).
        self.assertEqual(self.ok(c.replace(G1, "0" * 40))[1], "0" * 40)

    def test_long_root_refused_in_the_tail(self):            # review 2: before any path is opened
        cand = good().replace(NEW, AW + "/" + "a" * 5000)
        with self.assertRaises(D.Refused) as cm:
            D.parse_tail(cand)
        self.assertLess(len(str(cm.exception)), D.MSG_MAX + 100)    # bounded, not the 5,000-byte name

    def test_live_with_two_pins_refused_by_the_count(self):
        twice = LIVE.replace("record={'generation':'%s'}" % G0, "record={'generation':'%s','generation':'%s'}" % (G0, G0))
        with self.assertRaises(D.Refused) as cm:
            D.expected(twice, NEW, G1, "P1106")
        self.assertIn("one preflight target and one generation pin", str(cm.exception))

    def test_non_ascii_refused(self):
        self.refused(good() + "é", msg="ASCII")

    def test_line_cap(self):
        live = LIVE.replace("folders=['", "folders=['" + "y" * (D.MAX_LINE + 10) + "', '")
        self.refused(good(live=live), live=live, msg="prune")


@unittest.skipIf(os.name == "nt", "dir_fd and hard links: Linux")
class FS(unittest.TestCase):
    """main() against a scratch AGENT_WORK and drop-in directory, as if root."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="dropin-")
        self.addCleanup(shutil.rmtree, self.base)
        self.aw = os.path.join(self.base, "aw")
        self.ddir = os.path.join(self.base, "dropin.d")
        os.makedirs(os.path.join(self.aw, "surfd-dropin"))
        os.makedirs(self.ddir)
        self.old, self.new = self.aw + "/genold", self.aw + "/gennew"
        for root, gen in ((self.old, G0), (self.new, G1)):
            for d in ("control", "state"):
                os.makedirs(os.path.join(root, d))
            for p in D.PINS:
                with open(os.path.join(root, p), "w") as f:
                    f.write('{"generation": "%s"}' % gen if p == "state/manifest.json" else "x")
        os.makedirs(self.aw + "/x")
        self.live = live_text(self.old, G0, self.aw)
        patches = {"LIVE": os.path.join(self.ddir, "10-guarded-startup.conf"), "AGENT_WORK": self.aw,
                   "LOG": os.path.join(self.base, "log"), "LOCK": os.path.join(self.base, "lock"),
                   "STATUS": os.path.join(self.base, "status"), "RELOAD": ["/bin/true"],
                   "NEEDS_RELOAD": ["/bin/echo", "yes"],
                   "OWNER": __import__("pwd").getpwuid(os.getuid()).pw_name}
        p = mock.patch.multiple(D, **patches)
        p.start()
        self.addCleanup(p.stop)
        self.cand = D.expected(self.live, self.new, G1, "P1106")
        with open(D.LIVE, "w") as f:
            f.write(self.live)
        with open(os.path.join(self.aw, "surfd-dropin", "candidate.conf"), "w") as f:
            f.write(self.cand)
        r = mock.patch.object(D.os, "geteuid", return_value=0)
        r.start()
        self.addCleanup(r.stop)

    def run_main(self, *args):
        return D.main(["x"] + list(args))

    def livebytes(self):
        return slurp(D.LIVE)

    def backups(self):
        return sorted(n for n in os.listdir(self.ddir) if D.BACKUP.fullmatch(n))

    def test_dry_run_and_install(self):
        self.assertEqual(self.run_main("--dry-run"), 0)
        self.assertEqual(self.livebytes(), self.live.encode())
        self.assertFalse(os.path.exists(D.STATUS))           # a dry run writes nothing
        old_umask = os.umask(0o077)
        try:
            self.assertEqual(self.run_main(), 0)
            self.assertEqual(os.umask(0o077), 0o022)           # main set it
        finally:
            os.umask(old_umask)
        self.assertEqual(self.livebytes(), self.cand.encode())
        self.assertEqual(os.stat(D.LIVE).st_mode & 0o777, 0o644)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(slurp(os.path.join(self.ddir, self.backups()[0])), self.live.encode())
        self.assertFalse([n for n in os.listdir(self.ddir) if n.endswith(".tmp")])
        self.assertIn("installed", slurp(D.LOG, "r"))
        self.assertIn(" exit 0: installed", slurp(D.STATUS, "r"))
        self.assertTrue(slurp(D.STATUS, "r").startswith("invocation "))

    def test_dry_run_already_installed(self):
        with open(D.LIVE, "w") as f:
            f.write(self.cand)
        self.assertEqual(self.run_main("--dry-run"), 0)

    def test_short_writes_are_finished(self):
        real = os.write
        with mock.patch.object(D.os, "write", side_effect=lambda fd, b: real(fd, bytes(b)[:7])):
            self.assertEqual(self.run_main(), 0)
        self.assertEqual(self.livebytes(), self.cand.encode())

    def test_failed_write_changes_nothing(self):
        with mock.patch.object(D.os, "write", return_value=0):
            self.assertEqual(self.run_main(), 4)
        self.assertEqual(self.livebytes(), self.live.encode())
        self.assertEqual(sorted(os.listdir(self.ddir)), ["10-guarded-startup.conf"])
        self.assertIn(" exit 4: not installed", slurp(D.STATUS, "r"))

    def test_live_edited_meanwhile_is_kept(self):
        real = D.read_live
        calls = []

        def edited():
            calls.append(1)
            if len(calls) == 2:             # the re-read just before the swap: Lex has edited it
                with open(D.LIVE, "w") as f:
                    f.write("edited by Lex\n")
            return real()
        with mock.patch.object(D, "read_live", side_effect=edited):
            self.assertEqual(self.run_main(), 1)
        self.assertEqual(self.livebytes(), b"edited by Lex\n")
        self.assertEqual(self.backups(), [])

    def test_reload_failure_then_finish(self):
        with mock.patch.object(D, "RELOAD", ["/bin/false"]):
            self.assertEqual(self.run_main(), 3)
        self.assertEqual(self.livebytes(), self.cand.encode())
        self.assertEqual(self.run_main(), 0)          # already installed: the reload is finished
        self.assertIn("daemon-reload done", slurp(D.LOG, "r"))
        with mock.patch.object(D, "NEEDS_RELOAD", ["/bin/echo", "no"]), \
                mock.patch.object(D, "RELOAD", ["/bin/false"]):
            self.assertEqual(self.run_main(), 0)      # review 3: systemd up to date, no reload asked
        self.assertIn("systemd is up to date", slurp(D.STATUS, "r"))

    def test_reload_that_raises_is_3(self):          # review 3
        with mock.patch.object(D, "RELOAD", [os.path.join(self.base, "no-such-systemctl")]):
            self.assertEqual(self.run_main(), 3)
        self.assertEqual(self.livebytes(), self.cand.encode())

    def test_error_after_the_swap_is_a_warning(self):       # review 2
        with mock.patch.object(D, "prune", side_effect=OSError("EIO")):
            self.assertEqual(self.run_main(), 0)
        self.assertEqual(self.livebytes(), self.cand.encode())
        self.assertIn("warning: prune", slurp(D.LOG, "r"))

    def test_log_failure_still_installs(self):
        with mock.patch.object(D, "LOG", os.path.join(self.base, "nodir", "log")):
            self.assertEqual(self.run_main(), 0)
        self.assertEqual(self.livebytes(), self.cand.encode())

    def test_log_rotates(self):
        with open(D.LOG, "w") as f:
            f.write("x" * (D.LOG_MAX + 1))
        self.assertEqual(self.run_main(), 0)
        self.assertTrue(os.path.exists(D.LOG + ".1"))
        self.assertLess(os.path.getsize(D.LOG), 4096)

    def test_missing_sandbox_path_refused(self):
        shutil.rmtree(self.aw + "/x")
        self.assertEqual(self.run_main(), 1)
        self.assertEqual(self.livebytes(), self.live.encode())
        self.assertIn("sandbox path", slurp(D.STATUS, "r"))

    def test_fifo_oversized_and_linked_candidates_refused(self):    # review 3
        c = os.path.join(self.aw, "surfd-dropin", "candidate.conf")
        os.remove(c)
        os.mkfifo(c)
        self.assertEqual(self.run_main(), 1)          # at once: O_NONBLOCK, then not a regular file
        self.assertIn("not a regular file", slurp(D.STATUS, "r"))
        os.remove(c)
        with open(c, "wb") as f:
            f.write(b"x" * (D.MAX_BYTES + 1))
        self.assertEqual(self.run_main(), 1)
        self.assertIn("larger than", slurp(D.STATUS, "r"))
        with open(c, "w") as f:
            f.write(self.cand)
        os.link(c, c + ".2")
        self.assertEqual(self.run_main(), 1)
        self.assertIn("one link", slurp(D.STATUS, "r"))
        self.assertEqual(self.livebytes(), self.live.encode())

    def test_symlinked_candidate_dir_refused(self):
        real = os.path.join(self.aw, "real")
        os.rename(os.path.join(self.aw, "surfd-dropin"), real)
        os.symlink(real, os.path.join(self.aw, "surfd-dropin"))
        self.assertEqual(self.run_main(), 1)
        self.assertEqual(self.livebytes(), self.live.encode())
        self.assertIn("refused: candidate", slurp(D.STATUS, "r"))

    def test_symlinked_root_dir_refused(self):
        os.rename(self.new + "/control", self.new + "/control.real")
        os.symlink(self.new + "/control.real", self.new + "/control")
        self.assertEqual(self.run_main(), 1)

    def test_wrong_generation_in_manifest_refused(self):
        with open(self.new + "/state/manifest.json", "w") as f:
            f.write('{"generation": "%s"}' % G0)
        self.assertEqual(self.run_main(), 1)

    def test_stray_tmp_swept(self):
        stray = os.path.join(self.ddir, ".10-guarded-startup.abc123.tmp")
        open(stray, "w").close()
        self.assertEqual(self.run_main(), 0)
        self.assertFalse(os.path.exists(stray))

    def test_backups_pruned_by_time_never_the_new_one(self):  # reviews 2/3: fixtures that sort HIGH
        for i in range(D.BACKUPS_KEEP + 3):     # stamped 2099: newer than the one this run makes
            open(os.path.join(self.ddir, "10-guarded-startup.conf.pre-20990101T0000%02dZ-ffffffff" % i), "w").close()
        self.assertEqual(self.run_main(), 0)
        b = self.backups()
        self.assertEqual(len(b), D.BACKUPS_KEEP)
        self.assertTrue(any(n.endswith("-" + G1[:8]) for n in b))   # the one just made survives
        self.assertNotIn("10-guarded-startup.conf.pre-20990101T000000Z-ffffffff", b)   # the oldest went

    def test_arguments_refused(self):
        self.assertEqual(self.run_main("extra"), 2)

    def test_internal_error_is_4(self):
        with mock.patch.object(D, "read_candidate", side_effect=ZeroDivisionError("boom")):
            self.assertEqual(self.run_main(), 4)


@unittest.skipUnless(os.environ.get("REAL") == "1", "REAL=1 on the Pi")
class Real(unittest.TestCase):
    def test_gen_dropin_outputs_pass(self):
        d = "/etc/systemd/system/surfd.service.d/10-guarded-startup.conf."
        files = [d + "pre1093", d + "pre1104", d + "pre1106",
                 "/srv/nvme/agent-work/lexmaps-gen1106-20261029-incoming/10-guarded-startup.conf.1106"]
        labels = ["P1093", "P1104", "P1106"]
        for (a, b), label in zip(zip(files, files[1:]), labels):
            got = D.validate(slurp(a), slurp(b))
            self.assertEqual(got[2], label, (a, b))


if __name__ == "__main__":
    unittest.main()
