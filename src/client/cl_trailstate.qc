/* Patch 502: a visual prefix beside each save's .view. This is not evidence.
   Raw samples retain contact/stitch marks when a branch is rebuilt; copying
   only the decimated positions would keep abandoned glyphs and lose colours. */
float tr_raw, tr_stitch, tr_slseq, tr_cur_flags;
vector tr_cur_ang, tr_cur_vel;
float tr_rep_raw, tr_rep_tick, tr_rep_end, tr_rep_ack, tr_rep_go, tr_saveack;
float tr_req_wait;
float tr_timedgo_ack, tr_go_visual_t, tr_rep_tracewant, tr_rep_tracegot, tr_ticket;
float tr_practice, tr_practicebase, tr_practiceat;

void() Trail_RawClear =
{
	if (tr_raw >= 1)
		buf_del(tr_raw);
	tr_raw = buf_create_ex("string", 0);
	tr_stitch = tr_practice = FALSE;
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
	bufstr_set(tr_raw, buf_getsize(tr_raw), Trail_RawSample(o, v, fl, t, brk, stitch, aux, input_angles_x));
};

// One raw sample into the line and its live predecessor state.
float(string s, float endt) Trail_Refeed =
{
	local float t, fl, brk, stitch;
	local vector o, v, aux;
	if (tokenize(s) != 14)
		return FALSE;
	t = stof(argv(0));
	if (t > endt)
		return FALSE;
	o = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
	v = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
	fl = stof(argv(7));
	brk = stof(argv(8));
	stitch = stof(argv(9));
	aux = [stof(argv(10)), stof(argv(11)), stof(argv(12))];
	Line_Point(tr_live, o, v, fl, t, brk, stitch, aux);
	tr_lastt = t;
	tr_lastp = o;
	tr_nsamp = tr_nsamp + 1;
	return TRUE;
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
	local float i;

	tr_cur_flags = 0;
	tr_cur_ang = '0 0 0';
	i = Trail_RawIndex(t);
	if (i < 0) return;
	if (tokenize(bufstr_get(tr_raw, i)) != 14) return;
	tr_cur_flags = stof(argv(7));
	tr_cur_ang = [stof(argv(13)), stof(argv(10)), 0];
	tr_cur_vel = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
};

float tr_vis_ok, tr_vis_flags;
vector tr_vis_vel, tr_vis_ang;
// Visual interpolation has separate outputs; never used to serialize a save.
void(float t) Trail_VisualState =
{
	local float i, t0, t1, f;
	local vector vel0, ang0;

	tr_vis_ok = FALSE;
	tr_vis_flags = 0;
	tr_vis_vel = tr_vis_ang = '0 0 0';
	i = Trail_RawIndex(t);
	if (i < 0) return;
	if (tokenize(bufstr_get(tr_raw, i)) != 14) return;
	tr_vis_ok = TRUE;
	tr_vis_flags = stof(argv(7));
	tr_vis_ang = [stof(argv(13)), stof(argv(10)), 0];
	tr_vis_vel = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
	t0 = stof(argv(0));
	vel0 = tr_vis_vel;
	ang0 = tr_vis_ang;
	if (i + 1 >= buf_getsize(tr_raw)) return;
	if (tokenize(bufstr_get(tr_raw, i + 1)) != 14) return;
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
	tr_nsamp = 0;
	tr_lastt = 0;
	for (i = 0; i < n; i = i + 1)
	{
		s = bufstr_get(tr_raw, i);
		if (!Trail_Refeed(s, t))
			break;
		bufstr_set(tmp, i, s);
	}
	// Do not retain a future branch in either the points OR the raw history.
	if (tr_raw >= 1)
		buf_del(tr_raw);
	tr_raw = tmp;
	Line_End(tr_live);
	tr_since = 0;
	tr_builds = tr_builds + 1;
	tr_settle = cltime + TR_SETTLE;
	tr_stitch = TRUE;
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
			fremove(Trail_SavePath(id)); // invalidate only an observed new save
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
	for (i = 0; i < n; i = i + 1)
	{
		s = bufstr_get(raw, i);
		if (stof(s) > t)
			break;
		fputs(f, strcat(s, "\n"));
	}
	fclose(f);
	Trail_ReplayClear();
};

float(float id, float ticks) Trail_Load =
{
	local float f, tick, saved, i, argc, timed;
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
	tr_nsamp = 0;
	tr_lastt = 0;
	for (i = 0; i < LN_CAP * 4; i = i + 1)
	{
		s = fgets(f);
		if (!strcmp(s, ""))
			break;
		if (!Trail_Refeed(s, timed ? ticks * tick : 99999999))
			break;
		bufstr_set(tr_raw, i, s);
	}
	fclose(f);
	Line_End(tr_live);
	tr_since = 0;
	tr_builds = tr_builds + 1;
	tr_settle = cltime + TR_SETTLE;
	tr_stitch = TRUE;
	return tr_nsamp > 0;
};

#include "cl_trailrequest.qc"
