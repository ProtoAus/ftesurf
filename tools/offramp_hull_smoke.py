#!/usr/bin/env python3
"""Private actual hull/posture installer. Never ship this server.

NEW clean isolated native worktree only. Compose buffer/origin/shape/hull before
any write; use the unchanged buffer four-arm runner, then offramp_hull.py.
"""
import argparse
from pathlib import Path

from offramp_contact_smoke import isolated
from offramp_shape_smoke import prepare as shape_prepare
from stitched_rewind_smoke import once

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ('offramp_hull_native.inc', 'offramp_hull_selftest.inc')


def prepare(engine):
    common = engine / 'engine/common'
    if any((common / n).exists() for n in TARGETS):
        raise RuntimeError('Refusing to overwrite existing private hull includes')
    prepared = shape_prepare(engine)
    buffer = common / 'offramp_buffer_native.inc'
    inc = prepared[buffer]
    inc = once(inc, '#define OFFRAMPBUF_CAP 32768',
               '#define OFFRAMPBUF_CAP 32768\n#include "offramp_hull_native.inc"')
    inc = once(inc, '\tunsigned int ordinal;', '\tstruct offramp_hull_s hull;\n\tunsigned int ordinal;')
    inc = once(inc, '\tstruct offramp_origin_s origin;',
               '\tstruct offramp_hull_s hull;\n\tstruct offramp_origin_s origin;')
    inc = once(inc, '\t\tOfframpShape_Begin();', '\t\tOfframpShape_Begin();\n\t\tOfframpHull_Begin();')
    inc = once(inc, '\tr->bump = bump;', '\tOfframpHull_Snapshot(&r->hull);\n\tr->bump = bump;')
    inc = once(inc, '\tr->rate = pms_frametime;', '\tOfframpHull_Snapshot(&r->hull);\n\tr->rate = pms_frametime;')
    inc = once(inc, '\t\t\tr->normal[0], r->normal[1], r->normal[2]);',
               '\t\t\tr->normal[0], r->normal[1], r->normal[2]);\n\t\tOfframpHull_Dump(false, r->ordinal, 0, &r->hull);')
    inc = once(inc, '\t\tOfframpShape_Dump(r->ordinal, r->tick, &r->origin);',
               '\t\tOfframpShape_Dump(r->ordinal, r->tick, &r->origin);\n\t\tOfframpHull_Dump(true, r->ordinal, r->tick, &r->hull);')
    inc = once(inc, '\tOfframpShape_End();',
               '\tOfframpShape_End();\n\tCon_Printf("OFFRAMPHULL_END %u %u\\n", offrampbuf_nt, offrampbuf_nc);')
    prepared[buffer] = inc
    prepared[common / 'pm_source.c'] += '\n#include "offramp_hull_selftest.inc"\n'
    for name in TARGETS:
        prepared[common / name] = (ROOT / 'tools' / name).read_text()
    return prepared


def instrument(engine):
    isolated(engine)
    prepared = prepare(engine)
    # All source/generated anchors and all include collisions precede writes.
    for p, text in prepared.items():
        p.write_text(text)
    print('Private actual hull/posture seams installed:', engine)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--instrument-native', type=Path, required=True)
    a = ap.parse_args()
    instrument(a.instrument_native)


if __name__ == '__main__':
    main()
