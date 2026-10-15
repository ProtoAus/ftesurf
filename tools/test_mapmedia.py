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


if __name__ == '__main__': unittest.main()
