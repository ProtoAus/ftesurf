/*
  P1449: Jargon, the line finder -- its route preview and in-world editor (Lex, 10 Nov: the old tab was "way too
  confusing ... start from scratch, more human"). The panel (cl_tasoptui.qc TASOptUI_Draw) has three steps: a guide
  run (a demo line on in the leaderboard, or a KSF replay of the map), its route, then surf it. The route is the
  server's plan from the start box's exit (`tas autosurf <demo> plan`, TAS_EV_JPLAN): each ramp's face is drawn
  translucent under a wireframe edge, each point a numbered handle; in noclip a point is dragged -- a ramp's along its
  face, a bhop's on its floor, an air point across the view -- and the server keeps the move by the guide run's clock
  (`tas autosurf move`), so every later plan of that run has it.
*/
#define JG_MAX 64
float jg_n, jg_at;
float jg_k[JG_MAX];             // 1 a ramp to board, 2 a bhop, 3 the end, 4 a peak, 5 an air point
float jg_t[JG_MAX];             // the guide run's time there
vector jg_o[JG_MAX];
vector jg_nn[JG_MAX];
float jg_mv[JG_MAX];            // moved in the editor
float jg_surf[JG_MAX];          // its ramp's world surface (-2 not looked up, -1 none)
float jg_edit;                  // "Edit in world"
var float jg_hover = -1, jg_drag = -1;
vector jg_pos, jg_off, jg_from;
float jg_m1, jg_m2, jg_far, jg_replan;
#define JG_GUIDES 12
string jg_gp[JG_GUIDES];        // a guide run's file
string jg_gl[JG_GUIDES];        // ...and its label
float jg_gn, jg_pick, jg_gat;
string jg_planned;              // the file the shown plan is of

string(string p) TASJargon_Base =
{
	local float i;
	for (i = strlen(p) - 1; i >= 0 && substring(p, i, 1) != "/"; i = i - 1) ;
	p = substring(p, i + 1, -1);
	if (substring(p, strlen(p) - 4, 4) == ".rec") p = substring(p, 0, strlen(p) - 4);
	return p;
};

float() TASJargon_Airs =
{
	local float i, n;
	n = 0;
	for (i = 0; i < tov_rn; i = i + 1) if (tov_rk[i] == 3) n = n + 1;
	return n;
};

// a path safe to put in a console line (it goes through localcmd): letters, digits, _ . / - only (review)
float(string p) TASJargon_Safe =
{
	local float i, c;
	if (p == "" || strstrofs(p, "..") >= 0) return FALSE;
	for (i = 0; i < strlen(p); i = i + 1)
	{
		c = str2chr(p, i);
		if (!((c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || c == 95 || c == 46 || c == 47 || c == 45)) return FALSE;
	}
	return TRUE;
};

// the demo lines on in the leaderboard (cl_scores.qc board lines) whose file is here, then this map's KSF replays
void() TASJargon_Guides =
{
	local float i, h, n;
	local string p, l, m, pre;
	if (cltime < jg_gat) return;
	jg_gat = cltime + 1;
	for (i = 0; i < jg_gn; i = i + 1) { strunzone(jg_gp[i]); strunzone(jg_gl[i]); }
	jg_gn = 0;
	if (sb_ln_st)
		for (i = 0; i < SB_LNMAX && jg_gn < JG_GUIDES; i = i + 1)
			if (sb_ln_st[i] == SBL_ON)
			{
				p = sb_ln_path[i];
				if (p == "")
				if (substring(sb_ln_key[i], 0, 2) == "l:") p = substring(sb_ln_key[i], 2, -1);
				if (p == "" || substring(p, strlen(p) - 4, 4) != ".rec" || !TASJargon_Safe(p)) continue;
				l = sb_ln_name[i];                      // the row's player (an online or local board row)
				if (l == "") l = ln_owner[LN_BOARDSLOT(i)];
				if (l == "") l = TASJargon_Base(p);
				jg_gp[jg_gn] = strzone(p); jg_gl[jg_gn] = strzone(l); jg_gn = jg_gn + 1;
			}
	m = strtolower(zone_mapname);
	if (substring(m, 0, 5) == "surf_") m = substring(m, 5, -1);
	pre = strcat("ksf_", m, "_");
	h = search_begin("cfg/ksfreplays/*.rec", TRUE, TRUE);
	if (h >= 0)
	{
		n = search_getsize(h);
		for (i = 0; i < n && jg_gn < JG_GUIDES; i = i + 1)
		{
			p = search_getfilename(h, i);
			l = TASJargon_Base(p);
			if (strstrofs(strtolower(l), pre) != 0 || !TASJargon_Safe(p)) continue;
			jg_gp[jg_gn] = strzone(p); jg_gl[jg_gn] = strzone(strcat("KSF ", substring(l, strlen(pre), -1))); jg_gn = jg_gn + 1;
		}
		search_end(h);
	}
	if (jg_pick >= jg_gn) jg_pick = 0;
};

void() TASJargon_RequestPlan =
{
	if (jg_pick >= jg_gn) return;
	localcmd(sprintf("tas autosurf %s plan%s\n", jg_gp[jg_pick], TASJargon_Airs() ? " air" : ""));
	if (jg_planned != "") strunzone(jg_planned);
	jg_planned = strzone(jg_gp[jg_pick]);
};

void() TASJargon_PlanEvent =
{	// a chunk: the plan's size, the first point here, how many follow
	local float i, n, s, c, k, t, x, y, z;
	n = readbyte(); s = readbyte(); c = readbyte();
	if (s == 0) { jg_n = min(n, JG_MAX); jg_hover = jg_drag = -1; }
	for (i = s; i < s + c; i = i + 1)
	{
		k = readbyte(); t = readfloat();
		x = readfloat(); y = readfloat(); z = readfloat();
		if (i < JG_MAX) { jg_k[i] = k; jg_t[i] = t; jg_o[i] = [x, y, z]; jg_mv[i] = 0; jg_surf[i] = -2; }
		x = readshort() / 30000; y = readshort() / 30000; z = readshort() / 30000;
		if (i < JG_MAX) jg_nn[i] = [x, y, z];
	}
	jg_at = cltime;
};

vector(float i) TASJargon_Col =
{
	if (i == jg_hover || i == jg_drag) return SUI_THEME_ACCENT;
	if (jg_k[i] == 1) return jg_mv[i] ? '0.55 1 0.75' : SUI_THEME_GOOD;
	if (jg_k[i] == 2) return SUI_THEME_WARN;
	if (jg_k[i] == 5) return SUI_THEME_INFO;
	return SUI_THEME_DIM;
};

string(float i) TASJargon_Word =
{
	if (jg_k[i] == 1) return "Ramp";
	if (jg_k[i] == 2) return "Bhop";
	if (jg_k[i] == 5) return "Air point";
	if (jg_k[i] == 3) return "End";
	return "Point";
};

// the plane a point moves on: a ramp's face, a bhop's floor; '0 0 0' across the view (an air point)
vector(float i) TASJargon_Plane =
{
	if (jg_k[i] == 1) return jg_nn[i];
	if (jg_k[i] == 2) return '0 0 1';
	return '0 0 0';
};

vector(float i, vector eye, vector fwd) TASJargon_DragPoint =
{
	local vector n, p, q;
	local float d, t;
	n = TASJargon_Plane(i); p = jg_from; q = p;
	jg_far = FALSE;
	if (n == '0 0 0') return eye + fwd * max(16, (p - eye) * fwd);
	traceline(eye, eye + fwd * 8192, MOVE_NOMONSTERS, world);
	d = fwd * n;
	jg_far = TRUE;
	if (fabs(d) > 0.01)
	{
		t = ((p - eye) * n) / d;
		if (t > 0 && t < 8192) { q = eye + fwd * t; jg_far = FALSE; }
	}
	if (trace_fraction < 1 && trace_plane_normal * n > 0.95 && vlen(trace_endpos - q) < 96) q = trace_endpos;   // the face itself
	return q;
};

// shown with the Jargon tab open or "Edit in world" on; each frame: the handle under the crosshair, a drag, a replan due
void() TASJargon_Frame =
{
	local vector eye, fwd;
	local float i, d, best;
	jg_show = (jg_n > 0 && (jg_edit || (tasu_open && tasu_tab == TAS_TAB_OPTIMIZE)));
	if (jg_replan && cltime >= jg_replan) { jg_replan = 0; TASJargon_RequestPlan(); }
	if (!jg_edit) { jg_hover = jg_drag = -1; return; }
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;
	if (jg_drag >= 0)
	{
		if (jg_drag >= jg_n) { jg_drag = -1; return; }
		eye = TASJargon_DragPoint(jg_drag, eye, fwd);
		if (!jg_far) jg_pos = eye + jg_off;
		return;
	}
	if (tasu_open) { jg_hover = -1; return; }          // the panel's cursor is aiming, not the crosshair
	jg_hover = -1; best = cos(3 * M_PI / 180);
	for (i = 0; i < jg_n; i = i + 1)
	{
		d = normalize(jg_o[i] + '0 0 24' - eye) * fwd;
		if (d > best) { best = d; jg_hover = i; }
	}
};

// the route point (tas route) an air point of the plan came from: the nearest at its place
float(vector p) TASJargon_RouteOf =
{
	local float i, b, d;
	b = -1; d = 4;
	for (i = 0; i < tov_rn; i = i + 1)
		if (tov_rk[i] == 3)
		if (vlen(tov_rp[i] - p) < d) { d = vlen(tov_rp[i] - p); b = i; }
	return b;
};

float(float evtype, float scanx, float chary, float devid) TASJargon_InputEvent =
{
	local float r;
	if (evtype == IE_KEYUP && scanx == K_MOUSE2 && jg_m2) { jg_m2 = FALSE; return TRUE; }
	if (evtype == IE_KEYUP && scanx == K_MOUSE1 && jg_m1 && jg_drag < 0) { jg_m1 = FALSE; return TRUE; }
	if (!jg_edit) return FALSE;
	if (tasu_open && jg_drag < 0) return FALSE;         // the panel's clicks are its own
	if (evtype == IE_KEYDOWN && scanx == K_MOUSE1 && jg_hover >= 0)
	{
		jg_drag = jg_hover; jg_pos = jg_from = jg_o[jg_drag]; jg_m1 = TRUE;
		makevectors(getproperty(VF_ANGLES));
		jg_off = jg_pos - TASJargon_DragPoint(jg_drag, getproperty(VF_ORIGIN), v_forward);
		if (jg_far || TASJargon_Plane(jg_drag) == '0 0 0') jg_off = '0 0 0';
		return TRUE;
	}
	if (evtype == IE_KEYUP && scanx == K_MOUSE1 && jg_drag >= 0)
	{
		if (jg_k[jg_drag] == 1 || jg_k[jg_drag] == 2)
		{
			localcmd(sprintf("tas autosurf move %.3f %.1f %.1f %.1f\n", jg_t[jg_drag], jg_pos_x, jg_pos_y, jg_pos_z));
			jg_mv[jg_drag] = 1;
		}
		else if (jg_k[jg_drag] == 5)
		{
			r = TASJargon_RouteOf(jg_from);
			if (r >= 0) { localcmd(sprintf("tas route set %g %.1f %.1f %.1f 0 0 0\n", r + 1, jg_pos_x, jg_pos_y, jg_pos_z)); jg_replan = cltime + 0.4; }
		}
		jg_o[jg_drag] = jg_pos;
		jg_drag = -1; jg_m1 = FALSE;
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_MOUSE2 && jg_hover >= 0 && jg_drag < 0)
	{	// right click: an air point goes; a guide point goes back to the guide run's place on the next plan
		if (jg_k[jg_hover] == 5)
		{
			r = TASJargon_RouteOf(jg_o[jg_hover]);
			if (r >= 0) { localcmd(sprintf("tas route del %g\n", r + 1)); jg_replan = cltime + 0.4; }
		}
		jg_m2 = TRUE;
		return TRUE;
	}
	return FALSE;
};

// In the depth-tested world pass beside TASOptViz_Draw: ramp faces, handles, and a thin line through them in order.
void(vector a, vector b, vector col, float al) TASJargon_Seg =
{
	R_BeginPolygon(TOV_SHADER, 0);
	R_PolygonVertex(a, '0.5 0 0', col, al);
	R_PolygonVertex(b, '0.5 0 0', col, al);
	R_EndPolygon();
};
void() TASJargon_DrawWorld =
{
	local float i, j, s, np, h;
	local vector col, p, q, o;
	if (!jg_show) return;
	for (i = 0; i < jg_n; i = i + 1)
	{
		col = TASJargon_Col(i);
		o = (i == jg_drag) ? jg_pos : jg_o[i];
		if (jg_k[i] == 1)
		{
			if (jg_surf[i] == -2)
			{	// the ramp's face: the surface nearest a point just inside the ramp, if it lies in the plan's plane
				s = getsurfacenearpoint(world, jg_o[i] - jg_nn[i] * 24);
				if (s >= 0)
				if (getsurfacenormal(world, s) * jg_nn[i] < 0.95) s = getsurfacenearpoint(world, jg_o[i]);
				if (s >= 0)
				if (getsurfacenormal(world, s) * jg_nn[i] < 0.95) s = -1;
				jg_surf[i] = s;
			}
			s = jg_surf[i];
			if (s >= 0)
			{
				np = getsurfacenumpoints(world, s);
				R_BeginPolygon(TOV_SHADER, 0);
				for (j = 0; j < np; j = j + 1) R_PolygonVertex(getsurfacepoint(world, s, j) + jg_nn[i] * 0.5, '0.5 0 0', col, (i == jg_hover) ? 0.28 : 0.14);
				R_EndPolygon();
				for (j = 0; j < np; j = j + 1)
					TASJargon_Seg(getsurfacepoint(world, s, j) + jg_nn[i], getsurfacepoint(world, s, (j + 1) % np) + jg_nn[i], col, 0.85);
			}
		}
		// the handle: a cube on a post (zone_edit's look), bigger under the crosshair
		h = (i == jg_hover || i == jg_drag) ? 14 : 8;
		p = o + '0 0 1' * h;
		TASJargon_Seg(o, o + '0 0 56', col, 0.9);
		for (j = 0; j < 4; j = j + 1)
		{
			q = [(j & 1) ? h : -h, (j & 2) ? h : -h, 0];
			TASJargon_Seg(p + [q_x, q_y, -h], p + [q_x, q_y, h], col, 0.95);
		}
		TASJargon_Seg(p + [-h, -h, -h], p + [h, -h, -h], col, 0.95); TASJargon_Seg(p + [h, -h, -h], p + [h, h, -h], col, 0.95);
		TASJargon_Seg(p + [h, h, -h], p + [-h, h, -h], col, 0.95); TASJargon_Seg(p + [-h, h, -h], p + [-h, -h, -h], col, 0.95);
		TASJargon_Seg(p + [-h, -h, h], p + [h, -h, h], col, 0.95); TASJargon_Seg(p + [h, -h, h], p + [h, h, h], col, 0.95);
		TASJargon_Seg(p + [h, h, h], p + [-h, h, h], col, 0.95); TASJargon_Seg(p + [-h, h, h], p + [-h, -h, h], col, 0.95);
		if (i > 0) TASJargon_Seg(((i - 1 == jg_drag) ? jg_pos : jg_o[i - 1]) + '0 0 28', o + '0 0 28', '1 1 1', 0.35);
	}
};

// the 2D pass (after the lines): each handle's number, the hovered one's name; the projection is pinned in TASOptViz_Pin
void() TASJargon_Draw2D =
{
	local float i, tsz, f0, w;
	local vector q, o, eye, fwd, vs;
	local string s;
	if (!jg_show) return;
	f0 = ui_font_cur;
	Font_Set(ui_font_ui);
	vs = getproperty(VF_SCREENVSIZE);
	tsz = Font_Px(bound(11, vs_y / 80, 18));
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES)); fwd = v_forward;
	for (i = 0; i < jg_n; i = i + 1)
	{
		o = ((i == jg_drag) ? jg_pos : jg_o[i]) + '0 0 64';
		if ((o - eye) * fwd < 16) continue;
		q = project(o);
		if (q_z < -1 || q_z > 1) continue;
		s = (i == jg_hover || i == jg_drag) ? sprintf("%g  %s%s", i + 1, TASJargon_Word(i), jg_mv[i] ? " (moved)" : "") : ftos(i + 1);
		w = stringwidth(s, TRUE, [tsz, tsz]);
		q = [rint(q_x - w * 0.5), rint(q_y - tsz), 0];
		drawfill(q - [4, 2, 0], [w + 8, tsz + 4, 0], '0 0 0', 0.55, 0);
		drawstring(q, s, [tsz, tsz], TASJargon_Col(i), 1, 0);
	}
	Font_Set(f0);
};

void(vector scr) TASJargon_DrawHint =
{
	local float tsz, f0, w;
	local vector at;
	local string s;
	if (!jg_edit) return;
	f0 = ui_font_cur;
	Font_Set(ui_font_ui);
	tsz = Font_Px(bound(11, scr_y / 72, 20));
	if (jg_drag >= 0) s = sprintf("Moving %s %g: let go to place it", TASJargon_Word(jg_drag), jg_drag + 1);
	else if (jg_hover >= 0) s = sprintf("%s %g: drag with the left mouse button%s", TASJargon_Word(jg_hover), jg_hover + 1,
		(jg_k[jg_hover] == 5) ? ", right click removes it" : "");
	else s = "Editing the route: fly round in noclip (V), aim at a handle and drag it";
	w = stringwidth(s, TRUE, [tsz, tsz]);
	at = [rint((scr_x - w) * 0.5), rint(scr_y * 0.84), 0];
	sui_roundbox(at - [12, 6, 0], [w + 24, tsz + 12, 0], 6, SUI_THEME_PANEL, 0.8);
	sui_text(at, [tsz, tsz], s, (jg_drag >= 0 || jg_hover >= 0) ? SUI_THEME_ACCENT : SUI_THEME_DIM, 1, 0);
	Font_Set(f0);
};
