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
===========================================================================
*/

float zone_loaded;

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
			Zone_AddBox(e.absmin, e.absmax, type, e.stage);
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
	*/
	down = dest - [0, 0, ZONE_SNAP_DROP];
	tracebox(dest, PM_HULL_MINS, PM_HULL_MAXS, down, FALSE, self);
	snapped = trace_endpos + '0 0 1';

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
	if (dest_z - snapped_z >= ZONE_SNAP_DROP - 1)
	{
		dprint(sprintf("zones: no floor within %g units under zone %g, using the raw destination\n",
		               ZONE_SNAP_DROP, n));
		return dest + '0 0 1';
	}

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
	local string kind;

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
		sprint(self, PRINT_HIGH,
		       sprintf("  %2g %-10s track %g seg %g  %-24s  ",
		               z, Zone_TypeName(zone_type[z]), zone_track[z], zone_seg[z], kind));
		sprint(self, PRINT_HIGH,
		       sprintf("moved %.0f  yaw %-4s %s\n",
		               vlen(dest - old), haveyaw ? ftos(yaw) : "--",
		               Zone_PointInside(z, dest) ? "" : "^1OUTSIDE^7"));
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
		if (track > 0)   what = sprintf("bonus %g", track);
		else if (seg > 0) what = sprintf("stage %g", seg + 1);
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

	SV_ZoneMove(z);
	SV_ZoneSayWhere(word, what, z);
};
