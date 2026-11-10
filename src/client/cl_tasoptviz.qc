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
// P1449: the route clicked in the Optimizer tab, as the server's notes report it (cl_tasoptui.qc TASAuto_Event): a
// post a point (mint a ramp to board, butter a bhop floor, aqua a point) and a thin line through them in order.
#define TOV_ROUTE 64
float tov_rn;
vector tov_rp[TOV_ROUTE];
float tov_rk[TOV_ROUTE];
vector tov_rnorm[TOV_ROUTE];   // each point's face (0 0 0 a point, 0 0 1 a bhop floor)

// P1449 route editor (Lex, 10 Nov): noclip round, aim at a route marker, drag it with the left button -- it stays on
// its own face's plane (on the face itself where the crosshair meets it), a bhop point on its floor, a point on
// whatever the crosshair hits; the right button removes it. Released, `tas route set` makes it the server's.
float rte_on;
var float rte_hover = -1, rte_drag = -1;
vector rte_pos;
vector rte_off;                 // the point less where the crosshair met its plane at the press: a click does not jump it
float rte_m1, rte_m2;           // a left/right press was this editor's: its release is too (review)
float rte_far;                  // the last DragPoint's plane meeting was out of reach: the point stays (review 2)
float tasu_open;                // the TAS tab is open: its clicks are its own (cl_tasui.qc)
vector(float k, vector eye, vector fwd) RouteEdit_DragPoint =
{
	local vector n, p, q;
	local float d, t;
	n = tov_rnorm[k]; p = tov_rp[k]; q = p;
	traceline(eye, eye + fwd * 8192, MOVE_NOMONSTERS, world);
	if (n == '0 0 0') { rte_far = (trace_fraction >= 1); return rte_far ? p : trace_endpos; }
	d = fwd * n;
	rte_far = TRUE;
	if (fabs(d) > 0.01)
	{
		t = ((p - eye) * n) / d;
		if (t > 0 && t < 8192) { q = eye + fwd * t; rte_far = FALSE; }    // on the plane, or not moved (review 2)
	}
	if (trace_fraction < 1 && trace_plane_normal * n > 0.95 && vlen(trace_endpos - q) < 96) q = trace_endpos;     // the face itself
	return q;
};
void() RouteEdit_Frame =
{
	local vector eye, fwd;
	local float i, d, best;
	if (!rte_on) { rte_hover = rte_drag = -1; return; }
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;
	if (rte_drag >= 0)
	{
		if (rte_drag >= tov_rn) { rte_drag = -1; return; }
		eye = RouteEdit_DragPoint(rte_drag, eye, fwd);
		if (!rte_far) rte_pos = eye + rte_off;
		return;
	}
	if (tasu_open) { rte_hover = -1; return; }       // the tab's cursor, not the crosshair, is aiming (review)
	rte_hover = -1; best = cos(3 * M_PI / 180);       // the post nearest the crosshair, within 3 degrees
	for (i = 0; i < tov_rn; i = i + 1)
		if (tov_rk[i])
		{
			d = normalize(tov_rp[i] + '0 0 48' - eye) * fwd;
			if (d > best) { best = d; rte_hover = i; }
		}
};
float(float evtype, float scanx, float chary, float devid) RouteEdit_InputEvent =
{
	local vector n;
	// its own presses' releases only, even after the editor closed or a drag was dropped (review 2)
	if (evtype == IE_KEYUP && scanx == K_MOUSE2 && rte_m2) { rte_m2 = FALSE; return TRUE; }
	if (evtype == IE_KEYUP && scanx == K_MOUSE1 && rte_m1 && rte_drag < 0) { rte_m1 = FALSE; return TRUE; }
	if (!rte_on) return FALSE;
	if (tasu_open && rte_drag < 0) return FALSE;      // the TAS tab's clicks are its own (review)
	if (evtype == IE_KEYDOWN && scanx == K_MOUSE1 && rte_hover >= 0)
	{
		rte_drag = rte_hover; rte_pos = tov_rp[rte_drag]; rte_m1 = TRUE;
		makevectors(getproperty(VF_ANGLES));
		rte_off = rte_pos - RouteEdit_DragPoint(rte_drag, getproperty(VF_ORIGIN), v_forward);   // grabbed where it is
		if (rte_far || tov_rnorm[rte_drag] == '0 0 0') rte_off = '0 0 0';     // a point follows the crosshair's hit itself (review 2)
		return TRUE;
	}
	if (evtype == IE_KEYUP && scanx == K_MOUSE1 && rte_drag >= 0)
	{
		n = tov_rnorm[rte_drag];
		localcmd(sprintf("tas route set %g %.1f %.1f %.1f ", rte_drag + 1, rte_pos_x, rte_pos_y, rte_pos_z));
		localcmd(sprintf("%.4f %.4f %.4f\n", n_x, n_y, n_z));
		tov_rp[rte_drag] = rte_pos;       // drawn there until the server's note says where it is
		rte_drag = -1; rte_m1 = FALSE;
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_MOUSE2 && rte_hover >= 0 && rte_drag < 0)     // not mid-drag (review)
	{
		localcmd(sprintf("tas route del %g\n", rte_hover + 1));
		rte_m2 = TRUE;
		return TRUE;
	}
	return FALSE;
};
void(vector scr) RouteEdit_DrawHint =
{
	local float tsz;
	local string s;
	if (!rte_on) return;
	tsz = bound(11, scr_y / 72, 20);
	s = (rte_drag >= 0) ? sprintf("Moving point %g: let go to place it", rte_drag + 1)
		: ((rte_hover >= 0) ? sprintf("Point %g: drag with the left button, right button removes it", rte_hover + 1)
		: "Route edit: aim at a marker (noclip to fly round); tas route edit or the tab ends it");
	sui_roundbox([scr_x * 0.5 - tsz * 17, scr_y * 0.62 - 6, 0], [tsz * 34, tsz + 12, 0], 6, SUI_THEME_PANEL, 0.8);
	sui_text([scr_x * 0.5 - tsz * 16.4, scr_y * 0.62, 0], [tsz, tsz], s, (rte_drag >= 0 || rte_hover >= 0) ? SUI_THEME_ACCENT : SUI_THEME_DIM, 1, 0);
};

void() TASOptViz_Draw =
{
	local float i, j, age, a, n;
	local vector col;
	if (!tov_shader)
	{
		shaderforname(TOV_SHADER, "{\ncull disable\n{\nmap $whiteimage\nblendfunc blend\nrgbgen vertex\nalphagen vertex\n}\n}\n");
		tov_shader = 1;
	}
	RouteEdit_Frame();
	for (i = 0; i < tov_rn; i = i + 1)
	{	// the route: shown whether or not the search lines are (kind 0: a slot this client never saw)
		if (!tov_rk[i]) continue;
		col = (tov_rk[i] == 1) ? SUI_THEME_GOOD : ((tov_rk[i] == 2) ? SUI_THEME_WARN : SUI_THEME_INFO);
		if (i == rte_hover || i == rte_drag) col = SUI_THEME_ACCENT;
		R_BeginPolygon(TOV_SHADER, 0);
		R_PolygonVertex((i == rte_drag) ? rte_pos : tov_rp[i], '0.5 0 0', col, 0.9);
		R_PolygonVertex(((i == rte_drag) ? rte_pos : tov_rp[i]) + '0 0 96', '0.5 0 0', col, 0.9);
		R_EndPolygonRibbon((i == rte_hover || i == rte_drag) ? 10 : 5, '0 1 0');
		if (i > 0)
		if (tov_rk[i - 1])
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
