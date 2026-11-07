/* Patch 502: a visual prefix beside each save's .view. This is not evidence.
   Raw samples retain contact/stitch marks when a branch is rebuilt; copying
   only the decimated positions would keep abandoned glyphs and lose colours. */
float tr_raw, tr_stitch, tr_slseq, tr_cur_flags;
vector tr_cur_ang, tr_cur_vel;
float tr_rep_raw, tr_rep_tick, tr_rep_end, tr_rep_ack, tr_rep_go, tr_saveack;
float tr_req_wait;
float tr_timedgo_ack, tr_go_visual_t, tr_rep_tracewant, tr_rep_tracegot, tr_ticket;
float tr_practice, tr_practicebase, tr_practiceat;
// P1007: the energy zero the HUD used for this sample, as a 15th field of the
// raw line when known (a 14-field line is an older file or a replay prefix).
float tr_eref, tr_erefok;

/*
  P1384: a load or a trim fills tr_raw at once and the live line takes those rows over the next
  frames (Trail_Catch from Trail_Frame), TR_CATCH a frame. Refeeding them all in the load's frame
  was 300 ms for 45835 rows, 45 ms for 6416 (bhop_monster_jam save012, a p90 save; rig/bench1 in
  the P1384 task root). While it catches up Trail_Take only records, so the rows stay in order;
  Trail_Settle finishes it first wherever the whole line is read (rewind, a run's end).
*/
#define TR_CATCH 400            // ~2.6 ms of QC a frame at the measured 6.6 us a row
float  tr_catching, tr_catchi;  // the line is behind tr_raw; the next row it has not taken
vector tr_catchv;               // the last recorded sample's velocity: Trail_Take's break test

void() Trail_RawClear =
{
	if (tr_raw >= 1)
		buf_del(tr_raw);
	tr_raw = buf_create_ex("string", 0);
	tr_stitch = tr_practice = FALSE;
	tr_catching = FALSE;
};

// One raw row into the live line, nothing else (Trail_Take keeps the sample counters).
float(string s) Trail_CatchFeed =
{
	local float n;
	n = tokenize(s);
	if (n != 14 && n != 15)
		return FALSE;
	Line_Point(tr_live, [stof(argv(1)), stof(argv(2)), stof(argv(3))],
	           [stof(argv(4)), stof(argv(5)), stof(argv(6))], stof(argv(7)), stof(argv(0)),
	           stof(argv(8)), stof(argv(9)), [stof(argv(10)), stof(argv(11)), stof(argv(12))]);
	return TRUE;
};

// Up to `rows` more of tr_raw into the line. A bad row is passed over (Trail_Load used to stop
// there: only a damaged file has one).
void(float rows) Trail_Catch =
{
	local float n, end;
	if (!tr_catching)
		return;
	n = (tr_raw >= 1) ? buf_getsize(tr_raw) : 0;
	end = min(n, tr_catchi + rows);
	for (; tr_catchi < end; tr_catchi = tr_catchi + 1)
		Trail_CatchFeed(bufstr_get(tr_raw, tr_catchi));
	if (tr_catchi >= n)
		tr_catching = FALSE;
	Line_End(tr_live);
};

void() Trail_Settle = { Trail_Catch(LN_CAP * 4); };

// The rows just put in tr_raw: counters from its last row, then the line starts catching up.
void() Trail_CatchStart =
{
	local float n;
	n = buf_getsize(tr_raw);
	tr_nsamp = n;
	tr_lastt = 0;
	if (n > 0 && tokenize(bufstr_get(tr_raw, n - 1)) >= 14)
	{
		tr_lastt = stof(argv(0));
		tr_lastp = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
		tr_catchv = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
	}
	tr_catchi = 0;
	tr_catching = (n > 0);
	Trail_Catch(TR_CATCH);
	if (!n)
		Line_End(tr_live);
};

string(vector o, vector v, float fl, float t, float brk, float stitch, vector aux, float pitch) Trail_RawSample =
{
	return sprintf("%.6f %s %s %g %g %g %s", t,
	               sprintf("%.6f %.6f %.6f", o_x, o_y, o_z),
	               sprintf("%.6f %.6f %.6f", v_x, v_y, v_z), fl, brk, stitch,
	               sprintf("%.6f %.6f %.6f %.6f", aux_x, aux_y, aux_z, pitch));
};

#include "cl_trailreplay.qc"

void(vector o, vector v, float fl, float t, float brk, float stitch, vector aux) Trail_Record =
{
	if (tr_raw < 1)
		return;
	if (buf_getsize(tr_raw) >= LN_CAP * 4)
		return;
	if (tr_erefok)
		bufstr_set(tr_raw, buf_getsize(tr_raw),
		           strcat(Trail_RawSample(o, v, fl, t, brk, stitch, aux, input_angles_x),
		                  sprintf(" %.4f", tr_eref)));
	else
		bufstr_set(tr_raw, buf_getsize(tr_raw), Trail_RawSample(o, v, fl, t, brk, stitch, aux, input_angles_x));
};

// Raw clocks are six-decimal text. Compare cutoffs in that same representation.
float(float t) Trail_RawClock =
{
	return stof(sprintf("%.6f", t));
};

// Last sample at/before t on the nondecreasing clock, including duplicates.
float(float t) Trail_RawIndex =
{
	local float lo, hi, mid;

	if (tr_raw < 1) return -1;
	lo = 0;
	hi = buf_getsize(tr_raw) - 1;
	if (hi < 0) return -1;
	while (lo < hi)
	{
		mid = ceil((lo + hi) * 0.5);
		if (stof(bufstr_get(tr_raw, mid)) <= t) lo = mid;
		else hi = mid - 1;
	}
	return lo;
};

// Authoritative practice-save posture/velocity remains the selected sample.
void(float t) Trail_CursorState =
{
	local float i, n;

	tr_cur_flags = 0;
	tr_cur_ang = '0 0 0';
	i = Trail_RawIndex(t);
	if (i < 0) return;
	n = tokenize(bufstr_get(tr_raw, i));
	if (n != 14 && n != 15) return;
	tr_cur_flags = stof(argv(7));
	tr_cur_ang = [stof(argv(13)), stof(argv(10)), 0];
	tr_cur_vel = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
};

float tr_vis_ok, tr_vis_flags, tr_vis_eref, tr_vis_erefok;
vector tr_vis_vel, tr_vis_ang;
// Visual interpolation has separate outputs; never used to serialize a save.
void(float t) Trail_VisualState =
{
	local float i, t0, t1, f, n;
	local vector vel0, ang0;

	tr_vis_ok = FALSE;
	tr_vis_flags = 0;
	tr_vis_erefok = FALSE;
	tr_vis_vel = tr_vis_ang = '0 0 0';
	i = Trail_RawIndex(t);
	if (i < 0) return;
	n = tokenize(bufstr_get(tr_raw, i));
	if (n != 14 && n != 15) return;
	tr_vis_ok = TRUE;
	// P1007: the zero is a step (a jump or an anchor moves it), so the sample's own.
	if (n == 15)
	{
		tr_vis_eref = stof(argv(14));
		tr_vis_erefok = TRUE;
	}
	tr_vis_flags = stof(argv(7));
	tr_vis_ang = [stof(argv(13)), stof(argv(10)), 0];
	tr_vis_vel = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
	t0 = stof(argv(0));
	vel0 = tr_vis_vel;
	ang0 = tr_vis_ang;
	if (i + 1 >= buf_getsize(tr_raw)) return;
	n = tokenize(bufstr_get(tr_raw, i + 1));
	if (n != 14 && n != 15) return;
	t1 = stof(argv(0));
	// Trails store breaks/stitches separately from legacy recording flags.
	if (t1 <= t0 || (stof(argv(7)) & 0x4000000) || stof(argv(8)) || stof(argv(9))) return;
	f = bound(0, (t - t0) / (t1 - t0), 1);
	tr_vis_vel = vel0 + ([stof(argv(4)), stof(argv(5)), stof(argv(6))] - vel0) * f;
	tr_vis_ang = Interp_View(ang0, [stof(argv(13)), stof(argv(10)), 0], f);
};

void(float t) Trail_Trim =
{
	local float i, n, tmp;
	local string s;
	n = (tr_raw >= 1) ? buf_getsize(tr_raw) : 0;
	tmp = buf_create_ex("string", 0);
	if (tmp < 1)
		return;
	Line_Begin(tr_live);
	Line_Tick(tr_live, tr_tick);
	tr_stagefrom = 0;               // P1006: a rebuilt line is shown whole until its next stage
	tr_contbrk = FALSE;
	t = Trail_RawClock(t);
	for (i = 0; i < n; i = i + 1)
	{
		s = bufstr_get(tr_raw, i);
		if (stof(s) > t)
			break;
		bufstr_set(tmp, i, s);
	}
	// Do not retain a future branch in either the points OR the raw history.
	if (tr_raw >= 1)
		buf_del(tr_raw);
	tr_raw = tmp;
	Trail_CatchStart();             // P1384
	tr_since = 0;
	tr_builds = tr_builds + 1;
	tr_settle = cltime + TR_SETTLE;
	tr_stitch = TRUE;
};

// P1087: what a TAS go (back, edit, undo) cut off at t, kept as the comparison line; the
// sample at/before t starts it so it joins the kept prefix. Nothing past t: the old one stays.
float tr_tasref;
float tr_tasload_at;            // cltime this client sent `tas project load` (cl_tastimeline.qc)
float(float st) Trail_TASGo =
{
	return (getstatf(STAT_FS_TASPAUSE) == 1 && st == TS_RUNNING && cltime - tr_tasload_at > 3);
};
void() Trail_TASDrop =
{
	if (tr_tasref) Line_Clear(LN_S_TASREF);
	tr_tasref = FALSE;
};
void(float t) Trail_TASKeep =
{
	local float i, n, a;
	n = (tr_raw >= 1) ? buf_getsize(tr_raw) : 0;
	a = Trail_RawIndex(Trail_RawClock(t));
	if (a < 0 || a + 1 >= n)
		return;
	ln_want = min(n - a, LN_CAP2);  // the arena grew by LN_CAP2 for it; longer is halved
	Line_Begin(LN_S_TASREF);
	Line_Tick(LN_S_TASREF, tr_tick);
	for (i = a; i < n; i = i + 1)
	{
		if (tokenize(bufstr_get(tr_raw, i)) < 14)
			continue;
		Line_Point(LN_S_TASREF, [stof(argv(1)), stof(argv(2)), stof(argv(3))],
			[stof(argv(4)), stof(argv(5)), stof(argv(6))], stof(argv(7)), stof(argv(0)),
			stof(argv(8)), stof(argv(9)), [stof(argv(10)), stof(argv(11)), stof(argv(12))]);
	}
	Line_End(LN_S_TASREF);
	tr_tasref = (ln_n[LN_S_TASREF] >= 2);
};

string(float id) Trail_SavePath =
{
	local string p;
	p = Rec_SavePath(id);
	return strcat(substring(p, 0, strlen(p) - 8), "trail.txt");
};

void(float id, float ticks) Trail_Save =
{
	local float f, i, n, t, raw, tick, timed, observed;
	local string s;
	raw = (tr_rep_raw >= 1) ? tr_rep_raw : tr_raw;
	tick = (tr_rep_raw >= 1) ? tr_rep_tick : tr_tick;
	if (raw < 1 || tick <= 0)
	{
		observed = (tr_req_wait > 0 && getstatf(STAT_FS_SLSAVEACK) == tr_req_wait &&
		            FS_SlopOp(getstatf(STAT_FS_SLSAVEOP)) == SLOP_SAVED &&
		            FS_SlopId(getstatf(STAT_FS_SLSAVEOP)) == id);
		if (!observed)
			observed = (tr_saveack > 0 && getstatf(STAT_FS_SLTRAILTAG) == tr_saveack);
		if (observed)
		{
			fremove(Trail_SavePath(id)); // invalidate only an observed new save
			SaveLead_Forget();
		}
		Trail_ReplayClear();
		return;
	}
	f = fopen(Trail_SavePath(id), FILE_WRITE);
	if (f < 0)
		return;
	timed = (ticks >= 0);           // the saved result, not a later load's live state
	fputs(f, sprintf("FTESURF-TRAIL 1 %.9g %g %g\n", tick, ticks, timed));
	n = buf_getsize(raw);
	t = timed ? ticks * tick : 99999999;
	t = Trail_RawClock(t);
	for (i = 0; i < n; i = i + 1)
	{
		s = bufstr_get(raw, i);
		if (stof(s) > t)
			break;
		fputs(f, strcat(s, "\n"));
	}
	fclose(f);
	SaveLead_Remember(id, ticks, raw, i - 1);  // P1384
	Trail_ReplayClear();
};

float(float id, float ticks) Trail_Load =
{
	local float f, tick, saved, i, argc, timed, endt;
	local string s;
	f = fopen(Trail_SavePath(id), FILE_READ);
	if (f < 0)
		return FALSE;
	s = fgets(f);
	argc = tokenize(s);
	tick = stof(argv(2));
	saved = stof(argv(3));
	timed = (argc >= 5) ? stof(argv(4)) : (saved > 0);
	if (strcmp(argv(0), "FTESURF-TRAIL") || stof(argv(1)) != 1 || tick <= 0 || saved != ticks)
	{
		fclose(f);
		return FALSE;
	}
	Trail_RawClear();
	tr_tick = tick;
	Line_Begin(tr_live);
	Line_Tick(tr_live, tick);
	tr_stagefrom = 0;               // P1006
	tr_contbrk = FALSE;
	endt = timed ? ticks * tick : 99999999;
	endt = Trail_RawClock(endt);
	for (i = 0; i < LN_CAP * 4; i = i + 1)
	{
		s = fgets(f);
		if (!strcmp(s, ""))
			break;
		if (!i)
		{
			argc = tokenize(s);
			if (argc != 14 && argc != 15)
				break;              // not a picture row: an empty picture, as before
		}
		if (stof(s) > endt)
			break;
		bufstr_set(tr_raw, i, s);
	}
	fclose(f);
	Trail_CatchStart();             // P1384: the line takes these rows over the next frames
	tr_since = 0;
	tr_builds = tr_builds + 1;
	tr_settle = cltime + TR_SETTLE;
	tr_stitch = TRUE;
	return tr_nsamp > 0;
};

#include "cl_trailrequest.qc"
