"""Copy the part of noclip.website the run viewer needs into vendor/noclip.

    python tools/vendor.py <noclip checkout>

Follows relative imports from ROOTS, reading a file from stubs/ instead of the
checkout wherever stubs/ has one, and copies exactly that closure. Rerun it to
move to a new upstream commit; vendor/noclip/UPSTREAM.txt records which.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUBS = os.path.join(HERE, 'stubs')
OUT = os.path.join(HERE, 'vendor', 'noclip')

ROOTS = [
    'SourceEngine/Main.ts',
    'SourceEngine/BSPFile.ts',
    'SourceEngine/VPK.ts',
    'gfx/platform/GfxPlatformWebGL2.ts',
    'gfx/helpers/RenderGraphHelpers.ts',
    'Camera.ts',
    'InputManager.ts',
    'DataFetcher.ts',
    'DataShare.ts',
    'SceneBase.ts',
]

IMPORT = re.compile(r"""(?:import|export)\s[^'";]*?from\s*['"]([^'"]+)['"]"""
                    r"""|import\s*\(\s*['"]([^'"]+)['"]\s*\)"""
                    r"""|import\s+['"]([^'"]+)['"]""", re.S)


def source(rel, src):
    stub = os.path.join(STUBS, rel)
    return stub if os.path.isfile(stub) else os.path.join(src, rel)


def resolve(rel_dir, spec, src):
    p = os.path.normpath(os.path.join(rel_dir, spec)).replace('\\', '/')
    cands = [p[:-3] + '.ts'] if p.endswith('.js') else []
    cands += [p, p + '.ts']
    for c in cands:
        if os.path.isfile(source(c, src)):
            return c
    raise SystemExit(f'unresolved import {spec!r} from {rel_dir}')


def main():
    src = os.path.join(sys.argv[1], 'src')
    commit = subprocess.run(['git', '-C', sys.argv[1], 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True).stdout.strip()
    seen, todo, bare = set(), list(ROOTS), set()
    while todo:
        rel = todo.pop()
        if rel in seen:
            continue
        seen.add(rel)
        if not rel.endswith('.ts'):
            continue
        with open(source(rel, src), encoding='utf-8') as fh:
            text = fh.read()
        for m in IMPORT.finditer(text):
            spec = m.group(1) or m.group(2) or m.group(3)
            if spec.startswith('.'):
                todo.append(resolve(os.path.dirname(rel), spec, src))
            else:
                bare.add(spec)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    lines = [f'noclip.website {commit}', 'https://github.com/magcius/noclip.website',
             'MIT licence: LICENSE beside this file.',
             'Files marked "stub" are FTESurf replacements from src/viewer/stubs/.', '']
    for rel in sorted(seen):
        frm = source(rel, src)
        dst = os.path.join(OUT, 'src', rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        # LF, as .gitattributes stores it: upstream has CRLF files, and a digest
        # of the CRLF copy would not match a checkout.
        with open(frm, 'rb') as fh:
            data = fh.read().replace(b'\r\n', b'\n')
        with open(dst, 'wb') as fh:
            fh.write(data)
        digest = hashlib.sha256(data).hexdigest()[:16]
        tag = 'stub' if frm.startswith(STUBS) else 'upstream'
        lines.append(f'{digest} {tag:8} {rel}')
    shutil.copyfile(os.path.join(sys.argv[1], 'LICENSE'), os.path.join(OUT, 'LICENSE'))
    lines += ['', 'bare imports: ' + ', '.join(sorted(bare))]
    with open(os.path.join(OUT, 'UPSTREAM.txt'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(f'{len(seen)} files from {commit[:12]}; bare imports: {sorted(bare)}')


if __name__ == '__main__':
    main()
