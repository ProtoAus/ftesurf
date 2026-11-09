/*
  P1449: the surf line editor's Optimizer tab -- `tas autosurf` and the one-stretch optimizer without
  their commands. The server reports autosurf's state as TAS_EV_AUTOSURF (sv_tasautosurf.qc).
*/
float taso_state, taso_i, taso_n, taso_try, taso_backs;
string taso_note;
var float taso_tube = 300, taso_look = 100, taso_tries = 2, taso_backmax = 6, taso_hop = 1, taso_finish = 0;
var float taso_ticks = 300;
float taso_startpause;          // `tas autosurf startpause` as last pressed here (the server toggles and says so)
float taso_listed;              // the demo list was searched for this map
string taso_listmap;
#define TASO_DEMOS 8
string taso_demo[TASO_DEMOS];
float taso_demon, taso_pick;

void() TASAuto_Event =
{
	taso_state = readbyte(); taso_i = readshort(); taso_n = readshort();
	taso_try = readbyte(); taso_backs = readbyte();
	if (taso_note != "") strunzone(taso_note);
	taso_note = strzone(readstring());
};

// A name the console line can carry whole: letters, digits, _ - . / (the server's own rule, review).
float(string f) TASOptUI_SafeName =
{
	local float i, c;
	if (strstrofs(f, "..") >= 0) return FALSE;      // the forwarder and SV_TASDemoPathOK refuse it (review)
	for (i = 0; i < strlen(f); i = i + 1)
	{
		c = str2chr(f, i);
		if (!((c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || c == 95 || c == 45 || c == 46 || c == 47)) return FALSE;
	}
	return f != "";
};

// A data/ recording unless its header names another map (autosurf refuses those: SV_TASAutoRead).
float(string f) TASOptUI_ThisMap =
{
	local float fh, i, c;
	local string line;
	fh = fopen(f, FILE_READ);
	if (fh < 0) return FALSE;
	for (i = 0; i < 64; i = i + 1)
	{
		line = fgets(fh);
		if (line == "") continue;
		c = tokenize(line);
		if (argv(0) == "map" && c >= 2) { fclose(fh); return !strcasecmp(argv(1), zone_mapname); }
		if (c >= 7 && FS_TASNumber(argv(0))) break;     // the samples began without a map line
	}
	fclose(fh);
	return TRUE;
};

// This map's KSF replays (cfg/ksfreplays/ksf_<map without surf_>_<runner>.rec), searched once a map.
void() TASOptUI_List =
{
	local float h, i, n;
	local string m, f, pre;
	if (taso_listed && taso_listmap == zone_mapname) return;
	for (i = 0; i < taso_demon; i = i + 1) strunzone(taso_demo[i]);
	taso_demon = 0; taso_pick = 0;
	if (taso_listmap != "") strunzone(taso_listmap);
	taso_listmap = strzone(zone_mapname); taso_listed = TRUE;
	m = strtolower(zone_mapname);
	if (substring(m, 0, 5) == "surf_") m = substring(m, 5, -1);
	pre = strcat("ksf_", m, "_");
	h = search_begin("cfg/ksfreplays/*.rec", TRUE, TRUE);
	if (h >= 0)
	{
		n = search_getsize(h);
		for (i = 0; i < n && taso_demon < TASO_DEMOS; i = i + 1)
		{
			f = search_getfilename(h, i);
			if (strstrofs(strtolower(f), pre) >= 0 && TASOptUI_SafeName(f)) { taso_demo[taso_demon] = strzone(f); taso_demon = taso_demon + 1; }
		}
		search_end(h);
	}
	h = search_begin("data/*.rec", TRUE, TRUE);      // a recording of your own put in data/ (autosurf refuses another map's)
	if (h >= 0)
	{
		n = search_getsize(h);
		for (i = 0; i < n && taso_demon < TASO_DEMOS; i = i + 1)
		{
			f = search_getfilename(h, i);
			if (TASOptUI_SafeName(f) && TASOptUI_ThisMap(f)) { taso_demo[taso_demon] = strzone(f); taso_demon = taso_demon + 1; }
		}
		search_end(h);
	}
};

void(float v) TASOptUI_Tube = { taso_tube = rint(v / 10) * 10; };
void(float v) TASOptUI_Look = { taso_look = rint(v / 10) * 10; };
void(float v) TASOptUI_Tries = { taso_tries = rint(v); };
void(float v) TASOptUI_Backs = { taso_backmax = rint(v); };
void(float v) TASOptUI_Ticks = { taso_ticks = rint(v / 10) * 10; };

// The target where the crosshair points: the face it hits when that is a surf slope.
void() TASOptUI_Target =
{
	local vector o, n;
	o = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	traceline(o, o + v_forward * 16384, MOVE_NOMONSTERS, world);
	if (trace_fraction >= 1) { print("tas: the crosshair is on nothing to aim at\n"); return; }
	n = trace_plane_normal;
	if (fabs(n_z) >= 0.1 && fabs(n_z) <= 0.72)
		localcmd(sprintf("tas target %.1f %.1f %.1f 300 %.4f %.4f %.4f\n", trace_endpos_x, trace_endpos_y, trace_endpos_z, n_x, n_y, n_z));
	else
		localcmd(sprintf("tas target %.1f %.1f %.1f 200\n", trace_endpos_x, trace_endpos_y, trace_endpos_z));
};

void(vector at, float width, float tsz, float hint, float row) TASOptUI_Draw =
{
	local float i, half, running;
	local vector chip;
	local string label;
	TASOptUI_List();
	running = (taso_state == 1);
	half = (width - 6) / 2; chip = [half, row, 0];
	sui_text(at, [tsz, tsz], "Autosurf a demo's route", SUI_THEME_TEXT, 1, 0); at_y = at_y + tsz * 1.6;
	label = (taso_note == "") ? "Pause on a demo's route (or prestrafe out of the start box with the pause below on), pick the demo, press Autosurf." : taso_note;
	if (running) label = sprintf("Stretch %g of %g, try %g, %g backtracks -- %s", taso_i + 1, taso_n, taso_try + 1, taso_backs, taso_note);
	sui_text(at, [hint, hint], label, running ? SUI_THEME_TEXT : SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.8;
	if (!taso_demon) { sui_text(at, [hint, hint], "No replay for this map in cfg/ksfreplays or data/.", SUI_THEME_MUTED, 1, 0); at_y = at_y + hint * 1.8; }
	for (i = 0; i < taso_demon; i = i + 1)
	{
		label = taso_demo[i];
		if (substring(label, 0, 15) == "cfg/ksfreplays/") label = substring(label, 15, -1);
		if (Profile_Chip(sprintf("taso_demo%g", i), at + [(i & 1) * (half + 6), floor(i / 2) * (row + 3), 0], chip, label, hint, taso_pick == i))
			taso_pick = i;
	}
	at_y = at_y + ceil(taso_demon / 2) * (row + 3) + hint * 0.6;
	WPU_Slider("taso_tube", "Route tube (u)", at, width, taso_tube, '100 600 50', TASOptUI_Tube, tsz); at_y = at_y + tsz * 2.2;
	WPU_Slider("taso_look", "Look ahead", at, width, taso_look, '0 200 20', TASOptUI_Look, tsz); at_y = at_y + tsz * 2.2;
	WPU_Slider("taso_tries", "Tries", at, width, taso_tries, '1 5 4', TASOptUI_Tries, tsz); at_y = at_y + tsz * 2.2;
	WPU_Slider("taso_backs", "Backtracks", at, width, taso_backmax, '0 12 12', TASOptUI_Backs, tsz); at_y = at_y + tsz * 2.2;
	if (Profile_Chip("taso_hop", at, chip, taso_hop ? "Bhop platforms: hop" : "Bhop platforms: off", hint, taso_hop)) taso_hop = !taso_hop;
	if (Profile_Chip("taso_finish", at + [half + 6, 0, 0], chip, taso_finish ? "To the end zone" : "Ramps only", hint, taso_finish)) taso_finish = !taso_finish;
	at_y = at_y + row + 3;
	if (Profile_Chip("taso_startp", at, [width, row, 0], taso_startpause ? "Pause on leaving the start box: on" : "Pause on leaving the start box: off", hint, taso_startpause))
		{ taso_startpause = !taso_startpause; localcmd("tas autosurf startpause\n"); }
	at_y = at_y + row + 3;
	if (Profile_Chip("taso_viz", at, [width, row, 0], cvar("tas_viz") ? "Search lines shown" : "Search lines hidden", hint, cvar("tas_viz")))
		localcmd(cvar("tas_viz") ? "set tas_viz 0\n" : "set tas_viz 1\n");
	at_y = at_y + row + hint;
	if (running)
	{
		if (Profile_Chip("taso_stop", at, [width, row, 0], "Stop autosurf", tsz, TRUE)) localcmd("tas autosurf stop\n");
	}
	else if (taso_demon && Profile_Chip("taso_go", at, [width, row, 0], "Autosurf from here", tsz, FALSE))
		localcmd(sprintf("tas autosurf %s tube %g look %g tries %g backs %g%s%s\n", taso_demo[taso_pick], taso_tube, taso_look,
			taso_tries, taso_backmax, taso_hop ? "" : " nohop", taso_finish ? " finish" : ""));
	at_y = at_y + row + hint * 1.4;
	sui_text(at, [tsz, tsz], "One stretch", SUI_THEME_TEXT, 1, 0); at_y = at_y + tsz * 1.6;
	sui_text(at, [hint, hint], "Aim at a ramp's face (or a point), set the target, then optimize toward it.", SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.8;
	if (Profile_Chip("taso_target", at, chip, "Target at crosshair", hint, FALSE)) TASOptUI_Target();
	if (Profile_Chip("taso_clear", at + [half + 6, 0, 0], chip, "Clear target", hint, FALSE)) localcmd("tas target clear\n");
	at_y = at_y + row + 3;
	WPU_Slider("taso_ticks", "Search ticks", at, width, taso_ticks, '50 760 71', TASOptUI_Ticks, tsz); at_y = at_y + tsz * 2.2;
	if (Profile_Chip("taso_opt", at, [width, row, 0], sprintf("Optimize toward the target (%g ticks)", taso_ticks), hint, FALSE))
		localcmd(sprintf("tas optimize %g left curve 12 aim energy fast\n", taso_ticks));
};
