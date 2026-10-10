#!/usr/bin/env python3
"""Owned source-only one-factor six-row predecessor control; no install/cache."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil


def create(fte, out, site='plugins/ui_imgui/scores.inc', old='(m.count-base)/9 > 24',
           new='(m.count-base)/9 > 6', variant='six-row-limit', factor='scoreboard row cap only'):
    if out.exists(): raise RuntimeError('control output already exists')
    if not any((p/'OWNER.md').is_file() for p in out.parents): raise RuntimeError('owned task root required')
    files = list((fte/'plugins').glob('*.h')) + list((fte/'engine').rglob('*.h'))
    source = fte/'plugins/ui_imgui'
    files += [p for p in source.rglob('*') if p.is_file() and
              (p.suffix in ('.cpp','.inc','.h') or p.name == 'SHA256.json')]
    files += [source/'vendor'/name for name in json.loads((source/'vendor/SHA256.json').read_text())]
    records = []
    for path in sorted(set(files)):
        relative = path.relative_to(fte); target = out/relative
        target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,target)
        records.append({'path': relative.as_posix(),'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    target = out/site; text = target.read_bytes().decode()
    if text.count(old) != 1: raise RuntimeError('unique one-factor site required')
    target.write_bytes(text.replace(old,new).encode())
    (out/'control.json').write_text(json.dumps({'variant':variant,'factor':factor,
        'fte_source':str(fte),'files':records,'changed':{'path':target.relative_to(out).as_posix(),
        'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}},indent=2)+'\n')
    return out


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte',type=Path,default=Path('C:/msys64/home/Lex/fteqw-imgui-input'))
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args(); print(create(a.fte.resolve(),a.out.resolve()))
