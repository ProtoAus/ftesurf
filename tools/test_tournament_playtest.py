#!/usr/bin/env python3
"""Focused offline ownership/transport controls for the local tournament rig."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('playtest', HERE/'tournament_playtest.py')
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
WORK = None


class RigTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='unit-', dir=WORK))
        (self.root/'OWNER.md').write_text('Owned local-playtest unit fixture.\n')

    def test_owned_path_requires_owner(self):
        with self.assertRaises(ValueError):
            P.owned_root(Path('/tmp/unowned-tournament-path-that-must-not-be-created'))
        self.assertFalse(Path('/tmp/unowned-tournament-path-that-must-not-be-created').exists())
        self.assertEqual(P.owned_root(self.root/'output'), self.root/'output')

    def test_native_console_has_a_real_owned_tty_and_stops(self):
        (self.root/'player').mkdir()
        child = P.Native(self.root, 'player', [sys.executable, '-u', '-c',
            'import os,sys; print("TTY",os.isatty(0),flush=True); '
            'print("READ",input(),flush=True)'])
        try:
            child.send('hello')
            self.assertEqual(child.process.wait(timeout=5), 0)
        finally:
            child.stop()
        log = (self.root/'player-console.log').read_text()
        self.assertIn('TTY True', log)
        self.assertIn('READ hello', log)

    def test_fatal_native_console_is_not_silently_waited_out(self):
        (self.root/'player-console.log').write_text('normal startup\nCSQC_Abort: fixture\n')
        with self.assertRaisesRegex(RuntimeError, 'player native failure'):
            P.native_failures(self.root)

    def _asset_fixture(self):
        content = self.root/'content'
        for name in P.MAPS:
            zone = content/'ftesurf/maps/zones/local'/(name+'.json')
            zone.parent.mkdir(parents=True, exist_ok=True)
            zone.write_text('{"fixture":true}\n')
        return content

    def test_no_implicit_asset_network(self):
        content = self._asset_fixture()
        with mock.patch.object(P.urllib.request, 'urlopen') as fetch:
            with self.assertRaisesRegex(ValueError, 'prepare once with --download'):
                P.map_assets(content, self.root/'assets', False)
        fetch.assert_not_called()

    def test_named_map_fetch_has_honest_user_agent_and_retains_digest(self):
        content = self._asset_fixture()
        class Response(io.BytesIO):
            url = 'https://maps.proto.bar/objects/maps/public-test.bsp'
        def fetch(request, timeout):
            self.assertEqual(request.get_header('User-agent'), 'WorldOfSurf-LocalPlaytest/1.0')
            self.assertIn(request.full_url, ['https://play.proto.bar/maps/'+n+'.bsp' for n in P.MAPS])
            self.assertEqual(timeout, 90)
            return Response(b'VBSP'+b'\0'*16)
        with mock.patch.object(P.urllib.request, 'urlopen', side_effect=fetch) as called:
            maps = P.map_assets(content, self.root/'assets', True)
        self.assertEqual(called.call_count, 6)
        self.assertEqual(len(list(maps.glob('*.bsp'))), 6)
        manifest = json.loads((self.root/'assets/map-assets.json').read_text())
        self.assertEqual(len(manifest), 12)
        self.assertTrue(all(len(h)==64 for h in manifest.values()))
        self.assertFalse(any(p.suffix=='.part' for p in maps.iterdir()))

    def test_invalid_remote_asset_is_never_published(self):
        content = self._asset_fixture()
        response = io.BytesIO(b'not a BSP')
        response.url = 'https://maps.proto.bar/objects/maps/bad.bsp'
        with mock.patch.object(P.urllib.request, 'urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'bounded Source BSP'):
                P.map_assets(content, self.root/'assets', True)
        self.assertFalse(list((self.root/'assets/maps').glob('*.bsp')))

    def test_plaintext_redirect_is_refused(self):
        content = self._asset_fixture()
        response = io.BytesIO(b'VBSP'+b'\0'*16)
        response.url = 'http://example.invalid/map.bsp'
        with mock.patch.object(P.urllib.request, 'urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'left HTTPS'):
                P.map_assets(content, self.root/'assets', True)

    def test_played_profile_cannot_become_a_template(self):
        template = self.root/'template'
        (template/'backend').mkdir(parents=True)
        args = argparse.Namespace(template=template)
        with self.assertRaisesRegex(ValueError, 'pristine'):
            P.from_template(args, self.root)

    def test_template_without_source_snapshot_cannot_be_qualified(self):
        template = self.root/'template-without-source'
        template.mkdir()
        args = argparse.Namespace(template=template)
        with self.assertRaisesRegex(ValueError, 'source snapshot'):
            P.from_template(args, self.root)

    def test_fixture_link_does_not_accept_unsigned_account_proof(self):
        # A fresh child process isolates surfd module config/schema globals.
        rig = self.root/'proof'
        (rig/'ftesurf').mkdir(parents=True)
        (rig/'ftesurf/csprogs.dat').write_bytes(b'fixture gamecode')
        (rig/'server/ftesurf/maps/zones/local').mkdir(parents=True)
        program = '''
import importlib.util,json,sys
from pathlib import Path
p=Path(sys.argv[1]);rig=Path(sys.argv[2])
s=importlib.util.spec_from_file_location('playtest',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
S,actors,web,thread=m.start_backend(rig,{'http_port':m.free_port(m.socket.SOCK_STREAM)})
try:
    response=S.app.test_client().post('/api/account',data={
        'key':'local-test-only','pub':'ab'*32,'sig':'00'*64,
        'server':'127.0.0.1:27616','keyed':'12'*32,'game':'0'*64,
        'nonce':'cd'*16,'node':'p27616','ip':'127.0.0.1'})
    body=response.get_json()
    with S.app.app_context():
        tokens=S.get_db().execute('SELECT count(*) FROM social_sessions').fetchone()[0]
    assert tokens==0,(response.status_code,body)
    assert not body.get('linked') and not body.get('social'),body
    print('UNSIGNED_PROOF_REFUSED',response.status_code)
finally:
    web.shutdown();thread.join(timeout=5)
'''
        result = subprocess.run([sys.executable,'-B','-c',program,str(HERE/'tournament_playtest.py'),str(rig)],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertIn('UNSIGNED_PROOF_REFUSED',result.stdout)

    def test_native_click_uses_existing_ui_hit_testing(self):
        fake = mock.Mock()
        P.click(fake, 'tour_create')
        commands = fake.send.call_args.args[0]
        self.assertIn('hud_edit ui hover tour_create', commands)
        self.assertIn('hud_edit ui down mouse1', commands)
        self.assertIn('hud_edit ui up mouse1', commands)
        self.assertNotIn('cmd tour create', commands)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args, rest = parser.parse_known_args()
    WORK = P.owned_root(args.work_root)
    unittest.main(argv=[sys.argv[0], *rest])
