/*
===========================================================================
  cl_proximity.qc -- Source's PlayerProximity fade on brush entities (Patch 810).

  proxyplayer.cpp:45-60 writes |entity WorldSpaceCenter - local player WorldSpaceCenter| * scale
  into a material var on every bind.  surf_tripportals' neon (plar/plars_hell_window*, 279
  func_brush) feeds that to Subtract($one, d) -> $alpha, so each piece fades out as one unit with
  distance from the player.  One value per entity, so it is computed here and written to the
  entity's alpha.  twotexture.glsl bakes the same chain per fragment from the eye; this is the
  per-entity form, and through a portal it still measures from the player, as Source does.

  One shape: $alpha <- Subtract(A, P), P <- PlayerProximity, with A and P's result vars the
  material declares (Source drops a proxy whose var is not found, functionproxy.cpp:136-139,
  209-221).  And only on the material arm that can show it: an UnlitGeneric with a $basetexture
  and no $additive, $alpha, $alphatest, $vertexalpha, emissive blend or AnimatedTexture is a plain
  pass with alphaGen identity (mat_vmt.c, the UnlitGeneric arm), which takes the entity's alpha
  once it is below 1 (RF_TRANSLUCENT -> BEF_FORCETRANSPARENT -> gl_backend.c:3054-3058).  The
  others go to a program, a constant or vertex alphaGen, or an alpha test, and would pop or cut
  instead of fading.  A model with any other material is declined too, because an entity alpha
  fades every face of it.  The engine draws a declined model as before.
===========================================================================
*/

#define PROX_MAX    1024
#define PROX_PMAX   16
#define PROX_VMAX   32

float   prox_n, prox_declined, prox_over, prox_mats_n, prox_gen;
float   prox_mode;              // vbsp_proximity: 0 the engine draws them, 1 fade, 2 drawn here unfaded
float   prox_mi[PROX_MAX];
float   prox_scale[PROX_MAX];
float   prox_base[PROX_MAX];
vector  prox_ctr[PROX_MAX];
string  prox_map;
string  prox_mats;              // "\n<material>=<scale> <base>\n", or "=-" for no fade; zoned
vector  prox_eye;               // the measuring point, once a frame
float   prox_drawn, prox_out, prox_calls;   // the last frame's callbacks, for vbsp_proximity_debug
.float  prox_slot;              // 1 + table index; 0 when the model is not one of ours
.float  prox_seen;              // the prox_gen prox_slot was looked up in
.float  prox_model;             // ...and the modelindex
.vector prox_at;                // where it was last linked

// One VMT's Proxies, in file order, and its top-level vars.  Zoned; Prox_ClearVMT frees them.
float   pk_n, pv_n, pk_cur, pk_over;
string  pk_shader;
string  pk_kind[PROX_PMAX];
string  pk_res[PROX_PMAX];
string  pk_s1[PROX_PMAX];
string  pk_s2[PROX_PMAX];
float   pk_scale[PROX_PMAX];
string  pv_name[PROX_VMAX];
string  pv_val[PROX_VMAX];

void() Prox_ClearVMT =
{
	local float i;
	for (i = 0; i < pk_n; i = i + 1)
	{
		strunzone(pk_kind[i]); strunzone(pk_res[i]); strunzone(pk_s1[i]); strunzone(pk_s2[i]);
	}
	for (i = 0; i < pv_n; i = i + 1)
	{
		strunzone(pv_name[i]); strunzone(pv_val[i]);
	}
	pk_n = pv_n = pk_over = 0;
	if (pk_shader != "")
		strunzone(pk_shader);
	pk_shader = "";
};

void(float d, string b2, string key, string val) Prox_KeyValue =
{
	local float k;

	if (d == 1 && substring(key, 0, 1) == "$")
	{
		if (pv_n >= PROX_VMAX)
		{
			pk_over = TRUE;
			return;
		}
		pv_name[pv_n] = strzone(key);
		pv_val[pv_n] = strzone(val);
		pv_n = pv_n + 1;
		return;
	}
	if (d != 3 || b2 != "proxies" || pk_cur < 0)
		return;
	k = pk_cur;
	if (key == "resultvar")     { strunzone(pk_res[k]); pk_res[k] = strzone(val); }
	else if (key == "srcvar1")  { strunzone(pk_s1[k]);  pk_s1[k]  = strzone(val); }
	else if (key == "srcvar2")  { strunzone(pk_s2[k]);  pk_s2[k]  = strzone(val); }
	else if (key == "scale")    pk_scale[k] = stof(val);
};

// KeyValues as a token stream, so a block name and its brace may sit on different lines.  One
// key and value per line: a third token, such as [$X360], is not a key.  FALSE when the file
// cannot be read or is a patch (its include is not followed).
float(string m) Prox_ReadVMT =
{
	local float fh, i, j, n, d, took;
	local string ln, t, key, b1, b2, b3;

	Prox_ClearVMT();
	fh = fopen(strcat("materials/", m, ".vmt"), FILE_READ);
	if (fh < 0)
		return FALSE;
	d = 0;
	pk_cur = -1;
	key = b1 = b2 = b3 = "";
	for (i = 0; i < 400; i = i + 1)
	{
		ln = fgets(fh);
		if (ln == "")
			continue;               // a blank line or the end; fgets cannot tell them apart
		j = strstrofs(ln, "//");
		if (j >= 0)
			ln = substring(ln, 0, j);
		ln = strreplace("{", " { ", strreplace("}", " } ", strtolower(ln)));
		n = tokenize_console(ln);
		took = FALSE;
		for (j = 0; j < n; j = j + 1)
		{
			t = argv(j);
			if (t == "{")
			{
				d = d + 1;
				if (d == 1) b1 = key;
				else if (d == 2) b2 = key;
				else if (d == 3) b3 = key;
				if (d == 3)
					pk_cur = -1;
				if (d == 3 && b2 == "proxies")
				{
					if (pk_n >= PROX_PMAX)
						pk_over = TRUE;
					else
					{
						pk_cur = pk_n;
						pk_kind[pk_n] = strzone(b3);
						pk_res[pk_n] = strzone("");
						pk_s1[pk_n] = strzone("");
						pk_s2[pk_n] = strzone("");
						pk_scale[pk_n] = (b3 == "playerproximity") ? 0.002 : 0;   // proxyplayer.cpp:41
						pk_n = pk_n + 1;
					}
				}
				key = "";
			}
			else if (t == "}")
			{
				d = d - 1;
				key = "";
			}
			else if (took)
				continue;
			else if (key == "")
				key = t;
			else
			{
				Prox_KeyValue(d, b2, key, t);
				key = "";
				took = TRUE;
			}
		}
	}
	fclose(fh);
	if (b1 != "")
		pk_shader = strzone(b1);
	return b1 != "patch" && b1 != "";
};

string(string name) Prox_Var =
{
	local float i;
	for (i = 0; i < pv_n; i = i + 1)
		if (pv_name[i] == name)
			return pv_val[i];
	return "";
};

// The pk_/pv_ lists resolved to "<scale> <base>", or "" when they are not the one shape.
string() Prox_Resolve =
{
	local float i, sub, pp;
	local string v;

	if (pk_over || pk_shader != "unlitgeneric" || Prox_Var("$basetexture") == "")
		return "";
	if (stof(Prox_Var("$additive")) || stof(Prox_Var("$alphatest")) ||
	    stof(Prox_Var("$emissiveblendenabled")))
		return "";
	if (Prox_Var("$alpha") != "" || Prox_Var("$vertexalpha") != "")
		return "";                  // a constant or vertex alphaGen ignores the entity's alpha
	for (i = 0; i < pk_n; i = i + 1)
		if (pk_kind[i] == "animatedtexture")
			return "";              // vmt/animated
	sub = pp = -1;
	for (i = 0; i < pk_n; i = i + 1)
		if (pk_res[i] == "$alpha")
			sub = i;                // the last writer wins: Source binds them in order
	if (sub < 0)
		return "";                  // separate tests: QC's || evaluates both sides
	if (pk_kind[sub] != "subtract")
		return "";
	for (i = 0; i < pk_n; i = i + 1)
		if (pk_res[i] == pk_s2[sub])
			pp = i;
	if (pp < 0)
		return "";
	if (pk_kind[pp] != "playerproximity" || !pk_scale[pp] || Prox_Var(pk_res[pp]) == "")
		return "";
	for (i = 0; i < pk_n; i = i + 1)
		if (pk_res[i] == pk_s1[sub])
			return "";              // the constant side is computed: not this shape
	v = Prox_Var(pk_s1[sub]);
	if (v == "")
		return "";                  // a literal or an undeclared var: Source's Init fails
	return sprintf("%g %g", pk_scale[pp], stof(v));
};

// The texture name getsurfacetexture gives, as a path under materials/ without .vmt.
string(string t) Prox_MatName =
{
	t = strreplace("\\", "/", strtolower(t));
	if (substring(t, 0, 10) == "materials/")
		t = substring(t, 10, -1);
	if (substring(t, -4, 4) == ".vmt")
		t = substring(t, 0, strlen(t) - 4);
	return t;
};

// "<scale> <base>" for a material, read once per map.  "" when it does not fade.
string(string m) Prox_Material =
{
	local float i, j;
	local string v, old;

	i = strstrofs(prox_mats, strcat("\n", m, "="));
	if (i >= 0)
	{
		i = i + strlen(m) + 2;
		j = strstrofs(prox_mats, "\n", i);
		v = substring(prox_mats, i, j - i);
		return (v == "-") ? "" : v;
	}
	v = "";
	if (Prox_ReadVMT(m))
		v = Prox_Resolve();
	Prox_ClearVMT();
	old = prox_mats;
	prox_mats = strzone(strcat(old, m, "=", (v == "") ? "-" : v, "\n"));
	strunzone(old);
	prox_mats_n = prox_mats_n + 1;
	if (v != "")
		dprint(sprintf("proximity: %s fades as alpha = base - scale * distance, scale base %s\n", m, v));
	return v;
};

float(float isnew) Prox_Delta;

// vbsp_proximity 0 at a map load skips the listen as well, so nothing runs per frame; set mid-map
// it only hands the entities back to the engine.
void() Prox_LoadForMap =
{
	local float i, s, got, other, sc, bs, t0;
	local string nm, tex, v;
	local entity probe;

	registercvar("vbsp_proximity", "1", 0);
	registercvar("vbsp_proximity_debug", "0", 0);
	if (prox_map != "")
		strunzone(prox_map);
	prox_map = "";
	nm = serverkey("map");
	if (nm != "")
		prox_map = strzone(nm);
	if (prox_mats != "")
		strunzone(prox_mats);
	prox_mats = strzone("\n");
	prox_n = prox_declined = prox_over = prox_mats_n = 0;
	prox_gen = prox_gen + 1;
	sc = bs = 0;
	if (!cvar("vbsp_proximity"))
	{
		dprint("proximity: not listening (vbsp_proximity 0 at the map load)\n");
		return;
	}
	t0 = gettime(1);

	probe = spawn();
	for (i = 1; i < 8192; i = i + 1)
	{
		nm = modelnameforindex(i);
		if (nm == "")
			break;
		if (substring(nm, 0, 1) != "*")
			continue;
		setmodel(probe, nm);
		got = other = 0;
		for (s = 0; s < 4096; s = s + 1)
		{
			tex = getsurfacetexture(probe, s);
			if (tex == "")
				break;
			v = Prox_Material(Prox_MatName(tex));
			if (v == "")
			{
				other = 1;
				continue;
			}
			tokenize(v);
			if (!got)
			{
				got = 1;
				sc = stof(argv(0));
				bs = stof(argv(1));
			}
			else if (stof(argv(0)) != sc || stof(argv(1)) != bs)
				other = 1;          // two different fades on one entity
		}
		if (s >= 4096)
			other = 1;              // faces past the cap were never read
		if (!got)
			continue;
		if (other)
		{
			prox_declined = prox_declined + 1;
			continue;
		}
		if (prox_n >= PROX_MAX)
		{
			prox_over = prox_over + 1;
			continue;
		}
		prox_mi[prox_n] = probe.modelindex;
		prox_scale[prox_n] = sc;
		prox_base[prox_n] = bs;
		prox_ctr[prox_n] = (probe.mins + probe.maxs) * 0.5;
		prox_n = prox_n + 1;
		deltalisten(nm, Prox_Delta, 0);
	}
	remove(probe);

	if (prox_n || prox_declined || prox_over)
		print(sprintf("proximity: %g brush entities fade with distance, %g declined (other materials), %g past the table, %g materials read, %.0f ms, on %s\n",
			prox_n, prox_declined, prox_over, prox_mats_n, (gettime(1) - t0) * 1000, prox_map));
	else
		dprint(sprintf("proximity: none on %s (%g materials read, %.0f ms)\n",
			prox_map, prox_mats_n, (gettime(1) - t0) * 1000));
};

void() Prox_LoadFromWorld =
{
	Prox_LoadForMap();
};

// Before addentities, which is where the engine calls Prox_Delta, and after the replay and
// spectate cameras.  Source measures from the local player's WorldSpaceCenter: the feet plus half
// Momentum's 62-unit hull (45 ducked: 8.5 lower, at most 0.02 of alpha).  A replay or spectate
// measures from the player it shows, a free camera (free spectate, the ghost) from itself, as an
// observer or a noclip player would; 33 is the 64-unit eye less that centre.
void() Prox_Frame =
{
	if (serverkey("map") != prox_map)
		Prox_LoadForMap();
	prox_mode = cvar("vbsp_proximity");
	if (cvar("vbsp_proximity_debug"))
	{
		print(sprintf("proximity: mode %g, last frame %g callbacks, %g drawn, %g faded out, measured from %v, %g listened\n",
			prox_mode, prox_calls, prox_drawn, prox_out, prox_eye, prox_n));
		cvar_set("vbsp_proximity_debug", "0");
	}
	prox_calls = prox_drawn = prox_out = 0;
	if (!prox_n)
		return;
	if (rec_wt_on)
		prox_eye = rec_wt_org + '0 0 31';
	else if (spc_cam && spc_mode != SPM_FREE)
		prox_eye = spc_hfeet + '0 0 31';
	else if (spc_cam || rec_gh_on)
		prox_eye = getproperty(VF_ORIGIN) - '0 0 33';
	else
		prox_eye = HUD_Feet() + '0 0 31';
};

// deltalisten's callback, once per rendered frame for each listened entity (cl_ents.c, from
// CL_LinkPacketEntities).  TRUE: the engine leaves it to this entity's drawmask.
float(float isnew) Prox_Delta =
{
	local float k, a;
	local vector c, f, r, u;

	if (isnew || self.prox_seen != prox_gen || self.prox_model != self.modelindex)
	{
		self.prox_seen = prox_gen;
		self.prox_model = self.modelindex;
		self.prox_slot = 0;
		for (k = 0; k < prox_n; k = k + 1)
			if (prox_mi[k] == self.modelindex)
			{
				self.prox_slot = k + 1;
				break;
			}
	}
	prox_calls = prox_calls + 1;
	self.drawmask = 0;
	if (!self.prox_slot || !prox_mode)
		return FALSE;               // the engine draws it (off, or listened for by an earlier read)
	if (self.effects & EF_NODRAW)
		return TRUE;

	// Linked for its leaves only, which r_ignoreentpvs 0 culls by (pr_csqc.c:804); SOLID_NOT so
	// no trace hits it (world.c:670), set every frame because the state copy writes SOLID_BSP.
	self.solid = SOLID_NOT;
	if (isnew || self.origin != self.prox_at)
	{
		setorigin(self, self.origin);
		self.prox_at = self.origin;
	}
	if (prox_mode == 2)
	{
		self.drawmask = MASK_ENGINE;
		prox_drawn = prox_drawn + 1;
		return TRUE;
	}

	k = self.prox_slot - 1;
	c = prox_ctr[k];
	if (self.angles != '0 0 0')
	{
		f = v_forward; r = v_right; u = v_up;
		makevectors(self.angles);   // a brush model's axis: forward, -right, up
		c = c_x * v_forward - c_y * v_right + c_z * v_up;
		v_forward = f; v_right = r; v_up = u;
	}
	// Source's shader does not clamp (BaseShader.cpp:443-456); the blend clamps the product.
	a = bound(0, prox_base[k] - vlen(self.origin + c - prox_eye) * prox_scale[k], 1);
	if (self.alpha)
		a = a * self.alpha;         // the server's renderamt; 0 is opaque (CSQC_EntStateToCSQC)
	if (a <= 0)
	{
		prox_out = prox_out + 1;
		return TRUE;
	}
	self.alpha = a;
	self.drawmask = MASK_ENGINE;
	prox_drawn = prox_drawn + 1;
	return TRUE;
};
