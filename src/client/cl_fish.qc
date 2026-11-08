/*
  cl_fish.qc -- P1436: func_fish_pool's fish, simulated here (Lex: decorative motion is client-side).

  fish.cpp in full: each pool spawns fish_count fish at its origin; CFishPool::Update runs every 0.1 s --
  line-of-sight lists every 0.5 s, then CFish::Update: Avoid (two feelers, the pool's max_range), FlockTo the
  visible fish and the pool centre, turn rate capped by speed, speed eased to calm or panic, the radial part
  of the velocity dropped at the edge.  The fish swim level at the pool origin's height.  The step's move
  (MOVETYPE_FLY at that velocity, stopped by the world) is taken at the end of the step; the position the
  client "receives" is sampled at its start, as m_x/m_y are, on SendPropFloat's 7-bit grid (-255 + k * 510/127;
  angles k * 360/127).  c_fish.cpp then draws each fish tracking that with its spring (sub-stepped to stay
  stable through a hitch) and wiggle, which is what makes them swim rather than slide.

  Not as Source: fish never die (no damage); the local player alone panics them, within 75 units of the
  predicted origin (Touch and player_footstep's quiet range) -- each client runs its own fish, so other players
  do not; pools farther than FISH_SIMFAR from the eye rest.
*/

#define FISH_MAX      512       // the library's most is 240 (surf_garden_css)
#define FPOOL_MAX     64        // ...and 56 pools (surf_sh)
#define FISH_STEP     0.1
#define FISH_SIMFAR   3000
#define FISH_QPOS     (510 / 127)   // SendPropFloat 7 bits over -255..255
#define FISH_QANG     (360 / 127)
#define FISH_ERRN     20
#define FISH_SUB      0.05      // the tracking spring's longest step (unstable past ~0.125 s)

vector *fp_org;
float  *fp_range;
float  *fp_first;
float  *fp_n;
float  *fp_vis;                 // per pool: n*n line-of-sight flags, from fp_visofs
float  *fp_visofs;
float  *fp_vist;
float  fp_n_;

entity *fs_e;
vector *fs_pos;                 // the "server" position (fish.cpp)
vector *fs_act;                 // what the client received: fs_pos at the step's start, quantised
float  *fs_actang;
vector *fs_link;                // where the entity was last linked
float  *fs_pool;
float  *fs_ang;
float  *fs_dang;
float  *fs_speed;
float  *fs_want;
float  *fs_calm;
float  *fs_panic;
float  *fs_cw;
float  *fs_avoid;
float  *fs_tdisp;
float  *fs_tgo;
float  *fs_tmove;
float  *fs_tpanic;
float  *fs_tturn;
vector *fs_lpos;                // c_fish.cpp's local position and velocity
vector *fs_lvel;
float  *fs_wigt0;
float  *fs_wigph;
float  *fs_wigrt;
float  *fs_err;                 // FISH_ERRN error samples each
float  *fs_errn;
float  *fs_erri;
float  fs_n;
float  fish_tacc, fish_last, fish_dbgt, fish_started;
float  vbsp_fish_pools, vbsp_fish_skip;

void() Fish_Alloc =
{
	if (fp_org)
		return;
	fp_org = memalloc(sizeof(vector) * FPOOL_MAX);
	fp_range = memalloc(sizeof(float) * FPOOL_MAX);
	fp_first = memalloc(sizeof(float) * FPOOL_MAX);
	fp_n = memalloc(sizeof(float) * FPOOL_MAX);
	fp_visofs = memalloc(sizeof(float) * FPOOL_MAX);
	fp_vist = memalloc(sizeof(float) * FPOOL_MAX);
	fp_vis = memalloc(sizeof(float) * FPOOL_MAX * 400);     // 20 fish a pool squared; more are capped
	fs_e = memalloc(sizeof(entity) * FISH_MAX);
	fs_pos = memalloc(sizeof(vector) * FISH_MAX);
	fs_act = memalloc(sizeof(vector) * FISH_MAX);
	fs_actang = memalloc(sizeof(float) * FISH_MAX);
	fs_link = memalloc(sizeof(vector) * FISH_MAX);
	fs_pool = memalloc(sizeof(float) * FISH_MAX);
	fs_ang = memalloc(sizeof(float) * FISH_MAX);
	fs_dang = memalloc(sizeof(float) * FISH_MAX);
	fs_speed = memalloc(sizeof(float) * FISH_MAX);
	fs_want = memalloc(sizeof(float) * FISH_MAX);
	fs_calm = memalloc(sizeof(float) * FISH_MAX);
	fs_panic = memalloc(sizeof(float) * FISH_MAX);
	fs_cw = memalloc(sizeof(float) * FISH_MAX);
	fs_avoid = memalloc(sizeof(float) * FISH_MAX);
	fs_tdisp = memalloc(sizeof(float) * FISH_MAX);
	fs_tgo = memalloc(sizeof(float) * FISH_MAX);
	fs_tmove = memalloc(sizeof(float) * FISH_MAX);
	fs_tpanic = memalloc(sizeof(float) * FISH_MAX);
	fs_tturn = memalloc(sizeof(float) * FISH_MAX);
	fs_lpos = memalloc(sizeof(vector) * FISH_MAX);
	fs_lvel = memalloc(sizeof(vector) * FISH_MAX);
	fs_wigt0 = memalloc(sizeof(float) * FISH_MAX);
	fs_wigph = memalloc(sizeof(float) * FISH_MAX);
	fs_wigrt = memalloc(sizeof(float) * FISH_MAX);
	fs_err = memalloc(sizeof(float) * FISH_MAX * FISH_ERRN);
	fs_errn = memalloc(sizeof(float) * FISH_MAX);
	fs_erri = memalloc(sizeof(float) * FISH_MAX);
};

float(float a, float b) Fish_Rand = { return a + random() * (b - a); };

// SendPropFloat's 7 bits over -255..255: the nearest of -255 + k * 510/127.
float(float x) Fish_Q = { return -255 + rint((bound(-255, x, 255) + 255) / FISH_QPOS) * FISH_QPOS; };

void(float i) Fish_Panic =
{
	fs_tpanic[i] = time + Fish_Rand(5, 15);
	fs_tmove[i] = time + Fish_Rand(10, 20);
	fs_want[i] = fs_panic[i];
};

// CFish::FlockTo; o < 0 flocks to the pool centre.
void(float i, float o, float amount) Fish_FlockTo =
{
	local vector to, fw, pp, rel;
	local float range, maxr, turn, side, power, p;
	if (time < fs_tdisp[i])
		return;
	p = fs_pool[i];
	maxr = (o >= 0) ? 100 : 300;
	to = ((o >= 0) ? fs_pos[o] : fp_org[p]) - fs_pos[i];
	range = vlen(to);
	if (range > 0)
		to = to * (1 / range);
	if (range > maxr)
		return;
	fw = [cos(fs_ang[i] * (M_PI / 180)), sin(fs_ang[i] * (M_PI / 180)), 0];
	pp = [-fw_y, fw_x, 0];
	if (o >= 0 && range < 25)
	{	// close and closing: avoid
		rel = fw * -fs_speed[i];
		rel = rel + [cos(fs_ang[o] * (M_PI / 180)), sin(fs_ang[o] * (M_PI / 180)), 0] * fs_speed[o];
		if (to * rel < 0)
		{
			if (pp * to > 0)
				fs_dang[i] = fs_dang[i] - 5 * (1 - range / 25);
			else
				fs_dang[i] = fs_dang[i] + 5 * (1 - range / 25);
			return;
		}
	}
	turn = 1 - fw * to;
	side = (pp * to > 1) ? 1 : -1;      // as written in fish.cpp: a dot of unit vectors is never > 1
	if (turn > 1)
		side = fs_cw[i] ? 1 : -1;
	power = 1 - range / maxr;
	fs_dang[i] = fs_dang[i] + amount * 0.7 * power * side * turn;
};

// CFish::Avoid: 0 (clear) to 1 (about to hit something).
float(float i) Fish_Avoid =
{
	local vector to, fw, pp, o;
	local float p, rd, ld;
	p = fs_pool[i];
	o = fs_pos[i];
	fw = [cos(fs_ang[i] * (M_PI / 180)), sin(fs_ang[i] * (M_PI / 180)), 0];
	pp = [-fw_y, fw_x, 0];
	to = fp_org[p] - o;
	if (vlen(to) > fp_range[p] - 20)
	{
		if (to * fw < 0)
			fs_dang[i] = fs_dang[i] + (fs_cw[i] ? -100 : 100);
		return 1;
	}
	rd = ld = 0;
	traceline(o, o + (fw + pp * 0.2) * fs_avoid[i], MOVE_NOMONSTERS, world);
	if (trace_fraction < 1)
		rd = 1 - trace_fraction;
	traceline(o, o + (fw - pp * 0.2) * fs_avoid[i], MOVE_NOMONSTERS, world);
	if (trace_fraction < 1)
		ld = 1 - trace_fraction;
	if (fs_cw[i])
	{
		if (rd > 0)
			fs_dang[i] = fs_dang[i] - 100 * rd;
		else
			fs_dang[i] = fs_dang[i] + 100 * ld;
	}
	else
	{
		if (ld > 0)
			fs_dang[i] = fs_dang[i] + 100 * ld;
		else
			fs_dang[i] = fs_dang[i] - 100 * rd;
	}
	return max(ld, rd);
};

// The velocity fish.cpp ends its Update with: forward at its speed, nothing outward at the edge.
vector(float i) Fish_Vel =
{
	local vector fw, vel, d, toc, pp;
	local float p;
	p = fs_pool[i];
	fw = [cos(fs_ang[i] * (M_PI / 180)), sin(fs_ang[i] * (M_PI / 180)), 0];
	vel = fw * fs_speed[i];
	d = fs_pos[i] - fp_org[p];
	if (vlen(d) > fp_range[p] - 5)
	{
		toc = -d;
		if (toc * vel < 0)
		{
			toc = normalize(toc);
			pp = [-toc_y, toc_x, 0];
			vel = pp * (pp * vel);
		}
	}
	return vel;
};

// CFishPool::Update for pool p: one 0.1 s step, then the step's move.
void(float p) Fish_PoolStep =
{
	local float a, b, n, i, o, danger, maxch, ofs;
	local vector rel, vel, me;
	n = fp_n[p];
	a = fp_first[p];
	ofs = fp_visofs[p];
	me = pmove_org;
	if (time >= fp_vist[p])
	{	// line of sight, symmetric, every 0.5 s
		fp_vist[p] = time + 0.5;
		for (i = 0; i < n; i = i + 1)
		{
			fp_vis[ofs + i * n + i] = 0;
			for (o = i + 1; o < n; o = o + 1)
			{
				traceline(fs_pos[a + i], fs_pos[a + o], MOVE_NOMONSTERS, world);
				b = (trace_fraction >= 1);
				fp_vis[ofs + i * n + o] = b;
				fp_vis[ofs + o * n + i] = b;
			}
		}
	}
	for (b = 0; b < n; b = b + 1)
	{
		i = a + b;
		rel = fs_pos[i] - fp_org[p];                // m_x, m_y at the top of Update
		fs_act[i] = fp_org[p] + [Fish_Q(rel_x), Fish_Q(rel_y), 0];
		fs_actang[i] = rint((fs_ang[i] - 360 * floor(fs_ang[i] / 360)) / FISH_QANG) * FISH_QANG;
		if (vlen(me - fs_pos[i]) < 75)
			Fish_Panic(i);              // Touch / player_footstep (quiet range)
		if (time > fs_tturn[i])
		{
			fs_tturn[i] = time + Fish_Rand(10, 30);
			fs_cw[i] = !fs_cw[i];
		}
		if (fs_tpanic[i] > time)
			fs_want[i] = fs_panic[i];
		else if (fs_tmove[i] > time)
			fs_want[i] = fs_calm[i];
		else if (time > fs_tgo[i])
		{
			fs_tgo[i] = time + Fish_Rand(10, 60);
			fs_tmove[i] = time + Fish_Rand(2, 10);
			fs_want[i] = fs_calm[i];
		}
		danger = Fish_Avoid(i);
		for (o = 0; o < n; o = o + 1)
			if (fp_vis[ofs + b * n + o])
				Fish_FlockTo(i, a + o, 1 - danger);
		Fish_FlockTo(i, -1, 1 - danger);
		maxch = (25 + 175 * (fs_speed[i] / fs_panic[i])) * FISH_STEP;
		fs_ang[i] = fs_ang[i] + bound(-maxch, fs_dang[i], maxch);
		fs_dang[i] = 0;
		fs_speed[i] = fs_speed[i] + 2 * (fs_want[i] - fs_speed[i]) * FISH_STEP;
		if (time > fs_tmove[i])
			fs_want[i] = max(0, fs_want[i] - FISH_STEP);
	}
	for (b = 0; b < n; b = b + 1)
	{	// MOVETYPE_FLY over the step, stopped by the world
		i = a + b;
		vel = Fish_Vel(i);
		if (vel != '0 0 0')
		{
			traceline(fs_pos[i], fs_pos[i] + vel * FISH_STEP, MOVE_NOMONSTERS, world);
			fs_pos[i] = trace_endpos;
		}
	}
};

// Steps the pools, then poses each fish as c_fish.cpp: the received position tracked by a spring, a wiggle
// when it jumps.
void() Fish_Frame =
{
	local float p, i, k, n, dt, sdt, el, avg, et, sw, wig, steps, sub, tz;
	local vector err, lv, lp, eye, o;
	local entity f;

	dt = time - fish_last;
	fish_last = time;
	if (dt <= 0 || dt > 0.25)
		return;                 // paused, a demo seek, a hitch or the clock arriving: hold them
	if (!fish_started)
	{	// CFish::Spawn's timers, against the server's clock now that it has arrived
		fish_started = TRUE;
		for (i = 0; i < fs_n; i = i + 1)
		{
			fs_tdisp[i] = time + Fish_Rand(0, 10);
			fs_tgo[i] = time + Fish_Rand(10, 60);
			fs_tmove[i] = time + Fish_Rand(2, 10);
		}
		for (p = 0; p < fp_n_; p = p + 1)
			fp_vist[p] = time + random() * 0.5;     // the pools' sight checks spread over the half second
	}
	eye = getproperty(VF_ORIGIN);
	fish_tacc = fish_tacc + dt;
	steps = 0;
	while (fish_tacc >= FISH_STEP && steps < 3)
	{
		fish_tacc = fish_tacc - FISH_STEP;
		steps = steps + 1;
		for (p = 0; p < fp_n_; p = p + 1)
			if (vlen(fp_org[p] - eye) - fp_range[p] < FISH_SIMFAR)
				Fish_PoolStep(p);
	}
	if (cvar("vbsp_fx_debug"))
	if (time > fish_dbgt || time < fish_dbgt - 3)
	{
		fish_dbgt = time + 2;
		print(sprintf("fish: %g, fish 0 at %v drawn at %v speed %.1f want %.1f (calm %.1f panic %.1f)\n", fs_n,
		              fs_pos[0], fs_lpos[0], fs_speed[0], fs_want[0], fs_calm[0], fs_panic[0]));
	}
	sub = ceil(dt / FISH_SUB);
	sdt = dt / sub;
	for (i = 0; i < fs_n; i = i + 1)
	{
		p = fs_pool[i];
		if (vlen(fp_org[p] - eye) - fp_range[p] >= FISH_SIMFAR)
			continue;
		f = fs_e[i];
		o = fp_org[p];
		tz = o_z;
		err = fs_act[i] - fs_lpos[i];
		err_z = 0;
		el = vlen(err);
		wig = 0;
		if (time - fs_wigt0[i] < 5)
		{
			sw = 1 - (time - fs_wigt0[i]) / 5;
			wig = 6 * sw * sin(fs_wigph[i]);
			fs_wigph[i] = fs_wigph[i] + fs_wigrt[i] * dt;
			fs_wigrt[i] = fs_wigrt[i] - 5 * dt;
		}
		f.angles = [0, fs_actang[i] + wig, 0];
		n = fs_errn[i];
		avg = 0;
		for (k = 0; k < n; k = k + 1)
			avg = avg + fs_err[i * FISH_ERRN + k];
		if (n)
			avg = avg / n;
		if (el - avg > 2)
		{	// a jump well above the usual error: it started swimming
			fs_wigt0[i] = time;
			fs_wigrt[i] = min(30, 2 * el);
		}
		k = fs_erri[i];
		fs_err[i * FISH_ERRN + k] = el;
		k = k + 1;
		if (k >= FISH_ERRN)
			k = 0;
		fs_erri[i] = k;
		fs_errn[i] = min(FISH_ERRN, n + 1);
		lv = fs_lvel[i];
		lp = fs_lpos[i];
		for (k = 0; k < sub; k = k + 1)
		{	// the spring, sub-stepped
			err = fs_act[i] - lp;
			el = vlen([err_x, err_y, 0]);
			et = min(1, el / 20);
			et = et * et;
			lv_x = lv_x + et * 115 * err_x * sdt;
			lv_y = lv_y + et * 115 * err_y * sdt;
			lv_x = lv_x - (2 + et * 6) * lv_x * sdt;
			lv_y = lv_y - (2 + et * 6) * lv_y * sdt;
			lp = lp + [lv_x, lv_y, 0] * sdt;
		}
		lp_z = tz;
		fs_lvel[i] = lv;
		fs_lpos[i] = lp;
		f.origin = lp;
		if (vlen(lp - fs_link[i]) > 32)
		{	// relinked only after a real move (cl_trk.qc's Trk_Relink measured what a relink costs)
			setorigin(f, lp);
			fs_link[i] = lp;
		}
	}
};

// The first fish the engine adds each frame runs the frame for all of them.
float() Fish_Predraw =
{
	if (time != fish_last)
		Fish_Frame();
	return PREDRAW_AUTOADD;
};

void() Fish_Clear =
{
	local float i;
	for (i = 0; i < fs_n; i = i + 1)
		if (fs_e[i])
			remove(fs_e[i]);
	fs_n = fp_n_ = 0;
};

// The lump's pools.  Called from Sprite_LoadForMap.
void() Fish_LoadForMap =
{
	local string tok, key, cn, mdl;
	local vector org;
	local float cnt, rng, i, k, p, visofs;
	local entity f;

	Fish_Alloc();
	Fish_Clear();
	vbsp_fish_pools = vbsp_fish_skip = 0;
	fish_tacc = 0;
	fish_last = time;
	fish_started = FALSE;
	if (!vbsp_fish_seen || !cvar("vbsp_fish"))
		return;
	visofs = 0;
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = mdl = "";
		org = '0 0 0';
		cnt = 0;
		rng = 255;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if      (key == "classname")  cn = tok;
			else if (key == "origin")     org = Sprite_ParseVec(tok);
			else if (key == "model")      mdl = tok;
			else if (key == "fish_count") cnt = floor(stof(tok));
			else if (key == "max_range")  rng = bound(1, stof(tok), 255);
		}
		if (cn != "func_fish_pool" || cnt <= 0)
			continue;
		cnt = min(cnt, 20);
		if (mdl == "" || fp_n_ >= FPOOL_MAX || fs_n + cnt > FISH_MAX)
		{
			vbsp_fish_skip = vbsp_fish_skip + 1;
			continue;
		}
		precache_model(mdl);
		p = fp_n_;
		fp_org[p] = org;
		fp_range[p] = rng;
		fp_first[p] = fs_n;
		fp_n[p] = cnt;
		fp_visofs[p] = visofs;
		fp_vist[p] = 0;
		visofs = visofs + cnt * cnt;
		for (k = 0; k < cnt * cnt; k = k + 1)
			fp_vis[fp_visofs[p] + k] = 0;
		for (k = 0; k < cnt; k = k + 1)
		{	// CFish::Spawn (the timers start with the first frame, Fish_Frame)
			i = fs_n;
			f = spawn();
			f.classname = "fish";
			setmodel(f, mdl);
			f.drawmask = MASK_ENGINE;
			f.predraw = Fish_Predraw;
			setorigin(f, org);
			fs_e[i] = f;
			fs_pool[i] = p;
			fs_pos[i] = org;
			fs_act[i] = org;
			fs_link[i] = org;
			fs_lpos[i] = org;
			fs_lvel[i] = '0 0 0';
			fs_ang[i] = Fish_Rand(0, 360);
			fs_actang[i] = fs_ang[i];
			fs_dang[i] = 0;
			fs_speed[i] = 0;
			fs_calm[i] = Fish_Rand(10, 20);
			fs_panic[i] = fs_calm[i] * Fish_Rand(4, 5);
			fs_want[i] = fs_calm[i];
			fs_cw[i] = (random() < 0.5);
			fs_avoid[i] = Fish_Rand(40, 75);
			fs_tpanic[i] = 0;
			fs_tturn[i] = 0;
			fs_wigt0[i] = -100;
			fs_errn[i] = fs_erri[i] = 0;
			fs_n = fs_n + 1;
		}
		fp_n_ = fp_n_ + 1;
		vbsp_fish_pools = vbsp_fish_pools + 1;
	}
	print(sprintf("fish: %g in %g of %g func_fish_pool (%g declined: no model, over a cap)\n",
	              fs_n, vbsp_fish_pools, vbsp_fish_seen, vbsp_fish_skip));
};
