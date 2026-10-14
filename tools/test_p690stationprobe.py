"""Acted synthetic rejection controls for fixed-station diagnostic eligibility."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import numpy as np
from PIL import Image
import p690stationprobe as g
import test_p690ordinary as baseline
from p690cache import GateError, HASHES, STAMPS, sha


OUTPUT = None


class StationTests(unittest.TestCase):
    results = []

    @classmethod
    def setUpClass(cls):
        cls.root = OUTPUT
        cls.root.mkdir(parents=True, exist_ok=False)
        baseline.OUTPUT = cls.root / 'baseline'
        baseline.OrdinaryTests.setUpClass()
        cls.seed = cls.root / 'seed'
        shutil.copytree(baseline.OrdinaryTests.root, cls.seed)
        d = deepcopy(baseline.OrdinaryTests.quiet)
        d.update(station='kitsune', driver_sha256='c' * 64, helper_sha256='d' * 64)
        d['bundles'] = {'probe': dict(hashes=HASHES['probe'], staged=HASHES['probe'],
            version=STAMPS['probe'] + '\n"vid_renderer" is "gl"')}
        d['stops'] = {'probe': dict(cl='quit, rc 0', sv='quit, rc 0')}
        d['modes'] = [dict(r, arm='probe', info=r['info'] + '\ntimer idle on surf_kitsune',
            settings=r['settings'] + '\n' + '\n'.join(
                f'"{k}" is "{v}"' for k, v in dict(g.EXTRA_SETTINGS, vbsp_glare_interval=.025).items()))
            for r in d['modes'] if r['arm'] == 'probe']
        d['samples'] = [r for r in d['samples'] if r['arm'] == 'p688' and r['metric'] == 'cost' and r['phase'] == 'ordinary' and r['rep'] < 2]
        for r in d['samples']:
            r['arm'] = 'probe'
            ticket = r['ticket'].replace('p688', 'probe')
            p = cls.seed / r['path']
            p.write_text(p.read_text().replace(r['ticket'], ticket))
            r.update(ticket=ticket, sha256=sha(p))
        d['shots'] = [dict(r, arm='probe') for r in d['shots'] if r['arm'] == 'merged' and r['rep'] in ('before', 'after')]
        for r in d['shots']:
            p = cls.seed / f'mode{r["mode"]}-{r["rep"]}.png'
            shutil.copyfile(cls.seed / r['path'], p)
            r.update(path=p.name, sha256=sha(p))
        image = np.asarray(Image.open(cls.seed / d['shots'][0]['path'])).copy()
        on = image.copy()
        on[:20, :100] ^= 127
        for rep, pixels in (('hud-on', on), ('hud-off', image), ('hud-return', on)):
            p = cls.seed / (rep + '.png')
            Image.fromarray(pixels).save(p)
            d['shots'].append(dict(arm='probe', mode=1, rep=rep, path=p.name, sha256=sha(p)))
        cls.original = d
        (cls.seed / 'capture.json').write_text(json.dumps(d))
        g.grade(cls.seed)
        cls.results = []

    @classmethod
    def tearDownClass(cls):
        baseline.OrdinaryTests.tearDownClass()

    def case(self):
        root = self.root / self.id().split('.')[-1]
        shutil.copytree(self.seed, root)
        return root, deepcopy(self.original)

    def save(self, root, data):
        (root / 'capture.json').write_text(json.dumps(data))

    def reject(self, change, pattern):
        root, data = self.case()
        change(root, data)
        self.save(root, data)
        with self.assertRaisesRegex(GateError, pattern) as caught:
            g.grade(root)
        self.results.append(dict(control=self.id(), verdict='REJECTED_AS_EXPECTED', error=str(caught.exception)))

    def test_positive_all_stations(self):
        for name, station in g.STATIONS.items():
            root = self.root / name
            shutil.copytree(self.seed, root)
            d = deepcopy(self.original)
            d['station'] = name
            old = g.STATIONS['kitsune']
            for r in d['modes']:
                camera = station['camera']
                r['info'] = (f"origin {camera[0]:.4f} {camera[1]:.4f} {camera[2]:.4f}\n"
                    f"angles {camera[3]:.4f} {camera[4]:.4f} {camera[5]:.4f}\n"
                    f"velocity 0.0000 0.0000 0.0000\ntimer idle on {station['map']}")
                r['settings'] = r['settings'].replace('"vbsp_glare_interval" is "0.025"', f'"vbsp_glare_interval" is "{station["glare"]}"')
            for r in d['actors']:
                r['text'] = r['text'].replace(old['map'], station['map']).replace(
                    'eye=-14986.237,-14484.737,836.362 angles=19.297,125.601,0.000',
                    'eye=' + ','.join(f'{v+z:.3f}' for v, z in zip(station['camera'][:3], (0, 0, 64))) +
                    ' angles=' + ','.join(f'{v:.3f}' for v in station['camera'][3:]))
            self.save(root, d)
            self.assertTrue(g.grade(root)['eligible'])
        self.results.append(dict(control='three positive fixed stations', verdict='ELIGIBLE'))

    def test_missing_sample(self):
        self.reject(lambda r, d: d['samples'].pop(), 'missing station sampler')

    def test_duplicate_sample(self):
        self.reject(lambda r, d: d['samples'].append(deepcopy(d['samples'][0])), 'duplicate station sample')

    def test_missing_wait(self):
        self.reject(lambda r, d: (r / d['samples'][0]['wait']['path']).unlink(), 'missing/linked evidence')

    def test_bad_wait_receipt(self):
        self.reject(lambda r, d: d['samples'][0]['wait'].__setitem__('sha256', '0' * 64), 'hash mismatch')

    def test_bad_wait_ticket(self):
        def change(root, d):
            row = d['samples'][0]
            path = root / row['wait']['path']
            path.write_text('waited: WRONG\n')
            row['wait']['sha256'] = sha(path)
        self.reject(change, 'sample completion wait did not act')

    def test_truncated_cost(self):
        def change(root, d):
            row = d['samples'][0]
            p = root / row['path']
            p.write_text(p.read_text().replace('33 Draw Calls', 'BAD Draw Calls'))
            row['sha256'] = sha(p)
        self.reject(change, 'cost: malformed number')

    def test_stale_window(self):
        def change(root, d):
            row = d['samples'][1]
            row['start'] = d['samples'][0]['end'] + .1
            row['wait'].update(start=row['start'], end=row['start'] + .01)
        self.reject(change, 'overlapping station sampler')

    def test_incomplete_cadence_ring(self):
        def change(root, d):
            row = d['samples'][0]
            p = root / row['path']
            p.write_text(p.read_text().replace('last 128 swaps', 'last 20 swaps'))
            row['sha256'] = sha(p)
        self.reject(change, 'full128-swap ring')

    def test_wrong_camera(self):
        self.reject(lambda r, d: d['modes'][0].__setitem__('info', d['modes'][0]['info'].replace('-14986.3', '-14886.3')), 'wrong station body')

    def test_moving_body(self):
        self.reject(lambda r, d: d['modes'][0].__setitem__('info', d['modes'][0]['info'].replace('velocity 0.', 'velocity 1.')), 'nonstationary')

    def test_running_timer_is_valid_stationary(self):
        root, d = self.case()
        for r in d['modes']:
            r['info'] = r['info'].replace('timer idle on', 'timer running on') + ', practice 1, recording 1'
        self.save(root, d)
        self.assertTrue(g.grade(root)['eligible'])
        self.results.append(dict(control='stationary practice timer running', verdict='ELIGIBLE'))

    def test_wrong_info_world(self):
        self.reject(lambda r, d: d['modes'][0].__setitem__('info', d['modes'][0]['info'].replace('surf_kitsune', 'wrong')), 'wrong station info world')

    def test_wrong_world(self):
        self.reject(lambda r, d: d['actors'][0].__setitem__('text', d['actors'][0]['text'].replace('surf_kitsune', 'wrong')), 'wrong station ordinary')

    def test_eye_drift(self):
        self.reject(lambda r, d: d['actors'][1].__setitem__('text', d['actors'][1]['text'].replace('836.362', '836.360')), 'rendered camera drift')

    def test_stale_actor(self):
        self.reject(lambda r, d: d['actors'][1].__setitem__('text', d['actors'][0]['text']), 'stale station actor')

    def test_cached_draw(self):
        self.reject(lambda r, d: d['actors'][0].__setitem__('text', d['actors'][0]['text'].replace('cached=0', 'cached=1')), 'wrong station ordinary')

    def test_no_draw_advance(self):
        self.reject(lambda r, d: d['actors'][1].__setitem__('text', d['actors'][1]['text'].replace('ordinary=1200', 'ordinary=1001')), 'did not advance128')

    def test_wrong_hud_state(self):
        self.reject(lambda r, d: d['modes'][0].__setitem__('settings', d['modes'][0]['settings'].replace('"hud_timer" is "0"', '"hud_timer" is "1"')), 'wrong station cvar hud_timer')

    def test_missing_extra_state(self):
        self.reject(lambda r, d: d['modes'][0].__setitem__('settings', d['modes'][0]['settings'].replace('"hl2_water" is "2"', '')), 'missing/duplicate station cvar hl2_water')

    def test_locked_cvar(self):
        self.reject(lambda r, d: d['modes'][0].__setitem__('settings', d['modes'][0]['settings'] + '\nEffective value is 1'), 'locked effective')

    def test_wrong_probe(self):
        self.reject(lambda r, d: d['bundles']['probe']['staged'].__setitem__('fteqw.exe', '0' * 64), 'wrong exact station probe')

    def test_missing_provenance(self):
        self.reject(lambda r, d: d.pop('helper_sha256'), 'missing station provenance')

    def test_false_restoration(self):
        self.reject(lambda r, d: d.__setitem__('restored', False), 'restoration closure')

    def test_no_stop(self):
        self.reject(lambda r, d: d['stops']['probe'].__setitem__('cl', 'forced'), 'rc0 stops')

    def test_missing_png(self):
        self.reject(lambda r, d: d['shots'].pop(), 'missing/extra station PNG')

    def test_reused_png_path(self):
        def change(root, d):
            before = next(r for r in d['shots'] if r['mode'] == 1 and r['rep'] == 'before')
            after = next(r for r in d['shots'] if r['mode'] == 1 and r['rep'] == 'after')
            after.update(path=before['path'], sha256=before['sha256'])
        self.reject(change, 'reused station PNG path')

    def test_bad_png_receipt(self):
        self.reject(lambda r, d: d['shots'][0].__setitem__('sha256', '0' * 64), 'hash mismatch')

    def test_existing_output_refused_without_writes(self):
        before = {p.name: sha(p) for p in self.seed.iterdir() if p.is_file()}
        run = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--output', str(self.seed)],
            capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn('output directory must not already exist', run.stderr)
        self.assertEqual(before, {p.name: sha(p) for p in self.seed.iterdir() if p.is_file()})
        self.results.append(dict(control='existing output refusal without writes', verdict='REJECTED_AS_EXPECTED'))

    def test_animation_is_ineligible_not_invalid(self):
        root, d = self.case()
        row = next(r for r in d['shots'] if r['mode'] == 2 and r['rep'] == 'after')
        p = root / row['path']
        image = np.asarray(Image.open(p)).copy()
        image[300, 400] ^= 255
        Image.fromarray(image).save(p)
        row['sha256'] = sha(p)
        self.save(root, d)
        result = g.grade(root)
        self.assertFalse(result['eligible'])
        self.assertEqual(result['repeats'][2], dict(changed_pixels=1, bounds=[400, 300, 400, 300]))
        self.assertEqual(result['failures'], ['mode2 fullframe repeat differs'])
        self.results.append(dict(control='one-pixel synthetic fullframe drift', verdict='INELIGIBLE'))

    def test_no_hud_action(self):
        root, d = self.case()
        off = next(r for r in d['shots'] if r['rep'] == 'hud-off')
        for row in d['shots']:
            if row['rep'] in ('hud-on', 'hud-return'):
                shutil.copyfile(root / off['path'], root / row['path'])
                row['sha256'] = sha(root / row['path'])
        self.save(root, d)
        result = g.grade(root)
        self.assertEqual(result['failures'], ['HUD control did not act >1000pixels'])
        self.results.append(dict(control='unacted HUD', verdict='INELIGIBLE'))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True, help='fresh operator-owned directory')
    args = ap.parse_args()
    OUTPUT = args.output.resolve()
    if OUTPUT.exists():
        ap.error('output directory must not already exist')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(StationTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if OUTPUT.is_dir():
        (OUTPUT / 'controls.json').write_text(json.dumps(dict(tests=result.testsRun,
            failures=len(result.failures), errors=len(result.errors), controls=StationTests.results), indent=2) + '\n')
    raise SystemExit(not result.wasSuccessful())
