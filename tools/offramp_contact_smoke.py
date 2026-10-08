#!/usr/bin/env python3
"""Private native/live off-ramp measurement. Diagnostic progs NEVER ship.

Requires a PRIVATE server built with native_instrument()'s two seams. No
classification or recording/evidence semantics are changed. Each render/sample
row is emitted at its actual production call site, not reconstructed by Python.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

from stitched_rewind_smoke import BASE, once

ROOT = Path(__file__).resolve().parents[1]

NATIVE_CALL = '''\t\tCon_Printf("OFFRAMP_NATIVE %u %.9g %d %d %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g\\n",
\t\t\tpms_offbase + iters + 1, tick, (int)pmove.rampcontact, (int)pmove.onground,
\t\t\tpmove.origin[0], pmove.origin[1], pmove.origin[2],
\t\t\tpmove.velocity[0], pmove.velocity[1], pmove.velocity[2],
\t\t\tpmove.rampnormal[0], pmove.rampnormal[1], pmove.rampnormal[2]);
'''

def isolated(work):
    work = work.resolve()
    if not (work / '.git').is_file():
        raise RuntimeError('Diagnostic seams require an isolated Git worktree, never the owner checkout')
    dirty = subprocess.check_output(['git', '-C', str(work), 'status', '--porcelain',
                                     '--untracked-files=no'], text=True)
    if dirty.strip():
        raise RuntimeError('Refusing diagnostic seams in a tracked-dirty worktree')


def native_instrument(work):
    """Apply ONLY in an isolated native checkout before sv-rel, never an install."""
    isolated(work)
    p = work / 'engine/common/pm_source.c'
    text = once(p.read_text(), 'void PMSrc_PlayerMove (float gamespeed)\n{',
                '/* PRIVATE per-native-tick contact trace; diagnostic build NEVER ships. */\n'
                'unsigned int pms_offbase;\nvoid PMSrc_PlayerMove (float gamespeed)\n{')
    p.write_text(once(text, '\t\tPMSrc_Tick ();\n\t\tavail -= tick;',
                     '\t\tPMSrc_Tick ();\n' + NATIVE_CALL + '\t\tavail -= tick;'))
    p = work / 'engine/server/sv_user.c'
    p.write_text(once(p.read_text(), '#else\n\tPM_PlayerMove (sv.gamespeed);\n#endif',
                     '#else\n\t{\n\t\textern unsigned int pms_offbase;\n'
                     '\t\tpms_offbase = host_client->movetickcount;\n'
                     '\t\tPM_PlayerMove (sv.gamespeed);\n\t}\n#endif'))


def instrument(work):
    isolated(work)
    p = work / 'src/client/cl_trailstate.qc'
    p.write_text(once(p.read_text(), '\tif (tr_raw < 1)\n\t\treturn;\n\tif (buf_getsize(tr_raw)', r'''	print(sprintf("OFFRAMP_SAMPLE %d %d %.9g %.9g %d %s\n", tr_gen,
	              ln_nsamp[tr_live] - 1, t, cltime, clientcommandframe,
	              sprintf("%g %g %g %g %g", fl, ln_pkind[tr_live], ln_ron[tr_live], tr_live, brk)));
	print(sprintf("OFFRAMP_BODY %d %d %s %s %.9g\n", tr_gen,
	              ln_nsamp[tr_live] - 1, sprintf("%.9g %.9g %.9g", o_x, o_y, o_z),
	              sprintf("%.9g %.9g %.9g", v_x, v_y, v_z), ln_rlast[tr_live]));
	if (tr_raw < 1)
		return;
	if (buf_getsize(tr_raw)'''))
    p = work / 'src/client/cl_lines.qc'
    text = once(p.read_text(), 'void(float s, float k, float sub, float t, vector o, vector v) Line_Ev =',
                'float ln_offleave; // PRIVATE: auto-hold first ACTED surf-to-air leave\n'
                'void(float s, float k, float sub, float t, vector o, vector v) Line_Ev =')
    text = once(text, '\tln_ek[b + n]  = k;', r'''	if (s >= LN_S_TRAIL)
		print(sprintf("OFFRAMP_EVENT %g %d %g %g %.9g %s\n", s, ln_nsamp[s], k, sub, t,
		              sprintf("%.9g %.9g %.9g", o_x, o_y, o_z)));
	if (s >= LN_S_TRAIL && k == LN_E_LEAVE && sub == 9 && !ln_offleave)
		ln_offleave = t;
	ln_ek[b + n]  = k;''')
    text = once(text, '\t\tln_nmk = ln_nmk + 1;', r'''		if (s >= LN_S_TRAIL)
			print(sprintf("OFFRAMP_RENDER %g %d %g %.9g %.9g %s\n", s, ln_ei[n + e], k,
			              ln_et[n + e], cltime, sprintf("%.9g %.9g %.9g", p_x, p_y, p_z)));
		ln_nmk = ln_nmk + 1;''')
    p.write_text(text)
    p = work / 'src/client/cl_main.qc'
    text = once(p.read_text(), 'void(float vwidth, float vheight, float notmenu) CSQC_UpdateView =',
                'float off_state, off_due; // PRIVATE acted leave -> production rewind view\n'
                'void(float vwidth, float vheight, float notmenu) CSQC_UpdateView =')
    text = once(text, '\tRewind_Frame(navfocus);', r'''	if (ln_offleave && !off_state)
	{
		Rewind_Open();
		off_state = 1; off_due = cltime + 0.15;
	}
	if (off_state == 1 && cltime >= off_due && !rw_on)
	{
		Rewind_Open();
		off_state = 2; off_due = cltime + 0.35;
	}
	if (off_state == 2 && cltime >= off_due && rw_on && !rw_cd && !rw_ack)
	{
		rw_i = Line_Find(tr_live, ln_offleave);
		Rewind_Cursor();
		print(sprintf("OFFRAMP_HELD %.9g %.9g %g %g %g\n", tr_cur_t, ln_offleave, rw_on, rw_cd, rw_ack));
		off_state = 3;
	}
	Rewind_Frame(navfocus);''')
    p.write_text(text)
    p = work / 'src/server/sv_player.qc'
    p.write_text(once(p.read_text(), '\tSV_TimerFrame(self);', r'''	SV_TimerFrame(self);
	print(sprintf("OFFRAMP_PACKET %d %d %d %g %g %g %s\n", self.run_pkn,
	              self.run_movetick, SV_TimerTicks(self), self.run_t_state,
	              SV_RecLive(self), self.run_rampcontact,
	              sprintf("%.9g %.9g %.9g", self.origin_x, self.origin_y, self.origin_z)));
	print(sprintf("OFFRAMP_ANCHOR %d %.9g %d %.9g\n", self.run_pkn,
	              self.run_t_starttick, self.run_t_frzticks, run_t_tick));'''))


def config(fps, mapname):
    # Walk off the real start. No setpos, synthetic ramp, noclip, or input-contact
    # injection. Hands-off route is only a measurement if a native ride ACTS.
    text = BASE.replace('cl_maxfps 100\n', f'cl_maxfps {fps}\n').replace('map surf_dune\n', f'map {mapname}\n') + '''
set hud_lines_marks 1
set hud_lines_nums 2
set hud_lines_dist 0
set hud_rewind_chase 1
cmd zone_goto start
waitms 800
+forward
+moveright
waitms 2300
-forward
-moveright
cmd timer
waitms 10000
trail
cmd timer
rewind status
wait 12
screenshot offramp_contact.png
wait 12
echo RUNLINES COMPLETE
quit
'''
    if mapname == 'surf_voyager':
        text = text.replace('+moveright\n', '').replace('-moveright\n', '')
        text = text.replace('+forward\n', '+back\n').replace('-forward\n', '-back\n')
        text = text.replace('waitms 10000\n', 'waitms 8000\n')
    return text


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native-server', type=Path)
    ap.add_argument('--output-dir', type=Path)
    ap.add_argument('--instrument-native', type=Path, help='Apply private seams in a clean isolated engine worktree')
    ap.add_argument('--grade-only', type=Path, help='Strictly grade a retained rig without launching anything')
    ap.add_argument('--fps', type=int, nargs='+', default=[30, 100, 300])
    ap.add_argument('--port', type=int, default=27617)
    ap.add_argument('--map', choices=['surf_dune', 'surf_voyager'], default='surf_voyager')
    ap.add_argument('--instrument-only', action='store_true')
    a = ap.parse_args()
    if a.instrument_native:
        native_instrument(a.instrument_native)
        return
    if a.instrument_only:
        instrument(ROOT)
        return
    if a.grade_only:
        from offramp_contact import grade
        print(json.dumps(grade(a.grade_only), indent=2))
        return
    if not a.native_server or not a.output_dir:
        ap.error('Live diagnostics require --native-server and --output-dir')
    if not (ROOT / '.git').is_file():
        ap.error('Run only from an isolated source worktree')
    if b'OFFRAMP_NATIVE' not in a.native_server.read_bytes():
        ap.error('Server lacks the private per-native-tick diagnostic')
    if 'OFFRAMP_SAMPLE' not in (ROOT / 'src/client/cl_trailstate.qc').read_text():
        ap.error('Apply --instrument-only and build with -QuakeDir empty first')
    a.output_dir.mkdir(parents=True, exist_ok=True)
    # ROOT is an already isolated source checkout. Instrument separately with
    # --instrument-only; do not implicitly mutate either owner's source tree.
    runner = ROOT / 'tools/runlines_smoke.py'
    rt = runner.read_text()
    rt = once(rt, "['C:/FTEQuake/fteqwsv64.exe', *common", f'[{str(a.native_server)!r}, *common')
    rt = once(rt, "shutil.copyfile(ROOT / 'default.fmf', rig / 'default.fmf')",
              "shutil.copyfile(ROOT / 'default.fmf', rig / 'default.fmf')\n"
              "        for plugin in a.content.glob('fteplug_*_x64.dll'):\n"
              "            shutil.copyfile(plugin, rig / plugin.name)")
    rt = rt.replace('surf_dune', a.map)
    # Keep generated runner beside the real runner so ROOT remains this checkout.
    diagnostic_runner = ROOT / 'tools/offramp_overlay_runner.py'
    diagnostic_runner.write_text(rt)
    for fps in a.fps:
        if fps not in (30, 100, 300):
            raise ValueError('Use the registered 30/100/300 FPS arms')
        out = a.output_dir / f'fps{fps}'
        out.mkdir(exist_ok=True)
        cfg = out / 'offramp.cfg'
        cfg.write_text(config(fps, a.map))
        result = subprocess.run([sys.executable, '-B', str(diagnostic_runner), str(cfg),
                                 '--dedicated', '--port', str(a.port), '--timeout', '120',
                                 '--output-dir', str(out)], capture_output=True, text=True)
        (out / 'runner.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'Unacted overlay; retained {out / "runner.log"}')
        rig = Path(result.stdout.strip().splitlines()[-1].removeprefix('Retained private rig: '))
        native_root = a.native_server.resolve().parents[2]
        provenance = {'captured_utc': datetime.now(timezone.utc).isoformat(),
                      'native_ref': subprocess.check_output(['git', '-C', str(native_root), 'rev-parse', 'HEAD'], text=True).strip(),
                      'native_diff_sha256': hashlib.sha256(subprocess.check_output(['git', '-C', str(native_root), 'diff', '--', 'engine/common/pm_source.c', 'engine/server/sv_user.c'])).hexdigest(),
                      'source_diff_sha256': hashlib.sha256(subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--', 'src/client/cl_lines.qc', 'src/client/cl_main.qc', 'src/client/cl_trailstate.qc', 'src/server/sv_player.qc'])).hexdigest(),
                      'source_ref': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
                      'native_server_sha256': sha(a.native_server),
                      'client_sha256': sha(Path('C:/FTESurf/ftesurf64.exe')),
                      'fps': fps, 'map': a.map, 'rig': str(rig),
                      'qwprogs_sha256': sha(ROOT / 'ftesurf/qwprogs.dat'),
                      'csprogs_sha256': sha(ROOT / 'ftesurf/csprogs.dat'),
                      'diagnostic_only': True}
        (out / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
        print(f'Retained {fps} FPS: {rig}')


if __name__ == '__main__':
    main()
