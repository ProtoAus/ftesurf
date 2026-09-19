/*
===========================================================================
  sv_pose.qc -- the lobby pose stream.  Patch 383.

  With lobby_av_stream 1 each avatar is a CSQC entity: Pose_Capture quantizes
  the owner's pose once per packet (PlayerPostThink) and Pose_Send writes the
  stored sample to each viewer.  client/cl_body.qc reads it.  Clients without
  CSQC still get the engine entity, mirrored at 15 Hz by Lobby_AvatarPose.

  WIRE (MSG_ENTITY).  Every short is written signed; q24 is a signed 24-bit
  value as WriteShort(lo) + WriteByte(hi) (Pose_W24).

    header  byte   PB_POSE | PB_LOOK | PB_SPEC.  0x80 reserved: a type byte
                   follows (nothing sends it yet).  0 = an empty update: a
                   FALSE return would make the engine send a REMOVE.
    LOOK    8 B    slot (num_for_edict(owner) - 1), lf (PBL_*), lc (palette
                   index), trail colour, worn r g b 0..255, alpha * 255
    POSE    17 B   short tick (run_movetick mod 65536), q24 x y z (1/64 u),
                   short pitch, short yaw (v_angle, 65536/360 per degree),
                   byte eye (view_ofs_z * 2), byte pf (PBF_*)
    SPEC    15 B   short vx vy vz (1 u/s), byte keys (SV_RecKeys & 63, 64 =
                   attack), byte run_t_state, byte run_t_track,
                   q24 run_t_flags, q24 run_t_ticks.  Only to viewers whose
                   pb_watch is the owner.

  A sample is published (copied to pb_q*, SendFlags set) on a teleport, a
  held-flag change, every moved tick while spectated, every moved tick up to
  the pb_capticks gap otherwise, and while unchanged as one rest marker then a
  keepalive every POSE_KEEPALIVE s of wall time -- also while held, when no
  tick moves, so no viewer extrapolates a held body.
===========================================================================
*/

#define PB_POSE 1
#define PB_LOOK 2
#define PB_SPEC 4

#define PBF_DUCKED  1
#define PBF_GROUND  2
#define PBF_NOCLIP  4
#define PBF_SER     8       // teleport serial * 8, three bits (8..56)
#define PBF_HELD    64      // run_pmhold, a save-lock hold or MOVETYPE_NONE
#define PBF_RESUME  128     // first moved sample after a rest

#define PBL_COLOUR  1       // lobby_av_colors
#define PBL_TRAIL   2       // lobby_fx after the lobby_av_fxmax cap
#define PBL_MOTES   4
#define PBL_GLOW    8
#define PBL_LONG    16
#define PBL_CUSTOM  32      // worn rgb is a lobbyrgb triple, not palette lc

#define POSE_KEEPALIVE 0.5

// On the avatar: capture state.
.float  pb_ct;              // run_movetick at the last capture
.vector pb_corg;
.vector pb_cvel;
.float  pb_ser;             // teleport serial, 0..7
.float  pb_px;              // run_portalx at the last capture
// ...the published sample.
.float  pb_pubt;            // run_movetick it was taken at
.float  pb_kat;             // server time it was published
.float  pb_rest;            // it repeats the pose before it
.float  pb_held;            // its PBF_HELD
.vector pb_q0;              // [short tick, short pitch, short yaw]
.vector pb_qo;              // origin * 64, integers
.vector pb_q1;              // [eye byte, pf, keys byte]
.vector pb_qv;              // velocity, integers
.vector pb_qr;              // [state, track, flags]
.float  pb_qt;              // run_t_ticks
// ...the appearance last sent.
.vector pb_lk1;             // [slot, lf, lc]
.vector pb_lk2;             // [trail colour, alpha byte, 0]
.vector pb_lkc;             // worn rgb, bytes

// On the player.
.float  pb_specn;           // viewers spectating this player, Pose_Frame
.entity pb_dwatch;          // developer `cmd pose_watch`: pb_watch without Patch 382

float pb_capticks;          // minimum published gap, ticks
float pb_nav;               // streaming avatars
// Counters for `cmd pose_stats`, per map.
float pb_nsend, pb_nbytes, pb_npose, pb_bpose, pb_nspec, pb_bspec;
float pb_nlook, pb_nempty;
float pb_npub, pb_nka, pb_ntp, pb_nheld;

// The candidate sample, filled by Pose_Quant.
vector pose_n0, pose_no, pose_n1, pose_nv, pose_nr;
float  pose_nt;

float(entity p) Pose_Tick =
{
	if (p.run_movetickrate > 0)
		return p.run_movetickrate;
	if (run_t_tick > 0)
		return run_t_tick;
	return PM_TICK;
};

// Degrees to a signed short, 65536 per turn.
float(float a) Pose_QAng =
{
	local float v;

	v = rint(a * (65536 / 360));
	return v - 65536 * floor((v + 32768) / 65536);
};

void(float v) Pose_W24 =
{
	local float hi, lo;

	v = bound(-8388608, rint(v), 8388607);
	if (v < 0)
		v = v + 16777216;
	hi = floor(v / 65536);
	lo = v - hi * 65536;
	if (lo >= 32768)
		lo = lo - 65536;
	WriteShort(MSG_ENTITY, lo);
	WriteByte(MSG_ENTITY, hi);
};

float(entity p) Pose_Held =
{
	return p.run_pmhold || p.rec_sl_hold || p.movetype == MOVETYPE_NONE;
};

// Quantize p into pose_n*; TRUE when the drawn pose differs from the published one.
float(entity av, entity p, float held) Pose_Quant =
{
	local float t, pf, k;

	t = p.run_movetick - 65536 * floor(p.run_movetick / 65536);
	if (t >= 32768)
		t = t - 65536;
	// Held: angles stay as they entered the hold.  No tick moves, so a turn
	// could only arrive as a keepalive's 2 Hz same-tick snap.
	if (held && av.pb_held)
		pose_n0 = [t, av.pb_q0_y, av.pb_q0_z];
	else
		pose_n0 = [t, Pose_QAng(p.v_angle_x), Pose_QAng(p.v_angle_y)];
	pose_no = [rint(p.origin_x * 64), rint(p.origin_y * 64), rint(p.origin_z * 64)];

	pf = av.pb_ser * PBF_SER;
	if (p.pmove_flags & PMF_DUCKED)     pf = pf | PBF_DUCKED;
	if (p.flags & FL_ONGROUND)          pf = pf | PBF_GROUND;
	if (p.movetype == MOVETYPE_NOCLIP)  pf = pf | PBF_NOCLIP;
	if (held)                           pf = pf | PBF_HELD;

	k = SV_RecKeys(p);
	pose_n1 = [bound(0, rint(p.view_ofs_z * 2), 255), pf,
	           (k & 63) | ((k & FSI_ATTACK) ? 64 : 0)];
	pose_nv = [bound(-32767, rint(p.velocity_x), 32767),
	           bound(-32767, rint(p.velocity_y), 32767),
	           bound(-32767, rint(p.velocity_z), 32767)];
	pose_nr = [bound(0, p.run_t_state, 255), bound(0, p.run_t_track, 255), p.run_t_flags];
	pose_nt = p.run_t_ticks;

	if (pose_no != av.pb_qo)
		return TRUE;
	if (pose_n0_y != av.pb_q0_y || pose_n0_z != av.pb_q0_z)
		return TRUE;
	if (pose_n1_x != av.pb_q1_x)
		return TRUE;
	return pf != (av.pb_q1_y - (av.pb_q1_y & PBF_RESUME));
};

void(entity av, entity p, float resume) Pose_Publish =
{
	av.pb_q0 = pose_n0;
	av.pb_qo = pose_no;
	av.pb_q1 = pose_n1;
	if (resume)
		av.pb_q1_y = av.pb_q1_y | PBF_RESUME;
	av.pb_qv = pose_nv;
	av.pb_qr = pose_nr;
	av.pb_qt = pose_nt;
	av.pb_pubt = p.run_movetick;
	av.pb_kat = time;
	av.pb_held = (pose_n1_y & PBF_HELD) ? TRUE : FALSE;
	av.SendFlags = av.SendFlags | PB_POSE;
	if (p.pb_specn > 0)
		av.SendFlags = av.SendFlags | PB_SPEC;
	pb_npub = pb_npub + 1;
};

// Once per owner packet, after the timer (PlayerPostThink).  Patch 382 also
// calls it from the held branch, where no tick moves.
void(entity p) Pose_Capture =
{
	local entity av;
	local float d, tick, tp, held, heldchg, ka, changed, force, due;
	local vector pred;

	av = p.lobby_av;
	if (!av || !av.SendEntity)
		return;

	tick = Pose_Tick(p);
	d = p.run_movetick - av.pb_ct;
	tp = FALSE;
	if (d >= 0)
	{
		// 64 u plus the whole predicted step: a full stop against a wall, or a
		// pusher carrying the player between two zero-tick packets, is not a teleport.
		pred = av.pb_corg + av.pb_cvel * (d * tick);
		if (vlen(p.origin - pred) > 64 + vlen(av.pb_cvel) * d * tick)
			tp = TRUE;
	}
	else if (vlen(p.origin - av.pb_corg) > 1)
		tp = TRUE;              // the tick went backwards
	if (p.run_portalx != av.pb_px)
		tp = TRUE;

	av.pb_ct   = p.run_movetick;
	av.pb_corg = p.origin;
	av.pb_cvel = p.velocity;
	av.pb_px   = p.run_portalx;
	if (tp)
	{
		av.pb_ser = (av.pb_ser + 1) & 7;
		pb_ntp = pb_ntp + 1;
	}

	held    = Pose_Held(p);
	heldchg = (held != av.pb_held);     // P12's control build: heldchg = FALSE
	ka      = (time - av.pb_kat >= POSE_KEEPALIVE);
	if (d <= 0 && !tp && !heldchg && !ka)
		return;

	changed = Pose_Quant(av, p, held);
	force   = tp || heldchg || (p.pb_specn > 0 && d > 0);
	due     = (p.run_movetick - av.pb_pubt >= pb_capticks);

	if (changed)
	{
		if (!force && !due && !av.pb_rest && !held)
			return;
	}
	else if (!force)
	{
		// Held: no tick moves, so `due` never comes; the keepalive is the clock.
		if (av.pb_rest || held)
		{
			if (!ka)
				return;
			pb_nka = pb_nka + 1;
		}
		else if (!due)
			return;
	}
	if (heldchg)
		pb_nheld = pb_nheld + 1;

	Pose_Publish(av, p, changed && av.pb_rest);
	av.pb_rest = !changed;
};

// First sample, published at once (spawn, stream switched on).
void(entity av, entity p) Pose_Seed =
{
	local float held;

	av.pb_ct   = p.run_movetick;
	av.pb_corg = p.origin;
	av.pb_cvel = p.velocity;
	av.pb_px   = p.run_portalx;
	av.pb_held = FALSE;         // live angles: pb_q0 may predate a stream switch-off
	held = Pose_Held(p);
	Pose_Quant(av, p, held);
	Pose_Publish(av, p, FALSE);
	av.pb_rest = FALSE;
};

// Appearance, sent on change only.  Called at spawn, from the 1 Hz colour pass
// and on an alpha change.
void(entity av, entity p) Pose_Look =
{
	local float lf, tc;
	local vector k1, k2, kc;

	if (!av.SendEntity)
		return;

	lf = 0;
	if (lobby_colors)                   lf = lf | PBL_COLOUR;
	if (p.lobby_fx & FS_AVFX_TRAIL)     lf = lf | PBL_TRAIL;
	if (p.lobby_fx & FS_AVFX_MOTES)     lf = lf | PBL_MOTES;
	if (p.lobby_fx & FS_AVFX_GLOW)      lf = lf | PBL_GLOW;
	if (p.lobby_fx & FS_AVFX_TRAILONG)  lf = lf | PBL_LONG;
	if (p.lobby_custom)                 lf = lf | PBL_CUSTOM;

	tc = p.lobby_trailc;
	if (tc < 1 || tc > FS_AVCOLOURS)
		tc = p.lobby_colour;

	k1 = [bound(0, num_for_edict(p) - 1, 255), lf, bound(0, p.lobby_colour, 255)];
	k2 = [bound(0, tc, 255), bound(0, rint(av.alpha * 255), 255), 0];
	kc = [bound(0, rint(p.lobby_rgb_x * 255), 255),
	      bound(0, rint(p.lobby_rgb_y * 255), 255),
	      bound(0, rint(p.lobby_rgb_z * 255), 255)];
	if (k1 == av.pb_lk1 && k2 == av.pb_lk2 && kc == av.pb_lkc)
		return;
	av.pb_lk1 = k1;
	av.pb_lk2 = k2;
	av.pb_lkc = kc;
	av.SendFlags = av.SendFlags | PB_LOOK;
};

// The avatar's SendEntity.  Always TRUE: FALSE sends a REMOVE.
float(entity to, float sf) Pose_Send =
{
	local entity p;
	local float f, n;

	p = self.lobby_owner;
	f = sf & (PB_POSE | PB_LOOK);
	if (to && p && (sf & (PB_POSE | PB_SPEC)))
	if (to.pb_watch == p || to.pb_dwatch == p)
		f = f | PB_POSE | PB_SPEC;

	WriteByte(MSG_ENTITY, f);
	n = 1;
	if (f & PB_LOOK)
	{
		WriteByte(MSG_ENTITY, self.pb_lk1_x);
		WriteByte(MSG_ENTITY, self.pb_lk1_y);
		WriteByte(MSG_ENTITY, self.pb_lk1_z);
		WriteByte(MSG_ENTITY, self.pb_lk2_x);
		WriteByte(MSG_ENTITY, self.pb_lkc_x);
		WriteByte(MSG_ENTITY, self.pb_lkc_y);
		WriteByte(MSG_ENTITY, self.pb_lkc_z);
		WriteByte(MSG_ENTITY, self.pb_lk2_y);
		n = n + 8;
		pb_nlook = pb_nlook + 1;
	}
	if (f & PB_POSE)
	{
		WriteShort(MSG_ENTITY, self.pb_q0_x);
		Pose_W24(self.pb_qo_x);
		Pose_W24(self.pb_qo_y);
		Pose_W24(self.pb_qo_z);
		WriteShort(MSG_ENTITY, self.pb_q0_y);
		WriteShort(MSG_ENTITY, self.pb_q0_z);
		WriteByte(MSG_ENTITY, self.pb_q1_x);
		WriteByte(MSG_ENTITY, self.pb_q1_y);
		n = n + 17;
	}
	if (f & PB_SPEC)
	{
		WriteShort(MSG_ENTITY, self.pb_qv_x);
		WriteShort(MSG_ENTITY, self.pb_qv_y);
		WriteShort(MSG_ENTITY, self.pb_qv_z);
		WriteByte(MSG_ENTITY, self.pb_q1_z);
		WriteByte(MSG_ENTITY, self.pb_qr_x);
		WriteByte(MSG_ENTITY, self.pb_qr_y);
		Pose_W24(self.pb_qr_z);
		Pose_W24(self.pb_qt);
		n = n + 15;
	}

	pb_nsend  = pb_nsend + 1;
	pb_nbytes = pb_nbytes + n;
	if (f == PB_POSE)
	{
		pb_npose = pb_npose + 1;
		pb_bpose = pb_bpose + n;
	}
	else if (f == (PB_POSE | PB_SPEC))
	{
		pb_nspec = pb_nspec + 1;
		pb_bspec = pb_bspec + n;
	}
	else if (!f)
		pb_nempty = pb_nempty + 1;
	return TRUE;
};

// StartFrame, after Lobby_Frame: spectator counts and the publish gap.
void() Pose_Frame =
{
	local entity p, w, av;
	local float n, spec, rate, budget, tick, c;

	pb_nav = 0;
	if (!lobby_on || !lobby_avatars)
		return;

	p = find(world, classname, "player");
	while (p)
	{
		p.pb_specn = 0;
		if (p.pb_dwatch)
		if (p.pb_dwatch.classname != "player" || !p.pb_dwatch.lobby_av)
			p.pb_dwatch = world;
		p = find(p, classname, "player");
	}
	spec = 0;
	p = find(world, classname, "player");
	while (p)
	{
		w = p.pb_watch;
		if (!w)
			w = p.pb_dwatch;
		if (w && w != p)
		{
			w.pb_specn = w.pb_specn + 1;
			spec = 1;
		}
		p = find(p, classname, "player");
	}

	n = 0;
	av = find(world, classname, "lobbyavatar");
	while (av)
	{
		if (av.SendEntity)
			n = n + 1;
		av = find(av, classname, "lobbyavatar");
	}
	pb_nav = n;

	// Whole ticks.  The budget is one viewer's downstream: every other body's
	// 20 B update, plus the watched one's 15 B SPEC when anyone spectates.
	tick = run_t_tick;
	if (tick <= 0)
		tick = PM_TICK;
	rate   = cvar("lobby_av_rate");
	budget = cvar("lobby_av_budget");
	c = 1;
	if (rate > 0)
		c = max(c, ceil(1 / (rate * tick) - 0.05));
	if (budget > 0 && n > 1)
		c = max(c, ceil(((n - 1) * 20 + spec * 15) / (budget * tick)));
	pb_capticks = c;
};

// Client commands: `pose_stats [reset]`, and (developer) `pose_watch <n>`:
// n = entnum of the player to receive SPEC for, -1 the first other player, 0 off.
float(entity e, string c) Pose_Command =
{
	local float n;
	local entity t;

	if (c == "pose_stats")
	{
		if (argv(1) == "reset")
		{
			pb_nsend = 0;  pb_nbytes = 0;  pb_npose = 0;  pb_bpose = 0;
			pb_nspec = 0;  pb_bspec = 0;   pb_nlook = 0;  pb_nempty = 0;
			pb_npub = 0;   pb_nka = 0;     pb_ntp = 0;    pb_nheld = 0;
		}
		sprint(e, PRINT_HIGH, sprintf("pose: stream %g avatars %g capticks %g budget %g rate %g\n",
		       cvar("lobby_av_stream"), pb_nav, pb_capticks,
		       cvar("lobby_av_budget"), cvar("lobby_av_rate")));
		sprint(e, PRINT_HIGH, sprintf("pose: publish %g keepalive %g teleport %g held %g\n",
		       pb_npub, pb_nka, pb_ntp, pb_nheld));
		sprint(e, PRINT_HIGH, sprintf("pose: send %g bytes %g look %g empty %g\n",
		       pb_nsend, pb_nbytes, pb_nlook, pb_nempty));
		sprint(e, PRINT_HIGH, sprintf("pose: pose-only %g avg %.2f B, pose+spec %g avg %.2f B\n",
		       pb_npose, pb_npose ? pb_bpose / pb_npose : 0,
		       pb_nspec, pb_nspec ? pb_bspec / pb_nspec : 0));
		return TRUE;
	}

	if (c == "pose_watch")
	{
		if (!cvar("developer"))
		{
			sprint(e, PRINT_HIGH, "pose_watch: developer only\n");
			return TRUE;
		}
		n = stof(argv(1));
		t = world;
		if (n < 0)
		{
			t = find(world, classname, "player");
			while (t && (t == e || !t.lobby_av))
				t = find(t, classname, "player");
		}
		else if (n > 0)
			t = edict_num(n);
		if (t && (t.classname != "player" || !t.lobby_av))
			t = world;
		e.pb_dwatch = t;
		sprint(e, PRINT_HIGH, sprintf("pose_watch: %g\n", t ? num_for_edict(t) : 0));
		return TRUE;
	}
	return FALSE;
};
