/*
  cl_fx.qc -- P1430: look-only effects drawn from the entity lump, switched and fired by the server.

  Arcs: point_tesla (tesla.cpp, c_tesla.cpp FX_Tesla) and env_beam with no LightningEnd (EnvBeam.cpp
  RandomArea / RandomPoint).  A spark is a few beams from the source: two thirds aimed around it at
  even yaws from a random offset with a random pitch, the rest random, each traced out to the radius
  (three tries for a hit) and ending 8 units short of what it hit.  An arc is drawn as FX_SEGS jittered
  segments, re-jittered every frame (TE_BEAMTESLA's noise), additive, fading over its life, tapering to
  one unit at the far end (FX_BuildTesla's m_flEndWidth 1).

  State: ENTWIRE_FXSTATE (sv_entities.qc SV_FxSend) carries class, origin, name, on and an event count;
  a tesla fires a spark per new event (DoSpark) and sparks on its own interval while on.  env_beam arcs
  ride the laser wire (Laser_Net forwards here).
*/

#define FX_MAX        512       // arc sources a map
#define ARC_MAX       384       // live arcs
#define FX_SEGS       10
#define FX_CLS_TESLA  1         // ENTWIRE_FXSTATE classes (sh_defs.qc)
#define FX_CLS_BEAMARC 2

float  *fx_cls;
vector *fx_org;
float  *fx_rad;
vector *fx_col;
float  *fx_mat;
float  *fx_w0;
float  *fx_w1;
float  *fx_l0;
float  *fx_l1;
float  *fx_i0;
float  *fx_i1;
float  *fx_b0;
float  *fx_b1;
float  *fx_amp;
float  *fx_on;
float  *fx_next;
float  *fx_tnc;
vector *fx_korg;                // the entity's own origin, what the nets match

vector *arc_s;
vector *arc_e;
float  *arc_w;
vector *arc_col;
float  *arc_mat;
float  *arc_t0;
float  *arc_life;
float  *arc_amp;
float  arc_n;                   // ring cursor

void() Fx_Alloc =
{
	if (fx_cls)
		return;
	fx_cls = memalloc(sizeof(float) * FX_MAX);
	fx_org = memalloc(sizeof(vector) * FX_MAX);
	fx_rad = memalloc(sizeof(float) * FX_MAX);
	fx_col = memalloc(sizeof(vector) * FX_MAX);
	fx_mat = memalloc(sizeof(float) * FX_MAX);
	fx_w0 = memalloc(sizeof(float) * FX_MAX);
	fx_w1 = memalloc(sizeof(float) * FX_MAX);
	fx_l0 = memalloc(sizeof(float) * FX_MAX);
	fx_l1 = memalloc(sizeof(float) * FX_MAX);
	fx_i0 = memalloc(sizeof(float) * FX_MAX);
	fx_i1 = memalloc(sizeof(float) * FX_MAX);
	fx_b0 = memalloc(sizeof(float) * FX_MAX);
	fx_b1 = memalloc(sizeof(float) * FX_MAX);
	fx_amp = memalloc(sizeof(float) * FX_MAX);
	fx_on = memalloc(sizeof(float) * FX_MAX);
	fx_next = memalloc(sizeof(float) * FX_MAX);
	fx_tnc = memalloc(sizeof(float) * FX_MAX);
	fx_korg = memalloc(sizeof(vector) * FX_MAX);
	arc_s = memalloc(sizeof(vector) * ARC_MAX);
	arc_e = memalloc(sizeof(vector) * ARC_MAX);
	arc_w = memalloc(sizeof(float) * ARC_MAX);
	arc_col = memalloc(sizeof(vector) * ARC_MAX);
	arc_mat = memalloc(sizeof(float) * ARC_MAX);
	arc_t0 = memalloc(sizeof(float) * ARC_MAX);
	arc_life = memalloc(sizeof(float) * ARC_MAX);
	arc_amp = memalloc(sizeof(float) * ARC_MAX);
};

// One spark from source i: its beams, each traced to the radius.
void(float i) Fx_Spark =
{
	local float n, k, around, yawoff, tries, a;
	local vector dir, endp;

	endp = fx_org[i];

	n = rint(fx_b0[i] + random() * (fx_b1[i] - fx_b0[i]));
	if (n < 1)
		n = 1;
	around = floor(n * 2 / 3);
	yawoff = random() * 360;
	for (k = 0; k < n; k = k + 1)
	{
		tries = 0;
		do
		{
			if (k < around)
			{
				makevectors([0, yawoff + 360 / n * k, 0]);
				dir = v_forward;
				dir_z = random() * 2 - 1;
			}
			else
				dir = [random() * 2 - 1, random() * 2 - 1, random() * 2 - 1];
			dir = normalize(dir);
			traceline(fx_org[i], fx_org[i] + dir * fx_rad[i], MOVE_NOMONSTERS, world);
			tries = tries + 1;
		} while (trace_fraction >= 1 && tries < 4);
		endp = trace_endpos - dir * 8;
		a = arc_n;
		arc_n = arc_n + 1;
		if (arc_n >= ARC_MAX)
			arc_n = 0;
		arc_s[a] = fx_org[i];
		arc_e[a] = endp;
		arc_w[a] = fx_w0[i] + random() * (fx_w1[i] - fx_w0[i]);
		arc_col[a] = fx_col[i];
		arc_mat[a] = fx_mat[i];
		arc_t0[a] = time;
		arc_life[a] = max(0.05, fx_l0[i] + random() * (fx_l1[i] - fx_l0[i]));
		arc_amp[a] = fx_amp[i];
	}
	if (cvar("vbsp_fx_debug"))
		print(sprintf("fx: spark at %v: %g arcs, last to %v (radius %g, mat %g)\n", fx_org[i], n, endp, fx_rad[i], fx_mat[i]));
};

void(entity e) Fx_Net;

// The lump: point_tesla, and env_beam with no LightningEnd (from its LightningStart, else itself).
void(float want) Fx_LoadForMap =
{
	local string tok, key, cn, tn, pn, tex, scol, ls, le, mon;
	local vector org, col;
	local float sf, ramt, rad, w0, w1, l0, l1, i0, i1, b0, b1, amp, life, strike, bw, i, k;
	local hashtable names;
	local entity net;

	Fx_Alloc();
	fx_n = 0;
	vbsp_fx_tesla = vbsp_fx_arc = vbsp_fx_skip = 0;
	for (k = 0; k < ARC_MAX; k = k + 1)
		arc_life[k] = 0;
	if (!want)
		return;
	names = hash_createtab(64, EV_VECTOR);
	// Pass 1: every named entity's origin (first of each name, as BeamUpdateVars finds it).
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		tn = "";
		org = '0 0 0';
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			if (key == "targetname") tn = tok;
			else if (key == "origin") org = Sprite_ParseVec(tok);
		}
		if (tn != "")
		if (hash_get(names, strtolower(tn), '0 0 -99999', EV_VECTOR) == '0 0 -99999')
			hash_add(names, strtolower(tn), org, HASH_REPLACE | EV_VECTOR);
	}
	// Pass 2: the sources.
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = tn = pn = tex = scol = ls = le = mon = "";
		org = '0 0 0';
		sf = rad = life = strike = bw = amp = 0;
		ramt = 255;
		w0 = w1 = 5;            // CTesla's constructor
		l0 = 0.3;
		l1 = 0.55;
		i0 = i1 = 0.5;
		b0 = b1 = 6;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if      (key == "classname")      cn = tok;
			else if (key == "origin")         org = Sprite_ParseVec(tok);
			else if (key == "targetname")     tn = tok;
			else if (key == "parentname")     pn = tok;
			else if (key == "texture")        tex = tok;
			else if (key == "m_color" || key == "rendercolor") scol = tok;
			else if (key == "renderamt")      ramt = stof(tok);
			else if (key == "spawnflags")     sf = stof(tok);
			else if (key == "m_flradius" || key == "radius") rad = stof(tok);
			else if (key == "thick_min")      w0 = stof(tok);
			else if (key == "thick_max")      w1 = stof(tok);
			else if (key == "lifetime_min")   l0 = stof(tok);
			else if (key == "lifetime_max")   l1 = stof(tok);
			else if (key == "interval_min")   i0 = stof(tok);
			else if (key == "interval_max")   i1 = stof(tok);
			else if (key == "beamcount_min")  b0 = stof(tok);
			else if (key == "beamcount_max")  b1 = stof(tok);
			else if (key == "m_bon")          mon = tok;
			else if (key == "lightningstart") ls = tok;
			else if (key == "lightningend")   le = tok;
			else if (key == "life")           life = stof(tok);
			else if (key == "striketime")     strike = stof(tok);
			else if (key == "boltwidth")      bw = stof(tok);
			else if (key == "noiseamplitude") amp = stof(tok);
		}
		if (cn != "point_tesla")
		if (!(cn == "env_beam" && le == ""))
			continue;
		if (pn != "" || fx_n >= FX_MAX)
		{
			vbsp_fx_skip = vbsp_fx_skip + 1;
			continue;
		}
		i = fx_n;
		fx_korg[i] = org;
		col = '1 1 1';
		if (scol != "")
			col = Sprite_ParseColor(scol);
		if (cn == "point_tesla")
		{
			if (tex == "")
				tex = "sprites/physbeam.vmt";
			fx_cls[i] = FX_CLS_TESLA;
			fx_org[i] = org;
			fx_rad[i] = (rad > 0) ? rad : 200;
			fx_w0[i] = w0 * 2;          // drawn width twice the key, as the lasers' (beamdraw.cpp)
			fx_w1[i] = w1 * 2;
			fx_l0[i] = l0;
			fx_l1[i] = l1;
			fx_i0[i] = i0;
			fx_i1[i] = i1;
			fx_b0[i] = b0;
			fx_b1[i] = b1;
			fx_amp[i] = 16;             // FX_BuildTesla's amplitude
			fx_col[i] = col * (200 / 255);   // m_flBrightness 200
			fx_on[i] = (stof(mon) != 0);
			vbsp_fx_tesla = vbsp_fx_tesla + 1;
		}
		else
		{	// env_beam RandomArea (no start) / RandomPoint (from the start): one beam a strike
			if (ls != "")
			{
				org = hash_get(names, strtolower(ls), '0 0 -99999', EV_VECTOR);
				if (org == '0 0 -99999')
				{
					vbsp_fx_skip = vbsp_fx_skip + 1;
					continue;
				}
			}
			fx_cls[i] = FX_CLS_BEAMARC;
			fx_org[i] = org;
			fx_rad[i] = (rad > 0) ? rad : 256;
			fx_w0[i] = fx_w1[i] = bound(0.1, bw, 102.3) * 2;
			fx_l0[i] = fx_l1[i] = (life > 0) ? life : 0.1;
			fx_i0[i] = fx_l0[i];
			fx_i1[i] = fx_l0[i] + strike;
			if (!(sf & 4))
				fx_i0[i] = fx_i1[i];    // without SF_BEAM_RANDOM the restrike is fixed
			fx_b0[i] = fx_b1[i] = 1;
			fx_amp[i] = amp;
			fx_col[i] = col * ((ramt & 255) / 255);
			fx_on[i] = !(tn != "" && !(sf & 1));
			vbsp_fx_arc = vbsp_fx_arc + 1;
		}
		fx_mat[i] = Sprite_Material(tex, 0);
		if (fx_mat[i] < 0)
		{
			vbsp_fx_skip = vbsp_fx_skip + 1;
			continue;
		}
		fx_tnc[i] = crc16(TRUE, tn);
		fx_next[i] = time + random() * fx_i1[i];
		fx_n = fx_n + 1;
	}
	hash_destroytab(names);
	for (net = find(world, classname, "fx_net"); net; net = find(net, classname, "fx_net"))
		Fx_Net(net);            // states that arrived before this load (their fire count is spent: 0)
};

// ENTWIRE_FXSTATE (cl_body.qc): on, and the sparks the new events ask for.
.float fx_ncls, fx_ntnc, fx_non, fx_nfire;

float fx_dbg_t;

void(entity e) Fx_Net =
{
	local float i, k;
	if (cvar("vbsp_fx_debug"))
		print(sprintf("fx: net class %g at %v name %g on %g fire %g (%g sources)\n", e.fx_ncls, e.origin, e.fx_ntnc, e.fx_non, e.fx_nfire, fx_n));
	for (i = 0; i < fx_n; i = i + 1)
	{
		if (fx_cls[i] != e.fx_ncls || fx_tnc[i] != e.fx_ntnc || vlen(fx_korg[i] - e.origin) > 0.1)
			continue;
		fx_on[i] = e.fx_non;
		for (k = 0; k < e.fx_nfire; k = k + 1)
			Fx_Spark(i);
		if (fx_on[i])
			fx_next[i] = time + fx_i0[i] + random() * (fx_i1[i] - fx_i0[i]);
	}
};

// The laser wire's on/off, for env_beam arcs (Laser_Net forwards it).
void(entity e) Fx_LaserNet =
{
	local float i;
	for (i = 0; i < fx_n; i = i + 1)
		if (fx_cls[i] == FX_CLS_BEAMARC && fx_tnc[i] == e.las_nettnc && vlen(fx_korg[i] - e.origin) < 0.1)
			fx_on[i] = e.las_neton;
};

// Sources spark on their interval; arcs draw.  Called beside Laser_Draw; returns the arcs drawn.
float(vector eye, vector fwd, float maxdist) Fx_Draw =
{
	local float i, k, a, age, fade, drawn, len, half, rad, ha, hb;
	local vector p, q, dir, sp, pa, pb, side, up, col, spa, spb;
	local string mat;

	if (!fx_n)
		return 0;
	for (i = 0; i < fx_n; i = i + 1)
	{
		if (!fx_on[i])
			continue;
		if (time < fx_next[i] && time > fx_next[i] - 60)
			continue;
		fx_next[i] = time + fx_i0[i] + random() * (fx_i1[i] - fx_i0[i]);
		if (maxdist > 0 && vlen(fx_org[i] - eye) - fx_rad[i] > maxdist)
			continue;
		Fx_Spark(i);
	}
	drawn = 0;
	for (a = 0; a < ARC_MAX; a = a + 1)
	{
		if (arc_life[a] <= 0)
			continue;
		age = time - arc_t0[a];
		if (age >= arc_life[a] || age < 0)
		{
			arc_life[a] = 0;
			continue;
		}
		p = arc_s[a];
		q = arc_e[a];
		dir = q - p;
		len = vlen(dir);
		if (len < 1)
			continue;
		rad = len * 0.5 + arc_amp[a];
		if (fwd * ((p + q) * 0.5 - eye) < -rad)
			continue;
		if (maxdist > 0 && vlen((p + q) * 0.5 - eye) - rad > maxdist)
			continue;
		dir = dir * (1 / len);
		fade = 1 - age / arc_life[a];
		col = arc_col[a] * fade;
		half = arc_w[a] * 0.5;
		mat = sprmat_name[arc_mat[a]];
		side = normalize(crossproduct(dir, '0 0 1'));
		if (side * side < 0.5)
			side = '1 0 0';
		up = crossproduct(side, dir);
		pa = p;
		for (k = 1; k <= FX_SEGS; k = k + 1)
		{
			pb = p + dir * (len * k / FX_SEGS);
			if (k < FX_SEGS)
				pb = pb + (side * (random() * 2 - 1) + up * (random() * 2 - 1)) * arc_amp[a];
			sp = crossproduct(pb - pa, pa - eye);
			if (sp * sp > 0.0001)
			{
				sp = normalize(sp);
				ha = half + (0.5 - half) * (k - 1) / FX_SEGS;
				hb = half + (0.5 - half) * k / FX_SEGS;
				spa = sp * ha;
				spb = sp * hb;
				R_BeginPolygon(mat, DRAWFLAG_ADD);
				R_PolygonVertex(pa - spa, [0, (k - 1) / FX_SEGS, 0], col, 1);
				R_PolygonVertex(pa + spa, [1, (k - 1) / FX_SEGS, 0], col, 1);
				R_PolygonVertex(pb + spb, [1, k / FX_SEGS, 0], col, 1);
				R_PolygonVertex(pb - spb, [0, k / FX_SEGS, 0], col, 1);
				R_EndPolygon();
			}
			pa = pb;
		}
		drawn = drawn + 1;
	}
	if (cvar("vbsp_fx_debug"))
	if (time > fx_dbg_t)
	{
		fx_dbg_t = time + 1;
		print(sprintf("fx: %g arcs drawn this frame, %g sources\n", drawn, fx_n));
	}
	return drawn;
};
