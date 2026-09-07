/*
===========================================================================
  sv_main.qc -- world setup and the per-frame server hook.
===========================================================================
*/

void() main = { };

/*
  Push the movement parameters the client needs for prediction and for the
  HUD into serverinfo.  CSQC reads them back with serverkeyfloat() so both
  VMs agree without registering the cvars twice.  (This is the same trick
  quakec/csqctest/src/common/pmove.qc:332-344 uses.)

  Called once at worldspawn and again whenever a value changes, so tuning a
  cvar live in the console reaches the HUD on the next tick.
*/
float sv_mv_gravity, sv_mv_accelerate, sv_mv_airaccelerate;
float sv_mv_friction, sv_mv_stopspeed;	// sv_mv_maxspeed is in sv_defs.qc

void() SV_UpdateMovementServerInfo =
{
	local float g, a, aa, f, ss, ms;

	g  = cvar("sv_gravity");
	a  = cvar("sv_accelerate");
	aa = cvar("sv_airaccelerate");
	f  = cvar("sv_friction");
	ss = cvar("sv_stopspeed");
	ms = cvar("sv_maxspeed");

	if (g  != sv_mv_gravity)       { sv_mv_gravity = g;        forceinfokey(world, "sv_gravity",       ftos(g));  }
	if (a  != sv_mv_accelerate)    { sv_mv_accelerate = a;     forceinfokey(world, "sv_accelerate",    ftos(a));  }
	if (aa != sv_mv_airaccelerate) { sv_mv_airaccelerate = aa; forceinfokey(world, "sv_airaccelerate", ftos(aa)); }
	if (f  != sv_mv_friction)      { sv_mv_friction = f;       forceinfokey(world, "sv_friction",      ftos(f));  }
	if (ss != sv_mv_stopspeed)     { sv_mv_stopspeed = ss;     forceinfokey(world, "sv_stopspeed",     ftos(ss)); }
	if (ms != sv_mv_maxspeed)      { sv_mv_maxspeed = ms;      forceinfokey(world, "sv_maxspeed",      ftos(ms)); }

	// Patch 249.  Source's TICK_INTERVAL, for the basevelocity cash-out's
	// (1.0 + frametime * 0.5).  Refreshed here rather than read per player per
	// command.  pm_ticrate is already an INTERVAL in seconds despite the name
	// (sv_phys.c:95, "Fixed physics step ... in seconds") -- 0.015 for surf,
	// 0.01 for bhop -- so it is used as-is, not inverted.
	run_bv_tick = cvar("pm_ticrate");
	if (run_bv_tick <= 0)
		run_bv_tick = 0.015;

	run_bv_debug = cvar("run_bv_debug");
};

void() StartFrame =
{
	// Armed by worldspawn, so this is the first frame AFTER the entity lump
	// was built rather than the first frame of any kind -- StartFrame does get
	// called before the map's entities exist, and reporting there reads zero.
	if (vbsp_need_report)
	{
		vbsp_need_report = FALSE;
		// Patch 191: before the report, because the report prints its count.
		// This is also the earliest it CAN run -- the same "StartFrame is
		// called before the map's entities exist" trap the comment above
		// records -- and it is early enough, because nothing resolves a target
		// until a player touches something, which is strictly after this frame.
		SV_RepairTargetCase();

		// Build 37: after the case repair, because an output's target is
		// resolved against .targetname and the repair may have just changed
		// one; before the report, because the report prints the wiring count.
		// This is also the earliest it can run, for the same reason as above --
		// materialising outputs needs every entity on the map to exist.
		SV_EntityIOBuild();

		SV_EntityReport();
	}

	SV_UpdateMovementServerInfo();
	SV_ZoneFrame();
};

/*
  Map player fields onto client stats so the HUD can read exact, authoritative
  values.  These arrive one server tick old, which on a listen server is
  indistinguishable from live.

  BUILD 39 -- AND THE SENTENCE THAT USED TO BE HERE WAS FALSE, EXPENSIVELY.

  It read: "Movement is engine-side, so CSQC has no predicted state to read
  from".  The first half is true and the second does not follow.  FTE publishes
  the predicted player state to CSQC as the globals pmove_org and pmove_vel
  (pr_cmds.c:13350, written every frame in CSQC_ChangeLocalPlayer), and this
  tree had never declared either of them -- because of this comment, as far as
  anyone can tell.

  What it cost: the HUD built its feet from a predicted eye minus a server-side
  eye height and its speed from STAT_FS_VELOCITY below, which is three clocks
  for two quantities, and energy is z + |v|^2/2g so all of it landed in the
  readout.  See HUD_Feet in cl_hud.qc.

  THE STATS ARE STILL THE AUTHORITY for everything that is not the local
  player's own position and velocity.  run_groundnorm is traced by
  SV_PlayerPostThink and exists nowhere else; the board telemetry below is
  written by the engine into fields with no client-side equivalent; the timer
  and the save list are server state by definition.  Those genuinely do arrive
  a tick old and there is nothing better to read.
*/
void() SV_RegisterStats =
{
	clientstat(STAT_FS_VELOCITY,   EV_VECTOR, velocity);
	clientstat(STAT_FS_FLAGS,      EV_FLOAT,  flags);
	clientstat(STAT_FS_MOVETYPE,   EV_FLOAT,  movetype);
	clientstat(STAT_FS_GROUNDNORM, EV_VECTOR, run_groundnorm);

	// Written by the engine, not by us -- see Patch 131.  The fields are
	// declared in sv_player.qc purely so the engine's GetEdictFieldValue
	// lookup finds them; nothing in QC ever assigns to them.
	clientstat(STAT_FS_BOARDNORM,   EV_VECTOR, run_boardnormal);
	clientstat(STAT_FS_BOARDVEL,    EV_VECTOR, run_boardvelocity);
	clientstat(STAT_FS_BOARDCOUNT,  EV_FLOAT,  run_boardcount);
	clientstat(STAT_FS_RAMPCONTACT, EV_FLOAT,  run_rampcontact);
	clientstat(STAT_FS_RAMPNORM,    EV_VECTOR, run_rampnormal);
	clientstat(STAT_FS_PMFLAGS,     EV_FLOAT,  pmove_flags);

	/*
	  The timer and the save-lock list.

	  All eleven are plain player fields written by sv_timer.qc /
	  sv_saveloc.qc, so the HUD owns none of the state and cannot disagree
	  with the server about it.  STAT_FS_TIMERTICKS changes every frame while
	  a run is live, which is one float per snapshot -- the delta compressor
	  sends nothing at all for the other ten while they sit still.
	*/
	clientstat(STAT_FS_TIMERSTATE,  EV_FLOAT,  run_t_state);
	clientstat(STAT_FS_TIMERTICKS,  EV_FLOAT,  run_t_ticks);
	clientstat(STAT_FS_TIMERSEG,    EV_FLOAT,  run_t_seg);
	clientstat(STAT_FS_TIMERSEGS,   EV_FLOAT,  run_t_segs);
	clientstat(STAT_FS_TIMERTRACK,  EV_FLOAT,  run_t_track);
	clientstat(STAT_FS_TIMERFLAGS,  EV_FLOAT,  run_t_flags);
	clientstat(STAT_FS_TIMERSPLIT,  EV_FLOAT,  run_t_split);
	clientstat(STAT_FS_TIMERDELTA,  EV_FLOAT,  run_t_delta);
	clientstat(STAT_FS_TIMERPB,     EV_FLOAT,  run_t_pb);

	/*
	  BUILD 19 -- checkpoints, the same triple again.

	  Free at rest for the same reason the stage triple is: all three sit still
	  between gates, so the delta compressor sends nothing for them across the
	  whole of a segment.  run_t_cpn is an ordinal rather than a crossing count so
	  it can index a personal best; it is strictly increasing within a run, which
	  is what lets the client edge-detect it directly.
	*/
	clientstat(STAT_FS_TIMERCP,     EV_FLOAT,  run_t_cpn);
	clientstat(STAT_FS_TIMERCPT,    EV_FLOAT,  run_t_cpticks);
	clientstat(STAT_FS_TIMERCPD,    EV_FLOAT,  run_t_cpdelta);

	clientstat(STAT_FS_SAVECOUNT,   EV_FLOAT,  rec_sl_count);
	clientstat(STAT_FS_SAVEINDEX,   EV_FLOAT,  rec_sl_index);

	/*
	  Build 17.  rec_sl_count is now a MIRROR of a global list rather than the
	  list itself -- the saves live on disk under the map, so they belong to the
	  map and not to whoever is standing on it.  clientstat takes a field, so
	  SV_SaveLocSync copies the count across once a tick; see the note there.

	  The other three are the save-state handshake.  SLSEQ and SLOP tell the
	  CLIENT's half of the recorder that a save happened and which slot, which it
	  cannot see any other way -- a save is a client command handled on the
	  server and nothing comes back but stats.  SAVETICKS is the cursor slot's
	  stored run clock, so the menu can say which save is the one at 1:04.
	*/
	clientstat(STAT_FS_SLSEQ,       EV_FLOAT,  rec_sl_slseq);
	clientstat(STAT_FS_SLOP,        EV_FLOAT,  rec_sl_slop);
	clientstat(STAT_FS_SAVETICKS,   EV_FLOAT,  rec_sl_savetick);

	/*
	  Build 30.  The parked velocity, so the HUD can print what the save is
	  holding instead of the zero the freeze writes into .velocity.  The essay
	  is beside STAT_FS_HOLD in sh_defs.qc.

	  Free at rest, both of them: rec_sl_hold is 0 and rec_sl_holdvel is '0 0 0'
	  for every tick nobody is parked, so the delta compressor sends nothing for
	  either outside a hold.
	*/
	clientstat(STAT_FS_HOLD,        EV_FLOAT,  rec_sl_hold);
	clientstat(STAT_FS_HOLDVEL,     EV_VECTOR, rec_sl_holdvel);

	/*
	  Build 30.  Ghost, and the client takes this as the authority rather than
	  latching its own answer when `ghost` is typed -- so the camera cannot be
	  detached on a frame where this server still thinks the body's zone
	  crossings count.  Free at rest like everything else here.
	*/
	clientstat(STAT_FS_GHOST,       EV_FLOAT,  rec_gh_on);

	// Which run, so the client's per-frame angle sidecar lands beside the
	// server's .rec under the same name.  Both sit still for whole runs at a
	// time, so the delta compressor sends nothing for either while one is going.
	clientstat(STAT_FS_RUNLEG,      EV_FLOAT,  rec_rec_leg);
	clientstat(STAT_FS_RUNTAG,      EV_FLOAT,  rec_rec_tag);
	clientstat(STAT_FS_RUNTICKS,    EV_FLOAT,  rec_rec_ticks);

	/*
	  BUILD 24: a stage lifted out of a main run, and the four values the client
	  needs to write the matching .view slice for it.

	  All four change in ONE tick, inside SV_StageClose, and the client keys off
	  STAGEREC alone -- see the essay in sh_defs.qc.  Three of them sit still for
	  a whole stage at a time and the fourth is a counter, so the delta compressor
	  sends nothing at all for any of them for most of a run.
	*/
	clientstat(STAT_FS_STAGEREC,    EV_FLOAT,  run_st_rec);
	clientstat(STAT_FS_STAGESEG,    EV_FLOAT,  run_st_recseg);
	clientstat(STAT_FS_STAGETICKS,  EV_FLOAT,  run_st_recticks);
	clientstat(STAT_FS_STAGEAT,     EV_FLOAT,  run_st_recat);

	/*
	  BUILD 43: the stage IN PROGRESS, where the four above are the stage that is
	  already over.  See the STAT_FS_STAGE* block in sh_defs.qc for why a stage
	  you can arm, start and fail needs to say so within a second.

	  FAILS is a counter and the client edge-detects it; ST is a packed SF_* word
	  recomputed once per tick by SV_StageStat; BASE is the run clock this stage
	  is being timed from, which the arm rule MOVES after the boundary.  All three
	  sit still for a whole stage at a time, so the delta compressor sends nothing
	  for any of them for most of a run.
	*/
	clientstat(STAT_FS_STAGEFAILS,  EV_FLOAT,  run_st_fails);
	clientstat(STAT_FS_STAGEST,     EV_FLOAT,  run_st_word);
	clientstat(STAT_FS_STAGEBASE,   EV_FLOAT,  run_st_tick);

	/*
	  The player's fog controller, by targetname.  The only EV_STRING stat in the
	  game: it carries a NAME rather than an index so the two sides never have to
	  agree on a numbering, and it is a stat rather than serverinfo because
	  Source's SetFogController is fired at !activator and is therefore
	  per-player.  Written by SV_ApplyInput (sv_entities.qc), read by Fog_Frame
	  (cl_fog.qc).  Empty for the whole run on the 1283 maps that never switch,
	  so the delta compressor sends it once and then never again.
	*/
	clientstat(STAT_FS_FOGCTRL,     EV_STRING, run_fogctrl);
};

void() worldspawn =
{
	// worldspawn is the first entity in the lump, so this zeroes the spawn
	// tallies before anything counts into them -- and re-arms the report.
	// Both matter across a map change: these are globals and they persist.
	SV_EntityReset();

	/*
	  BUILD 34 -- why every prop in the game had a bounding box of nothing.

	  FTESurf compiles to qwprogs.dat, whose progdefs CRC is 54730 -- which the
	  engine reads as PROG_QW (pr_cmds.c:702, :713).  PF_setmodel transfers a
	  model's bounds onto the entity only when
	      progstype != PROG_QW || sv_gameplayfix_setmodelsize_qw
	  (pr_cmds.c:3156), and that cvar defaults to 0.  Nothing was setting it.  So
	  `setmodel(prop, "models/....mdl")` in SV_SpawnProp left .mins and .maxs at
	  '0 0 0' for every prop on every map, and three things followed:

	    - the engine's pmove bails on exactly that -- `if (!check->v->size[0])
	      return true;` (sv_user.c:7049) -- so no prop was ever a physent, and
	      Patch 229's collision fix is INERT without these two lines;
	    - World_LinkEdict boxes non-BSP solids by .mins/.maxs (world.c:534-535), so
	      absmin == absmax == origin and each prop sat in the area grid as a POINT;
	    - SV_SpawnProp's own setsize(self, self.mins*sc, self.maxs*sc) was
	      multiplying zero by the scale.

	  Both cvars are needed, and realbox has to be 1 before the FIRST
	  precache_model -- otherwise sv.models[i] is never filled for a .mdl
	  (pr_cmds.c:4622) and setmodelsize_qw alone falls through to a hardcoded
	  +/-16 fallback cube.  Hence above the precache below, not further down with
	  the other cvar_sets.  worldspawn is the first entity in the lump, so this
	  precedes every prop either way.

	  Safe for everything else: every other setmodel in this game binds a '*N'
	  brush model, which takes the early return at pr_cmds.c:3111 and is
	  unaffected, and the player setmodel("")s then setsize()s itself explicitly
	  (PutClientInServer, sv_player.qc).

	  IT WAS NOT SAFE FOR THE PLAYER, from Build 34 to Build 41, because that
	  last clause was not true: the setsize came FIRST and the setmodel("")
	  landed on top of it.  An empty model string does not load, so it took the
	  +/-16 fallback named three paragraphs up and left the player hull at
	  mins.z -16 -- the eye 16 units above the floor it should have been level
	  with.  See the comment on the setmodel in PutClientInServer, which now
	  runs first and says why it has to.  If a player model is ever added,
	  the setsize MUST still come last.

	  COST, and it is real: precache_model now loads every prop model
	  synchronously on the server thread at map load.  vbsp_prop_nobox_n on the
	  `props:` line is the readout that says whether this actually took.
	*/
	cvar_set("sv_gameplayfix_setmodelrealbox", "1");
	cvar_set("sv_gameplayfix_setmodelsize_qw", "1");

	// The engine needs modelindex 1 to exist; every map supplies it.
	precache_model("");

	lightstyle(0, "m");

	SV_RegisterStats();

	// Deathmatch-ish rules so the engine doesn't try to run single-player
	// intermission/level-progression logic on a surf map.
	cvar_set("deathmatch", "1");
	cvar_set("teamplay", "0");

	SV_UpdateMovementServerInfo();

	/*
	  The tick recorder.  On by default -- a run you did not record is a run
	  you cannot play back, and the cost is a text append per tick into an
	  engine-side buffer that only touches the disk when the run ends.

	  Set 0 if you want the timer without the ~1.5 MB per five minutes.
	*/
	registercvar("rec_enable", "1");

	// See SV_ZoneHit.  0 is the build-9 point test and exists to A/B against.
	registercvar("run_zone_swept", "1");

	/*
	  The start may not be hopped.  Build 19.

	  1 marks a run practice if you leave the start by bunny-hopping rather than
	  by one pre-strafe jump or by walking out; see SV_TimerJumpWatch, which also
	  explains why the test is a ground DWELL and not a jump count.  0 restores
	  the previous build exactly, and is what a bhop or KZ map wants -- hopping is
	  the whole game there.

	  The threshold is run_prestrafe_time, deliberately shared with the client's
	  +forward release so the rule and the assist cannot disagree; the server
	  publishes it to serverinfo in SV_TimerMapInit.
	*/
	registercvar("run_starthop", "1");

	/*
	  ...and the two lines that make the rule above actually fire.  Build 20.

	  run_starthop 1 has been the default since build 19 and did nothing, because
	  SV_TimerArm reset the flag that gates the rule but not the air-phase clock
	  the rule settles on -- so every arm that followed a fall closed the window
	  on the tick after it opened.  This switch covers the two-line repair
	  (SV_TimerArm clears run_t_airat; the settle needs TS_RUNNING) plus the stage
	  handover exemption those two make necessary.

	  0 is build 19 byte-for-byte, which makes this a real bisection rather than
	  a claim -- and build 19's behaviour is "the rule never fires", so 0 is also
	  the setting for anyone who wants hopped starts allowed without turning the
	  reporting off.

	  REGISTERED IN SV_TimerMapInit, NOT HERE, and so is run_rearmstops below --
	  see the essay there.  Both are read by that function, which StartFrame
	  reaches BEFORE worldspawn runs, so a registration here would arrive after
	  the read had already auto-created them empty.  Named here anyway because
	  this is where someone looks for a server cvar.
	*/

	/*
	  Arriving back in a start zone mid-run keeps the time on screen, in grey.

	  Build 19 stopped the clock for `!r` and for cancel zones -- everything that
	  goes through SV_TimerVoid.  Walking back into the box, or being put there by
	  a map trigger_teleport, does not: it reaches the arm through SV_TimerTryArm,
	  where there was nothing latching the time.  0 restores the snap-to-zero.

	  Registered in SV_TimerMapInit for the reason given above.
	*/

	/*
	  A fluffed start can be taken back by stopping.  Build 21.

	  Hop out of the box and the attempt is marked practice, and until now the
	  only way back was to physically re-enter the start zone -- SV_TimerArm is
	  the one place the taint is cleared.  With this on, standing on the ground
	  for run_prestrafe_time forgives it while you are still ARMED, so the next
	  jump is judged as a fresh initial jump.  It is the same dwell that decides
	  whether the client releases +forward, so the rule stays one number.

	  Inside the start zone only.  Out on the platform the clock is already
	  running, so forgiveness would have to restart it from wherever you stopped
	  -- a route skip -- and 0.25 s of friction leaves far too much of a bhop's
	  speed intact to call the start clean.  See the run_rearmhop essay in
	  sv_timer.qc for the arithmetic.

	  Registered in SV_TimerMapInit for the reason given above.
	*/

	/*
	  A map teleport is a "I was put here", and the timer was never told.

	  trigger_teleport_touch has never called SV_TimerWarped, so run_t_lastorg
	  stayed where you were and the next tick's SWEPT zone test ran a segment
	  across the whole map -- firing every stage and end zone on the line between
	  the two ends.  That can silently FINISH a run, which is worse than the
	  reported symptom.  Read live rather than cached: it fires per touch, not
	  per tick.  0 is the old behaviour, for bisecting a map that depended on it.
	*/
	registercvar("run_teleport_warp", "1");

	/*
	  `retry` restores your position and your run across the map restart.
	  0 gives you Patch 167's behaviour -- restart and respawn at the start --
	  which is the previous build exactly, so this stays a one-command A/B.
	*/
	registercvar("rec_retry", "1");

	/*
	  Patch 256.  trigger_setspeed -- 372 volumes across 94 maps that have
	  spawned inert since the beginning, without even a warning, because the
	  trigger_ prefix arm of SV_OnEntityNoSpawnFunction returns before the
	  unknown-classname dprint.

	  It WRITES VELOCITY, so 0 is worth having: a wrong mode decode on those 94
	  maps is a dead stop or a launch, and 0 puts them back to inert without a
	  rebuild.  It also changes what a recorded run means -- surf_bossfight's
	  start pads are 5000 u/s -- so a leaderboard comparison across this build
	  needs to know which side of it a run was set on.
	*/
	registercvar("run_setspeed", "1");

	/*
	  The arm SV_RetryPoint sets and SV_TimerMapInit latches.  Registered so it
	  reads 0 rather than empty in a fresh session, which is what makes a
	  save00 orphaned by a crash harmless.  NOT archived: it must not survive
	  the process.  See SV_TimerMapInit.
	*/
	registercvar("rec_retry_armed", "0");

	dprint("FTESurf: worldspawn\n");
};
