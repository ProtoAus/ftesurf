/*
===========================================================================
  sv_player.qc -- player lifecycle.

  Deliberately thin.  Movement is the ENGINE's job (engine/common/pm_source.c
  once it lands; FTE's stock QuakeWorld pmove until then), so this file must
  NOT define SV_RunClientCommand -- doing so makes SV_RunFullQCMovement
  bypass the engine pmove entirely (sv_user.c:7490).
===========================================================================
*/

.float  ftesurf_lastspawn;

/*
  THE BOARD TELEMETRY BLOCK USED TO LIVE HERE AND NOW LIVES IN sv_timer.qc.

  Build 19 had already had to move one of them -- .run_rampcontact -- because
  sv_progs.src compiles sv_timer.qc FIRST and the start-hop rule needed it there.
  Build 24 needs the other five for the same structural reason and a better one:
  the RECORDER is in that file, and .rec v4 writes the ramp/ground plane into
  every sample and the board entry into its own record, so a replay can draw the
  strafe bar, the board panel and the segment column instead of refusing to.

  Splitting one engine-written set across two files to save a move was already
  costing a paragraph of explanation in each; the whole block is over there now,
  with the essay it always deserved.  The engine finds all six BY NAME with
  GetEdictFieldValue, so which file declares them makes no difference to it --
  only to fteqcc, and only in the order it reads them.

  See sv_timer.qc, just below .run_rampcontact.
*/

/*
===========================================================================
  Spawn point selection.

  Surf maps come from CS:S, so the spawn is usually info_player_terrorist or
  info_player_counterterrorist; a few use info_player_start.  Try in the
  order a surf map is most likely to provide, and round-robin between
  multiple spawns of the winning class so respawning in a start zone with
  several pads doesn't always drop you on the same one.
===========================================================================
*/
entity(string cn) SV_FindSpawnClass =
{
	local entity e, chosen;
	local float count;

	count = 0;
	chosen = world;
	e = world;
	while ((e = find(e, classname, cn)))
	{
		count = count + 1;
		if (random() * count < 1)
			chosen = e;
	}
	return chosen;
};

entity() SV_SelectSpawnPoint =
{
	local entity spot;

	spot = SV_FindSpawnClass("info_player_start");
	if (spot) return spot;
	spot = SV_FindSpawnClass("info_player_counterterrorist");
	if (spot) return spot;
	spot = SV_FindSpawnClass("info_player_terrorist");
	if (spot) return spot;
	spot = SV_FindSpawnClass("info_player_deathmatch");
	if (spot) return spot;
	spot = SV_FindSpawnClass("info_player_teamspawn");
	if (spot) return spot;

	return world;
};

/*
===========================================================================
  PutClientInServer
===========================================================================
*/
void() PutClientInServer =
{
	local entity spot;

	// First, because a save-lock hold owns the movetype and the velocity while
	// it lasts.  Everything it gives back is overwritten a few lines down --
	// what matters is that the LATCH is off, or the pin would re-freeze this
	// player on the next tick, at the save, having just respawned.
	SV_SaveLocRelease(self);

	/*
	  And the ghost, build 30.  Cleared directly rather than through SV_GhostSet
	  because there is nothing here for the funnel to do: a respawn has no run
	  left to write a closing marker into, and the funnel's console line would be
	  noise on top of a respawn nobody asked a question about.  What matters is
	  only that the latch is off -- a player who respawned while detached would
	  otherwise have a body the zone tests never look at.
	*/
	self.rec_gh_on = FALSE;

	/*
	  BUILD 37 -- everything a map's entity I/O can write onto a PLAYER.

	  .targetname is the load-bearing one.  bhop_futile renames the player
	  block1, block2, ... as they progress and gates each platform's reset
	  teleport on that name; carrying the name across a respawn would leave you
	  arriving at the start already called "block14" and being reset by the
	  first platform you touch.  A respawn is the start of the sequence, so the
	  name has to go with it.

	  It is also why the name must not outlive the map: .targetname on a player
	  is findable by find(), so a stale one could answer a lookup meant for a
	  map entity on the NEXT map.
	*/
	self.targetname   = "";
	self.run_speedmod  = 0;
	self.vbsp_bhop_on   = world;
	self.vbsp_bhop_since = 0;
	// Patch 270, Stage 2.  The per-player landing count, cleared with the rest
	// of the bhop dwell state for the same reason: a count carried into the
	// next life would teleport the player off a LandingLimit block they have
	// only just landed on.
	self.vbsp_bhop_cntblk = world;
	self.vbsp_bhop_cnt    = 0;

	// Patch 256.  Same reasoning one field over: `AddOutput gravity` is a
	// MULTIPLIER a map writes onto the player (208 maps do), and 1441 of the
	// library's 2239 writes are the restore-to-1 that pairs with it.  Miss the
	// restore -- die inside the volume, or leave by a route that has no exit
	// trigger -- and 0.25 rides into the next life and the next map with
	// nothing in any cvar to explain it.  Zero means one on both sides
	// (pm_source.c, gamemovement.cpp:3113), so clearing is the correct reset.
	self.gravity = 0;

	// Patch 249.  A carrier is per-position state: respawning inside a push
	// volume with last life's basevelocity still held would cash it out on the
	// first command of the new run and put the speed on the board.
	self.run_basevel       = '0 0 0';
	self.run_basevel_armed = 0;
	self.run_basevelocity  = '0 0 0';

	self.classname   = "player";
	self.health      = 100;
	self.takedamage  = DAMAGE_NO;
	self.solid       = SOLID_SLIDEBOX;
	self.movetype    = MOVETYPE_WALK;
	self.flags       = FL_CLIENT;
	self.effects     = 0;
	self.velocity    = '0 0 0';
	self.deadflag    = 0;		// DEAD_NO -- a gamecode constant, not an engine one
	self.fixangle    = TRUE;
	self.max_health  = 100;
	self.items       = 0;
	self.weapon      = 0;
	self.weaponmodel = "";

	/*
	  No model: this is a first-person training tool and nobody else is
	  watching.  Saves the player-model network + animation cost entirely.

	  THIS MUST COME BEFORE THE setsize BELOW, and the order is load-bearing.

	  worldspawn sets sv_gameplayfix_setmodelsize_qw 1 so that props receive
	  their model's bounds (Build 34 -- without it every prop had a box of
	  nothing and no prop was ever a physent).  With that cvar set, PF_setmodel
	  stamps a hardcoded +/-16 cube onto any entity whose model does not load,
	  and the empty string is exactly that case: pr_cmds.c:3181-3186, the "nq
	  pretended that its models were all +/- 16" fallback.

	  Run AFTER the setsize -- which is where it sat from Build 34 to Build 41
	  -- it replaced the CS:S hull with mins.z = -16.  The Source mover derives
	  the hull TOP from the bottom (player_maxs[2] = player_mins[2] + stand-
	  height), so the box became -16..46: the right height, 62, in the wrong
	  place.  The feet then rested on the floor with the ORIGIN 16 units above
	  it, and since view_ofs is measured from the origin the eye sat at 80
	  instead of 64 -- while every readout that measured the eye against the
	  origin still said a correct 64.  Ducked it read 63, which is why crouching
	  looked like the right standing height next to a 64-unit crate.
	  sv_user.c writes the hull back to the entity each move, so one bad
	  setmodel was enough to make it permanent.

	  worldspawn's own note claimed this was safe because "the player
	  setmodel("")s then setsize()s itself explicitly".  That is now true.
	*/
	setmodel(self, "");

	// CS:S hull, origin AT THE FEET (Source convention, not Quake's centre).
	setsize(self, PM_HULL_MINS, PM_HULL_MAXS);
	self.view_ofs = PM_VIEW_OFS;
	// PM_RUN_SPEED is only the fallback now -- see PlayerPreThink below.
	self.maxspeed = cvar("sv_maxspeed");
	if (self.maxspeed <= 0)
		self.maxspeed = PM_RUN_SPEED;

	spot = SV_SelectSpawnPoint();
	if (spot)
	{
		// CBasePlayer::Spawn nudges 1 unit up off the spawn pad.
		setorigin(self, spot.origin + '0 0 1');
		self.angles = spot.angles;
	}
	else
	{
		dprint("FTESurf: no spawn point in this map, using world origin\n");
		setorigin(self, '0 0 64');
		self.angles = '0 0 0';
	}
	self.angles_z = 0;
	self.v_angle = self.angles;

	self.ftesurf_lastspawn = time;

	// Claim the timer's ring/split row, clear any run, and drop the recorder.
	// A respawn is a teleport as far as a timed run is concerned.
	SV_TimerSpawn(self);

	/*
	  LAST, and after SV_TimerSpawn on purpose.

	  `retry` restarted the map, and this is the first moment the player it
	  restarted for exists again.  It has to run after the spawn has finished
	  putting them at a spawn point and idling their timer, because undoing all
	  of that is exactly what it is for.  A no-op on every ordinary spawn --
	  see the arm latch in SV_TimerMapInit.
	*/
	SV_RetryApply(self);
};

/*
===========================================================================
  Connect / disconnect
===========================================================================
*/
void() ClientConnect =
{
	bprint(PRINT_HIGH, self.netname, " entered the game\n");

	/*
	  Re-open the map's areaportals for THIS client.  See func_areaportal.

	  openportal() both flips the state on the server's world model and sends
	  svc_setportalstate to every CONNECTED client -- and at spawn time, when
	  the entities run, there are none.  In a listen game that does not matter
	  (the server and client share one model_t, so the direct call has already
	  done the job), but a client connecting over the network would otherwise
	  join with every area but its own culled away.
	*/
	SV_OpenAllPortals();

	// Patch 270: give this player a body for everyone else to look at.  A no-op
	// unless lobby_enable is set, so a solo session is byte-identical to before.
	Lobby_ClientConnect(self);
};

void() ClientDisconnect =
{
	bprint(PRINT_HIGH, self.netname, " left the game\n");

	// Before the timer teardown, because it only removes an entity and the
	// timer's teardown is the part that must not be skipped if this throws.
	Lobby_ClientDisconnect(self);

	// Close any open .rec before the edict goes: fclose is what actually
	// writes the file, and a leaked handle is one of MAX_QC_FILES gone for
	// the rest of the session.
	SV_TimerIdle(self);
	SV_TimerReleaseSlot(self);

	/*
	  Patch 270, Stage 2.  Beside SV_TimerReleaseSlot because it is the same
	  act: this releases the OTHER per-player slot, the trigger bit, which is
	  keyed on the edict number the engine is about to hand to whoever connects
	  next.  Without it that player inherits every trigger_once this one
	  consumed, for the rest of the map, in silence.  See SV_TouchForget.
	*/
	SV_TouchForget(self);
};

void() ClientKill =
{
	// 'kill' is the reset-to-spawn button, not suicide -- there is no combat.
	PutClientInServer();
};

void() SetNewParms    = { };
void() SetChangeParms = { };

/*
===========================================================================
  Per-frame hooks.

  PreThink is empty on purpose -- the engine runs the whole move in
  SV_RunCmd and there is nothing for QC to add before it.

  PostThink samples the surface the player is about to hit, purely so the
  HUD can show the ramp normal.  Tracing forward along velocity for exactly
  one tick is the same swept box TryPlayerMove will run next tick, so the
  reported normal is the plane that will actually clip you -- which is what
  you want when the question is "am I on a 0.7 boundary?".  A straight-down
  trace would report nothing at all while surfing.
===========================================================================
*/
/*
  BUILD 15 -- make sv_maxspeed the knob it always looked like.

  `.maxspeed` is what the mover actually reads: the server networks it per
  client as svc_maxspeed and sv_user.c:7883 hands THAT to pm_source, never the
  cvar.  PutClientInServer used to pin it to a compile-time constant, so
  sv_maxspeed was a cvar you could set all day with no effect -- and prestrafe
  scales exactly with it, which made that the single most misleading knob in
  the config.

  Tracked here rather than only at spawn so a change takes effect on the next
  tick instead of the next respawn.  SV_UpdateMovementServerInfo runs in
  StartFrame, ahead of every player think, so sv_mv_maxspeed is already this
  frame's value; the guard is for the frames before StartFrame has ever run,
  where handing the mover a zero would leave the player unable to move at all.
*/
void() PlayerPreThink =
{
	/*
	  The pre-move ground state, for OnJump (SV_TriggerIOTouch).

	  This runs BEFORE the move; the trigger touch loop runs after it.  So a
	  player whose flags said ONGROUND here and do not by the time a touch fires,
	  and who is moving upward, jumped on this exact command.  Recording it costs
	  one field write per player per command and is the only way to tell a jump
	  from a walk off a ledge without the engine telling us.
	*/
	self.run_wasground = ((self.flags & FL_ONGROUND) != 0);

	/*
	  PATCH 249 -- CheckMovingGround, in its own slot.

	  Source runs this at player_command.cpp:472, BEFORE PreThink, before Think
	  and before ProcessMovement.  Here it is the first thing PreThink does,
	  which is the same place relative to everything that matters: after last
	  command's touch functions wrote the carrier, and before the engine reads
	  .run_basevelocity out of us at sv_user.c:7994.

	  It has to be before that read.  A boost that is cashed out here must NOT
	  also be handed to pmove this command, or it is spent twice -- once as
	  velocity and once as a carrier.  SV_BaseVelocityFrame zeroes the held
	  vector and then assigns the engine field from it, in that order, so the
	  engine gets '0 0 0' on exactly the command the money is paid.
	*/
	SV_BaseVelocityFrame(self);

	if (sv_mv_maxspeed > 0)
		self.maxspeed = sv_mv_maxspeed;

	/*
	  BUILD 37 -- player_speedmod's ModifySpeed, applied here rather than at the
	  moment the input fires.

	  It has to be here, because the line above overwrites .maxspeed every tick:
	  anything written to that field from a touch function would survive exactly
	  until the next PreThink.  Source's own value is a multiplier on the
	  player (m_flLaggedMovementValue), so a multiplier is also the faithful
	  shape.

	  bhop_futile is the only map here that uses it and every one of its three
	  ModifySpeed outputs passes 1.0, so this is a no-op on the map it was
	  written for.  That is the honest outcome and not a failure -- the map
	  toggles a "no bhop" zone whose speed factor happens to be unity.
	*/
	if (self.run_speedmod > 0 && self.run_speedmod != 1)
		self.maxspeed = self.maxspeed * self.run_speedmod;
};

/*
  BUILD 13b -- noclip marks the run as practice, WHEREVER noclip came from.

  Build 13 put SV_TimerPractice in SV_ParseClientCommand's "noclip" branch and
  it never once ran, because that branch is unreachable: `noclip` is an ENGINE
  command, registered twice in the client-command table (sv_user.c:6668 and
  :6740 -> Cmd_Noclip_f) and again as a console command for the listen server
  (sv_ccmds.c:3645 -> SV_Noclip_f).  Both flip movetype themselves and return;
  neither forwards to QC's ClientCommand, so the gamecode is simply never told.
  `setpos` does the same thing (sv_user.c:5591-5595), and so would any future
  engine path that hands you a free position.

  Watching the movetype is what makes that irrelevant.  It is the STATE that
  means "this position was not earned", so keying off the state rather than off
  one of the several commands that can produce it is both shorter and complete.
  One float per player and a compare per tick.
*/
.float run_lastmovetype;

/*
  BUILD 43 -- LEVEL FOR THE STAGE, EDGE FOR THE RUN, AND THE HOLE THAT CLOSES.

  Per-stage cleanliness means SV_StageOpen destroys the taint at every boundary,
  because "the next stage starts clean" is the whole feature.  An EDGE detector
  cannot survive that: noclip on in stage 2, cross into stage 3 still noclipping,
  and the edge has long since fired -- so stage 3 is admitted as clean while you
  fly through it and gets written to the stage board.

  IT WOULD HAVE PASSED EVERY TEST ANYONE WOULD THINK TO WRITE, which is why it is
  worth six lines of comment: a test that toggles noclip inside one stage sets
  the edge inside that stage and reads correctly.  Only holding it ACROSS a
  boundary shows it, and that is the gesture nobody scripts.

  So the STATE sets the per-stage field every tick it is true, and the EDGE calls
  the run-level funnel exactly as before.  run_t_dirty keeps its old lifetime --
  set once, cleared only by an arm -- so nothing about the run changes.

  BUILD 44 CLOSED THE SECOND HALF.  Build 43's note here said the same shape was
  wanted for `sv_cheats` -- which can be on for a whole session with no edge
  inside any given stage -- and that it was deliberately absent because nothing
  in that build made sv_cheats taint a run at all.  It does now, so the watcher
  below watches both states and the note is kept as the record of why the
  asymmetry existed for one build.
*/
.float run_lastcheats;           // build 44, the sv_cheats edge

/*
  TWO STATES, TWO EDGES, ONE WATCHER.

  They are watched together rather than in two functions because they are one
  question -- "is this position earned" -- and because the LEVEL half is a union:
  a stage is cheated if either was true at any point inside it, and two watchers
  would have written that union in two places.  The two EDGES stay separate,
  because turning noclip on and typing sv_cheats 1 are different news and either
  one arriving first must still be reported.

  sv_cheats is read through SV_CheatsOn, which is where the run_class and
  run_cheatwatch gates live and where the decision NOT to cache the cvar is
  argued.  Reading it here directly would put a third copy of that rule in the
  tree; the umbrella below is the only thing this function decides for itself.

  THE UMBRELLA IS RAISED FOR NOCLIP UNCONDITIONALLY, because noclip was a taint
  before this build and a cvar must not be able to take an existing taint away.

  BUILD 46: AND FOR sv_cheats UNCONDITIONALLY TOO.  This paragraph used to add
  "and for cheats only through the gate, and that split is what makes
  `run_class 0` build 43 exactly".  It did -- and that WAS the defect, stated
  as a feature: build 43 did not watch sv_cheats at all, so "exactly build 43"
  meant an sv_cheats run ranked.  The gate is gone from SV_CheatsOn.  At
  run_class 0 the edge below still fires and still funnels to SV_TimerPractice,
  so the attempt is plain `practice` and unrankable and only the WORD is
  bisected; at 1 nothing about this function changed at all.

  THE NAME IS BUILD 13b's AND IS NOW HALF THE STORY.  Kept anyway: four essays in
  sv_timer.qc name this function as the canonical level-vs-edge example, and a
  rename that silently orphans all four is worse than a name that undersells by
  one state.  The comment above is the correction.
*/
void(entity e) SV_NoclipWatch =
{
	local float nc, sc;

	nc = (e.movetype == MOVETYPE_NOCLIP) ? TRUE : FALSE;
	sc = SV_CheatsOn();

	// ---- LEVEL: every tick either is true, whatever fired when ----------
	if (nc)
		e.run_st_dirty = TRUE;
	if (sc)
		e.run_st_dirty = TRUE;
	if (SV_CheatLevel(e))
		e.run_st_cheat = TRUE;

	// ---- EDGE: the run-level funnel, once per gesture ------------------
	if (nc)
	if (e.run_lastmovetype != MOVETYPE_NOCLIP)
		SV_TimerCheat(e);

	if (sc)
	if (!e.run_lastcheats)
		SV_TimerCheat(e);

	e.run_lastmovetype = e.movetype;
	e.run_lastcheats   = sc;
};

void() PlayerPostThink =
{
	local vector dest;

	SV_NoclipWatch(self);

	/*
	  BUILD 37 -- the func_bhop dwell rule.

	  BEFORE SV_TimerFrame, which matters: SV_BhopFrame can teleport, and the
	  timer's swept zone test must see the arrival rather than run a segment
	  from the platform to the destination.  SV_BhopTeleport calls
	  SV_TimerWarped for the same reason trigger_teleport_touch does, and that
	  call is only correct if the timer has not already scanned this tick.
	*/
	SV_BhopFrame(self);

	// +use, for maps that wire a func_button.  A rising edge on .button5 and a
	// short trace; nothing at all happens on a map that wires nothing.
	SV_UseFrame(self);

	/*
	  The timer, the zone scan and the recorder, once per usercmd.

	  Here rather than in StartFrame because this is the ONLY hook that runs
	  after the move with the post-move origin, and because a recording sampled
	  at the server frame rate would be sampling a different clock from the one
	  the physics ran on.  It is also where the leg tracker (`!r`) now latches
	  -- see SV_ZoneFrame for why that moved.
	*/
	SV_TimerFrame(self);

	/*
	  BUILD 43: pack the stage state for the wire.  HERE and not at the bottom of
	  SV_TimerFrame, which has three early returns -- no zone file, ghosting, and
	  the freeze block above the zone guard -- and the state is most interesting
	  on exactly those ticks.  See SV_StageStat.
	*/
	SV_StageStat(self);

	// Pinned at a save-lock while the load key is held.  After the timer, so
	// the zone scan sees where the move actually left you and the pin is the
	// last word on the origin.
	SV_SaveLocHoldFrame(self);

	// The save list is global (it is on disk, under the map) and clientstat
	// takes a field, so the count and the cursor's stored time are mirrored into
	// this player's fields here.  Three float compares; see SV_SaveLocSync.
	SV_SaveLocSync(self);

	// NOTE: view_ofs is NOT set here any more.
	//
	// The eye moves SMOOTHLY through a crouch (Source's SetDuckedEyeOffset on
	// a SimpleSpline over TIME_TO_DUCK / TIME_TO_UNDUCK) while the hull snaps
	// at the end of the transition.  That curve is a function of pmove's
	// carried duck timer, which QC cannot see -- PMF_DUCKED only flips once
	// the transition has already finished, so anything driven from it can
	// only ever be the snap this used to do.
	//
	// So the engine writes view_ofs[2] itself, right where it writes
	// PMF_DUCKED (sv_user.c, gated on pm_physicsmode 1), and SV_UpdateClient-
	// Stats carries it to the client as the float STAT_VIEWHEIGHT.  Writing
	// it here as well would stamp on the curve every frame.

	if (self.velocity == '0 0 0')
	{
		self.run_groundnorm = '0 0 0';
		return;
	}

	dest = self.origin + self.velocity * PM_TICK;
	tracebox(self.origin, self.mins, self.maxs, dest, FALSE, self);

	if (trace_fraction < 1)
		self.run_groundnorm = trace_plane_normal;
	else
		self.run_groundnorm = '0 0 0';
};

/*
===========================================================================
  Client commands.

  Unrecognised commands MUST be forwarded to the clientcommand builtin or
  the engine's own handling (say, kill, ...) stops working.
===========================================================================
*/
void(string cmd) SV_ParseClientCommand =
{
	local string c;
	local float  cmdargc;

	cmdargc = tokenize(cmd);
	c = argv(0);

	if (c == "noclip")
	{
		if (self.movetype == MOVETYPE_NOCLIP)
		{
			self.movetype = MOVETYPE_WALK;
			sprint(self, PRINT_HIGH, "noclip OFF\n");
		}
		else
		{
			self.movetype = MOVETYPE_NOCLIP;
			sprint(self, PRINT_HIGH, "noclip ON\n");
			// TF_PRACTICE is set by SV_NoclipWatch, not here -- this branch is
			// dead code on any build where the engine registers `noclip`
			// itself, which is every build.  Kept because a client CAN reach
			// it (`cmd noclip` from a build without the engine command) and
			// because the watcher makes it harmless either way.
		}
		return;
	}

	if (c == "respawn" || c == "restart")
	{
		PutClientInServer();
		return;
	}

	// What this map actually contains that we do not handle.  Needs
	// `developer 1` set BEFORE the map loads, since the census is built as
	// entities spawn.
	if (c == "ent_census")
	{
		SV_CensusPrint();
		return;
	}

	if (c == "zone_dests")
	{
		SV_ZoneDests();
		return;
	}

	// Build 19.  The checkpoint ordinals, which nothing else can show.
	if (c == "zone_cps")
	{
		SV_ZoneCheckpoints();
		return;
	}

	/*
	  Where the eye actually is, measured against a SERVER-side floor trace so
	  brush entities count, plus the height of whatever the crosshair is on.
	  The client-side `eye` HUD row cannot do the first and does not attempt
	  the second; see SV_EyeInfo for why both halves are needed.
	*/
	if (c == "run_eyeinfo")
	{
		SV_EyeInfo();
		return;
	}

	// Patch 280: what the mover sees under your feet.  See SV_SlideInfo.
	if (c == "run_slideinfo")
	{
		SV_SlideInfo();
		return;
	}

	/*
	  Build 54: what the SERVER made of the entity the client is pointing at --
	  its real solidity, whether it has a touch, and its entity-I/O chain.  Sent
	  by cl_entview.qc's ent_here, which does the aiming; SV_EntInfo says why the
	  aim cannot be done on this side.
	*/
	if (c == "ent_info")
	{
		SV_EntInfo();
		return;
	}

	// What is holding me, right now.  See SV_Stuck.
	if (c == "stuck")
	{
		SV_Stuck();
		return;
	}

	// What the timer's state machine currently believes.  See SV_TimerReport.
	if (c == "timer")
	{
		SV_TimerReport(self);
		return;
	}

	/*
	  Save-locks.

	  ONE COMMAND PER ACTION rather than `saveloc <verb>`, because these are
	  driven by single key presses in CSQC (cl_saveloc.qc) and a key that maps
	  to exactly one command cannot send the wrong verb.

	  BUILD 25: sl_loadlast AND sl_dellast ARE GONE, AND THAT IS THE BUG FIX.

	  They were the menu-CLOSED bindings and acted on the END of the list rather
	  than on the cursor -- sl_loadlast loaded rec_sl_count, not rec_sl_index.  So
	  stepping to save 2 of 5 with the menu open and then pressing 2 with it shut
	  loaded save 5, which is exactly the reported "it loads the current save
	  instead of the one I selected".  The digits now only act while the menu is
	  up (cl_saveloc.qc) and there is only one meaning of each, so the pair of
	  commands that could disagree with the cursor no longer exists.
	*/
	if (c == "sl_save")    { SV_SaveLocCreate(self);                     return; }
	if (c == "sl_load")    { SV_SaveLocLoad(self, self.rec_sl_index);     return; }

	/*
	  Hold.  Two commands rather than one with an argument, so a lost or
	  reordered release cannot be misread as a press: `sl_holdoff` means
	  exactly one thing whatever else is in flight.
	*/
	if (c == "sl_hold")    { SV_SaveLocHold(self, TRUE);                 return; }
	if (c == "sl_holdoff") { SV_SaveLocHold(self, FALSE);                return; }

	/*
	  Watching a recording.  ONE command with an argument, unlike the hold above,
	  and the reason is the opposite of that one's: a watch is a mode rather than
	  a key, the client sends the two edges seconds or minutes apart rather than
	  in flight together, and `rec_watch 0` from the console has to be a way out
	  if a client ever fails to send its own.
	*/
	if (c == "rec_watch")   { SV_WatchHold(self, stof(argv(1)));          return; }

	/*
	  Ghost, build 30.  One verb with an argument, on the `rec_watch` side of the
	  distinction the essay above draws rather than the sl_hold/sl_holdoff side:
	  it is a mode held for as long as you are looking around, its two edges are
	  typed a long way apart, and `cmd rec_ghost 0` has to exist as a way back
	  into your body if a client ever fails to send its own.
	*/
	if (c == "rec_ghost")   { SV_GhostSet(self, stof(argv(1)));           return; }

	/*
	  BUILD 43 -- WHERE THE DETACHED CAMERA IS, for the PVS and for nothing else.

	  The one thing the server was never told, and the reason a replay on some
	  maps drew a skeleton of world brushwork with every func_brush ramp and
	  prop_dynamic model missing: entity visibility is computed from the client's
	  EDICT, which during a replay is a body pinned where the key was pressed.
	  See the essay at SV_ViewEyeAt in sv_saveloc.qc for the measurement.

	  IT MOVES NOTHING AND DECIDES NOTHING.  It writes one invisible marker's
	  origin, which the engine unions into this client's PVS through .view2.  The
	  body stays pinned, the clock stays frozen, no zone is tested against it and
	  no trigger is touched -- setorigin relinks without running touch functions.
	  So there is no exploit surface here even though it is a client saying where
	  it is: the worst a lying client can do is ask to be sent entities it could
	  already have asked for by walking there, in a single-player training tool
	  with sv_cheats one word away.

	  REFUSED WHEN NEITHER MODE IS OPEN, which is the whole of the validation it
	  needs.  A player who is not watching and not ghosting has no eye to move,
	  and SV_ViewEyeAt would otherwise spawn one that nothing ever removes.
	*/
	if (c == "rec_watchpos")
	{
		if (self.rec_wt_hold || self.rec_gh_on)
			SV_ViewEyeAt(self, [stof(argv(1)), stof(argv(2)), stof(argv(3))]);
		return;
	}

	if (c == "sl_del")     { SV_SaveLocDelete(self, self.rec_sl_index);   return; }
	if (c == "sl_delall")  { SV_SaveLocDeleteAll(self);                  return; }
	if (c == "sl_prev")    { SV_SaveLocStep(self, -1);                   return; }
	if (c == "sl_next")    { SV_SaveLocStep(self,  1);                   return; }
	if (c == "sl_first")   { SV_SaveLocFirst(self);                      return; }
	if (c == "sl_last")    { SV_SaveLocLast(self);                       return; }
	if (c == "sl_list")    { SV_SaveLocList(self);                       return; }
	if (c == "sl_goto")    { SV_SaveLocLoad(self, stof(argv(1)));        return; }

	// The client half of `retry`.  The engine's own command offers itself to
	// CSQC first (Patch 185); CSQC writes its sidecar and then forwards here.
	if (c == "rec_retry")   { SV_RetryPoint(self);                        return; }

	if (c == "zone_goto")
	{
		// zone_goto <n> [yaw] [pitch] -- the angles are optional and only
		// applied when given, so an interactive `zone_goto 0` still leaves you
		// looking wherever you were looking.
		SV_ZoneGotoAng(stof(argv(1)), stof(argv(2)), stof(argv(3)), cmdargc >= 3);
		return;
	}

	/*
	  viewpos -- where am I?  Build 24.

	  ONE VERB EACH, and that is the whole of this change.  `setpos` with no
	  arguments printed the position, which is the engine's own convention
	  (sv_user.c:5587) and is genuinely confusing: the command called "set"
	  was the only way to "get", so the two halves of "where am I, and put me
	  back there" both lived under the word for the second one.

	  It prints in setpos's own argument order, so the line pastes straight back
	  in -- which is the entire point of it existing and is why it is not merely
	  a %v of the origin.  A zone number cannot do this job: zones are leg starts,
	  and "the first ramp of stage 1" is not one.

	  Server-side, because the answer is the PLAYER's position: origin and
	  v_angle as the server holds them, which is exactly what setpos writes back.
	  The client's camera is a different question and, while a replay is playing,
	  a different place entirely -- `replay status` answers that one.
	*/
	if (c == "viewpos")
	{
		sprint(self, PRINT_HIGH,
		       sprintf("setpos %.1f %.1f %.1f %.1f %.1f %.1f\n",
		               self.origin_x, self.origin_y, self.origin_z,
		               self.v_angle_x, self.v_angle_y, self.v_angle_z));
		return;
	}

	/*
	  setpos -- put me exactly there.

	  IT SHADOWS THE ENGINE'S OWN setpos, deliberately, and keeps its argument
	  order (x y z pitch yaw roll, sv_user.c:5587) so a line printed by either
	  works in either.  The engine's does two things that are wrong here:

	  * it forces MOVETYPE_NOCLIP and leaves you in it, so arriving somewhere to
	    look at it means also remembering to turn noclip off before you can
	    stand on anything;
	  * it does not tell the timer.  A jump across the map with the swept zone
	    test live draws a segment from where you were to where you asked for and
	    fires every stage and end zone on the line between them -- see
	    SV_ZoneMove, which has the same problem and the same two-line fix.

	  Our chat and zone commands teleport without a cheat gate, so this matches
	  them rather than the engine's cheat rule.

	  BUILD 24: IT MARKS THE RUN PRACTICE RATHER THAN VOIDING IT.

	  Voiding threw the attempt away, which made setpos unusable for the thing it
	  is actually reached for mid-run -- "put me at that ramp and let me try the
	  next section" -- because the clock you were studying disappeared along with
	  the position.  Practice keeps the clock, the splits and the checkpoints
	  exactly as they were and only refuses to KEEP the result, which is the same
	  bargain a save-lock load and a stage restart already make.  The taint
	  survives the rest of the attempt and is cleared by the next arm, so a run
	  cannot be laundered by teleporting and then finishing.
	*/
	if (c == "setpos")
	{
		if (cmdargc < 4)
		{
			sprint(self, PRINT_HIGH,
			       "setpos <x> <y> <z> [pitch] [yaw] [roll] -- "
			       "^5viewpos^7 prints where you are\n");
			return;
		}

		SV_SaveLocRelease(self);
		/*
		  BUILD 44: A CHEAT, NOT A STITCH, and it is the one call in the class
		  split that could honestly go the other way.

		  The argument FOR stitch: setpos is this mod's own deliberately ungated
		  command (see the paragraph above about the cheat gate), and it is reached
		  mid-run for "put me at that ramp and let me try the next section" -- a
		  practice gesture with legal physics, which is exactly what `segmented`
		  is meant to name.

		  The argument for cheat, which wins: it hands you a POSITION YOU DID NOT
		  EARN.  That is noclip's whole argument and noclip is not in doubt, and a
		  save-lock at least required you to have stood there once.  Landing it in
		  the gentler bucket would let a run be teleported to the last ramp and
		  labelled with the same word as somebody replaying a section they saved.

		  One line either way.  Written down so a later change here is a decision.
		*/
		SV_TimerCheat(self);

		setorigin(self, [stof(argv(1)), stof(argv(2)), stof(argv(3))]);
		self.velocity = '0 0 0';
		SV_TimerWarped(self);

		// Angles are optional, and all three arrive together or not at all --
		// which is what the engine's own print emits.
		//
		// BOTH FIELDS GET THE FULL TRIPLE.  The engine sends .angles rather than
		// .v_angle whenever fixangle is set (sv_send.c:1535), so the old
		// `[0, v_angle_y, 0]` here silently dropped the pitch off the wire and
		// this command could not aim up or down -- the same one-token bug as
		// SV_SaveLocPlace, and the reason a scripted screenshot always came out
		// level.  The engine's own setpos (sv_user.c:5605, Patch 165) writes
		// both, and its comment is this bug.
		if (cmdargc >= 7)
		{
			self.v_angle  = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
			self.angles   = self.v_angle;
			self.fixangle = TRUE;
		}

		sprint(self, PRINT_HIGH, sprintf("setpos: %v\n", self.origin));
		return;
	}

	/*
	  Momentum's chat commands.

	  `say` reaches us before the engine's own SV_Say_f does -- the ucmds table
	  entry has no noqchandling flag, so PR_KrimzonParseCommand gets first
	  refusal (sv_user.c) -- which is exactly the hook a chat command needs.
	  Anything that is not one of ours falls through to clientcommand() at the
	  bottom and gets said out loud as normal.

	  THE SPACE IS REQUIRED: `!s 1`, not `!s1`.

	  Both spacings used to be accepted, on the grounds that `!s2` is what
	  fingers produce.  Reversed by request.

	  THE WHOLE MESSAGE ARRIVES AS ONE TOKEN, which is the thing to know here
	  and which I got wrong first.  Cmd_ForwardToServer quotes the chat text, so
	  `say !s 2` reaches SV_ParseClientCommand as TWO tokens, not three:
	  argv(0) = "say" and argv(1) = "!s 2", space and all.  cmdargc is 2 and
	  argv(2) is empty.

	  Which means the old parser's `(cmdargc >= 3) ? stof(argv(2))` branch was
	  DEAD CODE and had always been: `!s 2` never worked, and only `!s2` ever
	  did, through the digit-suffix path.  So this is not a restriction, it is
	  the spaced form being implemented for the first time -- Momentum's own
	  syntax, which is presumably why it was the one being asked for.

	  So split argv(1) on its first space ourselves.  The rule is then exactly
	  "the word before the space IS the command", which also keeps `!rank` and
	  anything else this game does not have going to chat instead of silently
	  teleporting whoever typed it.  A tail that is not purely digits also falls
	  through, so `!s 2 lol` is chat rather than a stage warp.
	*/
	if (c == "say" || c == "say_team")
	{
		local string msg, w, tail;
		local float  n, sp, i, ch, alldigits;

		msg = strtolower(argv(1));
		sp  = strstrofs(msg, " ", 0);

		if (sp < 0)
		{
			w = msg;
			tail = "";
		}
		else
		{
			w    = substring(msg, 0, sp);
			tail = substring(msg, sp + 1, strlen(msg) - (sp + 1));
		}

		if (w == "!m" || w == "!s" || w == "!b" || w == "!r")
		{
			alldigits = TRUE;
			for (i = 0; i < strlen(tail); i = i + 1)
			{
				ch = str2chr(tail, i);
				if (ch < '0' || ch > '9')
				{
					alldigits = FALSE;
					break;
				}
			}

			if (alldigits)
			{
				n = stof(tail);         // stof("") is 0, which is what !m/!r want
				SV_ZoneChatCommand(w, n);
				return;
			}
		}
	}

	/*
	  The same two, as real commands, so they can be bound to a key without
	  going through the chat parser.

	  NAMED zone_*, matching zone_goto and zone_dests above.  They were
	  fs_restart and fs_reset, which was a bad mistake in two ways.  `fs_restart`
	  is an ENGINE console command (Cmd_AddCommand, fs.c) that rebuilds the
	  entire filesystem -- the path that re-enumerates every mounted package,
	  re-parses every shader, and carries the dangling-bucket crash the engine's
	  own comment in fs.c documents.  So the name was taken, by the single most
	  expensive command in the build.

	  It did not collide outright, because ours arrives as a client->server
	  command (`cmd fs_restart`) while the engine's is dispatched locally -- which
	  is the second problem: `bind x fs_restart` reached the ENGINE every time and
	  ours was unreachable by the obvious route.  Both halves go away with the
	  rename.
	*/
	if (c == "zone_restart") { SV_ZoneChatCommand("!m", 0); return; }
	if (c == "zone_reset")   { SV_ZoneChatCommand("!r", 0); return; }

	clientcommand(self, cmd);
};
