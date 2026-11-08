/*
  cl_explode.qc -- P1435: env_explosion's Explode, drawn as Source's client effect.

  explode.cpp InputExplode sends TE_Explosion; c_te_explosion.cpp hands it to C_BaseExplosionEffect::Create
  (fx_explosion.cpp), which is what this copies: sound, then (no SF 4 NoFireball) the core -- smoke filler,
  inner core and a ground ring (no SF 256 NoFireballSmoke), embers and fireballs -- and (no SF 512 NoParticles)
  sparks and flecks.  Magnitude only sets the probe length that picks the blast's direction (away from nearby
  walls); EXPLOSION_FORCE_MIN = MAX = 2, so the force is a constant.  The dynamic light is a FIXME in Source
  (never called) and the 0.1 s refraction bulge (CExplosionOverlay) is not drawn here.  Under water Source draws
  a different effect; that one is skipped.  The first Explode leaves a Scorch decal on the floor it found.

  Not as Source: every client gets every explosion (Source's CPASFilter is not reproducible here), drawn within
  XP_FAR; the particles draw in material passes, not depth-sorted, so fire is always over smoke; a spot the
  light lookup cannot answer gets mid-grey smoke (Source's would be black); the CS:S fallback sound has no
  80-110 pitch; flecks bounce off the world only.

  The lump gives each named one (the server keeps only those) its place, light and direction at map load; the
  effect-state wire (class FX_CLS_EXPLODE) fires it.  Particles are simulated here and drawn as polygons.
*/

#define XP_MAX        256       // named env_explosions a map
#define XP_PMAX       1024      // live particles (one explosion makes at most 140)
#define XP_FAR        8000      // farther than this: heard, not drawn
#define XP_ATTN       0.2222    // SNDLVL_140dB, as Snds_Attn: 20 / (140 - 50)

#define XK_PUFF       0         // CExplosionParticle (smoke, embers, fireballs)
#define XK_SPARK      1         // CTrailParticles
#define XK_FLECK      2         // CFleckParticles

#define XM_SMOKE      0         // particle/particle_noisesphere (g_Mat_DustPuff[1])
#define XM_FIRE       1         // effects/fire_cloud2
#define XM_EMB1       2
#define XM_EMB2       3
#define XM_FLECK1     4
#define XM_FLECK2     5
#define XM_N          6

vector *xp_korg;                // the entity's own origin, what the net matches
float  *xp_tnc;
float  *xp_sf;
vector *xp_org;                 // where it goes off: pulled 24 off the floor below, as InputExplode
vector *xp_dir;                 // GetForceDirection
vector *xp_lt;                  // the world's light there, for the smoke
float  *xp_wet;
vector *xp_hit;                 // the floor the ground trace hit, for the scorch; xp_hn '0 0 0' if none
vector *xp_hn;
float  *xp_scorch;              // the scorch decal's handle once placed
float  xp_n;

vector *xpp_p;
vector *xpp_v;
vector *xpp_col;
float  *xpp_t0;
float  *xpp_life;
float  *xpp_s0;
float  *xpp_s1;
float  *xpp_roll;
float  *xpp_rd;
float  *xpp_kind;
float  *xpp_mat;
float  *xpp_len;                // a spark's length (seconds of its velocity)
float  xpp_cur;
float  xp_last;
float  xp_mat[XM_N];            // sprmat indexes, -1 if the material does not resolve
float  xp_snd;                  // 1: weapons/explode3-5 (Momentum's BaseExplosionEffect.Sound); 2: CS:S debris1-2
float  xp_sndattn;
float  vbsp_xp_n, vbsp_xp_skip, vbsp_xp_fired;

void() Explode_Alloc =
{
	if (xp_korg)
		return;
	xp_korg = memalloc(sizeof(vector) * XP_MAX);
	xp_tnc = memalloc(sizeof(float) * XP_MAX);
	xp_sf = memalloc(sizeof(float) * XP_MAX);
	xp_org = memalloc(sizeof(vector) * XP_MAX);
	xp_dir = memalloc(sizeof(vector) * XP_MAX);
	xp_lt = memalloc(sizeof(vector) * XP_MAX);
	xp_wet = memalloc(sizeof(float) * XP_MAX);
	xp_hit = memalloc(sizeof(vector) * XP_MAX);
	xp_hn = memalloc(sizeof(vector) * XP_MAX);
	xp_scorch = memalloc(sizeof(float) * XP_MAX);
	xpp_p = memalloc(sizeof(vector) * XP_PMAX);
	xpp_v = memalloc(sizeof(vector) * XP_PMAX);
	xpp_col = memalloc(sizeof(vector) * XP_PMAX);
	xpp_t0 = memalloc(sizeof(float) * XP_PMAX);
	xpp_life = memalloc(sizeof(float) * XP_PMAX);
	xpp_s0 = memalloc(sizeof(float) * XP_PMAX);
	xpp_s1 = memalloc(sizeof(float) * XP_PMAX);
	xpp_roll = memalloc(sizeof(float) * XP_PMAX);
	xpp_rd = memalloc(sizeof(float) * XP_PMAX);
	xpp_kind = memalloc(sizeof(float) * XP_PMAX);
	xpp_mat = memalloc(sizeof(float) * XP_PMAX);
	xpp_len = memalloc(sizeof(float) * XP_PMAX);
};

float(float a, float b) Xp_RandF = { return a + random() * (b - a); };
float(float a, float b) Xp_RandI = { a = floor(a); b = floor(b); return min(b, floor(a + random() * (b - a + 1))); };
vector(float s) Xp_RandV = { return [Xp_RandF(-s, s), Xp_RandF(-s, s), Xp_RandF(-s, s)]; };

// One particle into the ring; returns its slot.
float(float kind, float mat, vector p, vector v, float life, float s0, float s1, float rd, vector col) Xp_Add =
{
	local float k;
	k = xpp_cur;
	xpp_cur = xpp_cur + 1;
	if (xpp_cur >= XP_PMAX)
		xpp_cur = 0;
	if (xpp_life[k] <= 0)
		xp_live = xp_live + 1;
	xpp_kind[k] = kind;
	xpp_mat[k] = mat;
	xpp_p[k] = p;
	xpp_v[k] = v;
	xpp_t0[k] = time;
	xpp_life[k] = life;
	xpp_s0[k] = s0;
	xpp_s1[k] = s1;
	xpp_roll[k] = random() * 360;
	xpp_rd[k] = rd;
	xpp_col[k] = col;
	return k;
};

// fx_explosion.cpp ScaleForceByDeviation: spread * |cos| between the two.
float(vector a, vector b, float spread) Xp_Dev = { return spread * fabs(a * b); };

// One explosion: C_BaseExplosionEffect::Create.
void(float i) Explode_Go =
{
	local float k, n, f, dev, lum, sf, sz, yaw;
	local vector org, dir, v, lt, fw, nc, eye;
	local string s;

	sf = xp_sf[i];
	org = xp_org[i];
	dir = xp_dir[i];
	vbsp_xp_fired = vbsp_xp_fired + 1;
	if (cvar("vbsp_fx_debug"))
		print(sprintf("explode: %g at %v dir %v flags %g wet %g\n", i, org, dir, sf, xp_wet[i]));
	if (!(sf & 64) && xp_snd)
	{	// BaseExplosionEffect.Sound
		if (xp_snd == 1)
			s = sprintf("weapons/explode%g.wav", Xp_RandI(3, 5));
		else
			s = sprintf("weapons/debris%g.wav", Xp_RandI(1, 2));
		pointsound(org, s, 1, xp_sndattn);
	}
	if (!(sf & 16) && xp_scorch[i] < 0 && xp_hn[i] != '0 0 0')
	{	// UTIL_DecalTrace(&tr, "Scorch"): decals/scorch1-2, 128 wide; one a spot (they would only stack)
		nc = xp_hn[i];
		fw = (fabs(nc_z) < 0.9) ? normalize(crossproduct(nc, '0 0 1')) : normalize(crossproduct(nc, '1 0 0'));
		xp_scorch[i] = adddecal_static(sprintf("decals/scorch%g", Xp_RandI(1, 2)), xp_hit[i] + nc * 0.5,
		                               nc * (1 / DECAL_DEPTH), fw * (1 / 64), '1 1 1', '1 1 0');
		if (xp_scorch[i] >= 0)
			Decal_Keep(xp_scorch[i]);
		else
			xp_scorch[i] = 0;   // failed: do not try again
	}
	if (xp_wet[i])
		return;
	eye = getproperty(VF_ORIGIN);
	if (vlen(org - eye) > XP_FAR)
		return;
	if (!xp_live)
		xp_last = time;             // an idle clock would hand the first frame a 0.1 s step
	if (!(sf & 4))
	{	// CreateCore; force is clamped to 2, so spread is 0.7
		lt = xp_lt[i];
		lum = (lt_x * 0.3 + lt_y * 0.59 + lt_z * 0.11) * 255;
		if (!(sf & 256))
		{
			for (k = 0; k < 4; k = k + 1)
			{	// smoke filler
				v = normalize(Xp_RandV(0.7) + dir * Xp_RandF(1, 6));
				f = Xp_RandF(1, 750) * 2 * Xp_Dev(v, dir, 0.7);
				n = Xp_RandI(lum * 0.5, lum);
				nc = [min(255, lt_x * n), min(255, lt_y * n), min(255, lt_z * n)] * (1 / 255);
				Xp_Add(XK_PUFF, XM_SMOKE, org, v * f, Xp_RandF(2, 3), 72, 144, Xp_RandF(-2, 2), nc);
			}
			for (k = 0; k < 8; k = k + 1)
			{	// inner core
				v = normalize(Xp_RandV(0.7) + dir * Xp_RandF(1, 6));
				f = Xp_RandF(1, 2000) * 2 * Xp_Dev(v, dir, 0.7);
				n = Xp_RandI(lum * 0.5, lum);
				nc = [min(255, lt_x * n), min(255, lt_y * n), min(255, lt_z * n)] * (1 / 255);
				sz = Xp_RandI(32, 64);
				Xp_Add(XK_PUFF, XM_SMOKE, org + Xp_RandV(16), v * f, Xp_RandF(0.5, 1), sz, sz * 2, Xp_RandF(-8, 8), nc);
			}
			for (k = 0; k < 32; k = k + 1)
			{	// ground ring, flat whatever the direction
				yaw = (k + 1) * (2 * M_PI / 32);
				fw = [cos(yaw), sin(yaw), 0];
				f = Xp_RandF(500, 2000) * 2 * 0.7;
				n = Xp_RandI(lum * 0.5, lum);
				nc = [min(255, lt_x * n), min(255, lt_y * n), min(255, lt_z * n)] * (1 / 255);
				sz = Xp_RandI(16, 32);
				Xp_Add(XK_PUFF, XM_SMOKE, org + Xp_RandV(4) + fw * Xp_RandF(8, 16), fw * f, Xp_RandF(0.5, 1.5),
				       sz, sz * 4, Xp_RandF(-8, 8), nc);
			}
		}
		for (k = 0; k < 16; k = k + 1)
		{	// embers
			v = normalize(Xp_RandV(1.4) + dir);
			dev = Xp_Dev(v, dir, 0.7);
			n = Xp_RandI(192, 255) / 255;
			sz = bound(4, floor(Xp_RandI(8, 16) * dev), 32);
			Xp_Add(XK_PUFF, XM_EMB1 + Xp_RandI(0, 1), org + Xp_RandV(32), v * (Xp_RandF(1, 400) * 8 * dev * dev),
			       Xp_RandF(2, 3), sz, sz, Xp_RandF(-8, 8), [n, n, n]);
		}
		for (k = 0; k < 32; k = k + 1)
		{	// fireballs
			v = normalize(Xp_RandV(0.525) + dir);
			dev = Xp_Dev(v, dir, 0.7);
			n = Xp_RandI(128, 255) / 255;
			sz = bound(32, floor(Xp_RandI(32, 85) * dev), 85);
			Xp_Add(XK_PUFF, XM_FIRE, org + Xp_RandV(48), v * (Xp_RandF(400, 800) * 8 * dev * dev),
			       Xp_RandF(0.2, 0.4), sz, floor(sz * 1.5), Xp_RandF(-16, 16), [n, n, n]);
		}
	}
	if (!(sf & 512))
	{	// CreateDebris
		n = Xp_RandI(8, 16);
		for (k = 0; k < n; k = k + 1)
		{	// sparks: streaks, gravity 200, dampened 8/s
			v = normalize(Xp_RandV(1) + dir) * Xp_RandF(1500, 2500);
			f = Xp_Add(XK_SPARK, XM_FIRE, org, v, Xp_RandF(0.1, 0.15), Xp_RandF(2, 16), 0, 0, '1 1 1');
			xpp_len[f] = Xp_RandF(0.05, 0.1);
		}
		n = Xp_RandI(16, 32);
		for (k = 0; k < n; k = k + 1)
		{	// flecks: bounce, gravity 800
			v = dir + Xp_RandV(1);
			sz = Xp_RandI(1, 3);
			v = normalize(v);
			dev = Xp_Dev(v, dir, 0.8);
			f = Xp_RandF(0.5, 1.5) * 0.25;
			f = min(1, f);
			f = Xp_Add(XK_FLECK, XM_FLECK1 + Xp_RandI(0, 1), org + dir * 16 + Xp_RandV(8),
			           v * (Xp_RandF(64, 256) * (4 - sz) * 8 * dev * dev), 3, sz, sz, Xp_RandF(0, 360), [f, f, f]);
		}
	}
};

// ENTWIRE_FXSTATE2 class FX_CLS_EXPLODE (Fx_Net forwards it): one explosion per new event.
void(entity e) Explode_FxNet =
{
	local float i, k;
	if (!e.fx_nfire || !cvar("vbsp_explosions"))
		return;
	for (i = 0; i < xp_n; i = i + 1)
	{
		if (xp_tnc[i] != e.fx_ntnc || vlen(xp_korg[i] - e.origin) > 0.1)
			continue;
		for (k = 0; k < min(e.fx_nfire, 3); k = k + 1)
			Explode_Go(i);
	}
};

// GetForceDirection: each axis probed `mag` out; the sum points away from what is close.
vector(vector org, float mag) Explode_Dir =
{
	local vector d, sum;
	local float k;
	sum = '0 0 0';
	for (k = 0; k < 6; k = k + 1)
	{
		d = '0 0 0';
		if (k == 0) d_x = 1; else if (k == 1) d_x = -1;
		else if (k == 2) d_y = 1; else if (k == 3) d_y = -1;
		else if (k == 4) d_z = 1; else d_z = -1;
		if (mag > 0)
		{
			traceline(org, org + d * mag, MOVE_NOMONSTERS, world);
			sum = sum - d * (1 - trace_fraction);
		}
	}
	if (sum == '0 0 0')
		return '0 0 1';
	return normalize(sum);
};

// A file in any mounted pack (whichpack answers "" for one inside a .vpk; cl_banner.qc does this).
float(string p) Explode_Have =
{
	local float h, n;
	h = search_begin(p, TRUE, TRUE);
	if (h < 0)
		return FALSE;
	n = search_getsize(h);
	search_end(h);
	return n > 0;
};

// The lump: every named env_explosion (the server keeps only those).  Called from Sprite_LoadForMap.
void() Explode_LoadForMap =
{
	local string tok, key, cn, tn, pn;
	local vector org, eo, lt, a, b, m;
	local float sf, mag, i, vc, k;

	Explode_Alloc();
	xp_n = vbsp_xp_n = vbsp_xp_skip = vbsp_xp_fired = 0;
	for (i = 0; i < XP_PMAX; i = i + 1)
		xpp_life[i] = 0;
	xp_live = 0;
	if (!vbsp_xp_seen)
		return;
	xp_mat[XM_SMOKE] = Sprite_Material("particle/particle_noisesphere", 0);
	xp_mat[XM_FIRE] = Sprite_Material("effects/fire_cloud2", 0);
	xp_mat[XM_EMB1] = Sprite_Material("effects/fire_embers1", 0);
	xp_mat[XM_EMB2] = Sprite_Material("effects/fire_embers2", 0);
	xp_mat[XM_FLECK1] = Sprite_Material("effects/fleck_cement1", 0);
	xp_mat[XM_FLECK2] = Sprite_Material("effects/fleck_cement2", 0);
	xp_snd = 0;
	xp_sndattn = XP_ATTN;
	if (Explode_Have("sound/weapons/explode3.wav"))
		xp_snd = 1;
	else if (Explode_Have("sound/weapons/debris1.wav"))
	{
		xp_snd = 2;
		xp_sndattn = 20 / (85 - 50);    // CS:S's BaseExplosionEffect.Sound is SNDLVL_85dB
	}
	if (xp_snd == 1)
	{
		precache_sound("weapons/explode3.wav");
		precache_sound("weapons/explode4.wav");
		precache_sound("weapons/explode5.wav");
	}
	else if (xp_snd == 2)
	{
		precache_sound("weapons/debris1.wav");
		precache_sound("weapons/debris2.wav");
	}
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = tn = pn = "";
		org = '0 0 0';
		sf = mag = 0;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if      (key == "classname")  cn = tok;
			else if (key == "origin")     org = Sprite_ParseVec(tok);
			else if (key == "targetname") tn = tok;
			else if (key == "parentname") pn = tok;
			else if (key == "spawnflags") sf = stof(tok);
			else if (key == "imagnitude") mag = stof(tok);
		}
		if (cn != "env_explosion" || tn == "")
			continue;
		if (pn != "" || xp_n >= XP_MAX)
		{	// a moving parent takes it somewhere the lump does not know
			vbsp_xp_skip = vbsp_xp_skip + 1;
			continue;
		}
		i = xp_n;
		xp_korg[i] = org;
		xp_tnc[i] = crc16(TRUE, tn);
		xp_sf[i] = sf;
		traceline(org + '0 0 8', org + '0 0 -32', MOVE_NOMONSTERS, world);
		eo = org;
		xp_hn[i] = '0 0 0';
		xp_scorch[i] = -1;
		a = org + '0 0 8';
		b = trace_endpos + '0 0 0.5';
		if (pointcontents(a) != CONTENT_WATER && pointcontents(b) == CONTENT_WATER)
		{	// the trace stops at the water's surface: find it
			for (k = 0; k < 10; k = k + 1)
			{
				m = (a + b) * 0.5;
				if (pointcontents(m) == CONTENT_WATER)
					b = m;
				else
					a = m;
			}
			eo = a + '0 0 24';
		}
		else if (trace_fraction < 1)
		{
			eo = trace_endpos + trace_plane_normal * 24;
			if (trace_ent == world)
			{
				xp_hit[i] = trace_endpos;
				xp_hn[i] = trace_plane_normal;
			}
		}
		xp_org[i] = eo;
		xp_wet[i] = (pointcontents(eo) == CONTENT_WATER);   // c_te_explosion.cpp tests CONTENTS_WATER only
		xp_dir[i] = Explode_Dir(eo, mag);
		vc = cvar("hl2_lt_vcache");     // sampled once, as cl_emit.qc's steam jets
		if (vc)
			cvar_set("hl2_lt_vcache", "0");
		lt = getlight(eo + xp_dir[i] * 32) * (1 / 255);
		if (vc)
			cvar_set("hl2_lt_vcache", ftos(vc));
		if (lt == '0 0 0')
			lt = '0.5 0.5 0.5';     // no answer (cl_ropes.qc does the same)
		xp_lt[i] = lt;
		xp_n = xp_n + 1;
	}
	vbsp_xp_n = xp_n;
	print(sprintf("explosions: %g of %g env_explosion kept for their inputs (%g parented or over the cap), sound %s\n",
	              xp_n, vbsp_xp_seen, vbsp_xp_skip, (xp_snd == 1) ? "explode3-5" : ((xp_snd == 2) ? "debris1-2" : "none")));
};

// Simulates and draws the live particles; returns how many were drawn.  Called from Sprite_Draw.
float(vector eye, vector fwd) Explode_Draw =
{
	local float k, m, dt, decay, age, t, ramp, sz, cr, sn, drawn, live, len, w, flags, a, dmp;
	local vector p, v, sv, vr, vu, r, u, col, nrm, d, sp;
	local string mat;

	if (!xp_live)
		return 0;
	dt = time - xp_last;
	xp_last = time;
	if (dt < 0 || dt > 0.1)
		dt = (dt < 0) ? 0 : 0.1;
	decay = pow(0.0001, dt / 0.5);      // CExplosionParticle::UpdateVelocity
	makevectors(getproperty(VF_ANGLES));
	vr = v_right;
	vu = v_up;
	live = 0;
	for (k = 0; k < XP_PMAX; k = k + 1)
	{
		if (xpp_life[k] <= 0)
			continue;
		age = time - xpp_t0[k];
		if (age >= xpp_life[k] || age < 0)
		{
			xpp_life[k] = 0;
			continue;
		}
		live = live + 1;
		v = xpp_v[k];
		if (xpp_kind[k] == XK_PUFF)
		{
			sv = v;
			v = v * decay;
			if (v * v < 32 * 32)
			if (sv != '0 0 0')
				v = normalize(sv) * 32;
			xpp_p[k] = xpp_p[k] + v * dt;
			xpp_roll[k] = xpp_roll[k] + xpp_rd[k] * dt;
			xpp_rd[k] = xpp_rd[k] + xpp_rd[k] * (dt * -8);
			if (fabs(xpp_rd[k]) < 0.5)
				xpp_rd[k] = (xpp_rd[k] > 0) ? 0.5 : -0.5;
		}
		else if (xpp_kind[k] == XK_SPARK)
		{
			v_z = v_z - 200 * dt;
			xpp_p[k] = xpp_p[k] + v * dt;
			v = v * max(0, 1 - dt * 8);
		}
		else if (v != '0 0 0')
		{	// CParticleCollision::MoveParticle: gravity; a bounce at 0.4-0.6 of the speed, roll reversed to a
			// quarter; at rest on a floor slower than 48 down; stopped in solid
			xpp_roll[k] = xpp_roll[k] + xpp_rd[k] * dt;
			v_z = v_z - 800 * dt;
			p = xpp_p[k];
			traceline(p, p + v * dt, MOVE_NOMONSTERS, world);
			if (trace_allsolid)
			{
				v = '0 0 0';
				xpp_rd[k] = 0;
			}
			else if (trace_fraction < 1)
			{
				nrm = trace_plane_normal;
				xpp_p[k] = trace_endpos + nrm * 0.5;
				if (nrm_z >= 0.5 && fabs(v_z) <= 48)
				{
					v = '0 0 0';
					xpp_rd[k] = 0;
				}
				else
				{
					dmp = Xp_RandF(0.4, 0.6);
					v = (v - nrm * (2 * (v * nrm))) * dmp;
					xpp_rd[k] = xpp_rd[k] * -0.25;
				}
			}
			else
				xpp_p[k] = p + v * dt;
		}
		xpp_v[k] = v;
	}
	xp_live = live;
	drawn = 0;
	for (m = 0; m < XM_N; m = m + 1)
	{
		if (xp_mat[m] < 0)
			continue;
		mat = sprmat_name[xp_mat[m]];
		flags = (m == XM_SMOKE || m >= XM_FLECK1) ? DRAWFLAG_NORMAL : DRAWFLAG_ADD;
		for (k = 0; k < XP_PMAX; k = k + 1)
		{
			if (xpp_life[k] <= 0 || xpp_mat[k] != m)
				continue;
			p = xpp_p[k];
			if (fwd * (p - eye) < -128)
				continue;
			t = (time - xpp_t0[k]) / xpp_life[k];
			if (xpp_kind[k] == XK_SPARK)
			{	// Tracer_Draw from the particle along its velocity, fading in length, not colour
				len = max(0.01, xpp_len[k] * (1 - t));
				d = xpp_v[k] * len;
				w = min(vlen(d), xpp_s0[k]);
				sp = crossproduct(d, p - eye);
				if (sp * sp < 0.0001)
					continue;
				sp = normalize(sp) * (w * 0.5);
				R_BeginPolygon(mat, flags);
				R_PolygonVertex(p - sp, '0 0 0', '1 1 1', 1);
				R_PolygonVertex(p + sp, '1 0 0', '1 1 1', 1);
				R_PolygonVertex(p + d + sp, '1 1 0', '1 1 1', 1);
				R_PolygonVertex(p + d - sp, '0 1 0', '1 1 1', 1);
				R_EndPolygon();
				drawn = drawn + 1;
				continue;
			}
			if (xpp_kind[k] == XK_PUFF)
			{	// Bias(1 - t, 0.25) is (1 - t)^2, on colour and alpha both; SetNearClip(64, 128)
				ramp = (1 - t) * (1 - t);
				col = xpp_col[k] * ramp;
				a = ramp * bound(0, (fwd * (p - eye) - 64) / 64, 1);
				sz = xpp_s0[k] + (xpp_s1[k] - xpp_s0[k]) * t;
			}
			else
			{
				col = xpp_col[k];
				a = 1 - t;
				sz = xpp_s0[k];
			}
			if (a <= 0)
				continue;
			cr = cos(xpp_roll[k]) * sz;     // RenderParticle_ColorSizeAngle: size is the half-width, roll radians
			sn = sin(xpp_roll[k]) * sz;
			r = vr * cr + vu * sn;
			u = vu * cr - vr * sn;
			R_BeginPolygon(mat, flags);
			R_PolygonVertex(p - r + u, '0 0 0', col, a);
			R_PolygonVertex(p + r + u, '1 0 0', col, a);
			R_PolygonVertex(p + r - u, '1 1 0', col, a);
			R_PolygonVertex(p - r - u, '0 1 0', col, a);
			R_EndPolygon();
			drawn = drawn + 1;
		}
	}
	return drawn;
};
