/*
===========================================================================
  sv_saveloc.qc -- save states.

  A save state is a position you can come back to, plus the RUN that was in
  progress when you dropped it.  Momentum calls the position half a saveloc;
  every surf community calls it save/load.  Build 17 added the other half.

  WHAT A SAVE HOLDS, AND WHY THAT IS THE INTERESTING PART

  Until build 17 a save was five floats: origin, velocity, pitch, yaw, duck.
  Loading one teleported you and marked the run practice, and that was all --
  the clock, the splits and the checkpoints stayed at whatever they happened to
  be.  So practising the entry to stage 4 of a good run meant losing the run
  every time you failed it, which is the thing you were practising FOR.

  Now a save holds the attempt.  Load it and the clock reads what it read when
  you saved, the splits behind you are the ones you actually set, the checkpoint
  you last crossed is still crossed, and the recording carries the movement up
  to that point -- so the run you eventually finish is one continuous file from
  the start zone, not a fragment beginning halfway up a ramp.

  It is practice, always: you did not earn the position.  It is also marked
  TF_SHADOW, which is strictly narrower -- and since build 44 TF_SEGMENT, which
  is what the leaderboard calls it.

  TF_SHADOW is USUALLY what the recording is named after, and build 45 made that
  a "usually": if the same attempt also cheated, TF_CHEAT outranks it and the
  file is written as `cheat.rec` instead.  Not a tie-break for neatness -- a
  shadow name is ARCHIVED and would accumulate a stamped junk file per lap, and
  a cheat name is one scratch slot.  See RT_SHADOW and RT_CHEAT.

  WHY THE LIST IS SERVER-SIDE

  Two of the things a save restores are not CSQC's to give back.  The origin has
  to be set authoritatively or prediction fights it, and the DUCK STATE lives
  inside the engine's pmove -- pmove.ducked is carried across commands in
  host_client->pmsrc (sv_user.c:7815) and QC cannot see it, let alone write it.
  Engine Patch 142 adds one optional field, run_forceduck, purely so this file can
  hand it back.

  Restoring the duck matters more than it sounds.  Save while crouched under a
  lip, load standing, and the 62-unit hull spawns inside the ceiling: you arrive
  stuck, in the exact spot you were trying to practise.  (17 units of it, the
  difference between PM_HULL_MAXS and PM_DUCK_MAXS.)

  WHY THE LIST IS GLOBAL, AND THE CURSOR IS NOT

  The saves live on disk now, under the MAP, so they are a property of the map
  and not of whoever is standing on it.  Keeping a per-player copy of a shared
  thing would mean two players could disagree about a file they can both see.
  So the rows are global and only the cursor -- the "3/7", which is a question
  about what YOUR next keypress does -- is per player.
===========================================================================
*/

/*
  ON DISK.

      data/saves/<mapname>/save07/state.txt     the state, one key per line
                                  run.rec       movement up to the save point
                                  run.view      camera + keys, written by CSQC

  `data/` is not a choice: QC's write sandbox allows exactly `data/` and `cfg/`
  (pr_bgcmd.c QC_FixFileName), and everything else is rewritten or refused.
  Nothing has to create the directories -- fclose goes through COM_WriteFile,
  which calls FS_CreatePath first.

  THE FOLDER NUMBER IS NOT THE LIST POSITION.

  Deleting a save slides the list down (see SV_SaveLocDelete), so if position
  were the folder name then every delete would have to rename every folder after
  it -- three files each, across a directory, with no way to make it atomic and
  no way to recover half of it.  So the folder id is STABLE, allocated
  lowest-free at create and never touched again, and the ORDER comes from a
  `seq` counter inside the file.  Nothing is ever renamed, a deleted id is free
  for reuse, and "the newest save is the last one" still holds -- which the menu
  depends on, because `1` then `2` with the menu closed means "save here, put me
  back here".
*/
#define SL_STATE_VERSION 1

// search_begin flags.  QCSEARCH_NAMESORT, pr_bgcmd.c:3506.
#define SL_NAMESORT 32

/*
  The list.  Only what the HUD, the menu and the per-tick hold actually need --
  everything else is read out of state.txt at the moment of a load, which is a
  few hundred bytes once per keypress rather than 32 rows of run state resident
  for the whole map.
*/
vector rec_sl_org  [FS_MAXSAVES];
vector rec_sl_vel  [FS_MAXSAVES];
float  rec_sl_pit  [FS_MAXSAVES];
float  rec_sl_yaw  [FS_MAXSAVES];
float  rec_sl_duck [FS_MAXSAVES];
float  rec_sl_id   [FS_MAXSAVES];        // folder number, 1..FS_MAXSAVES, stable
float  rec_sl_seq  [FS_MAXSAVES];        // creation order; the sort key
float  rec_sl_tick [FS_MAXSAVES];        // the run clock stored in the slot
float  rec_sl_seg  [FS_MAXSAVES];        // segment, for the console list
float  rec_sl_cps  [FS_MAXSAVES];        // checkpoints crossed, for the same

float  rec_sl_n;                         // rows in use
float  rec_sl_nextseq;                   // one past the highest seq on this map

// Build 25.  A delete-all drives SV_SaveLocDelete once per row and must not
// print its per-row summary each time.  Bare (Q106), and set/cleared around the
// loop in SV_SaveLocDeleteAll rather than passed down, so the eight other
// callers of that function need no change.
float  rec_sl_quiet;

// Patch 270, Stage 2.  TRUE once SV_SaveLocScan has actually read the disk for
// this map.  FALSE means the list is empty because the scan was refused in a
// lobby, NOT because there is nothing on disk -- a distinction SV_SaveFreeID
// would otherwise get wrong, by handing out an id whose folder already exists.
float  rec_sl_scanned;

.float rec_sl_count;             // networked mirror of rec_sl_n; see SV_SaveLocSync
.float rec_sl_index;             // 1-based cursor; 0 when the list is empty

// The save/load event stream, for the client's half of the recording.  See
// STAT_FS_SLSEQ in shared/sh_defs.qc.
.float rec_sl_slseq;
.float rec_sl_slop;
.float rec_sl_savetick;          // the cursor slot's stored run clock

/*
  HOLD.

  While the load key is held down the player is parked at the save and starts
  moving the instant it is released.  That is a different tool from a one-shot
  load: it lets you sit at the top of a ramp and study the approach, or line an
  angle up without the fall, and then begin the section when you choose.

  IT FREEZES THE PLAYER; IT DOES NOT RE-PLACE THEM EVERY TICK.

  The first version did re-place them every tick, and that was wrong in a way
  worth writing down, because it looked like a plausible design.  The player
  stayed MOVETYPE_WALK, so the CLIENT went on predicting: it ran the move
  forwards from the last snapshot, drew you a few units along, then the next
  snapshot put you back at the save.  Sixty-six times a second.  That is the
  "glitching and flickering" -- not a bug in the pin, the pin working exactly
  as written against a prediction that was never told to stop.

  MOVETYPE_NONE is how you tell it to stop.  SV_PMTypeForClient maps it to
  PM_NONE (sv_user.c:7398-7399), whose whole purpose is that -- the engine's own
  comment at :7377 calls it "let the client know that its prediction is fucked.
  should make it just lerp."  The same value reaches the client's copy of pmove,
  so both sides agree that this player does not move and neither one has to win.

  And the objection the old comment raised against it is simply not true of the
  Source pmove.  PM_NONE zeroes the move inputs, runs CategorizePosition and
  returns (pm_source.c:1701-1705) -- it never reaches PMSrc_Duck, so
  pmove.ducked is untouched and PMSrc_ApplyHull keeps rebuilding the hull the
  save asked for.  Angles are applied outside pmove, so you can still look
  around while parked, which is most of the point.

  Velocity is zeroed while frozen and the SAVE'S velocity is handed back on
  release, so letting go is exactly a load: same origin, same speed, same hull.

  rec_sl_holdrow is the LIST ROW.  It used to be an absolute array index, which
  meant the same thing when the arrays were per player; now that the list is
  global it is simply the row, and it is still re-pointed rather than trusted --
  deleting an earlier save while holding would otherwise slide the list out from
  under the hold.
*/
.float rec_sl_hold;
.float rec_sl_holdrow;
.float rec_sl_holdmove;          // the movetype to give back on release

/*
  Build 30.  The velocity the hold is parked on, published as STAT_FS_HOLDVEL.

  It is the same number the release hands back three lines lower down -- this
  field exists only so the CLIENT can see it too, because .velocity is zero for
  the whole hold and the HUD had no other way to know what it was.  Kept in step
  with rec_sl_holdrow rather than written once: the hold can be re-pointed at
  another row (hold 2, tap 4/5) without ever passing through a release.

  '0 0 0' whenever rec_sl_hold is clear, so the stat costs nothing at rest and a
  stale value can never be read back out of it.
*/
.vector rec_sl_holdvel;

/*
  Engine Patch 142.  Written by QC, consumed and cleared by the engine: it is
  found by name with GetEdictFieldValue just before PMSrc_LoadState, applied
  to pmove's carried duck state, and zeroed.  A mod that does not declare it
  (quakers, sharing this engine tree) gets NULL back and the patch does
  nothing at all -- the same idiom as the run_board* telemetry.

  0 = no change, 1 = stand up, 2 = crouch.  Zero is the no-op because a QC
  field is zero on a fresh edict, so nothing has to remember to initialise it.
*/
#define FD_NONE   0
#define FD_STAND  1
#define FD_DUCK   2

.float run_forceduck;

// Defined below, next to the hold it undoes; forward-declared because a reset
// and a respawn both have to be able to let go of one.
void(entity e) SV_SaveLocRelease;

// Build 24, and forward-declared for the same reason: a map reset has to let go
// of a watch too, and it happens three hundred lines above the definition.
void(entity e) SV_WatchRelease;

/*
===========================================================================
  Paths
===========================================================================
*/
/*
  BUILD 25: THE NAME MOVED TO shared/sh_defs.qc, and this is a forwarder.

  It was two digits and local, and build 25 widened the id space to 999.  The
  same string is needed by the client's Rec_SavePath and Seq_Path -- a save's
  four files are joined by nothing but the directory they land in -- so the rule
  is now FS_SaveSlotName, in the file all three VMs compile, and the essay giving
  the reason is there beside it.  Left as a forwarder rather than replaced at the
  eight call sites below, which is the shape SV_TrackSegs and Watch_IsSample
  already have for the same reason.
*/
string(float id) SL_NN = { return FS_SaveSlotName(id); };

string(float id) SL_Dir      = { return sprintf("data/saves/%s/save%s/", mapname, SL_NN(id)); };
string(float id) SL_StatePath= { return strcat(SL_Dir(id), "state.txt"); };
string(float id) SL_RecPath  = { return strcat(SL_Dir(id), "run.rec"); };
string(float id) SL_ViewPath = { return strcat(SL_Dir(id), "run.view"); };
// Build 20.  Written by the CLIENT, like run.view -- the segment column is
// client-side state and the server has never seen it.  Named here only so the
// delete below can remove it; see SV_SaveLocDelete for why that matters.
string(float id) SL_SeqPath  = { return strcat(SL_Dir(id), "seq.txt"); };

/*
===========================================================================
  Writing a save
===========================================================================
*/
/*
  The state file.

  Plain text, one key per line, ANY ORDER, and an unknown key MUST be skipped
  rather than rejected -- the same grammar the .rec header uses and for the same
  reason: it is what lets a later build add a key without breaking a reader that
  was written before it existed.  A format you can read with `type` is the one
  that survives being written before its reader.
*/
void(entity e, float id, float seq) SV_SaveWriteState =
{
	local filestream f;
	local float i, mark;
	local string p;

	p = SL_StatePath(id);
	f = fopen(p, FILE_WRITE);
	if (f < 0)
	{
		sprint(e, PRINT_HIGH, sprintf("^1save: cannot write %s\n", p));
		return;
	}

	/*
	  The recording's prefix goes out FIRST, so that `reclines` below describes a
	  file that already exists.  If the write fails we record a mark of 0, which
	  a load reads as "this save has no movement behind it" -- degraded, not
	  wrong, and exactly what a save taken before the clock started looks like
	  anyway.
	*/
	mark = SV_RecWritePrefix(e, SL_RecPath(id));

	fputs(f, sprintf("FTESURF-SAVE %g\n", SL_STATE_VERSION));
	fputs(f, sprintf("map %s\n", mapname));
	fputs(f, sprintf("seq %g\n", seq));
	fputs(f, sprintf("created %s\n", strftime(TRUE, "%Y%m%d-%H%M%S")));

	// Position.  Written at full precision rather than the %.1f the console
	// `setpos` line uses: this is a state file and not something to read.
	fputs(f, sprintf("origin %.4f %.4f %.4f\n",
	                 e.origin_x, e.origin_y, e.origin_z));
	fputs(f, sprintf("velocity %.4f %.4f %.4f\n",
	                 e.velocity_x, e.velocity_y, e.velocity_z));
	fputs(f, sprintf("angles %.4f %.4f\n", e.v_angle_x, e.v_angle_y));
	fputs(f, sprintf("duck %g\n", (e.pmove_flags & PMF_DUCKED) ? 1 : 0));

	// The timer.
	fputs(f, sprintf("state %g\n", e.run_t_state));
	fputs(f, sprintf("track %g\n", e.run_t_track));
	fputs(f, sprintf("startseg %g\n", e.run_t_startseg));
	fputs(f, sprintf("seg %g\n", e.run_t_seg));
	fputs(f, sprintf("segs %g\n", e.run_t_segs));
	/*
	  ZERO WHEN THERE IS NO RUN, and this was a real bug rather than a nicety.

	  SV_TimerTicks is floor((time - run_t_start) / tick + 0.5) and run_t_start is
	  0 until a run starts -- so on an idle timer it returns the number of ticks
	  since the MAP loaded, and the save list cheerfully printed that as the run
	  time.  Three saves taken while idle read 0:09.330, 0:16.170 and 0:18.780,
	  which look exactly like three points along a run and are the wall clock.

	  Caught by the verification pass, which is the only place it could have
	  been: every number was plausible and they even increased in the right
	  order.

	  A FINISHED timer needs the other of the two, for the mirror-image reason:
	  SV_TimerTicks keeps counting after the finish, so the live figure would
	  grow while you stood in the end zone.  run_t_ticks is the one that stopped.
	*/
	if (e.run_t_state == TS_RUNNING)
		fputs(f, sprintf("ticks %g\n", SV_TimerTicks(e)));
	else if (e.run_t_state == TS_FINISHED)
		fputs(f, sprintf("ticks %g\n", e.run_t_ticks));
	else
		fputs(f, "ticks 0\n");
	/*
	  The same clock unrounded, and the one a load actually restores from.

	  `ticks` above is what the timer REPORTS -- the rounded integer a
	  leaderboard compares -- and restoring from it would put the clock up to
	  half a tick behind where the save was taken, which makes the first sample
	  after a resume older than the last sample already in the recording.  Time
	  running backwards mid-file is not something a reader can interpolate
	  through, and tools/reccheck.py refuses it.

	  Both are written because they answer different questions and the file is
	  read by more than one thing: the list shows `ticks`, the load uses this.
	*/
	fputs(f, sprintf("elapsed %.6f\n",
	                 (e.run_t_state == TS_RUNNING) ? SV_TimerElapsed(e) : 0));
	fputs(f, sprintf("split %g\n", e.run_t_split));
	fputs(f, sprintf("delta %g\n", e.run_t_delta));

	// TF_FROZEN and TF_STOPPED are masked out for the same reason TF_RECORDING
	// is on the way back in (see SV_SaveApplyState): each states something that
	// is true RIGHT NOW -- a hold, and a cancelled run still on screen -- and no
	// file can assert one.  Save while parked and the flag would otherwise
	// travel to whoever loads that state later.
	fputs(f, sprintf("flags %g\n",
	                 e.run_t_flags - (e.run_t_flags & (TF_FROZEN | TF_STOPPED))));
	fputs(f, sprintf("pb %g\n", e.run_t_pb));
	fputs(f, sprintf("dirty %g\n", e.run_t_dirty));
	/*
	  BUILD 44: the class latch, beside the umbrella it belongs to.

	  Only `retry` reads it back -- a load is a stitch and re-derives its own
	  class -- but a retry of a run that had been noclipped before the clock
	  started must come back cheated, and TF_CHEAT in `flags` above cannot say so:
	  the whole reason run_t_cheat exists is that the flags word is zeroed by the
	  arm and the latch is what crosses it.  A retry restores an attempt that may
	  not have started yet.

	  A NEW KEY IS BACKWARD-COMPATIBLE IN BOTH DIRECTIONS.  The reader is a
	  key-match loop with defaults, so an older save simply reads 0 here, and an
	  older build reading a newer save skips a key it does not know.  No version
	  and no format bump -- the same property the `fromsave` key relied on.
	*/
	fputs(f, sprintf("cheat %g\n", e.run_t_cheat));
	// Which save this attempt was already resumed from, if any.  Only `retry`
	// reads it back -- a load overwrites it with its own slot -- but without it
	// a retry of a shadow run restores TF_SHADOW from `flags` and then reports
	// "shadow run from save 0" at the finish.
	fputs(f, sprintf("fromsave %g\n", e.run_t_fromsave));

	/*
	  The occupancy latches, VERBATIM.

	  These are "which zones am I already standing in, and which have already
	  fired".  A save taken inside a stage box has to restore them or the very
	  next tick sees the box as newly entered and fires the split again -- which
	  is the difference between "exactly like it was" and "nearly".
	*/
	fputs(f, sprintf("azone %g\n", e.run_t_azone));
	fputs(f, sprintf("evzone %g\n", e.run_t_evzone));
	fputs(f, sprintf("armzone %g\n", e.run_t_armzone));
	fputs(f, sprintf("cpzone %g\n", e.run_t_cpzone));
	fputs(f, sprintf("pendarm %g\n", e.run_t_pendarm));
	/*
	  BUILD 19: the checkpoint high-water mark, which is a latch in exactly the
	  same sense as the four above it.  Without it, resuming a save taken past
	  checkpoint 2 lets you collect 1 and 2 again on the way back through --
	  their times would overwrite the run's, and on a PB the .pb file would
	  record gates reached the second time round.
	*/
	fputs(f, sprintf("cpmax %g\n", e.run_t_cpmax));

	// The splits actually set this run, one line each.  Zeroes are skipped:
	// a segment with no split is not the same as a segment completed in 0.
	for (i = 1; i < FS_MAXSPLITS; i = i + 1)
		if (SV_TimerGetRunSplit(e, i) > 0)
			fputs(f, sprintf("runsplit %g %g\n", i, SV_TimerGetRunSplit(e, i)));

	/*
	  BUILD 23: and the checkpoint times, which this file has never carried.

	  cpmax above restores WHICH checkpoints have been passed; this restores WHEN.
	  Without it a retried run reaches the finish with an all-zero checkpoint row,
	  and if that run is a personal best SV_TimerFinish copies the zeroes into
	  run_pb_cp and SV_PBSave then writes a .pb with no cp lines at all -- the
	  map's checkpoint records deleted by the act of beating your own time.  See
	  SV_TimerGetRunCP in sv_timer.qc.

	  Zeroes skipped for the same reason as the splits: a checkpoint not yet
	  reached is not a checkpoint reached at tick 0.
	*/
	for (i = 1; i < FS_MAXCPS; i = i + 1)
		if (SV_TimerGetRunCP(e, i) > 0)
			fputs(f, sprintf("runcp %g %g\n", i, SV_TimerGetRunCP(e, i)));

	// The recorder.
	fputs(f, sprintf("reclines %g\n", mark));
	fputs(f, sprintf("recsamples %g\n", e.rec_rec_n));
	fputs(f, sprintf("recpad %g\n", e.rec_rec_padn));
	fputs(f, sprintf("reccp %g\n", e.rec_rec_cp));
	fputs(f, sprintf("recserial %g\n", e.rec_rec_serial));

	fclose(f);
};

/*
===========================================================================
  Reading a save
===========================================================================
*/
/*
  The light row -- what the list, the HUD and the per-tick hold need.

  Read for every slot at map load, which is why it is separated from the full
  restore below: thirty-two of these is thirty-two small files, and none of them
  needs the run state until somebody actually presses load.

  Returns the seq, or -1 if the file is not a save state we understand.
*/
float(float id, float row) SV_SaveReadLight =
{
	local filestream f;
	local string k;
	local float n, seq;
	local vector v;

	f = fopen(SL_StatePath(id), FILE_READ);
	if (f < 0)
		return -1;

	seq = -1;

	rec_sl_org [row] = '0 0 0';
	rec_sl_vel [row] = '0 0 0';
	rec_sl_pit [row] = 0;
	rec_sl_yaw [row] = 0;
	rec_sl_duck[row] = 0;
	rec_sl_id  [row] = id;
	rec_sl_tick[row] = 0;
	rec_sl_seg [row] = 0;
	rec_sl_cps [row] = 0;

	while ((k = fgets(f)) != "")
	{
		n = tokenize(k);
		if (n < 2)
			continue;
		k = argv(0);

		// The two VECTORS below need a real local on the way into the array --
		// an array element is not an lvalue fteqcc will swizzle, which is the
		// same thing SV_ZoneMove needs zone_centre for.  The floats are fine
		// assigned straight in.
		if (k == "seq")      { seq = stof(argv(1)); continue; }
		if (k == "ticks")    { rec_sl_tick[row] = stof(argv(1)); continue; }
		if (k == "seg")      { rec_sl_seg [row] = stof(argv(1)); continue; }
		if (k == "reccp")    { rec_sl_cps [row] = stof(argv(1)); continue; }
		if (k == "duck")     { rec_sl_duck[row] = stof(argv(1)); continue; }

		if (k == "origin")
		{
			if (n >= 4)
			{
				v = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
				rec_sl_org[row] = v;
			}
			continue;
		}
		if (k == "velocity")
		{
			if (n >= 4)
			{
				v = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
				rec_sl_vel[row] = v;
			}
			continue;
		}
		if (k == "angles")
		{
			if (n >= 3)
			{
				rec_sl_pit[row] = stof(argv(1));
				rec_sl_yaw[row] = stof(argv(2));
			}
			continue;
		}
		// anything else: skipped, by the grammar's own rule
	}
	fclose(f);

	/*
	  A file with no `seq` is not one of ours -- or is one of ours that was
	  half-written when something went wrong, which amounts to the same thing.
	  Refusing it here is what keeps a torn file out of the list rather than in
	  it at position zero.
	*/
	return seq;
};

/*
  The full restore.  Everything the light read skipped, applied straight to the
  player.  Returns TRUE if the file was readable.

  ORDER MATTERS ONCE, at the end: the recorder is rewound AFTER the timer is
  restored, because the `resume` record it writes carries the restored tick.

  `retry` SWITCHES TWO BEHAVIOURS, and the difference is exactly what the marking
  means:

    * A LOAD gives you a position you did not travel to, so the attempt is
      practice from then on, and a running one is a shadow run.  That is right,
      and it is why loading a save cannot set a PB.

    * A RETRY does not move you at all -- the MAP was reset around you.  So the
      attempt is restored verbatim, flags and all, including whether it was
      already practice.  Forcing practice here would make `retry` useless for a
      real run, which is the entire point of the feature.

  A retry also has to PLACE the player, which a load does not: SV_SaveLocPlace
  does that from the in-memory rec_sl_* arrays, and the retry point is slot 0 --
  deliberately outside the list, so it has no row.  Hence the four position keys
  below, which the loader has always skipped.
*/
float(entity e, float id, float retry) SV_SaveApplyState =
{
	local filestream f;
	local string k;
	local float n;
	local float ticks, elapsed, haveelapsed, mark, samples, padn, cps, serial;
	local float st, tr, ss, sg, sgs, spl, dlt, flg, pbv, dty, rfrom;
	local float cht;                // build 44, the cheat latch
	local float az, ez, am, cz, pa, cmx;
	local float rpit, ryaw, rduck;
	local vector rorg, rvel;

	f = fopen(SL_StatePath(id), FILE_READ);
	if (f < 0)
		return FALSE;

	// Defaults are "what an idle timer looks like", so a save file missing a key
	// restores a sane state rather than an undefined one.
	ticks = elapsed = haveelapsed = mark = samples = padn = cps = serial = 0;
	st = TS_IDLE; tr = ss = sg = spl = dlt = flg = pbv = dty = rfrom = 0;
	cht = 0;                        // a pre-44 save file knows nothing about it
	sgs = 1;
	az = ez = am = cz = pa = -1;
	cmx = 0;                        // a pre-19 save file has reached no checkpoint
	rpit = ryaw = rduck = 0;
	rorg = e.origin;                // a file with no origin leaves you where you are
	rvel = '0 0 0';

	// The splits are cleared BEFORE the file is read, not after: a save with
	// fewer splits than the run currently in progress must not inherit the
	// leftovers of the one it is replacing.
	SV_TimerClearSplits(e);

	while ((k = fgets(f)) != "")
	{
		n = tokenize(k);
		if (n < 2)
			continue;
		k = argv(0);

		if (k == "state")      { st  = stof(argv(1)); continue; }
		if (k == "track")      { tr  = stof(argv(1)); continue; }
		if (k == "startseg")   { ss  = stof(argv(1)); continue; }
		if (k == "seg")        { sg  = stof(argv(1)); continue; }
		if (k == "segs")       { sgs = stof(argv(1)); continue; }
		if (k == "ticks")      { ticks = stof(argv(1)); continue; }
		if (k == "elapsed")    { elapsed = stof(argv(1)); haveelapsed = TRUE; continue; }
		if (k == "split")      { spl = stof(argv(1)); continue; }
		if (k == "delta")      { dlt = stof(argv(1)); continue; }
		if (k == "flags")      { flg = stof(argv(1)); continue; }
		if (k == "pb")         { pbv = stof(argv(1)); continue; }
		if (k == "dirty")      { dty = stof(argv(1)); continue; }
		if (k == "cheat")      { cht = stof(argv(1)); continue; }

		if (k == "azone")      { az = stof(argv(1)); continue; }
		if (k == "evzone")     { ez = stof(argv(1)); continue; }
		if (k == "armzone")    { am = stof(argv(1)); continue; }
		if (k == "cpzone")     { cz = stof(argv(1)); continue; }
		if (k == "pendarm")    { pa = stof(argv(1)); continue; }
		if (k == "cpmax")      { cmx = stof(argv(1)); continue; }

		if (k == "fromsave")   { rfrom = stof(argv(1)); continue; }

		/*
		  The position keys, read only because `retry` has no rec_sl_* row to be
		  placed from.  A load ignores these and goes through SV_SaveLocPlace,
		  which has already run by the time this is called.
		*/
		if (k == "origin")   { if (n >= 4) rorg = [stof(argv(1)), stof(argv(2)), stof(argv(3))]; continue; }
		if (k == "velocity") { if (n >= 4) rvel = [stof(argv(1)), stof(argv(2)), stof(argv(3))]; continue; }
		if (k == "angles")   { if (n >= 3) { rpit = stof(argv(1)); ryaw = stof(argv(2)); } continue; }
		if (k == "duck")     { rduck = stof(argv(1)); continue; }

		if (k == "reclines")   { mark    = stof(argv(1)); continue; }
		if (k == "recsamples") { samples = stof(argv(1)); continue; }
		if (k == "recpad")     { padn    = stof(argv(1)); continue; }
		if (k == "reccp")      { cps     = stof(argv(1)); continue; }
		if (k == "recserial")  { serial  = stof(argv(1)); continue; }

		if (k == "runsplit")
		{
			if (n >= 3)
				SV_TimerSetRunSplit(e, stof(argv(1)), stof(argv(2)));
			continue;
		}

		// BUILD 23.  Additive by this format's own rule, so a state.txt written
		// by build 22 simply has no runcp lines and restores as it always did --
		// which is the pre-existing behaviour, not a new failure.
		if (k == "runcp")
		{
			if (n >= 3)
				SV_TimerSetRunCP(e, stof(argv(1)), stof(argv(2)));
			continue;
		}
	}
	fclose(f);

	/*
	  Place the player, retry only.  Same shape as SV_SaveLocPlace, including
	  the pitch in BOTH angle fields -- the engine transmits .angles rather than
	  .v_angle whenever fixangle is set (sv_send.c:1535), so writing [0,yaw,0]
	  would silently drop the pitch.
	*/
	if (retry)
	{
		setorigin(e, rorg);
		e.velocity = rvel;
		e.angles   = [rpit, ryaw, 0];
		e.v_angle  = e.angles;
		e.fixangle = TRUE;
		e.run_forceduck = rduck ? FD_DUCK : FD_STAND;
		SV_TimerWarped(e);

		/*
		  EVERY MOVER IN THE MAP JUST WENT BACK TO ITS SPAWN STATE, so a spot
		  that was open air when the point was written can be inside a door or
		  a lift now.  Warn rather than refuse: refusing would strand the player
		  at the map's spawn having asked not to be moved, and `!r` is one key
		  away.  tracebox against self so we test the player's own hull.
		*/
		tracebox(e.origin, e.mins, e.maxs, e.origin, FALSE, e);
		if (trace_startsolid)
			sprint(e, PRINT_HIGH,
			       "^3retry: you are inside something -- the map's movers reset\n");
	}

	e.run_t_state    = st;
	e.run_t_track    = tr;
	e.run_t_startseg = ss;
	e.run_t_seg      = sg;
	e.run_t_segs     = (sgs > 0) ? sgs : 1;
	e.run_t_split    = spl;
	e.run_t_delta    = dlt;
	e.run_t_pb       = pbv;
	e.run_t_dirty    = dty;

	e.run_t_azone    = az;
	e.run_t_evzone   = ez;
	e.run_t_armzone  = am;
	e.run_t_cpzone   = cz;
	e.run_t_pendarm  = pa;
	e.run_t_cpmax    = cmx;

	/*
	  BUILD 19: a restored run is not a start, so the hop rule is already over.

	  It would settle on its own within FS_STARTSETTLE, since you come back
	  airborne or on a ramp -- but `retry` restores a CLEAN run across a
	  map_restart into a fresh edict where every field reads zero, and leaving
	  this false would put a 0.4-second window at the far end of a two-minute run
	  in which a hop could mark it practice.  Saying so outright is cheaper than
	  reasoning about that window.
	*/
	e.run_t_startok  = TRUE;

	/*
	  TF_RECORDING and TF_FROZEN are NOT restored from the file.

	  Both are statements about something that exists right now -- a buffer, and
	  a hold -- and neither can be true because a file says so.  The file cannot
	  know whether the rewind below is going to succeed; taking TF_RECORDING from
	  the saved flags would leave the HUD claiming a recording that no buffer is
	  backing, and the client would then write a sidecar for a .rec that is never
	  going to be written.  TF_FROZEN would be recomputed away by the next
	  maintain anyway, but a state file that carries it is still lying, and it
	  would be a stopped clock the moment the mirror ever became authoritative.
	*/
	e.run_t_flags = flg - (flg & (TF_RECORDING | TF_FROZEN | TF_STOPPED));

	/*
	  Prefer the unrounded clock; fall back to the rounded one for a save file
	  written before `elapsed` existed.  The fallback is exactly the half-tick
	  approximation this key was added to remove, so it is degraded rather than
	  wrong -- and the only cost of that is one `resume` join a reader may find
	  a few milliseconds out of order.
	*/
	if (!haveelapsed)
		elapsed = ticks * run_t_tick;

	/*
	  ONLY A RUNNING CLOCK IS RESUMED.

	  SV_TimerResume recomputes run_t_ticks from the origin it just set, so
	  calling it for a FINISHED state would move the origin to now and rewrite
	  the finishing time as zero -- erasing the result the save was taken to
	  keep.  An idle or armed save has no clock to put back either.
	*/
	if (st == TS_RUNNING)
		SV_TimerResume(e, elapsed);
	else
		e.run_t_ticks = ticks;

	/*
	  Every load is practice.  Only a load of a RUNNING save is a shadow run.

	  The two are not the same claim, and the difference is load-bearing.
	  TF_PRACTICE means "you got here by a route that is not a run", which noclip
	  sets too.  TF_SHADOW means "the clock and the checkpoints came out of the
	  save as well", which is what makes the finished attempt a continuation
	  worth recording under its own name.

	  A save taken while IDLE or ARMED has no run in it to continue.  Marking one
	  TF_SHADOW would be wrong in a way that then sticks: leaving the start zone
	  from a restored ARMED state runs SV_TimerStart directly, and SV_TimerStart
	  does not clear run_t_flags -- only SV_TimerArm does, and no arm happens on
	  that path.  So the flag would survive into a genuinely fresh run and label
	  its recording `_shadow`.  Practice via run_t_dirty is the correct and
	  sufficient marking for those: you did teleport, and that is all that
	  happened.

	  A FINISHED save is excluded for the same reason -- there is nothing left to
	  continue, only a result to look at.

	  NONE OF WHICH APPLIES TO A RETRY, which is why it has its own branch.  A
	  retry did not teleport you and did not give you a clock you had not run
	  for -- the map reset around a player who never moved -- so the attempt is
	  restored exactly as it was written, practice flag and all.  Marking it
	  would mean `retry` could never be used during a real attempt, and using it
	  during a real attempt is the request.
	*/
	if (retry)
	{
		e.run_t_dirty    = dty;
		e.run_t_fromsave = rfrom;

		/*
		  BUILD 43: and the stage taint with it, as closely as the file allows.

		  run_st_dirty is NOT in the save format and is not being added to it: a
		  retry restores an attempt that was written a moment ago by a player who
		  did not move, so the run's own taint is the best available statement
		  about the stage inside it.  The two can disagree in exactly one case --
		  a clean run whose CURRENT stage was dirtied after the save was taken --
		  and there the stage is being under-tainted for one boundary.  Cheap to
		  fix later by widening the save; not worth a format bump for a gesture
		  whose whole premise is that nothing happened.
		*/
		e.run_st_dirty = dty;

		// Build 44, and the same two-field shape one class down: the latch so a
		// retry of an attempt that was cheated before the clock started still is,
		// and the per-stage copy for the same reason run_st_dirty takes one.
		e.run_t_cheat  = cht;
		e.run_st_cheat = cht;
	}
	else
	{
		/*
		  BUILD 43: THROUGH THE FUNNEL, not around it.

		  These were two direct writes -- `run_t_flags |= TF_PRACTICE` and
		  `run_t_dirty = TRUE` -- which is what SV_TimerPractice does plus the
		  per-stage taint it now also owns.  Bypassing it meant the one gesture
		  the "segmented" category is NAMED after would be the one that never set
		  the per-stage field, and a save-locked stage would have been admitted to
		  the stage board as clean.

		  AND THE CHEAT LATCH IS RE-APPLIED FIRST, because the flags restore above
		  can otherwise LAUNDER one.  The word came out of the file, so a run that
		  was clean when the save was taken and has been noclipped since gets its
		  TF_CHEAT wiped by the load and finishes labelled `segmented`.  A load
		  rewinds the clock; it does not rewind your hands.  Nothing about ranking
		  turns on it -- both classes are practice -- but a label that can be
		  removed by a gesture is not a label, and labels are the whole of this
		  build.  run_t_cheat survives because SV_TimerArm is the only thing that
		  clears it, which is exactly what it was made to survive.

		  Caught by a scripted trace and not by reading: it needs a save taken
		  before a cheat and a load taken after one, which is three gestures in an
		  order nobody writes down.

		  BUILD 46: AND IT NEEDS THE run_class GATE, which it did not need when
		  it was written.  This is the third and last place TF_CHEAT is set, and it
		  was safe ungated only because run_t_cheat could not BE true at
		  run_class 0 -- every source of the latch was gated upstream.  Build 46
		  ungated the sv_cheats source on purpose, so without this line the bit
		  would arrive at run_class 0 through a save-load and through nothing
		  else: `cheated` from one gesture and `practice` from every other, which
		  is worse than either answer.  Nothing about ranking turns on it in either
		  direction -- the run is practice from the funnel below regardless.
		*/
		if (e.run_t_cheat)
		if (run_t_runclass)
			e.run_t_flags = e.run_t_flags | TF_CHEAT;

		/*
		  ...AND THEN THE FUNNEL.

		  It prints "practice mode -- this run will not be saved" on a load taken
		  while the clock is running, which the direct writes did not.  That is a
		  new line on screen and it is the truth: the run you just loaded into is
		  not going to be kept.

		  BUILD 44: AND IT IS THE GESTURE THE CLASS IS NAMED AFTER.  A save-lock
		  load is "legit settings, stitched together" verbatim, so it goes through
		  the stitch sibling rather than the bare funnel -- and the line on screen
		  now reads `segmented run` instead of `practice run`, which is the whole
		  of what was asked for one level up.  Under run_class 0 the sibling
		  degrades to exactly the call that was here.
		*/
		SV_TimerStitched(e);

		if (st == TS_RUNNING)
		{
			e.run_t_flags = e.run_t_flags | TF_SHADOW;
			e.run_t_fromsave = id;
		}
		else
			e.run_t_fromsave = 0;
	}

	/*
	  And the movement behind it.  Last, so the `resume` record lands after the
	  rewind and carries the tick the timer was just put back to.

	  A REWIND THAT FAILS MUST DISCARD, and this is the sharp edge of the whole
	  feature.  If it fails while a buffer from some OTHER run is still in hand
	  -- you saved, voided, ran something else, then loaded -- then leaving that
	  buffer alone would append the resumed run's samples onto the tail of an
	  unrelated one, and the file written at the finish would be two runs spliced
	  together with nothing in it to say so.  A recording that is missing is
	  recoverable; one that is quietly wrong is not.
	*/
	if (SV_RecRewind(e, SL_RecPath(id), mark, serial, samples, padn, cps))
	{
		/*
		  A DIFFERENT RECORD FOR A RETRY, and not merely for tidiness.

		  A `resume` tells a reader that the .view sidecar jumps FORWARD here by
		  however long the abandoned attempt lasted.  A retry's sidecar jumps
		  BACKWARDS instead: cltime is realtime - cl.mapstarttime and
		  clientcommandframe is cl.movesequence, and the map restart resets both
		  to near zero.  A reader told "resume" would see the sidecar's own two
		  clocks run backwards and have no way to know that was expected.

		  Across a retry the only join key that stays valid is the run clock --
		  field 3 of a .view line, STAT_FS_TIMERTICKS -- because SV_TimerResume
		  makes the .rec's `t` column continuous by construction.
		*/
		if (retry)
			SV_RecPut(e, sprintf("retry %g", ticks));
		else
			SV_RecPut(e, sprintf("resume %g %g", id, ticks));

		/*
		  BUILD 43 -- AND THE STAGE HAS TO BE REOPENED, WHICH IS NOT OPTIONAL.

		  run_st_line is an INDEX INTO THE BUFFER THE REWIND JUST MOVED.  A warm
		  rewind sets rec_rec_lines back to `mark`, and the stage in progress was
		  almost certainly opened after that -- so run_st_line now points PAST the
		  end of the recording, and SV_StageClose's [run_st_line, rec_rec_lines)
		  range is empty or inverted.  The `if (rec_rec_lines <= run_st_line)` guard
		  there catches the empty case and writes nothing, which is the safe
		  failure; reopening is the correct one.

		  AFTER the record above, so the `resume` or `retry` line is not the first
		  line of the new slice -- the same ordering SV_StageFail and
		  SV_TimerRestartSeg both document, and for the same reason.

		  It re-arms.  There is no crossing to arm ON, so the arm resolves itself
		  from the boundary box on the next tick exactly as it does after `!r`:
		  land inside it and the stage times from when you leave, land outside and
		  it disarms.  Correct either way.
		*/
		if (e.run_t_state == TS_RUNNING)
		if (e.run_st_seg >= 0)
		{
			SV_StageOpen(e, e.run_t_seg, ticks);

			/*
			  AND PUT THE TAINT BACK, because SV_StageOpen reads it from the
			  LEVEL -- the movetype at this instant -- which is MOVETYPE_WALK for
			  a player who walked to the save key and pressed load.  Opening the
			  stage would therefore launder the load, and the load is the gesture
			  the whole "segmented" category is named after.

			  run_t_dirty and not TRUE: on the retry path it carries the saved
			  attempt's own value, so a retry of a clean run stays clean and a
			  retry of a dirty one stays dirty.
			*/
			e.run_st_dirty = e.run_t_dirty;

			/*
			  BUILD 44: and the CLASS with it, from the run's own word.

			  SV_StageOpen zeroes the stitch half and re-reads the cheat half from
			  the level, and both are wrong here for the reason the paragraph above
			  gives about the umbrella: the level is MOVETYPE_WALK with cheats off
			  for a player who walked to the save key and pressed load.  So the run
			  answers for the stage, exactly as it does for run_st_dirty -- the same
			  over-taint in the same one case (a clean run whose current stage was
			  dirtied after the save was taken) and the same argument for accepting
			  it rather than widening the save format.
			*/
			if (e.run_t_flags & TF_SEGMENT)
				e.run_st_stitch = TRUE;
			if (e.run_t_cheat)
			{
				e.run_st_cheat = TRUE;
				e.run_st_dirty = TRUE;
			}
		}
	}
	else
		SV_RecDiscard(e);

	return TRUE;
};

/*
===========================================================================
  The scan -- the disk IS the list
===========================================================================
*/
/*
  Sort the rows by seq.

  An insertion sort over at most 32 rows, which is nothing, and it is a sort
  rather than a "trust the filename order" because the folder id is deliberately
  NOT the order -- see the header.  Ten parallel arrays swap together; a swap
  that misses one would put one save's origin against another's clock, and that
  failure is silent and would look like the timer being wrong.
*/
void() SV_SaveSort =
{
	local float i, j;
	local vector vo, vv;
	local float a, b, c, d, g, h, k, m;

	for (i = 1; i < rec_sl_n; i = i + 1)
	{
		vo = rec_sl_org [i];  vv = rec_sl_vel [i];
		a  = rec_sl_pit [i];  b  = rec_sl_yaw [i];
		c  = rec_sl_duck[i];  d  = rec_sl_id  [i];
		g  = rec_sl_seq [i];  h  = rec_sl_tick[i];
		k  = rec_sl_seg [i];  m  = rec_sl_cps [i];

		j = i;
		while (j > 0)
		{
			if (rec_sl_seq[j - 1] <= g)
				break;
			rec_sl_org [j] = rec_sl_org [j - 1];
			rec_sl_vel [j] = rec_sl_vel [j - 1];
			rec_sl_pit [j] = rec_sl_pit [j - 1];
			rec_sl_yaw [j] = rec_sl_yaw [j - 1];
			rec_sl_duck[j] = rec_sl_duck[j - 1];
			rec_sl_id  [j] = rec_sl_id  [j - 1];
			rec_sl_seq [j] = rec_sl_seq [j - 1];
			rec_sl_tick[j] = rec_sl_tick[j - 1];
			rec_sl_seg [j] = rec_sl_seg [j - 1];
			rec_sl_cps [j] = rec_sl_cps [j - 1];
			j = j - 1;
		}

		rec_sl_org [j] = vo;  rec_sl_vel [j] = vv;
		rec_sl_pit [j] = a;   rec_sl_yaw [j] = b;
		rec_sl_duck[j] = c;   rec_sl_id  [j] = d;
		rec_sl_seq [j] = g;   rec_sl_tick[j] = h;
		rec_sl_seg [j] = k;   rec_sl_cps [j] = m;
	}
};

/*
  Build the list from what is on disk.

  The pattern is data/saves/<map>/ then a star then /state.txt -- spelled out in
  words because the literal ends a C comment, which is a lesson this file learnt
  the loud way.

  A wildcard in a MIDDLE path component, which is legal here and was checked
  rather than assumed: Sys_EnumerateFiles2 (client/sys_win.c) splits the pattern
  at the first wildcard and recurses into every directory that matches it.  These
  are loose files we wrote ourselves, so the package search paths are not in the
  way either.

  The id is taken from the folder NAME rather than from inside the file, because
  the name is what the three paths are spelled from -- a file whose `seq` says
  one thing and whose folder says another is still found under its folder.
*/
void() SV_SaveLocScan =
{
	local searchhandle h;
	local string pre, fn;
	local float i, cnt, id, seq, pl;

	rec_sl_n = 0;
	rec_sl_nextseq = 1;

	/*
	  PATCH 270, STAGE 2 -- THE OTHER ROW-ADDER, and the reason the gate in
	  SV_SaveLocCreate was not enough on its own.

	  That gate's own argument was "with nothing ever added the list stays
	  empty, so load, step, delete and delete-all all find nothing".  The
	  premise was false: THIS function adds rows too, from disk, at map init,
	  before any player can be refused anything.  A server whose operator
	  practised on this map solo loads their data/saves/<map>/save01../state.txt
	  straight into the shared list, and then every one of the 32 strangers can
	  press the delete-all key -- SV_SaveLocDeleteAll fremoves four files per
	  row -- or teleport themselves to the operator's practice points.

	  That is the same class of silent, irreversible, cross-player data
	  destruction the patch was written to close on best.pb, left open one file
	  over.  Gating the scan is what makes the create gate's premise true.

	  Below the two resets on purpose: the list must still be CLEARED on a map
	  change even in a lobby, or the previous map's rows would survive into it.

	  rec_sl_scanned RECORDS THAT THIS WAS SKIPPED, and it is not bookkeeping
	  for its own sake.  An empty list here does not mean an empty disk: the
	  host's data/saves/<map>/save01../state.txt are still there.  SV_SaveFreeID
	  picks the lowest id NOT IN THE LIST, so with the list empty and the folders
	  present it hands back 1, and the next `save` overwrites save01 -- which is
	  the same data destruction this gate exists to prevent, arriving through the
	  gate instead of around it.  It needs the lobby to be switched off mid-map
	  to happen, because create is refused while it is on, but that is a console
	  command away.  SV_SaveLocCreate rescans when it sees this flag clear.
	*/
	if (Lobby_NoSaveLoc())
	{
		rec_sl_scanned = FALSE;
		return;
	}

	if (mapname == "")
		return;

	rec_sl_scanned = TRUE;

	pre = sprintf("data/saves/%s/save", mapname);
	pl  = strlen(pre);

	h = search_begin(sprintf("data/saves/%s/*/state.txt", mapname), SL_NAMESORT, TRUE);
	if (h < 0)
		return;

	cnt = search_getsize(h);
	for (i = 0; i < cnt; i = i + 1)
	{
		if (rec_sl_n >= FS_MAXSAVES)
			break;

		fn = strtolower(search_getfilename(h, i));
		if (substring(fn, 0, pl) != strtolower(pre))
			continue;

		// FS_SAVENAMELEN characters, because that is what FS_SaveSlotName always
		// writes -- reading the id back by offset is only sound while the width
		// is fixed, which is why that constant lives beside the writer.
		id = stof(substring(fn, pl, FS_SAVENAMELEN));
		if (id < 1 || id > FS_MAXSAVES)
			continue;

		seq = SV_SaveReadLight(id, rec_sl_n);
		if (seq < 0)
			continue;               // not a save state, or torn

		rec_sl_seq[rec_sl_n] = seq;
		rec_sl_n = rec_sl_n + 1;

		if (seq >= rec_sl_nextseq)
			rec_sl_nextseq = seq + 1;
	}
	search_end(h);

	SV_SaveSort();

	if (rec_sl_n > 0)
		dprint(sprintf("saveloc: %g save state(s) on %s\n", rec_sl_n, mapname));
};

/*
  Per map.  Called from SV_TimerMapInit, which is after mapname is known and
  after the zones are loaded.

  It no longer just clears -- the saves outlive the map change now, which is
  most of the point of putting them on disk.  What it does clear is every
  player's hold and cursor, because those are about a session and not about the
  map.
*/
void() SV_SaveLocReset =
{
	local entity p;

	p = world;
	while ((p = find(p, classname, "player")))
	{
		// Before the list is rebuilt: releasing reads the row it was holding.
		SV_SaveLocRelease(p);

		// And a watch, for the same reason a hold is cleared here: the CSQC VM
		// that opened it was destroyed by the map change, so nothing is left to
		// send the release and the player would spawn on the new map pinned.
		SV_WatchRelease(p);
		p.rec_sl_index = 0;
	}

	SV_SaveLocScan();

	p = world;
	while ((p = find(p, classname, "player")))
		if (rec_sl_n > 0)
			p.rec_sl_index = rec_sl_n;
};

/*
  Mirror the global list into the fields that are actually networked, and keep
  the cursor inside it.

  Called once per tick from PlayerPostThink.  clientstat takes a FIELD, so a
  global list cannot be published directly -- and a mirror updated at every
  mutation site instead would be one more thing to remember at each of the five
  places the list changes.  Three float compares a tick is cheaper than that
  bug.
*/
void(entity e) SV_SaveLocSync =
{
	e.rec_sl_count = rec_sl_n;

	if (e.rec_sl_index > rec_sl_n)
		e.rec_sl_index = rec_sl_n;
	if (rec_sl_n > 0 && e.rec_sl_index < 1)
		e.rec_sl_index = 1;

	e.rec_sl_savetick = 0;
	if (e.rec_sl_index >= 1)
		if (e.rec_sl_index <= rec_sl_n)
			e.rec_sl_savetick = rec_sl_tick[e.rec_sl_index - 1];
};

// One save/load event out to the client.  See STAT_FS_SLSEQ.
void(entity e, float op, float id) SV_SaveLocEvent =
{
	// FS_SlopPack, not a literal radix -- see STAT_FS_SLOP.  The three decoders
	// are in three other files and one of them is in another VM.
	e.rec_sl_slop = FS_SlopPack(op, id);
	e.rec_sl_slseq = e.rec_sl_slseq + 1;
};

/*
===========================================================================
  The list
===========================================================================
*/
void(entity e) SV_SaveLocSay =
{
	if (rec_sl_n <= 0)
		sprint(e, PRINT_HIGH, "^7saves: ^3none\n");
	else
		sprint(e, PRINT_HIGH, sprintf("^7saves: ^2%g^7/%g\n", e.rec_sl_index, rec_sl_n));
};

/*
  The lowest folder number nobody is using.

  Lowest-free rather than highest-plus-one so the ids stay dense and the folder
  listing stays readable; the ORDER comes from seq, so reusing a hole cannot
  reorder the list.

  BUILD 25: ONE PASS, NOT TWO NESTED ONES.  It used to walk the whole list for
  every candidate id, which at 32 slots was 1,024 compares in the worst case and
  invisible.  At 999 it is a million, on a keypress, and the worst case is the
  ordinary one -- a full list is exactly when every id has to be tested.  Marking
  the used ids into a scratch row first makes it linear.

  rec_sl_used is bare and is not cleared between calls beyond the ids it is about
  to read: only the rows actually in the list are stamped, and only those rows
  are consulted, so a stale mark from a longer list cannot be reached.  The stamp
  is rec_sl_nextseq, which is monotonic for the life of the map and therefore
  cannot collide with a previous call's.
*/
float  rec_sl_used[FS_MAXSAVES + 1];      // id -> the stamp of the call that used it
float  rec_sl_usedstamp;

float() SV_SaveFreeID =
{
	local float id, i;

	rec_sl_usedstamp = rec_sl_usedstamp + 1;

	for (i = 0; i < rec_sl_n; i = i + 1)
	{
		id = rec_sl_id[i];
		if (id >= 0)
		if (id <= FS_MAXSAVES)
			rec_sl_used[id] = rec_sl_usedstamp;
	}

	for (id = 1; id <= FS_MAXSAVES; id = id + 1)
		if (rec_sl_used[id] != rec_sl_usedstamp)
			return id;

	return 0;
};

/*
  Create.  Appended, and the new one becomes current -- so `1` then `2` with
  the menu closed is always "save here, put me back here", which is the whole
  point of the two-key form.
*/
void(entity e) SV_SaveLocCreate =
{
	local float id, seq, row;

	/*
	  PATCH 270, STAGE 2 -- no save-locs in a lobby.

	  The list above this function is ONE list.  rec_sl_* are plain globals with
	  no player dimension anywhere in them, so on a 32-player server every
	  `save` lands in the same shared list, every `delete` deletes out of it,
	  and the cursor each player steps with rec_sl_index walks over everybody
	  else's rows.  Player A pressing delete-all removes player B's practice
	  points mid-section.

	  Refused at CREATE only, and that is the whole surface that needs it: with
	  nothing ever added the list stays empty, so load, step, delete and
	  delete-all all find nothing and say so through their existing empty-list
	  paths.  Gating six functions would be six chances to miss one.

	  A save-loc is a tool for one player alone with a difficult section, which
	  is exactly what a lobby is not.  Turning it off there costs nothing anyone
	  would want; sharing it silently destroys work.
	*/
	if (Lobby_NoSaveLoc())
	{
		sprint(e, PRINT_HIGH,
		       "^3save: save points are off in a public lobby -- the list is "
		       "shared, so a save here would be everyone's.\n");
		return;
	}

	/*
	  PATCH 270, STAGE 2.  The lobby refused the scan, so the empty list is a
	  policy, not a fact about the disk -- and we are past the lobby gate above,
	  so the lobby has since been switched off and the disk is authoritative
	  again.  Read it before allocating an id, or SV_SaveFreeID returns 1 and
	  SV_SaveWriteState overwrites an existing save01.  See rec_sl_scanned.
	*/
	if (!rec_sl_scanned)
		SV_SaveLocScan();

	if (rec_sl_n >= FS_MAXSAVES)
	{
		sprint(e, PRINT_HIGH,
		       sprintf("^3save: the list is full (%g).  Delete one first.\n", FS_MAXSAVES));
		return;
	}

	id = SV_SaveFreeID();
	if (id < 1)
	{
		sprint(e, PRINT_HIGH, "^3save: no free slot number\n");
		return;
	}

	seq = rec_sl_nextseq;
	rec_sl_nextseq = rec_sl_nextseq + 1;

	SV_SaveWriteState(e, id, seq);

	// Read the light row straight back out of the file we just wrote, rather
	// than filling it from the player here.  It is one small read, and it means
	// the list is showing what a load would ACTUALLY restore -- if the write
	// failed or was short, the list says so instead of showing a row that only
	// exists in memory.
	row = rec_sl_n;
	if (SV_SaveReadLight(id, row) < 0)
	{
		sprint(e, PRINT_HIGH, "^1save: the state file did not come back readable\n");
		return;
	}
	rec_sl_seq[row] = seq;
	rec_sl_n = rec_sl_n + 1;

	e.rec_sl_index = rec_sl_n;
	SV_SaveLocEvent(e, SLOP_SAVED, id);

	sprint(e, PRINT_HIGH, sprintf("^7save ^2%g^7 (slot %s)  %s\n",
	                              rec_sl_n, SL_NN(id),
	                              (e.run_t_state == TS_RUNNING)
	                                ? SV_TimerString(SV_TimerTicks(e))
	                                : "no run"));
};

/*
  Build 30.  Republish the parked velocity for the row the hold is on.

  One funnel, called from all three places a hold's row can be established --
  the press, a re-point while parked, and the per-tick frame -- so there is no
  path that freezes a player without saying what they are frozen at.  Guarded
  the way every array read in this file is (nested ifs: QuakeC's && evaluates
  both sides and would index the array anyway), and it clears rather than holds
  a stale vector when the row has gone.
*/
void(entity e) SV_SaveLocHoldVel =
{
	e.rec_sl_holdvel = '0 0 0';

	if (!e.rec_sl_hold)
		return;
	if (e.rec_sl_holdrow < 0)
		return;
	if (e.rec_sl_holdrow >= rec_sl_n)
		return;

	e.rec_sl_holdvel = rec_sl_vel[e.rec_sl_holdrow];
};

/*
  Put the player at row `r`.  Split out from SV_SaveLocLoad because the hold
  calls it every tick and must not re-print, re-arm practice mode, touch the
  timer, or move the cursor while it does.
*/
void(entity e, float r) SV_SaveLocPlace =
{
	setorigin(e, rec_sl_org[r]);
	e.velocity = rec_sl_vel[r];

	/*
	  THE PITCH GOES IN BOTH, and that is not a style choice -- it is the whole
	  of why a loaded save has never restored the angle you saved it at.

	  .angles on a player is the MODEL's orientation and .v_angle is the view,
	  so writing the real pitch into .angles looks wrong.  But sv_send.c:1535 is

	      ang = ent->v->fixangle ? ent->v->angles : ent->v->v_angle;

	  -- when fixangle is set the engine transmits .angles, NOT .v_angle.  So
	  `[0, yaw, 0]` here meant the saved pitch was dropped on the wire every
	  single time, and only the yaw ever reached the client.  The model is
	  wrong for the one frame before the client's own angles come back, which
	  is what every other correct caller in this codebase already accepts:
	  SV_ZoneGotoAng (sv_zones.qc:513) writes [pitch, yaw, 0] and is the path
	  that has always aimed correctly.  The engine's own setpos (sv_user.c:5605,
	  Patch 165) writes the full triple to both and its comment is this bug.
	*/
	e.angles   = [rec_sl_pit[r], rec_sl_yaw[r], 0];
	e.v_angle  = e.angles;

	// Hand the duck state back to the engine's pmove.  See run_forceduck.
	e.run_forceduck = rec_sl_duck[r] ? FD_DUCK : FD_STAND;

	// A save state is a teleport as far as the swept zone test is concerned.
	SV_TimerWarped(e);
};

void(entity e, float n) SV_SaveLocLoad =
{
	local float r, id;

	/*
	  PATCH 270, STAGE 2 -- the last of the four surfaces, and the only one that
	  is not about destroying data.

	  Gating the scan empties the list, so on a map that loads as a lobby this
	  is unreachable.  It is reachable on the host who practised offline and
	  then switched the lobby on: the list is still in memory, and every
	  stranger's 3/4/5/6 key teleports them onto that host's practice points --
	  and, through SV_SaveLocPlace, onto their saved velocity and run clock.
	  Not destructive, but it is somebody else's position being handed out, and
	  a shadow run started from it would be timed against a section the player
	  never travelled.

	  Load, delete, delete-all and create are now all refused.  Step, first and
	  last only move a cursor and cannot act without this function.
	*/
	if (Lobby_NoSaveLoc())
	{
		sprint(e, PRINT_HIGH,
		       "^3save: save points are off in a public lobby.\n");
		return;
	}

	if (rec_sl_n <= 0)
	{
		sprint(e, PRINT_HIGH, "^3save: nothing saved on this map\n");
		return;
	}

	if (n < 1) n = 1;
	if (n > rec_sl_n) n = rec_sl_n;
	e.rec_sl_index = n;

	r  = n - 1;
	id = rec_sl_id[r];

	SV_SaveLocPlace(e, r);

	/*
	  BUILD 39 -- "I DID NOT LAND HERE, I WAS PUT HERE", and this was the one
	  placement in the codebase that never said so.

	  trigger_teleport_touch clears this, trigger_teleport_relative_touch now
	  clears this, SV_BhopTeleport clears this.  A load did not -- and a load is
	  the only one of the four that also hands you back a VELOCITY, which is the
	  combination that matters: save while rising, load onto a floor, and the
	  first tick believes it is standing there with your old rise still on the
	  clock.

	  WHAT THIS DOES NOT DO, so nobody assumes it later: it does not close the
	  double-jump hole.  PMSrc_Tick calls CategorizePosition (pm_source.c:2732)
	  BEFORE FullWalkMove, and that re-derives onground from a fresh trace and
	  overwrites whatever sv_user.c:7944 loaded out of this flag.  The jump is
	  Patch 241's problem and Patch 241 solves it.  This is about the QC's own
	  view of the world -- STAT_FS_FLAGS, the HUD's ground regime, Board_Frame's
	  segment kind, the bhop dwell timer -- all of which read the flag and none
	  of which get a trace of their own.

	  HERE AND NOT IN SV_SaveLocPlace, which is where it was first written and
	  which would have been wrong: SV_SaveLocHoldFrame re-calls Place every tick
	  the origin has drifted (:1517), so the clear would land mid-park and flicker
	  the ground flag under a frozen player who is demonstrably standing still.
	  Loading is the event; re-pinning is not.
	*/
	e.flags = e.flags - (e.flags & FL_ONGROUND);

	/*
	  The run state, and it is a full restore rather than a "keep going".

	  SV_SaveApplyState is what makes this a save STATE rather than a save-lock:
	  the clock goes back to the tick it read at the save, the splits behind you
	  become the ones you actually set, the latches go back verbatim so a box you
	  were standing in does not fire again, and the recorder rewinds to the
	  movement you had done by then.
	*/
	if (!SV_SaveApplyState(e, id, FALSE))
		sprint(e, PRINT_HIGH, "^3save: the state file could not be read\n");

	/*
	  Loading WHILE PARKED re-targets the hold rather than fighting it.

	  You can hold 2 and tap 4/5 to walk the list without unfreezing, which is
	  the natural way to find the save you meant.  Without this the next tick's
	  drift check would drag you straight back to the row the hold started on.
	*/
	if (e.rec_sl_hold)
	{
		e.rec_sl_holdrow = r;
		e.velocity = '0 0 0';

		// The published copy follows the re-point, or walking the list while
		// parked would leave the HUD reading the row you started the hold on.
		SV_SaveLocHoldVel(e);
	}

	/*
	  BUILD 47: LOADING AT A START BOX IS HOW YOU PICK A START, NOT A STITCH.

	  A save-lock load taints the attempt -- SV_TimerStitched above sets
	  TF_SEGMENT and TF_PRACTICE, and sl_hold's copy adds its own through
	  SV_TimerFreeze, both of which arrive on ONE keypress because
	  cl_saveloc.qc sends sl_load and sl_hold together.  That is right for a
	  load taken halfway down a map.  It is wrong for the ordinary gesture of
	  putting yourself back at a start box to pick which start you are running
	  from, and there is nothing segmented about walking out of it afterwards.

	  AFTER SV_SaveApplyState ON PURPOSE.  That call restores run_t_azone and
	  run_t_armzone verbatim from the file (the whole point of a save STATE), so
	  anything written before it is overwritten.  It is also exactly why the
	  taint survived: with azone restored to the box you are standing in, the
	  edge test in SV_TimerFrame (`az != e.run_t_azone`) never fires, so
	  SV_TimerArm -- the ONLY thing that launders an attempt -- never runs.

	  SO THIS FORCES THE EDGE AND LETS THE EXISTING MACHINE DO THE REST.
	  SV_TimerArm already zeroes run_t_flags, run_t_said, run_t_hopped and
	  run_t_fromsave, and RE-DERIVES run_t_dirty and run_t_cheat from the live
	  state -- so a player who is actually noclipping or has sv_cheats on stays
	  tainted, which is correct and is why reusing the arm beats writing a
	  parallel clear that would have to remember all six fields.

	  TS_RUNNING is excluded: a save taken mid-run that happens to sit inside a
	  start box is still a resumed run and still owes its TF_SHADOW.  Nothing is
	  printed in the intervening tick either -- SV_TimerClassSay is gated on
	  TS_RUNNING, so the taint that is about to be laundered was never announced.
	*/
	if (e.run_t_state != TS_RUNNING)
	if (SV_ZoneStartAt(e, e.origin) >= 0)
		e.run_t_azone = -1;

	// fixangle only on the one-shot load.  The hold re-places the origin every
	// tick but must NOT keep stamping the view angles, or you could not look
	// around while parked.
	e.fixangle = TRUE;

	SV_SaveLocEvent(e, SLOP_LOADED, id);

	if (e.run_t_state == TS_RUNNING)
		sprint(e, PRINT_HIGH,
		       sprintf("^5save %g^7 -- run resumed at ^5%s^7, %g checkpoint(s), shadow run\n",
		               n, SV_TimerString(e.run_t_ticks), rec_sl_cps[r]));
	else
		SV_SaveLocSay(e);
};

/*
  Release.  Idempotent, and safe on a player who was never holding -- it is
  called from the key-up, from the deadman below, from PutClientInServer and
  from anything else that needs to be sure.
*/
void(entity e) SV_SaveLocRelease =
{
	if (!e.rec_sl_hold)
		return;

	e.rec_sl_hold = FALSE;

	// MOVETYPE_NONE is 0, so a stored 0 means "it was already frozen when the
	// hold started" -- give back WALK, which is the only thing a player can
	// usefully be here and is what PutClientInServer sets.
	e.movetype = e.rec_sl_holdmove ? e.rec_sl_holdmove : MOVETYPE_WALK;
	e.rec_sl_holdmove = 0;

	/*
	  Hand back the save's velocity.  While frozen it was zero; letting go has
	  to be indistinguishable from a fresh load or "park, then start the
	  section" would always start you from a standstill.

	  Guarded, because the row can have gone away under the hold -- the same
	  nested-if rule every array read in this build follows, since QuakeC's &&
	  evaluates both sides and would read the array anyway.
	*/
	if (e.rec_sl_holdrow >= 0)
		if (e.rec_sl_holdrow < rec_sl_n)
			e.velocity = rec_sl_vel[e.rec_sl_holdrow];

	// The published copy goes with it.  .velocity is the live answer again from
	// here on, so leaving this set would give the HUD two sources that disagree
	// the moment you move.
	e.rec_sl_holdvel = '0 0 0';

	// And the clock starts again.  This is the single thaw funnel: every way a
	// hold can end -- key-up, the client deadman, the console or menu taking
	// focus, the save being deleted, the list emptying, a map change, respawn,
	// setpos -- arrives here, which is why the freeze is safe to make sticky.
	SV_TimerThaw(e);
};

/*
  Hold / release.  `down` arrives from the client on the key's edges only
  (cl_saveloc.qc filters the repeats), so this is not per-tick traffic.
*/
void(entity e, float down) SV_SaveLocHold =
{
	if (!down)
	{
		SV_SaveLocRelease(e);
		return;
	}

	// Already holding: the client re-sent it.  Not an error -- see the deadman
	// heartbeat in cl_saveloc.qc -- and it must not stack a second movetype.
	if (e.rec_sl_hold)
		return;

	if (rec_sl_n <= 0)
	{
		sprint(e, PRINT_HIGH, "^3save: nothing saved on this map\n");
		return;
	}

	e.rec_sl_hold    = TRUE;
	e.rec_sl_holdrow = e.rec_sl_index - 1;
	e.rec_sl_holdmove = e.movetype;

	e.movetype = MOVETYPE_NONE;
	e.velocity = '0 0 0';

	// ...and the same number published, before the first snapshot of the hold
	// goes out.  Doing it here as well as in the per-tick frame below is what
	// makes the readout correct ON THE PRESS rather than one tick later, which
	// is the whole complaint this build is answering.
	SV_SaveLocHoldVel(e);

	/*
	  BUILD 44 -- THE HOLD IS A STITCH, AND IT IS A RENAMING RATHER THAN A NEW
	  TAINT.

	  A hold has marked the run practice since build 18 and does it inside
	  SV_TimerFreeze below, whose own comment is the argument: "a stopped clock is
	  not something a kept run may have".  Which is right, and it is also exactly
	  what `segmented` means -- park at every hard section, study the line, let go,
	  and the number at the end was never run in one take.  So the word changes and
	  nothing about what is kept does.

	  BEFORE SV_TimerFreeze, DELIBERATELY, and this is the whole reason the call is
	  here rather than left to that function.  SV_TimerFreeze's own
	  SV_TimerPractice would fire first and spend the class message on the word
	  `practice`; the print reports an UPGRADE and there is only one.  Marking here
	  first makes the freeze's call the silent one.

	  AND NOT IN SV_TimerFreeze ITSELF, which has a second caller: opening a REPLAY
	  mid-attempt freezes the clock the same way and is not a save-lock.  Pausing
	  to watch somebody's demo is plain practice, and moving the stitch one level
	  down would have relabelled it on the strength of a shared implementation
	  detail.
	*/
	SV_TimerStitched(e);

	// Build 18: and the clock stops with you.  Studying an approach from a
	// parked position is not time spent on the run, and letting it count made
	// the save-lock unusable mid-attempt.  Only asks -- SV_TimerFreezeFrame
	// does the arithmetic, at a `time` this hook does not have.
	SV_TimerFreeze(e);
};

/*
===========================================================================
  WATCHING A RECORDING.  Build 24.

  `rec_watch 1` pins the player exactly as a save-lock hold does, and for the
  reason the request gave: watching a replay must not start a run or trigger
  anything on the map.  The camera is entirely client-side -- the client sets
  VF_ORIGIN and VF_ANGLES from the file and the server is never told where the
  recording goes -- so this is the whole of the server's involvement.

  IT DELIBERATELY DOES NOT REUSE rec_sl_hold, AND THAT IS THE POINT.

  It would fit: the pin is the same MOVETYPE_NONE, the clock stop is the same
  SV_TimerFreeze, and the release is the same pair undone.  But a save-lock hold
  is a KEY BEING HELD, with a client heartbeat and a deadman and a list row it is
  anchored to; a watch is a mode that stays on until something closes it.  Two
  state machines sharing one flag means every future edit to either has to be
  correct for both, and build 11's dead load key was exactly that failure --
  one missing release left the flag latched and every later press was swallowed
  by a guard that thought the key was still down.

  So: its own field, its own release, and it REFUSES while a save-lock hold is
  live rather than silently taking the movetype out from under it.  The two can
  never be on at once, which is the invariant that makes them independent.

  The client also empties its own usercmd the moment a replay opens
  (CSQC_Input_Frame), so nothing can move between the command being sent and it
  arriving.  This is the half that stops gravity and the movers.
*/
.float rec_wt_hold;
.float rec_wt_holdmove;

/*
===========================================================================
  BUILD 43 -- THE PVS EYE, AND WHY A DETACHED CAMERA NEEDS ONE.

  The essay above says "the server is never told where the recording goes" as
  though it were the end of the design.  It is, for movement -- but not for
  VISIBILITY, and that turned out to be a bug the report found before we did:

      "surf_fiellu Demo playback like on some maps, doesn't show some of the
       models or ramps, playing the map is fine."

  The server builds a client's PVS from client->edict (sv_ents.c:4375) and drops
  every entity that fails it (sv_ents.c:4163).  During a replay client->edict is
  the pinned body, standing wherever the key was pressed, and it never moves --
  so the camera flies away and the entity set stays behind.  The world BSP keeps
  drawing, because it is client-side and follows the overridden view; what
  vanishes is precisely what the SERVER sends.  FTESurf spawns surf ramps as
  func_brush/func_slide and decorations as prop_dynamic, all of them networked
  entities, so what vanishes is "models and ramps".  prop_static survives -- it
  is not an entity at all, it lives in the map's own game lump.

  MEASURED ON surf_fiellu BEFORE ANY OF THIS WAS WRITTEN (cfg/testrun/b43pvs):
      baseline        entities 324 (brush 0) -> 3 (brush 0) -> 0 (brush 0)
      sv_nopvs 1      entities 268 (brush 41) -> 107 (brush 41) -> 104 (brush 41)
      sv_nopvs 0      entities 164 (brush 0) -> 0 (brush 0)      (matches baseline)
      r_novis 1       entities 217 (brush 0) -> 3 (brush 0)      (fixes NOTHING)
  Forty-one brush entities, present only when the SERVER stops culling.  The
  r_novis arm is the one that makes it a diagnosis rather than a story: it is
  the CLIENT's world cull, and it brought nothing back.

  THE FIX IS AN ENGINE HOOK THAT ALREADY EXISTS.  sv_ents.c:4382-4383 feeds a
  client's `.view2` to SV_AddCameraEntity, which UNIONS a second origin and area
  into the PVS rather than replacing it.  So one invisible marker, moved to the
  camera, and the server's answer becomes "the body OR the camera".  FTESurf has
  never set .view2 anywhere; no engine change is needed.

  ONE FIELD FOR BOTH MODES, AND THE INVARIANT THAT MAKES IT SAFE.  The essay
  above is emphatic that the replay pin must not share rec_sl_hold, and it is
  right -- two state machines sharing one flag means every future edit to either
  has to be correct for both.  This is not that: it is a RESOURCE with one owner
  at a time, and the ownership is already enforced.  A watch refuses under a
  save-lock hold (:1391) and a ghost refuses under a watch (SV_GhostSet), so the
  two callers can never both hold it.  If that ever stops being true this needs
  splitting -- and the reason it would need splitting is written here so the
  next person does not have to derive it.

  THE POSITION COMES FROM THE CLIENT, at a few times a second and only when it
  has moved.  PVS granularity is a whole visleaf, so nothing here wants per-tick
  precision, and a stringcmd per tick to say the camera moved forty units would
  be silly.  See Watch_Camera for the throttle.
===========================================================================
*/
.entity rec_vw_eye;

/*
  Take the eye away.  Called from both releases, and safe to call when there is
  none -- which is the ordinary case for every player who has never opened a
  replay.
*/
void(entity e) SV_ViewEyeDetach =
{
	if (e.rec_vw_eye == world)
		return;

	remove(e.rec_vw_eye);
	e.rec_vw_eye = world;
	e.view2     = world;
};

/*
  Give it one, at `org`, creating it on the first call.

  MOVETYPE_NONE and SOLID_NOT with no model: it exists only to be a second
  origin for FatPVS, so it must not collide, must not be sent to anyone and must
  not touch anything on the way past.  setorigin relinks without running touch
  functions, which is what makes moving it every few frames free of side effects
  -- and is why this does NOT reuse the pinned player as its own eye, which
  would have been simpler and would have driven the timer's zone scan through
  every stage boundary on the map.
*/
void(entity e, vector org) SV_ViewEyeAt =
{
	/*
	  DETACHES rather than merely declining, so the cvar is a real bisection and
	  not a one-way switch.  Read live rather than latched at map init for the
	  same reason: turning it off with a replay already open has to put the
	  entity set back to build 42's on the next snapshot, or an A/B against it
	  measures whatever the eye happened to be pointing at when it was turned
	  off -- which is a third state neither arm describes.
	*/
	if (!cvar("rec_watch_pvs"))
	{
		SV_ViewEyeDetach(e);
		return;
	}

	if (e.rec_vw_eye == world)
	{
		e.rec_vw_eye = spawn();
		e.rec_vw_eye.classname = "rec_view_eye";
		e.rec_vw_eye.movetype  = MOVETYPE_NONE;
		e.rec_vw_eye.solid     = SOLID_NOT;
		e.rec_vw_eye.owner     = e;
		setmodel(e.rec_vw_eye, "");
		setsize(e.rec_vw_eye, '0 0 0', '0 0 0');
		e.view2 = e.rec_vw_eye;
	}

	setorigin(e.rec_vw_eye, org);
};

void(entity e) SV_WatchRelease =
{
	if (!e.rec_wt_hold)
		return;

	e.rec_wt_hold = FALSE;
	SV_ViewEyeDetach(e);

	// MOVETYPE_NONE is 0, so a stored 0 means "already frozen when this
	// started" -- hand back WALK, which is what PutClientInServer sets.  Same
	// argument as SV_SaveLocRelease, and the same trap: a plain restore of a
	// zero would leave the player pinned with nothing left holding them.
	e.movetype = e.rec_wt_holdmove ? e.rec_wt_holdmove : MOVETYPE_WALK;
	e.rec_wt_holdmove = 0;

	SV_TimerThaw(e);
};

void(entity e, float on) SV_WatchHold =
{
	if (!on)
	{
		SV_WatchRelease(e);
		return;
	}

	if (e.rec_wt_hold)
		return;                 // already watching; must not stack a movetype

	/*
	  Refuse under a save-lock hold rather than fight it.  Both want the
	  movetype and both would give it back; whichever released second would hand
	  back a MOVETYPE_NONE it had stored from the other, and the player would be
	  frozen with nothing holding them and no way to ask for a release.
	*/
	if (e.rec_sl_hold)
	{
		sprint(e, PRINT_HIGH,
		       "^3replay: let go of the save-lock key first\n");
		return;
	}

	e.rec_wt_hold     = TRUE;
	e.rec_wt_holdmove = e.movetype;

	e.movetype = MOVETYPE_NONE;
	e.velocity = '0 0 0';

	/*
	  Seeded at the BODY, not left absent until the first rec_watchpos arrives.
	  A replay opens with the camera on the run's first sample, which on most
	  maps is somewhere near where you were standing anyway -- but for the frame
	  or two before the client's first position lands, an eye at the body gives
	  exactly build 42's entity set rather than an unpredictable one.  Starting
	  from "no worse than before" is cheap here and worth having.
	*/
	SV_ViewEyeAt(e, e.origin + e.view_ofs);

	// And the clock stops, so opening a replay mid-attempt costs nothing.  Only
	// asks: SV_TimerFreezeFrame does the arithmetic, at a `time` this hook does
	// not have -- a client command runs at physicstime and a usercmd at sv.time,
	// which is the build 18 finding.
	SV_TimerFreeze(e);
};

/*
===========================================================================
  GHOST.  Build 30.  The third mode, and the one that is not a pin.

  `rec_ghost 1` detaches the player's CAMERA and leaves the body running.  It is
  here, beside the other two, because the three have to refuse each other and
  because a reader looking for "what can take a player out of ordinary play"
  should find all of them in one place.  It is otherwise their opposite:

      save-lock hold   MOVETYPE_NONE, velocity zeroed, clock frozen
      replay pin       MOVETYPE_NONE, velocity zeroed, clock frozen
      ghost            NOTHING TOUCHED.  The body keeps its movetype, its
                       velocity and its clock, and goes on surfing unattended.

  SO THERE IS NO MOVETYPE TO STORE AND NO RELEASE TRAP.  The bug both of those
  carry -- MOVETYPE_NONE is 0, so a stored 0 has to be restored as WALK or the
  player is left pinned with nothing holding them -- cannot arise here, because
  nothing is ever stored.  That is worth saying out loud rather than leaving as
  an absence, because the obvious way to write a third mode is to copy the
  second one.

  IT STILL REFUSES UNDER THE OTHER TWO, for a different reason than they refuse
  each other.  Not contention over the movetype -- ghost wants none -- but
  because both of them mean the body is FROZEN, and a ghost of a body that
  cannot move is a worse `replay` with none of its controls.  The client also
  refuses to fly while either is open.

  WHAT IT DOES NOT DO, deliberately: it does not mark the run practice.  A
  ghosted run stays valid and is MARKED instead, via TF_GHOST and a pair of
  records in the .rec -- see SV_TimerGhostMark and the essay in sh_defs.qc.
  Ghosting is close to self-policing (a body with no hands on it does not
  survive most maps for long), and where it is not, the marker is what lets a
  leaderboard decide later without re-recording anything.
===========================================================================
*/
void(entity e, float on) SV_GhostSet =
{
	if (!on)
	{
		if (!e.rec_gh_on)
			return;

		e.rec_gh_on = FALSE;
		SV_ViewEyeDetach(e);

		/*
		  The swept test's far end, one last time.  Every ghosted tick warped it
		  already (see the gate in SV_TimerFrame), so this is belt and braces
		  rather than the mechanism -- but the cost is two assignments and the
		  failure it guards against is a run being silently finished by a segment
		  drawn across the map.
		*/
		SV_TimerWarped(e);
		SV_TimerGhostMark(e, FALSE);

		sprint(e, PRINT_HIGH, "^5ghost off^7 -- back in your body\n");
		return;
	}

	if (e.rec_gh_on)
		return;

	if (e.rec_sl_hold)
	{
		sprint(e, PRINT_HIGH, "^3ghost: let go of the save-lock key first\n");
		return;
	}
	if (e.rec_wt_hold)
	{
		sprint(e, PRINT_HIGH, "^3ghost: stop the replay first\n");
		return;
	}

	e.rec_gh_on = TRUE;

	/*
	  BUILD 43: the ghost camera has the same stale-PVS defect a replay does, and
	  for the same reason -- rec_gh_camorg is a client-side setproperty and the
	  server is not told about it either.  It is MILDER here only because the
	  body is still moving and so the stale PVS at least drifts, which is why it
	  was never the report.  Same eye, same one-owner rule: a ghost has already
	  refused under a watch four lines above.
	*/
	SV_ViewEyeAt(e, e.origin + e.view_ofs);

	// Mark the recording BEFORE the first ghosted tick is sampled, so the
	// marker sits ahead of the samples it describes rather than one inside them.
	SV_TimerGhostMark(e, TRUE);

	if (e.run_t_state == TS_RUNNING)
		sprint(e, PRINT_HIGH,
		       "^5ghost^7 -- your body is still running; the clock has not stopped\n");
	else
		sprint(e, PRINT_HIGH, "^5ghost^7 -- `ghost` again to go back\n");
};

/*
  Per tick, from PlayerPostThink.  Not the pin any more -- MOVETYPE_NONE is the
  pin.  This is the two things freezing alone cannot do.
*/
void(entity e) SV_SaveLocHoldFrame =
{
	local vector o;

	if (!e.rec_sl_hold)
		return;

	// The list can shrink underneath a hold (3 deletes it, and the menu stays
	// up while you hold 2).  Let go rather than stay frozen against a row that
	// is no longer part of the list.
	if (rec_sl_n <= 0 || e.rec_sl_holdrow < 0 || e.rec_sl_holdrow >= rec_sl_n)
	{
		SV_SaveLocRelease(e);
		return;
	}

	/*
	  A frozen player is not an unmovable one: a teleport zone still calls
	  setorigin on them, and so does anything else in this tree that moves a
	  player without asking pmove.  Re-place only when the origin has actually
	  drifted, so the ordinary case sends nothing and cannot re-introduce the
	  per-tick snapping this rewrite exists to remove.
	*/
	o = rec_sl_org[e.rec_sl_holdrow];
	if (e.origin != o)
		SV_SaveLocPlace(e, e.rec_sl_holdrow);

	e.velocity = '0 0 0';

	// Re-asserted every tick for the same reason the origin above is: the LIST
	// can move under a stationary hold (a delete slides every later row down by
	// one), so the row's velocity has to be re-read rather than remembered.
	SV_SaveLocHoldVel(e);
};

/*
  Delete.  The three files go; the DIRECTORY stays.

  QC has no way to remove a directory -- there is no builtin for it and the
  write sandbox would not reach one anyway -- so an emptied save07/ is left
  behind.  That is deliberately harmless rather than merely tolerated: the scan
  keys on state.txt, so a folder without one is not a save, its id is free for
  reuse, and the next create writes straight back into it.  The cost is one
  directory entry.
*/
void(entity e, float n) SV_SaveLocDelete =
{
	local float i, id, r;
	local entity p;

	/*
	  PATCH 270, STAGE 2 -- the one function in this file that calls fremove.

	  Gating the scan makes the list empty on a map that LOADS as a lobby, and
	  that covers the ordinary case.  It cannot cover the other one:
	  Lobby_NoSaveLoc reads its cvars live, deliberately, so an operator who
	  practises with lobby_enable 0 and then types `lobby_enable 1` still has a
	  populated in-memory list -- create refused, delete wide open.

	  Refused here rather than trusted to be unreachable.  This is the last line
	  before four files per row are removed from somebody's disk, and "the list
	  should be empty by now" is exactly the reasoning that left this hole in
	  the first place.  SV_SaveLocDeleteAll loops this function, so it is
	  covered by the same test.
	*/
	if (Lobby_NoSaveLoc())
	{
		sprint(e, PRINT_HIGH,
		       "^3save: save points are off in a public lobby -- the list is "
		       "shared, so this would delete someone else's.\n");
		return;
	}

	if (rec_sl_n <= 0)
	{
		sprint(e, PRINT_HIGH, "^3save: nothing saved on this map\n");
		return;
	}

	if (n < 1) n = 1;
	if (n > rec_sl_n) n = rec_sl_n;

	r  = n - 1;
	id = rec_sl_id[r];

	/*
	  Anyone parked at or after this row lets go FIRST.

	  The bounds check in SV_SaveLocHoldFrame only catches a row that has fallen
	  off the end -- and the rows below the deleted one all slide down, so a hold
	  on row 4 of 6 would survive the delete of row 2 and silently re-place the
	  player at what used to be row 5.  Being teleported to a different save
	  because someone deleted an earlier one is exactly the class of thing that
	  looks like the save list being corrupt.
	*/
	p = world;
	while ((p = find(p, classname, "player")))
		if (p.rec_sl_hold)
			if (p.rec_sl_holdrow >= r)
				SV_SaveLocRelease(p);

	/*
	  state.txt FIRST.  It is the file the scan keys on, so if the process dies
	  between these the slot is already gone from the list rather than half
	  present -- and the orphans are overwritten by the next create that reuses
	  the id.

	  FOUR files as of build 20, and the fourth is not optional.  seq.txt is
	  written by the client, so nothing else here would ever remove it; left
	  behind, it would pair with the fresh state.txt of whatever save next reused
	  this id and restore ANOTHER attempt's segment column.  That is the failure
	  class Rec_ViewRetry's own fremove essay describes: it does not look broken,
	  it looks like it worked.
	*/
	fremove(SL_StatePath(id));
	fremove(SL_RecPath(id));
	fremove(SL_ViewPath(id));
	fremove(SL_SeqPath(id));

	for (i = n; i < rec_sl_n; i = i + 1)
	{
		rec_sl_org [i - 1] = rec_sl_org [i];
		rec_sl_vel [i - 1] = rec_sl_vel [i];
		rec_sl_pit [i - 1] = rec_sl_pit [i];
		rec_sl_yaw [i - 1] = rec_sl_yaw [i];
		rec_sl_duck[i - 1] = rec_sl_duck[i];
		rec_sl_id  [i - 1] = rec_sl_id  [i];
		rec_sl_seq [i - 1] = rec_sl_seq [i];
		rec_sl_tick[i - 1] = rec_sl_tick[i];
		rec_sl_seg [i - 1] = rec_sl_seg [i];
		rec_sl_cps [i - 1] = rec_sl_cps [i];
	}

	rec_sl_n = rec_sl_n - 1;

	if (e.rec_sl_index > rec_sl_n)
		e.rec_sl_index = rec_sl_n;
	if (rec_sl_n > 0 && e.rec_sl_index < 1)
		e.rec_sl_index = 1;

	// Build 25: silent when a delete-all is driving, which would otherwise print
	// one "saves: 39/39" line per row and bury its own summary.
	if (!rec_sl_quiet)
		SV_SaveLocSay(e);
};

/*
  Previous / next, and THEY LOAD.

  They used to move the cursor and leave you where you were, so cycling to the
  save you wanted took 4,4,4,2 -- and the only way to find out which one 3/7
  actually was, was to load it.  Stepping now teleports you there, which makes
  4 and 5 a walk backwards and forwards along the saves themselves.  Requested;
  and it also makes "Load Save" honest, since it is now the only key that does
  something 4 and 5 do not.
*/
void(entity e, float dir) SV_SaveLocStep =
{
	if (rec_sl_n <= 0)
	{
		SV_SaveLocSay(e);
		return;
	}

	e.rec_sl_index = e.rec_sl_index + dir;

	// Wrap rather than clamp: the menu's 3/4 are a two-key cycle through a
	// short list and stopping dead at the ends makes it feel broken.
	if (e.rec_sl_index < 1)          e.rec_sl_index = rec_sl_n;
	if (e.rec_sl_index > rec_sl_n)    e.rec_sl_index = 1;

	SV_SaveLocLoad(e, e.rec_sl_index);
};

/*
  First and last.  Build 25, and they are Step's siblings rather than a different
  kind of thing: Momentum's menu offers all four, and if 3 and 4 teleport then 5
  and 6 have to as well or two of the four navigation keys would silently mean
  something else.  SV_SaveLocLoad clamps its argument, so an empty list is the
  same refusal it already prints.
*/
void(entity e) SV_SaveLocFirst =
{
	if (rec_sl_n <= 0) { SV_SaveLocSay(e); return; }
	SV_SaveLocLoad(e, 1);
};

void(entity e) SV_SaveLocLast =
{
	if (rec_sl_n <= 0) { SV_SaveLocSay(e); return; }
	SV_SaveLocLoad(e, rec_sl_n);
};

/*
  Delete every save on this map.

  IT DELETES FROM THE END, one row at a time, through SV_SaveLocDelete.  A loop
  that removed the files itself and then set rec_sl_n = 0 would be shorter and
  would skip three things that function does and that this one needs just as
  much: it drops every hold whose row is going away (otherwise a player parked on
  save 4 stays frozen against an array that no longer describes anything), it
  removes ALL FOUR files including the client-written seq.txt (an orphan seq.txt
  pairs with the next save that reuses the id and restores another attempt's
  segment column -- the failure Rec_ViewRetry's essay describes, which does not
  look broken, it looks like it worked), and it keeps the cursor inside the list
  as it shrinks.

  From the END so the slide-down inside SV_SaveLocDelete never has anything to
  move: deleting row 1 of 40 copies 39 rows down, forty times over, for a list
  that is about to be empty.

  The CONFIRMATION IS THE CLIENT'S, deliberately.  This is the one action in the
  menu with nothing to undo it and 7 and 8 are adjacent keys, so the second press
  is required -- but the arm is a 3-second timer belonging to one player's
  keyboard, and putting it here would mean a per-player timer field on the server
  for a decision the server does not otherwise take part in.  A console
  `cmd sl_delall` is deliberately NOT gated: the console is already the place
  where you mean what you type.
*/
void(entity e) SV_SaveLocDeleteAll =
{
	local float n;

	if (rec_sl_n <= 0)
	{
		sprint(e, PRINT_HIGH, "^3save: nothing saved on this map\n");
		return;
	}

	/*
	  PATCH 270, STAGE 2 -- BEFORE THE LOOP, and the loop is now guarded too.

	  Adding the lobby refusal to SV_SaveLocDelete alone HUNG THE SERVER.  The
	  loop below is `while (rec_sl_n > 0) SV_SaveLocDelete(...)` and its only
	  termination condition is that the callee shrinks the list.  Give the
	  callee a reason to decline and it spins forever, inside a QC frame, taking
	  the whole server with it -- and the case that reaches it is exactly the
	  one the refusal was added for: a host who practised offline, so the list
	  is populated, and then turned the lobby on.

	  Two changes rather than one.  This gate stops it happening; the progress
	  check in the loop stops the NEXT reason a delete might decline from doing
	  the same thing.  A loop whose exit depends on a callee's side effect
	  should not trust the callee.
	*/
	if (Lobby_NoSaveLoc())
	{
		sprint(e, PRINT_HIGH,
		       "^3save: save points are off in a public lobby -- the list is "
		       "shared, so this would delete someone else's.\n");
		return;
	}

	n = rec_sl_n;

	rec_sl_quiet = TRUE;
	while (rec_sl_n > 0)
	{
		local float before;
		before = rec_sl_n;
		SV_SaveLocDelete(e, rec_sl_n);
		if (rec_sl_n >= before)
			break;                  // declined or failed: stop, do not spin
	}
	rec_sl_quiet = FALSE;

	// What was actually removed, not what was planned.  They differ if the
	// loop broke early, and printing the plan would claim a deletion that did
	// not happen.
	n = n - rec_sl_n;

	sprint(e, PRINT_HIGH, sprintf("^1deleted^7 all %g save state(s) on %s\n", n, mapname));
};

void(entity e) SV_SaveLocList =
{
	local float i;
	local vector o, v;

	if (rec_sl_n <= 0)
	{
		sprint(e, PRINT_HIGH, "saveloc: nothing saved on this map\n");
		return;
	}

	sprint(e, PRINT_HIGH, sprintf("saveloc: %g saved on %s, current %g\n",
	                              rec_sl_n, mapname, e.rec_sl_index));
	for (i = 0; i < rec_sl_n; i = i + 1)
	{
		// An array element is not an lvalue fteqcc will swizzle, so both of
		// these need a real local -- the same thing SV_ZoneMove needs for
		// zone_centre.  And three prints, because varargs cap at 8.
		o = rec_sl_org[i];
		v = rec_sl_vel[i];

		sprint(e, PRINT_HIGH,
		       sprintf("  %s%2g^7 slot %s  %6.0f %6.0f %6.0f  ",
		               (i + 1 == e.rec_sl_index) ? "^2" : "^7", i + 1,
		               SL_NN(rec_sl_id[i]), o_x, o_y, o_z));
		sprint(e, PRINT_HIGH,
		       sprintf("%4.0f u/s  yaw %4.0f  %s  ",
		               vlen([v_x, v_y, 0]), rec_sl_yaw[i],
		               rec_sl_duck[i] ? "ducked" : "standing"));
		sprint(e, PRINT_HIGH,
		       sprintf("%s  stage %g  %g cp\n",
		               (rec_sl_tick[i] > 0) ? SV_TimerString(rec_sl_tick[i]) : "--",
		               rec_sl_seg[i] + 1, rec_sl_cps[i]));
	}
};

/*
===========================================================================
  `retry` -- restart the map's entities without moving the player

  The gesture is Source's: put me back into the game I am already in.  On a
  listen server that is a map reload, which is the surf-practice move -- doors,
  platforms, buttons and the run you triggered by accident all go back to their
  spawn state.  Engine Patch 167 made the command do that.  What it did NOT do
  was keep you where you were, so a retry mid-run cost you the run and the
  walk back, which made it useless for the thing it exists for.

  THIS IS A SAVE STATE WITH A DIFFERENT LIFETIME, and almost none of it is new
  code.  Build 17 already writes origin, velocity, angles, duck, the whole timer
  block, the four occupancy latches, the run splits and the recorder's mark to a
  text file, and already reads them back.  A retry point is that file, parked in
  slot 0, consumed once, and deleted.

  WHY DISK, when this is the same process.  SV_SpawnServer calls PR_Deinit, so
  every SSQC global and every edict is destroyed; on the client side
  CLQW_ParseServerData calls CSQC_Shutdown unconditionally, so the CSQC VM and
  its sidecar buffer go too.  Nothing survives a map_restart in either VM.  Disk
  is not a convenience here, it is the only channel there is.

  THE ORDERING IS NOT A RACE, which is worth stating because it looks like one.
  CL_Retry_f offers the command to CSQC and PR_ExecuteProgram runs QC to
  completion -- so the client's fopen/buf_writefile/fclose of its sidecar is on
  disk before the builtin even returns.  Only then does QC ask the server, via a
  reliable stringcmd, and only then does the server restart the map.  There is
  no interleaving available.

  The honest shortfall: the sidecar covers the run to the KEYSTROKE and the .rec
  covers it to the moment the server handled the command, one client frame and
  one round trip later -- so 1-2 ticks of .rec have no camera behind them.  The
  exact fix is an ack with a timeout, on a gesture that has to feel instant.
  Not worth it; recorded here so the gap is known rather than discovered.
===========================================================================
*/

/*
  rec_retry_armed -- latched from a cvar in SV_TimerMapInit, this map only.  A
  GLOBAL because PR_Deinit zeroes it, which makes it per-map for free.  It is
  DECLARED in sv_timer.qc, which sv_progs.src compiles first and which is where
  the latch happens; this is the code that owns it.

  A map_restart is already queued.

  sv.mapchangelocked guards the changelevel BUILTIN, not localcmd, so two
  `retry`s arriving in the same frame would queue two restarts -- and the second
  would find the point already consumed and simply restart the map again, which
  reads as the command being flaky.  Zeroed by PR_Deinit, so per-map for free.
*/
float rec_retry_sent;

void(entity e) SV_RetryPoint =
{
	local entity p;
	local float n;

	if (!cvar("rec_retry"))
	{
		sprint(e, PRINT_HIGH, "^3retry: disabled (rec_retry 0)\n");
		return;
	}
	if (e.classname != "player")
		return;
	if (rec_retry_sent)
		return;

	/*
	  ONE PLAYER ONLY.  A retry restarts the map for everyone on the server, so
	  "whose position is restored" has no good answer with more than one person
	  connected -- and silently restoring the person who typed it while throwing
	  everyone else back to spawn is worse than refusing.  Single-player is what
	  this build is, so this is a guard rather than a limitation.
	*/
	n = 0;
	p = world;
	while ((p = find(p, classname, "player")))
		n = n + 1;
	if (n > 1)
	{
		sprint(e, PRINT_HIGH,
		       "^3retry: restarts the map for everyone -- not while others are connected\n");
		return;
	}

	/*
	  LET GO FIRST, and this is not politeness.

	  A save-lock hold zeroes the velocity (SV_SaveLocHold) and keeps it zero
	  every tick, and only SV_SaveLocRelease hands the real one back.  Writing
	  the state under a hold would restore you standing still, silently
	  discarding the speed you had -- and it would write TF_FROZEN into a file
	  with no client left alive to ever send sl_holdoff.  Releasing here makes
	  "retry while parked" mean "let go, then retry", which is the only sane
	  reading of it.
	*/
	SV_SaveLocRelease(e);

	SV_SaveWriteState(e, FS_RETRY_SLOT, 0);

	rec_retry_sent = TRUE;
	cvar_set("rec_retry_armed", "1");
	localcmd("map_restart\n");
};

/*
  Consume the retry point.  Called at the END of PutClientInServer, which is the
  first moment at which this player exists AND the map's zones are loaded.
*/
void(entity e) SV_RetryApply =
{
	/*
	  run_t_tick comes from SV_TimerMapInit, and SV_TimerResume EARLY-RETURNS if
	  it is still zero -- so getting here first would restore the position and
	  the splits and silently not restore the CLOCK, which is the one thing a
	  retry is for.  The ordering is in fact guaranteed (SV_SpawnServer runs two
	  physics frames before any client is put in), but this is one compare
	  against a silent failure, and it is the idiom sv_zones.qc already uses.
	*/
	if (!zone_loaded)
		SV_ZoneFrame();

	if (!rec_retry_armed)
		return;

	// Exactly once, whatever happens below -- a second player spawning must not
	// re-consume it, and a failed read must not leave it armed for the next map.
	rec_retry_armed = FALSE;

	if (!SV_SaveApplyState(e, FS_RETRY_SLOT, TRUE))
	{
		sprint(e, PRINT_HIGH, "^3retry: the saved state could not be read\n");
		return;
	}

	SV_SaveLocEvent(e, SLOP_RETRY, FS_RETRY_SLOT);

	/*
	  state.txt first, for the reason SV_SaveLocDelete gives: it is the file the
	  scan keys on, so a crash between these two leaves an orphan .rec rather
	  than a state the reader would try to pair with a missing recording.

	  THE .view IS NOT OURS TO DELETE.  The client has not read it yet -- it
	  learns to, from the stat event above, on its NEXT RENDERED FRAME, which is
	  strictly after this runs.  Removing it here is the one ordering mistake
	  that would make the camera track silently vanish with nothing to show for
	  it.  The client removes its own, on the next retry.
	*/
	fremove(SL_StatePath(FS_RETRY_SLOT));
	fremove(SL_RecPath(FS_RETRY_SLOT));

	if (e.run_t_state == TS_RUNNING)
		sprint(e, PRINT_HIGH,
		       sprintf("^5retry^7 -- run restored at ^5%s^7\n",
		               SV_TimerString(e.run_t_ticks)));
	else
		sprint(e, PRINT_HIGH, "^5retry^7 -- back where you were\n");
};
