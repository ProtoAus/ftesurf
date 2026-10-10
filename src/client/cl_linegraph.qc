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

  Patch 610: the envelope is binned over the VIEW, which the comparison panel
  zooms and pans, into a second buffer that swaps in when it is complete; until
  then the old one is drawn at the new view. The HUD graph is a hud_edit element
  (`graph`) with a switch on the board and in the panel. Both draw with
  cl_plot.qc; the panel takes the board's type.
*/
#define LG_SLOTS 9
#define LG_BINS 384
#define LG_STRIDE 12
// A bin: 0/1 speed min/max, 2/3 energy min/max, 4/5 speed first/last, 6/7 energy.
#define LG_HAVE 8
#define LG_BREAK 9
#define LG_FIRSTT 10
#define LG_LASTT 11
#define LG_MINSPAN 0.25         // the narrowest view, seconds
#define LG_POLYMAX 1600         // vertices a slot's curve holds: four a bin, and change

float *lg_bins;                 // two buffers of LG_SLOTS * LG_BINS bins
float lg_front;                 // the one drawn; the other is built into
float lg_open, lg_building, lg_buildslot, lg_buildpoint, lg_tmax, lg_cursor_t;
float lg_v0, lg_v1, lg_fit;     // the view, seconds from each run's start; fit = all of it
float lg_f0, lg_f1, lg_fok;     // what the drawn buffer was binned over, and that it was
float lg_b0, lg_b1;             // ...and the last build's
float lg_drag, lg_dragt;        // panning: the time the button went down on
float lg_seen[LG_SLOTS], lg_seen_n[LG_SLOTS], lg_available[LG_SLOTS];
float lg_selected[LG_SLOTS], lg_ref[LG_SLOTS];
float lg_gen;                   // bumped when the drawn curves change
vector lg_ry[2];                // the value range drawn: speed, energy
float lg_rgen[2], lg_rv0[2], lg_rv1[2];
float lg_hud;                   // the HUD graph drew this frame
/*
  What is drawn every frame: each curve cut down, once, to the fewest vertices
  that stay within a physical pixel of what its bins hold (the filter keeps half
  a pixel from the points it is fed, and a bin's low and high are fed when they
  stand that far off its first and last). [t, value, starts a strip]
  per vertex, per plot (speed, energy) and slot; rebuilt when the drawn buffer,
  the value range or the plot's height changes. Measured, three 46-53 s runs:
  102 vertices in all on the HUD's speed plot and 204 on the panel's, where
  the bins hold about 2300 points (`linegraph status` prints the counts).
*/
float *lg_poly;
float lg_polyn[18];
float lg_pgen[2], lg_plo[2], lg_phi[2], lg_ph[2];
float lg_sw_k, lg_sw_n, lg_sw_tol, lg_sw_have, lg_sw_start;
float lg_sw_at, lg_sw_av, lg_sw_pt, lg_sw_lo, lg_sw_hi;
vector lg_mouse, lg_plotp, lg_plotsize;
float lg_ploty1;                // the bottom of the lower plot

float(float s) LineGraph_Available =
{
	if (s == 0) return (rec_wt_open && ln_on[0] && cvar("hud_watch_path") > 0);
	return (sb_ln_st[s - 1] == SBL_ON && ln_on[s] && (lg_open || cvar("hud_lines_board") > 0));
};

vector(float s) LineGraph_Colour = { return Plot_Series(s); };

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

/*
  Patch 614: the comparison panel's two plots on ImPlot, where the ui_imgui plugin
  and an engine with NativeUIPlot/1 are present (NUI_PlotAvailable). QC keeps the
  panel, the chips, the card and every number in them. The plugin is handed each
  run's rows by pointer (time, speed and breaks straight from the line arrays,
  energy from lgn_e) and draws the curves, the axes and the view the player
  drags; it reports that view and the cursor's time back. Anything missing or
  refused and the QC plots draw instead, the same frame.
*/
#define LGN_BUDGET 8192         // energy rows summed a frame
#define LGN_PERIOD 0.25         // seconds between revisions while a line still loads
#define LGN_MINW   160          // physical pixels the plugin's owner needs
#define LGN_MINH   120
float lgn_handle;               // the native owner, 0 for none
float lgn_failed;               // why it was refused during this open (LineGraph_NativeFail), else 0
float lgn_rev, lgn_dirty, lgn_pub;  // revisions sent; rows differ from the last; its cltime
float *lgn_e;                   // energy less lg_ref, [slot * LN_CAP + row]
float *lgn_scratch;             // eight floats for `linegraph probe`
float lgn_done[LG_SLOTS];       // lgn_e is current below this row
float lgn_first[LG_SLOTS];      // the first row sent: the run's start
float lgn_sgen[LG_SLOTS], lgn_sstep[LG_SLOTS], lgn_sg[LG_SLOTS], lgn_sref[LG_SLOTS], lgn_sstart[LG_SLOTS];
float lgn_map[LG_SLOTS], lgn_count, lgn_marked;  // the published revision: series -> slot
float lgn_serial, lgn_r0, lgn_r1;   // the range asked for; r1 <= r0 is the whole run
float lgn_v0, lgn_v1;           // the view the plugin reports
float lgn_hover, lgn_hovert, lgn_points, lgn_rebuilt, lgn_cut, lgn_drew;
float lgn_lost, lgn_nodraw;     // frames running on which the owner was opened again / its draw refused
float lgn_nodraws, lgn_events;  // draws refused, and positions and notches sent, ever (`linegraph status`)
float lgn_wheel, lgn_sentpos;   // notches not yet sent; the last event sent was a position
float lgn_refuse, lgn_lose;     // `linegraph refuse` and `lose N`, not yet acted on
var float lgn_hot = -1;         // the slot whose chip is under the cursor
vector lgn_pos, lgn_size;       // the plots' rectangle, virtual
float lgn_in, lgn_down, lgn_moved;  // cursor inside; buttons held from inside; a position to send
float lgn_leave;                // draws until the hover is abandoned: the last release is drawn first
float lgn_probe;                // `linegraph probe`: the next hostile case, 0 for none
float lg_frames, lg_frames_t;   // `linegraph frames`: panel frames since it was last asked, and when
float lg_routes, lg_routes_n, lg_routes_q;  // panel frames ever, and those whose plots the plugin / QC drew

void() LineGraph_NativeClose =
{
	if (lgn_handle) NUI_Close(lgn_handle);
	lgn_handle = 0;
	lgn_rev = lgn_count = lgn_marked = 0;   // revisions restart with an owner
	lgn_dirty = TRUE;
	lgn_in = lgn_down = lgn_moved = lgn_leave = lgn_hover = lgn_drew = lgn_probe = 0;
	lgn_wheel = lgn_sentpos = lgn_refuse = lgn_lose = lgn_nodraw = 0;
};

// 1 open, 2 memory, 3 rows, 4 view, 5 draw (refused three frames running), 6 input,
// 7 the owner lost three frames running, 9 `linegraph refuse`. `linegraph status` prints it.
void(float why) LineGraph_NativeFail =
{
	LineGraph_NativeClose();
	lgn_failed = why;
};

// The window lost focus: a held button's release may never come.
void() LineGraph_NativeBlur =
{
	if (!lgn_handle) return;
	if (lgn_in || lgn_down) NUI_Input(lgn_handle, 6, 0, 0);
	lgn_in = lgn_down = lgn_leave = lgn_wheel = lgn_sentpos = FALSE;
};

void() LineGraph_Close =
{
	lg_open = FALSE;
	lg_drag = FALSE;
	lg_fit = TRUE;                  // the HUD graph is always the whole run
	LineGraph_NativeClose();
	lgn_failed = lgn_lost = 0;      // the next open may try the plugin again
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
	lg_fit = TRUE;
	lgn_serial = lgn_serial + 1;    // and the plugin's view with it
	lgn_r0 = lgn_r1 = 0;
	UI_CursorClaim(UIC_LINEGRAPH);
};

void() LineGraph_Reset =
{
	local float s;
	LineGraph_Close();
	Online_MomClear();
	rec_sb_momwant = sb_ln_momfetch = 0;
	lg_fok = FALSE;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		lg_seen[s] = -1;
		lg_seen_n[s] = lg_available[s] = 0;
		lgn_sgen[s] = -1;
	}
};

void() LineGraph_Register =
{
	registercvar("hud_linegraph", "1", CVAR_ARCHIVE);
	registercvar("hud_linegraph_labels", "1", CVAR_ARCHIVE);
	// Patch 610. Under the map info, clear of the key block the old bottom-right
	// panel covered. 1 speed, 2 energy, 3 both.
	registercvar("hud_linegraph_x", "0.99", CVAR_ARCHIVE);
	registercvar("hud_linegraph_y", "0.30", CVAR_ARCHIVE);
	registercvar("hud_linegraph_plots", "1", CVAR_ARCHIVE);
	registercvar("hud_linegraph_size", "0", CVAR_ARCHIVE);
	// Patch 614: the panel's plots through the ui_imgui plugin where it is loaded.
	registercvar("ui_native_graphs", "1", CVAR_ARCHIVE);
	registercommand("linegraph");
	lg_buildslot = LG_SLOTS;
	lg_fit = TRUE;
	LineGraph_Reset();
};

void() LineGraph_Prepare =
{
	local float s, changed, i, b, j, k, t, v, e, gap, budget, back, span;
	changed = FALSE;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		i = LineGraph_Available(s);
		if (lg_available[s] != i || lg_seen[s] != ln_graphgen[s] || lg_seen_n[s] != ln_n[s])
		{
			changed = TRUE;
			if (lg_seen[s] != ln_graphgen[s]) lg_selected[s] = TRUE;
		}
	}
	if (changed)
	{
		if (!lg_bins) lg_bins = memalloc(sizeof(float) * 2 * LG_SLOTS * LG_BINS * LG_STRIDE);
		lg_tmax = 0;
		for (s = 0; s < LG_SLOTS; s = s + 1)
		{
			lg_available[s] = LineGraph_Available(s);
			lg_seen[s] = ln_graphgen[s];
			lg_seen_n[s] = ln_n[s];
			if (lg_available[s])
			{
				i = max(ln_ia[s], Line_Find(s, ln_start[s]));
				lg_ref[s] = (i <= ln_ib[s]) ? LineGraph_Energy(s, i) : 0;
				lg_tmax = max(lg_tmax, ln_t[s * LN_CAP + ln_ib[s]] - ln_start[s]);
			}
		}
		// Neither buffer is of these lines any more.
		lg_fok = FALSE;
		lg_building = FALSE;
		lg_b1 = lg_b0 - 1;
	}
	if (lg_tmax <= 0) { lg_buildslot = LG_SLOTS; lg_fok = FALSE; return; }

	if (!lg_open) lg_fit = TRUE;
	if (lg_fit) { lg_v0 = 0; lg_v1 = lg_tmax; }
	span = min(lg_tmax, max(LG_MINSPAN, lg_v1 - lg_v0));
	lg_v0 = bound(0, lg_v0, lg_tmax - span);
	lg_v1 = lg_v0 + span;
	// A number no mouse makes (`linegraph cursor 1e39 0` while dragging) left NaN
	// here, and a rebuild every frame. Anything that is not a span of the run is all of it.
	if (!(lg_v1 > lg_v0 && lg_v0 >= 0 && lg_v1 <= lg_tmax + LG_MINSPAN))
	{
		lg_fit = TRUE;
		lg_v0 = 0;
		lg_v1 = lg_tmax;
	}

	back = !lg_front;
	if (lg_b0 != lg_v0 || lg_b1 != lg_v1)
	{
		lg_b0 = lg_v0;
		lg_b1 = lg_v1;
		for (s = 0; s < LG_SLOTS; s = s + 1)
		for (j = 0; j < LG_BINS; j = j + 1)
		{
			k = ((back * LG_SLOTS + s) * LG_BINS + j) * LG_STRIDE;
			lg_bins[k + LG_HAVE] = lg_bins[k + LG_BREAK] = 0;
		}
		lg_building = TRUE;
		lg_buildslot = 0;
		lg_buildpoint = -1;
	}
	budget = 2048;
	while (lg_buildslot < LG_SLOTS && budget > 0)
	{
		s = lg_buildslot;
		// From one sample before the view to one past it: a curve runs in from
		// the plot's edge instead of starting inside it.
		if (lg_buildpoint < 0)
			lg_buildpoint = lg_available[s] ? max(ln_ia[s], Line_Find(s, ln_start[s] + lg_b0) - 1) : 0;
		i = lg_buildpoint;
		if (!lg_available[s] || i > ln_ib[s])
		{
			lg_buildslot = lg_buildslot + 1;
			lg_buildpoint = -1;
			continue;
		}
		lg_buildpoint = i + 1;
		budget = budget - 1;
		b = s * LN_CAP;
		t = ln_t[b + i] - ln_start[s];
		if (t < 0) continue;
		gap = ln_brk[b + i];
		if (i > ln_ia[s])
		if (ln_t[b + i] - ln_t[b + i - 1] > max(0.25, ln_tick[s] * ln_step[s] * 2)) gap = TRUE;
		// The sample either side of the view is there for the segment that crosses
		// the plot's edge. Binned on its own (the run ended before the view, or a
		// break or a gap lies between) it set the value range from outside it: a
		// 40 s run's last speed topped the axis of a view of 45 to 55 s.
		if (t < lg_b0)
		{
			if (i >= ln_ib[s]) continue;
			if (ln_brk[b + i + 1]) continue;
			if (ln_t[b + i + 1] - ln_t[b + i] > max(0.25, ln_tick[s] * ln_step[s] * 2)) continue;
		}
		if (t > lg_b1)
		{
			lg_buildslot = lg_buildslot + 1;
			lg_buildpoint = -1;
			if (gap) continue;
		}
		j = bound(0, floor((t - lg_b0) / (lg_b1 - lg_b0) * (LG_BINS - 1)), LG_BINS - 1);
		k = ((back * LG_SLOTS + s) * LG_BINS + j) * LG_STRIDE;
		v = ln_spd[b + i];
		e = LineGraph_Energy(s, i) - lg_ref[s];
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
	}
	if (lg_building)
	if (lg_buildslot >= LG_SLOTS)
	{
		lg_building = FALSE;
		lg_front = back;
		lg_f0 = lg_b0;
		lg_f1 = lg_b1;
		lg_fok = TRUE;
		lg_gen = lg_gen + 1;
	}
};

/*
  [lo, hi, valid]: what the drawn bins hold inside the view, out to round
  numbers. Cached: the HUD graph asks every frame and the answer moves only
  with the view, a swap or a legend tick.
*/
vector(float energy) LineGraph_RangeY =
{
	local float s, j, k, j0, j1, lo, hi, o, step, any, mid;
	if (!lg_fok) return '0 1 0';
	if (lg_rgen[energy] == lg_gen)
	if (lg_rv0[energy] == lg_v0)
	if (lg_rv1[energy] == lg_v1)
		return lg_ry[energy];
	lg_rgen[energy] = lg_gen;
	lg_rv0[energy] = lg_v0;
	lg_rv1[energy] = lg_v1;
	lg_ry[energy] = '0 1 0';
	o = energy * 2;
	j0 = max(0, floor((lg_v0 - lg_f0) / (lg_f1 - lg_f0) * (LG_BINS - 1)));
	j1 = min(LG_BINS - 1, ceil((lg_v1 - lg_f0) / (lg_f1 - lg_f0) * (LG_BINS - 1)));
	lo = 99999999;
	hi = -99999999;
	any = FALSE;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		if (!lg_available[s] || !lg_selected[s]) continue;
		if (energy && ln_g[s] <= 0) continue;
		for (j = j0; j <= j1; j = j + 1)
		{
			k = ((lg_front * LG_SLOTS + s) * LG_BINS + j) * LG_STRIDE;
			if (!lg_bins[k + LG_HAVE] || lg_bins[k + LG_BREAK]) continue;
			lo = min(lo, lg_bins[k + o]);
			hi = max(hi, lg_bins[k + o + 1]);
			any = TRUE;
		}
	}
	if (!any) return '0 1 0';
	// A flat stretch still gets a band wide enough to read.
	mid = energy ? 20 : 50;
	if (hi - lo < mid)
	{
		mid = (hi + lo) * 0.5 - mid * 0.5;
		lo = mid;
		hi = mid + (energy ? 20 : 50);
	}
	step = Plot_Step(hi - lo, 4);
	lo = floor(lo / step) * step;
	hi = ceil(hi / step) * step;
	if (hi <= lo) hi = lo + step;
	if (lo == 0) lo = 0;                // never "-0" on an axis
	if (hi == 0) hi = 0;
	lg_ry[energy] = [lo, hi, 1];
	return lg_ry[energy];
};

// One vertex into the curve being built.
void(float t, float v) LineGraph_Vertex =
{
	if (lg_sw_n >= LG_POLYMAX) return;
	lg_poly[lg_sw_k + lg_sw_n * 3] = t;
	lg_poly[lg_sw_k + lg_sw_n * 3 + 1] = v;
	lg_poly[lg_sw_k + lg_sw_n * 3 + 2] = lg_sw_start;
	lg_sw_start = FALSE;
	lg_sw_n = lg_sw_n + 1;
};

// Close the strip being built: its last point, on the line that fits the rest.
void() LineGraph_SwingEnd =
{
	if (lg_sw_have)
	if (lg_sw_pt > lg_sw_at)
		LineGraph_Vertex(lg_sw_pt, lg_sw_av + (lg_sw_lo + lg_sw_hi) * 0.5 * (lg_sw_pt - lg_sw_at));
	lg_sw_have = FALSE;
};

/*
  The next point of a strip, time ascending. From the last vertex, [lo, hi] is
  the range of slopes that pass within the tolerance of every point since; when
  a point empties it, the point before becomes a vertex on that range's middle
  line. No drawn segment is further than the tolerance from a point it replaced.
*/
void(float t, float v) LineGraph_Swing =
{
	local float dx, lo, hi;
	if (!lg_sw_have)
	{
		lg_sw_have = TRUE;
		lg_sw_start = TRUE;
		LineGraph_Vertex(t, v);
		lg_sw_at = lg_sw_pt = t;
		lg_sw_av = v;
		lg_sw_lo = -99999999;
		lg_sw_hi = 99999999;
		return;
	}
	dx = t - lg_sw_at;
	if (dx <= 0) return;                // a repeat of the vertex itself
	lo = (v - lg_sw_tol - lg_sw_av) / dx;
	hi = (v + lg_sw_tol - lg_sw_av) / dx;
	if (max(lo, lg_sw_lo) > min(hi, lg_sw_hi))
	{
		// The middle line's own end, so the next segment starts where this one stops.
		lg_sw_av = lg_sw_av + (lg_sw_lo + lg_sw_hi) * 0.5 * (lg_sw_pt - lg_sw_at);
		lg_sw_at = lg_sw_pt;
		LineGraph_Vertex(lg_sw_at, lg_sw_av);
		dx = t - lg_sw_at;
		if (dx <= 0) return;
		lg_sw_lo = (v - lg_sw_tol - lg_sw_av) / dx;
		lg_sw_hi = (v + lg_sw_tol - lg_sw_av) / dx;
	}
	else
	{
		lg_sw_lo = max(lo, lg_sw_lo);
		lg_sw_hi = min(hi, lg_sw_hi);
	}
	lg_sw_pt = t;
};

// Every slot's curve for one plot, from the drawn buffer, to within `tol` of
// its values. A break, a gap and a bin holding either end a strip.
void(float energy, float tol) LineGraph_Simplify =
{
	local float s, j, k, o, prev, gapmax, t0, t1, vf, vl, va, vb;
	if (!lg_poly) lg_poly = memalloc(sizeof(float) * 2 * LG_SLOTS * LG_POLYMAX * 3);
	o = energy * 2;
	lg_sw_tol = tol;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		lg_sw_k = (energy * LG_SLOTS + s) * LG_POLYMAX * 3;
		lg_sw_n = 0;
		lg_sw_have = FALSE;
		lg_polyn[energy * LG_SLOTS + s] = 0;
		if (!lg_available[s]) continue;
		if (energy && ln_g[s] <= 0) continue;
		gapmax = max(0.25, ln_tick[s] * ln_step[s] * 2);
		prev = -1;
		for (j = 0; j < LG_BINS; j = j + 1)
		{
			k = ((lg_front * LG_SLOTS + s) * LG_BINS + j) * LG_STRIDE;
			if (!lg_bins[k + LG_HAVE]) continue;
			if (lg_bins[k + LG_BREAK])
			{
				LineGraph_SwingEnd();
				prev = -1;
				continue;
			}
			if (prev >= 0)
			if (lg_bins[k + LG_FIRSTT] - lg_bins[prev + LG_LASTT] > gapmax)
				LineGraph_SwingEnd();
			prev = k;
			// The bin's first and last samples at their own times; a spike those
			// two do not show goes through both extremes, between them.
			t0 = lg_bins[k + LG_FIRSTT];
			t1 = lg_bins[k + LG_LASTT];
			vf = lg_bins[k + 4 + o];
			vl = lg_bins[k + 5 + o];
			va = lg_bins[k + o];
			vb = lg_bins[k + 1 + o];
			LineGraph_Swing(t0, vf);
			if (vb - va > fabs(vf - vl) + tol)
			{
				if (fabs(vf - va) < fabs(vf - vb))
				{
					LineGraph_Swing(t0 + (t1 - t0) * 0.33, va);
					LineGraph_Swing(t0 + (t1 - t0) * 0.67, vb);
				}
				else
				{
					LineGraph_Swing(t0 + (t1 - t0) * 0.33, vb);
					LineGraph_Swing(t0 + (t1 - t0) * 0.67, va);
				}
			}
			LineGraph_Swing(t1, vl);
		}
		LineGraph_SwingEnd();
		lg_polyn[energy * LG_SLOTS + s] = lg_sw_n;
	}
};

/*
  A plot's well, grid and numbers, with no polygon in it: this is drawn before
  any curve. The panel has a gutter left of the plot for the values; the HUD
  graph prints its two ends inside, the upper through `cap` ("%g u/s").
*/
void(vector p, vector size, vector r, float fs, float u, float modal, string cap) LineGraph_Frame =
{
	local float step, v, y, n;
	_sui_round_draw(p, size, modal ? 4 : 2 * u, SUI_THEME_WELL, modal ? 1 : 0.75);
	if (!r_z)
		return;
	if (!modal)
	{
		drawfill([p_x, floor(p_y + size_y * 0.5)], [size_x, 1], SUI_THEME_EDGE, 0.7, 0);
		Plot_Text([p_x + 2 * u, p_y + u], sprintf(cap, r_y), fs, SUI_THEME_MUTED, 1);
		Plot_Text([p_x + 2 * u, p_y + size_y - fs - u], sprintf("%g", r_x), fs, SUI_THEME_MUTED, 1);
		return;
	}
	step = Plot_Step(r_y - r_x, 4);
	n = 0;
	for (v = ceil(r_x / step) * step; v <= r_y + step * 0.01 && n < 16; v = v + step)
	{
		if (v == 0) v = 0;              // ceil(-0.5) * step is -0, and %g prints the sign
		y = floor(p_y + size_y * (1 - (v - r_x) / (r_y - r_x)));
		if (y > p_y + 1)
		if (y < p_y + size_y - 1)
			drawfill([p_x, y], [size_x, 1], SUI_THEME_EDGE, 0.9, 0);
		Scores_TextR([p_x - fs * 0.6, bound(p_y, y - fs * 0.5, p_y + size_y - fs)], fs,
		             sprintf("%g", v), SUI_THEME_MUTED, 1);
		n = n + 1;
	}
};

// One plot's curves at the current view. Polygons only: the caller has the clip
// area set and draws no text until it is reset.
void(vector p, vector size, float energy, vector r, float wpx) LineGraph_Curves =
{
	local float s, i, k, n, sx, sy, base;
	if (!lg_fok || !r_z) return;
	sx = size_x / (lg_v1 - lg_v0);
	sy = size_y / (r_y - r_x);
	base = p_y + size_y;
	if (lg_pgen[energy] != lg_gen || lg_plo[energy] != r_x || lg_phi[energy] != r_y || lg_ph[energy] != size_y)
	{
		lg_pgen[energy] = lg_gen;
		lg_plo[energy] = r_x;
		lg_phi[energy] = r_y;
		lg_ph[energy] = size_y;
		// Half a physical pixel, in the plot's value units.
		LineGraph_Simplify(energy, 0.5 / (max(1, sui_style_pixel_ratio_y) * sy));
	}
	// Highest slot first: the replay and the first board line end up on top.
	for (s = LG_SLOTS - 1; s >= 0; s = s - 1)
	{
		if (!lg_available[s] || !lg_selected[s]) continue;
		n = lg_polyn[energy * LG_SLOTS + s];
		if (!n) continue;
		Plot_Strip(wpx, Plot_Series(s), 0.95);
		k = (energy * LG_SLOTS + s) * LG_POLYMAX * 3;
		for (i = 0; i < n; i = i + 1)
		{
			if (lg_poly[k + 2]) Plot_StripEnd();
			Plot_Q([p_x + (lg_poly[k] - lg_v0) * sx, base - (lg_poly[k + 1] - r_x) * sy]);
			k = k + 3;
		}
		Plot_StripEnd();
	}
};

// A drawn run's energy rests on g = 800 that its recording did not state.
float() LineGraph_Assumed =
{
	local float s;
	for (s = 0; s < LG_SLOTS; s = s + 1)
		if (lg_available[s])
		if (lg_selected[s])
		if (ln_g_assumed[s])
			return TRUE;
	return FALSE;
};

// A dot on a curve: the series colour in a dark ring.
void(vector at, float d, vector col) LineGraph_Dot =
{
	_sui_round_draw(at - [d * 0.5 + 1, d * 0.5 + 1], [d + 2, d + 2], d * 0.5 + 1, SUI_THEME_WELL, 1);
	_sui_round_draw(at - [d * 0.5, d * 0.5], [d, d], d * 0.5, col, 1);
};

// The open replay's playhead: where it is now on its own curve.
void(vector p, vector size, float energy, vector r, float d) LineGraph_Playhead =
{
	local float t, x, v;
	local vector sample;
	if (!lg_available[0] || !lg_selected[0] || !r_z) return;
	t = rec_wt_time - ln_start[0];
	if (t < lg_v0 || t > lg_v1) return;
	x = floor(p_x + (t - lg_v0) / (lg_v1 - lg_v0) * size_x);
	drawfill([x, p_y], [1, size_y], SUI_THEME_TEXT, 0.45, 0);
	sample = LineGraph_At(0, t);
	if (!sample_z) return;
	if (energy && ln_g[0] <= 0) return;
	v = energy ? sample_y - lg_ref[0] : sample_x;
	LineGraph_Dot([x, p_y + size_y * (1 - (v - r_x) / (r_y - r_x))], d, Plot_Series(0));
};

/*
  The HUD graph: the ticked runs' speed (and energy) against time, small enough
  to play beside. hud_linegraph switches it; hud_edit's `graph` row moves it.
*/
void(vector scr, float have) LineGraph_Hud =
{
	local float sz, u, hsz, w, h, ph, plots, s, y, x, lw, rows, e, tw, n;
	local vector p, bp, pp, r;
	local string name;

	Font_Set(ui_font_ui);
	u = cvar("hud_scale");
	if (u <= 0) u = 2;
	u = min(u, scr_x / 640);        // a narrow window gets a smaller graph, as it does a smaller board
	sz  = Font_Px(HUD_Size("hud_linegraph_size", 8 * u));
	u   = sz / 8;
	hsz = Font_Px(6 * u);
	w   = 150 * u;
	ph  = 40 * u;
	plots = cvar("hud_linegraph_plots");
	n = (plots >= 3) ? 2 : 1;

	// The legend wraps; count its rows before the box is drawn.
	rows = 1;
	x = 0;
	lw = w - 12 * u;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		if (!lg_available[s] || !lg_selected[s]) continue;
		tw = 6 * u + stringwidth(LineGraph_Name(s), TRUE, [hsz, hsz]) + 5 * u;
		if (x > 0)
		if (x + tw > lw + 5 * u) { rows = rows + 1; x = 0; }
		x = x + tw;
	}
	if (rows > 3) rows = 3;

	h = (3 + PLOT_BAND) * u + n * ph + (n - 1) * 4 * u + 10 * u + rows * 8 * u + 4 * u;
	bp = [scr_x * cvar("hud_linegraph_x"), scr_y * cvar("hud_linegraph_y"), 0];
	p  = [floor(bp_x - w), floor(bp_y), 0];
	Plot_Panel(p, [w, h], u);
	y = p_y + Plot_Header(p, w, u, sz, "Run graph", (have == 1) ? "1 run" : sprintf("%g runs", have), SUI_THEME_MUTED);
	pp = [p_x + 6 * u, y + 2 * u, 0];
	lg_hud = TRUE;

	// ---- fills and text ----------------------------------------------------
	if (!lg_fok)
	{
		_sui_round_draw(pp, [lw, n * ph + (n - 1) * 4 * u], 2 * u, SUI_THEME_WELL, 0.75);
		Plot_Text(pp + [4 * u, 4 * u], "building...", hsz, SUI_THEME_MUTED, 1);
	}
	else
	{
		e = (plots == 2);               // the first plot is energy only on its own
		r = LineGraph_RangeY(e);
		LineGraph_Frame(pp, [lw, ph], r, hsz, u, FALSE, e ? "E %g" : "%g u/s");
		if (n == 2)
			LineGraph_Frame(pp + [0, ph + 4 * u], [lw, ph], LineGraph_RangeY(TRUE), hsz, u, FALSE, "E %g");
		if (plots >= 2)
		if (LineGraph_Assumed())
			Plot_TextR([pp_x + lw - 2 * u, pp_y + (n - 1) * (ph + 4 * u) + u], "g 800 assumed", hsz, SUI_THEME_WARN, 1);
	}
	y = pp_y + n * ph + (n - 1) * 4 * u + 2 * u;
	Plot_Text ([pp_x, y], Plot_Clock(lg_v0, 1), hsz, SUI_THEME_MUTED, 1);
	Plot_TextR([pp_x + lw, y], Plot_Clock(lg_v1, 1), hsz, SUI_THEME_MUTED, 1);
	y = y + 8 * u;
	x = 0;
	rows = 1;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		if (!lg_available[s] || !lg_selected[s]) continue;
		name = LineGraph_Name(s);
		tw = 6 * u + stringwidth(name, TRUE, [hsz, hsz]) + 5 * u;
		if (x > 0)
		if (x + tw > lw + 5 * u) { rows = rows + 1; x = 0; y = y + 8 * u; }
		if (rows > 3) break;
		_sui_round_draw(_sui_pixel_align([pp_x + x, y + (hsz - 4 * u) * 0.5 + u]), [4 * u, 4 * u], 2 * u, Plot_Series(s), 1);
		Plot_Text([pp_x + x + 6 * u, y], name, hsz, SUI_THEME_DIM, 1);
		x = x + tw;
	}

	// ---- curves, then fills ------------------------------------------------
	if (lg_fok)
	{
		e = (plots == 2);
		r = LineGraph_RangeY(e);
		drawsetcliparea(pp_x, pp_y, lw, ph);
		LineGraph_Curves(pp, [lw, ph], e, r, 1.5);
		drawresetcliparea();
		LineGraph_Playhead(pp, [lw, ph], e, r, 4 * u);
		if (n == 2)
		{
			r = LineGraph_RangeY(TRUE);
			drawsetcliparea(pp_x, pp_y + ph + 4 * u, lw, ph);
			LineGraph_Curves(pp + [0, ph + 4 * u], [lw, ph], TRUE, r, 1.5);
			drawresetcliparea();
			LineGraph_Playhead(pp + [0, ph + 4 * u], [lw, ph], TRUE, r, 4 * u);
		}
	}
	HUD_Rect("graph", p, [w, h], bp);
	Font_Reset();
};

// A legend chip's width at height `h`: a dot, the name, the pill's ends.
float(float s, float h) LineGraph_ChipW =
{
	return ceil(h * 0.5 + ceil(h * 0.36) + h * 0.3
	            + stringwidth(LineGraph_Name(s), TRUE, [sb_szui, sb_szui]) + h * 0.55);
};

// A run's chip in the panel's legend: its colour, number and name; lit while
// its curves are drawn.
void(float s, vector pos, float h) LineGraph_Chip =
{
	local float w, d, hot;
	local string id, name;
	id = sprintf("lg_slot%g", s);
	name = LineGraph_Name(s);
	d = ceil(h * 0.36);
	w = LineGraph_ChipW(s, h);
	sui_action_element(pos, [w, h], id, sui_noop);
	hot = sui_is_hovered(id);
	if (hot) lgn_hot = s;
	if (hot)
		sui_style_box(pos, [w, h], h * 0.5, lg_selected[s] ? SBC_PANEL : SUI_THEME_WELL, SUI_THEME_EDGE_HI, 1);
	else
		sui_roundbox(pos, [w, h], h * 0.5, lg_selected[s] ? SBC_PANEL : SUI_THEME_WELL, 1);
	sui_roundbox([floor(pos_x + h * 0.5), pos_y + floor((h - d) * 0.5)], [d, d], d * 0.5,
	             lg_selected[s] ? Plot_Series(s) : SUI_THEME_MUTED, 1);
	Scores_Text([floor(pos_x + h * 0.5 + d + h * 0.3), pos_y + floor((h - sb_szui) * 0.5)], sb_szui, name,
	            lg_selected[s] ? SUI_THEME_TEXT : SUI_THEME_MUTED, 1);
	if (sui_is_released(id))
	{
		lg_selected[s] = !lg_selected[s];
		lg_gen = lg_gen + 1;
	}
};

// What every drawn run reads at the cursor's time, beside the cursor.
void(float t, vector scr, vector plot, vector size) LineGraph_Card =
{
	local float s, n, best, fs, rh, w, h, x, y, xs, xg, xe, note;
	local vector sample, p;
	local string text;

	fs = rec_sb_szhead;
	rh = fs + 6;
	n = 0;
	best = -1;
	note = FALSE;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		if (!lg_available[s] || !lg_selected[s]) continue;
		sample = LineGraph_At(s, t);
		if (!sample_z) continue;
		n = n + 1;
		best = max(best, sample_x);
		if (ln_g_assumed[s]) note = TRUE;
	}
	// Right edges of the three number columns: speed, how far behind the fastest
	// run it is at this instant, energy.
	w  = fs * 23.5;
	xs = fs * 14.6;
	xg = fs * 18.2;
	xe = w - fs * 0.8;
	h = fs + 12 + max(1, n) * rh + (note ? rh : 0) + 6;
	p = [lg_mouse_x + 16, lg_mouse_y - h * 0.5, 0];
	if (p_x + w > plot_x + size_x) p_x = lg_mouse_x - 16 - w;
	p_y = bound(4, p_y, scr_y - h - 4);
	sui_roundbox(p + '-2 -1 0', [w + 4, h + 4], 8, '0 0 0', 0.22);
	sui_style_box(p, [w, h], 6, SUI_THEME_CHIP, SUI_THEME_EDGE_HI, 1);
	Scores_Text([p_x + fs * 0.8, p_y + 6], fs, Time_MsString((int)floor(t * 1000 + 0.5)), SUI_THEME_TEXT, 1);
	Scores_TextR([p_x + xs, p_y + 6], fs, "u/s", SUI_THEME_MUTED, 1);
	Scores_TextR([p_x + xg, p_y + 6], fs, "behind", SUI_THEME_MUTED, 1);
	Scores_TextR([p_x + xe, p_y + 6], fs, "energy", SUI_THEME_MUTED, 1);
	y = p_y + fs + 14;
	if (!n)
		Scores_Text([p_x + fs * 0.8, y], fs, "no sample here", SUI_THEME_MUTED, 1);
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		if (!lg_available[s] || !lg_selected[s]) continue;
		sample = LineGraph_At(s, t);
		if (!sample_z) continue;
		x = p_x + fs * 0.8;
		sui_roundbox([x, y + (fs - 7) * 0.5 + 1], [7, 7], 3.5, Plot_Series(s), 1);
		Scores_Text([x + fs * 0.8, y], fs, substring(LineGraph_Name(s), 0, 18), SUI_THEME_TEXT, 1);
		Scores_TextR([p_x + xs, y], fs, sprintf("%.0f", sample_x), SUI_THEME_TEXT, 1);
		if (best - sample_x >= 0.5)
			Scores_TextR([p_x + xg, y], fs, sprintf("%.0f", best - sample_x), SUI_THEME_BAD, 1);
		text = "-";
		if (ln_g[s] > 0)
			text = sprintf("%+.0f%s", sample_y - lg_ref[s], ln_g_assumed[s] ? "*" : "");
		Scores_TextR([p_x + xe, y], fs, text, SUI_THEME_DIM, 1);
		y = y + rh;
	}
	if (note)
		Scores_Text([p_x + fs * 0.8, y], fs, "* gravity 800 assumed: not in the recording", SUI_THEME_WARN, 1);
};

// ---- Patch 614: the panel's plots on ImPlot (the block over LineGraph_NativeClose) ----

// Virtual to physical pixels; z is 0 when the engine could not say.
vector(vector v) LineGraph_NativePx =
{
	local vector physical, virtualsize;
	physical = getproperty(VF_SCREENPSIZE);
	virtualsize = getproperty(VF_SCREENVSIZE);
	if (virtualsize_x <= 0 || virtualsize_y <= 0) return '0 0 0';
	return [v_x * physical_x / virtualsize_x, v_y * physical_y / virtualsize_y, 1];
};

// Brings lgn_e up to date, LGN_BUDGET rows a frame. TRUE once every drawn run's
// rows are summed.
float() LineGraph_NativeRows =
{
	local float s, i, b, first, budget, complete, stale;
	if (!lgn_e)
	{
		lgn_e = memalloc(sizeof(float) * LG_SLOTS * LN_CAP);
		if (!lgn_e) return FALSE;
		for (s = 0; s < LG_SLOTS; s = s + 1) lgn_sgen[s] = -1;
	}
	budget = LGN_BUDGET;
	complete = TRUE;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		if (!lg_available[s])
		{
			if (lgn_sgen[s] != -1) lgn_dirty = TRUE;
			lgn_sgen[s] = -1;
			continue;
		}
		first = max(ln_ia[s], Line_Find(s, ln_start[s]));
		// What the rows were summed from. The halving past LN_CAP rewrites rows in
		// place under the same generation: its doubled step is what says so.
		stale = (lgn_sgen[s] != ln_graphgen[s] || lgn_sstep[s] != ln_step[s] || lgn_first[s] != first);
		if (lgn_sg[s] != ln_g[s] || lgn_sref[s] != lg_ref[s] || lgn_sstart[s] != ln_start[s]) stale = TRUE;
		if (lgn_done[s] > ln_ib[s] + 1) stale = TRUE;
		if (stale)
		{
			lgn_sgen[s] = ln_graphgen[s]; lgn_sstep[s] = ln_step[s]; lgn_first[s] = first;
			lgn_sg[s] = ln_g[s]; lgn_sref[s] = lg_ref[s]; lgn_sstart[s] = ln_start[s];
			lgn_done[s] = first;
			lgn_dirty = TRUE;
		}
		b = s * LN_CAP;
		for (i = lgn_done[s]; i <= ln_ib[s] && budget > 0; i = i + 1)
		{
			lgn_e[b + i] = LineGraph_Energy(s, i) - lg_ref[s];
			budget = budget - 1;
		}
		if (i != lgn_done[s]) lgn_dirty = TRUE;
		lgn_done[s] = i;
		if (i <= ln_ib[s]) complete = FALSE;
	}
	return complete;
};

// One revision: every drawn run that has a row, in slot order. The engine reads
// the rows where they lie, checks them and copies them; a refusal is FALSE.
float() LineGraph_NativePublish =
{
	local float s, k, n, b, rows, flags;
	n = 0;
	for (s = 0; s < LG_SLOTS; s = s + 1)
		if (lg_available[s])
		if (ln_ib[s] >= lgn_first[s]) n = n + 1;
	lgn_rev = lgn_rev + 1;
	if (!ui_native_plot_begin(lgn_handle, lgn_rev, n)) return FALSE;
	k = 0;
	lgn_marked = FALSE;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		if (!lg_available[s]) continue;
		rows = ln_ib[s] - lgn_first[s] + 1;
		if (rows < 1) continue;
		b = s * LN_CAP + lgn_first[s];
		flags = (ln_g[s] > 0) ? 1 : 0;      // energy needs a gravity (LineGraph_Energy)
		if (s == 0) { flags = flags + 2; lgn_marked = TRUE; }   // the replay's clock rides it
		if (!ui_native_plot_series(lgn_handle, k, [flags, max(0.25, ln_tick[s] * ln_step[s] * 2), 0], Plot_Series(s)))
			return FALSE;
		if (ln_g[s] > 0)
		{
			if (!ui_native_plot_rows(lgn_handle, k, &ln_t[b], &ln_spd[b], &lgn_e[b], &ln_brk[b], rows, ln_start[s]))
				return FALSE;
		}
		else if (!ui_native_plot_rows(lgn_handle, k, &ln_t[b], &ln_spd[b], __NULL__, &ln_brk[b], rows, ln_start[s]))
			return FALSE;
		lgn_map[k] = s;
		k = k + 1;
	}
	if (!ui_native_plot_commit(lgn_handle)) return FALSE;
	lgn_count = k;
	lgn_dirty = FALSE;
	lgn_pub = cltime;
	return TRUE;
};

/*
  `linegraph probe`: one hostile transaction a frame through the real builtins,
  each printing what every call returned (-1: not called). tools/p614plots.py
  holds the table they must match; all are refusals, and the plots must still
  be drawn, from a newer revision, after the last. One a frame because the
  engine budgets transactions per frame: a refusal for THAT is not the one
  under test.
*/
void() LineGraph_NativeProbe =
{
	local float n, s, rev, bg, sr, rw, cm, vw, v;
	local float *x;
	local float *a;
	local vector spec, rgb;
	local string name;
	if (!lgn_count) { print("linegraph: probe needs a drawn run\n"); lgn_probe = 0; return; }
	if (!lgn_scratch) lgn_scratch = memalloc(sizeof(float) * 8);
	if (!lgn_scratch) { lgn_probe = 0; return; }
	n = lgn_probe;
	lgn_probe = lgn_probe + 1;
	rev = lgn_rev + 1;
	s = lgn_map[0];
	x = &ln_t[s * LN_CAP + lgn_first[s]];
	a = &ln_spd[s * LN_CAP + lgn_first[s]];
	spec = [0, 0.25, 0];
	rgb = '0.5 0.5 0.5';
	v = 10 + lgn_rev;                       // +Inf, made at run time: six squarings
	v = v * v; v = v * v; v = v * v; v = v * v; v = v * v; v = v * v;
	lgn_scratch[0] = 1; lgn_scratch[1] = 0; // time running backwards
	lgn_scratch[2] = 0; lgn_scratch[3] = 1;
	lgn_scratch[4] = 5; lgn_scratch[5] = v;
	lgn_scratch[6] = 2000000000; lgn_scratch[7] = 0;    // past PLUGUI_PLOT_MAX_VALUE, and finite
	bg = sr = rw = cm = vw = -1;
	name = "";
	if (n == 1) { name = "stale-revision"; bg = ui_native_plot_begin(lgn_handle, lgn_rev, 1); }
	else if (n == 2) { name = "seventeen-series"; bg = ui_native_plot_begin(lgn_handle, rev, 17); }
	else if (n == 3) { name = "fractional-count"; bg = ui_native_plot_begin(lgn_handle, rev, 1.5); }
	else if (n == 4)
	{
		name = "unknown-flag";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, [4, 0.25, 0], rgb);
		cm = ui_native_plot_commit(lgn_handle);
	}
	else if (n == 5)
	{
		name = "zero-gap";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, [0, 0, 0], rgb);
	}
	else if (n == 6)
	{
		name = "colour-out-of-range";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, spec, '2 0 0');
	}
	else if (n == 7)
	{
		name = "no-rows";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, spec, rgb);
		rw = ui_native_plot_rows(lgn_handle, 0, x, a, __NULL__, __NULL__, 0, 0);
		cm = ui_native_plot_commit(lgn_handle);
	}
	else if (n == 8)
	{
		name = "too-many-rows";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, spec, rgb);
		rw = ui_native_plot_rows(lgn_handle, 0, x, a, __NULL__, __NULL__, 65537, 0);
	}
	else if (n == 9)
	{
		name = "null-time";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, spec, rgb);
		rw = ui_native_plot_rows(lgn_handle, 0, __NULL__, a, __NULL__, __NULL__, 2, 0);
	}
	else if (n == 10)
	{
		// Two rows that would start 1.6 GB past the line arrays.
		name = "beyond-vm-memory";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, spec, rgb);
		rw = ui_native_plot_rows(lgn_handle, 0, &ln_t[400000000], a, __NULL__, __NULL__, 2, 0);
	}
	else if (n == 11)
	{
		name = "second-value-not-declared";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, spec, rgb);
		rw = ui_native_plot_rows(lgn_handle, 0, x, a, a, __NULL__, 1, 0);
	}
	else if (n == 12)
	{
		name = "second-value-missing";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, [1, 0.25, 0], rgb);
		rw = ui_native_plot_rows(lgn_handle, 0, x, a, __NULL__, __NULL__, 1, 0);
	}
	else if (n == 13)
	{
		name = "time-backwards";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, spec, rgb);
		rw = ui_native_plot_rows(lgn_handle, 0, &lgn_scratch[0], &lgn_scratch[2], __NULL__, __NULL__, 2, 0);
	}
	else if (n == 14)
	{
		name = "infinite-value";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, spec, rgb);
		rw = ui_native_plot_rows(lgn_handle, 0, &lgn_scratch[2], &lgn_scratch[4], __NULL__, __NULL__, 2, 0);
	}
	else if (n == 15)
	{
		name = "series-missing";
		bg = ui_native_plot_begin(lgn_handle, rev, 2);
		sr = ui_native_plot_series(lgn_handle, 0, spec, rgb);
		rw = ui_native_plot_rows(lgn_handle, 0, &lgn_scratch[2], &lgn_scratch[2], __NULL__, __NULL__, 2, 0);
		cm = ui_native_plot_commit(lgn_handle);
	}
	else if (n == 16)
	{
		name = "rows-twice";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, spec, rgb);
		ui_native_plot_rows(lgn_handle, 0, &lgn_scratch[2], &lgn_scratch[2], __NULL__, __NULL__, 2, 0);
		rw = ui_native_plot_rows(lgn_handle, 0, &lgn_scratch[2], &lgn_scratch[2], __NULL__, __NULL__, 2, 0);
		cm = ui_native_plot_commit(lgn_handle);
	}
	else if (n == 17) { name = "hidden-mask-too-wide"; vw = ui_native_plot_view(lgn_handle, '0 0 13', '65536 0 0', '0 0 0'); }
	else if (n == 18) { name = "caption-size-zero"; vw = ui_native_plot_view(lgn_handle, '0 0 0', '0 0 0', '0 0 0'); }
	else if (n == 19) { name = "infinite-mark"; vw = ui_native_plot_view(lgn_handle, [v, 1, 13], '0 0 0', '0 0 0'); }
	else if (n == 20)
	{
		name = "value-past-a-billion";
		bg = ui_native_plot_begin(lgn_handle, rev, 1);
		sr = ui_native_plot_series(lgn_handle, 0, spec, rgb);
		rw = ui_native_plot_rows(lgn_handle, 0, &lgn_scratch[2], &lgn_scratch[6], __NULL__, __NULL__, 2, 0);
	}
	else
	{
		// The owner must have outlived all of it: ask for a fresh revision.
		print(sprintf("linegraph: probe done handle %g\n", lgn_handle > 0));
		lgn_probe = 0;
		lgn_dirty = TRUE;
		lgn_pub = 0;
		return;
	}
	print(sprintf("linegraph: probe %g %s begin %g series %g rows %g commit %g view %g\n", n, name, bg, sr, rw, cm, vw));
};

/*
  The plots' rectangle drawn by the plugin. FALSE: nothing was drawn there and
  the caller draws the QC plots. `fs` is the caption size, which the plugin
  matches its own type to.
*/
float(vector p, vector size, float fs) LineGraph_NativeDraw =
{
	local float k, bit, hidden, loud, marked, i, complete;
	local vector px, a;
	lgn_drew = lgn_hover = FALSE;
	lgn_pos = p;                    // kept whether or not it draws: `linegraph status` prints them
	lgn_size = size;
	if (lgn_failed) return FALSE;
	if (!cvar("ui_native_graphs")) { LineGraph_NativeClose(); return FALSE; }
	if (!NUI_PlotAvailable()) { LineGraph_NativeClose(); return FALSE; }
	px = LineGraph_NativePx(size);
	if (px_x < LGN_MINW || px_y < LGN_MINH) { LineGraph_NativeClose(); return FALSE; }
	complete = LineGraph_NativeRows();
	if (!lgn_e) { LineGraph_NativeFail(2); return FALSE; }
	if (!lgn_handle)
	{
		if (!complete) return FALSE;        // a few frames of the QC plots while the rows are summed
		Scores_NativeClose();               // one owner a VM: the board's table is not up behind this
	}
	if (lgn_lose > 0)
	if (lgn_handle)
	{
		lgn_lose = lgn_lose - 1;
		NUI_Close(lgn_handle);          // `linegraph lose`: behind this panel's back
	}
	// The live owner's handle again, at no cost; or a new owner where a renderer
	// restart or a plugin reload took the old one, and then everything is sent anew.
	i = NUI_Open(206);
	if (!i) { LineGraph_NativeFail(1); return FALSE; }
	if (i != lgn_handle)
	{
		// Lost once (a renderer restart) it is replaced. Lost again on each of three
		// frames it is dying of something this panel sends it, and is given up: a
		// new context, font atlas and revision every frame is no way to carry on.
		if (lgn_handle) lgn_lost = lgn_lost + 1;
		lgn_handle = i;
		if (lgn_lost >= 3) { LineGraph_NativeFail(7); return FALSE; }
		lgn_rev = lgn_count = lgn_marked = 0;
		lgn_in = lgn_down = lgn_leave = lgn_probe = lgn_wheel = lgn_sentpos = 0;
		lgn_dirty = TRUE;
	}
	else lgn_lost = 0;
	if (lgn_probe)
	if (lgn_rev)
		LineGraph_NativeProbe();
	if (lgn_dirty)
	if (complete)
	if (!lgn_rev || cltime < lgn_pub || cltime >= lgn_pub + LGN_PERIOD)
		if (!LineGraph_NativePublish()) { LineGraph_NativeFail(3); return FALSE; }
	if (!lgn_rev) return FALSE;

	hidden = loud = 0;
	bit = 1;
	for (k = 0; k < lgn_count; k = k + 1)
	{
		if (!lg_selected[lgn_map[k]]) hidden = hidden + bit;
		else if (lgn_hot == lgn_map[k]) loud = loud + bit;
		bit = bit * 2;
	}
	marked = (lgn_marked && lg_available[0] && lg_selected[0]);
	px = LineGraph_NativePx([fs, fs]);
	if (px_y < 1) px_y = 13;
	if (!ui_native_plot_view(lgn_handle, [marked ? rec_wt_time - ln_start[0] : 0, marked, px_y],
	                         [hidden, loud, 0], [lgn_serial, lgn_r0, lgn_r1]))
		{ LineGraph_NativeFail(4); return FALSE; }
	// One queued event a frame: the latest position, or one of the wheel's notches
	// (ImPlot zooms a step for a frame's wheel, whatever its size). A fast mouse
	// must not spend the engine's per-frame event budget, and ImGui takes a wheel
	// after a move (or a move after a wheel) a frame later, so a position before
	// every notch outran it and filled the plugin's queue. With both waiting they
	// take turns.
	if (lgn_in || lgn_down)
	{
		if (lgn_moved && (!lgn_wheel || !lgn_sentpos))
		{
			lgn_moved = FALSE;
			lgn_sentpos = TRUE;
			lgn_events = lgn_events + 1;
			px = LineGraph_NativePx(lg_mouse);
			if (!NUI_Input(lgn_handle, 1, px_x, px_y)) { LineGraph_NativeFail(6); return FALSE; }
		}
		else if (lgn_wheel)
		{
			i = (lgn_wheel > 0) ? 1 : -1;
			lgn_wheel = lgn_wheel - i;
			lgn_sentpos = FALSE;
			lgn_events = lgn_events + 1;
			if (!NUI_Input(lgn_handle, 3, 0, i)) { LineGraph_NativeFail(6); return FALSE; }
		}
	}
	else lgn_moved = lgn_wheel = FALSE;
	if (lgn_refuse) { lgn_refuse = FALSE; LineGraph_NativeFail(9); return FALSE; }
	drawsetcliparea(p_x, p_y, size_x, size_y);
	i = NUI_Draw(lgn_handle);
	drawresetcliparea();
	if (!i)
	{
		// A VM draws one native owner a frame, and the board's table has drawn this
		// one when its `run graphs` chip opens the panel (Scores_Finish, mid-frame).
		// Refused once is that, and QC draws this frame's plots; refused on three
		// frames running is the plugin's own failure.
		lgn_nodraw = lgn_nodraw + 1;
		lgn_nodraws = lgn_nodraws + 1;
		if (lgn_nodraw >= 3) LineGraph_NativeFail(5);
		return FALSE;
	}
	lgn_nodraw = 0;
	lgn_drew = TRUE;
	// What it shows and where the cursor reads: 1 and 2 the view, 3 the cursor's
	// time (absent off the plots), 4 the points it drew, 5 how many of its two
	// plots it had to cut afresh for this frame (0 while the view is only read).
	for (i = 0; i < 16; i = i + 1)
	{
		a = NUI_Poll(lgn_handle);
		if (a == '0 0 0') break;
		if (a_x == 1) lgn_v0 = a_z;
		else if (a_x == 2) lgn_v1 = a_z;
		else if (a_x == 3) { lgn_hover = TRUE; lgn_hovert = a_z; }
		else if (a_x == 4) lgn_points = a_z;
		else if (a_x == 5) { lgn_rebuilt = a_z; lgn_cut = lgn_cut + a_z; }
	}
	// The cursor left with nothing held. The plugin has now drawn whatever was let
	// go on the way out (a box, a pan); only then is its mouse taken away.
	if (lgn_in || lgn_down) lgn_leave = 0;
	else if (lgn_leave > 0)
	{
		lgn_leave = lgn_leave - 1;
		if (!lgn_leave)
			if (!NUI_Input(lgn_handle, 6, 0, 0)) { LineGraph_NativeFail(6); return TRUE; }
	}
	return TRUE;
};

// The cursor moved (lg_mouse). Leaving with no button held abandons the hover,
// two draws on (LineGraph_NativeDraw).
void() LineGraph_NativeMoved =
{
	local float inside;
	if (!lgn_handle || !lgn_drew) return;
	inside = (lg_mouse_x >= lgn_pos_x && lg_mouse_y >= lgn_pos_y
	       && lg_mouse_x < lgn_pos_x + lgn_size_x && lg_mouse_y < lgn_pos_y + lgn_size_y);
	if (lgn_in)
	if (!inside)
	if (!lgn_down)
		lgn_leave = 2;
	lgn_in = inside;
	lgn_moved = TRUE;
};

// A mouse button or the wheel while the native plots are up. TRUE: it was theirs.
// A press belongs to them when it lands inside; its release follows it out.
float(float evtype, float scanx) LineGraph_NativeKey =
{
	local float button, bit, down, ok;
	local vector px;
	if (!lgn_handle || !lgn_drew) return FALSE;
	down = (evtype == IE_KEYDOWN);
	button = bit = 0;
	if (scanx == K_MOUSE1) bit = 1;
	else if (scanx == K_MOUSE2) { button = 1; bit = 2; }
	else if (scanx != K_MWHEELUP && scanx != K_MWHEELDOWN) return FALSE;
	if (!bit)
	{
		// Notches are counted here and sent from the draw, one a frame.
		if (!lgn_in) return FALSE;
		if (down) lgn_wheel = bound(-10, lgn_wheel + ((scanx == K_MWHEELUP) ? 1 : -1), 10);
		return TRUE;
	}
	if (down)
	{
		if (!lgn_in) return FALSE;
		lgn_down = lgn_down | bit;
	}
	else
	{
		if (!(lgn_down & bit)) return FALSE;
		lgn_down = lgn_down - bit;
	}
	// A button is sent at once, after where it happened.
	px = LineGraph_NativePx(lg_mouse);
	lgn_moved = FALSE;
	lgn_sentpos = TRUE;
	if (!NUI_Input(lgn_handle, 1, px_x, px_y)) { LineGraph_NativeFail(6); return TRUE; }
	ok = NUI_Input(lgn_handle, 2, button, down);
	if (!ok) { LineGraph_NativeFail(6); return TRUE; }
	// Let go outside with nothing else held: the hover goes with it, once drawn.
	if (!lgn_in)
	if (!lgn_down)
		lgn_leave = 2;
	return TRUE;
};

// The whole run again, in whichever plots are up.
void() LineGraph_Fit =
{
	lg_fit = TRUE;
	lgn_serial = lgn_serial + 1;
	lgn_r0 = lgn_r1 = 0;
};

// The view is narrower than the run.
float() LineGraph_Zoomed =
{
	if (lgn_drew) return (lgn_v0 > 0.0005 || lgn_v1 < lg_tmax - 0.0005);
	return !lg_fit;
};

/*
  The panel's plot area on the plugin: one caption row, its rectangle, the
  footer and the card. FALSE: nothing was drawn and LineGraph_Panel carries on
  with the QC plots. `y` is the caption's row, `y1` the bottom of the area.
*/
float(vector scr, vector p, float w, float pad, float y, float y1) LineGraph_PanelNative =
{
	local vector nat, size;
	local float x, fs, k;
	local string text;
	fs = rec_sb_szhead;
	nat = [p_x + pad, y + fs + 6, 0];
	size = [w - pad * 2, y1 - nat_y, 0];
	if (!LineGraph_NativeDraw(nat, size, fs)) return FALSE;

	x = nat_x;
	Scores_Text([x, y], fs, "SPEED", SUI_THEME_MUTED, 1);
	x = x + fs * 4.2;
	Scores_Text([x, y], fs, "horizontal, u/s", SUI_THEME_DIM, 1);
	x = x + stringwidth("horizontal, u/s", TRUE, [fs, fs]) + pad * 2;
	Scores_Text([x, y], fs, "ENERGY", SUI_THEME_MUTED, 1);
	x = x + fs * 4.9;
	// As over the QC plots: where both do not fit, the warning is the one that stays.
	text = "height + v*v/2g, in units above the run's first sample";
	k = stringwidth("g 800 assumed where a recording does not say", TRUE, [fs, fs]);
	if (!LineGraph_Assumed())
		Scores_Text([x, y], fs, text, SUI_THEME_DIM, 1);
	else if (x + stringwidth(text, TRUE, [fs, fs]) + pad + k <= nat_x + size_x)
	{
		Scores_Text([x, y], fs, text, SUI_THEME_DIM, 1);
		Scores_TextR([nat_x + size_x, y], fs, "g 800 assumed where a recording does not say", SUI_THEME_WARN, 1);
	}
	else
		Scores_Text([x, y], fs, "g 800 assumed where a recording does not say", SUI_THEME_WARN, 1);

	y = y1 + pad;
	sui_fill([p_x + pad, y - floor(pad * 0.5)], [w - pad * 2, 1], SUI_THEME_EDGE, 1, 0);
	x = Scores_Hint(p_x + w - pad, y, "esc", "close");
	x = Scores_Hint(x, y, "rmb", "whole run, or drag a box");
	x = Scores_Hint(x, y, "drag", "pan");
	Scores_Hint(x, y, "wheel", "zoom");
	if (lg_tmax > 0)
		Scores_Text([p_x + pad, y], fs,
		            LineGraph_Zoomed() ? sprintf("%s to %s of %s", Plot_Clock(lgn_v0, 0.1), Plot_Clock(lgn_v1, 0.1), Plot_Clock(lg_tmax, 0.1))
		                               : sprintf("the whole run, %s", Plot_Clock(lg_tmax, 0.1)),
		            SUI_THEME_DIM, 1);
	if (lgn_hover)
	{
		lg_cursor_t = lgn_hovert;
		LineGraph_Card(lgn_hovert, scr, nat, size);
	}
	return TRUE;
};

/*
  The comparison panel: the board's chrome and type, the runs as chips, two
  plots on one time axis. Wheel zooms about the cursor, a drag pans, the right
  button (or the fit chip) shows the whole run again.
*/
void(vector scr, float have) LineGraph_Panel =
{
	local float scale, bs, pad, w, h, ph, gw, pw, x, y, y0, s, t, step, n, chiph, chipw, tabh, hover, e, xr, k, closing;
	local vector p, plot, r0, r1;
	local string text;

	scale = cvar("hud_scale");
	if (scale <= 0) scale = 2;
	if (scale > 16) scale = 16;
	bs = min(scale, scr_y / 432);
	if (bs < 1) bs = 1;
	Scores_Type(max(8 * bs, 6 * scale));
	pad   = rec_sb_szrow;
	tabh  = ceil(rec_sb_szrow * 1.9);
	chiph = ceil(rec_sb_szhead * 2);
	chipw = ceil(rec_sb_cw * 8.5);
	gw = ceil(rec_sb_cw * 6.5);
	// The plots are for reading curves: at a small hud_scale the type shrinks and
	// the panel does not (the old one was 1050 wide whatever the scale).
	w  = min(scr_x - pad * 2, max(pad * 68, floor(scr_x * 0.56)));
	pw = w - pad * 2 - gw;

	sui_begin(scr_x, scr_y);
	sui_fill('0 0 0', [scr_x, scr_y], '0 0 0', 0.35, 0);

	// The legend wraps: its height first, from the same flow the chips take.
	Font_Set(ui_font_ui);
	n = 1;
	x = 0;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		if (!lg_available[s]) continue;
		k = LineGraph_ChipW(s, tabh);
		if (x > 0)
		if (x + k > w - pad * 2) { n = n + 1; x = 0; }
		x = x + k + 6;
	}
	h = pad + rec_sb_sztitle + ceil(pad * 0.75) + n * (tabh + 6) + pad * 0.5
	  + (rec_sb_szhead + 6) * 2 + pad + rec_sb_szhead + 8
	  + pad + rec_sb_szhead + pad;
	ph = bound(rec_sb_szrow * 4, floor((scr_y * 0.90 - h) * 0.5), max(rec_sb_szrow * 12, floor(scr_y * 0.175)));
	h = h + ph * 2;
	p = [floor((scr_x - w) * 0.5), floor((scr_y - h) * 0.5), 0];
	sui_style_panel(p, [w, h], ceil(pad * 0.75), 0.98);

	// ---- the header ----------------------------------------------------------
	Scores_Text([p_x + pad, p_y + pad], rec_sb_sztitle, "Run graphs", SUI_THEME_TEXT, 1);
	x = p_x + pad + stringwidth("Run graphs", TRUE, [rec_sb_sztitle, rec_sb_sztitle]) + pad;
	Scores_Text([x, p_y + pad + rec_sb_sztitle - rec_sb_szhead - 3], rec_sb_szhead,
	            "time from each run or stage start", SUI_THEME_DIM, 1);
	y = p_y + pad + floor((rec_sb_sztitle - chiph) * 0.5);
	xr = p_x + w - pad - chipw;
	closing = Scores_Chip("lg_close", [xr, y], [chipw, chiph], "close", FALSE);   // acted on after sui_end
	xr = xr - ceil(chipw * 1.25) - 6;
	if (Scores_Chip("lg_hud", [xr, y], [ceil(chipw * 1.25), chiph], "hud graph", cvar("hud_linegraph") > 0))
		localcmd(sprintf("seta hud_linegraph %g\n", (cvar("hud_linegraph") > 0) ? 0 : 1));
	if (LineGraph_Zoomed())
	{
		xr = xr - chipw - 6;
		if (Scores_Chip("lg_fit", [xr, y], [chipw, chiph], "fit", FALSE))
			LineGraph_Fit();
	}

	// ---- the runs --------------------------------------------------------------
	y = p_y + pad + rec_sb_sztitle + ceil(pad * 0.75);
	x = 0;
	lgn_hot = -1;
	for (s = 0; s < LG_SLOTS; s = s + 1)
	{
		if (!lg_available[s]) continue;
		k = LineGraph_ChipW(s, tabh);
		if (x > 0)
		if (x + k > w - pad * 2) { x = 0; y = y + tabh + 6; }
		LineGraph_Chip(s, [p_x + pad + x, y], tabh);
		x = x + k + 6;
	}
	if (!have)
		Scores_Text([p_x + pad, y + (tabh - sb_szui) * 0.5], sb_szui,
		            "Tick a run's LINE box on the leaderboard to compare it here.", SUI_THEME_DIM, 1);
	y = y + tabh + 6 + pad * 0.5;

	// ---- the plots: fills and text, then every curve ---------------------------
	plot = [p_x + pad + gw, y + rec_sb_szhead + 6, 0];
	y0 = plot_y + ph + pad;             // the energy plot's caption
	lg_plotp = plot;
	lg_plotsize = [pw, ph, 0];
	lg_ploty1 = y0 + rec_sb_szhead + 6 + ph;
	// Patch 614: the same area on the plugin where it is present. FALSE and the QC
	// plots below draw, this frame.
	if (!have) LineGraph_NativeClose();
	else if (LineGraph_PanelNative(scr, p, w, pad, y, lg_ploty1 + 6 + rec_sb_szhead))
	{
		lg_routes_n = lg_routes_n + 1;
		sui_end();
		Font_Reset();
		if (closing)
			LineGraph_Close();
		return;
	}
	lg_routes_q = lg_routes_q + 1;
	r0 = LineGraph_RangeY(FALSE);
	r1 = LineGraph_RangeY(TRUE);

	Scores_Text([plot_x, y], rec_sb_szhead, "SPEED", SUI_THEME_MUTED, 1);
	Scores_Text([plot_x + rec_sb_szhead * 4.2, y], rec_sb_szhead, "horizontal, u/s", SUI_THEME_DIM, 1);
	Scores_Text([plot_x, y0], rec_sb_szhead, "ENERGY", SUI_THEME_MUTED, 1);
	// What it is, and beside it the warning when a drawn run's gravity is a guess;
	// where both do not fit, the warning is the one that stays.
	text = "height + v*v/2g, in units above the run's first sample";
	k = stringwidth("g 800 assumed where a recording does not say", TRUE, [rec_sb_szhead, rec_sb_szhead]);
	if (!LineGraph_Assumed())
		Scores_Text([plot_x + rec_sb_szhead * 4.9, y0], rec_sb_szhead, text, SUI_THEME_DIM, 1);
	else if (rec_sb_szhead * 4.9 + stringwidth(text, TRUE, [rec_sb_szhead, rec_sb_szhead]) + pad + k <= pw)
	{
		Scores_Text([plot_x + rec_sb_szhead * 4.9, y0], rec_sb_szhead, text, SUI_THEME_DIM, 1);
		Scores_TextR([plot_x + pw, y0], rec_sb_szhead, "g 800 assumed where a recording does not say", SUI_THEME_WARN, 1);
	}
	else
		Scores_Text([plot_x + rec_sb_szhead * 4.9, y0], rec_sb_szhead,
		            "g 800 assumed where a recording does not say", SUI_THEME_WARN, 1);
	LineGraph_Frame(plot, [pw, ph], r0, rec_sb_szhead, 1, TRUE, "");
	LineGraph_Frame([plot_x, y0 + rec_sb_szhead + 6], [pw, ph], r1, rec_sb_szhead, 1, TRUE, "");

	if (lg_tmax > 0)
	{
		step = Plot_TimeStep(lg_v1 - lg_v0, max(2, floor(pw / (rec_sb_szhead * 8))));
		n = 0;
		for (t = ceil(lg_v0 / step - 0.001) * step; t <= lg_v1 + step * 0.001 && n < 40; t = t + step)
		{
			x = floor(plot_x + (t - lg_v0) / (lg_v1 - lg_v0) * pw);
			if (x > plot_x + 2)
			if (x < plot_x + pw - 2)
			{
				drawfill([x, plot_y], [1, ph], SUI_THEME_EDGE, 0.6, 0);
				drawfill([x, y0 + rec_sb_szhead + 6], [1, ph], SUI_THEME_EDGE, 0.6, 0);
			}
			text = Plot_Clock(t, step);
			k = stringwidth(text, TRUE, [rec_sb_szhead, rec_sb_szhead]);
			Scores_Text([bound(plot_x, x - k * 0.5, plot_x + pw - k), lg_ploty1 + 6], rec_sb_szhead,
			            text, SUI_THEME_MUTED, 1);
			n = n + 1;
		}
	}
	if (have)
	if (!lg_fok)
		Scores_Text(plot + [pad * 0.5, pad * 0.5], rec_sb_szhead, "building...", SUI_THEME_MUTED, 1);

	// The footer's hints are text too: before the curves.
	y = lg_ploty1 + 6 + rec_sb_szhead + pad;
	sui_fill([p_x + pad, y - floor(pad * 0.5)], [w - pad * 2, 1], SUI_THEME_EDGE, 1, 0);
	x = Scores_Hint(p_x + w - pad, y, "esc", "close");
	x = Scores_Hint(x, y, "rmb", "whole run");
	x = Scores_Hint(x, y, "drag", "pan");
	Scores_Hint(x, y, "wheel", "zoom");

	hover = (lg_mouse_x >= plot_x && lg_mouse_x <= plot_x + pw && lg_mouse_y >= plot_y && lg_mouse_y <= lg_ploty1);
	t = lg_v0 + bound(0, (lg_mouse_x - plot_x) / pw, 1) * (lg_v1 - lg_v0);
	lg_cursor_t = t;
	if (lg_tmax > 0)
		Scores_Text([p_x + pad, y], rec_sb_szhead,
		            lg_fit ? sprintf("the whole run, %s", Plot_Clock(lg_tmax, 0.1))
		                   : sprintf("%s to %s of %s", Plot_Clock(lg_v0, 0.1), Plot_Clock(lg_v1, 0.1), Plot_Clock(lg_tmax, 0.1)),
		            SUI_THEME_DIM, 1);

	if (lg_fok)
	{
		drawsetcliparea(plot_x, plot_y, pw, ph);
		LineGraph_Curves(plot, [pw, ph], FALSE, r0, 2);
		drawresetcliparea();
		drawsetcliparea(plot_x, y0 + rec_sb_szhead + 6, pw, ph);
		LineGraph_Curves([plot_x, y0 + rec_sb_szhead + 6], [pw, ph], TRUE, r1, 2);
		drawresetcliparea();
		LineGraph_Playhead(plot, [pw, ph], FALSE, r0, 7);
		LineGraph_Playhead([plot_x, y0 + rec_sb_szhead + 6], [pw, ph], TRUE, r1, 7);

		// ---- the cursor: a line through both plots, a dot on each curve, the card
		if (hover)
		{
			x = floor(lg_mouse_x);
			drawfill([x, plot_y], [1, ph], SUI_THEME_TEXT, 0.7, 0);
			drawfill([x, y0 + rec_sb_szhead + 6], [1, ph], SUI_THEME_TEXT, 0.7, 0);
			for (s = 0; s < LG_SLOTS; s = s + 1)
			{
				if (!lg_available[s] || !lg_selected[s]) continue;
				r0 = LineGraph_At(s, t);
				if (!r0_z) continue;
				r1 = LineGraph_RangeY(FALSE);
				if (r1_z)
					LineGraph_Dot([x, plot_y + ph * (1 - (r0_x - r1_x) / (r1_y - r1_x))], 7, Plot_Series(s));
				r1 = LineGraph_RangeY(TRUE);
				e = r0_y - lg_ref[s];
				if (r1_z)
				if (ln_g[s] > 0)
					LineGraph_Dot([x, y0 + rec_sb_szhead + 6 + ph * (1 - (e - r1_x) / (r1_y - r1_x))], 7, Plot_Series(s));
			}
			LineGraph_Card(t, scr, plot, [pw, ph]);
		}
	}
	sui_end();
	Font_Reset();
	if (closing)
		LineGraph_Close();
};

void(vector scr) LineGraph_Draw =
{
	local float have, s;
	lg_hud = FALSE;
	if (lg_open)
	if (rec_sb_open || ui_he_open || ui_rs_cursor || ui_ev_cursor) LineGraph_Close();
	// A panel opened over this one (the customizer has a key) takes the mouse, and
	// a held button's release with it: here, and in the plugin.
	if (ui_cursor_claims & ~(UIC_WATCH | UIC_LINEGRAPH))
	{
		lg_drag = FALSE;
		LineGraph_NativeBlur();
	}
	if (!lg_open && !cvar("hud_linegraph")) return;
	if (rec_sb_open || ui_rs_cursor || ui_ev_cursor) return;
	// The HUD graph yields to the TAB board held over it, and to the finish card,
	// which is what a ticked line was raced for.
	if (!lg_open)
	if (sc_held) return;
	if (!lg_open)
	if (ui_rs_open)
	if (cvar("hud_results")) return;
	LineGraph_Prepare();
	have = 0;
	for (s = 0; s < LG_SLOTS; s = s + 1) if (lg_available[s]) have = have + 1;
	if (lg_open)
	{
		lg_frames = lg_frames + 1;      // `linegraph frames`
		lg_routes = lg_routes + 1;
		LineGraph_Panel(scr, have);
	}
	else if (have)
		LineGraph_Hud(scr, have);
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

// The view, from the panel's own input: `f` scales the span about time `t`.
void(float t, float f) LineGraph_Zoom =
{
	local float span, frac;
	if (lg_tmax <= 0) return;
	span = lg_v1 - lg_v0;
	frac = (span > 0) ? (t - lg_v0) / span : 0.5;
	span = min(lg_tmax, max(LG_MINSPAN, span * f));
	lg_fit = (span >= lg_tmax);
	lg_v0 = t - frac * span;
	lg_v1 = lg_v0 + span;           // LineGraph_Prepare keeps it inside the run
};

float(float evtype, float scanx, float chary, float devid) LineGraph_InputEvent =
{
	local float inplot, t;
	if (!lg_open) return FALSE;
	t = 0;
	if (lg_plotsize_x > 0)
		t = lg_v0 + bound(0, (lg_mouse_x - lg_plotp_x) / lg_plotsize_x, 1) * (lg_v1 - lg_v0);
	if (evtype == IE_MOUSEABS)
	{
		lg_mouse = [scanx, chary];
		LineGraph_NativeMoved();
		if (lg_drag)
		if (lg_plotsize_x > 0)
		{
			// The time the button went down on stays under the cursor.
			t = lg_v1 - lg_v0;
			lg_v0 = lg_dragt - (scanx - lg_plotp_x) / lg_plotsize_x * t;
			lg_v1 = lg_v0 + t;
			lg_fit = FALSE;
		}
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	// The plugin's plots take what lands on them; the chips and ESC stay here.
	if (evtype == IE_KEYDOWN || evtype == IE_KEYUP)
	if (LineGraph_NativeKey(evtype, scanx))
		return TRUE;
	inplot = (lg_mouse_x >= lg_plotp_x && lg_mouse_x <= lg_plotp_x + lg_plotsize_x
	       && lg_mouse_y >= lg_plotp_y && lg_mouse_y <= lg_ploty1);
	if (lgn_drew) inplot = FALSE;       // the QC plots are not on screen
	if (scanx == K_MOUSE1)
	{
		// A drag pans only once zoomed in: the whole run has nowhere to go.
		if (evtype == IE_KEYDOWN)
		if (inplot)
		if (!lg_fit)
		{
			lg_drag = TRUE;
			lg_dragt = t;
		}
		if (evtype == IE_KEYUP) lg_drag = FALSE;
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN) LineGraph_Fit();
		return TRUE;
	}
	if (scanx == K_MWHEELUP || scanx == K_MWHEELDOWN)
	{
		if (evtype == IE_KEYDOWN)
		if (inplot)
			LineGraph_Zoom(t, (scanx == K_MWHEELUP) ? 0.8 : 1.25);
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
	local float n, s, t, vs, ve;
	local vector sample;
	n = tokenize(cmd);
	if (argv(0) != "linegraph") return FALSE;
	if (n == 1) { if (lg_open) LineGraph_Close(); else LineGraph_Open(); return TRUE; }
	if (argv(1) == "close") { LineGraph_Close(); return TRUE; }
	if (argv(1) == "status")
	{
		print(sprintf("linegraph: open %g cursor %.4f duration %.4f build %g\n", lg_open, lg_cursor_t, lg_tmax, lg_buildslot));
		print(sprintf("linegraph: view %.4f %.4f fit %g drawn %.4f %.4f ok %g hud %g\n",
		              lg_v0, lg_v1, lg_fit, lg_f0, lg_f1, lg_fok, lg_hud));
		sample = LineGraph_RangeY(FALSE);
		print(sprintf("linegraph: speed %g %g valid %g", sample_x, sample_y, sample_z));
		sample = LineGraph_RangeY(TRUE);
		print(sprintf(" energy %g %g valid %g\n", sample_x, sample_y, sample_z));
		// What the last frame's curves were drawn from: vertices, speed then energy.
		vs = ve = 0;
		for (s = 0; s < LG_SLOTS; s = s + 1)
		{
			vs = vs + lg_polyn[s];
			ve = ve + lg_polyn[LG_SLOTS + s];
		}
		print(sprintf("linegraph: vertices %g %g\n", vs, ve));
		// The panel's plots as last laid out: left, top, width, and both plots' height.
		print(sprintf("linegraph: plots %g %g %g %g\n", lg_plotp_x, lg_plotp_y, lg_plotsize_x, lg_ploty1 - lg_plotp_y));
		sample = LineGraph_NativePx(lg_plotp);
		print(sprintf("linegraph: plots pixels %g %g", sample_x, sample_y));
		sample = LineGraph_NativePx([lg_plotsize_x, lg_ploty1 - lg_plotp_y]);
		print(sprintf(" %g %g\n", sample_x, sample_y));
		// Where the open replay's marker stands; -1 with no replay drawn.
		print(sprintf("linegraph: playhead %.4f runs %g\n",
		              lg_available[0] ? rec_wt_time - ln_start[0] : -1,
		              lg_available[0] + lg_available[1] + lg_available[2] + lg_available[3] + lg_available[4]
		              + lg_available[5] + lg_available[6] + lg_available[7] + lg_available[8]));
		// Patch 614. drew: the plugin drew the last frame's plots; refused: why it was
		// given up for this open (LineGraph_NativeFail), 0 if it was not.
		// rebuilt: plots the plugin cut afresh for the last frame; cut: the sum of that since
		// the game started (it stands still while a view is only read).
		print(sprintf("linegraph: native drew %g refused %g revision %g series %g points %g rebuilt %g cut %g\n",
		              lgn_drew, lgn_failed, lgn_rev, lgn_count, lgn_points, lgn_rebuilt, lgn_cut));
		print(sprintf("linegraph: native view %.4f %.4f hover %g %.4f\n", lgn_v0, lgn_v1, lgn_hover, lgn_hovert));
		print(sprintf("linegraph: native input in %g down %g wheel %g lost %g nodraw %g ever %g events %g\n",
		              lgn_in, lgn_down, lgn_wheel, lgn_lost, lgn_nodraw, lgn_nodraws, lgn_events));
		// Every panel frame is one or the other: a frame with no plots would show here.
		print(sprintf("linegraph: routes panel %g native %g qc %g\n", lg_routes, lg_routes_n, lg_routes_q));
		print(sprintf("linegraph: native rect %g %g %g %g\n", lgn_pos_x, lgn_pos_y, lgn_size_x, lgn_size_y));
		sample = LineGraph_NativePx(lgn_pos);
		print(sprintf("linegraph: native pixels %g %g", sample_x, sample_y));
		sample = LineGraph_NativePx(lgn_size);
		print(sprintf(" %g %g\n", sample_x, sample_y));
		return TRUE;
	}
	if (argv(1) == "cursor" && n == 4)
	{
		// Typed, bound or stuffed: only what a mouse could report is a position.
		t = stof(argv(2));
		s = stof(argv(3));
		if (!(t > -32768 && t < 32768)) t = 0;
		if (!(s > -32768 && s < 32768)) s = 0;
		LineGraph_InputEvent(IE_MOUSEABS, t, s, 0);
		return TRUE;
	}
	if (argv(1) == "cursorat" && n == 3)
	{
		if (lg_tmax > 0)
		if (lg_v1 > lg_v0)
			LineGraph_InputEvent(IE_MOUSEABS, lg_plotp_x + lg_plotsize_x * bound(0, (stof(argv(2)) - lg_v0) / (lg_v1 - lg_v0), 1),
			                     lg_plotp_y + lg_plotsize_y * 0.5, 0);
		return TRUE;
	}
	// The view, for a cfg: `zoom <from> <to>` in seconds, bare `zoom` for the whole run.
	if (argv(1) == "zoom")
	{
		LineGraph_Fit();
		if (n == 4)
		if (stof(argv(3)) > stof(argv(2)))
		{
			// Inside the run, both ends: a range the plugin could not show came back as
			// a report the engine dropped the owner over, every frame. With none of it
			// inside, the whole run stays.
			t = bound(0, stof(argv(2)), lg_tmax);
			s = bound(0, stof(argv(3)), lg_tmax);
			if (s > t)
			{
				lg_fit = FALSE;
				lg_v0 = lgn_r0 = t;
				lg_v1 = lgn_r1 = s;
			}
		}
		return TRUE;
	}
	// For a cfg: a point of the native plots' rectangle by fraction (their own axes
	// are the plugin's to place, so a time cannot be aimed at from here).
	if (argv(1) == "cursorfrac" && n == 4)
	{
		LineGraph_InputEvent(IE_MOUSEABS, lgn_pos_x + lgn_size_x * stof(argv(2)), lgn_pos_y + lgn_size_y * stof(argv(3)), 0);
		return TRUE;
	}
	// For a cfg, through the panel's own input path: `button 1|2 down|up`, `wheel 1|-1`.
	if (argv(1) == "button" && n == 4)
	{
		LineGraph_InputEvent((argv(3) == "down") ? IE_KEYDOWN : IE_KEYUP, (argv(2) == "2") ? K_MOUSE2 : K_MOUSE1, 0, 0);
		return TRUE;
	}
	if (argv(1) == "wheel" && n == 3)
	{
		LineGraph_InputEvent(IE_KEYDOWN, (stof(argv(2)) > 0) ? K_MWHEELUP : K_MWHEELDOWN, 0, 0);
		return TRUE;
	}
	// What a frame costs with the panel up, for an A/B of the two plot routes: frames
	// drawn since the last ask, and the client seconds they took.
	if (argv(1) == "frames")
	{
		print(sprintf("linegraph: frames %g seconds %.4f native %g\n", lg_frames, cltime - lg_frames_t, lgn_drew));
		lg_frames = 0;
		lg_frames_t = cltime;
		return TRUE;
	}
	// For a cfg: `refuse` gives the plugin up at the next draw, as any refusal would;
	// `lose N` closes its owner behind the panel on each of the next N draws.
	if (argv(1) == "refuse")
	{
		lgn_refuse = TRUE;
		return TRUE;
	}
	if (argv(1) == "lose" && n == 3)
	{
		lgn_lose = bound(0, floor(stof(argv(2))), 8);
		return TRUE;
	}
	// One hostile transaction a frame at the native plots (LineGraph_NativeProbe).
	if (argv(1) == "probe")
	{
		if (!lgn_drew) print("linegraph: probe needs the native plots drawn\n");
		else lgn_probe = 1;
		return TRUE;
	}
	if (argv(1) == "toggle" && n == 3)
	{
		s = bound(0, floor(stof(argv(2))), LG_SLOTS - 1);
		lg_selected[s] = !lg_selected[s];
		lg_gen = lg_gen + 1;
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
	print("linegraph [close | status | zoom [<from> <to>] | toggle 0..8 | sample <slot> <seconds> | probe]\n");
	return TRUE;
};
