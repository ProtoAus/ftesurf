#!/usr/bin/env python3
"""Private return-bound BIH witness installer; no physical-exit acceptance.

Use a NEW isolated clean native worktree. Includes the buffer plan atomically;
never layer this installer onto an already instrumented tree. Run the existing
four-arm buffer smoke, then grade its arms with offramp_origin.py.
"""
import argparse
from pathlib import Path

from offramp_buffer_smoke import seams as buffer_seams
from offramp_contact_smoke import isolated
from stitched_rewind_smoke import once

ROOT = Path(__file__).resolve().parent.parent
HEADER = '#include "offramp_origin_native.h"'


def plan(engine):
    common = engine / 'engine/common'
    bih, pm, src = [common / n for n in ('com_bih.c', 'pmovetst.c', 'pm_source.c')]
    edits = buffer_seams(engine)
    # Extend the NEW text at the existing buffer contact seam, not a second
    # overlapping replacement against source that has already changed.
    edits = [(p, old, new.replace('fixramps);\n\t\t\t\tpmove.rampcontact',
                                  'fixramps, &pmorigin, originroute);\n\t\t\t\tpmove.rampcontact'))
             for p, old, new in edits]
    edits += [
        (bih, '#include "com_bih.h"', '#include "com_bih.h"\n' + HEADER + '''
qboolean offramp_origin_active;
struct offramp_origin_s offramp_origin_native, offramp_origin_pm;
const trace_t *offramp_origin_out;
'''),
        (bih, 'struct bihtrace_s\n{', 'struct bihtrace_s\n{\n\tstruct offramp_origin_s origin;\n\tmodel_t *origin_model;'),
        (bih, 'static const q2mapsurface_t\tnullsurface;', '''static void OfframpOrigin_Leaf(struct bihtrace_s *tr, const struct bihnode_s *node, int kind)
{
	if (offramp_origin_active)
	{
		tr->origin.kind = kind;
		tr->origin.leaf = tr->origin.rootleaf = node - (const struct bihnode_s *)tr->origin_model->cnodes;
		tr->origin.depth = 0;
		tr->origin.contents = node->data.contents;
		tr->origin.model = tr->origin_model;
	}
}

static const q2mapsurface_t\tnullsurface;'''),
        (bih, '\t\t\t\tBIH_ClipBoxToBrush (tr, b);', '''			{
				unsigned int previous = bih_probe_seq;
				BIH_ClipBoxToBrush (tr, b);
				if (bih_probe_seq != previous)
					OfframpOrigin_Leaf(tr, node, 1);
			}'''),
        (bih, '\t\t\t\tBIH_ClipBoxToPatch (tr, b);', '''			{
				unsigned int previous = bih_probe_seq;
				BIH_ClipBoxToPatch (tr, b);
				if (bih_probe_seq != previous)
					OfframpOrigin_Leaf(tr, node, 3);
			}'''),
        (bih, '\t\t\tBIH_ClipToTriangle(tr, &node->data);', '''		{
			unsigned int previous = bih_probe_seq;
			BIH_ClipToTriangle(tr, &node->data);
			if (bih_probe_seq != previous)
				OfframpOrigin_Leaf(tr, node, 2);
		}'''),
        (bih, '\t\t\tprobeseq = bih_probe_seq;', '\t\t\tprobeseq = bih_probe_seq;\n\t\t\tofframp_origin_out = NULL;'),
        (bih, '\t\t\tsubmod->funcs.NativeTrace(submod, 0, NULLFRAMESTATE, node->data.mesh.tr->axis, start_l, end_l, tr->size.min, tr->size.max, tr->shape==shape_iscapsule, tr->hitcontents, &sub);\n\n\t\t\tif (sub.truefraction < tr->trace.truefraction)\n\t\t\t{\n\t\t\t\ttr->trace.truefraction = sub.truefraction;', '''			submod->funcs.NativeTrace(submod, 0, NULLFRAMESTATE, node->data.mesh.tr->axis, start_l, end_l, tr->size.min, tr->size.max, tr->shape==shape_iscapsule, tr->hitcontents, &sub);

			if (sub.truefraction < tr->trace.truefraction)
			{
				if (offramp_origin_active)
				{
					tr->origin = OfframpOrigin_Read(&sub);
					if (tr->origin.kind)
					{
						tr->origin.depth++;
						tr->origin.rootleaf = node - (const struct bihnode_s *)tr->origin_model->cnodes;
					}
				}
				tr->trace.truefraction = sub.truefraction;'''),
        (bih, '\tstruct bihtrace_s tr;\n\n\tif (axis)', '\tstruct bihtrace_s tr;\n\n\ttr.origin = OfframpOrigin_Unknown();\n\ttr.origin_model = model;\n\tif (axis)'),
        (bih, '\t\tif (hmt.fraction < out_trace->fraction)\n\t\t\t*out_trace = hmt;', '''		if (hmt.fraction < out_trace->fraction)
		{
			*out_trace = hmt;
			tr.origin = OfframpOrigin_Unknown();
		}'''),
        (bih, '\treturn out_trace->fraction != 1;', '''	if (out_trace->fraction == 1 || out_trace->startsolid || out_trace->allsolid)
		tr.origin = OfframpOrigin_Unknown();
	OfframpOrigin_Publish(out_trace, tr.origin);
	return out_trace->fraction != 1;'''),
        (pm, '#include "quakedef.h"', '#include "quakedef.h"\n' + HEADER),
        (pm, '\tvec3_t\t\taxis[3];\n\n\t//nettest Patch 57', '\tvec3_t\t\taxis[3];\n\n\tofframp_origin_out = NULL;\n\t//nettest Patch 57'),
        (pm, '\ttrace_t\t\ttrace, total;', '\ttrace_t\t\ttrace, total;\n\tstruct offramp_origin_s totalorigin = OfframpOrigin_Unknown();\n\tqboolean originportal = false;'),
        (pm, '\t\tif (pe->isportal)\n\t\t{\n\t\t\t/* FTESurf Patch 203:', '\t\tif (pe->isportal)\n\t\t{\n\t\t\toriginportal = true;\n\t\t\t/* FTESurf Patch 203:'),
        (pm, '\t\t\t\t\tif (j != i && pe->isportal)\n\t\t\t\t\t\tPM_PortalCSG(pe, j, pmove.player_mins, pmove.player_maxs, start, end, &trace);', '''					if (j != i && pe->isportal)
					{
						originportal = true;
						PM_PortalCSG(pe, j, pmove.player_mins, pmove.player_maxs, start, end, &trace);
					}'''),
        (pm, '\t\t\ttotal = trace;\n\t\t\ttotal.entnum = i;', '\t\t\ttotal = trace;\n\t\t\ttotal.entnum = i;\n\t\t\ttotalorigin = OfframpOrigin_Read(&trace);'),
        (pm, '\treturn total;\n}', '''	if (total.fraction == 1 || total.startsolid || total.allsolid || originportal)
		totalorigin = OfframpOrigin_Unknown();
	offramp_origin_pm = totalorigin;
	return total;
}'''),
        (src, 'static int PMSrc_TryPlayerMove (vec3_t firstdest, trace_t *firsttrace)', 'static int PMSrc_TryPlayerMove (vec3_t firstdest, trace_t *firsttrace, const struct offramp_origin_s *firstorigin)'),
        (src, '\tqboolean\tstuck_on_ramp = false;', '\tstruct offramp_origin_s pmorigin;\n\tint originroute;\n\tqboolean\tstuck_on_ramp = false;'),
        (src, '\t\tif (firstdest && VectorCompare (end, firstdest) && !pms_haveportals)\n\t\t\tpm = *firsttrace;', '''		originroute = 0;
		if (firstdest && VectorCompare (end, firstdest) && !pms_haveportals)
		{
			pm = *firsttrace;
			pmorigin = firstorigin ? *firstorigin : OfframpOrigin_Unknown();
			originroute = 1;
		}'''),
        (src, '\t\t\tpm = PMSrc_TraceHull (fixed_origin, end);\n\t\t\tVectorCopy (valid_plane, pm.plane.normal);\n\t\t}\n\t\telse\n\t\t\tpm = PM_PlayerTracePortals (pmove.origin, end, MASK_PLAYERSOLID, &tookportal);', '''			pm = PMSrc_TraceHull (fixed_origin, end);
			pmorigin = offramp_origin_pm;
			originroute = 2; /* collider witness != synthesized accepted normal */
			VectorCopy (valid_plane, pm.plane.normal);
		}
		else
		{
			pm = PM_PlayerTracePortals (pmove.origin, end, MASK_PLAYERSOLID, &tookportal);
			pmorigin = offramp_origin_pm;
			if (pms_haveportals || tookportal)
			{
				pmorigin = OfframpOrigin_Unknown();
				originroute = 3;
			}
		}'''),
        (src, '\tfloat flDownDist, flUpDist;', '\tfloat flDownDist, flUpDist;\n\tstruct offramp_origin_s firstorigin = offramp_origin_pm;'),
        (src, '\tPMSrc_TryPlayerMove (vecEndPos, trace);', '\tPMSrc_TryPlayerMove (vecEndPos, trace, &firstorigin);'),
    ]
    # Every uncached call has identical text: bind each occurrence using the
    # original full line and ordinal spans, not repeated incremental edits.
    calls = [('PMSrc_TryPlayerMove (NULL, NULL);', 4),
             ('PMSrc_TryPlayerMove(NULL, NULL);', 3)]
    text = src.read_text()
    for token, count in calls:
        if text.count(token) != count:
            raise RuntimeError(f'Expected {count} uncached calls: {token}')
    return edits, src, calls


def compose(edits):
    originals = {p: p.read_text() for p, _, _ in edits}
    spans = {p: [] for p in originals}
    for p, old, new in edits:
        text = originals[p]
        if text.count(old) != 1:
            raise RuntimeError(f'Expected one seam: {p}: {old[:75]!r}')
        start = text.index(old)
        spans[p].append((start, start + len(old), new))
    result = {}
    for p, changes in spans.items():
        changes.sort()
        if any(a[1] > b[0] for a, b in zip(changes, changes[1:])):
            raise RuntimeError(f'Overlapping source seams: {p}')
        text = originals[p]
        for start, end, new in reversed(changes):
            text = text[:start] + new + text[end:]
        result[p] = text
    return result


def instrument(engine):
    isolated(engine)
    edits, src, calls = plan(engine)
    prepared = compose(edits)
    for old, _ in calls:
        prepared[src] = prepared[src].replace(old, old.replace('NULL, NULL', 'NULL, NULL, NULL'))
    common = engine / 'engine/common'
    targets = [common / n for n in ('offramp_buffer_native.inc', 'offramp_origin_native.h',
                                    'offramp_origin_selftest.inc')]
    if any(p.exists() for p in targets):
        raise RuntimeError('Refusing to overwrite existing diagnostic includes')
    inc = (ROOT / 'tools/offramp_buffer_native.inc').read_text()
    inc = once(inc, '#define OFFRAMPBUF_CAP', HEADER + '\n#define OFFRAMPBUF_CAP')
    inc = once(inc, '\tunsigned int ordinal, tick;', '\tstruct offramp_origin_s origin;\n\tint route;\n\tunsigned int ordinal, tick;')
    inc = once(inc, '\tif (offrampbuf_active)\n\t{', '\tofframp_origin_active = offrampbuf_active;\n\tif (offrampbuf_active)\n\t{\n\t\tOfframpOrigin_Selftest();')
    inc = once(inc, 'static void PMSrc_OfframpContact (trace_t *trace, int bump, qboolean recovered)', 'static void PMSrc_OfframpContact (trace_t *trace, int bump, qboolean recovered, const struct offramp_origin_s *origin, int route)')
    inc = once(inc, '\tr->tick = offrampbuf_nt;', '\tr->tick = offrampbuf_nt;\n\tr->origin = *origin;\n\tr->route = route;')
    inc = once(inc, '\tofframpbuf_active = false;', '\tofframpbuf_active = false;\n\tofframp_origin_active = false;')
    inc = once(inc, '\t\t\tr->maxs[0], r->maxs[1], r->maxs[2], r->recovered, r->startsolid, r->allsolid);', '''			r->maxs[0], r->maxs[1], r->maxs[2], r->recovered, r->startsolid, r->allsolid);
		Con_Printf("OFFRAMPORIGIN_CONTACT %u %u %i %i %i %i %i %u %i %s\\n",
			r->ordinal, r->tick, r->route, r->origin.kind, r->origin.leaf,
			r->origin.rootleaf, r->origin.depth, r->origin.contents, r->entnum,
			r->origin.model ? r->origin.model->name : "-");''')
    # All reads/anchors/include collision checks precede all writes.
    prepared[targets[0]] = inc
    prepared[targets[1]] = (ROOT / 'tools/offramp_origin_native.inc').read_text()
    prepared[targets[2]] = (ROOT / 'tools/offramp_origin_selftest.inc').read_text()
    prepared[common / 'com_bih.c'] += '\n#include "offramp_origin_selftest.inc"\n'
    for p, text in prepared.items():
        p.write_text(text)
    print('Private return-bound origin seams installed:', engine)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--instrument-native', type=Path, required=True)
    a = ap.parse_args()
    instrument(a.instrument_native)


if __name__ == '__main__':
    main()
