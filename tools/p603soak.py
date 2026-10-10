#!/usr/bin/env python3
"""Open/font/close churn, then a held-open soak, on the product scoreboard.

Uninstrumented progs and product commands only. Each cycle the provider prints its
own open/close/upload counters and the driver samples the client's private bytes.
Arms: native; legacy (same script with the table off: the noise floor); leak (a
provider built with DestroyContext removed, whose floor must rise well above
native's, or the statistic measures nothing). GL only; one machine.

Private bytes are not flat here: QC temp strings go to a threshold collector, so the
process saw-tooths by tens of MiB whatever is on screen, and a fitted slope reads the
teeth (the first run failed every arm that way, legacy included). The grade is on the
FLOOR: min of the last third minus min of the first third. A saw-tooth comes back to
its floor; a leak raises it. Use enough fast cycles that a leak outgrows the teeth.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import tempfile
import time
from types import SimpleNamespace

from p590bridge import sha
from p598build import build
from p603dense_variant import create
from p603perf import memory, parse, prepare, status

ARMS = ('native', 'legacy', 'leak')
MIB = 1 << 20
PAIR_BOUND = 32 * MIB     # native floor rise above legacy's, cycles and hold separately
LEAK_MARGIN = 96 * MIB    # the leak arm's floor must rise this far above native's
HOLD_DRIFT = 0.15         # last third against first third, QC UpdateView median


def warm(cycles):
    return max(10, cycles // 10)   # left out: first-use caches settle


def config(arm, port, cycles, hold, sets=(), waits=(400, 200, 200)):
    lines = ['cfg_save_auto 0', *(f'set {k} {v}' for k, v in sets), 'set log_enable 1', 'set log_dir logs', 'set log_name perf', 'set log_readable 1',
             'set cl_idlefps 0', 'set cl_maxfps 100', 'set vid_vsync 0', 'set r_speeds 2',
             'set pr_enable_profiling 0', 'set vid_conautoscale 0', 'set vid_conwidth 1920',
             'set vid_conheight 1080', 'set hud_scale 2', 'set gl_conback 0', 'set scr_conalpha 0',
             'set developer 0', 'set log_developer 0', 'set name P603Soak', 'set cl_run_upload 0',
             'set cl_board_url ""', 'waitms 1500', 'menu_restart', 'waitms 700', 'ui_close',
             'plug_load ui_imgui', f'connect 127.0.0.1:{port}', 'waitms 6500', 'ui_close',
             f'set ui_native_scores {int(arm != "legacy")}', 'set ui_native_scores_font 13', 'set hud_scale 2',
             'scores tab local', 'scores leg 0', 'scores status', 'scores close', 'waitms 500',
             'echo P603 SOAK BASE', 'ui_imgui_status', *(k for k, _ in sets)]
    for c in range(cycles):
        lines += ['scores open', f'waitms {waits[0]}']
        for px in (16, 24, 13): lines += [f'set ui_native_scores_font {px}', f'waitms {waits[1]}']
        lines += [f'echo P603 SOAK OPEN {c}', 'ui_imgui_status', 'scores close', f'waitms {waits[2]}',
                  f'echo P603 SOAK CYCLE {c}', 'ui_imgui_status']
    lines += ['scores open', 'waitms 1500', 'echo P603 SOAK HOLDBEGIN', 'ui_imgui_status']
    for s in range(hold):
        # parse() keys dumps by "P603 PERF SAMPLE <cycle> <phase> <n>".
        lines += ['waitms 1900', f'echo P603 SOAK HOLD {s}', f'echo P603 PERF SAMPLE 0 hold {s}',
                  'r_speeds_dump', 'waitms 100']
    lines += ['echo P603 PERF END 0 hold', 'echo P603 SOAK HOLDEND', 'ui_imgui_status', 'screenshot soak_hold',
              'scores close', 'waitms 500', 'echo P603 SOAK CLOSED', 'ui_imgui_status',
              'echo P603 SOAK FINISHED', 'quit']
    return '\n'.join(lines) + '\n'


def fit_growth(points):
    """Least-squares slope times the span. Reported only: on a saw-tooth it reads the teeth."""
    xs = [x for x, _ in points]; ys = [y for _, y in points]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return 0.0 if not den else sum((x - mx) * (y - my) for x, y in points) / den * (max(xs) - min(xs))


def floor_rise(points):
    ys = [y for _, y in sorted(points)]; third = len(ys) // 3
    return min(ys[-third:]) - min(ys[:third])


def marks(text):
    """Counter line that follows each marker: {'BASE': {...}, ('OPEN', 3): {...}, ...}."""
    out = {}
    for name, n, line in re.findall(r'P603 SOAK (BASE|OPEN|CYCLE|HOLDBEGIN|HOLDEND|CLOSED)(?: (\d+))?\s*[\r\n]+'
                                    r'(?:[^\r\n]*[\r\n]+)??[^\r\n]*?(UIIMGUI STATUS [^\r\n]+)', text):
        key = (name, int(n)) if n else name
        if key in out: raise ValueError('duplicate marker ' + str(key))
        out[key] = status(line)[0]
    return out


def measure(rig, arm, report):
    meta = report['arms'][arm]
    text = (rig / arm / 'ftesurf/logs/perf.log').read_text(errors='replace')
    cycles, hold = report['cycles'], report['hold']
    mem = {(m['kind'], m['n']): m['private_bytes'] for m in meta['memory']}
    result = {'focus_lines': len(re.findall(r'\[focus\]', text)), 'errors': []}
    def need(ok, why):
        if not ok: result['errors'].append(arm + ': ' + why)
    need(meta.get('returncode') == 0 and meta.get('timed_out') is False, 'failed exit')
    need(text.count('P603 SOAK FINISHED') == 1 and 'FTESurf CSQC loaded' in text, 'incomplete/quiet')
    need(not re.search(r'Unknown command|QC runtime error|CSQC_Abort|Shader double free|P603 (STATE|CAP)', text, re.I),
         'runtime error/instrumented QC')
    need('OpenGL renderer initialized' in text, 'GL backend not positively identified')
    need(re.search(rf'rows: {report["rows"]} \({report["rows"]} pass the filter\)', text), 'row workload absent/wrong')
    try: m = marks(text)
    except (ValueError, IndexError) as e: need(False, 'counters: ' + str(e)); return result
    native = arm != 'legacy'
    base = m.get('BASE')
    need(base is not None and base.get('live') == 0, 'no closed baseline')
    if base is None: return result
    for c in range(cycles):
        o, k = m.get(('OPEN', c)), m.get(('CYCLE', c))
        if o is None or k is None: need(False, f'cycle {c} counters missing'); continue
        need(o.get('live') == int(native), f'cycle {c}: table {"did not open" if native else "opened"} natively')
        need(k.get('live') == 0 and k.get('opens') == k.get('closes'), f'cycle {c}: not released')
        step = c + 1 if native else 0
        need(k.get('opens') == base['opens'] + step and k.get('uploads') == base['uploads'] + step,
             f'cycle {c}: opens/uploads are not one per cycle')
        need(k.get('rejected') == 0 and k.get('failed') == 0, f'cycle {c}: rejected/failed draw')
        need(('CYCLE', c) in mem, f'cycle {c}: memory sample missing')
    points = [(c, mem[('CYCLE', c)]) for c in range(warm(cycles), cycles) if ('CYCLE', c) in mem]
    need(len(points) == cycles - warm(cycles), 'cycle memory series incomplete')
    if len(points) >= 9: result.update(cycle_floor_rise=floor_rise(points), cycle_fit_growth=fit_growth(points))
    b, e = m.get('HOLDBEGIN'), m.get('HOLDEND')
    need(b is not None and e is not None, 'hold counters missing')
    if b and e:
        need(b.get('live') == int(native) and e.get('live') == int(native), 'hold: wrong route')
        need(all(b.get(k) == e.get(k) for k in ('opens', 'closes', 'uploads')), 'hold: reopened/reuploaded')
        need((e.get('frames', 0) > b.get('frames', 0)) == native, 'hold: native frames did not act')
        need(e.get('rejected') == 0, 'hold: rejected draw')
    rows = [r for r in parse(text) if r['phase'] == 'hold']
    need(len(rows) == hold and all(r['valid_dump'] for r in rows), 'hold CPU dumps missing/invalid')
    cpu = [r['buckets'].get('QC UpdateView', 0) for r in sorted(rows, key=lambda r: r['sample'])]
    if len(cpu) >= 6:
        third = len(cpu) // 3
        first, last = statistics.median(cpu[:third]), statistics.median(cpu[-third:])
        result.update(hold_qc_first=first, hold_qc_last=last, hold_qc_median=statistics.median(cpu),
                      hold_qc_min=min(cpu), hold_qc_max=max(cpu))
        need(first > 0 and abs(last - first) <= HOLD_DRIFT * first, f'hold: QC UpdateView drifted {first:.1f} -> {last:.1f}')
    points = [(s, mem[('HOLD', s)]) for s in range(hold) if ('HOLD', s) in mem]
    need(len(points) == hold, 'hold memory series incomplete')
    if len(points) >= 9: result.update(hold_floor_rise=floor_rise(points), hold_fit_growth=fit_growth(points))
    closed = m.get('CLOSED')
    need(closed is not None and closed.get('live') == 0 and closed.get('opens') == closed.get('closes'), 'final close leaked an owner')
    need(len(list((rig / arm / 'ftesurf/screenshots').glob('soak_hold.*'))) == 1, 'hold screenshot missing')
    return result


def grade(rig):
    report = json.loads((rig / 'report.json').read_text())
    errors, results = [], {}
    if set(report.get('planned_arms', ())) != set(report.get('arms', {})): errors.append('planned/acting arm set differs')
    for arm in report.get('arms', {}):
        if not (rig / arm / 'ftesurf/logs/perf.log').exists(): errors.append(arm + ': missing log'); continue
        results[arm] = measure(rig, arm, report)
        errors += results[arm].pop('errors')
    for phase in ('cycle', 'hold'):
        rise = {arm: r.get(phase + '_floor_rise') for arm, r in results.items()}
        if 'native' in rise and 'legacy' in rise:
            if None in (rise['native'], rise['legacy']): errors.append(f'{phase}: floor not measured')
            elif rise['native'] - rise['legacy'] >= PAIR_BOUND:
                errors.append(f'native: {phase} floor rises {(rise["native"] - rise["legacy"]) / MIB:.1f} MiB more than legacy')
        if phase == 'cycle' and 'leak' in rise:
            # Without native beside it the leak arm has nothing to stand clear of.
            if None in (rise['leak'], rise.get('native')) or rise['leak'] - rise['native'] < LEAK_MARGIN:
                errors.append(f'leak arm floor {rise["leak"]} against native {rise.get("native")}: the statistic does not discriminate')
    return errors, results


def run(a):
    if os.name != 'nt': raise RuntimeError('Windows runtime required; grade is portable')
    out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in (out, *out.parents)): raise RuntimeError('--out requires ancestor OWNER.md')
    out.mkdir(parents=True, exist_ok=True)
    rig = Path(tempfile.mkdtemp(prefix='p603-soak-', dir=out))
    plugins = {'native': a.plugin, 'legacy': a.plugin}
    if 'leak' in a.arms:
        source = create(a.fte.resolve(), rig / 'leak-source', site='plugins/ui_imgui/ui_imgui.cpp',
                        old='if (c->imgui) ImGui::DestroyContext(c->imgui);', new='', variant='context-leak',
                        factor='Close no longer destroys its ImGui context')
        plugins['leak'] = build(source, rig / 'leak-build', a.cxx.resolve())
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'planned_arms': list(a.arms), 'rows': a.rows,
              'cycles': a.cycles, 'hold': a.hold, 'sets': a.set, 'waits_ms': a.waits, 'csprogs_sha256': sha(a.qc_artifacts / 'csprogs.dat'),
              'engine_sha256': sha(a.engine), 'plugin_sha256': {k: sha(v) for k, v in plugins.items() if k in a.arms},
              'arms': {}, 'limits': 'One machine, GL, synthetic local rows. Process private bytes cannot see a leak '
              'inside the CSQC heap, and the floor statistic cannot see one smaller than about PAIR_BOUND over two '
              'thirds of the counted samples. Font changes and open/close churn only; paging needs real clicks.'}
    for arm in a.arms:
        root = rig / arm
        port = prepare(root, SimpleNamespace(rows=a.rows, qc_artifacts=a.qc_artifacts, engine=a.engine,
                                             server=a.server, plugin=plugins[arm]), arm)
        game = root / 'ftesurf'
        (game / 'perf.cfg').write_text(config(arm, port, a.cycles, a.hold, a.set, a.waits))
        svcmd = [str(root / 'fteqwsv64.exe'), '-basedir', str(root), '-nohome', '-noplugins', '-port', str(port),
                 '+set', 'cfg_save_auto', '0', '+set', 'sv_public', '0', '+set', 'lobby_dir', '', '+map', 'p603scores.map']
        clcmd = [str(root / 'ftesurf64.exe'), '-basedir', str(root), '-nohome', '-nosound', '-nocdaudio', '-window',
                 '+set', 'plug_loaddefault', '0', '+set', 'vid_width', '1920', '+set', 'vid_height', '1080',
                 '+set', 'vid_fullscreen', '0', '+set', 'vid_winmaximize', '0', '+set', 'vid_renderer', 'gl',
                 '+set', 'cfg_save_auto', '0', '+exec', 'perf.cfg']
        memories, seen, timed, rc = [], set(), False, None
        with (root / 'server.log').open('w') as so, (root / 'launch.log').open('w') as co:
            sv = subprocess.Popen(svcmd, cwd=str(root), stdout=so, stderr=subprocess.STDOUT)
            try:
                time.sleep(2)
                if sv.poll() is not None: raise RuntimeError('owned server exited: ' + str(root))
                cl = subprocess.Popen(clcmd, cwd=str(root), stdout=co, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 120 + a.cycles * (sum(a.waits) + 2 * a.waits[1] + 700) / 1000 + a.hold * 2.5
                    log = game / 'logs/perf.log'
                    while cl.poll() is None:
                        text = log.read_text(errors='replace') if log.exists() else ''
                        for kind, n in re.findall(r'P603 SOAK (CYCLE|HOLD) (\d+)', text):
                            if (kind, n) not in seen:
                                memories.append({'kind': kind, 'n': int(n), **memory(cl._handle)}); seen.add((kind, n))
                        if time.monotonic() > deadline: timed = True; cl.terminate(); break
                        time.sleep(0.05)
                    rc = cl.wait(timeout=10)
                finally:
                    if cl.poll() is None: cl.terminate(); cl.wait(timeout=10)
            finally:
                if sv.poll() is None: sv.terminate(); sv.wait(timeout=10)
        report['arms'][arm] = {'returncode': rc, 'timed_out': timed, 'memory': memories}
        (rig / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print('Completed', arm, root, flush=True)
    return rig


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte', type=Path, default=Path('C:/msys64/home/Lex/fteqw'))
    p.add_argument('--engine', type=Path)
    p.add_argument('--server', type=Path)
    p.add_argument('--qc-artifacts', type=Path)
    p.add_argument('--plugin', type=Path)
    p.add_argument('--cxx', type=Path, default=Path('C:/msys64/ucrt64/bin/g++.exe'))
    p.add_argument('--out', type=Path)
    p.add_argument('--arms', nargs='+', choices=ARMS, default=list(ARMS))
    p.add_argument('--rows', type=int, default=32, choices=range(6, 257))
    p.add_argument('--cycles', type=int, default=800)
    p.add_argument('--waits', type=int, nargs=3, default=[40, 20, 40], metavar=('OPEN', 'FONT', 'CLOSED'),
                   help='ms: after open, after each of three font changes, after close')
    p.add_argument('--hold', type=int, default=90, help='held-open samples, 2 s apart')
    p.add_argument('--set', nargs=2, action='append', default=[], metavar=('CVAR', 'VALUE'), help='set before the map loads')
    p.add_argument('--grade', type=Path, help='regrade a retained rig')
    a = p.parse_args()
    if a.grade is None:
        if None in (a.engine, a.server, a.qc_artifacts, a.plugin, a.out): p.error('run requires --engine --server --qc-artifacts --plugin --out')
        if a.cycles < 60 or a.hold < 9: p.error('too few cycles/hold samples for thirds')
    rig = a.grade or run(a)
    errors, results = grade(rig)
    (rig / 'grade.json').write_text(json.dumps({'errors': errors, 'results': results}, indent=2) + '\n')
    for arm, r in results.items(): print(arm, json.dumps(r))
    for e in errors: print('FAIL', e)
    print('Soak rig', rig, 'failures', len(errors)); raise SystemExit(bool(errors))
