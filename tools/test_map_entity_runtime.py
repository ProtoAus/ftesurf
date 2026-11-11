"""Bounded CPU/dedicated probe for the bunnyrace doors and bhop landing lifecycle.

Requires explicit owned --runtime, qualified --compiler, --engine and --plugin.
Uses a test-only StartFrame wrapper; does not edit production source or an install.
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import socket
import subprocess


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'compiler', 'engine', 'plugin', 'bsp'):
        ap.add_argument('--' + name, type=pathlib.Path, required=True)
    ap.add_argument('--port', type=int, default=27602)
    ap.add_argument('--control', action='store_true', help='compile the inspected base implementation; expect acting failures')
    ap.add_argument('--source', type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parents[1])
    args = ap.parse_args()
    assert hashlib.sha1(args.bsp.read_bytes()).hexdigest() == '25c0ae5ff2c98a4683090118cecb714ee662033f'
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', args.port))
    assert 27520 <= args.port <= 27620
    raw = args.runtime.absolute()
    for parent in (raw, *raw.parents):
        if parent.exists():
            assert not parent.is_symlink() and not (getattr(parent.lstat(), 'st_file_attributes', 0) & 0x400)
    root = raw.resolve()
    assert any((parent / 'OWNER.md').is_file() for parent in root.parents), 'runtime needs an owned task ancestor'
    root.mkdir(parents=True, exist_ok=False)  # never replace earlier evidence
    inputs = {name: {'path': str(getattr(args, name)), 'sha256': hashlib.sha256(getattr(args, name).read_bytes()).hexdigest()}
              for name in ('compiler', 'engine', 'plugin', 'bsp')}
    (root / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n', encoding='utf8')
    game = root / 'ftesurf'
    (game / 'maps').mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.bsp, game / 'maps/bhop_bunnyrace.bsp')
    shutil.copy2(args.plugin, root / 'fteplug_hl2_x64.dll')
    shutil.copy2(args.source.resolve() / 'default.fmf', root / 'default.fmf')
    src = args.source.resolve() / 'src'
    probe = root / 'sv_main_probe.qc'
    probe.write_text((src / 'server/sv_main.qc').read_text(encoding='utf8').replace(
        'void() StartFrame =', 'void() MapEntityOriginalStartFrame =', 1) + '\n' +
        pathlib.Path(__file__).with_name('map_entity_runtime_probe.qc').read_text(encoding='utf8'), encoding='utf8')
    control = root / 'sv_entities_control.qc'
    if args.control:
        base = subprocess.run(['git', 'show', '02e58218d874707af1321bb8fdb18cc4f32be31c:src/server/sv_entities.qc'],
                              cwd=args.source, capture_output=True, text=True, check=True).stdout
        control.write_text(base + '\n.float vbsp_door_slide, hammerid;\n.vector movedir;\nfloat(string m, string c) SV_BunnyDoorMatch = { return FALSE; };\n', encoding='utf8')
    manifest = [pathlib.Path(os.path.relpath(game / 'qwprogs.dat', src)).as_posix()]
    for line in (src / 'sv_progs.src').read_text(encoding='utf8').splitlines()[1:]:
        path = line.split('//', 1)[0].strip()
        if not path:
            continue
        replacement = probe if path == 'server/sv_main.qc' else control if args.control and path == 'server/sv_entities.qc' else None
        manifest.append(pathlib.Path(os.path.relpath(replacement, src)).as_posix() if replacement else path)
    source_list = src / 'mapprobe-test.src'
    owned_manifest = False
    manifest_text = '\n'.join(manifest) + '\n'
    try:
        with source_list.open('x', encoding='utf8') as handle:
            handle.write(manifest_text)
        owned_manifest = True
        result = subprocess.run([str(args.compiler.resolve()), '-max_strings', '4194304', '-srcfile', source_list.name], cwd=src,
                                capture_output=True, text=True, timeout=120)
        (root / 'compile.log').write_text(result.stdout + result.stderr, encoding='utf8')
    finally:
        if owned_manifest:
            assert source_list.read_text(encoding='utf8') == manifest_text, 'manifest replaced; preserve it for inspection'
            source_list.unlink()
    assert result.returncode == 0 and 'Done. 0 warnings' in result.stdout + result.stderr, (result.stdout + result.stderr)[-3000:]
    cfg = 'cfg_save_auto 0\nlog_enable 1\nlog_name mapprobe\nplug_load hl2\nsv_public 0\nsv_gamemode none\nset lobby_enable 0\nset sv_bhop_time_limit 100\nset vbsp_entity_io 1\nmap bhop_bunnyrace\n'
    (game / 'mapprobe.cfg').write_text(cfg, encoding='utf8')
    cmd = [str(args.engine.resolve()), '-plugin', '-nohome', '-basedir', str(root),
           '-manifest', str(root / 'default.fmf'), '-port', str(args.port),
           '+set', 'cfg_save_auto', '0', '+exec', 'mapprobe.cfg']
    with (root / 'console.log').open('x', encoding='utf8') as out:
        process = subprocess.Popen(cmd, cwd='C:/FTESurf', stdin=subprocess.PIPE,
                                   stdout=out, stderr=subprocess.STDOUT, creationflags=0x08000000)
        try:
            code = process.wait(timeout=45)
        except subprocess.TimeoutExpired:
            process.terminate()  # only this invocation's owned handle
            process.wait(timeout=10)
            raise
    logs = '\n'.join(p.read_text(encoding='utf8', errors='replace') for p in root.rglob('*.log') if p.name != 'compile.log')
    print('\n'.join(line for line in logs.splitlines() if 'MAPPROBE' in line))
    assert code == 0, code
    if args.control:
        assert 'MAPPROBE FAIL reset-true A-air-B-air-A' in logs
        assert 'MAPPROBE PASS Open input acted' in logs
        assert 'MAPPROBE FAIL both brushes reach authored endpoints' in logs
        assert 'MAPPROBE DONE failures=' in logs and 'MAPPROBE DONE failures=0' not in logs
    else:
        assert 'MAPPROBE DONE failures=0' in logs, 'probe failed or did not act; inspect ' + str(root)


if __name__ == '__main__':
    main()
