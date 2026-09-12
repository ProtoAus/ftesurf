/*
===========================================================================
  sv_zones.qc -- the server's copy of the zone tables.

  Both VMs parse the same file with the same code (shared/sh_zones.qc), so
  zone N means the same thing on both sides and nothing has to be networked.
  On a listen server that is exact by construction.

  CSQC's copy exists to draw them.  This one exists so `zone_goto` can move
  the player, and -- the real reason -- so the timer has its input already in
  place when it lands: start/end/stage detection is a server-side decision and
  Zone_PointInside is the whole of it.

  Loading is DEFERRED to the first server frame rather than done in
  worldspawn.  The legacy trigger_momentum_timer_* path has to find entities,
  and worldspawn is the first entity spawned -- at that point the rest of the
  map does not exist yet.

  BUILD 47: "THE FIRST SERVER FRAME" WAS NOT LATE ENOUGH, AND HAD NEVER BEEN.

  StartFrame is called BEFORE the map's entity lump is spawned -- sv_main.qc's
  own comment on the report block says so in as many words, and sv_timer.qc's
  registercvar essay is built on the same fact.  So the load above deferred
  itself past worldspawn's own body and landed in front of the entities anyway.
  On surf_summer_ksf the console said it out loud and nobody read it:

      zones(sv): 0 on surf_summer_ksf (none)          <- this file, FIRST
      FTESurf: worldspawn                             <- and worldspawn after
      zones:    12 on surf_summer_ksf (bsp entities)  <- CSQC, off the raw lump

  CSQC walks the raw entity lump with getentitytoken and never needed anything
  to be spawned, so it found all twelve; find() here matched nothing, cached
  the empty answer under zone_loaded, and never looked again.  Net effect: on
  every map whose zones come from BSP triggers -- 32 of the 1317 installed --
  the cages drew and NOTHING TIMED.  The JSON paths were unaffected, which is
  why this survived: they read a file and do not care when they run.

  The fix is zone_entsready, set from the same guarded block that already knows
  when the lump is finished (SV_RepairTargetCase and SV_EntityIOBuild are there
  for exactly this reason).  Until it is set, SV_ZoneFrame declines to load
  rather than loading nothing -- so the defensive `if (!zone_loaded)` calls
  scattered through the client commands below can no longer cache an empty map
  either.  They simply come up empty for the one frame before the lump lands.
===========================================================================
*/

float zone_loaded;

// Set by StartFrame's post-worldspawn block (sv_main.qc), and the whole of
// what makes the deferral above actually deferred.  Cleared per map for free:
// SSQC globals are re-initialised on every map load.
float zone_entsready;

// The stage number on a legacy trigger_momentum_timer_stage.  A VBSP entity
// key is matched to a QC field by name, so declaring it is all it takes to
// read it; maps that do not set it leave this 0.
.float stage;

/*
  Legacy BSP scan, server side.

  CSQC has to walk the raw entity lump with getentitytoken to find these;
  here they have already been spawned (as inert brush triggers, via
  SV_OnEntityNoSpawnFunction), so find() is enough and the model is already
  bound -- mins/maxs are simply there to read.
*/
float() SV_ZoneLoadFromBsp =
{
	local entity e;
	local float type, n;
	local string cn;
	local float i;

	Zone_Clear();
	n = 0;

	// Four passes rather than one over all entities: find() is per-classname,
	// and grouping by type keeps the zone ordering stable and readable in
	// zone_list instead of following entity-lump order.
	for (i = 0; i < 4; i = i + 1)
	{
		if      (i == 0) { cn = "trigger_momentum_timer_start";      type = ZONE_START; }
		else if (i == 1) { cn = "trigger_momentum_timer_stage";      type = ZONE_STAGE; }
		else if (i == 2) { cn = "trigger_momentum_timer_checkpoint"; type = ZONE_CHECKPOINT; }
		else             { cn = "trigger_momentum_timer_stop";       type = ZONE_END; }

		e = world;
		while ((e = find(e, classname, cn)))
		{
			/*
			  BUILD 47: DEFLATE THE ENGINE'S TOUCH EPSILON.

			  absmin/absmax are not the brush.  SV_LinkEdict grows them by one
			  unit on all six faces before storing them -- world.c:653-662,
			  "because movement is clipped an epsilon away from an actual edge,
			  we must fully check even when bounding boxes don't quite touch".
			  That is a collision-system margin, not authored geometry, and it
			  has been in every legacy zone this loader has ever built.

			  It also made the two VMs disagree.  cl_zones.qc builds the drawn
			  cage from probe.mins/maxs after setmodel, which is NOT expanded --
			  so on the 34 legacy maps the server has been testing a box two
			  units bigger per dimension than the client draws, and the claim at
			  the top of this file that both VMs are "exact by construction" was
			  only ever true of the JSON path.  The client is the one that is
			  right; this is the side that moves.

			  Deliberately its own change, landed before the hull rule, so the
			  two effects can be told apart in an A/B.
			*/
			Zone_AddBox(e.absmin + '1 1 1', e.absmax - '1 1 1', type, e.stage);
			n = n + 1;
		}
	}

	if (n)
		zone_source = ZSRC_BSP;
	return n > 0;
};

/*
===========================================================================
  Which leg you are on.

  `!r` means "put me back at the start of the thing I am currently running",
  and nothing else in the game knows what that is.  A leg is (track, segment):
  track 0 is the main route and 1.. are the bonuses, segment 0 is the leg's
  start zone and 1.. are its stages.

  Latched on ENTRY and never cleared until the map changes, which is the whole
  point -- you spend almost all of a run outside every zone and the answer has
  to survive that.  A respawn does NOT clear it: dying part way through stage 4
  should still send `!r` to stage 4.
===========================================================================
*/
.float run_leg_track;
.float run_leg_seg;

// The zone INDEX the leg was last established by, or -1.  See SV_ZoneMove for
// why the (track, seg) pair below is not enough on its own.
.float run_leg_zone;

/*
  The timer, forward-declared.

  sv_timer.qc comes after this file (it needs the zone tables), but two things
  here have to reach into it: every teleport voids the run in progress, and the
  per-map load is where the personal-best table is read.
*/
void(entity e, string why) SV_TimerVoid;
void() SV_TimerMapInit;
void(entity e, float z) SV_TimerArm;
void(entity e) SV_TimerWarped;
float(entity e, float n) SV_TimerTeleported;

void() SV_ZoneLoad =
{
	local entity p;

	zone_mapname = mapname;
	Zone_Clear();

	// The player entity outlives a map change on a listen server, so the leg
	// has to be cleared here rather than left to spawn.
	p = world;
	while ((p = find(p, classname, "player")))
	{
		p.run_leg_track = p.run_leg_seg = 0;
		p.run_leg_zone  = -1;
	}


	if (Zone_LoadJson(strcat("maps/zones/local/",  mapname, ".json"), ZSRC_LOCAL))
		;
	else if (Zone_LoadJson(strcat("maps/zones/online/", mapname, ".json"), ZSRC_ONLINE))
		;
	else
		SV_ZoneLoadFromBsp();

	// Silent when empty: most maps have no zones and saying so every load
	// would be noise.  CSQC prints the one visible line.
	dprint(sprintf("zones(sv): %g on %s (%s)\n",
	               zone_count, mapname, Zone_SourceName(zone_source)));

	// The timer's tables hang off the same load, and for the same reason:
	// this is the first point at which the map is known and its entities
	// exist.
	SV_TimerMapInit();
};

/*
  The per-player scan that used to live here is GONE, folded into
  SV_TimerFrame (sv_timer.qc).

  It was a second full walk of the zone table, per player, per server frame,
  answering a question the timer's own walk already has the answer to -- and it
  ran at the server frame rate while the timer's runs per usercmd, so on a
  listen server at 300 fps it was doing four times the work at a coarser
  resolution than the thing beside it.  What is left here is only the deferred
  load, which has to happen off a frame because worldspawn is too early.
*/
void() SV_ZoneFrame =
{
	// BUILD 47: the entity lump first.  See the essay at the top of this file
	// for what this cost -- without it the load ran a frame early, found no
	// trigger_momentum_timer_* to find, and cached that.  Returning rather than
	// loading is the point: zone_loaded stays FALSE, so the next frame gets it
	// right instead of the map spending its life with an empty table.
	if (!zone_entsready)
		return;

	if (!zone_loaded)
	{
		zone_loaded = TRUE;
		SV_ZoneLoad();
	}
};

// The zone that IS the start of a leg: segment 0 is its start zone, and any
// later segment's own first checkpoint is a stage zone (see Zone_AddTrack).
float(float track, float seg) SV_ZoneFindLeg =
{
	local float z;

	for (z = 0; z < zone_count; z = z + 1)
	{
		if (zone_track[z] != track || zone_seg[z] != seg)
			continue;
		if (zone_type[z] != ZONE_START && zone_type[z] != ZONE_STAGE)
			continue;
		return z;
	}
	return -1;
};

/*
===========================================================================
  Where a teleport actually goes.

  In preference order:

    teleDestPos + teleDestYaw     56 regions -- an explicit answer
    teleDestTargetname            3241 regions -- an info_teleport_destination
    the zone's own floor          everything else, and the legacy BSP path

  and then a DOWNWARD TRACE, because the FGD's wording for that key is "the
  point to which the player should be teleported when restarting a stage...
  placed directly on the ground below this point if possible".

  Two things about the trace are deliberate:

  * It reads trace_endpos and NEVER looks at trace_fraction.  FTE forces
    trace_fraction to 1 when a trace starts solid while still writing a correct
    endpos, and surf_simpsons2's five main-track destinations sit inside a world
    playerclip box and are start-solid at every hull height.  Gating on the
    fraction would skip the snap on exactly the maps that need it.

  * The drop is BOUNDED.  "Directly on the ground below this point" is a short
    search, not a shaft.  The largest legitimate drop in the library is 288
    units (surf_666's s1, s2 and s3), so 1024 leaves a wide margin and still
    refuses to fire the player two thousand units down a hole on a map whose
    destination happens to float over one.
===========================================================================
*/
#define ZONE_SNAP_DROP  1024

vector(float n, __out float yaw, __out float haveyaw) SV_ZoneDest =
{
	local vector c, dest, down, snapped;
	local entity e;

	yaw = 0;
	haveyaw = FALSE;
	dest = '0 0 0';         // fteqcc cannot see that the ZTD_NONE arm returns first

	if (zone_td_kind[n] == ZTD_POS)
	{
		dest = zone_td_pos[n];
		yaw = zone_td_yaw[n];
		haveyaw = TRUE;
	}
	else if (zone_td_kind[n] == ZTD_NAME)
	{
		e = find(world, targetname, zone_td_name[n]);
		if (e)
		{
			dest = e.origin;

			/*
			  BUILD 26: ZERO IS AN ANSWER.

			  This used to read `if (e.angles != '0 0 0')`, with a comment
			  claiming that a destination with no angles should leave you
			  looking where you were "because that is what Source does".  It is
			  not, and build 13 already proved it is not -- for THIS ENTITY
			  CLASS, three files away, with a census.  From the essay above
			  trigger_teleport_touch's own angle snap:

			      "6,635 of the library's 17,188 info_teleport_destination
			       entities point at yaw 0 -- deliberately, since north is a
			       direction -- and we ignored every one of them."

			  Two spellers of one rule; build 13 fixed the teleporter and left
			  the reset behind, so `!r` and a map's own trigger_teleport have
			  disagreed about the same entity ever since.

			  Measured for the zones this actually reaches -- the main-track
			  START region of the 400 installed maps that name a destination:

			      227  the destination's yaw is nonzero   -- already worked
			      173  the destination's angles are 0 0 0 -- reset did NOTHING

			  So on 43% of your library `!r` left the view wherever it happened
			  to be, which is the report.  Note the arm above disagreed with
			  this one INSIDE THIS FUNCTION as well: a teleDestPos region
			  applies its teleDestYaw of 0 and this one discarded it.

			  SV_ZoneMove writes [0, yaw, 0], so the pitch is levelled too --
			  trigger_teleport_touch does the same and says why: a destination
			  is a yaw marker and pitch on one is authoring noise.
			*/
			yaw     = e.angles_y;
			haveyaw = TRUE;
		}
		else
		{
			dprint(sprintf("zones: no info_teleport_destination '%s' for zone %g\n",
			               zone_td_name[n], n));
			zone_td_kind[n] = ZTD_NONE;     // do not look again on every teleport
		}
	}

	if (zone_td_kind[n] == ZTD_NONE)
	{
		/*
		  The old behaviour, still correct for the 34 legacy maps and for any
		  region that declares nothing.  Feet a little above `bottom` rather than
		  at the centre height: a start zone is typically 256 units tall and
		  dropping the player in at 128 just means a fall.
		*/
		c = zone_centre[n];
		return [c_x, c_y, zone_bottom[n] + 2];
	}

	/*
	  Drop to the floor -- and then CHECK THE ANSWER before committing to it.

	  The unverified version of this shipped in build 6 and the check is not
	  paranoia.  Measured on surf_666: the hull is clear at all thirteen
	  info_teleport_destination origins, and the drop moves you between 113 and
	  288 units.  That is a real floor trace doing its job on this map -- but
	  nothing made it TRUE, and a destination whose floor trace lands somewhere
	  the hull does not fit had no way to say so.  It returned the bad spot and
	  you arrived stuck.

	  So: re-test the hull where the drop wants to put us, and fall back to the
	  raw destination if it does not fit.  The mapper put the entity somewhere
	  the player fits; that is a better answer than a trace result nobody
	  checked.

	  The +1 is Source's own (CTriggerTeleport::Touch does tmp.z++ after aligning
	  to the hull) and build 7 gave trigger_teleport the same lift.  Landing with
	  EXACTLY zero clearance is how a resting position becomes a start-solid on
	  the next move.

	  BUILD 47: THE LIFT IS NOW A FALLBACK RATHER THAN A TOLL.

	  Reported as "when I !r it takes me to the ground, however when I move I
	  lower by like 1 unit or so", and that is exactly what it was: the lift is
	  unconditional, so every `!r` parked the player one unit in the air and the
	  first move spent a tick falling back down.  On a timer that measures from a
	  start box, a start position that is not the one you settle at is wrong twice
	  over -- the fall is real physics the run did not ask for, and the energy
	  readout is a unit of potential above the floor you are about to be on.

	  The lift's REASON is still sound, so it is kept where it is needed instead
	  of being deleted: a resting position with zero clearance can start-solid.
	  But a tracebox already stops DIST_EPSILON short of what it hits, so the
	  endpos is not flush against the floor to begin with, and in the ordinary
	  case there is nothing for the lift to fix.  So: try the floor itself, and
	  only lift if resting there actually is solid.  The failure the lift guards
	  against is still guarded; the cost is no longer paid by every teleport that
	  did not need it.
	*/
	down = dest - [0, 0, ZONE_SNAP_DROP];
	tracebox(dest, PM_HULL_MINS, PM_HULL_MAXS, down, FALSE, self);
	snapped = trace_endpos;

	/*
	  DID IT ACTUALLY LAND ON ANYTHING?

	  "Not solid" is not the same as "on the ground", and until this check the
	  code could not tell them apart -- it took whatever the drop returned and
	  the hull test below passed happily, because empty space is not solid.
	  agtricks is the map that showed it: its start teleDestPos has no floor
	  under it at all, the trace fell the whole 1024, and `!m` put the player
	  1210 units below the start zone in the void, where the timer then never
	  fired again.

	  trace_fraction cannot answer this -- FTE forces it to 1 when a trace
	  starts solid while still writing a correct endpos, which is why the
	  original code was written not to read it (see above).  The DISTANCE can:
	  a drop that used the entire search found nothing to stop it.

	  The FGD's wording is "placed directly on the ground below this point IF
	  POSSIBLE", so the fallback is the mapper's own point, unsnapped.
	*/
	// Build 47: >= ZONE_SNAP_DROP, not >= ZONE_SNAP_DROP - 1.  The old margin was
	// carrying the lift that snapped no longer has, so the two spellings mean the
	// same thing -- "the drop used the entire search and found nothing".  Getting
	// this wrong by one would put agtricks back in the void, quietly.
	if (dest_z - snapped_z >= ZONE_SNAP_DROP)
	{
		dprint(sprintf("zones: no floor within %g units under zone %g, using the raw destination\n",
		               ZONE_SNAP_DROP, n));
		return dest + '0 0 1';
	}

	tracebox(snapped, PM_HULL_MINS, PM_HULL_MAXS, snapped, FALSE, self);
	if (!trace_startsolid && !trace_allsolid)
		return snapped;

	// Resting exactly on the floor IS solid here -- so this is the case the
	// unconditional lift existed for.  Take it, and re-test: a lift that is also
	// solid means the drop found somewhere the player does not fit at all, and
	// the mapper's own point is the better answer (the FGD's wording is "placed
	// directly on the ground below this point IF POSSIBLE").
	snapped = snapped + '0 0 1';
	tracebox(snapped, PM_HULL_MINS, PM_HULL_MAXS, snapped, FALSE, self);
	if (trace_startsolid || trace_allsolid)
	{
		dprint(sprintf("zones: ground snap for zone %g lands solid, using the raw destination\n", n));
		return dest + '0 0 1';
	}

	return snapped;
};

/*
  `stuck` -- what is holding me, right now.

  Every offline test I can run says the teleport destinations on surf_666 are
  clear: no brush entity is solid there, no world brush contains the hull, and
  hl2_propcollision 0 does not free you.  That leaves what an offline BSP reader
  cannot see -- surf_666 has 100 DISPLACEMENTS and 11,076 displacement vertices,
  which the plugin turns into one collision triangle each, and the two maps that
  do NOT trap you have exactly zero displacements.

  Rather than guess a fourth time, this asks the engine.  It traces the player's
  ACTUAL current hull (so it tells the truth while ducked, which is the state
  you said you can still move in) and reports what the trace hit, how far it is
  to free space in each direction, and the contents at four heights up the body.
  hl2_dispcollision 0 is the matching A/B: if `stuck` stops reporting solid with
  that set, it is the displacement collision.
*/
void() SV_Stuck =
{
	local vector o, mn, mx, p;
	local float i, up, contf, contc, conth;

	o  = self.origin;
	mn = self.mins;
	mx = self.maxs;

	tracebox(o, mn, mx, o, FALSE, self);
	sprint(self, PRINT_HIGH,
	       sprintf("^5stuck^7: at %.0f %.0f %.0f  hull %.0f..%.0f tall %.0f\n",
	               o_x, o_y, o_z, mn_z, mx_z, mx_z - mn_z));
	sprint(self, PRINT_HIGH,
	       sprintf("        startsolid %g  allsolid %g  hit '%s'\n",
	               trace_startsolid, trace_allsolid,
	               (trace_ent == world) ? "world" : trace_ent.classname));

	contf = pointcontents(o + '0 0 1');
	contc = pointcontents(o + [0, 0, (mx_z - mn_z) * 0.5]);
	conth = pointcontents(o + [0, 0, mx_z - 2]);
	sprint(self, PRINT_HIGH,
	       sprintf("        contents feet %g  chest %g  head %g\n", contf, contc, conth));

	// How far straight up before the hull fits.  0 means it already does.
	up = -1;
	for (i = 0; i <= 128; i = i + 4)
	{
		p = o + [0, 0, i];
		tracebox(p, mn, mx, p, FALSE, self);
		if (!trace_startsolid)
		{
			up = i;
			break;
		}
	}
	if (up < 0)
		sprint(self, PRINT_HIGH, "        no free space within 128 units above\n");
	else
		sprint(self, PRINT_HIGH, sprintf("        free at +%g up\n", up));

	/*
	  And whether a STANDING hull would fit here at all, which is the whole of
	  "I can sort of move if I crouch": the ducked hull is 45 tall and the
	  standing one 62, so anything with less than 62 units of headroom lets you
	  crawl and then traps you the moment you stand.
	*/
	p  = PM_HULL_MAXS;      // a vector constant is not swizzleable in place
	up = p_z;
	p  = PM_DUCK_MAXS;
	tracebox(o, PM_HULL_MINS, PM_HULL_MAXS, o, FALSE, self);
	sprint(self, PRINT_HIGH,
	       sprintf("        a STANDING hull here: startsolid %g  (ducked %g tall, standing %g)\n",
	               trace_startsolid, p_z, up));
};

/*
  run_eyeinfo -- how high the eye ACTUALLY is, and how tall the thing you are
  judging it against ACTUALLY is.

  Build 41 answered "the eye is 32 units too high" with a CSQC readout that
  measured the camera against pmove_org and got 64.06, and the report was
  called not-reproducible.  That measurement was true and useless: it proves
  the eye is 64 above the ORIGIN, which is the one thing nobody doubted.  It
  says nothing about where the origin is relative to the FLOOR, and the floor
  trace that was supposed to cover that gap ran in CSQC, where a traceline
  falls straight through brush entities -- so on surf_aesthetic's spawn it
  reported world geometry 17 units below the func_ the player was standing on
  and looked like proof of the very bug being investigated.

  This runs SERVER side, where a traceline collides brush entities, so the
  floor it finds is the floor you are standing on.  Two numbers settle it:

    EYE ABOVE FLOOR  -- 64 means the engine is right and the eye is Momentum's.
    aim above floor  -- point the crosshair at the TOP EDGE of the crate you
                        are comparing against.  That number is the crate's
                        real height.  A 64 crate with a 64 eye reads +0.00
                        against the eye; a 48 crate reads -16.

  Because the second one is the half that was never measured.  "I am 16 too
  high next to a 64 box" and "I am correct next to a 48 box" produce the
  identical feeling, and the identical 16, and only the crate can tell them
  apart.  See PM_VIEW_OFS / PM_HULL_MAXS in sh_defs.qc for the shipped values
  and mom_gamerules.cpp's g_ViewVectorsMom for where they came from.
*/
void() SV_EyeInfo =
{
	local vector o, eye, hit;
	local float  floorz, gap, eyeh, headz, aimz;
	local string who;

	o   = self.origin;
	eye = o + self.view_ofs;

	/*
	  Straight down from just above the origin.  `self` is the ignore entity,
	  so the trace cannot start inside our own hull, and TRUE skips other
	  players -- but NOT brush entities, which is the whole point.
	*/
	traceline(o + '0 0 1', o - '0 0 8192', TRUE, self);
	floorz = trace_endpos_z;
	who    = (trace_ent == world) ? "world" : trace_ent.classname;

	gap   = o_z - floorz;
	eyeh  = eye_z - floorz;
	headz = (o_z + self.maxs_z) - floorz;

	sprint(self, PRINT_HIGH,
	       sprintf("^5eye^7: origin %.2f  hull %.0f..%.0f  ducked %g\n",
	               o_z, self.mins_z, self.maxs_z,
	               (self.pmove_flags & PMF_DUCKED) ? 1 : 0));
	sprint(self, PRINT_HIGH,
	       sprintf("     floor %.2f via '%s'   feet-above-floor %.2f\n",
	               floorz, who, gap));
	sprint(self, PRINT_HIGH,
	       sprintf("     ^3EYE ABOVE FLOOR %.2f^7  (view_ofs %.2f, head %.2f)\n",
	               eyeh, self.view_ofs_z, headz));

	/*
	  And the other half: what are you looking at?  Aim at the top edge of the
	  crate.  `aim vs eye` is the number your eyes are actually reporting --
	  0.00 means the crate top is exactly on your eye line.
	*/
	makevectors(self.v_angle);
	traceline(eye, eye + v_forward * 4096, TRUE, self);
	if (trace_fraction >= 1)
	{
		sprint(self, PRINT_HIGH, "     aim: nothing within 4096 units\n");
		return;
	}

	hit  = trace_endpos;
	aimz = hit_z - floorz;
	sprint(self, PRINT_HIGH,
	       sprintf("     aim %.2f above floor, %+.2f vs eye, %.0f away, '%s'\n",
	               aimz, hit_z - eye_z, vlen(hit - eye),
	               (trace_ent == world) ? "world" : trace_ent.classname));
};

/*
  run_slideinfo -- Patch 280's instrument: what the mover would see under the
  feet, from the SERVER, where a traceline collides brush entities.  Two lines
  per call so a log of samples reads as a table:

      slide: org x y z  vel x y z  speed2d S  onground G  ducked D
             under 'classname' skin K normal.z N frac F

  onground is the FL_ONGROUND bit STAT_FS_FLAGS carries to the HUD
  (sv_main.qc's clientstat), so it is the same bit the client reads.  skin in
  -32..-25 means the brush wears the slide tag; with pm_slide 0 the tag is
  still worn and still printed, which is what makes the A arm a control and
  not a different map.  Not gated by anything.

  The first line is two sprintf calls, not one: fteqcc's sprintf takes at most
  8 arguments and the row has nine values.
*/
void() SV_SlideInfo =
{
	local vector o, v, h;
	local string who;

	o = self.origin;
	v = self.velocity;
	h = v;
	h_z = 0;

	traceline(o + '0 0 1', o - '0 0 16', TRUE, self);
	who = (trace_ent == world) ? "world" : trace_ent.classname;

	sprint(self, PRINT_HIGH,
	       strcat(sprintf("^5slide^7: org %.1f %.1f %.1f  vel %.1f %.1f %.1f",
	                      o_x, o_y, o_z, v_x, v_y, v_z),
	              sprintf("  speed2d %.1f  onground %g  ducked %g\n",
	                      vlen(h),
	                      (self.flags & FL_ONGROUND) ? 1 : 0,
	                      (self.pmove_flags & PMF_DUCKED) ? 1 : 0)));
	sprint(self, PRINT_HIGH,
	       sprintf("       under '%s' skin %g normal.z %.3f frac %.3f\n",
	               who, trace_ent.skin, trace_plane_normal_z, trace_fraction));
};

/*
===========================================================================
  Build 54 -- ent_info: what the SERVER made of the entity the client is
  pointing at.

  The other half of cl_entview.qc.  The client can read the entity lump and
  tell you everything the mapper authored; only this side knows what actually
  happened to it -- which spawn function claimed it, what solidity it ended up
  with, whether it has a touch, and what its entity-I/O outputs do.  When the
  two disagree that IS the finding: a trigger the catch-all turned into
  SOLID_NOT because its class is unimplemented reads identically to a working
  one from the lump alone.

  THE CLIENT SENDS A CLASSNAME AND A POINT, not an entity index, and not the
  "*N" model string -- which was the obvious idea and does not work.
  SV_OnEntityNoSpawnFunction CLEARS .model and .modelindex on every trigger it
  does not implement (sv_entities.qc:5023-5030), so the one identifier both
  sides share is gone on exactly the entities most worth asking about.  A
  classname plus the crosshair's impact point survives that, and it also works
  for point entities, which never had a model to match on.

  A SERVER-SIDE TRACE WOULD NOT WORK EITHER, for a reason worth writing down:
  World_ClipToEverything rejects a SOLID_TRIGGER or SOLID_BSPTRIGGER that is not
  flagged FL_FINDABLE_NONSOLID (world.c:1918), and the server's own triggers are
  not -- SV_BindInvisibleBrush does not set it and giving it to them would
  change what findradius returns for gameplay code.  So the aim is done on the
  client, against its own copies, and only the answer is asked for here.

  The arguments are client-supplied, and they are used for exactly two things:
  a find() by classname and a bbox compare.  Nothing is executed and the reply
  goes to the asking client alone.
===========================================================================
*/
string(float s) SV_SolidName =
{
	if (s == SOLID_NOT)         return "NOT";
	if (s == SOLID_TRIGGER)     return "TRIGGER";
	if (s == SOLID_BBOX)        return "BBOX";
	if (s == SOLID_SLIDEBOX)    return "SLIDEBOX";
	if (s == SOLID_BSP)         return "BSP";
	if (s == SOLID_CORPSE)      return "CORPSE";
	if (s == SOLID_BSPTRIGGER)  return "BSPTRIGGER";
	return ftos(s);
};

/*
  BUILD 56 -- A PER-CLIENT COOLDOWN, because this now ships to public lobbies.

  Every ent_info costs one find() walk over a classname, and until this build
  it answered as fast as a client could send it: no rate limit and no cheat
  gate, on servers any stranger can join.  A person clicking the inspector
  asks a few times a minute, so a quarter of a second between answers costs
  nobody anything and caps a spamming client at four walks a second.

  SILENT, deliberately.  A "slow down" reply per refused packet would move the
  cost from the entity walk into the network, which is the opposite of the
  point.  The field is on the asking client, not a global, so one player's
  clicking can never delay another's.

  AND IT ONLY BELIEVES A DEADLINE THAT IS AT MOST ONE COOLDOWN AWAY.  SSQC
  `time` starts again from zero on every map load, so a deadline that survived
  from a longer previous map would sit hours "in the future" and refuse the
  command for the whole of this one -- silently, which would look exactly like
  the inspector having broken.  Anything further ahead than the cooldown itself
  is stale and is ignored.
*/
#define SV_ENTINFO_COOLDOWN 0.25
.float sv_entinfo_next;         // earliest `time` this client may ask again

void() SV_EntInfo =
{
	local entity e, best;
	local vector p;
	local string cn;
	local float  bestd, d, n, vol, bestvol;

	if (self.sv_entinfo_next > time &&
	    self.sv_entinfo_next <= time + SV_ENTINFO_COOLDOWN)
		return;
	self.sv_entinfo_next = time + SV_ENTINFO_COOLDOWN;

	if (argv(1) == "")
	{
		sprint(self, PRINT_HIGH, "^1ent_info^7: no classname given\n");
		return;
	}

	cn = argv(1);
	p  = [stof(argv(2)), stof(argv(3)), stof(argv(4))];

	/*
	  Containment first, nearest-origin second.  A brush entity's origin is
	  almost always '0 0 0' -- VBSP bakes brush geometry in world coordinates and
	  subtracts an origin only for the things that rotate -- so origin alone
	  would tie every func_brush on the map at once.  The bbox is the thing that
	  actually distinguishes them.
	*/
	best = world;
	bestd = 0;
	/*
	  -1 IS "nothing has contained the point yet", and 0 is a real volume.  Not a
	  pedantic distinction: a server entity with no model has absmin == absmax, so
	  its volume IS zero, and b56b found one -- ent_info trigger_multiple answered
	  "solid NOT  model '-'".  With 0 as the sentinel, every later containing
	  entity would beat it and the LAST one would win instead of the smallest.
	*/
	bestvol = -1;
	n = 0;
	e = find(world, classname, cn);
	while (e)
	{
		n = n + 1;
		if (p_x >= e.absmin_x && p_x <= e.absmax_x &&
		    p_y >= e.absmin_y && p_y <= e.absmax_y &&
		    p_z >= e.absmin_z && p_z <= e.absmax_z)
		{
			/*
			  THE SMALLEST BOX THAT HOLDS THE POINT, not the first one found.
			  Volumes of one class nest -- a big trigger_multiple with small ones
			  inside it is ordinary mapping -- and the client already picked the
			  smallest it could see, so answering with whichever came first in
			  edict order described a different entity than the one that was
			  clicked.  No `break` for the same reason.
			*/
			vol = (e.absmax_x - e.absmin_x) * (e.absmax_y - e.absmin_y) *
			      (e.absmax_z - e.absmin_z);
			if (bestvol < 0 || vol < bestvol)
			{
				bestvol = vol;
				best    = e;
			}
		}
		else if (bestvol < 0)
		{
			// Nearest origin, but only while nothing has contained the point.
			d = vlen(e.origin - p);
			if (best == world || d < bestd)
			{
				bestd = d;
				best  = e;
			}
		}
		e = find(e, classname, cn);
	}

	if (best == world)
	{
		/*
		  Not a failure to report -- it is the most useful answer this command
		  gives.  The catch-all removes a point entity outright when it has no
		  geometry to preserve (sv_entities.qc:5010-5015), so "the lump has it
		  and the server does not" is exactly what an unimplemented class looks
		  like from here.
		*/
		sprint(self, PRINT_HIGH,
		       sprintf("^3ent_info^7: '%s' is in the map but NOT on the server -- removed at spawn (unimplemented class)\n", cn));
		return;
	}

	sprint(self, PRINT_HIGH,
	       sprintf("^5ent_info^7: '%s' solid %s  model '%s'  modelindex %g\n",
	               best.classname, SV_SolidName(best.solid),
	               (best.model == "") ? "-" : best.model, best.modelindex));
	sprint(self, PRINT_HIGH,
	       sprintf("          targetname '%s'  target '%s'  touch %s  think %s  (%g of this class)\n",
	               best.targetname, best.target,
	               best.touch ? "yes" : "no",
	               best.think ? "yes" : "no", n));

	/*
	  And what it DOES.  The output chain was parsed at map load and is sitting
	  on the entity already (SV_EntityIOBuild, sv_entities.qc:1939), so this is a
	  walk and not a re-parse.  This is the line the whole feature exists for:
	  "which functions each trigger touches and what it does".
	*/
	e = best.vbsp_io_out;
	if (!e)
		sprint(self, PRINT_HIGH, "          no entity-I/O outputs\n");
	while (e)
	{
		sprint(self, PRINT_HIGH,
		       sprintf("          %s -> %s . %s (%s) delay %g x%g\n",
		               e.vbsp_io_name, e.vbsp_io_target, e.vbsp_io_input,
		               e.vbsp_io_param, e.vbsp_io_delay, e.vbsp_io_times));
		e = e.vbsp_io_next;
	}
};

/*
  Stand at zone n's destination.  Silent: the chat commands go through here
  too, and they say their own, much shorter thing.
*/
void(float n) SV_ZoneMove =
{
	local vector dest;
	local float  yaw, haveyaw;
	local float  samestage;

	dest = SV_ZoneDest(n, yaw, haveyaw);

	/*
	  Build 12: ONE teleport does not void, and it is the one you asked for.

	  Going back to the start of the stage you are ALREADY ON, mid-run, is a
	  stage restart -- the main clock keeps counting and only that segment begins
	  again.  Everything else still voids: a timed run that survived being moved
	  anywhere else would be worth nothing.  The timer owns that decision and
	  returns which of the two it did, because the arm at the bottom of this
	  function has to know: arming a zone we just restarted into would throw the
	  surviving run away by the back door.
	*/
	samestage = SV_TimerTeleported(self, n);

	setorigin(self, dest);
	self.velocity = '0 0 0';

	// You did not travel here.  Without this the next tick's swept zone test
	// runs a segment from wherever you were to the destination and fires every
	// stage and end zone on the line between them.
	SV_TimerWarped(self);

	if (haveyaw)
	{
		self.angles   = [0, yaw, 0];
		self.v_angle  = self.angles;
		self.fixangle = TRUE;
	}

	/*
	  LATCH THE ZONE INDEX, not the (track, segment) pair.

	  `!r` means "the start of the leg I am on".  The leg used to be stored as
	  that pair and re-derived by SV_ZoneFindLeg, which is not injective: on ten
	  legs across nine maps two different zones carry the same pair, and
	  surf_aircontrol's bonus-2 start region is byte-identical to its main start.
	  So `!b 2` followed by `!r` already sent you to the main track.  Latching
	  the index that was actually used cannot be re-derived into a different
	  answer.
	*/
	self.run_leg_zone  = n;
	self.run_leg_track = zone_track[n];
	self.run_leg_seg   = zone_seg[n];

	/*
	  ARM THE LEG YOU ASKED FOR, rather than waiting for the zone scan to
	  notice where you landed.

	  `!s 3` means "put me at the start of stage 3", and the timer that follows
	  should be stage 3's -- not whatever the next tick's point-in-polygon test
	  happens to say.  Leaving it to the scan made the answer depend on the
	  ground snap landing inside the polygon, which is a property of the map's
	  data and not of what you asked for: on a leg where it lands outside, the
	  reset simply dropped you to idle and the run you were on was gone with
	  nothing armed in its place.

	  Arming here is also what makes reset-on-a-stage START A STAGE RUN.  The
	  scan re-arms from the same zone a tick later when the destination is
	  inside it, which is a no-op -- SV_TimerArm is idempotent while armed.

	  Only a START or a STAGE is a leg.  `zone_goto` will take any index,
	  including an end or a checkpoint, and arming from one of those would set
	  a startseg that no run can ever finish.

	  BUILD 12: a stage restart is the exception.  The run is still going and
	  arming would throw it away, which is the whole thing this was asked to
	  stop doing -- see samestage above.

	  BUILD 57: WHICH LEG A START ARMS IS SV_TimerArm's QUESTION, not this
	  function's.  The map's START is where both the full run and stage 1 begin,
	  so the zone cannot say which was asked for; run_t_wantstage1, set by the
	  chat command before this move, does.  Nothing here reads it.
	*/
	if (!samestage)
	if (zone_type[n] == ZONE_START || zone_type[n] == ZONE_STAGE)
		SV_TimerArm(self, n);
};

/*
  zone_goto <n> [yaw] [pitch] -- the console form, which names what it found.

  A diagnostic for "did the zone file parse into what I think it did", so it is
  deliberately wordier than the chat commands.

  The optional angles exist because a screenshot needs a REPEATABLE camera.
  Without them the only way to aim a headless check was to hold +left for a
  number of frames, which is a different angle on every machine and on every
  run -- it depends on the frame rate.  fixangle makes the client adopt the
  angles once and then hand control back.
*/
void(float n, float yaw, float pitch, float setang) SV_ZoneGotoAng =
{
	local vector c;

	if (!zone_loaded)
		SV_ZoneFrame();

	if (zone_count <= 0)
	{
		sprint(self, PRINT_HIGH, "zone_goto: this map has no zone data\n");
		return;
	}

	if (n < 0 || n >= zone_count)
	{
		sprint(self, PRINT_HIGH,
		       sprintf("zone_goto: %g is out of range (0..%g)\n", n, zone_count - 1));
		return;
	}

	c = zone_centre[n];

	// BUILD 57: a standing `!s 1` is cleared by zone_goto, and it is cleared at
	// the CALLER (sv_player.qc's zone_goto arm) rather than here -- run_t_* is
	// declared in sv_timer.qc, which compiles AFTER this file.  Same constraint
	// that makes SV_TimerChatLeg a forward declaration below.
	SV_ZoneMove(n);

	// The explicit angles win over the destination's own, since the point of
	// them is a repeatable camera for a headless screenshot.
	if (setang)
	{
		self.angles     = [pitch, yaw, 0];
		self.v_angle    = self.angles;
		self.fixangle   = TRUE;     // one-shot: the client adopts it, then aims freely again
	}

	sprint(self, PRINT_HIGH,
	       sprintf("zone_goto: %g -- %s, track %g, segment %g\n",
	               n, Zone_TypeName(zone_type[n]), zone_track[n], zone_seg[n]));

	// Naming the destination KIND is the whole diagnostic value now: "did this
	// region declare a destination, and did the targetname resolve".
	if (zone_td_kind[n] == ZTD_POS)
	{
		// An array element is not an lvalue fteqcc will swizzle; it needs a real
		// local, the same way SV_ZoneMove needs one for zone_centre.
		local vector td;
		td = zone_td_pos[n];
		sprint(self, PRINT_HIGH,
		       sprintf("           teleDestPos %.0f %.0f %.0f yaw %.0f\n",
		               td_x, td_y, td_z, zone_td_yaw[n]));
	}
	else if (zone_td_kind[n] == ZTD_NAME)
		sprint(self, PRINT_HIGH,
		       sprintf("           teleDest '%s'\n", zone_td_name[n]));
	else
		sprint(self, PRINT_HIGH,
		       sprintf("           no declared destination, box floor %.0f %.0f %.0f\n",
		               c_x, c_y, zone_bottom[n] + 2));

	sprint(self, PRINT_HIGH,
	       sprintf("           now at %.0f %.0f %.0f\n",
	               self.origin_x, self.origin_y, self.origin_z));
};

/*
  zone_dests -- every leg's declared destination, and where it actually lands.

  The one question this build made askable and nothing else answers: did this
  map's zone file declare destinations, did the targetnames resolve against the
  BSP, and how far is the answer from the box floor we used to use?  A map where
  every row reads "none" is a legacy map; a row reading "MISSING" is a zone file
  that references an entity the BSP does not have; a large delta is a stage that
  used to put you somewhere wrong.

  Deliberately prints the delta rather than just the destination -- the absolute
  coordinates mean nothing without the map open, and the delta is the thing that
  says whether the fix changed anything here.
*/
void() SV_ZoneDests =
{
	local float z, yaw, haveyaw;
	local vector c, old, dest;
	local string kind, state;

	if (!zone_loaded)
		SV_ZoneFrame();

	if (zone_count <= 0)
	{
		sprint(self, PRINT_HIGH, "zone_dests: this map has no zone data\n");
		return;
	}

	sprint(self, PRINT_HIGH, sprintf("zone_dests: %g zones on %s\n", zone_count, zone_mapname));

	for (z = 0; z < zone_count; z = z + 1)
	{
		if (zone_type[z] != ZONE_START && zone_type[z] != ZONE_STAGE)
			continue;

		c   = zone_centre[z];
		old = [c_x, c_y, zone_bottom[z] + 2];

		if (zone_td_kind[z] == ZTD_POS)
			kind = "teleDestPos";
		else if (zone_td_kind[z] == ZTD_NAME)
			kind = zone_td_name[z];
		else
			kind = "none";

		// SV_ZoneDest turns an unresolvable name into ZTD_NONE as a side effect,
		// so read the kind BEFORE calling it or every missing one reads "none".
		dest = SV_ZoneDest(z, yaw, haveyaw);
		if (zone_td_kind[z] == ZTD_NONE && kind != "none")
			kind = strcat(kind, " MISSING");

		/*
		  AND DOES IT LAND INSIDE ITS OWN ZONE?

		  The one question this whole path turns on and nothing used to ask.
		  The timer starts when you LEAVE the zone you armed in, so a
		  destination outside that zone is not a cosmetic wart: it means the
		  clock starts on the tick after the teleport, while you are still
		  standing there.  A row reading OUTSIDE is a map to be careful of.
		*/
		/*
		  Two prints, because fteqcc caps varargs at 8 and silently drops the
		  rest -- the dropped ones still format as zeroes.

		  BUILD 26: `yaw --` changed meaning and it is now the sharper answer.
		  It used to mean "either this region declares no destination, or it
		  declares one whose angles are zero", which are two very different
		  facts wearing one string.  Now that zero is an answer (see
		  SV_ZoneDest) `--` means only the first, so a row reading `yaw 0` is a
		  reset that will aim you north and a row reading `--` is a reset that
		  cannot aim you at all.
		*/
		/*
		  BUILD 47: THREE STATES, BECAUSE "OUTSIDE" STOPPED BEING A BOOLEAN.

		  Once leaving means "the hull clears the box", a destination whose
		  POINT is outside the ring but whose HULL still overlaps it is fine --
		  the clock will not start until you walk out of the band.  The old
		  boolean would cry OUTSIDE on a map with no problem at all.

		    (blank)  the point is in the ring; nothing to say
		    edge     point out, hull still overlapping -- fine under
		             run_zone_hull 1, a genuine wart under 0
		    OUTSIDE  clear of the box entirely, under either rule

		  Deliberately reports against the SHIPPED hull rather than the live one:
		  this is a static map audit, and there is no player ducking in it.
		*/
		if (Zone_PointInside(z, dest))
			state = "";
		else if (Zone_BoxInside(z, dest, PM_HULL_MINS, PM_HULL_MAXS))
			state = "^3edge^7";
		else
			state = "^1OUTSIDE^7";

		sprint(self, PRINT_HIGH,
		       sprintf("  %2g %-10s track %g seg %g  %-24s  ",
		               z, Zone_TypeName(zone_type[z]), zone_track[z], zone_seg[z], kind));
		sprint(self, PRINT_HIGH,
		       sprintf("moved %.0f  yaw %-4s %s\n",
		               vlen(dest - old), haveyaw ? ftos(yaw) : "--", state));
	}
};

/*
  Every checkpoint region and the ORDINAL it parsed to.  Build 19.

  The ordinal is invisible everywhere else -- it does not appear in the zone
  table's other listings and it is not geometry -- but the whole of checkpoint
  timing rests on it: it is the PB index, it is the network edge, and "only ever
  go forwards" is what dedupes a gate built from several regions.  So it needs a
  way to be read directly, and the shape it should have is worth seeing:

    several REGIONS sharing one ordinal   one gate, and it must fire once
    ordinals 1,2,3.. across the track     numbered track-wide, not per segment
    ordinal 0 on a checkpoint             a legacy BSP trigger with no `stage`
                                          key; it will never be timed

  Named for what it lists, like zone_dests beside it.
*/
void() SV_ZoneCheckpoints =
{
	local float z, n;
	local vector c;

	if (!zone_loaded)
		SV_ZoneFrame();

	n = 0;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_type[z] == ZONE_CHECKPOINT)
			n = n + 1;

	sprint(self, PRINT_HIGH, sprintf("zone_cps: %g checkpoint region(s) on %s\n",
	                                 n, zone_mapname));

	for (z = 0; z < zone_count; z = z + 1)
	{
		if (zone_type[z] != ZONE_CHECKPOINT)
			continue;
		c = zone_centre[z];
		// Two prints: fteqcc caps varargs at 8 and silently drops the rest --
		// the same trap zone_dests above documents.
		sprint(self, PRINT_HIGH,
		       sprintf("  zone %2g  track %g seg %g  cp %g  ",
		               z, zone_track[z], zone_seg[z], zone_cp[z]));
		sprint(self, PRINT_HIGH,
		       sprintf("centre %.0f %.0f  z %.0f..%.0f\n",
		               c_x, c_y, zone_bottom[z], zone_top[z]));
	}
};

/*
===========================================================================
  The Momentum chat commands.

  !m       start of the map          track 0, segment 0
  !s N     stage N                   track 0, segment N-1  (stage 1 IS the start)
  !b N     bonus N                   track N, segment 0
  !r       start of the leg you are on

  BUILD 57: `!s 1` and `!m` go to the SAME zone and arm DIFFERENT legs.  Stage 1
  begins at the map's START, so the destination cannot say which was asked for;
  the request does, and it is handed to the timer before the move so the arm at
  the bottom of SV_ZoneMove reads it.  `!s 1` times stage 1 alone and stops at
  stage 2 like every other stage run; `!m` times the map.

  The teleport is all of it for now.  Momentum's `!r` also declines to reset
  your time unless you are on stage 1 or a linear map, which needs a timer to
  decline against; build 7 owns that, and until then this just moves you.
===========================================================================
*/
/*
  The one line a chat command prints, and WHY IT NAMES THE DESTINATION.

  It used to say only "!s -- stage 2", which is the one thing you already knew.
  When a stage lands somewhere that looks wrong, the question is always the same
  and the answer was always another build: is this OUR lookup going astray, or
  is it the entity the mapper placed?  Naming the entity and where it put you
  answers that from the chat line.

  Momentum's stage restarts are info_teleport_destination entities named by the
  zone file (teleDestTargetname), and on surf_666 they sit 190-286 units
  directly ABOVE the zone centroid -- which is why they read as "a point
  floating inside the start" rather than as a start line, and why they are
  ground-snapped before you arrive.  A row that reads `none` is a legacy map
  falling back to the box floor.
*/
void(string word, string what, float n) SV_ZoneSayWhere =
{
	local string kind;

	if (zone_td_kind[n] == ZTD_POS)
		kind = "teleDestPos";
	else if (zone_td_kind[n] == ZTD_NAME)
		kind = zone_td_name[n];
	else
		kind = "box floor";

	sprint(self, PRINT_HIGH,
	       sprintf("^2%s^7 -- %s ^9(%s, %.0f %.0f %.0f)^7\n",
	               word, what, kind,
	               self.origin_x, self.origin_y, self.origin_z));
};

/*
  BUILD 57: the stage-1 request, handed to the timer, which owns it.

  Forward-declared here for the reason SV_TimerTeleported is: the run_t_* fields
  are declared in sv_timer.qc, which compiles after this file, and `!r` has to
  ask whether the run it is restarting is a stage-1 run.  Returns whether the
  request is standing once the word has been applied.
*/
float(entity e, string word, float n) SV_TimerChatLeg;

void(string word, float n) SV_ZoneChatCommand =
{
	local float track, seg, z;
	local string what;

	if (!zone_loaded)
		SV_ZoneFrame();

	if (zone_count <= 0)
	{
		sprint(self, PRINT_HIGH, "^3no zone data for this map\n");
		return;
	}

	if (word == "!m")
	{
		track = 0;  seg = 0;  what = "start of the map";
	}
	else if (word == "!s")
	{
		if (n < 1) n = 1;
		track = 0;  seg = n - 1;  what = sprintf("stage %g", n);
	}
	else if (word == "!b")
	{
		if (n < 1) n = 1;
		track = n;  seg = 0;  what = sprintf("bonus %g", n);
	}
	else		// !r
	{
		track = self.run_leg_track;
		seg   = self.run_leg_seg;

		/*
		  BUILD 57: BEFORE THE MOVE, because the move voids the run.  Inside a
		  stage-1 run `!r` lands on the START that `!m` lands on, and SV_ZoneMove's
		  arm has to come back as stage 1 rather than as the map -- so the timer is
		  asked while the run it is restarting still exists to be asked about.
		  The answer also names the leg in the chat line, which would otherwise
		  say "start of the map" about a stage-1 restart.
		*/
		if (track > 0)   what = sprintf("bonus %g", track);
		else if (seg > 0) what = sprintf("stage %g", seg + 1);
		else if (SV_TimerChatLeg(self, word, n)) what = "stage 1";
		else             what = "start of the map";

		/*
		  Straight back to the zone we latched, without re-deriving it.

		  SV_ZoneFindLeg(track, seg) returns the FIRST zone matching the pair,
		  and on ten legs across nine maps that is a different zone from the one
		  you are actually on -- surf_aircontrol's bonus-2 start region is
		  byte-identical to its main start, so `!b 2` then `!r` landed you on the
		  main track.  The latched index is the answer; the pair is only kept for
		  the message.
		*/
		if (self.run_leg_zone >= 0 && self.run_leg_zone < zone_count)
		{
			SV_ZoneMove(self.run_leg_zone);
			SV_ZoneSayWhere(word, what, self.run_leg_zone);
			return;
		}
	}

	z = SV_ZoneFindLeg(track, seg);
	if (z < 0)
	{
		sprint(self, PRINT_HIGH, sprintf("^3%s: this map has no %s\n", word, what));
		return;
	}

	// BUILD 57: the request, applied only once the destination exists -- a `!s 9`
	// on a five-stage map changes nothing, including a stage-1 request already
	// standing.  `!r` reaches here only when its latched zone was invalid, and
	// asking again is a no-op for it.
	SV_TimerChatLeg(self, word, n);

	SV_ZoneMove(z);
	SV_ZoneSayWhere(word, what, z);
};
