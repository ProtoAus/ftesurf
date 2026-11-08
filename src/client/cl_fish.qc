/*
  cl_fish.qc -- P1436: func_fish_pool's fish, simulated here (Lex: decorative motion is client-side).

  fish.cpp in full: each pool spawns fish_count fish at its origin; CFishPool::Update runs every 0.1 s --
  line-of-sight lists every 0.5 s, then CFish::Update: Avoid (two feelers, the pool's max_range), FlockTo the
  visible fish and the pool centre, turn rate capped by speed, speed eased to calm or panic, the radial part
  of the velocity dropped at the edge.  The fish swim level at the pool origin's height.  Between steps the
  position moves at the velocity, as MOVETYPE_FLY does, stopping at the world.  c_fish.cpp then draws each
  fish tracking that position through the network's 7-bit quantisation (4 units, 2.8 degrees) with its
  spring and wiggle, which is what makes them swim rather than slide.

  Fish never die here (no damage).  A player within 75 units panics a fish: Touch and player_footstep's
  quiet range; weapon/grenade events do not exist in this game.  Pools farther than FISH_SIMFAR from the eye
  are not simulated.  Each client runs its own fish.
*/

#define FISH_MAX      512       // the library's most is 240 (surf_garden_css)
#define FPOOL_MAX     64        // ...and 56 pools (surf_sh)
#define FISH_STEP     0.1
#define FISH_SIMFAR   3000
#define FISH_QPOS     (510 / 127)   // SendPropFloat 7 bits over -255..255
#define FISH_QANG     (360 / 127)

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
float  *fs_tmoved;              // the move timer's duration, for IsElapsed and the wiggle
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
float  fish_tacc, fish_last, fish_dbgt;
float  vbsp_fish_pools, vbsp_fish_skip;

#define FISH_ERRN     20

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
	fs_tmoved = memalloc(sizeof(float) * FISH_MAX);
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

void(float i) Fish_Panic =
{
	fs_tpanic[i] = time + Fish_Rand(5, 15);
	fs_tmoved[i] = Fish_Rand(10, 20);
	fs_tmove[i] = time + fs_tmoved[i];
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

// CFishPool::Update for pool p: one 0.1 s step.
void(float p, vector eye) Fish_PoolStep =
{
	local float a, b, n, i, o, danger, maxch, ofs;
	n = fp_n[p];
	a = fp_first[p];
	ofs = fp_visofs[p];
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
		if (vlen(eye - fs_pos[i]) < 75)
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
			fs_tmoved[i] = Fish_Rand(2, 10);
			fs_tmove[i] = time + fs_tmoved[i];
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
};

// The fish's velocity now (fish.cpp's tail of Update): forward at its speed, nothing outward at the edge.
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

// Moves, then poses as c_fish.cpp: the quantised position tracked by a spring, a wiggle when it jumps.
void() Fish_Frame =
{
	local float p, i, k, n, dt, el, avg, et, rate, sw, wig, steps;
	local vector act, err, lv, rel, np, eye;
	local entity f;

	dt = time - fish_last;
	fish_last = time;
	if (dt <= 0 || dt > 0.25)
		return;                 // paused, a demo seek or a hitch: hold them
	eye = getproperty(VF_ORIGIN);
	fish_tacc = fish_tacc + dt;
	steps = 0;
	while (fish_tacc >= FISH_STEP && steps < 3)
	{
		fish_tacc = fish_tacc - FISH_STEP;
		steps = steps + 1;
		for (p = 0; p < fp_n_; p = p + 1)
			if (vlen(fp_org[p] - eye) - fp_range[p] < FISH_SIMFAR)
				Fish_PoolStep(p, eye);
	}
	if (fish_tacc > FISH_STEP)
		fish_tacc = 0;          // a long hitch: drop the backlog
	if (cvar("vbsp_fx_debug"))
	if (time > fish_dbgt || time < fish_dbgt - 3)
	{
		fish_dbgt = time + 2;
		print(sprintf("fish: %g, fish 0 at %v drawn at %v speed %.1f want %.1f (calm %.1f panic %.1f)\n", fs_n,
		              fs_pos[0], fs_lpos[0], fs_speed[0], fs_want[0], fs_calm[0], fs_panic[0]));
	}
	for (i = 0; i < fs_n; i = i + 1)
	{
		p = fs_pool[i];
		if (vlen(fp_org[p] - eye) - fp_range[p] >= FISH_SIMFAR)
			continue;
		np = fs_pos[i] + Fish_Vel(i) * dt;          // MOVETYPE_FLY, stopped by the world
		traceline(fs_pos[i], np, MOVE_NOMONSTERS, world);
		fs_pos[i] = trace_endpos;
		// what the client would have received
		rel = fs_pos[i] - fp_org[p];
		act = fp_org[p] + [rint(bound(-255, rel_x, 255) / FISH_QPOS) * FISH_QPOS, rint(bound(-255, rel_y, 255) / FISH_QPOS) * FISH_QPOS, 0];
		np = fp_org[p];
		act_z = np_z;
		lv = fs_lvel[i];
		err = act - fs_lpos[i];
		err_z = 0;
		el = vlen(err);
		// wiggle while swimming (c_fish.cpp)
		f = fs_e[i];
		wig = 0;
		if (time - fs_wigt0[i] < 5)
		{
			sw = 1 - (time - fs_wigt0[i]) / 5;
			wig = 6 * sw * sin(fs_wigph[i]);
			fs_wigph[i] = fs_wigph[i] + fs_wigrt[i] * dt;
			fs_wigrt[i] = fs_wigrt[i] - 5 * dt;
		}
		f.angles = [0, rint(fs_ang[i] / FISH_QANG) * FISH_QANG + wig, 0];
		n = fs_errn[i];
		avg = 0;
		for (k = 0; k < n; k = k + 1)
			avg = avg + fs_err[i * FISH_ERRN + k];
		if (n)
			avg = avg / n;
		if (el - avg > 2)
		{
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
		et = min(1, el / 20);
		et = et * et;
		rate = et * 115;
		lv_x = lv_x + rate * err_x * dt;
		lv_y = lv_y + rate * err_y * dt;
		lv_x = lv_x - (2 + et * 6) * lv_x * dt;
		lv_y = lv_y - (2 + et * 6) * lv_y * dt;
		fs_lvel[i] = lv;
		np = fs_lpos[i] + lv * dt;
		np_z = act_z;
		fs_lpos[i] = np;
		setorigin(f, np);
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
		{	// CFish::Spawn
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
			fs_lpos[i] = org;
			fs_lvel[i] = '0 0 0';
			fs_ang[i] = Fish_Rand(0, 360);
			fs_dang[i] = 0;
			fs_speed[i] = 0;
			fs_calm[i] = Fish_Rand(10, 20);
			fs_panic[i] = fs_calm[i] * Fish_Rand(4, 5);
			fs_want[i] = fs_calm[i];
			fs_cw[i] = (random() < 0.5);
			fs_avoid[i] = Fish_Rand(40, 75);
			fs_tdisp[i] = time + Fish_Rand(0, 10);
			fs_tgo[i] = time + Fish_Rand(10, 60);
			fs_tmoved[i] = Fish_Rand(2, 10);
			fs_tmove[i] = time + fs_tmoved[i];
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
