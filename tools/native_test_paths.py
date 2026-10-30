"""Explicit native inputs for historical harnesses, without personal worktrees.

This selects paths only: it does not verify a source pin, compile an artifact,
launch a process, create a rig, or qualify a historical control/subject pair.
"""
import os
from pathlib import Path


def add_native_paths(parser, *, client=True, server=True):
    selected = os.environ.get('FTESURF_FTEROOT', '').strip()
    parser.add_argument('--fte', type=Path, default=Path(selected) if selected else None,
                        help='explicit engine source root (or FTESURF_FTEROOT); no personal-worktree fallback')
    if client:
        parser.add_argument('--engine', type=Path, help='client executable; otherwise --fte/engine/release/fteqw64.exe')
    if server:
        parser.add_argument('--server', type=Path, help='server executable; otherwise --fte/engine/release/fteqwsv64.exe')


def resolve_native_paths(parser, args, *, source=True, client=True, server=True):
    root = args.fte
    if source and root is None:
        parser.error('native work requires --fte or FTESURF_FTEROOT; select the intended source pin explicitly')
    for enabled, field, filename in ((client, 'engine', 'fteqw64.exe'), (server, 'server', 'fteqwsv64.exe')):
        if enabled and getattr(args, field) is None:
            if root is None:
                parser.error('native work requires --' + field + ' or --fte/FTESURF_FTEROOT')
            setattr(args, field, root / 'engine' / 'release' / filename)
    return args
