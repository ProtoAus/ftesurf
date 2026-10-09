#!/usr/bin/env python3
"""PRIVATE winning native triangle geometry installer. NEVER ship the server.

Compose the unchanged motion/buffer/origin/brush/hull plans and this value-copy
layer from one NEW clean native tree. Use unchanged offramp_motion_smoke.py for
five runtime arms, then offramp_tricopy.py; no new mover actor is asserted.
"""
import argparse
import hashlib
from pathlib import Path

from offramp_contact_smoke import isolated
from offramp_motion_smoke import prepare as motion_prepare
from stitched_rewind_smoke import once

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ('offramp_tricopy_types.h', 'offramp_tricopy_native.inc', 'offramp_tricopy_selftest.inc')


def prepare(engine):
    common = engine/'engine/common'
    if any((common/name).exists() for name in TARGETS):
        raise RuntimeError('Refusing to overwrite private triangle-copy includes')
    # These expressions define the claimed native slab. Refuse source drift,
    # rather than printing a disconnected assumed primitive thickness.
    source = (common/'com_bih.c').read_text()
    if source.count('planes[1].dist = -planes[0].dist + 4;') != 2:
        raise RuntimeError('Native triangle clipping/test back-slab contract changed')
    prepared = motion_prepare(engine)
    header = common/'offramp_origin_native.h'
    inc = prepared[header]
    inc = once(inc, '#include "offramp_shape_types.h"',
               '#include "offramp_shape_types.h"\n#include "offramp_tricopy_types.h"')
    inc = once(inc, '\tstruct offramp_shape_s shape;',
               '\tstruct offramp_shape_s shape;\n\tstruct offramp_tricopy_s triangle;')
    prepared[header] = inc
    bih = common/'com_bih.c'
    inc = prepared[bih]
    inc = once(inc, '#endif\n\t}\n}\n\nstatic const q2mapsurface_t',
               '#endif\n\t\tOfframpTriCopy_Snapshot(&tr->origin, kind == 2 ? &node->data : NULL,\n'
               '\t\t\tkind == 2 ? bih_probe_plane : 0, tr->shape != shape_ispoint);\n\t}\n}\n\nstatic const q2mapsurface_t')
    # Template identity covers the actual native copy/control code and installer;
    # it is independent of the unchanged motion fixture digest.
    stamp = hashlib.sha256(b''.join((ROOT/'tools'/n).read_bytes() for n in
                           ('offramp_tricopy_types.inc', *TARGETS[1:], 'offramp_tricopy_smoke.py'))).hexdigest()
    inc += f'\n#define OFFRAMP_TRICOPY_SOURCE_SHA256 "{stamp}"\n'
    inc += '#include "offramp_tricopy_native.inc"\n#include "offramp_tricopy_selftest.inc"\n'
    prepared[bih] = inc
    setup = common/'offramp_origin_selftest.inc'
    prepared[setup] = once(prepared[setup], '\tOfframpShape_Selftest(&world, &brush[0]);',
                          '\tOfframpShape_Selftest(&world, &brush[0]);\n\tOfframpTriCopy_Selftest(&world);')
    buffer = common/'offramp_buffer_native.inc'
    inc = prepared[buffer]
    inc = once(inc, '\t\tOfframpHull_Begin();', '\t\tOfframpHull_Begin();\n\t\tOfframpTriCopy_Begin();')
    inc = once(inc, '\t\tOfframpShape_Dump(r->ordinal, r->tick, &r->origin);',
               '\t\tOfframpShape_Dump(r->ordinal, r->tick, &r->origin);\n\t\tOfframpTriCopy_Dump(r->ordinal, r->tick, &r->origin);')
    inc = once(inc, '\tOfframpShape_End();', '\tOfframpShape_End();\n\tOfframpTriCopy_End();')
    prepared[buffer] = inc
    for name in TARGETS:
        template = name.replace('_types.h', '_types.inc')
        prepared[common/name] = (ROOT/'tools'/template).read_text()
    return prepared


def instrument(engine):
    isolated(engine)
    prepared = prepare(engine)
    for path, text in prepared.items():
        path.write_text(text, newline='' if path.name == 'offramp_motion_native.inc' else None)
    print('Private value-copied winning triangle seams installed:', engine)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--instrument-native', type=Path, required=True)
    a = ap.parse_args()
    instrument(a.instrument_native)


if __name__ == '__main__':
    main()
