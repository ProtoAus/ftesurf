#!/usr/bin/env python3
"""Owned, source-only one-factor native font selector control (no install/cache)."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil


def create(fte, out):
    if out.exists(): raise RuntimeError('control output already exists')
    if not any((p / 'OWNER.md').is_file() for p in out.parents):
        raise RuntimeError('control requires an owned task root')
    files = list((fte / 'plugins').glob('*.h'))
    files += [p for p in (fte / 'plugins/ui_imgui').rglob('*') if p.is_file() and
              (p.suffix in ('.cpp', '.inc', '.h') or p.name == 'SHA256.json')]
    vendor = fte / 'plugins/ui_imgui/vendor'
    files += [vendor / name for name in json.loads((vendor / 'SHA256.json').read_text())]
    files += list((fte / 'engine').rglob('*.h'))
    records = []
    for source in sorted(set(files)):
        relative = source.relative_to(fte)
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        records.append({'path': relative.as_posix(), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
    target = out / 'plugins/ui_imgui/scores.inc'
    text = target.read_text()
    old = 'int index = ScoresFontIndex(c.model);'
    if text.count(old) != 1: raise RuntimeError('unique selector mutation site required')
    target.write_text(text.replace(old, 'int index = 0; //CONTROL: metadata acts, but physical selector is frozen.'))
    manifest = {'variant': 'freeze-physical-selector', 'factor': 'selected bake only; schema/input/layout source unchanged',
                'fte_source': str(fte), 'files': records,
                'changed': {'path': str(target.relative_to(out)), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}}
    (out / 'control.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return out


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte', type=Path, default=Path('C:/msys64/home/Lex/fteqw-imgui-input'))
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    print(create(a.fte.resolve(), a.out.resolve()))
