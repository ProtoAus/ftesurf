"""Run the exact sprite draw-list builder in a small dedicated-server QC VM.

Synthetic ordering/lifetime controls, NOT a rendered-image or performance test.
Uses the existing p1341carrier fixture pattern. Output must be a NEW directory
under the caller's owned task root; no install or player data is modified.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import socket
import struct
import subprocess


def function(source, name):
    match = re.search(r'(?ms)^void\([^;{]*?\) ' + re.escape(name) + r' =\n\{.*?^\};', source)
    assert match, name
    return match.group()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--compiler', type=Path, required=True)
    p.add_argument('--server', type=Path, required=True)
    p.add_argument('--pak', type=Path, required=True)
    a = p.parse_args()
    source = (a.source / 'src/client/cl_sprites.qc').read_text(encoding='utf8')
    helper = function(source, 'Sprite_DrawLists')
    # Wiring controls: successful adds/reused template slots and every table load invalidate.
    for name in ('Sprite_Add', 'Glow_Add'):
        assert re.search(r'spr_n = spr_n \+ 1;\s+spr_drawdirty = TRUE;', function(source, name)), name
    load = function(source, 'Sprite_LoadForMap')
    assert re.search(r'spr_n = beam_n = beam_spot_n = 0;\s+spr_drawdirty = TRUE;', load)
    draw = function(source, 'Sprite_Draw')
    assert 'if (spr_drawdirty || !spr_drawhead)\n\t\tSprite_DrawLists();' in draw
    assert draw.index('Sprite_DrawLists();') < draw.index('eye = getproperty(VF_ORIGIN);')
    assert 'for (i = spr_drawhead[m]; i >= 0; i = spr_drawnext[i])' in draw
    assert 'for (i = spr_drawhead[SPRMAT_MAX]; i >= 0; i = spr_drawnext[i])' in draw
    constants = '\n'.join(re.findall(r'(?m)^#define (?:SPR_MAX|SPRMAT_MAX|SPRK_GLOW)\s+\d+[^\n]*', source))
    prefix = constants + '''
#define TRUE 1
#define FALSE 0
float spr_n, spr_drawdirty;
float spr_mat[SPR_MAX], spr_kind[SPR_MAX];
float *spr_drawhead;
float *spr_drawnext;
float checks, failures;
void(float ok, string label) Check =
{
    checks = checks + 1;
    if (!ok) { failures = failures + 1; bprint(2, strcat("DRAWLIST FAIL ", label, "\\n")); }
};
'''
    tests = r'''
void() Compare =
{
    local float i, m, found, expected, visits;
    spr_drawdirty = TRUE;
    Sprite_DrawLists();
    Check(!spr_drawdirty, "rebuild acted and cleared dirty");
    visits = 0;
    for (m = 0; m <= SPRMAT_MAX; m = m + 1)
    {
        found = spr_drawhead[m];
        for (i = 0; i < spr_n; i = i + 1)
        {
            if (m == SPRMAT_MAX)
                expected = (spr_kind[i] == SPRK_GLOW);
            else
                expected = (spr_kind[i] != SPRK_GLOW && spr_mat[i] == m);
            if (!expected) continue;
            Check(found == i, "same ascending slot as full scan");
            if (found < 0) return;
            visits = visits + 1;
            if (visits > SPR_MAX) { Check(FALSE, "cycle"); return; }
            found = spr_drawnext[found];
        }
        Check(found == -1, "no extra slot in pass");
    }
    Check(visits == spr_n, "each live slot visited exactly once");
};
void() worldspawn =
{
    local float i, mode;
    spr_n = 0; Compare();
    for (mode = 0; mode < 5; mode = mode + 1)
    {
        spr_n = SPR_MAX;
        for (i = 0; i < spr_n; i = i + 1)
        {
            spr_kind[i] = 0;
            spr_mat[i] = min(floor(random() * SPRMAT_MAX), SPRMAT_MAX - 1);
            if (mode == 0) spr_mat[i] = 0;
            if (mode == 1 || (mode == 2 && random() < 0.25))
            { spr_kind[i] = SPRK_GLOW; spr_mat[i] = -1; }
            if (mode == 3) spr_mat[i] = SPRMAT_MAX - 1;
        }
        Compare();
        // Same-count template slot reuse, including material<->glow changes.
        spr_mat[0] = SPRMAT_MAX - 1; spr_kind[0] = 0;
        spr_mat[SPR_MAX - 1] = -1; spr_kind[SPR_MAX - 1] = SPRK_GLOW;
        spr_mat[511] = 1; spr_kind[511] = 1;
        Compare();
        // Shrink/reload and append after an empty table must discard old chains.
        spr_n = 1; Compare(); spr_n = 0; Compare();
        spr_n = 1; spr_mat[0] = 0; spr_kind[0] = 0; Compare();
    }
    bprint(2, sprintf("DRAWLIST RESULT checks=%g failures=%g\n", checks, failures));
};
void() StartFrame = {};
void() SetNewParms = {};
void() SetChangeParms = {};
void() ClientConnect = {};
void() PutClientInServer = {};
void() ClientDisconnect = {};
void() ClientKill = {};
void() PlayerPreThink = {};
void() PlayerPostThink = {};
void() SpectatorConnect = {};
void() SpectatorThink = {};
void() SpectatorDisconnect = {};
'''
    out = a.out.resolve()
    out.mkdir(exist_ok=False)
    (out / 'src').mkdir()
    (out / 'ftesurf/maps').mkdir(parents=True)
    shutil.copy2(a.source / 'src/defs/sv_defs.qc', out / 'src/defs.qc')
    (out / 'src/test.qc').write_text(prefix + helper + tests, encoding='utf8')
    (out / 'src/progs.src').write_text('../ftesurf/qwprogs.dat\ndefs.qc\ntest.qc\n')
    result = subprocess.run([str(a.compiler.resolve()), '-srcfile', 'progs.src'], cwd=out / 'src', capture_output=True, timeout=30)
    log = result.stdout + result.stderr
    (out / 'compile.log').write_bytes(log)
    assert result.returncode == 0, 'QC compile failed; see compile.log'
    warnings = [line for line in log.splitlines() if re.search(rb'warning', line, re.I)
                and not re.fullmatch(rb'\s*Done\.\s+0 warnings\s*', line, re.I)]
    assert not warnings, warnings
    with a.pak.open('rb') as pak:
        magic, offset, size = struct.unpack('<4sii', pak.read(12))
        assert magic == b'PACK' and size % 64 == 0
        pak.seek(offset)
        directory = pak.read(size)
        entries = (struct.unpack('<56sii', directory[i:i+64]) for i in range(0, size, 64))
        entry = next(e for e in entries if e[0].split(b'\0', 1)[0] == b'maps/start.bsp')
        pak.seek(entry[1])
        body = pak.read(entry[2])
        assert len(body) == entry[2]
    (out / 'ftesurf/maps/start.bsp').write_bytes(body)
    (out / 'default.fmf').write_text('FTEMANIFEST 1\nGAME DrawListUnit\nNAME "Sprite ordering unit"\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\nMAINCONFIG unused\n')
    (out / 'ftesurf/unit.cfg').write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nlog_enable 1\nlog_developer 1\nlog_name drawlist-unit\ndeveloper 1\nsv_public 0\nsv_progs qwprogs.dat\nmap start\nquit\n')
    exe = out / 'fteqwsv64.exe'
    shutil.copy2(a.server, exe)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    command = [str(exe), '-manifest', str(out / 'default.fmf'), '-basedir', str(out), '-port', str(port), '+exec', 'unit.cfg']
    (out / 'inputs.json').write_text(json.dumps({'command': command, 'helper_sha256': hashlib.sha256(helper.encode()).hexdigest(), 'source_sha256': hashlib.sha256(source.encode()).hexdigest()}, indent=2) + '\n')
    with (out / 'process.log').open('wb') as log:
        process = subprocess.Popen(command, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        (out / 'owned-pid.json').write_text(json.dumps({'pid': process.pid, 'image': str(exe)}) + '\n')
        try:
            code = process.wait(timeout=45)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
            raise
    logs = b'\n'.join(f.read_bytes() for f in (out / 'ftesurf').rglob('*.log')) + (out / 'process.log').read_bytes()
    (out / 'combined.log').write_bytes(logs)
    assert code == 0, ('owned server exit', code)
    results = re.findall(rb'DRAWLIST RESULT checks=(\d+) failures=(\d+)', logs)
    assert results and all(int(checks) >= 12000 and int(fails) == 0 for checks, fails in results), results
    assert b'DRAWLIST FAIL' not in logs
    print('Exact QC helper: checks=%s failures=%s; synthetic ordering/lifetime only.' % tuple(x.decode() for x in results[0]))


if __name__ == '__main__':
    main()
