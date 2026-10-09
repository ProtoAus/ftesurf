#!/usr/bin/env python3
"""PRIVATE bounded native TryPlayerMove path installer/runner; NEVER ship."""
import argparse
import hashlib
import json
from pathlib import Path

from offramp_bevpm_smoke import prepare as prior_prepare, run
from offramp_contact_smoke import isolated
from stitched_rewind_smoke import once

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'offramp_tripath_native.inc'


def source_digest():
    return hashlib.sha256(b''.join((ROOT/'tools'/n).read_bytes() for n in
                                  (TARGET, 'offramp_tripath_smoke.py'))).hexdigest()


def prepare(engine, control=False):
    common = engine/'engine/common'
    if (common/TARGET).exists():
        raise RuntimeError('Refusing to overwrite private path include')
    prepared = prior_prepare(engine, control)
    if control:
        return prepared
    path = common/'pm_source.c'
    text = prepared[path]
    signature = ('static int PMSrc_TryPlayerMove (vec3_t firstdest, trace_t *firsttrace, '
                 'const struct offramp_origin_s *firstorigin)\n{')
    text = once(text, signature,
                f'#define OFFRAMP_TRIPATH_SOURCE_SHA256 "{source_digest()}"\n#include "{TARGET}"\n'+signature)
    first = text.index(signature)
    last = text.index('\n/*\n==================\nPMSrc_StayOnGround', first)
    body = text[first:last]
    body = once(body, '\tint\t\t\tbumpcount;', '\tint\t\t\tbumpcount;\n\tint pathcall, pathrow = -1;')
    body = once(body, '\tnumplanes = 0;\n\tVectorCopy (pmove.velocity, original_velocity);',
                '\tpathcall = OfframpPath_Call(pms_frametime, firstdest != NULL, pms_haveportals, fixramps);\n'
                '\tnumplanes = 0;\n\tVectorCopy (pmove.velocity, original_velocity);')
    body = once(body, '\t\tif (stuck_on_ramp && fixramps)\n\t\t{',
                '\t\tif (stuck_on_ramp && fixramps)\n\t\t{\n\t\t\tOfframpPath_Unsupported(pathcall);')
    body = once(body, '\t\tVectorMA (fixed_origin, time_left, pmove.velocity, end);',
                '\t\tVectorMA (fixed_origin, time_left, pmove.velocity, end);\n'
                '\t\tpathrow = OfframpPath_Attempt(pathcall, bumpcount, fixed_origin, end, time_left);')
    body = once(body, '\n\t\tif (tookportal)\n\t\t{',
                '\n\t\tOfframpPath_Result(pathrow, &pm, tookportal ? 3 :\n'
                '\t\t\t(firstdest && VectorCompare(end, firstdest) && !pms_haveportals) ? 1 :\n'
                '\t\t\t(stuck_on_ramp && has_valid_plane && fixramps) ? 2 : 0);\n'
                '\t\tif (tookportal)\n\t\t{\n\t\t\tOfframpPath_Unsupported(pathcall);')
    body = once(body, '\t\t\thas_valid_plane = false;\n\t\t\tstuck_on_ramp = true;\n\t\t\tcontinue;',
                '\t\t\thas_valid_plane = false;\n\t\t\tstuck_on_ramp = true;\n'
                '\t\t\tOfframpPath_Unsupported(pathcall);\n\t\t\tOfframpPath_Outcome(pathrow, 3, time_left);\n\t\t\tcontinue;')
    body = once(body, '\t\t\treturn 4;', '\t\t\tOfframpPath_Outcome(pathrow, 4, time_left);\n'
                '\t\t\tOfframpPath_Return(pathcall, 4, time_left, allFraction);\n\t\t\treturn 4;')
    body = once(body, '\t\t\t\ttrace_t stuck = PMSrc_TraceHull (pm.endpos, pm.endpos);',
                '\t\t\t\ttrace_t stuck = PMSrc_TraceHull (pm.endpos, pm.endpos);\n\t\t\t\tOfframpPath_Validation(pathrow, &stuck);')
    body = once(body, '\t\t\t\t\t\tstuck_on_ramp = true;\n\t\t\t\t\t\tcontinue;',
                '\t\t\t\t\t\tstuck_on_ramp = true;\n\t\t\t\t\t\tOfframpPath_Unsupported(pathcall);\n'
                '\t\t\t\t\t\tOfframpPath_Outcome(pathrow, 5, time_left);\n\t\t\t\t\t\tcontinue;')
    body = once(body, '\t\t\t\t\tVectorClear (pmove.velocity);\n\t\t\t\t\tbreak;\n\t\t\t\t}\n\t\t\t}',
                '\t\t\t\t\tVectorClear (pmove.velocity);\n\t\t\t\t\tOfframpPath_Outcome(pathrow, 6, time_left);\n\t\t\t\t\tbreak;\n\t\t\t\t}\n\t\t\t}')
    body = once(body, '\t\tif (pm.fraction == 1)\n\t\t\tbreak;',
                '\t\tif (pm.fraction == 1)\n\t\t{\n\t\t\tOfframpPath_Outcome(pathrow, 1, time_left);\n\t\t\tbreak;\n\t\t}')
    body = once(body, '\t\tif (numplanes >= PMSRC_MAX_CLIP_PLANES)\n\t\t{\t/* shouldn\'t happen */\n\t\t\tVectorClear (pmove.velocity);\n\t\t\tbreak;',
                '\t\tif (numplanes >= PMSRC_MAX_CLIP_PLANES)\n\t\t{\t/* shouldn\'t happen */\n\t\t\tVectorClear (pmove.velocity);\n\t\t\tOfframpPath_Outcome(pathrow, 7, time_left);\n\t\t\tbreak;')
    body = once(body, '\t\t\t\t\tVectorClear (pmove.velocity);\n\t\t\t\t\tbreak;',
                '\t\t\t\t\tVectorClear (pmove.velocity);\n\t\t\t\t\tOfframpPath_Outcome(pathrow, 8, time_left);\n\t\t\t\t\tbreak;')
    body = once(body, '\t\t\t\t\tpmove.velocity[1] = new_velocity[1];\n\t\t\t\t\tbreak;',
                '\t\t\t\t\tpmove.velocity[1] = new_velocity[1];\n\t\t\t\t\tOfframpPath_Outcome(pathrow, 9, time_left);\n\t\t\t\t\tbreak;')
    body = once(body, '\t\t\tif (d <= 0)\n\t\t\t{\n\t\t\t\tVectorClear (pmove.velocity);\n\t\t\t\tbreak;',
                '\t\t\tif (d <= 0)\n\t\t\t{\n\t\t\t\tVectorClear (pmove.velocity);\n\t\t\t\tOfframpPath_Outcome(pathrow, 10, time_left);\n\t\t\t\tbreak;')
    body = once(body, '\n\t}\n\n\tif (allFraction == 0)', '\n\t\tOfframpPath_Outcome(pathrow, 2, time_left);\n\t}\n\n\tif (allFraction == 0)')
    body = once(body, '\treturn blocked;', '\tOfframpPath_Return(pathcall, blocked, time_left, allFraction);\n\treturn blocked;')
    prepared[path] = text[:first]+body+text[last:]
    prepared[common/TARGET] = (ROOT/'tools'/TARGET).read_text()
    actor = common/'offramp_bevpm_native.inc'
    text = prepared[actor]
    text = once(text, '\t\tfor (i = 0; i < OFFRAMP_BEVPM_STEPS; i++)\n\t\t{\n\t\t\tpmove.cmd.msec = 15;',
                '\t\tOfframpPath_Begin(c, capture);\n\t\tfor (i = 0; i < OFFRAMP_BEVPM_STEPS; i++)\n\t\t{\n\t\t\tofframp_path_tick = i;\n\t\t\tpmove.cmd.msec = 15;')
    prepared[actor] = once(text, '\t\tPMSrc_OfframpEnd();', '\t\tPMSrc_OfframpEnd();\n\t\tOfframpPath_End();')
    return prepared


def instrument(engine, control=False):
    isolated(engine)
    prepared = prepare(engine, control)  # validate every seam before any write
    for path, text in prepared.items():
        path.write_text(text, newline='' if path.name in (TARGET, 'offramp_motion_native.inc') else None)
    print('Private native path installed:', 'fixture-only' if control else 'capture', engine)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--instrument-native', type=Path); ap.add_argument('--fixture-only', action='store_true')
    ap.add_argument('--server', type=Path); ap.add_argument('--control-server', type=Path)
    ap.add_argument('--output-dir', type=Path); ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--port', type=int, default=27617); ap.add_argument('--timeout', type=float, default=180)
    a = ap.parse_args()
    if a.instrument_native:
        instrument(a.instrument_native, a.fixture_only); return
    if not all((a.server, a.control_server, a.output_dir)) or a.fixture_only:
        ap.error('Need --server --control-server --output-dir')
    if a.output_dir.exists() or not (a.port == 27510 or 27520 <= a.port <= 27620) or a.timeout <= 0:
        ap.error('Need NEW output directory, positive timeout and lobby-range port')
    a.output_dir = a.output_dir.resolve()
    a.server = a.server.resolve(); a.control_server = a.control_server.resolve()
    a.content = a.content.resolve()
    a.output_dir.mkdir(parents=True)
    arms = {}
    for name, server, capture, oracle in (('nooracle', a.control_server, 0, 0), ('control', a.control_server, 0, 1),
                                        ('off', a.server, 0, 1), ('on', a.server, 1, 1), ('repeat', a.server, 1, 1)):
        arms[name] = run(server, a.output_dir, a.content, a.port, a.timeout, capture, oracle)
        arms[name]['tripath_source_sha256'] = source_digest()
        (a.output_dir/'arms.json').write_text(json.dumps(arms, indent=2)+'\n')
    print('Five native path arms completed; completion is NOT grading.')


if __name__ == '__main__':
    main()
