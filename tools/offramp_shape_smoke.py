#!/usr/bin/env python3
"""Private whole winning-brush snapshot installer. Never ship this server.

NEW clean isolated engine worktree only; composes buffer+origin+shape in memory.
Use the unchanged buffer four-arm runner, then offramp_shape.py to grade.
"""
import argparse
from pathlib import Path

from offramp_contact_smoke import isolated
from offramp_origin_smoke import prepare as origin_prepare
from stitched_rewind_smoke import once

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ('offramp_shape_types.h', 'offramp_shape_native.inc', 'offramp_shape_selftest.inc')


def prepare(engine):
    common = engine / 'engine/common'
    if any((common / n).exists() for n in TARGETS):
        raise RuntimeError('Refusing to overwrite existing private shape includes')
    prepared = origin_prepare(engine)
    header = common / 'offramp_origin_native.h'
    prepared[header] = once(prepared[header], 'struct offramp_origin_s\n{',
                            '#include "offramp_shape_types.h"\nstruct offramp_origin_s\n{')
    prepared[header] = once(prepared[header], '\tmodel_t *model;', '''	model_t *model;
	struct offramp_shape_s shape;
	vec3_t instance_origin, instance_angles;
	float instance_scale;
	int capsule, native_bih;''')
    bih = common / 'com_bih.c'
    prepared[bih] = once(prepared[bih], '\t\ttr->origin.model = tr->origin_model;', '''		tr->origin.model = tr->origin_model;
#if defined(Q2BSPS) || defined(Q3BSPS)
		OfframpShape_Snapshot(&tr->origin, kind == 1 ? node->data.brush : NULL);
#else
		OfframpShape_Snapshot(&tr->origin, NULL);
#endif''')
    prepared[bih] = once(prepared[bih], '\tOfframpOrigin_Publish(out_trace, tr.origin);', '''	/* A wrapper's inner BIH stamp is NOT ownership of its returned trace. */
	tr.origin.native_bih = tr.origin.kind && model->funcs.NativeTrace == BIH_Trace;
	OfframpOrigin_Publish(out_trace, tr.origin);''')
    prepared[bih] += '#include "offramp_shape_native.inc"\n#include "offramp_shape_selftest.inc"\n'
    pm = common / 'pmovetst.c'
    prepared[pm] = once(prepared[pm], '\t\t\ttotalorigin = OfframpOrigin_Read(&trace);', '''			totalorigin = OfframpOrigin_Read(&trace);
			VectorCopy(pe->origin, totalorigin.instance_origin);
			VectorCopy(pe->angles, totalorigin.instance_angles);
			totalorigin.instance_scale = pe->scale;
			totalorigin.capsule = pmove.capsule;''')
    selftest = common / 'offramp_origin_selftest.inc'
    prepared[selftest] = once(prepared[selftest], '\tnodes[2].data.brush = &brush[0];',
                              '\tOfframpShape_Selftest(&world, &brush[0]);\n\tnodes[2].data.brush = &brush[0];')
    buffer = common / 'offramp_buffer_native.inc'
    prepared[buffer] = once(prepared[buffer], '\t\tOfframpOrigin_Selftest();',
                            '\t\tOfframpOrigin_Selftest();\n\t\tOfframpShape_Begin();')
    prepared[buffer] = once(prepared[buffer], '\t\t\tr->origin.model ? r->origin.model->name : "-");',
                            '\t\t\tr->origin.model ? r->origin.model->name : "-");\n\t\tOfframpShape_Dump(r->ordinal, r->tick, &r->origin);')
    prepared[buffer] = once(prepared[buffer], '\tCon_Printf("OFFRAMPBUF_END', '\tOfframpShape_End();\n\tCon_Printf("OFFRAMPBUF_END')
    for target, fixture in zip(TARGETS, ('offramp_shape_types.inc', *TARGETS[1:])):
        prepared[common / target] = (ROOT / 'tools' / fixture).read_text()
    return prepared


def instrument(engine):
    isolated(engine)
    prepared = prepare(engine)
    # Every original/generated anchor/collision check precedes EVERY write.
    for p, text in prepared.items():
        p.write_text(text)
    print('Private whole winning-brush snapshot seams installed:', engine)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--instrument-native', type=Path, required=True)
    a = ap.parse_args()
    instrument(a.instrument_native)


if __name__ == '__main__':
    main()
