/*
  RAMP CONTACT INFERRED FROM A RECORDING'S OWN SAMPLES.

  An imported Momentum run records none (tools/momreimport.py: "Never 16"), so
  its line had no ramp marks and its segment column no ramp rows.  Free flight
  moves vz by one exact step a tick and a ramp pushes up; the step is read off
  the file, never assumed.  tools/rampinfer.py is the same rule in Python: its
  header has why each term is there and what the rule cannot see (a lift, a
  gravity zone, a ladder, a face pointing down, the plane), its --score and
  --twin measure it against bit 16, and cfg/test/runlines_infer.cfg grades this
  file against it.

  TWO READERS, ONE SPELLING.  0 is the open replay (Watch_InferScan: a bit per
  buffer line), 1 the board-line job (a first pass for the step, then bits as it
  streams).  Both walk the whole file in order through Infer_Step, so a board
  line and the replay of one file mark the same ticks.
*/
#define INF_EPS      0.045      // between the 0.04 and 0.05 a %.2f column can give
#define INF_FLAT     2.5        // steps: a push over this with no sideways change
#define INF_FLATH    0.5        // (u/s) is a floor touched for a tick, not a ramp
#define INF_MINAIR   30
#define INF_MINSHARE 0.10       // 5,258 imports: the lowest is 0.279
#define INF_HMAX     4000       // falls to 40.00 a tick
// A replay opens in ONE QC call and the engine ends a call at 100,000,000
// branches, calls and returns: the longest import (238,434 samples) opened at
// 76% of that before this file.  Over the cap neither reader infers, and says so.
#define INF_SCANMAX  200000

// Where a line's ramp contact came from.  Above INF_INFERRED: unavailable, why.
#define INF_MEASURED 0          // the file's own flags bit 16
#define INF_INFERRED 1
#define INF_NOVEL    2          // an import with no `momdemo`: no per-tick velocity, no ground flag
#define INF_FEWAIR   3          // under INF_MINAIR judgeable pairs
#define INF_NOSTEP   4          // no fall common enough
#define INF_NOBIT    5          // a native file older than the bit (under v4)
#define INF_LONG     6          // over INF_SCANMAX samples

float  *inf_h;                  // per reader, pairs falling by each 0.01
float  inf_seen[2];             // samples walked since Infer_Open
float  inf_air[2];              // judgeable pairs
float  inf_step[2];             // the fall a tick; 0 = not inferring
float  inf_share[2];
float  inf_why[2];
float  inf_n[2];                // contact ticks inferred
vector inf_po[2], inf_pv[2];    // the sample before
float  inf_pfl[2], inf_pt[2], inf_have[2];
float  inf_dvz, inf_dvh;        // Infer_Step's other answers: the change in vz, and sideways

string(float why) Infer_Name =
{
	if (why == INF_MEASURED) return "measured";
	if (why == INF_INFERRED) return "inferred";
	if (why == INF_NOVEL)    return "unavailable: no per-tick data";
	if (why == INF_FEWAIR)   return "unavailable: too little air";
	if (why == INF_NOSTEP)   return "unavailable: no steady fall";
	if (why == INF_LONG)     return "unavailable: too long a run";
	return "not recorded";
};

// A new file for reader r, and what its header allows.
void(float r, float why) Infer_Open =
{
	local float i, b;

	inf_air[r] = inf_step[r] = inf_share[r] = inf_n[r] = inf_seen[r] = 0;
	inf_why[r] = why;
	inf_have[r] = FALSE;
	if (why != INF_INFERRED)
		return;
	if (!inf_h)
		inf_h = memalloc(sizeof(float) * 2 * (INF_HMAX + 1));
	b = r * (INF_HMAX + 1);
	for (i = 0; i <= INF_HMAX; i = i + 1)
		inf_h[b + i] = 0;
};

// One sample, in file order.  TRUE: it and the one before are one mover tick
// apart, neither on ground and not a teleport; inf_dvz and inf_dvh are set.
float(float r, vector o, vector v, float fl, float t, float tick) Infer_Step =
{
	local float ok, dt;
	local vector pv;

	ok = FALSE;
	inf_seen[r] = inf_seen[r] + 1;
	if (inf_have[r])
	{
		pv = inf_pv[r];
		dt = t - inf_pt[r];
		if (dt > tick * 0.5 && dt < tick * 1.5)
		if (!((fl | inf_pfl[r]) & WT_F_ONGROUND))
		if (Interp_Fit(inf_po[r], pv, o, v, dt) != INTERP_SNAP)
		{
			inf_dvz = v_z - pv_z;
			inf_dvh = vlen([v_x - pv_x, v_y - pv_y, 0]);
			ok = TRUE;
		}
	}
	inf_po[r]   = o;
	inf_pv[r]   = v;
	inf_pfl[r]  = fl;
	inf_pt[r]   = t;
	inf_have[r] = TRUE;
	return ok;
};

// Pass one: count the pair Infer_Step just passed.
void(float r) Infer_Count =
{
	local float j;

	inf_air[r] = inf_air[r] + 1;
	j = floor(0.5 - inf_dvz * 100);
	if (j >= 1 && j <= INF_HMAX)
		inf_h[r * (INF_HMAX + 1) + j] = inf_h[r * (INF_HMAX + 1) + j] + 1;
};

// Pass one is over: the step (the lowest wins a tie), or why there is none.
// The next Infer_Step has no sample before it.
void(float r) Infer_Close =
{
	local float i, b, top, mode;

	inf_have[r] = FALSE;
	if (inf_why[r] != INF_INFERRED)
		return;
	b = r * (INF_HMAX + 1);
	top = mode = 0;
	for (i = 1; i <= INF_HMAX; i = i + 1)
		if (inf_h[b + i] > top)
		{
			top  = inf_h[b + i];
			mode = i;
		}
	inf_share[r] = (inf_air[r] > 0) ? top / inf_air[r] : 0;
	if (inf_seen[r] > INF_SCANMAX)
		inf_why[r] = INF_LONG;
	else if (inf_air[r] < INF_MINAIR)
		inf_why[r] = INF_FEWAIR;
	else if (inf_share[r] < INF_MINSHARE)
		inf_why[r] = INF_NOSTEP;
	else
		inf_step[r] = mode / 100;
};

// Pass two: is the pair Infer_Step just passed a contact?
float(float r) Infer_Bit =
{
	local float push;

	if (inf_step[r] <= 0)
		return FALSE;
	push = inf_dvz + inf_step[r];
	if (push <= INF_EPS)
		return FALSE;
	if (push > INF_FLAT * inf_step[r] && inf_dvh < INF_FLATH)
		return FALSE;
	inf_n[r] = inf_n[r] + 1;
	return TRUE;
};
