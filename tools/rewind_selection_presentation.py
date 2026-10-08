"""Opt-in private draw/clock probes; never deploy these diagnostic programs."""
from pathlib import Path
import math
import re

DRAW = r'''
void(vector p, string s, float size, vector rgb, float alpha) ResumeUI_Text =
{
	resumeui_text = strcat(resumeui_text, s, " | ");
	HUD_TextC(p, s, size, rgb, alpha);
};
'''
PROBE = r'''
void(string label) ResumeUI_Probe =
{
	local float f;
	f = fopen(strcat("cfg/test/resume_ui_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("RESUMEUI WRITE FAILED\n"); return; }
	fputs(f, "FTESURF-RESUMEUI 1\n");
	fputs(f, sprintf("phase %d %d %d %d %d\n", rw_on, rw_ack != 0, rw_cd != 0, ui_rw_on, tr_practice));
	fputs(f, sprintf("cursor %.6f %.6f %.6f\n", tr_cur_t, rw_visualt, tr_tick));
	fputs(f, sprintf("panel %.6f %.6f %d\n", resumeui_ticks, resumeui_tick, resumeui_flags));
	fputs(f, sprintf("ack %d %d %d %d %d %d %d\n", getstatf(STAT_FS_SAVETICKS),
		getstatf(STAT_FS_SLTRAILTAG), tr_saveack, getstatf(STAT_FS_TIMERTICKS),
		getstatf(STAT_FS_TIMERSTATE), getstatf(STAT_FS_TIMERFLAGS),
		(getstatf(STAT_FS_TIMERFLAGS) & TF_FROZEN) != 0));
	fputs(f, strcat("text ", resumeui_text, "\n"));
	fclose(f);
	print("RESUMEUI PROBE ", label, "\n");
};
'''
TIES = r'''
void(entity e) ResumeUI_Ties =
{
	local float *old;
	local float *m;
	local float n, head, i, fails, t, base, pit, yaw, dk;
	local vector o, v;
	old = rw_slot[num_for_edict(e)]; n = e.rw_n; head = e.rw_head;
	t = rw_t; base = rw_statebase; o = rw_o; v = rw_v;
	pit = rw_pit; yaw = rw_yaw; dk = rw_dk;
	m = memalloc(2 * RW_STRIDE * 4);
	for (i = 0; i < 2 * RW_STRIDE; i = i + 1) m[i] = 0;
	m[0] = 48; m[1] = 10; m[2] = 20; m[3] = 30;
	m[RW_STRIDE] = 50; m[RW_STRIDE+1] = 10; m[RW_STRIDE+2] = 20; m[RW_STRIDE+3] = 30;
	rw_slot[num_for_edict(e)] = m; e.rw_n = e.rw_head = 2;
	fails = 0;
	if (!SV_RewindFind(e, 49, '10 20 30', TRUE)) fails = fails + 1;
	else if (rw_t != 50) fails = fails + 1;
	if (!SV_RewindFind(e, 48, '10 20 30', TRUE)) fails = fails + 1;
	else if (rw_t != 48) fails = fails + 1;
	if (!SV_RewindFind(e, 16, '10 20 30', TRUE)) fails = fails + 1;
	else if (rw_t != 48) fails = fails + 1;
	if (SV_RewindFind(e, 10, '10 20 30', TRUE)) fails = fails + 1;
	m[1] = 1000;
	if (!SV_RewindFind(e, 48, '10 20 30', TRUE)) fails = fails + 1;
	else if (rw_t != 50) fails = fails + 1;
	rw_slot[num_for_edict(e)] = old; e.rw_n = n; e.rw_head = head;
	rw_t = t; rw_statebase = base; rw_o = o; rw_v = v;
	rw_pit = pit; rw_yaw = yaw; rw_dk = dk;
	memfree(m);
	print(sprintf("RESUMEUI TIES 5 %d\n", fails));
};
'''


UNITS = r'''
float resumeui_fake, resumeui_faketag, resumeui_faketicks;
float resumeui_checks, resumeui_fails;
float(float stat) ResumeUI_Stat =
{
	if (!resumeui_fake) return getstatf(stat);
	if (stat == STAT_FS_SLACK) return 10;
	if (stat == STAT_FS_SLSEQ) return 21;
	if (stat == STAT_FS_SLOP) return FS_SlopPack(SLOP_LOADED, 1);
	if (stat == STAT_FS_SLTRAILTAG) return resumeui_faketag;
	if (stat == STAT_FS_SAVETICKS) return resumeui_faketicks;
	return getstatf(stat);
};
void(float ok) ResumeUI_Check =
{
	resumeui_checks = resumeui_checks + 1;
	if (!ok) resumeui_fails = resumeui_fails + 1;
};
void() ResumeUI_Units =
{
	local float tick;
	tick = tr_tick;
	resumeui_fake = TRUE; resumeui_faketag = 77; resumeui_faketicks = 50;
	rw_on = TRUE; rw_ack = 10; rw_seq = 20; rw_go_ticket = 77;
	rw_reqtick = 0.015; rw_reqticks = 49; rw_go_practice = rw_nativeok = FALSE;
	Rewind_Answer();
	ResumeUI_Check(rw_nativeok && strstrofs(Rewind_ResumeInfo(), "native resume ", 0) == 0);
	rw_ack = 10; rw_nativeok = FALSE; resumeui_faketag = 76;
	Rewind_Answer();
	ResumeUI_Check(!rw_nativeok && !strcmp(Rewind_ResumeInfo(), "resume accepted -- native clock unavailable"));
	rw_ack = 10; resumeui_faketag = 77; resumeui_faketicks = -1;
	Rewind_Answer();
	ResumeUI_Check(!rw_nativeok && strstrofs(Rewind_ResumeInfo(), "native resume ", 0) < 0);
	rw_ack = 10; rw_go_practice = TRUE; resumeui_faketicks = 50;
	Rewind_Answer();
	ResumeUI_Check(!rw_nativeok && !strcmp(Rewind_ResumeInfo(), "practice resume -- untimed"));
	rw_ack = 10; rw_go_practice = FALSE; rw_nativeok = TRUE;
	ResumeUI_Check(strstrofs(Rewind_ResumeInfo(), "waiting for native snapshot", 0) >= 0 && strstrofs(Rewind_ResumeInfo(), "native resume ", 0) < 0);
	rw_on = FALSE;
	ResumeUI_Check(!strcmp(Rewind_ResumeInfo(), ""));
	rw_on = TRUE; rw_ack = rw_cd = 0; tr_tick = 0.015; tr_practice = FALSE;
	ResumeUI_Check(strstrofs(Rewind_ResumeInfo(), "sampled request ", 0) == 0);
	tr_practice = TRUE;
	ResumeUI_Check(!strcmp(Rewind_ResumeInfo(), "sampled practice cursor -- resume is untimed"));
	tr_practice = FALSE; tr_tick = 0;
	ResumeUI_Check(!strcmp(Rewind_ResumeInfo(), "sampled request unavailable"));
	tr_tick = tick; resumeui_fake = FALSE;
	rec_sl_holding = rec_sl_holdack = rec_sl_holdackat = rec_sl_holdkey = rec_sl_holdseen = rec_sl_holdrep = 0;
	Rewind_Reset();
	print(sprintf("RESUMEUI UIUNITS %d %d\n", resumeui_checks, resumeui_fails));
};
'''


def instrument(work):
    from stitched_rewind_smoke import once
    p = work / 'src/client/cl_hud.qc'
    p.write_text('string resumeui_text;\nfloat resumeui_ticks, resumeui_tick, resumeui_flags;\n' + p.read_text())
    p = work / 'src/client/cl_timer.qc'
    p.write_text(once(p.read_text(), '\tdisp = Timer_Display(state, ticks, tick, flags);',
                     '\tdisp = Timer_Display(state, ticks, tick, flags);\n'
                     '\tresumeui_ticks = disp; resumeui_tick = tick; resumeui_flags = flags;'))
    p = work / 'src/client/cl_rewind.qc'
    text = p.read_text()
    candidate = 'string() Rewind_ResumeInfo =' in text
    if candidate:
        # Only this private wrapper can fake stats, and only during explicit units.
        declaration, units = UNITS.split('void(float ok) ResumeUI_Check =', 1)
        text = once(text, 'void() Rewind_Answer =', declaration + '\nvoid() Rewind_Answer =')
        begin, finish = text.index('void() Rewind_Answer ='), text.index('// Every frame, with the other per-frame readers.')
        text = text[:begin] + text[begin:finish].replace('getstatf(', 'ResumeUI_Stat(') + text[finish:]
        units = 'void(float ok) ResumeUI_Check =' + units
        units = 'void() Rewind_Reset;\n' + units
    else:
        units = 'void() ResumeUI_Units = { print("RESUMEUI UIUNITS missing\\n"); };\n'
    start, end = text.index('void(vector scr) Rewind_Draw ='), text.index('float(float evtype, float scanx, float chary, float devid) Rewind_InputEvent =')
    block = text[start:end].replace('HUD_TextC(', 'ResumeUI_Text(')
    block = once(block, '\tlocal string s;\n', '\tlocal string s;\n\tresumeui_text = "";\n')
    text = text[:start] + DRAW + block + text[end:]
    text = once(text, 'float() Rewind_Console =', units + '\n' + PROBE + '\nfloat() Rewind_Console =')
    text = once(text, 'if (argv(0) != "rewind")', 'if (argv(0) == "resume_ui") { ResumeUI_Probe(argv(1)); return TRUE; }\n\tif (argv(0) == "resume_ui_units") { ResumeUI_Units(); return TRUE; }\n\tif (argv(0) != "rewind")')
    text = once(text, 'registercommand("rewind");', 'registercommand("rewind");\n\tregistercommand("resume_ui");\n\tregistercommand("resume_ui_units");')
    p.write_text(text)
    p = work / 'src/server/sv_rewindstate.qc'
    p.write_text(p.read_text() + '\n' + TIES)
    p = work / 'src/server/sv_player.qc'
    p.write_text(once(p.read_text(), 'if (c == "stitchguards")',
                     'if (c == "resumeuitie") { ResumeUI_Ties(self); return; }\n\tif (c == "stitchguards")'))


def config(text):
    from stitched_rewind_smoke import once
    text = once(text, 'cl_maxfps ', 'cl_delay_packets 120\ncl_delay_packets\ncl_maxfps ')
    if 'cmd stitchguards\n' in text:
        text = once(text, 'cmd stitchguards\n', 'resume_ui_units\ncmd stitchguards\ncmd resumeuitie\n')
        # Explicit latency + screenshot work can leave the initial save pending.
        text = once(text, 'rewind save\nwaitms 500\n', 'rewind save\nwaitms 1600\n')
    for prefix in ('warm', 'cold'):
        for i in range(1, 4):
            stem = f'{prefix}{i}'
            needle = f'stitch_probe {stem}_cursor\n'
            if needle not in text:
                continue
            if stem == 'warm1':
                text = once(text, needle, 'rewind step 0.5\nwait 4\n' + needle)
            text = once(text, needle, needle + f'resume_ui {stem}_cursor\n')
            text = once(text, f'rewind go\nwaitms 1200\necho ==== STITCH {stem}_hold1 ====',
                         f'rewind go\nwait 1\nresume_ui {stem}_pending\nwaitms 1200\necho ==== STITCH {stem}_hold1 ====')
            for phase in ('hold1', 'hold2', 'release'):
                needle = f'stitch_probe {stem}_{phase}\n'
                text = once(text, needle, needle + f'resume_ui {stem}_{phase}\n')
    return once(text, 'echo RUNLINES COMPLETE\n', 'resume_ui closed\necho RUNLINES COMPLETE\n')


def read(gd, label):
    lines = (gd / f'cfg/test/resume_ui_{label}.txt').read_text().splitlines()
    assert len(lines) == 6 and lines[0] == 'FTESURF-RESUMEUI 1', ('incomplete probe', label)
    result = {}
    for line, key, width in zip(lines[1:6], ('phase', 'cursor', 'panel', 'ack', 'text'), (5, 3, 3, 7, None)):
        words = line.split()
        assert words and words[0] == key, ('wrong probe field', label)
        if width is None:
            result[key] = line[5:]
        else:
            assert len(words) == width + 1, ('short field', label, key)
            result[key] = list(map(float, words[1:]))
            assert all(math.isfinite(v) for v in result[key]), ('nonfinite', label, key)
    return result


def seconds(text, key):
    m = re.search(key + r' (\d+):(\d{2}\.\d{3})', text)
    assert m, ('missing caption', key, text)
    return int(m[1]) * 60 + float(m[2])


def grade(gd):
    gd = Path(gd)
    server = (gd / 'logs/runlines_server.log').read_text(errors='replace')
    assert server.count('RESUMEUI TIES 5 0') == 1, 'native repeated-position controls unacted/failed'
    log = (gd / 'logs/runlines_smoke.log').read_text(errors='replace')
    assert 'RESUMEUI WRITE FAILED' not in log
    assert log.count('RESUMEUI UIUNITS 9 0') == 1, 'presentation units unacted/failed'
    for prefix in ('warm', 'cold'):
        for i in range(1, 4):
            stem = f'{prefix}{i}'
            rows = {p: read(gd, stem + '_' + p) for p in ('cursor', 'pending', 'hold1', 'hold2', 'release')}
            for phase in rows:
                assert log.count('RESUMEUI PROBE ' + stem + '_' + phase + '\n') == 1, ('probe coverage', stem, phase)
            c = rows['cursor']
            assert c['phase'] == [1, 0, 0, 1, 0]
            requested = round(c['cursor'][0] / c['cursor'][2]) * c['cursor'][2]
            assert abs(seconds(c['text'], 'sampled request') - requested) < .0007
            assert 'nearest recorded position' in c['text']
            assert abs(c['panel'][0] * c['panel'][1] - c['cursor'][1]) < .00001
            if stem == 'warm1':
                assert c['cursor'][1] > c['cursor'][0] + .001, 'fractional display/sample separation unacted'
            p = rows['pending']
            assert p['phase'] == [1, 1, 0, 0, 0], ('pending unacted', stem, p['phase'])
            assert 'waiting for native snapshot' in p['text'] and 'native resume ' not in p['text']
            assert abs(seconds(p['text'], 'requested') - requested) < .0007
            for phase in ('hold1', 'hold2'):
                h = rows[phase]
                assert h['phase'] == [1, 0, 1, 0, 0], ('hold unacted', stem)
                ticks, tag, ticket, timer, state, flags, frozen = h['ack']
                assert ticks == timer >= 0 and ticks == int(ticks) and tag == ticket > 0 and tag == int(tag) and frozen == 1
                assert h['panel'][0] == timer and h['panel'][2] == flags
                native = ticks * h['panel'][1]
                assert abs(seconds(h['text'], 'native resume') - native) < .0007
                assert abs(seconds(h['text'], 'requested') - requested) < .0007
                delta = re.search(r'([+-]\d+\.\d{3})s', h['text'])
                assert delta and abs(float(delta[1]) - (native - requested)) < .0007
            assert rows['hold1']['text'].split('native resume', 1)[1] == rows['hold2']['text'].split('native resume', 1)[1], ('caption crept', stem)
            assert rows['release']['phase'][:4] == [0, 0, 0, 0]
            assert rows['release']['text'] == '', ('stale closed caption', stem)
    assert read(gd, 'closed')['phase'][:4] == [0, 0, 0, 0]
    print('PASS resume UI: six requested/pending/native/fixed-hold/closed phases, nine presentation units and five real native position/tick tie controls; not requested-clock equivalence')
