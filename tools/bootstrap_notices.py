#!/usr/bin/env python3
"""Collect full license/notice texts from the bootstrap's LOCKED Cargo dependencies.

Conservatively includes all dependencies of the package for each selected target
(also Quakers-only crates). Missing license texts fail closed. No credentials are included.
"""
import argparse
import json
from pathlib import Path
import subprocess


def collect(root: Path, targets: list[str]) -> str:
    packages = {}
    for target in targets:
        result = subprocess.run(['cargo', 'metadata', '--locked', '--format-version', '1',
                                 '--filter-platform', target], cwd=root,
                                capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        nodes = {n['id']: n for n in metadata['resolve']['nodes']}
        reachable, pending = set(), [metadata['resolve']['root']]
        while pending:
            item = pending.pop()
            if item in reachable:
                continue
            reachable.add(item)
            pending.extend(dep['pkg'] for dep in nodes[item]['deps'])
        packages.update({p['id']: p for p in metadata['packages'] if p['id'] in reachable})
    sections = ['FTESurf Rust bootstrap - licenses and third-party notices\n'
                'Includes locked dependencies for: ' + ', '.join(targets) + '\n'
                'Conservatively includes Quakers-only dependencies. Original notices follow.\n']
    for package in sorted(packages.values(), key=lambda p: (p['name'], p['version'])):
        directory = Path(package['manifest_path']).parent
        files = []
        for path in directory.rglob('*'):
            if any(part in ('.git', 'target', 'tests', 'testdata', 'test_data')
                   for part in path.relative_to(directory).parts[:-1]):
                continue
            name = path.name.lower()
            is_notice = (name.startswith(('license', 'licence', 'copying', 'notice'))
                         or name == 'unlicense'
                         or ('licenses' in path.relative_to(directory).parts[:-1]
                             and path.suffix.lower() in ('', '.txt', '.md')))
            if path.is_file() and is_notice and path.suffix.lower() not in ('.rs', '.c', '.h', '.py'):
                files.append(path)
        if package.get('license_file'):
            explicit = directory / package['license_file']
            if explicit not in files:
                files.append(explicit)
        if not files:
            raise ValueError(f"license texts missing: {package['name']} {package['version']}")
        sections.append(f"\n{'=' * 72}\n{package['name']} {package['version']}\n"
                        f"Declared license: {package.get('license') or 'see included license file'}\n")
        for path in sorted(files):
            if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
                raise ValueError(f"unsafe license path: {package['name']} {package['version']}")
            # Paths in the output are crate-relative, never local machine/cache paths.
            label = path.relative_to(directory).as_posix()
            sections.append(f'\n--- {label} ---\n{path.read_text(encoding="utf-8").rstrip()}\n')
    return ''.join(sections)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', action='append', help='Repeat for every shipped target; default rustc host')
    args = parser.parse_args()
    targets = args.target
    if not targets:
        version = subprocess.run(['rustc', '-vV'], capture_output=True, text=True, check=True).stdout
        targets = [line.removeprefix('host: ') for line in version.splitlines() if line.startswith('host: ')]
        if len(targets) != 1:
            raise ValueError('cannot identify bootstrap target')
    text = collect(args.launcher_root, targets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding='utf-8', newline='\n')
    print('Bootstrap license/notice texts collected from locked Cargo packages.')


if __name__ == '__main__':
    main()
