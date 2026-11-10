/*
  P1449: tas optimize's candidates drawn where they fly (TAS_EV_OPTVIZ, sv_tasoptimize.qc
  SV_TASOptVizSend): the recent ones fading -- green reached the target, red met a trigger,
  blue missed -- the best so far bright yellow, the target a cross. `tas_viz 0` hides them.
  `tas_viz_style 1` (default) draws them as the demo line does (cl_lines.qc's anti-aliased strip, a constant pixel
  width, over the world); 0 the depth-tested world ribbons, whose width is in units (Lex: low quality, odd widths).
  tas_viz_lines (shown at once, 16..2048), tas_viz_fade (seconds), the server's tas_viz_rate (sent a second), widths from
  gl_2dline_width, tas_viz_cam 1 an overhead camera on the stretch being searched (Lex, 10 Nov: for a video).
*/
#define TOV_LINES 2048     // the most tas_viz_lines keeps
#define TOV_PTS   128      // sv_tasoptimize.qc samples up to TOPT_VIZN (128) a path
vector *tov_pt;            // TOV_LINES x TOV_PTS, allocated on the first line
float tov_n[TOV_LINES];
float tov_t[TOV_LINES];
float tov_kind[TOV_LINES];
float tov_head;
var float autocvar_tas_viz_lines = 64;
var float autocvar_tas_viz_fade = 3;
var float autocvar_tas_viz_cam = 0;
vector tov_start;
vector tov_camo, tov_cama;  // tas_viz_cam's view this frame
float tov_camf;             // ...the frame it was set (cltime)
vector tov_best[TOV_PTS];
float tov_bestn, tov_bestt, tov_final;
vector tov_tgt;
float tov_tgton, tov_tgtt;
var float autocvar_tas_viz = 1;
var float autocvar_tas_viz_style = 1;

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
			if (i == 0) tov_start = p;
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
	if (!tov_pt) tov_pt = (vector*)memalloc(TOV_LINES * TOV_PTS * 12);
	slot = tov_head % bound(16, autocvar_tas_viz_lines, TOV_LINES);
	tov_head = (slot + 1) % bound(16, autocvar_tas_viz_lines, TOV_LINES);
	for (i = 0; i < n; i = i + 1)
	{
		p = TASOptViz_Point(i, p0);
		if (i == 0) p0 = p;
		if (i < TOV_PTS && tov_pt) tov_pt[slot * TOV_PTS + i] = p;
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
float jg_show;                  // Jargon's route is drawn (cl_jargon.qc): the old route posts give way
vector(float k, vector eye, vector fwd) RouteEdit_DragPoint =
{
	local vector n, p, q;
	local float d, t;
	n = tov_rnorm[k]; p = tov_rp[k]; q = p;
	traceline(eye, eye + fwd * 8192, MOVE_NOMONSTERS, world);
	// a point (an air point most often): across the view at its depth -- onto whatever the crosshair hit, a point in the
	// sky jumped to the far wall
	if (n == '0 0 0') { rte_far = FALSE; return eye + fwd * max(16, (p - eye) * fwd); }
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
	local float tsz, f0, w;
	local vector at;
	local string s;
	if (!rte_on) return;
	f0 = ui_font_cur;
	Font_Set(ui_font_ui);
	tsz = Font_Px(bound(11, scr_y / 72, 20));      // a baked size: a scaled one draws resampled glyphs
	s = (rte_drag >= 0) ? sprintf("Moving point %g: let go to place it", rte_drag + 1)
		: ((rte_hover >= 0) ? sprintf("Point %g: drag with the left button, right button removes it", rte_hover + 1)
		: "Route edit: aim at a marker (noclip to fly round); tas route edit or the tab ends it");
	w = stringwidth(s, TRUE, [tsz, tsz]);
	at = [rint((scr_x - w) * 0.5), rint(scr_y * 0.84), 0];         // below the speed readout
	sui_roundbox(at - [12, 6, 0], [w + 24, tsz + 12, 0], 6, SUI_THEME_PANEL, 0.8);
	sui_text(at, [tsz, tsz], s, (rte_drag >= 0 || rte_hover >= 0) ? SUI_THEME_ACCENT : SUI_THEME_DIM, 1, 0);
	Font_Set(f0);
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
	for (i = 0; i < tov_rn && !jg_show; i = i + 1)
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
	for (i = 0; i < bound(16, autocvar_tas_viz_lines, TOV_LINES) && autocvar_tas_viz_style != 1 && tov_pt; i = i + 1)
	{
		n = tov_n[i];
		if (n < 2) continue;
		age = cltime - tov_t[i];
		if (age > max(0.1, autocvar_tas_viz_fade)) { tov_n[i] = 0; continue; }
		a = 0.6 * (1 - age / max(0.1, autocvar_tas_viz_fade));
		col = (tov_kind[i] == 2) ? '0.3 1 0.4' : ((tov_kind[i] == 3) ? '1 0.3 0.3' : '0.5 0.7 1');
		TASOptViz_Line(i * TOV_PTS, n, col, a, 3);
	}
	if (autocvar_tas_viz_style != 1)
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

// tas_viz_style 1: the lines after renderscene, in the demo line's 2D pass (cl_main.qc beside Trail_Draw). The projection
// is pinned before renderscene as Trail_Pin does (cs_buildmatricies is lazy: the first project() must come before it).
void() TASOptViz_Pin =
{
	if ((!autocvar_tas_viz || autocvar_tas_viz_style != 1) && !jg_show) return;     // Jargon's labels project too
	makevectors(getproperty(VF_ANGLES));
	project(getproperty(VF_ORIGIN) + v_forward * 256);
};

// one path onto the strip, cut at the near plane (project() divides by w unguarded)
void(float best, float base, float n, vector col, float al) TASOptViz_Strip =
{
	local float j, da, db;
	local vector a, b;
	Line_RunEnd();
	for (j = 0; j + 1 < n; j = j + 1)
	{
		if (best) { a = tov_best[j]; b = tov_best[j + 1]; }
		else { a = tov_pt[base + j]; b = tov_pt[base + j + 1]; }
		a = a + TOV_LIFT; b = b + TOV_LIFT;
		da = (a - ln_eye) * ln_fwd; db = (b - ln_eye) * ln_fwd;
		if (da < LN_NEAR && db < LN_NEAR) { Line_RunEnd(); continue; }
		if (da < LN_NEAR) { Line_RunEnd(); Line_Pt(a + (b - a) * ((LN_NEAR - da) / (db - da)), col, al); }
		else if (ln_rn == 0) Line_Pt(a, col, al);
		if (db < LN_NEAR) { Line_Pt(b + (a - b) * ((LN_NEAR - db) / (da - db)), col, al); Line_RunEnd(); }
		else Line_Pt(b, col, al);
	}
	Line_RunEnd();
};

void() TASOptViz_Draw2D =
{
	local float i, n, age, w, fade;
	if (!autocvar_tas_viz || autocvar_tas_viz_style != 1) return;
	Line_ViewFrame();
	if (cvar("developer") && floor(cltime) != floor(cltime - frametime))
		print(sprintf("tas_viz 2d: eye %v fwd %v cam %g; start %v -> %v; target -> %v; best %g\n", ln_eye, ln_fwd, tov_camf == cltime,
			tov_start, project(tov_start + TOV_LIFT), project(tov_tgt), tov_bestn));
	w = max(1, cvar("gl_2dline_width"));        // Lex: the engine's 2D line width
	fade = max(0.1, autocvar_tas_viz_fade);
	Line_Width(w);
	for (i = 0; i < bound(16, autocvar_tas_viz_lines, TOV_LINES) && tov_pt; i = i + 1)
	{
		n = tov_n[i];
		if (n < 2) continue;
		age = cltime - tov_t[i];
		if (age > fade) { tov_n[i] = 0; continue; }
		TASOptViz_Strip(FALSE, i * TOV_PTS, n, (tov_kind[i] == 2) ? '0.3 1 0.4' : ((tov_kind[i] == 3) ? '1 0.3 0.3' : '0.5 0.7 1'),
			0.6 * (1 - age / fade));
	}
	if (tov_bestn >= 2 && (tov_final ? cltime - tov_bestt < 20 : cltime - tov_bestt < 60))
	{
		Line_Width(2 * w);
		TASOptViz_Strip(TRUE, 0, tov_bestn, tov_final ? '1 1 1' : '1 0.9 0.2', 0.95);
	}
};

// tas_viz_cam (Lex, 10 Nov): while a stretch is searched, the view 45 degrees up behind its start looking at the best line's
// middle, swaying slowly; once its line plays, 1 a chase view behind the body, 2 a 45-degree follow, the body drawn either
// way (the local player has no world model in first person). The camera passes through the world: nothing clips it,
// and the near plane (gl_mindist, not archived) is pushed to 55% of the way to what it looks at for that render, so the
// walls between are cut away; the engine keeps the last good PVS cluster when the view is in solid or the void (P138).
float tov_mindist;          // gl_mindist before the camera's render (0: not changed this frame)
entity tov_body;
void() TASOptViz_Cam =
{
	local vector f, h, cam, me, feet;
	local float d, r, y;
	tov_mindist = 0;
	if (!autocvar_tas_viz_cam || !tov_tgton || cltime - tov_tgtt > 120) return;
	me = getproperty(VF_ORIGIN);
	feet = (pmove_org != '0 0 0') ? pmove_org : me - '0 0 64';
	if (tov_final && cltime - tov_bestt < 20)
	{	// riding the played line
		h = normalize([pmove_vel_x, pmove_vel_y, 0]);
		if (vlen(h) < 0.5) h = normalize([tov_tgt_x - feet_x, tov_tgt_y - feet_y, 0]);
		f = feet + '0 0 36';
		cam = (autocvar_tas_viz_cam == 2) ? f - h * 300 + '0 0 300' : f - h * 260 + '0 0 90';
		if (!tov_body)
		{
			tov_body = spawn();
			setmodel(tov_body, "models/player.iqm");
			tov_body.solid = SOLID_NOT;
		}
		setorigin(tov_body, feet);
		tov_body.angles = [0, vectoyaw(h), 0];
		Av_Dress(tov_body);
		addentity(tov_body);
	}
	else
	{
		d = vlen(tov_tgt - tov_start);
		y = vectoyaw(tov_tgt - tov_start) + 12 * sin(cltime * 0.35);          // the slow sway
		makevectors([0, y, 0]);
		h = v_forward;
		f = (tov_bestn >= 2) ? tov_best[floor(tov_bestn * 0.5)] + TOV_LIFT : tov_start + TOV_LIFT;
		r = bound(500, 0.45 * d, 3000);
		cam = tov_start + TOV_LIFT - h * r * 0.7071 + '0 0 1' * r * 0.7071;
	}
	h = vectoangles(f - cam);
	h_x = 0 - h_x;                                          // vectoangles' pitch is up-positive, a view's down-positive
	setproperty(VF_ORIGIN, cam);
	setproperty(VF_ANGLES, h);
	tov_camo = cam; tov_cama = h; tov_camf = cltime;
	tov_mindist = max(0.01, cvar("gl_mindist"));
	cvar_set("gl_mindist", ftos(max(tov_mindist, 0.55 * vlen(f - cam))));
	if (cvar("developer") && floor(cltime) != floor(cltime - frametime))
		print(sprintf("tas_viz cam: at %v angles %v looking at %v (final %g, near %g)\n", cam, h, f, tov_final, cvar("gl_mindist")));
};

// after the main renderscene: the near plane back for every other view this frame
void() TASOptViz_AfterScene =
{
	if (tov_mindist > 0) cvar_set("gl_mindist", ftos(tov_mindist));
	tov_mindist = 0;
};
