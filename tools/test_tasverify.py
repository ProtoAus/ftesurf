#!/usr/bin/env python3
"""TAS verifier falsifiers: synthetic grammar and owned-child resource controls.
No game engines or player data.

Agents set TAS_TEST_ROOT to their owned task root for temporary unit directories.
Actual Pi native positive/unfinished/startat controls are separate delivery evidence.
"""
from copy import deepcopy
import json
import os
import signal
from pathlib import Path
import tempfile
from types import SimpleNamespace
import subprocess
import sys
import unittest
from unittest.mock import patch

import reccheck
import tasrev
import tasverify as v
import test_reccheck as grammar


def project(rows=None, startat=2, legal=True):
    rows = rows or [(70, 0, 0, 0, 16384, 0, 0)] * 2 + [(0, 0, 0, 0, 16384, 0, 0)] * 18
    lines = ['tasproject ' + ('3' if legal else '2'), 'map bhop_eazy', 'mapcrc 676de275',
             'zonecrc c50cfd70', 'pmpin pmsrcver=11 physmode=1', 'assist tas', 'origin local',
             'saved 2026-10-30T00:00:00', 'revision 1', 'supply 1 ' + str(len(rows))]
    if legal:
        lines += ['start 0', 'baseat 0 0 64 0 0 0', 'startat ' + str(startat)]
    else:
        lines += ['base 1 ' + 'ab' * 32 + ' 0', 'baseat 0 0 64 0 0 0']
    lines += ['head ' + str(len(rows))]
    lines += ['i ' + ' '.join('%.0f' % x for x in row) for row in rows]
    lines += ['end ' + str(len(rows))]
    body = ('\n'.join(lines) + '\n').encode()
    return body + ('revsha ' + tasrev.revhash(body)[0] + '\n').encode()


def recording(warps=()):
    with patch.object(grammar, 'TICK', .015), patch.object(grammar, 'PIN', 'pmsrcver=11 physmode=1'):
        lines = grammar.build(ver=9, packets=8, startjit=(0, 0, 0, 0), warps=warps)
    lines = [('flags ' + str(v.TF_TAS | 257)) if x.startswith('flags ') else x for x in lines]
    return ('\n'.join(lines) + '\n').encode()


def rehash(data):
    body = data.rsplit(b'revsha ', 1)[0]
    return body + ('revsha ' + tasrev.revhash(body)[0] + '\n').encode()


class Evidence(unittest.TestCase):
    def setUp(self):
        self.project = project()
        self.rec = recording()

    def grade(self, project_bytes=None, rec_bytes=None):
        return v.assess(self.project if project_bytes is None else project_bytes,
                        self.rec if rec_bytes is None else rec_bytes, 'cheat.rec')

    def test_synthetic_native_grammar_is_actually_valid(self):
        r = reccheck.check_rec('cheat.rec', data=self.rec)
        self.assertEqual(r.faults, [])
        self.assertEqual(r.finish_ticks, 8)

    def test_positive_unused_tail_and_exact_identity(self):
        r = self.grade()
        self.assertEqual((r['ticks'], r['consumed_rows'], r['unused_tail_rows']), (8, [3, 10], 10))
        self.assertEqual(r['recording_sha256'], v.digest(self.rec))
        self.assertEqual(r['project_sha256'], v.digest(self.project))
        self.assertEqual(r['recording_bytes'], len(self.rec))

    def test_changed_input_acts(self):
        rows = list(tasrev.parse(self.project)['rows']); rows[2] = (1, 0, 0, 0, 16384, 0, 0)
        with self.assertRaisesRegex(v.Held, 'INPUT_MISMATCH'):
            self.grade(project(rows))

    def test_shifted_start_acts(self):
        with self.assertRaisesRegex(v.Held, 'INPUT_MISMATCH'):
            self.grade(project(startat=1))

    def test_revised_hash_is_not_raw_file_identity(self):
        changed = self.project.replace(b'saved 2026-10-30', b'saved 2026-10-29')
        a, b = self.grade(), self.grade(changed)
        self.assertEqual(a['revision'], b['revision'])
        self.assertNotEqual(a['project_sha256'], b['project_sha256'])

    def test_bad_hash_and_legacy_are_refused(self):
        for data in [self.project.replace(b'revsha ', b'revsha 0', 1), project(legal=False)]:
            with self.subTest(data=data[:12]), self.assertRaises(v.Refused):
                v.admit(data)

    def test_oversize_and_move_range(self):
        with self.assertRaisesRegex(v.Refused, 'PROJECT_SIZE'):
            v.admit(b'x' * (v.MAX_PROJECT + 1))
        rows = list(tasrev.parse(self.project)['rows']); rows[0] = (451, 0, 0, 0, 0, 0, 0)
        with self.assertRaisesRegex(v.Refused, 'MOVE_RANGE'):
            v.admit(project(rows))

    def test_missing_or_duplicate_end_never_passes(self):
        end = next(x for x in self.rec.splitlines(keepends=True) if x.startswith(b'end '))
        for data in [self.rec.replace(end, b''), self.rec + end]:
            with self.subTest(data=data[-80:]), self.assertRaises(v.Held):
                self.grade(rec_bytes=data)

    def test_truncated_input_cannot_zip_to_pass(self):
        row = next(x for x in self.rec.splitlines(keepends=True) if x.startswith(b'in 7 '))
        with self.assertRaises(v.Held):
            self.grade(rec_bytes=self.rec.replace(row, b''))

    def test_mover_tick_not_packet_ordinal(self):
        rows = self.rec.splitlines(keepends=True)
        inputs = [i for i, row in enumerate(rows) if row.startswith(b'in ')]
        first_mt = rows[inputs[0]].split()[2]
        words = rows[inputs[1]].split(); words[2] = first_mt
        rows[inputs[1]] = b' '.join(words) + b'\n'
        with self.assertRaisesRegex(v.Held, 'INPUT_CLOCK'):
            self.grade(rec_bytes=b''.join(rows))

    def test_duplicate_input_and_clock_gap(self):
        row = next(x for x in self.rec.splitlines(keepends=True) if x.startswith(b'in 3 '))
        changed = row.split(); changed[2] = str(int(changed[2]) + 1).encode()
        for data in [self.rec.replace(row, row + row), self.rec.replace(row, b' '.join(changed) + b'\n')]:
            with self.assertRaises(v.Held):
                self.grade(rec_bytes=data)
        # Packet ordinals may repeat; they must never substitute for the mover clock.
        self.assertEqual(self.grade(rec_bytes=self.rec.replace(b'in 3 ', b'in 4 ', 1))['ticks'], 8)

    def test_pin_changes_and_jitter_hold(self):
        for old, new in [(b'mapcrc 676de275', b'mapcrc 676de274'),
                         (b'zonecrc c50cfd70', b'zonecrc c50cfd71'),
                         (b'pmsrcver=11', b'pmsrcver=12')]:
            with self.subTest(old=old), self.assertRaisesRegex(v.Held, 'PIN_'):
                self.grade(rehash(self.project.replace(old, new)))
        with self.assertRaises(v.Held):
            self.grade(rec_bytes=self.rec.replace(b'startjit 0 0 0 0', b'startjit 1 0 0 0'))

    def test_ordinary_map_teleport_is_allowed(self):
        rec = recording(warps=((2, grammar.HORIZON + 2, 'tele', 2),))
        self.assertEqual(self.grade(rec_bytes=rec)['ticks'], 8)

    def test_other_natural_world_transitions_are_allowed(self):
        for kind in ('telerel', 'bhop', 'speed', 'push', 'lift', 'catapult', 'reverse'):
            with self.subTest(kind=kind):
                self.assertEqual(self.grade(rec_bytes=recording(warps=((2, grammar.HORIZON + 2, kind, 2),)))['ticks'], 8)
        with self.assertRaises(v.Held):
            self.grade(rec_bytes=recording(warps=((2, grammar.HORIZON + 2, 'pin', 2),)))

    def test_no_tas_ancestry_never_passes(self):
        with self.assertRaises(v.Held):
            self.grade(rec_bytes=self.rec.replace(('flags ' + str(v.TF_TAS | 257)).encode(), b'flags 0'))

    def test_wire_shorts_not_displayed_angle_tolerance(self):
        self.assertEqual(v.wire_angle('22.9999'), 4187)
        self.assertEqual(v.wire_angle('180.0000'), -32768)
        for x in ('nan', 'inf', '1.2345', '99999999999'):
            with self.subTest(x=x), self.assertRaises(v.Held):
                v.wire_angle(x)


class Runtime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tas-unit-', dir=os.environ.get('TAS_TEST_ROOT'))
        self.root = Path(self.tmp.name)
        (self.root / 'OWNER.md').write_text('synthetic unit fixture, owned by this test')
        source = self.root / 'asset'; source.write_bytes(b'fixture')
        item = {'path': str(source), 'sha256': v.filehash(source)}
        required = ['qwprogs.dat', 'csprogs.dat', 'menu.dat', 'cfg/default.cfg',
                    'maps/bhop_eazy.bsp', 'maps/zones/local/bhop_eazy.json']
        self.runtime = {'format': 1, 'map': 'bhop_eazy', 'gamemode': 'surf', 'tickrate': str(v.TICK),
                        'mount_policy': 'exclusive-vfs-1', 'absent_dependencies': [], 'case_roots': [],
                        'native': {k: dict(item) for k in ('server', 'client', 'plugin')},
                        'assets': {'ftesurf/' + k: dict(item) for k in required}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_runtime_and_missing_dependency(self):
        v.validate_runtime(self.runtime, 'bhop_eazy')
        with patch.object(v, 'filehash', return_value='0' * 64):
            with self.assertRaisesRegex(v.Held, 'RUNTIME_HASH'):
                v.validate_runtime(self.runtime, 'bhop_eazy')
        (self.root / 'asset').unlink()
        with self.assertRaises(OSError):
            v.validate_runtime(self.runtime, 'bhop_eazy')

    def test_absence_is_a_pin(self):
        p = self.root / 'new.phy'
        self.runtime['absent_dependencies'] = [str(p)]
        v.validate_runtime(self.runtime, 'bhop_eazy')
        p.write_bytes(b'appeared')
        with self.assertRaisesRegex(v.Held, 'DEPENDENCY_APPEARED'):
            v.validate_runtime(self.runtime, 'bhop_eazy')

    def test_shadow_mounts_and_project_paths_are_refused(self):
        for path in ('ftesurf/pak0.pak', 'ftesurf/data/tasproj/bhop_eazy/input.tasp',
                     '../ftesurf/x', '/ftesurf/x', 'ftesurf/maps/other.ent'):
            r = deepcopy(self.runtime); r['assets'][path] = next(iter(r['assets'].values()))
            with self.subTest(path=path), self.assertRaises(v.Held):
                v.validate_runtime(r, 'bhop_eazy')

    def test_unknown_mount_policy_and_profile_refused(self):
        for key, value in [('mount_policy', 'fallback'), ('map', 'other'), ('tickrate', '0.01'), ('case_roots', None)]:
            r = deepcopy(self.runtime); r[key] = value
            with self.assertRaises(v.Held):
                v.validate_runtime(r, 'bhop_eazy')

    def test_final_matching_scan_cannot_cross_deadline(self):
        for scanned_at in (.5, 1.5):
            with self.subTest(scanned_at=scanned_at):
                now, scans = [0], []
                peer = object.__new__(v.Peer)
                peer.watch = [peer]; peer.window = b''; peer.window_start = 0
                def scan():
                    scans.append(True)
                    now[0] = scanned_at
                    peer.window = b'finished'
                peer.scan = scan
                with patch.object(v.time, 'monotonic', side_effect=lambda: now[0]):
                    if scanned_at < 1:
                        self.assertEqual(peer.wait(b'finished', 1).group(), b'finished')
                    else:
                        with self.assertRaisesRegex(v.Held, 'TIME_LIMIT'):
                            peer.wait(b'finished', 1)
                self.assertEqual(len(scans), 1)

    def test_final_budget_includes_assessment_and_cleanup(self):
        for elapsed in (.9, 1.1):
            report = {'result': 'PASS', 'replay_wall_limit_seconds': 1}
            with patch.object(v.time, 'monotonic', return_value=100 + elapsed):
                v.finish_replay_budget(report, 100)
            self.assertAlmostEqual(report['replay_wall_seconds'], elapsed)
            self.assertEqual(report['result'], 'PASS' if elapsed < 1 else 'HOLD')
            if elapsed > 1:
                self.assertEqual(report['reason'], 'TIME_LIMIT')
        report = {'result': 'ERROR', 'reason': 'CLEANUP_PROCESS_ALIVE', 'replay_wall_limit_seconds': 1}
        with patch.object(v.time, 'monotonic', return_value=102):
            v.finish_replay_budget(report, 100)
        self.assertEqual((report['result'], report['reason']), ('ERROR', 'CLEANUP_PROCESS_ALIVE'))

    def test_partial_input_time_limit_stops_only_owned_handles(self):
        runtime_file = self.root / 'runtime.json'; runtime_file.write_text(json.dumps(self.runtime))
        proj = self.root / 'input.tasp'; proj.write_bytes(project())
        peers = []

        class FakePeer:
            def __init__(self, exe, base, server, watch=None):
                self.server = server; self.stopped = False
                self.proc = SimpleNamespace(pid=1234, returncode=None, poll=lambda: 0 if self.stopped else None)
                peers.append(self)
                watch.append(self)
            def wait(self, pattern, deadline, after=0):
                if not self.server:
                    raise v.Held('TIME_LIMIT')
            def stop(self):
                self.stopped = True
                self.proc.returncode = 0

        def prepare(out, runtime, raw, token, port, copied):
            return out / 'project.tasp'

        with patch.object(v.sys, 'platform', 'linux'), \
                patch.object(v.os, 'uname', create=True, return_value=SimpleNamespace(machine='aarch64')), \
                patch.object(v, 'Peer', FakePeer), patch.object(v, 'prepare', prepare):
            r = v.run(runtime_file, proj, self.root / 'job', 27616)
        self.assertEqual(r['result'], 'HOLD')
        self.assertEqual(r['reason'], 'TIME_LIMIT')
        self.assertEqual(len(peers), 2)
        self.assertTrue(all(p.stopped for p in peers))
        self.assertTrue(r['checks']['owned_peers_stopped'])
        self.assertTrue((self.root / 'job/result.json').is_file())

    @unittest.skipUnless(os.name == 'posix', 'owned process and signal control')
    def test_cancel_during_cleanup_notifies_without_interrupting_reap(self):
        runtime_file = self.root / 'runtime.json'; runtime_file.write_text(json.dumps(self.runtime))
        proj = self.root / 'input.tasp'; proj.write_bytes(project())
        out = self.root / 'cleanup-cancel'
        peers, readers = [], []

        class FakePeer(v.Peer):
            def __init__(self, exe, base, server, watch=None):
                base.mkdir()
                self.server = server; self.stopped = False; self.image_identity = None
                read, self.master = os.pipe(); readers.append(read)
                self.console = (base / 'console.log').open('xb')
                self.proc = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(60)'],
                                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, start_new_session=True)
                self.live_at_cancel = False
                native_wait = self.proc.wait
                fired = False
                def wait(timeout=None):
                    nonlocal fired
                    if not fired:
                        fired = True
                        self.live_at_cancel = self.proc.poll() is None
                        os.kill(os.getpid(), signal.SIGTERM)
                        # The live child ignores our pipe's quit; exercise escalation now.
                        raise subprocess.TimeoutExpired('owned test child', timeout)
                    return native_wait(timeout)
                self.proc.wait = wait
                peers.append(self); watch.append(self)
            def wait(self, pattern, deadline, after=0):
                if not self.server:
                    raise v.Held('TIME_LIMIT')

        argv = ['tasverify.py', 'run', '--runtime', str(runtime_file), '--project', str(proj),
                '--out', str(out), '--port', '27616']
        try:
            with patch.object(v.sys, 'argv', argv), patch.object(v.sys, 'platform', 'linux'), \
                    patch.object(v.os, 'uname', create=True, return_value=SimpleNamespace(machine='aarch64')), \
                    patch.object(v, 'Peer', FakePeer), \
                    patch.object(v, 'prepare', return_value=out / 'project.tasp'), patch('builtins.print'):
                self.assertEqual(v.main(), 2)
            report = json.loads((out / 'result.json').read_bytes())
            self.assertEqual((report['result'], report['reason']), ('HOLD', 'CANCELLED'))
            self.assertEqual(len(peers), 2)
            self.assertTrue(all(p.live_at_cancel and p.stopped and p.proc.poll() is not None for p in peers))
            self.assertTrue(all(p.master is None and p.console is None for p in peers))
            self.assertTrue(report['checks']['owned_peers_stopped'])
        finally:
            for peer in peers:
                if peer.proc.poll() is None:
                    peer.proc.kill(); peer.proc.wait(5)
            for read in readers:
                os.close(read)

    def fixture(self):
        game = self.root / 'fixture/sv/ftesurf'
        for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat', 'cfg/default.cfg',
                     'maps/bhop_eazy.bsp', 'maps/zones/local/bhop_eazy.json',
                     'cfg/maps/map_bhop_eazy.cfg', 'cfg/maps/entfix_bhop_eazy.cfg',
                     'cfg/lobby/mode_surf.cfg', 'models/box.mdl'):
            p = game / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'fixture')
        source = self.root / 'asset'
        return game, v.runtime_manifest(self.root / 'fixture', source, source, source, 'bhop_eazy', 'surf')

    def test_builder_pins_actual_rules_fixes_and_model_absence(self):
        game, runtime = self.fixture()
        v.validate_runtime(runtime, 'bhop_eazy')
        for name in ('cfg/maps/map_bhop_eazy.cfg', 'cfg/maps/entfix_bhop_eazy.cfg', 'cfg/lobby/mode_surf.cfg'):
            self.assertIn('ftesurf/' + name, runtime['assets'])
        phy = game / 'models/box.phy'
        self.assertIn(str(phy), runtime['absent_dependencies'])
        phy.write_bytes(b'appeared')
        with self.assertRaisesRegex(v.Held, 'DEPENDENCY_APPEARED'):
            v.validate_runtime(runtime, 'bhop_eazy')

    def test_edo_presence_and_absence_both_pin_native_entities(self):
        game, runtime = self.fixture()
        path = game / 'maps/bhop_eazy.edo'
        self.assertIn(str(path), runtime['absent_dependencies'])
        path.write_bytes(b'{ }\n')
        with self.assertRaisesRegex(v.Held, 'DEPENDENCY_APPEARED'):
            v.validate_runtime(runtime, 'bhop_eazy')
        source = self.root / 'asset'
        current = v.runtime_manifest(self.root / 'fixture', source, source, source, 'bhop_eazy', 'surf')
        self.assertIn('ftesurf/maps/bhop_eazy.edo', current['assets'])
        v.validate_runtime(current, 'bhop_eazy')

    @unittest.skipUnless(sys.platform.startswith('linux'), 'native case-sensitive filesystem controls')
    def test_native_case_aliases_are_refused_before_and_after_approval(self):
        game, runtime = self.fixture()
        source = self.root / 'asset'
        for rel in ('maps/BHOP_EAZY.edo', 'maps/bhop_eazy.EDO', 'models/BOX.phy', 'MAPS/bhop_eazy.edo'):
            with self.subTest(alias=rel):
                path = game / rel
                parent_created = not path.parent.exists()
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b'case alias')
                with self.assertRaisesRegex(v.Held, 'DEPENDENCY_CASE_ALIAS'):
                    v.validate_runtime(runtime, 'bhop_eazy')
                with self.assertRaisesRegex(v.Held, 'DEPENDENCY_CASE_ALIAS'):
                    v.runtime_manifest(self.root / 'fixture', source, source, source, 'bhop_eazy', 'surf')
                path.unlink()
                if parent_created:
                    path.parent.rmdir()
                v.validate_runtime(runtime, 'bhop_eazy')

    @unittest.skipUnless(sys.platform.startswith('linux'), 'native case-sensitive filesystem controls')
    def test_missing_model_root_case_alias_is_also_fenced(self):
        game, unused = self.fixture()
        (game / 'models/box.mdl').unlink(); (game / 'models').rmdir()
        source = self.root / 'asset'
        runtime = v.runtime_manifest(self.root / 'fixture', source, source, source, 'bhop_eazy', 'surf')
        v.validate_runtime(runtime, 'bhop_eazy')
        alias = game / 'MODELS'; alias.mkdir()
        with self.assertRaisesRegex(v.Held, 'DEPENDENCY_CASE_ALIAS'):
            v.validate_runtime(runtime, 'bhop_eazy')
        with self.assertRaisesRegex(v.Held, 'DEPENDENCY_CASE_ALIAS'):
            v.runtime_manifest(self.root / 'fixture', source, source, source, 'bhop_eazy', 'surf')
        alias.rmdir()
        v.validate_runtime(runtime, 'bhop_eazy')

    @unittest.skipUnless(sys.platform.startswith('linux'), 'native case-sensitive filesystem controls')
    def test_uppercase_mdl_extension_still_has_physics_absence_witness(self):
        game, unused = self.fixture()
        (game / 'models/box.mdl').rename(game / 'models/BOX.MDL')
        source = self.root / 'asset'
        runtime = v.runtime_manifest(self.root / 'fixture', source, source, source, 'bhop_eazy', 'surf')
        self.assertIn(str(game / 'models/BOX.phy'), runtime['absent_dependencies'])
        v.validate_runtime(runtime, 'bhop_eazy')
        (game / 'models/box.PHY').write_bytes(b'alias')
        with self.assertRaisesRegex(v.Held, 'DEPENDENCY_CASE_ALIAS'):
            v.validate_runtime(runtime, 'bhop_eazy')

    def test_plugin_policy_requires_a_positive_native_ack(self):
        console = self.root / 'console.log'; console.write_bytes(b'normal startup\n')
        peer = SimpleNamespace(base=self.root)
        with self.assertRaisesRegex(v.Held, 'PLUGIN_SEARCH_POLICY'):
            v.require_plugin_policy(peer)
        console.write_bytes(v.PLUGIN_POLICY_ACK + b'\n')
        v.require_plugin_policy(peer)

    def test_incompatible_mode_overlay_is_not_silently_dropped(self):
        game, runtime = self.fixture()
        mode = game / 'cfg/lobby/mode_surf.cfg'; mode.write_bytes(b'pm_ticrate 0.01\n')
        with self.assertRaisesRegex(v.Held, 'RUNTIME_HASH'):
            v.validate_runtime(runtime, 'bhop_eazy')
        source = self.root / 'asset'
        with self.assertRaisesRegex(v.Held, 'UNSUPPORTED_TAS_TICKRATE'):
            v.runtime_manifest(self.root / 'fixture', source, source, source, 'bhop_eazy', 'surf')

    def test_native_copies_are_inside_the_aggregate_staging_cap(self):
        game, runtime = self.fixture()
        for kind, count in (('server', 32), ('client', 64), ('plugin', 16)):
            path = self.root / ('native-' + kind); path.write_bytes(b'x' * count)
            runtime['native'][kind] = {'path': str(path), 'sha256': v.filehash(path)}
        asset_bytes = sum(Path(item['path']).stat().st_size for item in runtime['assets'].values())
        cap = asset_bytes * 2 + 32 + 64 + 16 * 2 - 1
        out = self.root / 'copy-budget'; out.mkdir()
        with patch.object(v, 'MAX_ASSETS', cap), self.assertRaisesRegex(v.Held, 'RUNTIME_SIZE_LIMIT'):
            v.prepare(out, runtime, project(), 'ab' * 12, 27616, [])

    def test_production_oversize_is_refuse_before_engine_launch(self):
        source = self.root / 'oversized.tasp'; source.write_bytes(b'x' * (v.MAX_PROJECT + 1))
        with patch.object(v.sys, 'platform', 'linux'), \
                patch.object(v.os, 'uname', create=True, return_value=SimpleNamespace(machine='aarch64')), \
                patch.object(v, 'Peer') as peer:
            with self.assertRaisesRegex(v.Refused, 'PROJECT_SIZE'):
                v.run(None, source, self.root / 'oversized-job', 27616)
            peer.assert_not_called()

    @unittest.skipUnless(os.name == 'posix', 'Linux process-image/PTY controls')
    def test_both_post_spawn_identity_failures_reap_and_close(self):
        original = Path.stat
        source = self.root / 'asset'
        image = original(source)
        for which in ('proc', 'source'):
            base = self.root / which; base.mkdir()
            watch = []
            proc = SimpleNamespace(pid=12345, returncode=None)
            proc.poll = lambda: proc.returncode
            proc.wait = lambda timeout: setattr(proc, 'returncode', 0)
            proc.terminate = lambda: setattr(proc, 'returncode', 0)
            proc.kill = proc.terminate
            def status(path, *a, **kw):
                if str(path) == '/proc/12345/exe':
                    if which == 'proc': raise OSError('injected proc stat')
                    return image
                if path == source: raise OSError('injected source stat')
                return original(path, *a, **kw)
            with patch.object(v.subprocess, 'Popen', return_value=proc) as spawn, patch.object(Path, 'stat', status):
                with self.assertRaises(OSError):
                    v.Peer(str(source), base, True, watch=watch)
            argv = spawn.call_args.args[0]
            self.assertIn('-pluginrootonly', argv)
            for cvar, value in (('pr_ssqc_memsize', '128m'), ('pr_csqc_memsize', '128m'), ('pr_menu_memsize', '64m')):
                self.assertEqual(argv[argv.index(cvar) + 1], value)
            self.assertEqual(len(watch), 1)
            self.assertEqual(proc.poll(), 0)
            self.assertIsNone(watch[0].master)
            self.assertIsNone(watch[0].console)

    @unittest.skipUnless(os.name == 'posix', 'Linux mapped plugin identity')
    def test_effective_plugin_not_nominated_copy(self):
        path = self.root / 'fteplug_hl2_arm64.so'; path.write_bytes(b'plugin-A')
        st = path.stat()
        maps = ('1000-2000 r-xp 00000000 %x:%x %d %s\n' %
                (os.major(st.st_dev), os.minor(st.st_dev), st.st_ino, path)).encode()
        peer = SimpleNamespace(proc=SimpleNamespace(pid=12345))
        with patch.object(v, 'bounded', return_value=maps):
            self.assertEqual(v.plugin_image(peer, v.digest(b'plugin-A'))['device_inode'], [st.st_dev, st.st_ino])
            with self.assertRaisesRegex(v.Held, 'PLUGIN_IMAGE'):
                v.plugin_image(peer, v.digest(b'plugin-B'))

    def test_pending_client_wait_monitors_server_and_console(self):
        for which in ('server-log', 'server-console', 'client-console'):
            peers = []
            for name in ('server', 'client'):
                peer = object.__new__(v.Peer)
                peer.base = self.root / (which + '-' + name); peer.base.mkdir()
                peer.log = peer.base / 'ftesurf/logs/tasverify.log'; peer.log.parent.mkdir(parents=True)
                peer.offset = 0; peer.window = b''; peer.window_start = 0
                peer.static = {}; peer.last_inventory = 0
                peer.proc = SimpleNamespace(poll=lambda: None)
                peer.watch = peers; peers.append(peer)
            target = peers[0].log if which == 'server-log' else peers[0 if which == 'server-console' else 1].base / 'console.log'
            target.write_bytes(b'x' * 64)
            with patch.object(v, 'MAX_LOG', 64), self.assertRaisesRegex(v.Held, 'LOG_OUTPUT_LIMIT'):
                peers[1].wait(b'never', v.time.monotonic() + 1)

    @unittest.skipUnless(os.name == 'posix', 'Linux producer-side rlimit')
    def test_native_output_producer_has_a_hard_limit(self):
        path = self.root / 'producer-output'
        code = 'import os,sys; f=os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT,0o600); os.write(f,b"x"*8192)'
        with patch.object(v, 'MAX_LOG', 4096):
            child = subprocess.run([sys.executable, '-c', code, str(path)], preexec_fn=v.native_limits(),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        self.assertLessEqual(path.stat().st_size, 4096)

    def test_existing_output_cannot_be_reused(self):
        with patch.object(v.sys, 'platform', 'linux'), \
                patch.object(v.os, 'uname', create=True, return_value=SimpleNamespace(machine='aarch64')):
            with self.assertRaisesRegex(v.Held, 'FRESH_OWNED_ROOT_REQUIRED'):
                v.run(None, None, self.root, 27616)


if __name__ == '__main__':
    unittest.main()
