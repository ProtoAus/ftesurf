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
float jg_got;                   // rows of the plan arrived so far (its chunks overwrite the old plan's in place)
float jg_k[JG_MAX];             // 1 a ramp to board, 2 a bhop, 3 the end, 4 a peak, 5 an air point, 6 a turn point (P1483)
float jg_t[JG_MAX];             // the guide run's time there
vector jg_o[JG_MAX];
vector jg_nn[JG_MAX];
float jg_mv[JG_MAX];            // moved in the editor
float jg_surf[JG_MAX];          // its ramp's world surface (-2 not looked up, -1 none)
float jg_edit;                  // "Edit in world"
var float jg_hover = -1, jg_drag = -1;
vector jg_pos, jg_off, jg_from;
float jg_m1, jg_m2, jg_far, jg_replan;
var float jgw_sel = -1;           // the panel's selected waypoint
float jgw_selk, jgw_selt;         // ...by what it is (cl_tasoptui.qc follows it across replans)
vector jgw_selo;
#define JG_GUIDES 12
string jg_gp[JG_GUIDES];        // a guide run's file
string jg_gl[JG_GUIDES];        // ...and its label
float jg_gn, jg_pick, jg_gat;
string jg_planned;              // the file the shown plan is of
// "Edit in the world" (Lex, 10 Nov: close the window, noclip round, Esc opens it again): a camera the movement keys fly,
// client-side as the ghost's is (cl_ghost.qc Ghost_Fly) -- the body stays where it waits, its TAS state untouched (ghost
// itself cancels TAS), so "From here" still works after the edit; the body drawn as the ghost's stand-in
float jg_fly, jg_flyt, jg_btn;
vector jg_camorg, jg_bodyang, jg_move;

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

// P1478: the map's courses from its zones -- main, its stages, its bonuses -- one picked; the guide runs offered are runs
// of that course by their own .rec header (track, leg): a KSF bonus replay was offered for the main start before
#define JG_COURSES 40
float jg_cn, jg_cpick, jg_czc;
float jg_ct[JG_COURSES], jg_cl[JG_COURSES];     // track (0 main, k bonus k), leg (0 the whole track, k stage k)
string jg_cmap;
void() TASJargon_Courses =
{
	local float t, k, segs;
	if (jg_cmap == zone_mapname && jg_czc == zone_count) return;
	if (jg_cmap != "") strunzone(jg_cmap);
	jg_cmap = strzone(zone_mapname); jg_czc = zone_count; jg_cn = 0; jg_cpick = 0;
	if (zone_count <= 0) return;
	if (Zone_TrackExists(0))
	{
		jg_ct[0] = 0; jg_cl[0] = 0; jg_cn = 1;
		segs = Zone_TrackSegs(0);
		for (k = 1; k <= segs && segs > 1 && jg_cn < JG_COURSES; k = k + 1) { jg_ct[jg_cn] = 0; jg_cl[jg_cn] = k; jg_cn = jg_cn + 1; }
	}
	for (t = 1; t < ZONE_MAXTRACKS && jg_cn < JG_COURSES; t = t + 1)
		if (Zone_TrackExists(t)) { jg_ct[jg_cn] = t; jg_cl[jg_cn] = 0; jg_cn = jg_cn + 1; }
};
string(float i) TASJargon_CourseLabel =
{
	if (i < 0 || i >= jg_cn) return "this map";
	if (jg_ct[i] > 0) return sprintf("Bonus %g", jg_ct[i]);
	return (jg_cl[i] > 0) ? sprintf("Stage %g", jg_cl[i]) : "Main";
};
// the console words for the picked course ("" on a map without zones)
string() TASJargon_CourseWords = { return (jg_cpick < jg_cn) ? sprintf(" course %g %g", jg_ct[jg_cpick], jg_cl[jg_cpick]) : ""; };

// a .rec's header, read once a map: this map's, its track and leg (-1 unstated), its time when it says (KSF)
#define JG_HC 64
string jg_hcp[JG_HC];
float jg_hct[JG_HC], jg_hcl[JG_HC], jg_hcs[JG_HC], jg_hcok[JG_HC];
float jg_hcn;
string jg_hcmap;
float(string p) TASJargon_Head =
{
	local float i, h, fh, c;
	local string line;
	if (jg_hcmap != zone_mapname)
	{
		for (i = 0; i < jg_hcn; i = i + 1) strunzone(jg_hcp[i]);
		jg_hcn = 0;
		if (jg_hcmap != "") strunzone(jg_hcmap);
		jg_hcmap = strzone(zone_mapname);
	}
	for (i = 0; i < jg_hcn; i = i + 1) if (!strcmp(jg_hcp[i], p)) return i;
	fh = fopen(p, FILE_READ);
	if (fh < 0) return -1;
	if (jg_hcn >= JG_HC) { strunzone(jg_hcp[0]); for (i = 1; i < JG_HC; i = i + 1) { jg_hcp[i-1] = jg_hcp[i]; jg_hct[i-1] = jg_hct[i]; jg_hcl[i-1] = jg_hcl[i]; jg_hcs[i-1] = jg_hcs[i]; jg_hcok[i-1] = jg_hcok[i]; } jg_hcn = JG_HC - 1; }
	h = jg_hcn; jg_hcn = jg_hcn + 1;
	jg_hcp[h] = strzone(p); jg_hct[h] = jg_hcl[h] = -1; jg_hcs[h] = 0; jg_hcok[h] = TRUE;
	for (i = 0; i < 48; i = i + 1)
	{
		line = fgets(fh);
		if (line == "") continue;
		c = tokenize(line);
		if (argv(0) == "begin" || (c >= 7 && FS_TASNumber(argv(0)))) break;
		if (argv(0) == "map" && c >= 2) jg_hcok[h] = !strcasecmp(argv(1), zone_mapname);
		else if (argv(0) == "track" && c == 2) jg_hct[h] = stof(argv(1));
		else if (argv(0) == "leg" && c == 2) jg_hcl[h] = stof(argv(1));
		else if (argv(0) == "ksftime" && c == 2) jg_hcs[h] = stof(argv(1));
	}
	fclose(fh);
	return h;
};
// 2 a run of the picked course, 1 a whole-track run of its track (the server cuts the stage from it), 0 neither
float(float h) TASJargon_Fit =
{
	local float t, l;
	if (h < 0) return 0;
	if (!jg_hcok[h]) return 0;
	if (jg_cpick >= jg_cn) return 2;
	t = max(0, jg_hct[h]); l = max(0, jg_hcl[h]);
	if (t != jg_ct[jg_cpick]) return 0;
	if (l == jg_cl[jg_cpick]) return 2;
	return (l == 0 && jg_cl[jg_cpick] > 0) ? 1 : 0;
};
float jg_gfit[JG_GUIDES];
void(string p, string l, float want) TASJargon_Add =
{
	local float i, h;
	if (jg_gn >= JG_GUIDES || !TASJargon_Safe(p)) return;
	for (i = 0; i < jg_gn; i = i + 1) if (!strcmp(jg_gp[i], p)) return;
	h = TASJargon_Head(p);
	if (TASJargon_Fit(h) != want) return;
	if (jg_hcs[h] > 0 && strstrofs(l, ":") < 0 && substring(l, strlen(l) - 1, 1) != "s")     // a leaderboard name has its time
		l = (jg_hcs[h] >= 60) ? sprintf("%s %g:%s%.2f", l, floor(jg_hcs[h] / 60), (jg_hcs[h] - 60 * floor(jg_hcs[h] / 60) < 10) ? "0" : "",
			jg_hcs[h] - 60 * floor(jg_hcs[h] / 60)) : sprintf("%s %.2fs", l, jg_hcs[h]);
	if (want == 1) l = strcat(l, " (full run)");
	jg_gp[jg_gn] = strzone(p); jg_gl[jg_gn] = strzone(l); jg_gfit[jg_gn] = want; jg_gn = jg_gn + 1;
};
// a leaderboard replay's name "00m52.530s_farsh_r23168" as "farsh 52.53s"; others as their base name
string(string p) TASJargon_RunLabel =
{
	local float i, j, m;
	p = TASJargon_Base(p);
	if (substring(p, 2, 1) == "m" && substring(p, 9, 1) == "s" && substring(p, 10, 1) == "_")
	{
		j = -1;
		for (i = strstrofs(p, "_r", 11); i >= 0; i = strstrofs(p, "_r", i + 1)) j = i;
		m = stof(substring(p, 0, 2));
		return sprintf("%s %s", substring(p, 11, ((j > 11) ? j : strlen(p)) - 11),
			m ? sprintf("%g:%s", m, substring(p, 3, 6)) : sprintf("%.2fs", stof(substring(p, 3, 6))));
	}
	return p;
};
void(string dir, float want, float most) TASJargon_Folder =
{
	local float h, n, c, k, g;
	local string f;
	h = search_begin(sprintf("%s/*.rec", dir), 33, TRUE);    // name order: leaderboard names start with the time
	if (h < 0) return;
	n = search_getsize(h); k = 0;
	for (c = 0; c < n && k < most && jg_gn < JG_GUIDES; c = c + 1)
	{
		f = search_getfilename(h, c);
		if (strstrofs(f, "_dnf") >= 0) continue;      // an abandoned run's short time is not the fastest
		g = jg_gn;
		TASJargon_Add(f, TASJargon_RunLabel(f), want);
		if (jg_gn > g) k = k + 1;
	}
	search_end(h);
};
void(float want) TASJargon_Ksf =
{
	local float i, h, n, k, g;
	local string p, l, m, pre;
	m = strtolower(zone_mapname);
	if (substring(m, 0, 5) == "surf_") m = substring(m, 5, -1);
	pre = strcat("ksf_", m, "_");
	h = search_begin("cfg/ksfreplays/*.rec", TRUE, TRUE);
	if (h < 0) return;
	n = search_getsize(h); k = 0;
	for (i = 0; i < n && jg_gn < JG_GUIDES && k < 3; i = i + 1)
	{
		p = search_getfilename(h, i);
		l = TASJargon_Base(p);
		if (strstrofs(strtolower(l), pre) != 0) continue;
		g = jg_gn;
		TASJargon_Add(p, strcat("KSF ", substring(l, strlen(pre), -1)), want);
		if (jg_gn > g) k = k + 1;
	}
	search_end(h);
};

// The guide runs of the picked course: the demo lines on in the leaderboard (cl_scores.qc) first -- your pick -- then
// this course's leaderboard replays, KSF replays, Momentum replays and your own recordings in data/; for a stage, whole
// runs of its track after those (marked "full run"). Rebuilt when the course, the map or the board's lines change.
string jg_gkey;
float jg_grt;
void() TASJargon_Guides =
{
	local float i, w;
	local string p, l, key, leg, full, keep;
	if (cltime < jg_gat) return;
	jg_gat = cltime + 1;
	TASJargon_Courses();
	key = sprintf("%s %g", zone_mapname, jg_cpick);
	if (sb_ln_st)
		for (i = 0; i < SB_LNMAX; i = i + 1)
			if (sb_ln_st[i] == SBL_ON) key = strcat(key, " ", sb_ln_path[i], sb_ln_key[i]);
	if (key == jg_gkey && cltime < jg_grt) return;      // the folders again every 5 s (new downloads)
	if (key != jg_gkey) { if (jg_gkey != "") strunzone(jg_gkey); jg_gkey = strzone(key); jg_pick = 0; keep = ""; }
	else keep = (jg_pick < jg_gn) ? strzone(jg_gp[jg_pick]) : "";      // a faster download sorts in ahead: keep the file (review B)
	jg_grt = cltime + 5;
	for (i = 0; i < jg_gn; i = i + 1) { strunzone(jg_gp[i]); strunzone(jg_gl[i]); }
	jg_gn = 0;
	leg = (jg_cpick < jg_cn) ? FS_LegDir(jg_ct[jg_cpick], jg_cl[jg_cpick]) : "main";
	full = (jg_cpick < jg_cn) ? FS_LegDir(jg_ct[jg_cpick], 0) : "main";
	for (w = 2; w >= 1; w = w - 1)
	{
		if (sb_ln_st)
			for (i = 0; i < SB_LNMAX && jg_gn < JG_GUIDES; i = i + 1)
				if (sb_ln_st[i] == SBL_ON)
				{
					p = sb_ln_path[i];
					if (p == "")
					if (substring(sb_ln_key[i], 0, 2) == "l:") p = substring(sb_ln_key[i], 2, -1);
					if (p == "" || substring(p, strlen(p) - 4, 4) != ".rec") continue;
					l = sb_ln_name[i];                      // the row's player (an online or local board row)
					if (l == "") l = ln_owner[LN_BOARDSLOT(i)];
					if (l == "") l = TASJargon_RunLabel(p);
					TASJargon_Add(p, l, w);
				}
		if (w == 1 && (jg_cpick >= jg_cn || !jg_cl[jg_cpick])) break;     // whole runs are the course itself
		p = Online_CacheDir(zone_mapname, jg_ct[min(jg_cpick, max(0, jg_cn - 1))] * (jg_cn > 0), (w == 2 && jg_cpick < jg_cn) ? jg_cl[jg_cpick] : 0);
		TASJargon_Folder(substring(p, 0, strlen(p) - 1), w, (w == 2) ? 3 : 2);    // lowercased, as written (ext4: review B)
		TASJargon_Ksf(w);
		TASJargon_Folder(sprintf("data/momentum/%s/%s", zone_mapname, (w == 2) ? leg : full), w, (w == 2) ? 3 : 2);
		if (w == 2) TASJargon_Folder("data", 2, 4);
	}
	if (keep != "")
	{
		for (i = 0; i < jg_gn; i = i + 1) if (!strcmp(jg_gp[i], keep)) jg_pick = i;
		strunzone(keep);
	}
	if (jg_pick >= jg_gn) jg_pick = 0;
};

// The picked course's Continue, if one is saved (sv_tasautosurf.qc SV_TASAutoSave): its stretch and of, read every 2 s
float jg_knext, jg_kof, jg_kat;
float jg_klearn;                // P1483: stretches of this course with a learned line (data/jargon/<map>/<leg>.prior)
var float jg_kc = -1;
void() TASJargon_Saved =
{
	local float fh, i;
	if (cltime < jg_kat && jg_kc == jg_cpick) return;
	if (jg_kc != jg_cpick) jg_knext = jg_kof = 0;      // another course: none until its answer (TASJargon_SavedEvent)
	jg_kat = cltime + 5; jg_kc = jg_cpick;
	if (jg_cpick >= jg_cn) return;
	jg_klearn = 0;
	fh = fopen(sprintf("data/jargon/%s/%s.prior", zone_mapname, FS_LegDir(jg_ct[jg_cpick], jg_cl[jg_cpick])), FILE_READ);
	if (fh >= 0)
	{
		for (i = 0; i < 70; i = i + 1) if (substring(fgets(fh), 0, 2) == "p ") jg_klearn = jg_klearn + 1;
		fclose(fh);
	}
	// the saved run is the server's to read: CSQC may not open data/tasproj/ (each refusal printed, every 2 s)
	localcmd(sprintf("cmd tas autosurf saved %g %g\n", jg_ct[jg_cpick], jg_cl[jg_cpick]));
};
void() TASJargon_SavedEvent =
{
	local float ct, cl, k, n;
	ct = readbyte(); cl = readbyte(); k = readshort(); n = readshort();
	if (jg_cpick < jg_cn && ct == jg_ct[jg_cpick] && cl == jg_cl[jg_cpick]) { jg_knext = k; jg_kof = n; }
};

var float jg_plannedc = -1;         // the course the shown plan is of
void() TASJargon_RequestPlan =
{
	local float x;
	if (jg_pick >= jg_gn) return;
	x = cvar("tas_jargon_exp");     // the panel's experiments: apex, join, launch and turns shape the plan (cl_tasoptui.qc)
	localcmd(sprintf("tas autosurf %s plan%s%s%s\n", jg_gp[jg_pick], TASJargon_CourseWords(), TASJargon_Airs() ? " air" : "",
		strcat((x & 4) ? " apex" : "", (x & 8) ? " join" : "", (x & 512) ? " launch" : "", (x & 1024) ? " turns" : "")));
	// another course or run: none until its plan arrives (a refused one left the last course's route up: review B); the
	// same one (an edit's replan) keeps its points up meanwhile -- a run refuses plans, and they stayed blank (Lex)
	if (jg_planned != jg_gp[jg_pick] || jg_plannedc != jg_cpick) jg_n = 0;
	jg_hover = jg_drag = -1;
	if (jg_planned != "") strunzone(jg_planned);
	jg_planned = strzone(jg_gp[jg_pick]);
	jg_plannedc = jg_cpick;
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
	jg_got = s + c;
	jg_at = cltime;
};

vector(float i) TASJargon_Col =
{
	if (i == jg_hover || i == jg_drag) return SUI_THEME_ACCENT;
	if (jg_k[i] == 1) return jg_mv[i] ? '0.55 1 0.75' : SUI_THEME_GOOD;
	if (jg_k[i] == 2) return SUI_THEME_WARN;
	if (jg_k[i] == 5) return SUI_THEME_INFO;
	if (jg_k[i] == 6) return SUI_THEME_INFO * 0.6;     // a turn point: planned, not a handle
	return SUI_THEME_DIM;
};

string(float i) TASJargon_Word =
{
	if (jg_k[i] == 1) return "Ramp";
	if (jg_k[i] == 2) return "Bhop";
	if (jg_k[i] == 5) return "Air point";
	if (jg_k[i] == 6) return "Turn point";
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
var float autocvar_tas_jargon_route = 1;     // Lex: the waypoints stay on     // P1483 stream: the route stays drawn with the panel closed

// shown with the Jargon tab open or "Edit in world" on; each frame: the handle under the crosshair, a drag, a replan due
void() TASJargon_Frame =
{
	local vector eye, fwd;
	local float i, d, best;
	jg_show = (jg_n > 0 && (jg_edit || (tasu_open && tasu_tab == TAS_TAB_OPTIMIZE) || taso_state == 1 || taso_armed || autocvar_tas_jargon_route));     // route: the stream panel's
	if (jg_replan && cltime >= jg_replan && taso_state != 1) { jg_replan = 0; TASJargon_RequestPlan(); }    // held while it runs (review 1528)
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
		if (jg_k[i] == 1 || jg_k[i] == 2 || jg_k[i] == 5)
		if (d > best) { best = d; jg_hover = i; }
	}
};

void() TASJargon_EditStart =
{
	if (taso_state == 1) { print("tas jargon: Move in the world waits for a stop -- type the numbers in the table to edit live\n"); return; }      // its free camera and the chase would fight
	if (!jg_n) TASJargon_RequestPlan();
	jg_edit = jg_fly = TRUE; jg_flyt = cltime;
	jg_camorg = getproperty(VF_ORIGIN); jg_bodyang = getproperty(VF_CL_VIEWANGLES); jg_move = '0 0 0'; jg_btn = 0;
	if (tasu_open) TASUI_Close();
};
// ended without reopening the panel: a map load, or a replay, rewind, ghost or spectate view taking the camera (review)
void(float restore) TASJargon_FlyCancel =
{
	if (!jg_fly && !jg_edit) return;
	jg_fly = jg_edit = FALSE; jg_drag = jg_hover = -1;
	if (restore) setproperty(VF_CL_VIEWANGLES, jg_bodyang);
};
// a forced view angle while flying is the body's (as Ghost_SetAngles takes it): the camera keeps the mouse's
float(vector newang, float isdelta) TASJargon_SetAngles =
{
	if (!jg_fly) return FALSE;
	jg_bodyang = isdelta ? jg_bodyang + newang - getproperty(VF_CL_VIEWANGLES) : newang;
	return TRUE;
};
void() TASJargon_EditEnd =
{
	jg_fly = jg_edit = FALSE; jg_drag = jg_hover = -1;
	setproperty(VF_CL_VIEWANGLES, jg_bodyang);
	if (!tasu_open) { tasu_tab = TAS_TAB_OPTIMIZE; TASUI_Toggle(0); }
};
// CSQC_Input_Frame: the movement keys fly the camera; the body gets an empty command with its aim pinned
float() TASJargon_InputFrame =
{
	if (!jg_fly) return FALSE;
	jg_move = input_movevalues; jg_btn = input_buttons;
	input_movevalues = '0 0 0'; input_buttons = 0; input_angles = jg_bodyang;
	return TRUE;
};
// the view, beside Ghost_Frame: the camera flown, the body drawn where it waits
void() TASJargon_FlyFrame =
{
	local float dt;
	if (!jg_fly) return;
	if (rec_gh_on || rec_wt_on || rw_on || Spec_Active() || !LT_StatsAreMine()) { TASJargon_FlyCancel(TRUE); return; }
	dt = cltime - jg_flyt;
	if (dt < 0 || dt > 0.5) dt = 0;
	jg_flyt = cltime;
	jg_camorg = Ghost_Fly(jg_camorg, getproperty(VF_CL_VIEWANGLES), jg_move, jg_btn, dt);
	setproperty(VF_ORIGIN, jg_camorg);
	Ghost_DrawBodyAt((pmove_org != '0 0 0') ? pmove_org : jg_camorg - '0 0 64', jg_bodyang_y);
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
	if (jg_fly && evtype == IE_KEYDOWN && scanx == K_ESCAPE) { TASJargon_EditEnd(); return TRUE; }
	if (evtype == IE_KEYUP && scanx == K_MOUSE2 && jg_m2) { jg_m2 = FALSE; return TRUE; }
	if (evtype == IE_KEYUP && scanx == K_MOUSE1 && jg_m1 && jg_drag < 0) { jg_m1 = FALSE; return TRUE; }
	if (!jg_edit) return FALSE;
	if (taso_state == 1 && jg_drag < 0) return FALSE;   // armed or running: no new drag (review 1528)
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
		if (jg_drag == jgw_sel) jgw_selo = jg_pos;
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
// hovered, selected in the panel, or the one a running chain works on: its ramp lit, its handle big
float(float i) TASJargon_Lit = { return (i == jg_hover || i == jgw_sel || (taso_state == 1 && i == taso_i)); };
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
				for (j = 0; j < np; j = j + 1) R_PolygonVertex(getsurfacepoint(world, s, j) + jg_nn[i] * 0.5, '0.5 0 0', col, TASJargon_Lit(i) ? 0.3 : 0.14);
				R_EndPolygon();
				for (j = 0; j < np; j = j + 1)
					TASJargon_Seg(getsurfacepoint(world, s, j) + jg_nn[i], getsurfacepoint(world, s, (j + 1) % np) + jg_nn[i], col, 0.85);
			}
		}
		// the handle: a cube on a post (zone_edit's look), bigger under the crosshair
		h = (i == jg_drag || TASJargon_Lit(i)) ? 14 : 8;
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
	else s = "Editing the route: fly with your movement keys, aim at a handle and drag it -- Esc goes back to the panel";
	w = stringwidth(s, TRUE, [tsz, tsz]);
	at = [rint((scr_x - w) * 0.5), rint(scr_y * 0.84), 0];
	sui_roundbox(at - [12, 6, 0], [w + 24, tsz + 12, 0], 6, SUI_THEME_PANEL, 0.8);
	sui_text(at, [tsz, tsz], s, (jg_drag >= 0 || jg_hover >= 0) ? SUI_THEME_ACCENT : SUI_THEME_DIM, 1, 0);
	Font_Set(f0);
};
