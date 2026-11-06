// P1344: derived mover annotation, never an input, restore field or proof.
// Native schema1: kind0 no ramp,1 committed world ramp,2 nonworld,3 unsupported.
.vector run_tas_contactinfo;
.vector run_tas_contactplane;
.vector run_tas_contactpoint;

void(entity e, float tick, float kind, vector normal, float distance, vector point) SV_TASSolveObserve;
// Live diagnostic only. Revision-bound full-line proposals are separate.
.float tasc_ready, tasc_serial, tasc_gen, tasc_native, tasc_tick, tasc_done;
.float tasc_samples, tasc_gaps, tasc_ramps, tasc_frozen;
.float tasc_ramp_tick, tasc_ramp_native, tasc_ramp_dist;
.vector tasc_ramp_normal, tasc_ramp_point;
#include "sv_tascontactspans.qc"
#include "sv_tascontactspage.qc"

void(entity e) SV_TASContactsLiveBegin =
{
	e.tasc_ready = TRUE;
	e.tasc_serial = e.rec_rec_serial;
	e.tasc_gen = e.rec_rec_gen;
	e.tasc_native = e.run_movetick;
	e.tasc_tick = SV_TimerTicks(e);
	e.tasc_done = e.run_tas_done;
	e.tasc_samples = e.tasc_gaps = e.tasc_ramps = e.tasc_frozen = 0;
	e.tasc_ramp_tick = e.tasc_ramp_native = e.tasc_ramp_dist = 0;
	e.tasc_ramp_normal = e.tasc_ramp_point = '0 0 0';
	SV_TASContactSpansBegin(e);
};

// PreThink sees the previous complete command; PostThink catches packet-final.
// Never tokenize the recorder here: command dispatch owns its argv transaction.
void(entity e) SV_TASContactsObserve =
{
	local float tick, native, delta, logical;
	local vector info;

	if (Lobby_Active()) return;
	if (e.run_t_state != TS_RUNNING || !e.run_t_clock || e.run_t_starttick < 0) return;
	if (e.rec_rec_serial <= 0 || e.rec_rec_buf <= 0) return;
	info = e.run_tas_contactinfo;
	if (info_x != 1) return;
	if (fabs(e.run_movetickrate - 0.01) > 0.0001)
		if (fabs(e.run_movetickrate - 0.015) > 0.0001) return;
	if (!e.tasc_ready || e.tasc_serial != e.rec_rec_serial || e.tasc_gen != e.rec_rec_gen)
	{
		SV_TASContactsLiveBegin(e);
		return;
	}
	native = e.run_movetick;
	delta = native - e.tasc_native;
	// A hold consumes native bookkeeping, not an input-line contact sample.
	if (e.run_tas_paused && e.run_tas_done == e.tasc_done && info_y == 3)
	{
		e.tasc_native = native;
		e.tasc_done = e.run_tas_done;
		return;
	}
	if (delta <= 0) return;
	tick = SV_TimerTicks(e);
	logical = tick - e.tasc_tick;
	e.tasc_native = native;
	e.tasc_done = e.run_tas_done;
	if (logical < 0)
	{
		// Navigation isn't an input edit: retain the diagnostic, don't relabel it.
		e.tasc_frozen = TRUE;
		return;
	}
	if (!logical || e.tasc_frozen) return;
	e.tasc_tick = tick;
	if (delta != 1 || logical != 1 || info_y < 0 || info_y > 3 || info_y != floor(info_y))
	{
		e.tasc_gaps = e.tasc_gaps + max(1, max(delta, logical));
		SV_TASContactSpan(e,tick-logical,tick,3,'0 0 0',0,'0 0 0');
		SV_TASSolveObserve(e,tick,3,'0 0 0',0,'0 0 0');
		return;
	}
	e.tasc_samples = min(TASP_MAX, e.tasc_samples + 1);
	SV_TASContactSpan(e,tick-1,tick,info_y,e.run_tas_contactplane,info_z,e.run_tas_contactpoint);
	SV_TASSolveObserve(e,tick,info_y,e.run_tas_contactplane,info_z,e.run_tas_contactpoint);
	if (info_y >= 2)
	{
		e.tasc_gaps = e.tasc_gaps + 1;
		return;
	}
	if (info_y != 1) return;
	e.tasc_ramps = min(TASP_MAX, e.tasc_ramps + 1);
	e.tasc_ramp_tick = tick;
	e.tasc_ramp_native = native;
	e.tasc_ramp_dist = info_z;
	e.tasc_ramp_normal = e.run_tas_contactplane;
	e.tasc_ramp_point = e.run_tas_contactpoint;
};

void(entity e, float argc) SV_TASContactsCommand =
{
	local vector info, plane, point;
	local string normal, lineage;
	if (argc == 8)
		if (!strcmp(argv(2),"page")) { SV_TASContactsPage(e,argc); return; }
	if (argc == 3)
		if (!strcmp(argv(2),"spans")) { SV_TASContactSpansStatus(e); return; }
	if (argc != 2)
	{
		if (argc != 3) { sprint(e, PRINT_HIGH, "tas contacts: usage: tas contacts [status]\n"); return; }
		if (strcmp(argv(2), "status")) { sprint(e, PRINT_HIGH, "tas contacts: usage: tas contacts [status]\n"); return; }
	}
	info = e.run_tas_contactinfo;
	plane = e.run_tas_contactplane;
	point = e.run_tas_contactpoint;
	if (info_x != 1)
	{
		sprint(e, PRINT_HIGH, "tas contacts: native contact schema unavailable; no proposals inferred\n");
		return;
	}
	normal = sprintf("%.9g,%.9g,%.9g",plane_x,plane_y,plane_z);
	sprint(e, PRINT_HIGH, sprintf("tas contacts: schema%.0f kind%.0f plane%.9g normal%s native%.0f tick%.0f\n",
		info_x,info_y,info_z,normal,e.run_movetick,SV_TimerTicks(e)));
	sprint(e, PRINT_HIGH, sprintf("tas contacts: actual collision point %.9g,%.9g,%.9g\n", point_x, point_y, point_z));
	lineage = sprintf("serial%.0f gen%.0f frozen%.0f",e.tasc_serial,e.tasc_gen,e.tasc_frozen);
	sprint(e, PRINT_HIGH, sprintf("tas contacts live: ready%.0f sampled%.0f rampTicks%.0f gaps%.0f lastTick%.0f %s\n",
		e.tasc_ready,e.tasc_samples,e.tasc_ramps,e.tasc_gaps,e.tasc_tick,lineage));
	if (!e.tasc_ramps) return;
	plane = e.tasc_ramp_normal;
	point = e.tasc_ramp_point;
	sprint(e, PRINT_HIGH, sprintf("tas contacts last ramp: tick%.0f native%.0f plane%.9g normal%.9g,%.9g,%.9g\n",
		e.tasc_ramp_tick, e.tasc_ramp_native, e.tasc_ramp_dist, plane_x, plane_y, plane_z));
	sprint(e, PRINT_HIGH, sprintf("tas contacts last point: %.9g,%.9g,%.9g; diagnostic, not a complete proposal cache\n", point_x, point_y, point_z));
};
