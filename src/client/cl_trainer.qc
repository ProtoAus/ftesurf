/*
===========================================================================
  cl_trainer.qc -- the strafe trainer: what your hands did, one strafe at a
  time, after the fact.

  WHAT THIS IS NOT.  HUD_DrawStrafe (cl_hud.qc:3908) already grades the turn
  rate you are holding RIGHT NOW, smoothed over hud_strafe_smooth, against
  Strafe_IdealTurn.  That is the instrument you steer by and this file does
  not duplicate it -- it grades the same quantity through the same
  Strafe_Quality, so the two agree by construction, but it slices the result
  per STRAFE and keeps the last jump so you can read what already happened.
  A needle cannot answer "was my third strafe worse than my second", and that
  is the question a human improves on.

  THE MEASUREMENT THAT IS NEW HERE IS THE SYNC.  Everything else on the HUD
  measures the mouse.  Nothing measured the KEY, and "the swap lagged the
  flick by 30 ms" is invisible at 66 Hz to the person doing it.

  WHY IT SAMPLES IN CSQC_Input_Frame AND NOTHING ELSE WOULD DO.

  input_movevalues is only valid inside that hook.  At draw time the engine
  republishes it from cl_pendingcmd, which CL_ClearPendingCommands memsets
  after every send, so a rendered frame that follows a send reads '0 0 0'
  with the key still held -- one frame in five at 66.7/340, approaching every
  frame as fps falls to the send rate.  cl_hud.qc:5374-5400 is the essay; it
  cost a "it says no strafe key but I am pressing a strafe key" bug report.

  And ONE COMMAND IS EXACTLY ONE TICK here, which is what makes a per-command
  sample a per-tick sample: Net_MatchTicrate (cl_main.qc:108) forces
  cl_netfps to 1/pm_ticrate on every map load, and cl_netfps_snap 1
  (cl_input.c:3274) rounds the interval to a whole number of ticks, so no
  command ever carries none or two.

  WHY SPEED COMES FROM THE SERVER'S STAT AND THE NOISE DOES NOT MATTER.

  pmove_vel is re-derived per RENDERED frame and lands a whole tick ahead or
  not depending on where the frame falls (cl_hud.qc:325-338), so a per-tick
  velocity DIFFERENCE taken from it is one tick of jitter on a signal that is
  one tick tall.  This grades a RATE instead, and speed enters the rate only
  through Strafe_IdealTurn's atan2(gain, speed) -- as a magnitude, where one
  tick of error is 0.45 u/s in 1000, or 0.05%.  So STAT_FS_VELOCITY, which is
  the server's own exact number one snapshot old, is not merely good enough
  here: it is the right input, and it needs no prediction to be running.

  The turn itself is exact.  input_angles is SHORT2ANGLE of the outgoing
  usercmd (pr_csqc.c:3977), quantised to 360/65536 = 0.0055 deg, against 1.7
  deg of real turn in a tick at 1000 u/s.
===========================================================================
*/

#define TRN_MAXS   16           // strafes kept; a long surf jump is 6-8
#define TRN_PTS   256           // per-tick trace samples, ~2.5 s at 100 Hz
#define TRN_ROWS    6           // detail rows drawn; the rest stay on the timeline

/*
  THE COMMITTED-TURN THRESHOLD, in degrees per second, and it is a floor on
  the SIGNAL rather than a taste.

  d_yaw per tick is what decides the sync, and near a reversal it passes
  through zero -- so a bare sign test flips on the quantisation (0.0055 deg,
  i.e. 0.37 deg/s at 66.7 Hz) and reports a reversal every time the hand
  wobbles.  15 deg/s is an eighth of the ideal rate at 1000 u/s (115) and
  well clear of the mouse's own noise floor at rest, so it commits on a real
  direction change and not on a tremor.
*/
#define TRN_TURNMIN  15

/*
  Past this, a flick and a key swap are two separate events rather than a
  mistimed pair, and pairing them would invent a number.

  120 ms, RAISED FROM 90 BY THE ARM.  p462trn.cfg authors a 60 ms offset and
  measures it at 45..90 depending on where the command boundary falls -- and a
  run that landed on 90 sat exactly on the old limit, where the next tick of
  jitter would have reported "no flick" for a gesture that plainly had one.
  A human who is 100 ms out has a real and very visible fault, and "+100, very
  late" is a more useful answer than a dash.

  Still well under a strafe: these run 150-400 ms, so the previous strafe's own
  flick stays outside the window and cannot be credited to this swap.
*/
#define TRN_SYNCWIN  0.120

#define TRN_NOSYNC   999        // sentinel: no flick to pair this swap with

float ui_trn_on;                // hud_trainer, refreshed with the movevars

// The input-frame clock: the sum of input_timelength, so every time below is
// in the command timeline rather than in wall time.  A render hitch cannot
// move a sync offset measured in it, which cltime could.
float trn_clock;

// --- the movevars, cached; see Trn_ReadVars -------------------------------
float trn_tick, trn_gain, trn_binds, trn_cap;
float trn_haveaa;               // sv_airaccelerate was published at all
float trn_vart;                 // trn_clock of the last read

// --- the open jump --------------------------------------------------------
float trn_air;                  // airborne right now, per the server's flag
float trn_j_t0;                 // trn_clock at take-off
float trn_j_v0, trn_j_v1;       // horizontal speed at take-off / latest
float trn_j_n;                  // strafes closed or open in THIS jump
float trn_j_shown;              // the jump the panel is drawing (frozen on land)

// --- the strafe ring ------------------------------------------------------
float trn_n;                    // strafes in the ring, 0..TRN_MAXS
float trn_s_dir[TRN_MAXS];      // +1 right (sidemove > 0), -1 left
float trn_s_t0[TRN_MAXS];       // trn_clock when the key went down
float trn_s_dur[TRN_MAXS];
float trn_s_qsum[TRN_MAXS];     // Strafe_Quality * dt, over graded ticks only
float trn_s_esum[TRN_MAXS];     // (rate/ideal - 1) * dt, same ticks
/*
  The measured turn rate itself, dt-weighted.  Nothing on screen reads it: it
  exists so the report below can print a number an arm can CHECK, because
  `+right` turns at exactly cl_yawspeed (CL_AdjustAngles, cl_input.c:1368) and
  that makes the rate the one quantity here with an authored expected value.
  err and q are both ratios against an ideal the arm would have to re-derive.
*/
float trn_s_rsum[TRN_MAXS];
float trn_s_gdur[TRN_MAXS];     // the duration those ticks account for
float trn_s_wrong[TRN_MAXS];    // dt held with the key opposing the turn
float trn_s_sync[TRN_MAXS];     // seconds: + key late, - key early
float trn_s_v0[TRN_MAXS], trn_s_v1[TRN_MAXS];

// --- the per-tick trace ---------------------------------------------------
float trn_p_n;
float trn_p_t[TRN_PTS];
float trn_p_r[TRN_PTS];         // turn rate / ideal; -1 = no answer
float trn_p_d[TRN_PTS];         // key direction at that tick, 0 = none

// --- sampling state ------------------------------------------------------
float trn_lastyaw, trn_haveyaw;
float trn_dir;                  // the committed key direction
float trn_tsign;                // the committed TURN direction
float trn_flip_t;               // trn_clock of the last committed flip
float trn_pend;                 // strafe awaiting a flick, or -1

/*
  The numbers the grade rests on, read from the SERVERINFO the server
  republishes for exactly this (sv_main.qc:41) rather than from a compile-time
  constant.

  pm_ticrate IS the physics step and it is NOT the same on every map: bhop
  maps load cfg/lobby/mode_bhop.cfg, which sets 0.01 against surf's 0.015.
  Reading PM_TICK here would grade every bhop map's ideal rate 50% low -- the
  same bug cl_hud.qc:3926 records having shipped and fixed.

  THE TICK IS THE WHOLE OF THAT ERROR.  That mode file also sets
  sv_airaccelerate 1000 against surf's 150, and it is worth writing down that
  this changes NOTHING here: both saturate the 30 u/s air cap in every
  reachable case -- the worst row is rising, 100 Hz, walking wishspeed 135,
  which still saturates at 88.8 (mode_bhop.cfg:75-116 derives it) -- so
  Strafe_AirGain returns the cap either way and the ideal rate is identical.
  Only the tick moves the number.

  Twice a second, not per tick: these change at map load and the lock reverts
  a live change inside Cvar_Set (sv_phys.c:3280), so per-tick reads would buy
  nothing.
*/
void() Trn_ReadVars =
{
	local float airaccel, maxspeed;

	/*
	  THROTTLED ON trn_clock, WHICH IS WHY hud_trainer IS NOT READ HERE.

	  trn_clock only advances below the on/off gate in Trn_InputFrame, so with
	  the panel off it stands still -- and a throttle measured against a clock
	  that has stopped never expires.  Reading the switch inside this function
	  therefore turned the panel off ONCE and for good: nothing would ever look
	  at the cvar again.  It reads every tick at the top of Trn_InputFrame
	  instead, which costs one cvar lookup and is the only read that has to
	  happen while the feature is doing nothing.
	*/
	if (trn_vart && trn_clock - trn_vart < 0.5 && trn_clock >= trn_vart)
		return;
	trn_vart = trn_clock;

	trn_tick = serverkeyfloat("pm_ticrate");        if (trn_tick <= 0) trn_tick = PM_TICK;
	trn_cap  = serverkeyfloat("pm_maxairspeed");    if (trn_cap  <= 0) trn_cap  = 30;
	maxspeed = serverkeyfloat("sv_maxspeed");       if (maxspeed <= 0) maxspeed = PM_RUN_SPEED;

	/*
	  NO FALLBACK ON THIS ONE, DELIBERATELY, and it is the only read here
	  without one.

	  cl_board.qc:2345 substitutes 150 when the key is missing and that is the
	  wrong shape for this value: 150 is the number Strafe_CapBinds exists to
	  test against, so inventing it converts "I was never told" into "the cap
	  binds, grade away".  A server genuinely running a low airaccelerate must
	  read as not-binding.  So 0 stays 0, CapBinds returns false, and nothing
	  is graded -- with trn_haveaa below separating the two reasons, because
	  "missing" and "too low" are different findings and only one of them is
	  about the server's settings.  cl_hud.qc:3932 and cl_lines.qc:282 are the
	  two reads in the tree that do neither.
	*/
	airaccel   = serverkeyfloat("sv_airaccelerate");
	trn_haveaa = (airaccel > 0);

	/*
	  surfacefriction 1, not the 0.25 PMSrc_CategorizePosition applies while
	  airborne and RISING (pm_source.c:2098).  It multiplies into accelspeed so
	  it belongs here in principle -- and at every setting this mod ships it
	  changes nothing, because 150*260*0.015*0.25 = 146 still saturates the
	  30 u/s cap.  trn_binds is what notices a server that has left that
	  regime, and then the trainer declines to grade rather than grading the
	  server's airaccelerate as if it were the player's hands.
	*/
	trn_gain  = Strafe_AirGain(airaccel, maxspeed, trn_tick, 1, trn_cap);
	trn_binds = Strafe_CapBinds(airaccel, maxspeed, trn_tick, 1, trn_cap);
};

void() Trn_Clear =
{
	trn_n       = 0;
	trn_p_n     = 0;
	trn_j_n     = 0;
	trn_j_shown = 0;
	trn_dir     = 0;
	trn_tsign   = 0;
	trn_flip_t  = 0;
	trn_pend    = -1;
	trn_haveyaw = FALSE;
	trn_air     = FALSE;
	trn_vart    = 0;            // ...and let Trn_ReadVars run again on re-enable
};

// Horizontal, like every other speed on this HUD, and from the server rather
// than from prediction -- see the header.
float() Trn_Speed =
{
	local vector v;

	v_x = getstatf(STAT_FS_VELOCITY + 0);
	v_y = getstatf(STAT_FS_VELOCITY + 1);
	v_z = 0;
	return vlen(v);
};

/*
  A strafe's grade: the duration-weighted mean quality over the ticks that
  could be graded at all, which is NOT its whole duration -- see the grade
  block in Trn_InputFrame on ramp ticks.  -1 is "no answer", the third verdict
  Strafe_Quality itself returns for the same reason, and every caller draws
  neutral on it rather than a zero.

  Up here with the ring rather than down with the panel because Trn_Report
  reads it too, and QuakeC needs the definition before the file that uses it.
*/
float(float i) Trn_Q =
{
	if (i < 0 || i >= TRN_MAXS)
		return -1;
	if (trn_s_gdur[i] <= 0.0001)
		return -1;
	return trn_s_qsum[i] / trn_s_gdur[i];
};

// The longest strafe in the shown jump, which the detail bars are drawn as a
// fraction of.  Its own function because the row loop would otherwise recompute
// it per row, and because 0 has to become 1 exactly once.
float(float first) Trn_MaxDur =
{
	local float i, m;

	m = 0;
	for (i = first; i < trn_n; i = i + 1)
		if (trn_s_dur[i] > m)
			m = trn_s_dur[i];
	return (m > 0) ? m : 1;
};

/*
  WHAT THE ARM GRADES.  One line per strafe, at the moment it stops being the
  open one, carrying the numbers this file authored rather than anything
  downstream of them -- so a config can check the measurement without looking
  at pixels, and a zero in it is this file's zero.

  dprint, so it needs developer 1 AND log_developer 1 to reach a log file:
  Con_DPrintf is gated twice (common.c:9173), which AGENTS.md:899 documents and
  two arms here have been written twice for.
*/
void(float i) Trn_Report =
{
	local float q, r, e;

	if (i < 0 || i >= TRN_MAXS || trn_s_dur[i] <= 0)
		return;

	q = Trn_Q(i);
	r = (trn_s_gdur[i] > 0) ? trn_s_rsum[i] / trn_s_gdur[i] : 0;
	e = (trn_s_gdur[i] > 0) ? trn_s_esum[i] / trn_s_gdur[i] : 0;

	dprint(sprintf("trainer: %s dur %.0fms graded %.0fms q %.3f rate %.1f ideal %.1f sync ",
	               (trn_s_dir[i] > 0) ? "R" : "L",
	               trn_s_dur[i] * 1000, trn_s_gdur[i] * 1000, q,
	               r, (1 + e != 0) ? r / (1 + e) : 0));
	// A second call rather than a ninth argument: fteqcc silently DROPS the
	// ninth parameter of a varargs call (cl_avatar.qc:905).
	dprint(sprintf("%s wrong %.0fms v %.0f->%.0f\n",
	               (trn_s_sync[i] == TRN_NOSYNC) ? "none"
	                       : sprintf("%+.0fms", trn_s_sync[i] * 1000),
	               trn_s_wrong[i] * 1000, trn_s_v0[i], trn_s_v1[i]));
};

// Push one strafe onto the ring, dropping the oldest when it is full.  The
// shift is TRN_MAXS moves of ten floats at most a few times a second; a head
// index would save that and cost every reader a modulo, which is the worse
// trade in a file where the draw walks the ring three times.
float(float dir, float t0, float v0) Trn_Open =
{
	local float i;

	if (trn_n >= TRN_MAXS)
	{
		for (i = 0; i < TRN_MAXS - 1; i = i + 1)
		{
			trn_s_dir[i]   = trn_s_dir[i + 1];
			trn_s_t0[i]    = trn_s_t0[i + 1];
			trn_s_dur[i]   = trn_s_dur[i + 1];
			trn_s_qsum[i]  = trn_s_qsum[i + 1];
			trn_s_esum[i]  = trn_s_esum[i + 1];
			trn_s_rsum[i]  = trn_s_rsum[i + 1];
			trn_s_gdur[i]  = trn_s_gdur[i + 1];
			trn_s_wrong[i] = trn_s_wrong[i + 1];
			trn_s_sync[i]  = trn_s_sync[i + 1];
			trn_s_v0[i]    = trn_s_v0[i + 1];
			trn_s_v1[i]    = trn_s_v1[i + 1];
		}
		trn_n = TRN_MAXS - 1;
		if (trn_pend >= 0)
			trn_pend = trn_pend - 1;
		if (trn_j_shown > trn_n)
			trn_j_shown = trn_n;
	}

	i = trn_n;
	trn_s_dir[i]   = dir;
	trn_s_t0[i]    = t0;
	trn_s_dur[i]   = 0;
	trn_s_qsum[i]  = 0;
	trn_s_esum[i]  = 0;
	trn_s_rsum[i]  = 0;
	trn_s_gdur[i]  = 0;
	trn_s_wrong[i] = 0;
	trn_s_sync[i]  = TRN_NOSYNC;
	trn_s_v0[i]    = v0;
	trn_s_v1[i]    = v0;
	trn_n = trn_n + 1;
	trn_j_n = trn_j_n + 1;
	return i;
};

/*
  ONE SAMPLE PER OUTGOING COMMAND.  Called from CSQC_Input_Frame AFTER
  PreStrafe_InputFrame, so what is read is the usercmd as it will actually
  leave -- if the prestrafe assist has dropped +forward, the trainer sees the
  cmd the server will run rather than the key the hand is on.  The spectate,
  replay and ghost branches above it all return before this, which is correct:
  none of those three is the player strafing.
*/
void() Trn_InputFrame =
{
	local float yaw, d, dt, side, dir, rate, ideal, q, sp, air, i, ts;

	ui_trn_on = cvar("hud_trainer");
	if (!ui_trn_on)
	{
		if (trn_n || trn_haveyaw)
			Trn_Clear();
		return;
	}
	Trn_ReadVars();

	dt  = input_timelength;
	yaw = input_angles_y;

	// The first sample after a clear, a map change or the panel being switched
	// on has no previous yaw to difference.  Take the reference and nothing
	// else: a delta against 0 would read as a 180-degree flick.
	if (!trn_haveyaw)
	{
		trn_lastyaw = yaw;
		trn_haveyaw = TRUE;
		return;
	}

	// The signed shortest turn, wrap handled once in sh_interp.qc rather than
	// with another inline while-pair (cl_hud.qc:5305 predates that helper).
	d = Interp_Arc(trn_lastyaw, yaw);
	trn_lastyaw = yaw;

	if (dt <= 0)
		return;
	trn_clock = trn_clock + dt;

	sp  = Trn_Speed();
	air = !(getstatf(STAT_FS_FLAGS) & FL_ONGROUND);
	rate = fabs(d) / dt;

	/*
	  THE COMMITTED TURN DIRECTION, and its flip time is the flick.

	  Source measures yaw as atan2(y,x), so a POSITIVE rate is turning LEFT
	  (cl_hud.qc:5354).  Below TRN_TURNMIN nothing is committed and the last
	  direction stands -- see the note on the constant.
	*/
	if (rate >= TRN_TURNMIN)
	{
		ts = (d < 0) ? 1 : -1;          // +1 = turning right, -1 = left
		if (ts != trn_tsign)
		{
			trn_tsign  = ts;
			trn_flip_t = trn_clock;

			/*
			  A swap that arrived BEFORE its flick: the strafe opened with no
			  flick to pair with, and this is it.  Negative, because the key
			  led -- and only inside the window, or an unrelated later flick
			  would be credited to it.
			*/
			if (trn_pend >= 0 && trn_pend < trn_n)
			{
				if (trn_clock - trn_s_t0[trn_pend] <= TRN_SYNCWIN)
					trn_s_sync[trn_pend] = trn_s_t0[trn_pend] - trn_clock;
				trn_pend = -1;
			}
		}
	}

	// Take-off and landing.  The server's flag, not pmove_onground, which is
	// recomputed per rendered frame and can toggle inside one command frame
	// with nothing having happened (cl_hud.qc:3991).
	if (air && !trn_air)
	{
		// A new jump.  The previous one stays in the ring until this one has a
		// strafe of its own, so taking off does not blank what you were reading.
		trn_j_t0 = trn_clock;
		trn_j_v0 = sp;
		trn_j_n  = 0;
		trn_dir  = 0;
		trn_pend = -1;
	}
	trn_air  = air;
	trn_j_v1 = sp;

	if (!air)
	{
		if (trn_dir)
			Trn_Report(trn_n - 1);
		// Grounded: close whatever was open.  Ground movement is a different
		// optimum entirely (sh_strafe.qc:190-210) -- wishdir nearly ALONG the
		// velocity, not across it -- and grading it with the air formula would
		// be confidently wrong rather than slightly wrong.
		trn_dir  = 0;
		trn_pend = -1;
		return;
	}

	/*
	  sidemove is right MINUS left (CL_BaseMove, cl_hud.qc:5446), so both keys
	  held and neither key held are the SAME zero in the usercmd and this
	  cannot tell them apart.  It does not guess: a zero closes the strafe and
	  shows on the timeline as a gap, which is the true reading either way.
	*/
	side = input_movevalues_y;
	dir  = 0;
	if (side > 0) dir =  1;
	if (side < 0) dir = -1;

	if (dir != trn_dir)
	{
		if (trn_dir)
			Trn_Report(trn_n - 1);
		trn_dir = dir;
		if (dir)
		{
			i = Trn_Open(dir, trn_clock, sp);

			/*
			  Pair the swap with a flick.  One of two cases, and the sign is
			  the whole point:

			    the flick already happened, inside the window -> key LATE, +ms
			    no flick yet -> pend, and the branch above resolves it as key
			      EARLY, -ms, when the flick arrives

			  A swap with no flick either side of it keeps TRN_NOSYNC and the
			  panel prints a dash.  That is the third verdict: "no flick to
			  measure against" is not a score of zero.
			*/
			if (trn_flip_t && trn_clock - trn_flip_t <= TRN_SYNCWIN)
				trn_s_sync[i] = trn_clock - trn_flip_t;
			else
				trn_pend = i;
		}
		else
			trn_pend = -1;
	}

	if (!dir || !trn_n)
		return;

	i = trn_n - 1;
	trn_s_dur[i] = trn_s_dur[i] + dt;
	trn_s_v1[i]  = sp;

	/*
	  THE GRADE.  Strafe_Quality, the same function and the same arguments the
	  live bar passes in free air -- cscale == aircap there, which makes its
	  scale factor exactly 1 (sh_strafe.qc:530).  So a strafe the bar called
	  perfect scores 1.00 here by construction, and the two instruments can
	  never disagree about what good is.

	  FLAT AIR ONLY.  On a ramp the ideal is a different function of the plane
	  normal (Strafe_IdealTurnPlane), between 1.8x and 6x away from this one,
	  and the normal is not available at input-frame cadence -- STAT_FS_RAMPNORM
	  is a snapshot behind and the bar needs the pre-clip velocity with it.
	  Rather than grade a surf ramp against the free-air number, ticks in
	  contact with a ramp are counted into the DURATION and not into the grade:
	  trn_s_gdur is what the average divides by, so a strafe that was half on a
	  ramp reports the half it can stand behind.
	*/
	ideal = 0;
	if (trn_binds && !getstatf(STAT_FS_RAMPCONTACT))
		ideal = Strafe_IdealTurn(sp, trn_gain, trn_tick);

	if (ideal > 0.001)
	{
		q = Strafe_Quality(rate, ideal, trn_cap, trn_cap);
		if (q >= 0)
		{
			trn_s_qsum[i] = trn_s_qsum[i] + q * dt;
			trn_s_esum[i] = trn_s_esum[i] + ((rate / ideal) - 1) * dt;
			trn_s_rsum[i] = trn_s_rsum[i] + rate * dt;
			trn_s_gdur[i] = trn_s_gdur[i] + dt;
		}

		// Holding the key against the turn.  sidemove > 0 (right) belongs with
		// a NEGATIVE yaw rate; the pairing is the one thing a beginner gets
		// backwards, and it is invisible in a quality number because a rate is
		// unsigned.  Counted only once the turn is committed, or a tremor at
		// the top of a flick would read as the whole strafe being wrong.
		if (trn_tsign && trn_tsign != dir && rate >= TRN_TURNMIN)
			trn_s_wrong[i] = trn_s_wrong[i] + dt;
	}

	// The trace.  One slot per tick, so the graph IS the measurement and not a
	// resample of it.  Oldest-drops, same reason as the strafe ring.
	if (trn_p_n >= TRN_PTS)
	{
		for (ts = 0; ts < TRN_PTS - 1; ts = ts + 1)
		{
			trn_p_t[ts] = trn_p_t[ts + 1];
			trn_p_r[ts] = trn_p_r[ts + 1];
			trn_p_d[ts] = trn_p_d[ts + 1];
		}
		trn_p_n = TRN_PTS - 1;
	}
	trn_p_t[trn_p_n] = trn_clock;
	trn_p_r[trn_p_n] = (ideal > 0.001) ? (rate / ideal) : -1;
	trn_p_d[trn_p_n] = dir;
	trn_p_n = trn_p_n + 1;

	trn_j_shown = trn_j_n;
};

// ---------------------------------------------------------------------------
//  The panel
// ---------------------------------------------------------------------------

// Quality as a letter, because "88%" does not say whether 88 is good and a
// grade does.  The boundaries are Strafe_Quality's own shape, not taste:
// q = 1-(1-r)^2, so 0.96 is exactly the +-20% band the function reproduces
// (sh_strafe.qc:520) and 0.84 is +-40%.
string(float q) Trn_Grade =
{
	if (q <  0)    return "-";
	if (q >= 0.99) return "S";
	if (q >= 0.96) return "A";
	if (q >= 0.90) return "B";
	if (q >= 0.84) return "C";
	if (q >= 0.70) return "D";
	return "E";
};

// Blue for left, orange for right -- the same pair the mouse pad already uses
// for the same two keys (MPC_STRAFE, cl_mouse.qc:25), so one convention covers
// both panels rather than each inventing its own.
vector(float dir) Trn_DirColour =
{
	return (dir > 0) ? '1.00 0.55 0.15' : '0.30 0.65 1.00';
};

// Late is the costly direction and reads red; early is merely untidy.  20 ms
// is the pass band: at surf rate that is one tick either side of simultaneous,
// which is the finest thing the measurement can resolve.
vector(float sync) Trn_SyncColour =
{
	if (sync == TRN_NOSYNC)  return '0.45 0.45 0.50';
	if (sync >  0.020)       return '1.00 0.45 0.40';
	if (sync < -0.020)       return '1.00 0.80 0.35';
	return '0.45 0.85 0.45';
};

/*
  The dominant fault, as a sentence, over the strafes of the shown jump.  ONE
  fault, the largest, rather than a list: a paragraph during a jump is not
  readable and the ranking is the useful part.
*/
string(float first) Trn_Coach =
{
	local float i, n, gd, esum, ssum, sn, wrong, q, worst;

	n = 0; gd = 0; esum = 0; ssum = 0; sn = 0; wrong = 0;
	worst = 1;
	for (i = first; i < trn_n; i = i + 1)
	{
		n = n + 1;
		gd    = gd + trn_s_gdur[i];
		esum  = esum + trn_s_esum[i];
		wrong = wrong + trn_s_wrong[i];
		if (trn_s_sync[i] != TRN_NOSYNC)
		{
			ssum = ssum + trn_s_sync[i];
			sn = sn + 1;
		}
		q = Trn_Q(i);
		if (q >= 0 && q < worst)
			worst = q;
	}

	if (!n)
		return "no strafe yet";
	if (gd <= 0.0001)
	{
		// The reasons a tick is ungradeable, named rather than merged into one
		// refusal.  "I was not told" is not "the server is set too low", and
		// neither is "you are on a ramp" -- see Trn_ReadVars on the fallback.
		if (!trn_haveaa)
			return "no sv_airaccelerate from server";
		if (!trn_binds)
			return "server airaccel too low to grade";
		return "on a ramp -- the bar grades that";
	}

	// Worst first: a wrong key costs more than any amount of rate error, and
	// it is the one fault the rate number cannot show.
	if (wrong > gd * 0.2)
		return "key fights your turn";

	esum = esum / gd;
	if (fabs(esum) > 0.12)
		return (esum > 0) ? sprintf("mouse %.0f%% too fast", esum * 100)
		                  : sprintf("mouse %.0f%% too slow", -esum * 100);

	if (sn && fabs(ssum / sn) > 0.020)
		return (ssum / sn > 0) ? sprintf("keys %.0f ms late",  (ssum / sn) * 1000)
		                       : sprintf("keys %.0f ms early", -(ssum / sn) * 1000);

	if (worst < 0.90)
		return "one weak strafe -- see the rows";

	return "clean";
};

/*
  THE TIMELINE IS THE POINT OF THE PANEL.

  x is time within the jump, shared by both halves, so the two read as one
  picture.  Around the upper axis: a band per strafe, left above and right
  below, with a white tick where the mouse REVERSED.  The horizontal gap
  between a band's edge and its tick IS the sync error, at the same scale as
  everything else on screen -- which is the one representation of it a human
  can read at a glance instead of subtracting two numbers.

  Below: one column per tick of turn rate over ideal, centre line = ideal, up
  is too fast.  Per TICK, not resampled, because the trace is the measurement.
*/
void(vector p, float w, float h, float first, float sz) Trn_Timeline =
{
	local float i, span, t0, x, x2, gut, tw, bh, cy, r, dev, ch, ty;
	local vector c;

	t0 = trn_j_t0;
	span = trn_clock - t0;
	if (span < 0.35)
		span = 0.35;                    // a short hop must not stretch to fill

	// A gutter for the L/R keys, INSIDE the panel: the axis has to be labelled
	// or "above the line" means nothing, and hanging the labels off the left
	// edge would put them outside the backdrop and outside HUD_Rect's box.
	gut = ceil(sz * 0.9);
	tw  = w - gut;

	bh = ceil(h * 0.21);                // one band
	cy = p_y + bh;                      // the key axis
	ch = h * 0.22;                      // the trace's half-height
	ty = p_y + h * 0.76;                // ...and its centre

	drawfill([p_x + gut, cy], [tw, ui_cv_scale], '0.30 0.32 0.38', 0.55, 0);

	HUD_Text([p_x, cy - bh],          "L", sz * 0.75, '0.30 0.65 1.00', 0.7);
	HUD_Text([p_x, cy + ui_cv_scale], "R", sz * 0.75, '1.00 0.55 0.15', 0.7);

	/*
	  --- the trace.  Its band and the key bands do not overlap vertically
	  (0.54h..0.98h against 0..0.45h), so the two are independent and this can
	  be switched off without disturbing anything drawn below it.
	*/
	if (cvar("hud_trainer_trace"))
	{
		drawfill([p_x + gut, ty], [tw, ui_cv_scale * 0.5], '0.30 0.32 0.38', 0.35, 0);
		for (i = 0; i < trn_p_n; i = i + 1)
		{
			if (trn_p_t[i] < t0)
				continue;
			r = trn_p_r[i];
			if (r < 0)
				continue;                   // no answer: a gap, not a zero

			x = p_x + gut + ((trn_p_t[i] - t0) / span) * tw;

			// (r-1) in [-1,1] spans exactly the meaningful range: Strafe_Quality is
			// zero at both r = 0 and r = 2, so clamping here clamps nothing a grade
			// could still have distinguished.
			dev = r - 1;
			if (dev >  1) dev =  1;
			if (dev < -1) dev = -1;

			// The ratio is the grade's only input, so hand it over as one: turn = r
			// against ideal = 1 is the same fraction Strafe_Quality would divide.
			c = HUD_QualityColor(Strafe_Quality(r, 1, trn_cap, trn_cap));
			if (dev >= 0)
				drawfill([x, ty - dev * ch],
				         [ui_cv_scale, dev * ch + ui_cv_scale * 0.5], c, 0.8, 0);
			else
				drawfill([x, ty], [ui_cv_scale, -dev * ch], c, 0.8, 0);
		}
	}

	// --- a band per strafe ------------------------------------------------
	for (i = first; i < trn_n; i = i + 1)
	{
		x  = p_x + gut + ((trn_s_t0[i] - t0) / span) * tw;
		x2 = p_x + gut + ((trn_s_t0[i] + trn_s_dur[i] - t0) / span) * tw;
		if (x2 - x < ui_cv_scale)
			x2 = x + ui_cv_scale;       // a one-tick strafe must still be seen
		if (x2 > p_x + w)
			x2 = p_x + w;

		r = Trn_Q(i);
		c = (r < 0) ? '0.45 0.45 0.50' : HUD_QualityColor(r);

		if (trn_s_dir[i] < 0)
			drawfill([x, cy - bh], [x2 - x, bh], c, 0.85, 0);
		else
			drawfill([x, cy + ui_cv_scale], [x2 - x, bh], c, 0.85, 0);

		// THE FLICK, drawn where it actually happened rather than as a number.
		if (trn_s_sync[i] != TRN_NOSYNC)
		{
			x2 = p_x + gut + ((trn_s_t0[i] - trn_s_sync[i] - t0) / span) * tw;
			drawfill([x2, cy - bh - 2 * ui_cv_scale],
			         [ui_cv_scale, bh * 2 + 5 * ui_cv_scale], '1 1 1', 0.85, 0);
		}
	}
};

void(vector scr) Trn_Draw =
{
	local float w, sz, hsz, lh, pad, i, first, rows, q, gq, gd, x, y0, tlh, mx;
	local vector p, bp, c;
	local string s;

	if (!cvar("hud_trainer"))
		return;

	// A replay and a spectated player are somebody else's hands, and this panel
	// is about yours.  Both of those also stop Trn_InputFrame being reached at
	// all (CSQC_Input_Frame returns above it), so the data behind the panel
	// would be the last live jump -- stale, and captioned as if it were theirs.
	if (rec_wt_on || getstatf(STAT_FS_SPEC))
		return;

	Font_Set(ui_font_ui);
	sz  = HUD_Size("hud_trainer_size", Font_Px(8 * ui_cv_scale));
	hsz = Font_Px(6 * ui_cv_scale);
	lh  = ceil(sz * 1.35);
	pad = ceil(sz * 0.7);
	w   = ceil(sz * 21);
	// The trace occupies the lower half of the timeline's box, so switching it
	// off has to shrink the box or it leaves a slab of empty fill.  Trn_Timeline
	// reads the same cvar and lays the bands out against whatever it is handed.
	tlh = cvar("hud_trainer_trace") ? ceil(sz * 4.4) : ceil(sz * 2.1);

	bp = [cvar("hud_trainer_x") * scr_x, cvar("hud_trainer_y") * scr_y, 0];
	p  = [bp_x - w * 0.5, bp_y, 0];
	y0 = p_y;

	// Which strafes belong to the jump on show.  trn_j_shown freezes at the
	// landing, so the panel keeps the last jump up instead of blanking.
	first = trn_n - trn_j_shown;
	if (first < 0)
		first = 0;

	// hud_trainer_rows 0 is "timeline only", which is the compact form: the
	// timeline already carries every strafe, so the rows are the detail and not
	// the measurement.  Clamped, because a hand-set 99 would walk the ring.
	rows = floor(cvar("hud_trainer_rows"));
	if (rows < 0)        rows = 0;
	if (rows > TRN_ROWS) rows = TRN_ROWS;
	if (rows > trn_n - first)
		rows = trn_n - first;

	gq = 0; gd = 0;
	for (i = first; i < trn_n; i = i + 1)
	{
		gq = gq + trn_s_qsum[i];
		gd = gd + trn_s_gdur[i];
	}
	q = (gd > 0.0001) ? (gq / gd) : -1;

	// The backdrop is sized from the row count rather than from a constant,
	// because the count changes during a jump and a fixed box either clips the
	// sixth row or leaves a slab of empty fill under a one-strafe hop.
	drawfill([p_x - pad, y0 - pad],
	         [w + pad * 2, lh * 2.2 + tlh + pad * 0.5 + lh * rows + pad * 2],
	         '0.05 0.06 0.08', 0.55, 0);

	// --- the header -------------------------------------------------------
	HUD_Text([p_x, p_y], "STRAFE", sz, '0.35 0.75 1.00', 0.95);

	/*
	  The jump's speed change, which is NOT the grade and must not be read as
	  one: it is two samples of STAT_FS_VELOCITY either end of the air time, so
	  a ramp, a booster or a wall is in it as much as your hands are.  It is
	  here because it is the number a surfer actually wants, and the grade
	  beside it is the one that is only about the hands.
	*/
	mx = trn_j_v1 - trn_j_v0;
	HUD_TextR([p_x + w, p_y], sprintf("%s%.0f u/s", (mx >= 0) ? "+" : "", mx),
	          sz, HUD_GainColor(mx), 0.95);
	p_y = p_y + lh;

	c = (q < 0) ? '0.45 0.45 0.50' : HUD_QualityColor(q);
	HUD_Text ([p_x, p_y], Trn_Coach(first), hsz, '0.70 0.70 0.74', 0.9);
	HUD_TextR([p_x + w, p_y],
	          (q < 0) ? "-" : sprintf("%s  %.0f%%", Trn_Grade(q), q * 100),
	          sz, c, 0.95);
	p_y = p_y + lh * 1.2;

	// --- the timeline -----------------------------------------------------
	Trn_Timeline(p, w, tlh, first, sz);
	p_y = p_y + tlh + pad * 0.5;

	/*
	  --- the rows, oldest first so they read down the way the timeline reads
	  across.  TRN_ROWS at most: a jump with more strafes than that has its
	  detail in the timeline, and a panel that grew mid-jump would move the
	  numbers being read.
	*/
	mx = Trn_MaxDur(first);
	i = trn_n - rows;
	if (i < first)
		i = first;
	for (; i < trn_n; i = i + 1)
	{
		q = Trn_Q(i);
		c = (q < 0) ? '0.45 0.45 0.50' : HUD_QualityColor(q);
		x = p_x;

		HUD_Text([x, p_y], (trn_s_dir[i] > 0) ? "R" : "L", sz,
		         Trn_DirColour(trn_s_dir[i]), 0.95);
		x = x + sz * 1.2;

		// The bar's LENGTH is the strafe's own duration against the longest in
		// the jump, so an uneven rhythm shows as ragged right edges; its fill
		// colour is the grade.  Two facts, one bar, and they are independent.
		drawfill([x, p_y + sz * 0.15], [w * 0.42, sz * 0.7], '0.12 0.13 0.16', 0.7, 0);
		drawfill([x, p_y + sz * 0.15], [w * 0.42 * (trn_s_dur[i] / mx), sz * 0.7],
		         c, 0.85, 0);
		x = x + w * 0.42 + sz * 0.5;

		HUD_Text([x, p_y], Trn_Grade(q), sz, c, 0.95);

		if (trn_s_sync[i] == TRN_NOSYNC)
			s = "-";
		else
			s = sprintf("%s%.0f", (trn_s_sync[i] > 0) ? "+" : "",
			            trn_s_sync[i] * 1000);
		HUD_TextR([p_x + w, p_y], s, sz, Trn_SyncColour(trn_s_sync[i]), 0.95);
		p_y = p_y + lh;
	}

	HUD_Rect("trainer", [p_x - pad, y0 - pad],
	         [w + pad * 2, p_y - y0 + pad * 2], bp);
	Font_Reset();
};

void() Trn_RegisterCvars =
{
	// OFF by default.  It is a practice instrument, not a readout, and it costs
	// a sample per command plus three ring walks per frame when it is on.
	registercvar("hud_trainer", "0", CVAR_ARCHIVE);
	registercvar("hud_trainer_size", "0", CVAR_ARCHIVE);
	registercvar("hud_trainer_rows", "6", CVAR_ARCHIVE);
	registercvar("hud_trainer_trace", "1", CVAR_ARCHIVE);
	/*
	  LEFT OF CENTRE AND HIGH, and both numbers were measured off a screenshot
	  rather than chosen -- two collisions in a row said guessing does not work.
	  0.5/0.60 drew over the speedometer (0.5/0.68) and its "340" read straight
	  through the 0.55 backdrop; 0.28/0.40 then landed on the Segments column,
	  which is at hud_seq -0.25/0.5 RIGHT-anchored and so occupies 420..640 x
	  647..847 at hud_scale 2 on a 2560x1494 buffer -- not where its cvars read.
	  0.28/0.27 puts this at 537..897 x 403..633, which clears the splits block
	  above it, the segments column below it, and the whole centre stack.
	*/
	registercvar("hud_trainer_x", "0.28", CVAR_ARCHIVE);
	registercvar("hud_trainer_y", "0.27", CVAR_ARCHIVE);
	Trn_Clear();
};
