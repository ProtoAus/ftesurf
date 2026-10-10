#!/usr/bin/env python3
"""Real host-state unit controls plus non-vacuous runtime-grader falsifiers."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from PIL import Image
import p590bridge as subject


class Grader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rig = Path(self.tmp.name)
        (self.rig/'report.json').write_text(json.dumps({'arms': {a: {'exit': 0} for a in subject.ARMS}}))
        for arm in subject.ARMS:
            provider = arm not in ('control', 'absent')
            root = self.rig/arm/'ftesurf'; (root/'logs').mkdir(parents=True)
            lines = ['P590 FINISHED']
            for vm in ('menu', 'client'):
                lines += [f'P590 QC INIT vm={vm} available={int(provider)} outside_open=0 builtin={int(arm != "control")}',
                          f'P590 QC DRAW vm={vm} phase=0 available={int(provider)} handle={int(provider)} native={int(provider)} rejects=6 before=1 after=1 legacy={int(not provider)}',
                          f'P590 QC COMMAND vm={vm} command=outside handle=1 result=0 stale=0',
                          f'P590 QC COMMAND vm={vm} command=close handle=0 result={int(provider)} stale=0']
            if provider:
                lines += ['P590 ABI rejected=7 service=1']
                for vm in (1, 2):
                    lines += [f'P590 DRAW vm={vm} handle={vm} frame=1 ok=1 virtual=320x240 pixel=640x480 clip=120,120,300,240']
                for reason in range(1, 6):
                    lines += [f'P590 OPEN vm=1 owner=101 handle={reason} allocated=1 fail=0',
                              f'P590 CLOSE vm=1 handle={reason} reason={reason} destroyed=1']
            (root/'logs/bridge.log').write_text('\n'.join(lines))
            shots = {'menu': provider, 'menu_close': provider, 'menu_restart': provider,
                     'client': provider, 'client_close': provider}
            if provider:
                shots.update(both=True, plugin_off=False, plugin_on=True, renderer=True,
                             draw_failed=False, open_failed=False, recovered=True,
                             disconnected=True, reconnected=True)
            (root/'screenshots').mkdir()
            for name, native in shots.items():
                im = Image.new('RGB', (640, 480), 'black')
                points = {(50, 90): 'red', (90, 90): 'lime' if native else 'yellow',
                          (115, 90): 'blue', (90, 55): 'red', (170, 90): 'red',
                          (90, 140): 'red', (245, 90): 'white'}
                for (x, y), colour in points.items():
                    im.putpixel((x*2, y*2), Image.new('RGB', (1, 1), colour).getpixel((0, 0)))
                im.save(root/'screenshots'/f'{name}.png')

    def tearDown(self):
        self.tmp.cleanup()

    def mutate(self, old, new, arm='subject1'):
        path = self.rig/arm/'ftesurf/logs/bridge.log'
        text = path.read_text(); self.assertIn(old, text)
        path.write_text(text.replace(old, new))
        self.assertTrue(subject.grade(self.rig))

    def test_acting_controls_pass(self):
        self.assertEqual(subject.grade(self.rig), [])

    def test_silent_init(self):
        self.mutate('P590 QC INIT vm=client', 'QUIET')

    def test_silent_native(self):
        self.mutate('P590 DRAW vm=2', 'QUIET')

    def test_silent_qc_draw(self):
        self.mutate('P590 QC DRAW vm=menu', 'QUIET')

    def test_silent_legacy_control(self):
        self.mutate('legacy=1', 'legacy=0', 'control')

    def test_wrong_guard(self):
        self.mutate('outside_open=0', 'outside_open=1')

    def test_absent_service_not_absent_builtin(self):
        self.mutate('builtin=1', 'builtin=0', 'absent')

    def test_outside_draw(self):
        self.mutate('command=outside handle=1 result=0', 'command=outside handle=1 result=1')

    def test_stale_alias(self):
        self.mutate('command=close handle=0 result=1 stale=0', 'command=close handle=0 result=1 stale=1')

    def test_missing_rejections(self):
        self.mutate('rejects=6', 'rejects=0')

    def test_wrong_abi(self):
        self.mutate('rejected=7', 'rejected=6')

    def test_wrong_clip(self):
        self.mutate('clip=120,120,300,240', 'clip=0,0,640,480')

    def test_wrong_physical_dimensions(self):
        self.mutate('pixel=640x480', 'pixel=320x240')

    def test_resource_leak(self):
        self.mutate('destroyed=1', 'destroyed=0')

    def test_unreleased_owner(self):
        self.mutate('P590 CLOSE vm=1 handle=5', 'QUIET')

    def test_missing_reason(self):
        self.mutate('reason=4', 'reason=1')

    def test_duplicate_release(self):
        self.mutate('P590 FINISHED', 'P590 CLOSE vm=1 handle=1 reason=1 destroyed=1\nP590 FINISHED')

    def test_recycled_handle(self):
        self.mutate('handle=2', 'handle=1')

    def test_wrong_order_or_clip_pixel(self):
        path = self.rig/'subject1/ftesurf/screenshots/client.png'
        im = Image.open(path); im.putpixel((230, 180), (0, 255, 0)); im.save(path)
        self.assertTrue(subject.grade(self.rig))

    def test_missing_screenshot(self):
        (self.rig/'subject1/ftesurf/screenshots/renderer.png').unlink()
        self.assertTrue(subject.grade(self.rig))

    def test_wrong_resolution(self):
        Image.new('RGB', (320, 240)).save(self.rig/'subject1/ftesurf/screenshots/client.png')
        self.assertTrue(subject.grade(self.rig))

    def test_runtime_error(self):
        self.mutate('P590 FINISHED', 'QC runtime error\nP590 FINISHED')

    def test_missing_finish(self):
        self.mutate('P590 FINISHED', 'QUIET')

    def test_timeout(self):
        report = json.loads((self.rig/'report.json').read_text())
        report['arms']['subject1']['timed_out'] = True
        (self.rig/'report.json').write_text(json.dumps(report))
        self.assertTrue(subject.grade(self.rig))


def host_controls(fte: Path, cc: Path, fixture=None) -> int:
    with tempfile.TemporaryDirectory(prefix='p590-host-') as directory:
        root = Path(directory)
        header = (fte/'plugins/plugin.h').read_text()
        start = header.index('//ExportInterface: one trusted synchronous service;')
        marker = '#define pluguimodelservice2_name "NativeUIModel/2"'
        if marker not in header: marker = '#define pluguimodelservice_name "NativeUIModel/1"'
        if marker not in header: marker = '#define pluguiinputservice_name "NativeUIInput/1"'
        end = header.index(marker, start)
        end = header.index('\n', end)
        (root/'ui_abi.h').write_text(header[start:end]+'\n')
        #These implementation includes have no host state; stubs live in fixture TU.
        (root/'pr_common.h').write_text('//deterministic host stub\n')
        (root/'gl_draw.h').write_text('//deterministic host stub\n')
        env = os.environ.copy(); env['PATH'] = str(cc.resolve().parent)+os.pathsep+env.get('PATH', '')
        exe = root/('host.exe' if os.name == 'nt' else 'host')
        command = [str(cc), '-std=c99', '-Wall', '-Wextra', '-Werror', '-O2',
                   '-I'+str(root), '-I'+str(fte/'engine/client'),
                   str(fixture or subject.ROOT/'tools/fixtures/p590bridge_host.c'), '-o', str(exe)]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        if result.returncode or result.stdout or result.stderr:
            print(result.stdout+result.stderr)
            return 1
        return subprocess.run([str(exe)], env=env).returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fte', type=Path, default=Path('C:/msys64/home/Lex/fteqw-ui-bridge'))
    parser.add_argument('--cc', type=Path, default=Path('C:/msys64/ucrt64/bin/gcc.exe') if os.name == 'nt' else Path(shutil.which('cc') or 'cc'))
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Grader))
    raise SystemExit(bool(host_controls(args.fte, args.cc) or not result.wasSuccessful()))
