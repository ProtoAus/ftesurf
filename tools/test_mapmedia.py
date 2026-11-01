#!/usr/bin/env python3
"""Offline falsifiers for the public-map XL inventory and size-bounded derivatives."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import mapmedia as m

U = '12345678-abcd-1234-abcd-123456789abc'


def picture():
    im = Image.effect_noise((1920, 1080), 80).convert('RGB')
    f = io.BytesIO(); im.save(f, 'JPEG', quality=95)
    return f.getvalue()


class Media(unittest.TestCase):
    def test_derivatives_keep_dimensions_and_limit(self):
        b = m.backdrop(picture(), 1920, 131072)
        self.assertLess(len(b), 131072)
        self.assertEqual(m.jpeg(b).size, (1920, 1080))
        self.assertEqual(m.jpeg(m.backdrop(b, 2560, 2000000)).size, (2560, 1440))

    def test_nonimage_not_persisted(self):
        with tempfile.TemporaryDirectory() as d, patch.object(m, 'fetch', return_value=b'<html>no</html>'):
            out = m.process(U, Path(d), None, 1920, 131072, True)
            self.assertEqual(out['state'], 'failed')
            self.assertFalse(list(Path(d).glob('*.jpg')))

    def test_offline_regeneration_does_not_request(self):
        with tempfile.TemporaryDirectory() as d, patch.object(m, 'fetch', side_effect=AssertionError('network')):
            root = Path(d); body = picture(); (root / (U+'-xl.jpg')).write_bytes(body)
            out = m.process(U, root, None, 1920, 131072, False)
            self.assertEqual(out['state'], 'ok')
            self.assertEqual((root / (U+'-xl.jpg')).read_bytes(), body)
            self.assertTrue((root / (U+'-bg.jpg')).is_file())

    def test_deleted_thumbnail_uses_real_alternate_identity(self):
        other = 'aaaaaaaa-abcd-1234-abcd-123456789abc'
        def fetch(url, limit):
            if U in url: raise OSError('selected thumbnail gone')
            return picture()
        with tempfile.TemporaryDirectory() as d, patch.object(m, 'fetch', side_effect=fetch):
            out = m.process(U, Path(d), None, 1920, 131072, True, [other])
            self.assertEqual(out['state'], 'ok')
            self.assertEqual(out['uuid'], other)
            self.assertEqual(out['requested_uuid'], U)
            self.assertFalse((Path(d)/(U+'-xl.jpg')).exists())
            self.assertTrue((Path(d)/(other+'-xl.jpg')).exists())

    def test_cached_bhop_without_bhop_prefix_is_included(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'_cache';p.mkdir();(p/'fixture.dat').touch()
            data=[dict(id=1,name='kz_bhop_fixture',leaderboards=[dict(style=0,gamemode=2,trackType=0,tier=1)],thumbnail=dict(id=U))]
            with patch.object(m.mapmeta,'read_msml',return_value=data), patch.object(m.mapmeta,'pick_gamemode',return_value=2):
                rows=m.catalogue(d,[])
                self.assertEqual([x['name'] for x in rows],['kz_bhop_fixture'])

    def test_atlas_large_cell_chooses_large_source(self):
        import mapthumbs as t
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            Image.new('RGB',(256,144)).save(root/(U+'-medium.jpg'))
            Image.new('RGB',(1920,1080)).save(root/(U+'-xl.jpg'))
            with patch.object(t,'FETCHED',d), patch.object(t,'CELL_W',512), patch.object(t,'CELL_H',288):
                self.assertTrue(t.source_for('surf_fixture', U, 'absent').endswith('-xl.jpg'))

    def test_fill_missing_never_shifts_or_deletes_existing_atlases(self):
        import mapthumbs as t
        other='aaaaaaaa-abcd-1234-abcd-123456789abc'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); images=root/'images';images.mkdir();atlas=root/'atlas';atlas.mkdir()
            Image.new('RGB',(256,144)).save(images/(other+'-medium.jpg'))
            (atlas/'atlas0.png').write_bytes(b'predecessor page must not be touched')
            old='meta surf_old 1 1 1 0 0 5 '+U
            meta=root/'mapmeta.txt';meta.write_text(old+'\nmeta surf_new 1 1 1 0 - - '+other+'\n')
            with patch.object(t,'FETCHED',str(images)):
                self.assertEqual(t.build('absent',str(meta),str(atlas),fill_missing=True,start_page=9),(1,1))
            self.assertEqual((atlas/'atlas0.png').read_bytes(),b'predecessor page must not be touched')
            rows=meta.read_text().splitlines()
            self.assertEqual(rows[0],old)
            self.assertEqual(rows[1].split()[6:8],['9','0'])
            self.assertTrue((atlas/'atlas9.png').is_file())

    def test_missing_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(m.process(U, Path(d), None, 1920, 131072, False)['state'], 'missing-xl')
            with self.assertRaises(ValueError): m.catalogue(d, [])

    def test_live_pagination_has_acted_controls(self):
        calls = []
        def body(url, limit):
            calls.append(url)
            mode = 1 if 'gamemode=1' in url else 2
            skip = 100 if 'skip=100' in url else 0
            return json.dumps(dict(totalCount=101, data=[dict(id=mode*1000+i) for i in range(skip, min(101, skip+100))])).encode()
        with patch.object(m, 'fetch', side_effect=body), patch.object(m.time, 'sleep'):
            self.assertEqual(len(m.live_maps()), 202)
        self.assertEqual(len(calls), 4)
        bad = json.dumps(dict(totalCount=101, data=[dict(id=1)]*100)).encode()
        with patch.object(m, 'fetch', return_value=bad):
            with self.assertRaises(ValueError): m.live_maps()

    def test_union_prefers_live_and_accounts_missing_thumbnails(self):
        rows = m.catalogue('absent', [dict(id=1,name='surf_new',status=0,thumbnail=dict(id=U)),
                dict(id=2,name='bhop_no',status=0), dict(id=3,name='kz_bhop_surface',status=0)])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['uuid'], None)
        self.assertEqual(rows[2]['uuid'], U)
        self.assertEqual(rows[2]['source'], 'live-approved')


    def test_catalogue_ksf_names_fill_only_own_unsheeted_rows(self):
        # P1174: KSF's site names the sheet lacks get rows; a renamed second
        # build (`of` set), a Momentum-only row and a sheet name do not.
        import mapmeta
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, 'mapdl.txt')
            p.write_text('FTESURF-MAPDL 1\n'
                         'dl surf_corrosion surf k 6 64962 2026-10-11 0 0 6 -\n'
                         'dl surf_x_css surf k 4 1 2026-10-11 0 0 4 surf_x\n'
                         'dl surf_mom surf m 2 1 2026-10-11 0 2 0 -\n'
                         'dl surf_sheet surf k 3 1 2026-10-11 0 0 3 -\n'
                         'dl surf_untiered surf k 0 1 2026-10-11 0 0 0\n'
                         'dl kz_other kz k 2 1 2026-10-11 0 0 2 -\n')
            got = mapmeta.read_catalogue_ksf(str(p), {'surf_sheet'})
        self.assertEqual(got, {'surf_corrosion': (6, ''), 'surf_untiered': (None, '')})


class P1178(unittest.TestCase):
    FIELD = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.')

    def test_author_token_fits_the_menu_field_check_and_round_trips(self):
        import mapmeta as mm
        cases = [(['ArcticPanda'], 'ArcticPanda'), (['Sneaky Weasel', 'rio.'], 'Sneaky Weasel, rio.'),
                 (['\u00dcber', '\u65e5\u672c'], '\u00dcber, \u65e5\u672c'), (['^1Red\x07  Name'], '1Red Name'),
                 (['-'], '-'), ([], ''), (None, '')]
        for names, text in cases:
            tok = mm.author_token(names)
            self.assertTrue(1 <= len(tok) <= 64 and set(tok) <= self.FIELD, tok)
            self.assertEqual(mm.author_text(tok), text)
        tok = mm.author_token(['x' * 20, 'y' * 20, 'z' * 20, 'w' * 20])
        self.assertEqual(mm.author_text(tok), 'x' * 20 + ', ' + 'y' * 20 + ' +2')
        self.assertEqual(len(mm.author_token(['a' * 80])), 64)
        self.assertEqual(mm.author_token(['   ']), '-')

    def test_momentum_author_is_credit_type_zero(self):
        import mapmeta as mm
        rec = dict(name='surf_fixture', leaderboards=[], credits=[
            dict(type=1, user=dict(alias='Helper')), dict(type=0, user=dict(alias='Maker')),
            dict(type=0, user=dict(alias='Second')), dict(type=2, user=dict(alias='Tester'))])
        rec['submission'] = dict(placeholders=[dict(alias='NoAccount', type=0), dict(alias='Thanks', type=3)])
        meta = mm.from_cache(rec)
        self.assertEqual(meta.author, ['Maker', 'Second', 'NoAccount'])
        rec['submission']['placeholders'] = []
        meta = mm.from_cache(rec)
        self.assertEqual(meta.author, ['Maker', 'Second'])
        t = meta.line().split()
        self.assertEqual(len(t), 15)
        self.assertEqual(mm.author_text(t[12]), 'Maker, Second')
        self.assertEqual(t[13:], ['-', '-'])

    def test_hd_atlas_packs_every_row_and_never_touches_old_cells(self):
        import mapthumbs as t
        other = 'aaaaaaaa-abcd-1234-abcd-123456789abc'
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); images = root / 'images'; images.mkdir(); atlas = root / 'atlas'; atlas.mkdir()
            Image.new('RGB', (480, 270), (200, 10, 10)).save(images / (other + '-small.jpg'))
            page = Image.new('RGB', (2048, 2048), (0, 0, 0))
            page.paste(Image.new('RGB', (128, 72), (10, 200, 10)), (5 * 128, 0))
            page.save(atlas / 'atlas0.png')
            rows = ['meta surf_gone 1 1 1 0 0 5 ' + U + ' 1 rank -',
                    'meta surf_red 1 1 1 0 - - ' + other + ' 1 rank - Maker',
                    'meta surf_none 1 1 1 0 - - - 1 rank -']
            meta = root / 'mapmeta.txt'; meta.write_text('FTESURF-MAPMETA 1\n' + '\n'.join(rows) + '\n')
            with patch.object(t, 'FETCHED', str(images)), patch.object(t, 'KSFSHOTS', str(images / 'ksf')), \
                    patch.object(t, 'SHOTS', str(root)):
                self.assertEqual(t.build_hd('absent', str(meta), str(atlas)), (2, 1))
            got = [l.split() for l in meta.read_text().splitlines()[1:]]
            self.assertEqual([r[6:8] for r in got], [['0', '5'], ['-', '-'], ['-', '-']])
            self.assertEqual([r[13:15] for r in got], [['0', '0'], ['0', '1'], ['-', '-']])
            self.assertEqual(got[1][12], 'Maker')
            with Image.open(atlas / 'hd0.jpg') as im:
                self.assertEqual(im.size, (1920, 2016))
                im = im.convert('RGB')
                self.assertGreater(im.getpixel((80, 45))[1], 150)           # the old green cell, scaled
                self.assertGreater(im.getpixel((240, 45))[0], 150)          # the red source
                self.assertEqual(im.getpixel((240, 93)), im.getpixel((240, 89)))   # padding repeats the edge
            self.assertEqual((atlas / 'atlas0.png').stat().st_size > 0, True)
            # fill-missing: a new row goes on a NEW page, existing cells stay put.
            meta.write_text(meta.read_text() + 'meta surf_new 1 1 1 0 - - ' + other + ' 1 rank -\n')
            with patch.object(t, 'FETCHED', str(images)), patch.object(t, 'KSFSHOTS', str(images / 'ksf')), \
                    patch.object(t, 'SHOTS', str(root)):
                self.assertEqual(t.build_hd('absent', str(meta), str(atlas), fill_missing=True), (1, 1))
            got = [l.split() for l in meta.read_text().splitlines()[1:]]
            self.assertEqual([r[13:15] for r in got], [['0', '0'], ['0', '1'], ['-', '-'], ['1', '0']])
            # A page on disk that the table no longer names is never written into.
            (atlas / 'hd2.jpg').write_bytes(b'shipped page')
            meta.write_text(meta.read_text() + 'meta surf_new2 1 1 1 0 - - ' + other + ' 1 rank -\n')
            with patch.object(t, 'FETCHED', str(images)), patch.object(t, 'KSFSHOTS', str(images / 'ksf')), \
                    patch.object(t, 'SHOTS', str(root)):
                self.assertEqual(t.build_hd('absent', str(meta), str(atlas), fill_missing=True), (1, 1))
            self.assertEqual((atlas / 'hd2.jpg').read_bytes(), b'shipped page')
            self.assertEqual(meta.read_text().splitlines()[-1].split()[13:15], ['3', '0'])
            # A failed decode leaves the pages and the table as they were.
            before = meta.read_text()
            buf = io.BytesIO(); Image.effect_noise((480, 270), 80).convert('RGB').save(buf, 'JPEG')
            (images / ('bbbbbbbb-abcd-1234-abcd-123456789abc-small.jpg')).write_bytes(buf.getvalue()[:len(buf.getvalue()) // 2])  # header intact, scan cut
            meta.write_text(before + 'meta surf_bad 1 1 1 0 - - bbbbbbbb-abcd-1234-abcd-123456789abc 1 rank -\n')
            pages = sorted(p.name for p in atlas.iterdir())
            with patch.object(t, 'FETCHED', str(images)), patch.object(t, 'KSFSHOTS', str(images / 'ksf')), \
                    patch.object(t, 'SHOTS', str(root)):
                with self.assertRaises(RuntimeError):
                    t.build_hd('absent', str(meta), str(atlas))
            self.assertEqual(sorted(p.name for p in atlas.iterdir()), pages)

    def test_refresh_lists_hd_pages_and_gates_their_loss(self):
        import mapmedia_refresh as r
        with tempfile.TemporaryDirectory() as d:
            g = Path(d); (g / 'gfx' / 'mapthumbs').mkdir(parents=True)
            (g / 'gfx' / 'mapthumbs' / 'hd0.jpg').write_bytes(b'x' * 7)
            (g / 'gfx' / 'mapthumbs' / 'atlas0.png').write_bytes(b'y' * 3)
            t = g / 'mapmeta.txt'
            t.write_text('FTESURF-MAPMETA 1\n# hd 0 1\nmeta surf_a 1 1 1 0 0 0 - 1 rank - - 0 0\n')
            r.stamp(str(t), str(g), ('', []), True)
            lines = t.read_text().splitlines()
            self.assertIn('# hd 0 7', lines)
            self.assertIn('# atlas 0 3', lines)
            self.assertEqual(sum(l.startswith('# hd ') for l in lines), 1)
            old = {('meta', 'surf_%d' % i): ('1', '-', '-', '0') for i in range(40)}
            new = {k: ('1', '-', '-', '-') for k in old}
            self.assertEqual(len(r.losses(old, new)[3]), 40)
            self.assertIn('gfx/mapthumbs/hd0.jpg', r.media_files(str(g)))
            # 30 old cells lost of 30 is over the gate even with 100 hd cells kept.
            old = {('meta', 'surf_%d' % i): ('1', '0' if i < 30 else '-', '0', '0') for i in range(100)}
            new = {k: ('1', '-', '-', '0') for k in old}
            live, cand, state = g / 'live.txt', g / 'cand.txt', g / 'state'
            state.mkdir()
            write = lambda p, d: p.write_text(''.join('meta %s 1 1 1 0 %s %s - 1 rank - - %s 0\n'
                                                      % (n, v[1], v[2], v[3]) for (_, n), v in d.items()))
            write(live, old); write(cand, new)
            self.assertFalse(r.gate('mapmeta', str(live), str(cand), str(state), False))


if __name__ == '__main__': unittest.main()
