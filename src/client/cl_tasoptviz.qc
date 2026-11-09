/*
  P1449: tas optimize's candidates drawn where they fly (TAS_EV_OPTVIZ, sv_tasoptimize.qc
  SV_TASOptVizSend): the recent ones fading -- green reached the target, red met a trigger,
  blue missed -- the best so far bright yellow, the target a cross. `tas_viz 0` hides them.
*/
#define TOV_LINES 64
#define TOV_PTS   64       // sv_tasoptimize.qc samples up to 64 a path
vector tov_pt[TOV_LINES * TOV_PTS];
float tov_n[TOV_LINES];
float tov_t[TOV_LINES];
float tov_kind[TOV_LINES];
float tov_head;
vector tov_best[TOV_PTS];
float tov_bestn, tov_bestt, tov_final;
vector tov_tgt;
float tov_tgton, tov_tgtt;
var float autocvar_tas_viz = 1;

// The first point as floats, the rest as 4-unit shorts from it (SV_TASOptVizWrite).
vector(float i, vector p0) TASOptViz_Point =
{
	local vector p;
	if (i == 0) { p_x = readfloat(); p_y = readfloat(); p_z = readfloat(); return p; }
	p_x = readshort() * 4; p_y = readshort() * 4; p_z = readshort() * 4;
	return p0 + p;
};

void() TASOptViz_Event =
{
	local float kind, n, i, slot;
	local vector p, p0;
	kind = readbyte(); n = readbyte(); p0 = '0 0 0';
	if (cvar("developer") && kind != 1 && kind != 2 && kind != 3) print(sprintf("tas_viz: event %g, %g points\n", kind, n));
	if (kind == 0)
	{	// a new search: its start, and its target when one is set
		for (i = 0; i < TOV_LINES; i = i + 1) tov_n[i] = 0;
		tov_bestn = 0; tov_final = 0; tov_tgton = 0; tov_tgtt = cltime;
		for (i = 0; i < n; i = i + 1)
		{
			p = TASOptViz_Point(i, p0);
			if (i == 0) p0 = p;
			if (i == 1) { tov_tgt = p; tov_tgton = 1; }
		}
		return;
	}
	if (kind == 4 || kind == 5)
	{	// the best so far (5), or the one played (4)
		for (i = 0; i < n; i = i + 1)
		{
			p = TASOptViz_Point(i, p0);
			if (i == 0) p0 = p;
			if (i < TOV_PTS) tov_best[i] = p;
		}
		tov_bestn = min(n, TOV_PTS); tov_bestt = cltime; tov_final = (kind == 4);
		return;
	}
	slot = tov_head; tov_head = (tov_head + 1) % TOV_LINES;
	for (i = 0; i < n; i = i + 1)
	{
		p = TASOptViz_Point(i, p0);
		if (i == 0) p0 = p;
		if (i < TOV_PTS) tov_pt[slot * TOV_PTS + i] = p;
	}
	tov_n[slot] = min(n, TOV_PTS); tov_t[slot] = cltime; tov_kind[slot] = kind;
};

// Each line one camera-facing ribbon (R_EndPolygonRibbon, cl_ptrail.qc's call), not a polygon a segment: a
// strip per segment was ~2000 batches a frame, and a rig client stalled long enough to time out while
// drawing them (three of four demo runs; none of two with tas_viz 0).
#define TOV_SHADER "ftesurf/tasviz"
#define TOV_LIFT   '0 0 32'      // origins are at the feet: off the ramp, or the depth test hides the line in it
float tov_shader;

void(float base, float n, vector col, float alpha, float halfw) TASOptViz_Line =
{
	local float j;
	R_BeginPolygon(TOV_SHADER, 0);
	for (j = 0; j < n; j = j + 1) R_PolygonVertex(tov_pt[base + j] + TOV_LIFT, '0.5 0 0', col, alpha);
	R_EndPolygonRibbon(halfw, '0 1 0');
};

// In the depth-tested world pass beside Zone_Draw.
// P1449: the route clicked in the Optimizer tab (cl_tasoptui.qc keeps it as it sends `tas route add`): a post a
// point (mint a ramp to board, butter a bhop floor, aqua a point) and a thin line through them in order.
#define TOV_ROUTE 64
float tov_rn;
vector tov_rp[TOV_ROUTE];
float tov_rk[TOV_ROUTE];

void() TASOptViz_Draw =
{
	local float i, j, age, a, n;
	local vector col;
	if (!tov_shader)
	{
		shaderforname(TOV_SHADER, "{\ncull disable\n{\nmap $whiteimage\nblendfunc blend\nrgbgen vertex\nalphagen vertex\n}\n}\n");
		tov_shader = 1;
	}
	for (i = 0; i < tov_rn; i = i + 1)
	{	// the route: shown whether or not the search lines are
		col = (tov_rk[i] == 1) ? SUI_THEME_GOOD : ((tov_rk[i] == 2) ? SUI_THEME_WARN : SUI_THEME_INFO);
		R_BeginPolygon(TOV_SHADER, 0);
		R_PolygonVertex(tov_rp[i], '0.5 0 0', col, 0.9);
		R_PolygonVertex(tov_rp[i] + '0 0 96', '0.5 0 0', col, 0.9);
		R_EndPolygonRibbon(5, '0 1 0');
		if (i > 0)
		{
			R_BeginPolygon(TOV_SHADER, 0);
			R_PolygonVertex(tov_rp[i - 1] + '0 0 48', '0.5 0 0', '1 1 1', 0.45);
			R_PolygonVertex(tov_rp[i] + '0 0 48', '0.5 0 0', '1 1 1', 0.45);
			R_EndPolygonRibbon(2, '0 1 0');
		}
	}
	if (!autocvar_tas_viz) return;
	for (i = 0; i < TOV_LINES; i = i + 1)
	{
		n = tov_n[i];
		if (n < 2) continue;
		age = cltime - tov_t[i];
		if (age > 3) { tov_n[i] = 0; continue; }
		a = 0.6 * (1 - age / 3);
		col = (tov_kind[i] == 2) ? '0.3 1 0.4' : ((tov_kind[i] == 3) ? '1 0.3 0.3' : '0.5 0.7 1');
		TASOptViz_Line(i * TOV_PTS, n, col, a, 3);
	}
	if (tov_bestn >= 2 && (tov_final ? cltime - tov_bestt < 20 : cltime - tov_bestt < 60))
	{
		R_BeginPolygon(TOV_SHADER, 0);
		for (j = 0; j < tov_bestn; j = j + 1) R_PolygonVertex(tov_best[j] + TOV_LIFT, '0.5 0 0', tov_final ? '1 1 1' : '1 0.9 0.2', 0.95);
		R_EndPolygonRibbon(6, '0 1 0');
	}
	if (tov_tgton && cltime - tov_tgtt < 120)
		for (j = 0; j < 3; j = j + 1)
		{	// the target: three crossed bars
			R_BeginPolygon(TOV_SHADER, 0);
			R_PolygonVertex(tov_tgt - ((j == 0) ? '24 0 0' : ((j == 1) ? '0 24 0' : '0 0 24')), '0.5 0 0', '1 0.4 1', 0.9);
			R_PolygonVertex(tov_tgt + ((j == 0) ? '24 0 0' : ((j == 1) ? '0 24 0' : '0 0 24')), '0.5 0 0', '1 0.4 1', 0.9);
			R_EndPolygonRibbon(2, '0 1 0');
		}
};
