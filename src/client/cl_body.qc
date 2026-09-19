/*
===========================================================================
  cl_body.qc -- lobby bodies from the pose stream.  Patch 383.

  Each avatar server/sv_pose.qc streams (its header is the wire grammar) is a
  CSQC entity here.  CSQC_Ent_Update pushes every sample into a ring of
  PB_RING cell entities; Body_Frame renders each body at a delayed clock
  between two samples with shared/sh_interp.qc; the predraw places and
  dresses it.

  CLOCK, per body.  o = min over two 0.5 s buckets of (arrival cltime - tick *
  pm_ticrate): the lowest-delay path, following drift.  The render clock R
  chases cltime - o - D, D = max(cl_body_delay, 1.5 * interval + 0.02), at
  +-5%; it jumps when > 0.25 s behind or below the ring's oldest cell, and
  holds when > 0.02 s ahead.  A sample
  > 0.25 s off o, or late by > 2 ticks while R had run past the newest sample
  (the owner's tick stopped), reseeds o and restarts R no earlier than the
  pose last drawn.  Past the newest sample R extrapolates cl_body_extrap s
  (position and angles), never while the sample is held.
===========================================================================
*/

// Wire: see sv_pose.qc.
#define PB_POSE     1
#define PB_LOOK     2
#define PB_SPEC     4
#define PB_TYPE     128     // reserved: a type byte follows

#define PBF_DUCKED  1
#define PBF_GROUND  2
#define PBF_NOCLIP  4
#define PBF_SERMASK 56
#define PBF_HELD    64
#define PBF_RESUME  128
#define PC_SPEC     256     // cell flag: this sample carried a SPEC block

#define PBL_COLOUR  1
#define PBL_TRAIL   2
#define PBL_MOTES   4
#define PBL_GLOW    8
#define PBL_LONG    16
#define PBL_CUSTOM  32

// Body_Pose's answer.
#define BP_LIVE     1       // a sample <= 1.0 s old, or held
#define BP_HELD     2
#define BP_VEL      4       // vel is real: this client receives the owner's SPEC
#define BP_DUCKED   8
#define BP_ONGROUND 16
#define BP_SNAP     32      // the drawn teleport serial changed this Body_Frame

// History for R to lag its target by the whole 0.25 s jump threshold plus D at
// 100 Hz (31 x 0.01 s); below the oldest cell Body_Eval jumps instead.
#define PB_RING     32

// body_trace status bits.
#define BT_STARVED  1       // R ran past the newest sample
#define BT_RESEED   2       // a sample since the last frame reseeded the clock
#define BT_SNAP     4
#define BT_UNDER    8       // R fell behind the oldest cell
#define BT_HOLD     16      // R held (ahead of target)
#define BT_JUMP     32      // R jumped (behind target)
#define BT_HELD     64
#define BT_RAW      128     // cl_body_raw: the newest sample, undelayed

// A cell (never drawn).  .origin/.angles/.velocity hold the sample.
.float  pc_t;               // unwrapped tick
.float  pc_eye;
.float  pc_fl;              // PBF_* less RESUME, plus PC_SPEC
.float  pc_keys;            // FSI_* mask
.float  pc_kraw;            // the wire keys byte, for body_trace
.float  pc_state, pc_track, pc_flags, pc_ticks;
.entity pc_next;            // newer
.entity pc_prev;            // older

// A body.
.entity pb_head;            // newest cell
.entity pb_nextbody;
.float  pb_n;               // valid cells
.float  pb_t0;              // tick of the first cell since the ring (re)started
.float  pb_slot;            // owner slot + 1; 0 until a LOOK
.float  pb_lo;              // last wire tick
.float  pb_tnew;            // newest tick, unwrapped
.float  pb_clk;             // the clock is seeded
.float  pb_o, pb_bmin0, pb_bmin1, pb_bt;
.float  pb_rclk;            // R, seconds of owner tick time
.float  pb_reval;           // the time last drawn
.float  pb_ivl;             // sample interval EWMA, s
.float  pb_starved;
.float  pb_rxt;             // cltime of the last sample
.float  pb_rsflag;
.float  pb_lf, pb_lc, pb_tc;
.vector pb_rgb;             // worn rgb, bytes
.float  pb_fxtrail, pb_fxmote, pb_motacc;
.vector pb_rorg, pb_rang, pb_rvel;
.float  pb_reye, pb_rfl, pb_rkeys, pb_rkraw, pb_rser, pb_snap, pb_st;
.float  pb_rstate, pb_rtrack, pb_rflags, pb_rticks;
.vector pb_trail;
.float  pb_trailok, pb_duck;
.float  pb_rx, pb_rx0t, pb_tks, pb_gapn, pb_reseed, pb_under, pb_frames, pb_latef;

entity pb_list;
float  pb_tick;             // pm_ticrate
float  pb_ftime, pb_fdt;
float  pb_cv_delay, pb_cv_extrap, pb_cv_hermite, pb_cv_raw;
float  pb_tr_slot, pb_tr_n, pb_tr_dc;
entity pb_tr_ent;

float() Body_TickRate =
{
	local float t;

	t = serverkeyfloat("pm_ticrate");
	if (t <= 0)
		t = PM_TICK;
	return t;
};

void() Body_ReadCvars =
{
	pb_cv_delay   = cvar("cl_body_delay");
	pb_cv_extrap  = cvar("cl_body_extrap");
	pb_cv_hermite = cvar("cl_body_hermite");
	pb_cv_raw     = cvar("cl_body_raw");
};

void() Body_RegisterCvars =
{
	registercvar("cl_body_delay",   "0.05");
	registercvar("cl_body_extrap",  "0.03");
	registercvar("cl_body_hermite", "1");
	registercvar("cl_body_raw",     "0");       // debug: newest sample, no interpolation
	registercommand("body_stats");
	registercommand("body_trace");
	Body_ReadCvars();
};

float(entity b) Body_Delay =
{
	return max(pb_cv_delay, 1.5 * b.pb_ivl + 0.02);
};

// The engine's colormod/glowmod byte (sv_ents.c:3927), so a streamed body wears
// exactly the tint the entity path gave it.
vector(vector v) Body_Q32 =
{
	return [bound(0, floor(v_x * 32), 255), bound(0, floor(v_y * 32), 255),
	        bound(0, floor(v_z * 32), 255)] * (1 / 32);
};

float() Body_Predraw =
{
	local float duck, n;
	local vector rgb, org;

	if (!self.pb_n || (spc_hideslot && self.pb_slot == spc_hideslot))
	{
		self.pb_trailok = FALSE;
		return PREDRAW_NEXT;
	}

	org  = self.pb_rorg;
	duck = (self.pb_rfl & PBF_DUCKED) ? 1 : 2;
	if (duck != self.pb_duck)
	{
		self.pb_duck = duck;
		setmodel(self, duck == 1 ? "models/player_duck.iqm" : "models/player.iqm");
	}
	setorigin(self, org);
	self.angles = [0, self.pb_rang_y, 0];

	if (self.pb_lf & PBL_CUSTOM)
		rgb = self.pb_rgb * (1 / 255);
	else
		rgb = Av_PaletteRGB(self.pb_lc);
	if (self.pb_lf & PBL_COLOUR)
		self.colormod = Body_Q32(Av_ColourModRGB(rgb));
	else
		self.colormod = '0 0 0';
	if (self.pb_lf & PBL_GLOW)
		self.glowmod = Body_Q32(Av_GlowModRGB(rgb));
	else
		self.glowmod = Body_Q32('0.032 0.032 0.032');

	if (self.pb_lf & PBL_TRAIL)
	{
		if (self.pb_trailok && !self.pb_snap)
			trailparticles(self.pb_fxtrail, self, self.pb_trail, org);
		self.pb_trail   = org;
		self.pb_trailok = TRUE;
	}
	if (self.pb_lf & PBL_MOTES)
	{
		// A count, not a rate: integrated at 6/s as Av_Dress does.
		self.pb_motacc = self.pb_motacc + 6 * pb_fdt;
		n = floor(self.pb_motacc);
		if (n >= 1)
		{
			self.pb_motacc = self.pb_motacc - n;
			pointparticles(self.pb_fxmote, org + '0 0 32', '0 0 0', n);
		}
	}
	return PREDRAW_AUTOADD;
};

void(entity b) Body_New =
{
	local entity c, first, prev;
	local float i;

	first = world;
	prev  = world;
	for (i = 0; i < PB_RING; i = i + 1)
	{
		c = spawn();
		c.classname = "bodycell";
		if (first)
		{
			prev.pc_next = c;
			c.pc_prev = prev;
		}
		else
			first = c;
		prev = c;
	}
	prev.pc_next  = first;
	first.pc_prev = prev;

	b.classname = "lobbybody";
	b.pb_head   = prev;         // the first push lands on `first`
	b.pb_n      = 0;
	b.drawmask  = MASK_ENGINE;
	b.predraw   = Body_Predraw;
	b.pb_nextbody = pb_list;
	pb_list = b;
	if (pb_tick <= 0)
		pb_tick = Body_TickRate();
	b.pb_ivl = pb_tick;
};

void(entity b) Body_Free =
{
	local entity c, nx, o;
	local float i;

	c = b.pb_head;
	for (i = 0; i < PB_RING; i = i + 1)
	{
		nx = c.pc_next;
		remove(c);
		c = nx;
	}
	b.pb_head = world;

	if (pb_list == b)
		pb_list = b.pb_nextbody;
	else
		for (o = pb_list; o; o = o.pb_nextbody)
			if (o.pb_nextbody == b)
			{
				o.pb_nextbody = b.pb_nextbody;
				break;
			}
	if (pb_tr_ent == b)
		pb_tr_ent = world;
};

void() CSQC_Ent_Remove =
{
	if (self.pb_head)
		Body_Free(self);
	remove(self);
};

entity(entity b, float t) Body_Push =
{
	local entity c;

	c = b.pb_head.pc_next;
	b.pb_head = c;
	if (!b.pb_n)
		b.pb_t0 = t;
	if (b.pb_n < PB_RING)
		b.pb_n = b.pb_n + 1;
	c.pc_t = t;
	return c;
};

// The oldest valid cell's tick.
float(entity b) Body_OldestT =
{
	if (b.pb_n >= PB_RING)
		return b.pb_head.pc_next.pc_t;
	return b.pb_t0;
};

// Everything but the tick.
void(entity d, entity s) Body_Copy =
{
	d.origin   = s.origin;
	d.angles   = s.angles;
	d.velocity = s.velocity;
	d.pc_eye   = s.pc_eye;
	d.pc_fl    = s.pc_fl;
	d.pc_keys  = s.pc_keys;
	d.pc_kraw  = s.pc_kraw;
	d.pc_state = s.pc_state;
	d.pc_track = s.pc_track;
	d.pc_flags = s.pc_flags;
	d.pc_ticks = s.pc_ticks;
};

float() Body_R24 =
{
	local float lo, hi, v;

	lo = readshort();
	hi = readbyte();
	if (lo < 0)
		lo = lo + 65536;
	v = hi * 65536 + lo;
	if (v >= 8388608)
		v = v - 16777216;
	return v;
};

void(entity b) Body_ReadLook =
{
	local float s, lf, lc, tc, r, g, bl, a;
	local entity o;

	s  = readbyte();
	lf = readbyte();
	lc = readbyte();
	tc = readbyte();
	r  = readbyte();
	g  = readbyte();
	bl = readbyte();
	a  = readbyte();

	// A reconnect can briefly leave two bodies claiming one slot: the newest LOOK wins.
	for (o = pb_list; o; o = o.pb_nextbody)
		if (o != b && o.pb_slot == s + 1)
			o.pb_slot = 0;

	b.pb_slot = s + 1;
	b.pb_lf   = lf;
	b.pb_lc   = lc;
	b.pb_tc   = tc;
	b.pb_rgb  = [r, g, bl];
	b.alpha   = a / 255;
	b.pb_fxtrail = 0;
	b.pb_fxmote  = 0;
	if (lf & PBL_TRAIL)
	{
		if (lf & PBL_LONG)
			b.pb_fxtrail = particleeffectnum(sprintf("ftesurf_avtrailL_%g", tc));
		else
			b.pb_fxtrail = particleeffectnum(sprintf("ftesurf_avtrail_%g", tc));
	}
	if (lf & PBL_MOTES)
		b.pb_fxmote = particleeffectnum(sprintf("ftesurf_avmote_%g", lc));
};

// On a sample that advanced the tick.
void(entity b, float t) Body_Clock =
{
	local float os;

	os = cltime - t * pb_tick;
	if (!b.pb_clk)
	{
		b.pb_clk   = TRUE;
		b.pb_bmin0 = os;
		b.pb_bmin1 = os;
		b.pb_bt    = cltime;
		b.pb_o     = os;
		b.pb_rclk  = t * pb_tick - Body_Delay(b);
		b.pb_reval = b.pb_rclk;
		return;
	}

	if (cltime - b.pb_bt >= 0.5)
	{
		b.pb_bmin1 = b.pb_bmin0;
		b.pb_bmin0 = os;
		b.pb_bt    = cltime;
	}
	else if (os < b.pb_bmin0)
		b.pb_bmin0 = os;

	if (fabs(os - b.pb_o) > 0.25 || (b.pb_starved && os - b.pb_o > 2 * pb_tick + 0.01))
	{
		b.pb_bmin0 = os;
		b.pb_bmin1 = os;
		b.pb_o     = os;
		b.pb_rclk  = max(cltime - os - Body_Delay(b), b.pb_reval);
		b.pb_reseed = b.pb_reseed + 1;
		b.pb_rsflag = TRUE;
		return;
	}
	b.pb_o = min(b.pb_bmin0, b.pb_bmin1);
};

// One read per statement: argument evaluation order is not guaranteed.
void(entity b, float spec) Body_ReadPose =
{
	local float lo, ox, oy, oz, pi, ya, ey, pf;
	local float vx, vy, vz, ky, st, tr, fl, tk;
	local float d, t, first, lag, mv, hold;
	local vector no, na;
	local entity c;

	lo = readshort();
	ox = Body_R24();
	oy = Body_R24();
	oz = Body_R24();
	pi = readshort();
	ya = readshort();
	ey = readbyte();
	pf = readbyte();
	vx = 0;  vy = 0;  vz = 0;  ky = 0;
	st = 0;  tr = 0;  fl = 0;  tk = 0;
	if (spec)
	{
		vx = readshort();
		vy = readshort();
		vz = readshort();
		ky = readbyte();
		st = readbyte();
		tr = readbyte();
		fl = Body_R24();
		tk = Body_R24();
	}

	if (lo < 0)
		lo = lo + 65536;
	if (pb_tick <= 0)
		pb_tick = Body_TickRate();

	d = 0;
	if (b.pb_n)
	{
		d = lo - b.pb_lo;
		d = d - 65536 * floor(d / 65536);
		if (d >= 32768)
		{
			b.pb_n   = 0;           // the owner's tick went backwards: start over
			b.pb_clk = FALSE;
		}
	}
	first = !b.pb_n;
	t = first ? lo : b.pb_tnew + d;
	b.pb_lo = lo;

	no = [ox, oy, oz] * (1 / 64);
	na = [pi * (360 / 65536), ya * (360 / 65536), 0];
	c  = b.pb_head;
	// Whole RHS parenthesised: fteqcc parses `x = a && b` as `(x = a) && b`.
	mv = (!first && (no != c.origin || na != c.angles));
	// Leaving a rest: hold the rest pose until the tick before this one.  A
	// newer sample can supersede the one carrying RESUME, so a move after two
	// equal cells (a rest marker, a keepalive) holds too.
	hold = (!first && d > 1 && ((pf & PBF_RESUME)
	       || (mv && b.pb_n > 1 && c.origin == c.pc_prev.origin && c.angles == c.pc_prev.angles)));
	// P5's control build: hold = FALSE;

	if (!first && d == 0)
		c = b.pb_head;              // same tick: a held keepalive, or a warp with no tick
	else
	{
		if (hold)
		{
			c = Body_Push(b, t - 1);
			Body_Copy(c, c.pc_prev);
		}
		c = Body_Push(b, t);
	}

	c.origin = no;
	c.angles = na;
	c.pc_eye = ey * 0.5;
	c.pc_fl  = pf - (pf & PBF_RESUME);
	if (spec)
	{
		c.pc_fl    = c.pc_fl | PC_SPEC;
		c.velocity = [vx, vy, vz];
		c.pc_kraw  = ky;
		c.pc_keys  = (ky & 63) | ((ky & 64) ? FSI_ATTACK : 0);
		c.pc_state = st;
		c.pc_track = tr;
		c.pc_flags = fl;
		c.pc_ticks = tk;
	}
	else
	{
		c.velocity = '0 0 0';
		c.pc_kraw  = 0;
		c.pc_keys  = 0;
		c.pc_state = 0;
		c.pc_track = 0;
		c.pc_flags = 0;
		c.pc_ticks = 0;
	}

	lag = cltime - t * pb_tick - b.pb_o;
	if (first || d > 0)
	{
		b.pb_tnew = t;
		Body_Clock(b, t);
		if (!first)
		{
			b.pb_tks  = b.pb_tks + d;
			b.pb_gapn = b.pb_gapn + 1;
			pb_tk_total = pb_tk_total + d;
			if (d <= 8)
				b.pb_ivl = b.pb_ivl + 0.1 * (d * pb_tick - b.pb_ivl);
		}
	}

	b.pb_rxt = cltime;
	if (!b.pb_rx0t)
		b.pb_rx0t = cltime;
	b.pb_rx = b.pb_rx + 1;
	pb_rx_total = pb_rx_total + 1;

	if (pb_tr_n > 0 && b == pb_tr_ent)
		print(strcat(sprintf("bx %.4f %g %g %.4f", cltime, t, d, first ? 0 : lag),
		             sprintf(" %g %g %g %g\n", pf, spec ? 1 : 0, b.pb_rsflag, mv)));
};

void(float isnew) CSQC_Ent_Update =
{
	local float f;

	if (isnew || !self.pb_head)
		Body_New(self);
	f = readbyte();
	if (f & PB_LOOK)
		Body_ReadLook(self);
	if (f & PB_POSE)
		Body_ReadPose(self, f & PB_SPEC);
};

// Past the newest sample by dt: its velocity, else the step from the cell
// before it continued (angles too, or a turning body stalls its yaw on every
// starved frame).  Into pb_xorg / pb_xang.
vector pb_xorg, pb_xang;
void(entity b, entity a, float dt) Body_Extrap =
{
	local entity p;
	local float g;

	pb_xorg = a.origin;
	pb_xang = a.angles;
	if (a.pc_fl & PC_SPEC)
		pb_xorg = a.origin + a.velocity * dt;
	if (b.pb_n < 2)
		return;
	p = a.pc_prev;
	g = a.pc_t - p.pc_t;
	if (g < 1 || g > 4 || (a.pc_fl & PBF_SERMASK) != (p.pc_fl & PBF_SERMASK))
		return;
	g = 1 + dt / (g * pb_tick);
	if (!(a.pc_fl & PC_SPEC))
		pb_xorg = p.origin + (a.origin - p.origin) * g;
	pb_xang = Interp_View(p.angles, a.angles, g);
};

void(entity b) Body_Eval =
{
	local entity a, nb, c;
	local float k, re, rt, nt, ot, ta, tb, f, held, st, ser, moving;
	local vector org;

	c    = b.pb_head;
	nt   = c.pc_t * pb_tick;
	ot   = Body_OldestT(b) * pb_tick;
	held = c.pc_fl & PBF_HELD;
	st   = b.pb_rsflag ? BT_RESEED : 0;
	b.pb_rsflag = FALSE;

	// Jump when far behind, or when R has left the ring and the target has not:
	// clamped to the oldest cell, R would step with every sample until caught up.
	rt = cltime - b.pb_o - Body_Delay(b);
	if (rt - b.pb_rclk > 0.25 || (b.pb_rclk < ot && rt >= ot))
	{
		b.pb_rclk = rt;
		st = st | BT_JUMP;
	}
	else if (b.pb_rclk - rt > 0.02)
		st = st | BT_HOLD;
	else
		b.pb_rclk = b.pb_rclk + pb_fdt * (1 + bound(-0.05, 5 * (rt - b.pb_rclk), 0.05));

	b.pb_starved = (b.pb_rclk > nt);
	if (b.pb_starved)
		st = st | BT_STARVED;
	re = min(b.pb_rclk, nt + (held ? 0 : pb_cv_extrap));
	if (pb_cv_raw)
	{
		re = nt;
		st = st | BT_RAW;
	}

	// a: the newest cell at or before re; nb: the one after it.
	a  = c;
	nb = world;
	k  = 1;
	while (k < b.pb_n && a.pc_t * pb_tick > re)
	{
		nb = a;
		a  = a.pc_prev;
		k  = k + 1;
	}
	if (a.pc_t * pb_tick > re)
	{
		re = a.pc_t * pb_tick;
		b.pb_under = b.pb_under + 1;
		st = st | BT_UNDER;
	}
	b.pb_reval = re;
	ta = a.pc_t * pb_tick;

	b.pb_rvel = (a.pc_fl & PC_SPEC) ? a.velocity : '0 0 0';
	if (!nb)
	{
		org = a.origin;
		b.pb_rang = a.angles;
		if (re > ta && !held)
		{
			Body_Extrap(b, a, re - ta);
			org = pb_xorg;
			b.pb_rang = pb_xang;
		}
		b.pb_reye = a.pc_eye;
	}
	else
	{
		tb = nb.pc_t * pb_tick;
		f  = (re - ta) / (tb - ta);
		if ((a.pc_fl & PBF_SERMASK) != (nb.pc_fl & PBF_SERMASK))
		{
			// A teleport between them: stay on a until nb is due, then snap.
			org = a.origin;
			b.pb_rang = a.angles;
			b.pb_reye = a.pc_eye;
		}
		else
		{
			if (pb_cv_hermite && (a.pc_fl & nb.pc_fl & PC_SPEC) && nb.pc_t - a.pc_t <= 4
			    && Interp_Fit(a.origin, a.velocity, nb.origin, nb.velocity, tb - ta) == INTERP_HERMITE)
				org = Interp_Hermite(a.origin, a.velocity, nb.origin, nb.velocity, tb - ta, f);
			else
				org = a.origin + (nb.origin - a.origin) * f;
			b.pb_rang = Interp_View(a.angles, nb.angles, f);
			b.pb_reye = a.pc_eye + (nb.pc_eye - a.pc_eye) * f;
			if (a.pc_fl & nb.pc_fl & PC_SPEC)
				b.pb_rvel = a.velocity + (nb.velocity - a.velocity) * f;
		}
	}
	b.pb_rorg   = org;
	b.pb_rfl    = a.pc_fl;
	b.pb_rkeys  = a.pc_keys;
	b.pb_rkraw  = a.pc_kraw;
	b.pb_rstate = a.pc_state;
	b.pb_rtrack = a.pc_track;
	b.pb_rflags = a.pc_flags;
	b.pb_rticks = a.pc_ticks;
	if (a.pc_state == TS_RUNNING && !(a.pc_flags & TF_FROZEN))
	{
		b.pb_rticks = a.pc_ticks + max(0, re / pb_tick - a.pc_t);
		if (nb && (nb.pc_fl & PC_SPEC))
			b.pb_rticks = min(b.pb_rticks, nb.pc_ticks);
	}

	ser = a.pc_fl & PBF_SERMASK;
	b.pb_snap = (b.pb_frames > 0 && ser != b.pb_rser);
	b.pb_rser = ser;
	if (b.pb_snap)
		st = st | BT_SNAP;
	if (held)
		st = st | BT_HELD;
	b.pb_st = st;

	// Late = out of samples while the newest two differ; a rest runs past its
	// keepalives by design.
	moving = FALSE;
	if (b.pb_n > 1)
		moving = (c.origin != c.pc_prev.origin || c.angles != c.pc_prev.angles);
	b.pb_frames = b.pb_frames + 1;
	pb_bf_total = pb_bf_total + 1;
	if (b.pb_starved && moving && !held)
	{
		b.pb_latef = b.pb_latef + 1;
		pb_late_total = pb_late_total + 1;
	}
};

entity(float slot) Body_Find =
{
	local entity b;

	for (b = pb_list; b; b = b.pb_nextbody)
		if (b.pb_n && b.pb_slot == slot + 1)
			return b;
	return world;
};

float(float slot) Body_Has =
{
	return Body_Find(slot) != world;
};

// Seconds since the slot's last sample; -1 without a body.
float(float slot) Body_Age =
{
	local entity b;

	b = Body_Find(slot);
	if (!b)
		return -1;
	return cltime - b.pb_rxt;
};

// FSI_* of the drawn sample; 0 unless this client receives the owner's SPEC.
float(float slot) Body_Keys =
{
	local entity b;

	b = Body_Find(slot);
	if (!b || !(b.pb_rfl & PC_SPEC))
		return 0;
	return b.pb_rkeys;
};

float(float slot, __inout vector org, __inout vector ang, __inout float eye,
      __inout vector vel) Body_Pose =
{
	local entity b;
	local float r;

	b = Body_Find(slot);
	if (!b)
		return 0;
	org = b.pb_rorg;
	ang = b.pb_rang;
	eye = b.pb_reye;
	vel = '0 0 0';
	r = 0;
	if (b.pb_head.pc_fl & PBF_HELD)
		r = r | BP_HELD | BP_LIVE;
	if (cltime - b.pb_rxt <= 1)
		r = r | BP_LIVE;
	if (b.pb_rfl & PC_SPEC)
	{
		r = r | BP_VEL;
		vel = b.pb_rvel;
	}
	if (b.pb_rfl & PBF_DUCKED)
		r = r | BP_DUCKED;
	if (b.pb_rfl & PBF_GROUND)
		r = r | BP_ONGROUND;
	if (b.pb_snap)
		r = r | BP_SNAP;
	return r;
};

// The owner's run clock at the drawn time; 0 unless this client receives SPEC.
float(float slot, __inout float state, __inout float ticks, __inout float track,
      __inout float flags) Body_Run =
{
	local entity b;

	b = Body_Find(slot);
	if (!b || !(b.pb_rfl & PC_SPEC))
		return 0;
	state = b.pb_rstate;
	ticks = b.pb_rticks;
	track = b.pb_rtrack;
	flags = b.pb_rflags;
	return 1;
};

// body_trace with no stream body (lobby_av_stream 0, the control): the engine's
// lerped avatar, and an arrival per engine delta.
void() Body_TraceEngine =
{
	local float i, n, act, mi, dc;
	local vector o, a;

	if (nm_ok)
	{
		dc = getdeltacount(nm_mi_stand) + getdeltacount(nm_mi_duck);
		if (pb_tr_dc && dc > pb_tr_dc)
			print(sprintf("bx %.4f -1 %g 0 0 0 0\n", cltime, dc - pb_tr_dc));
		pb_tr_dc = dc;
	}

	n = getentity(0, GE_MAXENTS);
	for (i = 1; i < n; i = i + 1)
	{
		act = getentity(i, GE_ACTIVE);
		if (!act)
			continue;
		mi = getentity(i, GE_MODELINDEX);
		if ((nm_mi_stand && mi == nm_mi_stand) || (nm_mi_duck && mi == nm_mi_duck))
		{
			o = getentity(i, GE_ORIGIN);
			a = getentity(i, GE_ANGLES);
			print(strcat(sprintf("bt %.4f 0 %.3f %.3f %.3f %.3f %.3f", cltime, o_x, o_y, o_z, a_y, a_x),
			             " 0 0 0 0 -1 0\n"));
			return;
		}
	}
};

void() Body_Trace =
{
	local entity b;

	if (pb_tr_n <= 0)
		return;
	pb_tr_n = pb_tr_n - 1;

	b = pb_tr_ent;
	if (!b)
	{
		if (pb_tr_slot >= 0)
			b = Body_Find(pb_tr_slot);
		else
			for (b = pb_list; b; b = b.pb_nextbody)
				if (b.pb_n)
					break;
		pb_tr_ent = b;
	}
	if (!b)
	{
		Body_TraceEngine();
		return;
	}
	print(strcat(sprintf("bt %.4f %.3f %.3f %.3f %.3f %.3f %.3f", cltime, b.pb_reval / pb_tick,
	                     b.pb_rorg_x, b.pb_rorg_y, b.pb_rorg_z, b.pb_rang_y, b.pb_rang_x),
	             sprintf(" %.2f %g %g %g %g %g\n", b.pb_reye, b.pb_st, b.pb_rkeys, b.pb_rkraw,
	                     b.pb_slot - 1, b.pb_rfl)));
};

// CSQC_UpdateView, after Ghost_Frame and before the spectate camera and addentities.
void() Body_Frame =
{
	local entity b;
	local float n;

	pb_tick = Body_TickRate();
	pb_fdt  = cltime - pb_ftime;
	if (pb_fdt < 0)
		pb_fdt = 0;
	if (pb_fdt > 1)
		pb_fdt = 1;
	pb_ftime = cltime;
	Body_ReadCvars();

	n = 0;
	for (b = pb_list; b; b = b.pb_nextbody)
	{
		if (!b.pb_n)
			continue;
		Body_Eval(b);
		n = n + 1;
	}
	pb_nbodies = n;
	Body_Trace();
};

void() Body_Stats =
{
	local entity b;
	local float span;

	print(sprintf("body: cltime %.3f, %g bodies, tick %g, delay %g extrap %g raw %g\n",
	              cltime, pb_nbodies, pb_tick, pb_cv_delay, pb_cv_extrap, pb_cv_raw));
	for (b = pb_list; b; b = b.pb_nextbody)
	{
		span = cltime - b.pb_rx0t;
		print(sprintf("bs slot %g rx %g rate %.2f gap %.3f ivl %.4f D %.4f\n",
		              b.pb_slot - 1, b.pb_rx, span > 0 ? b.pb_rx / span : 0,
		              b.pb_gapn ? b.pb_tks / b.pb_gapn : 0, b.pb_ivl, Body_Delay(b)));
		print(sprintf("bs slot %g frames %g late %g reseed %g under %g age %.3f\n",
		              b.pb_slot - 1, b.pb_frames, b.pb_latef, b.pb_reseed, b.pb_under,
		              cltime - b.pb_rxt));
	}
};

float(string cmd) Body_ConsoleCommand =
{
	tokenize(cmd);

	if (argv(0) == "body_stats")
	{
		Body_Stats();
		return TRUE;
	}
	if (argv(0) == "body_trace")
	{
		// body_trace <slot|-1 the first body> <frames>
		pb_tr_slot = (argv(1) == "") ? -1 : stof(argv(1));
		pb_tr_n    = (argv(2) == "") ? 600 : stof(argv(2));
		pb_tr_ent  = world;
		pb_tr_dc   = 0;
		print(sprintf("body_trace: slot %g, %g frames\n", pb_tr_slot, pb_tr_n));
		return TRUE;
	}
	return FALSE;
};
