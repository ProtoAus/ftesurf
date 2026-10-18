/*
  cl_compare.qc -- the Comparison window.  Patch 779.

  You against the race ghost's line: RG_Frame's first anchored choice (your stage
  PB, your run PB, else the first ticked board line), kept even when its body has
  been dropped past its end (rg_cmpslot, cl_raceghost.qc), and remembered from the
  last running frame for the finish row, which arrives once the clock has stopped.

  Live, measured where you ARE: the line's point nearest your feet, followed by a
  cursor (CMP_BACK seconds behind to CMP_AHEAD ahead of the last match) and found
  afresh over the leg -- from the line's anchor -- when that loses you.  Not by its
  clock: after a fail you are seconds off its pace and still on its route.  Time is
  yours minus theirs to get here; speed and energy yours minus theirs here, both on
  the speedometer's zero.  A split is your row against their own crossing of it (the
  server's hull sweep over their line; the finish is their line's end).  A Segments
  row is your energy against theirs where you are.  Green ahead, red behind.

  Not in a rewind, a replay or spectate: "you" there is not a running body.
*/

#define CMP_BACK   1            // the cursor's search, seconds of the line behind it
#define CMP_AHEAD  4            // ...and ahead
#define CMP_FAR    384          // further than this from the line: not comparable
#define CMP_NEWRUN 0.25         // a clock this far below the last match's: a new attempt

float  cmp_ok;                  // this frame's live match
float  cmp_dist;
float  cmp_yt, cmp_ys, cmp_ye;  // you: leg time, speed, energy
float  cmp_tt, cmp_ts, cmp_te;  // them, at the matched point
float  cmp_mt, cmp_ms, cmp_mz, cmp_mvz, cmp_mi;     // Cmp_Match / Cmp_Nearest's answers
float  cmp_cur, cmp_curslot, cmp_curgen, cmp_lastclk;   // the cursor; -1 none
// The line in use (Cmp_Ctx): slot, its clock at the anchor, your clock there, the leg.
float  cmp_cs, cmp_ca, cmp_cam, cmp_cleg;
float  cmp_lslot, cmp_lanc, cmp_lam, cmp_lleg;      // the last running frame's
// The last split (kind, number, you, them) and the last Segments row.
float  cmp_spat, cmp_spk, cmp_spseg, cmp_sppend, cmp_spfrom;
float  cmp_syt, cmp_sys, cmp_sye, cmp_stt, cmp_sts, cmp_ste;
float  cmp_sgat, cmp_sgk, cmp_sgsub, cmp_sgy, cmp_sgt;
float  cmp_byt, cmp_bys, cmp_bye, cmp_btt, cmp_bts, cmp_bte;   // Cmp_Block's six numbers

void() Cmp_RegisterCvars =
{
	registercvar("hud_compare",        "1",      CVAR_ARCHIVE);
	registercvar("hud_compare_x",      "0.0333", CVAR_ARCHIVE);
	registercvar("hud_compare_y",      "0.66",   CVAR_ARCHIVE);
	registercvar("hud_compare_size",   "0",      CVAR_ARCHIVE);
	registercvar("hud_compare_splits", "1",      CVAR_ARCHIVE);
	registercvar("hud_compare_segs",   "1",      CVAR_ARCHIVE);
	registercommand("compare");
	cmp_lslot = cmp_cur = cmp_spfrom = -1;
};

float() Cmp_Off =
{
	return (ui_rw_on || rec_wt_on || Spec_Active());
};

// The line to compare against: this frame's choice, else the last running frame's.
float() Cmp_Ctx =
{
	if (Cmp_Off())
		return FALSE;
	if (rg_cmpslot >= 0)
	{
		cmp_cs   = rg_cmpslot;
		cmp_ca   = rg_cmpanc;
		cmp_cam  = rg_cmpam;
		cmp_cleg = rg_runleg;
		return TRUE;
	}
	if (cmp_lslot < 0)
		return FALSE;
	cmp_cs   = cmp_lslot;
	cmp_ca   = cmp_lanc;
	cmp_cam  = cmp_lam;
	cmp_cleg = cmp_lleg;
	return TRUE;
};

// The line's gravity, or the server's where the file pinned none (the 800 is a guess).
float(float s) Cmp_G =
{
	local float g;

	g = ln_g[s];
	if (ln_g_assumed[s])
		g = serverkeyfloat("sv_gravity");
	if (g <= 0)
		g = 800;
	return g;
};

/*
  Slot s's sample nearest `feet` in [i0, i1], exactly: a chunk whose bounding sphere
  (ln_cc/ln_cr, cl_lines.qc) is no nearer than the best so far is skipped.  The
  distance, and the index in cmp_mi; -1 for an empty range.
*/
float(float s, float i0, float i1, vector feet) Cmp_Nearest =
{
	local float b, cb, c, k, i, lo, hi, d, bd, bi;

	b  = LN_B(s);
	cb = b / LN_CHUNK;
	bd = bi = -1;
	for (c = floor(i0 / LN_CHUNK); c * LN_CHUNK <= i1; c = c + 1)
	{
		k = cb + c;
		if (bd >= 0)
		if (vlen(ln_cc[k] - feet) - ln_cr[k] >= bd)
			continue;
		lo = max(i0, c * LN_CHUNK);
		hi = min(i1, c * LN_CHUNK + LN_CHUNK - 1);
		for (i = lo; i <= hi; i = i + 1)
		{
			d = vlen(ln_pos[b + i] - feet);
			if (bd < 0 || d < bd)
			{
				bd = d;
				bi = i;
			}
		}
	}
	cmp_mi = bi;
	return bd;
};

/*
  Slot s's point nearest `feet`, its leg starting at its clock `a`: near the cursor
  while it holds, else over the whole leg; then projected onto the segment toward
  you (not across a teleport).  Answers in cmp_mt/ms/mz/mvz and cmp_dist; FALSE past
  CMP_FAR.
*/
float(float s, float a, vector feet) Cmp_Match =
{
	local float b, ia, ib, i0, i1, bd, bi, j, f;
	local vector p0, p1, dv;

	b  = LN_B(s);
	ia = ln_ia[s];
	ib = ln_ib[s];
	if (!ln_on[s] || ib <= ia)
		return FALSE;
	ia = bound(ia, Line_Find(s, a), ib);        // this leg only: not an earlier stage
	if (cmp_curslot != s || cmp_curgen != ln_graphgen[s] || rg_now < cmp_lastclk - CMP_NEWRUN)
		cmp_cur = -1;
	bd = -1;
	if (cmp_cur >= ia)
	if (cmp_cur <= ib)
	{
		i0 = bound(ia, Line_Find(s, ln_t[b + cmp_cur] - CMP_BACK), ib);
		i1 = bound(ia, Line_Find(s, ln_t[b + cmp_cur] + CMP_AHEAD), ib);
		bd = Cmp_Nearest(s, i0, i1, feet);
	}
	if (bd < 0 || bd > CMP_FAR)
		bd = Cmp_Nearest(s, ia, ib, feet);
	bi = cmp_mi;
	if (bd < 0 || bd > CMP_FAR)
	{
		cmp_cur = -1;
		return FALSE;
	}
	cmp_cur = bi;
	cmp_curslot = s;
	cmp_curgen = ln_graphgen[s];
	cmp_lastclk = rg_now;

	// The neighbour on your side; nested: ln_pos[b + bi - 1] at bi == 0 is out of range.
	j = bi + 1;
	if (j > ib)
		j = bi - 1;
	else if (bi > ia)
	if (vlen(ln_pos[b + bi - 1] - feet) < vlen(ln_pos[b + j] - feet))
		j = bi - 1;
	f = 0;
	if (j < ia)
		j = bi;
	else if (ln_brk[b + max(bi, j)])
		j = bi;
	else
	{
		p0 = ln_pos[b + bi];
		p1 = ln_pos[b + j];
		dv = p1 - p0;
		if (dv * dv > 0)
			f = bound(0, ((feet - p0) * dv) / (dv * dv), 1);
	}
	p0 = ln_pos[b + bi];
	p1 = ln_pos[b + j];
	cmp_mt   = ln_t[b + bi] + (ln_t[b + j] - ln_t[b + bi]) * f;
	cmp_ms   = ln_spd[b + bi] + (ln_spd[b + j] - ln_spd[b + bi]) * f;
	cmp_mvz  = ln_vz[b + bi] + (ln_vz[b + j] - ln_vz[b + bi]) * f;
	cmp_mz   = p0_z + (p1_z - p0_z) * f;
	cmp_dist = bd;
	return TRUE;
};

// Slot s's sample i as cmp_ms/mz/mvz, for Cmp_E.
void(float s, float i) Cmp_At =
{
	local float b;
	local vector p;

	b = LN_B(s) + i;
	p = ln_pos[b];
	cmp_ms  = ln_spd[b];
	cmp_mvz = ln_vz[b];
	cmp_mz  = p_z;
};

// The matched point's energy height (LineGraph_Energy's form).
float(float s) Cmp_E =
{
	return cmp_mz + (cmp_ms * cmp_ms + cmp_mvz * cmp_mvz) / (2 * Cmp_G(s));
};

// You and the line, here and now: this frame's choice only (a running clock).
float() Cmp_Live =
{
	local vector ss;

	cmp_ok = FALSE;
	if (Cmp_Off() || rg_cmpslot < 0)
		return FALSE;
	if (!Cmp_Match(rg_cmpslot, rg_cmpanc, HUD_Feet()))
		return FALSE;
	ss = HUD_SplitSample();
	cmp_yt = rg_now - rg_cmpam;
	cmp_ys = ss_x;
	cmp_ye = ss_y;
	cmp_tt = cmp_mt - rg_cmpanc;
	cmp_ts = cmp_ms;
	cmp_te = Cmp_E(rg_cmpslot) - HUD_EnergyRef();
	cmp_ok = TRUE;
	return TRUE;
};

// As the Splits list names the row (Timer_DrawSplits).
string() Cmp_SplitName =
{
	if (cmp_spk == SPK_STAGE)
		return sprintf("stage %g", cmp_spseg);
	if (cmp_spk == SPK_CP)
		return sprintf("cp %g", cmp_spseg);
	return "finish";
};

// The server's event test (SV_ZoneHit): the hull swept at run_zone_hull 1, else the
// point; at a teleport, where the body is.
float(float z, vector a, vector b, float swept) Cmp_Hit =
{
	if (serverkeyfloat("run_zone_hull") >= 1)
	{
		if (swept)
			return Zone_BoxSwept(z, a, b, PM_HULL_MINS, PM_HULL_MAXS);
		return Zone_BoxInside(z, b, PM_HULL_MINS, PM_HULL_MAXS);
	}
	if (swept)
		return Zone_SegmentInside(z, a, b);
	return Zone_PointInside(z, b);
};

/*
  Slot s's first crossing, from its anchor `a` (or the last split found, `from`), of
  the regions a split of kind k and number n is made of on this track: a stage's box
  (zone_seg), a checkpoint (zone_cp, numbered across the track), or the finish --
  the END, and for a stage run (leg > 0) also the next stage's box.  The index, or -1.
*/
#define CMP_ZMAX 16
float cmp_zl[CMP_ZMAX];
float(float s, float a, float k, float n, float leg, float from) Cmp_SplitFind =
{
	local float b, ia, ib, i, z, nz, j, ty;

	nz = 0;
	ty = ZONE_END;
	if (k == SPK_STAGE)
		ty = ZONE_STAGE;
	else if (k == SPK_CP)
		ty = ZONE_CHECKPOINT;
	for (z = 0; z < zone_count && nz < CMP_ZMAX; z = z + 1)
	{
		if (zone_track[z] != rg_track)
			continue;
		if (ty == ZONE_END && leg > 0)
		if (zone_type[z] == ZONE_STAGE && zone_seg[z] == leg)
		{
			cmp_zl[nz] = z;
			nz = nz + 1;
			continue;
		}
		if (zone_type[z] != ty)
			continue;
		if (ty == ZONE_STAGE && zone_seg[z] != n)
			continue;
		if (ty == ZONE_CHECKPOINT && zone_cp[z] != n)
			continue;
		cmp_zl[nz] = z;
		nz = nz + 1;
	}
	if (nz < 1 || !ln_on[s])
		return -1;
	b  = LN_B(s);
	ib = ln_ib[s];
	ia = bound(ln_ia[s], Line_Find(s, a), ib);
	if (from > ia)
	if (from <= ib)
		ia = from;
	for (i = ia; i <= ib; i = i + 1)
		for (j = 0; j < nz; j = j + 1)
		{
			z = cmp_zl[j];
			if (i > ia)
			if (!ln_brk[b + i])
			{
				if (Cmp_Hit(z, ln_pos[b + i - 1], ln_pos[b + i], TRUE))
					return i;
				continue;
			}
			if (Cmp_Hit(z, ln_pos[b + i], ln_pos[b + i], FALSE))
				return i;
		}
	return -1;
};

/*
  Timer_SplitsPush's hook: the split row just pushed, your numbers the row's, theirs
  their own crossing of it (a finish: their line's end, where it is the same leg).
  Where their line has none, the position match a frame on (Cmp_SplitTake).
  Cleared first: a split that cannot be compared shows nothing, not the last one.
*/
void(float row) Cmp_Split =
{
	local float i, s;

	cmp_spat = cmp_sppend = 0;
	if (!cvar("hud_compare") || !cvar("hud_compare_splits"))
		return;
	if (!Cmp_Ctx())
		return;
	cmp_spk   = ui_sp_kind[row];
	cmp_spseg = ui_sp_seg[row];
	cmp_syt   = ui_sp_ticks[row] * Timer_Tick() - cmp_cam;
	cmp_sys   = ui_sp_speed[row];
	cmp_sye   = ui_sp_energy[row];
	s = cmp_cs;
	i = -1;
	if (cmp_spk == SPK_FINISH)
	{
		if (cmp_cleg <= 0 && ln_leg[s] <= 0)
			i = ln_ib[s];
		else if (cmp_cleg > 0 && ln_leg[s] == cmp_cleg)
			i = ln_ib[s];
	}
	if (i < 0)
		i = Cmp_SplitFind(s, cmp_ca, cmp_spk, cmp_spseg, cmp_cleg, cmp_spfrom);
	if (i < 0)
	{
		cmp_sppend = 1;
		return;
	}
	cmp_spfrom = i;
	Cmp_At(s, i);
	cmp_stt  = ln_t[LN_B(s) + i] - cmp_ca;
	cmp_sts  = cmp_ms;
	cmp_ste  = Cmp_E(s) - HUD_EnergyRef();
	cmp_spat = cltime;
	dprint(sprintf("compare: split %s (their crossing)  you %.3f %.0f %.0f  them %.3f %.0f %.0f\n",
	               Cmp_SplitName(), cmp_syt, cmp_sys, cmp_sye, cmp_stt, cmp_sts, cmp_ste));
};

// The fallback, a frame after the push: the stat can arrive before the predicted
// feet reach a placement the client did not predict.
void() Cmp_SplitTake =
{
	if (cmp_sppend <= 0)
		return;
	cmp_sppend = 0;
	if (!cmp_ok)
		return;
	cmp_stt  = cmp_tt;
	cmp_sts  = cmp_ts;
	cmp_ste  = cmp_te;
	cmp_spat = cltime;
	dprint(sprintf("compare: split %s (where you are)  you %.3f %.0f %.0f  them %.3f %.0f %.0f\n",
	               Cmp_SplitName(), cmp_syt, cmp_sys, cmp_sye, cmp_stt, cmp_sts, cmp_ste));
};

// Seq_Push's hook: the Segments row just pushed or merged, on its own zero.
void(float row) Cmp_Seg =
{
	cmp_sgat = 0;
	if (!cvar("hud_compare") || !cvar("hud_compare_segs"))
		return;
	if (!Cmp_Live())
		return;
	cmp_sgk   = seq_kind[row];
	cmp_sgsub = seq_sub[row];
	cmp_sgy   = seq_eend[row] - seq_eref[row];
	cmp_sgt   = Cmp_E(rg_cmpslot) - seq_eref[row];
	cmp_sgat  = cltime;
	dprint(sprintf("compare: segment %g  you %.0f  them %.0f  (%.0f u off)\n",
	               cmp_sgk, cmp_sgy, cmp_sgt, cmp_dist));
};

// +0.51 / -1.20 seconds; +60 / -12 for the rest.
string(float d, float secs) Cmp_Diff =
{
	if (secs)
		return sprintf("%s%.2f", (d >= 0) ? "+" : "-", fabs(d));
	return sprintf("%s%d", (d >= 0) ? "+" : "-", fabs(d));
};

// Ahead is green: less time, more speed, more energy.
vector(float d, float secs) Cmp_Col =
{
	if (secs)
		d = -d;
	if (d > (secs ? 0.005 : 0.5))
		return TC_AHEAD;
	if (d < (secs ? -0.005 : -0.5))
		return TC_BEHIND;
	return '0.65 0.67 0.72';
};

/*
  Columns in characters of the fixed-pitch face (0.6 em, as BD_Row): the block's
  name at 0, you/them at 8, time right-aligned at 21, speed at 28, energy at 34, a
  Segments row's difference at 40.  Under the line's name, one row names them for
  every block.
*/
#define CMP_CW 0.6
#define CMP_X1 8
#define CMP_X2 21
#define CMP_X3 28
#define CMP_X4 34
#define CMP_X5 40

/*
  A block: you, them and the difference, from cmp_byt..cmp_bte (more than eight
  would be parameters).  cmp_byt < -1e9 is a Segments row: energy only, its
  difference on the `them` line.  A speed or energy difference is of the two numbers
  shown, so 300 and 270 read +30.
*/
float(vector p, float y, float sz, float lh, string title) Cmp_Block =
{
	local float cw, x0, x1, x2, x3, x4, en, yt, ys, ye, tt, ts, te;
	local vector dim;

	yt = cmp_byt;
	ys = rint(HUD_Round(cmp_bys));
	ye = rint(HUD_Round(cmp_bye));
	tt = cmp_btt;
	ts = rint(HUD_Round(cmp_bts));
	te = rint(HUD_Round(cmp_bte));

	cw = sz * CMP_CW;
	x0 = p_x + cw * CMP_X1;
	x1 = p_x + cw * CMP_X2;
	x2 = p_x + cw * CMP_X3;
	x3 = p_x + cw * CMP_X4;
	x4 = p_x + cw * CMP_X5;
	en = (yt > -1000000000);
	dim = '0.55 0.60 0.68';
	HUD_Text([p_x, y, 0], title, sz, '0.85 0.90 1.00', 0.9);

	HUD_Text([x0, y, 0], "you", sz, dim, 0.85);
	if (en)
	{
		HUD_TextR([x1, y, 0], Time_MsString(Time_TickMs(yt, 1)), sz, '1 1 1', 1);
		HUD_TextR([x2, y, 0], sprintf("%d", ys), sz, '1 1 1', 1);
	}
	HUD_TextR([x3, y, 0], sprintf("%d", ye), sz, '1 1 1', 1);
	y = y + lh;

	HUD_Text([x0, y, 0], "them", sz, dim, 0.85);
	if (en)
	{
		HUD_TextR([x1, y, 0], Time_MsString(Time_TickMs(tt, 1)), sz, '0.75 0.80 0.88', 1);
		HUD_TextR([x2, y, 0], sprintf("%d", ts), sz, '0.75 0.80 0.88', 1);
	}
	HUD_TextR([x3, y, 0], sprintf("%d", te), sz, '0.75 0.80 0.88', 1);
	if (!en)
	{
		HUD_TextR([x4, y, 0], strcat(Cmp_Diff(ye - te, FALSE), "e"), sz, Cmp_Col(ye - te, FALSE), 1);
		return y + lh * 1.3;
	}
	y = y + lh;

	HUD_TextR([x1, y, 0], Cmp_Diff(yt - tt, TRUE), sz, Cmp_Col(yt - tt, TRUE), 1);
	HUD_TextR([x2, y, 0], Cmp_Diff(ys - ts, FALSE), sz, Cmp_Col(ys - ts, FALSE), 1);
	HUD_TextR([x3, y, 0], Cmp_Diff(ye - te, FALSE), sz, Cmp_Col(ye - te, FALSE), 1);
	return y + lh * 1.3;
};

void(vector scr) Cmp_Draw =
{
	local vector p;
	local float sz, lh, y, live, sp, sg;
	local string s;

	if (!cvar("hud_compare") || Cmp_Off())
		return;
	// A new attempt is armed: the last one's line, split and segment are not this one's.
	if (getstatf(STAT_FS_TIMERSTATE) == TS_ARMED)
	{
		cmp_spat = cmp_sgat = cmp_sppend = 0;
		cmp_lslot = cmp_spfrom = -1;
	}
	if (rg_cmpslot >= 0)
	if (getstatf(STAT_FS_TIMERSTATE) == TS_RUNNING)
	{
		cmp_lslot = rg_cmpslot;
		cmp_lanc  = rg_cmpanc;
		cmp_lam   = rg_cmpam;
		cmp_lleg  = rg_runleg;
	}
	live = Cmp_Live();
	Cmp_SplitTake();
	sp = (cvar("hud_compare_splits") && cmp_spat > 0);
	sg = (cvar("hud_compare_segs") && cmp_sgat > 0);
	if (!live && !sp && !sg)
		return;

	sz = HUD_Size("hud_compare_size", 8 * ui_cv_scale);
	lh = sz * 1.3;
	p = [scr_x * cvar("hud_compare_x"), scr_y * cvar("hud_compare_y"), 0];
	y = p_y;
	Font_Set(ui_font_mono);
	s = Cmp_Ctx() ? RG_SlotName(cmp_cs) : "--";
	if (strlen(s) > CMP_X5 - 4)
		s = strcat(substring(s, 0, CMP_X5 - 5), "~");
	HUD_Text([p_x, y, 0], strcat("vs ", s), sz, '0.65 0.85 1.00', 1);
	y = y + lh;
	HUD_TextR([p_x + sz * CMP_CW * CMP_X2, y, 0], "time", sz, '0.55 0.60 0.68', 0.85);
	HUD_TextR([p_x + sz * CMP_CW * CMP_X3, y, 0], "u/s", sz, '0.55 0.60 0.68', 0.85);
	HUD_TextR([p_x + sz * CMP_CW * CMP_X4, y, 0], "e", sz, '0.55 0.60 0.68', 0.85);
	y = y + lh * 1.2;

	if (live)
	{
		cmp_byt = cmp_yt;  cmp_bys = cmp_ys;  cmp_bye = cmp_ye;
		cmp_btt = cmp_tt;  cmp_bts = cmp_ts;  cmp_bte = cmp_te;
		y = Cmp_Block(p, y, sz, lh, "now");
	}
	if (sp)
	{
		cmp_byt = cmp_syt;  cmp_bys = cmp_sys;  cmp_bye = cmp_sye;
		cmp_btt = cmp_stt;  cmp_bts = cmp_sts;  cmp_bte = cmp_ste;
		y = Cmp_Block(p, y, sz, lh, Cmp_SplitName());
	}
	if (sg)
	{
		cmp_byt = -2000000000;  cmp_bys = 0;  cmp_bye = cmp_sgy;
		cmp_btt = 0;            cmp_bts = 0;  cmp_bte = cmp_sgt;
		y = Cmp_Block(p, y, sz, lh, HUD_SeqName(cmp_sgk, cmp_sgsub));
	}
	Font_Reset();
	HUD_Rect("compare", p, [sz * CMP_CW * CMP_X5, y - p_y, 0], p);
};

// `compare`: the window as text.
float(string cmd) Cmp_ConsoleCommand =
{
	if (argv(0) != "compare")
		return FALSE;
	if (!Cmp_Live())
		print(sprintf("compare: no live match (line slot %g, run clock %.3f)\n", rg_cmpslot, rg_now));
	else
	{
		print(sprintf("compare: vs slot %g \"%s\" %.0f u off\n", rg_cmpslot,
		              RG_SlotName(rg_cmpslot), cmp_dist));
		print(sprintf("compare: now  you %.3f %.0f %.0f  them %.3f %.0f %.0f\n",
		              cmp_yt, cmp_ys, cmp_ye, cmp_tt, cmp_ts, cmp_te));
	}
	if (cmp_spat > 0)
		print(sprintf("compare: split %s  you %.3f %.0f %.0f  them %.3f %.0f %.0f\n",
		              Cmp_SplitName(), cmp_syt, cmp_sys, cmp_sye, cmp_stt, cmp_sts, cmp_ste));
	if (cmp_sgat > 0)
		print(sprintf("compare: segment %s  you %.0f  them %.0f\n",
		              HUD_SeqName(cmp_sgk, cmp_sgsub), cmp_sgy, cmp_sgt));
	return TRUE;
};
