/*
  P1449: the surf line editor's Optimizer tab -- `tas autosurf` and the one-stretch optimizer without
  their commands. The server reports autosurf's state as TAS_EV_AUTOSURF (sv_tasautosurf.qc).
*/
float taso_state, taso_i, taso_n, taso_try, taso_backs;
string taso_note;
var float taso_tube = 300, taso_look = 100, taso_tries = 2, taso_backmax = 0, taso_hop = 1, taso_finish = 0;   // backs 0: auto
var float taso_ticks = 300;
float taso_listed;              // the demo list was searched for this map
string taso_listmap;
#define TASO_DEMOS 12
string taso_demo[TASO_DEMOS];
float taso_demon, taso_pick;
float taso_adv;                 // the advanced settings and one-stretch tools shown
#define TASO_STRETCHES 64
float taso_rb[TASO_STRETCHES], taso_rf[TASO_STRETCHES];   // each reached stretch: speed at farsh's board height, and his (0: none)
var float taso_lastk = -1;          // the stretch last reached (the line under the strip)

// P1449 search panel (TAS_EV_SEARCH, sv_tasoptimize.qc SV_TASOptStatsSend): what a curve search is doing, over the
// game, for fun and for seeing how it works (Lex, 10 Nov). tas_searchpanel 0 hides it; it shows while searches
// report and a few seconds after.
var float autocvar_tas_searchpanel = 1;
float tsp_t, tsp_phase, tsp_flags, tsp_gen, tsp_evals, tsp_elapsed, tsp_speed, tsp_ref, tsp_closest;
float tsp_tube, tsp_wall, tsp_weak, tsp_edge, tsp_cut, tsp_batches, tsp_bwork, tsp_aimx, tsp_aimy, tsp_lead, tsp_from, tsp_bal, tsp_bup, tsp_n;
#define TSP_HIST 48
float tsp_hist[TSP_HIST];   // the best line's speed after each generation, this search
float tsp_histn;
void() TASSearch_Event =
{
	local float evals0, i;
	evals0 = tsp_evals;
	tsp_phase = readbyte(); tsp_flags = readbyte();
	tsp_gen = readshort(); tsp_evals = readshort(); tsp_elapsed = readfloat();
	tsp_speed = readshort(); tsp_ref = readshort(); tsp_closest = readshort();
	tsp_tube = readshort(); tsp_wall = readshort(); tsp_weak = readshort(); tsp_edge = readshort(); tsp_cut = readshort();
	tsp_batches = readshort(); tsp_bwork = readshort();
	tsp_aimx = readshort(); tsp_aimy = readshort(); tsp_lead = readbyte() / 100; tsp_from = readshort();
	tsp_bal = readshort(); tsp_bup = readshort(); tsp_n = readshort();
	if (tsp_evals < evals0 || !tsp_t) tsp_histn = 0;      // a new search
	if (tsp_histn == TSP_HIST)
	{
		for (i = 1; i < TSP_HIST; i = i + 1) tsp_hist[i - 1] = tsp_hist[i];
		tsp_histn = TSP_HIST - 1;
	}
	tsp_hist[tsp_histn] = tsp_speed; tsp_histn = tsp_histn + 1;
	tsp_t = time;
};

string(float lead) TASSearch_LeadWord =
{
	if (lead < 0.15) return "straight at it";
	if (lead < 0.4) return "fairly direct";
	if (lead <= 0.6) return "along the face";
	return "wide";
};

void(vector scr) TASSearch_Draw =
{
	local float tsz, w, row, h, x, y, i, n, lo, hi, v, k;
	local vector at, col;
	local string s;
	if (!autocvar_tas_searchpanel || !tsp_t || time < tsp_t || time - tsp_t > 8) return;
	tsz = bound(11, scr_y / 72, 20); row = tsz * 1.55; w = tsz * 33;
	h = row * 9.6;
	at = [16, floor(scr_y * 0.24), 0];
	sui_roundbox(at - [8, 8, 0], [w + 16, h + 16, 0], 8, SUI_THEME_PANEL, 0.86);
	y = at_y;
	// the title, and a scanning dot while it searches
	sui_text([at_x, y, 0], [tsz * 1.1, tsz * 1.1], "SEARCH", SUI_THEME_ACCENT, 1, 0);
	s = (tsp_phase == 2) ? sprintf("done: %g generations, %.1f s", max(0, tsp_gen), tsp_elapsed)
		: ((tsp_gen < 0) ? sprintf("seeding grid, %.1f s", tsp_elapsed) : sprintf("generation %g, %.1f s", tsp_gen, tsp_elapsed));
	sui_text([at_x + tsz * 6.5, y + tsz * 0.1, 0], [tsz, tsz], s, SUI_THEME_DIM, 1, 0);
	if (tsp_phase != 2 && time - tsp_t < 3)
	{
		x = at_x + w - tsz * 4 + (tsz * 3.6) * (0.5 + 0.5 * sin(time * 4));
		drawfill([x, y + tsz * 0.35, 0], [tsz * 0.4, tsz * 0.4, 0], SUI_THEME_ACCENT, 0.9, 0);
	}
	y = y + row * 1.15;
	// where
	if (taso_state == 1)
		s = sprintf("Stretch %g of %g, try %g, %g backtracks so far", taso_i + 1, taso_n, taso_try + 1, taso_backs);
	else s = "One stretch";
	sui_text([at_x, y, 0], [tsz, tsz], s, SUI_THEME_TEXT, 1, 0); y = y + row;
	// how much
	s = sprintf("%g candidates, %g a second", tsp_evals, rint(tsp_evals / max(0.1, tsp_elapsed)));
	s = strcat(s, (tsp_flags & 16) ? sprintf(", %g of them on worker threads", tsp_bwork) : ", one thread");
	sui_text([at_x, y, 0], [tsz, tsz], s, SUI_THEME_DIM, 1, 0); y = y + row;
	// the best so far
	if (tsp_flags & 1)
	{
		s = sprintf("Best line makes it at %g u/s", tsp_speed);
		if (tsp_ref > 0) s = strcat(s, sprintf(" (farsh %g, %s%g)", tsp_ref, (tsp_speed >= tsp_ref) ? "+" : "", tsp_speed - tsp_ref));
		col = (tsp_ref > 0 && tsp_speed < tsp_ref * 0.98) ? SUI_THEME_WARN : SUI_THEME_GOOD;
	}
	else if (tsp_flags & 2) { s = sprintf("Best line makes it, but too slowly: %g u/s", tsp_speed); col = SUI_THEME_WARN; }
	else { s = sprintf("Nothing makes it yet: the best try misses by %g u", tsp_closest); col = SUI_THEME_BAD; }
	sui_text([at_x, y, 0], [tsz, tsz], s, col, 1, 0); y = y + row;
	// what it tunes on that line
	if (tsp_flags & 1)
	{
		if (tsp_bal || tsp_bup)
			s = sprintf("Boards %g u %s and %g u %s farsh's point", fabs(tsp_bal), (tsp_bal >= 0) ? "past" : "before", fabs(tsp_bup), (tsp_bup >= 0) ? "above" : "below");
		else s = "Boards at farsh's point";
		sui_text([at_x, y, 0], [tsz, tsz], s, SUI_THEME_DIM, 1, 0);
	}
	y = y + row;
	s = sprintf("Aims %+g, %+g u off the board, %s (lead %.2f)", tsp_aimx, tsp_aimy, TASSearch_LeadWord(tsp_lead), tsp_lead);
	if (tsp_from) s = strcat(s, sprintf(", steering from tick %g of %g", tsp_from, tsp_n));
	sui_text([at_x, y, 0], [tsz * 0.9, tsz * 0.9], s, SUI_THEME_MUTED, 1, 0); y = y + row;
	// why candidates fail
	n = max(1, tsp_evals);
	x = at_x;
	for (k = 0; k < 5; k = k + 1)
	{
		v = (k == 0) ? tsp_tube : ((k == 1) ? tsp_wall : ((k == 2) ? tsp_weak : ((k == 3) ? tsp_edge : tsp_cut)));
		col = (k == 0) ? SUI_THEME_INFO : ((k == 1) ? SUI_THEME_BAD : ((k == 2) ? SUI_THEME_WARN : ((k == 3) ? SUI_THEME_ACCENT : SUI_THEME_MUTED)));
		v = min(w - (x - at_x), w * v / n);
		if (v > 0) drawfill([x, y, 0], [v, tsz * 0.55, 0], col, 0.9, 0);
		x = x + v;
	}
	drawfill([x, y, 0], [max(0, w - (x - at_x)), tsz * 0.55, 0], SUI_THEME_WELL, 0.9, 0);
	y = y + tsz * 0.8;
	s = sprintf("left corridor %g%%, walls %g%%, too slow %g%%", rint(100 * tsp_tube / n), rint(100 * tsp_wall / n), rint(100 * tsp_weak / n));
	s = strcat(s, sprintf(", edge bug %g%%, trigger %g%%", rint(100 * tsp_edge / n), rint(100 * tsp_cut / n)));
	sui_text([at_x, y, 0], [tsz * 0.85, tsz * 0.85], s, SUI_THEME_MUTED, 1, 0); y = y + row;
	// the best line's speed, generation by generation
	if (tsp_histn >= 2)
	{
		lo = 1000000; hi = -1000000;
		for (i = 0; i < tsp_histn; i = i + 1) { lo = min(lo, tsp_hist[i]); hi = max(hi, tsp_hist[i]); }
		if (tsp_ref > 0) { lo = min(lo, tsp_ref); hi = max(hi, tsp_ref); }
		hi = max(hi, lo + 1);
		for (i = 0; i < tsp_histn; i = i + 1)
		{
			v = (tsp_hist[i] - lo) / (hi - lo) * tsz * 1.6 + 1;
			drawfill([at_x + i * (w / TSP_HIST), y + tsz * 1.7 - v, 0], [max(1, w / TSP_HIST - 1), v, 0], SUI_THEME_GOOD, 0.8, 0);
		}
		if (tsp_ref > 0)
			drawfill([at_x, y + tsz * 1.7 - ((tsp_ref - lo) / (hi - lo) * tsz * 1.6 + 1), 0], [w, 1, 0], SUI_THEME_WARN, 0.9, 0);
	}
};

void() TASAuto_Event =
{
	local float was, wasi, rk, rb, rf, k, i;
	was = taso_state; wasi = taso_i;
	taso_state = readbyte(); taso_i = readshort(); taso_n = readshort();
	taso_try = readbyte(); taso_backs = readbyte();
	if (taso_note != "") strunzone(taso_note);
	taso_note = strzone(readstring());
	rk = readshort(); rb = readshort(); rf = readshort();
	if (taso_state == 1 && was != 1) { for (k = 0; k < TASO_STRETCHES; k = k + 1) taso_rb[k] = taso_rf[k] = 0; taso_lastk = -1; }
	else if (taso_state == 1 && taso_i < wasi)      // a backtrack: what came after it is to be done again
		for (k = taso_i; k < TASO_STRETCHES; k = k + 1) taso_rb[k] = taso_rf[k] = 0;
	if (rk >= 0 && rk < TASO_STRETCHES) { taso_rb[rk] = rb; taso_rf[rk] = (rf > 0) ? rf : -1; taso_lastk = rk; }   // -1: a route point
	if (substring(taso_note, 0, 12) == "your route: ")
	{	// the server's count; a taken add's note carries its point ("N points, added x y z nx ny nz"), every other
		// note only trims (an undo, a clear) -- the markers are the server's route, typed adds included (review 6).
		// tokenize_console: tokenize splits off ':' and ',' (review 7). Slots this tab never saw (a reconnect, another
		// player's adds) are kind 0 and not drawn; the count still follows the server's (review 8).
		k = tokenize_console(taso_note);
		rk = stof(argv(2));
		if (k >= 11 && argv(4) == "added" && rk >= 1 && rk <= TOV_ROUTE)
		{
			for (i = tov_rn; i < rk - 1; i = i + 1) tov_rk[i] = 0;
			tov_rp[rk - 1] = [stof(argv(5)), stof(argv(6)), stof(argv(7))];
			tov_rk[rk - 1] = (stof(argv(10)) >= 0.99) ? 2 : ((stof(argv(8)) == 0 && stof(argv(9)) == 0 && stof(argv(10)) == 0) ? 3 : 1);
			tov_rn = rk;
		}
		else tov_rn = min(tov_rn, max(0, rk));
		strunzone(taso_note);                      // the status line: the count, not the coordinates
		taso_note = strzone(sprintf("your route: %g points", rk));
	}
};

// One box a stretch: mint at or above farsh's speed there (within 2%), butter within 10%, rose below (a reach
// the minimum would let through), dim to come; the current stretch outlined.
void(vector at, float width, float h) TASOptUI_Strip =
{
	local float k, w, r;
	local vector c;
	if (taso_n < 1) return;
	w = width / taso_n;
	for (k = 0; k < taso_n && k < TASO_STRETCHES; k = k + 1)
	{
		c = SUI_THEME_CHIP;
		if (taso_rf[k] > 0)
		{
			r = taso_rb[k] / taso_rf[k];
			c = (r >= 0.98) ? SUI_THEME_GOOD : ((r >= 0.9) ? SUI_THEME_WARN : SUI_THEME_BAD);
		}
		else if (taso_rf[k] < 0) c = SUI_THEME_GOOD;            // a route point reached
		if (k == taso_i && taso_state == 1) sui_roundbox(at + [k * w, 0, 0], [w - 2, h, 0], h * 0.3, SUI_THEME_ACCENT, 1);
		sui_roundbox(at + [k * w + 1, 1, 0], [w - 4, h - 2, 0], h * 0.3, c, (taso_rf[k] != 0) ? 0.9 : 1);
	}
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
	local float h, i, n, c, k;
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
	// this map's leaderboard and Momentum replays (data/online, data/momentum: the same .rec rows), three of each,
	// fastest first (their names start with the time or rank; SB_NAMESORT 32)
	for (i = 0; i < 2; i = i + 1)
	{
		h = search_begin(sprintf("data/%s/%s/main/*.rec", i ? "momentum" : "online", zone_mapname), 33, TRUE);
		if (h < 0) continue;
		n = search_getsize(h); k = 0;
		for (c = 0; c < n && k < 3 && taso_demon < TASO_DEMOS; c = c + 1)
		{
			f = search_getfilename(h, c);
			if (strstrofs(f, "_dnf") >= 0) continue;      // an abandoned run's short time is not the fastest (review)
			if (TASOptUI_SafeName(f)) { taso_demo[taso_demon] = strzone(f); taso_demon = taso_demon + 1; k = k + 1; }
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

// A route point where the crosshair points: a surf face to board, a floor to bhop on, else a point.
void() TASOptUI_RouteAdd =
{
	local vector o, n;
	o = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	traceline(o, o + v_forward * 16384, MOVE_NOMONSTERS, world);
	if (trace_fraction >= 1) { print("tas route: the crosshair is on nothing\n"); return; }
	n = trace_plane_normal;
	if (tov_rn >= TOV_ROUTE) { print("tas route: 64 points at most\n"); return; }
	if (fabs(n_z) >= 0.1 && fabs(n_z) <= 0.72) localcmd(sprintf("tas route add %.1f %.1f %.1f %.4f %.4f %.4f\n", trace_endpos_x, trace_endpos_y, trace_endpos_z, n_x, n_y, n_z));
	else if (n_z > 0.72) localcmd(sprintf("tas route add %.1f %.1f %.1f 0 0 1\n", trace_endpos_x, trace_endpos_y, trace_endpos_z + 1));
	else localcmd(sprintf("tas route add %.1f %.1f %.1f 0 0 0\n", trace_endpos_x, trace_endpos_y, trace_endpos_z));
};

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
	local string label, bs;
	TASOptUI_List();
	bs = taso_backmax ? sprintf(" backs %g", taso_backmax) : "";      // 0: autosurf's own (twice the stretches)
	running = (taso_state == 1);
	half = (width - 6) / 2; chip = [half, row, 0];
	sui_text(at, [tsz, tsz], "Autosurf", SUI_THEME_TEXT, 1, 0); at_y = at_y + tsz * 1.6;
	label = (taso_note == "") ? "Pick a replay, then how to start. The bot surfs its route, ramp by ramp." : taso_note;
	if (running) label = sprintf("Ramp %g of %g, try %g -- %s", taso_i + 1, taso_n, taso_try + 1, taso_note);
	sui_text(at, [hint, hint], label, running ? SUI_THEME_TEXT : SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.8;
	if (!taso_demon) { sui_text(at, [hint, hint], "No replay for this map in cfg/ksfreplays or data/.", SUI_THEME_MUTED, 1, 0); at_y = at_y + hint * 1.8; }
	for (i = 0; i < taso_demon; i = i + 1)
	{
		label = taso_demo[i];
		if (substring(label, 0, 15) == "cfg/ksfreplays/") label = substring(label, 15, -1);
		else if (substring(label, 0, 12) == "data/online/") label = strcat("board ", substring(label, strstrofs(label, "/main/") + 6, -1));
		else if (substring(label, 0, 14) == "data/momentum/") label = strcat("momentum ", substring(label, strstrofs(label, "/main/") + 6, -1));
		if (Profile_Chip(sprintf("taso_demo%g", i), at + [(i & 1) * (half + 6), floor(i / 2) * (row + 3), 0], chip, label, hint, taso_pick == i))
			taso_pick = i;
	}
	at_y = at_y + ceil(taso_demon / 2) * (row + 3) + hint * 0.6;
	if (running)
	{
		if (Profile_Chip("taso_stop", at, [width, row, 0], "Stop autosurf", tsz, TRUE)) localcmd("tas autosurf stop\n");
	}
	else if (taso_demon)
	{	// from a pause on the demo's route, or from the start box: a legal start, guided prestrafe and one jump
		if (Profile_Chip("taso_go", at, chip, "From here (paused)", tsz, FALSE))
			localcmd(sprintf("tas autosurf %s tube %g look %g tries %g%s%s%s\n", taso_demo[taso_pick], taso_tube, taso_look,
				taso_tries, bs, taso_hop ? "" : " nohop", taso_finish ? " finish" : ""));
		if (Profile_Chip("taso_gostart", at + [half + 6, 0, 0], chip, "From the start box", tsz, FALSE))
			localcmd(sprintf("tas autosurf %s tube %g look %g tries %g%s%s%s start\n", taso_demo[taso_pick], taso_tube, taso_look,
				taso_tries, bs, taso_hop ? "" : " nohop", taso_finish ? " finish" : ""));
		at_y = at_y + row + 3;
		if (Profile_Chip("taso_gojump", at, chip, "On my jump", tsz, FALSE))
			localcmd(sprintf("tas autosurf %s tube %g look %g tries %g%s%s%s onjump\n", taso_demo[taso_pick], taso_tube, taso_look,
				taso_tries, bs, taso_hop ? "" : " nohop", taso_finish ? " finish" : ""));
		if (Profile_Chip("taso_goexit", at + [half + 6, 0, 0], chip, "On leaving the box", tsz, FALSE))
			localcmd(sprintf("tas autosurf %s tube %g look %g tries %g%s%s%s onexit\n", taso_demo[taso_pick], taso_tube, taso_look,
				taso_tries, bs, taso_hop ? "" : " nohop", taso_finish ? " finish" : ""));
	}
	at_y = at_y + row + hint;
	// your own route, no replay: ramps (and bhop floors) clicked in order, then surfed
	sui_text(at, [hint, hint], (tov_rn > 0) ? sprintf("Your route: %g points (aim at each ramp in order, then surf it)", tov_rn)
		: "Or click your own route: aim at each ramp (or bhop floor) in order and add it.", SUI_THEME_DIM, 1, 0);
	at_y = at_y + hint * 1.6;
	// nested ifs: && does not short-circuit here (logicops off), and Profile_Chip draws as it tests (review 4).
	// Undo and Clear move the count only by the server's reply, so a refused one changes nothing.
	if (!running)
	{
		if (Profile_Chip("taso_radd", at, chip, "Add at crosshair", hint, FALSE)) TASOptUI_RouteAdd();
		if (Profile_Chip("taso_rundo", at + [half + 6, 0, 0], chip, "Undo", hint, FALSE)) localcmd("tas route undo\n");
		at_y = at_y + row + 3;
		if (Profile_Chip("taso_rclear", at, chip, "Clear", hint, FALSE)) localcmd("tas route clear\n");
		if (tov_rn > 0)
			if (Profile_Chip("taso_rgo", at + [half + 6, 0, 0], chip, "Surf my route", tsz, FALSE))
				localcmd(sprintf("tas autosurf route tries %g%s%s\n", taso_tries, bs, taso_hop ? "" : " nohop"));
	}
	else at_y = at_y + row + 3;
	at_y = at_y + row + hint;
	if (taso_n > 0)
	{	// the run so far, a box a ramp or bhop platform
		TASOptUI_Strip(at, width, row * 0.6); at_y = at_y + row * 0.6 + hint * 0.5;
		if (taso_lastk >= 0)      // nested: && does not short-circuit here, and taso_rf[-1] is out of range
		{
			if (taso_rf[taso_lastk] < 0)
				label = sprintf("Point %g: %g u/s", taso_lastk + 1, taso_rb[taso_lastk]);
			else
				label = sprintf("Ramp %g: %g u/s, farsh %g (%s%g)", taso_lastk + 1, taso_rb[taso_lastk], taso_rf[taso_lastk],
					(taso_rb[taso_lastk] >= taso_rf[taso_lastk]) ? "+" : "", taso_rb[taso_lastk] - taso_rf[taso_lastk]);
			sui_text(at, [hint, hint], label, SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.6;
		}
	}
	if (Profile_Chip("taso_panel", at, [width, row, 0], autocvar_tas_searchpanel ? "Search panel: shown while searching" : "Search panel: hidden", hint, autocvar_tas_searchpanel))
		cvar_set("tas_searchpanel", autocvar_tas_searchpanel ? "0" : "1");
	at_y = at_y + row + hint * 0.5;
	if (Profile_Chip("taso_adv", at, [width, row, 0], taso_adv ? "Advanced settings (hide)" : "Advanced settings", hint, taso_adv)) taso_adv = !taso_adv;
	at_y = at_y + row + hint;
	if (!taso_adv) return;
	WPU_Slider("taso_tube", "Route tube (u)", at, width, taso_tube, '100 600 50', TASOptUI_Tube, tsz); at_y = at_y + tsz * 2.2;
	WPU_Slider("taso_look", "Look ahead", at, width, taso_look, '0 200 20', TASOptUI_Look, tsz); at_y = at_y + tsz * 2.2;
	WPU_Slider("taso_tries", "Tries", at, width, taso_tries, '1 5 4', TASOptUI_Tries, tsz); at_y = at_y + tsz * 2.2;
	WPU_Slider("taso_backs", taso_backmax ? "Backtracks" : "Backs: auto", at, width, taso_backmax, '0 40 40', TASOptUI_Backs, tsz); at_y = at_y + tsz * 2.2;
	if (Profile_Chip("taso_hop", at, chip, taso_hop ? "Bhop platforms: hop" : "Bhop platforms: off", hint, taso_hop)) taso_hop = !taso_hop;
	if (Profile_Chip("taso_finish", at + [half + 6, 0, 0], chip, taso_finish ? "To the end zone" : "Ramps only", hint, taso_finish)) taso_finish = !taso_finish;
	at_y = at_y + row + 3;
	if (Profile_Chip("taso_viz", at, [width, row, 0], cvar("tas_viz") ? "Search lines shown" : "Search lines hidden", hint, cvar("tas_viz")))
		localcmd(cvar("tas_viz") ? "set tas_viz 0\n" : "set tas_viz 1\n");
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
