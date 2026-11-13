/*
  P1449: the surf line editor's Optimizer tab -- `tas autosurf` and the one-stretch optimizer without
  their commands. The server reports autosurf's state as TAS_EV_AUTOSURF (sv_tasautosurf.qc).
*/
float taso_state, taso_i, taso_n, taso_try, taso_backs;
string taso_note;
var float taso_tube = 300, taso_look = 100, taso_tries = 2, taso_backmax = 0;   // backs 0: auto
var float taso_ticks = 300;
float taso_listed;              // the demo list was searched for this map
string taso_listmap;
#define TASO_DEMOS 12
string taso_demo[TASO_DEMOS];
float taso_demon, taso_pick;
#define TASO_STRETCHES 64
float taso_rb[TASO_STRETCHES], taso_rf[TASO_STRETCHES];   // each reached stretch: speed at farsh's board height, and his (0: none)
var float taso_lastk = -1;          // the stretch last reached (the line under the strip)
var float taso_sel = -1;            // the stretch picked under the strip to redo the run from
float taso_stale;               // the strip is another course's (a switch since its run): hidden until a run starts
// the guide run's name for the panel's lines (Lex: farsh's name was baked into Jargon)
string() TASOptUI_Guide = { return (jg_pick < jg_gn) ? jg_gl[jg_pick] : "the guide"; };

// P1449 search panel (TAS_EV_SEARCH, sv_tasoptimize.qc SV_TASOptStatsSend): what a curve search is doing, over the
// game, for fun and for seeing how it works (Lex, 10 Nov). tas_searchpanel 0 hides it; it shows while searches
// report and a few seconds after.
var float autocvar_tas_searchpanel = 1;
float tsp_t, tsp_phase, tsp_flags, tsp_gen, tsp_evals, tsp_elapsed, tsp_speed, tsp_ref, tsp_closest;
float tsp_tube, tsp_wall, tsp_weak, tsp_edge, tsp_cut, tsp_batches, tsp_bwork, tsp_aimx, tsp_aimy, tsp_lead, tsp_from, tsp_bal, tsp_bup, tsp_n;
float tsp_cegen, tsp_kstall, tsp_cestall, tsp_cemin;   // the generation cap, generations without a gain, the stall that ends it, the floor
float tsp_width, tsp_widen, tsp_mem;    // the spread against its start (%), re-widenings, an earlier search's line among the first
float tsp_brief;                        // boards that left the ramp at once
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
	tsp_cegen = readbyte(); tsp_kstall = readbyte(); tsp_cestall = readbyte(); tsp_cemin = readbyte();
	tsp_width = readbyte(); tsp_widen = readbyte(); tsp_mem = readbyte();
	tsp_brief = readshort();
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
	if (lead < 0.15) return "straight at the ramp";
	if (lead < 0.4) return "fairly directly at the ramp";
	if (lead <= 0.6) return "in along the ramp's face";
	return "wide of the ramp, turning in late";
};

// a line at a size the current face is baked at (Font_Px), a smaller rung when it does not fit w, on whole pixels:
// sizes scaled to fit drew every glyph resampled -- uneven spacing, doubled strokes (Lex, 10 Nov)
void(vector pos, string s, float sz, vector col, float w) TASSearch_Line =
{
	local float px, want;
	px = Font_Px(sz);
	for (want = px - 1; want >= 6 && stringwidth(s, TRUE, [px, px]) > w; want = want - 1)
		if (Font_Px(want) < px) px = Font_Px(want);
	sui_text([rint(pos_x), rint(pos_y), 0], [px, px], s, col, 1, 0);
};

// a labelled bar: what share of the candidates a reason ended
void(vector at, float w, float tsz, string label, float v, float n, vector col) TASSearch_Reason =
{
	local float lw, bw, f;
	lw = w * 0.52; bw = w - lw - tsz * 3.2;
	f = bound(0, v / max(1, n), 1);
	TASSearch_Line(at, label, tsz * 0.85, SUI_THEME_DIM, lw - tsz * 0.5);
	drawfill(at + [lw, tsz * 0.25, 0], [bw, tsz * 0.5, 0], SUI_THEME_WELL, 0.9, 0);
	if (f > 0) drawfill(at + [lw, tsz * 0.25, 0], [max(1, bw * f), tsz * 0.5, 0], col, 0.95, 0);
	TASSearch_Line(at + [lw + bw + tsz * 0.4, 0, 0], sprintf("%g%%", rint(100 * f)), tsz * 0.85, SUI_THEME_MUTED, tsz * 2.8);
};

void(vector scr) TASSearch_Draw =
{
	local float tsz, w, row, h, x, y, i, lo, hi, v, f0, cap;
	local vector at, col;
	local string s;
	if (!autocvar_tas_searchpanel || !tsp_t || time < tsp_t || time - tsp_t > 8) return;
	f0 = ui_font_cur;
	Font_Set(ui_font_ui);
	tsz = Font_Px(bound(11, scr_y / 72, 20)); row = rint(tsz * 1.5); w = rint(tsz * 30);
	h = row * 18.6;
	at = [16, floor(scr_y * 0.2), 0];
	sui_roundbox(at - [8, 8, 0], [w + 16, h + 16, 0], 8, SUI_THEME_PANEL, 0.88);
	y = at_y;
	// who, and whether it is thinking
	v = Font_Px(tsz * 1.15);
	TASSearch_Line([at_x, y, 0], "JARGON", v, SUI_THEME_ACCENT, w);
	x = rint(stringwidth("JARGON", TRUE, [v, v]) + tsz);
	if (tsp_phase == 2) s = sprintf("done in %.1f s", tsp_elapsed);
	else if (time - tsp_t > 3) s = "waiting";
	else s = (tsp_gen < 0) ? "thinking: trying a spread of first guesses" : "thinking";
	TASSearch_Line([at_x + x, y + tsz * 0.12, 0], s, tsz, (tsp_phase == 2) ? SUI_THEME_GOOD : SUI_THEME_DIM, w - x - tsz * 2);
	if (tsp_phase != 2 && time - tsp_t < 3)
		drawfill([at_x + w - tsz * 1.2 + tsz * 0.5 * sin(time * 6), y + tsz * 0.35, 0], [tsz * 0.4, tsz * 0.4, 0], SUI_THEME_ACCENT, 0.9, 0);
	y = y + row * 1.2;
	// progress: generations against the cap, and the stall that ends it early
	cap = max(1, tsp_cegen);
	drawfill([at_x, y, 0], [w, tsz * 0.5, 0], SUI_THEME_WELL, 0.9, 0);
	drawfill([at_x, y, 0], [w * bound(0, max(0, tsp_gen) / cap, 1), tsz * 0.5, 0], SUI_THEME_ACCENT, 0.95, 0);
	y = y + tsz * 0.8;
	if (tsp_gen < 0) s = sprintf("First guesses: %g tried", tsp_evals);
	else s = sprintf("Generation %g of %g at most", tsp_gen, cap);
	if (tsp_phase == 2)
		s = (tsp_gen >= cap) ? sprintf("Stopped: used all %g generations", cap)
			: sprintf("Stopped: %g generations without a gain", tsp_cestall);
	TASSearch_Line([at_x, y, 0], s, tsz * 0.85, SUI_THEME_MUTED, w); y = y + row * 0.8;
	s = "";
	if (tsp_phase != 2 && tsp_gen >= 0 && (tsp_flags & 1) && tsp_gen < tsp_cemin) s = sprintf("May end early from generation %g", tsp_cemin);
	else if (tsp_phase != 2 && tsp_gen >= 0 && (tsp_flags & 1)) s = sprintf("Ends after %g without a gain (%g so far)", tsp_cestall, tsp_kstall);
	else if (tsp_phase != 2 && tsp_gen >= 0) s = "Ends early only once a line makes it";
	TASSearch_Line([at_x, y, 0], s, tsz * 0.85, SUI_THEME_MUTED, w); y = y + row * 0.8;
	// how wide it still looks: it narrows on the best lines, 4 of 20 stay wide, and it re-widens when stuck
	s = sprintf("Searching %g%% as wide as it started", tsp_width);
	if (tsp_mem) s = strcat(s, ", from its best line here");
	TASSearch_Line([at_x, y, 0], s, tsz * 0.85, SUI_THEME_MUTED, w); y = y + row * 0.8;
	s = "4 of 20 lines a generation stay wide";
	if (tsp_widen) s = strcat(s, sprintf("; re-widened %g time%s", tsp_widen, (tsp_widen == 1) ? "" : "s"));
	TASSearch_Line([at_x, y, 0], s, tsz * 0.85, SUI_THEME_MUTED, w); y = y + row;
	// where in the chain
	if (taso_state == 1 && taso_n > 0)
	{
		s = sprintf("Stretch %g of %g, try %g, %g backtracks so far", taso_i + 1, taso_n, taso_try + 1, taso_backs);
		TASSearch_Line([at_x, y, 0], s, tsz, SUI_THEME_TEXT, w);
		y = y + tsz * 1.25;
		drawfill([at_x, y, 0], [w, tsz * 0.3, 0], SUI_THEME_WELL, 0.9, 0);
		drawfill([at_x, y, 0], [w * bound(0, taso_i / taso_n, 1), tsz * 0.3, 0], SUI_THEME_GOOD, 0.9, 0);
		y = y + row * 0.55;
	}
	else { TASSearch_Line([at_x, y, 0], "One stretch", tsz, SUI_THEME_TEXT, w); y = y + row; }
	// how much
	s = sprintf("%g candidate lines, %g a second", tsp_evals, rint(tsp_evals / max(0.1, tsp_elapsed)));
	s = strcat(s, (tsp_flags & 16) ? sprintf(", %g rollouts on other cores", tsp_bwork) : ", one core");
	TASSearch_Line([at_x, y, 0], s, tsz * 0.9, SUI_THEME_DIM, w); y = y + row;
	// the best so far
	if (tsp_flags & 1)
	{
		s = sprintf("Best line makes it with energy %g", tsp_speed);
		if (tsp_ref > 0) s = strcat(s, sprintf(" (%s %g, %s%g)", TASOptUI_Guide(), tsp_ref, (tsp_speed >= tsp_ref) ? "+" : "", tsp_speed - tsp_ref));
		col = (tsp_ref > 0 && tsp_speed < tsp_ref * 0.98) ? SUI_THEME_WARN : SUI_THEME_GOOD;
	}
	else if (tsp_flags & 64) { s = "Best line boards, then falls off the ramp"; col = SUI_THEME_WARN; }
	else if (tsp_flags & 2) { s = sprintf("Best line makes it, but with too little energy: %g", tsp_speed); col = SUI_THEME_WARN; }
	else { s = sprintf("Nothing makes it yet: the closest misses by %g u", tsp_closest); col = SUI_THEME_BAD; }
	TASSearch_Line([at_x, y, 0], s, tsz, col, w); y = y + row;
	if (tsp_flags & 1)
	{
		if (tsp_bal || tsp_bup)
			s = sprintf("Boards %g u %s and %g u %s the guide's point", fabs(tsp_bal), (tsp_bal >= 0) ? "past" : "before", fabs(tsp_bup), (tsp_bup >= 0) ? "above" : "below");
		else s = "Boards at the guide's point";
		TASSearch_Line([at_x, y, 0], s, tsz * 0.9, SUI_THEME_DIM, w);
	}
	y = y + row;
	s = sprintf("Flies %s (lead %.2f), aiming %+g, %+g u off its point", TASSearch_LeadWord(tsp_lead), tsp_lead, tsp_aimx, tsp_aimy);
	TASSearch_Line([at_x, y, 0], s, tsz * 0.85, SUI_THEME_MUTED, w); y = y + row * 1.15;
	// why candidates fail: each its own share (one line can do several)
	TASSearch_Line([at_x, y, 0], "What the lines tried ran into (one line can hit several):", tsz * 0.85, SUI_THEME_TEXT, w); y = y + row;
	TASSearch_Reason([at_x, y, 0], w, tsz, "Strayed off the guide's path (cut there)", tsp_tube, tsp_evals, SUI_THEME_INFO); y = y + row * 0.85;
	TASSearch_Reason([at_x, y, 0], w, tsz, "Brushed a wall (costs it energy)", tsp_wall, tsp_evals, SUI_THEME_BAD); y = y + row * 0.85;
	TASSearch_Reason([at_x, y, 0], w, tsz, "Made it, with too little energy to count", tsp_weak, tsp_evals, SUI_THEME_WARN); y = y + row * 0.85;
	TASSearch_Reason([at_x, y, 0], w, tsz, "Made it only by an edge bug", tsp_edge, tsp_evals, SUI_THEME_ACCENT); y = y + row * 0.85;
	TASSearch_Reason([at_x, y, 0], w, tsz, "Boarded, then fell off the ramp", tsp_brief, tsp_evals, SUI_THEME_WARN); y = y + row * 0.85;
	TASSearch_Reason([at_x, y, 0], w, tsz, "Hit a trigger (cut there)", tsp_cut, tsp_evals, SUI_THEME_MUTED); y = y + row * 1.05;
	// the best line's speed, generation by generation
	TASSearch_Line([at_x, y, 0], (tsp_ref > 0) ? "Best energy by generation (speed plus height; line: the guide)" : "Best energy by generation (speed plus height)", tsz * 0.8, SUI_THEME_MUTED, w);
	y = y + tsz * 1.1;
	if (tsp_histn >= 2)
	{
		lo = 1000000; hi = -1000000;
		for (i = 0; i < tsp_histn; i = i + 1) { lo = min(lo, tsp_hist[i]); hi = max(hi, tsp_hist[i]); }
		if (tsp_ref > 0) { lo = min(lo, tsp_ref); hi = max(hi, tsp_ref); }
		hi = max(hi, lo + 1);
		for (i = 0; i < tsp_histn; i = i + 1)
		{
			v = (tsp_hist[i] - lo) / (hi - lo) * tsz * 1.4 + 1;
			drawfill([at_x + i * (w / TSP_HIST), y + tsz * 1.5 - v, 0], [max(1, w / TSP_HIST - 1), v, 0], SUI_THEME_GOOD, 0.8, 0);
		}
		if (tsp_ref > 0)
			drawfill([at_x, y + tsz * 1.5 - ((tsp_ref - lo) / (hi - lo) * tsz * 1.4 + 1), 0], [w, 1, 0], SUI_THEME_WARN, 0.9, 0);
	}
	Font_Set(f0);
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
	if (taso_state == 1 && was != 1) { for (k = 0; k < TASO_STRETCHES; k = k + 1) taso_rb[k] = taso_rf[k] = 0; taso_lastk = -1; taso_stale = 0; }
	else if (taso_state == 1 && taso_i < wasi)      // a backtrack: what came after it is to be done again
		for (k = taso_i; k < TASO_STRETCHES; k = k + 1) taso_rb[k] = taso_rf[k] = 0;
	if (rk >= 0 && rk < TASO_STRETCHES) { taso_rb[rk] = rb; taso_rf[rk] = (rf > 0) ? rf : -1; taso_lastk = rk; }   // -1: a route point
	if (substring(taso_note, 0, 18) == "saved for Continue") jg_kat = 0;
	taso_armed = (taso_state == 1 && substring(taso_note, 0, 6) == "armed:");
	// which take-over the server armed (its note): the label and Take over follow it, not the chip (review 1531)
	taso_armmode = !taso_armed ? -1 : ((strstrofs(taso_note, "surf as you like") >= 0) ? 3 : ((strstrofs(taso_note, "at your jump") >= 0) ? 0 : 1));     // the chase waits for the takeover
	if (taso_state == 2 && was != 2) taso_endt = cltime;
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
			tov_rnorm[rk - 1] = [stof(argv(8)), stof(argv(9)), stof(argv(10))];
			tov_rk[rk - 1] = (stof(argv(10)) >= 0.99) ? 2 : ((stof(argv(8)) == 0 && stof(argv(9)) == 0 && stof(argv(10)) == 0) ? 3 : 1);
			tov_rn = rk;
		}
		else if (k >= 12 && argv(4) == "set" && stof(argv(5)) >= 1 && stof(argv(5)) <= min(rk, TOV_ROUTE))
		{	// a dragged point (the drag editor, cl_tasoptviz.qc)
			i = stof(argv(5)) - 1;
			tov_rp[i] = [stof(argv(6)), stof(argv(7)), stof(argv(8))];
			tov_rnorm[i] = [stof(argv(9)), stof(argv(10)), stof(argv(11))];
			tov_rk[i] = (stof(argv(11)) >= 0.99) ? 2 : ((stof(argv(9)) == 0 && stof(argv(10)) == 0 && stof(argv(11)) == 0) ? 3 : 1);
		}
		else if (k >= 6 && argv(4) == "removed" && stof(argv(5)) >= 1 && stof(argv(5)) <= tov_rn)
		{
			for (i = stof(argv(5)) - 1; i + 1 < tov_rn; i = i + 1)
			{
				tov_rp[i] = tov_rp[i + 1]; tov_rnorm[i] = tov_rnorm[i + 1]; tov_rk[i] = tov_rk[i + 1];
			}
			tov_rn = min(tov_rn - 1, max(0, rk));
			rte_drag = -1;          // the indices moved under a drag (review)
		}
		else tov_rn = min(tov_rn, max(0, rk));
		strunzone(taso_note);                      // the status line: the count, not the coordinates
		taso_note = strzone(sprintf("your route: %g points", rk));
	}
};

// a stretch's colour: mint at or above the guide's speed there (within 2%), butter within 10%, rose below, dim to come
vector(float k) TASOptUI_StretchCol =
{
	if (taso_rf[k] > 0)
	{
		if (taso_rb[k] / taso_rf[k] >= 0.98) return SUI_THEME_GOOD;
		return (taso_rb[k] / taso_rf[k] >= 0.9) ? SUI_THEME_WARN : SUI_THEME_BAD;
	}
	if (taso_rf[k] < 0) return SUI_THEME_GOOD;           // a route point reached
	return SUI_THEME_CHIP;
};
// One box a stretch: mint at or above the guide's speed there (within 2%), butter within 10%, rose below (a reach
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

// P1449: Jargon's panel, three steps (Lex, 10 Nov: "too many options ... more human"): a guide run, its route (drawn and
// edited in the world, cl_jargon.qc), then surf it -- the old tube/look/tries/backs knots are one Effort choice.
// P1483 (Lex: demo it on stream, and it must not get stuck when you reset or switch stages): the simple view by default;
// any start while one runs stops it first and fires once the server says it stopped (TASOptUI_Frame).
string taso_pend;
float taso_pendat;
void(float force) TASOptUI_Stop =
{	// force: the Stop button and hotkey (review: a note with state 0 mid-run left them doing nothing)
	if (taso_pend != "") { strunzone(taso_pend); taso_pend = ""; }
	if (force || taso_state == 1) localcmd("tas autosurf stop\n");
};
void(string c) TASOptUI_Go =
{
	if (c == "") { print("tas jargon: no guide run for this course (turn one on in the leaderboard)\n"); return; }    // review: stopped, started nothing
	if (taso_pend != "") { strunzone(taso_pend); taso_pend = ""; }
	if (taso_state != 1) { localcmd(c); return; }
	localcmd("tas autosurf stop\n");
	taso_pend = strzone(c); taso_pendat = cltime;
};
void() TASOptUI_Frame =
{
	if (taso_pend == "") return;
	if (taso_state == 1 && cltime - taso_pendat < 3) return;     // waiting for the stop's note (3 s: then it is said by the refusal)
	localcmd(taso_pend);
	strunzone(taso_pend); taso_pend = "";
};
var float autocvar_tas_jargon_wide = 0;     // P1476: flights weave wider (Lex: no flip a tick) -- needs an engine with it
var float autocvar_tas_jargon_spots = 0;    // 1: each board tries 5 spots on its ramp (`spots`); 2: the best of 4 lines (`beam`, P1483)
// ---- Options (Lex, 13 Nov: "are they editable? can we edit them in the tas menu") ----
// The words a Start, Arm or Continue sends, as settings; the defaults send what the panel always sent (Normal + low +
// safe). Behaviour rules are tas_jargon_off bits (the server's; a local game shares the cvar).
var float autocvar_tas_jargon_effort = 1;     // 0 quick, 1 normal, 2 thorough (taso_effort before the one-panel rewrite)
var float autocvar_tas_jargon_polish = 0;
var float autocvar_tas_jargon_tube = 300;
var float autocvar_tas_jargon_low = 1;
var float autocvar_tas_jargon_endany = 1;
var float autocvar_tas_jargon_exp = 0;        // the experiments' words, a bit each (TASOptUI_ExpWord)
float jgo_open;
#define JGO_RULES 6
#define JGO_EXP 11
float(float i) TASOptUI_RuleBits =
{
	if (i == 0) return 8192; if (i == 1) return 4096; if (i == 2) return 524288;
	if (i == 3) return 49152; if (i == 4) return 458752; if (i == 5) return 256;
	return 0;
};
string(float i) TASOptUI_RuleName =
{
	if (i == 0) return "Through portals"; if (i == 1) return "One jump off the start"; if (i == 2) return "Line up at a bad angle";
	if (i == 3) return "Strict boarding"; if (i == 4) return "Finish fixes";
	return "Learn from my attempts";
};
string(float i) TASOptUI_RuleTip =
{
	if (i == 0) return "A teleport the guide took between stages is flown into and through, so a full run goes on to the next stage.";
	if (i == 1) return "One jump off the start platform toward the first ramp, even where the guide bhopped off it.";
	if (i == 2) return "Walks to where the guide stood; at the box's exit more than 30 degrees off the guide's line, backs off and lines up again.";
	if (i == 3) return "A board counts only on the guide's ramp face, not a near-twin one beside it, and only after a flight, not a slide onto it.";
	if (i == 4) return "The finish searches past the guide's last frame, aims inside the end zone, and retries a coast that misses.";
	return "Starts from what worked on this course in earlier attempts. Off: every run from scratch.";
};
string(float i) TASOptUI_ExpWord =
{
	if (i == 0) return "spots"; if (i == 1) return "regions"; if (i == 2) return "apex"; if (i == 3) return "join";
	if (i == 4) return "wide"; if (i == 5) return "tight"; if (i == 6) return "free"; if (i == 7) return "catch";
	if (i == 8) return "parallel"; if (i == 9) return "launch";
	return "turns";
};
string(float i) TASOptUI_ExpName =
{
	if (i == 0) return "Board spots"; if (i == 1) return "Human windows"; if (i == 2) return "Peak split"; if (i == 3) return "Join hops";
	if (i == 4) return "Wide weave"; if (i == 5) return "Tight turns"; if (i == 6) return "Free turns"; if (i == 7) return "Catch";
	if (i == 8) return "Parallel boards"; if (i == 9) return "Launch points";
	return "Turn points";
};
string(float i) TASOptUI_ExpTip =
{
	if (i == 0) return "Tries several boarding places along each ramp, each judged on the ramp after it.";
	if (i == 1) return "Aims anywhere the humans in your demos boarded each ramp (3 or more runs of the course).";
	if (i == 2) return "Splits each long flight at its peak: the launch, then the flight on its own.";
	if (i == 3) return "A run of platform hops is one search, so the first hop can set up the next.";
	if (i == 4) return "Its lines weave wider in the air.";
	if (i == 5) return "May copy the guide's hardest turns past the usual limit (tech sections).";
	if (i == 6) return "No limit on how hard it turns; energy decides.";
	if (i == 7) return "Strafes wider before each board.";
	if (i == 8) return "Judges a board by the heading it arrives with too.";
	if (i == 9) return "The guide's leave from each ramp becomes an air point.";
	return "An air point halfway through each big turn in the air.";
};
float(float b) TASOptUI_RuleOn = { return !(cvar("tas_jargon_off") & b); };
void(float b, float on) TASOptUI_RuleSet =
{
	local float v;
	v = cvar("tas_jargon_off");
	v = on ? (v - (v & b)) : (v | b);
	cvar_set("tas_jargon_off", sprintf("%.0f", v));      // %.0f: ftos may print a large one in exponent form
};
// a label over a row of choices
void(vector at, string s, float hint) TASOptUI_OptHead = { sui_text(at, [hint, hint], s, SUI_THEME_DIM, 1, 0); };
float jgo_exp;     // the experiments shown (folded by default: the panel does not scroll -- review 1531)
float(vector at, float width, float hint, float row) TASOptUI_DrawOptions =
{
	local float i, b, third, half, q, tsc, on;
	local string id;
	third = (width - 12) / 3; half = (width - 6) / 2; q = (width - 18) / 4; tsc = max(1, hint / 7);
	sui_text(at, [hint, hint], "Effort, path, boarding, finish: from the next Start or Arm. Switches: at once. Hover a choice.", SUI_THEME_MUTED, 1, 0);
	at_y = at_y + hint * 1.6;
	TASOptUI_OptHead(at, "How hard it tries", hint); at_y = at_y + hint * 1.5;
	for (i = 0; i < 3; i = i + 1)
	{
		id = sprintf("jgo_e%g", i);
		if (Profile_Chip(id, at + [i * (q + 6), 0, 0], [q, row, 0], (i == 0) ? "Quick" : ((i == 1) ? "Normal" : "Thorough"), hint,
			autocvar_tas_jargon_effort == i))
			cvar_set("tas_jargon_effort", ftos(i));
		sui_tooltip_for(id, (i == 0) ? "One try a ramp before it goes back: fastest, gives up soonest."
			: ((i == 1) ? "Two tries a ramp, with extra control over each ride's dip and flick. The default."
			: "Three tries a ramp, every ramp polished, up to 30 goes back. Slow."), tsc);
	}
	if (Profile_Chip("jgo_pol", at + [3 * (q + 6), 0, 0], [q, row, 0], "Polish", hint, autocvar_tas_jargon_polish || autocvar_tas_jargon_effort == 2))
	if (autocvar_tas_jargon_effort != 2)       // Thorough always polishes (review 1531: the click flipped a hidden setting)
		cvar_set("tas_jargon_polish", autocvar_tas_jargon_polish ? "0" : "1");
	sui_tooltip_for("jgo_pol", "Each ramp is searched until it carries 99% of the human's energy there (or its last try). Thorough always does.", tsc);
	at_y = at_y + row + hint;
	TASOptUI_OptHead(at, "Path: how far its lines may stray from the guide's", hint); at_y = at_y + hint * 1.5;
	for (i = 0; i < 4; i = i + 1)
	{
		b = (i == 0) ? 150 : ((i == 1) ? 300 : ((i == 2) ? 600 : 1200));
		id = sprintf("jgo_t%g", i);
		if (Profile_Chip(id, at + [i * (q + 6), 0, 0], [q, row, 0], (i == 0) ? "Narrow" : ((i == 1) ? "Normal" : ((i == 2) ? "Wide" : "Free")), hint,
			autocvar_tas_jargon_tube == b))
			cvar_set("tas_jargon_tube", ftos(b));
		sui_tooltip_for(id, sprintf("Lines stay within %g u of the guide's path. Narrower copies the guide; wider lets it find its own line.", b), tsc);
	}
	at_y = at_y + row + hint;
	TASOptUI_OptHead(at, "Boarding", hint); TASOptUI_OptHead(at + [half + 6, 0, 0], "Finish", hint); at_y = at_y + hint * 1.5;
	if (Profile_Chip("jgo_b1", at, [(half - 6) / 2, row, 0], "Guide's spot", hint, autocvar_tas_jargon_low)) cvar_set("tas_jargon_low", "1");
	sui_tooltip_for("jgo_b1", "A board past the guide's spot along the ramp, above it or far below it costs a line score.", tsc);
	if (Profile_Chip("jgo_b0", at + [(half + 6) / 2, 0, 0], [(half - 6) / 2, row, 0], "Anywhere", hint, !autocvar_tas_jargon_low)) cvar_set("tas_jargon_low", "0");
	sui_tooltip_for("jgo_b0", "Any board on the ramp's face counts the same.", tsc);
	if (Profile_Chip("jgo_f1", at + [half + 6, 0, 0], [(half - 6) / 2, row, 0], "End zone", hint, autocvar_tas_jargon_endany)) cvar_set("tas_jargon_endany", "1");
	sui_tooltip_for("jgo_f1", "The finish aims at the nearest way into the end zone.", tsc);
	if (Profile_Chip("jgo_f0", at + [half + 6 + (half + 6) / 2, 0, 0], [(half - 6) / 2, row, 0], "Guide's way in", hint, !autocvar_tas_jargon_endany))
		cvar_set("tas_jargon_endany", "0");
	sui_tooltip_for("jgo_f0", "The finish follows the guide's own way into the end.", tsc);
	at_y = at_y + row + hint;
	TASOptUI_OptHead(at, "Behaviour (on by default)", hint); at_y = at_y + hint * 1.5;
	for (i = 0; i < JGO_RULES; i = i + 1)
	{
		id = sprintf("jgo_r%g", i); b = TASOptUI_RuleBits(i); on = TASOptUI_RuleOn(b);
		if (Profile_Chip(id, at + [(i - 3 * floor(i / 3)) * (third + 6), floor(i / 3) * (row + 3), 0], [third, row, 0], TASOptUI_RuleName(i), hint, on))
		{
			TASOptUI_RuleSet(b, !on);
			if (b & 8192) jg_replan = cltime + 0.2;     // portals shape the plan: the list follows (held while it runs)
		}
		sui_tooltip_for(id, TASOptUI_RuleTip(i), tsc);
	}
	at_y = at_y + ceil(JGO_RULES / 3) * (row + 3) + hint * 0.5;
	if (Profile_Chip("jgo_xs", at, [width, row, 0], jgo_exp ? "Experiments and test switches (hide)" : "Experiments and test switches (show)", hint, jgo_exp))
		jgo_exp = !jgo_exp;
	sui_tooltip_for("jgo_xs", "Ways of searching that are off by default and not proven better, and the two crouch switches.", tsc);
	at_y = at_y + row + 3;
	if (jgo_exp)
	{
		if (Profile_Chip("jgo_ck", at, [half, row, 0], "Crouch: in the search", hint, cvar("tas_jargon_rowkeys")))
			cvar_set("tas_jargon_rowkeys", cvar("tas_jargon_rowkeys") ? "0" : "1");
		sui_tooltip_for("jgo_ck", "The guide run's crouch, tick by tick, in every line it tries. Measured: colin_blaster's first portal went from 2 of 2 runs through to 0 of 3.", tsc);
		if (Profile_Chip("jgo_cs", at + [half + 6, 0, 0], [half, row, 0], "Crouch: at the start", hint, cvar("tas_jargon_startduck")))
			cvar_set("tas_jargon_startduck", cvar("tas_jargon_startduck") ? "0" : "1");
		sui_tooltip_for("jgo_cs", "The guide's crouch-jump off the start platform, timed from Jargon's own jump. Measured: tensor2 stage 1's first ramp was no longer reached.", tsc);
		at_y = at_y + row + 3;
		b = 1;
		for (i = 0; i < JGO_EXP; i = i + 1)
		{
			id = sprintf("jgo_x%g", i); on = (autocvar_tas_jargon_exp & b) ? TRUE : FALSE;
			if (Profile_Chip(id, at + [(i - 4 * floor(i / 4)) * (q + 6), floor(i / 4) * (row + 3), 0], [q, row, 0], TASOptUI_ExpName(i), hint, on))
			{
				cvar_set("tas_jargon_exp", sprintf("%.0f", on ? (autocvar_tas_jargon_exp - b) : (autocvar_tas_jargon_exp | b)));
				if (b & 1548) jg_replan = cltime + 0.2;      // apex, join, launch, turns shape the plan (4+8+512+1024)
			}
			sui_tooltip_for(id, TASOptUI_ExpTip(i), tsc);
			b = b * 2;
		}
		at_y = at_y + ceil(JGO_EXP / 4) * (row + 3);
	}
	return at_y;
};
string() TASOptUI_Effort =
{
	if (autocvar_tas_jargon_effort == 0) return " tries 1 rideknots";
	if (autocvar_tas_jargon_effort == 2) return " tries 3 rideknots backs 30";
	return " tries 2 rideknots";
};
string() TASOptUI_Exps =
{
	local float i, b;
	local string s;
	s = ""; b = 1;
	for (i = 0; i < JGO_EXP; i = i + 1) { if (autocvar_tas_jargon_exp & b) s = strcat(s, " ", TASOptUI_ExpWord(i)); b = b * 2; }
	return s;
};
// the stream view's commands, built once for its buttons and `tas jargon go | arm` (hotkeys, the harness): "" when the
// picked course has no guide run
// a Continue's words: the continue parser takes effort, polish, low, safe, air, finish, spots, wide -- the path and the other
// experiments are the save's (review 1531: `tube` or an experiment refused it after the stop)
string() TASOptUI_ContinueWords =
{
	local string s;
	s = strcat(TASOptUI_Effort(), (autocvar_tas_jargon_polish || autocvar_tas_jargon_effort == 2) ? " polish" : "", autocvar_tas_jargon_low ? " low" : "",
		autocvar_tas_jargon_endany ? " safe" : "");
	return strcat(s, TASJargon_Airs() ? " air" : "", (TASJargon_CourseWords() != "") ? " finish" : "", (autocvar_tas_jargon_exp & 1) ? " spots" : "",
		(autocvar_tas_jargon_exp & 16) ? " wide" : "");
};
string() TASOptUI_DemoWords =
{
	local string s;
	s = strcat(TASOptUI_Effort(), (autocvar_tas_jargon_polish || autocvar_tas_jargon_effort == 2) ? " polish" : "", autocvar_tas_jargon_low ? " low" : "",
		(autocvar_tas_jargon_tube != 300) ? sprintf(" tube %.0f", bound(50, autocvar_tas_jargon_tube, 2000)) : "");
	return strcat(s, autocvar_tas_jargon_endany ? " safe" : "", TASJargon_Airs() ? " air" : "", (TASJargon_CourseWords() != "") ? " finish" : "", TASOptUI_Exps());
};
string() TASOptUI_GoCmd =
{
	jg_gat = 0; TASJargon_Guides();
	if (!jg_gn) return "";
	return sprintf("tas autosurf %s%s start%s\n", jg_gp[jg_pick], TASOptUI_DemoWords(), TASJargon_CourseWords());
};
string() TASOptUI_ArmCmd =
{
	jg_gat = 0; TASJargon_Guides();
	if (!jg_gn) return "";
	return sprintf("tas autosurf %s%s onjump%s\ntas play\n", jg_gp[jg_pick], TASOptUI_DemoWords(), TASJargon_CourseWords());   // TAS on: the server's, once armed
};
void(float n) TASOptUI_Course =
{
	TASJargon_Courses();
	if (!(n >= 0 && n < jg_cn) || n != floor(n)) { print(sprintf("tas jargon course: 1..%g on this map\n", jg_cn)); return; }
	if (n != jg_cpick)
	{	// the stop runs before the plan request: one console buffer, in order (review 1528: the hotkeys drew no route)
		TASOptUI_Stop(1); jg_cpick = n; jg_gat = 0; jg_kat = 0; taso_sel = -1; taso_stale = 1; jg_n = 0; jgw_sel = -1;
		TASJargon_Guides();
		if (jg_gn) TASJargon_RequestPlan();
	}    // the old course's strip hides (review 4-5: a Redo redid it)
	print(sprintf("tas jargon: %s\n", TASJargon_CourseLabel(n)));
};
// ---- The Jargon panel (Lex, 13 Nov: one panel, not a simple and an advanced view -- the waypoints in order with
// editable X Y Z, air points added to the list, undo; a start mode and Start; the waypoints stay drawn). The console's
// tas jargon / tas autosurf / tas route commands are unchanged. ----
var float autocvar_tas_jargon_startmode = 0;    // 0: on my jump, 1: on leaving the start zone, 2: Jargon starts itself
vector jgw_scroll;
float jgf_on, jgf_i, jgf_ax, jgf_caret;
string jgf_buf;
string jgf_seed;                 // the text it opened with: left unchanged is no edit (review 1528: a click moved it 0.05 u)
float jgf_k, jgf_t;              // the focused waypoint by what it is, not its row: a replan reorders rows (review 1528)
vector jgf_o;
float jgw_wheel, jgw_rowh, jgw_rows;
float jgd_open, jgd_w, jgd_n, jgd_rows;      // the open dropdown (1 course, 2 guide run), drawn last over the panel
vector jgd_pos, jgd_scroll;
string jgu_gd;                   // the guide run and course the edits were made on: another's are not undone onto it
float jgu_gc;
#define JGU_MAX 64
float jgu_n, jgu_top;            // edits held; redo replays jgu_top .. jgu_n - 1
float jgu_k[JGU_MAX], jgu_t[JGU_MAX];     // 1 a guide point moved (t), 2 an air point moved, 3 one added, 4 one deleted
vector jgu_a[JGU_MAX], jgu_b[JGU_MAX];    // from, to (3: b the point; 4: a the point)

string(float k) TASOptUI_WpKind =
{
	if (k == 1) return "Board"; if (k == 2) return "Hop"; if (k == 3) return "End"; if (k == 4) return "Peak";
	if (k == 5) return "Air"; if (k == 6) return "Turn"; if (k == 7) return "Portal";
	return "?";
};
float(float k) TASOptUI_WpEditable = { return (k == 1 || k == 2 || k == 5); };
// P1531: edits go through while Jargon runs or is armed -- a moved guide point reaches its waypoints at once, an air
// point at the next waypoint (the server's); the panel's own replan waits for the stop (cl_jargon). Reset alone waits.
float() TASOptUI_EditOK = { return TRUE; };
float(float i, float k, float t, vector o) TASOptUI_WpSame =
{
	if (jg_k[i] != k) return FALSE;
	if (k == 5) return (vlen(jg_o[i] - o) < 1);     // an air point is where it is; a guide point is its demo time
	return (fabs(jg_t[i] - t) < 0.01);
};
float(float k, float t, vector o, float hint) TASOptUI_WpFind =
{
	local float i;
	if (hint >= 0 && hint < jg_n)
		if (TASOptUI_WpSame(hint, k, t, o)) return hint;
	for (i = 0; i < jg_n; i = i + 1)
		if (TASOptUI_WpSame(i, k, t, o)) return i;
	return -1;
};
void(float i) TASOptUI_Select =
{
	jgw_sel = i;
	if (i >= 0) { jgw_selk = jg_k[i]; jgw_selt = jg_t[i]; jgw_selo = jg_o[i]; }
};
void() TASOptUI_UndoKeep =
{
	if (jgu_n)
	if (jgu_gd != jg_planned || jgu_gc != jg_plannedc) jgu_n = jgu_top = 0;
};
string() TASOptUI_ArmExitCmd =
{
	jg_gat = 0; TASJargon_Guides();
	if (!jg_gn) return "";
	return sprintf("tas autosurf %s%s onexit%s\ntas play\n", jg_gp[jg_pick], TASOptUI_DemoWords(), TASJargon_CourseWords());
};
// P1531 `When I press`: TAS on from the box you stand in (any course's); the course is picked at the takeover
string() TASOptUI_ArmKeyCmd =
{
	jg_gat = 0; TASJargon_Guides();
	if (!jg_gn) return "";
	return sprintf("tas autosurf %s%s onkey\ntas play\n", jg_gp[jg_pick], TASOptUI_DemoWords());
};
// P1531 take over from here (Lex, 13 Nov: "it doesn't matter what stage/bonus you're on, it will just know"): the course
// is the stage the run is in (the timer's), or the track on a map without stages; its guide run, the plan from the guide's
// row nearest the body going its way. `tas jargon takeover` binds it.
void() TASOptUI_Takeover =
{
	local float seg, segs, track, leg, c, i, was;
	if (taso_state == 1 && !taso_armed) { print("tas jargon: Jargon is surfing already: Take over is for a run you surf\n"); return; }
	if (Timer_Stat(STAT_FS_TIMERSTATE) != TS_RUNNING) { print("tas jargon: leave the start box first, then Take over\n"); return; }
	seg = Timer_Stat(STAT_FS_TIMERSEG); segs = Timer_Stat(STAT_FS_TIMERSEGS); track = Timer_Stat(STAT_FS_TIMERTRACK);
	leg = (segs > 1) ? seg + 1 : 0;
	TASJargon_Courses();
	c = -1;
	for (i = 0; i < jg_cn; i = i + 1) if (jg_ct[i] == track && jg_cl[i] == leg) c = i;
	if (c < 0) for (i = 0; i < jg_cn; i = i + 1) if (jg_ct[i] == track && jg_cl[i] == 0) c = i;
	if (c < 0) { print("tas jargon: no course here to take over\n"); return; }
	was = jg_cpick; jg_cpick = c; jg_gat = 0; TASJargon_Guides();
	if (!jg_gn)
	{	// the panel's course as it was (review 1531: it switched first and hid Take over, Stop and Back to playing)
		print(sprintf("tas jargon: no guide run of %s here: turn one on in the leaderboard\n", TASJargon_CourseLabel(c)));
		jg_cpick = was; jg_gat = 0; TASJargon_Guides();
		return;
	}
	if (c != was) { jg_kat = 0; taso_sel = -1; taso_stale = 1; jg_n = 0; jgw_sel = -1; }
	localcmd(sprintf("tas autosurf %s%s here%s\n", jg_gp[jg_pick], TASOptUI_DemoWords(), TASJargon_CourseWords()));
	if (jg_planned != "") strunzone(jg_planned);
	jg_planned = "";        // after this run the list is the whole course's again (the takeover's starts from here)
	print(sprintf("tas jargon: taking over in %s\n", TASJargon_CourseLabel(c)));
};
void() TASOptUI_Start =
{
	if (autocvar_tas_jargon_startmode == 3) { TASOptUI_Go(TASOptUI_ArmKeyCmd()); TASUI_Close(); return; }
	if (autocvar_tas_jargon_startmode == 2) { TASOptUI_Go(TASOptUI_GoCmd()); return; }
	TASOptUI_Go((autocvar_tas_jargon_startmode == 1) ? TASOptUI_ArmExitCmd() : TASOptUI_ArmCmd());
	TASUI_Close();      // armed: the player's own start, live
};
// the client's copy, before the server's replan says so
void(float t, vector p) TASOptUI_WpLocal =
{
	local float i;
	for (i = 0; i < jg_n; i = i + 1)
		if ((jg_k[i] == 1 || jg_k[i] == 2) && fabs(jg_t[i] - t) < 0.01) { jg_o[i] = p; jg_mv[i] = 1; jg_surf[i] = -2; }
};
// a guide point by its demo time (tas autosurf move), an air point by its route slot (tas route set)
float(float k, float t, vector from, vector to) TASOptUI_WpSend =
{
	local float r;
	if (!TASOptUI_EditOK()) return FALSE;
	if (k == 1 || k == 2) { localcmd(sprintf("tas autosurf move %.3f %.1f %.1f %.1f\n", t, to_x, to_y, to_z)); TASOptUI_WpLocal(t, to); return TRUE; }
	r = TASJargon_RouteOf(from);
	if (r < 0) { print("tas jargon: that air point is no longer on the route\n"); return FALSE; }
	localcmd(sprintf("tas route set %g %.1f %.1f %.1f 0 0 0\n", r + 1, to_x, to_y, to_z));
	jg_replan = cltime + 0.4;
	return TRUE;
};
float(vector p) TASOptUI_AirAdd =
{
	if (!TASOptUI_EditOK()) return FALSE;
	localcmd(sprintf("tas route add %.1f %.1f %.1f 0 0 0\n", p_x, p_y, p_z)); jg_replan = cltime + 0.4;
	return TRUE;
};
float(vector p) TASOptUI_AirDel =
{
	local float r;
	if (!TASOptUI_EditOK()) return FALSE;
	r = TASJargon_RouteOf(p);
	if (r < 0) { print("tas jargon: that air point is no longer on the route\n"); return FALSE; }
	localcmd(sprintf("tas route del %g\n", r + 1)); jg_replan = cltime + 0.4;
	return TRUE;
};
void(float k, float t, vector a, vector b) TASOptUI_WpPush =
{
	local float i;
	TASOptUI_UndoKeep();
	if (jgu_gd != jg_planned) { if (jgu_gd != "") strunzone(jgu_gd); jgu_gd = strzone(jg_planned); }
	jgu_gc = jg_plannedc;
	if (jgu_top >= JGU_MAX)
	{	// the oldest goes
		for (i = 1; i < JGU_MAX; i = i + 1) { jgu_k[i-1] = jgu_k[i]; jgu_t[i-1] = jgu_t[i]; jgu_a[i-1] = jgu_a[i]; jgu_b[i-1] = jgu_b[i]; }
		jgu_top = JGU_MAX - 1;
	}
	jgu_k[jgu_top] = k; jgu_t[jgu_top] = t; jgu_a[jgu_top] = a; jgu_b[jgu_top] = b;
	jgu_top = jgu_top + 1; jgu_n = jgu_top;     // a new edit ends the redo branch
};
void(float undo) TASOptUI_WpUndo =
{
	local float i, k;
	TASOptUI_UndoKeep();
	if (!TASOptUI_EditOK()) return;
	if (undo) { if (jgu_top < 1) return; jgu_top = jgu_top - 1; i = jgu_top; }
	else { if (jgu_top >= jgu_n) return; i = jgu_top; jgu_top = jgu_top + 1; }
	k = jgu_k[i];
	if (k == 1) TASOptUI_WpSend(1, jgu_t[i], undo ? jgu_b[i] : jgu_a[i], undo ? jgu_a[i] : jgu_b[i]);
	else if (k == 2)
	{
		if (TASOptUI_WpSend(5, 0, undo ? jgu_b[i] : jgu_a[i], undo ? jgu_a[i] : jgu_b[i]))
		{	// as FieldCommit: the row and the selection at the new place until the replan (review 1528: it dropped them)
			k = TASOptUI_WpFind(5, 0, undo ? jgu_b[i] : jgu_a[i], -1);
			if (k >= 0) { jg_o[k] = undo ? jgu_a[i] : jgu_b[i]; if (jgw_sel == k) jgw_selo = jg_o[k]; }
		}
	}
	else if (k == 3) { if (undo) TASOptUI_AirDel(jgu_b[i]); else TASOptUI_AirAdd(jgu_b[i]); }
	else if (undo) TASOptUI_AirAdd(jgu_a[i]);
	else TASOptUI_AirDel(jgu_a[i]);
};
// a typed number: digits, one point, a leading sign
float(string v) TASOptUI_IsNumber =
{
	local float i, c, digits, dots;
	digits = dots = 0;
	for (i = 0; i < strlen(v); i = i + 1)
	{
		c = str2chr(v, i);
		if (c >= 48 && c <= 57) digits = digits + 1;
		else if (c == 46) dots = dots + 1;
		else if (!((c == 45 || c == 43) && i == 0)) return FALSE;
	}
	return (digits >= 1 && dots <= 1);
};
void() TASOptUI_FieldCommit =
{
	local vector o, n;
	local float v, i;
	if (!jgf_on) return;
	jgf_on = FALSE; sui_field_focus("");
	if (jgf_buf == jgf_seed) return;
	i = TASOptUI_WpFind(jgf_k, jgf_t, jgf_o, jgf_i);
	if (i < 0) { print("tas jargon: that waypoint changed while you typed; nothing set\n"); return; }
	if (!TASOptUI_WpEditable(jg_k[i])) return;
	if (!TASOptUI_IsNumber(jgf_buf)) { print(sprintf("tas jargon: \"%s\" is not a number\n", jgf_buf)); return; }
	v = stof(jgf_buf);
	if (fabs(v) > 65536) return;
	o = jg_o[i]; n = o;
	if (jgf_ax == 0) n_x = v; else if (jgf_ax == 1) n_y = v; else n_z = v;
	if (n == o) return;
	if (!TASOptUI_WpSend(jg_k[i], jg_t[i], o, n)) return;
	TASOptUI_WpPush((jg_k[i] == 5) ? 2 : 1, jg_t[i], o, n);
	if (jg_k[i] == 5) { jg_o[i] = n; if (jgw_sel == i) jgw_selo = n; }      // the replan confirms it
};
string() TASOptUI_FieldId = { return sprintf("jgf_%g_%g", jgf_i, jgf_ax); };
void(float i, float ax, string seed) TASOptUI_FieldFocus =
{
	jgf_on = TRUE; jgf_i = i; jgf_ax = ax; jgf_k = jg_k[i]; jgf_t = jg_t[i]; jgf_o = jg_o[i];
	jgf_buf = seed; jgf_seed = seed; jgf_caret = strlen(seed);
};
// rows by what they are once a plan has all arrived: a replan may reorder them
void() TASOptUI_Refind =
{
	local float i;
	if (jg_got < jg_n) return;
	if (jgw_sel >= 0) TASOptUI_Select(TASOptUI_WpFind(jgw_selk, jgw_selt, jgw_selo, jgw_sel));
	if (!jgf_on) return;
	i = TASOptUI_WpFind(jgf_k, jgf_t, jgf_o, jgf_i);
	if (i < 0) { jgf_on = FALSE; sui_field_focus(""); }
	else if (i != jgf_i) { jgf_i = i; sui_field_focus(TASOptUI_FieldId()); }
};
float(float scanx, float chary) TASOptUI_FieldKey =
{
	if (scanx == K_ENTER || scanx == K_KP_ENTER) { TASOptUI_FieldCommit(); return TRUE; }
	if (scanx == K_ESCAPE) { jgf_on = FALSE; sui_field_focus(""); return TRUE; }
	sui_text_event(IE_KEYDOWN, scanx, chary, TASOptUI_FieldId(), jgf_buf, jgf_caret);
	return TRUE;
};
// the focused number field's keys (cl_main's input, before chat binds). Only a fresh press is taken, marked a text
// field's in the recipe tracker (2) as TASTimeline_RecipeInput does: its release and repeats are then taken ahead of
// this, and a key held from before -- its repeats, its release -- stays the game's (review 1528: a held W stuck down)
float(float evtype, float scanx, float chary) TASOptUI_FieldInput =
{
	if (!jgf_on) return FALSE;
	if (!tasu_open || tasu_tab != TAS_TAB_OPTIMIZE || chat_typing) { jgf_on = FALSE; sui_field_focus(""); return FALSE; }
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN)
		if (!sui_is_hovered(TASOptUI_FieldId())) TASOptUI_FieldCommit();
		return FALSE;
	}
	if (evtype != IE_KEYDOWN) return FALSE;
	if (scanx)
	{	// nested: every operand runs, and the wheel's 515 is past any array (review 1528: a crash)
		if (scanx < 0 || scanx >= TAS_RECIPE_SCANS || scanx != floor(scanx)) return FALSE;
		if (scanx >= K_F1 && scanx <= K_F12) return FALSE;
		if (!tast_recipe_keys) return FALSE;
		if (tast_recipe_fresh != scanx + 1) return FALSE;
		tast_recipe_keys[scanx] = 2;
	}
	return TASOptUI_FieldKey(scanx, chary);
};
// a repeat of a key the field owns, after TASTimeline_RecipeRepeat took it (cl_main)
void(float scanx, float chary) TASOptUI_FieldRepeat =
{
	if (!jgf_on) return;
	if (!tasu_open || tasu_tab != TAS_TAB_OPTIMIZE || chat_typing) { jgf_on = FALSE; sui_field_focus(""); return; }
	TASOptUI_FieldKey(scanx, chary);
};
// Esc with a dropdown open closes it, not the panel
float(float evtype, float scanx) TASOptUI_DropKey =
{
	if (!jgd_open) return FALSE;
	if (!tasu_open || tasu_tab != TAS_TAB_OPTIMIZE) { jgd_open = 0; return FALSE; }
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE) { jgd_open = 0; return TRUE; }
	return FALSE;
};
// the wheel over the waypoint list scrolls it (as Players_Wheel); its release is the list's too
float(float evtype, float scanx) TASOptUI_Wheel =
{
	local float bit, d;
	if (scanx != K_MWHEELUP && scanx != K_MWHEELDOWN) return FALSE;
	bit = (scanx == K_MWHEELUP) ? 1 : 2;
	if (evtype == IE_KEYUP)
	{
		if (!(jgw_wheel & bit)) return FALSE;
		jgw_wheel = jgw_wheel - bit;
		return TRUE;
	}
	if (evtype != IE_KEYDOWN || !tasu_open || tasu_tab != TAS_TAB_OPTIMIZE) return FALSE;
	_sui_mouse_move(_cursor_position, FALSE);
	if (jgd_open)
	if (sui_hover_index("jgd_list") >= 0)
	{
		d = max(1, jgw_rowh) * 2;
		if (scanx == K_MWHEELUP) d = 0 - d;
		jgd_scroll_y = bound(0, jgd_scroll_y + d, max(0, (jgd_n - jgd_rows) * jgw_rowh));
		jgw_wheel = jgw_wheel | bit;
		return TRUE;
	}
	if (sui_hover_index("jgw_list") < 0) return FALSE;
	d = max(1, jgw_rowh) * 2;
	if (scanx == K_MWHEELUP) d = 0 - d;
	jgw_scroll_y = bound(0, jgw_scroll_y + d, max(0, (jg_n - jgw_rows) * jgw_rowh));
	jgw_wheel = jgw_wheel | bit;
	return TRUE;
};
float(float chary) TASOptUI_FieldPaste =
{
	if (!jgf_on) return FALSE;
	sui_text_event(IE_KEYDOWN, 0, chary, TASOptUI_FieldId(), jgf_buf, jgf_caret);
	return TRUE;
};
// a table cell, not a button (Lex, 13 Nov: "X Y Z look like buttons"): flat, lit when hovered or picked
float(string id, vector pos, vector sz, string label, float tsz, float on, float right) TASOptUI_Cell =
{
	local float hot, tw, x;
	sui_action_element(pos, sz, id, sui_noop);
	hot = sui_is_hovered(id);
	if (on || hot) sui_fill(pos, sz, hot ? SUI_THEME_HOVER : SUI_THEME_SELECTED, hot ? 0.55 : 0.4, 0);
	tw = stringwidth(label, TRUE, [tsz, tsz]);
	if (tw > sz_x - 8) { tsz = tsz * (sz_x - 8) / tw; tw = sz_x - 8; }
	x = right ? sz_x - tw - 4 : 4;
	sui_text([pos_x + x, pos_y + (sz_y - tsz) * 0.5], [tsz, tsz], label, on ? SUI_THEME_ACCENT : (hot ? SUI_THEME_TEXT : SUI_THEME_DIM), 1, 0);
	return sui_is_released(id);
};
void(vector pos, vector sz, string label, float tsz, vector col) TASOptUI_RText =
{
	sui_text([pos_x + sz_x - 4 - stringwidth(label, TRUE, [tsz, tsz]), pos_y + (sz_y - tsz) * 0.5], [tsz, tsz], label, col, 1, 0);
};
void(float i, float ax, vector at, vector sz, float tsz) TASOptUI_WpField =
{
	local string id;
	local vector o;
	local float v;
	id = sprintf("jgf_%g_%g", i, ax);
	o = jg_o[i];
	v = (ax == 0) ? o_x : ((ax == 1) ? o_y : o_z);
	if (jgf_on && jgf_i == i && jgf_ax == ax)
	{
		sui_text_input(id, at, sz, jgf_buf, jgf_caret);
		Profile_FieldLook(id, at, sz, tsz, jgf_buf, jgf_caret, "", TRUE, sz_y * 0.5, ceil(sz_y * 0.45));
		return;
	}
	if (TASOptUI_Cell(id, at, sz, sprintf("%.1f", v), tsz, FALSE, TRUE))
	{
		if (jgf_on) TASOptUI_FieldCommit();
		if (!TASOptUI_EditOK()) return;
		TASOptUI_FieldFocus(i, ax, sprintf("%.1f", v));
		TASOptUI_Select(i);
		Profile_Unfocus(); sui_field_focus(id);
	}
};
void(float i) TASOptUI_GuidePick =
{
	if (!(i >= 0 && i < jg_gn) || i != floor(i)) { print(sprintf("tas jargon guide: 1..%g for this course\n", jg_gn)); return; }
	if (i == jg_pick) return;
	if (taso_state == 1) { print("tas jargon: Stop Jargon to change its guide run\n"); return; }
	jg_pick = i; TASJargon_RequestPlan();
	print(sprintf("tas jargon: guide run %s\n", jg_gl[i]));
};
void(string id, float which, vector pos, vector sz, string label, float tsz) TASOptUI_Drop =
{
	local float m;
	label = strcat(label, "   v");
	m = stringwidth(label, TRUE, [tsz, tsz]);
	if (m > sz_x - 12) tsz = tsz * (sz_x - 12) / m;
	if (Profile_Chip(id, pos, sz, label, tsz, jgd_open == which)) { jgd_open = (jgd_open == which) ? 0 : which; jgd_scroll = '0 0 0'; }
	if (jgd_open == which) { jgd_pos = pos + [0, sz_y + 2, 0]; jgd_w = sz_x; }     // under its opener (`tas jargon drop` opens one too)
};
// the guide points back where the guide run put them, and the panel's air points gone -- deleted highest route slot first
// (each delete renumbers those after it); the clicked-route tool's points (with a normal) stay (review 1528: `tas route
// clear` took them too). Undo brings the air points back.
float jgp_resetask;
float jgr_s[JG_MAX];
vector jgr_p[JG_MAX];
void() TASOptUI_Reset =
{
	local float i, j, n, r, t;
	local vector tv;
	n = 0;
	for (i = 0; i < jg_n; i = i + 1)
		if (jg_k[i] == 5)
		{
			r = TASJargon_RouteOf(jg_o[i]);
			if (r >= 0) { jgr_s[n] = r; jgr_p[n] = jg_o[i]; n = n + 1; }
		}
	for (i = 0; i < n; i = i + 1)       // highest slot first, each with its place
		for (j = i + 1; j < n; j = j + 1)
			if (jgr_s[j] > jgr_s[i]) { t = jgr_s[i]; jgr_s[i] = jgr_s[j]; jgr_s[j] = t; tv = jgr_p[i]; jgr_p[i] = jgr_p[j]; jgr_p[j] = tv; }
	localcmd("tas autosurf reset\n");
	jgu_n = jgu_top = 0;
	for (i = 0; i < n; i = i + 1)
	{
		localcmd(sprintf("tas route del %g\n", jgr_s[i] + 1));
		TASOptUI_WpPush(4, 0, jgr_p[i], '0 0 0');
	}
	jgw_sel = -1; jg_replan = cltime + 0.2;
};
// `tas jargon start | mode 0|1|2|3 | set N x|y|z V | field N x|y|z | air N | del N | undo | redo | list`: the panel's own
// functions, for binds and the harness that tests them (N counts from 1, as the list does; field opens one as a click)
void(float argc) TASOptUI_Verb =
{
	local float i, ax;
	local vector a;
	local string w;
	w = argv(2);
	if (w == "start") { TASOptUI_Start(); return; }
	if (w == "mode") { if (argc == 4 && stof(argv(3)) >= 0 && stof(argv(3)) <= 3) cvar_set("tas_jargon_startmode", argv(3)); return; }     // 3: When I press (P1531)
	if (w == "undo") { TASOptUI_WpUndo(TRUE); return; }
	if (w == "redo") { TASOptUI_WpUndo(FALSE); return; }
	if (w == "guide") { if (argc == 4) TASOptUI_GuidePick(stof(argv(3)) - 1); return; }
	if (w == "takeover") { TASOptUI_Takeover(); return; }
	if (w == "redofrom")
	{
		i = floor(stof(argv(3))) - 1;
		if (argc == 4) if (i >= 0 && i < jg_n) TASOptUI_Go(sprintf("tas autosurf redo %g %.3f\n", i + 1, jg_t[i]));
		return;
	}
	if (w == "options") { if (argc == 4) { if (jgf_on) TASOptUI_FieldCommit(); jgo_open = (stof(argv(3)) != 0); } print(sprintf("tas jargon: options %g, words%s\n", jgo_open, TASOptUI_DemoWords())); return; }
	if (w == "drop") { if (argc == 4) { jgd_open = bound(0, floor(stof(argv(3))), 2); jgd_scroll = '0 0 0'; print(sprintf("tas jargon: dropdown %g\n", jgd_open)); } return; }
	if (w == "guides")
	{
		for (i = 0; i < jg_gn; i = i + 1) print(sprintf("tas jargon: guide %g %s%s\n", i + 1, jg_gl[i], (i == jg_pick) ? " (picked)" : ""));
		return;
	}
	if (w == "list")
	{
		for (i = 0; i < jg_n; i = i + 1)
			{ a = jg_o[i]; print(sprintf("tas jargon: waypoint %g %s t=%.3f %.1f %.1f %.1f%s\n", i + 1, TASOptUI_WpKind(jg_k[i]), jg_t[i], a_x, a_y, a_z, jg_mv[i] ? " moved" : "")); }
		print(sprintf("tas jargon: %g waypoints, %g edits to undo; saved run: %g of %g\n", jg_n, jgu_top, jg_knext, jg_kof));
		return;
	}
	i = stof(argv(3)) - 1;
	if (!(i >= 0 && i < jg_n) || i != floor(i)) { print(sprintf("tas jargon %s: waypoint 1..%g\n", w, jg_n)); return; }
	if (w == "set" && argc == 6)
	{	// as the panel's field: the waypoint's axis typed, Enter
		ax = (argv(4) == "x") ? 0 : ((argv(4) == "y") ? 1 : ((argv(4) == "z") ? 2 : -1));
		if (ax < 0 || !TASOptUI_WpEditable(jg_k[i])) { print("tas jargon set: a board, hop or air point's x, y or z\n"); return; }
		TASOptUI_FieldFocus(i, ax, ""); jgf_buf = argv(5);
		TASOptUI_FieldCommit();
		return;
	}
	if (w == "field" && argc == 5)
	{
		ax = (argv(4) == "x") ? 0 : ((argv(4) == "y") ? 1 : ((argv(4) == "z") ? 2 : -1));
		if (ax < 0 || !TASOptUI_WpEditable(jg_k[i])) { print("tas jargon field: a board, hop or air point's x, y or z\n"); return; }
		if (jgf_on) TASOptUI_FieldCommit();
		if (!TASOptUI_EditOK()) return;
		a = jg_o[i];
		TASOptUI_FieldFocus(i, ax, sprintf("%.1f", (ax == 0) ? a_x : ((ax == 1) ? a_y : a_z)));
		TASOptUI_Select(i); sui_field_focus(TASOptUI_FieldId());
		print(sprintf("tas jargon: field %g %s open \"%s\"\n", i + 1, argv(4), jgf_buf));
		return;
	}
	if (w == "air")
	{
		a = (i + 1 < jg_n) ? 0.5 * (jg_o[i] + jg_o[i + 1]) + '0 0 64' : jg_o[i] + '0 0 128';
		if (TASOptUI_AirAdd(a)) TASOptUI_WpPush(3, 0, '0 0 0', a);
		return;
	}
	if (w == "del")
	{
		if (jg_k[i] != 5) { print("tas jargon del: only air points\n"); return; }
		a = jg_o[i];
		if (TASOptUI_AirDel(a)) TASOptUI_WpPush(4, 0, a, '0 0 0');
		return;
	}
	print("tas jargon: start | takeover | redofrom N | mode 0|1|2|3 | guide N | guides | set N x|y|z V | field N x|y|z | air N | del N | undo | redo | list\n");
};
void(vector at, float width, float tsz, float hint, float row, float running, string label) TASOptUI_DrawJargon =
{
	local float i, q, half, third, kw, fw, rows, tk;
	local vector chip3, lp, o, a;
	local string cn, cw;
	TASOptUI_Refind(); TASOptUI_UndoKeep();
	cn = TASJargon_CourseLabel(jg_cpick); cw = TASJargon_CourseWords();
	half = (width - 6) / 2; third = (width - 12) / 3; chip3 = [third, row, 0];
	sui_text(at, [hint, hint], label, running ? SUI_THEME_TEXT : SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 2;
	// what to surf and whose run it follows (Lex, 13 Nov: dropdowns, not a chip each)
	sui_text(at, [hint, hint], "Course", SUI_THEME_DIM, 1, 0);
	sui_text(at + [half + 6, 0, 0], [hint, hint], "Guide run", SUI_THEME_DIM, 1, 0);
	at_y = at_y + hint * 1.5;
	TASOptUI_Drop("jgd_c", 1, at, [half, row, 0], cn, hint);
	if (jg_gn) TASOptUI_Drop("jgd_g", 2, at + [half + 6, 0, 0], [half, row, 0], TASOptUI_Guide(), hint);
	at_y = at_y + row + hint;
	if (!jg_gn)
	{
		sui_text(at, [hint, hint], (jg_cn > 1) ? sprintf("No run of %s here yet: turn one on in the leaderboard.", cn)
			: "Turn on a run's line in the leaderboard and it shows up here.", SUI_THEME_MUTED, 1, 0);
		return;
	}
	// how the run starts, and Start
	sui_text(at, [hint, hint], "Jargon takes over:", SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.5;
	q = (width - 18) / 4;
	if (Profile_Chip("jgp_m0", at, [q, row, 0], "At my jump", hint, autocvar_tas_jargon_startmode == 0)) cvar_set("tas_jargon_startmode", "0");
	sui_tooltip_for("jgp_m0", "Arm, prestrafe in the start box and jump: Jargon takes over at your jump.", max(1, hint / 7));
	if (Profile_Chip("jgp_m1", at + [q + 6, 0, 0], [q, row, 0], "Leaving the start", hint, autocvar_tas_jargon_startmode == 1))
		cvar_set("tas_jargon_startmode", "1");
	sui_tooltip_for("jgp_m1", "Arm, prestrafe out of the start box: Jargon takes over at its edge.", max(1, hint / 7));
	if (Profile_Chip("jgp_m3", at + [2 * (q + 6), 0, 0], [q, row, 0], "When I press", hint, autocvar_tas_jargon_startmode == 3))
		cvar_set("tas_jargon_startmode", "3");
	sui_tooltip_for("jgp_m3", "Arm in any start box and surf as far as you like: Take over now (or a key bound to tas jargon takeover) hands it to Jargon from where you are, in the stage you are in.", max(1, hint / 7));
	if (Profile_Chip("jgp_m2", at + [3 * (q + 6), 0, 0], [q, row, 0], "By itself", hint, autocvar_tas_jargon_startmode == 2))
		cvar_set("tas_jargon_startmode", "2");
	sui_tooltip_for("jgp_m2", "Jargon starts the course itself from its start box.", max(1, hint / 7));
	at_y = at_y + row + 3;
	tk = (running && taso_armed && taso_armmode == 3);
	if (Profile_Chip("jgp_start", at, [third, row * 1.4, 0], tk ? ((Timer_Stat(STAT_FS_TIMERSTATE) == TS_RUNNING) ? "Take over now" : "Leave the box first")
		: ((autocvar_tas_jargon_startmode == 2) ? sprintf("Start %s", cn) : ((autocvar_tas_jargon_startmode == 3) ? "Arm" : sprintf("Arm %s", cn))), tsz, tk))
	{
		if (tk) TASOptUI_Takeover();
		else TASOptUI_Start();
	}
	if (Profile_Chip("jgp_stop", at + [third + 6, 0, 0], [third, row * 1.4, 0], "Stop", tsz, running)) TASOptUI_Stop(1);
	if (Profile_Chip("jgp_play", at + [2 * (third + 6), 0, 0], [third, row * 1.4, 0], "Back to playing", tsz, FALSE))
		{ TASOptUI_Stop(0); localcmd("tas play\n"); TASUI_Close(); }
	at_y = at_y + row * 1.4 + 3;
	if (autocvar_tas_jargon_startmode != 2)
	{
		sui_text(at, [hint, hint], (autocvar_tas_jargon_startmode == 3) ? "Arm in any start box, surf, then Take over now (or bind tas jargon takeover)."
			: "Arm, then stand in the course's start box (!r, or !s for a stage) and go.", SUI_THEME_MUTED, 1, 0);
		at_y = at_y + hint * 1.6;
	}
	if (jg_knext > 0 && cw != "")
	{
		if (Profile_Chip("jgs_cont", at, [width, row, 0], (jg_knext >= jg_kof) ? sprintf("Watch the saved %s run", cn)
			: sprintf("Continue %s from ramp %g of %g", cn, jg_knext + 1, jg_kof), hint, FALSE))
			TASOptUI_Go(sprintf("tas autosurf continue %g %g%s\n", jg_ct[jg_cpick], jg_cl[jg_cpick], TASOptUI_ContinueWords()));
		at_y = at_y + row + 3;
	}
	sui_text(at, [hint, hint], "Camera", SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.5;
	if (Profile_Chip("jgs_c0", at, chip3, "First person", hint, !autocvar_tas_viz_cam)) cvar_set("tas_viz_cam", "0");
	if (Profile_Chip("jgs_c2", at + [third + 6, 0, 0], chip3, "Chase", hint, autocvar_tas_viz_cam == 2)) cvar_set("tas_viz_cam", "2");
	if (Profile_Chip("jgs_c1", at + [2 * (third + 6), 0, 0], chip3, "Overview", hint, autocvar_tas_viz_cam == 1)) cvar_set("tas_viz_cam", "1");
	at_y = at_y + row + hint;
	// the lower half: the waypoints, or the options
	if (Profile_Chip("jgl_w", at, [half, row, 0], "Waypoints", hint, !jgo_open)) jgo_open = 0;
	if (Profile_Chip("jgl_o", at + [half + 6, 0, 0], [half, row, 0], "Options", hint, jgo_open)) { if (jgf_on) TASOptUI_FieldCommit(); jgo_open = 1; }
	at_y = at_y + row + hint;
	if (jgo_open) at_y = TASOptUI_DrawOptions(at, width, hint, row);
	else
	{
	// the waypoints: in order, X Y Z typed (Enter sets one, Esc leaves it), the selected one lit in the world
	sui_text(at, [hint, hint], (jg_n > 0) ? sprintf("Waypoints (%g): click X, Y or Z to type it, Enter to set", jg_n)
		: "Waypoints: planning...", SUI_THEME_DIM, 1, 0);
	at_y = at_y + hint * 1.5;
	kw = width * 0.3; fw = (width - kw - tsz - 18) / 3;
	rows = min(max(jg_n, 1), 8); jgw_rowh = row; jgw_rows = rows;
	sui_text(at + [4, 0, 0], [hint * 0.85, hint * 0.85], "#   Kind", SUI_THEME_MUTED, 1, 0);
	TASOptUI_RText(at + [kw + 6, 0, 0], [fw, hint * 0.85, 0], "X", hint * 0.85, SUI_THEME_MUTED);
	TASOptUI_RText(at + [kw + 12 + fw, 0, 0], [fw, hint * 0.85, 0], "Y", hint * 0.85, SUI_THEME_MUTED);
	TASOptUI_RText(at + [kw + 18 + 2 * fw, 0, 0], [fw, hint * 0.85, 0], "Z", hint * 0.85, SUI_THEME_MUTED);
	at_y = at_y + hint * 1.3;
	sui_list_view_begin("jgw_list", at, [width, rows * row, 0], [width - tsz, row, 0], jg_n, jgw_scroll, [0, tsz]);
	lp = '0 0 0';
	for (i = sui_list_item(lp); i > -1; i = sui_list_item(lp))
	{
		if (i == jgw_sel || (running && i == taso_i)) sui_fill(lp, [width - tsz, row - 2, 0], SUI_THEME_CHIP, (i == jgw_sel) ? 0.6 : 0.35, 0);
		if (TASOptUI_Cell(sprintf("jgw_r%g", i), lp, [kw, row - 2, 0], sprintf("%g   %s%s", i + 1, TASOptUI_WpKind(jg_k[i]), jg_mv[i] ? " *" : ""),
			hint, i == jgw_sel, FALSE))
			TASOptUI_Select((jgw_sel == i) ? -1 : i);
		if (TASOptUI_WpEditable(jg_k[i]))
		{
			TASOptUI_WpField(i, 0, lp + [kw + 6, 0, 0], [fw, row - 2, 0], hint);
			TASOptUI_WpField(i, 1, lp + [kw + 12 + fw, 0, 0], [fw, row - 2, 0], hint);
			TASOptUI_WpField(i, 2, lp + [kw + 18 + 2 * fw, 0, 0], [fw, row - 2, 0], hint);
		}
		else
		{
			o = jg_o[i];        // planned from the guide run: shown, not typed
			TASOptUI_RText(lp + [kw + 6, 0, 0], [fw, row - 2, 0], sprintf("%.1f", o_x), hint, SUI_THEME_MUTED);
			TASOptUI_RText(lp + [kw + 12 + fw, 0, 0], [fw, row - 2, 0], sprintf("%.1f", o_y), hint, SUI_THEME_MUTED);
			TASOptUI_RText(lp + [kw + 18 + 2 * fw, 0, 0], [fw, row - 2, 0], sprintf("%.1f", o_z), hint, SUI_THEME_MUTED);
		}
	}
	sui_list_view_end();
	at_y = at_y + rows * row + 4;
	// edits
	if (Profile_Chip("jgp_air", at, chip3, (jgw_sel >= 0) ? sprintf("+ Air point after %g", jgw_sel + 1) : "+ Air point (pick a row)", hint, FALSE))
	if (jgw_sel >= 0 && jgw_sel < jg_n)
	{	// between the picked point and the next, a little above: then type where it goes
		a = (jgw_sel + 1 < jg_n) ? 0.5 * (jg_o[jgw_sel] + jg_o[jgw_sel + 1]) + '0 0 64' : jg_o[jgw_sel] + '0 0 128';
		if (TASOptUI_AirAdd(a)) TASOptUI_WpPush(3, 0, '0 0 0', a);
	}
	if (Profile_Chip("jgp_del", at + [third + 6, 0, 0], chip3, "Delete air point", hint, FALSE))
	if (jgw_sel >= 0 && jgw_sel < jg_n)
	{
		if (jg_k[jgw_sel] == 5) { a = jg_o[jgw_sel]; if (TASOptUI_AirDel(a)) TASOptUI_WpPush(4, 0, a, '0 0 0'); jgw_sel = -1; }
		else print("tas jargon: only air points are deleted; a guide point goes back with Reset\n");
	}
	if (Profile_Chip("jgp_edit", at + [2 * (third + 6), 0, 0], chip3, jg_edit ? "Done moving" : "Move in the world", hint, jg_edit))
	{
		if (jg_edit) TASJargon_EditEnd(); else TASJargon_EditStart();
	}
	at_y = at_y + row + 3;
	if (Profile_Chip("jgp_undo", at, chip3, sprintf("Undo (%g)", jgu_top), hint, FALSE)) TASOptUI_WpUndo(TRUE);
	if (Profile_Chip("jgp_redo", at + [third + 6, 0, 0], chip3, sprintf("Redo (%g)", jgu_n - jgu_top), hint, FALSE)) TASOptUI_WpUndo(FALSE);
	if (Profile_Chip("jgp_reset", at + [2 * (third + 6), 0, 0], chip3, (cltime < jgp_resetask) ? "Click again to reset" : "Reset to the guide run", hint,
		cltime < jgp_resetask))
	{
		if (running) print("tas jargon: Stop Jargon to reset its waypoints\n");
		else if (cltime >= jgp_resetask) jgp_resetask = cltime + 3;      // twice: it moves every guide point back
		else { jgp_resetask = 0; TASOptUI_Reset(); }
	}
	at_y = at_y + row + 3;
	// P1531 (Lex: "a safer route... edit the waypoints and have JARGON actually try to follow them"): its last run rewound
	// to a waypoint, then on from there with your edits (`tas autosurf redo N`; a running one stops first)
	if (Profile_Chip("jgp_redofrom", at, [width, row, 0], (jgw_sel >= 0) ? sprintf("Redo from waypoint %g with my edits", jgw_sel + 1)
		: "Redo from a waypoint (pick a row)", hint, FALSE))
	if (jgw_sel >= 0 && jgw_sel < jg_n)
		TASOptUI_Go(sprintf("tas autosurf redo %g %.3f\n", jgw_sel + 1, jg_t[jgw_sel]));      // by its demo time (review 1531)
	sui_tooltip_for("jgp_redofrom", "Rewinds Jargon's last run to the start of this waypoint and goes on from there with your edits. The waypoint must have been reached in that run.", max(1, hint / 7));
	}       // the waypoints
	at_y = at_y + row + hint;
	if (Profile_Chip("jgs_l1", at, [half, row, 0], "Search lines", hint, cvar("tas_viz"))) cvar_set("tas_viz", cvar("tas_viz") ? "0" : "1");
	if (Profile_Chip("jgs_l2", at + [half + 6, 0, 0], [half, row, 0], "Thinking panel", hint, autocvar_tas_searchpanel))
		cvar_set("tas_searchpanel", autocvar_tas_searchpanel ? "0" : "1");
	if (jgd_open == 2 && !jg_gn) jgd_open = 0;
	if (jgd_open)
	{
		sui_action_element(jgd_pos - '4000 4000 0', '8000 8000 0', "jgd_shade", sui_noop);
		if (sui_is_released("jgd_shade")) jgd_open = 0;
		jgd_n = (jgd_open == 1) ? jg_cn : jg_gn;
		jgd_rows = bound(1, jgd_n, 10);
		sui_style_panel(jgd_pos, [jgd_w, jgd_rows * row + 8, 0], 4, 1);
		sui_list_view_begin("jgd_list", jgd_pos + '4 4 0', [jgd_w - 8, jgd_rows * row, 0], [jgd_w - 8 - tsz, row, 0], jgd_n, jgd_scroll, [0, tsz]);
		lp = '0 0 0';
		for (i = sui_list_item(lp); i > -1; i = sui_list_item(lp))
		{
			q = (jgd_open == 1) ? (jg_cpick == i) : (jg_pick == i);
			if (TASOptUI_Cell(sprintf("jgd_%g_%g", jgd_open, i), lp, [jgd_w - 8 - tsz, row - 2, 0],
				(jgd_open == 1) ? TASJargon_CourseLabel(i) : jg_gl[i], hint, q, FALSE))
			{
				if (jgd_open == 1) { if (jg_cpick != i) { TASOptUI_Course(i); jgu_n = jgu_top = 0; } }      // switching stops the run first
				else TASOptUI_GuidePick(i);
				jgd_open = 0;
			}
		}
		sui_list_view_end();
	}
};
void(vector at, float width, float tsz, float hint, float row) TASOptUI_Draw =
{
	local float running;
	local string label, cn;
	TASJargon_Guides();
	TASJargon_Saved();
	running = (taso_state == 1);
	// the route fills itself in: the picked run's plan as soon as the tab is open or the pick changes (Lex, 10 Nov)
	if (!running && jg_gn && (jg_planned != jg_gp[jg_pick] || jg_plannedc != jg_cpick)) TASJargon_RequestPlan();
	cn = TASJargon_CourseLabel(jg_cpick);
	if (running && taso_armed) label = (taso_armmode == 3) ? "Armed: surf as you like -- Take over now hands it to Jargon from where you are"
		: ((taso_armmode == 1) ? "Armed: Jargon takes over when you leave the start zone"
		: "Armed: prestrafe and jump -- Jargon takes over at your jump");
	else if (running) label = sprintf("Surfing %s: waypoint %g of %g, try %g", cn, taso_i + 1, taso_n, taso_try + 1);
	else label = (taso_note != "") ? taso_note : "Pick a course and how Jargon takes over, then Start or Arm.";
	TASOptUI_DrawJargon(at, width, tsz, hint, row, running, label);
};
