#!/usr/bin/env python3
"""P1384 arm: a tapped save load at a simulated ping (cl_delay_packets) against a dedicated server.

    python -B tools/p1384lead.py --out <dir under an OWNER.md root> --progs <build.ps1 -NoDeploy dir>
                                 --src <that build's src> [--delays 0,150,300] [--lead 1]

surf_dune's end room with the main start box moved into its corner (prepare). Each round: setpos into
the box, walk out (the run starts) for 2 s, save, walk 1 s, stop, then tap the load key
(`+sl_hold 50;-sl_hold 50`) or, with --hold, hold it 2.5 s in a second round.

The arm's csprogs is --src plus one TEST-ONLY probe (never shipped): with p1384_probe 1 it prints,
every rendered frame from the press until 1.5 s after the release, the client's own hold state, the
travel's state, the rendered eye (VF_ORIGIN after SaveLoc_Camera) and the predicted body. The engine's
cl_prederror 4 lines ("prederr: ...") are the misprediction witness. Graded per tap: the press frame
to the travel's first frame, the release frame, the largest eye jump between frames while held, and
prederr lines from the press to 3 s after it. Needs the rig lock and an announcement to peers.
"""
import argparse
import hashlib
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p840clock as R  # noqa: E402  take_lock/drop_lock/free_mb/owned
from spec_chat_smoke import Peer  # noqa: E402

CONTENT = Path('C:/FTESurf')
MAP = 'surf_dune'
# The end room (x 11360..12032, y 10944..11904, floor 12912) with a start box in its corner and the
# end moved far away, so a walk out of the box is a run and a save in the room is a running save.
BOX = (11500, 11600, 11080, 11180)  # clear of the room's chamfered corners
O = (11550.0, 11130.0, 12914.0)     # in the box; yaw 55 walks ~800 u of floor toward the far corner

PROBE = r'''
// P1384 ARM ONLY -- never shipped.
float p1384_was, p1384_rel;
void() P1384_Probe =
{
	local vector cam;
	if (rec_sl_holding) p1384_was = TRUE;
	else if (p1384_was) { p1384_was = FALSE; p1384_rel = cltime; }
	if (!rec_sl_holding && cltime - p1384_rel > 1.5) return;
	cam = getproperty(VF_ORIGIN);
	print(sprintf("P1384 t %.4f t0 %.4f hold %g wop %g buf %g pend %g left %.3f ", cltime, rec_sl_holdt0,
		rec_sl_holding, rec_sl_wophold, sl_lead_buf >= 1, sl_lead_pending > 0, SaveLead_Remaining()),
		sprintf("shold %g up %g cam %.2f %.2f %.2f ", getstatf(STAT_FS_HOLD), rec_sl_upwait, cam_x, cam_y, cam_z),
		sprintf("body %.2f %.2f %.2f txt [%s]\n", pmove_org_x, pmove_org_y, pmove_org_z, SaveLoc_LeadText()));
};
'''


SPLIT_PROBE = r'''
// P1437 ARM ONLY: emulate independent numeric-stat arrival, NOT packet transport.
float p1437_seq, p1437_until, p1437_arms, p1437_holdzeros, p1437_opstales, p1437_boundframes;
float(float st) P1437_Stat =
{
	local float value, seq, mode;
	value = getstatf(st);
	mode = cvar("p1437_split_stats");
	if (!mode || mode > 2) return value;
	seq = getstatf(STAT_FS_SLSEQ);
	if (seq != p1437_seq)
	{
		p1437_seq = seq;
		p1437_until = 0;
		if (FS_SlopOp(getstatf(STAT_FS_SLOP)) == SLOP_LOADED)
		{
			p1437_until = cltime + 0.12;
			p1437_arms += 1;
			print(sprintf("P1437 split seq %.0f mode %g at %.4f\n", seq, mode, cltime));
		}
	}
	if (cltime < p1437_until)
	{
		if (st == STAT_FS_HOLD) { p1437_holdzeros += 1; return 0; }
		if (mode >= 2 && st == STAT_FS_SLOP)
		{
			p1437_opstales += 1;
			return FS_SlopPack(SLOP_SAVED, FS_SlopId(value));
		}
	}
	return value;
};
void() P1437_Probe =
{
	local float ignored;
	ignored = P1437_Stat(STAT_FS_SLOP); // stale op exists even if the product ignores it
	if (sl_lead_early >= 2) p1437_boundframes += 1;
	if (p1437_arms)
		print(sprintf("P1437 acts %g holdzeros %g opstales %g bound %g\n",
		              p1437_arms, p1437_holdzeros, p1437_opstales, p1437_boundframes));
};
'''


CAPSULE_PROBE = r'''
string p1437_lastpacket, p1437_holdpacket;
float p1437_packetseq, p1437_packetuntil, p1437_packetarms, p1437_packetreads;
float p1437_cursorarmed, p1437_cursorreported, p1437_godumped;
float(float st) P1437_Cursor =
{
	local float value;
	value = getstatf(st);
	if (p1437_cursorarmed && st == STAT_FS_SLORG) value += 4096;
	return value;
};
void() P1437_TrailProbe =
{
	local float n, f, i, sq;
	n = 0;
	if (tr_raw >= 1) n = buf_getsize(tr_raw);
	if (P1437_PENDING)
	{
		print(sprintf("P1437 trail pending rows %g gen %g state %g\n", n, tr_gen, tr_state));
		if (rw_ack > 0 && !p1437_godumped && n > 0)
		{
			f = fopen("logs/p1437-go-before.txt", FILE_WRITE);
			if (f >= 0)
			{
				fputs(f, sprintf("%.9g\n", tr_tick));
				for (i = 0; i < n; i += 1) fputs(f, strcat(bufstr_get(tr_raw, i), "\n"));
				fclose(f);
				p1437_godumped = TRUE;
				print(sprintf("P1437 trail go dump rows %g\n", n));
			}
		}
	}
	sq = SaveEvent_Seq();
	if (p1437_cursorarmed && !P1437_PENDING && p1437_cursorreported != sq)
	{
		p1437_cursorreported = sq;
		print(sprintf("P1437 cursor coherent seq %g event %v cursor %v go %v\n", sq,
		              P1437_ORIGIN, [P1437_Cursor(STAT_FS_SLORG), P1437_Cursor(STAT_FS_SLORG + 1), P1437_Cursor(STAT_FS_SLORG + 2)], rw_gop));
	}
};
string(float st) P1437_String =
{
	local string value;
	local float seq;
	value = getstats(st);
	seq = getstatf(STAT_FS_SLSEQ);
	if (seq != p1437_packetseq)
	{
		p1437_packetseq = seq;
		p1437_packetuntil = 0;
		if (cvar("p1437_split_stats") >= 6 && FS_SlopOp(getstatf(STAT_FS_SLOP)) == SLOP_SAVED)
		{
			p1437_cursorarmed = TRUE;
			print(sprintf("P1437 saved cursor arm seq %g offset 4096\n", seq));
		}
		if (FS_SlopOp(getstatf(STAT_FS_SLOP)) == SLOP_LOADED)
		{
			if (strlen(p1437_holdpacket)) strunzone(p1437_holdpacket);
			p1437_holdpacket = strzone(p1437_lastpacket);
			p1437_packetuntil = cltime + 0.12;
			p1437_packetarms += 1;
			if (cvar("p1437_split_stats") >= 6 && rw_ack > 0)
			{
				p1437_cursorarmed = TRUE;
				print(sprintf("P1437 cursor arm seq %g offset 4096\n", seq));
			}
			print(sprintf("P1437 capsule arm %.0f at %.4f\n", seq, cltime));
		}
	}
	if (cltime < p1437_packetuntil)
	{
		p1437_packetreads += 1;
		return p1437_holdpacket;
	}
	if (strcmp(value, p1437_lastpacket))
	{
		if (strlen(p1437_lastpacket)) strunzone(p1437_lastpacket);
		p1437_lastpacket = strzone(value);
	}
	return value;
};
void() P1437_Turn =
{
	if (!cvar("p1437_turn")) return;
	cvar_set("p1437_turn", "0");
	setproperty(VF_CL_VIEWANGLES, [13, 137, 0]);
	input_angles = [13, 137, 0];
	print("P1437 turn to 13 137 0\n");
};
void() P1437_AngleProbe =
{
	if (!p1437_packetarms) return;
	print(sprintf("P1437 capsule acts %g reads %g\n", p1437_packetarms, p1437_packetreads));
	print(sprintf("P1437 angle native %v latch %v pending %g capsule %s\n",
	              getproperty(VF_CL_VIEWANGLES), rec_sl_holdang, P1437_PENDING,
	              getstats(STAT_FS_SLLEAD)));
};
'''


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def build_probe(src, out, split_stats=0):
    tree = out / 'cstree'
    shutil.copytree(src, tree / 'src', ignore=shutil.ignore_patterns('*.dat', '*.lno', 'rig'))
    (tree / 'ftesurf').mkdir()
    if split_stats:
        for f in (tree / 'src/client').glob('*.qc'):
            text = f.read_bytes().decode()
            text = text.replace('getstatf(STAT_FS_HOLD)', 'P1437_Stat(STAT_FS_HOLD)')
            text = text.replace('getstatf(STAT_FS_SLOP)', 'P1437_Stat(STAT_FS_SLOP)')
            if split_stats >= 3:
                text = text.replace('getstats(STAT_FS_SLLEAD)', 'P1437_String(STAT_FS_SLLEAD)')
            if split_stats >= 6:
                for st in ('STAT_FS_SLORG', 'STAT_FS_SLORG + 1', 'STAT_FS_SLORG + 2'):
                    text = text.replace(f'getstatf({st})', f'P1437_Cursor({st})')
            f.write_bytes(text.encode())
        # Declare before all consumers without touching generated defs/*.qc.
        (tree / 'src/client/p1437_split_proto.qc').write_bytes(
            b'float(float st) P1437_Stat;\n' + (b'string(float st) P1437_String;\nvoid() P1437_TrailProbe;\n' if split_stats >= 3 else b'')
            + (b'float(float st) P1437_Cursor;\n' if split_stats >= 6 else b''))
        f = tree / 'src/cl_progs.src'
        text = f.read_bytes()
        entry = b'shared/sh_defs.qc\n'
        assert text.count(entry) == 1
        f.write_bytes(text.replace(entry, entry + b'client/p1437_split_proto.qc\n'))
    if split_stats == 4:
        # Negative control: the reviewed pre-fix pending fences, never product.
        assert (tree / 'src/client/cl_saveevent.qc').is_file()
        f = tree / 'src/client/cl_saveloc.qc'
        text = f.read_text(); fence = '\tif (SaveEvent_Pending()) return;\n'
        assert text.count(fence) == 2
        f.write_text(text.replace(fence, ''))
        f = tree / 'src/client/cl_replay.qc'
        text = f.read_text(); fence = '\tif (!SaveEvent_Pending())\n'
        assert text.count(fence) == 1
        f.write_text(text.replace(fence, ''))
        f = tree / 'src/client/cl_rewind.qc'
        text = f.read_text()
        fence = ('\tif (SaveEvent_Pending())\n\t{\n'
                 '\t\tif ((cltime - rw_sentat) > RW_LOST) Rewind_Abandon();\n\t\treturn;\n\t}\n')
        assert text.count(fence) == 1
        f.write_text(text.replace(fence, ''))
        f = tree / 'src/client/cl_board.qc'
        text = f.read_text(); assert text.count('SaveEvent_Pending() || ') == 1
        f.write_text(text.replace('SaveEvent_Pending() || ', ''))
    if split_stats == 5:
        f = tree / 'src/client/cl_trail.qc'; text = f.read_text()
        fence = '\tif (SaveEvent_Pending()) return;\n'; assert text.count(fence) == 1
        f.write_text(text.replace(fence, ''))
    if split_stats == 6:
        f = tree / 'src/client/cl_rewind.qc'; text = f.read_text()
        old = 'return vlen(SaveEvent_Origin() - rw_gop) <= RW_GONEAR;'; assert text.count(old) == 1
        text = text.replace(old, 'return vlen([P1437_Cursor(STAT_FS_SLORG), P1437_Cursor(STAT_FS_SLORG + 1), P1437_Cursor(STAT_FS_SLORG + 2)] - rw_gop) <= RW_GONEAR;')
        f.write_text(text)
        f = tree / 'src/client/cl_board.qc'; text = f.read_text()
        old = 'seq_mk_aorg = SaveEvent_Origin();'; assert text.count(old) == 1
        f.write_text(text.replace(old, 'seq_mk_aorg = [P1437_Cursor(STAT_FS_SLORG), P1437_Cursor(STAT_FS_SLORG + 1), P1437_Cursor(STAT_FS_SLORG + 2)];'))
    if split_stats >= 3 and (tree / 'src/client/cl_saveevent.qc').is_file():
        f = tree / 'src/client/cl_trail.qc'; text = f.read_text()
        entry = '\tTrail_Catch(TR_CATCH);          // P1384\n'; assert text.count(entry) == 1
        f.write_text(text.replace(entry, entry + '\tP1437_TrailProbe(); // ARM ONLY, before fallback state transitions\n'))
        f = tree / 'src/client/cl_trailstate.qc'; text = f.read_text()
        entry = 'void() Trail_RawClear =\n{\n'; assert text.count(entry) == 1
        f.write_text(text.replace(entry, entry + '\tif (SaveEvent_Pending())\n\tif (tr_raw >= 1) print(sprintf("P1437 trail clear pending rows %g gen %g\\n", buf_getsize(tr_raw), tr_gen));\n'))
        f = tree / 'src/client/cl_replay.qc'; text = f.read_text()
        entry = 'void() Rec_ViewFailDrop =\n{\n'; assert text.count(entry) == 1
        text = text.replace(entry, entry + '\tif (rec_fa_view >= 1) print(sprintf("P1437 prefix drop lines %g pending %g\\n", rec_fa_lines, SaveEvent_Pending()));\n')
        entry = '\trec_fa_lines = rec_rp_lines;'; assert text.count(entry) == 1
        text = text.replace(entry, entry + '\n\tprint(sprintf("P1437 prefix keep lines %g\\n", rec_fa_lines));')
        entry = 'rec_rp_view = rec_fa_view;'; assert text.count(entry) == 2
        text = text.replace(entry, entry + '\n\t\t\t\tprint(sprintf("P1437 prefix transfer lines %g pending %g\\n", rec_fa_lines, SaveEvent_Pending()));')
        f.write_text(text)
    f = tree / 'src/client/cl_savelead.qc'
    capsule = CAPSULE_PROBE.replace('P1437_PENDING', 'SaveEvent_Pending()' if (tree / 'src/client/cl_saveevent.qc').is_file() else '0')
    has_origin = (tree / 'src/client/cl_saveevent.qc').is_file() and 'SaveEvent_Origin' in (tree / 'src/client/cl_saveevent.qc').read_text()
    capsule = capsule.replace('P1437_ORIGIN', 'SaveEvent_Origin()' if has_origin else '[0, 0, 0]')
    if not (tree / 'src/client/cl_saveevent.qc').is_file():
        capsule = capsule.replace('SaveEvent_Seq()', 'getstatf(STAT_FS_SLSEQ)')
    f.write_bytes(f.read_bytes() + PROBE.encode() + (SPLIT_PROBE.encode() if split_stats else b'')
                  + (capsule.encode() if split_stats >= 3 else b''))
    f = tree / 'src/client/cl_main.qc'
    t = f.read_bytes().decode()
    hook = '\tSaveLoc_Camera();               // Patch 430: a load drawn before its reply\n'
    assert t.count(hook) == 1
    t = t.replace(hook, hook + '\tif (cvar("p1384_probe")) P1384_Probe();   // ARM ONLY\n')
    if split_stats:
        t = t.replace(hook, hook + '\tif (cvar("p1384_probe")) P1437_Probe();   // ARM ONLY\n')
    if split_stats >= 3:
        t = t.replace(hook, hook + '\tif (cvar("p1384_probe")) P1437_AngleProbe();   // ARM ONLY\n')
        entry = 'void() CSQC_Input_Frame =\n{\n'; assert t.count(entry) == 1
        t = t.replace(entry, entry + '\tP1437_Turn(); // ARM ONLY\n')
    init = 'void(float apilevel, string enginename, float engineversion) CSQC_Init =\n{\n'
    assert t.count(init) == 1
    t = t.replace(init, init + '\tregistercvar("p1384_probe", "0", 0);\n'
                             f'\tregistercvar("p1437_split_stats", "{split_stats}", 0);\n'
                             '\tregistercvar("p1437_turn", "0", 0);\n')
    f.write_bytes(t.encode())
    # Match build.ps1's P1391 string budget; the default 2 MiB cannot compile
    # today's unchanged client, even before the probe is added.
    r = subprocess.run([str(tree / 'src/fteqcc64.exe'), '-max_strings', '4194304',
                        '-srcfile', 'cl_progs.src', '-Fomitarraydefs'], cwd=tree / 'src',
                       capture_output=True, text=True)
    (out / 'cs-build.log').write_text(r.stdout + r.stderr)
    warn = [l for l in (r.stdout + r.stderr).splitlines() if 'warning' in l.lower() and '0 warnings' not in l]
    assert r.returncode == 0 and not warn and (tree / 'ftesurf/csprogs.dat').is_file(), 'probe build failed'
    return tree / 'ftesurf/csprogs.dat'


def prepare(out, name, progs, csprogs):
    base = out / name
    game = base / 'ftesurf'
    for folder in ('glsl', 'scripts', 'models', 'particles'):
        if (CONTENT / 'ftesurf' / folder).is_dir():
            shutil.copytree(CONTENT / 'ftesurf' / folder, game / folder)
    for folder in ('fonts', 'ui'):
        if (CONTENT / 'ftesurf/gfx' / folder).is_dir():
            shutil.copytree(CONTENT / 'ftesurf/gfx' / folder, game / 'gfx' / folder)
    for folder in ('cfg', 'maps/zones/local', 'logs', 'data', 'downloads/csprogsvers'):
        (game / folder).mkdir(parents=True)
    (game / 'data/consent.txt').write_text('version 4\n')
    shutil.copy2(CONTENT / f'ftesurf/maps/{MAP}.bsp', game / f'maps/{MAP}.bsp')
    z = json.loads((CONTENT / f'ftesurf/maps/zones/local/{MAP}.json').read_text(encoding='utf-8'))
    main = z['tracks']['main']['zones']
    seg = main['segments'][0]
    seg['limitStartGroundSpeed'] = False
    reg = seg['checkpoints'][0]['regions'][0]
    end = main['end']['regions'][0]
    main['end']['regions'] = [dict(end, points=reg['points'], bottom=reg['bottom'], height=reg['height'])]
    reg['points'] = [[BOX[0], BOX[2]], [BOX[0], BOX[3]], [BOX[1], BOX[3]], [BOX[1], BOX[2]]]
    reg['bottom'], reg['height'] = 12912, 200
    reg.pop('teleDestTargetname', None)
    main['segments'] = [seg]
    z['tracks'] = {'main': z['tracks']['main']}
    (game / f'maps/zones/local/{MAP}.json').write_text(json.dumps(z), encoding='utf-8')
    shutil.copy2(progs / 'qwprogs.dat', game / 'qwprogs.dat')
    shutil.copy2(progs / 'menu.dat', game / 'menu.dat')
    shutil.copy2(csprogs, game / 'csprogs.dat')
    shutil.copy2(CONTENT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copy2(CONTENT / 'fteplug_hl2_x64.dll', base / 'fteplug_hl2_x64.dll')
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfP1384Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p1384-unused\n'
        'set sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
    subprocess.run([sys.executable, str(HERE / 'seed_csprogs.py'), str(game / 'csprogs.dat')],
                   check=True, capture_output=True)
    return base


ROW = re.compile(r'P1384 t (\S+) t0 (\S+) hold (\S+) wop (\S+) buf (\S+) pend (\S+) left (\S+) shold (\S+) '
                 r'up (\S+) cam (\S+) (\S+) (\S+) body (\S+) (\S+) (\S+) txt \[(.*?)\]')


def grade(seg):
    # Acting counters distinguish a disabled/non-reaching split from a pass.
    acts = re.findall(r'P1437 acts (\d+) holdzeros (\d+) opstales (\d+) bound (\d+)', seg)
    split = dict(split_arms=max((int(a[0]) for a in acts), default=0),
                 split_holdzeros=max((int(a[1]) for a in acts), default=0),
                 split_opstales=max((int(a[2]) for a in acts), default=0),
                 split_boundframes=max((int(a[3]) for a in acts), default=0))
    capsule = re.findall(r'P1437 capsule acts (\d+) reads (\d+)', seg)
    angles = re.findall(r'P1437 angle native ([^\r\n]+?) latch ([^\r\n]+?) pending (\d+) capsule ([^\r\n]+)', seg)
    errors = []
    for native, _, pending, packet in angles:
        fields = packet.split()
        if pending == '1' and len(fields) == 14 and fields[0] == 'L':
            got = [float(v) for v in native.split()]
            target = [float(fields[6]), float(fields[7]), 0.0]
            if len(got) == 3:
                errors.append(max(abs((a-b+180) % 360-180) for a, b in zip(got, target)))
    split.update(capsule_arms=max((int(a[0]) for a in capsule), default=0),
                 capsule_reads=max((int(a[1]) for a in capsule), default=0),
                 pending_angle_frames=len(errors), max_pending_angle_error=max(errors, default=0))
    rows = []
    for m in ROW.finditer(seg):
        g = m.groups()
        rows.append(dict(t=float(g[0]), t0=float(g[1]), hold=int(float(g[2])), wop=int(float(g[3])),
                         buf=int(float(g[4])), pend=int(float(g[5])), left=float(g[6]), shold=int(float(g[7])),
                         cam=tuple(float(x) for x in g[9:12]), body=tuple(float(x) for x in g[12:15]), txt=g[15]))
    held = [r for r in rows if r['hold']]
    if not held:
        # Down and up inside one frame: no rendered frame was held (lead-in 0 on a predicted load).
        return {'frames_held': 0, 'press_to_travel': None, 'press_to_release': 0.0 if 'run resumed' in seg else None,
                'eye_jumps_held': [], 'texts': [], 'first_countdown': None,
                'prederr': len(re.findall(r'prederr: seq ', seg)), **split}
    t0 = held[0]['t0']
    first = held[0]['t']
    travel = next((r for r in held if r['buf'] and not r['pend']), None)
    rel = next((r for r in rows if r['t'] > first and not r['hold']), None)
    jump, prev, jumps = 0.0, None, []
    for r in held:
        if prev is not None:
            d = sum((a - b) ** 2 for a, b in zip(r['cam'], prev)) ** 0.5
            jump = max(jump, d)
            if d > 30:                  # walking at 200 u/s moves the eye ~2 u a frame
                jumps.append((round(r['t'] - t0, 3), round(d)))
        prev = r['cam']
    gaps = [(round(b['t'] - t0, 3), round(b['t'] - a['t'], 3)) for a, b in zip(rows, rows[1:])
            if b['t'] - a['t'] > 0.03]
    texts = []
    for r in held:
        k = re.sub(r'\d+ ms', 'N ms', r['txt'])
        if not texts or texts[-1] != k:
            texts.append(k)
    return {'frames_held': len(held), 'press_to_first_frame': round(first - t0, 4),
            'press_to_travel': None if travel is None else round(travel['t'] - t0, 4),
            'press_to_release': None if rel is None else round(rel['t'] - t0, 4),
            'max_eye_jump_held': round(jump, 1), 'eye_jumps_held': jumps, 'first_countdown': next((r['txt'] for r in held if 'ms' in r['txt']), None),
            'texts': texts, 'frame_gaps': gaps, 'prederr': len(re.findall(r'prederr: seq ', seg)), **split}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--src', type=Path, required=True)
    ap.add_argument('--delays', default='0,150,300')
    ap.add_argument('--lead', default='1')
    ap.add_argument('--hold', action='store_true')
    ap.add_argument('--step', action='store_true', help='rounds that save twice, hold-load the second '
                    'and step back to the first (sl_prev) 0.4 s into the hold')
    ap.add_argument('--split-stats', type=int, choices=(0, 1, 2, 3, 4, 5, 6, 7), default=0,
                    help='ARM ONLY: 1=HOLD lag; 2=also stale op; 3=capsule lag; '
                         '4=old pending fences; 5=old trail transition; 6=mutable-cursor origin mutant; '
                         '7=cursor displacement with fixed origin. State emulation, NOT transport.')
    ap.add_argument('--turn-before-load', action='store_true',
                    help='ARM ONLY with split3/4: distinct native angle before saved setangle')
    ap.add_argument('--port', type=int, default=27621)
    ap.add_argument('--set', action='append', default=[], help='an extra client cvar line, e.g. "hud_trail 1"')
    ap.add_argument('--bigpic', type=int, default=0,
                    help='prepend this many synthetic rows to the saved trail.txt (a long picture)')
    a = ap.parse_args()
    a.out = a.out.resolve()
    R.owned(a.out)
    a.out.mkdir(parents=True, exist_ok=False)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', a.port))
    phys, commit = R.free_mb()
    print('free physical %d MB, commit %d MB' % (phys, commit), flush=True)
    if phys < 1500 or commit < 2200:
        raise SystemExit('not enough free memory for a server and a client')
    cs = build_probe(a.src, a.out, a.split_stats)
    report = {'qwprogs': sha(a.progs / 'qwprogs.dat'), 'csprogs_probe': sha(cs), 'src': str(a.src),
              'client': sha(CONTENT / 'ftesurf64.exe'), 'server': sha('C:/FTEQuake/fteqwsv64.exe'),
              'lead': a.lead, 'taps': {}}
    print('hashes', report, flush=True)
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
              'log_readable 1', 'developer 0', 'set cl_idlefps 0', 'set cl_maxfps 100', 'set run_resume 0',
              'set lobby_dir ""', 'set lobby_master ""', 'set cl_run_upload 0', 'set cl_board_url ""',
              'set sv_public 0', 'set milk_enable 0', 'set update_autocheck 0']
    R.take_lock('p1384lead (ftesurf-3a)')
    sv = cl = None
    try:
        svb = prepare(a.out, 'server', a.progs, cs)
        (svb / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 2', 'sv_maxclients 2', f'map {MAP}']) + '\n')
        sv = Peer(Path('C:/FTEQuake/fteqwsv64.exe'), svb, 'probe.cfg', True)
        sv.wait(r'Server spawned\.', timeout=120)
        sv.send('sv_cheats 1')
        clb = prepare(a.out, 'client', a.progs, cs)
        (clb / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            'name "P1384Arm"', f'connect 127.0.0.1:{a.port}']) + '\n')
        cl = Peer(CONTENT / 'ftesurf64.exe', clb, 'probe.cfg')
        cl.wait('FTESurf CSQC loaded', timeout=120)
        time.sleep(4)
        for line in ('menu_restart; ui_close', 'cl_prederror 4', f'cl_sl_leadin {a.lead}', 'cl_forwardspeed 200',
                     'rec_savelock 1', 'p1384_probe 0', f'p1437_split_stats {a.split_stats}', *a.set):
            cl.send(line)
            time.sleep(0.3)
        time.sleep(1)
        rounds = [(int(d), False) for d in a.delays.split(',')]
        if a.hold:
            rounds += [(int(d), True) for d in a.delays.split(',')]
        if a.step:
            rounds = [(int(d), 'step') for d in a.delays.split(',')]
        for d, hold in rounds:
            label = f'd{d}' + ('step' if hold == 'step' else 'hold' if hold else 'tap')
            cl.send(f'cl_delay_packets {d}')
            cl.send(f'setpos {O[0]} {O[1]} {O[2]} 0 55 0')
            time.sleep(2.0)
            cl.send('+forward')                     # out of the box: the run starts
            time.sleep(2.0)
            before = {p: p.stat().st_mtime for p in clb.glob('ftesurf/data/saves/**/trail.txt')}
            cl.send('sl_save')                      # on the run, moving
            time.sleep(1.0)
            if a.bigpic:
                new = [p for p in clb.glob('ftesurf/data/saves/**/trail.txt') if before.get(p) != p.stat().st_mtime]
                assert len(new) == 1, new
                lines = new[0].read_text(encoding='utf-8').splitlines()
                tok = lines[1].split()
                t0, x0 = float(tok[0]), float(tok[1])
                pad = []
                for k in range(a.bigpic, 0, -1):
                    tok[0], tok[1] = '%.6f' % (t0 - k * 0.015), '%.6f' % (x0 - k * 0.5)
                    pad.append(' '.join(tok))
                new[0].write_text('\n'.join(lines[:1] + pad + lines[1:]) + '\n', encoding='utf-8')
                report.setdefault('bigpic', []).append(len(pad) + len(lines) - 1)
            if hold == 'step':
                time.sleep(0.6)
                if a.turn_before_load:
                    cl.send('p1437_turn 1')  # row2 angle differs from the row1 stepped back to
                    time.sleep(0.15)
                cl.send('sl_save')                  # the second save, 0.6 s on: the cursor's
                time.sleep(0.4)
            cl.send('-forward')
            time.sleep(2.0)
            cl.send('p1384_probe 1')
            off = len(cl.text())
            cl.send(f'echo P1384 MARK {label}')
            if a.turn_before_load:
                assert a.split_stats >= 3
                cl.send('p1437_turn 1')
                time.sleep(0.15)
            if hold == 'step':
                cl.send('+sl_hold 50')
                time.sleep(0.4)
                cl.send('sl_prev')
                time.sleep(2.1)
                cl.send('-sl_hold 50')
            elif hold:
                cl.send('+sl_hold 50')
                time.sleep(2.5)
                cl.send('-sl_hold 50')
            else:
                cl.send('+sl_hold 50;-sl_hold 50')
            time.sleep(4.0)
            cl.send('p1384_probe 0')
            time.sleep(0.5)
            seg = cl.text()[off:]
            (a.out / f'{label}.log').write_text(seg, encoding='utf-8')
            report['taps'][label] = grade(seg)
            print(label, json.dumps(report['taps'][label]), flush=True)
        cl.send('cl_delay_packets 0')
    finally:
        for p in (cl, sv):
            if p is not None:
                p.stop()
        R.drop_lock()
    (a.out / 'report.json').write_text(json.dumps(report, indent=1))
    print('report', a.out / 'report.json')


if __name__ == '__main__':
    main()
