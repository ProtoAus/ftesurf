#!/usr/bin/env python3
"""Private diagnostic seams for requested cursor vs native nearest-position selection.

Never changes native selection or the original requested-clock grader. Requires
complete acted ring/request/acknowledgement observations and exact raw prefixes.
"""
import math
from pathlib import Path
import struct

from stitched_rewind_smoke import dump, native, once

SERVER_CAPTURE = r'''
.float stitch_selection;
void(entity e, float t, vector near, float usenear) Stitch_SelectionCapture =
{
	local float k, i, b;
	local float *m;

	if (e.stitch_selection >= 1) buf_del(e.stitch_selection);
	e.stitch_selection = buf_create_ex("string", 0);
	b = e.stitch_selection;
	if (b < 1) return;
	bufstr_set(b, 0, sprintf("request %.9g %.9g %.9g %.9g", t, near_x, near_y, near_z));
	bufstr_set(b, 1, sprintf("selected %.9g %.9g %.9g %.9g", rw_t, rw_o_x, rw_o_y, rw_o_z));
	bufstr_set(b, 2, sprintf("rules %.9g %.9g %g %g", run_t_tick, RW_NEAR, usenear, e.rw_n));
	m = rw_slot[num_for_edict(e)];
	for (k = 0; k < e.rw_n; k = k + 1)
	{
		i = ((e.rw_head - 1 - k + RW_CAP) % RW_CAP) * RW_STRIDE;
		bufstr_set(b, k + 3, sprintf("row %.9g %.9g %.9g %.9g", m[i], m[i+1], m[i+2], m[i+3]));
	}
};
void(entity e, string label) Stitch_SelectionServer =
{
	local float f, i;
	f = fopen(strcat("cfg/test/selection_server_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("SELECTION WRITE FAILED\n"); return; }
	if (e.stitch_selection >= 1)
	for (i = 0; i < buf_getsize(e.stitch_selection); i = i + 1)
		fputs(f, strcat(bufstr_get(e.stitch_selection, i), "\n"));
	fclose(f);
};
'''
CLIENT_CLOCK = r'''
void() Stitch_SelectionClock =
{
	local float f, i, n, cut, decoded, normalized, next;
	f = fopen("cfg/test/selection_clock.txt", FILE_WRITE);
	if (f < 0) { print("SELECTION WRITE FAILED\n"); return; }
	for (i = 0; i < 6; i = i + 1)
	{
		n = 49;
		if (i == 1) n = 135;
		if (i == 2) n = 35;
		if (i == 3) n = 62;
		if (i == 4) n = 0;
		if (i == 5) n = 1000000;
		cut = n * 0.015;
		decoded = stof(sprintf("%.6f", cut));
		normalized = __NORMALIZE__;
		next = stof(sprintf("%.6f", (n + 1) * 0.015));
		fputs(f, sprintf("clock %g %.9g %.9g %.9g %.9g\n", n, cut, decoded, normalized, next));
	}
	fclose(f);
};
'''
CLIENT_PROBE = r'''
	Stitch_SelectionClock();
	f = fopen(strcat("cfg/test/selection_client_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("SELECTION WRITE FAILED\n"); return; }
	fputs(f, sprintf("cursor %.9g %.9g %.9g %.9g\n", tr_cur_t, tr_cur_p_x, tr_cur_p_y, tr_cur_p_z));
	fputs(f, sprintf("ack %.9g %g %g %.9g\n", getstatf(STAT_FS_SAVETICKS),
	                getstatf(STAT_FS_SLTRAILTAG), tr_timedgo_ack, tr_tick));
	fputs(f, sprintf("event %g %g %g\n", FS_SlopOp(getstatf(STAT_FS_SLOP)),
	                getstatf(STAT_FS_SLSEQ), getstatf(STAT_FS_SLACK)));
	fclose(f);
'''
CLIENT_REQUEST = r'''
	local float sf;
	sf = fopen(strcat("cfg/test/selection_request_", cvar_string("selection_phase"), "_", sprintf("%d", tr_ticket), ".txt"), FILE_WRITE);
	if (sf < 0) print("SELECTION WRITE FAILED\n");
	else
	{
		fputs(sf, strcat(c, "\n"));
		fputs(sf, sprintf("sample %.9g %.9g %.9g %.9g %.9g\n", tr_cur_t,
		                tr_cur_p_x, tr_cur_p_y, tr_cur_p_z, tr_tick));
		fclose(sf);
	}
'''


def instrument(work):
    p = work / 'src/server/sv_saveloc.qc'
    text = once(p.read_text(), '#include "sv_rewindstate.qc"', SERVER_CAPTURE + '\n#include "sv_rewindstate.qc"')
    text = once(text, '\te.stitch_origin = rw_o;', '\tStitch_SelectionCapture(e, t, near, usenear);\n\te.stitch_origin = rw_o;')
    p.write_text(text)
    p = work / 'src/server/sv_player.qc'
    p.write_text(once(p.read_text(), 'SV_StitchProbe(self, argv(1)); return;',
                     'SV_StitchProbe(self, argv(1)); Stitch_SelectionServer(self, argv(1)); return;'))
    p = work / 'src/client/cl_trail.qc'
    normalize = 'Trail_RawClock(cut)' if 'Trail_RawClock =' in (work / 'src/client/cl_trailstate.qc').read_text() else 'cut'
    text = once(p.read_text(), 'void(string label) Stitch_Probe =',
                CLIENT_CLOCK.replace('__NORMALIZE__', normalize) + '\nvoid(string label) Stitch_Probe =')
    p.write_text(once(text, '\tprint("STITCH PROBE ", label, "\\n");',
                     CLIENT_PROBE + '\tprint("STITCH PROBE ", label, "\\n");'))
    p = work / 'src/client/cl_trailreplay.qc'
    p.write_text(once(p.read_text(), '\treturn strcat(c, " ", sprintf("%d", tr_ticket));',
                     CLIENT_REQUEST + '\treturn strcat(c, " ", sprintf("%d", tr_ticket));'))


def fields(path, widths, repeated=None):
    result, rows = {}, []
    for line in path.read_text().splitlines():
        words = line.split()
        assert words and words[0] in widths, 'unknown selection field'
        key = words[0]
        assert len(words) == widths[key] + 1, 'incomplete selection field'
        values = list(map(float, words[1:]))
        assert all(math.isfinite(v) for v in values), 'nonfinite selection field'
        if key == repeated:
            rows.append(values)
        else:
            assert key not in result, 'duplicate selection field'
            result[key] = values
    assert result.keys() == widths.keys() - {repeated}, 'missing selection field'
    return result, rows


def f32(x):
    return struct.unpack('f', struct.pack('f', x))[0]


def distance(a, b):
    d = [f32(f32(x) - f32(y)) for x, y in zip(a, b)]
    return f32(math.sqrt(f32(f32(f32(d[0]*d[0]) + f32(d[1]*d[1])) + f32(d[2]*d[2]))))


def nearest(request, rules, rows):
    t, *pose = request
    tick, window, use_near, count = rules
    assert tick > 0 and window == .5 and use_near == 1, 'selection rules not reached'
    assert count == len(rows) and len(rows) > 10, 'incomplete native ring'
    assert all(a[0] > b[0] for a, b in zip(rows, rows[1:])), 'native ring order/duplicates'
    eligible = [row for row in rows if abs(f32(f32(row[0]) - f32(t))) <= f32(window / f32(tick))]
    assert eligible, 'no eligible native snapshot'
    # Rows are newest first. Equal body and tick distances retain the first.
    return min(eligible, key=lambda row: (distance(row[1:], pose), abs(f32(f32(row[0]) - f32(t)))))


def grade(gd):
    gd = Path(gd)
    logs = ''.join((gd / 'logs' / name).read_text(errors='replace')
                   for name in ('runlines_smoke.log', 'runlines_server.log'))
    assert not any(s in logs for s in ('SELECTION WRITE FAILED', 'QC VM error', 'Unknown command', 'Cannot call', 'stack overflow'))
    _, clocks = fields(gd / 'cfg/test/selection_clock.txt', {'clock': 5}, 'clock')
    assert [r[0] for r in clocks] == [49, 135, 35, 62, 0, 1000000], 'compiled clock controls did not act'
    assert all(r[2] == r[3] < r[4] for r in clocks), 'compiled raw clock normalization lost a boundary or admitted a future tick'
    assert sum(r[1] != r[2] for r in clocks) >= 2, 'compiled roundtrip counterfactual did not act'
    print('PASS six compiled raw-clock boundary controls (including future-tick exclusion).')
    results = []
    for prefix in ('warm', 'cold'):
        for i in range(1, 4):
            stem = f'{prefix}{i}'
            _, cut, before = dump(gd, stem + '_cursor')
            _, _, held = dump(gd, stem + '_hold1')
            _, _, held2 = dump(gd, stem + '_hold2')
            _, _, released = dump(gd, stem + '_release')
            client, _ = fields(gd / f'cfg/test/selection_client_{stem}_hold1.txt',
                               {'cursor': 4, 'ack': 4, 'event': 3})
            server, rows = fields(gd / f'cfg/test/selection_server_{stem}_hold1.txt',
                                  {'request': 4, 'selected': 4, 'rules': 4, 'row': 4}, 'row')
            selected = server['selected']
            assert nearest(server['request'], server['rules'], rows) == selected, (stem, 'not nearest native snapshot')
            ticks, tag, ticket, tick = client['ack']
            assert tag == ticket > 0 and int(tag) == tag, (stem, 'uncorrelated timed go')
            assert client['event'][0] == 2 and client['event'][1] > 0 and client['event'][2] > 0, (stem, 'load did not act')
            request_lines = (gd / f'cfg/test/selection_request_{prefix}_{int(tag)}.txt').read_text().splitlines()
            assert len(request_lines) == 2, 'incomplete wire request'
            words = request_lines[0].split()
            assert len(words) == 6 and words[0] == 'sl_saveat' and words[-1] == 'go', 'not a timed go request'
            wire = list(map(float, words[1:5]))
            assert all(math.isfinite(v) for v in wire) and list(map(f32, wire)) == list(map(f32, server['request'])), (stem, 'wire request differs')
            sample = request_lines[1].split()
            assert len(sample) == 6 and sample[0] == 'sample', 'incomplete request sample'
            sample = list(map(float, sample[1:]))
            cursor, _ = fields(gd / f'cfg/test/selection_client_{stem}_cursor.txt',
                               {'cursor': 4, 'ack': 4, 'event': 3})
            assert all(math.isfinite(v) for v in sample) and sample[:4] == cursor['cursor'] and abs(sample[0] - cut) < .000001, (stem, 'wrong sampled cursor')
            assert tick > 0 and tick == sample[4] == server['rules'][0], (stem, 'tick changed')
            assert wire[0] == round(sample[0] / tick), (stem, 'wire tick differs from sample')
            assert all(float(format(v, '.6g')) == w for v, w in zip(sample[1:4], wire[1:])), (stem, 'wire pose differs from sample')
            assert ticks == selected[0], (stem, 'ack clock differs from native selection')
            n1, n2, nr = [native(gd, stem + '_' + arm) for arm in ('hold1', 'hold2', 'release')]
            assert all(n['ticks'] == [ticks, ticks] and n['hold'] == [1, 1, 1] and
                       n['expected'] == selected[1:] and
                       sum((a-b)**2 for a, b in zip(n['body'], selected[1:])) < .0001
                       for n in (n1, n2)), (stem, 'native body/clock differs')
            assert nr['hold'] == [0, 0, 0] and nr['ticks'][1] > ticks, (stem, 'release not acted')
            bound = f32(ticks * f32(tick))
            # Both raw clocks and the cutoff must cross the SAME six-decimal
            # representation. Do not admit a wider FPS/nearest-sample tolerance.
            raw_bound = f32(float(format(bound, '.6f')))
            expected = [row for row in before if f32(row[0]) <= raw_bound]
            assert held == expected and held2 == held and released[:len(held)] == held, (stem, 'not exact acknowledged raw prefix')
            delta = held[-1][0] - cut
            results.append((stem, cut, ticks, bound, held[-1][0], delta))
            print(f'PASS selection {stem}: requested {cut:.6f}, native/ack {bound:.6f}, raw end {held[-1][0]:.6f}, delta {delta:+.6f}')
    print('PASS six nearest-native selections, correlated clocks and exact acknowledged prefixes (not requested-clock equivalence).')
    return results
