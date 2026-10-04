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

// 0 the replay, 1..8 the board's, 9 and 10 the live trail's pair (cl_trail.qc,
// Patch 475 -- two so a finished run can fade while the next one builds over it).
// 3.25 MiB a slot at LN_CAP, counted off Line_Alloc's own arenas.
#define LN_SLOTS   11
#define LN_CAP     65536        // samples a slot holds (16 min at 66 Hz); past it, halved
#define LN_CHUNK   32
#define LN_GROUP   16           // chunks a group sphere covers
#define LN_BKCAP   512          // teleports marked per slot
#define LN_NEAR    8            // near clip, units (project() divides by w unguarded)
#define LN_GUARD   8192         // virtual px: a vertex past this is a near-plane stub
#define LN_LEVELS  5            // strides 2..32 (LN_CHUNK)
#define LN_PXERR   1.0          // physical px a stride may be off the samples
#define LN_SUBPX   16           // virtual px: a longer segment is subdivided

/*
  THE MARKS.  Patch 449.

  Where the run touched down, left the ramp, hopped, and where a segmented run
  was stitched.  They are the EDGES of Board_KindOf (cl_board.qc), the same
  three-state contact function the Segments column is built from, with none of
  that column's row-level debounce -- so every segment row boundary is a mark,
  and a bounce too short to become a row is a mark with no row.  That
  containment is the invariant p449mark grades; a second detector written here
  would drift from the column and the two would disagree about one run.

  A mark carries its own position and velocity rather than a point index, which
  is what makes it survive both decimations (the build-time ln_skip stride and
  the past-the-cap halving) with no index fixup at all.

  MEASURED, AND NOT WORKED AROUND: samples are one per PACKET (43-65/s against
  a nominal 66.67), and a bhop's ground contact is one tick.  A perfect hop's
  contact can fall between two packets and be absent from the file, so the line
  misses those hops -- and so does the Segments column, from the same samples,
  identically.  Do not interpolate hops the file does not contain.
*/
#define LN_EVCAP   4096         // marks a slot holds; past it, peaks go first
#define LN_EVZMIN  40           // u/s of |vz| a peak needs: 2.5 ticks of gravity
#define LN_CELLS   4096         // declutter cells; 64 x 36 at the default gap
#define LN_LABMAX  128          // labels queued for the end of the frame

#define LN_E_LAND    1          // touched ground or ramp
#define LN_E_LEAVE   2          // left it without jumping (a ramp exit, an edge)
#define LN_E_JUMP    3          // left the ground with the jump button down
#define LN_E_APEX    4          // vz turned over
#define LN_E_TROUGH  5          // vz turned back up
#define LN_E_STITCH  6          // a save state was loaded here: resume/retry
#define LN_E_BREAK   7          // a teleport: the marks' own record of a break

/*
  WHY A BREAK IS IN THE MARK TABLE when the teleport pass already draws it.

  It is not drawn from here -- Line_Draw's teleport pass owns the squares and
  the dashes.  It is here because it is the one thing a mark depends on that
  the table did not carry: a break suppresses the contact edge across it, and
  ln_bk cannot say where, because the past-the-cap halving moves a dropped
  sample's break onto the next kept point (up to a sample late, measured on
  bhop_monster_jam save010: 127437 samples, 8 marks out of phase).  So the
  table records the breaks the CLASSIFIER saw, and tools/p449mark.py grades
  against those instead of against a list that has been through decimation.
*/

vector *ln_pos;
float  *ln_spd;
float  *ln_t;
float  *ln_brk;                 // 1: no segment from the previous point (a teleport)
float  *ln_gain;
float  *ln_vz;                  // Patch 452: the third term of the energy
float  *ln_q;                   // Patch 453: air-control grade, -1 = no answer
vector *ln_col;                 // the colour, redone when the range or mode moves
float  *ln_cerr;                // per chunk and level 1..LN_LEVELS: the error, units
vector *ln_cc;                  // per chunk: centre, radius, holds a break
float  *ln_cr;
float  *ln_cbk;
vector *ln_gc;                  // per group of LN_GROUP chunks: centre, radius
float  *ln_gr;
float  *ln_bk;                  // break indices, LN_BKCAP a slot

// The marks: one entry each, position and velocity carried, never an index.
float  *ln_ek;                  // LN_E_*
float  *ln_es;                  // the contact pair it came from, from * 4 + to
float  *ln_et;                  // the run clock it landed on
vector *ln_ep;
float  *ln_evh;                 // horizontal speed there, u/s
float  *ln_e2;                  // v . v, 3D: the energy term, minus the height
float  *ln_ez;                  // vz, signed
float  *ln_ei;                  // the sample it came from, counted by this slot

float  ln_n[LN_SLOTS];
float  ln_bkn[LN_SLOTS];
float  ln_step[LN_SLOTS];       // build decimation: keep every step-th sample
float  ln_skip[LN_SLOTS];
float  ln_pbrk[LN_SLOTS];       // a break carried from a dropped sample
float  ln_on[LN_SLOTS];
float  ln_ia[LN_SLOTS], ln_ib[LN_SLOTS];     // the shown index range
float  ln_lo[LN_SLOTS], ln_hi[LN_SLOTS];     // its speed range

float  ln_evn[LN_SLOTS];        // marks held
float  ln_evcut[LN_SLOTS];      // the peaks were dropped to make room
float  ln_evdrop[LN_SLOTS];     // marks lost past the cap even so
float  ln_pkind[LN_SLOTS];      // the contact kind of the last sample, -1 unknown
float  ln_ron[LN_SLOTS];        // the ramp hold's two variables, this slot's own
float  ln_rlast[LN_SLOTS];
float  ln_gjmp[LN_SLOTS];       // +jump seen anywhere in the ground phase
float  ln_pvz[LN_SLOTS];
float  ln_vzmax[LN_SLOTS];      // |vz| since the last reversal: the peak gate
float  ln_nsamp[LN_SLOTS];      // samples this slot has classified
float  ln_tick[LN_SLOTS];       // the recording's own tick, for the ceiling
float  ln_pyaw[LN_SLOTS], ln_pt[LN_SLOTS];   // the sample before: yaw, clock
float  ln_gsince[LN_SLOTS];     // when the current ground phase began

/*
  THE MOVEMENT SETTINGS THE GRADE IS MEASURED AGAINST.

  Read once per load, from the server this client is on -- which is what the
  strafe bar does for a replay too (HUD_DrawStrafe, cl_hud.qc), so the line and
  the bar grade the same moment the same way.  A recording made on a server
  with different movement settings is therefore graded against THIS one's: that
  is a real limitation, it is the bar's limitation as well, and the v9 header's
  `pmpin` block is where a future patch would get the file's own.
*/
float  ln_mv_airaccel, ln_mv_accel, ln_mv_maxspeed, ln_mv_aircap;
float  ln_mv_gravity, ln_mv_gfric, ln_mv_stopspeed, ln_mv_duck, ln_mv_ghold;

// The window: the stretch of RUN TIME shown around the playhead, set by the
// caller.  Never inferred from tplay -- a board line is drawn with tplay
// 99999999 as a "no playhead" sentinel (cl_scores.qc), and a window derived
// from that shows nothing at all.
float  ln_winon, ln_wina, ln_winb, ln_winka, ln_winkb;

// The marks' own frame state: the cvars, read once, and the declutter grid.
float  ln_mkon, ln_mkland, ln_mkleave, ln_mkjump, ln_mkstitch;
float  ln_mkpx, ln_mkgap, ln_wpx;

// The numbers (Patch 451), read once a frame.  ln_grav is the reader's, not one
// baked in at load: the same file watched on a different sv_gravity is a
// different run and the energy has to say so.
float  ln_numon, ln_numspeed, ln_numenergy, ln_numvz, ln_numdelta, ln_numtime;
float  ln_numref, ln_numsize, ln_grav, ln_units, ln_names;
float  ln_labsz;                // the size the labels are measured and drawn at, see Line_Marks
float  ln_z0[LN_SLOTS], ln_v20[LN_SLOTS];       // the slot's first sample: z, v.v
float  ln_nlab;                 // labels queued, this Line_Draw
float  ln_labover;              // ...and the ones past LN_LABMAX

/*
  THE LABELS ARE QUEUED AND DRAWN AT THE END OF THE FRAME, not where they are
  worked out.

  Measured, not assumed: text drawn from inside Line_Draw does not appear at
  all.  The pass runs inside a stream of R_BeginPolygon batches, which the
  engine defers until a later 2D call flushes them, and a drawstring issued
  between two of them produced nothing -- including a fixed test string at a
  fixed position, which is how this was pinned down rather than guessed.  The
  counters said thirteen labels had drawn and the screenshot had none.

  Ev_Labels (cl_entview.qc) has the same shape for the same reason, and the
  slot for it in cl_main is already there.
*/
vector ln_lab_p[LN_LABMAX];
vector ln_lab_c[LN_LABMAX];
float  ln_lab_a[LN_LABMAX];
string ln_lab_t[LN_LABMAX];
float  ln_lab_n;
float  *ln_cell;                // a cell's last claiming frame
float  *ln_lcell;               // and the labels' own grid, see Line_Claim
float  ln_cellgen, ln_cellnx, ln_cellny;
vector ln_qmk;                  // Line_ProjPt's answer (a second return)
float  ln_nmk;                  // marks drawn, this Line_Draw
float  ln_trmk;                 // `replay marktrace`: frames left to print

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

/*
  PROVENANCE, AS A TINT RATHER THAN A COLOUR MODE.  A run imported from another
  game (tools/momimport.py; the `foreign` key in its .rec header) is drawn with
  its colour pulled toward blue.

  A TINT AND NOT A SIXTH hud_watch_path_color, which was the obvious shape and
  is the wrong one: a mode REPLACES the colouring, so an imported line could be
  identified or it could be read for speed, gain, contact, energy or air
  control, never both.  Blending composes with all five, so the thing the line
  is FOR still works and the line still says where it came from.

  Luminance is preserved rather than flattened -- the blend keeps the relative
  brightness the mode produced -- so a fast stretch of an imported line is still
  visibly faster than a slow one.
*/
float  ln_fgn[LN_SLOTS];        // slot holds a foreign run
float  ln_dtint;                // the draw's blend strength, 0 = none
#define LN_FGNCOL  '0.25 0.45 1.00'

void() Line_Alloc =
{
	if (ln_pos)
		return;
	ln_pos  = memalloc(sizeof(vector) * LN_SLOTS * LN_CAP);
	ln_spd  = memalloc(sizeof(float) * LN_SLOTS * LN_CAP);
	ln_t    = memalloc(sizeof(float) * LN_SLOTS * LN_CAP);
	ln_brk  = memalloc(sizeof(float) * LN_SLOTS * LN_CAP);
	ln_gain = memalloc(sizeof(float) * LN_SLOTS * LN_CAP);
	// +2.25 MiB, and the only per-point array the marks and the numbers did
	// not need: energy is z + |v|^2/2g and ln_spd is the HORIZONTAL speed, so
	// without this the colour would be energy with the vertical left out --
	// wrong exactly where a surf line is interesting.
	ln_vz   = memalloc(sizeof(float) * LN_SLOTS * LN_CAP);
	ln_q    = memalloc(sizeof(float) * LN_SLOTS * LN_CAP);
	ln_col  = memalloc(sizeof(vector) * LN_SLOTS * LN_CAP);
	ln_cerr = memalloc(sizeof(float) * LN_SLOTS * LN_CAP / LN_CHUNK * LN_LEVELS);
	ln_cc   = memalloc(sizeof(vector) * LN_SLOTS * LN_CAP / LN_CHUNK);
	ln_cr   = memalloc(sizeof(float) * LN_SLOTS * LN_CAP / LN_CHUNK);
	ln_cbk  = memalloc(sizeof(float) * LN_SLOTS * LN_CAP / LN_CHUNK);
	ln_gc   = memalloc(sizeof(vector) * LN_SLOTS * LN_CAP / LN_CHUNK / LN_GROUP);
	ln_gr   = memalloc(sizeof(float) * LN_SLOTS * LN_CAP / LN_CHUNK / LN_GROUP);
	ln_bk   = memalloc(sizeof(float) * LN_SLOTS * LN_BKCAP);
	// 1.28 MiB for every slot's marks, against 2.25 MiB for ONE more per-point
	// float array.  Nothing about a mark is per point, which is the argument.
	ln_ek   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_es   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_et   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_ep   = memalloc(sizeof(vector) * LN_SLOTS * LN_EVCAP);
	ln_evh  = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_e2   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_ez   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	// The ordinal is the mark's identity.  Two samples can share a `t` (a file
	// records one per packet, and a held clock repeats it -- both bhop fixtures
	// carry such a pair), so time does not identify a sample and a reader that
	// keys on it mis-assigns the mark.  +147 KB.
	ln_ei   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_cell = memalloc(sizeof(float) * LN_CELLS);
	ln_lcell = memalloc(sizeof(float) * LN_CELLS);
};

void(float s) Line_Clear =
{
	ln_on[s] = FALSE;
	ln_n[s]  = 0;
	ln_bkn[s] = 0;
	ln_ia[s] = ln_ib[s] = 0;
	ln_evn[s] = 0;
	ln_evcut[s] = FALSE;
	ln_evdrop[s] = 0;
	ln_nsamp[s] = 0;
};

// The recording's own tick.  The energy colour divides by the most energy air
// strafing can add in one (Strafe_PowerCeiling), and that is per tick -- a file
// recorded at a different rate would otherwise read as a different player.
// Patch 470: Line_Grade reads it too (it took the live server's, and graded a
// 0.01 file on a 0.015 lobby against a target 1.5x too low).
void(float s, float tick) Line_Tick =
{
	ln_tick[s] = (tick > 0) ? tick : 0.015;
};

void() Line_Movevars =
{
	ln_mv_airaccel = serverkeyfloat("sv_airaccelerate");
	ln_mv_accel    = serverkeyfloat("sv_accelerate");     if (ln_mv_accel    <= 0) ln_mv_accel    = 5;
	ln_mv_maxspeed = serverkeyfloat("sv_maxspeed");       if (ln_mv_maxspeed <= 0) ln_mv_maxspeed = PM_RUN_SPEED;
	ln_mv_aircap   = serverkeyfloat("pm_maxairspeed");    if (ln_mv_aircap   <= 0) ln_mv_aircap   = 30;
	ln_mv_gravity  = serverkeyfloat("sv_gravity");        if (ln_mv_gravity  <  1) ln_mv_gravity  = 800;
	ln_mv_gfric    = serverkeyfloat("sv_friction");       if (ln_mv_gfric    <  0) ln_mv_gfric    = 4;
	ln_mv_stopspeed= serverkeyfloat("sv_stopspeed");      if (ln_mv_stopspeed<  0) ln_mv_stopspeed= 75;
	ln_mv_duck     = serverkeyfloat("pm_duckspeed");
	ln_mv_ghold    = cvar("hud_strafe_groundhold");
};

void(float s) Line_Begin =
{
	Line_Alloc();
	Line_Movevars();
	Line_Clear(s);
	ln_step[s] = 1;
	ln_skip[s] = 0;
	ln_pbrk[s] = FALSE;
	ln_tick[s] = 0.015;
	ln_pkind[s] = -1;               // unknown, not "in the air": the first sample
	ln_ron[s]   = FALSE;            // of a board line's window must mark nothing
	ln_fgn[s]   = FALSE;            // until the header says otherwise
	ln_rlast[s] = 0;
	ln_gjmp[s]  = FALSE;
	ln_pvz[s]   = 0;
	ln_vzmax[s] = 0;
	ln_pyaw[s]  = 0;
	ln_pt[s]    = 0;
	ln_gsince[s] = 0;
};

/*
  The run in this slot came from another game.  Called by whichever scanner read
  the header -- the replay's (slot 0) and the board-line job's (slots 1..8) are
  separate passes over the same grammar, so both have to say it.

  Set AFTER Line_Begin, which clears it: a slot is reused by whatever is drawn
  there next, and a foreign line leaving its tint behind for the local run that
  replaces it would be a lie that persists until the map changes.
*/
void(float s, float on) Line_Foreign =
{
	if (s >= 0 && s < LN_SLOTS)
		ln_fgn[s] = on ? TRUE : FALSE;
};

float(float s) Line_IsForeign =
{
	return (s >= 0 && s < LN_SLOTS) ? ln_fgn[s] : FALSE;
};

/*
  One mark.  Full is handled in two stages rather than by truncating:

    1. the peaks go, as a class, in one pass.  They are dense, derived, and
       carry no glyph, and a line that keeps every hop and says the peaks went
       beats one that shows 600 of 1200 hops and says nothing.
    2. past that it stops and counts, which `replay status` prints (slot 0).

  Halving, the way the point array does, is the wrong answer here: it would
  drop every other hop.
*/
void(float s, float k, float sub, float t, vector o, vector v) Line_Ev =
{
	local float b, n, i, j;

	if (ln_evcut[s])
	if (k == LN_E_APEX || k == LN_E_TROUGH)
		return;

	b = s * LN_EVCAP;
	n = ln_evn[s];
	if (n >= LN_EVCAP)
	{
		if (!ln_evcut[s])
		{
			j = 0;
			for (i = 0; i < n; i = i + 1)
				if (ln_ek[b + i] != LN_E_APEX)
				if (ln_ek[b + i] != LN_E_TROUGH)
				{
					ln_ek[b + j]  = ln_ek[b + i];
					ln_ei[b + j]  = ln_ei[b + i];
					ln_es[b + j]  = ln_es[b + i];
					ln_et[b + j]  = ln_et[b + i];
					ln_ep[b + j]  = ln_ep[b + i];
					ln_evh[b + j] = ln_evh[b + i];
					ln_e2[b + j]  = ln_e2[b + i];
					ln_ez[b + j]  = ln_ez[b + i];
					j = j + 1;
				}
			ln_evn[s] = n = j;
			ln_evcut[s] = TRUE;
		}
		if (n >= LN_EVCAP)
		{
			ln_evdrop[s] = ln_evdrop[s] + 1;
			return;
		}
	}
	ln_ek[b + n]  = k;
	ln_es[b + n]  = sub;
	ln_et[b + n]  = t;
	ln_ep[b + n]  = o;
	ln_evh[b + n] = vlen([v_x, v_y, 0]);
	ln_e2[b + n]  = v * v;
	ln_ez[b + n]  = v_z;
	ln_ei[b + n]  = ln_nsamp[s];
	ln_evn[s] = n + 1;
};

// One sample.  brk: the segment from the previous sample is a teleport.
void(float s, vector o, float spd, float vz, float q, float t, float brk) Line_Add =
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
			ln_vz[b + i]  = ln_vz[j];
			ln_q[b + i]   = ln_q[j];
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
	ln_vz[b + n]  = vz;
	ln_q[b + n]   = q;
	ln_t[b + n]   = t;
	ln_brk[b + n] = (n > 0 && ln_pbrk[s]);
	ln_pbrk[s] = FALSE;
	ln_n[s] = n + 1;
};

/*
  HOW GOOD WAS THE AIR CONTROL AT THIS SAMPLE, on the strafe bar's own terms.

  This is the bar's regime logic (HUD_DrawStrafe, cl_hud.qc), sample by sample
  instead of frame by frame, and it calls the SAME sh_strafe.qc functions with
  the same movement settings -- so the line and the bar cannot grade one moment
  two ways.  The three regimes are not variations of one formula:

    ground   Accelerate has no 30 u/s cap, so the optimum is wishdir nearly
             ALONG the velocity, and it is evaluated after friction.
    ramp     the clip couples gravity into the rotating component; on a 53
             degree face the ideal is 17-55% of the flat one, so the flat
             figure would overstate the target by up to 6x.
    air      the flat formula.

  It returns -1 -- NO ANSWER, drawn grey -- rather than a grade wherever the
  bar refuses one: an air cap that does not bind (a turn rate then grades the
  server, not the player), a ground target under 10 deg/s where the square-root
  shoulder makes 1 u/s swing it 15 deg/s, a plane the maths cannot answer for,
  and the first sample of a slot, which has no previous yaw to turn from.  A
  colour that says "bad" when it means "cannot tell" is the failure this
  codebase has paid for more than once.
*/
float(float s, vector v, float fl, float t, vector aux) Line_Grade =
{
	local float speed, turn, dt, ideal, cscale, gain, fric, wishspeed, vf, ong, tick;

	tick = ln_tick[s];
	dt = t - ln_pt[s];
	if (dt <= 0 || ln_nsamp[s] < 1)
		return -1;                      // nothing to have turned from

	// Unsigned degrees per second, the short way round the circle.
	turn = aux_x - ln_pyaw[s];
	while (turn > 180)  turn = turn - 360;
	while (turn < -180) turn = turn + 360;
	turn = fabs(turn) / dt;

	speed = vlen([v_x, v_y, 0]);
	ong = fl & WT_F_ONGROUND;
	// A one-tick bhop landing is not a grounded phase -- the bar's own gate.
	if (ong)
	if (ln_mv_ghold > 0)
	if (t - ln_gsince[s] < ln_mv_ghold)
		ong = FALSE;

	wishspeed = ln_mv_maxspeed;
	if (ong)
	if (fl & WT_F_DUCKED)
	if (ln_mv_duck > 0)
		wishspeed = ln_mv_maxspeed * ln_mv_duck;

	// Surface friction: airborne and rising, below the non-jump velocity.
	fric = 1;
	if (!ong && v_z > 0 && v_z <= PM_NONJUMP_VEL)
		fric = 0.25;

	cscale = ln_mv_aircap;
	if (ong)
	{
		gain  = Strafe_GroundGain(ln_mv_accel, wishspeed, tick, fric);
		vf    = Strafe_AfterFriction(speed, ln_mv_gfric, ln_mv_stopspeed, tick);
		ideal = Strafe_IdealTurnGround(vf, gain, wishspeed, tick);
		if (ideal <= 10)
			return -1;                  // the shoulder: not a number to grade on
	}
	else if (!Strafe_CapBinds(ln_mv_airaccel, ln_mv_maxspeed, tick, fric,
	                          ln_mv_aircap))
		return -1;                      // the cap has slack: this grades the server
	else
	{
		gain = Strafe_AirGain(ln_mv_airaccel, wishspeed, tick, fric,
		                      ln_mv_aircap);
		if (aux_y >= 0.05 && aux_y <= PM_STANDABLE && aux_z != 0)
		{
			ideal  = Strafe_IdealTurnPlane(speed, tick, gain, ln_mv_gravity,
			                               aux_y, aux_z);
			cscale = Strafe_CScale(ln_mv_gravity, tick, aux_y, aux_z,
			                       ln_mv_aircap);
			if (ideal <= 0.001)
				return -1;              // the ramp is doing the turning, not you
		}
		else
			ideal = Strafe_IdealTurn(speed, gain, tick);
	}
	return Strafe_Quality(turn, ideal, cscale, ln_mv_aircap);
};

/*
  This sample's contact kind, with the slot's own ramp hold moved on.  It does
  NOT touch ln_pkind: the mark is the edge between two samples, so the caller
  owns what the previous one was.

  THE BRIDGED-GAP COUNTERS ARE DELIBERATELY NOT REPLICATED.  Board_RampHold
  also keeps ramp_raw/ramp_rawlast and counts ramp_drops/ramp_bridged on a
  gap's trailing edge; this has no equivalent and therefore cannot answer "how
  many gaps were bridged".  It does not need to -- the line wants kind EDGES,
  not a count -- but do not "fix" the omission: those counters belong to the
  live board, and `replay status`'s `ramp gaps bridged` is the board's number,
  not this one's (review, Patch 449).
*/
float(float s, vector v, float fl, float t) Line_Contact =
{
	local float raw, held;

	raw  = fl & WT_F_RAMP;
	held = Board_RampHeld(raw, ln_ron[s], ln_rlast[s], t);
	if (raw)
		ln_rlast[s] = t;
	ln_ron[s] = held;
	return Board_KindOf(fl & WT_F_ONGROUND, held);
};

// What a sample leaves behind for the next one to be compared against.
void(float s, float k, vector v, float fl) Line_Was =
{
	ln_pkind[s] = k;
	ln_pvz[s]   = v_z;
	ln_gjmp[s]  = (k == SEG_NONE) ? (ln_gjmp[s] || (fl & WT_F_JUMP)) : FALSE;
};

/*
  A sample BEFORE the shown window: its state only, no point and no mark.

  Slot 0's scan starts one sample early (rec_wt_bline) so its first shown point
  has a predecessor; a board line's job skips straight to its window and had
  none, which made the two mark the same run differently at its first contact.
  Exactly ONE sample seeds, in both -- a longer history would warm this slot's
  ramp hold while slot 0 starts it cold, and they would disagree again.
*/
void(float s, vector v, float fl, float t, float yaw) Line_Seed =
{
	Line_Was(s, Line_Contact(s, v, fl, t), v, fl);
	ln_pyaw[s] = yaw;
	ln_pt[s] = t;
	ln_vzmax[s] = 0;
	ln_nsamp[s] = 0;                // the window's first sample is ordinal 0
};

/*
  One sample, classified, then handed to Line_Add.  Patch 449.

  It runs ABOVE Line_Add's decimation return on purpose: once a slot has halved
  or is striding, half the samples never reach the point array, and a hop
  landing on one of them would vanish.  Same reason ln_pbrk is set up there.

  `stitch`: this sample is where a save state was loaded (a resume/retry record
  sits in the interval before it).  It is marked whatever the contact did --
  a load also moves the body, so brk is set here too and the contact edge across
  it is suppressed as meaningless.
*/
void(float s, vector o, vector v, float fl, float t, float brk, float stitch,
     vector aux) Line_Point =
{
	local float k, q;

	// aux is [yaw, the plane's z, wishdir . plane] -- one parm slot rather than
	// three, which is what keeps this call inside fteqcc's eight.
	q = Line_Grade(s, v, fl, t, aux);
	k = Line_Contact(s, v, fl, t);
	if (k == SEG_NONE && ln_pkind[s] != SEG_NONE)
		ln_gsince[s] = t;               // this ground phase began here

	if (brk)
		Line_Ev(s, LN_E_BREAK, 0, t, o, v);
	if (stitch)
		Line_Ev(s, LN_E_STITCH, 0, t, o, v);

	if (brk || ln_pkind[s] < 0)
		ln_vzmax[s] = 0;            // the body moved, or nothing is known yet
	else if (k != ln_pkind[s])
	{
		if (k == SEG_NONE || k == SEG_RAMP)
			Line_Ev(s, LN_E_LAND, ln_pkind[s] * 4 + k, t, o, v);
		else if (ln_pkind[s] == SEG_RAMP)
			// ALWAYS a leave, never a hop: +jump held through a whole surf would
			// otherwise put a double chevron on every ramp exit.
			Line_Ev(s, LN_E_LEAVE, ln_pkind[s] * 4 + k, t, o, v);
		else
			Line_Ev(s, ln_gjmp[s] ? LN_E_JUMP : LN_E_LEAVE,
			        ln_pkind[s] * 4 + k, t, o, v);
		ln_vzmax[s] = 0;            // a takeoff is not a trough
	}
	else if (k == SEG_AIR)
	{
		// The gate is the debounce: vz noise around zero would otherwise fire
		// hundreds of reversals a second on a slow slide.
		ln_vzmax[s] = max(ln_vzmax[s], fabs(v_z));
		if (ln_vzmax[s] >= LN_EVZMIN)
		{
			if (ln_pvz[s] > 0 && v_z <= 0)
			{
				Line_Ev(s, LN_E_APEX, 0, t, o, v);
				ln_vzmax[s] = 0;
			}
			else if (ln_pvz[s] <= 0 && v_z > 0)
			{
				Line_Ev(s, LN_E_TROUGH, 0, t, o, v);
				ln_vzmax[s] = 0;
			}
		}
	}

	Line_Was(s, k, v, fl);
	ln_pyaw[s] = aux_x;
	ln_pt[s] = t;
	if (!ln_nsamp[s])
	{
		ln_z0[s]  = o_z;        // the run's own start, one choice of energy zero
		ln_v20[s] = v * v;
	}
	ln_nsamp[s] = ln_nsamp[s] + 1;
	Line_Add(s, o, vlen([v_x, v_y, 0]), v_z, q, t, brk);
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

/*
  SHOW ONLY [ta, tb] OF RUN TIME, wherever the camera is.

  The distance cull answers "is it near me"; this answers "is it near where I
  am WATCHING", which is the question a replay actually asks.  It composes with
  the shown range by intersection -- a stage cut always wins and the window can
  only narrow it -- and with `ahead 0`, which clamps afterwards as it always did.

  ln_winon is set by the caller and never derived from tplay: a board line is
  drawn with tplay 99999999 to mean "no playhead", and `if (tplay < 99999)`,
  the obvious shortcut, makes every board line draw nothing.  p449win W5.
*/
void(float ta, float tb) Line_Window =
{
	ln_winon = TRUE;
	ln_wina  = ta;
	ln_winb  = tb;
	// Faded over a sixth of the span at each end: a line that stops dead reads
	// as a break in the recording rather than as the edge of a window.
	ln_winka = (tb > ta) ? 6 / (tb - ta) : 0;
	ln_winkb = ln_winka;
};

void() Line_WindowOff =
{
	ln_winon = FALSE;
};

// The first mark at or after t.  The list is appended in sample order, so it is
// sorted by construction.
float(float s, float t) Line_EvFind =
{
	local float b, lo, hi, m;

	b = s * LN_EVCAP;
	lo = 0;
	hi = ln_evn[s];
	while (lo < hi)
	{
		m = floor((lo + hi) * 0.5);
		if (ln_et[b + m] < t)
			lo = m + 1;
		else
			hi = m;
	}
	return lo;
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

/*
  CONTACT: ground, ramp or air, as a colour rather than a glyph.

  Taken from the MARKS, which are the edges of exactly this function, so the
  colour and the chevrons cannot disagree -- and no per-point kind has to be
  stored to do it.  A phase runs from one contact mark to the next, and a
  mark's sub-code carries the pair it crossed (from * 4 + to).
*/
void(float s) Line_ColContact =
{
	local float b, e, n, i, k, upto, sub;
	local vector c;

	b = s * LN_CAP;
	n = s * LN_EVCAP;
	// Before the first contact mark the run was in that mark's `from` state.
	k = -1;
	for (e = 0; e < ln_evn[s]; e = e + 1)
		if (ln_ek[n + e] <= LN_E_JUMP)
		{
			k = floor(ln_es[n + e] / 4);
			break;
		}
	e = 0;
	i = 0;
	while (i < ln_n[s])
	{
		// The next contact mark closes this phase.
		upto = ln_n[s];
		while (e < ln_evn[s])
		{
			if (ln_ek[n + e] <= LN_E_JUMP)
			{
				upto = Line_Find(s, ln_et[n + e]);
				break;
			}
			e = e + 1;
		}
		if (k == SEG_NONE)      c = '1.00 0.62 0.20';    // ground, the V's colour
		else if (k == SEG_RAMP) c = '0.35 0.85 1.00';    // riding a plane
		else if (k == SEG_AIR)  c = '0.85 0.88 0.95';    // neither
		else                    c = '0.45 0.45 0.50';    // before the first mark
		while (i < upto && i < ln_n[s])
		{
			ln_col[b + i] = c;
			i = i + 1;
		}
		if (e >= ln_evn[s])
		{
			while (i < ln_n[s])
			{
				ln_col[b + i] = c;
				i = i + 1;
			}
			return;
		}
		sub = ln_es[n + e];
		k = sub - floor(sub / 4) * 4;
		e = e + 1;
	}
};

/*
  ENERGY GAINED OR LOST, against the most air strafing can add.

  E = z + |v|^2/2g (Strafe_Energy), differenced over the same two-samples-each-
  side window the speed gain uses, and divided by Strafe_PowerCeiling -- the
  denominator the live strafe gauge already normalises by, so full green here
  and a full gauge there mean the same thing.  Speed and energy are NOT the
  same colour: a surfer trading height for speed reads green on gain and flat
  here, which is the point of having both.
*/
void(float s) Line_ColEnergy =
{
	local float b, i, j0, j1, dt, f, p, e0, e1;
	local vector o;

	b = s * LN_CAP;
	// pm_maxairspeed, not a literal 30: the grade in Line_Grade reads the
	// server's, and two air caps in one file is how the line would come to
	// disagree with itself on a server that changed it.
	p = Strafe_PowerCeiling(ln_mv_aircap, ln_grav, ln_tick[s]);
	if (p <= 0)
		p = 37.5;
	for (i = 0; i < ln_n[s]; i = i + 1)
	{
		j0 = j1 = i;
		for (dt = 0; dt < 2; dt = dt + 1)
		{
			if (j0 > 0)
			if (!ln_brk[b + j0])
				j0 = j0 - 1;
			if (j1 + 1 < ln_n[s])
			if (!ln_brk[b + j1 + 1])
				j1 = j1 + 1;
		}
		dt = ln_t[b + j1] - ln_t[b + j0];
		o = ln_pos[b + j0];
		e0 = o_z + (ln_spd[b + j0] * ln_spd[b + j0]
		            + ln_vz[b + j0] * ln_vz[b + j0]) / (2 * ln_grav);
		o = ln_pos[b + j1];
		e1 = o_z + (ln_spd[b + j1] * ln_spd[b + j1]
		            + ln_vz[b + j1] * ln_vz[b + j1]) / (2 * ln_grav);
		f = (dt > 0) ? bound(-1, ((e1 - e0) / dt) / p, 1) : 0;
		if (f >= 0)
			ln_col[b + i] = '0.85 0.85 0.85' + ('-0.55 0.15 -0.45' * f);
		else
			ln_col[b + i] = '0.85 0.85 0.85' + ('0.15 -0.60 -0.60' * (0 - f));
	}
};

/*
  AIR CONTROL, as the strafe bar grades it: green good, red poor, and GREY
  where there is no answer.  HUD_QualityColor is the bar's own ramp, so a
  stretch of line and the bar at that moment are the same colour.
*/
void(float s) Line_ColQuality =
{
	local float b, i;

	b = s * LN_CAP;
	for (i = 0; i < ln_n[s]; i = i + 1)
		ln_col[b + i] = HUD_QualityColor(ln_q[b + i]);
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
	// The marks, read once a frame beside the rest.  ln_wpx is the line's own
	// width, kept so the glyph pass can put it back: Line_Width writes globals
	// every emitter reads, and Scores_LinesDraw calls Line_Draw eight times.
	ln_wpx      = cvar("hud_watch_path_px");
	ln_mkon     = cvar("hud_lines_marks");
	ln_mkland   = cvar("hud_lines_land");
	ln_mkleave  = cvar("hud_lines_leave");
	ln_mkjump   = cvar("hud_lines_jump");
	ln_mkstitch = cvar("hud_lines_stitch");
	ln_mkpx     = cvar("hud_lines_size");   if (ln_mkpx < 1) ln_mkpx = 4;
	ln_mkgap    = cvar("hud_lines_gap");    if (ln_mkgap < 4) ln_mkgap = 40;
	ln_mkgap    = ln_mkgap * ln_px;
	ln_numon     = cvar("hud_lines_nums");
	ln_numspeed  = cvar("hud_lines_speed");
	ln_numenergy = cvar("hud_lines_energy");
	ln_numvz     = cvar("hud_lines_vz");
	ln_numdelta  = cvar("hud_lines_delta");
	ln_numtime   = cvar("hud_lines_time");
	ln_numref    = cvar("hud_lines_ref");
	ln_numsize   = cvar("hud_lines_numsize");  if (ln_numsize < 6) ln_numsize = 12;
	ln_names     = cvar("hud_lines_names");
	// Board_Frame's seq_units is not refreshed while a replay is up, so the
	// label reads the cvar itself: two readers of one cvar, not two answers.
	ln_units     = cvar("hud_seq_units");
	ln_grav      = serverkeyfloat("sv_gravity");
	if (ln_grav < 1)
		ln_grav = 800;
	fov = getproperty(VF_SCREENVSIZE);
	ln_cellnx = min(64, floor(fov_x / ln_mkgap) + 1);
	ln_cellny = min(LN_CELLS / max(1, ln_cellnx), floor(fov_y / ln_mkgap) + 1);
	ln_cellgen = ln_cellgen + 1;
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
			{
				// Two of the modes are whole-slot walks rather than per-point
				// functions: contact reads the mark list, and energy needs a
				// window either side of the point.
				if (ln_cmode == 2)
					Line_ColContact(s);
				else if (ln_cmode == 3)
					Line_ColEnergy(s);
				else if (ln_cmode == 4)
					Line_ColQuality(s);
				else
					for (i = s * LN_CAP; i < s * LN_CAP + ln_n[s]; i = i + 1)
						ln_col[i] = Line_Col(i);
			}
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
	if (ln_dtint)
		c = c + (LN_FGNCOL - c) * ln_dtint;
	a = ((ln_t[b + i] <= tplay) ? 1 : ahead) * ln_da;
	// The fade is by distance, as the cull is (review: by depth it cut hard at
	// the screen's sides); only a chunk reaching into it pays the vlen.
	if (ln_cfade)
		a = a * bound(0, (ln_far - vlen(p - ln_eye)) * ln_fadek, 1);
	if (ln_winon)
		a = a * bound(0, min((ln_t[b + i] - ln_wina) * ln_winka,
		                     (ln_winb - ln_t[b + i]) * ln_winkb), 1);

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
  A world point onto the screen, or FALSE.  The dot product runs BEFORE
  project(), which divides by w with no zero guard (pr_csqc.c) -- a point on
  the eye plane otherwise returns a NaN that reaches drawfill and drawstring.
  cl_entview.qc:1288-1294 is the same guard for the same reason.
*/
float(vector w) Line_ProjPt =
{
	if ((w - ln_eye) * ln_fwd < LN_NEAR)
		return FALSE;
	ln_qmk = project(w);
	if (ln_qmk_z < -1 || fabs(ln_qmk_x) > LN_GUARD || fabs(ln_qmk_y) > LN_GUARD)
		return FALSE;
	ln_qmk_z = 0;
	ln_qmk = [floor(ln_qmk_x / ln_px + 0.5) * ln_px,
	          floor(ln_qmk_y / ln_px + 0.5) * ln_px, 0];
	return TRUE;
};

/*
  One screen cell a mark, at most.  A generation stamp rather than a clear: the
  grid is 4096 floats and zeroing it per frame would cost more than the marks.

  This is what bounds the pass: 300 hops inside twenty screen pixels draw one
  chevron, not 300, and the cost follows what is READABLE rather than what is
  in range.  A numeric cap would instead keep the first N in time order, which
  is not the N you are looking at.
*/
float(vector q) Line_CellOf =
{
	local float cx, cy, i;

	cx = floor(q_x / ln_mkgap);
	cy = floor(q_y / ln_mkgap);
	if (cx < 0 || cy < 0 || cx >= ln_cellnx || cy >= ln_cellny)
		return -1;                      // off screen: not drawn, not claimed
	i = cy * ln_cellnx + cx;
	return (i < 0 || i >= LN_CELLS) ? -1 : i;
};

float(vector q, float lab) Line_Claim =
{
	local float i;

	i = Line_CellOf(q);
	if (i < 0)
		return FALSE;
	// Labels claim their OWN grid.  Sharing one, a label lost every cell its
	// own glyph had just taken -- at gap 240 that was every number on screen
	// (p451num N6: 9 marks, 0 labels), which is not thinning, it is off.
	if (lab)
	{
		if (ln_lcell[i] == ln_cellgen)
			return FALSE;
		ln_lcell[i] = ln_cellgen;
		return TRUE;
	}
	if (ln_cell[i] == ln_cellgen)
		return FALSE;
	ln_cell[i] = ln_cellgen;
	return TRUE;
};

/*
  A label's whole span, claimed in ONE go.

  Its two ends can fall in the same cell, and claiming them one after the other
  made the label lose to ITSELF: at gap 240 that was every number on screen
  (p451num N6, 9 marks and 0 labels).  So: test both, then take both.
*/
float(vector lp, float lw) Line_ClaimSpan =
{
	local float i0, i1;

	i0 = Line_CellOf(lp);
	i1 = Line_CellOf(lp + [lw, 0, 0]);
	if (i0 < 0 && i1 < 0)
		return FALSE;
	if (i0 >= 0 && ln_lcell[i0] == ln_cellgen)
		return FALSE;
	if (i1 >= 0 && ln_lcell[i1] == ln_cellgen)
		return FALSE;
	if (i0 >= 0) ln_lcell[i0] = ln_cellgen;
	if (i1 >= 0) ln_lcell[i1] = ln_cellgen;
	return TRUE;
};

// n chevrons, stacked upwards, apex up (+1) or down (-1).  Polygons and not
// drawstring("A"): whether the bundled font covers U+039B and whether
// utf8_enable is on are two questions nobody should answer to see a mark.
void(vector q, float up, float n, vector c, float al) Line_Chev =
{
	local float w, h, i, pass, a;
	local vector a2, col;

	w = ln_mkpx * ln_px;
	h = w;
	/*
	  Two passes, a dark wider stroke under the colour -- the border
	  Line_Square already draws, for the reason p449shot_on showed: a white
	  take-off chevron against surf_aesthetic's sky is invisible, and the trace
	  said twelve of them had drawn in the frame I could not find them in.
	*/
	for (pass = 0; pass < 2; pass = pass + 1)
	{
		Line_Width(ln_mkpx * 0.5 + (pass ? 0 : 2));
		col = pass ? c : '0 0 0';
		a   = pass ? al : al * 0.6;
		for (i = 0; i < n; i = i + 1)
		{
			a2 = q - [0, up * (h + i * (h + ln_px)), 0];
			Line_Seg2D(a2 - [w, 0 - up * h, 0], a2, col, a, col, a);
			Line_Seg2D(a2, a2 + [w, up * h, 0], col, a, col, a);
		}
	}
};

// The stitch: two bars, the dark edge Line_Square draws.  A save state came
// back here, so the run either side of it was not flown in one go.
void(vector q, vector c, float al) Line_Bars =
{
	local float w, h;

	w = ln_px;
	h = ln_mkpx * ln_px * 1.5;
	drawfill(q - [w * 3 + ln_px, h + ln_px], [2 * w + 2 * ln_px, 2 * h + 2 * ln_px],
	         '0 0 0', al * 0.7, 0);
	drawfill(q + [w, 0 - h - ln_px, 0], [2 * w + 2 * ln_px, 2 * h + 2 * ln_px],
	         '0 0 0', al * 0.7, 0);
	drawfill(q - [w * 3, h], [2 * w, 2 * h], c, al, 0);
	drawfill(q + [w * 2, 0 - h, 0], [2 * w, 2 * h], c, al, 0);
};

/*
  ONE MARK'S NUMBERS, as a single string.

  One string and one HUD_Text, never one per number: every HUD_Text carries its
  own shadow pass (HUD_TextDraw), so a call per number multiplies the draws.

  hud_lines_names 1 says what each number is -- "701 u/s  E -28  vz +120  dE +12
  1.23 s" -- with two spaces between fields so a name never reads as the previous
  field's unit; 0 is the bare "701 -28e +120z +12e 1.23s".

  The energy zero is a choice and it is the reader's: hud_lines_ref 0 takes the
  HUD's own (HUD_EnergyRef, what the split list measures from, so the two
  agree), 1 takes the RUN's first sample, which is self-contained and
  comparable between two recordings of the same map -- the reason it is the
  default on a line, where the watching player's anchor means nothing.
*/
string(float s, float e) Line_Label =
{
	local float b, ev, en, ref, de;
	local vector ep;                // an array element is not swizzleable
	local string t, sep, f;

	b = s * LN_EVCAP;
	t = "";
	sep = (ln_names ? "  " : " ");
	ev = ln_evh[b + e];
	// E = z + |v|^2 / 2g, Strafe_Energy evaluated from what the mark carries.
	ep = ln_ep[b + e];
	en = ep_z + ln_e2[b + e] / (2 * ln_grav);
	ref = ln_numref ? (ln_z0[s] + ln_v20[s] / (2 * ln_grav)) : HUD_EnergyRef();

	if (ln_numspeed)
	{
		t = sprintf("%.0f", ev);
		if (ln_names)
			t = strcat(t, " u/s");
	}
	if (ln_numenergy)
		t = strcat(t, (t != "") ? sep : "",
		           HUD_SeqAbsTight(en - ref, ln_grav, ln_units, ln_names));
	if (ln_numvz)
	{
		if (ln_names)
			f = sprintf("vz %+.0f", ln_ez[b + e]);
		else
			f = sprintf("%+.0fz", ln_ez[b + e]);
		t = strcat(t, (t != "") ? sep : "", f);
	}
	if (ln_numdelta)
	if (e > 0)
	{
		ep = ln_ep[b + e - 1];
		de = en - (ep_z + ln_e2[b + e - 1] / (2 * ln_grav));
		t = strcat(t, (t != "") ? sep : "",
		           HUD_SeqDelTight(de, Strafe_EquivSpeed(de, ln_grav), ln_units, ln_names));
	}
	if (ln_numtime)
	{
		if (ln_names)
			f = sprintf("%.2f s", ln_et[b + e]);
		else
			f = sprintf("%.2fs", ln_et[b + e]);
		t = strcat(t, (t != "") ? sep : "", f);
	}
	return t;
};

/*
  The marks over the drawn stretch, after the teleport pass so a stitch's bars
  sit over its dashes.  Walked from the mark list rather than from the points:
  the LOD stride skips points, and a mark on a skipped one must still draw.
*/
void(float s, float ia, float ib, float tplay, float ahead, float alpha) Line_Marks =
{
	local float b, n, e, k, al, t0, t1, lw, f0;
	local vector p, c, q, lp;
	local string lab;

	if (!ln_mkon)
		return;
	/*
	  The labels are Bebas, measured here in the face and at the size
	  Line_FrameEnd draws them in.  4/3 keeps a digit's ink area: they drew in the
	  engine's default lhfont (a digit is 10x12 px of its 16 px cell), Bebas's is
	  0.71x0.33 em -- so numsize 12 -> 16 is 1.5x as tall at 0.6x the width (61 px^2
	  against 67).  The chips 10/12/14/18 land on 12/16/20/24.
	*/
	f0 = ui_font_cur;
	Font_Set(ui_font_dispsm);
	ln_labsz = Font_Px(ln_numsize * 4 / 3);
	b = s * LN_CAP;
	n = s * LN_EVCAP;
	t0 = ln_t[b + ia];
	t1 = ln_t[b + ib];
	for (e = Line_EvFind(s, t0); e < ln_evn[s]; e = e + 1)
	{
		if (ln_et[n + e] > t1)
			break;
		if (ahead <= 0)
		if (ln_et[n + e] > tplay)
			break;
		k = ln_ek[n + e];
		c = '1 1 1';                    // fteqcc cannot see the chain covers it
		if (k == LN_E_LAND)   { if (!ln_mkland)   continue; c = '1.00 0.62 0.20'; }
		else if (k == LN_E_LEAVE)  { if (!ln_mkleave)  continue; c = '0.92 0.95 1.00'; }
		else if (k == LN_E_JUMP)   { if (!ln_mkjump)   continue; c = '0.35 0.85 1.00'; }
		else if (k == LN_E_STITCH) { if (!ln_mkstitch) continue; c = '0.72 0.74 0.78'; }
		else if (k == LN_E_APEX || k == LN_E_TROUGH)
		{
			// A peak is where vz turned over.  It gets no chevron -- there is
			// no contact to mark -- so it appears only when the numbers are on
			// and it is the number that is the point (hud_lines_nums 2).
			if (ln_numon < 2)
				continue;
			c = '0.75 0.80 0.95';
		}
		else
			continue;                   // a break: the teleport pass owns it
		p = ln_ep[n + e];
		al = ((ln_et[n + e] <= tplay) ? 1 : ahead) * alpha;
		if (ln_fadek > 0)
			al = al * bound(0, (ln_far - vlen(p - ln_eye)) * ln_fadek, 1);
		if (ln_winon)
			al = al * bound(0, min((ln_et[n + e] - ln_wina) * ln_winka,
			                       (ln_winb - ln_et[n + e]) * ln_winkb), 1);
		if (al <= 0)
			continue;
		if (!Line_ProjPt(p))
			continue;
		if (!Line_Claim(ln_qmk, FALSE))
			continue;
		q = ln_qmk;
		if (k == LN_E_STITCH)
			Line_Bars(q, c, al);
		else if (k == LN_E_APEX || k == LN_E_TROUGH)
			Line_Square(p, c, al * 0.8);    // a peak is a dot: the number is the point
		else
			Line_Chev(q, (k == LN_E_LAND) ? -1 : 1,
			          (k == LN_E_JUMP) ? 2 : 1, c, al);
		ln_nmk = ln_nmk + 1;

		// The label claims its OWN cells -- the numbers are wider than the
		// glyph, so a mark can keep its chevron and lose its number rather
		// than the pair of them overprinting a neighbour.
		lab = "";
		if (ln_numon)
		{
			lab = Line_Label(s, e);
			if (lab != "")
			{
				lp = q + [6 * ln_px, 0 - (ln_labsz + 4) * ln_px, 0];
				lw = stringwidth(lab, FALSE, [ln_labsz, ln_labsz]);
				if (Line_ClaimSpan(lp, lw))
				{
					if (ln_lab_n < LN_LABMAX)
					{
						ln_lab_p[ln_lab_n] = lp;
						ln_lab_t[ln_lab_n] = lab;
						ln_lab_c[ln_lab_n] = c;
						ln_lab_a[ln_lab_n] = al;
						ln_lab_n = ln_lab_n + 1;
						ln_nlab = ln_nlab + 1;
					}
					else
						ln_labover = ln_labover + 1;
				}
				else
					lab = "";
			}
		}
		if (ln_trmk > 0)
			print(sprintf("lndm %g %g %.4f %.1f %.1f %s\n", s, k, ln_et[n + e],
			              q_x, q_y, (lab != "") ? strcat("\"", lab, "\"") : "-"));
	}
	Font_Set(f0);
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
	// The window narrows the shown range; the cut it was set inside still wins.
	if (ln_winon)
	{
		ia = max(ia, Line_Find(s, ln_wina));
		ib = min(ib, Line_Find(s, ln_winb + 0.0001) - 1);
	}
	if (ib <= ia)
		return;
	if (ahead <= 0)
		ib = min(ib, Line_Find(s, tplay));   // the first point past the playhead
	ln_db = b;
	ln_dn = ln_n[s];
	ln_da = alpha;
	// Read per draw, not per point: the cvar cannot change inside one line.
	ln_dtint = ln_fgn[s] ? bound(0, cvar("hud_watch_path_foreign"), 1) : 0;

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

	// Patch 449.  The glyph stroke is its own width, and the line's is put back
	// before the next slot is drawn.
	Line_Width(ln_mkpx * 0.5);
	ln_nmk = ln_nlab = 0;
	Line_Marks(s, ia, ib, tplay, ahead, alpha);
	Line_Width(ln_wpx);

	// Two prints and not one: fteqcc caps a varargs call at eight and drops
	// the rest silently.  Every number here was computed by the pass above.
	if (ln_trmk > 0)
	{
		print(sprintf("lnd %g %.4f %g %.4f %.4f\n", s, tplay, ln_winon,
		              ln_wina, ln_winb));
		print(sprintf("lnd2 %g %g %g %g %g %g\n", s, ia, ib, ln_npt, ln_nseg,
		              ln_nmk));
		print(sprintf("lnd3 %g %g\n", s, ln_nlab));
	}
};

// The frame's marks are done: cl_main calls this after the board lines, which
// are drawn after the replay's.
void() Line_FrameEnd =
{
	local float i, f0;

	if (ln_lab_n > 0)
	{
		f0 = ui_font_cur;
		Font_Set(ui_font_dispsm);
		for (i = 0; i < ln_lab_n; i = i + 1)
			HUD_Text(ln_lab_p[i], ln_lab_t[i], ln_labsz, ln_lab_c[i], ln_lab_a[i]);
		Font_Set(f0);
	}
	if (ln_trmk > 0)
	{
		print(sprintf("lnde %g %g\n", ln_lab_n, ln_labover));
		ln_trmk = ln_trmk - 1;
	}
	ln_lab_n = 0;
	ln_labover = 0;
};

/*
  THE LINE'S OWN CVARS.  Patch 449.

  Registered here rather than in cl_watch.qc's block, where the hud_watch_path_*
  family lives, because this file owns them -- but they keep that family's
  CVAR_ARCHIVE and its shipped `set` lines in default.cfg, and nothing is
  renamed: hud_watch_path_far is still how far the lines are visible.

  The window defaults OFF.  It changes what an existing player sees, and a
  display change nobody asked for is a bug report.
*/
void() Line_RegisterCvars =
{
	registercvar("hud_lines_marks",  "1", CVAR_ARCHIVE);
	registercvar("hud_lines_land",   "1", CVAR_ARCHIVE);
	registercvar("hud_lines_leave",  "1", CVAR_ARCHIVE);
	registercvar("hud_lines_jump",   "1", CVAR_ARCHIVE);
	registercvar("hud_lines_stitch", "1", CVAR_ARCHIVE);
	registercvar("hud_lines_size",   "4", CVAR_ARCHIVE);
	registercvar("hud_lines_gap",   "40", CVAR_ARCHIVE);
	// Patch 451: the numbers.  ON by default (Lex, asked when they were off):
	// a line you have to switch on twice is a line most people never see.
	// 1 = on the contact marks; 2 adds the peaks, which is dense on a bhop run.
	registercvar("hud_lines_nums",    "1", CVAR_ARCHIVE);
	registercvar("hud_lines_speed",   "1", CVAR_ARCHIVE);
	registercvar("hud_lines_energy",  "1", CVAR_ARCHIVE);
	registercvar("hud_lines_vz",      "0", CVAR_ARCHIVE);
	registercvar("hud_lines_delta",   "0", CVAR_ARCHIVE);
	registercvar("hud_lines_time",    "0", CVAR_ARCHIVE);
	registercvar("hud_lines_ref",     "1", CVAR_ARCHIVE);
	registercvar("hud_lines_numsize","12", CVAR_ARCHIVE);
	// Lex, 4 Oct 2026: the numbers say what they are by default.
	registercvar("hud_lines_names",   "1", CVAR_ARCHIVE);
	registercvar("hud_lines_win",    "0", CVAR_ARCHIVE);
	registercvar("hud_lines_winf",   "0", CVAR_ARCHIVE);
};

void() Line_StatsReset =
{
	ln_nseg = ln_nclip = ln_nwild = ln_npt = 0;
	ln_bbmin = '99999 99999 0';
	ln_bbmax = '-99999 -99999 0';
	ln_first = '0 0 0';
};
