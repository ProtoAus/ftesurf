/*
===========================================================================
  sv_timer.qc -- the run timer, its splits, and the tick recorder.

  WHY THIS IS SERVER-SIDE AND NOT IN THE HUD

  Zone entry is a question about the AUTHORITATIVE origin.  CSQC has the
  same zone tables (both VMs parse the same file with the same code, see
  sh_zones.qc) and could answer it -- but it would be answering it about an
  interpolated, predicted position at the render rate, which is a different
  number from the one the server's own physics produced.  A timer that
  disagrees with the server about whether you crossed the line is worse than
  no timer.  So the state machine lives here and the HUD is a pure view over
  eleven stats.

  WHAT MOMENTUM ACTUALLY DOES, and what this reproduces

    start zone    surf starts when you LEAVE it, not when you enter.
                  (CTriggerTimerStart::OnEndTouch.)  Direction does not
                  matter: walking out the back of the start starts your run,
                  which is why every start zone is a closed box.  Bhop is the
                  deliberate exception: a grounded initial jump made inside
                  the start starts (or restarts) the clock on that tick, while
                  leaving the box remains the no-jump fallback.
    end zone      the timer stops the instant you ENTER it.
    stage zones   entering stage N's zone records a split and opens segment N.
    checkpoints   recorded, but not shown -- in Momentum they exist to
                  compare against, not to read while you are moving.
    cancel zones  entering one voids the run outright.

  Momentum times in INTEGER TICKS (m_iEndTick - m_iStartTick), and so does
  this: the stat, the file and the personal best are all tick counts, and
  only the display ever divides by the tick rate.  Anything else turns every
  comparison into an argument about rounding.

  ONE HONEST DIFFERENCE.  A tick here is measured as
  round((time - start) / pm_ticrate) rather than counted, because QC has no
  view of the engine's physics tick counter.  PM_PlayerMove runs a whole
  number of ticks per usercmd and `time` advances by the server frame, so
  the two agree to within one tick and the error does not accumulate --
  but it is a derived number and not the engine's own, and that is worth
  saying rather than implying otherwise.

  THE RECORDER

  Streamed to disk, not buffered in QC.  fopen(FILE_WRITE) accumulates into
  an engine-side buffer that grows by DOUBLING (pr_bgcmd.c:3114), so the
  whole run is one amortised O(n) append and none of it costs progs global
  space.  A five minute run is about 1.5 MB of text.

  The pre-start padding you asked for is a ring that is ALWAYS running --
  see rec_pad_* below -- and is flushed into the file at the moment the timer
  starts, with negative timestamps.  That is what makes a playback able to
  show the launch rather than starting with you already at speed.
===========================================================================
*/

// Segments per track.  surf_classics3 is the library's worst at 11 bonuses;
// the deepest single track measured is 10 segments, so 24 is a wide margin.
#define FS_MAXSPLITS   24
#define FS_MAXTRACKS   12       // main + up to 11 bonuses

/*
  Checkpoints per track.  Build 19.

  EQUAL TO FS_MAXSPLITS ON PURPOSE, and it is load-bearing rather than tidy:
  SV_PBLoad bounds-checks its second field against FS_MAXSPLITS BEFORE it
  dispatches on the keyword, so an equal cap means the existing guard covers the
  new `cp` line with no change to the reader at all.  Change one and you must
  change the other, or a checkpoint row past the smaller bound is silently
  dropped on load and silently written on save.

  The library's heaviest map is well inside this: 1455 checkpoint regions across
  535 zone files, and several regions usually make up one logical checkpoint.
*/
#define FS_MAXCPS      24

/*
  How long continuously airborne counts as "the start is over".  Build 19, item 3.

  DERIVED FROM THE HANG TIME, and the first version was not -- it used a flat
  0.4s and was wrong for a reason the very first test showed:

      RUN 3: hop out of the start
      timer: armed ... practice 0 ... start: ok 1

  0.4s is SHORTER than a single jump's flight, so the first, entirely legal jump
  settled the start while the player was still in the air, and every hop after it
  went unexamined.  The threshold has to clear one jump and not two.

  A jump leaves the ground at the Source impulse and comes back under gravity, so
  the hang time is 2*v/g -- 0.67s at 268.33 and 800.  x1.5 gives a margin without
  reaching the second hop of a chain, which lands at one hang time.  Scaled off
  sv_gravity rather than hard-coded because a low-gravity server doubles the
  flight and would have every legal start read as a hop.

  Clamped because sv_gravity is a cvar anyone can set to 1.
*/
#define FS_JUMPIMPULSE 268.3281572999747
#define FS_SETTLEMARGIN 1.5
#define FS_SETTLEMIN   0.5
#define FS_SETTLEMAX   4.0

/*
  How many players get a split row.  Was 4, and 4 was the whole reason the fifth
  player onwards got a working clock with no splits, no checkpoints, no .rec and
  no message saying why -- fine for a training tool, not fine for a 32-player
  lobby.  PATCH 270, STAGE 2 raises it to 32.

  FS_PADSLOTS STAYS AT 4, AND THE REASON IS MEASURED RATHER THAN ASSUMED.

  These two used to be one number.  Raising both looked free -- the split and
  checkpoint rows are 24 floats per player, so 32 of them is 6 KB -- but the
  pre-start padding ring is 9 parallel arrays x 256 samples PER PLAYER, and
  fteqcc does not store a QC array as plain data.  It emits an accessor with a
  dispatch whose size is O(the array's LENGTH), so length costs roughly 8x what
  the data does.

  Measured on this tree, changing nothing but this define:

      FS_PADSLOTS 4  ->  qwprogs.dat  1,078,102 bytes
      FS_PADSLOTS 8  ->  qwprogs.dat  1,641,738 bytes

  563 KB for four more rings whose actual contents are 68 KB.  Thirty-two would
  have been several megabytes of progs, parsed again by every mapcluster child.

  What the fifth player onward loses is ONLY the pre-start padding -- the 3.84 s
  of approach that gets prepended to a recording.  They still get a timer,
  splits, checkpoints and a .rec; SV_RecPadBase returns -1 and SV_RecPadFlush
  writes nothing.  And in a lobby it is moot in both directions, because
  lobby_norec turns the recorder off entirely and the ring exists only to feed
  it.  So this is today's behaviour preserved exactly, not a new limit.

  32 rather than the engine's MAX_CLIENTS on purpose: it is also the width of
  the trigger touch masks in sv_entities.qc, and having the two caps be the same
  number means there is no partially-covered range for a bug to hide in.
*/
#define FS_MAXPLAYERS  32
#define FS_PADSLOTS    4

// 256 samples is 3.84s at 66.67Hz.  Measured in SAMPLES rather than seconds
// because it is a ring: the array size is the cap, and expressing it in
// seconds would make the memory a function of pm_ticrate.
#define FS_RECPAD      256

/*
  Lines one recording may hold.  TWO CAPS SINCE BUILD 80, because the two
  recorders have genuinely different limits and only one of the limits is ours.

  THE OLD SINGLE CAP WAS COSTED AT THE WRONG RATE, WHICH IS THE WHOLE BUG.
  This comment read "50 minutes at 66.67 Hz".  That is true, and it is the SURF
  case; nobody re-costed it when bhop maps shipped at 100 Hz.  A bare line count
  is a duration divided by a rate; when the rate moved, the constant did not,
  and nothing said so.  Both numbers below therefore state the rate they were
  costed at and what they buy at the others.

  BUILD 80 THEN COSTED IT AT THE WRONG RATE AGAIN, ONE BUILD LATER, IN THE SAME
  SHAPE.  It measured bhop_monster_jam/main/cheat.rec -- 58,396 lines over
  647.2 s -- called that 90.2 lines/s, and sized 200,000 at 37 minutes.  The
  arithmetic is right and THE FILE IS WRONG FOR THE PURPOSE: it holds 58,353
  samples against an `end` of 64,724 ticks, a ratio of 0.898, so about a tenth
  of that run is FROZEN.  SV_TimerRecFrame deliberately writes no sample while
  frozen, and says so thirty lines from here, CITING THIS CAP AS THE REASON.  So
  build 80 calibrated a line cap on the one kind of run whose line rate is
  deliberately suppressed, while quoting the mechanism that suppresses it.  The
  baseline came out ~15% low.

  MEASURED PROPERLY, over the 97 recordings in data/runs: every clean 100-tick
  run reads 100.6-104.2 lines/s with samples/ticks EXACTLY 1.000 (twelve files),
  the long ones settling at ~104, and 97.62 bytes/line corpus-wide.  The only
  two files below 100 are the two cheat.rec captures, and they are the two with
  freezes in them.  Corrected, at 104 lines/s:

      200,000 (the pre-80 cap) ......  32 minutes, not 37
      1,000,000 (BUF) ...............  2.7 hours, not 3.1
      8,640,000 (build 80's STREAM) .  23.1 hours, not 26.6

  THE FOURTH LINE IS THE ONE THAT MATTERS.  8,640,000 was 12 h * 3600 * 200/s,
  and 200/s was "100 Hz packets plus a 100 Hz input trace".  With the sampler
  measured at 104 rather than 90, that pair is 204/s, and 8,640,000 / 204 is
  11.76 HOURS -- under the twelve the constant is named for.  The term also
  budgeted exactly zero lines for the header, for the FS_RECPAD ring of up to
  256, and for every board/cp/stage/split/end record, so the shortfall was
  structural and not marginal.  Hence 220 below, not 200.

  BUFFERED: 1,000,000, AND THIS ONE IS NOT A NUMBER WE CHOSE.  bufstr_set
  REFUSES an index past 1024*1024 with only a PR_RunWarning (pr_bgcmd.c:5566),
  so the buffer physically cannot hold more; the cap exists to turn a silent
  truncation into one we announce.  1,000,000 rather than 1,048,575 so that the
  margin is visibly deliberate rather than exact-to-the-limit.  At the measured
  104 lines/s that is 2.7 hours.  A RUN YOU CAN REWIND IS CAPPED BY THE BUFFER
  and it cannot
  be otherwise: a save-state resume rewinds to a mark and appends from there,
  which is random access, which is the one thing a stream cannot do.  That is
  why this path still exists at all.

  STREAMED: 9,504,000 = 12 hours * 3600 * 220 lines/s, and every term is load
  bearing.  220/s is built from measurements and not from a round number: 104
  for the per-packet sampler (measured, above), ~100 for the per-step input
  trace Phase 3 needs, and ~16 for everything the old term forgot -- the header,
  the padding ring, and the board/cp/stage/split/end records.  At today's rate,
  with no step trace yet written, it is 25.4 hours; at surf's 66.67 Hz, 38.3.

  A FREEZE IS THE ONE STATE WHERE THE TWO TERMS DISAGREE, and it is worth
  writing down before the step trace lands: while run_t_frzon the sampler writes
  NOTHING by design, so the combined rate falls from ~204 to ~100 rather than
  rising.  A save-state hold therefore cannot blow this cap faster than running
  does -- but it does spend budget for zero run time, which is the opposite of
  what the sampler's own freeze gate was written to achieve.  The step trace has
  to record frozen commands anyway, because the mover still runs ticks during
  them (pm_source.c dispatches pm_type INSIDE the tick), and a clock that
  excludes them can only be derived if they are present to exclude.

  The stream has no engine limit of any
  kind: FRIK_FILE_WRITESTREAM is a plain FS_OpenVFS(name, "wb")
  (pr_bgcmd.c:2835-2841) with no index and no array behind it, so nothing here
  is protecting a data structure.  It protects the disk and the counter.

  THE COUNTER IS THE CEILING THAT CANNOT BE RAISED HERE, and it is why the
  budget is twelve hours and not twenty-four.  rec_rec_lines is a QC float, i.e.
  IEEE single, so consecutive integers stop being representable at
  2^24 = 16,777,216 -- past that `n + 1 == n`, the line count FREEZES, and the
  file goes on growing underneath it.  That failure is silent in the worst way:
  the counter reads plausible and the `end` trailer's sample count reads
  plausible, and only counting the bytes disagrees.  9,504,000 is 56.6% of it,
  so the margin is 1.77x -- smaller than build 80's claimed "factor of two",
  which is the honest price of the re-costing above and is stated rather than
  rounded away.  Two more walls sit above and would also have to move: the
  7-digit <ticks7> filename stamp (9,999,999 ticks = 27.8 hours at 100 Hz) and
  the `t` column itself, which is a float holding seconds and is down to a ~4 ms
  quantum by 43,200.

  COST, measured rather than estimated: 97.62 bytes/line across the 97 real
  files in data/runs (27.4 MB over 280,981 lines).  Twelve hours at today's 104
  lines/s is ~439 MB on disk and ~54 MB at rest under xz -6 (8.20x, measured;
  -9e gets 8.27x, i.e. 0.8% for several times the CPU, which a NanoPi should not
  pay).  With the step trace it is roughly 700 MB and ~85 MB at rest -- ROUGHLY,
  and flagged as such, because a step row is about 60 bytes rather than 97.6 and
  that record does not exist yet.  Build 80's "492 MB" reconciled with neither
  its own bytes/line nor its own rate and is withdrawn.  These are the numbers
  the retention policy has to answer for, not this cap.
*/
#define FS_RECMAX_BUF     1000000
#define FS_RECMAX_STREAM  9504000

/*
  Two builtins the platform dump does not declare.

  pr_dumpplatform only emits a prototype for a builtin that carries one of the
  extension group flags, and fcopy/frename/fremove/fexists carry none
  (pr_cmds.c:12318-12321) -- so they are absent from defs/sv_defs.qc even
  though the engine has had them all along.  Named rather than numbered
  (`#0:frename` resolves by name at load) so a renumber upstream cannot turn
  this into a silent call to the wrong builtin.

  fcopy is deliberately NOT declared: it writes to its SOURCE path, which
  truncates the file you asked it to copy.  See ENGINE_PATCHES.md Patch 143.

  BOTH ARE CURRENTLY UNCALLED, and that is new: v3 writes the recording once,
  straight to its final name, so there is no .part to rename and none to remove.
  They stay declared because the save-state slots are next and delete files.
*/
float(string src, string dst) frename = #0:frename;
float(string fname) fremove         = #0:fremove;

/*
  Patch 419 (engine): the OS entropy the master-server challenge code already
  uses, reached by NAME so no builtin number is claimed.  QuakeC `random()` is
  `(rand()&0x7fff)/32768` from a once-seeded `rand()`, and TWO things here need
  better: the per-run nonce, and the randomized start -- whose offset this file
  PUBLISHES to four decimals in every header, a step of 4/32768 at
  `run_startjitter 2`, so each printed value names its own draw to within one
  count.  Engines before 419 lack both builtins; checkbuiltin gates every call
  and the callers fall back to random() rather than failing a run.
*/
string(float bytes) fs_randomhex = #0:fs_randomhex;
float() fs_randomf               = #0:fs_randomf;

// Patch 375 (engine): a byte range onto a file, or onto an open FILE_WRITESTREAM.
// Engines before 375 lack both; checkbuiltin gates every call.
int(string src, int ofs, int len, string dst, float append) fcopyrange = #0:fcopyrange;
int(filestream fh, string src, int ofs, int len) fappendrange = #0:fappendrange;

/*
  buf_create, with the arguments the platform dump's prototype leaves off.

  defs/sv_defs.qc declares it as `strbuf() buf_create` -- no parameters -- but
  the builtin takes two: a type and a flags word.  The flags word DEFAULTS TO
  BUFFLAG_SAVED (pr_bgcmd.c PF_buf_create), which means a buffer created the
  short way is serialised into savegames.  A recording is up to FS_RECMAX_BUF lines
  of text, and putting that in a savegame is not something anyone asked for.

  Same builtin number, second name: builtins may be declared more than once, and
  this is the only way to reach an argument the shipped prototype hides.
*/
strbuf(string bufclass, float bufflags) buf_create_ex = #460;

float  run_t_tick;               // pm_ticrate, cached per map

/*
  run_zone_swept -- test the SEGMENT travelled, or just the point you ended on.

  1 (default) is correct.  0 restores the point test the timer shipped with in
  build 9, and exists so the difference is falsifiable in one map load rather
  than argued about: on a map with a thin trigger plane, 0 finishes roughly one
  attempt in fifteen and 1 finishes every time.
*/
float  run_t_swept;

/*
  run_zone_hull and run_zone_hull_live, cached per map for the same reason
  run_t_swept is.  Build 47.

  run_t_hullevt is level >= 1: the hull decides "did you leave" and "did you
  touch".  run_t_hullocc is level >= 2: occupancy follows too, which moves every
  stage time on every staged map and is therefore not the default.  Split into
  two flags rather than compared against the level at each site so the hot loop
  does no arithmetic and so the two decisions cannot be conflated by accident --
  they are genuinely different questions, see the essay on SV_ZoneHit.
*/
float  run_t_hull;
float  run_t_hullevt;
float  run_t_hullocc;
float  run_t_hulllive;

/*
  run_prestrafe_time, cached per map.  Build 19.

  The ground dwell that separates a pre-strafe jump from a bhop -- the same
  number that decides whether the client releases +forward for you, which is why
  SV_TimerMapInit publishes it to serverinfo rather than letting each side keep
  its own.  Cached here for the same reason run_t_swept is: SV_TimerJumpWatch runs
  once per player per tick.
*/
float  run_t_dwell;

// The airborne time that settles the start, derived from sv_gravity per map --
// see the FS_SETTLE* block at the top of this file for why it cannot be a
// constant.
float  run_t_settle;

/*
  BUILD 20: run_starthop_strict, cached per map.

  Build 19's hop rule shipped never firing, and this is the switch for the two
  lines that fix it.  The bug was one omission: SV_TimerArm resets run_t_startok
  but NOT run_t_airsec, and nothing outside SV_TimerJumpWatch writes that field --
  so after any teleport that follows a fall (which is every `!r`, every `!s`,
  every map fall-off trigger) the first tick after the arm read an air phase
  seconds old, satisfied the settle at once, and closed the window before the
  player had pressed anything.

  Build 19's own hop test passed because it WALKED into the box.  Nobody walks
  into the box.

  0 is build 19 byte-for-byte, so the pair is a real bisection.
*/
float  run_t_startstrict;

/*
  BUILD 20: run_rearmstops, cached per map.

  Whether arriving back in a start zone mid-run keeps the time on screen in grey
  rather than snapping it to 0:00.000.  Build 19 latched that in SV_TimerVoid,
  which covers `!r` -- but re-entering the box on foot, or being put there by a
  map teleport, reaches SV_TimerArm through SV_TimerTryArm with no void anywhere
  on the path, so there was nothing to latch and nothing to show.

  See SV_TimerTryArm for why the latch has to live THERE and not one level down.
*/
float  run_t_rearmstops;

/*
  BUILD 83: run_startjitter, cached per map.  THE RANDOMIZED START, IN UNITS.

  A GAME RULE AND NOT AN ANTI-CHEAT, and it has to be said in that order because
  the rule has a cost the player can feel: your run begins within this many units
  of where you crossed the line, so ramp-one entry is no longer exactly
  reproducible from one attempt to the next.  That is a real price and it is paid
  by the honest player, which is why it is announced rather than hidden: the
  GAME RULE note over `set run_startjitter` in cfg/default.cfg states it.

  WHAT IT BUYS, stated at its true size.  A movement recorder replays a usercmd
  stream.  Re-simulation cannot refuse one -- it accepts a replayed stream BY
  CONSTRUCTION, which is the plan's own stated limit on Layer 2 -- so the only
  thing that touches an MMR is entering the map somewhere the recording did not.
  Surf is a single continuous momentum path with no recovery move: two units at
  ramp entry compounds through ClipVelocity and does not come back.

  WHY POSITION AND NOT THE SUB-TICK PHASE, which was the design this replaced.
  Seeding msec_carry looked cheaper -- one float already in pmsourcestate_t -- and
  is worthless: the phase is a function of the msec sequence and msec is a
  CLIENT-WRITTEN byte on the shipping clc_move path, so a replayer re-chooses its
  phase by re-choosing its msec.  Position is the one quantity entering the mover
  as STATE rather than as input, so no choice of msec, angles or movement values
  re-derives it.  That is the whole argument and it is why this is the carrier.

  HORIZONTAL ONLY, on purpose.  A vertical nudge changes GROUND CONTACT -- a
  player displaced up leaves the floor for a tick and gets air acceleration where
  they expected friction, which is a bigger felt change than the anti-replay
  property needs and a much larger one than two units of yaw-plane offset.  The
  z component of run_t_jitter is therefore always 0, and the file records the
  zero rather than omitting the column, so a reader never has to know that.

  0 DISABLES IT, and 0 is the pre-83 game byte-for-byte, so the pair is a real
  bisection.  A lobby pins it; see cfg/lobby/lobby.cfg.
*/
float  run_t_startjit;
float  run_t_osrand;        // -1 unknown, 0 random(), 1 the OS.  Latched per map.
float  run_t_osrsaid;       // ...and whether the DEGRADED case has been said yet

/*
  Patch 419: a float in [0,1) from the OS, or `random()` if this engine has no
  such builtin or the OS refused.

  THE BAD NEWS IS SAID LOUDLY AND THE GOOD NEWS QUIETLY, once per map each: the
  healthy branch is a dprint because a working server does not need telling,
  and the DEGRADED branch is a print because "the start jitter is
  unpredictable" stops being true and nobody should have to read the binary to
  discover it.  The case that matters most is new progs on an engine older than
  419 -- checkbuiltin is false, every draw silently falls back, and that is the
  rollout this print exists for.
*/
float() SV_Rand01 =
{
	local float r;

	if (checkbuiltin(fs_randomf))
	{
		r = fs_randomf();
		if (r >= 0)
		{
			if (run_t_osrand != 1)
			{
				run_t_osrand = 1;
				dprint("timer: randomness from the OS (Patch 419)\n");
			}
			return r;
		}
	}
	/*
	  SAID ONCE, ON ITS OWN LATCH.  Two mistakes lived here, both found by
	  review.  The first: `run_t_osrand` is a progs global, so it loads as 0 --
	  the same value this branch used to set -- and the `!= 0` test therefore
	  never fired on the case the print exists for.  A server with no builtin at
	  all ran the whole map on random() and said NOTHING, while the healthy path
	  announced itself.  The latch starts at -1 now (SV_TimerMapInit).
	  The second: one variable cannot latch both messages.  Sys_RandomBytes
	  opens /dev/urandom per call (sv_sys_unix.c), so a refusal is intermittent
	  rather than sticky, and a flag that flips both ways would print on every
	  transition -- up to eight draws per start attempt, per player, unrated.
	*/
	run_t_osrand = 0;
	if (!run_t_osrsaid)
	{
		run_t_osrsaid = TRUE;
		print("timer: NO OS RANDOMNESS -- the start jitter and the run nonce are "
		      "drawn from random(), whose published offsets each name their own "
		      "draw.  Patch 419 is not in force on this engine.\n");
	}
	else
		dprint("timer: OS randomness refused again\n");
	return random();
};

/*
  `bytes` of OS entropy as hex, or the same shape built from SV_Rand01 when the
  engine cannot.  The fallback is not silent (SV_Rand01 says so once) and is
  still worth having for the nonce, which mixes it with wall clock, uptime,
  runid and guid.
*/
string(float bytes) SV_RandHex =
{
	local string s;
	local float i;

	/*
	  BOUNDED HERE, BECAUSE THE TWO PATHS DISAGREED OUTSIDE 1..64.  The builtin
	  clamps to that range and the loop below did not, so a caller asking for 65
	  would have been given 128 hex characters by one path and 130 by the other
	  -- the OS path SHORT, silently.  Both live callers ask for 32 and 16; this
	  is the check SV_RecNonce already applies to the digest one line later, on
	  the value that feeds it.
	*/
	bytes = bound(1, rint(bytes), 64);
	if (checkbuiltin(fs_randomhex))
	{
		s = fs_randomhex(bytes);
		if (strlen(s) == bytes * 2)
			return s;
	}
	s = "";
	/*floor(x*256) and not rint(x*255): rint puts half the weight on 0 and on
	  255 and full weight on the 254 between them.  SV_Rand01 is strictly below
	  1 on both branches, so floor cannot reach 256.*/
	for (i = 0; i < bytes; i = i + 1)
		s = strcat(s, sprintf("%02x", floor(SV_Rand01() * 256)));
	return s;
};

/*
  BUILD 21: run_rearmhop, cached per map.

  Whether a hopped start can be TAKEN BACK by stopping.  Fluff the start -- two
  hops instead of one -- and today the attempt is dead until you physically
  re-enter the start box, because SV_TimerArm is the only thing that clears the
  taint.  With this on, standing on the ground for the pre-strafe dwell forgives
  it and the next jump is judged fresh.

  THE DETECTION IS DELIBERATELY THE ONE THE PLAYER CAN ALREADY FEEL: it is the
  same dwell that makes cl_main.qc release +forward, which is the same dwell the
  hop rule itself judges a jump by.  So the whole rule is one sentence in three
  places -- if the game released your +forward, that was an initial jump -- and
  the re-arm needs no new number and no new feedback to be legible.  You know it
  worked because W went dead in your hand.

  SCOPE: INSIDE THE START ZONE ONLY, and the boundary is doing real work.  While
  ARMED there is no clock to rewind and no ground to skip, so forgiveness costs
  nothing and cannot be farmed.  Once you have left the box the run is live, and
  "stand still, then jump" would have to restart the clock from wherever you are
  standing -- which is a route skip on any map with a run-up, and 0.25 s of
  ground friction only bleeds about 64% of your speed, so a 1500 u/s bhop would
  still leave at ~535 against a legal pre-strafe of ~289.  That is the exact
  hole build 20 was asked to close.  The recovery from out there is the one that
  already exists and is already honest: walk back into the box.

  0 is build 20 byte-for-byte.
*/
float  run_t_rearmhop;

/*
  Bhop starts on the initial jump, not at the edge of the start box.

  This is derived from the engine's resolved `gamemode` serverinfo key rather
  than from the map name.  That keeps all three of Patch 224's answers honest:
  mapmeta can identify a map whose name lies, `sv_gamemode bhop` can opt a surf
  map in, and `sv_gamemode none` can opt a bhop-named map out.  bhop-hl1 loads
  the same bhop category ruleset and gets the same timer rule.

  Cached once per map because SV_TimerJumpWatch is per-player, per-usercmd.
*/
float  run_t_bhopjump;

/*
  BUILD 43 -- THE STAGE RULES, CACHED PER MAP, AND ALL FOUR ARE BISECTIONS.

  Read once per map for the reason the six above are: they are consulted per
  player per tick, inside the function that already walks the zone table.  And
  latched rather than read live so an A/B is a `map` apart and cannot change
  underneath a run that is halfway through a stage.

    run_stagefail   re-entering a stage's own zone resets that stage.  0 is
                    build 42: the clock runs on through the failed attempt and
                    the "stage time" written at the next boundary contains both.
    run_stagearm    a stage is timed from when you LEAVE the boundary box, not
                    from the plane crossing.  This is the measurement change and
                    it is the one that retires old stage times -- see the essay
                    on SV_StageStart.  0 leaves the build-42 measurement in place
                    while keeping the fail rule, which is the smaller step.
    run_stageclean  SV_StageClose asks whether THIS STAGE is clean rather than
                    whether the run is.  0 is build 42's
                    `run_t_flags & TF_PRACTICE` test, so the per-stage
                    forgiveness can be switched off whole.
    run_stagehop    a bhop out of a boundary box is a legal stage start.  1 keeps
                    build 24's rule (any observed ground phase, no dwell); 0
                    requires the same pre-strafe dwell a run start does, which is
                    stricter and empties the stage boards on bhop maps.  It is a
                    cvar because bhop_eazy is the only honest place to decide it
                    and a config cannot run bhop_eazy.
*/
float  run_t_stagefail;
float  run_t_stagearm;
float  run_t_stageclean;
float  run_t_stagehop;

/*
  BUILD 48: run_stageghost, cached per map with the four above and a bisection
  like them.

    1  a ghosted stage is WRITTEN.  The camera being detached is a mark, not a
       refusal -- which is what the run level has always said about the same
       gesture (see SV_GhostSet: a ghosted run stays valid and is marked
       instead).  The file-format disagreement build 43 avoided by refusing is
       fixed properly instead, in SV_StageLine and SV_StageWrite.
    0  build 47 exactly: SV_StageClose refuses on run_st_ghost.

  A REAL BISECTION AND NOT A COSMETIC ONE, because the two settings write
  different FILES -- at 1 a stage_N folder gains recordings it never had.  That
  is the thing to switch off if a ghosted slice ever reads wrong, and it is why
  this is a cvar rather than a deletion.
*/
float  run_t_stageghost;

/*
  BUILD 44 -- THE RUN CLASSES, AND ONE OF THE TWO IS NOT A TUNING KNOB.

    run_class    split TF_PRACTICE into `segmented` and `cheated`.  0 is
                   build 43 exactly: neither new bit is ever set and every taint
                   reads `practice` again.

                   BUILD 44 CLAIMED HERE THAT THIS BISECTS THE WORDS AND NOTHING
                   ELSE, IN CAPITALS, AND THAT WAS WRONG IN TWO DIRECTIONS.  The
                   sentence is kept as a warning rather than deleted, because it
                   is the sentence a maintainer would otherwise trust:

                   1. AT 0, A CHEATED RUN OVERWRITES last.rec AGAIN.  Build 45
                      gave cheated runs their own filename, and the tag is
                      derived from TF_CHEAT -- which this cvar is what stops
                      being set.  So SV_TimerFinish falls through to RT_LAST and
                      the run destroys that leg's most recent ordinary attempt,
                      exactly as build 44 did.  This cvar now decides a FILE, not
                      only a word, and there is no way around it: the bit IS the
                      knowledge that the run cheated.

                   2. AT 0, sv_cheats ALONE STOPPED BEING A TAINT AT ALL, so
                      such a run was rankable.  That really was build 43 -- build
                      43 never watched the cvar -- which is precisely why "build
                      43 exactly" and "which runs are kept does not change" could
                      not both hold.  NOCLIP was unaffected: build 43 marked that
                      through run_t_dirty and SV_StageOpen's own movetype read,
                      and both still run at either setting.

                      BUILD 46 CLOSED IT, ON THE USER'S EXPLICIT CALL, by
                      dropping the run_class gate from SV_CheatsOn.  sv_cheats
                      now taints at EVERY setting of this cvar; at 0 it marks the
                      run plain `practice` with no new bit, which is what keeps
                      this a bisection of the WORDS.  It is no longer a bisection
                      of the RULESET and it should never have been one: a cvar
                      that decides what a class is CALLED must not also decide
                      what ranks.  run_cheatwatch is the switch that was designed
                      for the ruleset question and it still answers it the other
                      way -- by certifying nothing.

                   WHAT IS LEFT OPEN IS (1), AND IT CANNOT BE CLOSED FROM HERE.
                   The cheat FILENAME is derived from TF_CHEAT and TF_CHEAT is
                   the bit this cvar exists to withhold, so no setting can keep
                   the bisection and the filename both.  At 0 a cheated run is
                   refused the board (that is (2), now fixed) and then overwrites
                   last.rec, which costs the most recent ordinary attempt and
                   nothing that ranks.  Read that as what this cvar is: a
                   DEVELOPMENT SWITCH for bisecting build 44's classification
                   code, shipping at 1, and not a ruleset knob.
    run_cheatwatch  observe sv_cheats at all.  0 does NOT mean "cheats are
                   allowed and unmarked": it makes SV_TimerFinish set TF_PRACTICE
                   on EVERY run, unconditionally.  An install that is not
                   watching cannot certify anything as clean, and saying so costs
                   one line where pretending otherwise would quietly hand the
                   leaderboard runs nobody checked.  That is what keeps this a
                   bisection rather than a bypass.

  Cached per map like the four above, and sv_cheats itself is DELIBERATELY NOT --
  see SV_CheatLevel.
*/
float  run_t_runclass;
float  run_t_cheatwatch;

/*
  "IS THIS PLAYER CHEATING RIGHT NOW?"  Build 44, and it is a LEVEL, not an edge.

  Two states, one question.  MOVETYPE_NOCLIP is the state build 13b started
  watching because the commands that produce it never reach QC at all; sv_cheats
  is the state that unlocks the physics this whole mod is a ruleset for
  (default.cfg's pm_lockmovement note is the other half of that sentence).
  Neither is an event, and both can be true across a stage boundary -- which is
  precisely why the answer is a level and why every caller asks it again rather
  than remembering it.

  sv_cheats IS READ LIVE AND IS NOT CACHED, alone among the cvars this file
  consults per tick.  Caching it per map would make `sv_cheats 1` typed mid-map
  invisible to the watcher, and that gesture is the entire thing being watched --
  a latch that cannot see the event it exists for.  The cost is one hashed cvar
  lookup per player per tick, which is nothing beside the zone scan in the same
  function; the correctness is the point.

  run_cheatwatch gates only the cvar half.  Noclip is watched unconditionally
  because it was already a taint before this build and switching a cvar must not
  make an existing taint disappear -- see SV_TimerFinish for what turning the
  watch off actually costs you.

  BUILD 46: run_class NO LONGER GATES THIS, AND THAT IS THE WHOLE FIX.  This
  function used to return FALSE outright at run_class 0, which gave a cvar
  named after the VOCABULARY the power to take sv_cheats out of the RULESET: an
  sv_cheats run at run_class 0 was clean, and rankable.  Reported and refused
  in as many words.  So the gate lives in SV_TimerCheat now and only there, and
  the two questions are separated by which function answers them --

    SV_CheatsOn / SV_CheatLevel   is this position earned?     ruleset, ungated
    SV_TimerCheat                 what do we call it?          run_class

  -- which is a rule short enough to hold, where "the gate is in both and the
  second one is a bisection" was not.
*/
float() SV_CheatsOn =
{
	if (!run_t_cheatwatch) return FALSE;
	return cvar("sv_cheats") ? TRUE : FALSE;
};

float(entity e) SV_CheatLevel =
{
	/*
	  The NOCLIP half still carries the run_class gate, so at 0 noclip alone
	  leaves run_st_cheat untouched and build 43's single umbrella is all that is
	  written for it.  The UMBRELLA still covers noclip either way -- see
	  SV_StageOpen, which is the one caller that has to keep build 43's line as
	  well as this one.

	  BUILD 46: THE sv_cheats HALF NO LONGER DOES, so at run_class 0 a stage
	  played with cheats on DOES set run_st_cheat and is refused the stage board.
	  That is the one place where 0 stopped being build 43 to the letter, and it
	  is the point of the change rather than a cost of it: the cvar may not make
	  a cheat clean.  No file can end up disagreeing about it either, because a
	  stage carrying run_st_cheat is never written at all -- SV_StageClose refuses
	  on run_st_dirty, which run_st_cheat implies at both of the sites that set it.
	*/
	if (e.movetype == MOVETYPE_NOCLIP)
	if (run_t_runclass)
		return TRUE;
	return SV_CheatsOn();
};

/*
  THE THREE ZONE QUESTIONS, AND THE ONE PLACE EACH IS ANSWERED.

  Build 47 split what had been one function into three, because the ruleset
  asks three different questions of a zone and only two of them changed:

    SV_ZoneOcc   WHERE ARE YOU        -- occupancy.  "Which start box am I
                                        standing in."  A POINT question, and it
                                        stays one at run_zone_hull 1.  See the
                                        essay at the top of SV_TimerFrame.
    SV_ZoneIn    HAVE YOU LEFT        -- asked of one position, of the box you
                                        armed in.  The clock starts when this
                                        goes false.
    SV_ZoneHit   DID YOU TOUCH        -- asked of the movement, for the events:
                                        checkpoint, stage, end, cancel.

  Occupancy is a point question.  "Did you leave" and "did you touch" are hull
  questions.  That sentence is the whole of run_zone_hull 1, and it is worth
  keeping in that shape: the previous version of this comment claimed the arm
  test and the start test were the same test, and build 47 is where that stops
  being true.

  THE INVARIANT THAT MAKES IT SAFE: arming requires the POINT inside (level 1
  leaves SV_ZoneOcc alone) and starting requires the HULL outside -- and
  point-inside implies hull-inside, always.  So the hull rule can only DELAY a
  start.  It can never fire before the arm and never prevent a start that would
  otherwise happen.  What it does create is a band, one hull-width wide, around
  every start box where you are TS_ARMED with az == -1 and the clock has not
  started.  That band is the feature.
*/
float(float z, vector a, vector b, vector mins, vector maxs) SV_ZoneHit =
{
	if (run_t_hullevt)
	{
		if (run_t_swept)
			return Zone_BoxSwept(z, a, b, mins, maxs);
		return Zone_BoxInside(z, b, mins, maxs);
	}
	if (run_t_swept)
		return Zone_SegmentInside(z, a, b);
	return Zone_PointInside(z, b);
};

float(float z, vector p, vector mins, vector maxs) SV_ZoneIn =
{
	if (run_t_hullevt)
		return Zone_BoxInside(z, p, mins, maxs);
	return Zone_PointInside(z, p);
};

float(float z, vector p, vector mins, vector maxs) SV_ZoneOcc =
{
	if (run_t_hullocc)
		return Zone_BoxInside(z, p, mins, maxs);
	return Zone_PointInside(z, p);
};

/*
  THE HULL THE RULESET TESTS WITH.  One function, because a rule spelled at ten
  call sites is a rule that will disagree with itself at one of them.

  PM_DUCK_MINS and PM_HULL_MINS are identical (sh_defs.qc), so only maxs can
  differ, and only in z: 45 against 62.  See run_zone_hull_live for why the
  constant hull is the default even though the engine has the live one right
  there on the entity.
*/
vector(entity e) SV_RunHullMins =
{
	return PM_HULL_MINS;
};

vector(entity e) SV_RunHullMaxs =
{
	if (run_t_hulllive)
		return e.maxs;
	return PM_HULL_MAXS;
};

/*
  Which START zone is p standing in, or -1.  Build 47.

  Asked by the save-lock loader, and asked through SV_ZoneOcc rather than with a
  fresh point test of its own SO THAT IT CANNOT DRIFT from what SV_TimerFrame's
  arm scan means by "standing in a start box".  There is no ZoneAtPoint helper
  in this tree and the arm scan is inline; adding a second speller that answers
  a slightly different question is the failure this file keeps writing essays
  about, so this one is a thin wrapper over the same predicate and nothing else.

  Deliberately does NOT reproduce the scan's START-outranks-STAGE priority: the
  caller wants the yes/no, and a STAGE box is not a place you pick a start from.
*/
float(entity e, vector p) SV_ZoneStartAt =
{
	local float z;
	local vector mn, mx;

	mn = SV_RunHullMins(e);
	mx = SV_RunHullMaxs(e);

	for (z = 0; z < zone_count; z = z + 1)
	{
		if (zone_type[z] != ZONE_START)
			continue;
		if (SV_ZoneOcc(z, p, mn, mx))
			return z;
	}
	return -1;
};

/*
  The personal best table, per map.

  [track * FS_MAXSPLITS + leg] is the best time for that LEG: leg 0 is the full
  track and leg k is stage k.  run_pb_split is only meaningful for full runs and
  holds the cumulative time at each stage boundary, which is what the +/- on the
  HUD is measured against -- and it is still keyed by SEGMENT, because a split is
  one.

  BUILD 57: KEYED BY LEG, WHERE IT WAS KEYED BY THE STARTING SEGMENT.  Slot 1
  used to hold stage 2 and stage 1 had no slot, because its segment is 0 and 0
  was the full run.  FS_LegOf is the only speller of the key.  Legs cap at
  FS_MAXSPLITS - 1 = 23; every write below tests the leg against that bound.
*/
float run_pb_ticks[FS_MAXTRACKS * FS_MAXSPLITS];
float run_pb_split[FS_MAXTRACKS * FS_MAXSPLITS];
float run_pb_dirty;

// This run's own splits, so a new PB can write its split table out.
float run_run_split[FS_MAXPLAYERS * FS_MAXSPLITS];

/*
  The same pair again for checkpoints.  Build 19.

  Indexed by the checkpoint's ORDINAL within its segment (zone_cp[]), not by a
  crossing count and not by the segment -- on a linear map every checkpoint is
  segment 0, which is exactly why the old `cp` record could not say which one it
  was.  The ordinal is what makes a per-checkpoint PB addressable at all.

  run_pb_cp is keyed on the track only, like run_pb_split, because a checkpoint
  delta is only meaningful for a full-track run: a stage run starts mid-map and
  its clock is not comparable to a full run's at the same gate.
*/
float run_pb_cp [FS_MAXTRACKS  * FS_MAXCPS];
float run_run_cp[FS_MAXPLAYERS * FS_MAXCPS];

// The pre-start ring.  Eight parallel arrays rather than one of structures
// because QC has neither, and because the recorder writes them in a block.
// rec_pad_mv and rec_pad_key joined them in v3: the padding is real recording --
// it is the approach to the start zone -- so it has to carry everything a sample
// does, or the key display would go dark for the first four seconds of every
// replay.  It costs 8 KB.
//
// PATCH 270, STAGE 2: FS_PADSLOTS, not FS_MAXPLAYERS, and the two are no longer
// the same number -- see the measurement at that define.  Every index into
// these now comes from SV_RecPadBase, which is what stops a slot of 4..31
// walking off the end of an array silently.
vector rec_pad_org[FS_PADSLOTS * FS_RECPAD];
vector rec_pad_vel[FS_PADSLOTS * FS_RECPAD];
vector rec_pad_mv [FS_PADSLOTS * FS_RECPAD];
float  rec_pad_t  [FS_PADSLOTS * FS_RECPAD];
float  rec_pad_pit[FS_PADSLOTS * FS_RECPAD];
float  rec_pad_yaw[FS_PADSLOTS * FS_RECPAD];
float  rec_pad_fl [FS_PADSLOTS * FS_RECPAD];
float  rec_pad_key[FS_PADSLOTS * FS_RECPAD];
// v4, and for the reason the v3 note above gives about mv and key: the padding
// IS recording -- it is the approach to the start zone -- so a column that every
// other sample carries has to be carried here too, or the strafe bar would go
// blank for the first four seconds of every replay and then snap on.  12 KB.
vector rec_pad_norm[FS_PADSLOTS * FS_RECPAD];

// Which ring/split row a player owns, or -1.  Handed out on connect rather
// than derived from the edict number, which is not stable across a respawn.
entity run_slot_owner[FS_MAXPLAYERS];

// sv_saveloc.qc is the next file (it needs run_t_slot); a map change has to
// drop its list, and this file owns the per-map reset.
void() SV_SaveLocReset;
float(entity e) SV_TimerTicks;      // defined below SV_TimerArm; SV_TimerRestartSeg is above it
// Build 76: SV_TimerTicks calls this, and it is defined just BELOW it -- the two
// were written in the other order in build 74, when the counted clock was only a
// report.  Forward declared rather than moved so the diff of the build that made
// it the clock is the clock, not a hundred lines of relocation.
float(entity e) SV_TickCounted;
void(entity e) SV_TimerPractice;    // defined below SV_TimerWarped; SV_TimerFreeze is above it
// Build 44.  Beside their funnel, for the same reason: SV_StageOpen and
// SV_TimerStart both sit above the definitions and both consume a taint.
void(entity e) SV_TimerStitched;
void(entity e) SV_TimerCheat;

/*
  `retry`'s cross-restart arm.  OWNED BY sv_saveloc.qc -- see SV_RetryApply --
  and declared up here only because sv_progs.src compiles this file first and
  SV_TimerMapInit is where the cvar is latched into it.
*/
float rec_retry_armed;

/*
  1 while the move clipped a ramp plane.  ENGINE-WRITTEN, by name, from inside
  PMSrc_TryPlayerMove -- one of the four board-telemetry fields whose block and
  whose full explanation live in sv_player.qc.  Declared up here rather than
  there because sv_progs.src compiles this file first and SV_TimerJumpWatch needs
  it: a ramp can add 140 u/s of rise in a single tick just as a jump can, so
  without it the start-hop rule would call an early ramp a bhop.
*/
.float  run_rampcontact;

/*
  BUILD 24 -- THE OTHER FIVE, MOVED HERE FROM sv_player.qc TO JOIN IT.

  Board telemetry, engine Patch 131 and Patch 137.  None of the six is ever
  assigned anywhere in QuakeC: the engine writes them each move from inside
  PMSrc_TryPlayerMove's bump loop, which is the only place the real clip plane
  and the real PRE-clip velocity exist.  It finds them BY NAME, with
  GetEdictFieldValue -- so declaring them is what switches the feature on, and a
  mod that does not declare them (quakers, sharing this engine tree) has nothing
  written into it and pays nothing.

  They are here rather than in sv_player.qc because THE RECORDER IS HERE.  Build
  23's replay could not draw the strafe bar, the board panel or the segment
  column, and said so on screen, because the .rec carried none of this -- its
  flags column had onground, ducked, jump and attack and nothing else.  That was
  an honest refusal and it was also a missing four columns.  v4 writes them.

  WHICH OF THE TWO NORMALS GOES IN A SAMPLE.  run_boardnormal is the plane of the
  last ARRIVAL and is latched, deliberately, or the board grade would re-fire on
  every tick of a ride.  run_rampnormal is the plane THIS tick clipped, updated as
  a curved ramp turns underneath you and zeroed the moment you leave it.  The
  strafe bar wants the second question (HUD_RampNormal), the board readout wants
  the first -- so the sample carries run_rampnormal (or run_groundnorm when you are
  standing on something) and the board entry gets its own record with the latched
  pair.  One vector per sample rather than three.
*/
.vector run_groundnorm;          // networked to the HUD too; see SV_RegisterStats
.vector run_boardnormal;
.vector run_boardvelocity;
.float  run_boardcount;
.vector run_rampnormal;

/*
  BUILD 74 / ENGINE PATCH 325 -- THE CLOCK THE RUN IS ACTUALLY MADE OF.

  Written by the engine once per usercmd, on the same optional-field route as the
  five above: declare them and they are filled, do not and the engine writes
  nothing.

  WHY THEY EXIST.  SV_TimerTicks was, until build 76,
  floor((time - run_t_start)/run_t_tick + 0.5), and `time` in a think hook is
  sv.time, which the engine advances ONCE PER SERVER FRAME.  So every usercmd
  inside one frame reads the same clock.  Worse than that: PlayerPostThink is
  called from SV_PostRunCmd, which sits OUTSIDE the engine's per-usercmd loop, so
  everything in this file runs once per PACKET.  The stored time is therefore a
  function of when packets arrived and where the server's frame loop landed --
  neither of which is in the input stream, so a run time cannot be reproduced by
  re-simulating the usercmds that produced it.  That is the whole obstacle to a
  verifier, and it is what these measure.

  run_movetick is cumulative PER MAP, not per run and not per connection -- the
  engine resets it in SV_SpawnServer, because it is published as a QC float and a
  float is an exact integer only to 2^24 (69.9 h at 0.015).  Latch it and take a
  difference; never read it as an absolute.

  run_movetickrate IS NOT `run_t_tick` AND MUST NOT BE ASSUMED EQUAL TO IT.  That
  is the entire reason it is published.  run_t_tick is this file's cached
  cvar("pm_ticrate") with a compile-time fallback; run_movetickrate is the number
  the mover divided by.  While the clock is seconds a disagreement costs
  rounding; the day the stored quantity becomes TICKS it multiplies every
  recorded time by their ratio.  This tree shipped that bug once already in the
  other direction -- build 64, bhop maps running 0.01 read against a 0.015
  constant -- so the two are compared rather than conflated.  See SV_TickReport.

  run_movecarry is the mover's sub-tick remainder, in seconds.  It is what lets
  an elapsed time stay exact across a tick boundary; without it a counted clock
  can only ever answer in whole ticks.  NOT USED YET -- it is here because the
  save-state resume and the recorder's timestamps will both need it, and because
  a field the engine publishes and QC ignores costs nothing while a field the
  engine does not publish costs an engine release.

  NOTHING HERE RANKS ANYTHING IN BUILD 74.  This build measures the gap between
  the two clocks and reports it; it does not change one stored number.  That is
  deliberate: the gap has never been measured on a real run, and every decision
  that follows -- what the tolerance is, whether a stalled stream is a taint,
  whether the migration is worth its cost -- needs the measurement first.
*/
.float  run_movetick;            // cumulative mover ticks this map, per player
.float  run_movecarry;           // sub-tick remainder, seconds
// BUILD 87, engine Patch 346: what the mover was handed.  Optional fields, written
// after every move; 0 on an older engine, and run_pmepoch > 0 is how the recorder
// knows the engine publishes (a client cannot write an edict field).
.float  run_pmepoch;             // bumps when the mover's inputs (the pin) change
.float  run_physcrc;             // 24-bit digest of the last move's physent list
.float  run_portalx;             // linked-portal crossings, cumulative per map
.vector run_portalorg;           // post-move state of the last crossing move
.vector run_portalvel;
/*
  run_movetickrate IS DECLARED IN defs/sv_defs.qc, not here, and it is the odd
  one of the three.  Build 76 made Lobby_SubmitRun send it beside the tick count
  -- because since that build the stored quantity IS the mover's ticks, so the
  rate that converts them to milliseconds has to be the mover's too -- and
  sv_lobby.qc compiles BEFORE this file in sv_progs.src.  Same split, same
  reason, as sv_mv_maxspeed, which is declared down there beside it and says so.
  The essay above covers all three; only the declaration moved.
*/

.float  run_t_state;             // TS_*
.float  run_t_track;
.float  run_t_startseg;          // the 0-based SEGMENT the run began at
/*
  BUILD 57 -- A STAGE RUN SAYS SO, BECAUSE THE SEGMENT CANNOT.

  run_t_startseg used to double as the LEG: 0 was the full run and N was "a run
  that began at segment N", which FS_LegDir spelled stage_N.  That is one stage
  late on every staged map -- segment N is stage N+1 -- and it left stage 1 with
  no leg at all, because stage 1 begins at segment 0 and 0 already meant the
  whole track.  So `!s 1` armed a full run, SV_StageClose refused segment 0, and
  the scoreboard was one stage short.

  The segment stays a segment wherever it means one (splits, the .rec `stage`
  and `restart` records, the `startseg` header).  The leg is derived:

      leg = FS_LegOf(run_t_startseg, run_t_stagerun)   // 0 full run, k stage k

  run_t_stagerun is set by SV_TimerArm and nowhere else except a save restore.
  It is TRUE for an arm at a STAGE zone, as every stage run already was, and for
  an arm at the main track's START while run_t_wantstage1 is standing -- which is
  the one new leg, stage 1 run on its own.

  run_t_wantstage1 is the PLAYER'S REQUEST, not a fact about a run, and that is
  why it is a separate field.  `!s 1` sets it and then moves to the START; the
  arm that follows reads it.  It has to outlive the arm, because `!r` inside a
  stage-1 run voids and re-arms the same START and must come back as stage 1 --
  and it has to die the moment the player asks for anything else: `!m`, `!b`,
  `!s N` for N > 1, walking into a START, or an arm anywhere that is not the
  main track's START.  See SV_TimerArm, SV_TimerTryArm and SV_TimerChatLeg.
*/
.float  run_t_stagerun;          // TRUE: a stage-only run; its leg is startseg + 1
.float  run_t_wantstage1;        // `!s 1` is standing: the main START arms stage 1
.float  run_t_seg;               // segment in progress
.float  run_t_segs;              // segments in this track
/*
  BUILD 76 -- THE CLOCK'S ORIGIN, AND IT IS NO LONGER ON THE WALL.

  RENAMED FROM run_t_start ON PURPOSE, and the rename is the safety mechanism
  rather than tidying.  The field's TYPE did not change -- it is still one float
  of seconds -- so every one of its eight readers would have compiled untouched
  and silently mixed the two clocks, which is precisely the failure this whole
  migration exists to avoid.  fteqcc refuses an undeclared field, so renaming
  turns every site into a compile error and the compiler enumerates the work.
  Same trick, same reason, as the sentinel in run_t_starttick: make the wrong
  thing impossible to write rather than remembering not to write it.

  WHAT IT HOLDS NOW: SV_ClockSec at the moment the run started, i.e. cumulative
  SIMULATED seconds rather than wall seconds.  See SV_ClockSec for why that is a
  different number and what it buys.
*/
.float  run_t_startsec;          // SV_ClockSec when the timer started
.float  run_t_ticks;
/*
  BUILD 74/76: the counted clock's latches.

  -1 IS "NEVER LATCHED" and refuses to report, on run_t_rbreach's precedent and
  for exactly its reason: a run whose start took no latch would otherwise
  difference against a zero and invent a number.  A zero cannot mean this,
  because zero is a legal counter value -- it is what the first run after a map
  load starts at.  SV_TimerArm sets it to -1; SV_TimerStart latches the real one.

  BUILD 75 ADDED THE OTHER HALF OF THAT, AND IT WAS A SHIPPED DEFECT: the
  sentinel was written by the ARM alone, so a player who had never armed held the
  QC default of 0 and `cmd timer` differenced against it.  SV_TimerIdle seeds it
  now, because tearing an attempt down is what establishes that there is no run.

  run_t_frzticks is the ticks that elapsed while the clock was held, and
  run_t_frzsec is the same interval in simulated seconds.  BOTH, because the run
  has two readouts derived from one counter -- an integer tick count that ranks
  and a seconds figure that timestamps the recording -- and subtracting a rounded
  quantity from an exact one would put a rounding error into the .rec's `t`
  column on every freeze.  They are accumulated from the SAME delta in the same
  line, so they cannot drift apart.

  THE FREEZE IS NOT FREE ON A COUNTED CLOCK.  The mover runs its ticks for a
  MOVETYPE_NONE player exactly as fast as for a moving one -- PM_PlayerMove
  dispatches to the Source mover BEFORE any pm_type test, and the test that
  recognises the pin lives INSIDE PMSrc_Tick, after the tick has been spent -- so
  the ticks of a save-lock hold are counted unless something subtracts them.
  Accumulated rather than incremented: a packet can carry more than one usercmd
  and therefore more than one tick, so this takes the DELTA of the counter, which
  is right whatever the packet contained.

  run_t_lastmt / run_t_lastsec are the previous packet's readings, which is what
  those deltas are taken against.  They have no meaning outside
  SV_TimerFreezeFrame.

  run_t_clock is WHICH CLOCK THIS RUN IS ON, latched once at the start and never
  re-read: 1 counted, 0 sampled.  It is what guarantees no single recording ever
  carries two clocks, which is the one hazard that made this migration have to
  land whole rather than in pieces.  See TF_NOCLOCK.
*/
.float  run_t_starttick;         // run_movetick at the start; -1 = never latched
.float  run_t_tickcarry;         // Patch 363: ticks restored by SV_TimerResume, counted on top
.float  run_t_resumesec;         // Patch 363: the restored seconds, for a latch deferred to the first packet
.float  run_t_frzticks;          // ticks elapsed while frozen
.float  run_t_frzsec;            // the same interval, simulated seconds
.float  run_t_lastmt;            // previous packet's run_movetick
.float  run_t_lastsec;           // previous packet's SV_ClockSec
.float  run_t_clock;             // 1 = counted (the mover's ticks), 0 = sampled
/*
  BUILD 76: sv.time at the start, kept SOLELY so the report can still show the
  two clocks beside each other.

  EXACTLY ONE READER, SV_TickReport, and that is the field's whole safety
  argument: nothing derived from it can reach a stored number, a board row, a
  recording or a save file, however badly a later reader misunderstands it.  It
  exists because the migration removed the last sv.time origin from this file and
  an instrument that can only print the winner is not a comparison -- and this
  instrument is the one that found the bound that was asserted at eleven readings
  and falsified at eighteen.
*/
.float  run_t_startwall;         // sv.time at the start; SV_TickReport ONLY

/*
===========================================================================
  BUILD 76 -- THE ONE CLOCK EVERYTHING IN THIS FILE IS NOW MEASURED AGAINST.

  Cumulative SIMULATED seconds for this player on this map: how much time the
  mover has actually advanced them through, as opposed to how much time has
  passed in the room.

      ticks * rate + carry

  and that expression is not an approximation of anything -- it is EXACTLY the
  cumulative cmd.msec the mover has consumed.  PMSrc_PlayerMove does
  `avail = carry + msec; while (avail >= tick) { Tick(); avail -= tick; }
  carry = avail`, so ticks*rate + carry telescopes to the sum of every msec ever
  handed to it.  Nothing else in the engine has that property.

  WHY IT IS MONOTONE, which is the property the recorder depends on and the one
  worth proving rather than assuming.  Each command adds a non-negative msec and
  the loop only moves time from `avail` into `ticks*rate` at par, so the sum
  cannot decrease.  Two places perturb it and neither breaks it: the
  PMSRC_MAX_TICKS bail sets avail to 0, which only ever LOWERS the carry after
  having already banked the ticks (time is lost, not reversed); and
  PMSRC_TICK_EPSILON lets a tick run a hair early, which nudges the sum UP by at
  most one epsilon.  Monotone either way, which is all the .rec's `t` column
  asks for.

  WHAT IT BUYS.  This number is a function of the usercmd stream and of nothing
  else.  sv.time -- the old origin -- is `(Sys_DoubleTime() - starttime) *
  gamespeed`, advanced once per SERVER FRAME, so the old clock's readings were a
  function of when packets arrived and where the frame loop landed, neither of
  which is in the stream.  Measured over eighteen readings on a live lobby, the
  two disagreed by 0, 1 or 2 ticks with the sampled one ALWAYS the larger, so
  the old clock was handing players times that were slightly too long.

  THE FALLBACK IS `time`, AND IT IS NOT A COMPROMISE -- IT IS THE OLD CLOCK.
  The three engine fields arrive on the Patch 131 optional-field route, so an
  engine older than Patch 325 (or a build with the Source mover off) writes
  nothing and run_movetickrate stays 0.  Returning `time` there makes every
  caller in this file correct without a branch: run_t_startsec becomes an sv.time
  origin again, SV_TimerElapsed becomes `time - start`, and the game behaves
  exactly as build 75 did.  The run is marked TF_NOCLOCK and nobody is accused.

  THE SELECTOR IS run_movetickrate AND NOT run_t_clock, deliberately, and the
  reason is the padding ring.  The ring stamps this function BEFORE a run exists,
  so a selector that only becomes valid at SV_TimerStart would stamp the pad on
  one clock and subtract the other at flush -- a recording whose first twenty
  samples are nonsense, which is worse than either clock alone.  Keying on the
  engine field means the answer is stable from the first QC frame onward: the
  mover publishes it inside SV_RunCmd and everything in this file runs from
  SV_PostRunCmd, which is strictly after.  run_t_clock records WHICH ONE a run
  got, for the header and the taint; it does not choose.

  NOT the same thing as run_t_tick.  run_t_tick is this file's cached
  cvar("pm_ticrate"); run_movetickrate is the number the mover actually divided
  by.  Using the wrong one here would multiply every recorded time by their
  ratio -- build 64 shipped exactly that, in the other direction -- so this uses
  the mover's and SV_TickReport compares the pair on every call.
===========================================================================
*/
float(entity e) SV_ClockSec =
{
	if (e.run_movetickrate > 0)
		return e.run_movetick * e.run_movetickrate + e.run_movecarry;
	return time;
};
.float  run_t_split;
.float  run_t_delta;
.float  run_t_pb;
/*
  BUILD 48: the personal best this run was measured AGAINST, latched before the
  table is rewritten.  0 = there was none.

  A DEFECT FIX AND NOT A FEATURE, and the defect has been shipping since build
  19.  SV_TimerFinish sets run_pb_ticks[...] to this run's time when it is a
  personal best, and then -- twenty lines later, unconditionally -- re-reads
  run_t_pb out of that same table.  So on every PB run_t_pb IS run_t_ticks, the
  delta drawn from the pair is exactly zero, and the finish row down the left has
  never once shown a number on the runs anybody wanted a number for.

  Kept beside run_t_pb rather than folded into it because run_t_pb still has a
  live job: it is what the HUD compares the RUNNING clock against, and it has to
  become the new best the moment the new best exists.  Two facts, two fields.

  Cleared by SV_TimerArm with the rest of the attempt.
*/
.float  run_t_pbwas;
.float  run_t_flags;             // TF_*
/*
  THREE LATCHES, NOT ONE, because a Momentum zone is a TRIGGER and you can be
  inside several at once.

  The first version of this kept a single "the zone I am in" and picked the
  first match in table order.  That cannot express the shipped data:

    * surf_doodles' stage-1 box overlaps its start box by 480 units.
    * agtricks, surf_ethereal, surf_flyin_fortress, surf_hades2 and
      surf_quirky put their END zone INSIDE their start zone -- 5 legs of the
      1697 in the library.

  and it conflated two different questions.  "Which zone would a run begin
  from" (run_t_azone) and "which stage or end have I just crossed"
  (run_t_evzone) are asked of overlapping sets and answered independently, the
  way two triggers would fire independently.  run_t_armzone is the third: the
  zone the CURRENT arm came from, which is what "leaving the start starts the
  timer" is actually about -- it has to be the specific box we armed in, not
  whichever one happens to be underfoot.
*/
.float  run_t_azone;             // arm-able zone occupied now (start/stage), or -1
.float  run_t_evzone;            // stage/end zone occupied now, or -1
.float  run_t_armzone;           // the zone THIS arm came from, or -1
.float  run_t_cpzone;            // checkpoint zone occupied, or -1
.float  run_t_slot;              // index into the arrays above, or -1

/*
  The base index of a player's padding ring, or -1 for "has not got one".

  PATCH 270, STAGE 2.  Every site that used to write `e.run_t_slot * FS_RECPAD`
  behind an `if (e.run_t_slot < 0)` guard now goes through this, because the
  guard has to test TWO things since the ring stopped being one per player: a
  slot of -1, and a slot at or past FS_PADSLOTS.  An out-of-range write into a
  QC array is silent, so the one-sided test would have corrupted the next
  array in the globals block rather than erroring.

  It lives HERE, immediately under the field it reads, and not up beside the
  arrays where it belongs by subject: QuakeC has no forward declarations for
  FIELDS either, and .run_t_slot is declared 150 lines below rec_pad_org.
*/
float(entity e) SV_RecPadBase =
{
	if (e.run_t_slot < 0 || e.run_t_slot >= FS_PADSLOTS)
		return -1;
	return e.run_t_slot * FS_RECPAD;
};

/*
  Is this server writing .rec files at all?

  PATCH 270, STAGE 2.  rec_enable is the player's own switch and stays exactly
  what it was; lobby_norec is the server's, and it exists because the recorder
  does not scale in the one dimension that matters here.

  A run in progress lives as QC STRINGS in a strbuf until it closes -- the
  whole run, every tick, one line each -- so 32 simultaneous recordings is on
  the order of 50 MB of string table on a Pi with 3.2 GB and no swap.  The
  failure mode is not a slow server, it is the OOM killer taking the process.
  And the filenames collide: the archive name is <ticks>_<tag>.rec, so two
  people finishing on the same tick write the same path.

  Both call sites go through here rather than testing rec_enable twice, because
  they were already an if/else pair whose arms disagreeing would mean a run
  that starts a recording it never closes.
*/
float() SV_RecEnabled =
{
	if (!cvar("rec_enable"))
		return FALSE;
	return !Lobby_NoRec();
};

/*
  CHECKPOINTS, build 19.  The three that go on the wire plus the one that makes
  them well defined.

  run_t_cpmax is the highest ordinal recorded this run, and `> cpmax` is the whole
  admission rule.  It does three jobs that used to be three separate defects:

    * leaving and re-entering the same checkpoint no longer records it twice --
      the old edge was `cp != run_t_cpzone`, a zone index, so walking back through
      a gate counted again;
    * a logical checkpoint made of SEVERAL regions counts once.  surf_utopia's
      first checkpoint is a mirrored pair, two zones for one gate, and they share
      an ordinal;
    * it makes the ordinal monotone, which is what lets STAT_FS_TIMERCP double as
      its own edge and what makes run_run_cp[] addressable.

  This is Momentum's `checkpointsOrdered`, which is true in every shipped zone
  file I have looked at and which the parser does not read yet -- so it is being
  implemented by convention rather than from the key.  The key is right there in
  the file for the day a map disagrees; see the ignored-keys note in sh_zones.qc.
*/
.float  run_t_cpmax;             // highest checkpoint ordinal recorded this run
.float  run_t_cpn;               // that ordinal, networked; 0 = none yet
.float  run_t_cpticks;           // ticks at that crossing
.float  run_t_cpdelta;           // minus the PB's, signed; 0 = no PB

/*
  THE STOPPED CLOCK, build 19.  See TF_STOPPED in sh_defs.qc for why the truth
  has to live out here rather than in run_t_flags.

  Ticks the run stopped at, or 0 for "no stopped run to show".  Written by
  SV_TimerVoid from run_t_ticks -- NOT from a fresh SV_TimerTicks call, because
  the void is reachable from a `say` handler where `time` is
  sv.world.physicstime rather than sv.time and the arithmetic would be wrong by
  up to a server frame.  run_t_ticks was computed by the last SV_TimerFrame at the
  usercmd's own clock, so it is exact, and being one tick stale is the resolution
  of the display anyway.
*/
.float  run_t_stopat;

/*
  THE START-HOP RULE, build 19.  "Only a pre-strafe to a jump off the platform:
  you are not allowed to jump twice in a start."

  run_t_groundsec is the CLOCK the current ground phase began at, and 0 MEANS NOT
  GROUNDED -- that zero is doing real work.  A perfectly-timed hop never appears
  grounded to QC at all: CategorizePosition sets FL_ONGROUND and CheckJumpButton
  clears it inside the same tick, so PlayerPostThink sees an airborne player who
  was airborne last tick too.  Reading 0 there gives a dwell of 0, which is
  exactly right -- that hop had no ground phase worth the name.

  BUILD 76 -- RENAMED FROM run_t_groundat/run_t_airat, BECAUSE THE UNIT MOVED.
  They hold SV_ClockSec now rather than sv.time, and the rename is the mechanism
  that made the compiler enumerate the eight readers rather than trusting a grep.

  WHY THE DWELL HAD TO MOVE WITH THE RUN TIME.  This is not a display: the dwell
  decides a VERDICT -- whether a jump is an initial jump or an autohop, whether a
  stage slice qualifies, whether a fluffed start is taken back -- and those
  verdicts decide whether a run counts and where its clock starts.  Leaving them
  on sv.time would have shipped the thing the migration exists to prevent one
  level up from the number: a reproducible TIME attached to an irreproducible
  DECISION, so two re-simulations of one usercmd stream could agree on the ticks
  and disagree on whether there was a run at all.  run_t_dwell and run_t_settle
  are cvars in seconds and stay in seconds; what changed is which seconds.

  THE ZERO SENTINEL STAYS, AND THAT IS NOT A CONTRADICTION OF BUILD 75.  Build 75
  fixed run_t_starttick, where 0 is a value the counter genuinely holds for the
  first seconds of every map and differencing against it produced a confident
  four-figure number for a run that did not exist.  Here 0 is reachable only for
  a player whose mover has run zero ticks AND whose carry is exactly 0.0 -- the
  first instant of a map, before any command has moved them -- and reading it
  gives a dwell of zero, which REFUSES to qualify the hop.  The sentinel that
  bites is the one whose failure invents a number; this one's failure is a
  conservative no.  Stated because the surface reading of build 75 says otherwise.

  run_t_lastvz is the previous tick's velocity_z, because the jump edge is a
  velocity crossing and not a ground-flag edge, for the reason above.

  run_t_startok says the start is settled and hops are no longer anyone's
  business -- on a bhop map they are the entire game.
*/
.float  run_t_groundsec;          // SV_ClockSec this ground phase began; 0 = airborne
.float  run_t_airsec;             // SV_ClockSec this air phase began;    0 = grounded
.float  run_t_lastvz;
.float  run_t_startok;
// Jumps since the arm.  Diagnostic only -- the rule is the dwell, not the count
// -- but "how many jumps did it think I took" is the first question anyone asks
// of a rule that just marked their run practice, and it has no other answer.
.float  run_t_jumps;

/*
  Where the previous tick left you, for the swept zone test.

  The stage and end zones are tested against the SEGMENT you travelled this
  tick, not against the point you ended it at -- 101 of the library's 6772
  regions are under 32 units thick and several are one-unit trigger planes,
  which a point sampled at 66.67 Hz falls straight through.  See
  Zone_SegmentInside.

  Every teleport has to reset this or the segment spans the whole map and
  sweeps every zone between the two ends.  SV_TimerWarped is that reset, and
  nearly every setorigin in the game calls it.

  BUILD 83, CORRECTED: "every setorigin" was wrong, and the exception is small
  but real -- trigger_push's continuous arm lifts you one unit off the floor
  (sv_entities.qc:5427) with no SV_TimerWarped call.  One unit cannot span a
  zone, so nothing is broken by it; the sentence is narrowed rather than the code
  changed, because the invariant a reader takes away from an absolute claim is
  the one that gets built on next.  The start jitter below is the second
  exception and it is deliberate -- see SV_RunStartJitter.
*/
.vector run_t_lastorg;

/*
  BUILD 83: THE OFFSET THE START JITTER ACTUALLY APPLIED, in units, z always 0.

  Written by SV_RunStartJitter and read by SV_RecOpen, which is the whole of its
  life -- it exists so the recording can state the displacement rather than leave
  a verifier to infer it from a sample it has no other reading of.

  IT IS RECORDED BECAUSE IT CANNOT BE RE-DERIVED.  random() is builtin #7 and
  nothing in this tree seeds it (there is no crandom, no PRNG state, no cvar), so
  the number is genuinely unreproducible off this machine.  That is the same
  sentence experiment E3 wrote about trigger_teleport: THE FILE RECORDS THE
  CONSEQUENCE AND NEVER THE EVENT -- and shipping a randomized start without this
  field would have added a fresh instance of the hole E3 was run to find.

  ZERO IS A FACT AND ABSENCE IS A DIFFERENT ONE.  A blocked roll -- every
  candidate embedded in geometry or back inside the start box -- applies nothing
  and records `0 0 0`; a run under a build or a server with the rule off writes
  no key at all.  Those are different statements and the header keeps them
  different, which is the sv_mapcheck lesson: a comparison whose two sides are
  both zero agrees for a decade.
*/
.vector run_t_jitter;

/*
  GHOST.  Build 30.  The camera is detached; this body is coasting unattended.

  DECLARED HERE, WRITTEN IN sv_saveloc.qc, which compiles after this file --
  the same "declare where it is first read" arrangement cl_keys.qc:44-47
  explains for run_ps_release.  The logic belongs beside SV_WatchHold, because
  ghost is the third of the three modes that take a player out of ordinary play
  and the three have to refuse each other; the FIELD belongs here, because
  SV_TimerFrame is what reads it and SV_TimerFrame is the first thing compiled
  that does.

  While it is set, SV_TimerFrame runs no zone tests at all.  It is not enough to
  stop the events: the swept test's other end has to keep moving with the body
  or the tick you come back draws a segment from where you detached to wherever
  the body drifted, firing every zone on the line between -- which is the class
  of fault run_teleport_warp was added to fix, arriving by a new route.
*/
.float  rec_gh_on;

/*
  The stage zone a just-finished stage run is standing in.

  Finishing stage N leaves you inside stage N+1's zone, and that zone is also
  where stage N+1's run begins.  Arming it immediately would replace the time
  you just set with a zero on the same tick -- so the arm is deferred to the
  moment you LEAVE, which is when the next run starts anyway.  Momentum shows
  the same thing: your stage time stays up while you are still in the box.
*/
.float  run_t_pendarm;

/*
  Noclip (or a save-lock load) has touched this attempt, whether or not the clock
  was running at the time.

  It lives outside run_t_flags because SV_TimerArm zeroes those, and the interval
  this has to survive is exactly the arm.  See SV_TimerPractice.
*/
.float  run_t_dirty;

/*
  The start was hopped, and it can still be taken back.  Build 21.

  A SECOND TAINT, DELIBERATELY SEPARATE FROM run_t_dirty, because the two differ
  in the only way that matters here: this one is FORGIVABLE and that one is not.
  Standing still for the pre-strafe dwell is a complete answer to "you bhopped
  out of the box" -- you stopped, and the next jump is a fresh initial jump.  It
  is not an answer to "you flew here in noclip", and folding the hop into
  run_t_dirty would have made it one, because there would then be no way to
  forgive the hop without forgiving whatever else had dirtied the attempt.
  Ordering games on a single flag were the first thing tried and every ordering
  had a hole in it -- hop-then-noclip or noclip-then-hop, pick one.

  SV_TimerStart consumes (run_t_dirty || run_t_hopped), so an unforgiven hop still
  marks the run practice exactly as before; nothing downstream of the start can
  tell which of the two it was, and nothing downstream needs to.

  Cleared by SV_TimerArm with the rest of the attempt, and by the re-arm in
  SV_TimerJumpWatch.  Only ever SET while the clock is not yet running: a hop
  after the run has started goes straight to SV_TimerPractice, which is
  irreversible on purpose -- see the scope note there.
*/
.float  run_t_hopped;

/*
  A THIRD TAINT: this attempt was CHEATED.  Build 44.

  Outside run_t_flags for exactly the reason run_t_dirty is, and the case is the
  same one that essay was written about: noclip into the start zone, drop out of
  it, walk out.  Everything between the arm and the start is thrown away by
  SV_TimerArm's zeroing, so the bit that has to survive it lives here and
  SV_TimerStart consumes it.

  AND WHY THERE IS NO run_t_stitch BESIDE IT -- state this or somebody will "fix"
  the asymmetry by adding one.  A cheat is a STATE that can still be true at the
  moment you arm: sv_cheats can be on for the whole session and noclip is a
  movetype you can be sitting in.  A save-lock load is an EVENT.  Loading a save,
  walking back to the start box and re-arming is a genuinely fresh run and there
  is nothing left to carry -- so TF_SEGMENT goes into run_t_flags with the rest of
  the attempt and dies with it, which is correct.

  CLEARED FROM THE LEVEL by SV_TimerArm, not to zero, for the same reason
  run_t_dirty is: arming while noclipping, or with sv_cheats on, stays cheated.
*/
.float  run_t_cheat;

/*
  THE *ruleset BREACH COUNT AS IT STOOD WHEN THIS ATTEMPT'S CLOCK STARTED.
  Build 62.  BREACH, not seq: seq counts attempts to move a locked mover cvar,
  breach counts the ones that were not reverted and therefore actually changed
  the physics.  Differencing seq here would mark a run whose only sin was a
  mistyped cvar name the lock refused.  See SV_TimerRuleset.

  -1 means never sampled -- a pre-313 engine, or an attempt armed before this
  build -- and SV_TimerRuleset refuses to compare against it, so a missing
  sample can never manufacture a violation.
*/
.float  run_t_rbreach;

/*
  The client's off-profile transition count as it stood when this attempt armed.
  Build 72.

  The same shape as run_t_rbreach above and for the same reason: `inprof`'s
  current-state fields are a SNAPSHOT, and a snapshot cannot mark a span -- set
  m_accel at the top of the ramp and unset it before the end zone and both ends
  read clean.  So the client counts transitions into an off-profile state and
  this latches the count to difference against.  See SV_TimerProfile.

  -1 means never sampled -- a client that had sent no `inprof` key by the time
  this attempt armed -- and SV_ProfileBroken refuses to compare against it.  That
  matters more here than it does for the ruleset: `bad` counts for the life of
  the CLIENT, so a player who had mouse acceleration on ten minutes ago is still
  carrying a positive count, and differencing it against a zeroed field would
  mark a run for something that happened before it started.
*/
.float  run_t_pbad;

/*
  WHAT THIS CLIENT'S CSQC SAID, OVER THE CHANNEL ITS CONSOLE CANNOT WRITE.
  Build 78.  The why is the sendevent block in sh_defs.qc; this is the storage.

  run_t_pev IS THE ONE THAT MATTERS AND IT IS A PRESENCE FLAG, NOT A VALUE.  0
  means this client has never reported at all -- an older CSQC, `cl_nocsqc 1`,
  or a player who has not yet rendered a frame -- and SV_ProfileBroken turns
  that into TF_NOPROFILE rather than into "unknown".  Every other field here is
  meaningless while it is 0 and none of them may be read without checking it.

  THEY ARE CLEARED PER PLAYER, NOT PER RUN, and that is deliberate: they
  describe the CLIENT, which outlives any one attempt, so SV_TimerArm must not
  touch them.  What does touch them is SV_CSQCForget, from both ends of a
  connection -- the engine recycles edict numbers, and a slot handed to a new
  player still holding the last one's clean profile would rank a run nobody had
  checked.  That is SV_TouchForget's bug exactly, one layer up; see the essay
  there.
*/
.float  run_t_pev;        // 0 = never reported; else the grammar version reported in
.float  run_t_pevhave;
.float  run_t_pevraw;
.float  run_t_pevfilt;
.float  run_t_pevacc;
.float  run_t_pevbad;
.float  run_t_pevgrant;

/*
  ...AND WHETHER ITS JOURNAL IS RUNNING, OVER THAT SAME CHANNEL.  Build 79.
  The why is the build-79 block in sh_defs.qc; this is the storage.

  run_t_jev IS A PRESENCE FLAG AND IT IS NOT A VERSION, which is the one place
  this pair deliberately differs from the run_t_pev pair above.  There is no
  `rechid` grammar to select a field count from -- one value, two states -- so a
  version stored here would have a writer and no reader.  What versions the event
  is its NAME; see the essay.

  0 means this client's CSQC has never reported, and SV_TimerJournal turns that
  into TF_NOJOURNAL rather than into "unknown".  That is not the conservative
  reading, it is the true one: Rec_HidBegin is CSQC, so a client that cannot send
  this event cannot have written a .hid either.

  run_t_jevhid IS MEANINGLESS WHILE run_t_jev IS 0 and may not be read without
  checking it -- 0 there is "never spoke", not "said no", and the two are the
  same float.  Cleared per player by SV_CSQCForget for the edict-recycling
  reason above, which bites harder here: an inherited jevhid of 1 is a slot that
  claims a journal nobody asked it about.
*/
.float  run_t_jev;        // 0 = never reported; non-zero = this client's CSQC has spoken
.float  run_t_jevhid;     // what Rec_HidOK() answered: 1 journalling, 0 not

/*
  The worst class this attempt has been TOLD it is.  Build 44.

  A high-water mark and not a mirror of the flags: SV_SaveApplyState restores
  run_t_flags out of a file, so the class can go backwards mid-attempt, and a
  message keyed on the flags alone would then announce the same word twice as it
  climbed back.  This is what one gesture, one line depends on.

  It is a fact about what has been SAID, so it lives beside the flags and is
  cleared with them -- by the arm and by the idle, the two places a new attempt
  begins.  See SV_TimerClassSay.
*/
.float  run_t_said;

/*
  The run clock is stopped.  Build 18.

  run_t_freeze is the REQUEST -- something wants the clock held, and today that is
  only a save-lock hold.  It lives outside run_t_flags for the same reason
  run_t_dirty does, and the reason is sharper here: SV_TimerArm and SV_TimerIdle
  both zero run_t_flags, and BOTH ARE REACHABLE WHILE PARKED.  The arm test is a
  point test, so loading a save that sits inside a start box arms you without
  moving; a cancel zone reached by that same load voids you.  A flag those can
  clear would leave the clock ticking under a player who is still pinned.

  run_t_frzat is the elapsed SECONDS the clock stopped at, and run_t_frzon says the
  latch is live.  Seconds rather than ticks for the reason SV_TimerResume gives at
  length: a tick count is the elapsed time rounded, and re-deriving from it would
  walk the clock backwards half a tick every time the maintain ran.

  TF_FROZEN in run_t_flags is a per-tick mirror of all this, for the HUD.
*/
.float  run_t_freeze;
.float  run_t_frzat;
.float  run_t_frzon;

/*
  THE RECORDING LIVES IN A STRBUF, not in an open file.  Build 15.

  It used to be an incremental fputs into data/runs/<leg>.part, renamed at the
  end.  That looked like streaming and never was: PF_fclose is what actually
  writes (pr_bgcmd.c:2926 calls COM_WriteFile unconditionally), so the engine was
  already buffering the whole run in memory and the .part file was zero bytes
  until the moment it was closed.  The truncate-then-delete dance in
  SV_RecDiscard existed only to stop that write from happening on the way to a
  file we were about to remove -- which is most of practice, since every `!r`
  voids the run.

  So the buffer is now the thing, and the file is written once, straight to its
  final name.  Four things fall out of that:

    - a discard is buf_del: nothing is opened, so nothing has to be truncated,
      removed, or renamed, and the .part file stops existing at all;
    - a map change can no longer leave a stray .part behind;
    - a PREFIX of the run can be written (buf_writefile takes a count), which is
      what a save state needs to carry the movement up to the save point;
    - the line count is a mark that can be rewound to.

  rec_rec_lines counts EVERY line -- header, samples and the cp/stage/restart
  records interleaved with them -- because that is the index buf_writefile wants.
  rec_rec_n counts samples only, because that is what the `end` record reports and
  what the padding maths is expressed in.  They are not the same number and
  conflating them writes a truncated file.
*/
.float  rec_rec_buf;             // strbuf holding the whole recording, or -1
.float  rec_rec_lines;           // lines in it: the buf_writefile count
.float  rec_rec_n;               // samples written since `begin`
.float  rec_rec_padn;            // how many of them were padding
.float  rec_rec_cp;              // checkpoints crossed
.float  rec_rec_full;            // said once that this run hit its line cap
.float  rec_rec_lastbc;          // v4: last run_boardcount a `board` record covered
.float  rec_rec_flagline;        // v4: the buffer index of the reserved `flags` line

/*
  BUILD 82 -- THE INPUT TRACE'S TWO COUNTERS, and the second one is the whole
  reason the trace is worth writing at all.

  rec_rec_in is to `in` rows what rec_rec_n is to samples: the number the `end`
  record reports, so a reader can tell a truncated body from a short run.  It is
  a SEPARATE counter and not a reuse of rec_rec_n, because rec_rec_n's value is
  already spoken for by the padding arithmetic (rec_rec_padn is assigned FROM it
  at the end of the ring flush) and because `end` has always meant "samples" by
  that word.  Two facts, two counters.

  rec_rec_pk IS THE PACKET ORDINAL, AND IT IS THE ANSWER TO A DEFECT THIS
  FEATURE WOULD OTHERWISE HAVE SHIPPED WITH.

  Every other column of an `in` row describes one usercmd.  But the run's start
  and finish are not decided per usercmd: SV_TimerFrame runs from
  PlayerPostThink, which the engine calls ONCE PER PACKET (see the essay at
  SV_TimerElapsed and [[fte-postthink-is-per-packet]]), so a zone crossing is
  tested against the position the LAST command of a packet left you in, and the
  stored tick is latched there.  A verifier that re-ran the commands and tested
  zones after each one would land on a different tick from the one in the file,
  for a run that was in no way wrong -- and it would do so on exactly the runs
  where several commands arrive together, i.e. under packet loss, i.e. not
  reproducibly.

  So the grouping has to be IN the file.  It is stamped as a column rather than
  emitted as a marker record for two reasons: a marker would cost one more line
  per packet against a cap counted in lines, and a column cannot go missing --
  a dropped marker is indistinguishable from a packet with no commands in it,
  while a column that repeats is a group by construction.

  It is incremented at the TOP of SV_TimerFrame, so every row written by the
  PreThinks of one packet carries the value the previous packet's PostThink
  left behind.  That is all the reader needs: rows sharing a value belong to one
  packet, and the sample row that SV_TimerRecFrame writes at the end of that
  same SV_TimerFrame is that packet's post-state.  The ABSOLUTE value means
  nothing and no reader may attach meaning to it.
*/
.float  rec_rec_in;              // v6: input rows written since `begin`
.float  rec_rec_pk;              // v6: packet ordinal, stamped on each of them
.float  rec_rec_warp;            // v7: `warp` records written since `begin`

/*
  BUILD 85 -- THE CARRIER'S THREE FIELDS.

  rec_rec_bv is the last basevelocity the recorder WROTE DOWN, not the last one
  the mover was handed; the writer emits only on a difference, so the file
  carries one record per CHANGE (7 spans = ~14 records against 10,926 `in` rows).

  rec_rec_bvset is a sentinel, not a convenience: '0 0 0' is a legitimate carrier
  state, so without a flag the run's first record would be written only when the
  carrier happened to be non-zero.  SV_RecOpen clears it and the next command
  writes an unconditional floor record -- see the grammar block for why "zero at
  `begin`" is not a safe default.
*/
.float  rec_rec_ride;            // v8: `ride` records written since `begin`
.vector rec_rec_bv;              // v8: the carrier value last written down
.float  rec_rec_bvset;           // v8: rec_rec_bv means something
// v9 (build 87): the state records -- see the grammar block and SV_RecState.
.float  rec_rec_epoch;           // v9: pin epoch last written down (header or `pm`)
.float  rec_rec_pcrc;            // v9: physent digest last written down
.float  rec_rec_pcset;           // v9: rec_rec_pcrc means something
.float  rec_rec_portalx;         // v9: portal crossings already written down
.float  rec_rec_pm;              // v9: counts for the trailer, by landed line
.float  rec_rec_pe;
.float  rec_rec_portal;
.float  rec_rec_zseed;           // v9, build 88: a `zseed` record is owed

/*
===========================================================================
  BUILD 66 -- THE SECOND RECORDER, and it is the same recorder.

  Everything above holds the whole run in the QC string table until it closes,
  and the essay over rec_rec_buf explains why that is the honest shape rather
  than a lazy one: QC's FILE_WRITE does not stream either, it merely hides the
  buffer inside the engine and writes at fclose, and FILE_APPEND is worse
  because it reads the file back IN at open.  The .part file that preceded the
  buffer was zero bytes for the whole run.  There was no third option.

  ENGINE PATCH 316 ADDS ONE.  FS_FILE_WRITESTREAM (fopen mode 9) write-throughs
  every fputs with VFS_WRITE, so peak memory becomes ONE LINE instead of a whole
  run -- and fseek still works on the handle, which is the only reason the
  reserved `flags` header line survives the change.

  WHY THIS IS NOT SIMPLY THE NEW DEFAULT.  The buffer is not only storage; three
  features read it as a random-access array, and a stream is not one:

    * a discard is buf_del -- nothing was opened, so nothing has to be removed;
    * a SAVE STATE writes a PREFIX of it (buf_writefile takes a count) and a
      load REWINDS to a line index, which is what makes a saved-and-resumed run
      one continuous file rather than three fragments;
    * a STAGE DEMO is a RANGE of it lifted out and rebased at the boundary --
      SV_StageWrite reads lines [first..last] of a run that is still going.

  The last two are features, not implementation details, and a stream cannot
  give either of them without a second file open for the whole run.  So the two
  recorders both stay and the choice is made per run:

      OFF A LOBBY   the buffer, and everything above keeps working.  Memory was
                    never the problem here -- one player, one run.
      ON A LOBBY    the stream, forced.  Save points are already off in a lobby
                    (lobby_nosaveloc) so the prefix/rewind pair has no caller,
                    and stage lifting is declined with a line in the log rather
                    than silently producing nothing.

  That is a seam rather than a compromise: the features the stream cannot do are
  exactly the features a lobby already does not have.

  rec_stream exists so the streaming path can be exercised, and finished, off a
  lobby -- a run cannot be finished from a config on a zoned map, so the only
  way to test this at all is a real run on a listen server.  It defaults to 0,
  which is today's behaviour exactly.
===========================================================================
*/
.float  rec_rec_fh;              // the open stream, or -1.  Streaming runs only.
.float  rec_rec_stream;          // this run is being streamed, not buffered
.float  rec_rec_flagofs;         // byte offset of the reserved `flags` line
// Patch 375: a lobby save-load keeps its stream.  See SV_RecSnapshot.
.float  rec_rec_ver;             // line 0 of the stream as written: 9 or 10
.float  rec_rec_partlob;         // the part file's name as opened: 1 lobby, 2 plain, 0 not yet
.float  rec_rec_inmt, rec_rec_incy; // the last `in` row's <mt> <carry> (or instart's, 0)
.float  rec_rec_gen;             // warm rewinds since the serial began
.float  rec_rec_genbuf;          // strbuf: the mark each of them truncated to
.float  rec_cp_q;                // strbuf: pending save copies, "<bytes> <done> <dst>"
.float  rec_cp_head;             // the next one to work on
// Patch 376: the client's mouse counts, in-band (engine cl_input.c CL_SendCounts),
// read for the command being run.  See the `mc` record.
vector  input_cursor_trace_start, input_cursor_trace_endpos;
.vector rec_mc_ring, rec_mc_read;    // the last `mc` written
.float  rec_mc_n, rec_mc_bad, rec_mc_badrow;
.float  rec_mc_sup;                 // Patch 405: commands that sent cursor data
                                    // instead of counts -- the off switch, seen
// Patch 416: the run nonce.  See SV_RecNonce for what it is for and what it is
// worth.  Zoned, freed and rebuilt at every open.
.string rec_rec_nonce;              // the 32 hex chars in force for this run
string  run_nonce_seed;             // per-boot, zoned; the seed under all of them
// Patch 418: what `fs_ul` was PUBLISHED as at map init.  Read instead of the
// cvar so the server cannot ask for evidence under a policy its clients were
// never told about -- the key is sent once and the cvar can move afterwards.
float   run_t_evul;
.float  rec_rec_rcpt;               // Patch 417: this run's receipt is written
// Patch 426: THE RUN THAT ENDED, held for its receipt -- a finish (SV_RecClose)
// or an abandon the lobby kept as evidence (SV_RecDiscard).  The client signs a
// round trip after the end, and by then the live id and nonce may be gone: an
// abandon drops them in the same frame (p426cl.cfg), and a finish loses them to
// the next arm or run (p426bcl.cfg: a stage-1 finish, then leaving S2 armed
// stage 2).  Held only while it is the last run to END -- every other end, a
// connect and a disconnect clear it -- and taken only by a receipt that signs
// its tick count, so a late receipt cannot land on a later run.
.string rec_end_rid;
.string rec_end_nonce;
.float  rec_end_ticks;              // svticks: the RUNTICKS the client saw at the end
.float  rec_end_at;                 // `time` it was held (a load's own hold: this frame)

/*
  The reserved `flags` line, in one place and at a FIXED WIDTH.

  A stream cannot change a line's LENGTH after the fact -- seeking back and
  writing a longer `flags 1027` over a shorter `flags 0` would eat the newline
  and the first character of the line after it -- so the field is padded out at
  open and the correction writes the same number of bytes it reserved.

  ONE SPELLING FOR BOTH RECORDERS even though the buffered one could rewrite
  freely, because two ways of writing a header line that must agree is the exact
  drift this file has been bitten by before (see FS_TagArchived, build 45: one
  of the two spellings was updated and the other was not, and the failure was
  silent).  The cost is ten trailing spaces in every new .rec.

  Every reader was checked before choosing trailing whitespace over a
  zero-padded number: cl_scores.qc:293 and cl_watch.qc:528 both tokenize and
  stof argv(1), and tools/reccheck.py does int(float(...)) -- all three are
  unaffected by trailing spaces, and a zero-padded `flags 00000` would have been
  a worse choice for a human reading the file.
*/
string(float flags) SV_RecFlagLine =
{
	return sprintf("flags %-10s", ftos(flags));
};

/*
  Does a run starting now stream, or buffer?

  A lobby always streams, and it is not offered a choice: the whole reason
  lobby_norec exists is that 32 buffered recordings is an out-of-memory, so a
  lobby that recorded by buffering would be the defect rather than the feature.
*/
float() SV_RecStreams =
{
	if (Lobby_Active())
		return TRUE;
	return cvar("rec_stream") != 0;
};

/*
  Where a streamed run is written WHILE IT RUNS.

  It cannot go to its final name: that name carries the run's tick count
  (FS_RunPath) and the tick count is not known until the run has finished.  So
  the stream writes here and SV_RecClose renames.

  NOT UNDER data/runs/.  Scores_BuildRows enumerates every ".rec" in a leg's own
  folder, so a part file sitting in there would be picked up by the local scoreboard
  mid-run; it would in fact be dropped, because FS_TagFromName does not know the
  word and an unrecognised tag drops the row silently -- but relying on one bug
  to hide another is not a plan.  A separate directory cannot be enumerated by
  accident.

  Keyed on the run slot rather than on the player, because the slot is what makes
  it unique among the runs in progress ON THIS SERVER RIGHT NOW, which is the
  only collision a part file can have.  Two players finishing on the same tick
  collide on the FINAL name instead, and that is a separate defect with its own
  fix.
*/
string(entity e) SV_RecPartPath =
{
	// The Pi's lobbies share one data dir, so every lobby's slot 0 was one file
	// (and the evidence keep renames it).  Keyed by port there; offline unchanged.
	// Patch 375: the name as opened, so a lobby_enable flip mid-run cannot move it.
	if (e.rec_rec_partlob ? (e.rec_rec_partlob == 1) : Lobby_Active())
		return sprintf("data/parts/p%s-%g.rec", cvar_string("sv_port"), e.run_t_slot);
	return sprintf("data/parts/%g.rec", e.run_t_slot);
};

/*
  IS THERE A RECORDING OPEN RIGHT NOW?

  `rec_rec_buf >= 1` used to be the whole answer and was spelled out at four
  call sites, which is exactly what made build 66's first cut wrong: the
  recorder streamed, the strbuf stayed at -1, and every one of those four tests
  quietly said "not recording".  The run produced a file containing its header
  and its pre-start padding and NOTHING ELSE -- 102 samples, all of them
  padding, against the control's 271 -- and it did it without one error line,
  because each site's failure is to skip rather than to complain.

  The four were the per-frame SAMPLER (SV_TimerRecFrame), the `board` record
  (SV_RecBoard), the `ghost` record (SV_TimerGhost) and the stage slice
  (SV_StageClose).  Three of those write the columns that make a recording worth
  having; the fourth decides whether a stage is lifted at all.

  So the test is a function now, and the rule is: anything asking "should I
  write this?" asks here, and only code that specifically means THE STRBUF
  touches rec_rec_buf.
*/
float(entity e) SV_RecLive =
{
	if (e.rec_rec_stream)
		return e.rec_rec_fh >= 0;
	return e.rec_rec_buf >= 1;
};

/*
  Patch 375: a lobby save's copy of the stream's prefix, written to disk "after a
  bit" -- FS_RECCOPY_CHUNK bytes per packet from SV_TimerFrame -- rather than
  held in memory.  Bytes below a save's mark never change while the part file
  is open, so anything that closes, renames, truncates or reopens it finishes
  the player's copies first (SV_RecCopyFlush).  A failed copy removes its target;
  that save then loads warm only.  Byte counts are ints: a float is exact only to
  16 MB.
*/
#define FS_RECCOPY_CHUNK 524288
#define FS_RECCOPY_MAX   268435456      // 256 MB: a bigger prefix is not copied

void(entity e, int budget) SV_RecCopyStep =
{
	local int b, d, n, r;
	local string src, dst;

	while (e.rec_cp_q >= 1 && budget > 0)
	{
		if (e.rec_cp_head >= buf_getsize(e.rec_cp_q))
		{
			buf_del(e.rec_cp_q);
			e.rec_cp_q = 0;
			e.rec_cp_head = 0;
			return;
		}
		tokenize(bufstr_get(e.rec_cp_q, e.rec_cp_head));
		b = stoi(argv(0));
		d = stoi(argv(1));
		src = argv(2);                  // taken at the save: lobby_enable can flip
		dst = argv(3);
		n = b - d;
		if (n > budget)
			n = budget;
		if (n > 0)
		{
			r = fcopyrange(src, d, n, dst, d > 0);
			if (r != n)
			{
				dprint(sprintf("timer: save copy %s failed at %s of %s bytes (got %s)\n", dst, itos(d), itos(b), itos(r)));
				fremove(dst);
				n = b - d;
			}
			d = d + n;
			budget = budget - n;
		}
		if (d >= b)
			e.rec_cp_head = e.rec_cp_head + 1;
		else
			bufstr_set(e.rec_cp_q, e.rec_cp_head, sprintf("%s %s %s %s", itos(b), itos(d), src, dst));
	}
};

void(entity e) SV_RecCopyFlush =
{
	if (e.rec_cp_q >= 1)
		dprint(sprintf("timer: finishing %g pending save cop%s now\n",
		               buf_getsize(e.rec_cp_q) - e.rec_cp_head,
		               (buf_getsize(e.rec_cp_q) - e.rec_cp_head == 1) ? "y" : "ies"));
	while (e.rec_cp_q >= 1)
		SV_RecCopyStep(e, FS_RECCOPY_MAX);
};

// A slot that is deleted or saved over: its pending copy must not land -- in
// anyone's queue, since a dropped connection's edict keeps its own a while.
void(string dst) SV_RecCopyDrop =
{
	local float i;
	local entity p;

	p = world;
	while ((p = find(p, classname, "player")))
	{
		if (p.rec_cp_q < 1)
			continue;
		for (i = p.rec_cp_head; i < buf_getsize(p.rec_cp_q); i = i + 1)
		{
			tokenize(bufstr_get(p.rec_cp_q, i));
			if (argv(3) == dst)
				bufstr_set(p.rec_cp_q, i, "0 0 - -");
		}
	}
};

int   rec_snap_bytes;                   // SV_RecSnapshot -> SV_RecSaveKeys, one save
int   rs_bytes;                         // the save being loaded: 0 = no stream copy
float rs_gen, rs_ver, rs_flagofs, rs_pend;
float rs_in, rs_pk, rs_warp, rs_ride, rs_pm, rs_pe, rs_portal, rs_pinned;
float rs_pauses, rs_sess, rs_inmt, rs_incy;
string rs_rid;

float(entity e, float mark) SV_RecGenOK =
{
	local float g;

	if (rs_gen < 0 || rs_gen > e.rec_rec_gen)
		return FALSE;
	if (rs_rid == "" || rs_rid != e.rec_rec_rid)
		return FALSE;
	for (g = rs_gen + 1; g <= e.rec_rec_gen; g = g + 1)
		if (e.rec_rec_genbuf < 1 || stof(bufstr_get(e.rec_rec_genbuf, g)) < mark)
			return FALSE;
	return TRUE;
};

void(entity e, float mark) SV_RecGenPush =
{
	if (e.rec_rec_genbuf < 1)
		e.rec_rec_genbuf = buf_create_ex("string", 0);
	e.rec_rec_gen = e.rec_rec_gen + 1;
	if (e.rec_rec_genbuf >= 1)
		bufstr_set(e.rec_rec_genbuf, e.rec_rec_gen, sprintf("%d", mark));
};

void(entity e) SV_RecGenReset =
{
	if (e.rec_rec_genbuf >= 1)
		buf_del(e.rec_rec_genbuf);
	e.rec_rec_genbuf = 0;
	e.rec_rec_gen = 0;
};

float(entity e, string path) SV_RecSnapshot =
{
	local int b;

	rec_snap_bytes = 0;
	if (e.rec_rec_fh < 0 || e.rec_rec_lines <= 0 || !checkbuiltin(fcopyrange))
		return 0;
	b = fsize(e.rec_rec_fh);            // flushes (Patch 375)
	if (b <= 0 || b > FS_RECCOPY_MAX)
		return 0;
	if (e.rec_cp_q < 1)
	{
		e.rec_cp_q = buf_create_ex("string", 0);
		e.rec_cp_head = 0;
		if (e.rec_cp_q < 1)
			return 0;
	}
	SV_RecCopyDrop(path);
	bufstr_set(e.rec_cp_q, buf_getsize(e.rec_cp_q),
	           sprintf("%s 0 %s %s", itos(b), SV_RecPartPath(e), path));
	rec_snap_bytes = b;
	return e.rec_rec_lines;
};


/*
  BUILD 24 -- THE STAGE CURRENTLY BEING RUN INSIDE A MAIN RUN.

  A main run passes through every stage on the map, and each of those is a leg
  with its own folder and its own leaderboard that until now could only be filled
  by arming at that stage deliberately.  These five track the one in progress so
  that its slice of the recording can be lifted out at the next boundary.

  run_st_line is the index into the SAME buffer the whole run is being written
  into -- there is no second recorder.  buf_writefile takes a start and a count,
  which is the entire reason this is affordable: a stage demo is a range of lines
  that are already in memory, not a second copy of them.

  run_st_jump is the filter, and run_st_ramp is what makes it honest -- see
  SV_StageJump.  run_st_seg is the SEGMENT index the stage begins at.

  BUILD 57: THIS USED TO SAY run_st_seg IS THE LEG, and FS_LegDir spelled it
  stage_N, which is one stage early -- segment N is stage N+1 -- and it made
  segment 0, stage 1, unwritable because 0 was `main`.  The leg of segment s is
  s + 1, always, and FS_LegOf(s, TRUE) is how every writer spells it.
*/
.float  run_st_seg;              // the 0-based segment, or -1 when no stage is open
.float  run_st_line;             // buffer index where this stage's samples start
.float  run_st_tick;             // the run clock the stage began at
.float  run_st_jump;             // it began with a jump: this one is recordable
.float  run_st_ramp;             // a ramp has been touched since the boundary

/*
  BUILD 43 -- A STAGE IS ARMED AND STARTED, THE WAY A RUN IS.

  Build 24 timed a stage from the tick the boundary plane was crossed.  That is
  the right measurement for a boundary you FLY through and the wrong one for a
  boundary you LAND on: on a platform you land, stand, and jump off, and the
  standing was being timed.  Worse, the plane crossing is not a thing you can do
  again -- fail the stage, walk back up, and the clock kept the crossing you made
  two minutes ago, so the "stage time" written at the next boundary was the whole
  failed attempt plus the good one.

  So a stage boundary now uses the state machine the RUN START already uses, in
  the same three states and with the same names:

    ARMED    run_st_armed.  The clock base is still the crossing tick, so nothing
             has changed yet, and run_st_hold says whether you have actually been
             observed inside the boundary box.
    STARTED  you left the box.  SV_StageStart rebases run_st_tick to that tick,
             writes a `stagestart` record, and asks SV_StageJump whether the
             exit qualifies.  This is what the request means by "no pre-speed".
    FAILED   you came back INTO the box.  SV_StageFail rebases the split, counts
             it, writes a `restart` record and re-arms -- so the next attempt at
             this stage is judged from a clean slate exactly like the first.

  THE BOX ITSELF IS NOT PART OF THIS STATE.  SV_StageZone derives it by identity
  from the segment in progress -- see SV_StageOpen for the three paths a zone
  index remembered at the crossing does not survive -- and run_st_zone/run_st_zseg
  below are only a CACHE of that derivation, keyed on the segment they answer
  for, so a stale pair cannot be read as a fresh one.  The state here is only
  "which of the three are we in", which is what these two answer.

  run_st_hold IS NOT REDUNDANT WITH run_st_armed, and the case that needs it is the
  common one.  A boundary crossed at 2000 u/s is never occupied, so there is
  nothing to leave -- and without a "did we ever stand in it" latch, the first
  tick outside the box would look identical to walking out of it and would rebase
  the clock in the middle of a surf.  With it, a fly-through disarms on that same
  tick and keeps build 42's measurement exactly.

  run_st_fails and run_st_tp are PER STAGE and survive a fail (you are failing the
  same stage again) but not a boundary.  They are cleared by SV_TimerSplit and
  SV_TimerStart, which are the two places a genuinely different stage begins --
  NOT by SV_StageOpen, which a fail also goes through and which would therefore
  reset the count it exists to keep.
*/
.float  run_st_armed;            // the clock has not rebased yet; the box can still start it
.float  run_st_hold;             // observed inside that zone since it opened
.float  run_st_zone;             // SV_StageZone's cached answer, or -1
.float  run_st_zseg;             // the segment it was resolved for; -1 = unresolved
.float  run_st_fails;            // times this stage has been re-entered
.float  run_st_tp;               // teleports taken while this stage was open

/*
  BUILD 43 -- THE TAINT, PER STAGE, AND WHY IT CANNOT BE THE RUN'S.

  "if a stage is done in practice mode, but the next one has been started legit
  then that stage should be counted as legit and recorded."  So the question
  SV_StageClose asks stops being "is this RUN clean" and becomes "is this STAGE
  clean", and the answer has to be destroyed at every boundary -- which is the
  exact opposite of what run_t_dirty and run_t_hopped do.  Those two live outside
  run_t_flags precisely so they SURVIVE SV_TimerArm's zeroing; these are cleared
  by SV_StageOpen, because "the next stage starts clean" is the whole feature.

  ONE CLEAR SITE, and it is the same function that rebases the slice.  A fail and
  a fresh boundary then forgive identically by construction rather than by two
  rules that could drift apart later.

  THE HOLE THIS WOULD OTHERWISE SHIP, written down because it passes every test
  that toggles the state inside one stage:  SV_NoclipWatch is an EDGE detector.
  If the edge fired in stage 2 and you are still noclipping when you cross into
  stage 3, SV_StageOpen clears the taint and stage 3 is admitted as clean while
  you fly through it.  So the watchers set the per-stage field at LEVEL -- every
  tick the state is true -- and call the run-level funnel only on the EDGE.
  run_st_ghost is set at level in SV_TimerFrame's ghost branch for the same
  reason: a ghost that spans a boundary must taint both stages, not neither.
*/
.float  run_st_dirty;            // noclip/setpos/save-load touched THIS stage
.float  run_st_ghost;            // the camera was detached during THIS stage

/*
  ...AND WHY, build 44.  The same split TF_SEGMENT and TF_CHEAT make of
  TF_PRACTICE, one level down.

  run_st_dirty STAYS THE UMBRELLA and is still the only thing SV_StageClose
  refuses on, so nothing about which stages get written changes with these two.
  They exist so the answer to "why did that stage not record" is on screen and in
  `cmd timer`, and so SV_StageWrite's header can carry the same word the run's
  does -- a stage lifted out of a run is a .rec like any other and a reader that
  understood the parent's flags would otherwise get a coarser answer from the
  child.

  BOTH ARE CLEARED AT EVERY BOUNDARY, with the umbrella, by SV_StageOpen.  The
  cheat half is re-read FROM THE LEVEL there, not zeroed: sv_cheats being on is a
  state that outlives a boundary, which is the whole hole the level-vs-edge rule
  above exists to close.  The stitch half genuinely zeroes, because a save-lock
  load is an event and crossing a boundary afterwards puts it behind you -- the
  same asymmetry run_t_cheat and the missing run_t_stitch have at run level.
*/
.float  run_st_stitch;           // a save state was used inside THIS stage
.float  run_st_cheat;            // noclip/setpos/sv_cheats inside THIS stage

/*
  The five above, packed for the wire.  Build 43.  See STAT_FS_STAGEST.

  A MIRROR AND NOT THE TRUTH, exactly like TF_FROZEN: the truth is in the fields
  and this is recomputed from them once per tick by SV_StageStat.  It has to be
  recomputed rather than maintained, because five writers keeping one packed word
  in step is five chances to forget one, and the bug that produces -- a HUD that
  says `armed` about a stage that started ten seconds ago -- is the kind nobody
  reports because it looks like the feature merely being confusing.
*/
.float  run_st_word;

// Networked; see the STAT_FS_STAGE* block in sh_defs.qc.  Written in one breath.
.float  run_st_rec;              // monotonic, the client's edge
.float  run_st_recseg;
.float  run_st_recticks;
.float  run_st_recat;

/*
  BUILD 48 -- THE CLOSE REPORT, and it is deliberately NOT the four above.

  run_st_rec* is "a stage was WRITTEN": it is published at the bottom of
  SV_StageClose, past every refusal, and it exists so the client can slice the
  matching .view.  This group is "a stage ENDED, and here is what it was" --
  published at the TOP, before any refusal, because the interesting stages are
  precisely the ones that did not qualify.

  Two groups and not one widened group, because the two answer opposite
  questions and a reader that conflated them would draw a mark only on the
  stages that did not need one.

  WHY THE CLIENT CANNOT DERIVE ANY OF IT:

    the WORD      run_st_dirty, _cheat, _ghost and _stitch are all rewritten by
                  SV_StageOpen from the live level in this same
                  PlayerPostThink, and on a finish SV_StageStat's own
                  `run_st_seg < 0` guard zeroes the packed word outright.  The
                  engine samples stats when it builds the snapshot -- after
                  every PlayerPostThink -- and deltas against the last value it
                  SENT, so a value that lives and dies inside one
                  PlayerPostThink is never on the wire to be read.
    the TICKS     run_stagearm rebases run_st_tick to the moment you LEFT the
                  boundary box, so a stage's own duration is NOT the difference
                  between two consecutive run-relative splits and never was.

  run_st_endrec IS BUMPED ON EVERY CLOSE, INCLUDING REFUSED ONES.  A counter
  rather than a flag for the reason run_st_rec is one: a dropped snapshot loses
  a one-tick boolean outright, whereas a counter arriving two higher is a gap
  the reader can see and account for.
*/
.float  run_st_endrec;           // monotonic; bumped at the TOP of SV_StageClose
.float  run_st_endseg;           // the segment that closed
.float  run_st_endword;          // its SF_* word at the close, with SF_KNOWN
.float  run_st_endticks;         // its own duration, in ticks
.float  run_st_endlaunch;        // Patch 360: its launch speed (stat 100); -1 = never left its box
.float  run_st_endpbwas;         // Patch 361: its leg's PB before this close (stat 99, the banner)

/*
  PATCH 360, STAGE FILL-IN.  The takeoff that began this flight: tkok 1 = primed
  (the +forward-release dwell was met: a jump, or a walk-off), -1 = a hop, 0 =
  none.  Cleared by a ramp and by SV_StageOpen; a landing moves it to tkland for
  one tick, so a primed jump that lands on the box-exit tick still counts.  The
  verdict (prime, launch speed) is taken at the box exit by SV_StageLaunch.
  Ramp contact is read from run_boardcount, which is cumulative: run_rampcontact
  is only the packet's LAST tick, and a packet can hold up to 8.
*/
.float  run_st_tkok;
.float  run_st_tkspd;
.float  run_st_tksec;
.float  run_st_tkbc;             // run_boardcount before the takeoff's packet
.float  run_st_bcseen;           // run_boardcount at the end of the last JumpWatch
.float  run_st_tkland;
.float  run_st_tklandspd;
.float  run_st_tklandsec;
.float  run_st_prime;
.float  run_st_launch;
.float  run_st_launchsec;        // when the judged takeoff happened (SV_TimerStart vs the arm)
.float  run_t_armsec;            // SV_ClockSec at the arm: the opening stage's takeoff must follow it
.float  rec_rec_posts;           // `stagepost` records in this recording (the abandon keep)
float   run_t_stagecap;          // run_stagecap, cached per map
float   run_t_startcap;          // run_startcap, cached per map (Patch 403)
// Patch 364 (v10).  Recounted from the body on every rewind, like the trailer's counts.
.float  rec_rec_pauses;          // `pause` records: any at all makes the file v10
.float  rec_rec_sess;            // `session` records: the trailer's 11th field
.float  rec_rec_sesspend;        // a pause is open: 1, or 2 when a `seed` is owed with the session
.float  rec_rec_pinned;          // the header carries `pmpin` (a seed is written only with it)
float   rec_rewind_cold;         // SV_RecRewind's last success read its prefix off disk
// Multi-Session (sv_resume.qc).
.float  run_ms_sessions;         // `session`s this run has had (stat 101); 0 = one session
.float  run_st_ms;               // the open stage spans a pause: it never qualifies
.float  run_st_sp;               // Patch 382: ...or a spectate window
.float  run_ms_phase;            // a resume is restoring/counting down: no zone acts

/*
  BUILD 57, STAGE T -- THE FINISH, AS A COUNTER WITH ITS ANSWER BESIDE IT.

  The group above is "a stage ended"; this one is "a LEG ended".  It exists
  because in a lobby the client cannot see a finish at all: the recorder is off,
  so SV_RecClose -- which publishes RUNTAG, RUNTICKS and RUNLEG -- is never
  reached, and TS_FINISHED can be skipped outright when run_t_pendarm re-arms a
  chained stage run inside the same server frame.  The full argument is over
  STAT_FS_FINREC in shared/sh_defs.qc.

  BUMPED BY EVERY FINISH, lobby or not, for the reason run_st_endrec is bumped by
  every close: one rule at the one site that owns the event is cheaper than a
  condition somebody has to remember, and a counter turns a dropped snapshot into
  a visible GAP rather than a lost event.

  THEY ARE NOT CLEARED BY THE NEXT ARM.  `results` reopens the last card from
  these, exactly as it reads a RUNTAG that SV_RecDiscard deliberately leaves
  standing; a value that died with the attempt would make that command lie.
*/
.float  run_t_finrec;            // monotonic; bumped LAST, in SV_TimerFinish
.float  run_t_finticks;          // the time the finish was measured at
.float  run_t_finleg;            // RUNLEG's encoding: track * 100 + leg + 1
.float  run_t_finflags;          // TF_*, as the finish left them
.float  rec_pad_head;            // next ring slot to write
.float  rec_pad_len;

// Published as stats so the client can name its angle sidecar after the same
// run.  See STAT_FS_RUNLEG / STAT_FS_RUNTAG in shared/sh_defs.qc.
.float  rec_rec_leg;
.float  rec_rec_tag;
// BUILD 23: and the time, because the time is now part of the filename.  Set
// and cleared in exactly the same breath as rec_rec_tag, everywhere, so the two
// can never describe different runs.  See STAT_FS_RUNTICKS.
.float  rec_rec_ticks;

/*
  BUILD 66: DID THE FILE ACTUALLY LAND, AND HOW BIG WAS IT.

  rec_rec_ticks and rec_rec_tag say what the recording WOULD be called.  They
  are set on every close, including the one where the rename failed and the
  bytes are still sitting in data/parts/ under a name nothing will ever serve
  -- because their job is to tell the CLIENT which tag and time to name its own
  sidecar after, and that is true either way.

  The leaderboard needs the other question answered, and it is a different one:
  is there a file at that name on this disk?  Only the close knows, and only
  for the moment it ran.  Submitting a name for bytes that are not there would
  put a row in surfd's ledger pointing at nothing -- the exact failure the
  ledger exists to prevent, arrived at from the other end.

  A FLOAT AND NOT THE NAME ITSELF.  A .string field has to be strzone'd to
  survive the sprintf that built it and strunzone'd on every one of the five
  sites that clear this group, and getting that wrong leaks the string table
  slowly enough not to be noticed -- the argument rec_rec_runid already makes
  two declarations below.  The name costs one FS_RunLeaf call to rebuild at the
  finish, from the same pieces and the same helper that built it here.

  rec_rec_bytes is the recorder's own final offset, taken before the header
  fixup seeks backwards.  -1 means "not known", which is honest for the
  buffered recorder and for a run whose file did not land.
*/
.float  rec_rec_saved;           // the file is at its final name, right now
.float  rec_rec_bytes;           // its size at close, or -1

/*
  WHICH RUN THIS BUFFER IS, so a save state can tell "rewind the buffer you are
  already holding" from "read the prefix back off disk".  Build 17.

  A number and not the `runid` string that goes in the file header, and that is
  deliberate.  A QC string field has to be strzone'd to survive the sprintf that
  built it and strunzone'd on every overwrite, and getting that wrong leaks the
  string table slowly enough not to be noticed -- for a value whose only use is
  an equality test.  A monotonic float answers the same question exactly.

  Patch 364: this used to be a global, per map in fact (PR_Deinit zeroes globals
  on every map load).  A retry's cold rewind then made a buffer with serial 1
  again, a save from before it matched, and the load rewound WARM across the
  counter restart -- no `pause` (p364rewind arm D: "movetick goes backwards").
  Now a cvar, based once per process on the minute of the month x 256 so an
  older process's saves miss too; %d in the save and < 2^24, so it stays exact.
*/
.float  rec_rec_serial;
float() SV_RecNextSerial =
{
	local float s;
	s = cvar("rec_serial");
	if (s <= 0)
		s = ((stof(strftime(TRUE, "%d")) - 1) * 1440 + stof(strftime(TRUE, "%H")) * 60
		     + stof(strftime(TRUE, "%M"))) * 256;
	s = s + 1;
	cvar_set("rec_serial", sprintf("%d", s));
	return s;
};

/*
  The slot a run was resumed from, + 1.  0 is "not a shadow run".

  Outside run_t_flags on purpose, the same way run_t_dirty is: it has to name a
  SLOT, and it has to survive long enough to label the recording at close.
  Cleared by SV_TimerArm, which is where a new attempt begins.
*/
.float  run_t_fromsave;

/*
===========================================================================
  Slots
===========================================================================
*/
void(entity e) SV_TimerClaimSlot =
{
	local float i;

	e.run_t_slot = -1;
	for (i = 0; i < FS_MAXPLAYERS; i = i + 1)
	{
		if (run_slot_owner[i] == e)      // already ours (a reconnect)
		{
			e.run_t_slot = i;
			return;
		}
	}
	for (i = 0; i < FS_MAXPLAYERS; i = i + 1)
	{
		if (run_slot_owner[i] == world)
		{
			run_slot_owner[i] = e;
			e.run_t_slot = i;
			return;
		}
	}
};

void(entity e) SV_TimerReleaseSlot =
{
	local float i;
	for (i = 0; i < FS_MAXPLAYERS; i = i + 1)
		if (run_slot_owner[i] == e)
			run_slot_owner[i] = world;
	e.run_t_slot = -1;
};

// The formatting itself is shared with the HUD -- see shared/sh_time.qc for
// why that is not a duplicated twelve lines.
string(float ticks) SV_TimerString = { return Time_TickString(ticks, run_t_tick); };

/*
===========================================================================
  The recorder

  FTESURF-REC 9, in full, because four different things are going to read this
  and a grammar spread across five functions is one nobody can check against.

  (This heading said "FTESURF-REC 5" while the writer emitted 6, from build 82
  until build 83 corrected it.  Left noted rather than silently fixed: a reader
  who edits this block by following its own title documents the wrong version,
  and that is a trap worth one sentence.)

    FTESURF-REC 9           always first; 10 once a `pause` is written (Patch 364)
    map <name>              header, one key per line, ANY ORDER, and an
    track <n>               unknown key MUST be skipped rather than rejected --
    startseg <n>            that rule is what let v3 add three keys to v2's
    leg <n>                 five without breaking anything, and v4 four more
    tickrate <f>            the game's cached cvar("pm_ticrate")
    movetickrate <f>        v4 key, build 74: the rate the MOVER divided by.
                            0 means no engine value.  A reader that turns ticks
                            into seconds must prefer this one when it is present
    clock counted|sampled   v5, build 76.  Which clock produced every time in
                            this file.  Absent means sampled, which is what every
                            file before build 76 meant
    owner <name>            may contain spaces; read to end of line
    runid <str>             unique-ish: local wall clock to the second + slot
    nonce <hex32>           Patch 416.  The 128 bits the server picked when this
                            session opened and told the running client.  Additive
                            by the rule above; absent on every file written before
                            416 and on one whose engine has no SHA256.  The
                            matching answer is not a record: it is TF_NONCE in
                            `flags`.  A LATER SESSION HAS ITS OWN, written into
                            the body as `nonce <mt> <hex32>` -- see SV_RecNonce
    mapcrc <hex>            v4 key, build 73: the BSP THIS SERVER loaded
    zonesrc local|online|bsp  build 81.  WHICH OF THE THREE zone sources built
                            the table this run was timed against
    zonecrc <hex>           build 81.  8 hex of sha256 over the BUILT table --
                            not over the JSON file, so the BSP path's one-unit
                            deflation hashes differently from a JSON of the same
                            brush.  See Zone_Hash in sh_zones.qc
    zonerule <s> <h> <hl>   build 81.  run_zone_swept, run_zone_hull,
                            run_zone_hull_live as latched for this map.  Not
                            geometry and not movevars: two servers with the same
                            table and different rules give different times
    instart <mt> <start>    v6, build 82.  The mover tick this file's INPUT TRACE
                            begins at, and the run's own start tick.  Absent
                            means the file carries no `in` records at all.
                            Present, it is the trace's HORIZON: no `in` row can
                            exist below <mt>, so a verifier knows the commands
                            that carried the player across the start plane are
                            not in this file and must seed from the first sample
                            instead of re-deriving the start.  The two numbers
                            are EQUAL on a fresh start, by SV_TimerStart, and
                            differ after a save-state resume, which rebases the
                            start tick and not the mover's counter -- so their
                            difference is the one fact a reader cannot get any
                            other way
    startjit <u> <dx dy dz> v7, build 83.  THE RANDOMIZED START: the rule that
                            was in force, in units, and the offset the server
                            actually applied to the player at the instant the
                            clock started.  dz is always 0 -- the rule is
                            horizontal, see SV_RunStartJitter -- and the column
                            is written anyway so a reader never has to know it.

                            THREE STATES AND THEY ARE ALL DIFFERENT.  The key
                            ABSENT means the rule was off or the file predates
                            build 83.  `startjit <u> 0 0 0` means the rule ran
                            and every candidate was blocked -- embedded in
                            geometry, or back inside the start box -- so nothing
                            moved.  Anything else is a displacement that
                            happened.  Collapsing the middle case into absence
                            would be two zeroes agreeing, which is the failure
                            sv_mapcheck shipped for a decade.

                            THE RULE IS BESIDE THE OUTCOME on the `zonerule`
                            precedent: a verifier handed only an offset cannot
                            tell a run that rolled a small number from one played
                            under a smaller rule, and those are different runs.

                            IT IS RECORDED BECAUSE IT CANNOT BE RE-DERIVED.
                            Patch 419 draws it from the OS (Sys_RandomBytes), so
                            the number exists once, on one machine, at one
                            instant -- and on an engine older than 419 it comes
                            from an unseeded random(), which is the same
                            conclusion for a weaker reason.
                            This is the same sentence `warp` is about, one step
                            earlier in the run.
    flags <n>               TF_* as they stood AT THE FINISH -- see below
    pmpin <name=value ...>  v9, build 87, AFTER `flags` (the scoreboard reads 24
                            header lines).  THE PHYSICS PIN: the 70 values the
                            mover was handed on the start packet's last move --
                            movevars, pm_type, gamespeed, hull x/y, capsule, the
                            raw sv_maxvelocity of the pre-move clamp, the trace
                            cvars and pmsrcver -- as engine Patch 346 snapshot
                            them just before PM_PlayerMove, %.9g, matched BY NAME.
                            Never cvar(): five movevars are spawn-latched and
                            maxspeed/entgravity lag a send frame.  Absent when the
                            engine does not publish: the physics are then UNKNOWN.
                            Readers still take keys in any order; `after flags`
                            is where the writer puts it, not a rule to check.
    begin                   header ends here; everything after is a record

  THE THREE ZONE KEYS ARE ADDITIVE AND ARE ABSENT ON A MAP WITH NO ZONES, which
  is most of the library.  They are here because mapcrc's own argument -- a map
  name is not a map -- stops one level short: on this game the map does not
  contain the boxes that start and stop the clock.  All three are written by
  SV_RecOpen and by SV_StageWrite and DELIBERATELY NOT by cl_lobbytime.qc, whose
  header describes a run that happened on somebody else's machine; the note
  there explains why writing the client's answer would be worse than silence.

  WHY VERSION 5 EXISTS, because it is the only bump in this format's history that
  a reader cannot shrug off.  Every key added since v4 -- leg, mapcrc,
  movetickrate -- went in additively: an old reader skips what it does not know
  and simply sees less.  v5 changes what the NUMBERS MEAN.  Build 76 moved the
  run clock off sv.time and onto the mover's own tick counter, so `ticks` in the
  trailer and `t` on every sample below are COUNTED rather than SAMPLED.  A v4
  reader handed a v5 file parses every field correctly and is wrong about all of
  them by 0-2 ticks, always in the same direction, with nothing to notice.  That
  is what a version number is for and it is why `clock` is beside it rather than
  instead of it: the two are not the same fact, and a build-76 server on a
  pre-325 engine writes `FTESURF-REC 5` with `clock sampled`.

  WHY VERSION 6 EXISTS, AND WHY IT IS THE CHEAP KIND OF BUMP RATHER THAN v5'S.
  Build 82 adds the INPUT TRACE: one `in` record per simulated move, carrying
  what the mover was handed rather than where it ended up.  By the rules this
  format has kept since v3 that needs no bump at all -- one new record type,
  which an older reader skips like any other unknown, and one new header key,
  and header keys were already order-free.  Nothing existing changed meaning,
  which is exactly what v5 could not say.

  It is bumped anyway, for one reason: `end` grew a fifth field.  A reader that
  splits that line and takes four is still correct, and reccheck.py accepted
  exactly four until this build -- so the bump is what lets a checker tell "this
  file predates the trace" from "this file lost it", which are the same bytes
  otherwise.  That distinction is the whole of what a version number buys here
  and it is worth one integer.

  A v6 FILE MAY LEGITIMATELY CARRY NO `in` RECORDS: a run whose recording opened
  with no mover counter -- an engine older than Patch 325 -- has no mover tick to
  stamp, so SV_RecOpen writes neither the key nor the rows.  `instart` is what
  says which case a file is in, and a reader must key off the KEY and never off
  the version.

  WHY VERSION 7 EXISTS, AND IT IS v6'S ARGUMENT AGAIN RATHER THAN A NEW ONE.
  Build 83 adds one header key (`startjit`) and one record type (`warp`), and by
  the rules above neither needs a bump: keys are order-free and an unknown record
  is skipped.  What forces it is the same thing that forced v6 -- `end` grew a
  field, the sixth, counting the `warp` records in the body.

  But the reason to WANT the bump is sharper this time, and it is worth stating
  because it is the whole of what a version number buys a verifier.  A v6 file
  and a v7 file with no `warp` records are the same bytes and mean opposite
  things.  In v6 a run across a stage teleport carries no record of it BECAUSE
  THE WRITER DID NOT EXIST; in v7 the same silence means NOTHING TELEPORTED THE
  PLAYER.  Re-simulation has to trust the second and must refuse to trust the
  first, and without the marker it cannot tell which file it is holding.

  Note what this does NOT claim.  Nothing existing changed meaning -- a v6 reader
  handed a v7 file reads every field it knows correctly, exactly as v4 readers do
  with v5's extra keys.  This is the cheap kind of bump, like v6 and unlike v5.

  WHY VERSION 8 EXISTS, AND IT IS THE FIRST BUMP THAT WITHDRAWS A CLAIM.

  Mechanically it is v6 again: two new records (`ride`, `inend`) and a seventh
  `end` field, all additive.  What forces the bump is that V7'S HEADLINE CLAIM
  ABOVE -- no `warp` records means nothing imposed state -- IS FALSE.  E5
  measured surf_trance: zero warps, TEN boosters.  Wrong on 181 of the 536 zoned
  maps, and a verifier that trusted it would accept a run whose physics it cannot
  reproduce.

  So: for v7 and below the true sentence is "nothing THIS FORMAT CAN EXPRESS
  imposed state"; only from v8 is silence a statement about the run.  The engine's
  pm_recsim printed the strong form until engine Patch 344 narrowed it.

  WHY VERSION 9 EXISTS: EXACT STATE.  Same-binary replay of the mover is
  bit-exact (client prediction depends on it), so a re-simulation that drifts
  means the FILE is short of state.  An audit of every input to one SV_RunCmd
  found the drift sources E3 and b83 blamed on chaos: the seed and every
  warp/ride vector at %.2f, pm_source's carried state zero-seeded, `in` angles
  that were .v_angle (stale under fixangle) while the mover reads the usercmd,
  and the physics unpinned.  v9 closes each: `pmpin`, `seed`, `pm`, %.9g on every
  imposed vector, input_angles and an <fl> column on `in`, <row> and <fl> on
  `warp`, and two records that are CHECKED rather than applied (`pe`, `portal`).
  `in` and `warp` change shape and `end` grows three fields, hence the bump.
  A v8 reader skips the new records and misreads nothing it already knew except
  the widths it checks.  Readers key off `pmpin`/`seed`, never the version: an
  engine older than Patch 346 still writes a v9 file, without them.

  AND SV_StageWrite STILL WRITES `FTESURF-REC 5` AFTER THIS BUILD, which is not
  an oversight and is the clearest statement this format has of what its version
  marker means.  A lifted stage drops every `in` row (see SV_StageLine) and its
  trailer has four fields, so the file it produces is a version-5 file in every
  respect -- grammar, body and trailer.  THE MARKER DESCRIBES THE FILE, NOT THE
  BUILD THAT WROTE IT.  Stamping 6 on it would either claim a fifth trailer field
  that is not there, or require inventing one for a body that structurally cannot
  have rows to count.  Both are worse than a writer that emits an older version
  it genuinely conforms to.

  Then, in the order they happened, one per line:

    <t> <ox oy oz> <vx vy vz> <pit> <yaw> <fl> <keys> <fwd side up> <nx ny nz>
                            a sample.  t is seconds from the run start and is
                            NEGATIVE for the pre-start padding, which is how a
                            reader finds t=0.

                            v5: SIMULATED seconds -- the cumulative cmd.msec the
                            mover consumed -- not wall seconds.  Still monotone,
                            still interpolatable, still the same column; what
                            changed is that it is now a function of the usercmd
                            stream, so two re-simulations of one run agree on it.

                            ONE PER PACKET, not one per tick, and a reader must
                            not assume otherwise.  This is sampled from
                            PlayerPostThink, which the engine calls once per
                            received move packet -- but a packet can carry up to
                            four usercmds after loss, and SV_RunCmd splits any
                            command over 50 ms into two simulated halves.  So a
                            sample can stand for several ticks, and measured
                            rates in real files are 65/s, 64.6/s and 43.5/s
                            rather than the nominal 66.67.  Interpolate using
                            each sample's own t; never by index.

    in <pk> <mt> <carry> <fwd side up> <pit> <yaw> <roll> <bt>
    in <pk> <mt> <carry> <fwd side up> <pit> <yaw> <roll> <bt> <fl>   (v9)
                            v9: <carry> %.9g; <fwd side up> integers; the angles
                            are input_angles, the usercmd the mover reads
                            (pmove.c:1457), where v6-v8 wrote .v_angle, which
                            SV_RunCmd leaves stale while fixangle is set; and
                            <fl> is the state the engine reads next: 1
                            FL_ONGROUND, 2 teleport_time set, 4 movetype not
                            WALK (2 and 4 never occur on a clean run).  Rows are
                            numbered by position from 0: <row> in the records
                            below is that index.
                            v6, build 82.  ONE SIMULATED MOVE -- what the mover
                            was HANDED, where the sample above is where it ended
                            up.  These two record types are the whole body of a
                            v6 file and they interleave: the `in` rows of one
                            packet, then that packet's sample.

                            IT IS PER SIMULATED MOVE AND NOT PER USERCMD, and
                            the difference is not pedantry.  SV_RunCmd drops a
                            command that is over its msec budget entirely,
                            TRUNCATES one that is partly over (it writes through
                            the caller's pointer, so the wire msec is not what
                            ran), and splits anything over 50 ms into two halves
                            that are each simulated separately.  So one received
                            usercmd produces 0, 1, 2, 4 or 8 of these rows.  A
                            row is what the mover actually consumed, which is
                            the only thing a re-simulation can be checked
                            against.

                            <pk> is the packet this move belonged to -- see
                            rec_rec_pk for why the grouping has to be in the
                            file at all.  Rows sharing a value are one packet;
                            the value itself means nothing.

                            <mt> is cumulative run_movetick BEFORE this move and
                            <carry> is run_movecarry before it, in seconds.
                            Between them they are the authoritative timing
                            column: the ticks this move ran are the NEXT row's
                            <mt> minus this one's, and the frametime it was given
                            is that difference times movetickrate plus the change
                            in <carry>.  Both are therefore DERIVED rather than
                            stored -- a column that must agree with two others is
                            a second answer to a question that has one, which is
                            the sv_mapcheck shape, so msec is deliberately not
                            here.  The last row's span comes from the trailer.

                            <bt> IS NOT input_buttons AND MUST NOT BE READ AS IT.
                            1 jump, 2 duck, 4 speed -- exactly the three bits
                            pm_source.c reads (BUTTON_JUMP 2, BUTTON_DUCK 8,
                            BUTTON_SPEED 128) and nothing else, taken from
                            .button2/.button4/.button8, which SV_SetEntityButtons
                            writes by integer shift (pr_cmds.c:10482-10492).

                            THE GLOBAL CANNOT CARRY THEM SAFELY.  input_buttons is
                            registered `globalfloat` (pr_cmds.c:978 -- contrast
                            `globaluint64` for input_weapon three lines down) and
                            assigned from a quint64_t at :10523.  That is a float32
                            VALUE CONVERSION, which ROUNDS THE WHOLE NUMBER; it
                            does not truncate the high half and leave the low bits
                            alone.  Measured, not reasoned about:

                              (1<<25)|BUTTON_JUMP = 33554434 -> 33554432, & 2 == 0
                              (1<<26)|BUTTON_JUMP = 67108866 -> 67108864, & 2 == 0
                              (1<<25)|BUTTON_DUCK = 33554440 -> exact

                            -- i.e. the jump bit is gone from 2^25 up, because the
                            float32 spacing there is 4 and the bit is worth 2, so
                            `input_buttons & 2` reads 0 WHILE THE MOVER JUMPED.
                            The mover is unaffected: it reads pmove.cmd.buttons,
                            the raw 64-bit word (sv_user.c:7735 `pmove.cmd =
                            *ucmd`, unmasked).

                            AND THE SHIPPING CLIENT CANNOT REACH THAT, WHICH IS
                            THE POINT RATHER THAN A REASSURANCE.  cl_input.c's
                            GATHERBIT table tops out at bit 18 (+button16), and
                            every value it can send is exact in float32.  The
                            SERVER's parse has no such ceiling -- common.c:1912 is
                            a bare MSG_ReadUInt64 and nothing clamps it -- so the
                            bit that defeats the read is reachable by a client
                            that chooses to and by no other.  A trace whose
                            faithfulness depends on the client not lying is not
                            evidence, and that is the whole argument for the
                            per-bit fields: each is one bit shifted into a float
                            that holds 0 or 1, at any button word whatsoever.

                            <pit> <yaw> <roll> are .v_angle, i.e.
                            SHORT2ANGLE(ucmd->angles[]), at four decimals -- more
                            than the sample's two, because the quantum is
                            360/65536 = 0.0055 degrees and four decimals recover
                            the wire short exactly -- IF THE READER ROUNDS
                            (x*65536/360, nearest).  Truncating returns 30134 of
                            the 65536 shorts one step low (engine Patch 345).
                            <fwd side up> is .movement,
                            the raw usercmd triple, the same one the sample
                            carries.

                            THE IMPULSE IS NOT RECORDED, and that is a decision
                            rather than an omission: pm_source.c reads three
                            button bits and no impulse, and this mod has no
                            ImpulseCommands and no reader of .impulse anywhere.
                            An input that can reach neither the mover nor the
                            gamecode cannot change a run, and recording it would
                            be 100 bytes a second asserting that it might.
    warp <pk> <mt> <kind> <ox oy oz> <vx vy vz>
    warp <pk> <mt> <row> <kind> <ox oy oz> <vx vy vz> <fl>             (v9)
                            v9: <row> is the `in` row whose move this followed,
                            and it is the binding -- <mt> repeats across a
                            zero-tick move.  -1 = before the first row (a `!r`
                            or retouch between open and the first command):
                            imposed on the seed.  Vectors %.9g; <fl> 1 = FL_ONGROUND
                            after the imposition.  Two new kinds:
                              lift     trigger_push's +1 u origin lift (grounded,
                                       upward push) -- an origin write outside the
                                       mover that v8 did not record
                              zone     SV_ZoneMove: `!r` restarting the stage a
                                       live run is on, which v8 did not record
                            tele, telerel, bhop and zone reset the zone sweep
                            origin iff run_teleport_warp; push, speed and lift
                            never do.
                            v7, build 83.  STATE IMPOSED ON THE PLAYER FROM
                            OUTSIDE THE MOVER, written by the thing that imposed
                            it, carrying the state as it stood AFTERWARDS.

                            THIS RECORD EXISTS BECAUSE ITS ABSENCE WAS MEASURED.
                            Experiment E3 (engine Patch 327, `pm_recsim`) replayed
                            a real recording's input trace back through the mover
                            that wrote it and reproduced 1307 of 1324 packets to
                            this file's own printing floor.  Ten of the fifteen
                            that failed were trigger_teleport: ~250 u of position
                            with velocity preserved EXACTLY, landing on the run's
                            own start coordinates.  The file recorded the
                            CONSEQUENCE and never the EVENT -- so an open-loop
                            re-simulation died at the first one, and a verifier
                            could not tell a legitimate stage teleport from a
                            cheat that moved the player, because those are the
                            same bytes.

                            <kind> IS WHAT MAKES IT EVIDENCE rather than a second
                            copy of the sample stream.  A record synthesised by
                            watching for a discontinuity would see the jump and
                            still not know what caused it, which is the entire
                            question.  Every writer is inside the handler that
                            performed the imposition and names itself:

                              tele     trigger_teleport
                              telerel  trigger_teleport_relative
                              bhop     func_bhop's teleport
                              speed    trigger_setspeed
                              push     trigger_push, the SF_PUSH_ONCE arm

                            A reader must treat an unknown <kind> as a warp it
                            cannot attribute -- NOT as a parse error.  The list
                            above is expected to grow.

                            <mt> AND NOT A TIME.  Touches run per USERCMD, inside
                            SV_RunCmd after the move; samples and <pk> are per
                            PACKET, because PlayerPostThink is called outside the
                            usercmd loop.  So three teleports in one packet share
                            one <pk> and one sample and only the mover's counter
                            separates them.  <pk> is written beside it anyway so a
                            reader can tie the event to the sample that follows.
                            NOTE the `in` row for the same usercmd carries the
                            PRE-move counter, so a warp sits one tick above its
                            own input row BY CONSTRUCTION.

                            WHAT IT COVERS is a boundary and not a list: every
                            DIRECT WRITE of a player's origin or velocity, outside
                            the mover, by a map entity.

                            WHAT IT DOES NOT COVER, named because a gap that is
                            not written down gets rediscovered as a bug:
                            trigger_push's CONTINUOUS arm -- 4,940 instances
                            across 46.9% of the library -- writes no velocity at
                            all.  It writes .run_basevel, a carrier the engine
                            folds into pmove.basevelocity, and the cash-out
                            happens a whole command later in SV_BaseVelocityFrame.
                            So "velocity was written" catches the once-pad and
                            misses the common case entirely.  That family wants
                            its own measurement, the way this one got E3's.

                            BUILD 85: E5 MEASURED IT; the answer is the `ride`
                            record below.  The boundary above still holds -- a
                            carrier is not a direct write -- so it is a second
                            record, not a mode flag on this one.

                            AND `push` ABOVE IS A NULL SET.  E5's census found
                            exactly ONE SF_PUSH_ONCE trigger_push in 1310 maps
                            (mg_dreamscraper, unzoned).  The writer stays; its
                            absence says nothing.

                            AND THE FIRST WARP OF A RUN MAY LEGITIMATELY BE
                            MISSING.  SV_RecOpen is called from SV_TimerStart, so
                            a trigger in or beside the start box fires before the
                            recorder exists and SV_RecPut discards it in silence.
                            A reader must not read that as tampering; the trailer
                            count is the handle it has instead.

                            VELOCITY PRESERVED EXACTLY IS THE SIGNATURE OF THE
                            LEGITIMATE CASE, not the suspicious one.  A landmark
                            teleport -- 1,189 of them in this library -- returns
                            before VelocityMode is ever read, which is what makes
                            a stage-to-stage teleport preserve a run.  A check
                            that flags exact preservation flags every stage
                            transition there is.
    ride <pk> <mt> <what> <bx by bz>      (v9: <bx by bz> at %.9g)
                            v8, build 85.  THE VELOCITY CARRIER -- basevelocity,
                            which moves the player every command without ever
                            being written to .velocity, so neither `warp` nor the
                            sample stream can see it.

                              arm  the mover is handed this from this command on.
                                   PERSISTS UNTIL THE NEXT RECORD -- a state
                              pay  cashed out into real velocity in PreThink:
                                   velocity += (1 + tick*0.5) * <bx by bz>

                            A SPAN, NOT AN EVENT, because E5 measured that an
                            event record is necessary and not sufficient.  On
                            surf_trance (167 s, zero teleports): 1,683.8 u of
                            displacement the recorded velocity cannot explain, in
                            7 spans, longest 62 ticks = 0.915 s, and ZERO position
                            discontinuities.  A record at the cash-out alone would
                            fix the endpoint and leave the interior wrong, and a
                            zone test inside that window is taken at the wrong
                            place -- a rank.

                            WRITTEN AT THE HAND-OVER (SV_BaseVelocityFrame's
                            .run_basevelocity assignment), not at the touch.  A
                            touch states an INTENTION the mover may never see;
                            that line is the mover seeing it.  One record per
                            CHANGE, so a ride costs 2 lines, not 62.

                            SHAPES A READER MUST ACCEPT:
                              arm v ... pay v   a ride: carried, then collected
                              pay v (bare)      AddOutput basevelocity (789
                                                outputs / 139 zoned maps): never
                                                armed, so never handed over --
                                                no span to open
                              arm v ... arm 0   Z is spent inside the mover, so a
                                                vertical carrier ends with no pay
                            `arm 0 0 0` follows a `pay` exactly when the last
                            `arm` written was non-zero or none has been written
                            since open (the sentinel) -- so a bare AddOutput `pay`
                            mid-run has none after it (corrected build 87).  Written,
                            not derived: a derivation rule is an exception a
                            future writer can falsify silently.

                            THE FIRST `ride` OF A RUN STATES THE CARRIER IT
                            INHERITED -- `arm` if still riding, `pay` if the ride
                            ended on that command (measured: build 85's capture
                            arm opens `pay -1700` then `arm 0`).  Do NOT assume
                            zero at `begin`: surf_hourglass's only trigger_push is
                            inside the start box, so a run there begins mid-ride.

                            <mt> IS PRE-MOVE AND MATCHES THE `in` ROW BELOW IT.
                            Both come from PlayerPreThink.  A `warp`, written from
                            a touch after the move, sits one tick ABOVE its own
                            row instead -- the two conventions differ.

                            The cash-out constant is TICK_INTERVAL, a movevar this
                            format does not yet pin; `pay` states the carrier, not
                            the product, so a reader can see which half it assumed.
    seed <ox oy oz> <vx vy vz> <fl> <name=value ...>
                            v9, build 87, once, right after `begin`, only with
                            `pmpin`.  THE EXACT STATE the first `in` row's move
                            starts from: origin and velocity %.9g, <fl> 1 =
                            FL_ONGROUND, then pm_source's carried state (duck,
                            ducktime, carry, oldbuttons, stamina, ladder ...) as
                            the engine saved it after the start packet's last
                            move.  A replay seeds from this, not from the %.2f
                            sample.  The start LATCH is still taken on trust.
    zseed <name=value ...>  v9, build 88, additive (no bump): once, before the
                            first `in` row -- the timer latches the START packet
                            left: evzone azone cpzone track startseg stagerun, and
                            twarp (run_teleport_warp, which decides whether tele/
                            telerel/bhop move the zone sweep's origin).  Written at
                            the END of that packet's SV_TimerFrame, because
                            SV_RecOpen runs before steps 2-3 update the latches.
                            engine pm_verify seeds SV_VerifyBegin from it.
    pm <pk> <row> <name=value ...>
                            v9.  The pin changed: the full text, as `pmpin`, now
                            in force FROM row <row>'s move on.  Written after that
                            move (the engine publishes after it), so it can
                            follow its row.  entgravity and maxspeed change
                            mid-run legitimately (AddOutput gravity, speedmod).
    pe <pk> <row> <crc>     v9.  The physent list the server built for row <row>'s
                            move (world excluded; entity, solidity, portal flag,
                            bounds, model) hashed to 24 bits, written on change.
                            CHECKED, NOT APPLIED: a replay builds its own list
                            and compares -- entity I/O can toggle a brush's
                            solidity and nothing records why.
    portal <pk> <row> <n> <ox oy oz> <vx vy vz>
                            v9.  Row <row>'s move crossed <n> linked_portal_door
                            pair(s) inside the mover (PM_PlayerTracePortals), and
                            this is its post-move state.  CHECKED, NOT APPLIED: a
                            replay with the server's physents crosses it itself.
                            Not a `warp` -- nothing outside the mover wrote it.
    restart <seg> <ticks>   a stage was restarted mid-run.  The run clock is
                            untouched; the zone latches reset (SV_TimerRestartSeg).
                            engine pm_verify applies it (Patch 369).  Like a
                            `warp`, it belongs to the last `in` row before it --
                            and a `warp` or `restart` written AFTER that row's
                            packet sample came between packets (`!r`, whose zone
                            warp follows its restart): it acts after that
                            packet's zone scan, not inside its move
    cp <n> <ticks>          a checkpoint was crossed.  <n> IS THE ORDINAL, not a
                            segment: this block said <seg> until build 81 and the
                            writer has written the ordinal since build 19, whose
                            own comment at the call site explains why (zone_seg
                            is 0 for every checkpoint on a linear map, so every
                            record read `cp 0 <ticks>` and no reader could tell
                            them apart).  Three years of a checker written FROM
                            THIS BLOCK inherited the wrong name
    stagestart <seg> <ticks>  a stage run was started.  Added build 81 -- the
                            writer has existed since the stage runs did, and this
                            block never listed it
    stagepost <seg> <dur> <launch>
                            Patch 360, additive: stage <seg> of a MAIN run was
                            posted to its online stage board.  <dur> is the
                            stage's own duration (NOT the run clock): the next
                            `stage`/finish tick minus its `stagestart` (0 for the
                            run's first stage).  <launch> u/s at its primed start.
                            Written just before that boundary's `stage` (or the
                            trailer); never in a stage run (leg > 0).
    abandon <ticks>         Patch 360, additive: the run was abandoned at <ticks>
                            and KEPT because it had posted stages; the normal
                            inend/end trailer follows.  data/evidence/, not runs/.
                            (A run with posts that FINISHES under an unarchived
                            tag -- last/cheat -- lands there too, with no
                            `abandon`: the file name is its runid.)
    pause <mt> <carry> <ticks> <why>
                            v10, Patch 364.  The trace is parked at run clock
                            <ticks>.  <why> decides what <mt> <carry> are:
                              retry | load  a cold rewind (sv_saveloc.qc): the
                                       last `in` row's, as written (no row yet:
                                       `instart`'s <mt> and 0)
                              drop | rotate | server  Multi-Session (TF_MULTI-
                                       SESSION): the counter AFTER the last move,
                                       this session's closing horizon as `inend`;
                                       <ticks> is the session's clock at <mt>
                            Nothing that moves -- no `in`, no sample -- until:
    session <n> <mt> <carry> <ticks>
                            v10.  Session <n> (the first is 1, unwritten) begins
                            on the mover counter as it now stands: <mt> is its
                            horizon, and `in`/`warp`/`ride` <mt>, `board` <n> and
                            the pm/pe/portal floors restart with it.  <pk>, <row>,
                            sample <t> and the clock run on; <ticks> equals the
                            pause's.  A `seed` follows when the header has `pmpin`.
                            A file is v10 exactly when it holds a `pause`.
                            THE FLOOR: `pm` `pe` `portal` `warp` written between a
                            `pause` and the next `in` row are the new session's --
                            in force from its first row (a warp is imposed on the
                            seed) -- though their <row> names the row before it.
                            engine pm_verify replays Multi-Session pauses (Patch
                            367) and refuses retry | load.
    nonce <mt> <hex32>      Patch 416, additive (no bump).  A SECOND client was
                            handed this run: a Multi-Session resume, which can be
                            another machine days later and never saw the header's
                            nonce.  The last one written is the one in force, and
                            TF_NONCE in `flags` answers only the last.  Nothing
                            counts these: `end` does not grow a field, so a v9 or
                            v10 reader that skips the record loses nothing but
                            this.

                            <mt> IS THE NEW SESSION'S EPOCH, not the pause's.
                            run_movetick is cumulative per MAP and the engine
                            resets it in SV_SpawnServer, so this record -- the
                            only one that can sit between a `pause` and the
                            `session` that re-establishes the epoch -- carries a
                            number BELOW the pause above it and equal to the
                            session below it.  Measured, `p416/ms.rec` 766-768:
                            pause 826, nonce 466, session 2 466.  A reader that
                            assumes the body's <mt> column is monotone reads it
                            wrong.

                            A RETRY OR A SAVE-LOAD WRITES NONE, and does not mean
                            nothing happened: the recorder re-publishes the nonce
                            already in force (SV_RecNoncePublish) so the client
                            can answer again, because a retry destroys the CSQC VM
                            and takes the client's copy with it.  A COLD load is
                            the exception worth knowing -- it rebuilds the file
                            from a save slot, so the header, nonce included, is
                            the SAVED run's, and the server adopts it rather than
                            keeping a number this file does not state
    stage <seg> <ticks>     a stage boundary was crossed
    board <t> <n> <nx ny nz> <vx vy vz>
                            v4.  The engine's board counter moved to <n>: you
                            arrived on a ramp.  <nx ny nz> is the LATCHED arrival
                            plane and <vx vy vz> the PRE-CLIP velocity, which is
                            the pair Board_Compute grades and the pair the
                            segment column takes its air/ramp boundary energy
                            from.  Neither is derivable from the sample stream --
                            the sample carries the post-clip velocity, which is
                            the whole point of build 19's fix.

                            ONE RECORD CAN STAND FOR SEVERAL BOARDS.  Samples are
                            written per received PACKET and a packet can carry
                            four usercmds, so the counter may have moved by more
                            than one; <n> is written so a reader can see that it
                            did rather than assume it did not.  A run that boards
                            twice inside one packet is a run bouncing off a lip
                            at 66 Hz, and no per-packet format can separate them.
    retry <ticks>           a save-state retry, written beside `resume` by the
                            same function in sv_saveloc.qc.  Added to this block
                            in build 81; the writer long predates it.  ONE field,
                            not two -- the only record in this grammar with a
                            bare tick and no index, which is exactly the shape a
                            checker written from a stale block gets wrong
    resume <slot> <ticks>   the run was resumed from save state <slot>, and
                            everything after this line is a fresh attempt at the
                            same section.  Build 17.

                            A RECORD AND NOT A HEADER KEY, which was the first
                            design and was wrong.  A save rewinds the buffer to
                            a mark and appends from there, so anything written at
                            the resume lands in the MIDDLE of the sample stream --
                            and the header ends at `begin`, by this grammar's own
                            rule.  It is also an event with a time, which is what
                            a record is and what a header key is not.

                            A reader that does not know it skips it, exactly as
                            it would an unknown header key, so v3 stands.  The
                            sample stream did not change.

    ghost <0|1> <ticks>     the camera detached (1) or came back (0) at this
                            point in the run.  Build 30.

                            THE SAMPLES BETWEEN A 1 AND A 0 ARE A BODY NOBODY WAS
                            FLYING.  Their `keys` and movement columns are flat
                            zero and their pitch/yaw do not move, because the
                            usercmd is emptied and its angles pinned while
                            detached -- which is indistinguishable, to every
                            check that existed before this build, from a player
                            who simply let go.  reccheck.py's rule that the key
                            mask agrees with the movement columns is satisfied by
                            zeros, so nothing would have complained.

                            It is also the only thing that explains the .view.
                            The sidecar keeps recording the GHOST CAMERA's
                            angles, so across this window the two files disagree
                            about where the player was looking -- the first time
                            in this format that they legitimately can.  Both
                            files carry the markers so either can be read alone.

                            A record and not a header key, for the same two
                            reasons `resume` is: it has a time, and a save
                            rewind can land it mid-stream.  TF_GHOST in the
                            header says the run contains one at all, so a reader
                            that only wants to know "was this clean" does not
                            have to scan the samples.

                            Patch 373, THE POSITION RULE: a client command, so
                            always between packets -- after the previous
                            packet's sample, before the next `in` row.  It acts
                            after that packet: from the next packet to the `0`
                            no zone is scanned (latches kept) and the sweep
                            origin follows the body.  <ticks> is SV_TimerTicks
                            there, the counter after the last move.  Emptying is
                            the client's, one RTT late: the first rows of a
                            window may carry input, and once empty they stay
                            empty.  pm_verify replays it and HOLDs on input a
                            second into a window, or after it went empty.

    spec 1 <ticks> <mt> <carry> <ox> <oy> <oz> <vx> <vy> <vz> <fl> <wall>
    spec 0 <ticks> <mt> <carry> <ox> <oy> <oz> <vx> <vy> <vz> <fl> <wall> <why>
                            Patch 382 (additive, no bump).  The body was HELD for
                            a spectate: the engine ran ZERO mover ticks for it
                            (.run_pmhold, Patch 380) and no trigger touched it.
                            <ticks> SV_TimerTicks; <mt> <carry> run_movetick and
                            run_movecarry; <o*> origin, <v*> velocity; all %.9g.
                            <fl> 1 when FL_ONGROUND else 0.  <wall> the server's
                            `time`, %.3f: the window's length is the difference,
                            and it is NOT part of the edge identity.
                            A client command, so between packets: after the last
                            `in` row -- whose packet may lack its sample, since a
                            held packet writes none.
                            NOTHING is written between a 1 and its 0, and the two
                            edges state the same <ticks> .. <fl>.  The next
                            counter-bearing line after the 0 (`in`, a
                            drop|rotate|server `pause`) restates <mt> <carry>:
                            the trace is continuous and a replay needs nothing
                            from this record.
                            <why>: leave drop rotate server retry load zone setpos
                            respawn move notarget.
                            TF_SPEC in the header iff the file holds a window.
                            Only while TS_RUNNING.  Stage slices drop it; a stage
                            spanning a window never qualifies.

    mc <pk> <row> <rx> <ry> <ax> <ay> <rej>
                            Patch 376 (additive, no bump): the client's mouse
                            counts, in-band.  <rx> <ry> is what the input ring
                            delivered, <ax> <ay> what IN_MoveMouse read, both
                            summed since the client started and wrapped at 2^20;
                            <rej> the reports raw input rejected (Patch 306).
                            After the `in` row <row> of the packet that carried
                            it, when the payload changed, and first at a run's
                            first row.  A client before 376 writes none.  An
                            honest client has <rx> = <ax> and <ry> = <ay>
                            exactly; a hook that rewrites the delta between
                            ring and read (momentum.dll's shape) breaks it.
                            pm_verify HOLDs on any line where they differ.

  Then, written at close:

    inend <mt> <carry>      v8, build 85.  THE CLOSING HORIZON -- `instart`'s
                            counterpart, written at close.

                            N ROWS GIVE N-1 DURATIONS.  An `in` row states the
                            counter BEFORE its move, so a move's ticks are the
                            NEXT row's <mt> minus this one's -- leaving the last
                            row, which is the move the finish is latched on, with
                            no successor.  E3 priced it at 1-2 ticks: a rank.

                            A RECORD, NOT A HEADER KEY, because the value does not
                            exist until the run ends and the header seals at
                            `begin`.  Gated exactly as `instart` is, so a trailer
                            without one is a writer that has gone wrong.
    end <ticks> <samples> <padding> <checkpoints> <inputs> <warps> <rides>
        <pms> <pes> <portals>                                   (v9, one line)
        <sessions>                                              (v10: `session`s)
    split <seg> <ticks>     one per completed segment, ascending

  <pms> <pes> <portals> ARE v9 AND COUNTED BY LANDED LINE, like <rides>: `pm` is a
  state a reader holds, so a lost record is a wrong pin for an unbounded span.

  <rides> IS v8 AND IS COUNTED LIKE <warps>, but it answers a different question.
  A `ride` track is a STATE track -- a reader holds the last `arm` across every
  command -- so a record lost to the line cap is not one missing fact but a WRONG
  value held for an unbounded span.  The count is how a reader notices.

  <warps> IS v7 AND IT IS COUNTED THE SAME WAY <inputs> IS -- by whether a line
  landed, not by having attempted one.  It matters more than <inputs> does: a
  missing input row is one move of a thousand, but a missing `warp` is a
  250-unit discontinuity with nothing in the file to explain it, which is exactly
  the shape a verifier would have to read as tampering.  An exact count is what
  lets it say "truncated" instead of "forged".

  <inputs> IS v6 AND IT IS COUNTED, NOT ASSERTED.  It is the number of `in`
  records in the body, on exactly the argument build 24 learned the hard way
  about <padding>: a literal written there disagreed with the body in seven of
  the first twelve stage files.  A reader with an `instart` key and no count
  cannot tell a trace that stopped at the line cap from a run that was short,
  and the line cap is the failure this format is most likely to meet -- an
  input trace roughly doubles the rate at which a recording spends it.

  fl is the state mask: 1 onground, 2 PMF_DUCKED, 4 jump button, 8 attack,
  and v4 adds 16 RAMP CONTACT -- the engine's run_rampcontact, i.e. this tick's
  move actually clipped a ramp plane.  It goes in the flags word rather than in a
  column of its own because it is a state bit and because the word already had
  room; a v3 reader masks the bits it knows and never sees it.
  keys is the FSI_* input mask (shared/sh_defs.qc).  See SV_RecLine for why the
  mask and the raw movement triple are both there.

  <nx ny nz> is the plane under you: run_rampnormal while bit 16 is set, else
  run_groundnorm while bit 1 is set, else zero.  ONE vector and not two, because
  the three consumers all pick exactly one of them and they pick it with the same
  two bits -- Board_Frame's own state machine is `onground beats riding beats
  falling`, and HUD_RampNormal reads the ramp plane only when ramp contact is
  set.  Storing both would be six columns to answer a question that has one
  answer, and the flags word already says which one this is.

  WHAT CHANGED FROM v3, and the compatibility rules that made it safe:
    - three columns appended to every sample, never inserted;
    - one bit added to a mask that had room;
    - one header key added, and header keys were already order-free;
    - one new record type, which an older reader skips like any other unknown.
  So a v3 reader reads a v4 file correctly by ignoring what it does not know, and
  the v4 reader handles a v3 file by defaulting the three missing columns to zero
  and bit 16 to clear -- which reads as "no plane recorded", and cl_watch.qc
  turns exactly that into the build 23 refusal rather than into a wrong number.
  Your existing surf_aesthetic run is a v3 file and stays readable.

  THE `flags` HEADER KEY IS WRITTEN TWICE and that is the interesting part.
  SV_RecOpen reserves it as `flags 0` at a known line, because at open time the
  run cannot yet be practice; SV_RecClose rewrites that one line with bufstr_set
  before buf_writefile, because the header is still in memory and the flags are
  finally known.  So the leaderboard learns clean-vs-stitched from NINE fgets
  rather than by reading a 444 KB file to its trailer, and the file never grew a
  second pass.
===========================================================================
*/
/*
  Where a finished recording lands.  There is no .part any more -- see the
  rec_rec_buf comment above -- so this is the only path the recorder knows, and it
  is written exactly once, at the end, when the tag is finally known.

  BUILD 23: the layout, the padding rule and the reason both live in
  FS_RunPath (shared/sh_defs.qc) rather than here, because the client spells the
  same name for its .view and .hid sidecars and two spellers of one convention is
  a drift waiting to orphan both halves of a run.  This is now the ONE caller on
  the server side.

  `ticks` < 0 means "not archived" and yields the fixed `last` name.
*/
/*
  BUILD 66: WHICH PLAYER THIS RUN BELONGS TO, as a filename component.

  The format, the sanitiser and the reasons all live in FS_PlayerSeg
  (shared/sh_defs.qc), beside the parser that has to undo them.  What is decided
  HERE is the two things only the server knows: whether there is a player
  dimension at all, and what to do when the identity is missing.

  OFF A LOBBY IT IS "" AND THE NAME DOES NOT CHANGE.  One player per disk is not
  an assumption, it is the definition of a listen server: `data/runs` is that
  person's archive and always has been.  Adding their id to it would rename
  every future file for no gain and orphan the .view sidecar their own client
  writes under the old spelling (cl_replay.qc: Rec_ViewPath, which calls
  FS_RunPath and knows nothing about any of this).

  THE FALLBACK IS THE SLOT, and it is chosen for exactly the property the
  collision needs.  Reaching it means sv_guidkey is unset on a server that is
  running as a lobby -- a misconfiguration Lobby_SubmitRun already refuses to
  submit under and already tells the player about, so it is not this function's
  job to complain again.  But the recorder is still running and two people can
  still tie, and a client slot is unique among everyone CONNECTED AT THE SAME
  TIME, which is precisely the set of people who can tie on the same tick.  It
  is reused after they leave, so it identifies nobody across sessions -- which
  is honest about what an unidentified server can say.
*/
string(entity e) SV_RecWho =
{
	local string who;

	if (!Lobby_Active())
		return "";

	who = FS_PlayerSeg(e.netname, infokey(e, "guid"));
	if (who != "")
		return who;

	return sprintf("s%g", e.run_t_slot);
};

/*
  BUILD 66: `who` IS A PARAMETER rather than asked for here, on the same
  argument SV_RecClose's `flags` and SV_RecLine's timestamp are already made
  with: the call site is what knows the value, and a function that re-derives
  it is a second route to an answer that has to agree with the first.  Here it
  is also a cost -- SV_RecWho hashes a GUID -- and SV_RecClose needs the same
  string three times.
*/
string(entity e, float ticks, string who, string tag) SV_RecFinalPath =
{
	// BUILD 57: by LEG.  A stage-1 run begins at segment 0 exactly as a full run
	// does, and filing it by the segment would put it in `main`.
	// BUILD 66: and by PLAYER, which is "" everywhere except a lobby.
	return FS_RunPathWho(mapname, e.run_t_track,
	                     FS_LegOf(e.run_t_startseg, e.run_t_stagerun), ticks,
	                     who, tag, "rec");
};

/*
  RT_* to the word that goes in the filename.  One place, because the client
  spells the same name for its sidecar (Rec_ViewPath) and the two have to agree
  character for character or the pair is orphaned.
*/
// Kept as a name because this file calls it in several places; the definition
// moved to FS_TagName in shared/sh_defs.qc in build 23, beside the path it goes
// into, so the client is no longer spelling the same three words separately.
string(float tag) SV_RecTagName = { return FS_TagName(tag); };

/*
  One line into the recording.

  NO TRAILING NEWLINE.  buf_writefile writes one itself after every string
  (pr_bgcmd.c PF_buf_writefile: fwrite of the string, then fwrite of "\n"), so a
  line that carries its own comes out double-spaced.

  Nothing here is allowed to leave a hole in the buffer either: buf_writefile
  SKIPS a null entry entirely rather than writing a blank line, so a gap would
  silently shorten the file rather than show up in it.  rec_rec_lines is the next
  index and increments on every write, which keeps the buffer dense by
  construction.

  `< 1` rather than `< 0` throughout, and that is not a typo.  buf_create returns
  i + BUFSTRBASE and BUFSTRBASE is 1 (pr_bgcmd.c:5157) precisely so that a zero
  cannot be mistaken for a buffer -- so 0 means "never had one" just as surely as
  the -1 we write ourselves, and testing for both costs nothing.
*/
void(entity e, string s) SV_RecPut =
{
	local float cap;

	if (!SV_RecLive(e))
		return;

	/*
	  THE CAP IS A PROPERTY OF THE PATH, not of the recorder -- see the two
	  constants.  Read here rather than latched at open, because rec_rec_stream
	  can be cleared MID-OPEN: SV_RecOpen falls back to the buffer when the part
	  file will not open, and a run that fell back has to take the buffer's real
	  limit rather than the one it was promised on the way in.  Latching would
	  have handed such a run an 8.6M cap over a structure that refuses at 1.05M,
	  which is the silent truncation this constant exists to prevent, arrived at
	  by a different road.

	  %d AND NOT %g ON THE MESSAGE TOO.  `%g` is six significant digits, so the
	  streamed cap would announce itself as `8.64e+06` -- a number in the one
	  line whose whole job is to tell a human why their recording stopped.
	*/
	cap = e.rec_rec_stream ? FS_RECMAX_STREAM : FS_RECMAX_BUF;

	if (e.rec_rec_lines >= cap)
	{
		if (!e.rec_rec_full)
		{
			e.rec_rec_full = TRUE;
			dprint(sprintf("timer: recording hit the %d-line cap; "
			               "the rest of this run is not being kept\n", cap));
		}
		return;
	}

	/*
	  THE NEWLINE IS OURS ON THIS PATH AND NOT ON THE OTHER, which is the one
	  place the two recorders genuinely differ rather than merely branch.
	  buf_writefile appends a newline after every string it writes
	  (PF_buf_writefile: the string, then "\n"), so the buffered path must NOT
	  carry one -- the essay above this function is about exactly that.  fputs
	  writes what it is given and nothing else, so here it must.

	  Keeping the line count in step across both is what lets the line cap,
	  the save-state mark and `timer`'s report go on meaning one thing.  It is no
	  longer a buf_writefile index on this path -- nothing indexes a stream -- but
	  it is still the number of lines in the file, which is what every reader of
	  it actually wanted.
	*/
	if (e.rec_rec_stream)
	{
		fputs(e.rec_rec_fh, s);
		fputs(e.rec_rec_fh, "\n");
		e.rec_rec_lines = e.rec_rec_lines + 1;
		return;
	}

	bufstr_set(e.rec_rec_buf, e.rec_rec_lines, s);
	e.rec_rec_lines = e.rec_rec_lines + 1;
};

/*
  One sample.  Called from the recorder AND from the padding flush, so the
  timestamp is a parameter rather than read from the entity: the ring's
  samples are older than `time` and must keep their own.

  v3 adds four columns and adds them all on the END, so that a v2 reader -- which
  splits on whitespace and takes ten fields -- reads a v3 sample correctly and
  simply does not see the rest.  That is the whole compatibility story for the
  sample stream, and it is why the new fields are not spliced in beside the flags
  column they are related to.

      ... fl  keys  fwd side up

  `keys` and the movement triple overlap on purpose.  keys is the FSI_* mask,
  which is the form every consumer wants -- it is directly comparable to the
  client's own mask from the sidecar, and that comparison is what distinguishes a
  key you held from one the game sent for you.  The triple is the raw usercmd
  (sv_user.c:7693), which the mask cannot reproduce: it loses magnitude, and it
  loses upmove entirely.  Deriving the mask is easy and undoing it is impossible,
  so the raw values are the ones that had to be stored, and the mask is stored
  as well because computing it in five different readers would be worse.

  They cannot disagree: both come from the same .movement in the same call.
*/
void(entity e, float t, vector org, vector vel, vector mv,
     float pit, float yaw, float fl, float keys, vector n) SV_RecLine =
{
	// FOUR sprintfs on purpose: fteqcc caps varargs at 8 and SILENTLY drops
	// the rest, so a single seventeen-value format would write zeroes for the
	// tail rather than fail to compile.
	SV_RecPut(e, strcat(sprintf("%.4f %.2f %.2f %.2f ", t, org_x, org_y, org_z),
	                    sprintf("%.2f %.2f %.2f %.1f %.1f ",
	                            vel_x, vel_y, vel_z, pit, yaw),
	                    sprintf("%g %g %g %g %g ", fl, keys, mv_x, mv_y, mv_z),
	                    sprintf("%.4f %.4f %.4f", n_x, n_y, n_z)));
	e.rec_rec_n = e.rec_rec_n + 1;
};

/*
  FOUR DECIMALS ON THE NORMAL, which is more than any other column gets.

  It is a UNIT vector fed straight into dot products and into an acos: at two
  decimals the worst-case angular error is about 0.8 degrees, and the board
  grade's whole scale is `degrees off the normal`, where a degree is a visible
  grade step.  Positions get two decimals because a hundredth of a world unit is
  below anything that can be seen; a hundredth of a normal is not the same size
  of thing at all.  Costs ~8 bytes a sample.
*/
float(entity e) SV_RecFlags =
{
	local float fl;
	fl = 0;
	if (e.flags & FL_ONGROUND)                fl = fl + 1;
	if (e.pmove_flags & PMF_DUCKED)           fl = fl + 2;
	if (e.button2)                            fl = fl + 4;
	if (e.button0)                            fl = fl + 8;
	if (e.run_rampcontact)                     fl = fl + 16;   // v4
	return fl;
};

/*
  The plane that goes in the sample -- see the format block for why there is
  exactly one of them.

  Zero when you are neither riding nor grounded, which is most of a surf run and
  is the truthful answer: in free air there is no plane, and a reader must not be
  handed a stale one it would then draw a strafe target against.

  AND ZERO SOMETIMES WHILE GROUNDED, WHICH IS ALSO CORRECT.  run_groundnorm is not
  "the floor under your feet" -- SV_PlayerPostThink builds it by sweeping the hull
  one tick FORWARD along your own velocity and taking whatever it hits, and it
  returns '0 0 0' both when nothing is hit and when the velocity is zero.  So
  standing still records no plane at all.  That is the same quantity the live
  strafe bar is fed through STAT_FS_GROUNDNORM, which is the whole point: the
  replay hands the panel exactly what the panel gets live, including the empty
  case it has always handled.  reccheck.py reports it as a note rather than a
  fault for this reason.
*/
vector(entity e) SV_RecNormal =
{
	if (e.run_rampcontact)
		return e.run_rampnormal;
	if (e.flags & FL_ONGROUND)
		return e.run_groundnorm;
	return '0 0 0';
};

/*
  The input mask: what the usercmd for this tick actually carried.

  .movement is the raw (forwardmove, sidemove, upmove) the client sent
  (sv_user.c:7693), so its SIGN is the key and its magnitude is the speed cvar --
  which is why this reads signs and not values.  Positive sidemove is right
  (cl_input.c builds it as +moveright minus +moveleft).

  button2 is usercmd bit 1 and button4 is bit 3, which is the bit `+duck` sets
  (cl_input.c:1312 ORs in_duck into the same bit 3 that +button4 uses, so that
  pm_source.c sees Source's IN_DUCK).  Reading button4 rather than PMF_DUCKED is
  deliberate: PMF_DUCKED is the engine's carried duck STATE and stays set through
  a forced crouch you are not asking for.  The state is already in the flags
  column; this column is the request.

  +left and +right are absent and cannot be added: they have no usercmd bit at
  any sample rate.  The client's sidecar carries them.

  AND THE DIRECTIONAL BITS ARE NOT PROOF OF A KEYPRESS.  With +strafe held the
  MOUSE feeds sidemove, so LEFT/RIGHT here can be lit by a mouse the player
  strafed with rather than by a key they pressed.  The sign is still the truth
  about what the physics received, which is what this column is for -- but the
  key DISPLAY has to prefer the client's mask, which reads the keyboard itself.
*/
float(entity e) SV_RecKeys =
{
	local float m;
	m = 0;
	if (e.movement_x > 0)   m = m + FSI_FWD;
	if (e.movement_x < 0)   m = m + FSI_BACK;
	if (e.movement_y < 0)   m = m + FSI_LEFT;
	if (e.movement_y > 0)   m = m + FSI_RIGHT;
	if (e.button2)          m = m + FSI_JUMP;
	if (e.button4)          m = m + FSI_DUCK;
	if (e.button0)          m = m + FSI_ATTACK;
	return m;
};

/*
  BUILD 87 (v9): engine text copied into a recording must be what the engine
  wrote.  On an engine older than Patch 346 an unknown per-client infokey falls
  through to the CLIENT's userinfo, whose star keys can carry any bytes -- a
  newline included, i.e. a forged header line.  So the caller gates on
  run_pmepoch > 0 (an edict field no client can write) and this refuses anything
  outside the serializer's own alphabet.
*/
float(string s) SV_RecSafeText =
{
	local float i, n, c;
	n = strlen(s);
	if (n < 1 || n > 4000)
		return FALSE;
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (c >= 48 && c <= 57) continue;        // 0-9
		if (c >= 65 && c <= 90) continue;        // A-Z
		if (c >= 97 && c <= 122) continue;       // a-z
		if (c == 32 || c == 43 || c == 45 || c == 46 || c == 61 || c == 95)
			continue;                            // space + - . = _
		return FALSE;
	}
	return TRUE;
};

// `*pmpin` / `*pmstate`: the engine's name=value text, reassembled from its
// <=240-char chunks.  "" unless this engine publishes and the text is clean.
string(entity e, string key) SV_RecPinText =
{
	local float i;
	local string s, part;
	if (e.run_pmepoch <= 0)
		return "";
	s = "";
	for (i = 0; i < 16; i = i + 1)
	{
		part = infokey(e, strcat(key, ftos(i)));
		if (part == "")
			break;
		s = (i ? strcat(s, " ", part) : part);
	}
	if (!SV_RecSafeText(s))
		return "";
	return s;
};

// BUILD 87 (v9): the exact state the next `in` row's move starts from, %.9g, with
// the carried pm_source state.  Only in a file with `pmpin`.
void(entity e) SV_RecSeed =
{
	local string pst;
	pst = SV_RecPinText(e, "*pmstate");
	if (pst != "")
		SV_RecPut(e, strcat(sprintf("seed %.9v %.9v %d ", e.origin, e.velocity,
		                            (e.flags & FL_ONGROUND) ? 1 : 0), pst));
};

/*
  Patch 364: open the session a `pause` left owed (SV_RecPause), before the first
  line that stamps the mover counter.  <ticks> is read at this instant, so reccheck's
  "pause ticks == session ticks" tests that the clock stood still; while a retry's
  latch is pending (starttick -2) nothing has been counted and the clock IS the carry.
*/
void(entity e) SV_RecSession =
{
	local float was, tk;

	if (!e.rec_rec_sesspend)
		return;
	if (e.run_movetickrate <= 0)
		return;
	tk = e.run_t_tickcarry;
	if (e.run_t_starttick != -2)
		tk = SV_TimerTicks(e);
	was = e.rec_rec_lines;
	SV_RecPut(e, sprintf("session %d %d %.9g %d", e.rec_rec_sess + 2,
	                     e.run_movetick, e.run_movecarry, tk));
	if (e.rec_rec_lines == was)
		return;
	e.rec_rec_sess = e.rec_rec_sess + 1;
	if (e.rec_rec_sesspend > 1)
		SV_RecSeed(e);
	e.rec_rec_sesspend = 0;
};

/*
  PATCH 416: THE PER-RUN NONCE.  128 bits the server picks when a run opens,
  written into this file's header and stuffed to the one client that is running
  it, which answers `cmd rec_nack <hex>` and sets TF_NONCE.

  WHAT IT IS FOR, because on its own it catches nobody.  Every taint bit above
  is a statement about what a client CLAIMED -- its ruleset, its map hash, its
  input profile -- and so is worth what the client is worth.  This is the first
  thing in the chain a client cannot answer by asserting: the number did not
  exist until the run started, and it exists nowhere else.  That buys two
  things, and neither is a verdict:

    1. A CLIENT THAT ANSWERS IS A CLIENT THAT COULD HAVE.  The plan's open
       question about uploading evidence is not "did this run come with a
       journal" but "was the client ASKED and able".  A run with TF_NONCE and no
       journal is a client that would not; a run without it is a client that
       could not -- any build before this one.  Those are the same silence
       today and a demotion that cannot tell them apart would demote every
       legacy client, which is exactly the skew window sv_mapcheck shipped.
       So TF_NONCE is a MARKER, like TF_MULTISESSION and TF_SPEC: not a class,
       not in TF_UNCERT, and nothing is refused for its absence.

       AND THE ATTACKER PICKS WHICH SILENCE THEY PRESENT, which is the honest
       limit of this and was put to the patch by its own review.  Echoing the
       number is free for a patched client, and so is staying quiet and sitting
       in the legacy bucket.  So the bit does not separate honest from dishonest
       and must never be asked to: what it separates is a POPULATION.  While
       pre-416 clients exist, absence means nothing; once they do not, absence
       is a client choosing to look old, which is a different conversation and a
       later one.  Nothing here may be wired to a demotion before then.

    2. IT IS A REFERENT ANY LATER EVIDENCE CAN BE BOUND TO -- A LOWER BOUND ON
       WHEN THAT EVIDENCE WAS MADE, AND NOTHING MORE.  The client notes it into
       its own raw input journal (`in_journal_note nonce <hex>`), which stamps
       it at a position in the stream.  What that rules out is a journal written
       BEFORE the run: a library of pre-made ones cannot carry a number that did
       not exist yet.  What it does not rule out is the journal being assembled
       afterwards, at leisure, with the nonce in hand -- and `in_journal_note`
       is an ungated console command, so on a hostile client the note's position
       is chosen by the attacker too.  The note is therefore a convenience for
       honest clients and not, on its own, evidence against a dishonest one.
       Making it evidence means the ENGINE owning both ends of it, which is the
       next patch's job and not this one's.

  STRENGTH, AND THE FIRST VERSION OF THIS PARAGRAPH WAS WRONG IN THE DIRECTION
  THAT FLATTERS THE PATCH.  It said the seed was hard to predict because an
  attacker would have to know both the boot second and how many draws the server
  had made since, "which moves with every run every player takes".  THE DRAW
  COUNT IS PUBLISHED.  `startjit` two lines above writes the randomized start's
  offset at four decimals, and with run_startjitter 2 a draw's step is 4/32768 =
  0.000122 -- so each printed dx and dy names its own random() exactly, two
  draws per run, in the same header.  A player does not even need the file: the
  offset is applied to their own body.  random() is (rand()&0x7fff)/0x8000 and
  rand() is seeded once from time(0) at COM_Init (common.c:6861), so enough
  observed draws recover the stream.

  So: this WAS a nonce a determined attacker could predict.  The first version
  of this paragraph then said prediction buys them nothing, because the server
  sends them the number regardless -- and a reviewer of Patch 419 pointed out
  that this is true of the nonce's FIRST property only.  Its second is a LOWER
  BOUND ON WHEN THE EVIDENCE WAS MADE, which is what Patch 418's upload leans
  on: a client that can predict tomorrow's nonce can build the journal early
  and the bound is gone.  What the same leak also bought was `startjit` itself,
  which exists precisely so a run cannot be replayed from a known start.

  PATCH 419 CLOSES BOTH.  `SV_RandHex(16)` is 128 bits of OS entropy per nonce,
  so every other input above -- including `guid`, which is client userinfo and
  unsanitised -- is irrelevant to predicting it.  On an engine older than 419
  the fallback is the old mix, and SV_Rand01 says so at normal verbosity.
  Done this way so the whole patch ships with a progs deploy, which is routine,
  instead of an engine one, which is not.

  `run_nonce_seed` is a progs global, so it is rebuilt at every MAP LOAD and not
  once per boot.  Said plainly for the same reason as the rest of this note.

  ONE PER SESSION AND NOT ONE PER RUN, and the difference shows up in exactly
  one place: a Multi-Session resume (sv_resume.qc) can be a different machine
  days later, and that client never saw the header's nonce.  So the resume
  issues a fresh one, written into the body as `nonce <mt> <hex>` -- which is
  also the only honest thing to write, since the two sessions were answered by
  two clients and the file should say so.  A retry or a save-load keeps the one
  in force: same client, same connection, nothing to re-establish.
*/
void(entity e, float body) SV_RecNonce =
{
	local string n;
	local float was;

	/*
	  THE BIT GOES DOWN BEFORE ANYTHING ELSE HAPPENS, and it is the first thing
	  here because every other line below can fail.  TF_NONCE says "the client
	  answered THIS session's number"; a session that could not issue one must
	  not inherit an answer from the session before it -- and a resumed run's
	  flags are restored from its parked save, which carries the bit.  Reviewed
	  into existence: six paths reached a finish with a stale bit set, one of
	  them (`run_ms_norec`) a session in which no nonce was ever issued.
	*/
	e.run_t_flags = e.run_t_flags - (e.run_t_flags & TF_NONCE);

	if (!SV_RecLive(e))
		return;

	/*
	  LATCHED ON THE LENGTH AND NOT ON `!= ""`.  strzone() of the null string an
	  engine without SHA256 returns is a real, non-zero allocation whose CONTENT
	  still compares equal to "" -- so an emptiness test never latches, and this
	  would allocate one of them per run open, forever, on exactly the engine
	  the rest of this function is careful to handle.
	*/
	if (strlen(run_nonce_seed) < 32)
		run_nonce_seed = strzone(digest_hex("SHA256",
		                         sprintf("%s|%g|%s|%g|%g|%s",
		                                 strftime(TRUE, "%Y%m%d-%H%M%S"), time,
		                                 SV_RandHex(32), SV_Rand01(), SV_Rand01(),
		                                 cvar_string("sv_port"))));

	n = strtolower(digest_hex("SHA256", sprintf("%s|%s|%s|%g|%g|%s",
	                                            run_nonce_seed, e.rec_rec_rid,
	                                            infokey(e, "guid"),
	                                            e.run_movetick, time,
	                                            SV_RandHex(16))));
	/*
	  CHECKED AND NOT ASSUMED, on FS_GuidId's precedent (sh_defs.qc): an engine
	  whose digest_hex is absent or refuses "SHA256" returns "", and a run whose
	  header carried four characters of nonce would look like a run with one.
	  No nonce is a state this patch already handles everywhere; a short one is
	  not.
	*/
	if (strlen(n) < 32)
		return;
	n = substring(n, 0, 32);

	/*
	  THE LINE FIRST, THE LATCH SECOND, and the order is SV_RecWarp's argument:
	  SV_RecPut fails silently at the line cap and on a closed recorder, so a
	  latch set before the write would leave the server holding a nonce the file
	  does not name -- and the client would then ack a number no reader can find.
	  Keeping the previous one in force is the right failure: it is still a
	  number the file states.
	*/
	was = e.rec_rec_lines;
	if (body)
		SV_RecPut(e, sprintf("nonce %d %s", e.run_movetick, n));
	else
		SV_RecPut(e, sprintf("nonce %s", n));
	if (e.rec_rec_lines == was)
		return;

	if (e.rec_rec_nonce != "")
		strunzone(e.rec_rec_nonce);
	e.rec_rec_nonce = strzone(n);
	stuffcmd(e, sprintf("rec_nonce %s\n", n));
};

/*
  The client's answer.  `cmd rec_nack <hex>` -- see SV_ParseClientCommand.

  SILENT ON A MISMATCH, and deliberately.  A stale echo is ordinary: the nonce
  is re-issued on a resume and the old one can still be in flight, and a player
  who types the command in their own console is answering with nothing.  None of
  those is a fault to report, and a print here would be a print any client could
  ask for at any rate.  The bit is what the file records, and no bit is the
  answer to all three.
*/
void(entity e, string got) SV_RecNack =
{
	if (!SV_RecLive(e))
		return;
	if (e.rec_rec_nonce == "" || got != e.rec_rec_nonce)
		return;
	e.run_t_flags = e.run_t_flags | TF_NONCE;
};

/*
  A REWIND HAS TO RE-ESTABLISH BOTH HALVES, and the review found four ways it
  did not.

  WHY THE CLIENT HAS TO BE TOLD AGAIN.  A `retry` is a map_restart: it destroys
  the CSQC VM, and Rec_ViewInit clears the client's nonce with it.  Nothing
  re-issues one (a retry keeps the run and its header), so the run would finish
  with the file asserting an answer that the client running it could not have
  given -- and its journal naming no nonce at all.

  WHY A COLD LOAD ADOPTS THE FILE'S.  A cold load rebuilds the recording from a
  save slot, so the header this run now carries is the SAVED run's, nonce and
  all.  The server would otherwise keep holding the number it drew for the run
  it has just discarded, and the `SV_RecNonce` rule "the client would then ack a
  number no reader can find" would be broken by the one path that changes the
  file underneath it.  Drawing a fresh one instead would mean a body record on a
  load, which the grammar says belongs to a resumed SESSION; adopting is both
  simpler and truer -- the file states a nonce and now so do we.

  A pre-416 save has no such key, and then this run has no nonce: the string is
  emptied so nothing can be acked, which is the honest reading of a header that
  does not name one.

  THE BIT ALWAYS GOES DOWN.  Whatever the client answered belongs to the run as
  it was before the rewind; re-earning it costs one round trip.
*/
void(entity e, float cold) SV_RecNoncePublish =
{
	local float i;
	local string l;

	e.run_t_flags = e.run_t_flags - (e.run_t_flags & TF_NONCE);

	if (cold)
	{
		if (e.rec_rec_nonce != "")
			strunzone(e.rec_rec_nonce);
		e.rec_rec_nonce = "";
		/*
		  Bounded by `begin` and not by a line count, on the flags scan's rule
		  directly below in SV_RecRewind: the header's keys are order-free.

		  A STREAMED cold load has no buffer to read -- its header is on disk
		  and rec_rec_buf is -1 -- so it ends here with no nonce, which is the
		  honest outcome rather than a gap: nothing can be acked, the bit stays
		  down, and the file's own header remains the only claim about the run.
		  A load is segmented and off the ranked board in any case.
		*/
		if (e.rec_rec_buf < 1)
			return;
		for (i = 0; i < e.rec_rec_lines && i < 64; i = i + 1)
		{
			l = bufstr_get(e.rec_rec_buf, i);
			if (l == "begin")
				break;
			if (substring(l, 0, 6) == "nonce ")
			{
				e.rec_rec_nonce = strzone(substring(l, 6, 32));
				break;
			}
		}
	}

	if (e.rec_rec_nonce == "")
		return;
	stuffcmd(e, sprintf("rec_nonce %s\n", e.rec_rec_nonce));
};

/*
  PATCH 417: THE RUN RECEIPT, WRITTEN WHERE THE RECORDING CANNOT REACH.

  The client signs a short fixed statement over the nonce, the tick count it
  saw, and the SHA-256 of its own two evidence files, and sends the signature
  and its public key.  This writes that down.

  A SEPARATE FILE AND NOT A RECORD IN THE .rec, for a reason the format cannot
  argue with: the digests do not exist until the run has ENDED and the client's
  files have been written, and by then the .rec has been closed, counted and
  renamed.  A receipt is also a statement ABOUT a recording rather than part of
  one -- it is made afterwards, by the other end, and putting it inside the file
  it attests to would be the only circular line in the grammar.

  THE SERVER FILLS IN EVERY FIELD IT KNOWS AND THE CLIENT ONLY THE ONES IT
  SIGNED.  map, runid, the nonce and the server's own tick count come from here;
  pub, ticks, the two digests and the signature come from the client.  So a
  client cannot put a different run's name on its receipt, and the one field
  that appears twice -- ticks, once as the client signed it and once as this
  server counted it -- is a disagreement a reader can see rather than a
  contradiction hidden inside a signature.

  REFUSED UNLESS TF_NONCE IS ALREADY SET.  The bit says this client echoed the
  number this run was issued, so there is exactly one nonce the receipt can be
  about.  Without that the file would have to record whose nonce it thought it
  was signing, and a receipt naming its own referent is a receipt that proves
  nothing.

  ONE PER RUN, and the shapes are checked before anything is written: this is a
  client-driven file write on a public server.
*/
// A plain integer, optionally signed, short enough that nothing downstream has
// to think about it.  Used on the two receipt fields that are written verbatim.
/*
  Patch 417: ONE LINE OF A KEY/VALUE FILE, with everything that could end it
  early replaced by `?`.

  SV_RecSafeText above is a WHITELIST of six punctuation marks, which is right
  for a pin value and wrong here: a receipt carries a player's name and a server
  address, so it has to keep `^`, `:` and the rest of printable ASCII or it
  keeps nothing.  What it may not keep is anything a line-based reader treats as
  a break -- and the reader is Python, whose splitlines() ends a line on \v, \f,
  \x1c, \x1d, \x1e, U+0085, U+2028 and U+2029 as well as the two everybody
  remembers.  SV_FixupName strips none of those.  Printable ASCII contains none
  of them, so that is the line.
*/
string(string s) SV_RecCleanLine =
{
	local float i, n, c;
	local string out;

	n = strlen(s);
	if (n > 96)
		n = 96;
	out = "";
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		out = strcat(out, (c >= 32 && c < 127) ? chr2str(c) : "?");
	}
	return out;
};

float(string s, float neg) SV_RecIsInt =
{
	local float i, c, n;

	n = strlen(s);
	if (n < 1 || n > 11)
		return FALSE;
	i = 0;
	if (str2chr(s, 0) == '-')
	{
		if (!neg || n < 2)
			return FALSE;
		i = 1;
	}
	for (; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (c < '0' || c > '9')
			return FALSE;
	}
	return TRUE;
};

float(string s, float n) SV_RecIsHex =
{
	local float i, c;

	if (strlen(s) != n)
		return FALSE;
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')))
			return FALSE;
	}
	return TRUE;
};

// Patch 426: hold (or, with "", clear) the run that ended.
void(entity e, string rid, string nonce, float ticks) SV_RecEndHold =
{
	if (e.rec_end_rid != "")
		strunzone(e.rec_end_rid);
	if (e.rec_end_nonce != "")
		strunzone(e.rec_end_nonce);
	e.rec_end_rid = "";
	e.rec_end_nonce = "";
	e.rec_end_ticks = 0;
	if (rid != "" && nonce != "")
	{
		e.rec_end_rid = strzone(rid);
		e.rec_end_nonce = strzone(nonce);
		e.rec_end_ticks = ticks;
		e.rec_end_at = time;
	}
};

void(entity e, string pub, string ticks, string hid, string hidlen, string kept,
     string view, string sig, string svname) SV_RecRcpt =
{
	local float fh, svt, noup;
	local string path, who, rid, nonce;

	/*
	  EVERY REFUSAL SAYS WHY, under developer.  A receipt that silently does not
	  appear is indistinguishable from a client that never sent one, and the
	  first cut of this patch spent a harness run on exactly that question.
	  dprint rather than a print: it is client-driven, so it may not be
	  something a stranger can put on an operator's console.
	*/
	// Patch 426: the held run is the last one that ended, so it is this
	// receipt's -- if the receipt signs its tick count.  That turns a ticks
	// disagreement into a refusal (join_ticks cannot fire on a held receipt):
	// the answer when it cannot tell which run a receipt is for.  Copies,
	// because the hold is released before the open below.
	rid = strcat(e.rec_end_rid);
	nonce = strcat(e.rec_end_nonce);
	svt = e.rec_end_ticks;
	if (rid != "" && ticks != sprintf("%d", svt))
	{
		dprint(sprintf("timer: receipt refused -- it signs ticks %s and the run "
		               "held for one ended at %d\n", ticks, svt));
		return;
	}
	if (rid == "")
	{
	if (e.rec_rec_rid == "" || e.rec_rec_nonce == "")
	{
		dprint("timer: receipt refused -- no run id or no nonce\n");
		return;
	}
	if (!(e.run_t_flags & TF_NONCE))
	{
		dprint("timer: receipt refused -- the nonce was never answered\n");
		return;
	}
	/*
	  THE RUN HAS TO BE OVER, and the review found what its absence bought.
	  Every gate above is true from the moment the client acks the nonce, i.e.
	  the first second of the run -- so a client could send its receipt at tick
	  one, committing to digests of evidence that did not exist yet, record a
	  server tick count of zero, and BURN THE ONE-PER-RUN LATCH so the honest
	  receipt at the finish was refused.  The whole claim this patch makes about
	  the commitment is that it is made at the finish; this is the line that
	  makes that true.
	*/
	if (e.run_t_flags & TF_RECORDING)
	{
		dprint("timer: receipt refused -- the run is still recording\n");
		return;
	}
	if (e.rec_rec_rcpt)                 // one per run
	{
		dprint("timer: receipt refused -- this run already has one\n");
		return;
	}
	rid = e.rec_rec_rid;
	nonce = e.rec_rec_nonce;
	svt = e.rec_rec_ticks;
	}
	// Named one by one rather than as one test: "malformed field" cost a harness
	// run on the question of WHICH, and a refusal a reader cannot act on is a
	// refusal that has to be debugged twice.
	if (!SV_RecIsHex(pub, 64))
	{
		dprint(sprintf("timer: receipt refused -- pub %s\n", pub));
		return;
	}
	if (!SV_RecIsHex(sig, 128))
	{
		dprint(sprintf("timer: receipt refused -- sig %s\n", sig));
		return;
	}
	if (hid != "-" && !SV_RecIsHex(hid, 64))
	{
		dprint(sprintf("timer: receipt refused -- hid %s\n", hid));
		return;
	}
	if (view != "-" && !SV_RecIsHex(view, 64))
	{
		dprint(sprintf("timer: receipt refused -- view %s\n", view));
		return;
	}
	/*
	  -1 IS A LEGAL TICK COUNT HERE and refusing it was this patch's third
	  harness failure.  STAT_FS_RUNTICKS is -1 on a run the server is not
	  keeping -- a cheated or practice one -- so the client honestly signs -1,
	  and a server that threw the receipt away would drop every receipt on
	  exactly the runs a harness can produce.  What the client saw is what it
	  signs; `svticks` beside it is what this server counted, and the two
	  disagreeing is a fact for a reader rather than a reason to refuse.

	  THE SHAPE IS CHECKED AND NOT ONLY THE VALUE, because these two strings are
	  written into a file verbatim: `stof` alone would accept anything and store
	  it, and a field a client chooses the characters of is a field that ends up
	  in somebody's parser.  A digit string cannot.
	*/
	if (!SV_RecIsInt(ticks, TRUE) || !SV_RecIsInt(hidlen, FALSE))
	{
		dprint(sprintf("timer: receipt refused -- ticks %s hidlen %s\n", ticks, hidlen));
		return;
	}
	if (stof(ticks) < -1)
	{
		dprint(sprintf("timer: receipt refused -- ticks %s\n", ticks));
		return;
	}
	if (kept != "0" && kept != "1")
	{
		dprint(sprintf("timer: receipt refused -- kept %s\n", kept));
		return;
	}
	/*
	  THE SERVER LINE IS SIGNED, SO IT IS WRITTEN AS THE CLIENT SIGNED IT --
	  cleaned of anything that could end a line early, and not otherwise
	  touched.  It is the address the CLIENT's netchan says it is talking to,
	  and it is what makes a signature non-portable: see the relay in the patch
	  entry.  A cleaned value that no longer matches what was signed simply
	  fails to verify, which is the right outcome for a client that sent
	  something strange.
	*/
	svname = SV_RecCleanLine(svname);
	if (svname == "")
	{
		dprint("timer: receipt refused -- empty server name\n");
		return;
	}

	/*
	  THE LATCH BEFORE THE OPEN, not after.  Set afterwards, a disk that will
	  not take the file leaves the client free to send this again for the rest
	  of the run, one failed open each time, at whatever rate it likes.
	*/
	/*
	  BESIDE THE EVIDENCE AND NOT IN A DIRECTORY OF ITS OWN, so that
	  SV_EvidenceSweep's `run_evidence_days` reaps it on the same clock as the
	  recording it attests.  The first cut wrote data/receipts/, flat, shared by
	  12 lobbies, swept by nothing at all.
	*/
	path = sprintf("data/evidence/%s/%s.rcpt", mapname, rid);

	// Patch 426: THE FIRST RECEIPT OF A RUNID WINS, as the latch made it before
	// the hold.  A cold save-load keeps a finished run's runid (Patch 426
	// review: a later run's receipt rewrote it as a nonce FAULT).
	if (e.rec_end_rid != "")
	{
		fh = fopen(path, FILE_READ);
		if (fh >= 0)
		{
			fclose(fh);
			dprint(sprintf("timer: receipt refused -- %s already has one\n", rid));
			SV_RecEndHold(e, "", "", 0);    // it can never be written
			return;
		}
	}

	// An abandon's receipt asks for no evidence (review round 4/5): its upload
	// would hold the client's one upload slot while a finish's was refused.
	noup = (e.rec_end_rid != "" && svt == 0);
	if (e.rec_end_rid != "")
	{
		if (rid == e.rec_rec_rid)       // a finish: it is the live run's receipt too
			e.rec_rec_rcpt = TRUE;
		SV_RecEndHold(e, "", "", 0);
	}
	else
		e.rec_rec_rcpt = TRUE;

	fh = fopen(path, FILE_WRITE);
	if (fh < 0)
	{
		dprint(sprintf("timer: cannot write %s\n", path));
		return;
	}

	/*
	  THE OWNER IS A STRANGER'S TEXT AND IS WRITTEN THROUGH THE RECORDER'S OWN
	  SAFETY TEST.  SV_FixupName strips the characters a QuakeC parser trips on;
	  it does not strip the ones PYTHON's splitlines() breaks on -- \v, \f, the
	  file separators, U+2028 -- and this file is read by a Python checker that
	  takes key/value lines.  A name carrying one of those could add lines to
	  this receipt.  Unsafe text is replaced by the player's slot, which nobody
	  can choose.
	*/
	who = SV_RecCleanLine(e.netname);
	if (who == "")
		who = sprintf("slot %g", e.run_t_slot);

	/*
	  THE SIGNED LINES ARE THE FIVE PREFIXED `signed `, IN THIS ORDER -- server,
	  nonce, ticks, hid, view -- each newline-terminated under the version line.
	  A verifier rebuilds the message from them and from nothing else, so any
	  reformatting here breaks every receipt this server writes.  The unsigned
	  context above them is this server's own: what IT calls the run, who IT had
	  connected, and what IT counted.
	*/
	fputs(fh, sprintf("FTESURF-RCPT 1\n"));
	fputs(fh, sprintf("map %s\n", mapname));
	fputs(fh, sprintf("runid %s\n", rid));
	fputs(fh, sprintf("owner %s\n", who));
	fputs(fh, sprintf("svticks %d\n", svt));
	fputs(fh, sprintf("svport %s\n", cvar_string("sv_port")));
	fputs(fh, sprintf("pub %s\n", pub));
	fputs(fh, sprintf("sig %s\n", sig));
	fputs(fh, sprintf("signed server %s\n", svname));
	fputs(fh, sprintf("signed nonce %s\n", nonce));
	fputs(fh, sprintf("signed ticks %s\n", ticks));
	fputs(fh, sprintf("signed hid %s %s %s\n", hid, hidlen, kept));
	fputs(fh, sprintf("signed view %s\n", view));
	fclose(fh);
	dprint(sprintf("timer: receipt %s\n", path));

	/*
	  PATCH 418: AND NOW ASK FOR THE FILE THE CLIENT HAS JUST COMMITTED TO.

	  Here and not at the finish, because THIS is the moment both halves exist:
	  the client has signed a digest for its sidecar, and the server has a
	  receipt to check the arriving bytes against.  Asked for only when the
	  receipt names one -- `view -` is a run with no sidecar and nothing to
	  send.

	  THE REQUEST CARRIES NO PATH THE CLIENT READS.  sv_recupload names where
	  the SERVER's copy lands; the client sends the file its own gamecode armed,
	  or nothing at all.  That asymmetry is the whole security argument and it
	  lives in engine/client/cl_receipt.c.
	*/
	if (run_t_evul && nonce != "" && !noup)
	{
		/*
		  BOTH FILES IN ONE REQUEST, IN THE ORDER THE CLIENT ARMED THEM.  The
		  engine sends them one after the other -- an upload is a single stream
		  -- and asks for the second only when the first has landed.  The
		  journal is asked for ONLY at `run_evidence_ul 2`, and only when this
		  receipt says the client kept one: measured, it is 110 KB per second of
		  run against the sidecar's 2.93 KB, and the client's own cap refuses it
		  past ~38 seconds of run.  At `2` this asks for a file most runs cannot
		  send; see the transport arithmetic in engine/client/cl_receipt.c.
		*/
		/*
		  THE REQUEST NAMES THE RUN.  The engine stuffs `rec_ul_send <nonce>
		  <kind>` and the client answers with the file it armed for THAT run --
		  because the next run can finish while this one's evidence is still on
		  the wire, and a bare request was answered with whatever was armed
		  last.  A run with no nonce cannot be asked: there would be nothing to
		  name it by, and nothing staged under it either.
		*/
		if (view != "-" && hid != "-" && kept == "1" && run_t_evul >= 2)
			localcmd(sprintf("sv_recupload %g %s data/evidence/%s/%s.view data/evidence/%s/%s.hid\n",
			                 num_for_edict(e), nonce, mapname, rid, mapname, rid));
		else if (view != "-")
			localcmd(sprintf("sv_recupload %g %s data/evidence/%s/%s.view\n",
			                 num_for_edict(e), nonce, mapname, rid));
		else if (hid != "-" && kept == "1" && run_t_evul >= 2)
			localcmd(sprintf("sv_recupload %g %s data/evidence/%s/%s.hid\n",
			                 num_for_edict(e), nonce, mapname, rid));
	}
};

/*
  The client asking for the number it should already have.  `cmd rec_nonce_ask`.

  It exists because a stuffcmd is fire-and-forget and there is one case where it
  reliably misses: a `retry` is a map_restart, so the republish above happens
  while that client is still loading and has no CSQC registered to receive it.
  Measured -- p416rewind.cfg's R3 failed exactly there before this existed.

  IT DRAWS NOTHING AND GRANTS NOTHING.  A number already in force, to the client
  already running the run, with no flag touched: the answer still has to come
  back through SV_RecNack.  Silent when there is nothing to send, on that
  function's rule -- a client that asks at the wrong moment is not a fault.
*/
void(entity e) SV_RecNonceAsk =
{
	if (!SV_RecLive(e))
		return;
	if (e.rec_rec_nonce == "")
		return;
	stuffcmd(e, sprintf("rec_nonce %s\n", e.rec_rec_nonce));
};

/*
  BUILD 87 (v9): the three state tracks the engine publishes after each move --
  `pm` (the pin changed), `pe` (the physent list changed), `portal` (the mover
  crossed a linked_portal_door).  Each is written on CHANGE and bound to <row>,
  the `in` row whose move produced it: the value is only visible AFTER that move,
  so it cannot precede its row the way a `ride` does.

  Called at the top of PreThink, before the PostThink sample, and at close --
  i.e. before every `in` row, every sample and the trailer, so no change can
  outlive the move that made it.  Nothing before the first row: the header's
  `pmpin` covers the seed.
*/
void(entity e) SV_RecState =
{
	local float was, row;
	local string pin;

	if (!SV_RecLive(e))
		return;
	// Patch 364: this runs first in both thinks, so the session precedes every
	// counter-stamped line; nothing of the new map's state is written before it.
	SV_RecSession(e);
	if (e.rec_rec_sesspend)
		return;
	if (e.run_movetickrate <= 0 || e.run_pmepoch <= 0 || e.rec_rec_in < 1)
		return;
	row = e.rec_rec_in - 1;

	if (e.run_pmepoch != e.rec_rec_epoch)
	{
		pin = SV_RecPinText(e, "*pmpin");
		if (pin != "")
		{
			was = e.rec_rec_lines;
			SV_RecPut(e, strcat(sprintf("pm %d %d ", e.rec_rec_pk, row), pin));
			if (e.rec_rec_lines != was)
			{
				e.rec_rec_epoch = e.run_pmepoch;
				e.rec_rec_pm = e.rec_rec_pm + 1;
			}
		}
	}

	if (!e.rec_rec_pcset || e.run_physcrc != e.rec_rec_pcrc)
	{
		was = e.rec_rec_lines;
		SV_RecPut(e, sprintf("pe %d %d %d", e.rec_rec_pk, row, e.run_physcrc));
		if (e.rec_rec_lines != was)
		{
			e.rec_rec_pcrc = e.run_physcrc;
			e.rec_rec_pcset = TRUE;
			e.rec_rec_pe = e.rec_rec_pe + 1;
		}
	}

	if (e.run_portalx != e.rec_rec_portalx)
	{
		was = e.rec_rec_lines;
		SV_RecPut(e, sprintf("portal %d %d %d %.9v %.9v", e.rec_rec_pk, row,
		                     e.run_portalx - e.rec_rec_portalx,
		                     e.run_portalorg, e.run_portalvel));
		if (e.rec_rec_lines != was)
		{
			e.rec_rec_portalx = e.run_portalx;
			e.rec_rec_portal = e.rec_rec_portal + 1;
		}
	}
};

/*
  Start a recording: take a buffer, write the header, dump the ring into it.

  The header is deliberately plain text with one key per line: a format that can
  be read with `type` is the one that survives being written before its reader.
  Unknown keys must be SKIPPED rather than treated as an error, which is what
  lets v3 add owner/runid/view without a v2 reader caring.

  `owner` and `runid` are here for the peer-to-peer future rather than for
  anything today: a run that will one day be merged with someone else's needs to
  say whose it is and to have a name that is unique off this machine.  runid is
  the wall clock to the second plus the sample counter, which is unique unless
  two runs on the same leg start in the same second on the same profile.
*/
void(entity e) SV_RecOpen =
{
	local float i, s, base;
	local string mcrc;	// build 73; `s` above is the padding-ring index, not a string
	local string pin;	// build 87

	SV_RecCopyFlush(e);                 // Patch 375: the part file is about to be reopened
	SV_RecGenReset(e);
	e.rec_rec_ver = 9;
	e.rec_rec_inmt = -1;
	e.rec_mc_n = e.rec_mc_bad = 0;      // Patch 376
	e.rec_mc_badrow = -1;
	e.rec_mc_sup = 0;                   // Patch 405
	if (e.rec_rec_nonce != "")          // Patch 416: the last run's, freed here
	{
		strunzone(e.rec_rec_nonce);
		e.rec_rec_nonce = "";
	}
	e.rec_rec_rcpt = FALSE;             // Patch 417: one receipt per run
	e.rec_rec_buf = -1;
	e.rec_rec_fh = -1;
	e.rec_rec_stream = FALSE;
	e.rec_rec_flagofs = -1;
	e.rec_rec_lines = e.rec_rec_n = e.rec_rec_padn = e.rec_rec_cp = 0;
	e.rec_rec_full = FALSE;
	/*
	  BUILD 82.  Both reset here and nowhere else, because this is the one place
	  a recording begins.

	  THE FIRST `in` ROWS CARRY 0, not 1, and it is worth writing down because the
	  ordering is easy to get backwards.  This function is reached from
	  SV_TimerStart, which is reached from SV_TimerFrame, which has ALREADY done
	  its increment for the start packet -- so the reset lands after it.  The next
	  packet's PreThinks then write their rows before that packet's PostThink
	  increments anything.  Measured: the first row of a real run reads `in 0 605
	  ...` against `instart 605 605`.  Nothing reads the absolute value; this note
	  exists so that a reader checking the reset against the first row does not
	  conclude the counter is broken.
	*/
	e.rec_rec_in = e.rec_rec_pk = 0;
	// BUILD 83: and the warp count, here for the same reason and nowhere else.
	e.rec_rec_warp = 0;
	// BUILD 85: the ride count and the carrier sentinel.  rec_rec_bv is
	// deliberately NOT zeroed -- clearing the sentinel is what matters, and a
	// zeroed vector would make a missing sentinel look correct on a run that
	// started at rest, i.e. hide the bug on every file except the ones that matter.
	e.rec_rec_ride = 0;
	e.rec_rec_bvset = 0;
	// BUILD 87 (v9): the state tracks.  The epoch and portal count are seeded from
	// the LIVE values below, so the first record is a change and not the history.
	e.rec_rec_pm = e.rec_rec_pe = e.rec_rec_portal = 0;
	e.rec_rec_posts = 0;                // Patch 360
	e.rec_rec_pauses = e.rec_rec_sess = e.rec_rec_sesspend = 0;    // Patch 364
	e.rec_rec_pcset = 0;
	e.rec_rec_epoch = 0;
	e.rec_rec_portalx = e.run_portalx;
	e.rec_rec_zseed = TRUE;	// build 88: written at the end of this SV_TimerFrame
	// +1 so that 0 can mean "no run": track 0 leg 0 is the main track's full
	// run, which is the most common leg there is, and it would otherwise encode
	// to the same 0 that a discarded run leaves behind.  BUILD 57: the LEG, not
	// the starting segment -- see FS_LegOf.
	e.rec_rec_leg = e.run_t_track * 100 + FS_LegOf(e.run_t_startseg, e.run_t_stagerun) + 1;
	e.rec_rec_tag = RT_NONE;
	e.rec_rec_ticks = 0;
	// BUILD 66, AND THIS IS THE RESET THAT MATTERS.  A run that records nothing
	// at all never reaches a close, so without clearing here it would inherit
	// the PREVIOUS run's answer and submit that run's filename as its own.
	e.rec_rec_saved = FALSE;
	e.rec_rec_bytes = -1;

	// A new buffer is a new run, whether or not one is actually created below;
	// a save state's mark from the PREVIOUS run must not match this one.
	e.rec_rec_serial = SV_RecNextSerial();

	if (!SV_RecEnabled())
		return;

	/*
	  One of the two recorders, decided here and nowhere else.  The rest of this
	  function is identical either way, which is the point: the header, the
	  padding flush and every sample go through SV_RecPut and it is SV_RecPut
	  that knows where they land.
	*/
	e.rec_rec_stream = SV_RecStreams();
	if (e.rec_rec_stream)
	{
		e.rec_rec_partlob = Lobby_Active() ? 1 : 2;
		e.rec_rec_fh = fopen(SV_RecPartPath(e), FS_FILE_WRITESTREAM);
		if (e.rec_rec_fh < 0)
		{
			// Not fatal to the run, only to its recording -- the same shape as
			// the buf_create failure below, and said the same way.
			dprint(sprintf("timer: cannot stream to %s; this run is not being "
			               "recorded\n", SV_RecPartPath(e)));
			e.rec_rec_stream = FALSE;
			return;
		}
	}
	else
	{
		e.rec_rec_buf = buf_create_ex("string", 0);
		if (e.rec_rec_buf < 1)
		{
			dprint("timer: buf_create failed; this run is not being recorded\n");
			return;
		}
	}

	/*
	  BUILD 76: VERSION 5, AND THE BUMP IS NOT ADDITIVE HOUSEKEEPING.

	  Every other key added since version 4 went in under the header's additive
	  rule -- an unrecognised keyword falls through to nothing, so an old reader
	  skips it and a new reader derives what a file without it meant.  That rule
	  cannot carry this one.  Version 5 changes what the NUMBERS MEAN: `ticks` in
	  the trailer and `t` on every sample are counted off the mover's own tick
	  counter rather than sampled off sv.time, and a version-4 reader handed a
	  version-5 file would parse every field correctly and be wrong about all of
	  them by 0-2 ticks with no way to tell.  A silent difference is exactly what
	  a version number is for.

	  IT IS ALSO THE VERSION MARKER FOR ARCHIVED RUNS, and it costs nothing
	  because the marker was already being read.  The migration wanted a way for a
	  run filed before build 76 to be distinguishable from one filed after, and
	  the obvious route -- a marker in the FILENAME -- would have touched
	  FS_RunPathWho's grammar, the 7-digit stamp parse, FS_TagFromName, the
	  pruner's glob and `ui_who`, for a fact that is already in the file.
	  cl_scores.qc parses `FTESURF-REC <n>` into rec_sb_rowver[] for every row it
	  lists, and has since build 23.  So the version IS the marker, per file,
	  already joined to the row that shows it.  Same shape as the padding ring:
	  the cheap route was the one that added nothing.
	*/
	SV_RecPut(e, "FTESURF-REC 9");
	SV_RecPut(e, sprintf("map %s", mapname));
	SV_RecPut(e, sprintf("track %g", e.run_t_track));
	SV_RecPut(e, sprintf("startseg %g", e.run_t_startseg));
	/*
	  BUILD 57: THE LEG, BESIDE THE SEGMENT, because the segment stopped naming it.
	  A stage-1 run and a full run both write `startseg 0`; this key is what tells
	  a reader which folder the file belongs to.  ADDITIVE, by the header's own
	  rule -- an older reader skips it, and a newer reader that does not find it
	  derives FS_LegOf(startseg, startseg > 0), which is what every file written
	  before this line meant.
	*/
	SV_RecPut(e, sprintf("leg %g", FS_LegOf(e.run_t_startseg, e.run_t_stagerun)));
	SV_RecPut(e, sprintf("tickrate %g", run_t_tick));
	/*
	  BUILD 74: THE RATE THE MOVER ACTUALLY USED, beside the rate this file
	  believes.  Engine Patch 325.  ADDITIVE, by the header's own rule above.

	  `tickrate` on the line above is cvar("pm_ticrate") as cached by
	  SV_TimerMapInit.  `movetickrate` is the number PMSrc_PlayerMove divided the
	  command's msec by.  They SHOULD be identical and the whole reason to write
	  both is that nothing has ever checked: a recording carries a tick count and
	  a rate, and every reader -- reccheck.py, the replay, surfd's millis -- turns
	  one into the other by multiplying.  If the two rates ever diverge, every
	  time in the file is wrong by their ratio and nothing in the file says so.
	  Build 64 shipped that bug in the other direction, reading bhop maps at a
	  0.015 constant when they run at 0.01.  Two lines make it falsifiable.

	  Zero means "no engine value" -- an engine older than Patch 325, or the
	  Source mover off -- and readers must treat it as absent, not as a rate.
	*/
	SV_RecPut(e, sprintf("movetickrate %g", e.run_movetickrate));
	/*
	  BUILD 76: WHICH OF THE TWO CLOCKS TIMED THIS RUN.  `counted` or `sampled`.

	  A word rather than the version number, even though version 5 already
	  implies it, because the two facts can come apart in exactly one direction
	  and it is a direction that will happen: a build-76 server running against an
	  engine older than Patch 325 writes a version-5 file whose times are sampled.
	  `clock sampled` in a version-5 header is that server saying so in the file,
	  where the run's own TF_NOCLOCK bit says it on the board.  A reader that had
	  to infer it from `movetickrate 0` would be inferring, and this format's rule
	  since build 73's mapcrc is that a recording states what it knows.

	  It is written at OPEN because the choice is made at the start and latched
	  for the life of the run (see run_t_clock).  There is deliberately no path by
	  which a file's answer to this could change halfway down.
	*/
	SV_RecPut(e, sprintf("clock %s", e.run_t_clock ? "counted" : "sampled"));
	SV_RecPut(e, sprintf("owner %s", e.netname));
	// Patch 360: kept (zoned) as the run's id for stage posts and the evidence
	// file; a lobby appends its port -- 12 lobbies share one data dir.  Readers
	// slice only the date prefix.
	if (e.rec_rec_rid != "")
		strunzone(e.rec_rec_rid);
	if (Lobby_Active())
		e.rec_rec_rid = strzone(sprintf("%s-%g-p%s", strftime(TRUE, "%Y%m%d-%H%M%S"),
		                                e.run_t_slot, cvar_string("sv_port")));
	else
		e.rec_rec_rid = strzone(sprintf("%s-%g", strftime(TRUE, "%Y%m%d-%H%M%S"),
		                                e.run_t_slot));
	SV_RecPut(e, strcat("runid ", e.rec_rec_rid));

	// Patch 416: after `runid`, which it hashes.  The header's nonce is session
	// one's; a resume writes its own into the body.  See SV_RecNonce.
	SV_RecNonce(e, FALSE);

	/*
	  BUILD 73: WHICH BYTES OF THE MAP THIS RUN'S PHYSICS ACTUALLY RAN ON.
	  Engine Patch 321.  ADDITIVE, by the header's own rule above.

	  `map` names a file and a file name is not a map -- six maps in this library
	  are the same name at two different builds, and a recompiled BSP keeps its
	  name while changing every ramp on it.  A re-simulation verifier (the plan's
	  Layer 2) cannot check a claimed time without knowing exactly which bytes it
	  is re-simulating against, and neither can anybody comparing two runs on
	  "the same" map years apart.  This is the cheapest possible answer: one line,
	  written once, at open.

	  THE SERVER'S OWN HASH, NOT THE CLIENT'S CLAIM, and that is the distinction
	  that makes it worth storing.  TF_NOMAP records whether the CLIENT agreed,
	  which is a statement about the client and is only as good as the client;
	  this line records what the machine that ran the physics loaded, which no
	  client can influence.  The two answer different questions and the file
	  carries both.

	  OMITTED RATHER THAN WRITTEN EMPTY when the engine reports unknown -- a
	  pre-321 engine or plugin, or a loader that computes no checksum.  An absent
	  key reads as unknown to every reader by the header's existing rule, where a
	  `mapcrc ` with no value would be a line the grammar does not describe.
	*/
	mcrc = infokey(world, "*mapcrc");
	if (mcrc != "")
		SV_RecPut(e, sprintf("mapcrc %s", mcrc));

	/*
	  BUILD 81: WHICH BOXES THE CLOCK WAS STARTED AND STOPPED BY.  Additive, the
	  same way mapcrc was, and it exists because THE ARGUMENT DIRECTLY ABOVE DOES
	  NOT GO FAR ENOUGH.

	  mapcrc answers "which bytes did the physics run on".  It does not answer
	  "which boxes decided the time", and on this game those are different files.
	  SV_ZoneLoad tries maps/zones/local/<map>.json, then maps/zones/online/<map>
	  .json, and only then the BSP's own trigger brushes (sv_zones.qc:173-178).
	  Two of the three are not the map and can be re-authored at any moment, under
	  a standing record, with nothing in the file to notice.  The start tick and
	  the finish tick are both a function of that table, so a recording that names
	  its map and not its zones is not sufficient to re-simulate -- which is the
	  whole purpose mapcrc was added for.

	  AND `zonesrc` ALONE WOULD NOT DO IT, which is why there are two keys and not
	  one.  The BSP path deflates every box by a unit on all six faces
	  (sv_zones.qc:111, deliberate and documented there), so a BSP-sourced end
	  zone is two units smaller per axis than a JSON traced from the same brush.
	  Same map, same source name, different geometry.  zonecrc is over the BUILT
	  table precisely so those two hash differently -- see Zone_Hash.

	  zonerule IS THE THIRD FACT AND IT IS NOT GEOMETRY.  Whether a crossing is a
	  swept segment test or a point test (run_zone_swept), and whether entry and
	  occupancy are asked of the player's HULL or of the origin, and which hull
	  (run_zone_hull, run_zone_hull_live) -- all three are latched per map at
	  SV_TimerMapInit precisely so they cannot move under a run, and none of them
	  is a movevar, so pm_lockmovement does not cover them and nothing else in
	  this header records them.  Two servers with an identical table and different
	  rules produce different times from identical input.

	  OMITTED WHEN THERE IS NO TABLE, on the mapcrc precedent: a map with no zones
	  cannot be timed at all, so writing `zonecrc ` empty would describe nothing.
	*/
	if (zone_crc != "")
	{
		SV_RecPut(e, sprintf("zonesrc %s", Zone_SourceTag(zone_source)));
		SV_RecPut(e, sprintf("zonecrc %s", zone_crc));
		SV_RecPut(e, sprintf("zonerule %d %d %d",
		                     run_t_swept, run_t_hull, run_t_hulllive));
	}

	/*
	  BUILD 82: WHERE THE INPUT TRACE BEGINS, AND WHAT IT CANNOT COVER.

	  The `in` records below this header are what a re-simulation verifier reads.
	  They do not start at the start.  SV_RecOpen is called from SV_TimerStart,
	  which is called from SV_TimerFrame, which runs in PlayerPostThink -- i.e. at
	  the END of the packet that carried the player out of the start box.  Every
	  usercmd in that packet has already been simulated by the time this line is
	  written, so the commands that actually crossed the start plane are NOT IN
	  THIS FILE and no arrangement of this call site would put them there short of
	  a second ring buffer holding inputs, which is not built.

	  SAYING SO IN THE FILE IS THE ENTIRE POINT.  A verifier that did not know
	  this would re-simulate from the first `in` row, land short of the recorded
	  start, and report a discrepancy that is the recorder's and not the run's.
	  Knowing it, the horizon is exactly stated: seed from the first SAMPLE --
	  which SV_TimerRecFrame writes in this same PlayerPostThink, from the
	  post-move origin and velocity -- and verify forward from there.  What that
	  costs is real and should be said plainly: the start LATCH itself is taken on
	  trust, and only the run from the start packet's end state to the finish is
	  reproducible.  That is a smaller claim than "the run is re-simulable" and it
	  is the true one.

	  TWO NUMBERS AND NOT ONE.  They are equal here, always, because SV_TimerStart
	  assigns run_t_starttick = run_movetick three lines before calling this --
	  which is exactly why writing only one of them would be a trap.  (Until
	  Patch 363 SV_TimerResume rebased run_t_starttick to `movetick - ticks`; it
	  now latches movetick and carries the restored ticks in run_t_tickcarry, so
	  a resumed run's clock never needs a start below any horizon.)

	  GATED ON THE MOVER COUNTER EXISTING, on the mapcrc precedent.  Against an
	  engine older than Patch 325 there is no run_movetick, every `in` row would
	  stamp a constant 0, and a horizon of 0 would be a false statement rather
	  than a missing one.  No key, no rows -- SV_TimerInFrame takes the same test.
	*/
	if (e.run_movetickrate > 0)
	{
		SV_RecPut(e, sprintf("instart %d %d",
		                     e.run_movetick, e.run_t_starttick));
		e.rec_rec_inmt = e.run_movetick;    // Patch 375: SV_RecPause's `instart` case
		e.rec_rec_incy = 0;
	}

	/*
	  BUILD 83: THE START JITTER, as a RULE and an OUTCOME on one line.

	  `startjit <units> <dx> <dy> <dz>` -- the magnitude that was in force and the
	  offset that was actually applied.  Both, on the zonerule precedent: a rule
	  and the data it produced are two facts, and a verifier handed only the
	  outcome cannot tell a run that rolled a small number from one played under
	  a smaller rule.

	  A HEADER KEY AND NOT A RECORD, which is this grammar's own distinction: a
	  record is an event with a time, a key is a property of the run.  The jitter
	  happens exactly at the start, and the header already says when that was.

	  WRITTEN WHENEVER THE RULE WAS IN FORCE, including when it applied nothing.
	  Three distinguishable states, and they have to stay distinguishable:

	    absent           the rule was off, or the file predates build 83
	    startjit 2 0 0 0 the rule ran and every candidate was blocked
	    startjit 2 ...   the rule ran and moved the player

	  Folding the middle one into absence is the sv_mapcheck shape exactly -- two
	  sides that are both zero, agreeing, for as long as nobody looks.

	  %.4f AND NOT %g.  The offset is a small number near zero and %g is six
	  SIGNIFICANT digits, so it would spend all six on a value whose useful range
	  is +-2; four decimals is 0.0001 u, well under the sample's own %.2f floor,
	  and it is a fixed width a reader can rely on.
	*/
	if (run_t_startjit > 0)
		dprint(sprintf("timer: startjit %.4f %.4f %.4f\n", run_t_startjit,
		               e.run_t_jitter_x, e.run_t_jitter_y));
	if (run_t_startjit > 0)
		SV_RecPut(e, sprintf("startjit %.4f %.4f %.4f %.4f", run_t_startjit,
		                     e.run_t_jitter_x, e.run_t_jitter_y,
		                     e.run_t_jitter_z));

	/*
	  RESERVED, and rewritten by SV_RecClose.

	  The index is remembered rather than hardcoded, because the one thing that
	  would silently corrupt a header is a line inserted above this one by a
	  later build and a constant 7 left behind.  SV_RecClose checks the line it
	  is about to overwrite still begins with `flags` before writing, so even a
	  stale index refuses rather than clobbers.

	  Zero at open is the truth at open: a run cannot be practice before it has
	  started.  Everything that can taint it happens later.
	*/
	/*
	  BUILD 66: A BYTE OFFSET AS WELL AS A LINE INDEX, because the two recorders
	  correct this line by different means and each needs its own handle on it.
	  The buffered one overwrites by line index with bufstr_set; the streamed one
	  seeks to a byte and writes the same width back.  fseek before the write is
	  what makes the offset the START of the line rather than its end.
	*/
	e.rec_rec_flagline = e.rec_rec_lines;
	if (e.rec_rec_stream)
		e.rec_rec_flagofs = fseek(e.rec_rec_fh);
	SV_RecPut(e, SV_RecFlagLine(0));

	/*
	  BUILD 87 (v9): THE PHYSICS PIN, AFTER `flags` so the scoreboard's 24-line
	  header read still reaches `flags`.  The mover's inputs as of the start
	  packet's last move, as the engine snapshot them (Patch 346) -- never
	  cvar(): five movevars are spawn-latched and maxspeed/entgravity lag a send
	  frame.  Absent on an engine that does not publish, and a reader must then
	  treat the physics as unknown.
	*/
	pin = SV_RecPinText(e, "*pmpin");
	e.rec_rec_pinned = (pin != "");
	if (pin != "")
	{
		SV_RecPut(e, strcat("pmpin ", pin));
		e.rec_rec_epoch = e.run_pmepoch;
	}

	SV_RecPut(e, "begin");

	/*
	  BUILD 87 (v9): THE EXACT SEED.  The state the first `in` row's move starts
	  from, at %.9g (float32 round-trips), with the carried pm_source state.  The
	  %.2f sample below it is for watching; seeding a replay from it is where E3
	  and b83's open loops began to drift.  Only with the pin, for the same reason.
	*/
	if (pin != "")
		SV_RecSeed(e);

	// A fresh run has boarded nothing yet.  Seeded from the LIVE counter and not
	// from zero: the engine's counter is per-map and does not reset with the run,
	// so zeroing it here would emit a spurious `board` record on the first sample
	// of every attempt after the first.
	e.rec_rec_lastbc = e.run_boardcount;

	e.run_t_flags = e.run_t_flags | TF_RECORDING;

	// The padding, oldest first.  Timestamps are absolute on the clock the ring
	// stamps -- SV_ClockSec since build 76, sv.time before it -- and are made
	// relative to the START here, so they come out negative, which is exactly
	// what a playback needs to know where t=0 is.  See SV_RecPad for why moving
	// the ring to the counted clock cost no new array.
	base = SV_RecPadBase(e);
	if (base < 0)
		return;

	for (i = 0; i < e.rec_pad_len; i = i + 1)
	{
		s = base + ((e.rec_pad_head - e.rec_pad_len + i + FS_RECPAD * 2) % FS_RECPAD);
		SV_RecLine(e, rec_pad_t[s] - e.run_t_startsec,
		           rec_pad_org[s], rec_pad_vel[s], rec_pad_mv[s],
		           rec_pad_pit[s], rec_pad_yaw[s], rec_pad_fl[s], rec_pad_key[s],
		           rec_pad_norm[s]);
	}
	e.rec_rec_padn = e.rec_rec_n;
};

/*
  Throw the recording away.

  One buf_del.  Nothing was opened, so there is nothing to truncate, close,
  remove or rename -- which is the point of the buffer, because this path runs
  every time you press !r mid-run, and that is most of practice.

  RUNTAG is cleared here as well as set on close, so a client holding a stale
  "that one was a PB" from the previous run cannot mistake a voided run for a
  kept one and write a sidecar over a recording that is still good.
*/
/*
  PATCH 360: AN ABANDONED RUN THAT POSTED STAGES KEEPS ITS RECORDING.  Its stage
  rows are on the board, and deleting the stream would leave them with nothing
  to audit.  The file is closed the way SV_RecClose closes one -- `abandon`,
  then inend/end with the real counts -- and moved to
  data/evidence/<map>/<runid>.rec, outside data/runs so no list shows it;
  swept after run_evidence_days (SV_EvidenceSweep).  TRUE when it took the file.
*/
// The `end` trailer.  Two sprintfs: ten values against the eight-argument cap.
// Patch 364: an 11th field, <sessions>, in a v10 file (one with a `pause`).
void(entity e, float ticks) SV_RecTrailer =
{
	local string s;
	s = strcat(sprintf("end %d %d %d %d %d ",
	                   ticks, e.rec_rec_n, e.rec_rec_padn, e.rec_rec_cp, e.rec_rec_in),
	           sprintf("%d %d %d %d %d",
	                   e.rec_rec_warp, e.rec_rec_ride, e.rec_rec_pm,
	                   e.rec_rec_pe, e.rec_rec_portal));
	if (e.rec_rec_pauses > 0)
		s = strcat(s, sprintf(" %d", e.rec_rec_sess));
	SV_RecPut(e, s);
};

float(entity e) SV_RecKeepEvidence =
{
	local float ticks, flags, fh;
	local string dst;

	if (e.rec_rec_posts <= 0 || e.rec_rec_rid == "")
		return FALSE;
	ticks = SV_TimerTicks(e);
	flags = e.run_t_flags - (e.run_t_flags & TF_RECORDING) - (e.run_t_flags & TF_FROZEN);
	SV_RecPut(e, sprintf("abandon %d", ticks));
	SV_RecState(e);
	if (e.run_movetickrate > 0)
		SV_RecPut(e, sprintf("inend %d %.9g", e.run_movetick, e.run_movecarry));
	SV_RecTrailer(e, ticks);
	dst = sprintf("data/evidence/%s/%s.rec", mapname, e.rec_rec_rid);
	if (e.rec_rec_stream)
	{
		if (e.rec_rec_fh < 0)
			return FALSE;
		SV_RecCopyFlush(e);             // Patch 375: before the rename
		if (e.rec_rec_flagofs >= 0)
		{
			fseek(e.rec_rec_fh, e.rec_rec_flagofs);
			fputs(e.rec_rec_fh, SV_RecFlagLine(flags));
		}
		fclose(e.rec_rec_fh);
		e.rec_rec_fh = -1;
		fremove(dst);
		if (frename(SV_RecPartPath(e), dst) != 0)
		{
			fremove(SV_RecPartPath(e));
			return TRUE;                // the handle is gone either way
		}
	}
	else
	{
		if (e.rec_rec_flagline >= 0 && e.rec_rec_flagline < e.rec_rec_lines)
			bufstr_set(e.rec_rec_buf, e.rec_rec_flagline, SV_RecFlagLine(flags));
		fh = fopen(dst, FILE_WRITE);
		if (fh < 0)
			return FALSE;
		buf_writefile(fh, e.rec_rec_buf, 0, e.rec_rec_lines);
		fclose(fh);
	}
	print(sprintf("^5board:^7 kept %s (%g posted stage(s))\n", dst, e.rec_rec_posts));
	return TRUE;
};

// Evidence past run_evidence_days goes, by the runid's date (this map only).
/*
  Patch 418, after review: SWEEP ONE MAP EVERY INIT, THE WHOLE TREE ONCE.

  `pat` is the glob.  The per-map form is what this always did and it is cheap;
  the problem it left is that the directory is only ever visited while the map
  is in rotation, so a map that drops out keeps its evidence FOREVER.  With
  receipts that was ~500 bytes a run.  With uploads it is a few hundred KB a
  run, and it is also a promise broken: `run_evidence_days` is the retention
  this server states, and it was only being applied to whatever happened to be
  loaded.
*/
void(string pat) SV_EvidenceSweepPat =
{
	local float h, n, i, today, days, d, cut;
	local string fn;

	days = cvar("run_evidence_days");
	if (days <= 0)
		return;
	today = FS_DayNumOf(strftime(TRUE, "%Y%m%d"));
	/*
	  Patch 417: `.rc*` rather than `.rec`, so the run RECEIPTS this directory
	  now also holds expire on the same clock as the recordings they attest.
	  A receipt is client-driven -- one per run, written where nothing else
	  reaps it -- and an unbounded directory on a shared data dir is a fleet
	  problem rather than a file problem: 12 lobbies write into one tree, and
	  inodes run out long before bytes do.
	*/
	/*
	  Patch 418: `*.*` rather than `*.rc*`, because this directory now holds
	  three kinds of file with one lifetime -- the recording, its receipt, and
	  the client's uploaded sidecar.  They are all named for the same runid, so
	  the same date test covers all three, and a sweep that knew about two of
	  them would leave the third to grow forever.
	*/
	h = search_begin(pat, FS_NAMESORT, TRUE);
	if (h < 0)
		return;
	n = search_getsize(h);
	for (i = 0; i < n; i = i + 1)
	{
		fn = search_getfilename(h, i);
		cut = strlen(fn) - 1;
		while (cut >= 0 && str2chr(fn, cut) != 47)     // '/'
			cut = cut - 1;
		d = FS_DayNumOf(substring(fn, cut + 1, 8));
		if (d >= 0)
		if (today - d > days)
			fremove(fn);
	}
	dprint(sprintf("timer: evidence sweep %s (%g file(s) considered)\n", pat, n));
	search_end(h);
};

void() SV_EvidenceSweep =
{
	local string today;

	SV_EvidenceSweepPat(sprintf("data/evidence/%s/*.*", mapname));

	/*
	  AND ONCE A DAY, EVERY MAP -- including the ones no longer in rotation,
	  which is the only way their evidence is ever reaped.  Rotation is the
	  whole hole: this only ever visited the directory of the map that was
	  LOADED, so a map that leaves the pool keeps its evidence forever and
	  `run_evidence_days` quietly stops being the retention this server states.

	  The stamp is LOCALINFO and not a global or a cvar, both of which were
	  tried: SSQC globals are reset by the map load, and a cvar the gamecode
	  creates is purged when the progs are freed -- measured, the cvar version
	  ran the full sweep at every map init.  `svs.localinfo` outlives the progs,
	  is not sent to clients, and holds a day number rather than a flag so a
	  server that stays up for a fortnight sweeps on each of those days rather
	  than once at boot.
	*/
	/*
	  ONE PROCESS, NOT TWELVE, AND THAT IS WHY IT IS OPT-IN.  The tree is
	  shared: a whole-tree sweep applies THIS server's `run_evidence_days` to
	  every other lobby's evidence, so a practice server set to 1 would reap the
	  ranked lobbies a day after they recorded.  Set `run_evidence_sweepall 1`
	  on exactly one process -- the one whose retention is the house rule.
	*/
	if (!cvar("run_evidence_sweepall"))
		return;
	today = strftime(TRUE, "%Y%m%d");
	if (infokey(world, "fs_evswept") == today)
		return;
	localcmd(sprintf("localinfo fs_evswept %s\n", today));
	SV_EvidenceSweepPat("data/evidence/*/*.*");
};

void(entity e) SV_RecDiscard =
{
	local float live;

	/*
	  ONLY clear the tag if there was actually a recording to throw away, and
	  this distinction is the whole correctness of the handshake.

	  SV_TimerArm calls this unconditionally, and on a staged map arming is
	  immediate: you finish stage 1 and the moment you step out of its box the
	  next stage arms.  Clearing the tag there would race the client, which has
	  not necessarily rendered a frame since the finish -- at 30 fps two server
	  snapshots can land between two frames, and the sidecar would be silently
	  lost.  After SV_RecClose the buffer is already gone, so `live` is false and
	  the tag stands until the next run actually opens.

	  A VOIDED run is the case that must still clear it, and does: there the
	  buffer is live, because the run was.
	*/
	live = SV_RecLive(e);
	SV_RecCopyFlush(e);                 // Patch 375: the part file goes below
	SV_RecGenReset(e);

	if (live)
	if (SV_RecKeepEvidence(e))          // Patch 360: posted stages keep the file
	{
		if (!e.rec_rec_stream)
			buf_del(e.rec_rec_buf);
		live = FALSE;
		// Patch 426: kept, so the receipt the client signs next is held for.
		// No sidecar is asked for (RT_NONE, leg 0, as before): an abandon's
		// upload would hold the engine's one upload slot while the next
		// finish's sidecar was refused (review round 4).
		e.rec_rec_leg = 0;
		e.rec_rec_tag = RT_NONE;
		e.rec_rec_ticks = 0;
		e.rec_rec_saved = FALSE;
		e.rec_rec_bytes = -1;
		SV_RecEndHold(e, (e.run_t_flags & TF_NONCE && !e.rec_rec_rcpt) ? e.rec_rec_rid : "",
		              e.rec_rec_nonce, 0);
	}
	// Patch 426: an unkept end signs 0, as a held abandon does, so it clears
	// one; a held finish (its stamp, or -1) cannot be mistaken for it.
	else if (e.rec_end_ticks == 0)
		SV_RecEndHold(e, "", "", 0);

	if (live)
	{
		/*
		  BUILD 66: a streamed run has a FILE to get rid of, and this is the one
		  place the essay above stops being true -- "nothing was opened, so there
		  is nothing to truncate, close, remove or rename" is a property of the
		  buffer, not of recording.  The part file is closed and removed; there is
		  still no truncate and no rename, because the part name is not a name
		  anything else ever reads.

		  The bytes already written are wasted, and that is the honest cost of
		  streaming: this path runs on every `!r`, which on a lobby is most of
		  what a player does.  It is disk that was going to be written anyway and
		  the alternative -- holding the run in memory in case it is thrown away --
		  is the thing being fixed.
		*/
		if (e.rec_rec_stream)
		{
			if (e.rec_rec_fh >= 0)
				fclose(e.rec_rec_fh);
			fremove(SV_RecPartPath(e));
		}
		else
			buf_del(e.rec_rec_buf);

		e.rec_rec_leg = 0;
		e.rec_rec_tag = RT_NONE;
		e.rec_rec_ticks = 0;
		e.rec_rec_saved = FALSE;
		e.rec_rec_bytes = -1;
	}

	e.rec_rec_buf = -1;
	e.rec_rec_fh = -1;
	e.rec_rec_stream = FALSE;
	e.rec_rec_flagofs = -1;
	e.rec_rec_lines = 0;

	/*
	  The SAMPLE counters go too, and they did not before build 17.

	  They were harmless while nothing read them between runs -- SV_RecOpen
	  zeroes all three -- but "harmless because nobody looks" stopped being true
	  the moment `timer` started printing them, and it immediately reported "rec
	  lines 0 (159 samples)" for a player with no recording at all.  A counter
	  that survives the thing it counts is a counter that will eventually be
	  believed.
	*/
	e.rec_rec_n = e.rec_rec_padn = e.rec_rec_cp = 0;
	e.rec_rec_full = FALSE;

	e.run_t_flags = e.run_t_flags - (e.run_t_flags & TF_RECORDING);
	e.rec_rec_posts = 0;
	if (e.rec_rec_rid != "")
		strunzone(e.rec_rec_rid);
	e.rec_rec_rid = "";                 // an unrecorded next run posts no runid
	// Patch 416: beside its sibling.  A client edict is recycled without being
	// cleared, so a player who drops mid-run would otherwise leave a zoned
	// nonce held on that slot until somebody else's run opened.
	if (e.rec_rec_nonce != "")
		strunzone(e.rec_rec_nonce);
	e.rec_rec_nonce = "";
};

/*
  BUILD 23: hold the archive to rec_runs_keep files per leg, per tag class.

  It exists because putting the time in the filename removed the thing that used
  to bound this directory: a run no longer overwrites its predecessor, so
  without a pruner a leg grows one .rec + .view + .hid -- call it three megabytes
  -- every time you improve or take a practice run, forever, and nothing in the
  game would ever say so.

  SLOWEST FIRST, which is what makes this safe to run unattended.  The names are
  zero-padded tick counts, so an ascending name sort is an ascending TIME sort,
  so the entries past the quota are exactly the slowest ones and the personal
  best is the one file that can never be chosen.  That property is the entire
  reason the stamp is padded rather than written plain.

  PER TAG CLASS, not per leg.  One shared quota would let a session of practice
  shadow runs evict a year of real personal bests, which is the sort of loss a
  player discovers months later and cannot undo.

  The file just written is skipped rather than considered.  If it IS the slowest
  and over quota, the directory carries keep+1 entries until the next run prunes
  it -- a deliberate off-by-one, because the alternative is deleting a .rec while
  the client is still a frame or two away from writing the .view that belongs to
  it, leaving a sidecar with nothing on the other end of its name.

  `keepme` is the new file's BASENAME and the comparison is against the tail of
  each result, not the whole path.  search_getfilename returns whatever form the
  engine's enumerator produces, and this function's failure mode if the two
  spellings ever disagree is to delete the run it was called to protect -- so it
  compares the shortest thing that can possibly identify the file rather than
  the longest.
*/
/*
  BUILD 24: `startseg` is a PARAMETER now and was e.run_t_startseg.

  It had to become one the moment a main run started writing stage legs: during a
  main run e.run_t_startseg is 0, so a stage's prune would have swept the `main`
  folder instead of stage_N -- deleting real runs to make room for a file that is
  not even in that directory.  The call site is what knows which leg it just
  wrote, which is the same argument SV_RecLine already makes about its timestamp.

  BUILD 57: AND IT IS A LEG NOW, NOT A SEGMENT.  The two call sites pass the leg
  they just wrote into -- FS_LegOf of the run for a finish, seg + 1 for a lifted
  stage -- because FS_RunDir takes a leg, and a segment handed to it sweeps the
  folder of the stage before the one that was written.
*/
/*
  BUILD 66: AND PER PLAYER, on a lobby.  This is the second half of the
  filename change and it is the half that could have cost somebody their runs.

  The glob was `*_<tag>.rec` and the `*` swallows a middle component happily, so
  this function would have kept working and quietly done the wrong thing: one
  quota shared by thirty-two people, swept SLOWEST FIRST across all of them.
  Slowest-first is what makes the pruner safe on a single-player disk -- the
  padded stamp sorts by time so the entries past the quota are the ones you care
  least about -- and on a shared disk it becomes "delete the slowest PLAYER",
  who is the person whose runs matter most to them.  Twenty-five fast runs from
  one regular would evict every recording a newcomer had ever set.

  Putting `who` in the pattern makes the quota per player per leg per tag, which
  is the same rule the single-player case has always had, applied to the unit
  that now exists.  An empty `who` reproduces the old pattern exactly.
*/
void(entity e, float leg, string tag, string who, string keepme) SV_RecPrune =
{
	local float h, n, i, keep, kl;
	local string fn, stem;

	keep = cvar("rec_runs_keep");
	if (keep < 1)
		return;                 // 0 disables pruning entirely

	if (who != "")
		who = strcat(who, "_");

	h = search_begin(sprintf("%s*_%s%s.rec",
	                         FS_RunDir(mapname, e.run_t_track, leg),
	                         who, tag), FS_NAMESORT, TRUE);
	if (h < 0)
		return;

	kl = strlen(keepme);
	n  = search_getsize(h);
	for (i = keep; i < n; i = i + 1)
	{
		fn = search_getfilename(h, i);

		if (strlen(fn) >= kl)
			if (substring(fn, strlen(fn) - kl, kl) == keepme)
				continue;       // the run that was just written

		// Strip ".rec" and remove all three files of the set.  fremove on a
		// path that does not exist is a no-op, so the .view and .hid are
		// removed without asking whether they were ever written -- a run
		// recorded with rec_hid 0 has no .hid and that is not an error.
		stem = substring(fn, 0, strlen(fn) - 4);
		fremove(fn);
		fremove(strcat(stem, ".view"));
		fremove(strcat(stem, ".hid"));
		dprint(sprintf("timer: pruned %s\n", fn));
	}
	search_end(h);
};

/*
  Finish: append the trailer, write the buffer once, straight to its final name.

  No .part and no rename.  frename could not overwrite on Windows so the old
  path had to fremove the destination first, which meant a crash between the
  remove and the rename lost the previous recording as well as this one.  A
  single fopen of the final path cannot do that.
*/
void(entity e, float ticks, float tag, float flags) SV_RecClose =
{
	local float i, base, fh, stamp;
	local string dst, hdr, who;

	if (!SV_RecLive(e))
		return;
	SV_RecEndHold(e, "", "", 0);        // Patch 426: held again below, once it has ended

	/*
	  Patch 405: the counts off switch, on the OPERATOR's line -- `cmd timer`
	  prints it too, but nobody reads a player's console.  Printed here rather
	  than beside `board: submitting` because sv_progs.src:22 keeps sv_lobby.qc
	  depending on nothing in this project, and this is a sv_timer field.
	  Absence is never reported: a client older than Patch 376 is silent too.
	  This is cursor data arriving WITH no marker.  See SV_RecCounts.
	*/
	if (e.rec_mc_sup)
		print(sprintf("^1counts:^7 %s sent cursor data and no marker on %g"
		              " command(s) -- cl_prydoncursor suppresses Patch 376\n",
		              e.netname, e.rec_mc_sup));

	/*
	  v4: the reserved header line, finally answerable.

	  `flags` is a PARAMETER rather than read off the entity, for the reason
	  SV_RecLine already takes its timestamp as one: the call site is what knows
	  when the value is final.  SV_TimerFinish holds the flags it decided the tag
	  from, and reading e.run_t_flags here would be reading it a second time
	  through a different route -- which is how the tag and the flag get to
	  disagree about the same run.

	  TF_RECORDING and TF_FROZEN are masked out, exactly as the save file masks
	  them (sv_saveloc.qc): neither is a fact a stored run can assert.  The
	  recording is over by definition, and a frozen clock is a live condition.

	  bufstr_set on a line that is not the one we reserved would corrupt the
	  header silently -- a `map` line replaced by `flags 3` and the reader would
	  load the wrong map's zones -- so the line is READ BACK and checked first.
	  It costs one string compare per finished run.
	*/
	flags = flags - (flags & TF_RECORDING) - (flags & TF_FROZEN);
	if (!e.rec_rec_stream)
	if (e.rec_rec_flagline >= 0)
	if (e.rec_rec_flagline < e.rec_rec_lines)
	{
		hdr = bufstr_get(e.rec_rec_buf, e.rec_rec_flagline);
		if (substring(hdr, 0, 6) == "flags ")
			bufstr_set(e.rec_rec_buf, e.rec_rec_flagline, SV_RecFlagLine(flags));
		else
			dprint(sprintf("timer: rec header line %g is \"%s\", not flags -- left alone\n",
			               e.rec_rec_flagline, hdr));
	}

	/*
	  BUILD 80: %d AND NOT %g, HERE AND ON EVERY OTHER RECORD IN THIS FILE THAT
	  CARRIES A TICK COUNT OR A COUNTER.  This is the same defect build 76 fixed
	  in Lobby_SubmitRun, and it is worth reading that essay (sv_lobby.qc) beside
	  this one, because it ends with the sentence that let this survive:

	      "Any field HERE that can reach seven digits has the same flaw"

	  -- and `here` meant the wire body.  The fix went to the submission and
	  stopped there.  The .rec's own records have the identical flaw on thirteen
	  more lines, and they went unvisited for the ordinary reason: the thing that
	  broke was a byte count, so the repair was scoped to the thing that broke.

	  WHAT IT COSTS.  `%g` is six significant digits and then exponent form, so a
	  run past 1,000,000 ticks writes `end 1.00001e+06 ...`.  That is 2.78 hours
	  at 100 Hz, which is inside the range Lex has asked this format to cover.
	  The damage is not a parse error -- Python's float() reads `1.00001e+06`
	  perfectly happily -- it is that the value ARRIVES ROUNDED, to six digits,
	  in the field that states how long the run took.  A reader cannot tell a
	  rounded tick count from an exact one, which is the same shape as every
	  other bug in this tree's history: the wrong answer and the right answer are
	  the same bytes.

	  reccheck.py would catch it SIDEWAYS and only by luck -- `int(e_n)` against
	  len(samples) disagrees once the sample count rounds -- so the file would be
	  faulted for the wrong reason, on a different field, at a different
	  threshold from the one that actually went wrong.  Build 80 adds a direct
	  check there instead.

	  %d on a QC float is exact to 2^24 and truncates beyond, which is the same
	  ceiling FS_RECMAX_STREAM is sized against, deliberately: past that point
	  the counter feeding this line has stopped incrementing anyway, so there is
	  no format that could have told the truth about it.
	*/
	/*
	  BUILD 82: A FIFTH FIELD, APPENDED AND NEVER INSERTED, on the same rule the
	  sample stream's v3 columns took: a reader that splits this line and takes
	  four is still exactly right about all four.  It is the count of `in` records
	  in the body, and it is counted rather than asserted for the reason the
	  padding count beside it is -- see the grammar block.
	*/
	/*
	  BUILD 83: A SIXTH, BY THE SAME RULE, and it is what makes this a version
	  bump rather than a free addition.  It is the count of `warp` records -- and
	  it is the ONE field on this line whose absence changes what silence means.

	  A file with no `in` rows is a file from an engine with no mover counter, and
	  `instart` already says which.  A file with no `warp` records is either a run
	  that nothing teleported, a run whose recording was truncated, or a run
	  written by a build that could not record one -- and the first two are the
	  difference between a clean re-simulation and an unexplained 250-unit jump.
	  A counter plus a version number separates all three; neither alone does.
	*/
	/*
	  BUILD 85: THE CLOSING HORIZON.  Without it the last `in` row has no duration
	  -- N rows give N-1 spans, and the missing one is the move the finish is
	  latched on (E3: 1-2 ticks, a rank).  See the grammar block.

	  POST-FINISH VALUES, deliberately: SV_RecClose runs after PlayerPostThink has
	  latched the finish, so run_movetick has already counted the final move --
	  exactly the successor the last row lacks.  Gated as `instart` is, so the pair
	  is written under one condition and one without the other means truncated.
	*/
	// BUILD 87: a pin, physent or portal change on the FINISHING move has no
	// PreThink after it to be written from.
	SV_RecState(e);

	if (e.run_movetickrate > 0)
		SV_RecPut(e, sprintf("inend %d %.9g",
		                     e.run_movetick, e.run_movecarry));

	// BUILD 85: a seventh field, appended by the rule the fifth and sixth took --
	// the `ride` count.  It is the one whose loss costs most: a dropped sample is
	// one missing position, a dropped `ride` is a carrier a reader goes on holding
	// for every command after it, and that error does not heal.
	// BUILD 87 (v9): eighth to tenth, the three state tracks, by the same rule.
	SV_RecTrailer(e, ticks);

	if (e.run_t_slot >= 0)
	{
		base = e.run_t_slot * FS_MAXSPLITS;
		for (i = 1; i <= e.run_t_seg && i < FS_MAXSPLITS; i = i + 1)
			if (run_run_split[base + i] > 0)
				SV_RecPut(e, sprintf("split %d %d", i, run_run_split[base + i]));
	}

	/*
	  BUILD 23: pb and shadow go into the archive under their own time; last
	  keeps the fixed name it has always had.

	  The split is the whole reason the archive stays a sane size.  A pb happens
	  when you improve, and a shadow run is a deliberate practice attempt off a
	  save -- both are worth keeping and both are rare.  `last` is every other
	  attempt, which on a map you are grinding is forty an hour at a megabyte
	  each, and none of them is ever opened again.  Stamping that one would have
	  turned "keep the archive" into "fill the disk".

	  BUILD 45: ASKED THROUGH FS_TagArchived, which is where that question has
	  been answered since build 23 -- this line was a second spelling of it, and
	  adding RT_CHEAT is exactly the edit that would have updated one and not the
	  other.  The failure would have been silent and expensive: a cheated run
	  under a stamped name accumulates one file per lap and the pruner below
	  never sees it, because the prune is gated on this same `stamp`.
	*/
	stamp = -1;
	if (FS_TagArchived(tag))
		stamp = ticks;

	// BUILD 66: asked ONCE and carried, because the path below and the pruner's
	// two arguments are three uses of one answer -- and SV_RecWho hashes a GUID
	// to produce it, so asking three times is three sha256s per finish as well
	// as three chances for them to disagree.
	who = SV_RecWho(e);
	dst = SV_RecFinalPath(e, stamp, who, SV_RecTagName(tag));

	// Patch 360: a run that posted stages must not land under a fixed name its
	// next finish overwrites (last/cheat) -- it goes where an abandoned one does.
	// RT_NONE: no sidecar is written against it, and KeptLeaf names nothing.
	if (e.rec_rec_posts > 0)
	if (e.rec_rec_rid != "")
	if (!FS_TagArchived(tag))
	{
		dst = sprintf("data/evidence/%s/%s.rec", mapname, e.rec_rec_rid);
		tag = RT_NONE;
		print(sprintf("^5board:^7 kept %s (%g posted stage(s))\n", dst, e.rec_rec_posts));
	}

	/*
	  BUILD 66 -- THE STREAMED RUN IS ALREADY WRITTEN.  What is left is to
	  correct the header it reserved and move it to the name it earned.

	  THE TRAILER WENT IN FIRST, DELIBERATELY.  `end` and the splits were
	  appended above while the position was still the end of the file, so the
	  seek below is the LAST thing that touches the handle and nothing has to
	  seek back afterwards.  Doing it the other way round -- fix the header, then
	  append -- would need a second seek and would leave the file wrong if the
	  process died between the two.

	  SV_RecFlagLine is why this is safe: it reserved a fixed width at open, so
	  the correction writes exactly the bytes it is replacing.  A longer value
	  would otherwise eat the newline and the first character of `begin`.

	  fremove BEFORE frename, because FS_Rename is Sys_Rename underneath and
	  Windows' rename does not overwrite -- the note over this function records
	  that the pre-v3 recorder had to do the same.  The crash window it warns
	  about is real and is narrower here than it was: back then the destination
	  was the previous good recording, and now it can only be a file with this
	  exact tick count and tag already in it, i.e. a re-run of the same time.
	*/
	if (e.rec_rec_stream)
	{
		SV_RecCopyFlush(e);             // Patch 375: before the rename
		SV_RecGenReset(e);
		// BEFORE the fixup seek, because a one-argument fseek REPORTS the
		// position and the position is end-of-file only until the next line
		// moves it back to correct the header.  One read, no stat, and it is
		// the writer's own count rather than a second opinion about it.
		e.rec_rec_bytes = fseek(e.rec_rec_fh);
		if (e.rec_rec_flagofs >= 0)
		{
			fseek(e.rec_rec_fh, e.rec_rec_flagofs);
			fputs(e.rec_rec_fh, SV_RecFlagLine(flags));
		}
		fclose(e.rec_rec_fh);
		e.rec_rec_fh = -1;

		fremove(dst);
		if (frename(SV_RecPartPath(e), dst) != 0)
		{
			dprint(sprintf("timer: cannot rename %s to %s; the recording is "
			               "still in the part file\n", SV_RecPartPath(e), dst));
			e.rec_rec_bytes = -1;
		}
		else
		{
			e.rec_rec_saved = TRUE;
			dprint(sprintf("timer: streamed %s (%g samples, %g padding)\n",
			               dst, e.rec_rec_n, e.rec_rec_padn));
			if (stamp >= 0)
				SV_RecPrune(e, FS_LegOf(e.run_t_startseg, e.run_t_stagerun),
				            SV_RecTagName(tag), who,
				            FS_RunLeaf(stamp, who, SV_RecTagName(tag), "rec"));
		}

		e.rec_rec_stream = FALSE;
		e.rec_rec_flagofs = -1;
		e.rec_rec_lines = 0;
		e.run_t_flags = e.run_t_flags - (e.run_t_flags & TF_RECORDING);
		e.rec_rec_ticks = stamp;
		e.rec_rec_tag = tag;
		SV_RecEndHold(e, (flags & TF_NONCE && !e.rec_rec_rcpt) ? e.rec_rec_rid : "",
		              e.rec_rec_nonce, stamp);
		return;
	}

	fh = fopen(dst, FILE_WRITE);
	if (fh < 0)
		dprint(sprintf("timer: cannot open %s for writing\n", dst));
	else
	{
		// FOUR arguments, always.  The three-argument form of buf_writefile
		// computes its end index as `used - start` rather than `used`
		// (pr_bgcmd.c PF_buf_writefile), so asking for "from here to the end"
		// silently writes half a file whenever start is not 0.  Passing the
		// count explicitly avoids the bug rather than relying on start being 0.
		buf_writefile(fh, e.rec_rec_buf, 0, e.rec_rec_lines);
		// Patch 368: the size, as the stream reports it -- a lobby run is
		// buffered after a retry (SV_RecDestream), and its replay row said -1.
		// A buffered handle's one-argument fseek is the bytes written.
		e.rec_rec_bytes = fseek(fh);
		fclose(fh);
		dprint(sprintf("timer: wrote %s (%g samples, %g padding)\n",
		               dst, e.rec_rec_n, e.rec_rec_padn));
		// The buffered recorder writes straight to its final name -- no part
		// file, no rename -- so reaching here IS the file landing.
		e.rec_rec_saved = TRUE;

		// Only the archived classes accumulate; `last` is one file by
		// construction and has nothing to prune.  The basename is rebuilt here
		// rather than sliced off dst, because it is the same pieces the name was
		// made from and slicing would be a second way of spelling it.  BUILD 66:
		// through FS_RunLeaf, which is now the ONE place those pieces are joined
		// -- there are three of them and this sprintf knew about two.
		if (stamp >= 0)
			SV_RecPrune(e, FS_LegOf(e.run_t_startseg, e.run_t_stagerun),
			            SV_RecTagName(tag), who,
			            FS_RunLeaf(stamp, who, SV_RecTagName(tag), "rec"));
	}

	buf_del(e.rec_rec_buf);
	e.rec_rec_buf = -1;
	e.rec_rec_lines = 0;
	e.run_t_flags = e.run_t_flags - (e.run_t_flags & TF_RECORDING);

	// Told to the client LAST, and left standing until the next run opens: it
	// is the client's cue to write its angle sidecar beside this file, under
	// this same tag.  See STAT_FS_RUNTAG.
	e.rec_rec_ticks = stamp;
	e.rec_rec_tag = tag;
	SV_RecEndHold(e, (flags & TF_NONCE && !e.rec_rec_rcpt) ? e.rec_rec_rid : "",
	              e.rec_rec_nonce, stamp);
};

/*
  BUILD 66: THE NAME OF THE RECORDING THIS RUN KEPT, or "" if it kept none.

  The leaderboard submission carries this so surfd's replay ledger can point a
  board row at a file -- see Lobby_SubmitRun, which takes it as a parameter
  because sv_lobby.qc compiles first and cannot see anything in here.

  REBUILT THROUGH FS_RunLeaf, not remembered as a string, and not sliced off
  the path SV_RecClose built.  It is the same three pieces joined by the same
  function that named the file, which is the rule the pruner's basename already
  follows two functions up: a second way of spelling a name is a second thing
  to keep in step.

  THREE CONDITIONS, AND EACH OF THEM RULES OUT A DIFFERENT LIE:

    rec_rec_saved   the file is at that name right now.  A failed frename
                    leaves the bytes in data/parts/ and the close says so.
    ticks >= 0      the name is STAMPED, i.e. the tag is archived.  An
                    unstamped name -- `last`, `cheat`, the `lobby` stub -- is
                    a FIXED name whose bytes the player's own next finish
                    overwrites, so a durable index must never cite one.
    FS_TagArchived  asked directly as well, rather than trusted to follow from
                    the stamp.  They agree today because SV_RecClose derives
                    one from the other; that is exactly the kind of agreement
                    that a later tag quietly breaks, and the cost of asking is
                    a function call on the finish path.

  SV_RecWho IS ASKED A SECOND TIME HERE, which SV_RecClose's own comment warns
  about -- it hashes a GUID.  It is once more per FINISH, not per sample, and
  the alternative is carrying a zoned string through five reset sites for a
  value used once.  It is deterministic in netname and guid, and both are the
  same entity's, read in the same frame as the close: SV_TimerFinish calls
  SV_RecClose and Lobby_SubmitRun with no return between them.
*/
string(entity e) SV_RecKeptLeaf =
{
	if (!e.rec_rec_saved)
		return "";
	if (e.rec_rec_ticks < 0)
		return "";
	if (!FS_TagArchived(e.rec_rec_tag))
		return "";
	return FS_RunLeaf(e.rec_rec_ticks, SV_RecWho(e),
	                  SV_RecTagName(e.rec_rec_tag), "rec");
};

/*
===========================================================================
  Save states: the recorder's half.

  A save keeps the movement UP TO the save point, and loading it puts the
  recorder back at that point so the rest of the run appends on top -- so a run
  that is saved, failed twice and finished is ONE continuous file rather than
  three fragments or a file that starts halfway up a ramp.

  All three of these are about a MARK, which is just e.rec_rec_lines at the
  moment of the save.  The recorder was built for this: buf_writefile takes a
  count, so a prefix is a write, and bufstr_set overwrites by index, so a rewind
  is an assignment.  Nothing has to be copied or truncated.
===========================================================================
*/

/*
  Write the prefix.  Returns the mark, or 0 when there was nothing to keep --
  which is the ordinary case for a save taken before the clock starts, and is
  not an error: the padding ring will supply the approach when the run does
  begin.
*/
float(entity e, string path) SV_RecWritePrefix =
{
	local float fh;

	/*
	  BUILD 66: a streamed run has no prefix to write.  Returning 0 is the
	  ordinary "nothing to keep" answer this function already documents, so the
	  save is taken and simply carries no movement -- the run continues, the
	  clock is untouched, and the only loss is that a load will not stitch the
	  recording back together.

	  It is silent rather than warned about because on a lobby -- the only place
	  a run streams unless someone asked for it with rec_stream -- save points do
	  not exist at all (lobby_nosaveloc), so this branch has no caller there and a
	  warning would only ever fire at the person who set rec_stream on purpose.

	  [Patch 368: no longer true -- lobbies have had per-player saves since Patch
	  333.  A lobby save carries no movement and its load drops the recording (a
	  segmented run with no replay; measured, rt1cl.cfg).  A `retry` destreams
	  first (SV_RecDestream) and keeps it.]
	  [Patch 375: a stream's prefix is copied after the fact; SV_RecSnapshot.]
	*/
	if (e.rec_rec_stream)
		return SV_RecSnapshot(e, path);

	if (e.rec_rec_buf < 1 || e.rec_rec_lines <= 0)
		return 0;

	fh = fopen(path, FILE_WRITE);
	if (fh < 0)
	{
		dprint(sprintf("timer: cannot write %s\n", path));
		return 0;
	}

	// FOUR arguments, always -- see SV_RecClose.  Here it is not merely
	// defensive: a prefix is exactly the case where passing three would compute
	// `used - start` and write the wrong length.
	buf_writefile(fh, e.rec_rec_buf, 0, e.rec_rec_lines);
	fclose(fh);
	return e.rec_rec_lines;
};

// Patch 368: the stream read back into a buffer, counters kept, part file gone.
// A lobby `retry` needs it: the stream died at the map_restart and the run went
// on to rank clean with no replay (cfg/test/rt1cl.cfg).  Closed first: the stream
// goes through stdio, and an open part file read back 0 of 358 lines.  A failed
// read drops the recording, which is what every retry did before this.  Only
// the retry calls this -- it has the server to itself; every save doing it
// would buffer 32 players' runs.
float(entity e) SV_RecDestream =
{
	local float buf;

	if (!e.rec_rec_stream)
		return TRUE;
	SV_RecCopyFlush(e);                 // Patch 375
	fclose(e.rec_rec_fh);
	e.rec_rec_fh = -1;
	buf = buf_create_ex("string", 0);
	if (buf >= 1)
	if (buf_loadfile(SV_RecPartPath(e), buf))
	if (buf_getsize(buf) == e.rec_rec_lines)
	{
		fremove(SV_RecPartPath(e));
		e.rec_rec_flagofs = -1;
		e.rec_rec_stream = FALSE;
		e.rec_rec_buf = buf;
		return TRUE;
	}
	dprint(sprintf("timer: %s did not read back (%g of %g lines); recording dropped\n",
	               SV_RecPartPath(e), (buf >= 1) ? buf_getsize(buf) : -1, e.rec_rec_lines));
	if (buf >= 1)
		buf_del(buf);
	SV_RecDiscard(e);
	return FALSE;
};

/*
  Patch 375: A LOBBY SAVE-LOAD KEEPS ITS STREAM.  A save queues a copy of the
  part file's first <recbytes> bytes to its slot (SV_RecCopyStep) and states
  every counter a load needs, since nothing can rescan a stream.  A load of the
  same lineage cuts the stream back to those bytes (fsize with a new size);
  anything else rebuilds it from the slot's copy.  The file that results is the
  one the buffered path writes.

  The lineage is the serial plus rec_rec_gen: each warm rewind records the mark
  it cut to, and a save is warm only if no rewind since it cut below its mark --
  truncating to an earlier save destroys the bytes of every later one.  The
  buffered path takes the same test (before it, a later save loaded warm after
  an earlier one got the wrong branch as its prefix).
*/
// Into a save's state.txt, after SV_RecWritePrefix.
void(entity e, filestream f) SV_RecSaveKeys =
{
	fputs(f, sprintf("recgen %d\n", e.rec_rec_gen));
	if (e.rec_rec_rid != "")
		fputs(f, sprintf("recrid %s\n", e.rec_rec_rid));
	if (rec_snap_bytes <= 0)
		return;
	fputs(f, sprintf("recbytes %s\n", itos(rec_snap_bytes)));
	fputs(f, sprintf("recstream %d %d %d\n", e.rec_rec_ver, e.rec_rec_flagofs, e.rec_rec_sesspend));
	fputs(f, sprintf("recrows %d %d %d %d\n", e.rec_rec_in, e.rec_rec_pk, e.rec_rec_warp, e.rec_rec_ride));
	fputs(f, sprintf("recstate %d %d %d %d\n", e.rec_rec_pm, e.rec_rec_pe, e.rec_rec_portal, e.rec_rec_pinned));
	fputs(f, sprintf("recsess %d %d\n", e.rec_rec_pauses, e.rec_rec_sess));
	if (e.rec_rec_inmt >= 0)
		fputs(f, sprintf("reclast %d %.9g\n", e.rec_rec_inmt, e.rec_rec_incy));
	rec_snap_bytes = 0;
};

void() SV_RecKeysReset =
{
	rs_bytes = 0;
	rs_gen = -1;                        // a save before Patch 375: no lineage, so cold
	if (rs_rid != "")
		strunzone(rs_rid);
	rs_rid = "";
	rs_ver = 9;
	rs_flagofs = -1;
	rs_pend = rs_in = rs_pk = rs_warp = rs_ride = rs_pm = rs_pe = rs_portal = 0;
	rs_pinned = rs_pauses = rs_sess = rs_incy = 0;
	rs_inmt = -1;
};

// One state.txt line, already tokenized; TRUE if it was ours.
float(string k, float n) SV_RecKeyRead =
{
	if (k == "recgen")    { rs_gen = stof(argv(1)); return TRUE; }
	if (k == "recrid")    { if (rs_rid != "") strunzone(rs_rid); rs_rid = strzone(argv(1)); return TRUE; }
	if (k == "recbytes")  { rs_bytes = stoi(argv(1)); return TRUE; }
	if (k == "recstream" && n >= 4)
		{ rs_ver = stof(argv(1)); rs_flagofs = stof(argv(2)); rs_pend = stof(argv(3)); return TRUE; }
	if (k == "recrows" && n >= 5)
		{ rs_in = stof(argv(1)); rs_pk = stof(argv(2)); rs_warp = stof(argv(3)); rs_ride = stof(argv(4)); return TRUE; }
	if (k == "recstate" && n >= 5)
		{ rs_pm = stof(argv(1)); rs_pe = stof(argv(2)); rs_portal = stof(argv(3)); rs_pinned = stof(argv(4)); return TRUE; }
	if (k == "recsess" && n >= 3)
		{ rs_pauses = stof(argv(1)); rs_sess = stof(argv(2)); return TRUE; }
	if (k == "reclast" && n >= 3)
		{ rs_inmt = stof(argv(1)); rs_incy = stof(argv(2)); return TRUE; }
	return FALSE;
};

// SV_RecRecount for a stream: the counters the save stated, the latches cleared.
void(entity e, float mark, float samples, float padn, float cps) SV_RecRestore =
{
	e.rec_rec_lines = mark;
	e.rec_rec_n     = samples;
	e.rec_rec_padn  = padn;
	e.rec_rec_cp    = cps;
	e.rec_rec_full  = FALSE;
	e.rec_rec_in = rs_in;       e.rec_rec_warp = rs_warp;     e.rec_rec_ride = rs_ride;
	e.rec_rec_pm = rs_pm;       e.rec_rec_pe = rs_pe;         e.rec_rec_portal = rs_portal;
	e.rec_rec_pinned = rs_pinned;
	e.rec_rec_pauses = rs_pauses;
	e.rec_rec_sess = rs_sess;
	if (e.rec_rec_pk < rs_pk)
		e.rec_rec_pk = rs_pk;
	e.rec_rec_sesspend = rs_pend;
	e.rec_rec_inmt = rs_inmt;
	e.rec_rec_incy = rs_incy;
	e.rec_rec_bvset = FALSE;
	e.rec_rec_pcset = FALSE;
	e.rec_rec_epoch = 0;
	e.rec_rec_portalx = e.run_portalx;
	e.rec_rec_lastbc = e.run_boardcount;
	e.rec_rec_flagline = -1;
	e.rec_rec_leg = e.run_t_track * 100 + FS_LegOf(e.run_t_startseg, e.run_t_stagerun) + 1;
	e.run_t_flags = e.run_t_flags | TF_RECORDING;
};

float(entity e, string path, float mark, float serial,
      float samples, float padn, float cps, int b) SV_RecRewindStream =
{
	local int ofs, n;
	local float fh;
	local string why;

	if (!checkbuiltin(fappendrange))
		return FALSE;
	if (e.run_ms_phase)                 // the resume's copy owns the part file (SV_SaveLocLoad refuses too)
		return FALSE;
	SV_RecCopyFlush(e);

	// WARM: this save's lineage is the stream in hand -- cut it back.
	why = "no stream";
	if (e.rec_rec_stream && e.rec_rec_fh >= 0)
	{
		why = "another run";
		if (e.rec_rec_serial == serial)
		{
			why = "a later branch";
			if (e.rec_rec_lines >= mark && SV_RecGenOK(e, mark) && fsize(e.rec_rec_fh) >= b)
			{
				why = "truncate failed";
				if (fsize(e.rec_rec_fh, b) == b)
				{
					SV_RecRestore(e, mark, samples, padn, cps);
					SV_RecGenPush(e, mark);
					SV_RecNoncePublish(e, FALSE);   // Patch 416: same file
					dprint(sprintf("timer: load warm, cut to %s bytes\n", itos(b)));
					return TRUE;
				}
			}
		}
	}
	dprint(sprintf("timer: load cold (%s): %s bytes from %s\n", why, itos(b), path));

	// COLD: a new stream from the slot's copy, line 0 rewritten to 10 for the
	// `pause` the caller writes.  The old recording goes as the buffered path's
	// does -- dropped, its runid kept.
	if (!SV_RecEnabled() || !SV_RecStreams())
		return FALSE;
	if (e.rec_rec_stream)
	{
		if (e.rec_rec_fh >= 0)
			fclose(e.rec_rec_fh);
		fremove(SV_RecPartPath(e));
	}
	else if (e.rec_rec_buf >= 1)
		buf_del(e.rec_rec_buf);
	e.rec_rec_fh = -1;
	e.rec_rec_buf = -1;
	e.rec_rec_stream = FALSE;

	e.rec_rec_partlob = Lobby_Active() ? 1 : 2;
	fh = fopen(SV_RecPartPath(e), FS_FILE_WRITESTREAM);
	if (fh < 0)
		return FALSE;
	ofs = (rs_ver == 10) ? 15 : 14;     // "FTESURF-REC 9\n" or "...10\n"
	fputs(fh, "FTESURF-REC 10\n");
	n = fappendrange(fh, path, ofs, b - ofs + 1);   // one over: the copy must END at b
	if (n != b - ofs)
	{
		dprint(sprintf("timer: %s gave %s of %s bytes; recording dropped\n",
		               path, itos(n), itos(b - ofs)));
		fclose(fh);
		fremove(SV_RecPartPath(e));
		return FALSE;
	}
	e.rec_rec_fh = fh;
	e.rec_rec_stream = TRUE;
	e.rec_rec_ver = 10;
	e.rec_rec_flagofs = (rs_flagofs >= 0) ? rs_flagofs + 15 - ofs : -1;
	SV_RecRestore(e, mark, samples, padn, cps);
	SV_RecGenReset(e);
	e.rec_rec_serial = SV_RecNextSerial();
	SV_RecNoncePublish(e, TRUE);        // Patch 416: a streamed cold load keeps none
	rec_rewind_cold = TRUE;
	return TRUE;
};

/*
  BUILD 87: after a rewind the body is the prefix up to the mark, so every count
  a trailer states -- and v9's <row> -- must be recounted FROM IT, not carried:
  the rows past the mark are gone.  (v6-v8 carried rec_rec_in across a rewind
  and over-counted <inputs> on every resumed file.)  The change sentinels are
  cleared so the resumed stretch opens with floor records.
*/
void(entity e) SV_RecRecount =
{
	local float i, c, last, pend, pk;
	local string l;

	e.rec_rec_in = e.rec_rec_warp = e.rec_rec_ride = 0;
	e.rec_rec_pm = e.rec_rec_pe = e.rec_rec_portal = 0;
	e.rec_rec_pauses = e.rec_rec_sess = e.rec_rec_pinned = 0;     // Patch 364
	last = -1;
	pend = FALSE;
	for (i = 0; i < e.rec_rec_lines; i = i + 1)
	{
		l = bufstr_get(e.rec_rec_buf, i);
		c = str2chr(l, 0);
		if (c == 105 && substring(l, 0, 3) == "in ")              // i
		{
			e.rec_rec_in = e.rec_rec_in + 1;
			last = i;
		}
		else if (c == 115 && substring(l, 0, 8) == "session ")    // s
		{
			e.rec_rec_sess = e.rec_rec_sess + 1;
			pend = FALSE;
		}
		else if (c == 119 && substring(l, 0, 5) == "warp ")       // w
			e.rec_rec_warp = e.rec_rec_warp + 1;
		else if (c == 114 && substring(l, 0, 5) == "ride ")       // r
			e.rec_rec_ride = e.rec_rec_ride + 1;
		else if (c == 112)                                        // p
		{
			if (substring(l, 0, 3) == "pm ")
				e.rec_rec_pm = e.rec_rec_pm + 1;
			else if (substring(l, 0, 3) == "pe ")
				e.rec_rec_pe = e.rec_rec_pe + 1;
			else if (substring(l, 0, 7) == "portal ")
				e.rec_rec_portal = e.rec_rec_portal + 1;
			else if (substring(l, 0, 6) == "pause ")
			{
				e.rec_rec_pauses = e.rec_rec_pauses + 1;
				pend = TRUE;
			}
			else if (substring(l, 0, 6) == "pmpin ")
				e.rec_rec_pinned = TRUE;
		}
	}
	e.rec_rec_bvset = FALSE;
	e.rec_rec_pcset = FALSE;
	e.rec_rec_epoch = 0;
	e.rec_rec_portalx = e.run_portalx;

	// Patch 364: a pause the prefix left open is still owed its session, and the
	// packet ordinal runs on past the prefix's last row (a retry's edict starts at 0).
	e.rec_rec_sesspend = 0;
	if (pend)
		e.rec_rec_sesspend = 1 + e.rec_rec_pinned;
	if (last >= 0)
	{
		tokenize(bufstr_get(e.rec_rec_buf, last));
		pk = stof(argv(1)) + 1;
		if (e.rec_rec_pk < pk)
			e.rec_rec_pk = pk;
	}
	// The marker describes the file: v10 exactly when a `pause` is in it.
	l = bufstr_get(e.rec_rec_buf, 0);
	if (e.rec_rec_pauses > 0 && l == "FTESURF-REC 9")
		bufstr_set(e.rec_rec_buf, 0, "FTESURF-REC 10");
	if (e.rec_rec_pauses == 0 && l == "FTESURF-REC 10")
		bufstr_set(e.rec_rec_buf, 0, "FTESURF-REC 9");
};

/*
  Patch 364: a cold rewind (a retry, or a load that read its prefix off disk)
  parks the trace.  The mover counter under it may have restarted and the state
  was imposed, not simulated, so the rows go on in a new session (SV_RecSession).
  <mt> <carry> are the prefix's last `in` row, copied as written -- or `instart`'s
  <mt> and 0 when the save landed before the first row.  A prefix that ends inside
  a pause (saved before its session) is already parked: SV_RecRecount re-armed it.
*/
void(entity e, string why, float ticks) SV_RecPause =
{
	local float i, was;
	local string l, mt, cy;

	// Patch 375: a stream rebuilt from a save; its line 0 is already 10.
	if (e.rec_rec_stream && e.rec_rec_fh >= 0 && !e.rec_rec_sesspend && e.rec_rec_inmt >= 0)
	{
		was = e.rec_rec_lines;
		SV_RecPut(e, sprintf("pause %d %.9g %d %s", e.rec_rec_inmt, e.rec_rec_incy, ticks, why));
		if (e.rec_rec_lines == was)
			return;
		e.rec_rec_pauses = e.rec_rec_pauses + 1;
		e.rec_rec_sesspend = 1 + e.rec_rec_pinned;
		return;
	}
	if (e.rec_rec_buf < 1)
		return;
	if (e.rec_rec_sesspend)
		return;
	mt = cy = "";
	for (i = e.rec_rec_lines - 1; i >= 0; i = i - 1)
	{
		l = bufstr_get(e.rec_rec_buf, i);
		if (substring(l, 0, 3) == "in ")
		{
			tokenize(l);
			mt = argv(2);
			cy = argv(3);
			break;
		}
		if (substring(l, 0, 8) == "instart ")
		{
			tokenize(l);
			mt = argv(1);
			cy = "0";
			break;
		}
	}
	if (mt == "")
		return;                         // no counter, no trace: nothing to park
	was = e.rec_rec_lines;
	SV_RecPut(e, sprintf("pause %s %s %d %s", mt, cy, ticks, why));
	if (e.rec_rec_lines == was)
		return;
	e.rec_rec_pauses = e.rec_rec_pauses + 1;
	e.rec_rec_sesspend = 1 + e.rec_rec_pinned;
	if (bufstr_get(e.rec_rec_buf, 0) == "FTESURF-REC 9")
		bufstr_set(e.rec_rec_buf, 0, "FTESURF-REC 10");
};

// Multi-Session: park the trace at the counter as it stands after the last move
// (the closing horizon, as `inend`).  SV_MsApply's session answers it.  A stream's
// line 0 is rewritten by the resume's copy.
void(entity e, string why, float ticks) SV_RecParkLine =
{
	local float was;

	if (!SV_RecLive(e))
		return;
	SV_RecState(e);
	was = e.rec_rec_lines;
	SV_RecPut(e, sprintf("pause %d %.9g %d %s", e.run_movetick, e.run_movecarry, ticks, why));
	if (e.rec_rec_lines == was)
		return;
	e.rec_rec_pauses = e.rec_rec_pauses + 1;
	if (!e.rec_rec_stream)
	if (bufstr_get(e.rec_rec_buf, 0) == "FTESURF-REC 9")
		bufstr_set(e.rec_rec_buf, 0, "FTESURF-REC 10");
};

/*
  Put the recorder back at `mark`.  Two paths, and which one runs is decided by
  whether the buffer in hand is still the same run.

  WARM -- same run, and it has at least `mark` lines: assign.  The lines past the
  mark are stale but unreachable, because every write goes through bufstr_set by
  index and every read passes an explicit count.  No file is touched at all,
  which matters because this is the path that runs thirty times while you are
  learning one section.

  COLD -- a different run, or no buffer: read the prefix back off disk.  This is
  what makes a save survive a map change, a void, and a restart of the game.
  buf_loadfile appends line by line into a fresh buffer, so it round-trips
  exactly what buf_writefile wrote.

  Returns TRUE if the recorder is now at the mark.
*/
float(entity e, string path, float mark, float serial,
      float samples, float padn, float cps) SV_RecRewind =
{
	local float buf;
	local int sb;

	sb = rs_bytes;                      // Patch 375: consumed by whichever load asked
	rs_bytes = 0;
	rec_rewind_cold = FALSE;
	if (mark <= 0)
		return FALSE;
	if (sb > 0)                         // a save with a stream copy
		return SV_RecRewindStream(e, path, mark, serial, samples, padn, cps, sb);

	// BUILD 66: a stream cannot be rewound -- the lines past the mark are
	// already on disk and nothing indexes them.  The run carries on recording
	// from where it is; it just does not rejoin the saved prefix.  See
	// SV_RecWritePrefix for why this is quiet.
	if (e.rec_rec_stream)
		return FALSE;

	if (e.rec_rec_buf >= 1)
	if (e.rec_rec_serial == serial)
	if (e.rec_rec_lines >= mark)
	if (SV_RecGenOK(e, mark))           // Patch 375: no rewind since cut below it
	{
		SV_RecGenPush(e, mark);
		e.rec_rec_lines = mark;
		e.rec_rec_n     = samples;
		e.rec_rec_padn  = padn;
		e.rec_rec_cp    = cps;
		e.rec_rec_full  = FALSE;     // room again, so the cap may be re-reported
		e.rec_rec_leg   = e.run_t_track * 100 + FS_LegOf(e.run_t_startseg, e.run_t_stagerun) + 1;
		e.run_t_flags   = e.run_t_flags | TF_RECORDING;
		SV_RecRecount(e);            // build 87
		SV_RecNoncePublish(e, FALSE);   // Patch 416: same file, same nonce, tell it again
		return TRUE;
	}

	if (!SV_RecEnabled())
		return FALSE;

	buf = buf_create_ex("string", 0);
	if (buf < 1)
	{
		dprint("timer: buf_create failed; this run is not being recorded\n");
		return FALSE;
	}

	if (!buf_loadfile(path, buf))
	{
		// No prefix on disk.  A save made with rec_enable 0, or a hand-deleted
		// file.  Drop the buffer rather than starting a recording whose first
		// line is the middle of a run.
		buf_del(buf);
		return FALSE;
	}

	// Whatever came back is the truth about the file; `mark` was only the
	// writer's claim about it, and the two disagreeing means the file was
	// touched underneath us.  Trust the buffer.
	if (e.rec_rec_buf >= 1)
		buf_del(e.rec_rec_buf);

	e.rec_rec_buf   = buf;
	e.rec_rec_lines = buf_getsize(buf);
	e.rec_rec_n     = samples;
	e.rec_rec_padn  = padn;
	e.rec_rec_cp    = cps;
	e.rec_rec_full  = FALSE;
	SV_RecRecount(e);                // build 87

	e.rec_rec_serial = SV_RecNextSerial();
	SV_RecGenReset(e);

	/*
	  WHICH LEG this buffer is now for, so the client names its sidecar after the
	  run we have been put back into rather than after the one we left.

	  Only the cold path needs it -- the warm path is by definition the same run
	  and already has the right value -- but it is set on both, because "the leg
	  is whatever the timer currently says" is a rule that cannot go stale, and
	  "it was already right" is one that can.

	  rec_rec_tag is deliberately NOT touched.  It is the client's cue that a run
	  FINISHED, and clearing it here would race a client that has not rendered a
	  frame since a finish -- the same race SV_RecDiscard documents, and for the
	  same reason it does not clear the tag unconditionally either.

	  BUILD 57: the LEG, through FS_LegOf.  SV_SaveApplyState puts run_t_stagerun
	  back before it calls this, so a restored stage-1 run names its sidecar
	  stage_1 rather than main.
	*/
	e.rec_rec_leg = e.run_t_track * 100 + FS_LegOf(e.run_t_startseg, e.run_t_stagerun) + 1;

	/*
	  v4: find the reserved `flags` line again.

	  The COLD path is the one that needs this and it is easy to miss: a resumed
	  run in a fresh session never ran SV_RecOpen, so e.rec_rec_flagline is
	  whatever the edict was recycled with -- almost always 0, which is the magic
	  line.  SV_RecClose's read-back check would then refuse and the finished
	  shadow run would ship a header saying `flags 0` when it was practice, which
	  is the one thing the leaderboard filter reads.

	  Scanned rather than assumed, and bounded by `begin` rather than by a line
	  count, because the header's own rule is that its keys are order-free.  -1
	  means "this file has no such line" -- a v3 prefix resumed under a v4 build,
	  which is a real case for anyone with a save on disk right now -- and
	  SV_RecClose leaves the header alone rather than inventing one.

	  The board counter is reseeded here for the same reason SV_RecOpen seeds it.
	*/
	e.rec_rec_flagline = -1;
	{
		local float i;
		local string l;
		for (i = 0; i < e.rec_rec_lines && i < 64; i = i + 1)
		{
			l = bufstr_get(buf, i);
			if (l == "begin")
				break;
			if (substring(l, 0, 6) == "flags ")
			{
				e.rec_rec_flagline = i;
				break;
			}
		}
	}
	e.rec_rec_lastbc = e.run_boardcount;

	e.run_t_flags = e.run_t_flags | TF_RECORDING;
	// Patch 416: a different lineage -- adopt the nonce this buffer's header
	// states, because it is no longer the one we drew.  See SV_RecNoncePublish.
	SV_RecNoncePublish(e, TRUE);
	rec_rewind_cold = TRUE;         // Patch 364: the caller writes the `pause`
	return TRUE;
};

/*
  v4: emit a `board` record if the engine's counter moved since the last sample.

  CALLED BEFORE THE SAMPLE, not after, and the ordering is what a reader depends
  on.  The board is the thing that happened DURING the move this sample reports
  the end of, so the pre-clip velocity it carries belongs with the state going in
  -- a reader walking the file in order must see the board before it sees the
  post-clip sample, exactly as the client's Board_Frame reads BOARDVEL on the
  same frame it first sees the count move.

  Not written for the padding ring.  The ring stores the approach and a board out
  there belongs to no run: the segment column clears on the TS_RUNNING edge
  anyway, so a pre-start board record would describe a list that is about to be
  thrown away.  That is also why the ring has no board columns to store.
*/
void(entity e, float t) SV_RecBoard =
{
	if (!SV_RecLive(e))
		return;
	if (e.run_boardcount == e.rec_rec_lastbc)
		return;

	e.rec_rec_lastbc = e.run_boardcount;

	// A count that moved with no plane behind it is not a board -- it is the
	// counter being reset by a map change or a respawn.  Writing it would hand
	// the reader a zero normal to grade against.
	if (e.run_boardnormal == '0 0 0')
		return;

	// TWO sprintfs: nine values against the eight-argument varargs cap.
	SV_RecPut(e, strcat(sprintf("board %.4f %d %.4f %.4f %.4f ",
	                            t, e.run_boardcount,
	                            e.run_boardnormal_x, e.run_boardnormal_y,
	                            e.run_boardnormal_z),
	                    sprintf("%.2f %.2f %.2f",
	                            e.run_boardvelocity_x, e.run_boardvelocity_y,
	                            e.run_boardvelocity_z)));
};

/*
==============================================================================
  BUILD 83: STATE IMPOSED ON A PLAYER FROM OUTSIDE THE MOVER.

  This record exists because experiment E3 measured its absence.  pm_recsim
  (engine Patch 327) replayed a real recording's input trace back through the
  mover that produced it and reproduced 1307 of 1324 packets to the file's own
  printing floor -- and TEN of the fifteen that did not were trigger_teleport:
  ~250 units of position with velocity carried through exactly, landing on the
  run's own start coordinates.

      THE RECORDING RECORDED THE CONSEQUENCE AND NEVER THE EVENT.

  So an open-loop re-simulation died at the first teleport and everything after
  it was noise, and a verifier looking at the file could not tell a legitimate
  stage teleport from a cheat that simply moved the player.  Those are the same
  bytes.  This record is the event.

  WRITTEN BY THE THING THAT DID IT, which is the whole design and not an
  implementation detail.  A record synthesised by watching for a discontinuity
  would be exactly as blind as the sample stream already is -- it would see a
  jump and still not know what caused it, which is the question.  Every call
  site is inside the handler that performed the imposition and names itself.

  WHAT IT COVERS, stated as a boundary rather than a list: every DIRECT WRITE of
  a player's origin or velocity, outside the mover, by a map entity.  That is
  the three teleport classes, func_bhop's teleport, trigger_setspeed, and
  trigger_push's once-pad arm.

  WHAT IT DOES NOT COVER, and this is a measured gap rather than an oversight.
  trigger_push's CONTINUOUS arm -- 4,940 instances across 46.9% of the library --
  writes no velocity at all.  It writes .run_basevel, a carrier the engine folds
  into pmove.basevelocity, and the cash-out happens a whole command later in
  SV_BaseVelocityFrame, in PreThink, still outside the mover.  So "velocity was
  written" catches the once-pad and misses the common case entirely, and a
  record placed at the carrier would be recording an intention rather than an
  event.  That family wants its own measurement, the way this one got E3's, and
  guessing at its shape now would be the thing this record was built to stop.
  It is named in the plan as the next gap and it is not claimed here.

  AND THE FIRST TELEPORT OF A RUN MAY LEGITIMATELY HAVE NO RECORD.  SV_RecOpen
  is called from SV_TimerStart, so a trigger sitting in or beside the start box
  fires before the recorder exists.  SV_RecPut discards it silently -- that is
  the ordinary behaviour of a closed recorder and not a fault -- and a reader
  must not take a missing record as tampering.  What a reader CAN rely on is the
  count in the trailer, which is why one is written.

  NOT GATED ON run_teleport_warp.  That cvar decides a BEHAVIOUR (whether the
  swept zone segment is reset across a teleport) and sharing its gate would mean
  a bisection switch silently turned off the evidence too.  A record that exists
  to prove an event happened may not share a gate with a flag that decides what
  happens.

  GATED ON THE MOVER COUNTER, on the `instart` precedent.  Against an engine
  older than Patch 325 there is no run_movetick, so the file carries no input
  trace, so nothing re-simulates it and <mt> would be a constant 0 -- a false
  stamp rather than a missing one.  No trace, no events.
==============================================================================
*/
void(entity e, string kind) SV_RecWarp =
{
	float was;

	if (!SV_RecLive(e))
		return;
	if (e.run_movetickrate <= 0)
		return;
	SV_RecSession(e);       // Patch 364: a touch on the first move after a retry

	was = e.rec_rec_lines;

	/*
	  <mt> AND NOT `time`, AND NOT <pk> ALONE.  Touches run per USERCMD, inside
	  SV_RunCmd after the move; the sample and the packet ordinal are per PACKET,
	  because PlayerPostThink is called from SV_PostRunCmd outside the usercmd
	  loop.  So three teleports inside one packet share one <pk> and one sample
	  and can only be separated by the mover's own counter -- which the engine
	  has already advanced for this command (sv_user.c writes movetickcount
	  before the touch loop runs), so the stamp here is exact rather than
	  approximate.  <pk> is written beside it so a reader can still tie the event
	  to the sample that follows it.

	  The `in` row for the same usercmd carries the PRE-move counter, so an event
	  record sits one tick above its own input row by construction.  Said out
	  loud because a reader that expects them to match will "fix" the wrong one.

	  TWO sprintfs: ten values against the eight-argument varargs cap, which
	  fteqcc silently truncates rather than refusing to compile.
	*/
	/*
	  BUILD 87 (v9): <row>, the `in` row whose move this followed -- the binding a
	  replay uses, because <mt> repeats across a zero-tick move.  Vectors at %.9g
	  so the state is the state, not its %.2f print, and <fl> 1 = FL_ONGROUND
	  after the imposition (setspeed leaves it, the others clear it).
	*/
	SV_RecPut(e, sprintf("warp %d %d %d %s %.9v %.9v %d",
	                     e.rec_rec_pk, e.run_movetick, e.rec_rec_in - 1, kind,
	                     e.origin, e.velocity, (e.flags & FL_ONGROUND) ? 1 : 0));

	/*
	  COUNTED BY WHETHER A LINE ACTUALLY LANDED, on SV_TimerInFrame's argument and
	  by the same mechanism.  Both of SV_RecPut's failure modes are silent -- a
	  closed recorder and the line cap -- so an unconditional increment would make
	  the trailer's <warps> a count of records we MEANT to write, which is the
	  assertion this field exists instead of.  SV_RecPut returns void, so
	  rec_rec_lines moving is the only handle on it.

	  This matters more here than it does for <inputs>.  A missing input row is
	  one move of a thousand; a missing warp record is a 250-unit discontinuity
	  with nothing in the file to explain it -- which is precisely the shape a
	  verifier would have to read as tampering.  An exact count is what lets it
	  say "truncated" instead.
	*/
	if (e.rec_rec_lines != was)
		e.rec_rec_warp = e.rec_rec_warp + 1;
};

/*
==============================================================================
  BUILD 85: THE VELOCITY CARRIER.  Format and E5's numbers are in the grammar
  block; what belongs here is the decision and the two gates.

  A SPAN, NOT AN EVENT, and it took an experiment.  Build 83 declined to guess
  ("a record placed at the carrier would be recording an intention rather than an
  event") and named a measurement as the price.  E5 paid it and neither option
  won: an event record is NECESSARY BUT NOT SUFFICIENT, because a ride has a
  DURATION.  The intention problem is solved by WHERE this is called from --
  SV_BaseVelocityFrame's .run_basevelocity assignment is the mover receiving the
  carrier, so the record is written by the thing that did it, build 83's rule
  kept rather than bent.

  GATED ON THE MOVER COUNTER like `warp` and `instart`: no counter, no trace, and
  <mt> would be a constant 0 -- a false stamp rather than a missing one.

  NOT GATED ON run_t_frzon, which is where it parts company with the `in` rows.
  That gate is about VOLUME (a ten-second park is 660 rows); this writer emits on
  CHANGE, so a freeze costs nothing -- and the carrier DOES change across one.
  Suppressing it would leave the last `arm` standing as the reader's answer for
  the rest of the run.  A gate that makes silence mean the wrong thing may not be
  shared with one that only makes it mean less.
==============================================================================
*/
void(entity e, string what, vector bv) SV_RecRide =
{
	float was;

	if (!SV_RecLive(e))
		return;
	if (e.run_movetickrate <= 0)
		return;

	was = e.rec_rec_lines;


	/*
	  <mt> IS PRE-MOVE and matches the `in` row this sits above -- the opposite of
	  `warp`, which is written from a touch AFTER the move.  Each stamps the
	  counter where it is written; both conventions are in the grammar block.

	  ONE sprintf: six values, inside the 8-arg varargs cap.  %.2f like the sample
	  stream's velocity, not the `in` row's %.4f angles -- there is no wire quantum
	  here to justify four.
	*/
	// BUILD 87 (v9): %.9g -- a push along a diagonal is not a %.2f number.
	SV_RecPut(e, sprintf("ride %d %d %s %.9v",
	                     e.rec_rec_pk, e.run_movetick, what, bv));

	// Counted by whether a line landed, on SV_RecWarp's argument.
	if (e.rec_rec_lines != was)
		e.rec_rec_ride = e.rec_rec_ride + 1;
};

/*
  The carrier handed to the mover this command.  Called EVERY command by
  SV_BaseVelocityFrame and writing almost none of them.

  THE TEST IS AGAINST WHAT THE FILE SAYS, not against last command's carrier.
  SV_RecPut refuses past the line cap silently; testing the carrier would then see
  "no change" forever after and the file would assert a value it never wrote.
  rec_rec_bv moves only when a line landed, so a refusal is retried next command.

  THE SENTINEL MAKES THE FIRST CALL UNCONDITIONAL -- the floor record.  A run may
  begin mid-ride, so "zero at `begin`" is not a default a reader may take.
*/
void(entity e, vector bv) SV_RecRideArm =
{
	float was;

	if (e.rec_rec_bvset && bv == e.rec_rec_bv)
		return;

	was = e.rec_rec_ride;
	SV_RecRide(e, "arm", bv);

	// Only once the line landed: a cap refusal must leave the recorder still
	// owing this value, not believing it has stated it.
	if (e.rec_rec_ride != was)
	{
		e.rec_rec_bv = bv;
		e.rec_rec_bvset = TRUE;
	}
};

/*
  The cash-out: this carrier became real velocity, in PreThink, outside the mover.
  Unconditional -- an event, not a state.  The `arm 0 0 0` that always follows is
  written by the ordinary change test one call later, not derived; see the grammar
  block for why.
*/
void(entity e, vector bv) SV_RecRidePay =
{
	SV_RecRide(e, "pay", bv);
};

/*
  The always-on ring.  One entry per post-move sample whether or not anything
  is being timed, so the padding is already there when the start zone fires.

  BUILD 76: THE STAMP IS SV_ClockSec AND THE RING COST NOTHING TO MOVE.

  The migration's estimate had this as a new QC array -- a parallel ring of tick
  counts beside the existing seconds ring -- and that would have been the single
  most expensive line of the whole change: measured in this tree, four extra
  recorder rings once cost 563 KB of progs for 68 KB of data, because fteqcc
  emits array indexing as a per-element dispatch.  It is not needed.  The stamp
  was always a number subtracted from the run's origin at flush; what it MEANS is
  decided by which clock the origin is on, and both are seconds.  So the same
  float in the same slot carries the new unit, and the whole change is the
  right-hand side of one assignment plus the matching subtraction in SV_RecOpen.

  THE TWO SITES MUST AGREE AND THEY CANNOT BE CHECKED SEPARATELY.  A pad stamped
  in one unit and flushed against an origin in the other produces a recording
  whose first twenty samples are seconds-since-map-load before t=0 -- large,
  negative and plausible, which is the worst kind of wrong.  SV_ClockSec's
  selector is keyed on the ENGINE field rather than on run_t_clock precisely so
  this pair cannot straddle a run's latch; the essay there has the argument.
*/
void(entity e) SV_RecPad =
{
	local float s;

	s = SV_RecPadBase(e);
	if (s < 0)
		return;

	s = s + e.rec_pad_head;
	rec_pad_org[s] = e.origin;
	rec_pad_vel[s] = e.velocity;
	rec_pad_mv [s] = e.movement;
	rec_pad_t  [s] = SV_ClockSec(e);
	rec_pad_pit[s] = e.v_angle_x;
	rec_pad_yaw[s] = e.v_angle_y;
	rec_pad_fl [s] = SV_RecFlags(e);
	rec_pad_key[s] = SV_RecKeys(e);
	rec_pad_norm[s] = SV_RecNormal(e);

	e.rec_pad_head = (e.rec_pad_head + 1) % FS_RECPAD;
	if (e.rec_pad_len < FS_RECPAD)
		e.rec_pad_len = e.rec_pad_len + 1;
};

/*
===========================================================================
  Personal bests

  One small text file per map, rewritten whole on a new best.  Deliberately
  not one file per leg: the map browser (build 10) wants "have I set a time
  here, and what was it" answerable with a single fopen per map, and 1308
  maps x 12 tracks of separate files is not that.
===========================================================================
*/
void() SV_PBClear =
{
	local float i;
	for (i = 0; i < FS_MAXTRACKS * FS_MAXSPLITS; i = i + 1)
	{
		run_pb_ticks[i] = 0;
		run_pb_split[i] = 0;
	}
	for (i = 0; i < FS_MAXTRACKS * FS_MAXCPS; i = i + 1)
		run_pb_cp[i] = 0;
	run_pb_dirty = FALSE;
};

// BUILD 23: data/runs/<map>/best.pb -- inside the map's own folder now, with a
// fixed basename so the menu's census can scan for it with a single wildcard.
// See FS_PBPath in shared/sh_defs.qc for why the name is fixed rather than the
// map's.  tools/migrate_runs.py moves the old data/runs/<map>.pb files.
string() SV_PBPath = { return FS_PBPath(mapname); };

/*
  data/runs/<map>.pb -- one line per fact, three numbers each:

      best  <track> <leg>       <ticks>    the leg's best time
      split <track> <segment>   <ticks>    the PB's clock at that stage boundary
      cp    <track> <ordinal>   <ticks>    the PB's clock at that checkpoint

  ADDITIVE, LIKE THE .rec HEADER, and by the same mechanism: an unrecognised
  keyword falls through to nothing rather than aborting the load, so a file
  written by a newer build loads in an older one and vice versa.  `cp` joined it
  in build 19 and a pre-19 build reads such a file with no complaint.

  The bounds test lives ABOVE the keyword dispatch on purpose -- it is why
  FS_MAXCPS is required to equal FS_MAXSPLITS.

  BUILD 57: FTESURF-PB 2, AND `best` IS THE ONLY LINE WHOSE MEANING MOVED.
  Version 1 keyed it by the 0-based SEGMENT a run began at, so `best 0 1` was
  stage 2 and stage 1 could not be written at all.  Version 2 keys it by LEG --
  `best 0 1` is stage 1.  `split` and `cp` were always keyed by segment and by
  ordinal and are untouched.

  A VERSION-1 FILE IS SHIFTED IN MEMORY, not refused and not rewritten here:
  every `best t s` with s > 0 is read as leg s + 1, which is what it meant.  So
  an un-migrated best.pb shows the right stage times the moment this build loads
  it, and the next SV_PBSave writes it back as version 2.  What this cannot fix
  is the stage_N FOLDERS beside it, which still hold stage N+1 -- so the load
  says so, once per map, and names the tool that renames them.

  The version comes from the header, which SV_PBSave always writes first; a file
  with no header at all is older than the header and is version 1.  The shift
  happens BEFORE the bounds test, so the test asks about the leg: a version-1
  `best 0 23` is leg 24, which the table cannot hold, and it is dropped here
  exactly as an out-of-range line always was.
*/
void() SV_PBLoad =
{
	local filestream f;
	local string line, w;
	local float n, a, b, c;
	local float ver, shifted;       // build 57: the file's version; a v1 stage key was moved

	SV_PBClear();

	/*
	  PATCH 270, STAGE 2.  A lobby loads no personal bests at all.

	  Gating only the SAVE would leave the table populated from the host's own
	  best.pb, and every one of the 32 people on the map would be shown that
	  time as THEIR personal best -- in the HUD, in the "best by" line at every
	  stage, and in the finish card.  A number presented as yours that belongs
	  to somebody you have never met is worse than no number.

	  This is also the one PB call that runs at map init, before the first
	  StartFrame, which is why Lobby_NoPB reads its cvars live rather than a
	  value Lobby_Frame cached.  See the essay at those accessors.
	*/
	if (Lobby_NoPB())
		return;

	f = fopen(SV_PBPath(), FILE_READ);
	if (f < 0)
		return;

	ver     = 1;
	shifted = FALSE;

	while ((line = fgets(f)) != "")
	{
		n = tokenize(line);
		if (n >= 2)
		if (argv(0) == "FTESURF-PB")
		{
			ver = stof(argv(1));
			continue;
		}
		if (n < 4)
			continue;
		w = argv(0);
		a = stof(argv(1));
		b = stof(argv(2));
		c = stof(argv(3));

		// Build 57: a version-1 stage key is a segment; read it as its leg.
		if (w == "best")
		if (ver < 2)
		if (b > 0)
		{
			b = b + 1;
			shifted = TRUE;
		}

		if (a < 0 || a >= FS_MAXTRACKS || b < 0 || b >= FS_MAXSPLITS)
			continue;

		if (w == "best")
			run_pb_ticks[a * FS_MAXSPLITS + b] = c;
		else if (w == "split")
			run_pb_split[a * FS_MAXSPLITS + b] = c;
		/*
		  BUILD 19.  The bounds test above already covers this row because
		  FS_MAXCPS == FS_MAXSPLITS -- which is why they are required to be equal
		  and why the test sits before the keyword dispatch rather than inside
		  each arm.  An unknown keyword still falls through to nothing, so a .pb
		  written by this build loads in an older one and vice versa; same
		  additive rule the .rec header follows.
		*/
		else if (w == "cp")
			run_pb_cp[a * FS_MAXCPS + b] = c;
	}
	fclose(f);

	/*
	  BUILD 57: THE NOTICE IS ABOUT THE FOLDERS, AND IT MUST NOT GO QUIET WHEN THE
	  TREE BECOMES HARDER TO FIX RATHER THAN EASIER.

	  It used to print only on `shifted` -- a version-1 best.pb whose stage keys
	  were moved on load.  That reads the wrong thing.  One finish on build 57 has
	  SV_PBSave rewrite the file as FTESURF-PB 2 while the stage_N folders beside
	  it are still segment-numbered, so the warning stops on exactly the map that
	  now needs it most, and its silence reads as "migrated".  legs1 then refuses
	  that map, and refuses the whole tree with it.

	  So the test is the pair that actually disagrees: a stage folder with runs in
	  it, and no data/runs/.legs1 to say the rename has happened.  `shifted` still
	  prints on its own, because a version-1 file is worth naming even on a map
	  with no stage folders yet.
	*/
	if (!shifted)
	{
		local filestream mk;
		local float sh;

		mk = fopen(strcat(FS_RUNS_ROOT, ".legs1"), FILE_READ);
		if (mk < 0)
		{
			sh = search_begin(strcat(FS_RunDir(mapname, 0, 1), "*.rec"),
			                  FS_NAMESORT, TRUE);
			if (sh >= 0)
			{
				if (search_getsize(sh) > 0)
					shifted = TRUE;
				search_end(sh);
			}
		}
		else
			fclose(mk);
	}

	if (shifted)
		print(sprintf("^3timer:^7 %s and its stage_N folders predate build 57 -- times load "
		              "correctly, but the folders are one stage early until you run "
		              "tools/migrate_runs.py legs1.  This line stops when %s.legs1 exists.\n",
		              SV_PBPath(), FS_RUNS_ROOT));

	/*
	  BUILD 76: THE CLOCK NOTICE, and it is a different KIND of notice from the one
	  above, which is why it is a second line rather than another clause.

	  The build-57 line says a file is fine and its FOLDERS need renaming -- an
	  action, with a tool that performs it.  This one says the times in the file
	  are correct as measurements and were taken with a different instrument, and
	  there is no tool, because there is nothing anybody could run.  The sampled
	  clock ran 0-2 ticks long with a frequency that was not stable between
	  identical runs, so no arithmetic recovers what a given run would have scored.

	  SO IT NAMES THE BIAS AND ITS DIRECTION, which is the only actionable thing
	  there is: the player's stored bests are slightly slow by the new
	  measurement, so the next lap beats them by a hair nobody earned.  Said once
	  per map load, and it stops on its own the first time anything on that map is
	  written, because SV_PBSave stamps version 3.

	  ver < 3 AND NOT `ver == 2`, so a file from a build that never existed, or a
	  header-less file (which reads as version 1), is covered.  The same open
	  interval the shift test above uses.
	*/
	/*
	  THE WORDING IS NARROW ON PURPOSE, and it got narrower once the verification
	  arm had run.  The first draft of this line said the old clock "measured 0-2
	  ticks long" and told the player to expect the first run on each leg to beat
	  one.  Both halves were an over-claim: b76clock.cfg measured the gap at -1
	  twice on a listen server, so neither the magnitude nor the SIGN is settled.
	  A notice that predicts something the next run disproves teaches people to
	  ignore notices.  So it states only what is certain -- a different instrument,
	  a sub-frame difference, no conversion -- and predicts nothing.
	*/
	if (ver < 3)
		print(sprintf("^3timer:^7 %s was written before build 76 -- its times were taken on the "
		              "SAMPLED clock, which differs from the counted one by a fraction of a "
		              "frame in either direction.  They load unchanged; there is no sound "
		              "conversion, so old and new bests are not exactly comparable.\n",
		              SV_PBPath()));
};

void() SV_PBSave =
{
	local filestream f;
	local float t, s;

	/*
	  PATCH 270, STAGE 2 -- THE FILE-DESTROYING CASE, refused here rather than
	  only at the two callers.

	  This function rewrites data/runs/<map>/best.pb WHOLE from a table that has
	  no player dimension.  On a 32-player lobby the table holds whoever
	  finished last, so one stranger's run overwrites the host's entire history
	  for that map -- every track, every split, every checkpoint -- and nothing
	  anywhere says it happened.

	  The two callers are gated too.  This second guard is not redundancy for
	  its own sake: a third caller is exactly the kind of thing that gets added
	  later by someone who has read SV_TimerFinish and not this essay, and the
	  cost of that mistake is somebody's data.
	*/
	if (Lobby_NoPB())
		return;

	f = fopen(SV_PBPath(), FILE_WRITE);
	if (f < 0)
	{
		dprint(sprintf("timer: cannot write %s\n", SV_PBPath()));
		return;
	}

	/*
	  BUILD 57: version 2, whose `best` lines are keyed by LEG.  SV_PBLoad reads a
	  version-1 file by shifting its stage keys, so a best.pb an older build wrote
	  is rewritten here in the new meaning the first time anything on it changes.

	  BUILD 76: VERSION 3, AND IT IS THE ONLY VERSION BUMP HERE THAT CANNOT BE
	  MIGRATED IN MEMORY.

	  Version 1 -> 2 moved a KEY, and a key can be re-keyed: SV_PBLoad shifts a v1
	  stage number to its leg on the way in and the times themselves were never in
	  question.  This one moves the VALUES.  Every tick count in a v1 or v2 file
	  was sampled off sv.time; every one written from here is counted off the
	  mover.

	  AND THE SIZE OF THAT DIFFERENCE IS NOT KNOWN, WHICH IS THE THIRD TIME A
	  CLAIM ABOUT IT HAS HAD TO BE WITHDRAWN.  Build 74's log asserted the gap was
	  bounded at 1 after eleven readings and the next run measured 2.  Build 75's
	  log retreated to a narrower claim -- that the gap is 0..2 and that sampled is
	  ALWAYS at least counted, 18 of 18 -- and build 76's own verification arm
	  measured **-1**, twice.  So the direction is not a property of the system
	  either.

	  WHAT IS SOUND IS HALF OF THAT: the sampled clock is floor(x + 0.5), which
	  rounds BOTH ways, so it cannot be one-sided by construction.  A -1 therefore
	  needs no explaining; the old 18-of-18 does, and IT HAS NONE.  The obvious
	  candidate -- that those were all taken over a real network, where late
	  packets let sv.time run ahead of the mover -- was written down here and then
	  falsified by b76net.cfg, a live lobby through the router, which read -1
	  twice itself.  A fifth explanation is not being offered.

	  THERE IS THEREFORE NO CONVERSION, and offering one would be a lie twice over
	  -- the magnitude is not constant (2-of-7 on one run and 6-of-7 on the next,
	  same script, same map, same lobby) and now the sign is not either.  The three
	  honest options are refuse the file, convert it, or load it and say so.
	  Refusing throws away a player's history over a sub-frame difference;
	  converting invents numbers.  So it loads unchanged and SV_PBLoad prints one
	  line naming what happened -- the same answer build 57 gave the stage folders,
	  for the same reason.

	  THE BOARD NEEDED NONE OF THIS, and that is why this is cheap now and would
	  not have been in a month: the hosted records were deleted on 2026-09-14 and
	  /api/board returns no rows, so nothing anywhere is being compared across the
	  two measurements except a player's own local bests.
	*/
	fputs(f, "FTESURF-PB 3\n");
	fputs(f, sprintf("# %s  %s\n", mapname, strftime(TRUE, "%Y-%m-%d %H:%M")));

	// best: s is the LEG (0 the full run, k stage k), which is the table's own key.
	for (t = 0; t < FS_MAXTRACKS; t = t + 1)
		for (s = 0; s < FS_MAXSPLITS; s = s + 1)
			if (run_pb_ticks[t * FS_MAXSPLITS + s] > 0)
				fputs(f, sprintf("best %d %d %d\n", t, s, run_pb_ticks[t * FS_MAXSPLITS + s]));

	for (t = 0; t < FS_MAXTRACKS; t = t + 1)
		for (s = 0; s < FS_MAXSPLITS; s = s + 1)
			if (run_pb_split[t * FS_MAXSPLITS + s] > 0)
				fputs(f, sprintf("split %d %d %d\n", t, s, run_pb_split[t * FS_MAXSPLITS + s]));

	for (t = 0; t < FS_MAXTRACKS; t = t + 1)
		for (s = 0; s < FS_MAXCPS; s = s + 1)
			if (run_pb_cp[t * FS_MAXCPS + s] > 0)
				fputs(f, sprintf("cp %d %d %d\n", t, s, run_pb_cp[t * FS_MAXCPS + s]));

	fclose(f);
	run_pb_dirty = FALSE;
};

// BUILD 57: `leg` is a LEG -- 0 the full run, k stage k -- and the bound is on it.
float(float track, float leg) SV_PBGet =
{
	if (track < 0 || track >= FS_MAXTRACKS || leg < 0 || leg >= FS_MAXSPLITS)
		return 0;

	/*
	  PATCH 270, STAGE 2 -- and this is the READ side of the gate, which the
	  first version of the patch did not have.

	  SV_PBLoad refuses to read best.pb in a lobby, and that covers a map that
	  LOADS as a lobby.  It cannot cover the host who practises with
	  lobby_enable 0 and then types `lobby_enable 1` without changing map: the
	  table is already populated, SV_PBLoad is not going to run again, and every
	  one of the 32 people who join is then shown the host's time as their own
	  personal best -- in the HUD, in "best by" at every stage, and on the
	  finish card.

	  Gating the accessor rather than clearing the table on the transition is
	  deliberate: the table is still correct and still the host's, and flipping
	  lobby_enable back to 0 restores it without a re-read.  Nothing has to
	  detect the edge.
	*/
	if (Lobby_NoPB())
		return 0;

	return run_pb_ticks[track * FS_MAXSPLITS + leg];
};

/*
===========================================================================
  BUILD 24 -- LIFTING A STAGE OUT OF A MAIN RUN

  "Record stage records and demos when you are doing a main.  You will complete
  stages when doing a main but they are not recorded at the moment.  Only record
  stages that start with a jump, and not any that you surf through like a
  checkpoint."

  THE SLICE.  There is no second recorder and no second buffer.  Every sample of
  the whole run is already in rec_rec_buf, and a stage is a RANGE of those lines --
  buf_writefile takes a start and a count, which is the entire reason this costs
  nothing while the run is going and one pass at the boundary.

  THE TIMESTAMPS HAVE TO BE REBASED, and that is the only real work.  A sample
  written 42 seconds into a main run carries t = 42.3, and a stage file whose
  first sample says 42.3 would open its replay with the clock reading 0:42.  So
  each line is re-emitted with its first field shifted -- and ONLY its first
  field: the rest of the line is copied verbatim from the first space onward
  rather than re-formatted, so seventeen columns cannot pick up rounding drift on
  the way through.

  A HEADER KEY WOULD HAVE BEEN CHEAPER AND WAS THE WRONG ANSWER.  `tbase <f>`,
  subtracted by the reader, needs no rewrite at all -- but it makes every reader
  of every .rec learn a new rule, and a reader that does not is silently 42
  seconds out rather than visibly broken.  Rewriting means a stage demo is an
  ORDINARY .rec that reccheck.py, cl_watch.qc and anything written later handle
  with no change whatsoever.  That is worth one pass over a few hundred lines.
===========================================================================
*/

/*
  Does this line belong in the slice, and what does it become?

  Samples and `board` records carry `t` in seconds and are rebased.  `cp` carries
  the run clock in TICKS and is rebased in ticks.  `stage` is the boundary itself
  and is dropped -- the slice's own extent is its trailer.

  BUILD 43: THE COMMENT HERE USED TO SAY `restart` CANNOT OCCUR, AND IT CAN NOW.
  Build 24's reasoning was that `resume` and `restart` both force practice and a
  practice run never reaches SV_StageWrite.  Half of that is still true: a save
  resume dirties the stage and SV_StageClose refuses it.  The other half is not,
  because a stage FAIL writes `restart` and deliberately does not taint anything
  -- resetting on a stage is a legitimate part of running one.

  Every one of them is still dropped, and the reason is now stronger rather than
  weaker: SV_StageFail and SV_StageStart both move run_st_line PAST the record
  they just wrote, so a `restart` or a `stagestart` is outside the slice's range
  by construction and this function never sees one.  Dropping them here is the
  belt to that braces -- and it matters, because a `restart` copied into a stage
  demo would claim a reset that, rebased, sits at a negative time.

  Returns "" for a line to drop.
*/
string(string l, float tbase, float tickbase) SV_StageLine =
{
	local float sp, n;

	if (FS_IsSample(l))
	{
		// The first space, and everything after it copied verbatim.  Re-emitting
		// the other sixteen columns through sprintf would risk changing them.
		sp = strstrofs(l, " ");
		if (sp < 1)
			return "";
		return strcat(sprintf("%.4f", stof(substring(l, 0, sp)) - tbase),
		              substring(l, sp, strlen(l) - sp));
	}

	if (substring(l, 0, 6) == "board ")
	{
		sp = strstrofs(l, " ", 6);
		if (sp < 1)
			return "";
		return strcat(sprintf("board %.4f",
		                      stof(substring(l, 6, sp - 6)) - tbase),
		              substring(l, sp, strlen(l) - sp));
	}

	if (substring(l, 0, 3) == "cp ")
	{
		n = tokenize(l);
		if (n < 3)
			return "";
		if (stof(argv(2)) < tickbase)
			return "";              // a checkpoint from before this stage began
		return sprintf("cp %d %d", stof(argv(1)), stof(argv(2)) - tickbase);
	}

	/*
	  BUILD 48: `ghost` IS KEPT, and keeping it is what lets a ghosted stage be
	  written at all.

	  It used to fall through to the drop below, and that was the whole of the
	  problem build 43 solved by refusing the stage instead: SV_StageWrite's
	  header copies TF_GHOST in from run_st_ghost, so a slice claimed a ghost in
	  its header and carried no record of one in its body, which reccheck.py
	  faults as a disagreement.  Keep the records and the two agree, and then
	  there is nothing left to refuse.

	  Rebased in TICKS like `cp` and for the same reason -- both carry the run
	  clock, not a `t` in seconds.

	  A record from before this stage began is dropped like a checkpoint's, and
	  the state it carried is NOT lost: SV_StageWrite emits a synthetic opener
	  when the stage began already ghosting.  That is the span case, and it has
	  to be handled there rather than here, because this function sees one line
	  at a time and cannot know it is looking at the first.
	*/
	if (substring(l, 0, 6) == "ghost ")
	{
		n = tokenize(l);
		if (n < 3)
			return "";
		if (stof(argv(2)) < tickbase)
			return "";              // before this stage; the opener covers it
		return sprintf("ghost %d %d", stof(argv(1)), stof(argv(2)) - tickbase);
	}

	/*
	  BUILD 82: AN `in` ROW FALLS THROUGH TO THE DROP BELOW, DELIBERATELY, and
	  this paragraph exists so that nobody later reads the silence as the build-81
	  omission repeating itself.  (That one was real: this writer had been missing
	  mapcrc since build 73 and nobody had written down that it was missing.)

	  A lifted stage is a SLICE, and a slice rebases.  Every record this function
	  keeps is rewritten into the slice's own origin -- `t` against tbase, `cp` and
	  `ghost` against tickbase -- because the alternative is two clocks in one
	  file, which is the hazard build 76 landed whole to avoid.  An `in` row's
	  <mt> is cumulative mover ticks PER MAP; rebasing it would need the slice's
	  own mover origin, which SV_StageWrite is not given and which is not
	  derivable from tickbase alone, because tickbase is run ticks and the two
	  differ by the run's start tick and its accumulated frozen ticks.  Copying it
	  unrebased into a rebased file is exactly the thing not to do.

	  And the cost of dropping them is small and bounded, which is what makes this
	  the right call rather than a deferral.  A lifted stage exists to be WATCHED;
	  the input trace exists to be RE-SIMULATED, and a stage run ARMED at the stage
	  is an ordinary run that records one like any other.  What is lost is the
	  ability to re-simulate a stage that was lifted out of a longer run -- which
	  is also the only .rec in this tree that no verifier could seed anyway, since
	  its first sample is mid-flight rather than at a start plane.

	  SV_StageWrite writes no `instart` key for the same reason, so the file says
	  it has no trace rather than claiming a horizon it does not honour.
	*/

	/*
	  BUILD 83: AND A `warp` ROW FALLS THROUGH TOO, on the same argument and with
	  one addition that makes it stronger rather than weaker.

	  This function is DENY-BY-DEFAULT, so writing nothing here would already have
	  dropped the record -- in total silence, which is precisely why the paragraph
	  above exists and why this one does.  The build-43 ghost bug shipped by this
	  exact route: SV_StageWrite copied a taint bit into the slice header from
	  run_st_*, the body carried no record of it, and reccheck.py faulted the
	  disagreement.  A record that can be dropped without a sentence will be.

	  WHY IT IS DROPPED.  A `warp` carries <mt>, which is cumulative mover ticks
	  PER MAP -- the same unrebasable quantity the `in` rows carry, for the same
	  reason -- and it exists to be RE-SIMULATED, which a lifted stage cannot be
	  anyway: its first sample is mid-flight rather than at a start plane, so no
	  verifier can seed it.  Dropping the events beside the inputs they belong to
	  keeps the slice internally consistent; keeping the events without the inputs
	  would produce a file that states discontinuities nothing in it can explain.

	  AND THE HEADER AGREES, which is the half build 43 got wrong.  SV_StageWrite
	  writes `FTESURF-REC 5`: no `instart`, no trace, no `warp`, a four-field
	  trailer, and therefore no <warps> count to disagree with an empty body.  The
	  marker describes the file and not the build that wrote it, and a v5 file is
	  exactly what a slice structurally is.
	*/

	/*
	  BUILD 85: `ride` AND `inend` FALL THROUGH TOO, same two reasons -- <mt> is
	  per-MAP and unrebasable, and a slice cannot be re-simulated anyway.

	  ONE DIFFERENCE WORTH THE SENTENCE: `ride` is the first STATE this function
	  drops.  A reader carrying its own default across the gap would hold '0 0 0'
	  through a ride.  Safe only because the v5 marker says the file has no such
	  track, so the answer is "unknown" and not "zero" -- the same distinction the
	  rec_rec_bvset sentinel keeps on the writing side.
	*/

	// BUILD 87: `seed`, `pm`, `pe` and `portal` fall through too -- row-bound and
	// per-map like `in`, and a v5 slice has no rows for them to bind to.
	// Patch 382: `spec` too; a stage spanning a window never qualifies (run_st_sp).

	return "";
};

/*
  Write one stage's slice as a stand-alone recording.

  Built into a temporary strbuf and written with ONE buf_writefile rather than a
  few hundred fputs calls, which is the same argument the main recorder makes
  about its own buffer -- and it means the header, the samples and the trailer
  are one contiguous write that either happens or does not.
*/
// A stage's own taint, as run flags (the stage file's header and a stage post).
float(entity e) SV_StageFlags =
{
	local float i;

	i = 0;
	if (e.run_st_dirty)  i = i | TF_PRACTICE;
	if (e.run_st_ghost)  i = i | TF_GHOST;
	if (e.run_st_stitch) i = i | TF_PRACTICE | TF_SEGMENT;
	if (e.run_st_cheat)  i = i | TF_PRACTICE | TF_CHEAT;
	return i;
};

void(entity e, float seg, float dur, float tbase, float tickbase,
     float first, float last) SV_StageWrite =
{
	local float buf, i, fh, samples, cps, pad;
	local float gfirst;             // build 48: the slice's first ghost record, or -1
	local float leg;                // build 57: the leg this slice is filed under
	local string l, dst, who;

	/*
	  BUILD 66: A STREAMED RUN HAS NO LINES TO LIFT.

	  The slice below reads rec_rec_buf[first..last] of a run that is still
	  going, and a stream is not addressable -- those lines are on disk, behind a
	  write-only handle, in a file that is not finished.  Producing a stage demo
	  anyway would mean a second stream opened at every stage boundary, written
	  in parallel, renamed or removed once the boundary decides whether the stage
	  qualifies.  That is a real design and it is not this one.

	  SAID OUT LOUD rather than returned quietly, because unlike the save-state
	  pair above this one HAS a caller in a lobby: finishing a stage during a main
	  run is ordinary play, and the stage board would simply have no replay behind
	  its rows with nothing anywhere saying why.  A stage run ARMED at the stage
	  is an ordinary run and streams like any other -- it is only the lift out of
	  a main run that is missing.
	*/
	if (e.rec_rec_stream)
	{
		dprint(sprintf("stage: seg %g not lifted -- this run is streamed, and a "
		               "slice needs the buffer\n", seg));
		return;
	}

	buf = buf_create_ex("string", 0);
	if (buf < 1)
	{
		dprint("stage: buf_create failed; not writing this stage\n");
		return;
	}

	/*
	  The header, and it is a v4 header like any other -- the only things that
	  differ from the parent run's are `startseg` and `leg`, which are what make
	  this file a member of a stage leg rather than of main.  BUILD 57: `leg` is
	  seg + 1, the folder it is written into; `startseg` stays the segment, and
	  for stage 1 that is the same 0 the parent run's own header carries.

	  `flags` is written directly rather than reserved and rewritten: unlike a
	  live recording, everything about this one is already known.

	  BUILD 43: IT IS THE STAGE'S OWN WORD, NOT THE PARENT RUN'S.  Build 24 copied
	  e.run_t_flags in, on the reasoning that "a stage lifted out of a tainted run
	  is exactly as tainted as the run".  The request falsifies that sentence --
	  a clean stage inside a practice run is the thing it asks to be recorded --
	  and leaving the copy in would have shipped the feature and then labelled
	  every file it produced `practice`, which the leaderboard filter reads.

	  DERIVED FROM THE TAINTS RATHER THAN WRITTEN AS 0.  It is computed for the
	  same reason the `pad` count in the trailer is counted rather than asserted --
	  build 24 wrote a literal there and seven of the first twelve stage files
	  disagreed with it.  A header derived from the state it describes cannot drift
	  when a taint is added and this line is forgotten.

	  BUILD 48: AND IT IS NO LONGER PROVABLY ZERO.  This paragraph used to say so
	  in as many words -- "SV_StageClose has already refused every stage with
	  either bit set, so this can only ever emit zero" -- and that was true right
	  up until run_stageghost stopped a ghosted stage being refused.  TF_GHOST is
	  now a bit this line really can emit, which is exactly why the derivation was
	  worth keeping when it looked like dead arithmetic.  TF_PRACTICE and the two
	  class bits below are still provably zero, because run_st_dirty still refuses.

	  TF_SHADOW needs no test of its own now: it implies TF_PRACTICE, which sets
	  run_t_dirty, which the level watcher and SV_StageOpen turn into run_st_dirty
	  -- and a save-lock load during a stage taints that stage by construction.
	  Said out loud rather than left to be remembered.
	*/
	i = SV_StageFlags(e);   // the taint lines these essays describe, in one place (Patch 360)
	/*
	  BUILD 44: and the CLASS, on the same terms.  Both imply TF_PRACTICE and both
	  set the umbrella above, so these two lines add nothing a filter reads -- they
	  are here so a stage file and its parent run answer FS_RunClass the same way.
	  A stage lifted out of a run is a .rec like any other, and a reader that got
	  `segmented` from the parent and `practice` from the child would be right to
	  call that a bug in the writer.

	  Provably zero, like the two above: SV_StageClose refuses on run_st_dirty,
	  which both of these imply.  Derived anyway, for the reason the paragraph
	  above gives about a third taint and a forgotten line.
	*/
	leg = FS_LegOf(seg, TRUE);      // build 57: a lifted stage is always a stage leg

	/*
	  BUILD 76: VERSION 5 HERE TOO, AND THIS ONE IS THE HAZARD RATHER THAN THE
	  HOUSEKEEPING.

	  This is not a stub -- it is a real recording with a body, lifted out of the
	  parent run's buffer, and its `t` column is the parent's samples verbatim.
	  Those were stamped by SV_RecLine from SV_TimerElapsed, which is the counted
	  clock, so leaving `FTESURF-REC 4` on this file would have shipped exactly
	  the thing this migration was written to make impossible: a v4 header over a
	  v5 body, with nothing in the file saying which clock its numbers are on.  It
	  is the least visible of the three writers and therefore the one most likely
	  to have been missed -- found by grepping for the magic rather than by
	  reasoning about which files matter.

	  `movetickrate` joins it for the same reason, and it is not cosmetic: this
	  header did not carry it, and reccheck.py now faults a file that claims
	  `clock counted` without one, because such a file states that its ticks came
	  from the mover and cannot say how long one of them is.
	*/
	bufstr_set(buf, buf_getsize(buf), "FTESURF-REC 5");
	bufstr_set(buf, buf_getsize(buf), sprintf("map %s", mapname));
	bufstr_set(buf, buf_getsize(buf), sprintf("track %g", e.run_t_track));
	bufstr_set(buf, buf_getsize(buf), sprintf("startseg %g", seg));
	bufstr_set(buf, buf_getsize(buf), sprintf("leg %g", leg));
	bufstr_set(buf, buf_getsize(buf), sprintf("tickrate %g", run_t_tick));
	bufstr_set(buf, buf_getsize(buf), sprintf("movetickrate %g", e.run_movetickrate));
	bufstr_set(buf, buf_getsize(buf),
	           sprintf("clock %s", e.run_t_clock ? "counted" : "sampled"));
	bufstr_set(buf, buf_getsize(buf), sprintf("owner %s", e.netname));
	bufstr_set(buf, buf_getsize(buf),
	           sprintf("runid %s-s%g", strftime(TRUE, "%Y%m%d-%H%M%S"), seg));
	bufstr_set(buf, buf_getsize(buf), sprintf("flags %g", i));

	/*
	  BUILD 81: mapcrc AND THE ZONE PIN, both of which this writer had been
	  missing since they were added -- mapcrc since build 73, the zone keys as of
	  now.  This is the least visible of the three FTESURF-REC writers and it is a
	  REAL recording with a real body, so a reader that trusts the header learns
	  less from a lifted stage than from the run it was lifted out of, for no
	  reason anybody chose.  It is the same omission twice, which is the argument
	  for fixing it beside the second one rather than filing it again.

	  The values are the parent run's by construction: a stage slice is cut out of
	  a recording made on this server, on this map, against this zone table, in
	  the same frame -- so these are not a second measurement of anything, they
	  are the same measurement written into the second file.  cl_lobbytime.qc's
	  header deliberately gets NEITHER; see the note there.
	*/
	if (infokey(world, "*mapcrc") != "")
		bufstr_set(buf, buf_getsize(buf),
		           sprintf("mapcrc %s", infokey(world, "*mapcrc")));
	if (zone_crc != "")
	{
		bufstr_set(buf, buf_getsize(buf),
		           sprintf("zonesrc %s", Zone_SourceTag(zone_source)));
		bufstr_set(buf, buf_getsize(buf), sprintf("zonecrc %s", zone_crc));
		bufstr_set(buf, buf_getsize(buf),
		           sprintf("zonerule %d %d %d",
		                   run_t_swept, run_t_hull, run_t_hulllive));
	}

	bufstr_set(buf, buf_getsize(buf), "begin");

	/*
	  BUILD 48 -- THE SYNTHETIC GHOST OPENER, and it is the other half of letting
	  a ghosted stage be written at all.

	  SV_StageLine keeps `ghost` records now and rebases them, which makes a
	  header claiming TF_GHOST agree with a body that contains one -- for a ghost
	  that STARTED inside this stage.  A ghost that spans the boundary has its
	  turn-on record in the PREVIOUS slice, so this one would carry the header bit
	  and no record, which is the identical disagreement by a different route.

	  Derived rather than latched, because it is derivable and a new field would
	  be a fifth thing SV_StageOpen has to remember to clear.  The first ghost
	  record in range answers it:

	    none at all        it was on for the whole slice          -> opener
	    first turns it OFF it must have been on when we began     -> opener
	    first turns it ON  it began clear                         -> no opener

	  `i = last` to stop rather than `break`, matching the tbase scan below.
	*/
	if (e.run_st_ghost)
	{
		gfirst = -1;
		for (i = first; i < last; i = i + 1)
		{
			l = bufstr_get(e.rec_rec_buf, i);
			if (substring(l, 0, 6) == "ghost ")
			{
				tokenize(l);
				gfirst = stof(argv(1));
				i = last;
			}
		}
		if (gfirst != 1)
			bufstr_set(buf, buf_getsize(buf), "ghost 1 0");
	}

	/*
	  BUILD 25 -- tbase COMES FROM THE FIRST SAMPLE, NOT FROM THE SPLIT'S TICK.

	  Build 24 passed `run_st_tick * run_t_tick`, which RECONSTRUCTS the boundary
	  time from a tick count, and the first sample of the slice does not sit
	  exactly there: the split is processed inside a tick whose sample may have
	  been written just before or just after it, so the first rebased timestamp
	  lands within half a tick either side of zero and THE SIGN IS A COIN FLIP.

	  Your own first staged runs are the evidence, and they split five to two:

	      surf_colin_blaster_69000/stage_1   first sample  -0.0005
	      surf_colin_blaster_69000/stage_2   first sample  +0.0007

	  Half a millisecond, and it changes what the file MEANS.  A negative t is
	  the pre-start padding ring -- that is the grammar's one structural rule --
	  so a reader opens the span at -0.0005 and counts one approach sample, while
	  the trailer below says there are none.  reccheck.py faulted seven of your
	  twelve stage files on exactly that disagreement.

	  Taking the base from the first sample's own timestamp makes the trailer's
	  `0` true by construction rather than by hope, and it makes the comment
	  below -- "its first sample IS the boundary crossing" -- arithmetically so.

	  tickbase is NOT changed with it.  The `cp` records are rebased in TICKS,
	  and a tick count has tick resolution, so a sub-tick offset cannot move one.
	*/
	for (i = first; i < last; i = i + 1)
	{
		l = bufstr_get(e.rec_rec_buf, i);
		if (FS_IsSample(l))
		{
			cps = strstrofs(l, " ");        // reused as a scratch offset
			if (cps > 0)
				tbase = stof(substring(l, 0, cps));
			i = last;                       // found it; stop looking
		}
	}

	samples = 0;
	cps     = 0;
	pad     = 0;
	for (i = first; i < last; i = i + 1)
	{
		l = SV_StageLine(bufstr_get(e.rec_rec_buf, i), tbase, tickbase);
		if (l == "")
			continue;
		if (FS_IsSample(l))
		{
			samples = samples + 1;
			// Belt and braces on the fix above: with tbase taken from the first
			// sample this is provably zero, and it is counted anyway so that the
			// trailer reports what the file HAS rather than what it should have.
			// SV_RecClose's own read-back check is here for the same reason.
			if (str2chr(l, 0) == 45)        // '-'
				pad = pad + 1;
		}
		else if (substring(l, 0, 3) == "cp ")
			cps = cps + 1;
		bufstr_set(buf, buf_getsize(buf), l);
	}

	/*
	  PADDING, and it is COUNTED rather than asserted.

	  A main run's recording opens with the pre-start ring -- a few seconds of
	  approach at negative t, which is what tells a reader where t = 0 is.  A
	  stage lifted out of the middle has none: its first sample IS the boundary
	  crossing, which the tbase above now makes exactly true.  So this is zero on
	  every file -- and it is written from a count of the lines actually emitted,
	  because build 24 wrote a literal 0 here and seven of the first twelve stage
	  files disagreed with it.  A trailer that is derived from the body cannot.
	*/
	bufstr_set(buf, buf_getsize(buf),
	           sprintf("end %d %d %d %d", dur, samples, pad, cps));

	// BUILD 66: by player as well, on the same terms as a full run.  Unreachable
	// with a non-empty `who` today -- a lobby streams, and a streamed run cannot
	// be sliced, so SV_StageWrite refuses above -- but it is spelled correctly
	// rather than left as a thing that becomes wrong the day that changes.
	who = SV_RecWho(e);
	dst = FS_RunPathWho(mapname, e.run_t_track, leg, dur, who,
	                    FS_TagName(RT_PB), "rec");
	fh = fopen(dst, FILE_WRITE);
	if (fh < 0)
		dprint(sprintf("stage: cannot open %s for writing\n", dst));
	else
	{
		buf_writefile(fh, buf, 0, buf_getsize(buf));
		fclose(fh);
		dprint(sprintf("stage: wrote %s (%g samples from lines %g..%g)\n",
		               dst, samples, first, last));

		// Same pruner and the same rule as a full run: the archive grows one
		// file per improvement and is capped per leg, per player.
		SV_RecPrune(e, leg, FS_TagName(RT_PB), who,
		            FS_RunLeaf(dur, who, FS_TagName(RT_PB), "rec"));
	}

	buf_del(buf);
};

/*
  WHICH ZONE IS THE BOUNDARY BOX OF THE SEGMENT IN PROGRESS?  Build 43.

  By IDENTITY -- a STAGE zone, on our track, whose zone_seg is the segment we
  are on -- which is precisely the boundary that BEGAN that segment, and is what
  "the stage start zone" means in the request.

  IT CANNOT BE READ OFF `az`, and that was the first thing tried.  `az` is a
  PRIORITY: a START outranks a STAGE for arming, so on surf_doodles -- whose
  stage-1 box overlaps its start box by 480 units -- `az` names the start while
  you are standing in both, and a stage arm read off it would never see its own
  box at all.

  IT CANNOT BE COMPUTED IN THE MAIN ZONE SCAN EITHER, and that was the second
  thing tried and is the more interesting failure.  The scan runs BEFORE the
  event dispatch, so on the tick a boundary is crossed e.run_t_seg is still the
  OLD segment -- the answer would be resolved one dispatch too early and come
  back -1 on exactly the tick it is needed.  The .rec written by the run that
  caught it says so in two lines:

      stage   1 273
      restart 1 274

  ...a spurious FAIL on the tick after the boundary, because the arm saw no box,
  called it a fly-through, disarmed, and then read the next tick's genuine
  arrival as a re-entry.

  RESOLVED LAZILY AND CACHED, keyed on the segment it was resolved for.  The
  answer only changes when run_t_seg does, so this walks the table once per
  boundary and not once per tick -- which matters on a bhop map, where zone_count
  runs to a couple of hundred.  run_st_zseg is set to -1 by the arm and by
  SV_TimerIdle, so a new attempt, a new track or a new map resolves again.

  -1 is an ordinary answer and not a failure: segment 0 has no boundary zone,
  because a run's first segment begins at its START.
*/
float(entity e) SV_StageZone =
{
	local float z;

	for (z = 0; z < zone_count; z = z + 1)
	{
		if (zone_type[z] != ZONE_STAGE)
			continue;
		if (zone_track[z] != e.run_t_track)
			continue;
		if (zone_seg[z] != e.run_t_seg)
			continue;
		return z;
	}
	return -1;
};

/*
  A stage is ARMED here.  Called from SV_TimerSplit AFTER the boundary record,
  from SV_TimerStart for the run's first segment, from SV_StageFail when the
  stage is taken again, and from the save-lock resume once the recorder has been
  rewound underneath it.

  run_st_seg is set for segment 0 like any other, because SV_StageClose needs a
  consistent "there is a stage open" state to close, and a -1 there would make
  the first boundary a special case in a function that is otherwise the same
  every time.  BUILD 57: and segment 0 IS written now, as stage 1 -- it used to
  be refused as `main`, which is the whole run and not its first stage.

  IT TAKES NO ZONE, AND THAT IS A DECISION RATHER THAN AN OMISSION.  The obvious
  shape is a fourth parameter naming the boundary that was crossed, so the arm
  has something to test occupancy against.  It does not survive contact with the
  three paths that reach here:

    the `!r` restart  SV_ZoneMove calls SV_TimerTeleported BEFORE its setorigin,
                      so at this instant e.origin is still where you WERE.  A
                      zone handed in here would be tested against the wrong
                      position for one tick, and that tick reads "outside the
                      box", which starts the stage from a place you never were.
    a save resume     there is no crossing to name at all.
    the START rule    a STAGE zone is outranked by an overlapping START in the
                      arm scan (surf_doodles overlaps its two by 480 units), so
                      the latched `az` is not reliably the stage's own box.

  So SV_TimerFrame re-derives the stage's own boundary box every tick instead --
  by IDENTITY, `zone_seg[z] == e.run_t_seg` on our own track, which is precisely
  the zone that began the segment in progress.  It costs one compare inside a
  loop that is already testing that point against that zone, it cannot go stale,
  and it is right on the tick after a teleport with no special case anywhere.

  BOTH TAINTS ARE CLEARED FROM THE LEVEL, not to zero.  Clearing to zero would
  be right for one tick and wrong for the next: the level watchers re-taint on
  their next pass, so a stage entered while still noclipping would spend one tick
  looking clean.  Nothing reads it in that tick today -- SV_StageClose runs at
  the NEXT boundary -- but "nothing reads it yet" is a claim about the whole file
  and reading the level here is a fact about this line.
*/
void(entity e, float seg, float ticks) SV_StageOpen =
{
	e.run_st_seg  = seg;
	e.run_st_tick = ticks;
	e.run_st_line = e.rec_rec_lines;
	e.run_st_jump = FALSE;
	e.run_st_ramp = FALSE;
	e.run_st_ms   = FALSE;               // SV_MsApply sets it after reopening
	e.run_st_sp   = FALSE;

	e.run_st_armed = TRUE;
	e.run_st_hold  = FALSE;

	// Patch 360: a takeoff before this boundary never starts this stage.
	e.run_st_tkok   = 0;
	e.run_st_tkland = 0;
	e.run_st_prime  = FALSE;
	e.run_st_launch = -1;

	/*
	  BUILD 44: the cheat half is the LEVEL and the stitch half is zero, and the
	  asymmetry is the same one run_t_cheat and the missing run_t_stitch have.
	  sv_cheats and noclip are states that outlive a boundary; a save-lock load is
	  an event and crossing a boundary puts it behind you.

	  run_st_dirty is derived from the cheat rather than read a second time, so the
	  umbrella cannot disagree with the thing under it.  A third taint added later
	  goes into this expression and nowhere else.
	*/
	e.run_st_dirty  = (e.movetype == MOVETYPE_NOCLIP);   // build 43, unchanged
	e.run_st_cheat  = SV_CheatLevel(e);                  // build 44's half
	e.run_st_stitch = FALSE;
	if (e.run_st_cheat)
		e.run_st_dirty = TRUE;
	e.run_st_ghost  = e.rec_gh_on ? TRUE : FALSE;
};

/*
  THE FILTER, and it is the whole of what was asked for.

  A stage counts as jump-started when the player leaves the ground under their
  own power, from a real ground phase, having touched no ramp since the boundary:

    a jump          velocity_z crossing PM_NONJUMP_VEL with no ramp contact, which
                    is the same detector build 19 built for the start rule and is
                    the only one that can see a bhop at all -- CategorizePosition
                    sets FL_ONGROUND and CheckJumpButton clears it inside one
                    tick, so a well-timed hop never appears grounded to QC
    from the ground run_t_groundsec > 0, i.e. the ground was actually observed.  A
                    jump out of thin air is a trigger_push or a ramp, not a start
    no ramp yet     run_st_ramp.  THIS is the discriminator the request is about:
                    if you have already been on a ramp since crossing the plane,
                    you flew through the boundary and are surfing, and whatever
                    you do next is not the beginning of anything

  BUILD 43: run_st_jump CHANGES MEANING, from "a jump happened during this stage"
  to "this stage began the way a run begins".  Those were the same sentence while
  a stage began at a plane; they are not once it begins at a box exit, because
  WALKING out of the box is now a legal stage start and involves no jump at all.
  So this function keeps the three tests and gains a second caller -- SV_StageStart
  asks it on the leaving edge -- and the two conventions cannot drift because
  there is still only one place the tests are written.

  BUILD 43: run_stagehop.  Build 24 deliberately did NOT require the build-19
  dwell, on the reasoning that a stage platform you bhop off is just a stage
  platform and rejecting it would empty the stage boards on every bhop-friendly
  map.  That reasoning still holds and stays the default.  It is now a cvar
  because the arm rule makes the question sharper -- a hop out of the box now
  decides where the clock STARTS as well as whether the stage is written -- and
  because the only honest place to settle it is bhop_eazy, which has the most
  lifted stage slices on disk and which no config can run.

  run_t_groundsec > 0 carries the autohop case at either setting: a hop the server
  never saw grounded reads a dwell of zero and qualifies nothing.
*/
void(entity e) SV_StageJump =
{
	local float want;

	if (e.run_st_jump)
		return;
	if (e.run_st_ramp)
		return;
	if (e.run_t_groundsec <= 0)
		return;

	if (!run_t_stagehop)
	{
		want = run_t_dwell;
		if (want <= 0)
			want = 0.25;
		if ((SV_ClockSec(e) - e.run_t_groundsec) < want)
			return;
	}

	e.run_st_jump = TRUE;
};

// Patch 360: latch the takeoff that begins a flight (SV_TimerJumpWatch).
void(entity e, float ok) SV_StageTakeoff =
{
	local vector hv;

	/*
	  Patch 411: THE EFFECTIVE speed, and Patch 407 is why this line is here.
	  That patch fixed the same read in SV_StageLaunch one function below -- but
	  SV_StageLaunch's airborne branch takes its launch speed straight back out of
	  run_st_tkspd, and its landing branch out of run_st_tklandspd, a copy of it.
	  So both box exits that go through a takeoff kept reading bare .velocity and
	  run_stagecap stayed decorative on exactly the exit P360 wrote it for.

	  COUNTED ONCE OR NOT AT ALL: run_basevel is zeroed on cash-out
	  (the cash-out in SV_BaseVelocityFrame) and the mover subtracts it back out of
	  .velocity, so the two terms are disjoint at PostThink.  NOT because the Z is
	  already gone -- SV_BaseVelocityFrame zeroes run_basevel_z in PreThink and the
	  touch loop re-arms a full Z afterwards, so on an up-pad it is routinely
	  non-zero right here.  `hv_z = 0` below is what makes that harmless.  (Review
	  finding; the first draft of this comment had the reason wrong.)

	  THE INSTANT IS THE PACKET'S, NOT THE TAKEOFF COMMAND'S.  This runs once per
	  packet from the last command's state, so a carrier armed after the takeoff
	  is the one read.  Still strictly better than a read that was always zero,
	  and on a map with no push the two are byte-identical -- which also bounds
	  the evidence exposure, because `stagepost <launch>` carries this number.

	  RE-SCANNED, because P407's does not transfer: it sampled the box EXIT and a
	  carrier can be armed at takeoff and gone by then.  Live corpus 2026-09-20,
	  218 `ride` rows: exactly two files hold both a non-zero carrier and a
	  stagepost.  surf_deoa/main/0014484_kap has all four posts before its first
	  armed carrier, as P407 said.  surf_rookie/main/0033772_proto interleaves
	  them -- 17 posts against arms of 200, 300, 500 and 550 -- but every
	  `stagestart` there is bracketed by `ride ... arm 0 0 0` and every non-zero
	  arm falls strictly after it, mid-stage.  So no post on the board was taken
	  with a carrier live at its takeoff, and this line moves nothing already
	  recorded.  It arms run_stagecap for the future, which is the point.
	*/
	hv = e.velocity + (1 + run_bv_tick * 0.5) * e.run_basevel;
	hv_z = 0;
	e.run_st_tkok  = ok;
	e.run_st_tkspd = vlen(hv);
	e.run_st_tksec = SV_ClockSec(e);
	e.run_st_tkbc  = e.run_st_bcseen;   // a board anywhere in this packet counts
};

/*
  PATCH 360: WAS THIS STAGE STARTED THE WAY A RUN STARTS?  Asked at the box exit
  (SV_StageStart) and at the run start for the opening stage.  PRIMED: grounded
  for the pre-strafe dwell -- the same dwell that releases +forward
  (cl_main.qc) -- then a jump or a walk-out, at <= run_stagecap.  Speed is
  judged at TAKEOFF for an airborne exit (air-strafe gain after a primed jump is
  honest) and at the exit for a walk-out.  A flown-through boundary never gets
  here, so it is never primed: speed carried through a stage is not a start.
*/
/*
  PATCH 403: A RUN MAY NOT BEGIN CARRYING SPEED THE MOVER DID NOT PRODUCE.

  The speed is not in .velocity.  A trigger_push arms .run_basevel and the engine
  rides it as pmove.basevelocity; it only becomes .velocity on the first command
  nothing re-armed it (SV_BaseVelocityFrame, sv_entities.qc:992).  So a body
  crossing the start plane at 1800 u/s has `seed ... 0 0 0 1` -- measured, and
  pm_verify PASSed it (cfg/test/p403stage.cfg).  Anything that reads .velocity
  here reads zero, which is also why run_stagecap never fired: SV_StageLaunch
  takes `hv = e.velocity` and logged `prime 1 launch 0 ... cap 290` at 1809 u/s.

  So the cap is taken on the EFFECTIVE horizontal speed -- what the body will be
  doing once the carrier cashes out, at the cash-out's own scale -- and it is
  paid out of the CARRIER first.  Clamping the carrier rather than .velocity is
  what makes this free of evidence work:

    - the carrier's value reaches a recording only through `ride arm`, written
      from .run_basevelocity inside SV_BaseVelocityFrame (sv_entities.qc:1053).
      The in-box call sits immediately ABOVE that call in PlayerPreThink and the
      latch call is a packet later, so no record can ever state a number this
      has not already trimmed.  No new record, no REC bump, old files unaffected.
    - .velocity is never written at all.  The rule owns the carrier and nothing
      else, so a fast bhop or slope landing inside a start box is untouched.

  WHERE IT IS CALLED, and the first cut got this wrong.  The in-box call is in
  PlayerPreThink (sv_player.qc), which the engine runs once per USERCMD.  It used
  to sit in SV_TimerFrame, on the PlayerPostThink path, which runs once per
  PACKET -- while trigger_push_touch re-arms the whole push once per command.  So
  it trimmed the last command of each bunch and left the rest at full value, and
  a client setting its own packet rate set the ratio.  Review finding, 2026-09-20.

  NO GROUND GATE, and that is also a correction.  Momentum's rule is ground-only
  because Momentum clamps the player's VELOCITY, where a ground condition is what
  keeps it off bhop prespeed.  This clamps the carrier instead, so the ground test
  bought nothing and cost the whole rule: `FL_ONGROUND` is read after the move and
  after the touch loop, and both a jump and any upward-tilted push clear it, so a
  booster could exempt itself and every bhop start was a structural no-op.  Read
  the carrier and the ground question stops being one -- prespeed is .velocity and
  is never touched, while a jump pad's vertical carrier survives because only the
  x/y components are written.

  Applied on every map rather than reading the per-segment `limitStartGroundSpeed`
  key, because the key is false on bhop_arcane's start segment and on 15 of the
  rotation's 17 bhop maps, which would exempt the exact case this exists for.
  Lex's call, 2026-09-20.

  WHAT IT DOES NOT DO.  A push volume that reaches PAST the start box re-arms its
  full value on the first command of the run, and nothing clamps once the state is
  TS_RUNNING.  The run therefore BEGINS at the cap and then accelerates on the
  map, which is what happens in Momentum too -- its clamp also stops at the zone
  edge.  What is closed is building or inheriting speed inside the box; what is
  not closed is a booster the mapper drew across the start plane.
*/
void(entity e) SV_StartCapClamp =
{
	local vector hv, bv, tot, want;
	local float  k, sp, own;

	if (run_t_startcap <= 0)
		return;
	if (!e.run_basevel_x && !e.run_basevel_y)
		return;                     // nothing carried: nothing this rule owns

	k  = 1 + run_bv_tick * 0.5;     // the cash-out's own scale (sv_entities.qc:997)
	hv = [e.velocity_x, e.velocity_y, 0];
	bv = k * [e.run_basevel_x, e.run_basevel_y, 0];
	tot = hv + bv;
	sp = vlen(tot);
	if (sp <= run_t_startcap)
		return;

	/*
	  IT ONLY EVER TOUCHES THE CARRIER, never .velocity, and that is measured
	  rather than tidy.  Across the Pi's 43,369 grounded sample rows, 16.2% sit
	  at 250-299 u/s and 1.0% are above 300 -- ground running against the 289
	  prestrafe ceiling, and bhop landings and slope slides above it.  Clamping
	  the player's own speed would take prespeed off every bhop start, which is
	  the very thing `limitStartGroundSpeed: false` exists to permit and is set
	  on 15 of the rotation's 17 bhop maps.  So: a push may not carry you over
	  the cap at the start.  Under your own power you are not this rule's
	  business, at any speed.
	*/
	own = vlen(hv);
	if (own >= sp)
		return;                     // the carrier is BRAKING: dropping it would
		                            // raise the start, not lower it
	if (own >= run_t_startcap)
	{
		e.run_basevel_x = 0;        // already at the cap on your own
		e.run_basevel_y = 0;
	}
	else
	{
		// Scale the SUM onto the cap and hand the carrier back the difference.
		// Exact for any angle between the two, unlike scaling bv on its own.
		want = tot * (run_t_startcap / sp);
		e.run_basevel_x = (want_x - hv_x) / k;
		e.run_basevel_y = (want_y - hv_y) / k;
	}

	if (run_bv_debug)
		print(sprintf("startcap: %.1f -> %.1f (own %.1f, cap %g)\n",
		              sp, run_t_startcap, own, run_t_startcap));
};

void(entity e) SV_StageLaunch =
{
	local float want, now;
	local vector hv;

	want = run_t_dwell;
	if (want <= 0)
		want = 0.25;
	now = SV_ClockSec(e);
	/*
	  Patch 407: THE EFFECTIVE speed, not `.velocity`.  A trigger_push does not
	  write velocity -- it arms .run_basevel, which the engine rides as
	  pmove.basevelocity and cashes out at (1 + run_bv_tick * 0.5)
	  (sv_entities.qc:997).  Reading velocity alone judged a boundary crossed on
	  a booster as a STANDING START: the live log read
	  `prime 1 launch 0 tk 1 tkspd 1809 cap 290` while the body did 1809, so
	  run_stagecap has been decorative on any map with a push since P360.
	  Same quantity P403's SV_StartCapClamp uses for the start box, and AGENTS.md
	  states it once for both.

	  COST OF THE CHANGE, MEASURED BEFORE MAKING IT (tools/../stagescan): across
	  the whole live corpus -- 49 files, 69 stagepost records, 61 ride records of
	  which 8 carry a non-zero horizontal value -- ZERO stage posts were made
	  while a carrier was armed.  One file holds both kinds of record
	  (surf_deoa/main/0014484_kap), and its four posts (launch 260-273) all
	  precede its first armed carrier.  So nothing already on the board moves.
	*/
	hv = e.velocity + (1 + run_bv_tick * 0.5) * e.run_basevel;
	hv_z = 0;

	e.run_st_prime = FALSE;
	e.run_st_launchsec = now;
	if (e.run_t_groundsec > 0)
	{
		if (e.run_t_groundsec >= now && e.run_st_tkland > 0)
		{
			e.run_st_launch = e.run_st_tklandspd;   // a primed jump landed on the exit tick
			e.run_st_launchsec = e.run_st_tklandsec;
			e.run_st_prime  = TRUE;
		}
		else
		{
			e.run_st_launch = vlen(hv);
			e.run_st_prime  = (now - e.run_t_groundsec >= want);
		}
	}
	else if (e.run_st_tkok != 0)
	{
		e.run_st_launch = e.run_st_tkspd;
		e.run_st_launchsec = e.run_st_tksec;
		e.run_st_prime  = (e.run_st_tkok > 0);
	}
	else
		e.run_st_launch = vlen(hv);         // fell or was pushed out: never primed

	// A ghost since the boundary: the exit was judged at the un-ghost, not where
	// the body left the box (the ghost branch skips the stage block).
	if (e.run_st_ghost)
		e.run_st_prime = FALSE;

	if (run_t_stagecap > 0)
	if (e.run_st_launch > run_t_stagecap)
		e.run_st_prime = FALSE;
};

/*
  THE STAGE'S CLOCK STARTS HERE.  Build 43.

  You crossed the boundary, you stood in its box, and you have now left it.  That
  is the same three-beat the run start has had since build 1 -- arm by standing
  in the box, start by leaving it -- and it is what the request asks for in as
  many words: "stage times are counted with no pre-speed, so jump start, or
  walking out of the start zone."

  THIS IS A MEASUREMENT CHANGE AND IT RETIRES OLD STAGE TIMES.  Every stage .rec
  on disk before build 43 was measured plane-to-plane; from here a stage that is
  a platform is measured exit-to-plane, which is strictly shorter by however long
  you stood there.  So every pre-43 lifted PB is beaten on the first lap and
  looks artificially slow for a reason no file explains.  That is a real cost and
  it buys a real fix: surf_kitsune/stage_3 currently ranks a deliberate stage run
  above two lifted ones in ONE list, comparing two different measurements against
  one run_pb_ticks slot.  The user's call, taken explicitly.  run_stagearm 0 keeps
  the old measurement and the new fail rule together if it needs taking back.

  A BOUNDARY YOU FLY THROUGH NEVER REACHES HERE, which is what keeps the change
  narrow.  run_st_hold is only set by a tick spent inside the box, so a plane
  crossed at 2000 u/s disarms on the crossing tick and the stage keeps the build
  24 measurement exactly.  On the shipped maps that is most boundaries.

  THE RECORD GOES FIRST AND THE LINE MOVES AFTER IT, so `stagestart` is not the
  slice's own first line -- the same ordering SV_TimerRestartSeg documents for
  `restart`, and for the same reason: SV_StageLine drops non-samples, so a record
  inside the range would be silently dropped by the slicer instead of never being
  in it.

  run_st_ramp IS RESET AND run_st_jump IS NOT SET DIRECTLY.  Standing in the box is
  not surfing, so a ramp touched before the box exit says nothing about the stage
  that starts at it -- but the exit itself still has to qualify, and SV_StageJump
  is the one place that test is written.  A player who slides out of the box down
  a ramp gets no stage record, which is right: that is pre-speed.
*/
void(entity e, float ticks) SV_StageStart =
{
	SV_StageLaunch(e);                  // Patch 360: primed? (stage fill-in)
	SV_RecPut(e, sprintf("stagestart %d %d", e.run_st_seg, ticks));

	e.run_st_tick  = ticks;
	e.run_st_line  = e.rec_rec_lines;
	e.run_st_ms    = FALSE;              // a box exit after a resume is a clean start
	e.run_st_sp    = FALSE;

	/*
	  DISARMED.  run_st_armed is the ONLY thing separating the two readings of
	  standing in the boundary box: before the start it is an arm, after it it is
	  a fail.  The box itself is re-derived every tick from the segment, so there
	  is nothing here to forget.
	*/
	e.run_st_armed = FALSE;
	e.run_st_hold  = FALSE;

	e.run_st_ramp = FALSE;
	SV_StageJump(e);
};

/*
  THE STAGE WAS FAILED.  Build 43.

  "every fail should cause a time reset for timing of that stage", and the fail
  is re-entering that stage's own boundary zone -- which is the user's answer to
  the only question this feature really has, because a surf map cannot otherwise
  tell "I fell off and walked back" from "I am taking a different line".

  THE RUN CLOCK IS NOT TOUCHED, and that is build 12's decision restated rather
  than a new one: run_t_startsec is left exactly where it was and keeps counting, so
  the wasted time is still on the total.  Only run_t_split -- "the run time at
  which the segment in progress began" -- moves, and every stage-relative readout
  derives from it and follows.  SV_TimerRestartSeg has done exactly this since
  build 12 for the `!r` gesture; this is the same primitive reached by walking.

  IT DOES NOT SET PRACTICE, for build 13's reason, which the request agrees with:
  resetting on a stage is a legitimate part of running one.  You already paid for
  it in the total.

  SV_StageOpen re-arms on the SAME zone, which is what makes the next attempt
  judged from a clean slate -- new taints, new jump filter, new slice base -- and
  what makes "walk out of the box again" start the clock the same way it did the
  first time.  run_st_fails and run_st_tp deliberately survive it: they are counters
  about this stage, not about this attempt at it.

  AFTER the record, so the `restart` line is not the first line of the new slice.
*/
void(entity e, float ticks) SV_StageFail =
{
	e.run_st_fails = e.run_st_fails + 1;

	e.run_t_split = ticks;
	e.run_t_delta = 0;

	// The split recorded for this segment is void -- you are doing it again --
	// so move its base with the clock rather than leaving the failed attempt's
	// entry to be differenced against later.  Same three guards as everywhere
	// else in this file: nested, never `&&`.
	if (e.run_t_slot >= 0)
	if (e.run_t_seg > 0)
	if (e.run_t_seg < FS_MAXSPLITS)
		run_run_split[e.run_t_slot * FS_MAXSPLITS + e.run_t_seg] = ticks;

	sprint(e, PRINT_HIGH,
	       sprintf("^3stage %g reset^7 -- back in the stage zone (attempt %g)\n",
	               e.run_t_seg + 1, e.run_st_fails + 1));

	SV_RecPut(e, sprintf("restart %d %d", e.run_t_seg, ticks));

	SV_StageOpen(e, e.run_t_seg, ticks);
};

/*
  The stage that was open is over.  Write it if it qualifies.

  SEVEN REASONS TO WRITE NOTHING, and each of them is a different question:

    no recording      rec_rec_buf < 1.  Nothing to slice.
    not a full run    run_t_stagerun means this IS a stage run, and it writes
                      itself through SV_TimerFinish like any other leg.  BUILD
                      57: the flag, not `run_t_startseg > 0`, because a stage-1
                      run begins at segment 0 exactly as a full run does.
    (segment 0)       BUILD 57 DELETED THIS ONE.  It said the first segment of a
                      main run is the `main` leg -- FS_LegDir(track, 0) -- and
                      that was the bug: segment 0 is STAGE 1, and main is the
                      whole run.  Segment s is written under leg s + 1 now, and
                      a linear track, whose one segment really is the whole run,
                      is refused by SV_StageQualifies instead.
    surfed through    run_st_jump.  The filter -- for every stage except the one
                      the run began with, which the run's own start rules police.
                      See SV_StageQualifies.
    this stage is dirty  run_st_dirty, which BUILD 44 makes an umbrella over
                      run_st_stitch and run_st_cheat exactly as TF_PRACTICE is one
                      over TF_SEGMENT and TF_CHEAT.  THIS LINE DID NOT CHANGE and
                      must not: the class says WHY a stage is refused, never
                      WHETHER, and a filter that tested the two halves separately
                      would let a third taint through the day it was added.
                      BUILD 43, and it REPLACES the run-level
                      `run_t_flags & TF_PRACTICE` test rather than joining it.
                      That is the request: "if a stage is done in practice mode,
                      but the next one has been started legit, then that stage
                      should be counted as legit and recorded."  So a run that
                      was noclipped in stage 2 still writes stages 3, 4 and 5.
                      run_stageclean 0 restores the run-level test whole.
    this stage was ghosted  run_st_ghost.  BUILD 43, and it is a NEW refusal, not
                      a restatement.  TF_GHOST does not imply TF_PRACTICE, so
                      before this a ghosted run could already write a stage slice
                      -- and SV_StageLine drops `ghost` records while the header
                      below copied the bit in, which reccheck.py:618-620 faults as
                      a disagreement.  No file trips it only because no ghost has
                      ever been recorded.  This change edits that very header
                      line, so make the disagreement structurally impossible
                      instead of merely absent.
    not an improvement  it did not beat the stage leg's own best, so there is
                      nothing worth keeping.  Same rule as a full run, and it is
                      what stops a twenty-stage map writing twenty files per lap

  BUILD 43: THE PB RULE NO LONGER COVERS PRACTICE, AND THAT IS THE POINT.  The
  build 24 note here said a practice run writes no stages because a tainted run
  cannot set a personal best, so it cannot pass the improvement check.  That was
  true and is now deliberately false: run_pb_ticks IS written for a clean stage
  lifted out of a dirty run, because the stage was clean.  The improvement check
  therefore stands on its own rather than doubling as the taint filter, and the
  taint filter is the run_st_dirty line above.  Anything that weakens that line
  now weakens the only thing between a noclipped stage and the stage board.

  A stage that never STARTED cannot be written either, and it needs no test: an
  armed stage still carries the boundary tick as its base and run_st_jump FALSE,
  so the filter above refuses it.  Stated because "what happens if I cross the
  next boundary without leaving this one's box" is a fair question about a
  machine that has three states.
*/
/*
  The seven SF_* bits, packed.  Build 48 lifted this out of SV_StageStat.

  ONE SPELLER, because there are now two readers of the same fact and they must
  not be able to drift: the per-tick stat the HUD reads, and the close report the
  results card and the split marks read.  Two copies of a seven-line bit pack is
  exactly the shape of bug the field block above warns about -- five writers, five
  chances to forget one -- and adding a second copy while quoting that paragraph
  would have been funny rather than defensible.

  SF_KNOWN IS ALWAYS SET HERE.  That is the whole point of the bit: a word this
  function produced is a word somebody answered, and a zero is therefore
  distinguishable from a clean stage.  The one place a zero is written on purpose
  is SV_StageStat's no-stage-open guard, which means "nothing is true about it"
  and is the correct absent answer.
*/
float(entity e) SV_StageWord =
{
	local float w;

	w = SF_KNOWN;
	if (e.run_st_armed)  w = w | SF_ARMED;
	if (e.run_st_jump)   w = w | SF_JUMP;
	if (e.run_st_ramp)   w = w | SF_RAMP;
	if (e.run_st_dirty)  w = w | SF_DIRTY;
	if (e.run_st_ghost)  w = w | SF_GHOST;
	// Build 44.  SF_DIRTY is still the umbrella and still the only bit any filter
	// reads; these two say WHY.
	if (e.run_st_stitch) w = w | SF_STITCH;
	if (e.run_st_cheat)  w = w | SF_CHEAT;
	if (e.run_st_prime)  w = w | SF_PRIMED;     // Patch 360
	return w;
};

/*
  BUILD 57 -- DOES THIS STAGE QUALIFY?

  The jump, taint and linear refusals of SV_StageClose, lifted out whole and free
  of side effects, so a second reader can ask the same question and cannot get a
  different answer.  Stage T's lobby times are that reader.

  NOT HERE, DELIBERATELY: whether there is a recording to slice, whether a lobby
  may keep it, whether it beat the leg's best, and whether this is a stage run
  that files itself at the finish.  Those are questions about what gets WRITTEN.
  This one is about the stage, and a stage that qualified still qualified when
  nothing is written for it.

  It reads only what SV_StageClose leaves alone at its top -- run_st_jump,
  run_st_dirty, run_st_ghost, run_st_tick -- and the run's own flags, so it gives
  the same answer before and after the close report is taken.

  FOUR QUESTIONS, in order:

    no stage       seg < 0.  Nothing was open, and -1 has no leg.
    linear track   run_t_segs <= 1.  A track with one segment has no stages: that
                   segment IS the full run, and lifting it would file a duplicate
                   of main under stage_1 -- a leg the scoreboard rightly never
                   lists for a linear map.  (The old `seg <= 0` refusal covered
                   this by accident, along with the stage it should not have.)
    how it began   THE STAGE THE RUN BEGAN WITH qualifies on the RUN'S START
                   RULES; every later stage keeps the run_st_jump filter.
    taint          run_st_dirty and the ghost rule under run_stageclean 1, the
                   run's TF_PRACTICE under 0.  Build 48's rules, unchanged.

  WHY THE FIRST STAGE CANNOT USE run_st_jump.  run_st_jump means "this stage began
  the way a run begins", and SV_StageJump sets it from exactly two places: a
  grounded jump with no ramp contact since the boundary, and the exit from a
  boundary box that SV_TimerFrame's stage machine armed.  The stage a run begins
  with gets neither -- the stage machine refuses segment 0 and every stage run,
  because the run's own arm and start already own that box -- so a clean walk
  out of the START onto a ramp never sets it, and stage 1 would be refused on the
  single most ordinary start there is.

  WHAT POLICES THAT START INSTEAD is what already polices the run: the START
  zone's dwell and run_starthop.  Every way a start can be spoiled has landed in
  run_t_flags as TF_PRACTICE by the time this stage can close --

    a hop out of the box          run_t_hopped, consumed by SV_TimerStart
    a hop just after leaving it   SV_TimerJumpWatch -> SV_TimerPractice, while
                                  the start is unsettled
    noclip or cheats into the box run_t_dirty / run_t_cheat, consumed by the start
    a save-lock load              SV_TimerStitched: TF_SEGMENT | TF_PRACTICE
    run_cheatwatch 0              SV_TimerFinish, before the final close

  -- and run_st_dirty CANNOT stand in for it.  SV_TimerStart consumes those taints
  BEFORE it calls SV_StageOpen, which re-reads run_st_dirty from the live level
  and so launders a hopped start at the stage level.  The run's flag is the one
  place the start's verdict survives, and it is exact rather than over-strict for
  this stage: nothing can taint the run between its arm and the first boundary
  except something that happened during this stage.

  AND IT MUST HAVE BEGUN AT THE START.  run_st_tick == 0 says SV_TimerStart opened
  it, the only opener that passes a literal 0.  A save resume or `retry` re-opens
  the stage at the tick it resumed from, so its slice holds only what came after
  the resume while the time on the board would claim the whole stage.  A load is
  practice anyway; a retry of a clean run is not, and this refuses its short one.

  THE SAME RULE ANSWERS FOR A STAGE RUN'S OWN STAGE (seg == run_t_startseg), which
  SV_StageClose refuses before it asks but a second reader will ask about: that
  stage's start is the run's start too, policed by the same flags, and
  TF_PRACTICE is exactly what decides whether SV_TimerFinish ranks the run.
*/
float(entity e, float seg) SV_StageQualifies =
{
	if (seg < 0)
		return FALSE;
	if (e.run_st_ms)                     // it began before a Multi-Session pause
		return FALSE;
	if (e.run_st_sp)                     // Patch 382: it spans a spectate window
		return FALSE;
	if (e.run_t_segs <= 1)
		return FALSE;

	if (seg == e.run_t_startseg)
	{
		if (e.run_t_flags & TF_PRACTICE)
			return FALSE;
		if (e.run_st_tick != 0)
			return FALSE;
	}
	else if (!e.run_st_jump)
		return FALSE;

	if (run_t_stageclean)
	{
		if (e.run_st_dirty)
			return FALSE;
		/*
		  BUILD 48 -- GHOSTING NO LONGER REFUSES A STAGE, ON THE USER'S CALL, AND
		  THE REFUSAL WAS NEVER ABOUT FAIRNESS.

		  Build 43 added `if (e.run_st_ghost) return;` here and said why in as
		  many words: SV_StageLine dropped `ghost` records while SV_StageWrite's
		  header copied TF_GHOST in, and reccheck.py faults that disagreement.  So
		  the refusal was a cheap way to make a FILE FORMAT problem impossible, and
		  it bought that by throwing the stage away.

		  The run level never agreed with it.  SV_GhostSet's own essay says a
		  ghosted run stays valid and is MARKED instead, because a body with
		  nobody's hands on it is close to self-policing -- and detaching the
		  camera to look around is a thing this game is FOR.  A rule that voided
		  the stage but not the run around it was the odd one out.

		  So the format problem is fixed instead: SV_StageLine now keeps `ghost`
		  records and rebases them like `cp`, and SV_StageWrite emits a synthetic
		  one when a stage began already ghosting.  Header and content agree, and
		  the stage is written.

		  run_stageghost 0 restores build 47 exactly.  (Build 57 moved this rule
		  here from SV_StageClose, word for word.)
		*/
		if (!run_t_stageghost)
		if (e.run_st_ghost)
			return FALSE;
	}
	else
	{
		if (e.run_t_flags & TF_PRACTICE)
			return FALSE;
	}
	return TRUE;
};

/*
  PATCH 360, STAGE FILL-IN: MAY THIS STAGE OF A MAIN RUN GO ON THE STAGE BOARD?
  SV_StageQualifies (clean, a real start) AND primed at <= run_stagecap
  (SV_StageLaunch).  A `!s N` run posts at its finish instead.  run_cheatwatch 0
  marks practice only at the finish, so it would let a mid-run close through.
*/
float(entity e, float seg, float dur) SV_StageFillable =
{
	if (e.run_t_stagerun)
		return FALSE;
	if (!run_t_cheatwatch)
		return FALSE;
	if (dur < 1)
		return FALSE;
	if (!e.run_st_prime)
		return FALSE;
	// Where runs are recorded, a post needs the recording it will be audited
	// from: a lobby save-load drops the stream and the run carries on unrecorded.
	if (SV_RecEnabled())
	{
		if (!SV_RecLive(e))
			return FALSE;
		if (e.rec_rec_rid == "")
			return FALSE;
	}
	return SV_StageQualifies(e, seg);
};

float(entity e) SV_JournalBroken;
float(entity e) SV_RulesetBroken;
float(entity e) SV_ProfileBroken;

// The stage's own taint plus the run's certification holes, re-checked now:
// surfd demotes on those bits (TF_UNCERT), exactly as it does a finish.
float(entity e) SV_StageSubmitFlags =
{
	local float f;

	f = SV_StageFlags(e) | (e.run_t_flags & TF_UNCERT);
	if (SV_JournalBroken(e)) f = f | TF_NOJOURNAL;
	if (SV_RulesetBroken(e)) f = f | TF_NORULESET;
	if (SV_ProfileBroken(e)) f = f | TF_NOPROFILE;
	if (e.rec_mc_sup)        f = f | TF_NOCOUNTS;   // Patch 406
	return f;
};

void(entity e, float ticks) SV_StageClose =
{
	local float dur, pb, seg, leg;

	seg = e.run_st_seg;
	e.run_st_seg   = -1;
	e.run_st_armed = FALSE;

	/*
	  BUILD 48 -- THE CLOSE REPORT, AND IT IS RAISED BEFORE EVERY REFUSAL BELOW.

	  Above the returns deliberately.  The stages worth marking on screen are
	  precisely the ones this function is about to refuse -- a stage you
	  noclipped, a stage you loaded a save inside -- so a report published at the
	  bottom, where run_st_rec* lives, would fire only for the stages that needed
	  no mark at all.

	  A REFUSED CLOSE STILL HAS A REAL DURATION and it is reported: `dur` below is
	  computed from the same two numbers.  What the client does with it is its
	  business; what this function must not do is decide, on the client's behalf,
	  that an unrecorded stage is uninteresting.

	  The word is taken HERE, before SV_StageOpen re-reads the taints from the
	  live level a few frames' worth of calls later in SV_TimerSplit, because
	  after that it is gone -- and gone before any snapshot could have carried it.
	*/
	e.run_st_endseg   = seg;
	e.run_st_endword  = SV_StageWord(e);
	/*
	  BUILD 57, STAGE T -- AND THIS IS THE ONE BIT SV_StageWord CANNOT SET.

	  SF_QUALIFIES is the verdict of SV_StageQualifies, published so that a second
	  keeper of stage times -- the client's lobby store -- asks the server rather
	  than re-implementing a jump detector and a taint ladder it cannot observe.

	  It is OR'd in HERE rather than inside SV_StageWord because that function is
	  shared with the per-tick stat and takes no segment: `e.run_st_seg` is already
	  -1 four lines above, so the shared speller has nothing left to ask about.
	  The local `seg` is the only surviving copy of the right question, which is
	  why the answer can only be taken at this site.

	  SV_StageQualifies reads run_t_segs, run_t_startseg, run_t_flags, run_st_tick,
	  run_st_jump, run_st_dirty and run_st_ghost -- none of which this function has
	  touched -- so asking it before or after the report gives the same answer.
	*/
	if (SV_StageQualifies(e, seg))
		e.run_st_endword = e.run_st_endword | SF_QUALIFIES;
	e.run_st_endticks = ticks - e.run_st_tick;
	e.run_st_endpbwas = 0;
	if (seg >= 0)
		e.run_st_endpbwas = SV_PBGet(e.run_t_track, FS_LegOf(seg, TRUE));

	// Patch 360: a primed stage of a main run is posted to its stage board --
	// above every refusal below, which are about writing a local file.
	e.run_st_endlaunch = e.run_st_launch;
	if (SV_StageFillable(e, seg, e.run_st_endticks))
	if (Lobby_SubmitStage(e, e.run_t_track, FS_LegOf(seg, TRUE), e.run_st_endticks,
	                      SV_StageSubmitFlags(e)))
	{
		e.run_st_endword = e.run_st_endword | SF_POSTED;
		SV_RecPut(e, sprintf("stagepost %d %d %d", seg, e.run_st_endticks,
		                     rint(e.run_st_launch)));
		e.rec_rec_posts = e.rec_rec_posts + 1;
	}
	e.run_st_endrec   = e.run_st_endrec + 1;

	/*
	  BUILD 57: THREE REFUSALS WHERE THERE WERE FOUR, AND THE TAINT BLOCK MOVED.

	  `startseg > 0` became run_t_stagerun, because a stage-1 run begins at
	  segment 0.  `seg <= 0` is gone: segment 0 is stage 1, not `main`.  The jump
	  filter and the taint rules are SV_StageQualifies now -- unchanged for every
	  stage after the first -- so a second reader can ask this function's question
	  and cannot get a different answer.  The recorder, lobby and improvement
	  gates stay here, because they are about what may be WRITTEN.
	*/
	if (!SV_RecLive(e))                return;
	if (e.run_t_stagerun)              return;
	if (!SV_StageQualifies(e, seg))    return;

	dur = ticks - e.run_st_tick;
	if (dur <= 0)
		return;
	if (e.rec_rec_lines <= e.run_st_line)
		return;

	/*
	  PATCH 270, STAGE 2 -- no stage records in a lobby, and this one had to be
	  refused UP HERE rather than at the PB write further down.

	  A stage record IS a personal best; it is stored in the same table and
	  written to the same file.  Gating only the write left the guard below
	  reading a PB of 0 -- SV_PBGet returns 0 in a lobby -- so `dur >= pb` was
	  never true, the "only if you beat it" test stopped rejecting anything, and
	  SV_StageWrite would cut a stage .rec and print "first time on this stage"
	  EVERY LAP, for all 32 players.  A gate that turns a filter off is worse
	  than no gate.

	  It used to be unreachable by a second route -- lobby_norec meant
	  rec_rec_lines was 0, so the test two lines up already returned -- and that
	  paragraph ended by saying the second route was "one cvar away from being
	  false".  BUILD 66 IS THAT CVAR.  A lobby that records now streams, and a
	  streamed run has a real line count, so this gate is the only thing left
	  between a lobby and 32 players cutting a stage .rec every lap.  It was
	  already correct; it is now also load-bearing.

	  (SV_StageWrite refuses a streamed run on its own account as well, because a
	  slice needs the buffer -- but that is a second reason and not this one.
	  Stage times in a lobby belong in Stage 3's telemetry, which has a player
	  dimension.)
	*/
	if (Lobby_NoPB())
		return;

	/*
	  BUILD 57: THE LEG, seg + 1, for everything below -- the best this stage must
	  beat, the folder SV_StageWrite files it in, the slot it takes and the line
	  it prints.  All four used the segment, which filed stage 2 as stage_1 and
	  printed "stage 1" for the boundary every other readout calls stage 2.
	*/
	leg = FS_LegOf(seg, TRUE);

	pb = SV_PBGet(e.run_t_track, leg);
	if (pb > 0)
	if (dur >= pb)
		return;

	SV_StageWrite(e, seg, dur, e.run_st_tick * run_t_tick, e.run_st_tick,
	              e.run_st_line, e.rec_rec_lines);

	// The stage leg's own record, through the same table a deliberate stage run
	// writes: one PB per (track, leg), and best.pb is rewritten whole.
	//
	// Patch 270, Stage 2: not in a lobby.  Same reasoning as the finish path --
	// the table has no player dimension and the file is rewritten whole -- and
	// the stage line above is still printed, because the split it reports is
	// this player's own measurement either way.
	if (!Lobby_NoPB())
	{
		if (e.run_t_track >= 0)
		if (e.run_t_track < FS_MAXTRACKS)
		if (leg < FS_MAXSPLITS)
			run_pb_ticks[e.run_t_track * FS_MAXSPLITS + leg] = dur;
		SV_PBSave();
	}

	sprint(e, PRINT_HIGH,
	       sprintf("^2stage %g^7 -- %s%s\n", leg, SV_TimerString(dur),
	               (pb > 0) ? sprintf(", best by %s", SV_TimerString(pb - dur))
	                        : ", first time on this stage"));

	/*
	  Told to the client LAST and all four together, which is what lets it write
	  the matching .view slice without doing any arithmetic of its own.  See the
	  STAT_FS_STAGE* block in sh_defs.qc for why that matters.
	*/
	e.run_st_recseg   = seg;
	e.run_st_recticks = dur;
	e.run_st_recat    = e.run_st_tick;
	e.run_st_rec      = e.run_st_rec + 1;
};

/*
===========================================================================
  State
===========================================================================
*/
/*
  BUILD 24: the body moved to Zone_TrackSegs in shared/sh_zones.qc.

  It was right here and it was the only thing that was: the replay reader and the
  leaderboard each wrote `max(zone_seg) + 1` instead, which counts the end zone
  as a segment.  Two wrong reimplementations of one rule inside one build is the
  argument for a shared speller, so the rule is now in the file all three VMs
  compile and this is a name kept for its callers.
*/
float(float track) SV_TrackSegs = { return Zone_TrackSegs(track); };

void(entity e) SV_TimerClearSplits =
{
	local float i, base;
	if (e.run_t_slot < 0)
		return;
	base = e.run_t_slot * FS_MAXSPLITS;
	for (i = 0; i < FS_MAXSPLITS; i = i + 1)
		run_run_split[base + i] = 0;

	base = e.run_t_slot * FS_MAXCPS;
	for (i = 0; i < FS_MAXCPS; i = i + 1)
		run_run_cp[base + i] = 0;
};

/*
  The split row, reached from sv_saveloc.qc.

  Two accessors rather than letting the save code index run_run_split itself,
  because the bounds are three nested ifs (QuakeC's && evaluates both sides, so
  a guarded array read still reads) and having that written twice is how the two
  copies drift.
*/
float(entity e, float seg) SV_TimerGetRunSplit =
{
	if (e.run_t_slot < 0)     return 0;
	if (seg < 0)             return 0;
	if (seg >= FS_MAXSPLITS) return 0;
	return run_run_split[e.run_t_slot * FS_MAXSPLITS + seg];
};

void(entity e, float seg, float ticks) SV_TimerSetRunSplit =
{
	if (e.run_t_slot < 0)     return;
	if (seg < 0)             return;
	if (seg >= FS_MAXSPLITS) return;
	run_run_split[e.run_t_slot * FS_MAXSPLITS + seg] = ticks;
};

/*
  BUILD 23: the same pair for the CHECKPOINT row, and this closes a data-loss
  bug rather than adding a feature.

  run_run_cp[] was the one part of a run's state that a save file did not carry.
  Harmless for a LOAD, which always marks the run practice -- but `retry`
  restores everything verbatim and deliberately does NOT mark practice, because
  the map reset around you and you did not move.  So a retried run can still set
  a personal best, and SV_TimerFinish then copies this row into run_pb_cp
  wholesale.  A row that was never restored is a row of zeroes, and SV_PBSave
  writes a `cp` line only where the value is above zero -- so rewriting the file
  after such a PB emits NO cp lines at all.

  The map's entire checkpoint record, silently deleted, by beating your own time.
  Nothing prints, nothing fails, and the file that is gone is the only copy.
*/
float(entity e, float cpn) SV_TimerGetRunCP =
{
	if (e.run_t_slot < 0)  return 0;
	if (cpn < 0)          return 0;
	if (cpn >= FS_MAXCPS) return 0;
	return run_run_cp[e.run_t_slot * FS_MAXCPS + cpn];
};

void(entity e, float cpn, float ticks) SV_TimerSetRunCP =
{
	if (e.run_t_slot < 0)  return;
	if (cpn < 0)          return;
	if (cpn >= FS_MAXCPS) return;
	run_run_cp[e.run_t_slot * FS_MAXCPS + cpn] = ticks;
};

/*
  Put the clock back where a save state left it.

  BUILD 76: IT TAKES BOTH NUMBERS NOW, AND THAT MADE IT SIMPLER RATHER THAN
  HARDER -- which is worth saying plainly, because the migration was costed on
  the assumption that this function would be the expensive part.

  THE ESSAY IT REPLACES, AND WHY THE PROBLEM IS GONE.  Build 17 took the integer
  tick count here and that was wrong: a tick count was the elapsed time ROUNDED,
  because SV_TimerTicks was floor(x/tick + 0.5), so restoring from it landed the
  clock up to half a tick BEHIND where the save was taken.  The recorder stamps
  every sample with the elapsed, so the first sample after such a resume could
  carry a timestamp EARLIER than the last one already in the buffer, and a
  recording whose time runs backwards mid-file is one no reader can interpolate.
  tools/reccheck.py rejected exactly that, which is how it was found rather than
  shipped.  Build 17's answer was to store the unrounded seconds and derive the
  display from them.

  On a counted clock there is no rounding to lose.  The tick count IS the
  quantity -- an integer the mover produced -- so restoring it is exact by
  construction, and the seconds are a SECOND exact quantity rather than the
  original of which ticks were a lossy copy.  So both are restored, each into its
  own origin, and neither is derived from the other:

      run_t_starttick <- movetick now, minus the ticks the save holds
      run_t_startsec  <- ClockSec now, minus the seconds the save holds

  THE TWO ORIGINS MUST BE SET FROM ONE PAIR OF READINGS.  Taking SV_ClockSec
  twice would be harmless today (nothing advances between the two lines) and is
  exactly the kind of thing that stops being harmless later, so the reading is
  taken once into a local.

  THE FREEZE ACCUMULATORS ARE CLEARED, not carried.  A save file's `elapsed`
  already has its frozen time removed -- it is what SV_TimerElapsed returned when
  the save was written -- so carrying a frozen count into a restored run would
  subtract the same interval twice.  This is the one line of this function that a
  reader is likely to get wrong, because on the old clock there was nothing to
  clear.

  run_t_tick's early return is gone with the division it guarded.  sv_saveloc.qc
  has a note pointing at it; that note is corrected there.
*/
void(entity e, float ticks, float elapsed) SV_TimerResume =
{
	local float now;

	now = SV_ClockSec(e);

	e.run_t_startsec  = now - elapsed;
	// Patch 363: the counter restarts per map (a `retry` is a map_restart), so
	// `movetick - ticks` went negative and the run fell to the sampled clock.
	e.run_t_starttick = e.run_movetick;
	e.run_t_tickcarry = ticks;
	e.run_t_startwall = time - elapsed;     // the report's sampled side, same rebase
	e.run_t_frzsec    = 0;
	e.run_t_frzticks  = 0;
	e.run_t_lastsec   = now;
	e.run_t_lastmt    = e.run_movetick;

	/*
	  WHICH CLOCK THE RESTORED RUN IS ON IS DECIDED BY THIS ENGINE, not by the
	  file.  A save written on a counted server and loaded on a sampled one (or
	  the reverse) restores the same two numbers either way, because both origins
	  are re-based against readings taken here -- so the run continues correctly
	  in whichever unit this process can actually produce.  A save load marks the
	  run practice regardless, so no ranking decision rests on this line.
	*/
	e.run_t_clock = (e.run_movetickrate > 0);
	// Patch 363: a `retry` resumes from PutClientInServer, before the engine has
	// written this edict's mover fields -- latch on the first live packet
	// (SV_TimerFreezeFrame), not on a stale 0.
	if (!e.run_t_clock)
	{
		e.run_t_starttick = -2;
		e.run_t_resumesec = elapsed;
	}

	e.run_t_ticks = SV_TimerTicks(e);

	/*
	  If the clock is STOPPED, the latch is what the maintain re-derives from
	  every tick, so putting the clock back has to move the latch as well.

	  This is the load-while-parked path: hold 2 and tap 4/5 to walk the save
	  list without unfreezing (sv_saveloc.qc re-targets the hold rather than
	  fighting it), and the clock has to follow the save you land on.  Without
	  this line the next tick would overwrite the freshly resumed clock with the
	  elapsed the hold started at, and stepping through saves would silently
	  leave the timer showing the first one.
	*/
	if (e.run_t_frzon)
		e.run_t_frzat = elapsed;
};

/*
  The elapsed time of the run, in seconds, honest about the freeze.

  BUILD 76: SIMULATED seconds, not wall seconds -- SV_ClockSec rather than
  `time`.  This is the clock's fine-grained half: SV_TimerTicks ranks in whole
  ticks, and this is what the recorder stamps on every sample and what a save
  file carries.  Both are differences over the same counter, so they can never
  describe different runs; they are not the same number, and they are not meant
  to be.  Ticks is what the mover DID; this is what the mover CONSUMED, carry
  included, and it is monotone for the reason SV_ClockSec proves.

  ONE SUBTRACTION FOR BOTH CLOCK MODELS.  With no engine counter SV_ClockSec is
  `time` and this reduces to `time - run_t_startsec - run_t_frzsec`, which is
  build 75's number -- that build spelled it by re-deriving run_t_start on every
  frozen tick instead of accumulating the frozen interval, and the two are
  algebraically the same thing.  Accumulating is what lets the origin stop moving.

  THE FROZEN BRANCH SURVIVES, AND NOT FOR THE REASON IT USED TO.  On the old
  clock it was load-bearing because run_t_start was being rewritten every tick.
  It is no longer: run_t_frzsec absorbs exactly the interval run_t_startsec would
  have been shifted by, so the subtraction below is already constant across a
  hold.  What the branch answers now is the SECOND reason, which is older than
  the freeze and has not gone away:

  `time` is NOT THE SAME VALUE in every hook.  A client command runs under
  PR_KrimzonParseCommand, which sets time = sv.world.physicstime
  (pr_cmds.c:2508); a usercmd runs under SV_RunCmd, which sets time = sv.time
  (sv_user.c:7753).  The engine counter has the same shape of problem one layer
  down: run_movetick is advanced inside SV_RunCmd, per usercmd, while this file
  runs from SV_PostRunCmd, so a `cmd sl_save` arriving in the same packet as the
  moves can read a counter that SV_TimerFreezeFrame has not yet accounted for.
  The latch is immune to both by not being a subtraction at all.

  SO run_t_frzat IS ITS OWN FALSIFIER.  It is latched once, at the moment the
  hold starts, and never re-derived; the accumulator is maintained independently
  every packet.  If the two models disagree, the value at the thaw differs from
  the value at the freeze -- which is what `cmd timer`'s frz column shows.
*/
float(entity e) SV_TimerElapsed =
{
	if (e.run_t_frzon)
		return e.run_t_frzat;
	return SV_ClockSec(e) - e.run_t_startsec - e.run_t_frzsec;
};

/*
  Stop and start the run clock.  Both only ask; SV_TimerFreezeFrame does the work.

  THE HANDLERS MUST NOT DO ARITHMETIC.  See reason 2 on SV_TimerElapsed: these are
  called from a client command, where `time` is a different clock from the one the
  maintain and the recorder use.  Latching an elapsed here would be wrong by up to
  a server frame, every time -- and since build 76 by up to a PACKET of mover
  ticks as well, because a client command can be parsed in the same packet as the
  moves it follows and the counter has advanced past what the maintain has seen.
*/
void(entity e) SV_TimerFreeze =
{
	e.run_t_freeze = TRUE;

	/*
	  A stopped clock is not something a kept run may have.

	  On the normal path this is already true and this call does nothing: key 2
	  sends sl_load first, and applying a save state marks the run practice.  It
	  is here for the path that does not -- a bare `cmd sl_hold` from the console
	  would otherwise pause a clean run for free, which is a leaderboard hole.
	*/
	SV_TimerPractice(e);
};

void(entity e) SV_TimerThaw =
{
	e.run_t_freeze = FALSE;
};

/*
  Hold the clock still.  Called as the FIRST thing in SV_TimerFrame, once per
  usercmd, and it is the only place the freeze does arithmetic.

  BUILD 76 TURNED IT INSIDE OUT, AND THE RESULT IS SHORTER.  The clock used to be
  an ORIGIN, so stopping it meant re-deriving that origin from a latched elapsed
  on every frozen tick -- three assignments to run_t_start, in three branches, to
  maintain the invariant "run_t_start is always correct for the current `time`".
  A counted clock has no origin to chase: the hold is accounted by ADDING the
  frozen interval to an accumulator that every reader already subtracts.  So the
  origin is now written exactly twice in this file -- at the start and at a
  resume -- and nothing here touches it at all.

  THE OFF-BY-ONE PROOF, RE-DERIVED IN TICKS, because the old one was a proof
  about an origin and does not carry over.

  Let T_p be the packet the press is processed on and T_r the release.  The
  accumulate below runs BEFORE the branch that sets run_t_frzon, so the delta
  banked on T_p covers the ticks up to and including T_p and is NOT counted as
  frozen; the delta banked on T_r runs while run_t_frzon is still true and IS.
  So the ticks removed from the run are T_p+1 .. T_r: exactly T_r - T_p of them.
  The player is pinned (MOVETYPE_NONE) for T_p .. T_r-1, which is also T_r - T_p.
  Equal, in opposite directions, so the net drift over any press/release pair is
  ZERO ticks -- for any hold length, at any tick rate, and now for the same
  reason in both units, since run_t_frzsec is accumulated from the same delta on
  the same line.

  The old proof's corollary still holds and is now exact rather than nearly:
  the recording needs no marker for the gap, because the sample before the freeze
  and the sample after it differ by exactly the simulated time that was not
  frozen.  Strictly increasing, no hole in run time, no reader has to know it
  happened.

  The final `run_t_frzat = 0` gives a property worth having: a run that STARTS
  while you are parked pins at the tick it started on -- 0:00.015, since the
  maintain runs before the zone logic that calls SV_TimerStart and so cannot
  latch until the tick after -- and stays there until you let go.  That is
  reachable: a save's arm latch is restored verbatim, but you are placed at the
  save's origin, which may be outside the box you were armed in.
*/
void(entity e) SV_TimerFreezeFrame =
{
	local float now;

	/*
	  BUILD 74/76, and it must run on EVERY call, above the branch, for two
	  reasons: the deltas need a base whether the freeze is on or not, and the
	  off-by-one proof above depends on this sitting before run_t_frzon is set.

	  THE FREEZE IS NOT FREE ON A COUNTED CLOCK.  The mover keeps running ticks
	  for a pinned player -- PM_PlayerMove reaches the Source mover BEFORE any
	  pm_type test, and the test that recognises MOVETYPE_NONE is inside
	  PMSrc_Tick, after the tick is already spent -- so the ticks of a save-lock
	  hold are counted unless something subtracts them.  This is that something,
	  and since build 76 it is the ONLY thing: there is no origin being shuffled
	  underneath it any more.

	  BOTH UNITS, FROM ONE DELTA, ON ADJACENT LINES.  The run has two readouts
	  over one counter -- integer ticks that rank and seconds that timestamp the
	  recording -- and the freeze has to come off both.  Deriving one from the
	  other (frzsec = frzticks * rate) would put a rounding error into the .rec's
	  `t` column on every hold, which is the backwards-join class of defect
	  reccheck.py exists to catch.  Written as two accumulations of the same
	  interval instead, so they cannot disagree.

	  A DELTA, NOT AN INCREMENT.  Everything in this file runs once per PACKET
	  (PlayerPostThink is called from the engine's SV_PostRunCmd, which sits
	  outside its per-usercmd loop), so one call can cover several usercmds and
	  therefore several ticks.  `+ 1` would undercount a hold on a lagging client
	  and the error would be invisible.  Differencing is right whatever the packet
	  contained, which is the same argument the delta form wins on everywhere else
	  in this file.
	*/
	if (e.run_t_starttick == -2)            // Patch 363: see SV_TimerResume
	if (e.run_movetickrate > 0)
	{
		e.run_t_starttick = e.run_movetick;
		e.run_t_clock = TRUE;
		// ...and the seconds' origin with it: at the resume SV_ClockSec was still
		// `time`, a different clock from the mover seconds it reads from now on.
		e.run_t_startsec = SV_ClockSec(e) - e.run_t_resumesec;
		e.run_t_startwall = time - e.run_t_resumesec;
	}

	now = SV_ClockSec(e);
	if (e.run_t_frzon && e.run_t_starttick >= 0)
	{
		e.run_t_frzticks = e.run_t_frzticks + (e.run_movetick - e.run_t_lastmt);
		e.run_t_frzsec   = e.run_t_frzsec   + (now - e.run_t_lastsec);
	}
	e.run_t_lastmt  = e.run_movetick;
	e.run_t_lastsec = now;

	if (e.run_t_freeze && e.run_t_state == TS_RUNNING)
	{
		/*
		  LATCHED ONCE AND NEVER RE-DERIVED.  On the old clock this assignment
		  had a partner on the next line rewriting the origin every tick; there
		  is no partner now.  What the latch buys is the hook problem, not the
		  freeze: a `cmd sl_save` can be parsed in the same packet as the moves
		  it follows, so a reader that subtracted live would see a counter this
		  function has not yet accounted for.  See SV_TimerElapsed.
		*/
		if (!e.run_t_frzon)
		{
			e.run_t_frzon = TRUE;
			e.run_t_frzat = now - e.run_t_startsec - e.run_t_frzsec;
		}
		e.run_t_flags = e.run_t_flags | TF_FROZEN;
		return;
	}

	// Thawing, or the state left RUNNING underneath us (a void, a finish).  The
	// accumulator has already taken this packet's frozen interval above, so the
	// tick the player moves again is the first one counted with nothing to
	// re-derive -- which is the whole of what build 75 needed three branches for.
	e.run_t_frzon = FALSE;
	e.run_t_frzat = 0;
	e.run_t_flags = e.run_t_flags - (e.run_t_flags & TF_FROZEN);
};

/*
  The stopped clock's maintain, and the sibling of the one above in every way
  that matters.  Build 19.

  TWO JOBS, and the second is the one that is easy to miss.  It recomputes
  TF_STOPPED, which cannot be written where the fact is discovered because
  SV_TimerVoid's own SV_TimerIdle and the SV_TimerArm that follows it both zero
  run_t_flags.  AND it re-writes run_t_ticks, for exactly the same reason: the arm
  zeroes that too, one tick after the void latched it.  A version that only
  mirrored the flag would draw a grey 0:00.000, which is worse than what we had.

  Runs while ARMED or IDLE only.  RUNNING and FINISHED own the readout and clear
  the latch -- a finished run must show its finish time, not the last thing that
  was cancelled.
*/
void(entity e) SV_TimerStopFrame =
{
	if (e.run_t_stopat > 0)
	{
		if (e.run_t_state == TS_ARMED || e.run_t_state == TS_IDLE)
		{
			e.run_t_ticks = e.run_t_stopat;
			e.run_t_flags = e.run_t_flags | TF_STOPPED;
			return;
		}
		e.run_t_stopat = 0;
	}
	e.run_t_flags = e.run_t_flags - (e.run_t_flags & TF_STOPPED);
};

/*
  Stop the clock HERE, and make it visible on this tick.  Build 20.

  The maintain above runs at the TOP of SV_TimerFrame, and every site that can
  decide "the run stopped" runs below it -- so a bare `run_t_stopat = ticks` is
  correct but one tick late, and that one tick is a transmitted snapshot reading
  0:00.000.  A readout that blinks to zero and then back to the stopped time is
  worse than one that never stopped, because it looks like a bug rather than a
  feature.  So this writes all three, and the maintain takes over next tick.

  Call it AFTER the arm, never before: SV_TimerArm zeroes run_t_flags, which
  would take TF_STOPPED with it.
*/
void(entity e, float ticks) SV_TimerStopAt =
{
	e.run_t_stopat = ticks;
	e.run_t_ticks  = ticks;
	e.run_t_flags  = e.run_t_flags | TF_STOPPED;
};

void(entity e) SV_TimerIdle =
{
	// Patch 382: every funnel that ends a run releases a spectate first.
	if (e.run_sp_open)
		dprint(sprintf("spectate: %s's run torn down inside a window\n", e.netname));
	SV_RecDiscard(e);
	e.run_t_state    = TS_IDLE;
	e.run_t_ticks    = 0;
	e.run_t_split    = 0;
	e.run_t_delta    = 0;
	e.run_t_flags    = 0;
	e.run_t_startseg = 0;
	// Build 57: an idle timer has no leg.  run_t_wantstage1 is NOT cleared: it is
	// the player's request rather than a fact about this attempt, and `!r` after a
	// voided stage-1 run has to find it standing.
	e.run_t_stagerun = FALSE;
	e.run_t_seg      = 0;
	e.run_t_pendarm  = -1;

	e.run_t_cpmax    = 0;
	e.run_t_cpn      = 0;
	e.run_t_cpticks  = 0;
	e.run_t_cpdelta  = 0;

	// Build 21.  Tearing the attempt down takes its forgivable taint with it.
	// Both the set and the clear are TS_ARMED-gated so this cannot be reached
	// with it still set today -- it is here because this function's job is to
	// leave nothing behind, and a taint bit that outlives its attempt is the
	// exact shape of the bug run_t_dirty's own essay was written about.
	e.run_t_hopped   = 0;

	// Build 44, and for the same reason again.  run_t_said is a statement about
	// what the line above was told to say, so it goes with it -- an attempt torn
	// down while `cheated` would otherwise leave the next one unable to report
	// anything gentler than that, silently, for the rest of the map.
	e.run_t_said     = 0;

	// Build 43, and for that same reason.  A stage cannot outlive the run it was
	// a leg of, and `cmd timer` reporting `stage: leg 3 fails 2` about a player
	// standing idle in a start box is a report that lies.
	e.run_st_seg     = -1;
	e.run_st_armed   = FALSE;
	e.run_st_hold    = FALSE;
	e.run_st_fails   = 0;
	e.run_st_tp      = 0;
	e.run_st_zseg    = -1;   // and a map change reloads the zone table under it

	/*
	  BUILD 75, AND THE LIVE ARM ON THE FLEET IS WHAT FOUND IT -- build 74 shipped
	  the hazard it had just written an essay about.

	  run_t_starttick's own comment says 0 is a LEGAL value of the counter, because
	  run_movetick is reset per MAP and 0 is what every player's reads for the first
	  seconds after a load; that is the whole reason the sentinel is -1 rather than
	  0.  But the sentinel was written ONLY by SV_TimerArm, so between spawning and
	  the first arm the field held the QC default -- 0 -- and SV_TickCounted read
	  that as a latch taken at the map load.  Measured on lobby 4 over the real
	  network, on a player standing still who had never armed anything:

	      tick: counted 0 sampled 9033 gap 9033

	  A confident number, to four significant figures, about a run that does not
	  exist.  Nothing consumes SV_TickCounted yet so nothing was ranked wrongly --
	  but that is luck, not design, and an instrument that answers when it has no
	  reading is the sv_mapcheck failure exactly: a comparison whose two sides are
	  not comparable, reporting anyway.

	  It belongs HERE rather than in SV_TickReport.  Tearing the attempt down is
	  what establishes "there is no run", which is what every other line in this
	  function is for, and fixing it at the reader would leave the next consumer to
	  rediscover it.
	*/
	e.run_t_starttick = -1;
	e.run_t_tickcarry = 0;
	e.run_t_frzticks  = 0;
	e.run_ms_sessions = 0;
};

/*
  Abort.  Called by every teleport (SV_ZoneMove, the chat commands,
  PutClientInServer) and by a cancel zone.

  Silent when nothing was running, because the teleports call it
  unconditionally and "run cancelled" on every !r would be noise.
*/
void(entity e, string why) SV_TimerVoid =
{
	if (e.run_t_state == TS_RUNNING)
		sprint(e, PRINT_HIGH, sprintf("^3run cancelled^7 (%s)\n", why));

	/*
	  BUILD 19: keep the time on screen, greyed, instead of snapping to zero.

	  Every way a run stops without finishing arrives here -- `!r` on a linear
	  map or at stage 1, `!m`, `!s N`, a cancel zone, a map teleport -- and until
	  now all of them left the readout at 0:00.000, so the one number you wanted
	  (how far did I get) was the one that was thrown away.  `!r` MID-RUN on a
	  staged map does not come through here at all: that is SV_TimerRestartSeg,
	  which keeps the clock running, and is unchanged.

	  run_t_ticks and not SV_TimerTicks(e) -- see the field's own comment.  Taken
	  BEFORE SV_TimerIdle, which zeroes it.
	*/
	if (e.run_t_state == TS_RUNNING)
		e.run_t_stopat = e.run_t_ticks;

	SV_TimerIdle(e);

	// Clear the occupancy latches too, so arriving back inside the same zone
	// counts as ENTERING it.  Without this a `!r` into the start you were
	// already standing in would leave az unchanged and never re-arm.
	e.run_t_azone = e.run_t_evzone = e.run_t_armzone = e.run_t_cpzone = -1;
};

/*
  "I did not travel here, I was put here."

  Called after every setorigin that is not movement -- the zone teleports, the
  save-locks, the spawn.  Without it the next tick's swept test would run a
  segment from wherever you were to wherever you are and fire every stage and
  end zone on the line between them.
*/
void(entity e) SV_TimerWarped =
{
	e.run_t_lastorg = e.origin;

	/*
	  The padding ring is the APPROACH, and you did not approach.

	  SV_RecPad keeps a rolling ~3.8 seconds of where you were, and SV_RecOpen
	  writes it into the front of a run as negative-t lead-in.  It was never
	  cleared on a teleport, so after a save-lock load the ring still held the
	  run-up to somewhere else entirely -- and the next run would open with a
	  few seconds of a DIFFERENT PLACE stamped as its own lead-in, at plausible
	  timestamps.  Nothing reports that; it just quietly makes the front of the
	  file fiction.

	  Pre-existing, and found while stopping the clock: a hold that skips
	  padding preserves the stale samples longer rather than fixing them, so
	  the two belong in the same build.
	*/
	e.rec_pad_len = 0;
	e.rec_pad_head = 0;

	/*
	  BUILD 43 -- COUNT IT, AND COUNT IT HERE BECAUSE THIS IS THE ONE FUNNEL.

	  A DIAGNOSTIC AND NOT A RULE.  The stage fail rule fires on re-entering the
	  boundary box, which is what walking back up does.  A map whose fall-off
	  trigger teleports you to somewhere OUTSIDE that box fires nothing at all and
	  the stage clock runs straight through the failed attempt -- i.e. exactly
	  build 42, so the change is never worse than today, which is the property
	  that matters.  But it is silent, and a silent non-event looks identical to a
	  broken detector.

	  So `cmd timer` can say "teleports 3, fails 0" and name the map as one whose
	  zone file wants a stage region covering the ledge.  That edit is the correct
	  fix; a proximity heuristic is not, and nothing like one exists in this tree.

	  Gated on a stage being OPEN and the clock RUNNING, which keeps the spawn out
	  of the count -- it reaches here with no run going.  A save-lock LOAD mid
	  stage DOES count, and correctly: it is a teleport taken during a stage.

	  AND GATED ON NOT GHOSTING, which is not a nicety.  SV_TimerFrame's ghost
	  branch calls this EVERY TICK, deliberately, so the swept segment travels
	  with the body one tick at a time -- see the essay there.  Without this line
	  a ten-second ghost would report six hundred and sixty teleports.
	*/
	if (e.run_t_state == TS_RUNNING)
	if (e.run_st_seg >= 0)
	if (!e.rec_gh_on)
		e.run_st_tp = e.run_st_tp + 1;
};

/*
  Declare a ghost window in the recording.  Build 30.

  Called from both edges by SV_GhostSet.  Two things happen and they answer two
  different readers:

    the RECORD goes into the sample stream, so a reader walking the run in order
    knows exactly which samples were taken with nobody steering;

    TF_GHOST goes into run_t_flags, which SV_RecClose masks and writes into the
    header's reserved `flags` line -- so a reader that only wants to know
    whether the run contains a ghost at all never has to scan.

  THE BIT IS NOT CLEARED ON THE WAY OUT.  "This run contained a ghost" stays
  true for the rest of the attempt however many times you toggle; it is
  SV_TimerArm's zeroing of run_t_flags that ends it, which is right, because
  arming is what begins a new attempt.  Exactly the lifetime TF_PRACTICE has,
  and for exactly the same reason -- but NOT the same meaning: this one is a
  marker and does not imply TF_PRACTICE.  See the essay in sh_defs.qc.

  Nothing is written when no run is live.  There is no stream to put a record
  in, and a ghost outside a run is not a fact about any recording.
*/
void(entity e, float on) SV_TimerGhostMark =
{
	if (e.run_t_state != TS_RUNNING)
		return;

	if (on)
	{
		e.run_t_flags  = e.run_t_flags | TF_GHOST;
		// Build 43: and the stage.  The EDGE half; SV_TimerFrame's ghost branch
		// sets it at level every tick, so a ghost that spans a boundary taints
		// both stages rather than neither.  See the ghost rule in SV_StageQualifies.
		e.run_st_ghost = TRUE;
	}

	if (SV_RecLive(e))
		SV_RecPut(e, sprintf("ghost %d %d", on ? 1 : 0, SV_TimerTicks(e)));
};

// Patch 382: the pm_source state the engine carried out of the last move, for the
// log -- a held body's must read the same at both edges (`*pmstate`, Patch 346).
string(entity e) SV_SpecPMState =
{
	local float i;
	local string s, c;

	s = "";
	for (i = 0; i < 8; i = i + 1)
	{
		c = infokey(e, sprintf("*pmstate%g", i));
		if (c == "")
			break;
		s = strcat(s, c);
	}
	return s;
};

// Patch 382: a spectate window's edge (the `spec` record, grammar block).  Only a
// line that LANDED opens a window; the 0 is owed only for one that did.
void(entity e, float on, string why) SV_TimerSpecMark =
{
	local float was, fl;
	local string l;

	if (!on)
	if (!e.run_sp_open)
		return;
	e.run_sp_open = FALSE;
	if (e.run_t_state != TS_RUNNING || !SV_RecLive(e))
	{
		if (!on)
			dprint(sprintf("spectate: %s's `spec 0` has no recording left to go in\n", e.netname));
		return;
	}

	fl = (e.flags & FL_ONGROUND) ? 1 : 0;
	l = strcat(sprintf("spec %d %.9g %.9g %.9g ", on ? 1 : 0, SV_TimerTicks(e),
	                   e.run_movetick, e.run_movecarry),
	           sprintf("%.9v %.9v %d %.3f", e.origin, e.velocity, fl, time));
	if (!on)
		l = strcat(l, " ", why);
	was = e.rec_rec_lines;
	SV_RecPut(e, l);
	if (on)
		e.run_sp_open = (e.rec_rec_lines != was);
	if (cvar("developer"))
		dprint(sprintf("spectate: %s %s\n  pmstate %s\n", e.netname, l, SV_SpecPMState(e)));
};

/*
  "This attempt is not clean."

  THE LATCH IS THE POINT, and it is what build 15 added.  Before it, this
  function only did anything while the clock was already RUNNING -- so the one
  gesture that most obviously invalidates a time was the one it could not mark:
  noclip into the start zone, drop out of noclip, walk out, and the timer started
  a pristine run from a position you flew to.  Reported exactly that way.

  The state machine is why.  Entering the start zone ARMS (SV_TimerArm), which
  zeroes run_t_flags; leaving it STARTS (SV_TimerStart).  Anything written to
  run_t_flags between those two is thrown away, and everything about a noclip into
  the zone happens between those two.

  So the taint lives outside run_t_flags, in run_t_dirty, which survives the arm and
  is consumed by the start.  SV_TimerArm is the ONE place that clears it, and it
  clears it from the movetype at that instant -- so arming while noclipping stays
  dirty and a clean `!r` back to the start genuinely resets it.
*/
/*
  BUILD 44: SAY SO, IF THIS GESTURE MADE THE RUN WORSE THAN IT HAS EVER BEEN.

  AGAINST A REMEMBERED HIGH-WATER MARK, not against the class this call started
  with, and the two are not the same test.  Two scripted traces settled that:

    a before/after comparison inside SV_TimerPractice went SILENT for both
    siblings, because they set their bit first and the comparison then measured
    a value against itself -- the run went clean -> segmented -> cheated with
    nothing on screen at all;

    moving the comparison out to the siblings printed TWICE under run_class 0,
    where the sibling sets no bit and both it and the funnel see the same
    upgrade.

  A high-water mark answers both and is shorter than either.  It also answers a
  third case that neither would have: a save-lock LOAD restores run_t_flags from
  the file, so the class can go BACKWARDS mid-attempt and a pairwise test would
  then announce the same word a second time as it climbed back.

  run_t_said is cleared where run_t_flags is -- by the arm and by the idle -- so a
  fresh attempt can be told its own bad news.
*/
void(entity e) SV_TimerClassSay =
{
	local float now;

	now = FS_RunClass(e.run_t_flags);

	if (e.run_t_state != TS_RUNNING)
		return;
	if (now <= e.run_t_said)
		return;

	e.run_t_said = now;
	sprint(e, PRINT_HIGH,
	       sprintf("^3%s run^7 -- this run will not be saved\n",
	               FS_RunClassName(now)));
};

void(entity e) SV_TimerPractice =
{
	e.run_t_dirty = TRUE;

	/*
	  BUILD 43: AND THE STAGE, THROUGH THE SAME FUNNEL.

	  Every gesture that dirties an attempt also dirties the stage it happens in,
	  and putting that here rather than at each call site is what makes the two
	  impossible to get out of step -- the argument SV_TimerPractice's own
	  existence makes about TF_PRACTICE.  The DIFFERENCE between the two fields is
	  entirely in when they are cleared: run_t_dirty survives to the next arm,
	  run_st_dirty dies at the next boundary.

	  THIS IS THE EDGE HALF ONLY.  A watcher that fires once, in stage 2, and a
	  state that is still true in stage 3 would leave stage 3 clean -- so the two
	  watchers ALSO set run_st_dirty at level, every tick, and this call is what
	  they do on top of that for the run.  See SV_NoclipWatch.
	*/
	e.run_st_dirty = TRUE;

	/*
	  BUILD 44: THE PRINT FIRES ON A CLASS UPGRADE, NOT ON THE FIRST TAINT.

	  It used to be gated on `!(run_t_flags & TF_PRACTICE)` -- print once, the
	  first time anything dirties the attempt.  With three classes that is a hole
	  you can walk into: load a save (segmented, printed), then noclip.  The cheat
	  bit gets set, the umbrella is already up, and the player is never told the
	  run went from `segmented` to `cheated`.  A word on screen that is one gesture
	  out of date about the worst thing you have done is worse than none.

	  THE SIBLINGS BELOW SET THEIR BIT BEFORE CALLING THIS, so this one line
	  reports all three classes and neither of them needs a print of its own.
	*/
	e.run_t_flags = e.run_t_flags | TF_PRACTICE;
	SV_TimerClassSay(e);
};

/*
  A SAVE STATE WAS USED.  Build 44, and it is the gesture the category is named
  after: "stitched runs are legit settings but save locked".

  BOTH ITS CALLERS ALREADY TAINTED, which is worth stating because the first cut
  of this build assumed otherwise about one of them.  A save-lock LOAD marks
  practice through SV_SaveApplyState and always has; a save-lock HOLD marks it
  through SV_TimerFreeze, which build 18 added for exactly this reason -- "a
  stopped clock is not something a kept run may have".  So this function is a
  pure REFINEMENT of an existing taint, not a new one, and `run_class 0`
  degrades it to the SV_TimerPractice call that was there before with no guard
  needed at either site.

  THE BIT GOES ON BEFORE THE FUNNEL, so the word the player is shown is
  `segmented` and not `practice`.  That ordering is the whole of what makes
  SV_TimerPractice's single print cover all three classes.

  It does NOT set TF_SHADOW.  That is the narrower claim -- the clock and the
  checkpoints came out of the save too -- and only one of the two callers can
  make it.  See SV_SaveApplyState.
*/
void(entity e) SV_TimerStitched =
{
	if (run_t_runclass)
	{
		e.run_t_flags   = e.run_t_flags | TF_SEGMENT;
		e.run_st_stitch = TRUE;
	}
	SV_TimerPractice(e);
};

/*
  NOCLIP, setpos, OR sv_cheats.  Build 44.

  THE LATCH IS WHY THIS IS NOT JUST A FLAG WRITE.  run_t_cheat lives outside
  run_t_flags and survives SV_TimerArm for the identical reason run_t_dirty does --
  see its field essay -- and SV_TimerStart consumes the pair.  Without it,
  noclipping into a start box and walking out would produce a run whose header
  says `clean`, which is the exact bug build 15 fixed for TF_PRACTICE and would
  have been re-introduced one class down.

  run_st_cheat is set here as well as at level by the two watchers, and the
  overlap is deliberate: setpos is an EVENT with no state behind it, so nothing
  would ever set the per-stage bit for it if this line were left to the watchers.
*/
void(entity e) SV_TimerCheat =
{
	if (run_t_runclass)
	{
		e.run_t_cheat  = TRUE;
		e.run_t_flags  = e.run_t_flags | TF_CHEAT;
		e.run_st_cheat = TRUE;
	}
	SV_TimerPractice(e);
};

/*
  WAS THIS RUN'S RAW INPUT JOURNAL TAKEN?  Build 58.

  DELIBERATELY NOT THROUGH SV_TimerPractice.  Every other function in this block
  funnels into it because every other one describes something the player DID to
  the world.  This one describes a missing recording, the run itself is clean,
  and routing it through the funnel would print `practice` at somebody who
  played a perfectly ordinary run.  See TF_NOJOURNAL in sh_defs.qc.

  A LATCH, CALLED TWICE.  Once at SV_TimerStart so the bit is set before
  SV_RecOpen writes the header, and once at the finish so a `rec_hid 0` typed
  mid-run is caught too -- turning the journal off half way through leaves a
  file that covers half a run, which is not evidence.  It only ever sets, never
  clears, because turning the journal back ON mid-run does not retroactively
  record the part that was missed.

  BUILD 79: THE SOURCE IS THE EVENT, AND SILENCE IS A FAULT.  What follows is
  the build-58 reasoning this replaced, kept because it explains a rule that is
  still in force one channel over -- SV_ProfileKeyBroken reads the key the same
  careful way, for diagnostics.

    ONLY A LITERAL "0", and this is the important line in the function.  infokey
    returns "" for a key the client has never sent -- an older client, a client
    that connected two frames ago, a client whose CSQC has not run a frame yet --
    and "" is not a claim that no journal exists.  Reading it as one would stamp
    this bit on a run that has a perfectly good .hid sitting beside it, and the
    player would be shown a statement about their own run that is false.
    Unknown stays unknown; the board can decline to rank it quietly, which costs
    a player nothing they can see.  See the essay on TF_NOJOURNAL.

  THAT WAS RIGHT ABOUT THE KEY AND IT IS WHY THE KEY HAD TO GO.  A reader this
  careful is a reader a player can talk to: `rec_hid 0` then `setinfo rechid 1`
  is one console line that turns the careful "" handling into a forged "1", and
  the send-on-change cache in Rec_HidReport means CSQC never contradicts it.  The
  build-79 block in sh_defs.qc is the long version.

  THE THREE UNKNOWNS ABOVE COLLAPSE INTO ONE FAULT, and the collapse is honest
  rather than conservative.  "Older client", "connected two frames ago" and "CSQC
  has not run a frame yet" are all clients that have written no .hid, because
  Rec_HidBegin is CSQC -- so TF_NOJOURNAL is the true statement about every one
  of them.  This is not the profile's trade, where silence had to be faulted
  despite possibly being honest; here silence and the fault describe the same
  state.  It is still a quiet demotion and still not an accusation.

  NOT GATED ON run_t_runclass, unlike the three above it, and the difference is
  deliberate.  That switch bisects build 44's CLASSIFICATION code, and this bit
  is not a classification -- but the stronger reason is the rule its own essay
  states about run_cheatwatch: a switch that stops the server watching must not
  quietly produce runs that look clean, so it marks every run instead of none.
  Gating an evidence bit on a development switch would be exactly the bypass
  that essay refuses.
*/
/*
  THE RULE, SPLIT OUT PURE.  Build 79, on the SV_RulesetBroken (p313) and
  SV_ProfileBroken (build 72) precedent, and for their harness reason rather
  than for tidiness: a run cannot be FINISHED from a config on a zoned map --
  zone_goto voids and setpos taints -- see build 83's note -- so a rule that existed
  only inside the latch could not be checked headlessly at all.  Split out,
  `cmd timer` reports a live `would` beside the latched bit, with one copy of the
  rule and no side effect from asking.

  It is two lines and it is still worth splitting.  The two facts it folds
  together -- never reported, and reported no -- reach the same verdict today,
  and a later rule that needs to tell them apart will find them named.
*/
float(entity e) SV_JournalBroken =
{
	// Never reported.  Not "unknown" -- no CSQC means no Rec_HidBegin, so there
	// is no .hid for this attempt whatever the userinfo key says.
	if (e.run_t_jev == 0)
		return TRUE;

	// Reported, and the answer was no.
	if (!e.run_t_jevhid)
		return TRUE;

	return FALSE;
};

void(entity e) SV_TimerJournal =
{
	// Only ever sets, never clears -- see the latch note above.
	if (SV_JournalBroken(e))
		e.run_t_flags = e.run_t_flags | TF_NOJOURNAL;
};

/*
  THE CLIENT'S CSQC REPORTING ITS INPUT STACK.  Build 78.

  THE NAME IS THE INTERFACE AND NOTHING CHECKS IT.  The engine builds
  "CSEv_" + the name CSQC passed + one letter per argument (sv_user.c:8613-8621)
  and looks that string up; a mismatch prints `qcrequest "..." not supported` to
  that client and returns.  So this function's SPELLING is load-bearing in a way
  no compiler on either side can verify, and the partner is the sendevent() call
  in cl_replay.qc's Rec_ProfileReport.  Change one and you must change the other.

  SIX FLOATS IS THE CEILING, NOT A CHOICE -- sendevent takes six arguments -- and
  the grammar has seven fields.  The version is the one left out, because it is
  already carried by the signature: a seventh field would ship as
  CSEv_inprof_fffffff, a different function name, which an older server simply
  does not have and answers as silence.  That is the version check, for free and
  with no way to get it wrong.  If the payload ever needs more than six, pack
  them into vectors ("vvf" is nine) rather than dropping a field.

  NO VALIDATION, DELIBERATELY.  Everything here is compared and nothing is
  indexed, so a hostile value can only make FS_ProfileBroken say TRUE, which is
  the demoting direction.  A client that can reach this function with a lie in
  it has already patched its engine or its protocol, which is T4 and outside
  what this layer claims.

  `self` IS THE PLAYER: the engine assigns it before the call (sv_user.c:8644).
*/
void(float have, float raw, float filt, float acc, float bad, float grant)
	CSEv_inprof_ffffff =
{
	self.run_t_pev      = IP_VERSION;
	self.run_t_pevhave  = have;
	self.run_t_pevraw   = raw;
	self.run_t_pevfilt  = filt;
	self.run_t_pevacc   = acc;
	self.run_t_pevbad   = bad;
	self.run_t_pevgrant = grant;
};

/*
  THE CLIENT'S CSQC REPORTING WHETHER ITS JOURNAL IS RUNNING.  Build 79.

  The partner is sendevent("rechid", "f", v) in cl_replay.qc's Rec_HidReport, and
  the spelling is load-bearing in exactly the way CSEv_inprof_ffffff's is: the
  engine composes "CSEv_" + name + one letter per argument and looks the string
  up, so nothing on either side of this pairing is checked by a compiler.  Change
  one and you must change the other.  The failure mode is the safe one -- every
  client falls to the silence rule and every run reads nojournal 1.

  ONE FLOAT BECAUSE THERE IS ONE FACT.  It is Rec_HidOK(), not cvar("rec_hid"),
  so a run declined for want of consent reports the same 0 as one declined by the
  switch -- the question is "will a journal exist for this run" and both answers
  to it are no.  That was already true of the userinfo key and is not new here.

  THE PRESENCE FLAG IS SET FROM A LITERAL, NOT FROM THE PAYLOAD.  `hid` is 0 on
  an honest client that is simply not journalling, so assigning it to run_t_jev
  would make an honest "no" indistinguishable from silence -- and silence and
  "no" happen to reach the same verdict here, which is exactly what would keep
  the mistake invisible until some later rule needed to tell them apart.

  `self` IS THE PLAYER: the engine assigns it before the call (sv_user.c:8644).
*/
void(float hid) CSEv_rechid_f =
{
	self.run_t_jev    = TRUE;
	self.run_t_jevhid = hid;
};

/*
  ...and the other half of that, which is the half that is easy to forget.

  THE EDICT OUTLIVES THE PLAYER.  The engine hands slot N to whoever connects
  next, and a report is a fact about a CLIENT, so without this a new player
  inherits the last one's profile -- and the direction that matters is the
  cheap one: they inherit a CLEAN profile, run_t_pev reads non-zero, the silence
  rule never fires, and a run nobody checked ranks.

  Called from both ends of a connection rather than just one.  ClientConnect is
  the authoritative reset (a new player has told us nothing yet); ClientDisconnect
  is belt and braces and keeps an idle slot honest to anything that inspects it
  in between.  SV_TouchForget is the same act for the same reason on the trigger
  bits and the two sit together at the call site.

  BUILD 79 WIDENED IT AND RENAMED IT, and the rename is the point rather than
  tidiness.  It was SV_ProfileForget, which was an accurate name for a function
  that cleared one report and a dangerous one for a tree that was about to have
  two: the next reader adds a third CSQC report, finds a function named after the
  first one, and writes a second forget beside it -- and then there are two lists
  to keep in step, which is how the field that gets missed gets missed.  One
  function, named for the class of thing rather than for its first member, and
  the rule is stated here: EVERY FIELD A CSEv_ HANDLER IN THIS FILE WRITES IS
  CLEARED IN THIS FUNCTION.  There is no second place.
*/
void(entity e) SV_CSQCForget =
{
	e.run_t_pev      = 0;
	e.run_t_pevhave  = 0;
	e.run_t_pevraw   = 0;
	e.run_t_pevfilt  = 0;
	e.run_t_pevacc   = 0;
	e.run_t_pevbad   = 0;
	e.run_t_pevgrant = 0;

	e.run_t_jev      = 0;
	e.run_t_jevhid   = 0;
};

/*
  WHAT THE USERINFO KEY ALONE WOULD SAY.  Build 78.  DIAGNOSTIC ONLY.

  NOTHING DECIDES ON THIS FUNCTION AND NOTHING MAY.  It exists so `cmd timer`
  can print what the client's `inprof` key claims BESIDE what its CSQC actually
  reported, because the two differing is the signature of an attempted forgery
  and there is nowhere else it would ever be visible.  Build 77 decided on this
  key; build 78 does not, and the sendevent block in sh_defs.qc says why.

  IT IS THE SNAPSHOT HALF ONLY.  The `bad` counter is deliberately not read
  here: run_t_pbad is latched from the EVENT now, and differencing a key's
  counter against an event's latch would be comparing two channels that are
  allowed to disagree -- the key is one console line away from saying anything.

  The version/field-count handling is unchanged and still goes through
  FS_ProfileFields, so a v1 key still reads for the four facts it carries.  That
  is not vestigial: this is the reader that tells you what an old client, or a
  forger, is putting on the wire.
*/
float(entity e) SV_ProfileKeyBroken =
{
	local string s;
	local float n, nf, grant;

	s = infokey(e, "inprof");
	if (s == "")
		return FALSE;

	n = tokenize(s);
	if (n < 1)
		return FALSE;
	nf = FS_ProfileFields(stof(argv(0)));
	if (nf == 0)
		return FALSE;
	if (n < nf)
		return FALSE;

	// Assigned, never computed: fteqcc evaluates both sides of ?: and argv(6)
	// on a six-field key is "", whose stof is 0 -- the FAULT value, not the
	// unknown.  See the build-77 note this was lifted from.
	grant = -1;
	if (nf >= 7)
		grant = stof(argv(6));

	return FS_ProfileBroken(stof(argv(1)), stof(argv(2)),
	                        stof(argv(3)), stof(argv(4)), grant);
};

/*
  CAN THIS RUN'S AIM EVIDENCE BE CHECKED AT ALL?  Build 72.  TF_NOPROFILE.

  A PURE PREDICATE, ON THE SV_RulesetBroken PRECEDENT (p313), and for the same
  harness reason rather than for tidiness: a run cannot be FINISHED from a config
  on a zoned map -- zone_goto voids and setpos taints -- see build 83's note -- so a
  rule that existed only inside the latch could not be checked headlessly at all.
  Split out, `cmd timer` can report a live `wouldprof` beside the latched bit,
  with one copy of the rule and no side effect from asking.

  EVERY EARLY RETURN HERE IS "UNKNOWN", AND UNKNOWN IS RANKABLE.  There are four
  of them and they are the whole safety of this function:

    no key          an older client, or a client whose CSQC has not run a frame
                    yet.  infokey returns "" and "" is not a claim.
    short key       a grammar this build cannot read.  Taking the fields it
                    recognises would be reading field 3 of a future key as
                    m_filter because that is where m_filter used to sit.
    wrong version   the same, said explicitly.
    bit clear in    the cvar does not exist on that client.  in_rawinput is
    `have`          registered in in_win.c ONLY, so this is every Linux, macOS
                    and SDL player, and reading their missing cvar as 0 would
                    demote all of them forever.  See TF_NOPROFILE in sh_defs.qc.

  THE TESTS ARE ASYMMETRIC ON PURPOSE.  raw must be POSITIVE to pass, while
  filter and accel must be non-zero to fail.  A future in_rawinput 2 is still raw
  input and still passes; an m_accel of 0.0001 is still a non-linear function
  between the counts and the angle and still fails.  Each test is written the way
  the cvar it reads actually behaves rather than to a house style.
*/
float(entity e) SV_ProfileBroken =
{
	/*
	  BUILD 78: THE SOURCE IS THE EVENT, AND SILENCE IS A FAULT.

	  This replaces a read of the `inprof` userinfo key, and the swap is the
	  whole of build 78 -- the numbers are the same numbers, but a userinfo key
	  is one `setinfo` away from saying anything and a qcrequest is not.  The
	  long version is the sendevent block in sh_defs.qc.

	  THE FOURTH "UNKNOWN" OF THE BUILD-72 LIST BELOW HAS BECOME A FAULT AND THE
	  OTHER THREE HAVE NOT.  "No key" used to mean unknown, and unknown is
	  rankable; "no event" means the only witness that cannot be silenced from a
	  console has not spoken, and that is not the same statement.  `cl_nocsqc 1`
	  is the reason the difference matters: it is one line, it removes CSQC
	  entirely, and under the old rule it bought both a rankable run with no
	  profile AND a rankable run with no journal.

	  The list below still governs everything INSIDE a report -- a client that
	  speaks but lacks in_rawinput still gets its mask bit honoured, and that is
	  still every Linux, macOS and SDL player.  Speaking is what is now required;
	  having every cvar is not.
	*/
	if (e.run_t_pev == 0)
		return TRUE;

	// Linux beta (Lex, 2026-09-19): only Windows clients rank.  in_rawinput exists only in
	// in_win.c, so no IPH_RAW means Linux/macOS/SDL -- where device-targeted XTEST and
	// compositor injection cannot be seen (engine Patch 387's ceiling).
	if (!(e.run_t_pevhave & IPH_RAW))
		return TRUE;

	// The RULE is FS_ProfileBroken in sh_defs.qc and is not repeated here.
	if (FS_ProfileBroken(e.run_t_pevhave, e.run_t_pevraw,
	                     e.run_t_pevfilt, e.run_t_pevacc, e.run_t_pevgrant))
		return TRUE;

	/*
	  ...and the span the snapshot above cannot see.  run_t_pbad is latched at
	  the start; a client that stepped its counter in between was off-profile
	  inside this run even though both ends read clean.  See the `bad` note in
	  the inprof grammar.

	  -1 IS "NEVER SAMPLED" AND REFUSES TO COMPARE, on run_t_rbreach's precedent
	  and against the same failure: `bad` counts for the life of the CLIENT, not
	  of the run, so a player who fixed their settings ten minutes ago is still
	  carrying a positive count.  A run whose start took no latch -- an older
	  client that started sending the key mid-run, a connect between the two
	  calls -- would then difference a real count against a zeroed field and
	  invent a violation out of the first sample it ever saw.  That is a false
	  statement about a player, which is the one failure this bit may not have.
	*/
	if (e.run_t_pbad >= 0 && e.run_t_pevbad != e.run_t_pbad)
		return TRUE;

	return FALSE;
};

/*
  ...and the latch.

  CALLED TWICE, exactly like SV_TimerJournal and SV_TimerRuleset: once at
  SV_TimerStart so the bit is set before SV_RecOpen writes the header, and once
  at the finish so an `m_accel 1` typed mid-run is caught too.  It only ever
  sets: turning acceleration back off half way through does not retroactively
  make the first half checkable.

  THE START CALL LATCHES THE COUNTER FIRST, and in that order, so the comparison
  inside SV_ProfileBroken is trivially equal on this call -- a start can only be
  marked by the standing state, which is right, because there is no span yet to
  have crossed.  SV_TimerRuleset does the same thing for the same reason and the
  two are deliberately the same shape.

  A START THAT CANNOT READ THE KEY LEAVES run_t_pbad AT -1, which is SV_TimerArm's
  seed and means "never sampled" -- not 0, which would mean "sampled, and it was
  zero".  The difference is a false accusation; see SV_ProfileBroken.
*/
void(entity e, float atstart) SV_TimerProfile =
{
	if (atstart)
	{
		/*
		  Build 78: latched from the EVENT, for the reason the predicate one
		  function up gives at length -- the two must read the same channel or
		  the difference at the finish is between numbers that were never
		  comparable.  Build 77 parsed the key here and had to run FS_ProfileFields
		  to do it; the event carries `bad` as an argument, so there is no grammar
		  to get wrong on this side any more.

		  A CLIENT THAT HAS NOT REPORTED LEAVES run_t_pbad AT SV_TimerArm's -1,
		  which is "never sampled" and refuses to compare -- unchanged, and still
		  the point: `bad` counts for the life of the client, so differencing a
		  real count against a zeroed field would mark a run for something that
		  happened before it started.  Such a run is already faulted by the
		  silence rule, so this is belt and braces rather than the live path, but
		  it must stay correct: TF_NOPROFILE is set once and never cleared, and a
		  client that starts reporting mid-session would otherwise arrive at its
		  first finish with a poisoned latch.
		*/
		if (e.run_t_pev != 0)
			e.run_t_pbad = e.run_t_pevbad;
	}

	if (SV_ProfileBroken(e))
		e.run_t_flags = e.run_t_flags | TF_NOPROFILE;
};

/*
  DID THIS RUN HAPPEN ON OUR COPY OF THE MAP?  Build 73, engine Patch 321.

  The long version is the TF_NOMAP essay in sh_defs.qc.  The short version is
  that the engine has always had both numbers and never let QC see either: the
  server's map hash lived in sv.world.worldmodel->checksum and the client's claim
  in host_client->checksum, and the only consumer was sv_mapcheck's kick -- which
  is a refusal, not a fact, and which was inert on 1287 of the 1312 maps in the
  library until Patch 321.

  A PURE PREDICATE, on the SV_RulesetBroken / SV_ProfileBroken precedent, and for
  their harness reason rather than for tidiness: a run cannot be FINISHED from a
  config on a zoned map -- zone_goto voids and setpos taints -- see build 83's note -- so
  a rule that existed only inside the latch could not be checked headlessly at
  all.  Split out, `cmd timer` reports a live `wouldmap` beside the latched bit,
  with one copy of the rule and no side effect from asking.

  ONE ENGINE KEY, TWO SUBJECTS.  `*mapcrc` on world is the hash of the BSP THIS
  SERVER loaded; `*mapcrc` on a player is the hash THAT CLIENT claimed when it
  prespawned.  Deliberately not a serverkey: the expected answer is never put in
  serverinfo, because serverinfo reaches every client and a patched one would
  only have to echo it back.  See the Patch 321 comment in pr_cmds.c.

  EMPTY IS UNKNOWN AND UNKNOWN IS RANKABLE, on both sides and for four different
  reasons -- an engine or plugin older than Patch 321, a protocol that never
  sends a hash, a client asked before it prespawned, and a loader that computes
  none.  The engine folds the last of those into "" for us on purpose, so QC
  never has to know that a zero checksum means "nobody computed one": see the
  deploy-order note in pr_cmds.c, which is the difference between this check
  switching itself on per client as players update and it demoting every run by
  every player the moment the server half ships.

  STRING EQUALITY, NEVER stof.  A checksum is 32 bits and a QC float has a 24-bit
  mantissa, so a numeric compare would call differing maps equal -- silently, and
  in the direction that ranks.  See sh_defs.qc.
*/
float(entity e) SV_MapForeign =
{
	local string ours, theirs;

	ours = infokey(world, "*mapcrc");
	if (ours == "")
		return FALSE;
	theirs = infokey(e, "*mapcrc");
	if (theirs == "")
		return FALSE;
	if (theirs == ours)
		return FALSE;

	return TRUE;
};

/*
  ...and the latch.

  CALLED ONCE, AT THE START, and that is the one way this differs in shape from
  SV_TimerJournal, SV_TimerRuleset and SV_TimerProfile, all of which run again at
  the finish.  The missing second call is deliberate, not an omission: those three
  watch something a player can retype into a console mid-run, and neither side of
  this one can move inside a run.  The server's world model lives exactly as long
  as the map does, and a changelevel ENDS the run rather than continuing it; the
  client's claim is fixed at prespawn, which happens before it can spawn, let
  alone arm.  With no span to cross there is nothing to difference, which is also
  why this takes no latched field where the other two take one.
*/
void(entity e) SV_TimerMap =
{
	if (SV_MapForeign(e))
		e.run_t_flags = e.run_t_flags | TF_NOMAP;
};

/*
  WAS THIS RUN TIMED BY A CLOCK ANYBODY CAN RECOMPUTE?  Build 76, engine Patch 325.

  The long version is the TF_NOCLOCK essay in sh_defs.qc.  The short version is
  that a counted run time is a function of the usercmd stream and a sampled one
  is a function of packet arrival and server frame pacing, so only the first can
  ever be checked by re-simulating the inputs -- which is the entire point of
  moving the clock.

  CALLED ONCE, AT THE START, on SV_TimerMap's shape and for a stronger version of
  its reason.  SV_TimerJournal, SV_TimerRuleset and SV_TimerProfile all run again
  at the finish because each watches something a player can retype into a console
  mid-run.  This watches which engine is running, and an engine cannot be swapped
  underneath a live map -- but more than that, run_t_clock is LATCHED at the start
  precisely so the run's unit cannot change halfway through.  A second call would
  be asking a question whose answer this build guarantees is constant.

  IT READS run_t_clock AND NOT run_movetickrate.  Those are the same fact at the
  instant SV_TimerStart runs and they are not the same field, and the difference
  is the whole discipline of this migration: the run's unit is what was LATCHED,
  never what is currently true.  A latch read against a live value is how a
  recording ends up describing two clocks.
*/
void(entity e) SV_TimerClock =
{
	if (!e.run_t_clock)
		e.run_t_flags = e.run_t_flags | TF_NOCLOCK;
};

/*
  WERE THIS RUN'S PHYSICS PROVABLY THE RULESET'S?  Build 62, engine Patch 313.

  The long version is the TF_NORULESET essay in sh_defs.qc; the short version is
  that TF_CHEAT's own comment has admitted for builds that QC could see only half
  of SV_MovementLocked(), and engine Patch 313 publishes the whole predicate as
  *ruleset "<locked> <off> <seq>".  This is the only reader of that key.

  A LATCH, CALLED TWICE, exactly like SV_TimerJournal -- once at SV_TimerStart so
  the bit is set before SV_RecOpen writes the header, once at the finish so a
  ruleset opened MID-RUN is caught.  It only ever sets, never clears: re-locking
  half way through does not retroactively make the first half legal.

  THE START CALL EXISTS TO LATCH breach, NOT ONLY TO TEST.  This is the part
  that would be easy to leave out and is the whole reason the engine publishes
  counters at all.  `off` is a snapshot, and the window

      sv_cheats 1   ->  "0 0 1 0"    lock disengages
      sv_airaccel   ->  "0 1 2 1"    physics leave the ruleset, nothing reverts
      sv_cheats 0   ->  "1 0 2 1"    re-latch puts them back

  reads locked 1 / off 0 at BOTH ends.  A run spanning it is clean by every
  snapshot test and was not played under the ruleset.  Only the counters moved,
  so only a counter can say so -- measured on the shipped binary, those three
  strings verbatim.

  IT LATCHES breach AND NOT seq, AND THAT DISTINCTION IS THE WHOLE CORRECTION.
  seq counts ATTEMPTS to set a locked cvar off its canonical value; breach
  counts the subset that STOOD.  Under the lock the engine reverts inside the
  same Cvar_Set, so no physics tick ever sees the value -- the run's physics
  really were the ruleset's, and tainting on seq would state the opposite about
  a player who mistyped a cvar name into the console.  That is the Patch 305
  failure mode one layer up, and it was caught here by asking what the bit
  claims rather than by a test failing.  seq is still read, and reported beside
  the key at the finish, because a refused attempt is evidence even though it is
  not a violation.

  WHY A COUNTER IS NEEDED AT ALL WHEN SV_NoclipWatch ALREADY WATCHES sv_cheats.
  Because that watch is an EDGE -- sv_player.qc:472, `if (sc) if
  (!e.run_lastcheats)` -- sampled once per PlayerPostThink.  A toggle that goes
  1 and back to 0 between two of those is invisible to it, and every snapshot of
  this key still reads locked 1 / off 0 either side.  breach is the only thing
  in the game that sees that window.

  THE ABSENT KEY IS UNKNOWN AND IS NOT A VIOLATION.  serverkey returns "" on any
  engine before Patch 313, and every run this game has recorded to date was set
  on one.  Reading "" as "the ruleset was open" would stamp a false statement on
  all of them -- the same mistake SV_TimerJournal refuses to make with infokey's
  empty string, and the reason that function tests a literal "0".  Unknown stays
  unknown and the board declines quietly.

  run_t_rbreach carries -1 for "never sampled", set by SV_TimerArm, so a run that
  was armed under a pre-313 engine cannot compare against a latch of 0 and
  invent a violation out of the first real sample.

  tokenize writes one global buffer.  Safe here for the same reason it is safe
  at sv_entities.qc:1223 -- the value is parsed and consumed inside this
  function, and nothing it calls tokenizes.  The token count is checked rather
  than assumed: fewer than four fields is an engine that cannot answer this
  question and is treated as such, and a later engine adding a FIFTH field
  cannot break this reader.

  NOT GATED ON run_t_runclass, for the reason SV_TimerJournal states: a
  development switch that stops the server watching must not quietly produce
  runs that look certified.
*/
/*
  THE PREDICATE ITSELF, WITH NO SIDE EFFECT, so that the latch below and
  SV_TimerReport can ask the same question and cannot answer it differently.

  Split out for the reason SV_TimerReport's own harness note gives: a run cannot
  be FINISHED from a config on a zoned map -- zone_goto and setpos both route
  through SV_TimerWarped, which voids the attempt -- so the finish half of the
  latch would be untestable headlessly if the only way to see its answer were to
  reach an end box.  Build 58 hit this exact wall and the lesson it wrote down
  was "add a report line instead of chasing the finish".  A report that CALLED
  the latch would set the bit as a side effect of being asked, which is a report
  that changes what it reports; a report with its own copy of the rule would be
  the two-copies-of-one-predicate bug this file already refuses elsewhere.  So:
  one pure function, two callers.
*/
float(entity e) SV_RulesetBroken =
{
	local string s;
	local float n, locked, off, breach;

	s = serverkey("*ruleset");
	if (s == "")
		return FALSE;           // pre-313 engine: unknown stays unknown

	n = tokenize(s);
	if (n < 4)
		return FALSE;           // malformed is not a claim either

	locked = stof(argv(0));
	off    = stof(argv(1));
	//   argv(2) is seq -- attempts, reported but never tainted on
	breach = stof(argv(3));

	if (!locked || off)
		return TRUE;

	// The span.  -1 is "never sampled" and refuses to compare, so a run armed
	// under a pre-313 engine cannot invent a violation out of its first sample.
	if (e.run_t_rbreach >= 0 && breach != e.run_t_rbreach)
		return TRUE;

	return FALSE;
};

void(entity e, float atstart) SV_TimerRuleset =
{
	local string s;

	/*
	  LATCH BEFORE TESTING, and only at the start.  With the latch taken first
	  the breach comparison inside SV_RulesetBroken is trivially equal on this
	  call, so a start can only be marked by `locked`/`off` -- which is right,
	  because there is no span yet to have crossed.
	*/
	if (atstart)
	{
		s = serverkey("*ruleset");
		if (s != "")
		if (tokenize(s) >= 4)
			e.run_t_rbreach = stof(argv(3));
	}

	if (SV_RulesetBroken(e))
		e.run_t_flags = e.run_t_flags | TF_NORULESET;
};

/*
===========================================================================
  DOES THE RAMP CONTACT DROP OUT MID-RIDE, AND DOES THE PLANE ALTERNATE?
  Build 25, and it is an INSTRUMENT rather than a fix.

  The reported symptom is a strafe indicator that flickers between two values on
  a ramp, and reading pm_source.c gives two candidate mechanisms that look
  identical on screen and want opposite fixes:

    the CONTACT drops out    PMSrc_Tick clears rampcontact every tick
                             (:2665) and only a tick whose trace hits the ramp
                             sets it again (:1135).  The client then flips
                             between the ramp regime and the air regime.

    the PLANE alternates     rampnormal is whatever the LAST BUMP of that tick
                             clipped (:1142), so on a curved or displacement
                             ramp consecutive ticks legitimately report
                             different facet normals.  nz and wn alternate, and
                             so does the target rate, with no dropout at all.

  Both are per-tick, so both are invisible to a client sampling stats -- and a
  config cannot surf, so the only honest way to tell them apart is to count them
  where they happen.  That is here: PlayerPostThink runs once per tick and this
  is already the function that reads run_rampcontact.

  The counters describe THE CURRENT RIDE and reset when it genuinely ends, so
  `cmd timer` after one ramp answers the question directly rather than reporting
  a map-lifetime average that mixes twenty rides together.

  A "flip" is a plane that differs from the previous tick's by more than
  RAMP_SAMEPLANE, and the first value chosen for that was WRONG in a way the
  fixtures caught rather than reasoning.

  It was cos(2.6 deg), on the reasoning that anything smaller was float noise.
  There is no float noise: the engine VectorCopy's pm.plane.normal into
  pmove.rampnormal unchanged, so an unchanged plane dots to exactly 1.  And real
  ramp facets are far closer together than 2.6 degrees -- rotating a 35-degree
  surf normal's horizontal component by four degrees moves the NORMAL only 2.14,
  which the old threshold called "the same plane".  A synthetic ride built to
  contain nothing but alternating facets reported zero flips.

  So it is as tight as the recorded format allows: cos(0.26 deg), inside any real
  facet difference and outside four-decimal rounding.  The WORST angle is
  reported alongside the count, because a count cannot distinguish a ride whose
  facets differ by a twentieth of a degree -- alternating in a way nothing on
  screen could show -- from one whose facets differ by ten.

  tools/reccheck.py --ramps makes the same measurement over a whole .rec and
  carries the same constant with the same essay.
===========================================================================
*/
#define RAMP_SAMEPLANE 0.99999

/*
  How long a gap has to be before the instrument calls the ride over.

  DELIBERATELY MUCH LONGER THAN THE CLIENT'S HOLD (RAMP_GAP, 0.08s -- the
  engine's own PMSRC_BOARD_AIRGATE).  If the two were the same number this could
  never report a gap the hold refused to bridge, which is the single most useful
  thing it could tell us: it would silently agree with the fix instead of
  measuring whether the fix is long enough.  Half a second is well past any
  plausible bridge and well short of a real air time between two ramps.
*/
#define RAMP_GAPMAX 0.5

.float  run_rc_ticks;            // ticks of contact in the current ride
.float  run_rc_gaps;             // gaps bridged within it
.float  run_rc_gap;              // length of the gap being served, in ticks
.float  run_rc_worst;            // the longest gap this ride, in ticks
.float  run_rc_flips;            // ticks whose plane differed from the last one
.float  run_rc_worstdot;         // the smallest dot between two consecutive planes
.vector run_rc_lastn;            // the previous tick's plane

void(entity e) SV_RampWatch =
{
	local float d;
	local vector n;

	if (!e.run_rampcontact)
	{
		// Not on a ramp this tick.  Either we are serving a gap inside a ride,
		// or the ride is over and the next one starts from zero.
		if (e.run_rc_ticks > 0)
		{
			e.run_rc_gap = e.run_rc_gap + 1;
			if (e.run_rc_gap * run_t_tick > RAMP_GAPMAX)
			{
				e.run_rc_ticks = e.run_rc_gaps = e.run_rc_gap = 0;
				e.run_rc_worst = e.run_rc_flips = 0;
				e.run_rc_worstdot = 1;
				e.run_rc_lastn = '0 0 0';
			}
		}
		return;
	}

	// Back on, after a gap: that gap is now a bridged one and is measurable.
	if (e.run_rc_gap > 0)
	{
		e.run_rc_gaps = e.run_rc_gaps + 1;
		if (e.run_rc_gap > e.run_rc_worst)
			e.run_rc_worst = e.run_rc_gap;
		e.run_rc_gap = 0;
	}

	// Seeded on the ride's FIRST tick, not in a field initialiser: a fresh edict
	// zeroes every field, and a worst-dot of 0 is 90 degrees -- the report would
	// open by claiming the plane had turned a right angle before it had turned
	// at all.  The end-of-ride reset above does the same for every later ride.
	if (e.run_rc_ticks == 0)
		e.run_rc_worstdot = 1;

	e.run_rc_ticks = e.run_rc_ticks + 1;

	n = e.run_rampnormal;
	if (n != '0 0 0')
	{
		if (e.run_rc_lastn != '0 0 0')
		{
			// vector*vector is a dot product and needs a float lvalue before a
			// comparison -- fteqcc will not infer the type through one.
			d = n * e.run_rc_lastn;
			if (d < RAMP_SAMEPLANE)
				e.run_rc_flips = e.run_rc_flips + 1;
			if (d < e.run_rc_worstdot)
				e.run_rc_worstdot = d;
		}
		e.run_rc_lastn = n;
	}
};

/*
===========================================================================
  THE START MAY NOT BE HOPPED.  Build 19.

  The rule: a run counts if you walked out of the start zone, or left it on ONE
  initial jump.  Hop out and it is practice.

  "INITIAL JUMP" IS NOT A NEW IDEA HERE -- it is the definition that already
  drives the +forward release.  cl_main.qc drops +forward for a jump taken from
  a ground phase of at least run_prestrafe_time and hands it back on landing, and
  its design comment says in as many words that the threshold exists to tell a
  pre-strafe jump from a bhop.  Using the same number for the rule makes the rule
  legible before it is enforced: if the game released your +forward, that was an
  initial jump; if it did not, that was a hop.  The server owns the number and
  publishes it to serverinfo (SV_TimerMapInit) so the two cannot drift.

  WHY NOT A GROUND-FLAG EDGE, which is the obvious detector and the wrong one:
  it cannot see a bhop, and a bhop is the only thing this rule is about.
  CategorizePosition sets FL_ONGROUND and CheckJumpButton clears it inside the
  SAME tick, so PlayerPostThink sees an airborne player who was airborne last
  tick as well.  A perfectly-timed hop is invisible to it -- and a perfectly-
  timed hop is precisely the gesture being caught.

  So the jump edge is velocity_z crossing above PM_NONJUMP_VEL (140) from at or
  below it.  140 is not a constant invented for this: it is the number the
  physics itself uses to decide whether a rise is jump-like, and a jump sets
  velocity_z to about 262 from at most 0.  A ramp can clip a fast descent into a
  large rise in one tick too, which is what run_rampcontact is here to exclude --
  and it is also why run_t_startok has a ramp-contact arm.

  The dwell then falls out of run_t_groundsec, whose zero is doing the real work:
  a hop that was never observed on the ground reads a dwell of zero, which is
  exactly the right answer for it.
===========================================================================
*/
float(entity e) SV_TimerJumpWatch =
{
	local float ong, vz, jumped, dwell, want, settleok, launchz, bhopz;

	ong = (e.flags & FL_ONGROUND);
	vz  = e.velocity_z;

	// A jump, unless a ramp is what lifted us.
	jumped = FALSE;
	if (vz > PM_NONJUMP_VEL)
		if (e.run_t_lastvz <= PM_NONJUMP_VEL)
			if (!e.run_rampcontact)
				jumped = TRUE;
	e.run_t_lastvz = vz;

	want = run_t_dwell;
	if (want <= 0)
		want = 0.25;

	// The server half of the +forward-release test: a real observed ground
	// phase lasting at least `want` makes this an initial jump, not an autohop.
	dwell = 0;
	if (e.run_t_groundsec > 0)
		dwell = SV_ClockSec(e) - e.run_t_groundsec;

	/*
	  BHOP LAUNCH / RE-LAUNCH.

	  The PREVIOUS authoritative point must be inside the start.  `jumped` is
	  detected after movement, so testing e.origin alone would miss a fast jump
	  that crossed the boundary this tick, while accepting a jump that entered
	  the box from outside.  run_t_lastorg is exactly the pre-move endpoint.

	  ARMED uses run_t_armzone because a command such as zone_goto arms directly,
	  before the occupancy scan has filled run_t_azone.  RUNNING and FINISHED use
	  run_t_azone: entering a start in those states is deliberately only a pending
	  re-arm (SV_TimerTryArm), and this qualified jump is what commits it.

	  This function only LATCHES the zone.  SV_TimerFrame commits it after the old
	  run has had its end/stage/checkpoint events, and before the recorder samples
	  this tick.  That ordering matters on the shipped maps whose START and END
	  overlap: the old run gets to finish before the new jump replaces it.
	*/
	launchz = -1;
	bhopz = -1;
	if (e.run_t_state == TS_ARMED)
		launchz = e.run_t_armzone;
	else if (e.run_t_state == TS_RUNNING || e.run_t_state == TS_FINISHED)
		launchz = e.run_t_azone;

	/*
	  BUILD 47: HULLED, and for consistency rather than preference.

	  If the run starts when the hull is fully clear of the box, then a jump
	  taken while the hull still overlaps is by definition a jump taken FROM
	  INSIDE the box.  Leaving this a point test would create a band, one hull
	  wide, where you have not started (hull overlaps) but a qualifying bhop is
	  not recognised as a launch either -- two predicates disagreeing about the
	  same box, which is the exact bug class the sin/shit essay was written
	  about.

	  It asks about run_t_lastorg, so strictly it wants LAST tick's hull.  Under
	  run_zone_hull_live 0 that is moot because the hull is a constant; under 1
	  there is a one-tick skew on the duck state, which is one more argument for
	  the constant.
	*/
	if (run_t_bhopjump)
	if (!e.rec_gh_on)
	if (jumped)
	if (dwell >= want)
	if (launchz >= 0)
	if (launchz < zone_count)
	if (zone_type[launchz] == ZONE_START)
	if (SV_ZoneIn(launchz, e.run_t_lastorg, SV_RunHullMins(e), SV_RunHullMaxs(e)))
		bhopz = launchz;

	if (jumped)
		e.run_t_jumps = e.run_t_jumps + 1;

	// Patch 360: the takeoff that begins this flight -- a jump, or walking off
	// an edge (first airborne tick after ground, no jump) -- primed if the
	// dwell was met.  groundsec is still last tick's here (clocks update last).
	if (jumped)
		SV_StageTakeoff(e, (dwell >= want) ? 1 : -1);
	else if (!ong)
	if (e.run_t_groundsec > 0)
		SV_StageTakeoff(e, (dwell >= want) ? 1 : -1);
	if (e.run_rampcontact)
		e.run_st_tkok = 0;
	if (e.run_boardcount != e.run_st_tkbc)
		e.run_st_tkok = 0;          // a ramp on a tick the flag above did not see
	/*
	  PATCH 411, NOT DONE, and the two reasons are worth more than the attempt.
	  A booster IS credited as a stage start today: run_rampcontact above is the
	  only mover exclusion run_st_tkok and run_st_jump have, and it is blind to
	  the standable floor a pad clips off (pm_source.c:1313, |n_z| in [0.1, 0.7])
	  -- the same blind spot Patch 409 closed for the START rule.  A clear here
	  reading `run_pushed && !run_jumpcmd` was written, reviewed and withdrawn:

	    - IT IS NOT TAKEOFF-SCOPED.  This function runs every packet while
	      run_st_tkok lives from takeoff to landing, so it asks "did a carrier act
	      during this flight", not "was the takeoff the mover's".  run_pushed is
	      set by the CASH-OUT (SV_BaseVelocityFrame), which fires one command AFTER
	      you leave a volume, and run_jumpcmd cannot latch airborne -- so jumping
	      honestly out of a stage box that holds a pad, or merely flying through
	      one, silently deleted the split with no way to restore it.
	    - THE PREDICATE DOES NOT SURVIVE THE SIGN FLIP.  For P409 run_jumpcmd TRUE
	      means "press on with the accusation"; reused for CREDIT it means "grant
	      it", so holding +jump on a pad buys the mover's rise.  P409's own
	      residual (:9120) becomes a hole rather than an admission.

	  What it needs is a takeoff-scoped refusal that does not consult the jump
	  button at all, and the cost of that has to be measured first: the census
	  behind Patch 409 counted pushes overlapping START zones, not STAGE
	  boundaries, so the number of honest splits it would refuse is unknown.
	  run_stagecap catches the horizontal case once the takeoff speed is read
	  correctly (see SV_StageTakeoff); a purely vertical pad adds no horizontal
	  speed and is still credited.  Its own patch, after its own corpus scan.
	*/

	/*
	  BUILD 24: the same two observations, asked a different question.

	  This detector is here because it is the only one in the tree that can see a
	  jump AT ALL -- CategorizePosition sets FL_ONGROUND and CheckJumpButton
	  clears it inside the same tick, so a well-timed hop never appears grounded
	  to QC and a ground-edge detector misses it entirely.  Build 19 wrote it to
	  decide whether a START was hopped; build 24 asks whether a STAGE was
	  started, which is the same measurement with the opposite sign.

	  run_st_ramp is latched here rather than in the mover, because this function
	  already runs every tick and already reads run_rampcontact.  Once it is set,
	  the stage is a surf-through and no later jump can make it a stage start.
	*/
	if (e.run_rampcontact)
		e.run_st_ramp = TRUE;
	if (e.run_boardcount != e.run_st_bcseen)
		e.run_st_ramp = TRUE;       // Patch 360: same, mid-packet
	e.run_st_bcseen = e.run_boardcount;
	// A mover-driven rise still sets run_st_jump here; see the withdrawn clear
	// over the run_st_tkok lines above for why Patch 411 does not gate it yet.
	if (jumped)
	if (e.run_t_state == TS_RUNNING)
		SV_StageJump(e);

	SV_RampWatch(e);

	/*
	  Settle the start.  Any ONE of three, and they are three because the
	  question "is the launch over" has three honest answers:

	    airborne for FS_STARTSETTLE   you left, and you are still leaving
	    riding a ramp                 you are past the platform entirely, and it
	                                  also stops an early ramp being read as a hop
	    grounded for the dwell        you walked out and are simply walking

	  The last one is what makes a no-jump start legal without a special case.
	*/
	// Everything below is start business, so once the start is settled this
	// function is two flag tests and the phase clocks.
	if (!e.run_t_startok)
	{
		/*
		  BUILD 20: THE FIRST TWO MAY NOT SETTLE A START YOU HAVE NOT LEFT.

		  The third was always TS_RUNNING-gated; the other two were not, and that
		  is the second half of the reason the rule never fired.  Standing in the
		  box you are ARMED, so an airborne phase or a ramp clip THERE is not the
		  launch being over -- it is the launch not having happened.  It also
		  closes the hole where a sloped floor inside the start box settled the
		  start outright.

		  `&&` here is safe -- these are field reads, not array reads -- but this
		  file's essays train the reader to distrust it, so: no index is being
		  guarded on either line.
		*/
		settleok = TRUE;
		if (run_t_startstrict)
			settleok = (e.run_t_state == TS_RUNNING);

		if (settleok && e.run_rampcontact)
			e.run_t_startok = TRUE;
		else if (settleok && e.run_t_airsec > 0 && (SV_ClockSec(e) - e.run_t_airsec) >= run_t_settle)
			e.run_t_startok = TRUE;
		else if (e.run_t_state == TS_RUNNING)
			if (e.run_t_groundsec > 0 && (SV_ClockSec(e) - e.run_t_groundsec) >= want)
				e.run_t_startok = TRUE;

		/*
		  Tested AFTER the settle, deliberately: a jump taken from a long enough
		  ground phase is the legal one, and it is also the jump that settles the
		  start.  Testing before would flag the very gesture the rule permits.
		*/
		/*
		  BUILD 21: THE RULE ONLY SPEAKS INSIDE AN ATTEMPT.

		  The nested state test is new and it is required by the re-arm rather
		  than incidental to it.  run_t_startok can never become TRUE while IDLE --
		  every settle branch needs TS_RUNNING -- so an IDLE player who bhops
		  anywhere on the map fell into this block and was told "hopped start".
		  Harmless before, because SV_TimerArm cleared the taint on the way into
		  the next attempt and nothing ever read it; not harmless now, because the
		  line below it would invite them to stand still and re-arm a start they
		  are nowhere near.

		  Nested rather than `&&`: this file's convention, and cheap to keep.
		*/
		/*
		  PATCH 409: A BOOSTER IS NOT A JUMP, and run_rampcontact does not say so.

		  The exclusion above `jumped` covers a RAMP clipping a fast descent into
		  a rise.  A trigger_push does the same thing by the same code path --
		  PMSrc_TryPlayerMove clips velocity+basevelocity against the plane and
		  only the carrier is subtracted back out, so every unit of Z the clip
		  made stays in .velocity -- but the surface that did it is usually
		  STANDABLE, and pm_source.c:1313 sets rampcontact only for |n_z| in
		  [0.1, 0.7].  Reported live on surf_666 bonus 3, where the start box
		  overlaps a 3000 u/s pad: falling into the pit put 1453 u/s into
		  velocity_z off a 26.57 degree floor and the run was called a hopped
		  start.  See .run_pushed in sv_entities.qc for the three writers.

		  READ HERE AND NOWHERE ELSE, deliberately: `jumped` itself is unchanged,
		  so the bhop launch latch, run_t_jumps, SV_StageTakeoff and SV_StageJump
		  all behave exactly as before.  This withdraws an accusation; it grants
		  no speed, no position and no other forgiveness.

		  AND IT TAKES TWO FIELDS, which the first two drafts did not.
		  `run_pushed` alone says only "a carrier was handed to the mover this
		  packet", and a continuous pad re-arms that every command you touch it --
		  so on the 21 maps whose start box overlaps a push (census 2026-09-20,
		  1316 bsps: 21 overlap, 36 more within 300 u) it switched the whole rule
		  off for as long as you stood in the volume.  Both reviewers found that
		  independently.

		  A MAGNITUDE BOUND WAS THE SECOND DRAFT AND IS BEATEN.  CheckJumpButton
		  runs BEFORE AirMove, and AirMove is where the carrier is added, clipped
		  and subtracted back -- so the impulse and the clip's gain land in the
		  same tick and add.  A deliberate bhop out of B3's start box reads about
		  1259 (296 of jump, ~963 of clip) against a bound of 317, on the exact
		  map this patch exists for.  Sizing the rise cannot separate them.

		  SO IT IS THE INPUT.  CheckJumpButton is the only path to a commanded
		  rise and it needs the jump button and pre-move ground; a body falling
		  into a pit has neither, and no floor angle changes that.

		  RESIDUAL, stated rather than closed: grounded on a pad with jump held
		  while the clip lifts you is still read as a hop.  It is the ambiguous
		  case -- you did press it -- and it keeps the pre-409 answer.
		*/
		if (jumped && !e.run_t_startok && cvar("run_starthop"))
		if (!e.run_pushed || e.run_jumpcmd)
		if (e.run_t_state == TS_ARMED || e.run_t_state == TS_RUNNING)
		{
			if (dwell < want)
			{
				/*
				  Guarded on both taints so a bhop chain says this once rather
				  than once per hop -- and says it AGAIN after a re-arm, which is
				  right: a second fluffed start is a second thing to report.
				*/
				if (!e.run_t_dirty && !e.run_t_hopped)
				{
					sprint(e, PRINT_HIGH,
					       "^3hopped start^7 -- one jump out of the start, or walk out\n");
					if (run_t_rearmhop && e.run_t_state == TS_ARMED)
						sprint(e, PRINT_HIGH,
						       "              ^7stop and stand still to re-arm the start\n");
				}

				/*
				  BUILD 21: WHICH TAINT, AND THE SPLIT IS THE WHOLE FEATURE.

				  Not yet running -- you are still in the box -- so the hop is
				  recorded in run_t_hopped, which the re-arm below can take back.
				  SV_TimerStart consumes it exactly as it consumes run_t_dirty, so
				  an unforgiven hop still lands on the run that follows and a
				  clean `!r` still resets it.

				  Already RUNNING is the irreversible case and goes straight to
				  SV_TimerPractice as it always did.  There is nothing to forgive
				  out there: the clock has been counting since you left the box,
				  so "stand still and jump" could only mean restarting it from
				  wherever you happen to be standing.  See the run_rearmhop essay.
				*/
				if (e.run_t_state == TS_RUNNING)
					SV_TimerPractice(e);
				else
					e.run_t_hopped = TRUE;   // TS_ARMED; the outer test says so
			}
		}

		/*
		  THE RE-ARM.  Build 21.

		  Stop bhopping, stand for the same dwell that makes a jump an initial
		  jump, and the fluffed start is taken back: the next jump is judged from
		  a clean slate.

		  It deliberately does NOT set run_t_startok.  That would settle the start
		  while you are still standing in the box, which is the hole build 20
		  closed -- the point is to reopen the window, not to close it early.

		  run_t_jumps goes back to zero with it so the `timer` report describes
		  the attempt you are actually about to make.  It is a diagnostic counter
		  and nothing reads it for a decision, but a re-armed start that still
		  says `jumps 5` is a report that lies about the thing it exists to show.

		  TS_ARMED is the scope guard, and it is the state whose own definition
		  is "standing in the zone the run will start from" -- so the guard IS
		  the answer the user chose, spelled in the state machine rather than in
		  a position test.  The clock has not started, so there is no time to
		  rewind and no distance to skip.  run_t_groundsec > 0 carries the autohop
		  case for free, exactly as it does in the hop test above: a hop the
		  server never saw grounded reads a dwell of zero and re-arms nothing.
		*/
		if (run_t_rearmhop && e.run_t_hopped && e.run_t_state == TS_ARMED)
			if (e.run_t_groundsec > 0 && (SV_ClockSec(e) - e.run_t_groundsec) >= want)
			{
				e.run_t_hopped = FALSE;
				e.run_t_jumps  = 0;
				sprint(e, PRINT_HIGH,
				       "^2start re-armed^7 -- one jump out of the start\n");
			}
	}

	// The two phase clocks, written last so the dwell computed above is this
	// tick's rather than next tick's.  Zero means "not in this phase", which is
	// what makes the autohop case read correctly.  Build 76: stamped on
	// SV_ClockSec, so the dwell -- and therefore the VERDICT it decides -- is a
	// function of the usercmd stream like the run time it gates.  See the field.
	if (ong)
	{
		if (!e.run_t_groundsec)
		{
			e.run_t_groundsec = SV_ClockSec(e);
			// Landed: the flight's takeoff is kept for this one tick (Patch 360).
			e.run_st_tkland    = e.run_st_tkok;
			e.run_st_tklandspd = e.run_st_tkspd;
			e.run_st_tklandsec = e.run_st_tksec;
			e.run_st_tkok = 0;
		}
		e.run_t_airsec = 0;
	}
	else
	{
		if (!e.run_t_airsec)
			e.run_t_airsec = SV_ClockSec(e);
		e.run_t_groundsec = 0;
	}

	// Patch 409.  Their only reader is above, so clearing them here makes both
	// latches exactly one packet wide.  PlayerPostThink returns early under
	// run_pmhold (sv_player.qc) and so does PreThink, so nothing can set them
	// during a hold and the slack is one packet after release.
	e.run_pushed  = FALSE;
	e.run_jumpcmd = FALSE;

	return bhopz;
};

/*
  Build 12: restart THE STAGE without ending the run.

  `!r` on stage 3 used to void everything and start a fresh stage-3 run from
  zero.  That is Momentum's behaviour and it is right for a leaderboard, but it
  is not what you want while learning a map: you go back to the top of the stage
  you just failed and the clock you have been building for two minutes is gone.

  So the MAIN CLOCK IS NOT TOUCHED -- run_t_startsec is left exactly where it was
  and keeps counting -- and only the current segment restarts.  run_t_split
  already means "the run time at which the segment in progress began", so moving
  it to now is the whole of restarting the stage: every stage-relative readout
  derives from it and follows.

  BUILD 13: it does NOT set practice mode any more.

  Build 12 set TF_PRACTICE here on the reasoning that the total includes the
  attempt you abandoned.  That reasoning is sound for a leaderboard and wrong
  for this: resetting early on a stage is a legitimate part of running one --
  you know within half a second that the entry was bad, and you take it again.
  The clock keeps running and keeps counting the wasted time, which is the
  whole penalty and an honest one.  Marking the run unsaveable on top of that
  made the feature useless for the thing it was added for.

  What DOES set practice is the stuff that changes where you are or what the
  physics are: a save-lock load, and noclip (SV_TimerPractice, called from
  SV_NoclipWatch).  Those give you a position you did not earn.  Restarting a
  stage gives you a worse time.  Since build 15 noclip taints the attempt even
  before the clock starts -- see the run_t_dirty latch in SV_TimerPractice.

  Only reachable when the segment you are on is NOT the one you started from --
  restarting the leg you began on is just restarting the run, and that still
  voids and re-arms.  See SV_ZoneMove.
*/
void(entity e) SV_TimerRestartSeg =
{
	local float now;

	if (e.run_t_state != TS_RUNNING)
		return;

	now = SV_TimerTicks(e);
	e.run_t_split = now;
	e.run_t_delta = 0;

	// The split recorded for this segment is void -- you are doing it again --
	// so move its base with the clock rather than leaving the failed attempt's
	// entry to be differenced against later.
	if (e.run_t_slot >= 0)
		if (e.run_t_seg > 0)
			if (e.run_t_seg < FS_MAXSPLITS)
				run_run_split[e.run_t_slot * FS_MAXSPLITS + e.run_t_seg] = now;

	// Re-entering the very zone we are being put into has to count as ENTERING
	// it, or the scan sees no change and the next stage boundary is missed.
	// run_t_armzone is deliberately NOT cleared: nothing is being re-armed.
	e.run_t_azone = e.run_t_evzone = e.run_t_cpzone = -1;

	sprint(e, PRINT_HIGH, sprintf("^3stage %g restarted^7 -- the run clock keeps going\n",
	                              e.run_t_seg + 1));

	SV_RecPut(e, sprintf("restart %d %d", e.run_t_seg, now));

	/*
	  BUILD 24: the stage's slice starts again too, and this is not optional.

	  You are being put back at the top of the stage you are on, so the samples
	  before this line are a failed attempt at it -- keeping them would write a
	  demo containing both, timed only for the second, and its clock would not
	  match its own footage.  Reopening moves run_st_line past the `restart`
	  record above and resets the jump filter, so the restarted attempt has to
	  earn its stage record the same way the first one did.

	  AFTER the record, so the restart line is not the first line of the slice.

	  BUILD 43: THE STAGE COMES BACK ARMED, and the arm resolves itself on the
	  next tick rather than here.  SV_ZoneMove calls SV_TimerTeleported BEFORE its
	  setorigin, so at this instant e.origin is still where you were -- but the
	  boundary box is re-derived from e.run_t_seg in SV_TimerFrame, which runs
	  after the move, so the very next tick tests the position you were actually
	  put at.  `!r` on a stage therefore behaves exactly like walking back into
	  the box: armed, and timed from when you leave it again.
	*/
	SV_StageOpen(e, e.run_t_seg, now);
};

/*
  What a teleport does to the run, decided HERE rather than in sv_zones.qc.

  The zone code knows where it is putting you; the timer knows what that means.
  Keeping the test in this file is also the only place it can live: the run_t_*
  fields are declared here and sv_zones.qc is compiled first, so asking the
  question over there needs the whole field block forward-declared to answer it.

  Returns TRUE if the run SURVIVED (a stage restart), FALSE if it was voided --
  the caller needs to know, because arming a zone it just restarted into would
  throw the run away by the back door.
*/
/*
  Restart-in-place is exactly one case: mid-run, going back to the start of the
  segment you are ALREADY on, on your own track, and not the segment the run began
  from.  That last clause is what keeps it off stage 1 -- going back to where you
  started is restarting the run, and there voiding is right.

  Nested ifs, not `&&`: QuakeC's && is OP_AND and evaluates both sides, so a
  guarded zone_track[-1] still reads and still kills the server.

  PATCH 415 LIFTED IT OUT OF SV_TimerTeleported, which is the only caller that
  acts on it.  `!r` has to know the answer BEFORE the move rather than after: it
  decides whether this is a restart that keeps the clock (leave it alone) or a
  reset (where a start-box save may be preferred instead), and by the time
  SV_ZoneMove has run, the run it would have asked about is gone.  One spelling,
  because two of a rule this sharp is how they drift.
*/
float(entity e, float n) SV_TimerWouldRestartSeg =
{
	local float restart;

	restart = FALSE;
	if (e.run_t_state == TS_RUNNING)
	if (n >= 0)
	if (n < zone_count)
	if (zone_type[n] == ZONE_START || zone_type[n] == ZONE_STAGE)
	if (zone_track[n] == e.run_t_track)
	if (zone_seg[n] == e.run_t_seg)
	if (e.run_t_seg > e.run_t_startseg)
		restart = TRUE;

	return restart;
};

float(entity e, float n) SV_TimerTeleported =
{
	if (SV_TimerWouldRestartSeg(e, n))
	{
		SV_TimerRestartSeg(e);
		return TRUE;
	}

	SV_TimerVoid(e, "teleported");
	return FALSE;
};

/*
  BUILD 57 -- THE STAGE-1 REQUEST, FROM THE CHAT COMMANDS.

  Called by SV_ZoneChatCommand BEFORE its move, for the reason SV_TimerTeleported
  is called from there and lives here: the move voids the run, and `!r` has to
  ask about the run before it is gone.  sv_zones.qc compiles first and cannot
  read the run_t_* fields, so the decision is made in this file.

    !s 1      stage 1 alone: the START that follows arms stage 1
    !s N>1    a stage zone, which is a stage run by its own type -- the request ends
    !m, !b N  the map, or a bonus -- the request ends
    !r        SET when the run being restarted is a stage-1 run, and otherwise
              left exactly as it stands.  "The start of the leg you are on" has
              to come back as that leg, and deriving it from the run rather than
              trusting the flag alone means nothing that cleared the flag in
              between -- a bhop walk-through of the box, say -- can lose it.

  `n <= 1` for `!s`, because the handler reads a missing or zero number as stage
  1 and this must agree with it.  SV_TimerArm drops the request again if the
  START it lands on is not the main track's, or the track is linear.

  Returns whether the request stands afterwards, which is what lets `!r` say
  "stage 1" in the chat line instead of "start of the map".
*/
float(entity e, string word, float n) SV_TimerChatLeg =
{
	if (word == "!r")
	{
		if (e.run_t_stagerun)
		if (e.run_t_startseg == 0)
		if (e.run_t_track == 0)
			e.run_t_wantstage1 = TRUE;
		return e.run_t_wantstage1;
	}

	e.run_t_wantstage1 = FALSE;
	if (word == "!s")
	if (n <= 1)
		e.run_t_wantstage1 = TRUE;
	return e.run_t_wantstage1;
};

// Stand in a zone a run can begin from.  Arms it; the timer does not start
// until you leave THAT zone -- see the start check in SV_TimerFrame.
void(entity e, float z) SV_TimerArm =
{
	SV_RecDiscard(e);
	e.run_t_armsec = SV_ClockSec(e);    // Patch 360: see SV_TimerStart
	SV_TimerClearSplits(e);

	e.run_t_state    = TS_ARMED;
	e.run_t_armzone  = z;
	e.run_t_track    = zone_track[z];
	e.run_t_startseg = zone_seg[z];
	e.run_t_seg      = zone_seg[z];
	e.run_t_segs     = SV_TrackSegs(zone_track[z]);

	/*
	  BUILD 57: WHICH LEG THIS IS -- the one thing the zone cannot decide alone.

	  A STAGE zone arms a stage run, as it always did.  A START arms the full run
	  UNLESS `!s 1` is standing, and then it arms stage 1.  Every arm route in the
	  game reaches this line: the walk-in (SV_TimerTryArm), the bhop jump-start
	  and its re-arm (SV_TimerFrame), SV_ZoneMove behind every chat command and
	  zone_goto, and the FINISHED -> pendarm stage handover.  So this is the only
	  place a leg is chosen, and a save restore is the only other writer.

	  THE REQUEST IS ABOUT THE MAIN TRACK'S START ON A STAGED TRACK AND NOTHING
	  ELSE, and it is dropped the moment an arm lands anywhere else.  The handover
	  into stage 2 therefore ends it; a bonus START cannot inherit it and become
	  "bonus 1 stage 1"; and a linear track -- whose only segment IS the full run
	  -- can never file a run under stage_1.  Dropped rather than ignored, so a
	  later `!r` or walk-in cannot find a request left over from a leg the player
	  has already moved on from.

	  Before SV_PBGet below, which is keyed by the leg this decides.
	*/
	if (zone_type[z] != ZONE_START)
		e.run_t_wantstage1 = FALSE;
	else if (zone_track[z] != 0)
		e.run_t_wantstage1 = FALSE;
	else if (e.run_t_segs <= 1)
		e.run_t_wantstage1 = FALSE;

	e.run_t_stagerun = FALSE;
	if (zone_type[z] == ZONE_STAGE)
		e.run_t_stagerun = TRUE;
	else if (e.run_t_wantstage1)
		e.run_t_stagerun = TRUE;
	e.run_t_ticks    = 0;
	e.run_t_split    = 0;
	e.run_t_delta    = 0;
	e.run_t_flags    = 0;
	e.run_t_pendarm  = -1;
	// Build 62: -1, not 0.  Zero is a legitimate *ruleset seq, so clearing to it
	// would let a fresh attempt compare a real sample against a fake latch.  See
	// SV_TimerRuleset.
	e.run_t_rbreach     = -1;
	// Build 72: -1 for the same reason, and it bites harder here -- `bad` counts
	// for the life of the client, so 0 is both a legitimate value and the wrong
	// default.  See run_t_pbad and SV_ProfileBroken.
	e.run_t_pbad        = -1;
	// Build 74: -1 for the third time, and the reason is the sharpest of the
	// three -- run_movetick is reset PER MAP, so 0 is not merely a legitimate
	// value, it is the value every counter holds for the first seconds of every
	// map.  A run armed there and differenced against a zeroed latch would read
	// as having started at the map load.  See run_t_starttick and SV_TickReport.
	e.run_t_starttick   = -1;
	e.run_t_tickcarry   = 0;
	e.run_t_frzticks    = 0;
	/*
	  BUILD 76: the seconds half of the same teardown.

	  run_t_clock goes to 0 rather than being left standing, and that is the
	  sentinel discipline one level up: with no run there is no clock, and a
	  stale 1 would send SV_TimerTicks down the counted branch for an attempt
	  that never latched.  It cannot invent a number -- SV_TickCounted's -1 stops
	  that -- but it would pick the branch for the wrong reason, and a guard that
	  holds by accident is the shape build 75 was caught by.

	  run_t_frzsec beside run_t_frzticks because they are accumulated together
	  and must be cleared together; a half-cleared pair would subtract a frozen
	  interval from one readout of the next run and not the other.
	*/
	e.run_t_frzsec      = 0;
	e.run_t_clock       = 0;

	e.run_t_cpmax    = 0;
	e.run_t_cpn      = 0;
	e.run_t_cpticks  = 0;
	e.run_t_cpdelta  = 0;

	/*
	  BUILD 24: no stage is open until the clock starts.

	  SV_RecDiscard above has just thrown the buffer away, so run_st_line is an
	  index into a buffer that no longer exists -- and SV_StageClose reads it.
	  Nothing can reach that read from here (a close needs TS_RUNNING, and
	  SV_TimerStart reopens the stage before the state can become that), but
	  "unreachable" is a claim about the whole file and -1 is a fact about this
	  line.  It also stops the timer report saying `seg 0` about a player who is
	  standing in a start box doing nothing.
	*/
	e.run_st_seg     = -1;
	e.run_st_jump    = FALSE;
	e.run_st_ramp    = FALSE;

	/*
	  BUILD 43: and the rest of the stage machine with them.  Everything here is
	  a statement about a stage that no longer exists, and this function's job is
	  the same one SV_TimerIdle's essay describes -- leave nothing behind.  The
	  counters in particular: an arm that still says `fails 3` is a report that
	  lies about the attempt you are about to make, which is exactly the argument
	  run_t_jumps is zeroed by the re-arm for.

	  run_st_dirty is taken from the movetype for the same reason run_t_dirty is on
	  the line below: arming while noclipping stays dirty, and a clean `!r` back
	  to the start genuinely resets it.
	*/
	e.run_st_armed   = FALSE;
	e.run_st_hold    = FALSE;
	e.run_st_fails   = 0;
	e.run_st_tp      = 0;
	e.run_st_ghost   = e.rec_gh_on ? TRUE : FALSE;
	// Build 44.  The stitch half zeroes here -- a save-lock load before the arm is
	// behind you.  The cheat half is a taint and is written with the others below.
	e.run_st_stitch  = FALSE;

	// The box cache is keyed on the SEGMENT, and an arm can change the TRACK
	// underneath it -- a bonus start has its own stage zones with the same
	// segment numbers.  Invalidate rather than re-resolve: the next tick that
	// needs it will, and doing it here would walk the zone table on every arm.
	e.run_st_zseg    = -1;

	/*
	  BUILD 19: the start has not happened yet, so hops are this attempt's
	  business again.  Cleared here rather than in SV_TimerStart because the
	  gesture being policed happens BEFORE the clock starts -- it is the jumping
	  you do while standing in the box.
	*/
	e.run_t_startok  = FALSE;
	e.run_t_jumps    = 0;

	/*
	  BUILD 20: AND THE AIR PHASE, WHICH BUILD 19 FORGOT.

	  This one line is why the whole rule shipped inert.  run_t_airsec is written
	  in exactly one place -- SV_TimerJumpWatch's phase clocks -- so it survives
	  the arm carrying the timestamp of whatever fall preceded it.  Every ordinary
	  route to a start zone follows a fall: `!r`, `!s`, `!b`, zone_goto, a map
	  fall-off teleport.  The next tick then read `time - run_t_airsec` as three or
	  ten seconds, satisfied the settle, and set run_t_startok before the player
	  had touched the keyboard.  From there the rule is skipped for the whole
	  attempt, because line "if (!e.run_t_startok)" gates it and only this function
	  ever clears the flag.

	  Zero rather than `time`, and it heals itself: the phase-clock writer at the
	  bottom of SV_TimerJumpWatch re-stamps it on the very next tick, so the
	  window restarts from the arm with one tick of slop against a 1.006s test.

	  run_t_groundsec is DELIBERATELY NOT RESET, and that is not an oversight.
	  Zero in that field means "the ground was never observed since going
	  airborne" -- the autohop case -- and the dwell test below reads it as
	  dwell 0, i.e. a hop.  Zeroing it here would flag the most ordinary start
	  there is: teleport in, stand, jump out.

	  run_t_lastvz needs nothing either.  SV_TimerJumpWatch already wrote it
	  earlier in this same tick, and an edge needs the CURRENT vz above the
	  threshold, which a stale one cannot manufacture.
	*/
	if (run_t_startstrict)
		e.run_t_airsec = 0;

	/*
	  The ONE place the noclip taint is cleared, and it is cleared from the
	  movetype at this instant rather than unconditionally.

	  Arriving in the start zone is what begins an attempt, so it is the right
	  moment to ask whether the attempt is clean -- and the honest answer is "are
	  you noclipping right now".  Fly in and it stays dirty through the arm, the
	  start, and the whole run.  Walk in, or `!r` back to it, and it resets, which
	  is what makes a legitimate retry a legitimate retry.
	*/
	e.run_t_dirty  = (e.movetype == MOVETYPE_NOCLIP);
	e.run_st_dirty = e.run_t_dirty;

	/*
	  BUILD 44: the cheat latch, cleared the same way and from a WIDER level.

	  Same sentence as the line above with sv_cheats added to it: arming with
	  cheats on stays cheated for the whole attempt, and turning them off and
	  walking back to the box genuinely resets it.  That is what makes the class a
	  statement about the run rather than about the moment it happened to be read.

	  The umbrella takes it too.  run_t_dirty is what SV_TimerStart consumes and
	  what every pre-build-44 test reads, so a cheat that did not raise it would be
	  a run marked `cheated` in one field and clean in the other.
	*/
	e.run_t_cheat  = SV_CheatLevel(e);
	e.run_st_cheat = e.run_t_cheat;
	if (e.run_t_cheat)
	{
		e.run_t_dirty  = TRUE;
		e.run_st_dirty = TRUE;
	}

	// A new attempt has been told nothing yet, so it can be told everything.
	// With run_t_flags, because it is a statement about what those said.
	e.run_t_said = 0;

	// Build 21.  Unconditional where the line above is not, and the asymmetry is
	// the point: "are you noclipping right now" is a live question, "did you hop
	// out of a start box you have just this moment re-entered" is not.  Arriving
	// here IS the re-arm, so it clears the forgivable taint outright.
	e.run_t_hopped = FALSE;

	// Arming begins a new attempt, so it is no longer a continuation of one.
	// TF_SHADOW goes with run_t_flags above; this is the half that lives outside.
	e.run_t_fromsave = 0;

	// Build 48.  It describes the attempt, so it dies with the attempt -- a
	// stale one would let the results card compare a fresh run against the
	// previous leg's best.
	e.run_t_pbwas = 0;

	e.run_t_pb = SV_PBGet(e.run_t_track, FS_LegOf(e.run_t_startseg, e.run_t_stagerun));
	if (e.run_t_pb > 0)
		e.run_t_flags = e.run_t_flags | TF_HAVEPB;
};

/*
  THE SAMPLED CLOCK.  Build 74 leaves it exactly as it was, and says here what it
  is, because until now the file did not.

  `time` is sv.time, which the engine advances ONCE PER SERVER FRAME -- so every
  usercmd inside a frame reads the same value, and since PlayerPostThink is
  called from SV_PostRunCmd (outside the engine's per-usercmd loop) this whole
  file runs once per PACKET anyway.  The number this returns is therefore a
  function of packet arrival and server frame pacing as well as of the player's
  inputs, which is why re-simulating a usercmd stream cannot reproduce it.

  Two comments elsewhere in this file overstate this and are corrected in build
  74 rather than left: run_t_stopat's essay calls this "the usercmd's own clock,
  so it is exact" -- it is sv.time, and it is exact only against the alternative
  that paragraph is rejecting (a `say` hook, whose `time` is physicstime and
  staler still); and SV_TimerFrame says it "is the only hook whose `time` is the
  usercmd's", which is true only in that same relative sense.

  NO LONGER THE RANKING CLOCK.  Build 76 made the counted clock the answer and
  left the sampled one here as the fallback for an engine that cannot count.
  Everything above still describes what the fallback IS; the paragraph below
  describes when it is reached.
*/

/*
  THE RUN'S TIME, IN TICKS.  Build 76.

  TWO BRANCHES AND THEY ARE NOT ALTERNATIVES -- the first is the clock, the
  second is what is left when there is no clock.  run_t_clock is latched once at
  SV_TimerStart and never re-read, so a run cannot change branch underneath its
  own recording.  See TF_NOCLOCK.

  THE COUNTED BRANCH IS SUBTRACTION, NOT DIVISION, and that is the whole point:
  the mover produced these ticks, so there is no rate to divide by, no rounding
  to do and nothing to disagree about.  run_t_frzticks comes off because the
  mover keeps running ticks for a player pinned by a save-lock hold (the pm_type
  test is INSIDE PMSrc_Tick, after the tick is spent), so a freeze is not free
  here the way it was on an origin-based clock.

  THE SAMPLED BRANCH IS BUILD 75'S FUNCTION VERBATIM, with `time - run_t_start`
  replaced by SV_TimerElapsed -- which, when run_movetickrate is 0, evaluates to
  exactly `time - run_t_startsec - run_t_frzsec`, i.e. the same number the old
  origin-shuffling produced.  Falsifier for the claim: on an engine without Patch
  325 this build must report the same tick count build 75 did for the same run.

  WHAT IT STILL DOES WHEN THERE IS NO RUN IS UNCHANGED AND STILL WRONG, and it is
  left alone deliberately rather than quietly improved.  Asked on an idle player
  it differences against a stale origin and answers with a number -- the defect
  sv_saveloc.qc's `ticks 0` guard was written for in build 17, and the same shape
  build 75 fixed in SV_TickReport.  Fixing it HERE would change what `cmd timer`
  and the save list print for a case they already handle, in a build whose whole
  job is to move the clock; two behaviour changes in one build make a falsifier
  ambiguous.  It is written down so the next reader does not conclude it was
  missed.
*/
float(entity e) SV_TimerTicks =
{
	local float ct;

	/*
	  ONE COPY OF THE ARITHMETIC, and the call is why SV_TickCounted is forward
	  declared beside this function rather than simply inlined here.  It was
	  written in build 74 as the REPORT's accessor and it is the CLOCK now; two
	  spellings of the same subtraction, one ranking and one reporting, is the
	  defect FS_TagName and FS_RunClass both exist to prevent -- and the two would
	  disagree exactly when something was wrong, which is when the report is read.
	*/
	if (e.run_t_clock)
	{
		ct = SV_TickCounted(e);
		if (ct >= 0)
			return ct;
	}

	if (run_t_tick <= 0)
		return 0;
	return floor(SV_TimerElapsed(e) / run_t_tick + 0.5);
};

/*
  THE COUNTED CLOCK.  Ticks of simulation this run actually consumed, excluding
  any spent with the clock held.

  -1 means "this run never latched", which is not the same as 0 and must never be
  reported as a time.  The counter is reset per MAP, so 0 is a real value -- it
  is what every player's counter reads for the first seconds after a map load --
  and that is exactly why the sentinel is -1.  See run_t_starttick.

  WHAT MAKES THIS THE HONEST UNIT.  It is what the mover did, so it is a function
  of the usercmd stream and nothing else: it does not move when a packet arrives
  late, when two commands land in one frame, or when the server hitches.  It is
  also invariant to a client under-reporting its command msec -- fewer ticks is
  both a slower player and a slower clock, where a wall clock would keep running.

  WHAT IT IS NOT.  It is not immune to sv_gamespeed: the mover scales its tick
  budget by gamespeed exactly as sv.time is scaled, so pms_lockedmovevars stays
  load-bearing for this clock too.  And it is bounded above by the engine's
  anti-speedcheat msec budget, which can drop a whole usercmd -- but a dropped
  command costs the player the MOVEMENT of that tick as well as the tick, so it
  buys nothing: you cannot reach an end zone without the ticks that carry you
  there.  That is the answer to "does a stalled input stream become a fast run",
  and it is the reason this is measured rather than gated in build 74.
*/
float(entity e) SV_TickCounted =
{
	if (e.run_t_starttick < 0)
		return -1;
	return (e.run_movetick - e.run_t_starttick) + e.run_t_tickcarry - e.run_t_frzticks;
};

/*
  The two clocks, side by side, as one line -- build 74's whole deliverable, and
  it is KEPT rather than retired now that one of the two has won.

  IT MEASURED THE THING THAT DECIDED THE MIGRATION.  Eighteen readings over a
  live lobby: the gap was 0, 1 or 2 ticks and the sampled clock was ALWAYS the
  larger, so it had been handing players times that were slightly too long, and
  moving to the counted one makes every stored time 0-2 ticks faster.  It also
  measured the thing that was NOT true: after eleven readings the gap looked
  bounded at 1, that bound was written down, and the next run measured 2.  A
  standing instrument is what turns a claim like that into a correction instead
  of a belief, which is why it stays on after the decision it informed.

  SO THE SAMPLED SIDE NEEDS AN ORIGIN THAT NOTHING ELSE READS, and that is
  run_t_startwall.  The migration removed the last sv.time origin from this file;
  a report that could only print the number that had already won would not be a
  comparison.  One float, one assignment in SV_TimerStart, and exactly one
  reader -- this function -- so it is incapable of moving a stored number however
  it is misread.

  `rate` IS THE ONE THAT CAN RUIN EVERYTHING QUIETLY, and it is printed first for
  that reason.  run_t_tick is this file's cached cvar("pm_ticrate");
  run_movetickrate is the number the mover actually divided by.  The day a tick
  count became the stored quantity -- which is this build -- a disagreement
  between them multiplies every leaderboard time by their ratio, and this tree
  has already shipped that class of bug once, in build 64, when bhop maps running
  0.01 were read against a 0.015 constant.  So it is compared on every report
  rather than assumed, and a mismatch says so in words.
*/
string(entity e) SV_TickReport =
{
	local float ct, st, mr;
	local string rate, which;

	/*
	  THE RATE LINE HAS THREE STATES, NOT TWO, and collapsing them is how this
	  would lie.  A zero run_movetickrate does NOT mean the mover used a tick
	  length of zero -- it means nothing published one, i.e. this QC is running
	  against an engine older than Patch 325, or against a build with the Source
	  mover off.  Reading that as a mismatch would print an alarming red line on
	  a perfectly healthy server, which is the sv_mapcheck failure shape: a check
	  whose two sides are not comparable, reporting confidently anyway.
	*/
	mr = e.run_movetickrate;
	if (mr <= 0)
		rate = sprintf("rate --/%g (no engine value)", run_t_tick);
	else if (fabs(mr - run_t_tick) > 0.0001)
		rate = sprintf("rate %g/%g  ^1MISMATCH^7", mr, run_t_tick);
	else
		rate = sprintf("rate %g", mr);

	/*
	  BUILD 76: WHICH ONE IS RANKING, said out loud on every report.

	  The previous three builds could leave this implicit because the answer was
	  always the same one.  It is not any more: a build-76 server on a pre-325
	  engine ranks the sampled clock and marks the run TF_NOCLOCK, and the person
	  most likely to hit that is whoever deploys the two halves in the wrong
	  order.  Reading it off `cmd timer` is much cheaper than reading it off a
	  board row three days later.
	*/
	which = e.run_t_clock ? "counted" : "^3sampled^7";

	ct = SV_TickCounted(e);
	if (ct < 0)
		return sprintf("tick: not latched  %s  ranks %s", rate, which);

	/*
	  THE SAMPLED SIDE IS SPELLED OUT HERE AND NOT TAKEN FROM SV_TimerTicks, which
	  used to be where it came from and now returns the counted clock.  The old
	  formula verbatim, against the report-only wall origin: floor(x/tick + 0.5).
	  Keeping the comparison honest costs one expression; deriving it from the
	  accessor would have printed a gap of zero forever and read as a clean bill.
	*/
	/*
	  THE FREEZE COMES OFF BOTH SIDES OR THE GAP STOPS MEANING ANYTHING.

	  run_t_frzsec is subtracted here too, and it is not a detail.  Build 75's
	  sampled clock DID stop during a hold -- it shifted its origin forward by the
	  frozen interval on every frozen tick -- so a faithful reproduction of it has
	  to remove that interval as well.  Without this, a two-second hold leaves
	  `sampled` permanently ~130 ticks ahead and the gap column reports the HOLD
	  rather than the clock model, for the rest of the run.  An instrument a
	  save-lock silently disables is worse than no instrument, because it carries
	  on printing.

	  A SIMULATED interval subtracted from a WALL difference, which is a mixed
	  unit and is deliberate.  The mover runs its ticks for a pinned player at
	  full rate -- that is the entire reason run_t_frzticks exists -- so the two
	  advance together across a hold and this is exact to the sub-tick.  The
	  alternative is a second accumulator in wall seconds that nothing else would
	  ever read, to remove an error smaller than the quantity being measured.
	*/
	st = ct;
	if (run_t_tick > 0)
		st = floor((time - e.run_t_startwall - e.run_t_frzsec) / run_t_tick + 0.5);

	return sprintf("tick: counted %g sampled %g gap %g  frz %g/%.4f  %s  ranks %s",
	               ct, st, st - ct, e.run_t_frzticks, e.run_t_frzsec, rate, which);
};

void(entity e, float ticks) SV_TimerFinish =
{
	local float pb, ispb, i, base, tag, leg;
	local string what;              // build 57: a stage run's finish names its stage

	e.run_t_state = TS_FINISHED;
	e.run_t_ticks = ticks;

	/*
	  BUILD 44 -- AN INSTALL THAT IS NOT WATCHING CANNOT CERTIFY ANYTHING.

	  `run_cheatwatch 0` turns off the sv_cheats observation, and the tempting
	  reading of that is "cheats no longer taint runs".  It cannot be allowed to
	  mean that: it would turn one cvar into a way to put a run on the clean board
	  that was made with the physics unlocked, which is the one thing the whole
	  ruleset lock exists to prevent.  So switching the watch off marks EVERY run
	  practice instead, and the cvar stays a bisection rather than becoming a
	  bypass.  One line, and saying it out loud is cheaper than pretending.

	  BEFORE SV_StageClose, deliberately -- the stage inside an uncertifiable run
	  is just as uncertifiable, and the close below is the last thing that could
	  write one to the stage board.
	*/
	if (!run_t_cheatwatch)
	{
		e.run_t_flags  = e.run_t_flags | TF_PRACTICE;
		e.run_t_dirty  = TRUE;
		e.run_st_dirty = TRUE;
	}

	/*
	  BUILD 24: the LAST stage ends here, and it is the one a boundary never
	  closes -- there is no stage zone after the final segment, only the end zone.

	  FIRST, before anything below writes a PB or a file: SV_StageClose slices out
	  of e.rec_rec_buf, and SV_RecClose further down deletes that buffer.  It also
	  has to run before run_pb_ticks is rewritten for the MAIN leg, or a run that
	  is a personal best on both would have its last stage compared against a
	  number from the wrong leg.
	*/
	SV_StageClose(e, ticks);

	/*
	  BUILD 57: THE LEG, and it keys everything below -- the best this run is
	  measured against, the slot a new best goes into, and (through
	  SV_RecFinalPath) the folder the recording is filed in.  A stage run's
	  finish also says which stage it was, so the console names the leg the
	  results card names.
	*/
	leg  = FS_LegOf(e.run_t_startseg, e.run_t_stagerun);
	what = "";
	if (e.run_t_stagerun)
	{
		if (e.run_t_track > 0)
			what = sprintf("^7bonus %g stage %g: ", e.run_t_track, leg);
		else
			what = sprintf("^7stage %g: ", leg);
	}

	pb   = SV_PBGet(e.run_t_track, leg);
	ispb = FALSE;

	/*
	  BUILD 48: KEEP IT, because in about twenty lines it will not exist any more.

	  The PB branch below writes this run's own time into
	  run_pb_ticks[track][leg], and then -- unconditionally, further down --
	  run_t_pb is re-read out of that same table.  So on every personal best
	  run_t_pb IS run_t_ticks, any delta taken from the pair is exactly zero, and
	  the finish row in the split column has drawn no number since build 19 on
	  precisely the runs somebody wanted a number for.

	  Latched HERE, one line after the read and before anything can overwrite it,
	  because this is the only instant at which "the time this run was measured
	  against" is still on the machine.
	*/
	e.run_t_pbwas = pb;

	if (e.run_t_flags & TF_SHADOW)
	{
		// A run resumed from a save.  Still a real time for the section you
		// were practising, and still worth printing -- it is the whole point of
		// the shadow run -- but it is not comparable with a run from the start
		// and is never written as a best.
		sprint(e, PRINT_HIGH,
		       strcat(what,
		              sprintf("^5%s^7 (shadow run from save %g -- not saved as a time)\n",
		                      SV_TimerString(ticks), e.run_t_fromsave)));
	}
	else if (e.run_t_flags & TF_PRACTICE)
	{
		sprint(e, PRINT_HIGH,
		       strcat(what, sprintf("^3%s^7 (practice -- not saved)\n",
		                            SV_TimerString(ticks))));
	}
	/*
	  PATCH 270, STAGE 2 -- a lobby finish, which is a real time and is not a
	  personal best.

	  Its own branch rather than an extra condition on the test below, because
	  the else-arm's "+delta (pb ...)" line would then be printed against a pb
	  of 0 -- SV_PBLoad loads nothing in a lobby -- and read as "you were 47
	  seconds slower than a time of zero".  ispb stays FALSE, which is what
	  keeps the run out of the best-named .rec slot as well.

	  The time itself is still printed, and still told to the client, because
	  the server measured it and it is the player's.

	  BUILD 57, STAGE T -- AND THE LINE USED TO SAY SOMETHING FALSE.  It read
	  "(lobby -- ranked on the server, not saved here)", which promised a ranking
	  that has never existed and denied a saving that now does: the CLIENT keeps
	  this time, in data/runs on the player's own PC, the moment this finish is
	  published (client/cl_lobbytime.qc, STAT_FS_FINREC).  Nothing is uploaded and
	  nothing is ranked anywhere, so the honest line names the only thing that
	  actually happens.

	  It says "saved" unconditionally because the writer's refusals are the
	  player's own records rather than the server's rules -- the client prints
	  `not a lobby best` itself when this time does not beat the one on disk, and
	  it is the only half of the system that can know.
	*/
	else if (Lobby_NoPB())
	{
		sprint(e, PRINT_HIGH,
		       strcat(what,
		              sprintf("^2%s^7 (lobby -- saved on your PC)\n",
		                      SV_TimerString(ticks))));
	}
	else
	{
		if (pb <= 0 || ticks < pb)
		{
			ispb = TRUE;
			/*
			  BUILD 57: BY LEG, AND BOUNDS-CHECKED FOR THE FIRST TIME.  The index
			  was track * 24 + startseg with no test at all, so a stage run past
			  the table's width wrote into the NEXT track's full-run best -- and
			  past the last track, off the end of the array.  Keying by leg moved
			  that edge one stage closer, so it is tested now rather than trusted.
			*/
			if (e.run_t_track >= 0)
			if (e.run_t_track < FS_MAXTRACKS)
			if (leg < FS_MAXSPLITS)
				run_pb_ticks[e.run_t_track * FS_MAXSPLITS + leg] = ticks;

			// Splits belong to the full-track PB only; a stage run has none.
			// BUILD 57: the flag, because a stage-1 run starts at segment 0 too, and
			// its empty split row would otherwise overwrite the map's.
			if (!e.run_t_stagerun && e.run_t_slot >= 0)
			{
				base = e.run_t_slot * FS_MAXSPLITS;
				for (i = 1; i < FS_MAXSPLITS; i = i + 1)
					run_pb_split[e.run_t_track * FS_MAXSPLITS + i] = run_run_split[base + i];

				// ...and so do checkpoints, for the same reason: a stage run's
				// clock is not comparable to a full run's at the same gate.
				base = e.run_t_slot * FS_MAXCPS;
				for (i = 1; i < FS_MAXCPS; i = i + 1)
					run_pb_cp[e.run_t_track * FS_MAXCPS + i] = run_run_cp[base + i];
			}
			SV_PBSave();

			if (pb > 0)
				sprint(e, PRINT_HIGH,
				       strcat(what,
				              sprintf("^2%s^7 -- personal best by ^2%s^7\n",
				                      SV_TimerString(ticks), SV_TimerString(pb - ticks))));
			else
				sprint(e, PRINT_HIGH,
				       strcat(what,
				              sprintf("^2%s^7 -- first time on this leg\n",
				                      SV_TimerString(ticks))));
		}
		else
			sprint(e, PRINT_HIGH,
			       strcat(what,
			              sprintf("^7%s  ^1+%s^7  (pb %s)\n",
			                      SV_TimerString(ticks), SV_TimerString(ticks - pb),
			                      SV_TimerString(pb))));
	}

	e.run_t_pb = SV_PBGet(e.run_t_track, leg);
	if (e.run_t_pb > 0)
		e.run_t_flags = e.run_t_flags | TF_HAVEPB;

	/*
	  A practice run is still written out -- it is a recording of what you did,
	  and the only thing the flag decides is whether it is a personal best.

	  FOUR NAMES NOW.  A shadow run is practice, so before build 17 it would have
	  gone to `_last` and overwritten the most recent ordinary run on that leg --
	  and those are exactly the two files you would want to compare.  Build 45
	  found the same sentence true of a cheated run and gave it the same answer.

	  THE ORDER OF THE LAST TWO TESTS IS FS_RunClass's PRECEDENCE, and it is not
	  cosmetic.  A run that loaded a save AND noclipped carries both bits; taken
	  as a shadow it would be written under a STAMPED name and accumulate one
	  cheated file per lap inside the archive the leaderboard ranks from.  Taken
	  as a cheat it lands in a single scratch slot.  Same run, same two bits, and
	  the ordering decides whether the archive grows junk.

	  ispb is not re-derived here.  A cheated run cannot reach it: TF_CHEAT
	  implies TF_PRACTICE, and the personal-best test above refuses practice --
	  so the RT_PB branch and the RT_CHEAT branch cannot both be live for one
	  run, and no ordering between them can be wrong.
	*/
	/*
	  BUILD 48: FIVE NAMES, AND THE NEW ONE IS AT THE BOTTOM OF THE LADDER.

	  RT_RUN is what is left when none of the other three applies: you ran the
	  leg, you were clean, and you were slower than your best.  That case used to
	  fall through to RT_LAST and overwrite the attempt before it -- one slot,
	  forty attempts an hour, and the archive kept exactly one of them.

	  WHAT THAT COST WAS THE MEANING OF `RANK`.  Only PB-beating runs were ever
	  archived, so every stamped file on a leg was faster than every file written
	  before it: a monotone improvement chain, not a distribution.  A personal
	  best was therefore rank 1 by construction and a slower run's rank counted
	  your own past bests rather than a field of attempts.  No amount of care on
	  the reading side could have fixed that; the data was never collected.

	  BELOW SHADOW AND CHEAT, not above, because both of those say something this
	  does not.  It is the residue, and residues go last.

	  rec_runarchive 0 restores build 47: clean non-improving runs go back to
	  overwriting last.rec.  READ LIVE rather than latched per map, unlike the
	  run_stage* rules -- this decides a FILENAME once per finish, not a physics
	  question per tick, and latching it would make the switch invisible until a
	  map change, which is the one thing a bisection must not be.
	*/
	/*
	  BUILD 58: the journal latch, re-read at the finish.

	  ABOVE the tag decision, not below, so that the flags word and the filename
	  are still two views of one value -- the invariant the comment under this
	  block states.  It cannot change which tag is chosen: the chain below tests
	  TF_CHEAT, TF_SHADOW and TF_PRACTICE only, and TF_NOJOURNAL is none of them
	  by construction.  It is placed here so that stays true if the chain ever
	  grows a branch, rather than relying on the order it happens to have.

	  The second call is what catches `rec_hid 0` typed mid-run; SV_TimerJournal
	  latches, so a run that started without a journal stays marked.

	  BUILD 62: the ruleset latch is re-read here for the same reasons, and the
	  same argument about the tag chain holds -- it tests TF_CHEAT, TF_SHADOW and
	  TF_PRACTICE only, and TF_NORULESET is none of them by construction.  This
	  is the call that catches both a ruleset opened mid-run and the
	  unlock-move-relock window that leaves every snapshot reading clean.
	*/
	SV_TimerJournal(e);
	SV_TimerRuleset(e, FALSE);

	// Build 72: and the input profile, which catches an `m_accel 1` typed after
	// the clock started AND the set-and-unset window that leaves both ends
	// reading clean.  Same shape, same reason.  See SV_TimerProfile.
	SV_TimerProfile(e, FALSE);

	// Patch 406: and the counts channel.  No latch function and no re-read --
	// rec_mc_sup is a COUNT taken per command across the whole run, so it
	// already carries the mid-run case the three above need a second call for.
	// Lex's call 2026-09-20: demote, do not kick.  See TF_NOCOUNTS.
	if (e.rec_mc_sup)
		e.run_t_flags = e.run_t_flags | TF_NOCOUNTS;

	tag = RT_LAST;
	if (ispb)
		tag = RT_PB;
	else if (e.run_t_flags & TF_CHEAT)
		tag = RT_CHEAT;
	else if (e.run_t_flags & TF_SHADOW)
		tag = RT_SHADOW;
	/*
	  BUILD 66: ON A LOBBY THE ARCHIVE IS NOT OPTIONAL.

	  rec_runarchive is read LIVE, at the finish, so it is not the kind of
	  setting a config file can pin -- `rcon rec_runarchive 0` changes it for
	  the next finish on a running server.  At 0 a clean lobby run falls through
	  to RT_LAST, which is a FIXED name, and SV_RecClose's fremove-then-frename
	  means that player's next finish DESTROYS the previous recording, with a
	  dprint as the only trace.

	  That is the one live path from today's configuration back to losing runs,
	  and it exists on the servers whose whole point since build 66 is that they
	  keep everything (rec_runs_keep 0).  Nothing on a lobby wants the build-47
	  behaviour: nobody browses a public server's disk for their last attempt,
	  and surfd's ledger now indexes every kept file by name.  The operator's
	  lever for "stop writing recordings" is rec_enable 0, which stops writing
	  them -- not a switch that quietly turns archiving into overwriting.

	  On a personal disk it still means what it always meant, so the cvar is
	  unchanged everywhere else.
	*/
	else if (Lobby_Active() || cvar("rec_runarchive"))
	if (!(e.run_t_flags & TF_PRACTICE))
		tag = RT_RUN;

	// The flags as they stand HERE, which is after every taint has been applied
	// and after the tag has been decided from them -- so the header line and the
	// filename are two views of one value rather than two reads of a field.
	SV_RecClose(e, ticks, tag, e.run_t_flags);

	/*
	  BUILD 57, STAGE T -- THE FINISH, TOLD TO THE CLIENT IN ONE BREATH.

	  LAST, after SV_RecClose, because this is the first instant at which every
	  one of the four is final: the cheatwatch block at the top of this function
	  can still add TF_PRACTICE, SV_StageClose can still taint, and SV_RecClose
	  strips TF_RECORDING -- so flags read any earlier would describe a run that
	  was still being decided.

	  WHY IT IS PUBLISHED AT ALL, when RUNTAG/RUNTICKS/RUNLEG say the same things
	  twenty lines up: those three are written by SV_RecClose, which a lobby never
	  reaches (Lobby_NoRec leaves no buffer to close), and TS_FINISHED can be
	  skipped outright by a pend-arm inside this same server frame.  This group is
	  the one statement of "a leg ended" that survives both.  See STAT_FS_FINREC.

	  UNCONDITIONAL, lobby or not.  A counter that only ran in lobbies would be a
	  rule to remember at the one site that owns the finish, and the client already
	  has the gate it needs in STAT_FS_LOBBY.

	  THE COUNTER IS BUMPED LAST so that no snapshot can carry the edge ahead of
	  the values it describes -- the same ordering the stage triple above uses, for
	  the same reason.  FINLEG is spelled exactly as RUNLEG is at the three sites
	  that write rec_rec_leg (track * 100 + leg + 1, so 0 can mean "no run"), from
	  the local `leg` rather than re-read from the recorder's field, because the
	  recorder may never have opened a buffer for this run.
	*/
	e.run_t_finticks = ticks;
	e.run_t_finleg   = e.run_t_track * 100 + leg + 1;
	e.run_t_finflags = e.run_t_flags;
	e.run_t_finrec   = e.run_t_finrec + 1;

	/*
	  BUILD 64, STAGE 3 -- AND OFF TO THE LEADERBOARD, IF THIS SERVER HOLDS A KEY.

	  LAST IN THE FUNCTION, after SV_RecClose and after the finish group above,
	  for the same reason that group is where it is: this is the first instant at
	  which e.run_t_flags is final.  The cheatwatch block at the top can still add
	  TF_PRACTICE, SV_StageClose can still taint, SV_TimerJournal and
	  SV_TimerRuleset both latch twenty lines up, and SV_RecClose strips
	  TF_RECORDING.  Flags read any earlier describe a run that was still being
	  decided -- and the flags word is what surfd derives the row's STYLE from and
	  what demotes it out of the ranked tier, so reading it early would not fail
	  loudly, it would file the run on the wrong board.

	  UNCONDITIONAL FROM HERE.  Every gate belongs to Lobby_SubmitRun -- no
	  directory, no key, no identity, no time -- and repeating any of them here
	  would be a second place for the "which runs go up" rule to live.  In
	  particular this does NOT test for practice or cheated: surfd owns that
	  question and answers 204, which is not an error.  See the essay there.

	  A LOBBY FINISH SUBMITS LIKE ANY OTHER, which is the point rather than an
	  oversight: the keyed lobbies ARE the official servers, so a time set in
	  front of other players is exactly the run the ranked board exists for.
	  What a lobby does not do is keep a personal best (Lobby_NoPB), and that is
	  a different question about a different disk.
	*/
	// Patch 371: a new server best is told to the others where no board answers
	// finishes (Lobby_RunReply speaks there): one finish, one line.
	if (ispb)
	if (leg == 0)
	if (FS_RunClass(e.run_t_flags) == RC_CLEAN)
	if (!Lobby_BoardAnswers())
	if (Lobby_AnnOn())
	if (Lobby_AnnGate(e, 0, e.run_t_track))
		Lobby_SayOthers(e, sprintf("^5board:^7 %s set the server best on %s -- %s%s\n",
		                Lobby_ChatName(e), Lobby_Where(e.run_t_track), SV_TimerString(ticks),
		                (pb > 0) ? strcat(", ", SV_TimerString(pb - ticks), " faster") : ""));

	Lobby_SubmitRun(e, e.run_t_track, leg, ticks, e.run_t_flags,
	                SV_RecKeptLeaf(e), e.rec_rec_bytes, e.rec_rec_full);
};

void(entity e, float seg, float ticks) SV_TimerSplit =
{
	local float pbs;

	/*
	  BUILD 24: close the stage that just ended, THEN write the boundary record,
	  THEN open the next one.  The order is the slice's definition.

	  SV_StageClose takes [run_st_line, rec_rec_lines) -- so it must run before the
	  `stage` record below is appended, or the last line of every stage demo would
	  be the boundary that ended it, which the slicer would then have to strip
	  back out.  And SV_StageOpen must run after, so the next stage's first line
	  is the first SAMPLE rather than that record.
	*/
	SV_StageClose(e, ticks);

	e.run_t_seg   = seg;
	e.run_t_split = ticks;
	e.run_t_delta = 0;

	if (e.run_t_slot >= 0 && seg > 0 && seg < FS_MAXSPLITS)
		run_run_split[e.run_t_slot * FS_MAXSPLITS + seg] = ticks;

	// Patch 270, Stage 2: and not in a lobby.  SV_PBGet grew the read-side gate
	// but these two tables are indexed directly, so gating only the accessor
	// left the SPLIT and CHECKPOINT deltas still being taken against whatever
	// the host's best.pb happened to hold -- a running "+2.31" against a
	// stranger's ghost, on every stage boundary, which is the same wrong
	// number the finish card was fixed not to show.
	if (seg > 0 && seg < FS_MAXSPLITS && !Lobby_NoPB())
	{
		pbs = run_pb_split[e.run_t_track * FS_MAXSPLITS + seg];
		if (pbs > 0)
			e.run_t_delta = ticks - pbs;
	}

	SV_RecPut(e, sprintf("stage %d %d", seg, ticks));

	SV_StageOpen(e, seg, ticks);

	// BUILD 43: a genuinely different stage, so its counters start again.  NOT
	// in SV_StageOpen, which a fail also goes through -- see the field block.
	e.run_st_fails = 0;
	e.run_st_tp    = 0;
};

/*
  A checkpoint crossed while running.  Build 19, and it is SV_TimerSplit again
  on purpose -- same three fields written in the same tick, so the client can
  read CPT and CPD on the CP edge with no race, which is the one safety property
  the stage triple has that is worth copying exactly.

  The caller has already established that this is a forward crossing on our own
  track; see the checkpoint block in SV_TimerFrame.
*/
void(entity e, float cpn, float ticks) SV_TimerCheckpoint =
{
	local float pbc;

	e.run_t_cpmax   = cpn;
	e.run_t_cpn     = cpn;
	e.run_t_cpticks = ticks;
	e.run_t_cpdelta = 0;

	if (e.run_t_slot >= 0 && cpn > 0 && cpn < FS_MAXCPS)
		run_run_cp[e.run_t_slot * FS_MAXCPS + cpn] = ticks;

	// Full-track runs only, matching run_pb_split: a stage run reaches a gate
	// with a clock that started somewhere else, so the comparison is meaningless.
	// Patch 270, Stage 2: and not in a lobby -- the twin of the split gate a few
	// lines up, and for the same reason.  Both tables are read directly here
	// rather than through SV_PBGet, so the accessor's gate does not cover them.
	// BUILD 57: run_t_stagerun rather than `startseg == 0`, which a stage-1 run
	// shares with a full run -- every stage run is refused alike.
	if (!e.run_t_stagerun && cpn > 0 && cpn < FS_MAXCPS && !Lobby_NoPB())
	{
		pbc = run_pb_cp[e.run_t_track * FS_MAXCPS + cpn];
		if (pbc > 0)
			e.run_t_cpdelta = ticks - pbc;
	}

	e.rec_rec_cp = e.rec_rec_cp + 1;

	// The ORDINAL, where this used to write zone_seg[] -- which on a linear map
	// is 0 for every checkpoint on the map, so every record read `cp 0 <ticks>`
	// and no reader could tell them apart.
	SV_RecPut(e, sprintf("cp %d %d", cpn, ticks));
};

/*
  A stage or end zone crossed WHILE RUNNING.  Nothing here arms anything --
  arming is a separate question about a possibly different zone, asked below.
*/
void(entity e, float z) SV_TimerEvent =
{
	local float ty, sg, ticks;

	if (e.run_t_state != TS_RUNNING)
		return;
	if (zone_track[z] != e.run_t_track)
		return;

	ty = zone_type[z];
	sg = zone_seg[z];
	ticks = SV_TimerTicks(e);

	if (ty == ZONE_END)
	{
		SV_TimerFinish(e, ticks);
		return;
	}

	/* ZONE_STAGE */
	if (e.run_t_stagerun)
	{
		// A stage run ends at the NEXT stage boundary.  Anything else is you
		// wandering backwards, which is not a finish.
		//
		// BUILD 57: the flag, not `startseg > 0`.  A stage-1 run begins at
		// segment 0 and finishes on entering segment 1, then hands over to stage
		// 2 through run_t_pendarm exactly as every other stage run does.
		if (sg == e.run_t_startseg + 1)
		{
			SV_TimerFinish(e, ticks);

			// ...and this zone is also where the next stage run begins.  Held
			// over until you LEAVE it (see run_t_pendarm), so the time you just
			// set is not replaced by a zero on the same tick.
			e.run_t_pendarm = z;
		}
		return;
	}

	// A full-track run: a stage boundary is a split, and the run continues.
	// Out of order (skipped one, or came back up one) is left alone rather
	// than guessed at.
	if (sg == e.run_t_seg + 1)
		SV_TimerSplit(e, sg, ticks);
};

/*
==============================================================================
  BUILD 83: THE RANDOMIZED START.

  Displace the player by a small random amount at the instant the clock starts,
  so that an input stream replayed from a recording enters the map somewhere the
  recording did not.  Announced as a GAME RULE -- see run_startjitter, where the
  cost to the honest player is written down.

  WHY IT IS SAFE TO WRITE A POSITION HERE, which is a thing this file has never
  done before (there was no setorigin in sv_timer.qc until this build):

    - IT MUST NOT CALL SV_TimerWarped.  That function EMPTIES THE PADDING RING
      (rec_pad_len/rec_pad_head), and SV_RecOpen's flush is the ring's only
      reader -- so warping here would silently replace every run's ~3.8 s of
      recorded approach with nothing, and no check in the tree would say so.
      It is also not needed: SV_TimerFrame's last statement is
      `e.run_t_lastorg = e.origin`, downstream of all four SV_TimerStart call
      sites, so the next tick's swept zone segment already begins at the
      displaced origin.  Called after SV_StageOpen it would be worse still --
      run_st_seg is >= 0 by then, so every run would report `teleports 1` for a
      move the game itself made.

    - IT MUST NOT CALL SV_TimerPractice OR SV_TimerCheat.  The game moved the
      player; the player did not.  Those are the two funnels that would print a
      class word at somebody for obeying a rule we imposed.

    - IT MUST NOT RE-ENTER THE START BOX, and this is the failure that would not
      show up in a same-tick test.  The start fired because the HULL cleared
      run_t_armzone (see SV_TimerFrame).  A nudge back toward the box can put the
      hull inside again, and on the NEXT packet SV_TimerTryArm's re-arm branch
      (run_rearmstops, default 1) throws the attempt away with `run cancelled
      (back in the start)`.  On a bhop map the sibling branch does something
      quieter and worse -- it re-derives run_t_dirty and run_t_cheat from the
      live movetype.  So every candidate is tested with SV_ZoneIn against the
      SAME zone and the SAME hull the start itself used, because a second
      speller of "inside the box" is the drift this file keeps writing essays
      about.

    - IT MUST NOT EMBED THE PLAYER.  setorigin neither tests for solidity nor
      runs touch functions (which is separately why the nudge cannot fire a
      trigger).  Two units is small, but start boxes sit flush against floors
      and walls all over this library, so every candidate is traced with the
      ruleset's own hull and a blocked one is simply not taken.

  FOUR TRIES AND THEN NOTHING, which is a real decision rather than a loop bound.
  One try would mean a player who starts in a corner defeats the rule by standing
  there -- the roll fails, the run begins exactly where it did last time, and an
  MMR replays it.  Four independent directions make "blocked every way" require
  being genuinely boxed in.  When it does happen the offset applied is zero, the
  header records `0 0 0`, and a reader can see that the rule ran and found
  nowhere to go -- which is a different fact from the rule being off, and the
  header keeps them different.

  RECORDED, NEVER RE-DERIVED.  Patch 419 draws it from the OS, so this number
  exists once and nothing can recompute it; before 419 the same held for the
  weaker reason that random() is unseeded.  See .run_t_jitter.
==============================================================================
*/
float(entity e) SV_RunStartJitter =
{
	vector mn, mx, base, off, cand;
	float  mag, tries, ok, wasin;

	e.run_t_jitter = '0 0 0';

	mag = run_t_startjit;
	if (mag <= 0)
		return FALSE;

	base = e.origin;
	mn   = SV_RunHullMins(e);
	mx   = SV_RunHullMaxs(e);

	// Where the player stands RIGHT NOW by the arm scan's own reckoning.  The
	// invariant every candidate must hold is that this answer does not move --
	// see the essay at the test below for why it is the answer and not the
	// position that matters.
	wasin = FALSE;
	if (e.run_t_armzone >= 0)
		wasin = SV_ZoneOcc(e.run_t_armzone, base, mn, mx);

	tries = 0;
	while (tries < 4)
	{
		tries = tries + 1;

		/*
		  WHICH END IS OPEN DEPENDS ON THE BRANCH, and both are legal offsets.
		  random() is documented in sv_defs.qc as able to return exactly 1.0, so
		  the fallback gives a CLOSED interval [-mag, +mag]; Patch 419's
		  fs_randomf is [0,1), so the OS branch gives [-mag, +mag) -- the
		  attainable endpoint moved from the top to the bottom.  Stated rather
		  than clamped either way: an endpoint is a legal offset and clamping it
		  would bias an extreme by one ulp for no reason.  z is left at 0.
		*/
		/*
		  PATCH 419: the OS, not random().  This offset is written to the header
		  at four decimals and applied to the player's own body, so every draw is
		  published; the rule exists so a run cannot be planned against a known
		  start, and a draw a reader can name is not that.

		  IT DOES NOT MAKE THE RULE WHOLE, and the review that asked for this
		  sentence is right.  The accepted offset is uniform only CONDITIONED on
		  the tests below -- and on the point mass at exactly (0,0) when all
		  tries fail, which the header states as `startjit <u> 0 0 0`.  The
		  geometry is the player's choice: stand where the loop cannot succeed
		  and the start is exactly known on every run.  Entropy cannot fix a
		  conditioned distribution; only the candidate rule can, and that is not
		  this patch.
		*/
		off_x = (SV_Rand01() - 0.5) * 2 * mag;
		off_y = (SV_Rand01() - 0.5) * 2 * mag;
		off_z = 0;
		cand  = base + off;

		// Can the hull actually get there?  Trace rather than point-test: the
		// destination being empty says nothing about a 32x32x62 box reaching it.
		tracebox(base, mn, mx, cand, FALSE, e);
		if (trace_fraction < 1)
			continue;
		if (trace_startsolid)
			continue;
		if (trace_allsolid)
			continue;

		/*
		  AND DOES IT CHANGE WHETHER THE PLAYER OCCUPIES THE START BOX?

		  NOT "is it outside the box", WHICH WAS THE FIRST CUT AND WAS INERT ON
		  EVERY BHOP MAP.  The reasoning that produced it was that the start
		  fires when the hull leaves the box, so a candidate back inside would
		  re-arm -- true for a walk-out start and false for the other kind.  A
		  bhop map starts the clock ON THE JUMP (run_starthop), with the player
		  standing squarely in the box: every candidate is "inside", all four
		  tries are refused, and the rule applies nothing on every run forever.
		  Measured on the first capture, and the header is what said so --
		  `startjit 2.0000 0.0000 0.0000 0.0000`, the three-state design earning
		  its keep on its first outing, because a writer that omitted the key
		  when nothing was applied would have produced a silent inert feature
		  indistinguishable from one that was switched off.

		  THE HAZARD IS THE RE-ARM CANCEL AND ITS TRIGGER IS A CHANGE, not a
		  position.  SV_TimerFrame's arm scan computes `az` and acts only on
		  `az != e.run_t_azone`; so a candidate that leaves the answer alone
		  cannot cancel anything, whether the answer is "inside" or "outside".
		  Hold the occupancy invariant and the whole class is closed at both
		  kinds of start.

		  AND IT IS SV_ZoneOcc, NOT SV_ZoneIn.  The arm scan asks SV_ZoneOcc,
		  which reads run_t_hullocc (run_zone_hull >= 2); SV_ZoneIn reads
		  run_t_hullevt (>= 1).  At the shipped ruleset those differ -- the arm
		  is a POINT test and the start is a HULL test -- so guarding with
		  SV_ZoneIn refused a band one hull-width wide in which nothing bad
		  happens.  "Use the predicate the start fired on" was the wrong rule;
		  the right one is to use the predicate THE HAZARD fires on.

		  Nested rather than `&&`: QC's && is OP_AND and evaluates BOTH sides,
		  and SV_ZoneOcc indexes the zone arrays by z -- an out-of-range READ
		  aborts the whole VM, so a negative armzone must never reach it.  This
		  file has already paid for that once.
		*/
		ok = TRUE;
		if (e.run_t_armzone >= 0)
		{
			if (SV_ZoneOcc(e.run_t_armzone, cand, mn, mx) != wasin)
				ok = FALSE;
		}
		if (!ok)
			continue;

		setorigin(e, cand);
		e.run_t_jitter = off;
		return TRUE;
	}

	return FALSE;
};

void(entity e) SV_TimerStart =
{
	local float pr, ln;

	e.run_t_state = TS_RUNNING;
	e.run_t_ticks = 0;

	/*
	  BUILD 74/76: THE CLOCK STARTS, AND IT IS ONE READING TAKEN TWO WAYS.

	  Latched HERE and not at the arm, because the arm is not the start: you can
	  stand in a start box for a minute before leaving it, and those ticks are not
	  run time.  SV_TimerArm sets the sentinel; this takes the reading.

	  ONE CALL TO SV_ClockSec, INTO A LOCAL.  run_t_startsec and run_t_lastsec
	  must be the same number or the very first freeze accumulates a delta that
	  never happened.  Two calls would give the same answer today and that is
	  exactly the argument for taking one now, while the invariant is cheap to
	  state: everything a run's clock is built from comes from a single instant.

	  run_t_clock IS DECIDED HERE AND NOWHERE ELSE, for the life of the run.  It
	  is the guarantee that no recording can contain two clocks, which is the one
	  hazard that made this migration have to land whole -- re-basing the tick
	  accessor without the seconds one, or reading the engine field live in each,
	  would put a counted `ticks` beside a sampled `t` column in the same .rec and
	  nothing in the file would say so.  See TF_NOCLOCK, which is what a 0 here
	  costs the run at the finish.
	*/
	e.run_t_clock     = (e.run_movetickrate > 0);
	e.run_t_startsec  = SV_ClockSec(e);
	e.run_t_starttick = e.run_movetick;
	e.run_t_tickcarry = 0;
	e.run_ms_sessions = 0;
	e.run_t_frzticks  = 0;
	e.run_t_frzsec    = 0;
	e.run_t_lastmt    = e.run_movetick;
	e.run_t_lastsec   = e.run_t_startsec;
	e.run_t_startwall = time;       // report only -- see the field

	// Leaving the start zone is the reset you asked for: the stopped time from
	// the last attempt comes off the screen here and not before, so it is still
	// readable for the whole time you spend standing in the box.
	e.run_t_stopat = 0;

	/*
	  Something touched this attempt before the clock started.  The state is
	  RUNNING now, so this is the first moment SV_TimerPractice can say so --
	  see the latch essay there.  Before SV_RecOpen, so the run is already
	  flagged when the recording opens.

	  BUILD 21: run_t_hopped joins run_t_dirty here, and this is the only place
	  the two are treated alike.  Leaving the box is the deadline for taking a
	  hop back -- past it the taint is as final as the noclip one, which is why
	  nothing downstream needs to know which of the two it was.
	*/
	/*
	  BUILD 44: THE CHEAT LATCH IS CONSUMED FIRST, and the order is the whole
	  point rather than a detail.

	  SV_TimerCheat calls SV_TimerPractice itself, so running it first means a run
	  that was noclipped into the box comes out of here labelled `cheated` -- and
	  running it second would leave the umbrella already up, the class print
	  already spent on the word `practice`, and the header carrying a bit the
	  player was never told about.  Same reason shadow is tested before practice
	  everywhere on the client.

	  run_t_hopped stays with run_t_dirty and is deliberately NOT a class: a hopped
	  start is neither a cheat nor a stitch, and it is the whole of what the
	  residual `practice` word means on a file written after this build.
	*/
	// Patch 403: THE LATCH CLAMP, and it has to be here rather than one level up.
	// The per-tick call only sees the body while it is still inside the box; a
	// push volume that reaches past the box (bhop_arcane's stack, surf_666's
	// bonus-3 start) hands over a fresh carrier on the crossing tick itself.
	// Above the taint chain and therefore above SV_RecOpen, so the clamped
	// velocity is what `seed` states and a replay reproduces it.
	SV_StartCapClamp(e);

	if (e.run_t_cheat)
		SV_TimerCheat(e);
	else if (e.run_t_dirty || e.run_t_hopped)
		SV_TimerPractice(e);

	// Build 58: before SV_RecOpen for the same reason the latches above are --
	// so the recording's header is written with the run already flagged.  It is
	// NOT part of the if/else chain: a missing journal is not a taint class and
	// is orthogonal to all three of them.  See SV_TimerJournal.
	SV_TimerJournal(e);

	// Build 62: same placement and the same argument -- before SV_RecOpen, not
	// in the if/else chain.  The start call also LATCHES the *ruleset sequence
	// number, which the finish call differences against; without it the mid-run
	// unlock-and-relock window is invisible.  See SV_TimerRuleset.
	SV_TimerRuleset(e, TRUE);

	// Build 72: likewise before SV_RecOpen.  The start call LATCHES the client's
	// off-profile counter, which the finish call differences against; without it
	// an m_accel set and unset inside the run is invisible at both ends.  Exactly
	// the ruleset's argument one line up.  See SV_TimerProfile.
	SV_TimerProfile(e, TRUE);

	// Build 73: and the map, before SV_RecOpen for the same reason as the three
	// above -- so the recording's header is written with the run already flagged.
	// No finish call: neither side of this one can change inside a run.  See
	// SV_TimerMap.
	SV_TimerMap(e);

	// Build 76: and the clock.  Before SV_RecOpen like the four above, and here it
	// is load-bearing rather than tidy -- the header writes `clock counted` or
	// `clock sampled` from run_t_clock, and the board reads TF_NOCLOCK, so the
	// file and the row have to be stamped from one latch taken before either is
	// written.  See SV_TimerClock.
	SV_TimerClock(e);

	/*
	  Build 83: and the start jitter, last of the six and for a reason the other
	  five do not have.  They latch FACTS about the run so the header carries
	  them; this one CHANGES the run, and it has to happen before SV_RecOpen for
	  two independent reasons:

	    - the header states the offset, and the header is written below;
	    - SV_RecOpen flushes the pre-start padding ring and SV_TimerRecFrame
	      writes this packet's first real sample immediately after SV_TimerFrame
	      returns, so a displacement applied here lands in the file as the run's
	      opening position rather than as an unexplained jump between two
	      samples.  That is the whole shape E3 said was missing.

	  AFTER the taint chain above, deliberately.  The run's class is already
	  decided by this point, so nothing here can be mistaken for something the
	  player did -- which is the mistake a later edit would otherwise make.
	*/
	SV_RunStartJitter(e);

	SV_RecOpen(e);

	/*
	  BUILD 24: the run's first segment is also a stage, and it opens here.

	  AFTER SV_RecOpen, because run_st_line is an index into the buffer that call
	  creates -- opening before it would record a line number from the previous
	  run's buffer, and slicing from it would hand out somebody else's samples.

	  For a full run this is segment 0, which BUILD 57 writes as stage 1 when it
	  closes at the stage-2 boundary -- it used to be refused as `main`, which
	  is the whole run and not its first stage.  It qualifies on the run's own
	  start rules, and the literal 0 below is how SV_StageQualifies knows the
	  stage began here rather than at a resume.  For a stage run
	  (run_t_stagerun) it is that stage, and SV_StageClose refuses it -- a stage
	  run writes itself through SV_TimerFinish like any other leg.

	  BUILD 43: AND IT IS OPENED DISARMED, which is one line and was a visible bug
	  without it.

	  SV_TimerFrame's stage block refuses segment 0 and refuses a stage run
	  outright -- the run's own arm/start machine already owns both of those, and
	  running two of them over one box would rebase a clock the run had just set.
	  So nothing ever clears the arm for this one stage, and a scripted run caught
	  it sitting `armed 1` for the whole opening leg of every run.  Harmless on
	  the server, where only the block that refuses it reads the flag -- and NOT
	  harmless on the HUD, which since this build draws the word `armed` from it
	  and would have shown it from the start zone to the first boundary.

	  The arm rule therefore reaches exactly the boundaries in the middle, which
	  is where the request lives.
	*/
	// Patch 360: the opening stage is judged here, and its takeoff must follow
	// the arm (a primed jump outside, flown or landed into START, is not a start).
	// SV_StageOpen clears the verdict, so it is carried across.
	SV_StageLaunch(e);
	if (e.run_st_launchsec < e.run_t_armsec)
		e.run_st_prime = FALSE;
	pr = e.run_st_prime;
	ln = e.run_st_launch;
	SV_StageOpen(e, e.run_t_startseg, 0);
	e.run_st_prime  = pr;
	e.run_st_launch = ln;
	e.run_st_armed = FALSE;
	e.run_st_fails = 0;
	e.run_st_tp    = 0;
};

/*
  Standing in a zone a run could begin from.

  While RUNNING only a START zone acts -- falling back into the start of a
  leg restarts it, which is what every surf timer does and what players
  expect.  A stage zone while running is an EVENT (a split), never an arm, or
  a staged map would reset its own run at every boundary.
*/
void(entity e, float z) SV_TimerTryArm =
{
	local float stop, stops;

	/*
	  On bhop, merely entering a START is not a new attempt while a clock is live
	  or finished.  Keep that time and its recording intact until the player
	  makes a dwell-qualified initial jump inside the box; SV_TimerJumpWatch then
	  performs Arm+Start in one tick.  Walking through the box changes nothing.

	  Reset the pending attempt's noclip latch at the same boundary an ordinary
	  Arm would.  If noclip is used after entry, SV_TimerPractice sets it again,
	  and the jump watcher carries it across the deferred Arm.

	  IDLE still arms on entry, so walking out remains the fallback start.  ARMED
	  can switch to another start normally.  Stage zones are unchanged: this is a
	  rule about the map/bonus START, not the independent stage-run handover.
	*/
	if (run_t_bhopjump)
	if (zone_type[z] == ZONE_START)
	if (e.run_t_state == TS_RUNNING || e.run_t_state == TS_FINISHED)
	{
		e.run_t_dirty = (e.movetype == MOVETYPE_NOCLIP);
		// Build 44: and the class latch on the same boundary, from the same kind
		// of level read.  Leaving it standing would make a bhop map's deferred arm
		// the one route by which `cheated` outlives the attempt that earned it.
		e.run_t_cheat = SV_CheatLevel(e);
		if (e.run_t_cheat)
			e.run_t_dirty = TRUE;
		// Build 57: walking into a START ends a stage-1 request here too.  This is
		// the walk-in on a bhop map, and the jump that commits it arms through
		// SV_TimerArm with no chance to ask.  See the block below.
		e.run_t_wantstage1 = FALSE;
		return;
	}

	stops = FALSE;
	if (e.run_t_state == TS_RUNNING)
	{
		if (zone_type[z] != ZONE_START)
			return;
		if (run_t_rearmstops)
			stops = TRUE;
	}

	/*
	  BUILD 57: WALKING INTO A START ENDS A STAGE-1 REQUEST -- you are at the map's
	  start and it arms the map, which is what a START has always meant.  `!s 1`
	  is how to ask for stage 1, and `!r` inside a stage-1 run keeps it.

	  EXCEPT THE RE-ARM OF THE BOX YOU ARE ALREADY ARMED IN, and without this the
	  request would not survive one tick.  SV_ZoneMove arms the destination
	  itself, and the next tick's scan sees that same START as newly entered and
	  calls here again -- the idempotent re-arm SV_ZoneMove's own essay describes.
	  `!s 1` and `!r` both arrive that way, and so do a restored ARMED save and a
	  step back in from the hull band around the box.  None of those is arriving
	  at the start; each is standing in the attempt that is already armed.
	*/
	if (zone_type[z] == ZONE_START)
	if (!(e.run_t_state == TS_ARMED && e.run_t_armzone == z))
		e.run_t_wantstage1 = FALSE;

	/*
	  BUILD 20: THE STOPPED CLOCK, AND WHY IT IS LATCHED HERE.

	  Build 19 put the latch in SV_TimerVoid, which is right for `!r` and wrong
	  for everything else, because SV_TimerArm has three call sites and only the
	  sv_zones.qc one is preceded by a void.  Walking, falling or being teleported
	  back into the start box while RUNNING reaches the arm through THIS function
	  with no void anywhere on the path -- so run_t_stopat stayed 0, SV_TimerStopFrame
	  found nothing to restore, and the readout snapped to 0:00.000.

	  IT MUST NOT MOVE ONE LEVEL DOWN INTO SV_TimerArm.  The FINISHED->pendarm
	  stage handover calls SV_TimerArm DIRECTLY, so a latch there would stop the
	  clock at every stage boundary on every staged map -- the run would go grey
	  and read the previous stage's time on the way into the next one.

	  Order matters twice: read run_t_ticks BEFORE the arm, which zeroes it, and
	  set the flag AFTER the arm, which zeroes run_t_flags.
	*/
	stop = e.run_t_ticks;
	SV_TimerArm(e, z);
	if (stops)
	{
		SV_TimerStopAt(e, stop);
		sprint(e, PRINT_HIGH, "^3run cancelled^7 (back in the start)\n");
	}
};

/*
===========================================================================
  The per-tick scan.

  ONE pass over the zone table answering all four of the timer's questions,
  rather than four passes.  Zone_PointInside rejects on the AABB first
  (sh_zones.qc), so the common case -- 250-odd zones none of which you are
  anywhere near -- is a handful of compares each.

  allowBhop and overbounce are skipped outright: 3217 of the library's
  regions are allowBhop, up to 68 on a single map, and the timer has no
  opinion about any of them.

  TWO DIFFERENT TESTS, on purpose.

    arming (start/stage)     WHERE YOU ARE -- a point test.  You arm by
                             standing in a start box, and "am I still in the
                             box I armed in" is the question that starts the
                             clock.  A swept test there would arm you off a
                             box you flew past.
    events (stage/end/cancel/checkpoint)
                             WHERE YOU WENT -- a swept test against the
                             segment travelled this tick.  Crossing a line is
                             an event, and 101 of the library's regions are
                             thin enough that a point sampled at 66.67 Hz
                             goes straight through them.

  A stage zone is in both sets and gets both tests, which is the whole reason
  the two questions are separate.
===========================================================================
*/
/*
  One sample of the run, per tick.

  Split out of SV_TimerFrame by build 30 so the GHOST gate below can keep the
  recording going while skipping the zone tests.  That combination is the whole
  point of the split: a ghosted run is still a run and its .rec must not develop
  a hole -- a gap would be indistinguishable from a dropped connection, and the
  markers written at the edges would then bracket nothing.
*/
/*
===========================================================================
  BUILD 82 -- ONE SIMULATED MOVE, RECORDED FROM PlayerPreThink.

  Everything else this recorder writes is STATE: where the player was, how fast,
  on what plane.  A state trace answers "is this what happened" and cannot
  answer "would this happen again", which is the question Layer 2 of the
  anti-cheat plan exists to ask.  For that a verifier needs the INPUT the mover
  was handed, and until this build nothing in the tree wrote it down.

  WHY HERE AND NOT ANYWHERE ELSE.  PlayerPreThink is the only QC hook the engine
  calls once per SIMULATED MOVE.  Its sibling PlayerPostThink runs once per
  received PACKET (SV_RunCmd's caller does `if (ran) SV_PostRunCmd();` outside
  the per-usercmd loop), so the sampler above cannot see individual commands at
  all -- which is exactly why it samples at 65/s on a 66.67 Hz server and why
  this file's whole timing essay exists.

  AND THE ENGINE HAS ALREADY WRITTEN EVERY FIELD WE NEED, one screen above the
  call.  sv_user.c sets .v_angle from SHORT2ANGLE(ucmd->angles[]) at :7782,
  SV_SetEntityButtons at :7812, .movement from the raw ucmd triple at :7895, and
  only then runs PlayerPreThink.  So this function reads no input_* global and
  needs none -- which is fortunate twice over, because input_buttons rounds (see
  the <bt> paragraph in the grammar block) and because input_sequence is not
  declared in this tree's defs at all, so a read of it would have compiled, run,
  and returned zero forever.

  WHAT IS DELIBERATELY NOT STORED.  The frametime this move was given: it is
  exactly (next row's mt - this row's mt) * movetickrate + (next carry - this
  carry), so storing it would be a third copy of a two-copy fact.  The msec off
  the wire: SV_RunCmd's budget writes through the caller's pointer (`ucmd->msec
  -= 1` and `ucmd->msec = host_client->msecs`), so the received msec is not what
  ran, and the received msec is what a cheating client controls.  mt and carry
  are produced by the mover and are the two numbers no client writes.

  NO CVAR GATES THIS, and that is a decision.  A `rec_inputs 0` would be a knob
  whose only effect is to delete the evidence a ranked run is verified from, by
  the person it verifies -- which is `rec_hid 0` exactly, the hole Phase 0.5 of
  the plan named as outranking everything else in it.  The recorder being live
  is the whole gate.

  WHAT IT COSTS, MEASURED ON A REAL RUN rather than estimated (cfg/test/
  b82input.cfg): 1.84x the LINES and 1.50x the BYTES, at 51.1 bytes per input row
  against 85.9 for every other line in the same file.  The byte multiplier is the
  LOWER of the two, which is the opposite of the first guess written here -- an
  input row has ten columns and a sample has seventeen, so the trace is cheaper
  per line than the thing it doubles.  Against build 81's ~439 MB per 12 hours
  that is ~660 MB, ~80 MB at rest under xz -6.

  THE LINE CAP ALREADY BUDGETED THIS and needs no revisiting: build 81 sized
  FS_RECMAX_STREAM at 220 lines/s of which ~100 was named as the step trace, and
  this is that trace arriving at 0.84 rows per existing line.
===========================================================================
*/
// Patch 376: an `mc` after the `in` row its payload came with, when it changed --
// every command in a packet carries the packet's newest -- and always the first.
void(entity e) SV_RecCounts =
{
	local vector r, a;
	local float was;

	/*
	  Patch 405: THE COUNTS CHANNEL HAS AN OFF SWITCH, AND THIS IS WHAT IT LOOKS
	  LIKE FROM HERE.  CL_SendCounts is the `else if` of the engine's
	  prydon-cursor branch (cl_input.c:3477-3481), tested as
	  `*cl_prydoncursor.string && cl_prydoncursor.ival >= 0`.  The cvar defaults
	  to "" so the string test fails and the counts send; setting it to ANY value
	  >= 0 takes the cursor branch instead and the `mc` rows stop -- and
	  `cl_prydoncursor 0` reads like switching something OFF.  It is a plain
	  CVAR, not CVAR_CHEAT and not latched, and PEXT2_PRYDONCURSOR is advertised
	  unconditionally (sv_main.c:2156, "mods might break without").

	  ABSENCE ALONE CANNOT BE THE TEST, and that is why this is not a taint: a
	  client older than Patch 376 is also silent, and marking those would demote
	  every legacy client -- the skew-window failure this tree already measured
	  for mapcrc.  But the suppression has a POSITIVE signature.  The engine's
	  third branch, the one a client with no counts and no cursor takes, CLEARS
	  all of it (`Vector2Clear(cmd->cursor_screen)` and the two VectorClears).
	  So cursor data PRESENT with no version marker is the cursor branch running
	  on a server that asked for counts -- and nothing in FTESurf uses the prydon
	  cursor, so there is no honest reason to be in that branch here.

	  COUNTED, NOT ACTED ON.  Attaching a taint bit demotes real players, which
	  is Lex's call and not this function's; `cmd timer` and the finish log now
	  state it so the decision can be made on numbers.
	*/
	if (input_cursor_trace_start_z != 1)
	{
		if (input_cursor_trace_start != '0 0 0'
		 || input_cursor_trace_endpos != '0 0 0')
			e.rec_mc_sup = e.rec_mc_sup + 1;
		return;
	}
	if (e.rec_rec_in < 1)
		return;
	r = input_cursor_trace_start;
	a = input_cursor_trace_endpos;
	if (e.rec_mc_n > 0 && r == e.rec_mc_ring && a == e.rec_mc_read)
		return;
	was = e.rec_rec_lines;
	SV_RecPut(e, sprintf("mc %d %d %.10g %.10g %.10g %.10g %d",
	                     e.rec_rec_pk, e.rec_rec_in - 1, r_x, r_y, a_x, a_y, a_z));
	if (e.rec_rec_lines == was)
		return;
	e.rec_mc_ring = r;
	e.rec_mc_read = a;
	e.rec_mc_n = e.rec_mc_n + 1;
	if (r_x != a_x || r_y != a_y)
	{
		if (!e.rec_mc_bad)
			e.rec_mc_badrow = e.rec_rec_in - 1;
		e.rec_mc_bad = e.rec_mc_bad + 1;
	}
};

void(entity e) SV_TimerInFrame =
{
	local float bt;                 // the three mover bits, repacked
	local float was;                // rec_rec_lines before the write
	local float fl;                 // v9: the state the engine reads next

	if (e.run_t_state != TS_RUNNING)
		return;
	if (!SV_RecLive(e))
		return;

	/*
	  THE SAME GATE THE `instart` KEY TOOK, and it has to be the same or the file
	  contradicts itself: no counter means no horizon means no rows.  Rows
	  stamping a constant 0 would be worse than no rows, because a verifier would
	  read them as a mover that never advanced.
	*/
	if (e.run_movetickrate <= 0)
		return;

	/*
	  NOT WHILE FROZEN, matching the sampler exactly.  A save-lock hold pins the
	  player with MOVETYPE_NONE and re-zeroes velocity every tick; the commands
	  still arrive and the mover still counts ticks, so without this a ten-second
	  park is ~660 rows describing a body that cannot move, against a cap this
	  trace already spends twice as fast as the samples do.  Keeping the two
	  writers on ONE rule also means the interleaving a reader groups by never
	  develops a span with inputs and no sample to terminate it.
	*/
	if (e.run_t_frzon)
		return;

	/*
	  THE THREE BITS THE MOVER READS, from the three fields the engine wrote by
	  integer shift -- .button2 is BUTTON_JUMP (2), .button4 is BUTTON_DUCK (8),
	  .button8 is BUTTON_SPEED (128).  Repacked into 1/2/4 rather than re-emitting
	  2/8/128, because the stored word is a description of this file's own columns
	  and not a copy of a protocol constant that could be renumbered under it.

	  .button8 HAS NO OTHER READER IN THIS TREE, which is the one thing about this
	  line that is not obvious: the engine only populates an extended button field
	  if the progs actually declare it (pr_cmds.c walks buttonfields[] and skips
	  any whose offset is < 0), so this read is also what keeps the field alive.
	  SV_RecKeys already reads .button4, and .button2 has been read since build 1.
	*/
	bt = 0;
	if (e.button2) bt = bt + 1;
	if (e.button4) bt = bt + 2;
	if (e.button8) bt = bt + 4;

	/*
	  TWO sprintfs, for the reason SV_RecLine gives: fteqcc caps varargs at 8 and
	  SILENTLY drops the rest, so an eleven-value format would write zeroes for
	  the tail rather than fail to compile.

	  %d AND NOT %g ON mt, which is not a style choice on this field: %g is six
	  significant digits, run_movetick is cumulative per MAP rather than per run,
	  and a lobby that has been up for an hour is already past 1,000,000 -- so
	  every row of every run on that server would carry `1.00001e+06` and a reader
	  could not tell a rounded mover tick from an exact one.  That is build 79's
	  byte-count defect exactly, on the column this whole record is built around.
	  Same for the packet ordinal, which counts from the start of the recording
	  but is unbounded within it.
	*/
	/*
	  BUILD 87 (v9): THREE CHANGES, ALL FOR EXACT REPLAY.
	    - angles are input_angles, the usercmd the mover reads (pmove.c:1457), not
	      .v_angle, which SV_RunCmd leaves stale while fixangle is set;
	    - <carry> at %.9g, movement as integers (the wire fields are int);
	    - <fl>, the state the engine reads next (sv_user.c:7964): 1 FL_ONGROUND,
	      2 teleport_time set (waterjump, never on a clean run), 4 movetype not
	      WALK.  Written here, the last thing PreThink does, so every QC write to
	      the flag before the move is already in it.
	*/
	fl = 0;
	if (e.flags & FL_ONGROUND)      fl = fl + 1;
	if (e.teleport_time)            fl = fl + 2;
	if (e.movetype != MOVETYPE_WALK) fl = fl + 4;

	was = e.rec_rec_lines;
	SV_RecPut(e, strcat(sprintf("in %d %d %.9g %d %d %d ",
	                            e.rec_rec_pk, e.run_movetick, e.run_movecarry,
	                            e.movement_x, e.movement_y, e.movement_z),
	                    sprintf("%.4f %.4f %.4f %d %d",
	                            input_angles_x, input_angles_y, input_angles_z, bt, fl)));
	if (e.rec_rec_lines > was)
	{
		e.rec_rec_inmt = e.run_movetick;    // Patch 375: a stream's `pause` reads these
		e.rec_rec_incy = e.run_movecarry;
	}

	/*
	  COUNTED BY WHETHER A LINE ACTUALLY LANDED, not by having attempted one.
	  SV_RecPut refuses past the line cap and returns having written nothing, so
	  an unconditional increment would make the trailer's <inputs> a count of rows
	  we MEANT to write -- which is the assertion this field exists instead of.
	  rec_rec_lines is the only handle on that, because SV_RecPut returns void and
	  is shared with the buffered path.

	  IT THEREFORE BEHAVES DIFFERENTLY FROM rec_rec_n AT THE CAP, and that is
	  deliberate rather than an inconsistency to tidy up.  rec_rec_n over-counts
	  there, so `end` claims more samples than the body holds and reccheck.py
	  faults the file -- which is a true and useful statement about a truncated
	  recording, and is not being removed.  <inputs> is exact, so the same capped
	  file reports honestly on one axis and loudly on the other.  Between them a
	  reader can tell WHERE the truncation landed.
	*/
	if (e.rec_rec_lines != was)
	{
		e.rec_rec_in = e.rec_rec_in + 1;
		SV_RecCounts(e);                // Patch 376
	}
};

void(entity e) SV_TimerRecFrame =
{
	if (e.run_t_state != TS_RUNNING)
		return;

	e.run_t_ticks = SV_TimerTicks(e);

	/*
	  NOT WHILE FROZEN.  The clock is not advancing and the player cannot
	  move, so every sample would carry the same timestamp and the same
	  origin: a ten-second park is ~666 identical lines that say nothing
	  and push the run towards its line cap.  Skipping them leaves no hole
	  either -- see the tick arithmetic in SV_TimerFreezeFrame; the samples
	  either side end up exactly one tick apart.

	  A GHOST IS NOT A FREEZE and is deliberately not covered by this: the clock
	  IS advancing, the body IS moving, and those samples are the record of what
	  it did while nobody was steering.  They are the evidence, not noise.
	*/
	if (SV_RecLive(e) && !e.run_t_frzon)
	{
		SV_RecBoard(e, SV_TimerElapsed(e));
		SV_RecLine(e, SV_TimerElapsed(e), e.origin, e.velocity, e.movement,
		           e.v_angle_x, e.v_angle_y, SV_RecFlags(e), SV_RecKeys(e),
		           SV_RecNormal(e));
	}
};

/*
  BUILD 88: THE ZONE SCAN, MOVED VERBATIM OUT OF SV_TimerFrame so the verifier asks
  exactly the question the live timer asks (SV_VerifyStep).  Pure: reads only the
  zone table and the latched rules, writes only zs_*.  The explanation of each
  test stays with the code below; the order of the tests is the ranking.
*/
float zs_az, zs_ez, zs_cp, zs_cancel;
void(vector lastp, vector p, vector mn, vector mx) SV_ZoneScan =
{
	local float z, ty, az, ez, azpri, ezpri, cp, cancel;

	az = ez = cp = -1;
	azpri = ezpri = 0;
	cancel = FALSE;

	for (z = 0; z < zone_count; z = z + 1)
	{
		ty = zone_type[z];

		if (ty == ZONE_BHOP || ty == ZONE_OVERBOUNCE)
			continue;

		if (ty == ZONE_CANCEL)
		{
			if (SV_ZoneHit(z, lastp, p, mn, mx))
				cancel = TRUE;
			continue;
		}
		if (ty == ZONE_CHECKPOINT)
		{
			if (cp < 0)
				if (SV_ZoneHit(z, lastp, p, mn, mx))
					cp = z;
			continue;
		}
		if (ty == ZONE_END)
		{
			if (ezpri < 2)
				if (SV_ZoneHit(z, lastp, p, mn, mx))
				{
					ez = z;
					ezpri = 2;
				}
			continue;
		}

		/* START and STAGE: the arm question is asked of the point... */
		/*
		  A START outranks a STAGE for arming: standing in both means you are
		  at the map start, not mid-route.  Equal ranks keep the first, which
		  is table order and therefore segment order.

		  BUILD 47: STILL THE POINT, at run_zone_hull 1, and that is the
		  load-bearing half of the change rather than an oversight.  az drives
		  SV_TimerTryArm, which CANCELS a running attempt -- firing that a
		  hull-width early is a regression with no upside, and the request was
		  for the clock to start later, not for the run to be cancellable from
		  further away.  It is also the only test that runs for every START and
		  STAGE zone every tick, so keeping it a point test keeps the expensive
		  narrow phase out of the common path.  run_zone_hull 2 moves it, so
		  the claim is falsifiable in one map load.
		*/
		if (SV_ZoneOcc(z, p, mn, mx))
		{
			if (ty == ZONE_START)
			{
				if (azpri < 2) { az = z; azpri = 2; }
			}
			else
			{
				if (azpri < 1) { az = z; azpri = 1; }
			}

		}

		/*
		  ...and the event question of the segment.  A stage zone ends the
		  segment before it, so crossing one at 2000 u/s has to count even
		  though you were never sampled inside it.  An END outranks a STAGE
		  here (an end is terminal); the END arm above has already claimed
		  ezpri 2 if one was crossed.
		*/
		if (ty == ZONE_STAGE)
		{
			if (ezpri < 1)
				if (SV_ZoneHit(z, lastp, p, mn, mx))
				{
					ez = z;
					ezpri = 1;
				}

		}
	}

	zs_az = az;
	zs_ez = ez;
	zs_cp = cp;
	zs_cancel = cancel;
};

/*
  BUILD 88: THE VERIFIER'S HALF.  Engine `pm_verify` replays a v9 file exactly and
  calls these by name; the zone question is the live timer's own (SV_ZoneScan),
  so a verifier and a lobby cannot disagree about what a box means.  vf_* is the
  verifier's latch set, seeded from the file's `zseed`; nothing here touches an
  entity or a live player's timer.
*/
float vf_evzone, vf_azone, vf_track, vf_stagerun, vf_startseg;

// The zone pin as the header states it ("<src> <crc> <swept> <hull> <live>"),
// for the engine to compare as a string; "" when this map has no table.
string() SV_VerifyZonePin =
{
	if (zone_crc == "")
		return "";
	return sprintf("%s %s %d %d %d", Zone_SourceTag(zone_source), zone_crc,
	               run_t_swept, run_t_hull, run_t_hulllive);
};

void(float evzone, float azone, float track, float stagerun, float startseg) SV_VerifyBegin =
{
	vf_evzone = evzone;
	vf_azone = azone;
	vf_track = track;
	vf_stagerun = stagerun;
	vf_startseg = startseg;
};

/*
  One packet: 0 nothing, 1 the run finishes here, 2 a cancel zone was crossed,
  3 the START of this track was re-entered (a note: bhop starts differ).
  SV_TimerEvent's rule: an END of the run's track finishes any run; a stage run
  also finishes on the STAGE after its own.  Nested ifs, this file's rule --
  zone_track[-1] kills the VM.
*/
float(vector lastp, vector p, vector pmaxs) SV_VerifyStep =
{
	local vector mx;
	local float ez, az, r;

	mx = PM_HULL_MAXS;
	if (run_t_hulllive)
		mx = pmaxs;
	SV_ZoneScan(lastp, p, PM_HULL_MINS, mx);
	if (zs_cancel)
		return 2;

	r = 0;
	az = zs_az;
	if (az != vf_azone)
	{
		if (az >= 0)
		if (zone_type[az] == ZONE_START)
		if (zone_track[az] == vf_track)
			r = 3;
		vf_azone = az;
	}

	ez = zs_ez;
	if (ez != vf_evzone)
	{
		if (ez >= 0)
		if (zone_track[ez] == vf_track)
		{
			if (zone_type[ez] == ZONE_END)
				r = 1;
			else if (vf_stagerun)
			if (zone_seg[ez] == vf_startseg + 1)
				r = 1;
		}
		vf_evzone = ez;
	}
	return r;
};

// Patch 369: a `restart` record.  SV_TimerRestartSeg's latch reset, so the zone
// the replay is put into counts as entered at the next scan.
void() SV_VerifyRestart =
{
	vf_azone = -1;
	vf_evzone = -1;
};

void(entity e) SV_TimerFrame =
{
	local float az, ez, cp, cancel;
	local float bhopz, bhopstate, bhopdirty, bhopcheat;
	local float sz, sin, shit;      // build 43: OUR stage's own boundary box
	local vector p, lastp;
	local vector mn, mx;            // build 47: the hull the ruleset tests with

	if (e.rec_cp_q >= 1)            // Patch 375: a save's copy, a chunk a packet
		SV_RecCopyStep(e, FS_RECCOPY_CHUNK);

	/*
	  FIRST, and above the zone_count guard on purpose.

	  A map with no zone file still has a player who can hold a save-lock, and
	  leaving the maintain below the early return would strand run_t_frzon set
	  with nothing to ever clear it.  It is also the only hook whose `time` is
	  the usercmd's -- see SV_TimerElapsed.
	*/
	SV_TimerFreezeFrame(e);

	/*
	  BUILD 82: THE PACKET ORDINAL, and it is here for the same two reasons the
	  line above is -- unconditional, above every early return.

	  This function is called exactly once per received move packet
	  (PlayerPostThink), which is what makes a bare increment a packet counter.
	  Putting it below the `zone_count <= 0` guard or the ghost branch would make
	  it a counter of packets ON A TIMED MAP WHILE NOT GHOSTING, and the `in` rows
	  that read it are written from PlayerPreThink, which has no such gate: a
	  ghosting player's rows would then all claim one packet, and the grouping a
	  verifier reads would silently fuse the whole ghost window into a single
	  move.  The counter must cost nothing to be right, so it is.

	  It is a free-running float and nothing bounds it.  That is safe where the
	  recorder's own counters are, and for the same reason: %d is exact to 2^24,
	  which at 66.67 packets per second is 70 hours -- past the 12 the line cap is
	  sized for, and past anything a single recording can reach.
	*/
	e.rec_rec_pk = e.rec_rec_pk + 1;

	/*
	  Both up here with it, and both for the same two reasons it is.

	  SV_TimerStopFrame owns run_t_ticks while the clock is stopped, so it has to
	  run before anything reads it and it must not be behind a guard that a map
	  with no zone file trips -- a stopped time from the map you just left would
	  otherwise sit on screen forever on a map that cannot clear it.

	  SV_TimerJumpWatch keeps two phase clocks off `time`, and this is the only
	  hook whose `time` is the usercmd's rather than physicstime -- see
	  SV_TimerElapsed.  It also has to see EVERY tick to catch a hop, guard or no
	  guard.
	*/
	SV_TimerStopFrame(e);
	bhopstate = e.run_t_state;
	bhopz = SV_TimerJumpWatch(e);
	bhopdirty = e.run_t_dirty;
	// Build 44: the class latch travels with the umbrella.  Carried and not
	// re-derived, for the reason the restore sites below give -- the arm in
	// between recomputes from the movetype and would drop a taint that was
	// earned before it.
	bhopcheat = e.run_t_cheat;

	if (zone_count <= 0)
		return;

	// Multi-Session: parked for a restore.  A start here would open this run's
	// part file under the copy that is writing it (sv_resume.qc).
	if (e.run_ms_phase)
	{
		SV_TimerWarped(e);
		return;
	}

	/*
	  GHOSTING: NO ZONE TESTS AT ALL.  Build 30.

	  The tests below read e.origin -- the BODY -- and a body coasting unattended
	  is still a body, so without this it would arm starts, cross checkpoints,
	  fire stages and finish runs while its owner was somewhere else looking at
	  the map.  That is the one thing a ghost is not allowed to do.

	  SV_TimerWarped RATHER THAN A BARE RETURN, and the difference is the whole
	  reason this is three lines instead of one.  A bare return skips
	  `e.run_t_lastorg = e.origin` at the bottom of this function, so the tick the
	  ghost ENDS would draw its swept segment from wherever the body was when you
	  detached to wherever it has drifted to -- and Zone_SegmentInside would
	  happily fire every zone on the line between the two, up to and including
	  END.  A long ghost could silently finish a run.  Warping keeps the far end
	  of the segment travelling with the body, one tick at a time, so re-attaching
	  tests exactly the tick it actually happened in.

	  It is also right about the padding ring for the reason SV_TimerWarped
	  already gives: the ring is the APPROACH, and a body nobody was flying did
	  not approach anything.  That is why SV_RecPad is not called here either.

	  The RECORDER runs first and deliberately: those samples are the record of
	  what the body did while unattended, which is precisely what a verifier
	  needs to see between the two `ghost` markers.
	*/
	if (e.rec_gh_on)
	{
		/*
		  BUILD 43 -- THE LEVEL HALF OF THE GHOST TAINT.

		  SV_TimerGhostMark sets run_st_ghost on the detach EDGE, which is enough
		  for the stage you were in when you detached and useless for the one you
		  drift into.  A boundary crossed while ghosting reaches SV_StageOpen,
		  which clears the taint -- so without this line a long ghost would launder
		  every stage after the first.  Set here rather than in the branch below,
		  because this branch is the one a ghosting player actually takes.

		  It does NOT need the RUNNING gate: SV_StageOpen re-reads the level too,
		  so a ghost outside a run leaves nothing behind that an arm does not
		  overwrite.
		*/
		e.run_st_ghost = TRUE;

		SV_TimerRecFrame(e);
		SV_TimerWarped(e);
		return;
	}

	p = e.origin;
	lastp = e.run_t_lastorg;

	/*
	  Build 47.  Hoisted rather than fetched per zone: SV_RunHullMaxs is a
	  branch and this loop runs once per zone per player per tick.  e.mins/e.maxs
	  are the LIVE post-move hull here -- the engine writes pmove's back onto the
	  edict before PlayerPostThink -- which is what makes run_zone_hull_live 1
	  possible at all, and also why it is not the default.
	*/
	mn = SV_RunHullMins(e);
	mx = SV_RunHullMaxs(e);

	SV_ZoneScan(lastp, p, mn, mx);	// build 88: the scan, shared with the verifier
	az = zs_az;
	ez = zs_ez;
	cp = zs_cp;
	cancel = zs_cancel;

	/*
	  The leg tracker (`!r`) latches on start/stage entry and never clears --
	  it has to survive being outside every zone, which is where you spend
	  almost all of a run.  Folded in here so the table is walked once, not
	  twice; sv_zones.qc's own scan is gone.

	  NESTED, NOT `az >= 0 && zone_track[az] == ...`.  QuakeC's && is OP_AND
	  and evaluates BOTH sides -- there is no short circuit -- so the guarded
	  form still reads zone_track[-1] and dies on fteqcc's array bounds check
	  ("Progs boundcheck failed. Value is -1"), taking the server down with
	  it.  Every array read in this file is guarded by a nested if for that
	  reason.
	*/
	if (az >= 0)
	{
		e.run_leg_zone  = az;
		e.run_leg_track = zone_track[az];
		e.run_leg_seg   = zone_seg[az];
	}

	if (cancel)
	{
		if (e.run_t_state == TS_RUNNING)
			SV_TimerVoid(e, "cancel zone");
		// A cancel touched this move.  It must stay terminal even when the
		// same movement sample also contains a qualifying bhop start jump.
		bhopz = -1;
	}

	/*
	  1. Leaving the zone the run begins from, which is what starts the clock.

	  Tested against run_t_armzone specifically rather than against `az`: on a
	  map whose start and stage boxes overlap (surf_doodles' overlap by 480
	  units) `az` changes while you are still inside the box you armed in, and
	  starting the timer there would be half a second early.

	  The FINISHED arm is a stage run's handover -- see run_t_pendarm.
	*/
	if (e.run_t_state == TS_FINISHED)
	{
		if (e.run_t_pendarm >= 0)
		{
			if (!SV_ZoneIn(e.run_t_pendarm, p, mn, mx))
			{
				SV_TimerArm(e, e.run_t_pendarm);

				/*
				  BUILD 20: A STAGE RUN'S START IS ALREADY OVER.

				  Without this the hop rule's fix becomes a regression, and a
				  loud one.  A stage run does not begin by walking out of a box
				  -- it begins by flying through a plane at 2000 u/s, airborne,
				  with the ground nowhere near.  The arm above now clears both
				  run_t_startok and run_t_airsec, so for the next second every jump
				  reads run_t_groundsec == 0, which the dwell test correctly calls
				  a hop, and the whole stage run gets marked practice.

				  Build 19 papered over this by accident: the stale run_t_airsec it
				  forgot to reset settled the start immediately.  Fixing that
				  un-papers it, so the exemption has to be said out loud.

				  sv_saveloc.qc does exactly this for a restored run, with an
				  essay giving the same reason.
				*/
				if (run_t_startstrict)
					e.run_t_startok = TRUE;

				SV_TimerStart(e);
			}
		}
	}
	else if (e.run_t_state == TS_ARMED)
	{
		if (e.run_t_armzone >= 0)
		{
			/*
			  BUILD 47: THE RUN START, and the line the request was about.

			  "Only start the timer if your HULL leaves the start zone, not
			  center point."  At run_zone_hull 1 this is the hull test, so the
			  clock starts once your whole body is clear of the box rather than
			  once your feet are -- which is what Source's trigger does and
			  therefore what the mapper drew the box expecting.

			  Strictly later than build 46, never earlier: point-inside implies
			  hull-inside, so this cannot fire before the arm that set
			  run_t_armzone.
			*/
			if (!SV_ZoneIn(e.run_t_armzone, p, mn, mx))
				SV_TimerStart(e);
			// Patch 403 review: the in-box clamp used to live HERE, and here it
			// is worth almost nothing.  SV_TimerFrame runs from PlayerPostThink,
			// which the engine calls once per PACKET (sv_user.c:9331 brackets the
			// per-usercmd loop), while trigger_push_touch re-arms the full push
			// once per COMMAND -- so every command but the last rode unclamped,
			// and a client choosing its packet rate chose the ratio.  It is now
			// called per command from PlayerPreThink (sv_player.qc), ahead of the
			// cash-out and the `ride arm` record.
		}
	}

	/*
	  2. Entering an arm-able zone.

	  AFTER the start check above, and that ordering is the whole of
	  surf_doodles working: its stage-1 box overlaps its start box by 480
	  units, so on the tick you leave the start you are already standing in
	  stage 1.  Arming first would re-arm you as a STAGE run and throw away
	  the track run you had just begun.
	*/
	if (az != e.run_t_azone)
	{
		if (az >= 0)
			SV_TimerTryArm(e, az);
		e.run_t_azone = az;
	}

	// 3. Crossing a stage or end zone while the clock is running.
	if (ez != e.run_t_evzone)
	{
		if (ez >= 0)
			SV_TimerEvent(e, ez);
		e.run_t_evzone = ez;
	}

	/*
	  3b. THE STAGE'S OWN ARM, START AND FAIL.  Build 43.

	  AFTER the event dispatch above, which is what lets a stage opened on THIS
	  tick be armed on this tick -- a boundary you fly through must disarm in the
	  same breath it opens, or the first tick outside the box would look like
	  walking out of it.  BEFORE SV_TimerRecFrame below, so a `stagestart` or a
	  `restart` written here lands ahead of this tick's sample and run_st_line
	  points AT that sample rather than past it.

	  `p` and not e.origin, matching the start-exit check at 1 above: the two are
	  the same rule about two different boxes and they must not disagree about
	  which position the question is asked of.

	  THE BOX IS RESOLVED HERE AND NOT IN THE SCAN ABOVE, which is not tidiness:
	  the scan runs before the dispatch, so on a boundary tick it would answer
	  about the segment that just ENDED.  See SV_StageZone, and the two lines of
	  .rec that made the point.

	  FOUR GUARDS BEFORE THE STATE MACHINE, and each is a different refusal:

	    RUNNING      an armed or finished player is not in a stage.
	    !stagerun    a FULL run.  BUILD 57: the flag, where this read `startseg
	                 0` -- which a stage-1 run shares with a full run.  (Its
	                 segment is always 0, so the guard below would refuse it as
	                 well; this one says why.)  A stage RUN's own boundary is the run's start
	                 box, armed and started by the run's state machine -- running
	                 a second arm over the same box would rebase a clock the run
	                 had just set, and re-entering it would print "stage reset"
	                 for a gesture that today does nothing.
	    seg > 0      segment 0 is the run's opening and is armed the same way.
	    st_seg==seg  the open stage IS the segment in progress.  They can differ
	                 for exactly one tick, between SV_StageClose and SV_StageOpen
	                 inside SV_TimerSplit; nothing reaches here in that window
	                 today, and the guard is a fact about this line rather than a
	                 claim about that function.

	  Nested rather than `&&`, this file's convention.
	*/
	if (e.run_t_state == TS_RUNNING)
	if (!e.run_t_stagerun)
	if (e.run_t_seg > 0)
	if (e.run_st_seg == e.run_t_seg)
	{
		if (e.run_st_zseg != e.run_t_seg)
		{
			e.run_st_zone = SV_StageZone(e);
			e.run_st_zseg = e.run_t_seg;
		}
		sz = e.run_st_zone;

		/*
		  TWO TESTS OF ONE BOX, and needing both is the whole of the fix above.

		    sin   OCCUPANCY: the point ends this tick inside it.
		    shit  this tick's MOVEMENT touched it.  True on the crossing tick by
		          construction, because that swept test is what fired the event
		          that opened this stage in the first place.

		  On the crossing tick of a thin boundary the two disagree -- touched,
		  ended outside -- and that state is neither an entry nor an exit.  The
		  machine waits one tick rather than guessing, which is exactly what the
		  spurious `restart` a tick after every `stage` was.

		  BUILD 47 SPLIT THESE TWO ACROSS THE HULL RULE, AND THE ASYMMETRY IS
		  DELIBERATE.  sin is an occupancy question (SV_ZoneOcc, a point test at
		  level 1); shit is a touch question (SV_ZoneHit, hulled).  The machine's
		  invariant `sin implies shit` survives either pairing, because every
		  swept test in this file accepts on its endpoint and Zone_BoxSwept's
		  probe hexagon contains the endpoint rect by construction.

		  WHAT A HULLED sin WOULD BREAK, since it is not obvious.  Cross a
		  one-unit stage plane falling at 30 u/tick.  The hull-inside window in
		  p_z is [bottom-62, top], sixty-three units tall, so sin would stay TRUE
		  for two to four ticks AFTER the plane -- and the `else if (hold)` arm
		  below would then fire SV_StageStart from where the hull finally cleared
		  instead of from the plane.  Every flown-through stage boundary on every
		  staged map would silently switch from build 42's plane-to-plane
		  measurement to exit-from-box, ~45 ms shorter, contradicting build 43's
		  "A BOUNDARY YOU FLY THROUGH NEVER REACHES HERE".  Nobody asked for that,
		  so it lives behind run_zone_hull 2 where it can be measured.

		  shit MUST follow the event test above and not be left a point sweep:
		  the "true on the crossing tick by construction" clause is a COUPLING to
		  the ZONE_STAGE arm in the scan loop.  Hull one and not the other and an
		  event could fire on a tick where shit is FALSE, sending the machine down
		  the disarm path -- the outcome would still be right, but the sentence
		  above would be a lie, and this file's failure mode is comments that
		  stopped being true.
		*/
		sin = shit = FALSE;
		if (sz >= 0)
		{
			sin  = SV_ZoneOcc(sz, p, mn, mx);
			shit = SV_ZoneHit(sz, lastp, p, mn, mx);
		}

		if (e.run_st_armed)
		{
			if (sin)
			{
				e.run_st_hold = TRUE;    // standing in it; the clock waits
			}
			else if (e.run_st_hold)
			{
				// Was in it, is not now: the stage begins HERE.
				if (run_t_stagearm)
					SV_StageStart(e, SV_TimerTicks(e));
				else
					e.run_st_armed = FALSE;
			}
			else if (!shit)
			{
				/*
				  Never inside it and not even touching it this tick: flown
				  through.  Disarm, and the stage keeps build 42's measurement
				  from the plane crossing exactly.

				  `!shit` AND NOT just `!sin`, which is the difference between
				  this and the version a scripted run caught resetting a stage on
				  the tick after its own boundary.  See the two tests above.
				*/
				e.run_st_armed = FALSE;
			}
			/*
			  else: touched the box this tick but did not end inside it.  That is
			  the crossing tick of a thin boundary and it is neither an entry nor
			  an exit -- stay armed and let the next tick say which.
			*/
		}
		else if (sin)
		{
			/*
			  BACK IN THE BOX AFTER LEAVING IT.  The fail, and it fires ONCE:
			  SV_StageFail re-arms through SV_StageOpen, so the very next tick
			  takes the `sin` branch above and sets run_st_hold instead.

			  THE POINT TEST AND NOT THE SWEPT ONE, deliberately.  On the tick
			  the stage STARTS the movement from inside to outside still touches
			  the box, so a swept fail would fire on the very tick it was armed
			  out of -- every stage would reset itself the instant it began.
			  The cost is that a re-entry fast enough to pass through the box
			  inside one tick is missed, which is the same limitation the run's
			  own re-arm has and is not reachable by walking back up a stage.
			*/
			if (run_t_stagefail)
				SV_StageFail(e, SV_TimerTicks(e));
		}
	}

	/*
	  4. Checkpoints.  BUILD 19: timed and shown, where they used to be counted
	  and dropped.

	  The old comment here said checkpoints exist to compare against afterwards
	  rather than to read while you are moving, and that is Momentum's position.
	  It does not survive contact with a LINEAR map: surf_utopia has no stages at
	  all, so its three checkpoints are the only structure the run has, and the
	  split list sat empty from the start zone to the finish.

	  THREE GUARDS, and each one was a defect on its own:

	    zone_track   a bonus track's checkpoint used to fire during a main-track
	                 run.  SV_TimerEvent has had this guard since it was written;
	                 this block never did.
	    ordinal > 0  a legacy BSP checkpoint with no `stage` key has no ordinal,
	                 and timing it against index 0 would alias it to "none".
	    > cpmax      forward progress only.  This is what dedupes the mirrored
	                 region pair that makes up one gate, and what stops walking
	                 back through a gate recording it a second time.

	  The zone latch is still updated unconditionally, exactly as before: it is
	  occupancy, and it has to track where you are whether or not we time it.
	*/
	if (cp != e.run_t_cpzone)
	{
		if (cp >= 0)
		{
			if (e.run_t_state == TS_RUNNING)
			{
				if (zone_track[cp] == e.run_t_track)
				{
					if (zone_cp[cp] > 0)
					{
						if (zone_cp[cp] > e.run_t_cpmax)
							SV_TimerCheckpoint(e, zone_cp[cp], SV_TimerTicks(e));
					}
				}
			}
		}
		e.run_t_cpzone = cp;
	}

	/*
	  Commit a bhop launch only after the old clock has received every zone event
	  from this move.  A RUNNING attempt can therefore finish at an overlapping
	  END before this discards its recording and opens the new attempt.  The new
	  recorder still opens before SV_TimerRecFrame below, so its first sample is
	  the jump tick at t=0.

	  If this tick began ARMED and also left the box, the ordinary fallback above
	  has already called SV_TimerStart with this same `time`; do not Arm it a
	  second time or erase a stage/end event it crossed on launch.  If it remained
	  ARMED, start it here.  A changed armzone is possible in overlapping starts,
	  so restore the zone the jump actually came from first.

	  RUNNING/FINISHED means a true re-arm.  Preserve the pending noclip taint
	  across SV_TimerArm, which otherwise recomputes it only from the current
	  movetype.  The counter is explicitly one because Arm zeroes it after the
	  watcher counted this jump.
	*/
	if (bhopz >= 0)
	{
		if (bhopstate == TS_ARMED)
		{
			if (e.run_t_state == TS_ARMED)
			{
				if (e.run_t_armzone != bhopz)
				{
					SV_TimerArm(e, bhopz);
					if (bhopdirty)
						e.run_t_dirty = TRUE;
					if (bhopcheat)
					{
						e.run_t_cheat  = TRUE;
						e.run_st_cheat = TRUE;
					}
				}
				e.run_t_startok = TRUE;
				SV_TimerStart(e);
			}
			else
				e.run_t_startok = TRUE; // leave-zone fallback already started it
		}
		else
		{
			SV_TimerArm(e, bhopz);
			if (bhopdirty)
				e.run_t_dirty = TRUE;
			if (bhopcheat)
			{
				e.run_t_cheat  = TRUE;
				e.run_st_cheat = TRUE;
			}
			e.run_t_startok = TRUE;
			SV_TimerStart(e);
		}
		if (e.run_t_state == TS_RUNNING)
			e.run_st_jump = TRUE;
		e.run_t_jumps = 1;
	}

	SV_TimerRecFrame(e);

	// Same for the pre-start ring: a hold would otherwise flush ~3.8 seconds of
	// genuine approach out of it and replace it with one repeated frame, so the
	// next run would open with padding that says the player stood still.
	if (!e.run_t_frzon)
		SV_RecPad(e);

	// The swept test's other end, for next tick.  Note this is e.origin and
	// not `p`: an event handler above may have moved the player (a cancel
	// zone voids and the save-lock hold re-places), and the segment has to
	// start from where they actually are.
	e.run_t_lastorg = e.origin;

	// BUILD 88: the latches the start packet left, once, before the first row.
	// Written here and not in SV_RecOpen: that runs inside step 1, before steps
	// 2 and 3 update azone/evzone for this very packet.
	if (e.rec_rec_zseed)
	{
		e.rec_rec_zseed = FALSE;
		SV_RecPut(e, sprintf("zseed evzone=%d azone=%d cpzone=%d track=%d startseg=%d stagerun=%d twarp=%d",
		                     e.run_t_evzone, e.run_t_azone, e.run_t_cpzone, e.run_t_track,
		                     e.run_t_startseg, e.run_t_stagerun, cvar("run_teleport_warp") ? 1 : 0));
	}
};

/*
  Pack the stage state for the wire.  Build 43.

  CALLED FROM PlayerPostThink AND NOT FROM THE BOTTOM OF SV_TimerFrame, and the
  reason is the three early returns that function has: no zone file, ghosting,
  and the freeze/stop block above the zone guard.  A pack at the bottom would go
  stale on exactly the ticks the state is most interesting -- a ghost is a taint
  now, and a map with no zone file still has a HUD.  One caller that always runs
  beats four that between them nearly always do.
*/
void(entity e) SV_StageStat =
{
	local float w;

	// BUILD 48: the pack moved to SV_StageWord, beside SV_StageClose, so that the
	// per-tick stat and the close report cannot drift apart.  This function is now
	// only the two things that are true HERE and not there.
	w = SV_StageWord(e);

	// Nothing is open, so nothing is true about it.  Without this the last
	// stage's word would sit on the HUD through the finish and into the next arm.
	//
	// BUILD 48: and zero now MEANS that, rather than merely looking like a clean
	// stage -- SV_StageWord always sets SF_KNOWN, so the only zero on the wire is
	// this one, and every reader tests that bit before believing anything else.
	if (e.run_st_seg < 0)
		w = 0;

	e.run_st_word = w;
};

/*
===========================================================================
  Lifecycle
===========================================================================
*/
void(entity e) SV_TimerSpawn =
{
	SV_TimerClaimSlot(e);
	e.rec_rec_buf   = -1;
	e.rec_rec_leg   = 0;
	e.rec_rec_tag   = RT_NONE;
	e.rec_rec_ticks = 0;
	e.rec_rec_saved = FALSE;
	e.rec_rec_bytes = -1;
	e.run_t_azone   = -1;
	e.run_t_evzone  = -1;
	e.run_t_armzone = -1;
	e.run_t_cpzone  = -1;
	e.rec_pad_head = 0;
	e.rec_pad_len  = 0;
	SV_TimerWarped(e);
	SV_TimerIdle(e);
};

// Called once per map, from the same deferred point the zones load at.
void() SV_TimerMapInit =
{
	local entity p;
	local string mode;

	run_t_tick = cvar("pm_ticrate");
	if (run_t_tick <= 0)
		run_t_tick = PM_TICK;

	// Latched per map rather than read per zone per tick: this is inside the
	// hottest loop the server runs.
	run_t_swept = cvar("run_zone_swept");

	// Build 47.  Latched for the same reason, and MAP-LATCHED for a second one:
	// an A/B has to be a `map` apart so the ruleset cannot change underneath a
	// run in progress.
	run_t_hull     = cvar("run_zone_hull");
	run_t_hullevt  = (run_t_hull >= 1);
	run_t_hullocc  = (run_t_hull >= 2);
	run_t_hulllive = cvar("run_zone_hull_live");

	/*
	  Published for the same reason run_prestrafe_time is: the ruleset is a
	  SERVER decision and the client draws the zones.  zone_list prints where the
	  trigger actually is, and reading that off a client cvar would let the two
	  sides disagree about a boundary only one of them can see.
	*/
	localcmd(sprintf("serverinfo run_zone_hull %g\n", run_t_hull));

	// Patch 224 publishes the exact resolved mode before gamecode starts.  Read
	// that answer, not sv_gamemode (which may be empty/auto) or the map prefix.
	mode = serverkey("gamemode");
	run_t_bhopjump = FALSE;
	if (mode == "bhop" || mode == "bhop-hl1")
		run_t_bhopjump = TRUE;

	/*
	  The cross-restart latch for `retry`.  Build 18.

	  A CVAR because it has to survive one specific thing and NOT another.  It
	  must survive PR_Deinit -- the restart destroys every SSQC global, so a
	  global alone could not carry the arm across it.  It must NOT survive the
	  process: an unregistered, non-archived cvar reads 0 in a fresh session, so
	  a save00 left behind by a crash between the write and the restart cannot
	  fire on a map load two sessions later.

	  Latched into a global and disarmed IN THE SAME BREATH.  A restart that
	  never happens, or one that loads a different map, must not leak the arm
	  into whatever loads next -- and the global is zeroed by PR_Deinit, so the
	  arm is scoped to exactly one map load by construction.
	*/
	rec_retry_armed = cvar("rec_retry_armed");
	cvar_set("rec_retry_armed", "0");

	/*
	  ONE NUMBER FOR THE RULE AND THE ASSIST.  Build 19.

	  run_prestrafe_time is the ground dwell that separates a pre-strafe jump from
	  a bhop.  The CLIENT has always used it to decide whether to release
	  +forward for you; the server now uses it to decide whether your start was
	  hopped (SV_TimerJumpWatch).  Those two must never disagree -- "the game
	  released my +forward but the server called it a hop" is an unanswerable bug
	  report -- so the server publishes its value and the client prefers it over
	  its own cvar.  Same pattern as pm_ticrate, sv_gravity and sv_airaccelerate,
	  which the HUD already reads through serverkeyfloat.
	*/
	run_t_dwell = cvar("run_prestrafe_time");
	if (run_t_dwell <= 0)
		run_t_dwell = 0.25;      // csprogs registers the cvar; we may run first
	localcmd(sprintf("serverinfo run_prestrafe_time %g\n", run_t_dwell));

	/*
	  BUILD 25 -- THE USERCMD RATE IS BOUNDED BY A SERVERINFO KEY NOBODY SETS.

	  Nothing in the engine server ever writes `maxfps`, and the client's fallback
	  when the key is missing is 72:

	      cls.maxfps = atof(InfoBuf_ValueForKey(&cl.serverinfo, "maxfps"));
	      if (cls.maxfps < 20) cls.maxfps = 72;          cl_main.c:3202-3204

	  CL_FilterTime then bounds the SEND rate to it on every call made with
	  ignoreserver false, which is all three of the usercmd ones:

	      fpscap = cls.maxfps ? max(30.0, cls.maxfps) : 0x7fff;   // = 72
	      fps    = bound(6.7, wantfps, fpscap);                   // wantfps = cl_netfps
	      if (time < ceil(1000 / fps)) return 0;   // ceil(13.89) = 14ms -> 71.4Hz

	  cl_netfps is 66.6667 here, which sits under 72, so 66-tick has never noticed
	  -- and that is exactly why this is easy to leave broken.  Anything ABOVE 72
	  is silently clamped: a 100-tick ruleset would run its physics at 100 and send
	  usercmds at 71.4 with nothing on screen saying so.

	  UNCONDITIONAL, at every tick rate, because it is a CEILING and not a target.
	  Gating it on a gamemode would also mean the setting that makes a fast ruleset
	  possible is only present on maps that ruleset already applied to.

	  NOT in cfg/default.cfg: serverinfo is not persisted here (see cfg_save_infos at
	  the top of that file -- a saved `serverinfo <key>` line would restore a stale
	  mirror at boot), so every serverinfo key this mod owns is published from
	  right here, once per map, from the value the server actually holds.

	  The RENDER rate is a different branch and is not affected either way:
	  cl_main.c:7419 takes maxfpsignoreserver whenever cl_netfps > 0, so cl_maxfps
	  has always ignored this cap.
	*/
	localcmd(sprintf("serverinfo maxfps %g\n", FS_SERVERMAXFPS));

	// One jump's hang time plus a margin.  See the FS_SETTLE* block up top for
	// the failure this replaces -- a fixed 0.4s settled the start DURING the
	// first legal jump, so the hop that followed was never looked at.
	run_t_settle = cvar("sv_gravity");
	if (run_t_settle < 1)
		run_t_settle = 800;
	run_t_settle = FS_SETTLEMARGIN * 2 * FS_JUMPIMPULSE / run_t_settle;
	if (run_t_settle < FS_SETTLEMIN) run_t_settle = FS_SETTLEMIN;
	if (run_t_settle > FS_SETTLEMAX) run_t_settle = FS_SETTLEMAX;

	/*
	  Build 20's two, cached here for the same reason as the three above: both
	  are read inside per-player, per-tick code.  Latched per map rather than
	  read live, so an A/B is a `map` apart and cannot change under a live run.

	  REGISTERED HERE AND NOT IN worldspawn.

	  BUILD 47 CHANGED THE ORDERING THIS PARAGRAPH USED TO REST ON, so what it
	  says has changed with it.  What it said, and what was true through build
	  46: StartFrame is called BEFORE the map's entities exist (SV_EntityReport's
	  own comment in sv_main.qc says so), StartFrame called SV_ZoneFrame
	  unconditionally, and SV_ZoneFrame called this -- so this function ran
	  BEFORE worldspawn on every map load, and a registercvar in worldspawn would
	  arrive after the cvar() reads below had already created the names as the
	  empty string.  registercvar declines to overwrite an existing cvar, so the
	  defaults never landed and the features sat silently off with `(default)`
	  printed beside them.  Found exactly that way: the first verification run
	  reported `"run_starthop_strict" is "" (default)` while run_starthop, read at
	  runtime instead, read 1.

	  That ordering was ALSO the legacy-BSP zone bug -- the same early call meant
	  find() ran before the trigger_momentum_timer_* entities existed, so 32 maps
	  loaded zero zones and never timed.  Build 47 gates SV_ZoneFrame on
	  zone_entsready, which the post-worldspawn block in StartFrame sets, so this
	  function now runs AFTER worldspawn rather than before it.

	  The registrations stay here regardless, and are still the safe side of the
	  trap: this is the first thing that READS them either way, and registering
	  next to the read is what makes that unarguable.  Moving them into worldspawn
	  would work today and silently break again the next time something upstream
	  reads one of these names early.  run_prestrafe_time above carries a fallback
	  for the same family of reason ("csprogs registers the cvar; we may run
	  first").
	*/
	/*
	  BUILD 46: BEFORE THE REGISTRATIONS, for the reason the trap above is about
	  -- registercvar declines to overwrite a cvar that already exists, so a
	  value forwarded from an old fs_ name has to arrive FIRST or the default
	  below wins and the player's setting is silently discarded.  m_init already
	  ran this on a listen client; this call is what covers a dedicated server,
	  where menu.dat never loads at all.  It is idempotent -- a pair whose two
	  sides already agree does nothing and prints nothing.
	*/
	FS_CvarsMoved();

	registercvar("run_starthop_strict", "1");
	registercvar("run_rearmstops", "1");
	registercvar("run_rearmhop", "1");           // build 21, and see the trap above
	registercvar("rec_runs_keep", "25");         // build 23, and see the trap above
	registercvar("rec_watch_pvs", "1");          // build 43, and see the trap above
	registercvar("run_stagefail", "1");          // build 43, and see the trap above
	registercvar("run_stagearm", "1");
	registercvar("run_stageclean", "1");
	registercvar("run_stagehop", "1");
	registercvar("run_stageghost", "1");      // build 48
	registercvar("run_stagecap", "290");      // Patch 360: stage fill-in's launch cap, u/s
	registercvar("run_startcap", "290");      // Patch 403: a run may not BEGIN above this, u/s
	registercvar("run_evidence_days", "30");  // Patch 360: abandoned-run evidence kept this long
	registercvar("rec_runarchive", "1");      // build 48
	registercvar("run_class", "1");           // build 44, and see the trap above
	registercvar("run_cheatwatch", "1");
	/*
	  BUILD 83: THE RANDOMIZED START, in units.  2 is the shipped rule.

	  REGISTERED HERE AND READ SEVENTEEN LINES BELOW, beside every other per-map
	  latch, because that is the trap this block is an essay about: cvar() on a
	  name that does not exist AUTO-CREATES it as "" and registercvar then
	  declines to overwrite it, so a non-zero default registered anywhere a read
	  can beat it ships the feature inert and reading as 0.  Five features in this
	  tree have died that way.  A start jitter that silently never fires is
	  exactly the failure that would look like success -- runs would rank, times
	  would be normal, and the only symptom would be an MMR that works.

	  LATCHED PER MAP rather than read live, on the same rule as the nine above: a
	  rule must not change underneath a run that is already going.
	*/
	registercvar("run_startjitter", "2");     // build 83

	/*
	  BUILD 66.  0 is today's behaviour exactly -- the run is buffered -- and the
	  default is 0 rather than 1 because the buffered recorder is the one that can
	  still lift a stage out of a main run and stitch a save-and-resume back into
	  one file.  A lobby ignores this and always streams; see SV_RecStreams.

	  It exists mainly so the streaming path can be FINISHED off a lobby.  A run
	  cannot be finished from a config on a zoned map -- zone_goto voids it and
	  setpos taints it -- so the only way to exercise a close, a header correction
	  and a rename at all is a real run on a listen server, and that needs a
	  switch a person can set.

	  BUILD 83 CORRECTS THE MECHANISM IN ALL FOUR COPIES OF THIS SENTENCE, because
	  the wrong one sends an implementer to the wrong function.  SV_TimerWarped
	  VOIDS NOTHING AND TAINTS NOTHING -- it resets run_t_lastorg, empties the
	  pre-start padding ring and bumps a diagnostic counter, and its own header
	  says so.  The voids are SV_TimerVoid, reached from SV_TimerTeleported (which
	  is what zone_goto goes through) and from SV_TimerFrame's cancel-zone branch.
	  setpos does not void at all: it taints, via SV_TimerCheat, decided in
	  sv_player.qc.  This matters beyond tidiness -- build 83's start jitter had to
	  establish that a server-imposed move is exempt, and following these four
	  sentences would have built the exemption around a function that never
	  refused anything.
	*/
	registercvar("rec_stream", "0");          // build 66
	run_t_startstrict = cvar("run_starthop_strict");
	run_t_rearmstops  = cvar("run_rearmstops");
	run_t_rearmhop    = cvar("run_rearmhop");
	run_t_stagefail   = cvar("run_stagefail");
	run_t_stagearm    = cvar("run_stagearm");
	run_t_stageclean  = cvar("run_stageclean");
	run_t_stagehop    = cvar("run_stagehop");
	run_t_stageghost  = cvar("run_stageghost");   // build 48
	run_t_stagecap    = cvar("run_stagecap");     // Patch 360
	localcmd(sprintf("serverinfo run_stagecap %g\n", run_t_stagecap));
	run_t_startcap    = cvar("run_startcap");     // Patch 403
	localcmd(sprintf("serverinfo run_startcap %g\n", run_t_startcap));
	localcmd("serverinfo fs_counts 1\n");     // Patch 376: clients send mouse counts
	/*
	  Patch 418: THIS SERVER WILL TAKE A RUN'S ANGLE SIDECAR.  A client drops it
	  by default whenever the recording is somewhere else (Rec_ViewEnd), so the
	  key is the server saying the file has a home here -- and a client that
	  does not want to send one still does not have to (`rec_upload 0`).
	  Published unconditionally rather than per-run: it describes the SERVER, and
	  a key that appeared and disappeared would be a race against the run that
	  reads it.
	*/
	/*
	  THE VALUE AND NOT A BOOLEAN.  The first cut published `? 1 : 0`, so an
	  operator asking for journals at 2 told every client 1 and got sidecars --
	  the client reads this key to decide whether to KEEP its journal at all,
	  and a flattened value is a flattened decision.
	*/
	run_t_evul = bound(0, rint(cvar("run_evidence_ul")), 2);
	localcmd(sprintf("serverinfo fs_ul %g\n", run_t_evul));
	SV_EvidenceSweep();
	run_t_runclass    = cvar("run_class");
	run_t_cheatwatch  = cvar("run_cheatwatch");
	run_t_startjit    = cvar("run_startjitter");   // build 83
	run_t_osrand      = -1;      // Patch 419: "not yet determined", which the
	run_t_osrsaid     = FALSE;   // declaration promises and nothing else assigned

	SV_PBLoad();

	// The player entity outlives a map change on a listen server, so a run in
	// progress has to be torn down here rather than at spawn.
	p = world;
	while ((p = find(p, classname, "player")))
	{
		p.run_t_azone = p.run_t_evzone = p.run_t_armzone = p.run_t_cpzone = -1;
		p.rec_pad_len = p.rec_pad_head = 0;

		/*
		  DROP the recorder buffer rather than deleting it, and this is a
		  stronger rule than it was for the file handle it replaces.

		  A map change tears down the server progs, and PF_buf_shutdown
		  (pr_bgcmd.c) has already freed every strbuf the old instance held and
		  released its slot.  buf_create hands slots out lowest-free-first, so a
		  stale handle does not merely fail -- it ALIASES whatever buffer the new
		  instance created first, and a buf_del on it would silently destroy
		  live data belonging to something else.

		  The run in progress is lost, which is correct: you changed the map.
		*/
		p.rec_rec_buf = -1;
		p.rec_rec_lines = 0;
		p.rec_rec_leg = 0;
		p.rec_rec_tag = RT_NONE;
		p.rec_rec_ticks = 0;
		p.rec_rec_saved = FALSE;
		p.rec_rec_bytes = -1;
		SV_TimerIdle(p);
	}

	// Save-locks are per map by definition -- an origin from the last one is
	// somewhere else entirely on this one.
	SV_SaveLocReset();
};

/*
  `timer` -- what the state machine currently believes.

  A diagnostic rather than a HUD: the HUD says the time, this says WHY it says
  that time, which is the question when a map's zones do something unexpected.
*/
void(entity e) SV_TimerReport =
{
	local float z;
	local vector pl;                // build 24: the plane the .rec would store
	local float  pdeg;              // build 25: the ramp report's worst angle

	sprint(e, PRINT_HIGH, sprintf("^5timer^7: %s on %s, tick %g, start on %s\n",
	       (e.run_t_state == TS_IDLE)    ? "idle" :
	       (e.run_t_state == TS_ARMED)   ? "armed" :
	       (e.run_t_state == TS_RUNNING) ? "running" : "finished",
	       mapname, run_t_tick, run_t_bhopjump ? "jump" : "leave"));
	sprint(e, PRINT_HIGH, sprintf("        track %g  leg %g  startseg %g  seg %g of %g\n",
	       e.run_t_track, FS_LegOf(e.run_t_startseg, e.run_t_stagerun),
	       e.run_t_startseg, e.run_t_seg, e.run_t_segs));
	// Build 57: the two halves of the leg, because "why did `!s 1` time the map"
	// is answerable from these and from nothing else.  Its own line, clear of the
	// varargs cap the lines below keep away from.
	sprint(e, PRINT_HIGH, sprintf("        leg rule: stagerun %g  stage 1 asked %g\n",
	       e.run_t_stagerun ? 1 : 0, e.run_t_wantstage1 ? 1 : 0));
	sprint(e, PRINT_HIGH, sprintf("        %s  pb %s  practice %g  recording %g\n",
	       SV_TimerString(e.run_t_ticks),
	       (e.run_t_pb > 0) ? SV_TimerString(e.run_t_pb) : "--",
	       (e.run_t_flags & TF_PRACTICE) ? 1 : 0,
	       (e.run_t_flags & TF_RECORDING) ? 1 : 0));
	/*
	  BUILD 44: the class, the bits it came from, and the latch that survives the
	  arm -- because `practice 1` above no longer says WHICH of three things
	  happened, and that is the whole report.

	  `cheatlatch` against `cheat` is the diagnostic pair.  The latch set with the
	  flag clear is a noclip that happened before the clock started and has not
	  been consumed yet; both set is a run that is already stamped; the latch clear
	  with the flag set is a run that was cheated and has since been re-armed
	  cleanly -- which cannot happen inside one attempt and means the report is
	  being read across two.
	*/
	sprint(e, PRINT_HIGH,
	       sprintf("        class: %s (seg %g cheat %g cheatlatch %g)  cheats now %g\n",
	               FS_RunClassName(FS_RunClass(e.run_t_flags)),
	               (e.run_t_flags & TF_SEGMENT) ? 1 : 0,
	               (e.run_t_flags & TF_CHEAT) ? 1 : 0,
	               e.run_t_cheat ? 1 : 0,
	               SV_CheatsOn()));
	sprint(e, PRINT_HIGH,
	       sprintf("        class rules: run_class %g run_cheatwatch %g  (sv_cheats %g, noclip %g)\n",
	               run_t_runclass, run_t_cheatwatch, cvar("sv_cheats"),
	               (e.movetype == MOVETYPE_NOCLIP) ? 1 : 0));
	/*
	  BUILD 58: the raw input journal, as the SERVER sees it.

	  TWO COLUMNS BECAUSE THERE ARE TWO FACTS.  `said` is the client's live
	  userinfo claim, straight from infokey -- which is a STRING with three
	  states, so it is printed rather than reduced to a number: "1", "0", and ""
	  for a client that has not told us, which is not the same as one that told
	  us no.  `nojournal` is whether this attempt has actually been stamped, i.e.
	  whether the latch caught a "0" at the start or at the finish.

	  They disagree legitimately and that is the point of showing both: a player
	  who types `rec_hid 1` mid-run turns `said` back to 1 while `nojournal`
	  stays 1, because turning the journal on does not retroactively record the
	  part of the run that went unrecorded.  See SV_TimerJournal.

	  BUILD 79 MADE IT FOUR, and the first two are now the diagnostic pair
	  rather than the decision.  `key` is the userinfo claim, which nothing
	  decides on any more; `said` is whether the client's CSQC has reported over
	  the channel a console cannot write, and `hid` is what it reported.  A key
	  of "1" beside said 1 hid 0 is a forgery on screen -- the player typed
	  `setinfo rechid 1` over a journal that is off, and the run is stamped
	  anyway.  A key of "1" beside said 0 is the same lie told by a client with
	  no CSQC at all.  Neither is reachable without showing both columns, which
	  is the whole reason the key is still printed.

	  `would` IS THE LIVE ANSWER AND `nojournal` IS THE LATCHED ONE, the same
	  fifth column the ruleset and profile blocks carry and for the same reason:
	  a run cannot be finished from a config on a zoned map, so without it the
	  finish half of this latch could not be observed headlessly.  It calls
	  SV_JournalBroken, the same pure predicate the latch calls, so the two can
	  never drift, and it is pure, so asking does not mark the run.
	*/
	sprint(e, PRINT_HIGH,
	       sprintf("        journal: key \"%s\"  said %g  hid %g  nojournal %g  would %g\n",
	               infokey(e, "rechid"),
	               e.run_t_jev,
	               e.run_t_jevhid,
	               (e.run_t_flags & TF_NOJOURNAL) ? 1 : 0,
	               SV_JournalBroken(e)));
	/*
	  BUILD 62: the movement ruleset, as the ENGINE sees it (Patch 313).

	  THREE COLUMNS BECAUSE THERE ARE THREE FACTS, and the same reason the pair
	  above is two.  `key` is printed as the raw string rather than reduced,
	  because "" is a real and distinct state -- an engine older than Patch 313,
	  which cannot answer -- and is NOT the same as an engine answering
	  "0 0 0 0".  Its four fields are locked, off, seq and breach.  `breachat` is
	  what this attempt latched when its clock started, -1 if it never sampled
	  one.  `noruleset` is whether the bit actually got set.

	  They disagree legitimately, and that disagreement is the whole feature: a
	  key reading "1 0 7 3" against a breachat of 1 is a run whose ruleset is
	  locked and conforming RIGHT NOW and which was not locked and conforming
	  throughout -- two changes stood while this clock ran.  No single snapshot
	  can show that.  The gap between the key's seq (7) and its breach (3) is the
	  other half of the picture and is why they are separate numbers: four
	  attempts were refused by the lock, which is worth seeing and is not a
	  violation.  See SV_TimerRuleset.

	  `would` IS THE LIVE ANSWER AND `noruleset` IS THE LATCHED ONE, and the
	  fourth column exists because a run cannot be finished from a config on a
	  zoned map -- so without it the finish half of the latch could not be
	  observed headlessly at all.  It calls SV_RulesetBroken, the same pure
	  predicate the latch calls, so the two can never drift; and it is pure, so
	  asking does not mark the run.  would 1 with noruleset 0 is precisely the
	  state a finish would convert into a taint, which is what makes the mid-run
	  window testable without reaching an end box.
	*/
	sprint(e, PRINT_HIGH,
	       sprintf("        ruleset: key \"%s\"  breachat %g  noruleset %g  would %g\n",
	               serverkey("*ruleset"),
	               e.run_t_rbreach,
	               (e.run_t_flags & TF_NORULESET) ? 1 : 0,
	               SV_RulesetBroken(e)));
	/*
	  Build 72.  The same four columns for the same four reasons, one layer up.

	  `key` is the client's raw `inprof`, "" for a client that has never sent one
	  -- which is unknown, stays rankable, and is NOT the same as a client
	  answering "1 7 0 0 0 0".  `badat` is the off-profile transition count this
	  attempt latched at its start, -1 if it never sampled one.  `noprofile` is
	  whether the bit got set, and `would` is the live answer from the same pure
	  predicate the latch calls.

	  THIS IS THE ONLY WAY TO SEE THE FINISH HALF, and more so than for the
	  ruleset: the whole point of the counter is a window that is closed again by
	  the time anybody looks, so a report that could only show the current state
	  would be blind to exactly what the field exists for.  would 1 with
	  noprofile 0 and a `bad` in the key above `badat` is a run that was played
	  under acceleration and is not admitting to it now.
	*/
	sprint(e, PRINT_HIGH,
	       sprintf("        inprof:  key \"%s\"  badat %g  noprofile %g  would %g\n",
	               infokey(e, "inprof"),
	               e.run_t_pbad,
	               (e.run_t_flags & TF_NOPROFILE) ? 1 : 0,
	               SV_ProfileBroken(e)));
	/*
	  Build 78.  WHAT CSQC SAID, BESIDE WHAT THE KEY SAYS, because from here on
	  only the first of those decides anything and a reader of the line above
	  would have no way to know that.

	  `said` 0 is the interesting reading and it is the one that now faults: the
	  client has never reported over the channel its console cannot write.  When
	  it is non-zero the six numbers after it are the ones `would` above was
	  computed from -- so `key` and `ev` disagreeing is an attempted forgery
	  displayed rather than inferred, and `keywould 0  would 1` is that forgery
	  failing in one line.

	  THEY ARE ALLOWED TO DISAGREE TRANSIENTLY AND THAT IS NOT A FAULT, which is
	  why this prints rather than latches.  Both halves leave Rec_ProfileReport in
	  the same frame, but the key goes out as a console command through the
	  buffer and the event goes straight onto the netchan, so the server can see
	  the event first.  A rule keyed on the difference would fire on the ordinary
	  case.
	*/
	/*
	  TWO LINES AND NOT ONE, AND THE REASON IS A COMPILER WARNING WORTH OBEYING.
	  One `sprintf` carrying the format plus all eight values is nine parameters;
	  fteqcc warns at more than eight on a varargs call, and a warning about
	  argument passing on the one function in this file whose whole job is to
	  report the truth is not a warning to ship.  Split, each call is well inside
	  the limit and nothing has to be trusted.
	*/
	sprint(e, PRINT_HIGH,
	       sprintf("        inprof:  said %g  keywould %g\n",
	               e.run_t_pev,
	               SV_ProfileKeyBroken(e)));
	sprint(e, PRINT_HIGH,
	       sprintf("        inprof:  ev \"%g %g %g %g %g %g\"\n",
	               e.run_t_pevhave, e.run_t_pevraw, e.run_t_pevfilt,
	               e.run_t_pevacc, e.run_t_pevbad, e.run_t_pevgrant));
	/*
	  Build 73, engine Patch 321.  BOTH HASHES, not the verdict, because the whole
	  failure this replaces was a comparison that agreed for the wrong reason.

	  `ours` is what this server loaded and `theirs` is what the client claimed;
	  printing only `nomap` would make "the two agree" and "there is nothing to
	  compare" look identical on screen, which is exactly how an inert sv_mapcheck
	  passed for years.  An empty column is therefore the interesting reading, and
	  it has four causes -- all of them listed in SV_MapForeign, all of them
	  rankable.  `would` is the live answer from the same pure predicate the latch
	  calls; there is no second latch here, so unlike the two rows above it can
	  never disagree with `nomap` on a run that has started.
	*/
	sprint(e, PRINT_HIGH,
	       sprintf("        mapcrc:  ours \"%s\"  theirs \"%s\"  nomap %g  would %g\n",
	               infokey(world, "*mapcrc"),
	               infokey(e, "*mapcrc"),
	               (e.run_t_flags & TF_NOMAP) ? 1 : 0,
	               SV_MapForeign(e)));
	/*
	  Build 30.  Two different questions, so two columns rather than one:
	  `ghost` is whether the camera is detached RIGHT NOW (and therefore whether
	  the zone tests are running at all), `ghosted` is whether this attempt has
	  ever been -- the TF_GHOST marker that reaches the .rec header.  A run can
	  easily be the second without being the first, and that is exactly the state
	  a reader of the recording will be asking about.  Printed even when clear,
	  per this function's own standard.
	*/
	sprint(e, PRINT_HIGH, sprintf("        ghost %g  ghosted %g\n",
	       e.rec_gh_on ? 1 : 0,
	       (e.run_t_flags & TF_GHOST) ? 1 : 0));
	// Patch 382: the same two questions for a spectate, plus whose body and
	// whether a `spec 0` is owed.
	sprint(e, PRINT_HIGH, sprintf("        spectate %g  watching %g  open %g  spectated %g\n",
	       e.run_sp_phase, num_for_edict(e.pb_watch), e.run_sp_open ? 1 : 0,
	       (e.run_t_flags & TF_SPEC) ? 1 : 0));
	// Build 17.  Printed even when clear, and printed HERE rather than folded
	// into the practice column, because "is this a shadow run and which save is
	// it from" is a question with two halves and this is the diagnostic that is
	// supposed to answer why the timer says what it says.
	sprint(e, PRINT_HIGH, sprintf("        shadow %g  from save %g  rec lines %g (%g samples)\n",
	       (e.run_t_flags & TF_SHADOW) ? 1 : 0, e.run_t_fromsave,
	       e.rec_rec_lines, e.rec_rec_n));
	// BUILD 87: the row-bound counts SV_RecRecount restores after a rewind.
	sprint(e, PRINT_HIGH, sprintf("        rec rows: in %d warp %d ride %d pm %d pe %d portal %d\n",
	       e.rec_rec_in, e.rec_rec_warp, e.rec_rec_ride,
	       e.rec_rec_pm, e.rec_rec_pe, e.rec_rec_portal));

	/*
	  BUILD 66: WHICH RECORDER, and where it is writing.

	  `rec lines` above counts the same on both paths by design, so it cannot
	  answer the one question this build introduces -- is this run in memory or on
	  the disk?  Without this line the two are indistinguishable from inside the
	  game, and the only way to tell would be to look at the filesystem, which is
	  the test that needs a second process.

	  The part path is printed rather than described because it is the thing a
	  harness has to go and measure, and a path composed from real values beats a
	  path a test script composes for itself -- the same argument the `would write`
	  line below makes about the archive name.
	*/
	if (e.rec_rec_stream)
		sprint(e, PRINT_HIGH, sprintf("        recorder: STREAM fh %g -> %s  (flagofs %g)\n",
		       e.rec_rec_fh, SV_RecPartPath(e), e.rec_rec_flagofs));
	else
		sprint(e, PRINT_HIGH, sprintf("        recorder: buffer %g  (stream would be %g)\n",
		       e.rec_rec_buf, SV_RecStreams() ? 1 : 0));
	// The freeze, and BOTH halves of it: `want` is the request that survives an
	// arm or a void, `frozen` is whether the maintain is actually holding the
	// clock.  Seeing them disagree is the diagnostic -- want 1 with frozen 0
	// means the run is not RUNNING, which is the only legitimate way to get it.
	sprint(e, PRINT_HIGH, sprintf("        clock: want freeze %g, frozen %g at %.4fs\n",
	       e.run_t_freeze ? 1 : 0, e.run_t_frzon ? 1 : 0, e.run_t_frzat));

	/*
	  BUILD 23: the name this run WOULD be written under if it finished now.

	  It is here because the alternative is that the only way to see the archive
	  path composed from real values -- this map, this track, this segment, this
	  clock -- is to complete a run, and completing a run is the one thing a
	  scripted test cannot do on a surf map.  So the write path stopped being
	  unobservable without a mouse.  It is also the fastest answer to "where did
	  my recording go", which is a question the layout change invites.

	  e.run_t_ticks AND NOT SV_TimerTicks(e), which is the same trap build 17
	  found in the save file: SV_TimerTicks differences against an origin, and on a
	  timer that is not running that is TIME SINCE MAP LOAD -- a number that
	  rises steadily and looks exactly like a run.  The first cut of this line
	  printed 0000130 next to a clock reading 0:00.000.  run_t_ticks is the value
	  the display and the wire already use, so the two agree by construction.
	*/
	// BUILD 66: SV_RecWho(e) inline rather than "" -- this line's whole job is to
	// print the name the recorder WOULD use, and a report that quietly omitted
	// the player segment would be the one place you could look to check it and
	// be told the old answer.  It is also the only headless view of the segment
	// before a run has finished, which is what makes the format testable.
	sprint(e, PRINT_HIGH, sprintf("        would write %s\n",
	       SV_RecFinalPath(e, e.run_t_ticks, SV_RecWho(e), "pb")));
	/*
	  Build 19.  `stopped` is the latch and the flag together, for the same
	  reason the freeze prints both: a stopped time on screen with stopat 0 would
	  mean the mirror had gone stale, and stopat set with the flag clear means the
	  run is live again and the next tick will clear it.

	  `start` prints the hop rule's whole state -- settled, the dwell in force,
	  and which phase clock is running -- because "why did it call that a hop" is
	  answerable from those three and from nothing else.
	*/
	// Two lines rather than one: seven of the eight varargs slots is as close to
	// the cap as this file goes, and fteqcc drops the ninth SILENTLY.
	sprint(e, PRINT_HIGH, sprintf("        stopped %g at %s   rearm %g\n",
	       (e.run_t_flags & TF_STOPPED) ? 1 : 0,
	       (e.run_t_stopat > 0) ? SV_TimerString(e.run_t_stopat) : "--",
	       run_t_rearmstops));
	// Build 21: `hopped` is the forgivable taint and `rearmhop` says whether it
	// CAN be forgiven, so "I stood still and nothing happened" is answerable from
	// this line alone.  Seven of the eight varargs slots -- the cap is real and
	// fteqcc drops the ninth silently, so nothing else goes on this line.
	sprint(e, PRINT_HIGH, sprintf("        start: ok %g dwell %.2f settle %.2f strict %g hopped %g rearmhop %g\n",
	       e.run_t_startok ? 1 : 0, run_t_dwell, run_t_settle, run_t_startstrict,
	       e.run_t_hopped ? 1 : 0, run_t_rearmhop));
	sprint(e, PRINT_HIGH, sprintf("        phase: ground %.2f  air %.2f  jumps %g  ramp %g\n",
	       e.run_t_groundsec ? (SV_ClockSec(e) - e.run_t_groundsec) : 0,
	       e.run_t_airsec    ? (SV_ClockSec(e) - e.run_t_airsec)    : 0,
	       e.run_t_jumps, e.run_rampcontact));
	/*
	  BUILD 24: the board telemetry, said out loud, because .rec v4 writes it and
	  nothing else on the server side ever looked at it.

	  It is the ONE instrument for a question no config can settle: all five of
	  these fields are written by the engine BY NAME through GetEdictFieldValue,
	  and build 24 moved four of the five from sv_player.qc into this file so the
	  recorder could reach them.  A move that broke the lookup would produce
	  exactly zeroes here -- and a .rec full of zero planes, which the reader
	  would then draw a strafe target against.

	  Standing on flat ground every one of them is legitimately zero, so this
	  proves nothing until it is read ON A RAMP.  Say that where the numbers are
	  rather than in a test config nobody will read again.
	*/
	sprint(e, PRINT_HIGH, sprintf("        board: count %g  plane %.3f %.3f %.3f  vin %.0f\n",
	       e.run_boardcount,
	       e.run_boardnormal_x, e.run_boardnormal_y, e.run_boardnormal_z,
	       vlen(e.run_boardvelocity)));
	/*
	  BUILD 74: the two clocks, beside each other.  Here rather than in a test
	  config because this is the number every later decision about the run clock
	  depends on, and the only way to see it is to be in a run -- which no config
	  in this tree can produce cleanly (the one way a script can cross an end
	  zone is a noclip flight, and that is always a cheated run).  So it goes
	  where a human running `cmd timer` mid-run will find it.
	*/
	sprint(e, PRINT_HIGH, strcat("        ", SV_TickReport(e), "\n"));
	pl = SV_RecNormal(e);
	sprint(e, PRINT_HIGH, sprintf("        rec plane: %.3f %.3f %.3f  (fl %g, v4 bit 16 = ramp)\n",
	       pl_x, pl_y, pl_z, SV_RecFlags(e)));

	/*
	  BUILD 25: the ramp-flicker instrument.  See SV_RampWatch.

	  Read it DURING or immediately after one ride -- the counters describe the
	  current ride and reset when it ends, which is what makes them answerable
	  rather than an average over the whole map.

	  What each number decides:

	    gaps / worst   the CONTACT dropping out.  worst is in ticks; anything at
	                   or under RAMP_GAP / run_t_tick (about 5) is bridged by the
	                   client's hold, and a worst above that is a gap the fix does
	                   NOT cover and the constant has to grow.
	    flips          the PLANE alternating.  A ride down one flat brush face
	                   should read 0 or 1; a number near `ticks` means the engine
	                   is handing back a different facet every tick and the target
	                   rate is following it, which is a different bug with a
	                   different fix.

	  gaps 0 and flips 0 over a ride that felt like it flickered would mean both
	  candidates are wrong and the search moves to the client.
	*/
	/*
	  The angle needs a guard, and the first cut of this line printed `90.00 deg`
	  on flat ground because it did not have one.  run_rc_worstdot is zero on a
	  fresh edict and acos(0) is a right angle, so a player who had never touched
	  a ramp was reported as having seen the plane swing ninety degrees.  Zero is
	  the SENTINEL for "no two planes have been compared yet"; a real pair of
	  consecutive surf planes cannot dot to zero, because ninety degrees apart is
	  not a ride, it is a wall.
	*/
	pdeg = 0;
	if (e.run_rc_worstdot > 0)
		pdeg = acos((e.run_rc_worstdot > 1) ? 1 : e.run_rc_worstdot) * DEG_PER_RAD;

	sprint(e, PRINT_HIGH,
	       sprintf("        ramp: contact %g  ticks %g  gaps %g  worst %g  flips %g (%.2f deg)\n",
	               e.run_rampcontact ? 1 : 0, e.run_rc_ticks, e.run_rc_gaps,
	               e.run_rc_worst, e.run_rc_flips, pdeg));

	/*
	  BUILD 24: the stage in progress, which is what decides whether this leg of
	  a main run gets a demo of its own.

	  `jump 1 ramp 0` is a stage that WILL be recorded when you cross the next
	  boundary; `jump 0 ramp 1` is one you surfed into and will not.  A config
	  cannot cross a stage boundary on a surf map, so this line is the only way to
	  watch the filter make its decision -- and it makes it a second or two after
	  the boundary, which is exactly when you can still read it.
	*/
	sprint(e, PRINT_HIGH,
	       sprintf("        stage: seg %g  from %s  jump %g  ramp %g  line %g  wrote %g\n",
	               e.run_st_seg,
	               (e.run_st_seg >= 0) ? SV_TimerString(e.run_st_tick) : "--",
	               e.run_st_jump ? 1 : 0, e.run_st_ramp ? 1 : 0,
	               e.run_st_line, e.run_st_rec));
	/*
	  BUILD 43: the arm state, the fails, and the taints, on their own line.

	  Two lines rather than one because seven of eight varargs slots is as close
	  to the cap as this file goes and fteqcc drops the ninth SILENTLY -- the same
	  reason the `stopped` and `start:` lines are split above.

	  `armed 1 held 0` is a stage whose boundary you crossed and have not stood
	  in: a fly-through, and it will disarm on the next tick.  `armed 1 held 1` is
	  standing on the platform with the clock base still at the plane.  `armed 0`
	  is a stage that has started, and `from` on the line above is then the box
	  exit rather than the crossing -- which is the whole measurement change and
	  the one number to look at when a split is not what you expected.

	  `tp` against `fails` is the diagnostic for a map whose fall-off teleport
	  lands OUTSIDE the boundary box: teleports 3, fails 0 says the reset rule
	  never fired and the map's zone file wants a stage region over the ledge.
	  See SV_TimerWarped.
	*/
	sprint(e, PRINT_HIGH,
	       sprintf("        stage: armed %g held %g box %g fails %g tp %g dirty %g ghosted %g\n",
	               e.run_st_armed ? 1 : 0, e.run_st_hold ? 1 : 0,
	               (e.run_st_zseg == e.run_t_seg) ? e.run_st_zone : -1,
	               e.run_st_fails, e.run_st_tp,
	               e.run_st_dirty ? 1 : 0, e.run_st_ghost ? 1 : 0));
	// Build 44.  The two halves of `dirty` above -- so "the stage is dirty and I
	// have not touched noclip" has an answer rather than being a mystery.  Its own
	// line because the one above already spends seven of the eight vararg slots.
	sprint(e, PRINT_HIGH,
	       sprintf("        stage class: stitch %g cheat %g\n",
	               e.run_st_stitch ? 1 : 0, e.run_st_cheat ? 1 : 0));
	/*
	  BUILD 48 VERIFICATION: the close report and the PB latch, which nothing in
	  this function printed.  These five are what stats 85..89 carry; the client
	  side of the timer command prints its own reading of the same five (cl stats:
	  in cl_main.qc) and the two lines are meant to be diffed -- a value that is
	  real here and 0 there is a stat that never reached the wire.  rec is
	  monotonic and counts refused closes too.  A diagnostic, so no cvar.
	*/
	sprint(e, PRINT_HIGH,
	       sprintf("        stage close: rec %g seg %g word %g ticks %g  pbwas %g  spbwas %g\n",
	               e.run_st_endrec, e.run_st_endseg, e.run_st_endword,
	               e.run_st_endticks, e.run_t_pbwas, e.run_st_endpbwas));
	sprint(e, PRINT_HIGH,
	       sprintf("        stage fill: prime %g launch %g tk %g tkspd %g cap %g posts %g\n",
	               e.run_st_prime, e.run_st_launch, e.run_st_tkok, e.run_st_tkspd,
	               run_t_stagecap, e.rec_rec_posts));
	sprint(e, PRINT_HIGH,
	       sprintf("        mouse counts: %g record(s), %g ring/read disagreement(s), first row %g\n",
	               e.rec_mc_n, e.rec_mc_bad, e.rec_mc_badrow));
	// Patch 405: 0 is every honest client, legacy ones included.  Non-zero is
	// the prydon-cursor branch running on a server that asked for counts.
	if (e.rec_mc_sup)
		sprint(e, PRINT_HIGH,
		       sprintf("        ^1counts suppressed^7: %g command(s) sent cursor data"
		               " and no marker (cl_prydoncursor)\n", e.rec_mc_sup));
	sprint(e, PRINT_HIGH,
	       sprintf("        stage rules: fail %g arm %g clean %g hop %g\n",
	               run_t_stagefail, run_t_stagearm, run_t_stageclean, run_t_stagehop));
	sprint(e, PRINT_HIGH, sprintf("        arm zone %g (armed from %g), event zone %g, cp zone %g\n",
	       e.run_t_azone, e.run_t_armzone, e.run_t_evzone, e.run_t_cpzone));
	// Build 19.  cp N of the run, when it was crossed, and how that compares --
	// the three things the split row on the left is drawn from.
	sprint(e, PRINT_HIGH, sprintf("        checkpoints: %g crossed, at cp %g (%s, %s%s)\n",
	       e.rec_rec_cp, e.run_t_cpn,
	       (e.run_t_cpn > 0) ? SV_TimerString(e.run_t_cpticks) : "--",
	       (e.run_t_cpdelta > 0) ? "+" : "",
	       (e.run_t_cpdelta != 0) ? SV_TimerString(fabs(e.run_t_cpdelta)) : "no pb"));
	sprint(e, PRINT_HIGH, sprintf("        padding %g samples, pending arm %g, splits %g\n",
	       e.rec_pad_len, e.run_t_pendarm, e.run_t_seg - e.run_t_startseg));

	// BUILD 57: z is a LEG -- 0 the full run, k stage k -- so the name beside it is
	// the stage a player counts, and the table this reads is keyed the same way.
	for (z = 0; z < FS_MAXSPLITS; z = z + 1)
		if (SV_PBGet(e.run_t_track, z) > 0)
			sprint(e, PRINT_HIGH, sprintf("        pb: track %g leg %g (%s)  %s\n",
			       e.run_t_track, z,
			       (z > 0) ? sprintf("stage %g", z) : "main",
			       SV_TimerString(SV_PBGet(e.run_t_track, z))));
};
