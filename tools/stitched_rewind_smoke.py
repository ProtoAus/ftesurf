#!/usr/bin/env python3
"""Acted three-cut/long-wait rewind control, warm and fresh-client cold prefix.

Uses a private QC dump seam; never deploy its programs or touch install saves.
Predictions: initial stationary wait ACTS on a running, recording clock; each
cut replaces its future tail, held raw counts/time do not grow, and release grows
from the retained prefix. A fresh VM restores the explicit saved picture and
repeats three cuts WITHIN newly recorded history: pre-load full server snapshots
are not reconstructed from the picture. No idle-tail root cause is presumed.

Pre-P539 baseline is RED on the second/third cold cuts: missing cold recorder
lineage forces another cold reload and drops older state snapshots. Keep the
strict oracle and native server-body/clock controls; silence is not a pass.
"""
import argparse
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SEAM = r'''
void(string label) Stitch_Probe =
{
	local float f, i, n;
	local string s;

	f = fopen(strcat("cfg/test/stitch_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("STITCH PROBE WRITE FAILED\n"); return; }
	n = (tr_raw >= 1) ? buf_getsize(tr_raw) : 0;
	fputs(f, sprintf("FTESURF-STITCH 1 %.6f %g %g %g\n", cltime, n,
	                getstatf(STAT_FS_TIMERSTATE), getstatf(STAT_FS_TIMERFLAGS)));
	fputs(f, sprintf("cursor %.6f head %.6f stopped %g practice %g\n", tr_cur_t,
	                tr_lastt, tr_stopped, tr_practice));
	for (i = 0; i < n; i = i + 1)
	{
		s = bufstr_get(tr_raw, i);
		fputs(f, strcat(s, "\n"));
	}
	fclose(f);
	print("STITCH PROBE ", label, "\n");
};
'''
BASE = '''cfg_save_auto 0
fs_cache 0
name StitchControl
log_enable 1
log_dir logs
log_name runlines_smoke
cl_idlefps 0
cl_maxfps 100
hud_trail 1
set hud_rewind_chase 0
set run_resume 0
waitms 2000
map surf_dune
waitmap 60
waitms 6000
menu_restart
ui_close
con_notifystyle 0
con_notifytime 0
con_notifytime_error 0
con_notifylines 0
'''

SERVER_SEAM = r'''
void(string label, float got, float expected) Stitch_GuardCheck =
{
	print(sprintf("STITCH GUARD %s %d %d\n", label, got, expected));
};
void() SV_StitchGuards =
{
	local entity e, sg_peer;

	e = spawn();
	sg_peer = spawn();
	SV_RecKeysReset();
	SV_RecGenBegin(e);
	Stitch_GuardCheck("fresh-key", strlen(e.rec_rec_branch) == 32, TRUE);
	rs_branch = strzone(e.rec_rec_branch);
	rs_gen = 0;
	Stitch_GuardCheck("cold-match", SV_RecGenOK(e, 10), TRUE);
	strunzone(rs_branch); rs_branch = strzone("foreign");
	Stitch_GuardCheck("foreign-key", SV_RecGenOK(e, 10), FALSE);
	strunzone(rs_branch); rs_branch = "";
	Stitch_GuardCheck("missing-cold-key", SV_RecGenOK(e, 10), FALSE);
	rs_branch = strzone(e.rec_rec_branch);
	rs_rid = strzone("foreign-run");
	Stitch_GuardCheck("foreign-run", SV_RecGenOK(e, 10), FALSE);
	strunzone(rs_rid); rs_rid = "";
	rs_gen = -1;
	Stitch_GuardCheck("missing-generation", SV_RecGenOK(e, 10), FALSE);
	rs_gen = 1;
	Stitch_GuardCheck("future-generation", SV_RecGenOK(e, 10), FALSE);
	rs_gen = 0;
	SV_RecGenPush(e, 20);
	Stitch_GuardCheck("retained-earlier", SV_RecGenOK(e, 10), TRUE);
	Stitch_GuardCheck("stale-later", SV_RecGenOK(e, 30), FALSE);
	SV_RecGenPush(e, 5);
	Stitch_GuardCheck("intermediate-below-mark", SV_RecGenOK(e, 10), FALSE);
	SV_RecGenBegin(sg_peer);
	Stitch_GuardCheck("other-attachment", SV_RecGenOK(sg_peer, 10), FALSE);
	SV_RecGenBegin(e);
	Stitch_GuardCheck("reattachment", SV_RecGenOK(e, 10), FALSE);
	Stitch_GuardCheck("reset-generation", e.rec_rec_gen, 0);
	SV_RecKeysReset(); rs_gen = 0;
	e.rec_rec_rid = strzone("legacy-run");
	rs_rid = strzone("legacy-run");
	Stitch_GuardCheck("legacy-match", SV_RecGenOK(e, 10), TRUE);
	strunzone(rs_rid); rs_rid = strzone("other-legacy");
	Stitch_GuardCheck("legacy-foreign", SV_RecGenOK(e, 10), FALSE);
	SV_RecKeysReset();
	Stitch_GuardCheck("metadata-reset", rs_branch == "", TRUE);
	SV_RecGenReset(e); SV_RecGenReset(sg_peer);
	Stitch_GuardCheck("attachment-cleared", e.rec_rec_branch == "", TRUE);
	strunzone(e.rec_rec_rid);
	remove(e); remove(sg_peer);
};
.vector stitch_origin;
.float stitch_ticks;
void(entity e, string label) SV_StitchProbe =
{
	local filestream f;

	f = fopen(strcat("cfg/test/server_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("STITCH SERVER WRITE FAILED\n"); return; }
	fputs(f, sprintf("expected %.9g %.9g %.9g\n", e.stitch_origin_x, e.stitch_origin_y, e.stitch_origin_z));
	fputs(f, sprintf("body %.9g %.9g %.9g\n", e.origin_x, e.origin_y, e.origin_z));
	fputs(f, sprintf("ticks %.9g %.9g\n", e.stitch_ticks, e.run_t_ticks));
	fputs(f, sprintf("hold %d %d %d\n", e.rec_sl_hold, e.run_t_freeze, e.run_t_frzon));
	fputs(f, sprintf("identity %d %d\n", strlen(e.rec_rec_rid) > 0, strlen(e.rec_rec_nonce) > 0));
	fclose(f);
};
'''

def probe(label):
    return f'echo ==== STITCH {label} ====\nstitch_probe {label}\ntrail\ncmd timer\ncmd stitchprobe {label}\n'

def cuts(prefix):
    text = ''
    targets = (0.6, 0.4, 0.2) if prefix == 'warm' else (2.0, 1.5, 1.0)
    for i, target in enumerate(targets, 1):
        stem = f'{prefix}{i}'
        text += 'rewind\nwaitms 100\nrewind\nwaitms 350\n'
        text += f'rewind seek {target}\nwaitms 150\n'
        text += probe(stem + '_cursor') + 'rewind status\n'
        if prefix == 'warm' and i == 1:
            text += 'rewind save\nwaitms 500\n'
        text += 'rewind go\nwaitms 1200\n' + probe(stem + '_hold1')
        text += 'waitms 600\n' + probe(stem + '_hold2')
        text += 'waitms 2600\n+forward\nwaitms 350\n-forward\n'
        text += probe(stem + '_release') + 'rewind status\n'
        # A long FAILED branch is genuine counted time, and must ACT before
        # the next cut. It must not return in the next retained prefix.
        text += 'waitms 5000\n' + probe(stem + '_wait')
    return text

WARM = BASE + '''cmd stitchguards
waitms 100
cmd zone_goto 0
waitms 400
+forward
waitms 2300
-forward
''' + probe('beforewait') + 'waitms 6000\n' + probe('initial') + cuts('warm') + 'echo RUNLINES COMPLETE\nquit\n'
COLD = BASE + 'sl_goto 1\nwaitms 650\n' + probe('coldload') + '+forward\nwaitms 1000\n-forward\nwaitms 6000\n' + probe('coldinitial') + cuts('cold') + 'echo RUNLINES COMPLETE\nquit\n'

def once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'Private seam mismatch: {old!r}')
    return text.replace(old, new, 1)

def dump(gd, label):
    lines = (gd / f'cfg/test/stitch_{label}.txt').read_text().splitlines()
    head = lines[0].split()
    assert head[:2] == ['FTESURF-STITCH', '1'], label
    meta = list(map(float, head[2:]))
    cursor = float(lines[1].split()[1])
    rows = [list(map(float, s.split())) for s in lines[2:]]
    assert len(rows) == int(meta[1]) and len(rows) > 10, (label, meta)
    assert all(len(r) == 14 for r in rows), label
    assert all(a[0] <= b[0] for a, b in zip(rows, rows[1:])), label
    return meta, cursor, rows

def native(gd, label):
    widths = {'expected': 3, 'body': 3, 'ticks': 2, 'hold': 3, 'identity': 2}
    fields = {}
    for row in (gd / f'cfg/test/server_{label}.txt').read_text().splitlines():
        parts = row.split()
        assert parts and parts[0] in widths and parts[0] not in fields, 'unknown/duplicate native field'
        name = parts[0]
        assert len(parts) == widths[name] + 1, 'incomplete native observation'
        values = list(map(float, parts[1:]))
        assert all(math.isfinite(x) for x in values), 'non-finite native observation'
        fields[name] = values
    assert fields.keys() == widths.keys(), 'missing native observation'
    return fields

def grade(gd, streamed=True):
    log = (gd / 'logs/runlines_smoke.log').read_text(errors='replace')
    assert 'STITCH PROBE WRITE FAILED' not in log
    serverlog = (gd / 'logs/runlines_server.log').read_text(errors='replace')
    assert 'STITCH SERVER WRITE FAILED' not in serverlog
    assert not any(x in log + serverlog for x in ('QC VM error', 'Unknown command', 'Cannot call', 'stack overflow'))
    guards = re.findall(r'STITCH GUARD ([\w-]+) (\d+) (\d+)', serverlog)
    expected_guards = {'fresh-key', 'cold-match', 'foreign-key', 'missing-cold-key',
                       'foreign-run', 'missing-generation', 'future-generation',
                       'retained-earlier', 'stale-later', 'intermediate-below-mark',
                       'other-attachment', 'reattachment', 'reset-generation',
                       'legacy-match', 'legacy-foreign', 'metadata-reset', 'attachment-cleared'}
    assert len(guards) == len(expected_guards) and {g[0] for g in guards} == expected_guards, 'guard controls did not ACT'
    assert all(got == want for _, got, want in guards), guards
    print(f'PASS {len(guards)} compiled attachment/generation guards.')
    before, _, br = dump(gd, 'beforewait')
    initial, _, ir = dump(gd, 'initial')
    assert initial[0] - before[0] > 5.5 and ir[-1][0] - br[-1][0] > 5, 'initial long wait did not count'
    # Actual recording and freeze evidence comes from SSQC, not the dump seam.
    sections = {}
    for part in log.split('==== STITCH ')[1:]:
        label = part.split(' ====')[0]
        sections[label] = part
    _, _, loaded = dump(gd, 'coldload')
    saved = (gd/'data/saves/surf_dune/save001/trail.txt').read_text().splitlines()
    sr = [list(map(float, s.split())) for s in saved[1:]]
    assert loaded[:len(sr)] == sr and len(sr) > 10, 'cold prefix was not restored'
    assert sr[-1][0] < 1.0, 'cold targets must be after the loaded authoritative state'
    print('PASS cold persisted picture restoration (not full server state history).')
    faults = []
    for prefix in ('warm', 'cold'):
        for i in range(1, 4):
            stem = f'{prefix}{i}'
            current, cut, cr = dump(gd, stem + '_cursor')
            hold1, _, h1 = dump(gd, stem + '_hold1')
            hold2, _, h2 = dump(gd, stem + '_hold2')
            released, _, rr = dump(gd, stem + '_release')
            waited, _, wr = dump(gd, stem + '_wait')
            assert cut > 0 and cr[-1][0] > cut + 4, (stem, 'future long wait did not ACT')
            if abs(h1[-1][0] - cut) > .031:
                reason = f'{stem}: requested {cut:.3f}, retained {h1[-1][0]:.3f}; not the selected prefix'
                print('FAIL', reason)
                faults.append(reason)
                continue
            n1, n2, nr = [native(gd, stem + '_' + arm) for arm in ('hold1', 'hold2', 'release')]
            assert all(n['hold'] == [1, 1, 1] and n['ticks'][0] == n['ticks'][1] > 0 and
                       sum((x-y)**2 for x, y in zip(n['expected'], n['body'])) < .0001
                       for n in (n1, n2)), (stem, 'native body or held clock differs from selected snapshot')
            assert n1['ticks'] == n2['ticks'] and nr['hold'] == [0, 0, 0] and nr['ticks'][1] > n2['ticks'][1], (stem, 'native release did not ACT')
            if streamed and prefix == 'cold':
                assert all(n['identity'] == [0, 0] for n in (n1, n2, nr)), (stem, 'cold stream adopted evidence identity')
            assert h1 == h2 and hold2[0] - hold1[0] > .5, (stem, 'hold grows raw history')
            assert len(rr) > len(h2) and rr[-1][0] > h2[-1][0] + .2, (stem, 'release did not grow')
            assert wr[-1][0] > rr[-1][0] + 4, (stem, 'failed wait not counted')
            assert rr[:len(h2)] == h2, (stem, 'retained prefix was replaced')
            assert re.search(r'practice \d+  recording 1', sections[stem + '_cursor']), (stem, 'not recording')
            assert 'frozen 1 at' in sections[stem + '_hold1'] and 'frozen 1 at' in sections[stem + '_hold2'], (stem, 'not held')
            assert 'frozen 0 at' in sections[stem + '_release'], (stem, 'not released')
            assert re.search(r'rewind: on 0 counting 0 sent 0', sections[stem + '_release']), stem
            print(f'PASS {stem}: cut {cut:.3f}, held {len(h1)}, released {len(rr)}, future wait {wr[-1][0]-rr[-1][0]:.3f}s')
    if faults:
        raise RuntimeError(f'{len(faults)} cold cut controls failed; retained evidence is a regression, not a fix')
    print('PASS six acted cuts remove counted failed waits and exclude held time.')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--grade-only', type=Path)
    ap.add_argument('--buffered', action='store_true')
    ap.add_argument('--visual', action='store_true', help='Trace both cameras and compiled visual discontinuity controls')
    ap.add_argument('--baseline', action='store_true', help='Use HEAD client cursor/state code instead of working-tree edits')
    ap.add_argument('--fps', type=int, choices=(30, 100, 300), default=100)
    a = ap.parse_args()
    if a.grade_only:
        grade(a.grade_only/'ftesurf', not a.buffered)
        if a.visual:
            from stitched_visual import grade as grade_visual
            grade_visual(a.grade_only/'ftesurf')
        return
    a.output_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='stitch-source-', dir=a.output_dir))
    work.rmdir()
    subprocess.run(['git','-C',str(ROOT),'worktree','add','--detach',str(work),'HEAD'], check=True)
    shutil.copy2(ROOT/'src/fteqcc64.exe', work/'src/fteqcc64.exe')
    for rel in ('src/client/cl_rewind.qc','src/client/cl_trail.qc','src/client/cl_trailstate.qc','src/client/cl_trailreplay.qc',
                'src/server/sv_timer.qc','src/server/sv_resume.qc','src/server/sv_saveloc.qc',
                'src/server/sv_rewindstate.qc',
                'src/server/sv_player.qc','tools/runlines_smoke.py'):
        if a.baseline and rel in ('src/client/cl_rewind.qc', 'src/client/cl_trailstate.qc'):
            (work/rel).write_bytes(subprocess.check_output(['git', '-C', str(ROOT), 'show', f'HEAD:{rel}']))
        else:
            shutil.copy2(ROOT/rel, work/rel)
    p = work/'src/client/cl_trail.qc'
    text = once(p.read_text(), 'float() Trail_Console =', SEAM+'\nfloat() Trail_Console =')
    text = once(text, 'if (argv(0) != "trail")', 'if (argv(0) == "stitch_probe") { Stitch_Probe(argv(1)); return TRUE; }\n\tif (argv(0) != "trail")')
    text = once(text, 'registercommand("trail");', 'registercommand("trail");\n\tregistercommand("stitch_probe");')
    p.write_text(text)
    p = work/'src/server/sv_timer.qc'
    p.write_text(p.read_text() + SERVER_SEAM)
    p = work/'src/server/sv_saveloc.qc'
    p.write_text(once(p.read_text(), '\t// At the cap there is no row or id',
                     '\te.stitch_origin = rw_o;\n\te.stitch_ticks = rw_t;\n\t// At the cap there is no row or id'))
    p = work/'src/server/sv_player.qc'
    p.write_text(once(p.read_text(), '\tif (c == "rec_nack")',
                     '\tif (c == "stitchguards") { SV_StitchGuards(); return; }\n\tif (c == "stitchprobe") { SV_StitchProbe(self, argv(1)); return; }\n\tif (c == "rec_nack")'))
    if a.visual:
        from stitched_visual import instrument
        instrument(work)
    cfg = work/'ftesurf/cfg/test/stitched_rewind.cfg'
    stream = int(not a.buffered)
    warm = WARM.replace('map surf_dune\n', f'set rec_stream {stream}\nmap surf_dune\n')
    cold = COLD.replace('map surf_dune\n', f'set rec_stream {stream}\nmap surf_dune\n')
    if a.visual:
        from stitched_visual import config
        warm = config(warm, a.fps, units=True)
        cold = config(cold, a.fps)
    else:
        warm = once(warm, 'cl_maxfps 100\n', f'cl_maxfps {a.fps}\n')
        cold = once(cold, 'cl_maxfps 100\n', f'cl_maxfps {a.fps}\n')
    # The second cfg runs in the SAME isolated rig, via a fresh client process.
    cfg.write_text(warm.replace('echo RUNLINES COMPLETE\nquit\n', 'echo RUNLINES COMPLETE\nexec cfg/test/stitch_finish.cfg\n'))
    (work/'ftesurf/cfg/test/stitch_cold.cfg').write_text(cold)
    subprocess.run(['pwsh','-NoProfile','-File','./build.ps1','-Jobs','8','-QuakeDir',''], cwd=work/'src', check=True)
    # Reuse the safety-conscious harness setup, but keep its owned server while
    # the first client exits and a fresh VM loads the persisted prefix.
    runner = work/'tools/runlines_smoke.py'
    rt = runner.read_text()
    rt = once(rt, "client.wait(timeout=a.timeout)", "client.wait(timeout=a.timeout)\n        warm_log = gd / 'logs/runlines_smoke.log'\n        shutil.copyfile(warm_log, gd / 'logs/stitch_warm.log')\n        coldcfg = ROOT / 'ftesurf/cfg/test/stitch_cold.cfg'\n        (gd / 'cfg/test/stitch_cold.cfg').write_text(coldcfg.read_text().replace('map surf_dune\\n', f'connect 127.0.0.1:{a.port}\\n'))\n        client = subprocess.Popen([str(executable), *common, '-window', '+exec', 'cfg/test/stitch_cold.cfg'], cwd=a.content, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n        client.wait(timeout=a.timeout)")
    rt = once(rt, "target.write_text(text, encoding='utf-8')", "target.write_text(text, encoding='utf-8')\n        (gd / 'cfg/test/stitch_finish.cfg').write_text('quit\\n')")
    rt = once(rt, "'runlines_server', '+map', 'surf_dune'", f"'runlines_server', '+set', 'rec_stream', '{stream}', '+map', 'surf_dune'")
    runner.write_text(rt)
    result = subprocess.run([sys.executable,'-B',str(runner),str(cfg),'--dedicated','--port','27618','--timeout','180','--output-dir',str(a.output_dir)], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError('Acted stitch control failed; preserve retained artifacts')
    rig = Path(result.stdout.strip().splitlines()[-1].removeprefix('Retained private rig: '))
    print('Retained source:', work)
    print('Retained rig:', rig)
    grade(rig/'ftesurf', not a.buffered)
    if a.visual:
        from stitched_visual import grade as grade_visual
        grade_visual(rig/'ftesurf')

if __name__ == '__main__':
    main()
