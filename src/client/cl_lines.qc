/*
===========================================================================
  cl_lines.qc -- run lines.  Patch 432.

  Recorded paths drawn as screen-space strips, one point per recorded sample.
  The strip is 1 px (hud_watch_path_px) and anti-aliased by vertex alpha: a
  w px line box-filtered onto pixels is a trapezoid, full across w - 1 px and
  falling to 0 over a pixel each side (a 1 px line: a 2 px tent), so each
  segment is a fan whose outer vertices carry alpha 0.  Joints share mitred
  vertices, so a bend neither overlaps nor gaps.  Colour is speed, red (slow)
  through yellow to green (fast) over the shown lines' own range, or gain/loss
  (hud_watch_path_color 1).  A teleport is a break: a square at each end and a
  faint dashed line between.  A segment longer than LN_SUBPX on screen is
  subdivided along a Catmull-Rom through its neighbours.

  Slot 0 is the replay (Watch_ScanRange builds it); 1..8 are board lines.
  Drawn after renderscene, so a line shows through walls.  Points are culled
  by 32-point chunk against the view frustum, and a chunk draws every 2^L-th
  point for the largest L whose error (measured at load, Line_End) is under
  LN_PXERR on screen at its distance.  1 us of QC a drawn point (p432bench), a
  quarter of it the polygons; so past hud_watch_path_far a line fades out and
  is not walked at all (16-chunk groups are culled first).
===========================================================================
*/

#define LN_SLOTS   9
#define LN_CAP     65536        // samples a slot holds (16 min at 66 Hz); past it, halved
#define LN_CHUNK   32
#define LN_GROUP   16           // chunks a group sphere covers
#define LN_BKCAP   512          // teleports marked per slot
#define LN_NEAR    8            // near clip, units (project() divides by w unguarded)
#define LN_GUARD   8192         // virtual px: a vertex past this is a near-plane stub
#define LN_LEVELS  5            // strides 2..32 (LN_CHUNK)
#define LN_PXERR   1.0          // physical px a stride may be off the samples
#define LN_SUBPX   16           // virtual px: a longer segment is subdivided

vector *ln_pos;
float  *ln_spd;
float  *ln_t;
float  *ln_brk;                 // 1: no segment from the previous point (a teleport)
float  *ln_gain;
vector *ln_col;                 // the colour, redone when the range or mode moves
float  *ln_cerr;                // per chunk and level 1..LN_LEVELS: the error, units
vector *ln_cc;                  // per chunk: centre, radius, holds a break
float  *ln_cr;
float  *ln_cbk;
vector *ln_gc;                  // per group of LN_GROUP chunks: centre, radius
float  *ln_gr;
float  *ln_bk;                  // break indices, LN_BKCAP a slot

float  ln_n[LN_SLOTS];
float  ln_bkn[LN_SLOTS];
float  ln_step[LN_SLOTS];       // build decimation: keep every step-th sample
float  ln_skip[LN_SLOTS];
float  ln_pbrk[LN_SLOTS];       // a break carried from a dropped sample
float  ln_on[LN_SLOTS];
float  ln_ia[LN_SLOTS], ln_ib[LN_SLOTS];     // the shown index range
float  ln_lo[LN_SLOTS], ln_hi[LN_SLOTS];     // its speed range

// per frame
vector ln_eye, ln_fwd, ln_rt, ln_up;
float  ln_tx, ln_ty, ln_kx, ln_ky;           // tan(fov/2), and the sphere slack
float  ln_tolk;                  // units of error a unit of distance allows
float  ln_far, ln_fadek;          // hud_watch_path_far, and 1 / its fade's length
float  ln_cfade;                 // the last sphere tested reaches into the fade
float  ln_px;                   // one physical pixel, virtual units
float  ln_hw, ln_cw, ln_pk;     // outer / full-alpha half widths, peak alpha
float  ln_slo, ln_shi, ln_sinv, ln_cmode;
float  ln_gen, ln_cgen;          // lines built, and as of the last recolour
float  ln_cslo, ln_cshi, ln_ccmode;
float  ln_nseg, ln_nclip, ln_nwild, ln_npt;  // the last Line_Draw, for status
vector ln_bbmin, ln_bbmax, ln_first;
float  ln_frames;               // Watch_Path2D calls, to divide profile_csqc by

// the strip being streamed: the last two screen points, the pending side
float  ln_rn;
vector ln_rq0, ln_rs0, ln_rc0;
float  ln_ra0;
vector ln_rq1, ln_rc1, ln_rn1;
float  ln_ra1;

// the world point before, for the near clip and the subdivision
float  ln_hp, ln_pi, ln_pd, ln_pa;
vector ln_pp, ln_pc;
float  ln_db, ln_dn, ln_da;     // the slot being drawn: base, points, alpha

void() Line_Alloc =
{
	if (ln_pos)
		return;
	ln_pos  = memalloc(sizeof(vector) * LN_SLOTS * LN_CAP);
	ln_spd  = memalloc(sizeof(float) * LN_SLOTS * LN_CAP);
	ln_t    = memalloc(sizeof(float) * LN_SLOTS * LN_CAP);
	ln_brk  = memalloc(sizeof(float) * LN_SLOTS * LN_CAP);
	ln_gain = memalloc(sizeof(float) * LN_SLOTS * LN_CAP);
	ln_col  = memalloc(sizeof(vector) * LN_SLOTS * LN_CAP);
	ln_cerr = memalloc(sizeof(float) * LN_SLOTS * LN_CAP / LN_CHUNK * LN_LEVELS);
	ln_cc   = memalloc(sizeof(vector) * LN_SLOTS * LN_CAP / LN_CHUNK);
	ln_cr   = memalloc(sizeof(float) * LN_SLOTS * LN_CAP / LN_CHUNK);
	ln_cbk  = memalloc(sizeof(float) * LN_SLOTS * LN_CAP / LN_CHUNK);
	ln_gc   = memalloc(sizeof(vector) * LN_SLOTS * LN_CAP / LN_CHUNK / LN_GROUP);
	ln_gr   = memalloc(sizeof(float) * LN_SLOTS * LN_CAP / LN_CHUNK / LN_GROUP);
	ln_bk   = memalloc(sizeof(float) * LN_SLOTS * LN_BKCAP);
};

void(float s) Line_Clear =
{
	ln_on[s] = FALSE;
	ln_n[s]  = 0;
	ln_bkn[s] = 0;
	ln_ia[s] = ln_ib[s] = 0;
};

void(float s) Line_Begin =
{
	Line_Alloc();
	Line_Clear(s);
	ln_step[s] = 1;
	ln_skip[s] = 0;
	ln_pbrk[s] = FALSE;
};

// One sample.  brk: the segment from the previous sample is a teleport.
void(float s, vector o, float spd, float t, float brk) Line_Add =
{
	local float b, n, i, j;

	if (brk)
		ln_pbrk[s] = TRUE;
	if (ln_skip[s] > 0)
	{
		ln_skip[s] = ln_skip[s] - 1;
		return;
	}
	b = s * LN_CAP;
	n = ln_n[s];
	if (n >= LN_CAP)
	{
		// Past the cap: keep the even points, a dropped one's break on the next.
		for (i = 0; i < LN_CAP / 2; i = i + 1)
		{
			j = b + 2 * i;
			ln_pos[b + i] = ln_pos[j];
			ln_spd[b + i] = ln_spd[j];
			ln_t[b + i]   = ln_t[j];
			ln_brk[b + i] = ln_brk[j];
			if (i > 0)
			if (ln_brk[j - 1])
				ln_brk[b + i] = TRUE;
		}
		if (ln_brk[b + LN_CAP - 1])
			ln_pbrk[s] = TRUE;
		n = LN_CAP / 2;
		ln_step[s] = ln_step[s] * 2;
	}
	ln_skip[s] = ln_step[s] - 1;
	ln_pos[b + n] = o;
	ln_spd[b + n] = spd;
	ln_t[b + n]   = t;
	ln_brk[b + n] = (n > 0 && ln_pbrk[s]);
	ln_pbrk[s] = FALSE;
	ln_n[s] = n + 1;
};

// The tables drawing needs: chunk spheres, the break list, the gain.
void(float s) Line_End =
{
	local float b, n, c, i, i0, i1, j0, j1, k, dt;
	local vector mn, mx, p;

	b = s * LN_CAP;
	n = ln_n[s];
	ln_bkn[s] = 0;
	for (i = 1; i < n; i = i + 1)
		if (ln_brk[b + i])
		if (ln_bkn[s] < LN_BKCAP)
		{
			ln_bk[s * LN_BKCAP + ln_bkn[s]] = i;
			ln_bkn[s] = ln_bkn[s] + 1;
		}

	// Each chunk's box takes the point before it, so the joining segment is in.
	for (c = 0; c * LN_CHUNK < n; c = c + 1)
	{
		i0 = max(0, c * LN_CHUNK - 1);
		i1 = min(n, (c + 1) * LN_CHUNK);
		mn = mx = ln_pos[b + i0];
		k = FALSE;
		for (i = i0; i < i1; i = i + 1)
		{
			p = ln_pos[b + i];
			if (p_x < mn_x) mn_x = p_x;  if (p_x > mx_x) mx_x = p_x;
			if (p_y < mn_y) mn_y = p_y;  if (p_y > mx_y) mx_y = p_y;
			if (p_z < mn_z) mn_z = p_z;  if (p_z > mx_z) mx_z = p_z;
			if (ln_brk[b + i])
				k = TRUE;
		}
		ln_cc[s * LN_CAP / LN_CHUNK + c]  = (mn + mx) * 0.5;
		ln_cr[s * LN_CAP / LN_CHUNK + c]  = vlen(mx - mn) * 0.5;
		ln_cbk[s * LN_CAP / LN_CHUNK + c] = k;
	}
	for (c = 0; c * LN_CHUNK * LN_GROUP < n; c = c + 1)
	{
		i0 = max(0, c * LN_CHUNK * LN_GROUP - 1);
		i1 = min(n, (c + 1) * LN_CHUNK * LN_GROUP);
		mn = mx = ln_pos[b + i0];
		for (i = i0; i < i1; i = i + 1)
		{
			p = ln_pos[b + i];
			if (p_x < mn_x) mn_x = p_x;  if (p_x > mx_x) mx_x = p_x;
			if (p_y < mn_y) mn_y = p_y;  if (p_y > mx_y) mx_y = p_y;
			if (p_z < mn_z) mn_z = p_z;  if (p_z > mx_z) mx_z = p_z;
		}
		ln_gc[s * LN_CAP / LN_CHUNK / LN_GROUP + c] = (mn + mx) * 0.5;
		ln_gr[s * LN_CAP / LN_CHUNK / LN_GROUP + c] = vlen(mx - mn) * 0.5;
	}

	// Gain, u/s per s, over up to two samples each side within the same piece.
	for (i = 0; i < n; i = i + 1)
	{
		j0 = i;
		j1 = i;
		for (k = 0; k < 2; k = k + 1)
		{
			if (j0 > 0)
			if (!ln_brk[b + j0])
				j0 = j0 - 1;
			if (j1 + 1 < n)
			if (!ln_brk[b + j1 + 1])
				j1 = j1 + 1;
		}
		dt = ln_t[b + j1] - ln_t[b + j0];
		ln_gain[b + i] = (dt > 0) ? (ln_spd[b + j1] - ln_spd[b + j0]) / dt : 0;
	}

	/*
	  The stride errors: for each chunk and level L, the furthest any sample lies
	  from the polyline through every 2^L-th point (the chunk's first and last
	  kept), in units.  A chunk holding a break never strides.
	*/
	for (c = 0; c * LN_CHUNK < n; c = c + 1)
	{
		i0 = c * LN_CHUNK;
		i1 = min(n, i0 + LN_CHUNK) - 1;
		k = (s * LN_CAP / LN_CHUNK + c) * LN_LEVELS;
		for (j0 = 1; j0 <= LN_LEVELS; j0 = j0 + 1)
		{
			dt = 0;
			if (ln_cbk[s * LN_CAP / LN_CHUNK + c])
				dt = 99999;
			else
			{
				j1 = pow(2, j0);
				for (i = i0 + 1; i < i1; i = i + 1)
				{
					mn = ln_pos[b + i0 + floor((i - i0) / j1) * j1];
					mx = ln_pos[b + min(i0 + (floor((i - i0) / j1) + 1) * j1, i1)] - mn;
					p  = ln_pos[b + i] - mn;
					dt = max(dt, vlen(p - mx * bound(0, (mx * mx > 0) ? (p * mx) / (mx * mx) : 0, 1)));
				}
			}
			ln_cerr[k + j0 - 1] = dt;
		}
	}

	ln_ia[s] = 0;
	ln_ib[s] = n - 1;
	ln_on[s] = (n >= 2);
	ln_gen = ln_gen + 1;
};

// The first point at or after t (binary search on the run clock).
float(float s, float t) Line_Find =
{
	local float b, lo, hi, m;

	b = s * LN_CAP;
	lo = 0;
	hi = ln_n[s];
	while (lo < hi)
	{
		m = floor((lo + hi) * 0.5);
		if (ln_t[b + m] < t)
			lo = m + 1;
		else
			hi = m;
	}
	return lo;
};

/*
  Show [ta, tb] of slot s.  The colour range is its speeds at or after tsc, mean
  +- 2 sd inside min..max: a stop after a teleport or a restart put min at 0 and
  drew a whole stage one green (p432shot).
*/
void(float s, float ta, float tb, float tsc) Line_Range =
{
	local float b, i, v, n, sum, sq, mn, mx, sd;

	b = s * LN_CAP;
	ln_ia[s] = Line_Find(s, ta);
	ln_ib[s] = Line_Find(s, tb + 0.0001) - 1;
	n = sum = sq = 0;
	mn = 99999;
	mx = 0;
	for (i = ln_ia[s]; i <= ln_ib[s]; i = i + 1)
	{
		if (ln_t[b + i] < tsc)
			continue;
		v = ln_spd[b + i];
		mn = min(mn, v);
		mx = max(mx, v);
		sum = sum + v;
		sq = sq + v * v;
		n = n + 1;
	}
	ln_lo[s] = 0;
	ln_hi[s] = 1;
	if (n > 0)
	{
		v = sum / n;
		sd = sqrt(max(0, sq / n - v * v));
		ln_lo[s] = max(mn, v - 2 * sd);
		ln_hi[s] = min(mx, v + 2 * sd);
		if (ln_hi[s] <= ln_lo[s])
			ln_hi[s] = ln_lo[s] + 1;
	}
};

// ---- the anti-aliased strip ---------------------------------------------------

// Width w in physical px; sets the half widths the emitters use.
void(float w) Line_Width =
{
	if (w <= 0)
		w = 1;
	ln_pk = min(1, w);
	ln_hw = (max(w, 1) * 0.5 + 0.5) * ln_px;
	ln_cw = (max(w, 1) * 0.5 - 0.5) * ln_px;
};

void() Line_PxFrame =
{
	local vector ps, vs;

	ps = getproperty(VF_SCREENPSIZE);
	vs = getproperty(VF_SCREENVSIZE);
	ln_px = 1;
	if (ps_x > 0)
		ln_px = vs_x / ps_x;
};

// One segment a->b, sides sa/sb (unit, times the mitre factor).  Fans whose
// outer vertices carry alpha 0: a tent at 1 px, a trapezoid (two fans) wider.
void(vector a, vector sa, vector ca, float la, vector b, vector sb, vector cb, float lb) Line_Emit =
{
	local vector oa, ob, ia, ib;

	oa = sa * ln_hw;
	ob = sb * ln_hw;
	R_BeginPolygon("", DRAWFLAG_TWOSIDED, TRUE);
	if (ln_cw <= 0)
	{
		R_PolygonVertex(a,      '0 0 0', ca, la * ln_pk);
		R_PolygonVertex(a + oa, '0 0 0', ca, 0);
		R_PolygonVertex(b + ob, '0 0 0', cb, 0);
		R_PolygonVertex(b,      '0 0 0', cb, lb * ln_pk);
		R_PolygonVertex(b - ob, '0 0 0', cb, 0);
		R_PolygonVertex(a - oa, '0 0 0', ca, 0);
		R_EndPolygon();
		return;
	}
	ia = sa * ln_cw;
	ib = sb * ln_cw;
	R_PolygonVertex(a + ia, '0 0 0', ca, la);
	R_PolygonVertex(a + oa, '0 0 0', ca, 0);
	R_PolygonVertex(b + ob, '0 0 0', cb, 0);
	R_PolygonVertex(b + ib, '0 0 0', cb, lb);
	R_PolygonVertex(b - ib, '0 0 0', cb, lb);
	R_PolygonVertex(a - ia, '0 0 0', ca, la);
	R_EndPolygon();
	R_BeginPolygon("", DRAWFLAG_TWOSIDED, TRUE);
	R_PolygonVertex(a - ia, '0 0 0', ca, la);
	R_PolygonVertex(b - ib, '0 0 0', cb, lb);
	R_PolygonVertex(b - ob, '0 0 0', cb, 0);
	R_PolygonVertex(a - oa, '0 0 0', ca, 0);
	R_EndPolygon();
};

// A lone segment in screen units (the mouse pad's trail, a dash): flat ends.
void(vector a, vector b, vector ca, float la, vector cb, float lb) Line_Seg2D =
{
	local vector d;
	local float l;

	d = b - a;
	d_z = 0;
	l = vlen(d);
	if (l < 0.001)
		return;
	d = [d_y, 0 - d_x, 0] * (1 / l);
	Line_Emit(a, d, ca, la, b, d, cb, lb);
};

void() Line_RunEnd =
{
	if (ln_rn >= 2)
	{
		Line_Emit(ln_rq0, ln_rs0, ln_rc0, ln_ra0, ln_rq1, ln_rn1, ln_rc1, ln_ra1);
		ln_nseg = ln_nseg + 1;
	}
	ln_rn = 0;
};

/*
  A screen point onto the strip.  A segment is emitted a point late, when the
  side at its far end (the mitre with the next) is known; a point under a
  quarter pixel from the last is dropped.
*/
void(vector q, vector c, float a) Line_Q =
{
	local vector d, n, m;
	local float l, k;

	ln_npt = ln_npt + 1;
	if (q_x < ln_bbmin_x) ln_bbmin_x = q_x;
	if (q_y < ln_bbmin_y) ln_bbmin_y = q_y;
	if (q_x > ln_bbmax_x) ln_bbmax_x = q_x;
	if (q_y > ln_bbmax_y) ln_bbmax_y = q_y;
	if (ln_rn > 0)
	{
		d = q - ln_rq1;
		l = vlen(d);
		if (l < 0.25 * ln_px)
			return;
		n = [d_y, 0 - d_x, 0] * (1 / l);
		if (ln_rn == 1)
			ln_rs0 = n;
		else
		{
			m = ln_rn1 + n;
			l = vlen(m);
			if (l < 0.1)
				m = n;              // doubled back: no mitre to take
			else
			{
				m = m * (1 / l);
				k = m * n;
				m = m * (1 / ((k > 0.5) ? k : 0.5));
			}
			Line_Emit(ln_rq0, ln_rs0, ln_rc0, ln_ra0, ln_rq1, m, ln_rc1, ln_ra1);
			ln_nseg = ln_nseg + 1;
			ln_rs0 = m;
		}
		ln_rq0 = ln_rq1;
		ln_rc0 = ln_rc1;
		ln_ra0 = ln_ra1;
		ln_rn1 = n;
		ln_rn = 2;
	}
	else
	{
		ln_rn = 1;
		if (ln_nseg == 0)
			ln_first = q;
	}
	ln_rq1 = q;
	ln_rc1 = c;
	ln_ra1 = a;
};

// A projected point's guard: FALSE for a near-plane stub beside the eye (the
// strip is ended there).
float(vector q) Line_Sane =
{
	if (q_z < -1 || q_x > LN_GUARD || q_x < -LN_GUARD || q_y > LN_GUARD || q_y < -LN_GUARD)
	{
		ln_nwild = ln_nwild + 1;
		Line_RunEnd();
		return FALSE;
	}
	return TRUE;
};

// A world point in front of the near plane, onto the strip.
void(vector w, vector c, float a) Line_Pt =
{
	local vector q;

	q = project(w);
	if (!Line_Sane(q))
		return;
	q_z = 0;
	Line_Q(q, c, a);
};

// ---- colour -------------------------------------------------------------------

// Point i's colour: speed red -> yellow -> green over the shown range, or
// gain (u/s per s) grey -> green, loss grey -> red, full at 800.
vector(float i) Line_Col =
{
	local float f;

	if (ln_cmode == 1)
	{
		f = bound(-1, ln_gain[i] / 800, 1);
		if (f >= 0)
			return '0.85 0.85 0.85' + ('-0.55 0.15 -0.45' * f);
		return '0.85 0.85 0.85' + ('0.15 -0.60 -0.60' * (0 - f));
	}
	f = bound(0, (ln_spd[i] - ln_slo) * ln_sinv, 1);
	if (f < 0.5)
		return '1.00 0.22 0.22' + ('0.00 0.68 0.00' * (f * 2));
	return '1.00 0.90 0.22' + ('-0.70 0.10 0.13' * ((f - 0.5) * 2));
};

// ---- per frame ------------------------------------------------------------------

// The view the lines are projected against, and the shared colour range.
void() Line_ViewFrame =
{
	local vector fov;
	local float s, i;

	Line_PxFrame();
	Line_Width(cvar("hud_watch_path_px"));
	ln_eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	ln_fwd = v_forward;
	ln_rt  = v_right;
	ln_up  = v_up;
	fov = getproperty(VF_FOV);
	ln_tx = tan(bound(1, fov_x, 179) * (M_PI / 360));
	ln_ty = tan(bound(1, fov_y, 179) * (M_PI / 360));
	ln_kx = sqrt(1 + ln_tx * ln_tx);
	ln_ky = sqrt(1 + ln_ty * ln_ty);
	fov = getproperty(VF_SCREENPSIZE);
	ln_tolk = LN_PXERR * ln_tx / max(1, fov_x * 0.5);
	ln_far  = cvar("hud_watch_path_far");
	ln_fadek = (ln_far > 0) ? 3 / ln_far : 0;       // fades over its last third
	ln_cmode = cvar("hud_watch_path_color");
	ln_slo = 99999;
	ln_shi = 0;
	for (s = 0; s < LN_SLOTS; s = s + 1)
		if (ln_on[s])
		{
			ln_slo = min(ln_slo, ln_lo[s]);
			ln_shi = max(ln_shi, ln_hi[s]);
		}
	ln_sinv = (ln_shi > ln_slo) ? 1 / (ln_shi - ln_slo) : 0;

	// The colours, once per change of range, mode or line (not per frame).
	if (ln_gen != ln_cgen || ln_slo != ln_cslo || ln_shi != ln_cshi || ln_cmode != ln_ccmode)
	{
		for (s = 0; s < LN_SLOTS; s = s + 1)
			if (ln_on[s])
				for (i = s * LN_CAP; i < s * LN_CAP + ln_n[s]; i = i + 1)
					ln_col[i] = Line_Col(i);
		ln_cgen = ln_gen;
		ln_cslo = ln_slo;
		ln_cshi = ln_shi;
		ln_ccmode = ln_cmode;
	}
};

// A sphere against the view: -1 outside the frustum or past hud_watch_path_far,
// else the distance to its surface (0 inside it).
float(vector cen, float rad) Line_Sphere =
{
	local vector r;
	local float z, x;

	r = cen - ln_eye;
	z = r * ln_fwd;
	if (z < 0 - rad)
		return -1;
	x = r * ln_rt;
	if (x < 0) x = 0 - x;
	if (x - z * ln_tx > rad * ln_kx)
		return -1;
	x = r * ln_up;
	if (x < 0) x = 0 - x;
	if (x - z * ln_ty > rad * ln_ky)
		return -1;
	x = vlen(r);
	ln_cfade = (ln_far > 0 && x + rad > ln_far * 0.66);   // parts of it fade
	x = x - rad;
	if (x < 0)
		return 0;
	if (ln_far > 0)
	if (x > ln_far)
		return -1;
	return x;
};

// Chunk c of slot s: 0 off screen, else the stride (1, 2 .. LN_CHUNK) whose
// error is under LN_PXERR at its distance.
float(float s, float c) Line_ChunkStep =
{
	local float k, tol, l;

	k = s * LN_CAP / LN_CHUNK + c;
	tol = Line_Sphere(ln_cc[k], ln_cr[k]);
	if (tol < 0)
		return 0;
	tol = tol * ln_tolk;
	k = k * LN_LEVELS;
	for (l = LN_LEVELS; l >= 1; l = l - 1)
		if (ln_cerr[k + l - 1] <= tol)
			return pow(2, l);
	return 1;
};

// Point i of slot base b onto the strip: the near clip against the point before,
// the subdivision of a long segment, and the playhead split.
void(float i, float st, float tplay, vector phead, float ahead) Line_Feed =
{
	local vector p, c, x, pm, pn, w, q0, q1;
	local float b, d, a, f, k, j, sub, l;

	b = ln_db;
	p = ln_pos[b + i];
	d = (p - ln_eye) * ln_fwd;
	c = ln_col[b + i];
	a = ((ln_t[b + i] <= tplay) ? 1 : ahead) * ln_da;
	// The fade is by distance, as the cull is (review: by depth it cut hard at
	// the screen's sides); only a chunk reaching into it pays the vlen.
	if (ln_cfade)
		a = a * bound(0, (ln_far - vlen(p - ln_eye)) * ln_fadek, 1);

	if (!ln_hp)
	{
		if (d >= LN_NEAR)
			Line_Pt(p, c, a);
	}
	else if (ln_pd >= LN_NEAR && d >= LN_NEAR)
	{
		// The playhead between the two: the line bright to it, dim after (or
		// ended there, `ahead` 0).
		if (ln_t[b + ln_pi] <= tplay && ln_t[b + i] > tplay)
		{
			f = (tplay - ln_t[b + ln_pi]) / max(0.0001, ln_t[b + i] - ln_t[b + ln_pi]);
			Line_Pt(phead, ln_pc + (c - ln_pc) * f, ln_da);
			if (ahead <= 0)
			{
				Line_RunEnd();
				ln_hp = FALSE;
				return;
			}
			st = 0;                 // no curve back over the playhead (review)
		}

		// A long segment on screen: Catmull-Rom through the neighbours (none across
		// a break), and only at full resolution.
		q1 = project(p);
		if (!Line_Sane(q1))
		{
			ln_hp = TRUE;
			ln_pi = i;
			ln_pp = p;
			ln_pd = d;
			ln_pc = c;
			ln_pa = a;
			return;
		}
		q1_z = 0;
		sub = 1;
		if (st == 1)
		if (ln_rn > 0)
		{
			q0 = ln_rq1;
			l = vlen(q1 - q0);
			if (l > LN_SUBPX)
				sub = min(8, ceil(l / (LN_SUBPX * 0.5)));
		}
		if (sub > 1)
		{
			pm = (ln_pi > 0 && !ln_brk[b + ln_pi]) ? ln_pos[b + ln_pi - 1]
			                                       : 2 * ln_pp - p;
			pn = 2 * p - ln_pp;
			if (i + 1 < ln_dn)
			if (!ln_brk[b + i + 1])
				pn = ln_pos[b + i + 1];
			for (j = 1; j < sub; j = j + 1)
			{
				f = j / sub;
				k = f * f;
				w = 0.5 * ((2 * ln_pp) + (p - pm) * f
				           + (2 * pm - 5 * ln_pp + 4 * p - pn) * k
				           + (3 * ln_pp - pm - 3 * p + pn) * k * f);
				if ((w - ln_eye) * ln_fwd >= LN_NEAR)
					Line_Pt(w, ln_pc + (c - ln_pc) * f, ln_pa + (a - ln_pa) * f);
			}
		}
		Line_Q(q1, c, a);
	}
	else if (ahead <= 0 && ln_t[b + i] > tplay)
	{
		Line_RunEnd();              // ahead 0: nothing past the playhead
		ln_nclip = ln_nclip + 1;
	}
	else if (ln_pd >= LN_NEAR)
	{
		x = ln_pp + (p - ln_pp) * ((ln_pd - LN_NEAR) / (ln_pd - d));
		Line_Pt(x, c, a);
		Line_RunEnd();
		ln_nclip = ln_nclip + 1;
	}
	else if (d >= LN_NEAR)
	{
		x = p + (ln_pp - p) * ((d - LN_NEAR) / (d - ln_pd));
		Line_Pt(x, ln_pc, ln_pa);
		Line_Pt(p, c, a);
		ln_nclip = ln_nclip + 1;
	}
	else
		ln_nclip = ln_nclip + 1;

	ln_hp = TRUE;
	ln_pi = i;
	ln_pp = p;
	ln_pd = d;
	ln_pc = c;
	ln_pa = a;
};

// A dashed line a->b in the world (a teleport's jump), clipped to the near plane.
void(vector a, vector b, vector c, float al) Line_Dash =
{
	local float da, db, l, t, dash, gap;
	local vector qa, qb, u;

	da = (a - ln_eye) * ln_fwd;
	db = (b - ln_eye) * ln_fwd;
	if (da < LN_NEAR && db < LN_NEAR)
		return;
	if (da < LN_NEAR)
		a = a + (b - a) * ((LN_NEAR - da) / (db - da));
	else if (db < LN_NEAR)
		b = b + (a - b) * ((LN_NEAR - db) / (da - db));
	qa = project(a);
	qb = project(b);
	qa_z = qb_z = 0;
	if (fabs(qa_x) > LN_GUARD || fabs(qa_y) > LN_GUARD
	 || fabs(qb_x) > LN_GUARD || fabs(qb_y) > LN_GUARD)
		return;
	u = qb - qa;
	l = vlen(u);
	if (l < 1)
		return;
	u = u * (1 / l);
	dash = 6 * ln_px;
	gap  = 5 * ln_px;
	for (t = 0; t < l && t < 4000 * ln_px; t = t + dash + gap)
		Line_Seg2D(qa + u * t, qa + u * min(l, t + dash), c, al, c, al);
};

// A teleport's end: a small square with a dark edge.
void(vector w, vector c, float al) Line_Square =
{
	local vector q;
	local float h;

	if ((w - ln_eye) * ln_fwd < LN_NEAR)
		return;
	q = project(w);
	if (q_z < -1 || fabs(q_x) > LN_GUARD || fabs(q_y) > LN_GUARD)
		return;
	h = 3 * ln_px;
	q = [floor(q_x / ln_px + 0.5) * ln_px, floor(q_y / ln_px + 0.5) * ln_px, 0];
	drawfill(q - [h + ln_px, h + ln_px], [2 * h + 2 * ln_px, 2 * h + 2 * ln_px],
	         '0 0 0', al * 0.7, 0);
	drawfill(q - [h, h], [2 * h, 2 * h], c, al, 0);
};

/*
  Slot s over its shown range.  tplay: points after it draw at `ahead` (0 stops
  the line at the playhead, which phead marks); a board line passes a tplay past
  its end.  alpha scales the whole line.
*/
void(float s, float tplay, vector phead, float ahead, float alpha) Line_Draw =
{
	local float b, i, ib, c, st, ce, k, j, ia, al, g, ge, d0, d1;
	local vector p0, p1;

	if (!ln_on[s])
		return;
	b  = s * LN_CAP;
	ia = ln_ia[s];
	ib = ln_ib[s];
	if (ib <= ia)
		return;
	if (ahead <= 0)
		ib = min(ib, Line_Find(s, tplay));   // the first point past the playhead
	ln_db = b;
	ln_dn = ln_n[s];
	ln_da = alpha;

	ln_rn = 0;
	ln_hp = FALSE;
	i = ia;
	st = 1;
	c = 0;
	ce = -1;
	ge = -1;
	while (i <= ib)
	{
		// A group of LN_GROUP chunks off screen or past the far distance: skipped whole.
		if (i > ge)
		{
			g  = floor(i / (LN_CHUNK * LN_GROUP));
			ge = min(ib, (g + 1) * LN_CHUNK * LN_GROUP - 1);
			k  = s * LN_CAP / LN_CHUNK / LN_GROUP + g;
			if (Line_Sphere(ln_gc[k], ln_gr[k]) < 0)
			{
				Line_RunEnd();
				ln_hp = FALSE;
				i = ge + 1;
				ce = ge;
				continue;
			}
		}
		if (i > ce)
		{
			c  = floor(i / LN_CHUNK);
			ce = min(ib, (c + 1) * LN_CHUNK - 1);
			st = Line_ChunkStep(s, c);
			if (!st)
			{
				Line_RunEnd();
				ln_hp = FALSE;
				i = ce + 1;
				continue;
			}
			// Entering after a culled chunk: from the point before, unless a break.
			if (!ln_hp)
			if (i > ia)
			if (!ln_brk[b + i])
				Line_Feed(i - 1, st, tplay, phead, ahead);
		}
		if (ln_brk[b + i])
		{
			Line_RunEnd();
			ln_hp = FALSE;
		}
		Line_Feed(i, st, tplay, phead, ahead);
		if (ahead <= 0)
		if (ln_t[b + i] > tplay)
			break;
		// On the chunk's grid of st, and its last point (the error was measured so).
		if (i >= ce)
			i = ce + 1;
		else
			i = min(ce, c * LN_CHUNK + (floor((i - c * LN_CHUNK) / st) + 1) * st);
	}
	Line_RunEnd();

	// The teleports: a square at each end and a faint dashed line between.
	for (k = 0; k < ln_bkn[s]; k = k + 1)
	{
		j = ln_bk[s * LN_BKCAP + k];
		if (j <= ia || j > ib)
			continue;
		if (ahead <= 0)
		if (ln_t[b + j] > tplay)
			continue;
		p0 = ln_pos[b + j - 1];
		p1 = ln_pos[b + j];
		al = ((ln_t[b + j] <= tplay) ? 1 : ahead) * alpha;
		d0 = d1 = al;
		if (ln_fadek > 0)
		{
			d0 = al * bound(0, (ln_far - vlen(p0 - ln_eye)) * ln_fadek, 1);
			d1 = al * bound(0, (ln_far - vlen(p1 - ln_eye)) * ln_fadek, 1);
		}
		if (d0 <= 0 && d1 <= 0)
			continue;
		Line_Dash(p0, p1, '0.85 0.88 0.95', 0.35 * max(d0, d1));
		if (d0 > 0)
			Line_Square(p0, ln_col[b + j - 1], d0);
		if (d1 > 0)
			Line_Square(p1, ln_col[b + j], d1);
	}
};

void() Line_StatsReset =
{
	ln_nseg = ln_nclip = ln_nwild = ln_npt = 0;
	ln_bbmin = '99999 99999 0';
	ln_bbmax = '-99999 -99999 0';
	ln_first = '0 0 0';
};
