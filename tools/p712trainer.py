#!/usr/bin/env python3
"""Demo trainer runtime falsifier: recorded clocks, native/Momentum and original KSF.

No player recordings required. Uses ui_gallery's owned dedicated-socket rig.
Control: pass unmodified QC --control (same cfg/fixtures, trainer remains hidden).
Subject: checks independent authored +/-15 ms flips, pause/rate/seek identity,
unknown-input abstention, sample-budget catchup, and replay-to-live reset.
"""
import argparse
import json
from pathlib import Path
import re
import struct
import ui_gallery as G

TICK = .015


def samples(count=140):
    yaw = 0.
    z = 100.
    for i in range(count):
        k = i % 70
        air = 10 <= k < 60
        turn = (1 if k < 30 or k >= 50 else -1) if air else 0
        # A late L swap at 31; an early R swap at 49.
        side = 1 if k < 31 or k >= 49 else -1
        yaw -= turn * 90 * TICK
        vz = (288 - (k - 10) * 12) if air else 0
        z += vz * TICK
        yield ((i - 10) * TICK, i * 15., 0., z, 1000., 0., vz,
               0., yaw, 0 if air else 1, 8 if side > 0 else 4, 0, side * 450, 0)


def recording(kind, count=140):
    hdr = ['FTESURF-REC 4', 'map uigallery.map', 'owner DemoTrainerFixture',
           'runid p709', 'startseg 0', 'tickrate .015', 'movetickrate .015', 'flags 0']
    if kind == 'native':
        hdr += ['pmpin airaccelerate=150 maxspeed=250 maxairspeed=30 gravity=800']
    else:
        hdr += ['foreign momentum fixture', 'momdemo fixture']
        if kind != 'missing': hdr += ['moves wishvel 450']
    lines = hdr[:]
    for r in samples(count):
        if kind == 'missing': r = (*r[:11], 0, 0, 0)
        lines.append(' '.join(f'{x:.6f}' for x in r) + ' 0 0 0')
    lines.append(f'end {count - 11} {count} 0 0')
    return '\n'.join(lines) + '\n'


def binary(version):
    marks = [(0, 2, 1), (10, 3, 1), (139, 2, 99)]
    b = struct.pack('<4i', version, 0, 0, len(marks))
    if version == 3: b += struct.pack('<2i', 18, 3) + bytes(12)
    for tick, touch, zone in marks:
        b += struct.pack('<3i', tick, touch, zone) + bytes(512)
    for r in samples():
        t, x, y, z, vx, vy, vz, pitch, yaw, flags, keys, fw, side, up = r
        # CSS button namespace, NOT the .rec key mask.
        button = 1024 if side > 0 else 512
        b += struct.pack('<i9f', button, x, y, z, pitch, yaw, 0, vx, vy, vz)
        if version == 3:
            b += struct.pack('<3i2f2if', flags, 0, 0, fw, side, 0, 0, up)
    return b


def check(log, control):
    text = re.sub(r'(?m)^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', log)
    assert not re.search(r'QC runtime error|CSQC_Abort|Menu_Abort|runaway loop|Unknown command|-- refused|replay: nothing loaded', text), 'runtime/command/reader fault'
    blocks = {}
    for label, body in re.findall(r'P712 BEGIN (\w+)\n(.*?)P712 END \1\n', text, re.S):
        states = re.findall(r'trainer: demo (\d+) ready (\d+) missing (\d+) contact (\d+) tick ([\d.]+)', body)
        rows = [tuple(map(float, r)) for r in re.findall(
            r'trainer: sample (\d+) dir (-?[\d.]+) dur (-?[\d.]+) sync (-?[\d.]+) wrong (-?[\d.]+) graded (-?[\d.]+) q (-?[\d.]+)', body)]
        panel = re.search(r'trainer: panel ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)', body)
        assert 'replay: nothing loaded' not in body, label
        blocks[label] = {'states': states, 'rows': rows, 'panel': panel.groups() if panel else None}
    required = ['native', 'paused', 'slow', 'fast', 'back', 'mom', 'ksf2', 'ksf3', 'missing', 'long', 'offon', 'closed']
    assert set(blocks) == set(required), blocks.keys()
    if control:
        assert all(float(v) == 0 for v in blocks['native']['panel']), blocks['native']
        assert 'replay:' in text and 'samples' in text  # reader acted; absence of a trainer alone is not a pass
        return blocks
    ref = blocks['native']['rows']
    assert len(ref) == 3, ref
    assert abs(ref[1][3] - .015) < .00005, ref
    assert abs(ref[2][3] + .015) < .00005, ref
    assert all(r[5] > 0 and 0 <= r[6] <= 1 for r in ref), ref
    for label in ('paused', 'slow', 'fast', 'back', 'offon'):
        assert blocks[label]['rows'] == ref, (label, blocks[label]['rows'], ref)
    for label in ('mom', 'ksf3'):
        rows = blocks[label]['rows']
        assert len(rows) == 3, (label, rows)
        assert abs(rows[1][3] - .015) < .00005 and abs(rows[2][3] + .015) < .00005, (label, rows)
        assert all(r[5] == 0 and r[6] == -1 for r in rows), (label, rows)  # no invented mover pins
    rows = blocks['ksf2']['rows']
    assert len(rows) >= 5 and all(r[5] == 0 and r[6] == -1 for r in rows), rows
    assert any(abs(r[3] - .015) < .00005 for r in rows) and any(abs(r[3] + .015) < .00005 for r in rows), rows
    assert blocks['missing']['states'][-1][2] == '1' and not blocks['missing']['rows']
    assert blocks['long']['states'][-1][1] == '1' and blocks['long']['rows']
    assert blocks['closed']['states'][-1][0] == '0' and not blocks['closed']['rows']
    assert all(float(v) > 0 for v in blocks['native']['panel'][2:]), blocks['native']
    return blocks


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--qc-artifacts', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--control', action='store_true')
    a = p.parse_args()
    G.ROOT = Path('C:/FTESurf')  # content only; executable/progs are explicit
    def seed(game):
        dest = game / 'cfg/test'; dest.mkdir(parents=True, exist_ok=True)
        for kind in ('native', 'mom', 'missing'):
            (dest / (kind + '.rec')).write_text(recording(kind))
        (dest / 'long.rec').write_text(recording('native', 2100))
        for v in (2, 3): (dest / f'ksf{v}.rec').write_bytes(binary(v))
    G.seed_runs = seed
    def cfg(args, size, port, http_port, native):
        c = ['cfg_save_auto 0', 'log_enable 1', 'log_dir logs', 'log_name gallery',
             'cl_idlefps 0', 'cl_maxfps 100', 'vid_vsync 0', 'con_notifytime 0', 'con_notifylines 0',
             'developer 0', 'set fs_missingwarn 0', 'set ui_bootcheck 0', 'set rec_terms 4',
             'set run_resume 0', 'name DemoTrainerFixture', 'waitms 1500', 'menu_restart',
             'waitms 1200', f'connect 127.0.0.1:{port}', 'waitms 7000', 'ui_close', 'waitms 500',
             'hud_scale 2', 'hud_trainer 1', 'hud_trainer_size 24', 'hud_trainer_x .25', 'hud_trainer_y .15',
             'hud_trainer_split 1', 'hud_trainer_trace 1', 'hud_trainer_jumps 1', 'hud_trainer_rows 6',
             'hud_watch_skipidle 0', 'hud_watch_info 0', 'hud_watch_path 0']
        def status(label):
            c.extend([f'echo P712 BEGIN {label}', 'trainer status', f'screenshot p712-{label}.png', f'echo P712 END {label}'])
        c += ['replay cfg/test/native.rec', 'replay pause', 'replay seek end', 'wait 80']
        status('native'); c += ['+moveleft', '+right', 'wait 30', '-moveleft', '-right']; status('paused')
        for label, rate in [('slow', '.25'), ('fast', '4')]:
            c += ['replay seek -.15', f'replay speed {rate}', 'replay play', 'waitms 9000' if label == 'slow' else 'waitms 1000', 'replay pause', 'replay seek end', 'wait 30']
            status(label)
        c += ['replay seek .3', 'wait 30', 'replay seek end', 'wait 30']; status('back')
        for name in ('mom', 'ksf2', 'ksf3', 'missing', 'long'):
            c += ['replay stop']
            c += [f'replay ksf cfg/test/{name}.rec uigallery.map 0 FW' if name.startswith('ksf') else f'replay cfg/test/{name}.rec',
                  'replay pause', 'replay seek end', 'wait 100']
            status(name)
        c += ['replay stop', 'replay cfg/test/native.rec', 'replay pause', 'replay seek end', 'wait 30',
              'hud_trainer 0', 'wait 10', 'hud_trainer 1', 'wait 80']; status('offon')
        c += ['replay stop', 'wait 1']; status('closed')
        c += ['echo UIG COMPLETE', 'wait 5', 'quit']
        return '\n'.join(c) + '\n'
    G.config = cfg
    args = argparse.Namespace(out=a.out, engine=Path('C:/FTESurf/ftesurf64.exe'),
        server=Path('C:/FTEQuake/fteqwsv64.exe'), plugins=Path('C:/FTESurf'),
        qc_artifacts=a.qc_artifacts.resolve(), library=None, sizes=[(1280, 720)], hud_scale=2,
        renderer='vk', timeout=180)
    rig = G.run(args)
    report = json.loads((rig / 'report.json').read_text())
    root = rig / '1280x720'
    log = (root / 'ftesurf/logs/gallery.log').read_text(errors='replace')
    results = check(log, a.control)
    (a.out / 'trainer.json').write_text(json.dumps(results, indent=2) + '\n')
    assert report['arms']['1280x720']['returncode'] == 0
    print('P712', 'CONTROL (hidden, reader acted)' if a.control else 'PASS', root)


if __name__ == '__main__': main()
