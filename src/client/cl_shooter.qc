/*
  cl_shooter.qc -- P1439: env_shooter's Shoot, gibs simulated here.

  CGibShooter::ShootThink (effects.cpp): a gib every Delay seconds (one a server tick at 0) until m_iGibs are out,
  each along the entity's forward scattered by m_flVariance on all three axes, at m_flVelocity; then a repeatable
  one (SF 1) re-arms and any other is gone.  A gib is shootmodel at its skin and scale, from gibangles; Simulation
  0 (point) spins at 100-200 / 100-300 degrees a second, 1 and 2 (physics, ragdoll) at gibanglevelocity x 0.1-1.
  CGib flies MOVETYPE_FLYGRAVITY / FLY_BOUNCE at gibgravityscale: a bounce keeps the reflected velocity times
  elasticity 0.25 (the entity's 1 x a surface's default, physics_main_shared.cpp), and under 30 u/s it rests, laid
  flat on a floor (gib.cpp).  With SF 4 (strict remove) it goes at m_flGibLife (+-5%, 25 when 0) -- at once, as
  DieThink in multiplayer; otherwise it stays (the ring recycles the oldest past GIB_MAX).  Gibs are debris in
  Source and never touch players, so nothing here is on the server.

  Not as Source: sprite shootmodels, the flaming flag (SF 2), the material bounce sounds and body groups are not
  drawn; a spent one-shot shooter is spent on this client only (the server does not count gibs), so a client
  that joins later fires on a later Shoot.
*/

#define SH_MAX        64        // named env_shooters a map
#define GIB_MAX       256       // live gibs
#define SH_FAR        5000      // a shooter farther than this from the eye keeps its count but spawns nothing

vector *sh_korg;
float  *sh_tnc;
vector *sh_fw;
vector *sh_rt;
vector *sh_up;
float  *sh_cap;
float  *sh_left;
float  *sh_next;                // the next shot, 0 idle
float  *sh_vel;
float  *sh_var;
float  *sh_life;
float  *sh_delay;
vector *sh_gang;
float  *sh_gangv;
float  *sh_sim;
float  *sh_skin;
float  *sh_scale;
float  *sh_grav;
float  *sh_sf;
float  *sh_gone;
vector *sh_col;
float  *sh_alpha;
string sh_mdl[SH_MAX];
float  sh_n;

entity *gib_e;
vector *gib_v;
vector *gib_av;
float  *gib_die;
float  *gib_grav;
float  *gib_alpha;
float  *gib_rest;
string sh_loadmap;
float  gib_cur, sh_last;
float  vbsp_sh_n, vbsp_sh_skip, vbsp_sh_shots;

void() Sh_Alloc =
{
	if (sh_korg)
		return;
	sh_korg = memalloc(sizeof(vector) * SH_MAX);
	sh_tnc = memalloc(sizeof(float) * SH_MAX);
	sh_fw = memalloc(sizeof(vector) * SH_MAX);
	sh_rt = memalloc(sizeof(vector) * SH_MAX);
	sh_up = memalloc(sizeof(vector) * SH_MAX);
	sh_cap = memalloc(sizeof(float) * SH_MAX);
	sh_left = memalloc(sizeof(float) * SH_MAX);
	sh_next = memalloc(sizeof(float) * SH_MAX);
	sh_vel = memalloc(sizeof(float) * SH_MAX);
	sh_var = memalloc(sizeof(float) * SH_MAX);
	sh_life = memalloc(sizeof(float) * SH_MAX);
	sh_delay = memalloc(sizeof(float) * SH_MAX);
	sh_gang = memalloc(sizeof(vector) * SH_MAX);
	sh_gangv = memalloc(sizeof(float) * SH_MAX);
	sh_sim = memalloc(sizeof(float) * SH_MAX);
	sh_skin = memalloc(sizeof(float) * SH_MAX);
	sh_scale = memalloc(sizeof(float) * SH_MAX);
	sh_grav = memalloc(sizeof(float) * SH_MAX);
	sh_sf = memalloc(sizeof(float) * SH_MAX);
	sh_gone = memalloc(sizeof(float) * SH_MAX);
	sh_col = memalloc(sizeof(vector) * SH_MAX);
	sh_alpha = memalloc(sizeof(float) * SH_MAX);
	gib_e = memalloc(sizeof(entity) * GIB_MAX);
	gib_v = memalloc(sizeof(vector) * GIB_MAX);
	gib_av = memalloc(sizeof(vector) * GIB_MAX);
	gib_die = memalloc(sizeof(float) * GIB_MAX);
	gib_grav = memalloc(sizeof(float) * GIB_MAX);
	gib_alpha = memalloc(sizeof(float) * GIB_MAX);
	gib_rest = memalloc(sizeof(float) * GIB_MAX);
};

float(float a, float b) Sh_Rand = { return a + random() * (b - a); };

// One gib from shooter i (SpawnGib / InitPointGib).
void(float i) Sh_Gib =
{
	local vector dir;
	local float g;
	local entity e;
	vbsp_sh_shots = vbsp_sh_shots + 1;
	if (vlen(sh_korg[i] - getproperty(VF_ORIGIN)) > SH_FAR)
		return;
	dir = sh_fw[i] + sh_rt[i] * Sh_Rand(-1, 1) * sh_var[i] + sh_fw[i] * Sh_Rand(-1, 1) * sh_var[i]
	      + sh_up[i] * Sh_Rand(-1, 1) * sh_var[i];
	dir = normalize(dir);
	g = gib_cur;
	gib_cur = gib_cur + 1;
	if (gib_cur >= GIB_MAX)
		gib_cur = 0;
	e = gib_e[g];
	if (!e)
	{
		e = spawn();
		e.classname = "shooter_gib";
		e.drawmask = MASK_ENGINE;
		gib_e[g] = e;
	}
	if (gib_die[g] <= 0)
		gib_live = gib_live + 1;
	setmodel(e, sh_mdl[i]);
	setorigin(e, sh_korg[i]);
	e.angles = sh_gang[i];
	e.skin = sh_skin[i];
	e.scale = 1;                // m_flGibScale is never applied to a model gib
	e.colormod = sh_col[i];
	e.alpha = sh_alpha[i];
	gib_alpha[g] = sh_alpha[i];
	gib_v[g] = dir * sh_vel[i];
	if (sh_sim[i] == 0)
		gib_av[g] = [Sh_Rand(100, 200), Sh_Rand(100, 300), 0];
	else
		gib_av[g] = [sh_gangv[i] * Sh_Rand(0.1, 1), sh_gangv[i] * Sh_Rand(0.1, 1), 0];
	gib_die[g] = (sh_sf[i] & 4) ? time + sh_life[i] * Sh_Rand(0.95, 1.05) : time + 1000000;
	gib_rest[g] = FALSE;
	gib_grav[g] = sh_grav[i];
};

// ENTWIRE_FXSTATE2 class FX_CLS_SHOOTER (Fx_Net forwards it): Shoot re-arms the think, now.
void(entity e) Sh_FxNet =
{
	local float i;
	if (!e.fx_nfire || !cvar("vbsp_shooters"))
		return;
	for (i = 0; i < sh_n; i = i + 1)
	{
		if (sh_tnc[i] != e.fx_ntnc || vlen(sh_korg[i] - e.origin) > 0.1 || sh_gone[i])
			continue;
		if (cvar("vbsp_fx_debug"))
			print(sprintf("shooter: %g shoots (%g left, every %g s)\n", i, sh_left[i], sh_delay[i]));
		if (!sh_next[i])
			sh_busy = sh_busy + 1;
		sh_next[i] = time;
		if (!gib_live)
			sh_last = time;
	}
};

// Called from Sprite_LoadForMap.
void() Sh_LoadForMap =
{
	local string tok, key, cn, tn, pn, mdl, scol;
	local vector org, ang, gang;
	local float i, sf, gibs, vel, vari, life, delay, gangv, sim, skin, scl, grav, ramt, rmode;

	Sh_Alloc();
	if (sh_n && sh_loadmap == CL_LumpMapName())	// P1489
		return;                 // a cvar toggle re-ran the load: keep the shooters and their gibs
	if (sh_loadmap != "")
		strunzone(sh_loadmap);
	sh_loadmap = strzone(CL_LumpMapName());
	for (i = 0; i < GIB_MAX; i = i + 1)
	{
		gib_die[i] = 0;
		if (gib_e[i])
		{
			remove(gib_e[i]);
			gib_e[i] = world;
		}
	}
	for (i = 0; i < sh_n; i = i + 1)
		if (sh_mdl[i] != "")
		{
			strunzone(sh_mdl[i]);
			sh_mdl[i] = "";
		}
	sh_n = vbsp_sh_n = vbsp_sh_skip = vbsp_sh_shots = sh_busy = gib_live = gib_cur = 0;
	if (!vbsp_sh_seen_n)
		return;
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = tn = pn = mdl = scol = "";
		org = ang = gang = '0 0 0';
		sf = gibs = vel = vari = life = delay = gangv = sim = skin = 0;
		scl = grav = 1;
		ramt = 255;
		rmode = 0;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if      (key == "classname")        cn = tok;
			else if (key == "origin")           org = Sprite_ParseVec(tok);
			else if (key == "angles")           ang = Sprite_ParseVec(tok);
			else if (key == "targetname")       tn = tok;
			else if (key == "parentname")       pn = tok;
			else if (key == "shootmodel")       mdl = tok;
			else if (key == "spawnflags")       sf = stof(tok);
			else if (key == "m_igibs")          gibs = stof(tok);
			else if (key == "m_flvelocity")     vel = stof(tok);
			else if (key == "m_flvariance")     vari = stof(tok);
			else if (key == "m_flgiblife")      life = stof(tok);
			else if (key == "delay")            delay = stof(tok);
			else if (key == "gibangles")        gang = Sprite_ParseVec(tok);
			else if (key == "gibanglevelocity") gangv = stof(tok);
			else if (key == "simulation")       sim = stof(tok);
			else if (key == "skin")             skin = stof(tok);
			else if (key == "scale")            scl = stof(tok);
			else if (key == "gibgravityscale")  grav = stof(tok);
			else if (key == "rendercolor")      scol = tok;
			else if (key == "renderamt")        ramt = stof(tok);
			else if (key == "rendermode")       rmode = stof(tok);
		}
		if (cn != "env_shooter" || tn == "")
			continue;
		if (pn != "" || sh_n >= SH_MAX || mdl == "" || substring(strtolower(mdl), strlen(mdl) - 4, 4) != ".mdl")
		{	// parented, over the cap, or no model (a sprite shootmodel is not drawn)
			vbsp_sh_skip = vbsp_sh_skip + 1;
			continue;
		}
		precache_model(mdl);
		i = sh_n;
		makevectors(ang);
		sh_korg[i] = org;
		sh_tnc[i] = crc16(TRUE, tn);
		sh_fw[i] = v_forward;
		sh_rt[i] = v_right;
		sh_up[i] = v_up;
		sh_cap[i] = sh_left[i] = gibs;
		sh_next[i] = 0;
		sh_vel[i] = vel;
		sh_var[i] = vari;
		sh_life[i] = (life == 0) ? 25 : life;
		sh_delay[i] = max(0, delay);
		sh_gang[i] = gang;
		sh_gangv[i] = gangv;
		sh_sim[i] = sim;
		sh_skin[i] = skin;
		sh_scale[i] = (scl > 0) ? scl : 1;
		sh_grav[i] = grav;
		sh_sf[i] = sf;
		sh_gone[i] = FALSE;
		sh_col[i] = (scol != "") ? Sprite_ParseColor(scol) : '1 1 1';
		sh_alpha[i] = rmode ? bound(0, ramt, 255) / 255 : 1;     // renderamt counts only with a render mode
		if (sh_alpha[i] <= 0)
			sh_alpha[i] = 1;
		sh_mdl[i] = strzone(mdl);
		sh_n = sh_n + 1;
	}
	vbsp_sh_n = sh_n;
	print(sprintf("shooters: %g of %g env_shooter kept for their inputs (%g declined: parented, no model)\n",
	              sh_n, vbsp_sh_seen_n, vbsp_sh_skip));
};

// Runs the shooters and moves the gibs; called from Sprite_Draw (before renderscene).  Returns live gibs.
float() Sh_Frame =
{
	local float i, k, dt, n, sp, sp0;
	local vector v, p, nrm;
	local entity e;

	if (!sh_busy && !gib_live)
		return 0;
	dt = time - sh_last;
	sh_last = time;
	if (dt < 0 || dt > 0.1)
		dt = (dt < 0) ? 0 : 0.1;
	if (sh_busy)
	for (i = 0; i < sh_n; i = i + 1)
	{
		if (!sh_next[i])
			continue;
		for (n = 0; n < 8 && sh_next[i] && time >= sh_next[i]; n = n + 1)
		{	// ShootThink, at most 8 a frame
			Sh_Gib(i);
			sh_left[i] = sh_left[i] - 1;
			if (sh_left[i] <= 0)
			{
				sh_next[i] = 0;
				sh_busy = sh_busy - 1;
				if (sh_sf[i] & 1)
					sh_left[i] = sh_cap[i];     // SF_GIBSHOOTER_REPEATABLE
				else
					sh_gone[i] = TRUE;          // SUB_Remove
			}
			else
				sh_next[i] = sh_next[i] + max(0.015, sh_delay[i]);
		}
		if (sh_next[i] && time - sh_next[i] > 1)
			sh_next[i] = time;                  // a long hitch: do not fire the backlog
	}
	n = 0;
	for (k = 0; k < GIB_MAX; k = k + 1)
	{
		if (gib_die[k] <= 0)
			continue;
		e = gib_e[k];
		if (time > gib_die[k])
		{	// strict remove: gone at once
			if (cvar("vbsp_fx_debug"))
				print(sprintf("gib: %g removed at z %.1f%s\n", k, e.origin_z, gib_rest[k] ? ", at rest" : ""));
			gib_die[k] = 0;
			e.drawmask = 0;
			continue;
		}
		e.drawmask = MASK_ENGINE;
		n = n + 1;
		if (!gib_rest[k])
		{
			v = gib_v[k];
			v_z = v_z - 800 * gib_grav[k] * dt;
			p = e.origin;
			traceline(p, p + v * dt, MOVE_NOMONSTERS, world);
			if (trace_allsolid)
			{
				if (cvar("vbsp_fx_debug"))
					print(sprintf("gib: %g stuck at z %.1f, dt %g, speed %.1f\n", k, p_z, dt, vlen(v)));
				gib_rest[k] = TRUE;
				gib_av[k] = '0 0 0';
				v = '0 0 0';
			}
			else if (trace_fraction < 1)
			{	// FLY_BOUNCE: the reflection times elasticity 0.25; under 30 u/s at rest, laid flat on a floor
				nrm = trace_plane_normal;
				p = trace_endpos + nrm * 0.5;
				sp0 = vlen(v);
				v = (v - nrm * (2 * (v * nrm))) * 0.25;
				sp = vlen(v);
				if (cvar("vbsp_fx_debug"))
					print(sprintf("gib: %g bounces %.1f -> %.1f u/s, normal z %.2f, at z %.1f%s\n", k,
					              sp0, sp, nrm_z, p_z, (sp < 30) ? ", rests" : ""));
				if (sp < 30)
				{
					gib_rest[k] = TRUE;
					v = '0 0 0';
					gib_av[k] = '0 0 0';
					if (nrm_z > 0.7)
						e.angles = [0, e.angles_y, 0];
				}
				setorigin(e, p);
			}
			else
				setorigin(e, p + v * dt);
			gib_v[k] = v;
			e.angles = e.angles + gib_av[k] * dt;
		}
	}
	gib_live = n;
	return n;
};
