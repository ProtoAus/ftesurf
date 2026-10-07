"""Opt-in private visual diagnostics for stitched_rewind_smoke (never deployed)."""
import math
import re
from pathlib import Path

from stitched_rewind_smoke import dump

SEAM = r'''
void() Rewind_Reset;
float vs_checks, vs_failures;
void(float ok, string label) Visual_Check =
{
	vs_checks = vs_checks + 1;
	print(sprintf("VISUAL CHECK %s %d\n", label, ok));
	if (!ok) vs_failures = vs_failures + 1;
};
void() Visual_Units =
{
	local float b, oldraw, oldchase, f;
	local vector a;

	oldraw = tr_raw;
	oldchase = cvar("hud_rewind_chase");
	tr_raw = buf_create_ex("string", 0);
	b = tr_live * LN_CAP;
	Line_Begin(tr_live);
	Line_Add(tr_live, '100 100 100', 100, 0, 0, 0, FALSE);
	Line_Add(tr_live, '110 100 100', 200, 0, 0, 0.03, FALSE);
	Line_End(tr_live);
	bufstr_set(tr_raw, 0, "0 100 100 100 100 0 0 0 0 0 350 0 0 10");
	bufstr_set(tr_raw, 1, "0.03 110 100 100 200 0 0 0 0 0 10 0 0 20");
	rw_on = tr_cur_on = TRUE;
	rw_ack = rw_cd = 0;
	rw_i = 0.5;
	Rewind_Cursor();
	Trail_VisualState(rw_visualt);
	Visual_Check(rw_visualp == '105 100 100' && tr_vis_vel == '150 0 0', "continuous");
	Visual_Check(tr_cur_p == '100 100 100' && tr_cur_t == 0, "sampled-not-retimed");
	Visual_Check(fabs(tr_vis_ang_y) < 0.001, "short-yaw");
	bufstr_set(tr_raw, 1, "0.03 110 100 100 200 0 0 0 1 0 10 0 0 20");
	Trail_VisualState(0.015);
	Visual_Check(tr_vis_vel == '100 0 0' && tr_vis_ang == '10 350 0', "raw-break-columns");
	bufstr_set(tr_raw, 1, "0.03 110 100 100 200 0 0 0 0 1 10 0 0 20");
	Trail_VisualState(0.015);
	Visual_Check(tr_vis_vel == '100 0 0' && tr_vis_ang == '10 350 0', "raw-stitch-columns");
	bufstr_set(tr_raw, 1, "0.03 110 100 100 200 0 0 67108864 0 0 10 0 0 20");
	Trail_VisualState(0.015);
	Visual_Check(tr_vis_vel == '100 0 0', "legacy-flag-break");
	ln_brk[b + 1] = TRUE;
	Rewind_Cursor();
	Visual_Check(rw_visualp == '100 100 100' && rw_visualt == 0, "position-break");
	ln_brk[b + 1] = FALSE;
	Line_Add(tr_live, '1000 1000 100', 0, 0, 0, 0.06, TRUE);
	Line_Add(tr_live, '1000 1010 100', 0, 0, 0, 0.09, FALSE);
	Line_End(tr_live);
	cvar_set("hud_rewind_chase", "1");
	rw_i = 0.5;
	Rewind_Cursor();
	Rewind_Camera();
	a = getproperty(VF_ANGLES);
	Visual_Check(fabs(a_y) < 0.001, "chase-before-break");
	rw_i = 2.5;
	Rewind_Cursor();
	Rewind_Camera();
	a = getproperty(VF_ANGLES);
	Visual_Check(fabs(a_y - 90) < 0.001, "chase-after-break");
	buf_del(tr_raw);
	tr_raw = oldraw;
	cvar_set("hud_rewind_chase", ftos(oldchase));
	Rewind_Reset();
	Line_Clear(tr_live);
	f = fopen("cfg/test/visual_units.txt", FILE_WRITE);
	if (f < 0) { print("VISUAL WRITE FAILED\n"); return; }
	fputs(f, sprintf("units %d %d\n", vs_checks, vs_failures));
	fclose(f);
};
void(string label) Visual_Trace =
{
	local float f, i, b, j, n, oldi, oldchase;
	local vector oldorg, oldang, p0, a0, p1, a1;

	if (!rw_on || rw_ack || rw_cd || !tr_cur_on) return;
	f = fopen(strcat("cfg/test/visual_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("VISUAL WRITE FAILED\n"); return; }
	n = ln_n[tr_live];
	oldi = rw_i;
	oldchase = cvar("hud_rewind_chase");
	oldorg = getproperty(VF_ORIGIN);
	oldang = getproperty(VF_ANGLES);
	fputs(f, sprintf("FTESURF-VISUAL 1 %d %d %g\n", n, buf_getsize(tr_raw), cvar("cl_maxfps")));
	for (i = 0; i <= (n - 1) * 4; i = i + 1)
	{
		rw_i = i / 4;
		Rewind_Cursor();
		Rewind_Present();
		cvar_set("hud_rewind_chase", "0");
		Rewind_Camera();
		p0 = getproperty(VF_ORIGIN); a0 = getproperty(VF_ANGLES);
		cvar_set("hud_rewind_chase", "1");
		Rewind_Camera();
		p1 = getproperty(VF_ORIGIN); a1 = getproperty(VF_ANGLES);
		b = tr_live * LN_CAP + floor(rw_i);
		j = min(tr_live * LN_CAP + n - 1, b + 1);
		fputs(f, sprintf("%.6f %.6f %.6f", rw_i, tr_cur_t, rw_visualt));
		fputs(f, sprintf(" %.6f %.6f %.6f", tr_cur_p_x, tr_cur_p_y, tr_cur_p_z));
		fputs(f, sprintf(" %.6f %.6f %.6f", rw_visualp_x, rw_visualp_y, rw_visualp_z));
		fputs(f, sprintf(" %.6f %.6f %.6f", ui_rw_vel_x, ui_rw_vel_y, ui_rw_vel_z));
		fputs(f, sprintf(" %.6f %.6f %.6f", tr_vis_ang_x, tr_vis_ang_y, tr_vis_ang_z));
		fputs(f, sprintf(" %.6f %.6f %.6f", p0_x, p0_y, p0_z));
		fputs(f, sprintf(" %.6f %.6f %.6f", a0_x, a0_y, a0_z));
		fputs(f, sprintf(" %.6f %.6f %.6f", p1_x, p1_y, p1_z));
		fputs(f, sprintf(" %.6f %.6f %.6f", a1_x, a1_y, a1_z));
		fputs(f, sprintf(" %d %d %.6f %.6f %d\n", ln_brk[b], ln_brk[j], ln_t[b], ln_t[j], Trail_RawIndex(rw_visualt)));
	}
	fclose(f);
	rw_i = oldi;
	Rewind_Cursor();
	Rewind_Present();
	cvar_set("hud_rewind_chase", ftos(oldchase));
	setproperty(VF_ORIGIN, oldorg);
	setproperty(VF_ANGLES, oldang);
	PVS_Publish(oldorg);
	print("VISUAL TRACE ", label, "\n");
};
'''


def instrument(work):
    from stitched_rewind_smoke import once
    p = work / 'src/client/cl_rewind.qc'
    text = once(p.read_text(), 'float() Rewind_Console =', SEAM + '\nfloat() Rewind_Console =')
    text = once(text, 'if (argv(0) != "rewind")',
                'if (argv(0) == "visual_units") { Visual_Units(); return TRUE; }\n\t'
                'if (argv(0) == "visual_trace") { Visual_Trace(argv(1)); return TRUE; }\n\t'
                'if (argv(0) != "rewind")')
    text = once(text, 'registercommand("rewind");',
                'registercommand("rewind");\n\tregistercommand("visual_units");\n\tregistercommand("visual_trace");')
    p.write_text(text)


def config(text, fps, units=False):
    from stitched_rewind_smoke import once
    text = once(text, 'cl_maxfps 100\n', f'cl_maxfps {fps}\n')
    if units:
        text = once(text, 'cmd stitchguards\n', 'visual_units\ncmd stitchguards\n')
        if fps == 30:
            # Keep the existing >10 raw-sample coverage floor at this lower rate.
            for old, new in ((0.6, 0.9), (0.4, 0.7), (0.2, 0.5)):
                text = once(text, f'rewind seek {old}\n', f'rewind seek {new}\n')
    for prefix in ('warm', 'cold'):
        for i in range(1, 4):
            label = f'{prefix}{i}_cursor'
            old = f'stitch_probe {label}\n'
            if old in text:
                text = once(text, old, old + f'visual_trace {label}\n')
    return text


def close(a, b, eps=0.003):
    return len(a) == len(b) and all(abs(x-y) <= eps for x, y in zip(a, b))


def trace(gd, label):
    lines = (gd / f'cfg/test/visual_{label}.txt').read_text().splitlines()
    head = lines[0].split()
    assert len(head) == 5 and head[:2] == ['FTESURF-VISUAL', '1'], label
    n, rawcount, fps = map(float, head[2:])
    assert all(math.isfinite(x) for x in (n, rawcount, fps)), label
    assert n == int(n) and n > 1 and rawcount == int(rawcount) and rawcount >= n and fps > 0, label
    rows = [list(map(float, s.split())) for s in lines[1:]]
    assert len(rows) == 4 * (int(n)-1) + 1, (label, 'trace missing samples')
    assert all(len(r) == 32 and all(math.isfinite(x) for x in r) for r in rows), label
    assert all(r[0] == i/4 for i, r in enumerate(rows)), (label, 'incomplete/duplicate cursor scan')
    return int(n), int(rawcount), fps, rows


def grade(gd, *, phases=('warm', 'cold'), cuts=(1, 2, 3),
          stop_labels=('beforewait', 'initial')):
    """Grade complete camera scans; alternate fixtures keep the same strict oracle."""
    gd = Path(gd)
    log = (gd / 'logs/runlines_smoke.log').read_text(errors='replace')
    serverlog = (gd / 'logs/runlines_server.log').read_text(errors='replace')
    assert all(bad not in log + serverlog for bad in
               ('VISUAL WRITE FAILED', 'Unknown command', 'QC VM error', 'Cannot call', 'stack overflow'))
    units = (gd / 'cfg/test/visual_units.txt').read_text().split()
    assert len(units) == 3 and units[0] == 'units' and units[1] == '9', 'compiled unit controls did not ACT'
    unit_fails = int(units[2])
    checks = re.findall(r'VISUAL CHECK (\S+) ([01])(?:\s|$)', log)
    expected_checks = {'continuous', 'sampled-not-retimed', 'short-yaw', 'raw-break-columns',
                       'raw-stitch-columns', 'legacy-flag-break', 'position-break',
                       'chase-before-break', 'chase-after-break'}
    assert len(checks) == 9 and {s[0] for s in checks} == expected_checks
    assert unit_fails == sum(s[1] == '0' for s in checks)
    for name, ok in checks:
        print(('PASS' if ok == '1' else 'FAIL'), 'compiled', name)
    # Positive stop must have real elapsed clock, stationary positions and speed.
    _, _, initial = dump(gd, stop_labels[1])
    _, _, before = dump(gd, stop_labels[0])
    stop = [r for r in initial if r[0] > before[-1][0] + 1]
    assert stop and stop[-1][0] - stop[0][0] > 4, 'genuine stop did not ACT'
    assert all(close(r[1:4], stop[0][1:4]) and close(r[4:7], [0, 0, 0]) for r in stop)
    print(f'PASS genuine stop: {len(stop)} samples, {stop[-1][0]-stop[0][0]:.3f}s counted')
    total = 0
    assert phases and cuts, 'camera phases did not ACT'
    for prefix in phases:
        for cut in cuts:
            label = f'{prefix}{cut}_cursor'
            _, _, raw = dump(gd, label)
            assert all(math.isfinite(x) for row in raw for x in row), label
            n, rawcount, fps, rows = trace(gd, label)
            assert rawcount == len(raw), label
            assert f'VISUAL TRACE {label}' in log, (label, 'camera did not ACT')
            points = rows[::4]
            for r in rows:
                index = int(r[0])
                j = min(n-1, index+1)
                a, b = points[index], points[j]
                f = r[0] - index
                assert r[27] in (0, 1) and r[28] in (0, 1), label
                if b[27] or b[1] <= a[1]:
                    f = 0
                assert close(r[3:6], a[3:6]) and abs(r[1]-a[1]) < 0.00001
                assert close(r[6:9], [x+(y-x)*f for x,y in zip(a[3:6], b[3:6])]), (label, 'visual crosses break')
                assert abs(r[2] - (a[1]+(b[1]-a[1])*f)) < 0.00001
                ri = int(r[31])
                assert r[31] == ri and 0 <= ri < len(raw), label
                # Match production time lookup independently, including duplicate stamps.
                assert raw[ri][0] <= r[2] + 0.00001
                assert ri == len(raw)-1 or raw[ri+1][0] > r[2]-0.00001, label
                ra, rb = raw[ri], raw[min(len(raw)-1, ri+1)]
                blend = 0
                if rb[0] > ra[0] and not (int(rb[7]) & 0x4000000 or rb[8] or rb[9]):
                    blend = max(0, min(1, (r[2]-ra[0])/(rb[0]-ra[0])))
                want = [x+(y-x)*blend for x,y in zip(ra[4:7], rb[4:7])]
                # Dumped time is six decimals, not the original float32 lerp input.
                dt = rb[0]-ra[0]
                precision = .003 + (max(abs(x-y) for x,y in zip(ra[4:7], rb[4:7])) * 2e-6 / dt if dt > 0 else 0)
                assert close(r[9:12], want, precision), (label, 'velocity crosses raw break', r[0])
                angles = [ra[13], ra[10], 0]
                angle_precision = [.003] * 3
                if dt > 0 and not (int(rb[7]) & 0x4000000 or rb[8] or rb[9]):
                    for k, end in enumerate((rb[13], rb[10])):
                        arc = (end-angles[k]+180) % 360-180
                        angles[k] = (angles[k]+arc*blend+180) % 360-180
                        # Same six-decimal time quantization bound as velocity;
                        # discontinuities retain the strict floor.
                        angle_precision[k] += abs(arc) * 2e-6 / dt
                assert all(abs((x-y+180) % 360-180) < eps for x,y,eps in zip(r[12:15], angles, angle_precision)), (label, 'view crosses raw break')
                eye = 47 if int(ra[7]) & 2 else 64
                assert close(r[15:18], [r[6], r[7], r[8]+eye]), (label, 'first-person camera mismatch')
                assert close(r[18:21], r[12:15]), (label, 'first-person angles mismatch')
                assert r[24] == 12 and r[26] == 0, (label, 'chase path did not ACT')
                # Tangent may look only within the cursor's continuous span.
                lo = max(0, index-3)
                hi = min(n-1, index+3)
                for k in range(index, lo, -1):
                    if points[k][27]:
                        lo = k
                        break
                for k in range(index+1, hi+1):
                    if points[k][27]:
                        hi = k-1
                        break
                d = [points[hi][3]-points[lo][3], points[hi][4]-points[lo][4]]
                yaw = math.degrees(math.atan2(d[1], d[0])) % 360 if math.hypot(*d) >= 1 else 0
                assert abs((r[25]-yaw+180) % 360-180) < .003, (label, 'chase tangent crosses span', r[0], r[25], yaw)
            total += len(rows)
            print(f'PASS {label}: {len(rows)} first-person/chase cursor samples, cap {fps:g}')
    assert unit_fails == 0, f'{unit_fails} compiled discontinuity controls failed'
    print(f'PASS visual matrix: {total} cursor samples, 9 compiled controls; human camera feel not graded.')
