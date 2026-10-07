/*
  Patch 545: the graph of the SAME retained samples as the world run lines.
  Slots 0..8 only: replay + eight board comparisons, never the live trail.
  Clocks align at Line_Range's run/stage start. Energy includes vertical speed,
  uses recorded gravity when pinned, otherwise an explicitly labelled g=800
  assumption, relative to its first shown run sample. Never bridges a break.

  A bounded min/max envelope preserves spikes in the retained line. It is built
  incrementally (2048 points/frame), not by walking eight 32K lines every draw.
  The hover reads actual samples, not the display envelope. Line_Add's existing
  cap/decimation still applies; this is not a second recorder or evidence reader.
*/
#define LG_SLOTS 9
#define LG_BINS 384
#define LG_STRIDE 12
#define LG_HAVE 8
#define LG_BREAK 9
#define LG_FIRSTT 10
#define LG_LASTT 11

float *lg_bins;
float lg_open, lg_buildslot, lg_buildpoint, lg_tmax, lg_cursor_t;
float lg_seen[LG_SLOTS], lg_seen_n[LG_SLOTS], lg_available[LG_SLOTS];
float lg_selected[LG_SLOTS], lg_ref[LG_SLOTS], lg_last[LG_SLOTS];
float lg_order[LG_SLOTS], lg_labely[LG_SLOTS];
vector lg_mouse, lg_plotp, lg_plotsize;

float(float s) LineGraph_Available =
{
	if (s == 0) return (rec_wt_open && ln_on[0] && cvar("hud_watch_path") > 0);
	return (sb_ln_st[s - 1] == SBL_ON && ln_on[s] && (lg_open || cvar("hud_lines_board") > 0));
};

vector(float s) LineGraph_Colour =
{
	if (s == 0) return '0.95 0.95 0.95';
	if (s == 1) return '0.30 0.80 1.00';
	if (s == 2) return '1.00 0.65 0.25';
	if (s == 3) return '0.55 1.00 0.45';
	if (s == 4) return '0.90 0.50 1.00';
	if (s == 5) return '1.00 0.45 0.55';
	if (s == 6) return '0.30 1.00 0.85';
	if (s == 7) return '1.00 0.95 0.35';
	return '0.55 0.65 1.00';
};

string(float s) LineGraph_Name =
{
	local string name;
	name = ln_owner[s];
	if (name == "" && s > 0) name = sb_ln_name[s - 1];
	if (name == "") name = "unknown";
	return sprintf("%g %s", s, substring(name, 0, 18));
};

float(float s, float i) LineGraph_Energy =
{
	local float b, speed, vz;
	local vector p;
	b = s * LN_CAP + i;
	p = ln_pos[b];
	speed = ln_spd[b];
	vz = ln_vz[b];
	if (ln_g[s] <= 0) return 0;
	return p_z + (speed * speed + vz * vz) / (2 * ln_g[s]);
};

// [horizontal speed, absolute energy-height, valid]. No endpoint clamping or
// interpolation across a break; an exact recorded sample is still readable.
vector(float s, float seconds) LineGraph_At =
{
	local float i, b, t, dt, f, a;
	local vector lo, hi;
	if (!LineGraph_Available(s)) return '0 0 0';
	b = s * LN_CAP;
	t = seconds + ln_start[s];
	i = Line_Find(s, t);
	if (i > ln_ib[s] || i < ln_ia[s]) return '0 0 0';
	hi = [ln_spd[b + i], LineGraph_Energy(s, i), 1];
	if (fabs(ln_t[b + i] - t) < 0.00001) return hi;
	if (i <= ln_ia[s]) return '0 0 0';
	a = i - 1;
	dt = ln_t[b + i] - ln_t[b + a];
	if (ln_brk[b + i] || dt <= 0) return '0 0 0';
	if (dt > max(0.25, ln_tick[s] * ln_step[s] * 2)) return '0 0 0';
	lo = [ln_spd[b + a], LineGraph_Energy(s, a), 1];
	f = bound(0, (t - ln_t[b + a]) / dt, 1);
	return lo + (hi - lo) * f;
};

void() LineGraph_Close =
{
	lg_open = FALSE;
	UI_CursorRelease(UIC_LINEGRAPH);
};

void() LineGraph_Open =
{
	Scores_Close();
	if (ui_cursor_claims & ~(UIC_WATCH | UIC_LINEGRAPH))
	{
		print("^3linegraph:^7 close the other cursor panel first.\n");
		return;
	}
	lg_open = TRUE;
	UI_CursorClaim(UIC_LINEGRAPH);
};

void() LineGraph_Reset =
{
	local float s;
	LineGraph_Close();
	Online_MomClear();
	rec_sb_momwant = sb_ln_momfetch = 0;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		lg_seen[s] = -1;
		lg_seen_n[s] = lg_available[s] = 0;
	}
};

void() LineGraph_Register =
{
	registercvar("hud_linegraph", "1", CVAR_ARCHIVE);
	registercvar("hud_linegraph_labels", "1", CVAR_ARCHIVE);
	registercommand("linegraph");
	lg_buildslot = LG_SLOTS;
	LineGraph_Reset();
};

void() LineGraph_Prepare =
{
	local float s, changed, have, i, b, j, k, t, v, e, gap, budget;
	changed = FALSE;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		have = LineGraph_Available(s);
		if (lg_available[s] != have || lg_seen[s] != ln_graphgen[s] || lg_seen_n[s] != ln_n[s])
		{
			changed = TRUE;
			if (lg_seen[s] != ln_graphgen[s]) lg_selected[s] = TRUE;
		}
	}
	if (changed)
	{
		if (!lg_bins) lg_bins = memalloc(sizeof(float) * LG_SLOTS * LG_BINS * LG_STRIDE);
		lg_tmax = 0;
		for (s = 0; s < LG_SLOTS; s = s + 1)
		{
			lg_available[s] = LineGraph_Available(s);
			lg_seen[s] = ln_graphgen[s];
			lg_seen_n[s] = ln_n[s];
			lg_last[s] = -1;
			if (lg_available[s])
			{
				i = max(ln_ia[s], Line_Find(s, ln_start[s]));
				lg_ref[s] = (i <= ln_ib[s]) ? LineGraph_Energy(s, i) : 0;
				lg_tmax = max(lg_tmax, ln_t[s * LN_CAP + ln_ib[s]] - ln_start[s]);
			}
			for (j = 0; j < LG_BINS; j = j + 1)
			{
				k = (s * LG_BINS + j) * LG_STRIDE;
				lg_bins[k + LG_HAVE] = lg_bins[k + LG_BREAK] = 0;
			}
		}
		lg_buildslot = lg_buildpoint = 0;
	}
	if (lg_tmax <= 0) { lg_buildslot = LG_SLOTS; return; }
	budget = 2048;
	while (lg_buildslot < LG_SLOTS && budget > 0)
	{
		s = lg_buildslot;
		i = max(lg_buildpoint, ln_ia[s]);
		if (!lg_available[s] || i > ln_ib[s])
		{
			lg_buildslot = lg_buildslot + 1;
			lg_buildpoint = 0;
			continue;
		}
		lg_buildpoint = i + 1;
		budget = budget - 1;
		b = s * LN_CAP;
		t = ln_t[b + i] - ln_start[s];
		if (t < 0) continue;
		j = bound(0, floor(t / lg_tmax * (LG_BINS - 1)), LG_BINS - 1);
		k = (s * LG_BINS + j) * LG_STRIDE;
		v = ln_spd[b + i];
		e = LineGraph_Energy(s, i) - lg_ref[s];
		gap = ln_brk[b + i];
		if (i > ln_ia[s])
		if (ln_t[b + i] - ln_t[b + i - 1] > max(0.25, ln_tick[s] * ln_step[s] * 2)) gap = TRUE;
		if (!lg_bins[k + LG_HAVE])
		{
			lg_bins[k] = lg_bins[k + 1] = lg_bins[k + 4] = v;
			lg_bins[k + 2] = lg_bins[k + 3] = lg_bins[k + 6] = e;
			lg_bins[k + LG_FIRSTT] = t;
			lg_bins[k + LG_HAVE] = 1;
		}
		else
		{
			lg_bins[k] = min(lg_bins[k], v);
			lg_bins[k + 1] = max(lg_bins[k + 1], v);
			lg_bins[k + 2] = min(lg_bins[k + 2], e);
			lg_bins[k + 3] = max(lg_bins[k + 3], e);
		}
		lg_bins[k + 5] = v;
		lg_bins[k + 7] = e;
		lg_bins[k + LG_LASTT] = t;
		lg_bins[k + LG_BREAK] = (lg_bins[k + LG_BREAK] || gap);
		lg_last[s] = j;
	}
};

void(vector p, string text, float size, vector col) LineGraph_Text =
{
	drawstring(p, text, [size, size], col, 1, 0);
};

void(vector p, vector size, float energy, float fontsz) LineGraph_Plot =
{
	local float s, j, k, prev, mn, mx, v0, v1, x, n, i, tmp, y, t;
	local vector col, pa, pb, sample;
	mn = energy ? -1 : 0;
	mx = 1;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	if (lg_available[s] && lg_selected[s])
	if (!energy || ln_g[s] > 0)
	for (j = 0; j < LG_BINS; j = j + 1)
	{
		k = (s * LG_BINS + j) * LG_STRIDE;
		if (!lg_bins[k + LG_HAVE]) continue;
		mn = min(mn, lg_bins[k + energy * 2]);
		mx = max(mx, lg_bins[k + energy * 2 + 1]);
	}
	mx = mx + (mx - mn) * 0.06;
	drawfill(p, size, SBC_BG, 0.92, 0);
	for (i = 0; i < 5; i = i + 1)
	{
		y = p_y + size_y * i / 4;
		drawline(1, [p_x, y], [p_x + size_x, y], SBC_DIM, 0.22, 0);
		LineGraph_Text([p_x + 3, bound(p_y, y - fontsz * 0.5, p_y + size_y - fontsz)], sprintf("%.0f", mx - (mx - mn) * i / 4), fontsz, SBC_DIM);
	}
	LineGraph_Text(p + [3, 0 - fontsz - 3], energy ? "Energy - start sample (height units)" : "Horizontal speed (u/s)", fontsz, SBC_TEXT);
	n = 0;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		if (!lg_available[s] || !lg_selected[s]) continue;
		if (energy && ln_g[s] <= 0) continue;
		col = LineGraph_Colour(s);
		prev = -1;
		for (j = 0; j < LG_BINS; j = j + 1)
		{
			k = (s * LG_BINS + j) * LG_STRIDE;
			if (!lg_bins[k + LG_HAVE]) continue;
			x = p_x + size_x * j / (LG_BINS - 1);
			v0 = lg_bins[k + energy * 2];
			v1 = lg_bins[k + energy * 2 + 1];
			pa = [x, p_y + size_y * (1 - (v0 - mn) / (mx - mn))];
			pb = [x, p_y + size_y * (1 - (v1 - mn) / (mx - mn))];
			// A bin containing a break is not joined across itself, even when
			// the break and its neighbour fell into one pixel bucket.
			if (!lg_bins[k + LG_BREAK]) drawline(1, pa, pb, col, 0.65, 0);
			if (prev >= 0)
			if (!lg_bins[k + LG_BREAK] && !lg_bins[prev + LG_BREAK])
			if (lg_bins[k + LG_FIRSTT] - lg_bins[prev + LG_LASTT] <= max(0.25, ln_tick[s] * ln_step[s] * 2))
			{
				pa = [p_x + size_x * (prev / LG_STRIDE - s * LG_BINS) / (LG_BINS - 1),
				      p_y + size_y * (1 - (lg_bins[prev + 5 + energy * 2] - mn) / (mx - mn))];
				pb = [x, p_y + size_y * (1 - (lg_bins[k + 4 + energy * 2] - mn) / (mx - mn))];
				drawline(1.5, pa, pb, col, 0.9, 0);
			}
			prev = k;
		}
		if (prev >= 0)
		{
			lg_order[n] = s;
			lg_labely[s] = p_y + size_y * (1 - (lg_bins[prev + 5 + energy * 2] - mn) / (mx - mn));
			n = n + 1;
		}
	}
	// Sort endpoint labels by y, then separate them without swapping identity.
	for (i = 1; i < n; i = i + 1)
	for (j = i; j > 0; j = j - 1)
	{
		if (lg_labely[lg_order[j]] >= lg_labely[lg_order[j - 1]]) break;
		tmp = lg_order[j]; lg_order[j] = lg_order[j - 1]; lg_order[j - 1] = tmp;
	}
	y = p_y;
	for (i = 0; i < n; i = i + 1)
	{
		s = lg_order[i];
		lg_labely[s] = max(lg_labely[s], y);
		y = lg_labely[s] + fontsz + 1;
	}
	t = max(0, y - (p_y + size_y));
	for (i = 0; i < n; i = i + 1)
	{
		s = lg_order[i];
		k = (s * LG_BINS + lg_last[s]) * LG_STRIDE;
		col = LineGraph_Colour(s);
		pa = [p_x + size_x * lg_last[s] / (LG_BINS - 1),
		      p_y + size_y * (1 - (lg_bins[k + 5 + energy * 2] - mn) / (mx - mn))];
		pb = [p_x + size_x + 5, lg_labely[s] - t];
		drawline(1, pa, pb, col, 0.5, 0);
		LineGraph_Text(pb, LineGraph_Name(s), fontsz, col);
	}
	if (lg_open)
	if (lg_mouse_x >= p_x && lg_mouse_x <= p_x + size_x)
	{
		x = lg_mouse_x;
		t = (x - p_x) / size_x * lg_tmax;
		drawline(1, [x, p_y], [x, p_y + size_y], '1 1 1', 0.8, 0);
		for (s = 0; s < LG_SLOTS; s = s + 1)
		if (lg_available[s] && lg_selected[s])
		if (!energy || ln_g[s] > 0)
		{
			sample = LineGraph_At(s, t);
			if (!sample_z) continue;
			v0 = energy ? sample_y - lg_ref[s] : sample_x;
			y = p_y + size_y * (1 - (v0 - mn) / (mx - mn));
			drawfill([x - 2, y - 2], [4, 4], LineGraph_Colour(s), 1, 0);
		}
	}
};

void(vector scr) LineGraph_Draw =
{
	local float have, s, fs, w, h, ph, labelw, t, y, action, toggle;
	local vector p, plot, size, sample, col;
	local string text, id;
	if (lg_open)
	if (rec_sb_open || ui_he_open || ui_rs_cursor || ui_ev_cursor) LineGraph_Close();
	if (!lg_open && !cvar("hud_linegraph")) return;
	if (rec_sb_open || ui_he_open || ui_rs_cursor || ui_ev_cursor) return;
	LineGraph_Prepare();
	have = 0;
	for (s = 0; s < LG_SLOTS; s = s + 1) if (lg_available[s]) have = have + 1;
	if (!have && !lg_open) return;
	Font_Set(ui_font_ui);
	fs = Font_Px(max(8, min(12 * bound(0.75, cvar("hud_scale"), 2), scr_y / 60)));
	w = min(scr_x - fs * 2, lg_open ? 1050 : 760);
	if (lg_open) w = min(w, scr_x * 0.90);
	else w = min(w, scr_x * 0.65);
	labelw = fs * 12;
	ph = max(fs * max(6, have + 1), lg_open ? min(155, scr_y * 0.18) : min(105, scr_y * 0.12));
	h = ph * 2 + fs * 10;
	if (lg_open) h = ph * 2 + fs * (14 + have * 1.4);
	p = lg_open ? [floor((scr_x - w) / 2), floor((scr_y - h) / 2)] : [scr_x - w - fs, scr_y - h - fs * 4];
	plot = p + [fs, fs * 4];
	size = [w - labelw - fs * 2, ph];
	lg_plotp = plot;
	lg_plotsize = size;
	if (lg_open) sui_begin(scr_x, scr_y);
	drawfill(p, [w, h], SBC_PANEL, lg_open ? 0.97 : 0.80, 0);
	LineGraph_Text(p + [fs, fs], lg_open ? "Run comparison: elapsed seconds from each run/stage start" : "Run graphs  |  linegraph for mouse comparison", fs, SBC_TEXT);
	action = 0;
	toggle = -1;
	if (lg_open)
	{
		sui_action_element(p + [w - fs * 7, fs], [fs * 6, fs * 2], "lg_close", sui_noop);
		LineGraph_Text(p + [w - fs * 7, fs], "close", fs, SBC_DIM);
		if (sui_is_released("lg_close")) action = 1;
	}
	if (lg_buildslot < LG_SLOTS)
		LineGraph_Text(plot, "Building sampled graphs...", fs, SBC_DIM);
	else if (have)
	{
		LineGraph_Plot(plot, size, FALSE, fs);
		LineGraph_Plot(plot + [0, ph + fs * 3], size, TRUE, fs);
		for (s = 0; s < 5; s = s + 1)
		{
			t = lg_tmax * s / 4;
			LineGraph_Text(plot + [size_x * s / 4, ph * 2 + fs * 4], sprintf("%.2fs", t), fs, SBC_DIM);
		}
	}
	else LineGraph_Text(plot, "Tick run-line boxes in the leaderboard to load comparisons.", fs, SBC_DIM);
	if (lg_open)
	{
		t = bound(0, (lg_mouse_x - plot_x) / size_x, 1) * lg_tmax;
		lg_cursor_t = t;
		y = p_y + ph * 2 + fs * 12;
		LineGraph_Text([plot_x, y - fs * 2], sprintf("Mouse: %.3fs  |  E = z + full v^2/2g, relative to first run sample", t), fs, SBC_TEXT);
		for (s = 0; s < LG_SLOTS; s = s + 1)
		{
			if (!lg_available[s]) continue;
			col = LineGraph_Colour(s);
			id = sprintf("lg_slot%g", s);
			text = strcat(lg_selected[s] ? "[x] " : "[ ] ", LineGraph_Name(s));
			sui_action_element([plot_x, y], [w - fs * 2, fs * 1.4], id, sui_noop);
			if (sui_is_released(id)) toggle = s;
			LineGraph_Text([plot_x, y], text, fs, col);
			text = "speed n/a   E n/a";
			sample = LineGraph_At(s, t);
			if (sample_z)
			{
				text = sprintf("speed %.1f u/s   E n/a (no recorded gravity)", sample_x);
				if (ln_g[s] > 0)
					text = sprintf("speed %.1f u/s   E %+.1f u   g=%g%s", sample_x, sample_y - lg_ref[s], ln_g[s], ln_g_assumed[s] ? " assumed" : " recorded");
			}
			LineGraph_Text([plot_x + fs * 21, y], text, fs, col);
			y = y + fs * 1.4;
		}
		sui_end();
	}
	if (toggle >= 0) lg_selected[toggle] = !lg_selected[toggle];
	if (action) LineGraph_Close();
};

// Label the closest visible retained point; never invent a label floating over
// an off-screen path. Stable slot numbers and colours match both graph panels.
void() LineGraph_WorldLabels =
{
	local float s, i, b, d, best, stride;
	local vector q, at, pos;
	if (!cvar("hud_linegraph_labels")) return;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		if (!LineGraph_Available(s)) continue;
		if (s > 0)
		if (cvar("hud_lines_board") <= 0) continue;
		b = s * LN_CAP;
		best = 99999999;
		at = '0 0 0';
		stride = max(1, ceil((ln_ib[s] - ln_ia[s] + 1) / 256));
		for (i = ln_ia[s]; i <= ln_ib[s]; i = i + stride)
		{
			pos = ln_pos[b + i];
			d = vlen(pos - ln_eye);
			if (d > ln_far || d >= best) continue;
			if (s == 0 && cvar("hud_watch_path_ahead") <= 0)
			if (ln_t[b + i] > rec_wt_time) continue;
			if (!Line_ProjPt(pos)) continue;
			best = d;
			at = ln_qmk;
		}
		if (best == 99999999) continue;
		q = at + [6, 0 - ln_labsz - 6];
		HUD_Text(q, LineGraph_Name(s), max(12, ln_labsz), LineGraph_Colour(s), 0.95);
	}
};

float(float evtype, float scanx, float chary, float devid) LineGraph_InputEvent =
{
	if (!lg_open) return FALSE;
	if (evtype == IE_MOUSEABS)
	{
		lg_mouse = [scanx, chary];
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_ESCAPE)
	{
		if (evtype == IE_KEYDOWN) LineGraph_Close();
		return TRUE;
	}
	return FALSE;
};

float(string cmd) LineGraph_Command =
{
	local float n, s, t;
	local vector sample;
	n = tokenize(cmd);
	if (argv(0) != "linegraph") return FALSE;
	if (n == 1) { if (lg_open) LineGraph_Close(); else LineGraph_Open(); return TRUE; }
	if (argv(1) == "close") { LineGraph_Close(); return TRUE; }
	if (argv(1) == "status")
	{
		print(sprintf("linegraph: open %g cursor %.4f duration %.4f build %g\n", lg_open, lg_cursor_t, lg_tmax, lg_buildslot));
		return TRUE;
	}
	if (argv(1) == "cursor" && n == 4)
	{
		LineGraph_InputEvent(IE_MOUSEABS, stof(argv(2)), stof(argv(3)), 0);
		return TRUE;
	}
	if (argv(1) == "cursorat" && n == 3)
	{
		if (lg_tmax > 0)
			LineGraph_InputEvent(IE_MOUSEABS, lg_plotp_x + lg_plotsize_x * bound(0, stof(argv(2)) / lg_tmax, 1), lg_plotp_y + lg_plotsize_y * 0.5, 0);
		return TRUE;
	}
	if (argv(1) == "toggle" && n == 3)
	{
		s = bound(0, floor(stof(argv(2))), LG_SLOTS - 1);
		lg_selected[s] = !lg_selected[s];
		return TRUE;
	}
	if (argv(1) == "sample" && n == 4)
	{
		s = bound(0, floor(stof(argv(2))), LG_SLOTS - 1);
		t = stof(argv(3));
		sample = LineGraph_At(s, t);
		print(sprintf("linegraph: slot %g t %.4f valid %g speed %.4f selected %g bins %g\n", s, t, sample_z, sample_x, lg_selected[s], lg_buildslot));
		if (sample_z && ln_g[s] > 0)
			print(sprintf("linegraph: energy %.4f relative %+.4f gravity %.4f start %.4f\n", sample_y, sample_y - lg_ref[s], ln_g[s], ln_start[s]));
		return TRUE;
	}
	print("linegraph [close | toggle 0..8 | sample <slot> <seconds>]\n");
	return TRUE;
};
