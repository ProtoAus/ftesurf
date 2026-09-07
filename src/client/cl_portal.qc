/*
===========================================================================
  cl_portal.qc -- the client half of Patch 205's linked_portal_door.

  Two jobs, and only one of them is the visible one.

  RENDERING.  Source's linked_portal_door is a POINT entity: an origin, angles
  and a width x height, with no brush anywhere in the BSP.  The engine draws a
  portal by recursing the scene into a SURFACE (gl_backend.c:5778-5795 walks
  the SHADER_SORT_PORTAL batches), so there has to BE a surface -- which means
  shipping one.  models/ftesurf_portal.obj is a unit quad and
  scripts/portal.shader is what sorts it; the size of each of the library's 443
  doors comes from the entity's axis rows rather than from a model per size.

  PREDICTION, which is the half nobody sees until it is wrong.  These doors are
  not networked.  They are static map entities, so the client derives them from
  the same BSP entity lump the server does, with the same arithmetic -- there
  is no delta and so nothing to skew.  What matters is that they carry
  SOLID_PORTAL here too: without it the server would walk the player through
  the doorway while the client predicted them walking into the wall behind it,
  once per frame, forever.  Patch 203's CL_AddCSQCPortalsToPmove is what puts
  them into the client's physents; this file is what puts them into
  csqc_world.

  WHY THE ENTITY LUMP AND NOT A NETWORKED ENTITY.  Zone_LoadFromBsp
  (cl_zones.qc:145-187) and Decal_LoadForMap already read the lump with
  getentitytoken on VBSP maps in this build, so the mechanism is proven here
  rather than hoped for.  Networking would cost 443 entities on
  surf_tripportals and would introduce exactly the client/server disagreement
  the derivation avoids.

  THE LIMITATION THAT FOLLOWS FROM IT: a door toggled at runtime (Source's
  Enable/Disable inputs) will keep rendering after the server has stopped
  letting anyone through, because nothing tells the client.  No map in the
  library does this.  Documented rather than solved.
===========================================================================
*/

.string lpd_name;       // targetname, as written in the lump
                        // (NOT cleared after pairing: find() walks these for every
                        //  door, and a door whose partner is resolved later still
                        //  has to be findable.  Clearing them cost half the pairs.)
.string lpd_partner;    // partnername
.float  lpd_active;     // Patch 207: has a partner AND startactive -- gets an aperture

string vbsp_lpd_map;      // lazy-reload key, same idiom as vbsp_sky_mapname
float  vbsp_lpd_shown;    // how many doors we built
float  vbsp_lpd_held;     // ...and how many are name-holders with no aperture
float  vbsp_lpd_shader;   // shaderforname handle, resolved once

// Patch 207: the stale-lump guard.  See Portal_Poll at the bottom of this file.
string vbsp_lpd_sig;
float  vbsp_lpd_tries;        // signature rechecks left
float  vbsp_lpd_skip;         // frames to wait before the next one
float  vbsp_lpd_saidsettled;  // so the settled line prints once, not per frame

/*
  Patch 207: the cvars are REGISTERED, and read through cached handles.

  The Patch 205 version called cvar("vbsp_portal_debug") once per door per frame
  on a cvar nothing ever registered.  FTE auto-creates an unknown cvar as the
  empty string, so it booted as "" and read 0 -- which happened to be the ship
  default, so it worked by luck rather than by design.  The trap is already
  written up in this project's notes ("register at the point of first read, not
  in worldspawn") and it cost a whole feature once before.

  registercvar declines to overwrite an existing cvar, so a value already set in
  a config or on the command line survives this.
*/
float vbsp_lpd_cvarsdone;
void() FS_PortalRegisterCvars =
{
	if (vbsp_lpd_cvarsdone)
		return;
	vbsp_lpd_cvarsdone = TRUE;
	registercvar("vbsp_portal_render", "1");
	registercvar("vbsp_portal_dist",   "3000");
	registercvar("vbsp_portal_debug",  "0");
};

/*
  The .camera_transform the RENDERER gets.  The shared transform in
  sh_portal.qc does the geometry; this adds the one thing only the render
  caller wants.

  r_refdef.pvsorigin comes from whatever we leave in trace_endpos
  (pr_csqc.c:8792 seeds it with the eye, :8800 reads it back).  It must not be
  left as the transformed eye: the viewer is in front of the entry plane, so
  the transform puts their eye just BEHIND the exit plane -- inside the wall
  the exit door is set into -- and a PVS sample taken from solid returns
  nothing at all.  The symptom is a portal that is a black rectangle, and it
  looks exactly like a shader problem.

  The doorway's own centre, a step into the room it opens into, is both always
  valid and the honest answer to "what can be seen through this hole".
*/
vector(vector org, vector ang) FS_PortalTransformView =
{
	local vector p;
	p = FS_PortalTransform(org, ang);
	if (self.lpd_ok)
		trace_endpos = self.lpd_ob + self.lpd_fb * LPD_PVSNUDGE;
	return p;
};

/*
  RF_USEAXIS is how one quad becomes 443 differently sized doors.

  pr_csqc.c:838-844 copies v_forward, -v_right and v_up straight into the
  entity's axis rows and does NOT normalise them, and R_RotateForEntity feeds
  those rows into the model matrix unchanged -- so a non-unit row is a per-axis
  scale.  The quad is +-1 in its own y and z, so rows of length hw and hh give
  a hw x hh rectangle, and nothing else in the engine offers non-uniform scale
  (.scale is a single float, and USEAXIS forces it to 1 anyway).

  axis[0] stays UNIT on purpose: GLR_DrawPortal takes the portal plane's normal
  from the model normal rotated by the axis, and with the model normal being
  exactly (1,0,0) that product is axis[0] itself.  Scale it and the plane
  normal stops being a unit vector, which throws off every distance the portal
  code computes from it.  The quad has no thickness, so there is nothing to
  scale along it anyway.

  The negation on v_right undoes the engine's own VectorNegate.  The quad is
  symmetric so it would look identical either way; it is written correctly so
  that the basis handed to the renderer is the door's actual right-handed
  frame rather than a mirrored one.
*/
/*
  Patch 207: DECLINE THE ENTITY, which is the cheapest cull there is.

  Patch 205's predraw had no visibility test of any kind -- every door on the
  map returned PREDRAW_AUTOADD on every frame, and each one that survived
  frustum culling then drove a complete recursive R_RenderScene.  Measured on
  surf_kitsune at the hub, that is the difference between a 1.1 ms frame and an
  18.9 ms one: portals cost FOURTEEN TIMES the rest of the scene put together.

  Four questions, cheapest first, and all of them per-entity -- which is why
  they can live here rather than in a pre-pass.  Patch 206's r_portalmaxviews
  owns the "how many" decision, and it has to, because it is the only thing that
  can see the RECURSED views; a QC count would only ever bound the primary one.
  This just refuses the doors no view could want.

    1  vbsp_portal_render 0 -- apertures off entirely.  The physics still works,
       so the map is completable while the renderer is not trusted.  This is a
       real switch for the player, not a debug mode.
    2  NOCLIPPING.  A portal recursed from outside the world samples PVS from a
       cluster that does not exist and renders nothing, at full price.  Patch
       206 gates the engine side on r_viewcluster == -1; this gates the entity
       side on the movetype FTESurf already networks (STAT_FS_MOVETYPE), so the
       doors are not even offered to the renderer.
    3  FACING.  You cannot see through the back of a portal, and GLR_DrawPortal
       refuses one you are behind -- which, before Patch 206 taught its depth
       mask the same test, is exactly where the transparent square came from.
       Refusing it here as well means the mask never sees it at all.
    4  DISTANCE, then PVS.  checkpvs is the expensive one so it goes last; it
       works on these doors because World_LinkEdict runs FindTouchedLeafs before
       the SOLID_PORTAL branch (world.c:665-675), so they have a leaf list.
*/
float() FS_PortalPredraw =
{
	local vector eye, d;
	local float dist;

	FS_PortalRegisterCvars();

	if (!cvar("vbsp_portal_render"))
		return PREDRAW_NEXT;

	// Spectating and noclip both come through here; either way there is nothing
	// worth spending a scene render on.
	if (getstatf(STAT_FS_MOVETYPE) == MOVETYPE_NOCLIP)
		return PREDRAW_NEXT;

	eye = getproperty(VF_ORIGIN);
	d = eye - self.origin;

	// Behind the plane: the renderer would refuse it anyway.
	if (d * self.lpd_fa <= 0)
		return PREDRAW_NEXT;

	dist = cvar("vbsp_portal_dist");
	if (dist > 0 && vlen(d) > dist)
		return PREDRAW_NEXT;

	if (!checkpvs(eye, self))
		return PREDRAW_NEXT;

	if (cvar("vbsp_portal_debug"))
		dprint(sprintf("portal %s: offered at %g units\n",
			self.lpd_name == "" ? "?" : self.lpd_name, rint(vlen(d))));

	/*
	  RF_USEAXIS is how one quad becomes 443 differently sized doors -- see the
	  block above this function.  axis[0] stays unit on purpose; only right and
	  up carry the size.
	*/
	self.forceshader = vbsp_lpd_shader;
	self.camera_transform = FS_PortalTransformView;
	v_forward = self.lpd_fa;
	v_right   = (0 - self.lpd_hw) * self.lpd_ra;
	v_up      =      self.lpd_hh  * self.lpd_ua;
	self.renderflags = RF_USEAXIS;
	return PREDRAW_AUTOADD;
};

void() Portal_Clear =
{
	local entity e, n;
	e = findchain(classname, "vbsp_portal");
	while (e)
	{
		n = e.chain;
		remove(e);
		e = n;
	}
	vbsp_lpd_shown = 0;
	vbsp_lpd_held = 0;
};

/*
  Read every linked_portal_door out of the entity lump, then pair them.

  Two passes because pairing is by name and a door's partner is as likely to
  appear later in the lump as earlier -- the same reason the server resolves
  its side in a think.  Field strings survive the gap without strzone:
  FTE_QC_PERSISTENTTEMPSTRINGS (cl_defs.qc:212) keeps a temp string alive
  while a reference to it exists, and an entity field is a reference.

  The names are NOT cleared once a door has paired, which the first version of
  this did as tidiness.  find() searches lpd_name across every door on every
  iteration, so blanking a door's name the moment it paired made it invisible
  to every door resolved after it -- surf_kitsune built 9 of its 18, which is
  exactly one per pair.
*/
void() Portal_LoadForMap =
{
	local string tok, key;
	local string cn, nm, pn, sorg, sang, sw, sh, ssa, sd;
	local string sigfirst;
	local float sigcount;
	local entity e, d;
	local vector ext;

	Portal_Clear();
	FS_PortalRegisterCvars();
	sigcount = 0;
	sigfirst = "";
	vbsp_lpd_map = serverkey("map");
	if (vbsp_lpd_map == "")
		return;

	if (!vbsp_lpd_shader)
	{
		/*
		  shaderforname registers scripts/portal.shader's block from QC, so a
		  client running ruleset_allow_shaders 0 -- where the .shader file itself
		  is ignored -- still gets a portal-sorted surface rather than a white
		  quad.  The .obj's usemtl line normally does this on its own; this is the
		  belt to its braces, and .forceshader below is where it lands.

		  precache_model is here for the same "say it out loud" reason: setmodel
		  would load it anyway, and fteqcc warns about the model it cannot see
		  being precached.
		*/
		vbsp_lpd_shader = shaderforname("ftesurf_portal");
		precache_model("models/ftesurf_portal.obj");
	}

	getentitytoken(0);				// reset to the start of the lump
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;

		cn = nm = pn = sorg = sang = sw = sh = ssa = sd = "";
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			if      (key == "classname")     cn   = tok;
			else if (key == "targetname")    nm   = tok;
			else if (key == "partnername")   pn   = tok;
			else if (key == "origin")        sorg = tok;
			else if (key == "angles")        sang = tok;
			else if (key == "width")         sw   = tok;
			else if (key == "height")        sh   = tok;
			else if (key == "startactive")   ssa  = tok;
			else if (key == "StartDisabled") sd   = tok;
		}

		if (cn != "linked_portal_door")
			continue;

		/*
		  Patch 207: EVERY door becomes an entity, including the ones that will
		  never have an aperture.

		  Patch 205 skipped unpartnered and inactive doors here, and that broke
		  the very lookup it was trying to save work on.  The server keeps those
		  doors alive precisely so they stay findable by targetname -- three of
		  the library's 443 name a partner without being named by one, and on
		  bhop_aberrant `p2` points at a `p1` that has no partner of its own.  A
		  client that never created `p1` fails find() for `p2`, sweeps `p2` as
		  unpaired, and ends up with NO aperture where the server has a perfectly
		  good portal.  The two sides then disagree about a wall.

		  So they are name-holders: an entity with a name, no model and no solid.
		  Whether one gets an aperture is decided below, from lpd_active.
		*/
		e = spawn();
		e.classname   = "vbsp_portal";
		e.lpd_name    = nm;
		e.lpd_partner = pn;

		/*
		  The active test mirrors the SERVER's, character for character, because
		  the failure mode of not doing so is invisible until someone walks into
		  it.  sv_entities.qc refuses on `startactive == 0 || StartDisabled`, and
		  an absent key reads 0 there -- so an absent key must read inactive
		  here too.  stof("") is 0, which does exactly that.  All 443 doors
		  write startactive, so this is lockstep rather than a live case.
		*/
		e.lpd_active = (pn != "") && stof(ssa) != 0 && stof(sd) == 0;

		/*
		  Patch 207: the signature is taken from THIS walk, not from a fresh one
		  afterwards.  Taking it afterwards is what made the stale-lump guard
		  useless: on a tripportals -> demise change the lump flipped BETWEEN the
		  load walk and the signature walk, so the signature recorded demise's
		  zero doors while the entities recorded tripportals' 116 -- and the two
		  could then never disagree again, so the recheck closed the window and
		  kept the phantoms.  The signature has to describe what was actually
		  built.
		*/
		sigcount = sigcount + 1;
		if (sigfirst == "")
			sigfirst = sorg;
		e.origin      = stov(sorg);
		e.angles      = stov(sang);

		/*
		  DO NOT HALVE THESE.  `width` and `height` are ALREADY half-extents --
		  the key names lie, and momentum.fgd:5366-5372 says so outright:

		      orientedwidthheighthalf(width, height)
		      width(integer)  : "Half-Width (G)"  : 128 : "Half-width of the
		                        portal, on the Green axis."
		      height(integer) : "Half-Height (B)" : 128 : "Half-height of the
		                        portal, on the Blue axis."

		  Halving them again drew every door at HALF its size in each axis, a
		  QUARTER of the area, and did the same to the server's acceptance band
		  (sv_entities.qc:1033) so the outer ring of every doorway on every map
		  silently refused entry.  Patch 206 widened that band "to the whole
		  88-unit doorway" on surf_kitsune -- but kitsune's doorways are 176.

		  Measured rather than assumed, on portal_hub_exit: the frame opening in
		  the `kitsune` func_brush is 176.12 units wide read from 200 units back
		  and 176.15 read from 100 units back -- two distances agreeing to 0.03
		  units -- and its top edge sits at z 272.15 against a door origin of
		  z 184, so 88.15 vertically as well.  The entity declares 88 x 88.  The
		  frame is exactly twice the declared numbers, on both axes.

		  The fallback is the FGD's own default, so a door with the key missing
		  matches what Hammer would have shown the mapper.
		*/
		e.lpd_hw      = stof(sw);
		e.lpd_hh      = stof(sh);
		if (e.lpd_hw <= 0) e.lpd_hw = 128;
		if (e.lpd_hh <= 0) e.lpd_hh = 128;
	}

	for (e = findchain(classname, "vbsp_portal"); e; e = e.chain)
	{
		if (!e.lpd_active)
			continue;			// a name-holder: findable, but no aperture
		d = find(world, lpd_name, e.lpd_partner);
		if (!FS_PortalSetup(e, d))
			continue;

		ext = FS_PortalExtent(e.lpd_fa, e.lpd_ra, e.lpd_ua, e.lpd_hw, e.lpd_hh);

		/*
		  Order matters here in a way that is easy to get wrong.

		  .solid first: World_LinkEdict routes a SOLID_PORTAL onto the world's
		  portal list (world.c:675-679) instead of the area grid, and that list
		  is what CL_AddCSQCPortalsToPmove walks.  Set it after the link and the
		  entity is on the wrong list.

		  setmodel BEFORE setsize: setmodel overwrites mins/maxs with the
		  MODEL's bounds, which for the unit quad is a 2-unit cube -- as a
		  collision box that is nothing, and PM_PortalCSG would derive a
		  2-unit aperture from it.  setsize afterwards is what fixes both.
		*/
		e.movetype = MOVETYPE_NONE;
		e.solid    = SOLID_PORTAL;
		e.camera_transform = FS_PortalTransformView;
		e.drawmask = MASK_ENGINE;
		e.predraw  = FS_PortalPredraw;
		setmodel(e, "models/ftesurf_portal.obj");
		if (vbsp_lpd_shader)
			e.forceshader = vbsp_lpd_shader;
		setsize(e, '0 0 0' - ext, ext);
		setorigin(e, e.origin);

		vbsp_lpd_shown = vbsp_lpd_shown + 1;
	}

	/*
	  Patch 207: nothing is swept any more.

	  Patch 205 removed every door that had not paired, which is what broke the
	  one-way destinations described above -- the entity another door needs to
	  FIND is exactly the entity that has no partner of its own.  An unpaired
	  door costs one inert entity with no model, no solid and a predraw that is
	  never reached, so keeping it is cheaper than the bug.  Portal_Clear takes
	  them all on the next map change.
	*/
	for (e = findchain(classname, "vbsp_portal"); e; e = e.chain)
		if (!e.lpd_ok)
			vbsp_lpd_held = vbsp_lpd_held + 1;

	/*
	  SILENT when the map has none, which is 1290 of the library's 1308 maps.
	  Both numbers, because a mismatch against the server's "portal doors: N
	  linked" is the tell for a client/server divergence and one number cannot
	  show it.  A count that is exactly HALF the door count is the pairing bug
	  Patch 205 shipped with; a count that is short by a few is a one-way
	  destination.
	*/
	vbsp_lpd_sig = sprintf("%g/%s", sigcount, sigfirst);

	/*
	  The dprint runs unconditionally and the print does not, because a load that
	  clears a PREVIOUS map's doors builds nothing and would otherwise say
	  nothing -- which is exactly the case that looked broken for three runs.
	  The reload after a stale read is the successful outcome; it should be
	  audible to anyone looking, and invisible to everyone else.
	*/
	dprint(sprintf("portals: loaded %s -> %g apertures, %g name-only, sig %s\n",
		vbsp_lpd_map, vbsp_lpd_shown, vbsp_lpd_held, vbsp_lpd_sig));


	/*
	  NOT printed to the player here.  A load can read the PREVIOUS map's lump,
	  so the first load on a map is not necessarily the one whose numbers are
	  true -- Patch 205 duly announced "116 rendered on surf_demise" on a map
	  with no portal doors at all.  The visible line comes from the settled state
	  in Portal_Poll instead, once, with the numbers that survived.  The dprint
	  above is the audit trail for every load including the wrong ones.
	*/
};

/*
===========================================================================
  Patch 207: the stale-lump window, and why latching the map name is not enough.

  serverkey("map") and the entity lump do not change together, and they can
  change in EITHER ORDER.  Patch 205 assumed one order and documented the
  transient as harmless because "it self-corrects on the next pass" -- which is
  true only when the key lags the lump.  When the key LEADS it, the load reads
  the previous map's doors, latches the new map's name, and never looks again.

  Measured, and it is not cosmetic: changing from surf_tripportals to
  surf_demise built ONE HUNDRED AND SIXTEEN phantom apertures on a map that has
  no portal doors at all, and demise went to 90 ms a frame -- eleven fps on the
  map whose framerate was already the thing being complained about.  The log
  said `portals: 116 with apertures, 0 name-only, on surf_demise` in as many
  words, which is the only reason it was caught.

  So the key is not the gate.  A cheap SIGNATURE of the lump is: door count plus
  the first door's origin.  On a map change the loader runs, then keeps
  re-running at half-second intervals for a few seconds; the moment two
  consecutive reads agree, the window closes.  Portal_LoadForMap already begins
  with Portal_Clear, so re-running it is idempotent, and a handful of extra lump
  walks in the first seconds of a map costs nothing next to being wrong for the
  whole map.
===========================================================================
*/

/*
  COUNTED IN FRAMES, NOT IN `time`, and that is the second correction this
  window needed.  The first version armed itself with `time + 30`, which is
  broken by the very event it exists to survive: CSQC_WorldLoaded fires while
  `time` is still the OUTGOING map's (about 70 on a map you have been standing
  on), and then `time` resets to 0 for the new one.  The window was therefore
  scheduled thirty seconds into a future that had just been rewound, so
  `time < nextcheck` stayed true forever and not one recheck ran.  Frame counts
  cannot be rewound.
*/

string() Portal_Signature =
{
	local string tok, key, cn, sorg, first;
	local float n;

	n = 0;
	first = "";
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = sorg = "";
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			if      (key == "classname") cn   = tok;
			else if (key == "origin")    sorg = tok;
		}
		if (cn != "linked_portal_door")
			continue;
		n = n + 1;
		if (first == "")
			first = sorg;
	}
	return sprintf("%g/%s", n, first);
};

/*
  Called from CSQC_WorldLoaded -- the engine's "the precaches are done, you may
  read the entity lump now".

  IT STILL ARMS THE RECHECK, and that correction cost a run.  The first version
  treated this as authoritative and closed the window, on the reasoning that the
  engine would not offer the hook before the lump was ready.  It does: changing
  to surf_demise still read surf_tripportals' 116 doors here, and closing the
  window made that permanent -- strictly worse than the lazy compare it
  replaced, because at least that one got a second look.

  So neither entry point is trusted on its own.  The signature is the only thing
  that actually knows, and both paths arm it.
*/
void() Portal_LoadFromWorld =
{
	Portal_LoadForMap();
	vbsp_lpd_tries = 40;
	vbsp_lpd_skip  = 30;
	vbsp_lpd_saidsettled = FALSE;
};

void() Portal_Poll =
{
	local string map, sig;

	map = serverkey("map");
	if (map == "")
		return;

	if (map != vbsp_lpd_map)
	{
		Portal_LoadForMap();
		vbsp_lpd_tries = 40;
		vbsp_lpd_skip  = 30;
		vbsp_lpd_saidsettled = FALSE;
		return;
	}

	if (vbsp_lpd_tries <= 0)
	{
		// Say so ONCE.  "the recheck found nothing" and "the recheck never ran"
		// are indistinguishable from a log that only prints on a change, and
		// they have completely different fixes.
		if (!vbsp_lpd_saidsettled)
		{
			vbsp_lpd_saidsettled = TRUE;
			dprint(sprintf("portals: settled on %s with sig %s\n",
				vbsp_lpd_map, vbsp_lpd_sig));
			/*
			  SILENT when the map has none, which is 1290 of the library's 1308.
			  Both counts, because a mismatch against the server's "portal doors:
			  N linked" is the tell for a client/server divergence and one number
			  cannot show it.  Exactly HALF the door count is Patch 205's pairing
			  bug; short by a few is a one-way destination.
			*/
			if (vbsp_lpd_shown || vbsp_lpd_held)
				print(sprintf("portals: %g with apertures, %g name-only, on %s\n",
					vbsp_lpd_shown, vbsp_lpd_held, vbsp_lpd_map));
		}
		return;					// settled, or out of patience
	}
	if (vbsp_lpd_skip > 0)
	{
		vbsp_lpd_skip = vbsp_lpd_skip - 1;
		return;
	}
	vbsp_lpd_skip  = 30;
	vbsp_lpd_tries = vbsp_lpd_tries - 1;

	sig = Portal_Signature();
	dprint(sprintf("portals: recheck at %g, sig %s (was %s)\n", time, sig, vbsp_lpd_sig));
	if (sig == vbsp_lpd_sig)
	{
		vbsp_lpd_tries = 0;		// two reads agree: the lump has settled
		return;
	}

	dprint(sprintf("portals: lump changed under us (%s -> %s), reloading\n",
		vbsp_lpd_sig, sig));
	vbsp_lpd_sig = sig;
	Portal_LoadForMap();
};
