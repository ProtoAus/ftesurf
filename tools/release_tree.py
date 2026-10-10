#!/usr/bin/env python3
"""Fill a scratch release tree with the ship set's untracked files, copied from an install.

  release_tree.py <scratch tree> [<install>]

For trying a change to src/release/release.ps1's ship set without touching the tree releases are
cut from. Make the scratch tree with `git worktree add` under your own task root, build its QC
(`src/build.ps1`), copy the three engine binaries in from engine\release, run this, then
tools/release_dryrun.ps1.

Reads the ship lists out of the SCRATCH tree's own release.ps1 with tools/shipguard.py's parser,
then copies from the install (default C:/FTESurf, read only) each named file and each top-level
file of each glob directory that the scratch tree lacks. Never overwrites, never deletes, never
copies anything the lists do not name. It copies what the install HOLDS, strays included: on
2026-10-10 that was three *.ttf.prev in gfx/fonts, and the release script's deny tripwire stopped
on them, as it would in a real run.
"""
import fnmatch
import shutil
import sys
from pathlib import Path

tree = Path(sys.argv[1]).resolve()
install = Path(sys.argv[2] if len(sys.argv) > 2 else 'C:/FTESurf')
sys.path.insert(0, str(tree / 'tools'))
import shipguard as S  # noqa: E402

text = (tree / 'src/release/release.ps1').read_text(encoding='utf-8-sig', errors='replace')
copied = had = missing = 0
total = 0


def take(rel):
    global copied, had, missing, total
    dst, src = tree / rel, install / rel
    if dst.is_file():
        had += 1
        return
    if not src.is_file():
        missing += 1
        print('  not in the install either:', rel)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    copied += 1
    total += src.stat().st_size


for arr in ('ShipRootFiles', 'ShipGameFiles'):
    for f in S.ps_strings(S.ps_array(text, arr)):
        take(f)
for g in S.ps_globs(S.ps_array(text, 'ShipGlobs')):
    d = install / g['path']
    if not d.is_dir():
        missing += 1
        print('  glob directory not in the install:', g['path'])
        continue
    for entry in sorted(d.iterdir()):
        if not entry.is_file() or not S.win_filter(entry.name, g.get('filter', '*')):
            continue
        if any(fnmatch.fnmatch(entry.name.lower(), dn.lower()) for dn in g['deny']):
            continue
        take(g['path'] + '/' + entry.name)
print(f'{had} already in the tree, {copied} copied from {install} ({total / 1e6:.1f} MB), {missing} missing')
