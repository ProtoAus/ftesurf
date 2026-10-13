#!/usr/bin/env python3
"""Acting viewer controls/HUD test in an owned, isolated two-client socket rig.

--output-dir must sit under a task OWNER.md. --baseline REF compiles that exact
source with the same probes/config. Neither arm modifies an install or its data.
The baseline must fail the new board/modal/spectator-save assertions; existing
replay/rewind saves and loads must act in both. Screenshots are retained for look
review, not automatically called a style pass. Only the launched peer is stopped.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'probe seam mismatch: {old!r}')
    return text.replace(old, new, 1)


CLIENT = r'''
void(string label) Viewer_Probe =
{
	local float f, i, lines;
	f = fopen(strcat("cfg/test/viewer_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("VIEWER WRITE FAILED\n"); return; }
	lines = 0;
	for (i = 0; i < SB_LNMAX; i = i + 1)
		if (sb_ln_st[i] == SBL_ON) lines = lines + 1;
	fputs(f, sprintf("view %g %g %g %g %g %g %g\n", rec_wt_open, rw_on, spc_hud,
	                rec_sb_open, ui_he_open, av_open, Scores_NativeFront()));
	fputs(f, sprintf("save %g %g %g\n", getstatf(STAT_FS_SAVECOUNT),
	                getstatf(STAT_FS_SAVEINDEX), getstatf(STAT_FS_SPEC)));
	fputs(f, sprintf("body %.6f %.6f %.6f\n", pmove_org_x, pmove_org_y, pmove_org_z));
	fputs(f, sprintf("pose %.6f %.6f %.6f\n", spc_tfeet_x, spc_tfeet_y, spc_tfeet_z));
	fputs(f, sprintf("lines %g\n", lines));
	fputs(f, sprintf("pause %g\n", rec_wt_paused));
	fputs(f, sprintf("rewindhud %g %g\n", viewer_crosshair, viewer_keys));
	fputs(f, strcat("path ", rec_wt_path, "\n"));
	fclose(f);
	print("VIEWER PROBE ", label, "\n");
};
void(string id, float down) Viewer_Click =
{
	local float i, found, took;
	local vector p;
	found = FALSE;
	for (i = 0; i < min(MAX_ACTION_ELEMENTS, _action_elements_index); i = i + 1)
		if (!strcmp(_action_elements[i].id, id))
		{
			p = _action_elements[i].pos + _action_elements[i].size * 0.5;
			found = TRUE;
		}
	if (!found) { print("VIEWER MISSING HIT ", id, "\n"); return; }
	CSQC_InputEvent(IE_MOUSEABS, p_x, p_y, 0);
	took = CSQC_InputEvent(down ? IE_KEYDOWN : IE_KEYUP, K_MOUSE1, 0, 0);
	print(sprintf("VIEWER CLICK %s %g %g\n", id, down, took));
	print(sprintf("VIEWER HIT %s hover %s hold %s release %s\n", id,
	              _hover_action_count > 0 ? _hover_actions[0] : "-",
	              _hold_action_count > 0 ? _hold_actions[0] : "-",
	              _release_action_count > 0 ? _release_actions[0] : "-"));
};
'''
SERVER = r'''
void(entity e, string label) Viewer_Server =
{
	local float f, b, row;
	local vector q;
	f = fopen(strcat("cfg/test/viewer_server_", label, ".txt"), FILE_WRITE);
	if (f < 0) { print("VIEWER SERVER WRITE FAILED\n"); return; }
	b = SL_Blk(e);
	fputs(f, sprintf("hold %g %g %g\n", e.run_pmhold, e.rec_wt_hold, e.rec_sl_hold));
	fputs(f, sprintf("body %.6f %.6f %.6f\n", e.origin_x, e.origin_y, e.origin_z));
	fputs(f, sprintf("count %g\n", rec_sl_nb[b]));
	if (rec_sl_nb[b] > 0)
	{
		row = SL_Base(b) + rec_sl_nb[b] - 1;
		q = rec_sl_org[row];
		fputs(f, sprintf("saved %.6f %.6f %.6f\n", q_x, q_y, q_z));
		fputs(f, sprintf("tick %g\n", rec_sl_tick[row]));
	}
	fclose(f);
	print("VIEWER SERVER ", label, "\n");
};
'''
BASE = '''cfg_save_auto 0
fs_cache 0
name ViewerControl
log_enable 1
log_dir logs
log_name runlines_smoke
con_notifytime 0
con_notifylines 0
cl_idlefps 0
cl_maxfps 100
vid_vsync 0
hud_scale 2
hud_keys 1
hud_crosshair 1
hud_trail 1
set ui_native_scores 0
set run_resume 0
waitms 2000
map surf_dune
waitmap 60
waitms 6000
menu_restart
ui_close
cmd zone_goto 0
waitms 400
+forward
waitms 3000
cmd timer
waitms 2000
-forward
waitms 2500
cmd timer
rewind
waitms 350
viewer_probe rewind
screenshot viewer_rewind
sl_save
waitms 350
sl_load
waitms 700
replay cfg/test/runlines_sample.rec
waitms 400
viewer_click wt_pause 1
waitms 100
viewer_click wt_pause 0
waitms 100
viewer_probe demo
screenshot viewer_demo
hud_edit
waitms 250
viewer_probe editor
screenshot viewer_editor
hud_edit
waitms 100
hud_player open
waitms 250
viewer_probe profile
hud_player close
scores tab local
scores filter all
scores
waitms 500
viewer_probe board
screenshot viewer_board
viewer_click sb_ln0 1
waitms 100
viewer_click sb_ln0 0
waitms 800
viewer_probe line
viewer_click sb_run0 1
waitms 100
viewer_click sb_run0 0
waitms 500
viewer_probe switched
viewer_boardoff
waitms 200
viewer_event down 49
viewer_event up 49
waitms 350
viewer_probe demosave
viewer_event down 50
waitms 100
viewer_event up 50
waitms 800
viewer_probe demoload
spectate ViewerTarget
waitms 700
viewer_probe spec
cmd viewer_server spec
screenshot viewer_spec
viewer_event down 49
viewer_event up 49
waitms 400
viewer_probe specsave
cmd viewer_server specsave
viewer_event down 50
waitms 100
viewer_event up 50
waitms 900
viewer_probe specload
spectate ViewerTarget
waitms 500
replay cfg/test/runlines_sample.rec
waitms 700
viewer_probe specdemo
cmd viewer_server specdemo
waitms 250
echo RUNLINES COMPLETE
quit
'''


def instrument(source):
    p = source/'src/client/cl_hud.qc'
    text = p.read_text()
    text = once(text, 'void(vector scr) HUD_DrawCrosshair =',
                'float viewer_crosshair, viewer_keys;\nvoid(vector scr) HUD_DrawCrosshair =')
    # Count actual calls in either arm, after declarations, before any return.
    text = once(text, '\tn = cvar("hud_crosshair");', '\tif (ui_rw_on) viewer_crosshair = viewer_crosshair + 1;\n\tn = cvar("hud_crosshair");')
    text = once(text, '\tHUD_KeysGeom(scr);', '\tif (ui_rw_on) viewer_keys = viewer_keys + 1;\n\tHUD_KeysGeom(scr);')
    p.write_text(text)
    p = source/'src/client/cl_main.qc'
    text = once(p.read_text(), 'float(string cmd) CSQC_ConsoleCommand =', CLIENT+'\nfloat(string cmd) CSQC_ConsoleCommand =')
    text = once(text, '\t// Patch 372.  `vote key', '\tif (argv(0) == "viewer_probe") { Viewer_Probe(argv(1)); return TRUE; }\n\tif (argv(0) == "viewer_click") { Viewer_Click(argv(1), stof(argv(2))); return TRUE; }\n\tif (argv(0) == "viewer_event") { CSQC_InputEvent(argv(1) == "down" ? IE_KEYDOWN : IE_KEYUP, stof(argv(2)), 0, 0); return TRUE; }\n\t// Patch 372.  `vote key')
    text = once(text, '\tif (argv(0) == "viewer_probe")', '\tif (argv(0) == "viewer_boardoff") { Scores_Close(); return TRUE; }\n\tif (argv(0) == "viewer_probe")')
    text = once(text, '\tWatch_RegisterCvars();', '\tWatch_RegisterCvars();\n\tregistercommand("viewer_probe");\n\tregistercommand("viewer_click");\n\tregistercommand("viewer_event");\n\tregistercommand("viewer_boardoff");')
    p.write_text(text)
    p = source/'src/server/sv_player.qc'
    text = once(p.read_text(), 'void(string cmd) SV_ParseClientCommand =', SERVER+'\nvoid(string cmd) SV_ParseClientCommand =')
    text = once(text, '\tif (c == "rec_nack")', '\tif (c == "viewer_server") { Viewer_Server(self, argv(1)); return; }\n\tif (c == "rec_nack")')
    p.write_text(text)


def read_probe(game, label):
    fields = {}
    for line in (game/f'cfg/test/viewer_{label}.txt').read_text().splitlines():
        words = line.split()
        fields[words[0]] = words[1:] if words[0] == 'path' else list(map(float, words[1:]))
    return fields


def grade(game):
    log = (game/'logs/runlines_smoke.log').read_text(errors='replace')
    assert 'RUNLINES COMPLETE' in log and not re.search(r'QC VM error|Unknown command|WRITE FAILED', log, re.I)
    probes = {label: read_probe(game, label) for label in ('rewind', 'demo', 'editor', 'profile', 'board', 'line', 'switched', 'demosave', 'demoload', 'spec', 'specsave', 'specload', 'specdemo')}
    for label in probes:
        assert log.count('VIEWER PROBE '+label+'\n') == 1, 'missing/duplicate action '+label
    assert probes['rewind']['view'][1] == 1, 'rewind did not act'
    assert all(v > 0 for v in probes['rewind']['rewindhud']), 'rewind skipped normal HUD'
    assert probes['demo']['view'][0] == 1 and probes['demo']['save'][0] >= 1, 'demo/rewind control did not act'
    assert probes['demo']['pause'][0] == 1, 'clickable player pause did not act'
    assert probes['editor']['view'][4] == 1 and probes['profile']['view'][5] == 1, 'modal still refuses playback'
    assert probes['board']['view'][3] == 1 and probes['board']['view'][6] == 1, 'board not in front of viewer'
    assert probes['line']['lines'][0] >= 1, 'actual board click did not enable line'
    assert probes['switched']['path'] != probes['demo']['path'], 'actual row click did not switch demo'
    assert probes['demosave']['save'][0] == probes['demo']['save'][0] + 1, 'demo save did not act'
    assert probes['demoload']['view'][0] == 0, 'demo load did not leave playback'
    assert probes['spec']['view'][2] == 1 and probes['spec']['save'][2] > 0, 'real peer spectator did not act'
    assert probes['specsave']['save'][0] == probes['spec']['save'][0] + 1, 'spectator save refused'
    saved = read_probe(game, 'server_specsave')
    assert saved['hold'][0] == 1 and saved['tick'][0] == -1, 'spectator save altered hold or was not practice-only'
    assert max(abs(a-b) for a, b in zip(saved['saved'], probes['spec']['pose'])) < 2, 'not saved at watched pose'
    assert max(abs(a-b) for a, b in zip(saved['body'], saved['saved'])) > 50, 'parked body is not a disambiguating control'
    assert probes['specload']['save'][2] == 0, 'load did not leave spectate'
    assert probes['specdemo']['view'][0] == 1 and probes['specdemo']['save'][2] == 0, 'spectate-to-demo handoff refused'
    pin = read_probe(game, 'server_specdemo')['hold']
    assert pin[:2] == [0, 1], 'server viewer owners overlap'
    print('PASS acting board line/replay clicks, modal controls, viewer saves/loads, rewind HUD, exclusive handoff')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--baseline')
    ap.add_argument('--port', type=int, default=27616)
    ap.add_argument('--grade-only', type=Path)
    args = ap.parse_args()
    if args.grade_only:
        grade(args.grade_only/'ftesurf')
        return
    out = args.output_dir.resolve()
    if not any((p/'OWNER.md').is_file() for p in (out, *out.parents)):
        raise ValueError('--output-dir requires an owned task root')
    out.mkdir(parents=True, exist_ok=False)
    source = out/'source'
    tracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', 'src', 'ftesurf/cfg', 'default.fmf'], text=True).splitlines()
    for name in tracked:
        dst = source/name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if args.baseline:
            dst.write_bytes(subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{args.baseline}:{name}']))
        else:
            shutil.copy2(ROOT/name, dst)
    shutil.copy2('C:/FTESurf/src/fteqcc64.exe', source/'src/fteqcc64.exe')
    instrument(source)
    env = dict(os.environ, PATH='C:/FTESurf/src;'+os.environ['PATH'])
    build = subprocess.run(['pwsh', '-NoProfile', '-File', './build.ps1', '-Jobs', '8', '-NoDeploy'], cwd=source/'src', env=env, capture_output=True, text=True)
    (out/'build.log').write_text(build.stdout+build.stderr)
    assert build.returncode == 0, 'probe build failed; see build.log'
    qc = list((source/'rig').glob('build-nodeploy-*'))
    assert len(qc) == 1
    cfg = out/'viewer.cfg'
    cfg.write_text(BASE)
    sample = out/'viewer.rec'
    lines = ['FTESURF-REC 4', 'map surf_dune', 'owner ViewerFixture', 'track 0', 'startseg 0', 'leg 0', 'tickrate 0.015', 'flags 0', 'begin']
    for i in range(401):
        t = i/10
        lines.append(f'{t:.6f} {t*100-11500:.6f} 1300 14500 100 0 0 0 180 0 0 1 0 0 0 0 0')
    lines.append('end 2667')
    sample.write_text('\n'.join(lines)+'\n')
    data = out/'rows'
    data.mkdir()
    shutil.copy2(sample, data/'0002667_fixture_pb.rec')
    # Put a second playback identity on the board so a click cannot falsely pass.
    (data/'0003000_other_pb.rec').write_text(sample.read_text().replace('ViewerFixture', 'ViewerSecond').replace('end 2667', 'end 3000'))
    runner = (ROOT/'tools/runlines_smoke.py').read_text()
    runner = once(runner, 'ROOT = pathlib.Path(__file__).resolve().parent.parent', f'ROOT = pathlib.Path({str(ROOT)!r})')
    runner = once(runner, "source = {'qwprogs.dat': a.ssqc, 'csprogs.dat': a.csqc}.get(name)", "source = {'qwprogs.dat': a.ssqc, 'csprogs.dat': a.csqc, 'menu.dat': a.csqc.parent / 'menu.dat'}.get(name)")
    peer_cfg = f'cfg_save_auto 0\nname ViewerTarget\ncl_idlefps 0\ncl_maxfps 100\nlog_enable 1\nlog_dir logs\nlog_name viewer_target\nconnect 127.0.0.1:{args.port}\nwaitmap 60\nwaitms 6000\nmenu_restart\nui_close\ncmd zone_goto 0\nwaitms 400\n+forward\nwaitms 1000\n-forward\nwaitms 70000\nquit\n'
    runner = once(runner, '        if a.dedicated:\n            extra =', '        (gd / "cfg/test/viewer_server.cfg").write_text(\'cfg_save_auto 0\\nsv_guidkey "viewer-smoke-fixture-only"\\n\')\n        if a.dedicated:\n            extra =')
    runner = once(runner, '        client = subprocess.Popen(', '        (gd / "cfg/test/viewer_peer.cfg").write_text('+repr(peer_cfg)+')\n        peer = subprocess.Popen([str(executable), *common, "-window", "+exec", "cfg/test/viewer_peer.cfg"], cwd=a.content, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n        client = subprocess.Popen(')
    # Scoped cleanup belongs to this peer handle, never an executable-name kill.
    runner = once(runner, '    finally:\n', '    finally:\n        if "peer" in locals() and peer.poll() is None:\n            peer.terminate()\n            peer.wait(timeout=10)\n')
    harness = out/'runlines.py'
    harness.write_text(runner)
    result = subprocess.run([sys.executable, '-B', str(harness), str(cfg), '--recording', str(sample), '--dedicated', '--server-arg', '+exec cfg/test/viewer_server.cfg +set lobby_enable 1 +set lobby_nocollide 1 +set lobby_avatars 1 +set lobby_av_stream 1', '--port', str(args.port), '--timeout', '100', '--output-dir', str(out), '--ssqc', str(qc[0]/'qwprogs.dat'), '--csqc', str(qc[0]/'csprogs.dat'), '--put', 'data/runs/surf_dune/main/0002667_fixture_pb.rec='+str(data/'0002667_fixture_pb.rec'), '--put', 'data/runs/surf_dune/main/0003000_other_pb.rec='+str(data/'0003000_other_pb.rec')], capture_output=True, text=True)
    (out/'runtime.log').write_text(result.stdout+result.stderr)
    assert result.returncode == 0, 'runtime failed; see runtime.log'
    rigs = re.findall(r'^Retained private rig: (.+)$', result.stdout, re.M)
    assert len(rigs) == 1
    print('Retained viewer rig:', rigs[0])
    grade(Path(rigs[0])/'ftesurf')


if __name__ == '__main__':
    main()
