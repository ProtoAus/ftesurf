"""Synthetic acted falsifiers for the offline ordinary-render gate, NOT native proof.

--output must name a fresh operator-owned directory; no implicit temp/install writes.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
from pathlib import Path
import subprocess
import sys
import unittest

import numpy as np
from PIL import Image
import p690ordinary as g

OUTPUT = None


def cadence_text(mode=2, avg=10, speeds=0, count=128):
    return (f'"r_speeds" is "{speeds}"\nsys_framepacing mode: {mode}\n'
        f'Present cadence (last {count} swaps):\n'
        f'  interval           : avg {avg:.3f} ms ({1000 / avg:.1f} fps)  min {avg - .001:.3f}  max {avg + .001:.3f} ms\n'
        '  jitter (stddev)    : 0.5 us   spread (max-min) 2.0 us\n')


def cost_text(rep, slow=False):
    return cadence_text(mode=4 if slow else 2, avg=50 if slow else 10, speeds=2) + (
        '---- r_speeds_dump (us/frame, 100-frame average) ----\n'
        f'{50000 + rep if slow else 800 + rep} Total refresh\n'
        '60 r_speeds overhead\n30 Transparent Batches\n'
        f'{48000 if slow else 0} Frame pacing\n33 Draw Calls\n19 World Batches\n8985 Draw Indicies\n'
        '---- end r_speeds_dump ----\n')


class OrdinaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = OUTPUT
        cls.root.mkdir(parents=True, exist_ok=False)
        cls.results = []
        cls.serial = 0
        x, y = np.meshgrid(np.arange(960), np.arange(720))
        picture = np.stack((x % 256, y % 256, (x + y) % 256), axis=2).astype(np.uint8)
        changed = picture.copy()
        changed[250:350, 400:500] = 255 - changed[250:350, 400:500]
        for name, image in (('coarse.png', picture), ('refined.png', changed)):
            Image.fromarray(image).save(cls.root / name)
        d = dict(schema=1, restored=True, bundles={}, modes=[], actors=[], shots=[], samples=[], stops={})
        for arm in g.ALL_ARMS:
            d['bundles'][arm] = dict(hashes=g.HASHES[arm], staged=g.HASHES[arm],
                version='SYNTHETIC ' + g.STAMPS[arm] + '\n"vid_renderer" is "gl"')
            d['stops'][arm] = dict(cl='quit, rc 0', sv='quit, rc 0')
            for mode in (1, 2):
                cls.state(d, arm, mode, 'ordinary')
                for rep in ('before', 'after'):
                    name = 'refined.png' if mode == 2 and arm in ('merged', 'probe') else 'coarse.png'
                    d['shots'].append(dict(arm=arm, mode=mode, rep=rep, path=name, sha256=g.sha(cls.root / name)))
        cls.state(d, 'merged', 2, 'slow')
        cls.state(d, 'merged', 2, 'timing-return')
        d['shots'].append(dict(arm='merged', mode=2, rep='timing-return', path='refined.png', sha256=g.sha(cls.root / 'refined.png')))
        for mode in (1, 2):
            for rep in ('a', 'b'):
                ticket = mode * 2 - (rep == 'a')
                ordinary = 1000 * mode + (200 if rep == 'b' else 0)
                text = (f'MV11_CACHE ticket={ticket} ordinary={ordinary} cached=0 world=maps/surf_kitsune.bsp fromgame=4 flags=0x3480 cache=0 inuse=0\n'
                    f'MV11_VIEW eye=-14986.237,-14484.737,836.362 angles=19.297,125.601,0.000 mode={mode}\n')
                d['actors'].append(dict(mode=mode, rep=rep, text=text))
        clock = 100
        for arm in g.ARMS:
            for mode in (1, 2):
                phases = ['ordinary', 'slow', 'timing-return'] if arm == 'merged' and mode == 2 else ['ordinary']
                for phase in phases:
                    for metric in (('cadence',) if phase == 'timing-return' else ('cadence', 'cost')):
                        for rep in range(6 if phase == 'ordinary' else 2):
                            text = cadence_text(mode=4 if phase == 'slow' else 2, avg=50 if phase == 'slow' else 10) if metric == 'cadence' else cost_text(rep, phase == 'slow')
                            name = f'{arm}-{mode}-{phase}-{metric}-{rep}.txt'
                            (cls.root / name).write_text('SYNTHETIC\n' + text)
                            d['samples'].append(dict(arm=arm, mode=mode, phase=phase, metric=metric, rep=rep,
                                path=name, sha256=g.sha(cls.root / name), start=clock, end=clock + .4))
                            clock += 9 if phase == 'slow' else 4
        cls.base = d
        cls.quiet = copy.deepcopy(d)
        cls.quiet.update(schema=2, protocol_sha256='a' * 64, driver_sha256='b' * 64)
        for row in cls.quiet['modes']:
            row['settings'] += '\n' + '\n'.join(f'"{k}" is "{v}"' for k, v in g.QUIET_SETTINGS.items())
        for row in cls.quiet['samples']:
            ticket = f"{row['arm']}_m{row['mode']}_{row['metric']}_{row['phase']}_{row['rep']}"
            begin = 'MV14_BEGIN_' + ticket
            end = '---- end r_speeds_dump ----' if row['metric'] == 'cost' else 'MV14_END_' + ticket
            original = (cls.root / row['path']).read_text().removeprefix('SYNTHETIC\n')
            name = 'quiet-' + row['path']
            stamp = (datetime.datetime(2000, 1, 1) + datetime.timedelta(seconds=row['start'])).strftime('%Y-%m-%d %H:%M:%S')
            completion = stamp + ' ' + end
            primary = original + completion + '\n' if row['metric'] == 'cadence' else original.replace(end, completion)
            (cls.root / name).write_text(begin + '\n' + primary)
            wait = 'wait-' + row['path']
            (cls.root / wait).write_text('MATCH cl after 0.10 s: ' + completion + '\n')
            row.update(ticket=ticket, path=name, sha256=g.sha(cls.root / name), wait=dict(path=wait,
                sha256=g.sha(cls.root / wait), start=row['start'], end=row['start'] + .2))
        cls.before = dict(subject=dict(g.HASHES['merged'], **{'ftesurf64.exe': g.HASHES['merged']['fteqw64.exe']}),
            installs={'synthetic-install-a': 'a' * 64, 'synthetic-install-b': 'b' * 64}, fixtures={'synthetic.cfg': 'c' * 64})
        (cls.root / 'before.json').write_text(json.dumps(cls.before))
        (cls.root / 'restoration.json').write_text(json.dumps(dict(cls.before, restored=True)))
        (cls.root / 'SYNTHETIC.md').write_text('All evidence here is synthetic offline detector controls, never native results.\n')

    @staticmethod
    def state(d, arm, mode, phase):
        settings = dict(g.SETTINGS, r_blendsort=mode)
        if phase == 'slow':
            settings.update(sys_framepacing=4, cl_maxfps=20)
        d['modes'].append(dict(arm=arm, mode=mode, phase=phase,
            settings='\n'.join(f'"{k}" is "{v}"' for k, v in settings.items()),
            info='origin -14986.3 -14484.8 772.3\nangles 19.3 125.6 0.0\nvelocity 0.0000 0.0000 0.0000'))

    @classmethod
    def tearDownClass(cls):
        (cls.root / 'negative-results.json').write_text(json.dumps(cls.results, indent=2) + '\n')

    def evidence(self, data):
        (self.root / 'capture.json').write_text(json.dumps(data) + '\n')
        return g.grade(self.root)

    def reject(self, name, change, error, base=None):
        d = copy.deepcopy(self.base if base is None else base)
        change(d)
        with self.assertRaisesRegex(g.GateError, error) as caught:
            self.evidence(d)
        self.results.append(dict(control=name, verdict='REJECTED_AS_EXPECTED', error=str(caught.exception)))

    def text(self, row, change):
        old = (self.root / row['path']).read_text()
        self.__class__.serial += 1
        name = f'changed-{self.serial}.txt'
        (self.root / name).write_text(change(old))
        row.update(path=name, sha256=g.sha(self.root / name))

    @staticmethod
    def rows(d, arm='merged', mode=2, metric='cost', phase='ordinary'):
        return [r for r in d['samples'] if (r['arm'], r['mode'], r['metric'], r['phase']) == (arm, mode, metric, phase)]

    def test_positive(self):
        result = self.evidence(copy.deepcopy(self.base))
        self.assertEqual(len(result['groups']), 15)
        self.assertGreater(result['mode2_acted_pixels'], 1000)
        self.results.append(dict(control='synthetic-positive', verdict='PASS_SYNTHETIC_ONLY'))

    def test_closure(self):
        self.reject('unrestored', lambda d: d.update(restored=False), 'restoration')
        self.reject('missing-stop', lambda d: d['stops'].pop('probe'), 'stop closure')
        path = self.root / 'restoration.json'
        original = path.read_text()
        broken = json.loads(original)
        broken['fixtures']['synthetic.cfg'] = 'd' * 64
        path.write_text(json.dumps(broken))
        try:
            with self.assertRaisesRegex(g.GateError, 'restoration mismatch'):
                self.evidence(copy.deepcopy(self.base))
            (self.root / 'broken-restoration.json').write_text(path.read_text())
            self.results.append(dict(control='restoration-hash-mismatch', verdict='REJECTED_AS_EXPECTED'))
        finally:
            path.write_text(original)

    def test_bundle(self):
        self.reject('wrong-binary', lambda d: d['bundles']['merged']['hashes'].update({'fteqw64.exe': '0' * 64}), 'exact bundle')
        self.reject('wrong-stamp', lambda d: d['bundles']['merged'].update(version='old'), 'version stamp')
        self.reject('implicit-renderer', lambda d: d['bundles']['merged'].update(version=g.STAMPS['merged']), 'renderer')

    def test_states(self):
        self.reject('missing-state', lambda d: d['modes'].pop(), 'mode state')
        self.reject('cache1', lambda d: d['modes'][0].update(settings=d['modes'][0]['settings'].replace('"r_temporalscenecache" is "0"', '"r_temporalscenecache" is "1"')), 'wrong cvar')
        self.reject('locked-effective', lambda d: d['modes'][0].update(settings=d['modes'][0]['settings'] + '\nEffective value1'), 'locked effective')
        self.reject('camera-moved', lambda d: d['modes'][0].update(info='origin 0 0 0'), 'camera')
        self.reject('body-moving', lambda d: d['modes'][0].update(info=d['modes'][0]['info'].replace('velocity 0.0000', 'velocity 1.0000')), 'nonstationary')

    def test_actors(self):
        self.reject('missing-actor', lambda d: d['actors'].pop(), 'missing postdraw')
        for name, old, new, message in (
            ('wrong-map', 'surf_kitsune', 'other', 'ordinary postdraw'),
            ('wrong-eye', '-14986.237', '-14980.237', 'postdraw eye'),
            ('incomplete-eye', '-14986.237,-14484.737,836.362', '-14986.237,-14484.737', 'postdraw eye'),
            ('wrong-actor-mode', 'mode=1', 'mode=2', 'ordinary postdraw'),
            ('no-draw-advance', 'ordinary=1200', 'ordinary=1001', 'advance128'),
            ('stale-ticket', 'ticket=2', 'ticket=1', 'stale postdraw')):
            self.reject(name, lambda d, old=old, new=new: [r.update(text=r['text'].replace(old, new)) for r in d['actors']], message)

    def test_images(self):
        self.reject('PNG-hash-mismatch', lambda d: d['shots'][0].update(sha256='0' * 64), 'hash mismatch')
        self.reject('missing-PNG', lambda d: d['shots'].pop(), 'station screenshot')
        def inactive(d):
            for r in d['shots']:
                r.update(path='coarse.png', sha256=g.sha(self.root / 'coarse.png'))
        self.reject('inactive-sorter', inactive, 'sorter did not act')
        def unstable(d):
            d['shots'][0].update(path='refined.png', sha256=g.sha(self.root / 'refined.png'))
        self.reject('unstable-repeat', unstable, 'unstable station repeat')
        for name, array, error in (
            ('wrong-size', np.zeros((100, 100, 3), dtype=np.uint8), 'PNG size'),
            ('empty-frame', np.zeros((720, 960, 3), dtype=np.uint8), 'degenerate station')):
            path = self.root / (name + '.png')
            Image.fromarray(array).save(path)
            self.reject(name, lambda d, path=path: d['shots'][0].update(path=path.name, sha256=g.sha(path)), error)

    def test_samples(self):
        self.reject('missing-sample', lambda d: d['samples'].pop(), 'missing stationary')
        self.reject('duplicate-sample', lambda d: d['samples'].append(d['samples'][0]), 'duplicate sample')
        self.reject('overlap-command', lambda d: d['samples'][1].update(start=d['samples'][0]['end']), 'command interval')
        self.reject('nonfinite-clock', lambda d: d['samples'][0].update(start=float('nan')), 'finite number')
        self.reject('unsafe-path', lambda d: d['samples'][0].update(path='../x.txt'), 'unsafe evidence')
        for name, metric, old, new, message in (
            ('short-ring', 'cadence', 'last 128 swaps', 'last 127 swaps', 'full128'),
            ('wrong-sampled-mode', 'cadence', 'mode: 2', 'mode: 4', 'pacing mode'),
            ('accepting-rspeeds3', 'cost', '"r_speeds" is "2"', '"r_speeds" is "3"', 'sampled r_speeds'),
            ('short-cost', 'cost', '100-frame average', '99-frame average', 'full100'),
            ('missing-footer', 'cost', '---- end r_speeds_dump ----', 'PARTIAL', 'full100'),
            ('duplicate-footer', 'cost', '---- end r_speeds_dump ----', '---- end r_speeds_dump ----\n---- end r_speeds_dump ----', 'full100'),
            ('extra-partial-block', 'cost', '---- end r_speeds_dump ----', '---- end r_speeds_dump ----\n---- r_speeds_dump (us/frame, 100-frame average) ----', 'full100'),
            ('NaN-cost', 'cost', '800 Total refresh', 'nan Total refresh', 'finite number'),
            ('missing-world-draws', 'cost', '19 World Batches', '0 World Batches', 'draw activity'),
            ('missing-transparents', 'cost', '30 Transparent Batches', '0 Transparent Batches', 'draw activity'),
            ('fractional-quantity', 'cost', '19 World Batches', '19.5 World Batches', 'fractional draw'),
            ('missing-bucket', 'cost', '60 r_speeds overhead', '60 unrecognised', 'missing timing')):
            self.reject(name, lambda d, metric=metric, old=old, new=new: self.text(self.rows(d, metric=metric)[0], lambda t: t.replace(old, new)), message)
        def stale(d):
            a, b = self.rows(d)[:2]
            original = (self.root / a['path']).read_text()
            self.text(b, lambda t: original)
        self.reject('stale100frame-block', stale, 'stale100')
        def overlap_ring(d):
            r = self.rows(d, metric='cadence')[1]
            self.text(r, lambda t: cadence_text(avg=30))
        self.reject('overlap128swap-ring', overlap_ring, 'overlapping cadence')

    def test_regressions(self):
        def modify_cost(d, arm, factor):
            for r in self.rows(d, arm=arm):
                self.text(r, lambda t, rep=r['rep']: t.replace(f'{800 + rep} Total refresh', f'{factor * 800 + rep} Total refresh'))
        self.reject('merged-cost-regression', lambda d: modify_cost(d, 'merged', 2), 'merged regression')
        self.reject('P688-return-drift', lambda d: modify_cost(d, 'p688-return', 2), 'return drift')
        def inactive(d):
            for r in self.rows(d, phase='slow'):
                self.text(r, lambda t, rep=r['rep']: cost_text(rep).replace('mode: 2', 'mode: 4'))
        self.reject('unacted-slowdown', inactive, 'slowdown did not act')
        def failed_return(d):
            for r in self.rows(d, metric='cadence', phase='timing-return'):
                self.text(r, lambda t: cadence_text(avg=25))
        self.reject('failed-cadence-return', failed_return, 'cadence return')

    def test_quiet_schema(self):
        result = self.evidence(copy.deepcopy(self.quiet))
        self.assertEqual(result['capture_schema'], 2)
        self.results.append(dict(control='quiet-synthetic-positive', verdict='PASS_SYNTHETIC_ONLY'))
        def reject(name, change, error):
            self.reject(name, change, error, base=self.quiet)
        reject('quiet-missing-provenance', lambda d: d.pop('protocol_sha256'), 'provenance')
        reject('quiet-malformed-provenance', lambda d: d.update(driver_sha256='nan'), 'provenance')
        reject('quiet-missing-hud-control', lambda d: d['modes'][0].update(settings=d['modes'][0]['settings'].replace('"hud_mouse" is "0"', '')), 'cvar hud_mouse')
        reject('quiet-enabled-hud', lambda d: d['modes'][0].update(settings=d['modes'][0]['settings'].replace('"hud_timer" is "0"', '"hud_timer" is "1"')), 'wrong cvar hud_timer')
        reject('quiet-wrong-prediction', lambda d: d['modes'][0].update(settings=d['modes'][0]['settings'].replace('"cl_predict_timenudge" is "0.5"', '"cl_predict_timenudge" is "0"')), 'wrong cvar cl_predict_timenudge')
        reject('quiet-wrong-ticket', lambda d: d['samples'][0].update(ticket='stale'), 'ticket identity')
        reject('quiet-missing-wait', lambda d: d['samples'][0].pop('wait'), 'wait witness')
        reject('quiet-wait-hash-mismatch', lambda d: d['samples'][0]['wait'].update(sha256='0' * 64), 'hash mismatch')
        reject('quiet-wait-before-send', lambda d: d['samples'][0]['wait'].update(start=d['samples'][0]['start'] - 1), 'wait interval')
        reject('quiet-wait-after-read', lambda d: d['samples'][0]['wait'].update(end=d['samples'][0]['end'] + 1), 'wait interval')
        for name, metric, change, error in (
            ('quiet-missing-begin', 'cost', lambda t: t.replace('MV14_BEGIN_', 'NO_BEGIN_'), 'sample ticket'),
            ('quiet-duplicate-begin', 'cost', lambda t: t.splitlines()[0] + '\n' + t, 'sample ticket'),
            ('quiet-wrong-begin', 'cost', lambda t: t.replace('_ordinary_0', '_ordinary_1'), 'sample ticket'),
            ('quiet-missing-footer', 'cost', lambda t: t.replace('---- end r_speeds_dump ----', ''), 'sample ticket'),
            ('quiet-data-after-footer', 'cost', lambda t: t + 'OTHER_SAMPLE\n', 'sample ticket'),
            ('quiet-missing-end', 'cadence', lambda t: t.replace('MV14_END_', 'NO_END_'), 'sample ticket'),
            ('quiet-cost-in-cadence', 'cadence', lambda t: t.replace('sys_framepacing mode: 2', 'r_speeds_dump\nsys_framepacing mode: 2'), 'cadence-only')):
            reject(name, lambda d, metric=metric, change=change: self.text(self.rows(d, metric=metric)[0], change), error)
        reject('quiet-timeout-witness', lambda d: self.text(self.rows(d)[0]['wait'], lambda t: t.replace('MATCH cl', 'TIMEOUT cl')), 'wait did not act')
        reject('quiet-wrong-footer-witness', lambda d: self.text(self.rows(d)[0]['wait'], lambda t: t.replace('---- end r_speeds_dump ----', 'MV14_END_other')), 'wait did not act')
        reject('quiet-wrong-wait-timestamp', lambda d: self.text(self.rows(d)[0]['wait'], lambda t: t.replace('2000-', '2001-')), 'witness/primary mismatch')
        def foreign(d, swapped=False, same_primary=False):
            a, b = self.rows(d)[:2]
            wa, wb = copy.deepcopy(a['wait']), copy.deepcopy(b['wait'])
            b['wait'].update(path=wa['path'], sha256=wa['sha256'])
            if swapped:
                a['wait'].update(path=wb['path'], sha256=wb['sha256'])
            if same_primary:
                # Force matching completion text to independently exercise path reuse.
                last = (self.root / a['path']).read_text().splitlines()[-1]
                self.text(b, lambda t: '\n'.join(t.splitlines()[:-1]) + '\n' + last + '\n')
        reject('quiet-foreign-valid-witness', foreign, 'witness/primary mismatch')
        reject('quiet-swapped-valid-witnesses', lambda d: foreign(d, swapped=True), 'witness/primary mismatch')
        reject('quiet-reused-witness-path', lambda d: foreign(d, same_primary=True), 'reused sample completion witness path')

    def test_quiet_cli_under_optimization(self):
        for valid in (True, False):
            d = copy.deepcopy(self.quiet)
            if not valid:
                self.text(self.rows(d)[0], lambda t: t.replace('MV14_BEGIN_', 'NO_BEGIN_'))
            (self.root / 'capture.json').write_text(json.dumps(d))
            for flags in (['-B'], ['-B', '-O']):
                p = subprocess.run([sys.executable, *flags, str(Path(g.__file__)), str(self.root)], capture_output=True, text=True)
                self.assertEqual(p.returncode, 0 if valid else 1, p.stdout + p.stderr)
                self.assertIn('PASS bounded ordinary' if valid else 'sample ticket', p.stdout)
                self.results.append(dict(control=f'quiet-CLI-{valid}-' + '-'.join(flags), verdict='PASS_SYNTHETIC_ONLY' if valid else 'REJECTED_AS_EXPECTED', exit=p.returncode))

    def test_cli_under_optimization(self):
        (self.root / 'capture.json').write_text(json.dumps(self.base))
        for flags in (['-B'], ['-B', '-O']):
            p = subprocess.run([sys.executable, *flags, str(Path(g.__file__)), str(self.root)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn('PASS bounded ordinary', json.loads(p.stdout)['verdict'])
            self.results.append(dict(control='CLI-positive-' + '-'.join(flags), verdict='PASS_SYNTHETIC_ONLY', exit=p.returncode))
        d = copy.deepcopy(self.base)
        d['restored'] = False
        (self.root / 'capture.json').write_text(json.dumps(d))
        for flags in (['-B'], ['-B', '-O']):
            p = subprocess.run([sys.executable, *flags, str(Path(g.__file__)), str(self.root)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
            self.assertIn('missing restoration closure', p.stdout)
            self.results.append(dict(control='CLI-invalid-' + '-'.join(flags), verdict='REJECTED_AS_EXPECTED', exit=p.returncode))


def main():
    global OUTPUT
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    OUTPUT = args.output
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OrdinaryTests))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
