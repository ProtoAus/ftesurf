#!/usr/bin/env python3
"""Non-root tests for the new-service installer's read-only preflight/health gates."""
import contextlib
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

if sys.platform == 'win32':
    sys.modules.setdefault('pwd', types.SimpleNamespace())
spec=importlib.util.spec_from_file_location('zonepub_install',Path(__file__).with_name('install_zonepub.py'))
i=importlib.util.module_from_spec(spec);spec.loader.exec_module(i)


class Install(unittest.TestCase):
    def test_account_preflight_is_readonly_and_rejects_empty_sibling(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'accounts.sqlite3'
            with contextlib.closing(sqlite3.connect(p)) as db:
                db.executescript('CREATE TABLE accounts(steamid TEXT,banned_at INTEGER);CREATE TABLE keylinks(pub TEXT,steamid TEXT);')
            raw=p.read_bytes();i.check_accounts(p);self.assertEqual(p.read_bytes(),raw)
            empty=Path(d)/'empty.sqlite3';empty.write_bytes(b'')
            with self.assertRaises(sqlite3.Error):i.check_accounts(empty)
            missing=Path(d)/'missing.sqlite3'
            with self.assertRaises(sqlite3.Error):i.check_accounts(missing)
            self.assertFalse(missing.exists())

    def test_listener_preflight_refuses_occupied_port(self):
        with socket.socket() as held:
            held.bind(('127.0.0.1',0));port=held.getsockname()[1]
            with self.assertRaises(OSError):i.check_port(port)
        i.check_port(port)
        with patch.object(i,'run',return_value=types.SimpleNamespace(stdout=b'not-found\n')):i.check_unit()
        with patch.object(i,'run',return_value=types.SimpleNamespace(stdout=b'loaded\n')):
            with self.assertRaises(RuntimeError):i.check_unit()

    def test_health_requires_exact_source_and_valid_challenge(self):
        source='a'*40
        response=types.SimpleNamespace(headers={'X-Zonepub-Source':source},
            read=lambda limit:json.dumps(dict(ok=1,nonce='b'*32)).encode())
        with patch.object(i.urllib.request,'urlopen',return_value=contextlib.nullcontext(response)) as call:
            i.probe_app(source)
            self.assertEqual(json.loads(call.call_args.args[0].data)['sha'],'0'*64)
        with patch.object(i.urllib.request,'urlopen',return_value=contextlib.nullcontext(response)):
            with self.assertRaises(RuntimeError):i.probe_app('c'*40)
        response.read=lambda limit:b'{"ok":true,"nonce":"invalid"}'
        with patch.object(i.urllib.request,'urlopen',return_value=contextlib.nullcontext(response)):
            with self.assertRaises(RuntimeError):i.probe_app(source)

    def test_release_files_import_on_their_own(self):
        root=Path(__file__).resolve().parent.parent
        blobs={dest:(root/src).read_bytes() for src,dest in i.FILES.items()}
        i.check_imports(blobs)
        blobs.pop('steam.py')
        with self.assertRaises(RuntimeError):i.check_imports(blobs)


if __name__=='__main__':unittest.main()
