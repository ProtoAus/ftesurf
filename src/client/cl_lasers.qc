/*
  cl_lasers.qc -- Source's env_laser, drawn from the entity lump.  P1252, Phase A:
  static lasers only.

  CEnvLaser (EnvLaser.cpp StrikeThink) traces MASK_SOLID from its origin to a random
  entity named LaserTarget, every think.  Nothing kept here moves, so one trace at
  load gives the same end.  Declined and counted: one with a parentname, one whose
  target is parented or a mover, one with no target entity, one whose material does
  not resolve.  P1256: a laser that starts off is kept, undrawn; the server's edict
  (SV_LaserInput) sends TurnOn/TurnOff/Toggle, applied by Laser_Net.

  Each (laser, target) pair is one entry in cl_sprites.qc's beam table after the
  shafts (beam_spot_n .. beam_n), so Sprite_SkyTick and the distance/behind culls
  cover it.  Several entities sharing the target name make a group: one entry is
  drawn, re-picked every LAS_REPICK.  Entries are emitted material by material so
  consecutive polygons batch (pr_csqc.c:1671).

  The look, from the SDK: additive (view_beams.cpp:1952, no FBEAM_SOLID), colour
  rendercolor/255 times FxBlend/255, and FxBlend is 255 under kRenderNormal and
  renderamt otherwise (c_baseentity.cpp:3502-3508); drawn width twice the key
  (beamdraw.cpp DrawSegs); texture v runs length*0.01 from the laser, offset
  fmod(curtime * speed^2, 1) where speed = atoi(TextureScroll) * 0.1
  (RecvProxy_Beam_ScrollSpeed).  NoiseAmplitude and renderfx are not drawn.
*/

#define LAS_MAX       1024      // lasers staged a map; worst (surf_s_t_a_t_i_o_n) is 232
#define LAS_TGT_MAX   4096      // entities carrying a wanted target name
#define LAS_REPICK    0.015     // one think at 66 tick

// Per beam entry, indexed by (beam index - beam_spot_n); BEAM_MAX long.
float *las_mat;                 // sprmat index
float *las_speed;               // texture lengths a second, speed^2
float *las_grp;                 // the entry heading this entry's group
float *las_cnt;                 // at a head: entries in the group
float *las_pick;                // at a head: the entry drawn now
float *las_next;                // at a head: when to pick again
float *las_on;                  // at a head: drawn; the lump's start state until the server says (P1256)
float *las_tnc;                 // at a head: crc16 of its targetname, with the origin what Laser_Net matches

// Load-time staging: per laser (LAS_MAX), per target name (LAS_MAX), per target (LAS_TGT_MAX).
vector *lsg_org;
vector *lsg_col;                // colour times brightness
float *lsg_wid;                 // full width
float *lsg_speed;
float *lsg_mat;
float *lsg_name;                // its target name's index; -1 once declined
float *lsg_on;
float *lsg_tnc;
float *lname_head;              // first target + 1, 0 = none
vector *ltgt_org;
float *ltgt_mov;
float *ltgt_next;               // next target with the same name + 1

// Classes a target can move with (func_brush can be parented or toggled).  A
// parented target of any class is caught by its parentname instead.
float(string cn) Laser_Mover =
{
	if (cn == "func_tracktrain" || cn == "func_tanktrain" || cn == "func_train" ||
	    cn == "path_track" || cn == "path_corner" || cn == "func_door" ||
	    cn == "func_door_rotating" || cn == "func_rotating" || cn == "func_movelinear" ||
	    cn == "func_plat" || cn == "func_platrot" || cn == "func_button" ||
	    cn == "func_rot_button" || cn == "momentary_rot_button" || cn == "func_physbox" ||
	    cn == "func_brush" || cn == "phys_bone_follower")
		return TRUE;
	if (substring(cn, 0, 12) == "prop_dynamic" || substring(cn, 0, 12) == "prop_physics")
		return TRUE;
	return FALSE;
};

// P1256: one laser's on/off from the server (SV_LaserSend, cl_body.qc), on the laser with that origin
// and name.  Kept on the entity, so a load after it arrives reapplies it.
.float las_neton, las_nettnc;

void(entity e) Laser_Net =
{
	local float i, k;

	if (!las_on)
		return;
	for (i = beam_spot_n; i < beam_n; i = i + 1)
	{
		k = i - beam_spot_n;
		if (las_grp[k] == k && las_tnc[k] == e.las_nettnc && vlen(beam_org[i] - e.origin) < 0.1)
			las_on[k] = e.las_neton;
	}
	if (cvar("developer") >= 2)     // one line per laser: ~240 a second on surf_hyper
		print(sprintf("lasers: the laser at %v turned %s by the server\n", e.origin, e.las_neton ? "on" : "off"));
};

void(float want) Laser_LoadForMap =
{
	local string tok, key, cn, tn, pn, lt, tex, scol;
	local vector org, col, endp;
	local float  sf, rmode, ramt, wid, ts, nl, nn, nt, l, w, t, n, mov, m, e, h, lost;
	local hashtable names;
	local entity net;

	// vbsp_las_seen is counted by Sprite_LoadForMap's walk.
	vbsp_las_n = vbsp_las_off = vbsp_las_notgt = 0;
	vbsp_las_parent = vbsp_las_moving = vbsp_las_nomat = vbsp_las_over = 0;
	las_drawn = 0;
	if (!want || !vbsp_las_seen)
		return;

	if (!las_mat)
	{
		las_mat    = memalloc(sizeof(float) * BEAM_MAX);
		las_speed  = memalloc(sizeof(float) * BEAM_MAX);
		las_grp    = memalloc(sizeof(float) * BEAM_MAX);
		las_cnt    = memalloc(sizeof(float) * BEAM_MAX);
		las_pick   = memalloc(sizeof(float) * BEAM_MAX);
		las_next   = memalloc(sizeof(float) * BEAM_MAX);
		las_on     = memalloc(sizeof(float) * BEAM_MAX);
		lsg_on     = memalloc(sizeof(float) * LAS_MAX);
		las_tnc    = memalloc(sizeof(float) * BEAM_MAX);
		lsg_tnc    = memalloc(sizeof(float) * LAS_MAX);
		lsg_org    = memalloc(sizeof(vector) * LAS_MAX);
		lsg_col    = memalloc(sizeof(vector) * LAS_MAX);
		lsg_wid    = memalloc(sizeof(float) * LAS_MAX);
		lsg_speed  = memalloc(sizeof(float) * LAS_MAX);
		lsg_mat    = memalloc(sizeof(float) * LAS_MAX);
		lsg_name   = memalloc(sizeof(float) * LAS_MAX);
		lname_head = memalloc(sizeof(float) * LAS_MAX);
		ltgt_org   = memalloc(sizeof(vector) * LAS_TGT_MAX);
		ltgt_mov   = memalloc(sizeof(float) * LAS_TGT_MAX);
		ltgt_next  = memalloc(sizeof(float) * LAS_TGT_MAX);
	}

	names = hash_createtab(256, EV_FLOAT);
	nl = nn = nt = lost = 0;

	// Pass 1: the lasers, and the names they want.
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = tn = pn = lt = tex = scol = "";
		org = '0 0 0';
		sf = rmode = wid = ts = 0;
		ramt = 255;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			if      (key == "classname")   cn = tok;
			else if (key == "origin")      org = Sprite_ParseVec(tok);
			else if (key == "targetname")  tn = tok;
			else if (key == "parentname")  pn = tok;
			else if (key == "texture")     tex = tok;
			else if (key == "rendercolor") scol = tok;
			else if (key == "renderamt")   ramt = stof(tok);
			else if (key == "rendermode")  rmode = stof(tok);
			else if (key == "spawnflags")  sf = stof(tok);
			// Source matches keys case-blind (FStrEq); the library writes both of each
			// ("Width" on 6 lasers, bhop_avantasia and bhop_backrooms).
			else if (key == "width"         || key == "Width")         wid = stof(tok);
			else if (key == "LaserTarget"   || key == "lasertarget")   lt = tok;
			else if (key == "TextureScroll" || key == "texturescroll") ts = stof(tok);
		}
		if (cn != "env_laser")
			continue;

		if (pn != "")
		{
			vbsp_las_parent = vbsp_las_parent + 1;
			continue;
		}
		// No target: StrikeThink fires at its own end point, which PointsInit set to the origin.
		if (lt == "")
		{
			vbsp_las_notgt = vbsp_las_notgt + 1;
			continue;
		}
		if (nl >= LAS_MAX)
		{
			vbsp_las_over = vbsp_las_over + 1;
			continue;
		}

		// Names match case-blind in Source (NamesMatch); the hash is case-exact.
		lt = strtolower(lt);
		w = hash_get(names, lt, -1, EV_FLOAT);
		if (w < 0)
		{
			w = nn;
			nn = nn + 1;
			hash_add(names, lt, w, HASH_REPLACE | EV_FLOAT);
			lname_head[w] = 0;
		}

		col = '1 1 1';
		if (scol != "")
			col = Sprite_ParseColor(scol);
		if (rmode != 0)
			col = col * ((ramt & 255) / 255);

		// SetWidth caps it at MAX_BEAM_WIDTH; the send table's 10 bits step it by ~0.1 and
		// SPROP_ROUNDUP lifts the bottom a step, so 0 arrives as 0.1 (beam_shared.cpp:164).
		wid = bound(0.1, floor(wid * 10 + 0.5) * 0.1, 102.3);
		ts = floor(fabs(ts)) * 0.1;     // atoi truncates; the sign is squared away

		lsg_org[nl]   = org;
		lsg_col[nl]   = col;
		lsg_wid[nl]   = wid * 2;
		lsg_speed[nl] = ts * ts;
		lsg_mat[nl]   = Sprite_Material(tex, 0);   // "" resolves to -1, as Spawn removes it
		lsg_name[nl]  = w;
		lsg_on[nl]    = !(tn != "" && !(sf & 1));  // CEnvLaser::Spawn: off when named without SF_BEAM_STARTON
		lsg_tnc[nl]   = crc16(TRUE, tn);           // 79 lasers share an origin with a differently named one
		nl = nl + 1;
	}

	// Pass 2: every entity carrying a wanted name.  One name may be on many.
	if (nn > 0)
	{
		getentitytoken(0);
		while ((tok = getentitytoken()) != "")
		{
			if (tok != "{")
				continue;
			cn = tn = pn = "";
			org = '0 0 0';
			while ((key = getentitytoken()) != "" && key != "}")
			{
				tok = getentitytoken();
				if      (key == "classname")  cn = tok;
				else if (key == "targetname") tn = tok;
				else if (key == "parentname") pn = tok;
				else if (key == "origin")     org = Sprite_ParseVec(tok);
			}
			if (tn == "")
				continue;
			w = hash_get(names, strtolower(tn), -1, EV_FLOAT);
			if (w < 0)
				continue;
			if (nt >= LAS_TGT_MAX)
			{
				lost = lost + 1;
				continue;
			}
			ltgt_org[nt]  = org;
			ltgt_mov[nt]  = (pn != "" || Laser_Mover(cn));
			ltgt_next[nt] = lname_head[w];
			lname_head[w] = nt + 1;
			nt = nt + 1;
		}
	}
	hash_destroytab(names);
	if (lost)
		dprint(sprintf("lasers: %g target entities past LAS_TGT_MAX ignored\n", lost));

	// Which bucket each staged laser lands in.
	for (l = 0; l < nl; l = l + 1)
	{
		n = mov = 0;
		for (t = lname_head[lsg_name[l]]; t > 0; t = ltgt_next[t - 1])
		{
			n = n + 1;
			if (ltgt_mov[t - 1])
				mov = TRUE;
		}
		if (!n)
		{
			vbsp_las_notgt = vbsp_las_notgt + 1;
			lsg_name[l] = -1;
		}
		else if (mov)
		{
			vbsp_las_moving = vbsp_las_moving + 1;
			lsg_name[l] = -1;
		}
		else if (lsg_mat[l] < 0)
		{
			vbsp_las_nomat = vbsp_las_nomat + 1;
			lsg_name[l] = -1;
		}
	}

	// Emit material by material, one entry per target, each traced once.
	for (m = 0; m < sprmat_n; m = m + 1)
	{
		for (l = 0; l < nl; l = l + 1)
		{
			if (lsg_name[l] < 0)
				continue;
			if (lsg_mat[l] != m)
				continue;

			n = 0;
			for (t = lname_head[lsg_name[l]]; t > 0; t = ltgt_next[t - 1])
				n = n + 1;
			if (beam_n + n > BEAM_MAX)
			{
				vbsp_las_over = vbsp_las_over + 1;
				continue;
			}

			h = beam_n - beam_spot_n;
			org = lsg_org[l];
			for (t = lname_head[lsg_name[l]]; t > 0; t = ltgt_next[t - 1])
			{
				// Sees the world and Sprite_LoadOccluders' brush copies, as Beam_Add does.
				endp = ltgt_org[t - 1];
				traceline(org, endp, MOVE_NOMONSTERS, world);
				if (trace_fraction < 1)
					endp = trace_endpos;

				e = beam_n;
				beam_org[e] = org;
				beam_end[e] = endp;
				beam_col[e] = lsg_col[l];
				beam_w0[e]  = lsg_wid[l];
				beam_w1[e]  = lsg_wid[l];
				beam_rad[e] = vlen(endp - org) * 0.5 + lsg_wid[l];
				beam_sky[e] = SKY_UNTESTED;
				las_mat[e - beam_spot_n]   = m;
				las_speed[e - beam_spot_n] = lsg_speed[l];
				las_grp[e - beam_spot_n]   = h;
				beam_n = beam_n + 1;
			}
			las_cnt[h]  = n;
			las_pick[h] = h + floor(random() * n);
			las_next[h] = 0;
			las_on[h]   = lsg_on[l];
			las_tnc[h]  = lsg_tnc[l];
			vbsp_las_n = vbsp_las_n + 1;
			if (!lsg_on[l])
				vbsp_las_off = vbsp_las_off + 1;
		}
	}

	for (net = find(world, classname, "laser_net"); net; net = find(net, classname, "laser_net"))
		Laser_Net(net);
};

// Called from Sprite_Draw after the shafts; returns the beams drawn.
float(vector eye, vector fwd, float maxdist, float skyon) Laser_Draw =
{
	local float  i, k, h, len, half, v, tm, m, drawn;
	local vector dir, dd, p, q, sp, col;
	local string mat;

	drawn = 0;
	// speed*100 is a whole number, so a 100 s period keeps the scroll exact and float time small.
	tm = time - 100 * floor(time * 0.01);
	for (i = beam_spot_n; i < beam_n; i = i + 1)
	{
		k = i - beam_spot_n;
		h = las_grp[k];
		if (!las_on[h])
			continue;
		if (las_cnt[h] > 1)
		{
			// The second test catches time running backwards (a demo seek, a reconnect).
			if (time >= las_next[h] || time < las_next[h] - 1)
			{
				las_pick[h] = h + floor(random() * las_cnt[h]);
				las_next[h] = time + LAS_REPICK;
			}
			if (las_pick[h] != k)
				continue;
		}
		if (skyon && beam_sky[i] == SKY_BEHIND)
		{
			spr_skyhid = spr_skyhid + 1;
			continue;
		}

		dd = (beam_org[i] + beam_end[i]) * 0.5 - eye;
		if (maxdist > 0 && vlen(dd) - beam_rad[i] > maxdist)
			continue;
		if (fwd * dd < -beam_rad[i])
			continue;

		dir = beam_end[i] - beam_org[i];
		len = vlen(dir);
		if (len < 1)
			continue;
		dir = dir * (1 / len);

		// Across the beam, facing the eye: cross(dir, point - eye) is the same at every point of a
		// straight beam, so one quad is what CBeamSegDraw's per-point segments draw.
		half = beam_w0[i] * 0.5;
		col = beam_col[i];
		m = las_mat[k];
		mat = sprmat_name[m];
		v = tm * las_speed[k];
		v = v - floor(v);
		p = beam_org[i];
		q = beam_end[i];
		sp = crossproduct(dir, p - eye);
		if (sp * sp < 0.0001)
			sp = crossproduct(dir, fwd);	// the eye on the beam's line: it is a point anyway
		if (sp * sp < 0.0001)
			continue;
		sp = normalize(sp) * half;
		R_BeginPolygon(mat, DRAWFLAG_ADD);
		R_PolygonVertex(p - sp, [0, v, 0], col, 1);
		R_PolygonVertex(p + sp, [1, v, 0], col, 1);
		R_PolygonVertex(q + sp, [1, v + len * 0.01, 0], col, 1);
		R_PolygonVertex(q - sp, [0, v + len * 0.01, 0], col, 1);
		R_EndPolygon();
		drawn = drawn + 1;
	}
	las_drawn = drawn;
	return drawn;
};
