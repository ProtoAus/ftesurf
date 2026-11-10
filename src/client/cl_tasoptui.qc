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
		s = sprintf("Best line makes it at %g u/s", tsp_speed);
		if (tsp_ref > 0) s = strcat(s, sprintf(" (%s %g, %s%g)", TASOptUI_Guide(), tsp_ref, (tsp_speed >= tsp_ref) ? "+" : "", tsp_speed - tsp_ref));
		col = (tsp_ref > 0 && tsp_speed < tsp_ref * 0.98) ? SUI_THEME_WARN : SUI_THEME_GOOD;
	}
	else if (tsp_flags & 64) { s = "Best line boards, then falls off the ramp"; col = SUI_THEME_WARN; }
	else if (tsp_flags & 2) { s = sprintf("Best line makes it, but too slowly: %g u/s", tsp_speed); col = SUI_THEME_WARN; }
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
	TASSearch_Reason([at_x, y, 0], w, tsz, "Brushed a wall (costs it speed)", tsp_wall, tsp_evals, SUI_THEME_BAD); y = y + row * 0.85;
	TASSearch_Reason([at_x, y, 0], w, tsz, "Made it, too slowly to count", tsp_weak, tsp_evals, SUI_THEME_WARN); y = y + row * 0.85;
	TASSearch_Reason([at_x, y, 0], w, tsz, "Made it only by an edge bug", tsp_edge, tsp_evals, SUI_THEME_ACCENT); y = y + row * 0.85;
	TASSearch_Reason([at_x, y, 0], w, tsz, "Boarded, then fell off the ramp", tsp_brief, tsp_evals, SUI_THEME_WARN); y = y + row * 0.85;
	TASSearch_Reason([at_x, y, 0], w, tsz, "Hit a trigger (cut there)", tsp_cut, tsp_evals, SUI_THEME_MUTED); y = y + row * 1.05;
	// the best line's speed, generation by generation
	TASSearch_Line([at_x, y, 0], (tsp_ref > 0) ? "Best speed by generation (line: the guide)" : "Best speed by generation", tsz * 0.8, SUI_THEME_MUTED, w);
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
	if (taso_state == 1 && was != 1) { for (k = 0; k < TASO_STRETCHES; k = k + 1) taso_rb[k] = taso_rf[k] = 0; taso_lastk = -1; }
	else if (taso_state == 1 && taso_i < wasi)      // a backtrack: what came after it is to be done again
		for (k = taso_i; k < TASO_STRETCHES; k = k + 1) taso_rb[k] = taso_rf[k] = 0;
	if (rk >= 0 && rk < TASO_STRETCHES) { taso_rb[rk] = rb; taso_rf[rk] = (rf > 0) ? rf : -1; taso_lastk = rk; }   // -1: a route point
	if (substring(taso_note, 0, 18) == "saved for Continue") jg_kat = 0;
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
var float taso_effort = 1;      // 0 quick, 1 normal, 2 thorough
var float autocvar_tas_jargon_wide = 0;     // P1476: flights weave wider (Lex: no flip a tick) -- needs an engine with it
var float autocvar_tas_jargon_spots = 0;    // 1: each board tries 5 spots on its ramp (`spots`); 2: the best of 4 lines (`beam`, P1483)
string() TASOptUI_Effort =
{
	if (taso_effort == 0) return " tries 1 rideknots low";
	if (taso_effort == 2) return " tries 3 rideknots polish low backs 30";
	return " tries 2 rideknots low";
};
void(vector at, float width, float tsz, float hint, float row) TASOptUI_Draw =
{
	local float i, half, third, running, nb, nh, na, nm, q, st;
	local vector chip, chip3;
	local string label, go, cw, cn;
	TASJargon_Guides();
	TASJargon_Saved();
	running = (taso_state == 1);
	// the route fills itself in: the picked run's plan as soon as the tab is open or the pick changes (Lex, 10 Nov)
	if (!running && jg_gn && (jg_planned != jg_gp[jg_pick] || jg_plannedc != jg_cpick)) TASJargon_RequestPlan();
	cn = TASJargon_CourseLabel(jg_cpick); cw = TASJargon_CourseWords();
	half = (width - 6) / 2; chip = [half, row, 0];
	third = (width - 12) / 3; chip3 = [third, row, 0];
	sui_text(at, [hint, hint], "Jargon finds a fast line through the map, ramp by ramp, guided by a run you pick.", SUI_THEME_DIM, 1, 0);
	at_y = at_y + hint * 1.7;
	if (running) label = sprintf("Surfing: ramp %g of %g, try %g -- %s", taso_i + 1, taso_n, taso_try + 1, taso_note);
	else label = (taso_note != "") ? taso_note : "Pick a guide run, check its route, then surf.";
	sui_text(at, [hint, hint], label, running ? SUI_THEME_TEXT : SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 2;

	// P1478: the course (Lex, 11 Nov: maps, bonuses and stages with a click) -- the map's own, from its zones
	st = 1;
	if (jg_cn > 1)
	{
		sui_text(at, [tsz, tsz], "1   Course", SUI_THEME_TEXT, 1, 0); at_y = at_y + tsz * 1.6;
		q = (width - 18) / 4;
		for (i = 0; i < jg_cn; i = i + 1)
			if (Profile_Chip(sprintf("jg_k%g", i), at + [(i - 4 * floor(i / 4)) * (q + 6), floor(i / 4) * (row + 3), 0], [q, row, 0],
				TASJargon_CourseLabel(i), hint, jg_cpick == i))
				if (!running) { jg_cpick = i; jg_gat = 0; jg_kat = 0; }
		at_y = at_y + ceil(jg_cn / 4) * (row + 3) + hint;
		st = 2;
	}
	// the guide run
	sui_text(at, [tsz, tsz], sprintf("%g   Guide run", st), SUI_THEME_TEXT, 1, 0); at_y = at_y + tsz * 1.6;
	if (!jg_gn)
	{
		sui_text(at, [hint, hint], (jg_cn > 1) ? sprintf("No run of %s here yet: turn one on in the leaderboard.", cn)
			: "Turn on a run's line in the leaderboard and it shows up here.", SUI_THEME_MUTED, 1, 0);
		at_y = at_y + hint * 1.9;
	}
	for (i = 0; i < jg_gn; i = i + 1)
		if (Profile_Chip(sprintf("jg_g%g", i), at + [(i & 1) * (half + 6), floor(i / 2) * (row + 3), 0], chip, jg_gl[i], hint, jg_pick == i))
			if (!running) { jg_pick = i; TASJargon_RequestPlan(); }
	at_y = at_y + ceil(jg_gn / 2) * (row + 3) + hint;

	// 2: its route
	nb = nh = na = nm = 0;
	for (i = 0; i < jg_n; i = i + 1)
	{
		if (jg_k[i] == 1) nb = nb + 1;
		if (jg_k[i] == 2) nh = nh + 1;
		if (jg_k[i] == 5) na = na + 1;
		if (jg_mv[i]) nm = nm + 1;
	}
	sui_text(at, [tsz, tsz], sprintf("%g   Route", st + 1), SUI_THEME_TEXT, 1, 0);
	label = (jg_n && jg_planned == jg_gp[jg_pick] && jg_plannedc == jg_cpick) ? sprintf("%g ramps, %g bhops%s%s", nb, nh, na ? sprintf(", %g air points", na) : "",
		nm ? sprintf(", %g moved", nm) : "") : (jg_gn ? "press Show route" : "");
	sui_text(at + [tsz * 7, tsz * 0.15, 0], [hint, hint], label, SUI_THEME_DIM, 1, 0);
	at_y = at_y + tsz * 1.6;
	if (Profile_Chip("jg_show", at, chip, (jg_n && jg_planned == jg_gp[jg_pick] && jg_plannedc == jg_cpick) ? "Show route again" : "Show route", hint, FALSE))
		TASJargon_RequestPlan();
	if (Profile_Chip("jg_edit", at + [half + 6, 0, 0], chip, "Edit in the world", hint, FALSE)) TASJargon_EditStart();
	at_y = at_y + row + 3;
	if (Profile_Chip("jg_air", at, chip, "Add air point here", hint, FALSE)) { localcmd("tas route here\n"); jg_replan = cltime + 0.4; }
	if (Profile_Chip("jg_reset", at + [half + 6, 0, 0], chip, "Undo my moves", hint, FALSE)) { localcmd("tas autosurf reset\n"); jg_replan = cltime + 0.3; }
	at_y = at_y + row + 3;
	sui_text(at, [hint, hint], "Edit closes this panel: fly with your movement keys and drag the handles.", SUI_THEME_MUTED, 1, 0);
	at_y = at_y + hint * 1.4;
	sui_text(at, [hint, hint], "Esc brings this panel back.", SUI_THEME_MUTED, 1, 0);
	at_y = at_y + hint * 2;

	// surf it: from the course's start (one click), on from the saved run, or from here
	sui_text(at, [tsz, tsz], sprintf("%g   Surf", st + 2), SUI_THEME_TEXT, 1, 0); at_y = at_y + tsz * 1.6;
	go = strcat(TASOptUI_Effort(), TASJargon_Airs() ? " air" : "", autocvar_tas_jargon_wide ? " wide" : "", (autocvar_tas_jargon_spots == 1) ? " spots" : ((autocvar_tas_jargon_spots == 2) ? " beam" : ""));
	if (cw != "") go = strcat(go, " finish");       // a course runs to its end box
	if (running)
	{
		if (Profile_Chip("jg_stop", at, [width, row, 0], "Stop", tsz, TRUE)) localcmd("tas autosurf stop\n");
		at_y = at_y + row + 3;
	}
	else
	{
		if (jg_gn)
		{
			if (Profile_Chip("jg_gostart", at, [width, row, 0], (cw != "") ? sprintf("Surf %s from its start", cn) : "Restart from the start zone", tsz, FALSE))
				localcmd(sprintf("tas autosurf %s%s start%s\n", jg_gp[jg_pick], go, cw));
			at_y = at_y + row + 3;
		}
		if (jg_knext > 0 && cw != "")
		{	// the run saved as it went (data/tasproj/<map>/jg_<course>): replayed, then on from the stretch it had reached
			if (Profile_Chip("jg_gocont", at, [width, row, 0], (jg_knext >= jg_kof) ? sprintf("Load the saved %s run (route done)", cn)
				: sprintf("Continue %s from stretch %g of %g", cn, jg_knext + 1, jg_kof), tsz, FALSE))
				localcmd(sprintf("tas autosurf continue %g %g%s\n", jg_ct[jg_cpick], jg_cl[jg_cpick], go));
			at_y = at_y + row + 3;
		}
		if (jg_gn)
		{
			if (Profile_Chip("jg_gohere", at, chip, "From here", hint, FALSE))
				localcmd(sprintf("tas autosurf %s%s%s\n", jg_gp[jg_pick], go, cw));
			at_y = at_y + row + 3;
			sui_text(at, [hint, hint], "Start: the box, prestrafe and jump are done for you; the run saves as it goes.", SUI_THEME_MUTED, 1, 0);
			at_y = at_y + hint * 1.4;
			sui_text(at, [hint, hint], "Continue: the saved run, then on from where it stopped. Here: from your pause.", SUI_THEME_MUTED, 1, 0);
			at_y = at_y + hint * 1.9;
		}
	}
	sui_text(at, [hint, hint], "Effort", SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.5;
	if (Profile_Chip("jg_e0", at, chip3, "Quick", hint, taso_effort == 0)) taso_effort = 0;
	if (Profile_Chip("jg_e1", at + [third + 6, 0, 0], chip3, "Normal", hint, taso_effort == 1)) taso_effort = 1;
	if (Profile_Chip("jg_e2", at + [2 * (third + 6), 0, 0], chip3, "Thorough", hint, taso_effort == 2)) taso_effort = 2;
	at_y = at_y + row + hint * 0.6;
	sui_text(at, [hint, hint], "Strafing in the air", SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.5;
	if (Profile_Chip("jg_w0", at, chip, "Tight (most accurate)", hint, !autocvar_tas_jargon_wide)) cvar_set("tas_jargon_wide", "0");
	if (Profile_Chip("jg_w1", at + [half + 6, 0, 0], chip, "Wider (looks human)", hint, autocvar_tas_jargon_wide)) cvar_set("tas_jargon_wide", "1");
	at_y = at_y + row + hint * 0.6;
	sui_text(at, [hint, hint], "Where it boards each ramp", SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.5;
	if (Profile_Chip("jg_spot0", at, chip3, "The guide's spot", hint, !autocvar_tas_jargon_spots)) cvar_set("tas_jargon_spots", "0");
	if (Profile_Chip("jg_spot1", at + [third + 6, 0, 0], chip3, "Try 5 spots", hint, autocvar_tas_jargon_spots == 1)) cvar_set("tas_jargon_spots", "1");
	if (Profile_Chip("jg_spot2", at + [2 * (third + 6), 0, 0], chip3, "Best of 4 lines", hint, autocvar_tas_jargon_spots == 2)) cvar_set("tas_jargon_spots", "2");
	at_y = at_y + row + hint * 0.6;
	sui_text(at, [hint, hint], "Camera while it thinks (it rides in first person)", SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.5;
	if (Profile_Chip("jg_c0", at, chip, "Mine", hint, !autocvar_tas_viz_cam)) cvar_set("tas_viz_cam", "0");
	if (Profile_Chip("jg_c1", at + [half + 6, 0, 0], chip, "Overview, third person", hint, autocvar_tas_viz_cam != 0)) cvar_set("tas_viz_cam", "1");
	at_y = at_y + row + hint * 0.6;
	if (Profile_Chip("jg_viz", at, chip, cvar("tas_viz") ? "Search lines: on" : "Search lines: off", hint, cvar("tas_viz")))
		cvar_set("tas_viz", cvar("tas_viz") ? "0" : "1");
	if (Profile_Chip("jg_panel", at + [half + 6, 0, 0], chip, autocvar_tas_searchpanel ? "Thinking panel: on" : "Thinking panel: off", hint, autocvar_tas_searchpanel))
		cvar_set("tas_searchpanel", autocvar_tas_searchpanel ? "0" : "1");
	at_y = at_y + row + hint;
	if (taso_n > 0)
	{	// the run so far: a numbered button a stretch, its colour bar how it went; one picked, the run redone from there
		sui_text(at, [hint, hint], "Stretches -- pick one to redo the run from there", SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.5;
		third = (width - 3 * (min(taso_n, 16) - 1)) / min(taso_n, 16);
		for (i = 0; i < taso_n && i < TASO_STRETCHES; i = i + 1)
		{
			chip3 = at + [(i - 16 * floor(i / 16)) * (third + 3), floor(i / 16) * (row + 7), 0];
			sui_roundbox(chip3 + [1, row + 1, 0], [third - 2, 3, 0], 1, TASOptUI_StretchCol(i), 1);
			if (Profile_Chip(sprintf("jg_s%g", i), chip3, [third, row, 0], ftos(i + 1), hint, taso_sel == i || (running && i == taso_i)))
				taso_sel = (taso_sel == i) ? -1 : i;
		}
		at_y = at_y + ceil(min(taso_n, TASO_STRETCHES) / 16) * (row + 7) + hint * 0.4;
		if (taso_sel >= 0 && !running)
		{
			if (Profile_Chip("jg_redo", at, [width, row, 0], sprintf("Redo the run from stretch %g", taso_sel + 1), hint, FALSE))
				localcmd(sprintf("tas autosurf redo %g\n", taso_sel + 1));
			at_y = at_y + row + 3;
		}
		if (taso_lastk >= 0)      // nested: && does not short-circuit here, and taso_rf[-1] is out of range
		{
			if (taso_rf[taso_lastk] < 0) label = sprintf("Point %g: %g u/s", taso_lastk + 1, taso_rb[taso_lastk]);
			else label = sprintf("Ramp %g: %g u/s, the guide run %g (%s%g)", taso_lastk + 1, taso_rb[taso_lastk], taso_rf[taso_lastk],
				(taso_rb[taso_lastk] >= taso_rf[taso_lastk]) ? "+" : "", taso_rb[taso_lastk] - taso_rf[taso_lastk]);
			sui_text(at, [hint, hint], label, SUI_THEME_DIM, 1, 0); at_y = at_y + hint * 1.6;
		}
	}
};
