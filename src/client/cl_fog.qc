/*
  cl_fog.qc -- Source (HL2) fog, read from the map's own entities.

  WHY THIS EXISTS.  Every Source map that authors fog does it with an
  `env_fog_controller` entity, and the 3D skybox carries its own fog on
  `sky_camera`.  FTE only ever reads fog from WORLDSPAWN keys
  (engine/client/wad.c, `fog`/`waterfog`/`skyroomfog`/`_fog`), and a census of
  the 1337-map library found worldspawn fog keys on exactly ZERO of them.  So
  the engine's fog parser can never fire on this content and every fogged map
  has been rendering flat and over-lit.  194 maps carry a controller, 174 with
  one enabled; 169 carry a sky_camera, and 27 of those are the ONLY fog the map
  has.  About 201 maps are affected -- 134 surf_, 29 bhop_.

  WHY IT IS NOT IN cl_decals.qc.  That file already walks the entity lump and
  already reads sky_camera's origin and scale, so bolting fog on there looks
  free.  It is not: that walk is driven by a lazy serverkey("map") compare from
  CSQC_UpdateView, and Patch 207 established that this bets on an ordering which
  does not always hold -- it cost 116 phantom apertures on surf_demise.  The
  portals and the sprites were moved to CSQC_WorldLoaded for exactly this
  reason; the fog follows them.  sky_camera's fog keys are re-read here rather
  than smuggled across from the decal walk, so the feature is self-contained.

  ------------------------------------------------------------------
  THE MATHS, WHICH IS THE WHOLE POINT OF THIS FILE

  Source's fog is linear (start/end distance).  FTE's DEFAULT is exponential
  density, so this looks like it needs a lossy conversion.  It does not -- FTE
  has a linear branch (r_fog_linear 1) and that branch reuses the existing
  fog fields with Source's own meanings.  From engine/gl/gl_vidcommon.c, the
  built-in "sys/fog.h":

      z   = gl_FragCoord.z / gl_FragCoord.w;
      fac = (w_fogdensity - z) / (w_fogdensity - w_fogdepthbias);
      fac = (1.0 - w_fogalpha) + (clamp(fac, 0.0, 1.0) * w_fogalpha);
      return mix(w_fogcolour, regularcolour, fac);

  So `density` is a fog END distance and `depthbias` a fog START distance, and
  the effective fog fraction is

      alpha * clamp01( (z - start) / (end - start) )

  BUT THE NAIVE SUBSTITUTION IS WRONG.  Source does not multiply by
  fogmaxdensity, it takes a min().  From the Momentum tree,
  materialsystem/stdshaders/common_fxc.h:238-242:

      float dist = distance( eyePos.xyz, worldPos.xyz );
      return min( flFogMaxDensity, saturate( (dist*flFogOORange) - flFogEndOverRange ) );

  With a multiply, a controller at the census p10 of fogmaxdensity 0.15 draws
  fog 6.7x TOO THIN across the entire near field, and only meets Source at the
  far plane.  125 of the 244 enabled controllers sit at maxdensity 1 where the
  two agree, which is exactly why the bug would survive a casual look.

  The fix costs nothing.  Reparametrise instead of substituting: with
  m = bound(0, fogmaxdensity, 1) and R = fogend - fogstart, emit

      alpha := m
      end'  := fogstart + m*R

  and FTE then computes  m * clamp01((z-start)/(m*R))  which is identically
  min(m, (z-start)/R) -- Source's min(), exactly.  It also disposes of the
  fogmaxdensity 2 maps for free: alpha can no longer exceed 1, so mix() can no
  longer extrapolate past the fog colour into negative RGB.

  WHAT IS STILL AN APPROXIMATION, said out loud:
    * Source lerps by the fog factor SQUARED, in linear light space, and applies
      SRGBOutput afterwards (common_ps_fxc.h:271-272, 349-352).  We lerp by the
      factor in gamma space.  The two errors partly cancel and the residue is
      not predictable from theory -- it wants a screenshot against Momentum with
      vid_srgb pinned, not an argument.
    * Source measures RADIAL distance; FTE's gl_FragCoord.z/gl_FragCoord.w is
      planar eye depth.  Source's fog thickens toward the screen edges by
      ~1.3-1.4x at the corners of a wide fov and ours does not.  This affects
      every map, not just the 13 that set `fogradial`.
    * fogblend/fogcolor2/fogdir (40 controllers) blend two colours by view angle.
      fogstate_t holds one colour.  We use fogcolor.
    * farz is ignored; there is no FTE equivalent on this path.
*/

// The controller entities, one per env_fog_controller in the lump.  Kept as
// entities and keyed by name for the same reason cl_portal.qc keeps its doors:
// the server switches fog at runtime by NAME, and a name we did not keep is a
// switch we cannot honour.
.string fog_name;
.vector fog_colour;		// already 0..1
.float  fog_start;
.float  fog_end;
.float  fog_maxdens;
.float  fog_on;			// fogenable
.float  fog_master;		// spawnflags & 1  (Source's SF_FOG_MASTER)

float  vbsp_fog_count;		// controllers found in this map's lump
entity vbsp_fog_default;	// the one Source would start the map on
entity vbsp_fog_active;		// the one currently applied
string vbsp_fog_lastname;	// last name the server asked for; edge-detect
float  vbsp_fog_lastonoff;	// last vbsp_fog value applied; edge-detect

float  vbsp_fog_skyhave;
vector vbsp_fog_skycol;
float  vbsp_fog_skystart, vbsp_fog_skyend, vbsp_fog_skydens, vbsp_fog_skyscale;
float  vbsp_fog_skyon;

/*
  Source writes fog colours as "R G B" in 0..255 (occasionally with a fourth
  component, which is unused).  Hammer's bracket conventions do not appear on
  these keys -- that is a VMT thing -- so a plain three-float parse is right.
*/
vector(string s) Fog_ParseColour =
{
	local float n;
	n = tokenize(s);
	if (n < 3)
		return '0 0 0';
	return [stof(argv(0)) / 255, stof(argv(1)) / 255, stof(argv(2)) / 255];
};

/*
  Emit one fog command.  `cmd` is "fog" or "skyroomfog"; `scale` divides the two
  distances and is 1 for world fog.

  Turning fog off is `<cmd> 0`: CL_Fog_f's argc-2 case sets density 0, and the
  renderer treats density 0 as "no fog" (it is what gates PERMUTATION_FOG), so
  the shader is not merely transparent, it is not compiled in.
*/
void(string cmd, entity c, float scale) Fog_EmitOne =
{
	local float m, r, e2;

	if (!c || !c.fog_on || !cvar("vbsp_fog"))
	{
		localcmd(strcat(cmd, " 0\n"));
		return;
	}

	m = bound(0, c.fog_maxdens, 1);
	r = c.fog_end - c.fog_start;

	/*
	  4 controllers in the library have fogend <= fogstart.  There is no fog
	  that means: the shader's (density-depthbias) denominator would be zero or
	  negative, giving a divide by zero or fog that inverts and thins with
	  distance.  Source draws nothing sane for these either, so: no fog.
	  m == 0 is the same story by a different route (26 masters are deliberate
	  "no fog" entities, usually named fog_none).
	*/
	if (r <= 0 || m <= 0)
	{
		localcmd(strcat(cmd, " 0\n"));
		return;
	}

	if (scale <= 0)
		scale = 1;

	e2 = (c.fog_start + m * r) / scale;		// the reparametrised end -- see header

	localcmd(sprintf("%s %g %g %g %g %g %g\n", cmd,
	                 e2,
	                 c.fog_colour_x, c.fog_colour_y, c.fog_colour_z,
	                 m,
	                 c.fog_start / scale));
};

/*
  The 3D skybox's own fog.  Source divides skybox fog distances by the
  sky_camera scale (viewrender.cpp, Enable3dSkyboxFog: scale = 1/m_skybox3d.scale
  then FogStart(GetSkyboxFogStart()*scale)), because the skybox geometry is
  built at 1/scale size.  FTE's skyroom renders that small geometry at TRUE size
  and only moves the camera, so the division is needed here too.

  The engine used to apply a hardcoded /64 of its own at this point
  (gl_warp.c); Patch 254 guards that off under r_fog_linear precisely so this
  can supply the real number.
*/
void() Fog_EmitSky =
{
	local entity c;
	local float sc;

	if (!vbsp_fog_skyhave)
		return;

	sc = vbsp_fog_skyscale;
	if (sc <= 0)
		sc = 16;			// Source's own default

	c = spawn();
	c.fog_on      = vbsp_fog_skyon;
	c.fog_colour  = vbsp_fog_skycol;
	c.fog_start   = vbsp_fog_skystart;
	c.fog_end     = vbsp_fog_skyend;
	c.fog_maxdens = vbsp_fog_skydens;
	Fog_EmitOne("skyroomfog", c, sc);
	remove(c);
};

/*
  Underwater fog.  In Source this does NOT come from env_fog_controller -- it is
  the water material's own $fogcolor/$fogstart/$fogend, which only the VBSP
  plugin ever sees.  The plugin publishes the first water material's set on
  hl2_waterfog / _start / _end at map load (Patch 254), the same cvar channel
  cl_gfx.qc already reads hl2_unresolved through.

  Emitted once and then forgotten: the engine swaps to cl.fog[FOGTYPE_WATER] by
  itself whenever the view is underwater (gl_rmain.c checks RDF_UNDERWATER), so
  nothing here has to track submersion, and the gamecode never has to ask.

  Note the maps that care most about underwater fog do not rely on this at all --
  surf_minimumwage and surf_summer_ksf both switch to a controller literally
  named fog_underwater over the entity-I/O path above.  This is the generic case.
*/
void() Fog_EmitWater =
{
	local entity c;
	local string col;
	local float n, e;

	col = cvar_string("hl2_waterfog");
	e   = cvar("hl2_waterfog_end");

	// No water material on this map declared fog.  Leave the slot alone rather
	// than clearing it -- CL_ResetFog already zeroed all three at map load.
	if (col == "" || e <= 0)
		return;

	n = tokenize(col);
	if (n < 3)
		return;

	c = spawn();
	c.fog_on      = TRUE;
	c.fog_colour  = [stof(argv(0)), stof(argv(1)), stof(argv(2))];	// already 0..1
	c.fog_start   = cvar("hl2_waterfog_start");
	c.fog_end     = e;
	c.fog_maxdens = 1;
	Fog_EmitOne("waterfog", c, 1);
	remove(c);
};

void(entity c) Fog_Apply =
{
	vbsp_fog_active = c;
	Fog_EmitOne("fog", c, 1);
};

/*
  Find a controller by targetname.  Mirrors SV_FindByName's two-stage rule
  (sv_entities.qc): exact match first, then a case-insensitive sweep.
  SV_RepairTargetCase fixes .target but NOT .targetname, so some maps really do
  disagree in case and a single exact find() would silently miss them.
*/
entity(string nm) Fog_FindByName =
{
	local entity e;

	if (nm == "")
		return world;

	e = find(world, fog_name, nm);
	if (e)
		return e;

	for (e = world; (e = find(e, classname, "vbsp_fog")); )
		if (!strcasecmp(e.fog_name, nm))
			return e;

	return world;
};

void() Fog_LoadFromWorld =
{
	local string tok, key, cn, nm;
	local string scol, sstart, send, sdens, senable, sflags, sscale;
	local entity e, best;

	vbsp_fog_count    = 0;
	vbsp_fog_default  = world;
	vbsp_fog_active   = world;
	vbsp_fog_lastname = "";
	vbsp_fog_lastonoff = -1;
	vbsp_fog_skyhave  = FALSE;
	best = world;

	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;

		cn = nm = scol = sstart = send = sdens = senable = sflags = sscale = "";
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			if      (key == "classname")     cn      = tok;
			else if (key == "targetname")    nm      = tok;
			else if (key == "fogcolor")      scol    = tok;
			else if (key == "fogstart")      sstart  = tok;
			else if (key == "fogend")        send    = tok;
			else if (key == "fogmaxdensity") sdens   = tok;
			else if (key == "fogenable")     senable = tok;
			else if (key == "spawnflags")    sflags  = tok;
			else if (key == "scale")         sscale  = tok;
		}

		if (cn == "sky_camera")
		{
			// First one wins, matching the sky_camera rule cl_decals.qc already
			// uses for the camera position: a map with two has one per skybox
			// area and picks between them with entity I/O we do not model.
			if (!vbsp_fog_skyhave)
			{
				vbsp_fog_skyhave  = TRUE;
				vbsp_fog_skycol   = Fog_ParseColour(scol);
				vbsp_fog_skystart = stof(sstart);
				vbsp_fog_skyend   = stof(send);
				vbsp_fog_skydens  = (sdens == "") ? 1 : stof(sdens);
				vbsp_fog_skyscale = stof(sscale);
				vbsp_fog_skyon    = (senable != "" && senable != "0");
			}
			continue;
		}

		if (cn != "env_fog_controller")
			continue;

		e = spawn();
		e.classname   = "vbsp_fog";
		e.fog_name    = nm;
		e.fog_colour  = Fog_ParseColour(scol);
		e.fog_start   = stof(sstart);
		e.fog_end     = stof(send);
		e.fog_maxdens = (sdens == "") ? 1 : stof(sdens);	// Source's default
		e.fog_on      = (senable != "" && senable != "0");
		e.fog_master  = stof(sflags) & 1;			// SF_FOG_MASTER
		vbsp_fog_count = vbsp_fog_count + 1;

		/*
		  SOURCE'S SELECTION RULE, AND WHY IT IS NOT "THE FIRST ENABLED ONE".

		  The default controller is the one flagged master, else the FIRST in
		  lump order -- regardless of fogenable.  fogenable then decides whether
		  fog draws.  Picking the first ENABLED one instead gets 34 of the 194
		  maps wrong, because 26 of them have a master deliberately set
		  fogenable 0 (usually literally named fog_none) so the map STARTS
		  unfogged and triggers fog in later.

		  surf_minimumwage is the clean example -- its only enabled controller
		  is fog_underwater, so "first enabled" drowns the whole map in
		  underwater fog from the spawn point:
		      [0] fog_none        sf=1 enable=0            <- Source uses this
		      [1] fog_underwater  sf=0 enable=1 1650..4000
		*/
		if (!best || (e.fog_master && !best.fog_master))
			best = e;
	}

	vbsp_fog_default = best;
	Fog_Apply(best);
	Fog_EmitSky();
	Fog_EmitWater();

	// The same shape of report the decal/overlay/skyroom lines already print:
	// the interesting number is how many controllers a map has versus which one
	// we started on, because that gap is what a switching bug looks like.
	if (vbsp_fog_count)
		print(sprintf("fog: %g controller%s, start on %s%s\n",
		              vbsp_fog_count, (vbsp_fog_count == 1) ? "" : "s",
		              (best.fog_name != "") ? best.fog_name : "(unnamed)",
		              best.fog_on ? "" : " (off)"));
	if (vbsp_fog_skyhave && vbsp_fog_skyon)
		print(sprintf("fog: sky_camera fog %g..%g scale %g\n",
		              vbsp_fog_skystart, vbsp_fog_skyend, vbsp_fog_skyscale));
};

/*
  Per-frame.  Two edges to watch:

  1. The server telling us the player's fog controller changed.  Source fires
     SetFogController at !activator from a trigger; 54 maps in the library do it,
     397 times.  It arrives as a per-player string stat rather than a stuffcmd,
     because a stuffcmd runs at RESTRICT_SERVER and CL_Fog_f would then latch
     cl.fog_locked -- after which the player's own vbsp_fog toggle is refused,
     silently.
  2. The player toggling vbsp_fog.
*/
void() Fog_Frame =
{
	local string want;
	local float onoff;
	local entity c;

	if (!vbsp_fog_count && !vbsp_fog_skyhave)
		return;

	onoff = cvar("vbsp_fog") ? 1 : 0;
	want  = getstats(STAT_FS_FOGCTRL);

	if (want == vbsp_fog_lastname && onoff == vbsp_fog_lastonoff)
		return;

	if (want != vbsp_fog_lastname)
	{
		// An empty stat means the server has not switched us onto anything, so
		// the map's own default stands.  A name we cannot find is left alone
		// rather than treated as "no fog": a typo in a map should not blank the
		// fog the player can already see.
		c = (want == "") ? vbsp_fog_default : Fog_FindByName(want);
		if (c)
			vbsp_fog_active = c;
	}

	vbsp_fog_lastname  = want;
	vbsp_fog_lastonoff = onoff;

	Fog_Apply(vbsp_fog_active);
	Fog_EmitSky();
	Fog_EmitWater();	// so vbsp_fog 0 turns the underwater fog off too
};
