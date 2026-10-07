/*
===========================================================================
  cl_trail.qc -- the live run line.  Patch 475.

  cl_lines.qc draws recorded paths, and every slot it had was fed from a FILE:
  slot 0 is the replay, 1..8 are the board's.  This feeds two more from the
  player, as the run happens -- Lex: "a demo line trail to follow a player
  during a run of a map, stage, bonus or whatever and even if they fail and go
  back to start the line with labels stays until a new run starts which it
  fades out".

  So there are three rules and they are not the same rule:
    * while RUNNING, the line grows;
    * when the run ends ANY way -- finished, cancelled, teleported out -- the
      line stops growing and STAYS, whole, with its marks;
    * when the NEXT run starts, that one fades while the new one builds.

  TWO SLOTS AND A SWAP, NOT A COPY.  The third rule means the old line has to
  outlive the start of the new one, and the point arenas are flat memalloc'd
  blocks with no copy operation in cl_lines.qc.  So the two slot INDICES are
  swapped and nothing moves: Line_Begin clears whichever slot is now live, and
  the other keeps its points and fades on its own timer.

  IT COSTS 6.5 MiB, WHICH IS THE PRICE OF THE CROSS-FADE.  Measured from
  Line_Alloc's own arenas at LN_CAP 65536: 3.0 MiB of per-point arrays a slot
  (ln_pos and ln_col are vectors, six more are floats), 160 KB of marks and
  84 KB of chunk tables -- 3.25 MiB a slot, and LN_SLOTS goes 9 -> 11.  One
  slot would do if the old line vanished the instant the new run started, and
  that is precisely the behaviour the ask rules out.

  ONE SAMPLE PER COMMAND FRAME, WHICH IS THE RATE THE SERVER RECORDS AT.
  cl_replay.qc's header argues why that is the right rate for POSITION: the
  engine renders an intermediate frame as a pure lerp of the two bracketing
  tick states (cl_pred.c:1409-1425), so a per-frame sample carries nothing the
  two ticks around it did not already carry.  At 300 fps this would be five
  times the memory for no extra truth, and LN_CAP would be four minutes instead
  of sixteen.  clientcommandframe is the edge; cltime would give the render rate.

  pmove_org AND pmove_vel, NOT VF_ORIGIN.  cl_hud.qc:1784-1856 carries the
  argument in full: VF_ORIGIN is the renderer's smoothed eye -- eye height, bob
  and stair smoothing on it -- and a ghost overrides it outright, so a trail
  drawn from it would wander off the body whenever the camera did.  pmove_org is
  the feet as CL_PredictMove left them.  Its all-zero value is the "prediction
  has not run" sentinel rather than a place anyone can stand, and that is the
  guard in Trail_Sample.

  THE LINE_END BUDGET.  Line_End rebuilds the chunk spheres, the break list, the
  gain column and the stride errors in one O(n) pass -- right for a file read
  once, wrong per sample on a line that grows all run.  It is called every
  TR_BUILD samples instead, so the head of the line lags by up to that many
  samples behind a player who is standing at the head of it looking forward.
  `trail` prints the pass count and the sample count so the cost can be READ
  rather than guessed at; Line_End is chunk-local everywhere except its gain
  window, so an incremental form is available if a reading ever asks for one.

  IT IS A PICTURE AND NOTHING ELSE.  Nothing here is sent anywhere, nothing here
  is evidence, and the run's real recording is the server's .rec exactly as
  before.  A trail that disagreed with the .rec would be a drawing bug and never
  a scoring one.
===========================================================================
*/

#define TR_S0      9            // the two slots this file owns
#define TR_S1     10
#define TR_BUILD  16            // samples between Line_End passes
#define TR_EYEMID 0.5           // of the way between duck and stand view heights
#define TR_SETTLE 0.5           // Patch 477: seconds after a clock-back restart...
#define TR_JUMP   128           // ...in which a step this long drops the head (52 u is 3500 u/s)

float  tr_live, tr_prev;        // slot indices, swapped at a run start
float  tr_on;                   // the live slot holds a run
float  tr_stopped;              // retain the pre-reset head for rewind
float  tr_prevon;               // ...and the other holds the one before it
float  tr_prevat;               // cltime the fade began
float  tr_frame;                // clientcommandframe of the last sample
float  tr_state;                // last STAT_FS_TIMERSTATE, for the start edge
float  tr_since;                // samples since the last Line_End
float  tr_nsamp;                // samples this run
float  tr_builds;               // Line_End passes this run
float  tr_cv, tr_fade;
float  tr_tick;                 // the server's pm_ticrate, read per run
float  tr_lastt;                // the run clock of the last sample, seconds
vector tr_lastp;                // ...and where it was
float  tr_settle;               // cltime a clock-back restart may still drop a stale head
float  tr_gen;                  // Patch 477: lines opened, so a line is told from one two runs back
// Patch 477: the rewind cursor (cl_rewind.qc sets these).  While it is up the
// live line is drawn bright to it and dim past it, and no sample is taken.
float  tr_cur_on;
float  tr_cur_t;
vector tr_cur_p;

#include "cl_trailstate.qc"

/*
  Both zero is the uninitialised state and TR_S0 is not zero, so this is a
  sentinel rather than a flag.  A CSQC global is 0 after a map change
  (cl_replay.qc:176-198 makes the same point about its buffer handle), so the
  slots have to be re-established per map and not merely once.
*/
void() Trail_Init =
{
	if (tr_live || tr_prev)
		return;
	tr_live = TR_S0;
	tr_prev = TR_S1;
};

void() Trail_RegisterCvars =
{
	Trail_Init();
	registercvar("hud_trail",      "1",   CVAR_ARCHIVE);
	registercvar("hud_trail_fade", "1.0", CVAR_ARCHIVE);
	registercvar("hud_trail_prev", "1",   CVAR_ARCHIVE);
	registercommand("trail");
};

// A map change leaves the arenas allocated and the slots holding another map's
// run.  Called from the world-loaded path.
void() Trail_Reset =
{
	Trail_Init();
	Line_Clear(tr_live);
	Line_Clear(tr_prev);
	tr_on = tr_prevon = tr_stopped = FALSE;
	tr_nsamp = tr_builds = tr_since = 0;
	tr_state = 0;
	if (tr_raw >= 1)
		buf_del(tr_raw);
	tr_raw = tr_stitch = tr_slseq = tr_practice = 0;
	tr_timedgo_ack = tr_saveack = tr_rep_ack = tr_rep_go = 0;
	Trail_ReplayClear();
};

/*
  A new run.  The swap is the whole of it: whatever was live keeps its points
  and starts fading, and the slot that was fading is cleared and built into.
*/
void() Trail_Open =
{
	local float t;

	Trail_Init();
	t = tr_live;
	tr_live = tr_prev;
	tr_prev = t;

	tr_prevon = tr_on;              // only if there was in fact a run there
	tr_prevat = cltime;

	tr_tick = serverkeyfloat("pm_ticrate");
	if (tr_tick <= 0)
		tr_tick = 0.015;

	Line_Begin(tr_live);
	Line_Tick(tr_live, tr_tick);
	Trail_RawClear();
	tr_settle = cltime + TR_SETTLE;     // Patch 477: a load can start a line from idle too
	tr_gen    = tr_gen + 1;
	tr_on     = TRUE;
	tr_stopped = FALSE;
	tr_nsamp  = 0;
	tr_builds = 0;
	tr_since  = 0;
};

// The plane under the player, which is what the recorder writes: the ramp
// normal while riding one, else the ground normal, else nothing.  SV_RecNormal
// (sv_timer.qc:3614) picks between the same two in the same order.
vector() Trail_Normal =
{
	if (getstatf(STAT_FS_RAMPCONTACT))
		return [getstatf(STAT_FS_RAMPNORM), getstatf(STAT_FS_RAMPNORM + 1),
		        getstatf(STAT_FS_RAMPNORM + 2)];
	if (pmove_onground)
		return [getstatf(STAT_FS_GROUNDNORM), getstatf(STAT_FS_GROUNDNORM + 1),
		        getstatf(STAT_FS_GROUNDNORM + 2)];
	return '0 0 0';
};

/*
  DUCKED IS DERIVED, and said so here rather than pretended otherwise.  The
  engine's pmove.ducked is not visible to QC at all -- sv_saveloc.qc's header
  needed Engine Patch 142 to get it back for a save state -- and no stat carries
  it live.  STAT_VIEWHEIGHT is the server's own eye height, and the two
  configured values are far apart (64 standing against 47 ducked by default), so
  the midpoint between them is an unambiguous test that also survives somebody
  changing either cvar.  It feeds only Line_Grade's wishspeed cap.
*/
float() Trail_Ducked =
{
	local float stand, duck, eye;

	stand = cvar("pm_viewheight");
	duck  = cvar("pm_duckviewheight");
	if (stand <= 0 || duck <= 0 || duck >= stand)
		return FALSE;               // nothing to compare against; claim nothing
	eye = getstatf(STAT_VIEWHEIGHT);
	if (eye <= 0)
		return FALSE;
	return eye < duck + (stand - duck) * TR_EYEMID;
};

// Visual occupancy only; the server still owns arming and certification.
float(vector p) Trail_InBoundary =
{
	local float z, track;
	track = getstatf(STAT_FS_TIMERTRACK);
	for (z = 0; z < zone_count; z = z + 1)
	{
		if (zone_track[z] != track)
			continue;
		if (zone_type[z] != ZONE_START && zone_type[z] != ZONE_STAGE)
			continue;
		if (Zone_PointInside(z, p))
			return TRUE;
	}
	return FALSE;
};

void() Trail_Sample =
{
	local float fl, t, brk, b, dt;
	local vector o, v, nrm, wsh;

	o = pmove_org;
	if (o == '0 0 0')
		return;                     // prediction has not run; not a position
	v = pmove_vel;

	fl = 0;
	if (pmove_onground)                     fl = fl | WT_F_ONGROUND;
	if (getstatf(STAT_FS_RAMPCONTACT))      fl = fl | WT_F_RAMP;
	if (Trail_Ducked())                     fl = fl | WT_F_DUCKED;
	if (Keys_Held(FSK_JUMP))                fl = fl | WT_F_JUMP;

	// The run clock, in seconds, which is the .rec's own `t` column and the one
	// clock the recording and the sidecar already share.  Two samples CAN carry
	// the same value -- the stat moves per server tick and this runs per command
	// -- and Line_Grade returns -1 on a zero interval, which is the handled case.
	t = tr_practice ? tr_practicebase + cltime - tr_practiceat
	                : getstatf(STAT_FS_TIMERTICKS) * tr_tick;

	nrm = Trail_Normal();
	wsh = Watch_WishOf(input_angles_y, input_movevalues_x, input_movevalues_y);

	/*
	  Patch 477: a load's clock stat can land a frame before its origin, so the
	  first samples of a clock-back restart sit at the place the load left --
	  measured in p477rewind R9: point 0 at the wall, 389 u from the server's
	  nearest sample.  The teleport's step drops them, so the line starts where
	  the body did.
	*/
	if (tr_stitch && cltime < tr_settle)
	if (vlen(o - [getstatf(STAT_FS_SLORG), getstatf(STAT_FS_SLORG + 1),
	              getstatf(STAT_FS_SLORG + 2)]) > TR_JUMP)
		return;                     // load clock arrived ahead of the body
	if (!tr_nsamp)
		Line_Seed(tr_live, v, fl, t, input_angles_y);

	brk = tr_stitch;
	if (tr_nsamp > 0)
	{
		b = tr_live * LN_CAP + ln_n[tr_live] - 1;
		dt = max(tr_tick, t - tr_lastt);
		// A drawing discontinuity, never an authoritative .rec warp.
		if (vlen(o - tr_lastp) > max(128, (ln_spd[b] + fabs(ln_vz[b])) * dt * 3 + 64))
			brk = TRUE;
		if (brk && !tr_stitch && Trail_InBoundary(o))
		{
			tr_stopped = TRUE;
			Line_End(tr_live);
			return; // never attach the reset destination to the rewind head
		}
	}
	Line_Point(tr_live, o, v, fl, t, brk, tr_stitch, [input_angles_y, nrm_z, wsh * nrm]);
	Trail_Record(o, v, fl, t, brk, tr_stitch, [input_angles_y, nrm_z, wsh * nrm]);
	tr_stitch = FALSE;

	tr_lastt = t;
	tr_lastp = o;
	tr_nsamp = tr_nsamp + 1;
	tr_since = tr_since + 1;
	if (tr_since >= TR_BUILD)
	{
		Line_End(tr_live);
		tr_since = 0;
		tr_builds = tr_builds + 1;
	}
};

// Before clearscene, with the other per-frame readers.
void() Trail_Frame =
{
	local float st, sq, op, id, saved;

	Trail_Init();
	tr_cv = cvar("hud_trail");
	if (!tr_cv)
	{
		// Do not leave an old picture at a reused id while trails are disabled.
		sq = getstatf(STAT_FS_SLSEQ);
		if (sq != tr_slseq && tr_saveack > 0)
		if (getstatf(STAT_FS_SLTRAILTAG) == tr_saveack)
		if (getstatf(STAT_FS_SLTRAILTAG) != tr_req_wait)
		if (FS_SlopOp(getstatf(STAT_FS_SLOP)) == SLOP_SAVED)
			Trail_Save(FS_SlopId(getstatf(STAT_FS_SLOP)), getstatf(STAT_FS_SAVETICKS));
		if (tr_on || tr_prevon)
			Trail_Reset();          // turned off underneath us
		tr_slseq = sq;
		return;
	}

	st = getstatf(STAT_FS_TIMERSTATE);
	sq = getstatf(STAT_FS_SLSEQ);
	op = SLOP_NONE;
	if (sq != tr_slseq)
	{
		tr_slseq = sq;
		op = FS_SlopOp(getstatf(STAT_FS_SLOP));
		id = FS_SlopId(getstatf(STAT_FS_SLOP));
		saved = getstatf(STAT_FS_SAVETICKS);
		if (op == SLOP_SAVED && getstatf(STAT_FS_SLTRAILTAG) != tr_req_wait)
		{
			tr_rep_tracewant = tr_rep_ack;
			tr_rep_tracegot = getstatf(STAT_FS_SLTRAILTAG);
			if (tr_rep_raw < 1 || tr_rep_tracegot == tr_rep_ack)
				Trail_Save(id, saved);
		}
		if (op == SLOP_LOADED)
		{
			// An implicit go may reuse its previous id. It is a new prefix,
			// never whatever picture a remote client's old file held there.
			if (tr_timedgo_ack > 0)
			if (getstatf(STAT_FS_SLTRAILTAG) == tr_timedgo_ack)
			{
				Trail_Trim((saved >= 0) ? saved * tr_tick : tr_go_visual_t);
				Trail_Save(id, saved);
			}
			if (!tr_rep_go || getstatf(STAT_FS_SLTRAILTAG) != tr_rep_ack)
				Trail_ReplayClear();
			if (tr_rep_raw >= 1)
			{
				if (tr_raw >= 1)
					buf_del(tr_raw);
				tr_raw = tr_rep_raw;
				tr_rep_raw = 0;
				tr_tick = tr_rep_tick;
				Trail_Trim(tr_rep_end);
				Trail_Save(id, saved);
			}
			if (!tr_on)
				Trail_Open();
			if (st == TS_ARMED && ln_n[tr_live] >= 2)
			{
				// Loading a start is a reset. Keep the failed line rewindable.
				tr_stopped = TRUE;
				tr_practice = FALSE;
				Line_End(tr_live);
			}
			else
			{
				if (!Trail_Load(id, saved))
					Trail_Trim(-1); // never substitute another run's picture
				tr_on = TRUE;
				tr_stopped = FALSE;
				tr_practice = (st != TS_RUNNING);
				tr_practicebase = tr_lastt;
				tr_practiceat = cltime;
			}
		}
	}
	if (st == TS_RUNNING && (tr_state != TS_RUNNING ||
	    (tr_stopped && !Trail_InBoundary(pmove_org))) && op != SLOP_LOADED)
		Trail_Open();
	else if (st == TS_RUNNING && !tr_practice && tr_nsamp && getstatf(STAT_FS_TIMERTICKS) * tr_tick < tr_lastt)
		Trail_Trim(getstatf(STAT_FS_TIMERTICKS) * tr_tick);
	tr_state = st;

	// The fade, and the clear at the end of it.  Run on its own clock rather
	// than off the new line's progress: a run that starts and is cancelled in
	// half a second must not leave the previous one on screen for ever.
	tr_fade = cvar("hud_trail_fade");
	if (tr_fade <= 0)
		tr_fade = 1;
	if (tr_prevon && cltime - tr_prevat >= tr_fade)
	{
		Line_Clear(tr_prev);
		tr_prevon = FALSE;
	}

	if (tr_on && st != TS_RUNNING && !tr_cur_on && !rec_sl_holding)
	if (!tr_practice || (cltime >= tr_settle && Trail_InBoundary(pmove_org)))
	{
		if (!tr_stopped)
			Line_End(tr_live);
		tr_stopped = TRUE;
		tr_practice = FALSE;
	}
	if (!tr_on || tr_stopped || (st != TS_RUNNING && !tr_practice) || tr_cur_on || rec_wt_open ||
	    (getstatf(STAT_FS_TIMERFLAGS) & TF_FROZEN))
		return;                     // a finished or cancelled run KEEPS its line
	if (clientcommandframe == tr_frame)
		return;
	tr_frame = clientcommandframe;
	Trail_Sample();
};

/*
  The projection pin.  cl_watch.qc:3138-3143: cs_buildmatricies is lazy and
  renderscene rewrites r_refdef.vrect, so the frame's first project() must come
  before renderscene or every screen-space point is against the wrong matrix.
  Scores_LinesPin does this for the board lines and returns early when they are
  off, so the trail cannot lean on it.
*/
void() Trail_Pin =
{
	if (!cvar("hud_trail") || rec_wt_on)
		return;
	if (!tr_on && !tr_prevon)
		return;
	makevectors(getproperty(VF_ANGLES));
	project(getproperty(VF_ORIGIN) + v_forward * 256);
};

// After renderscene, beside the board's lines and for the same reason.
void() Trail_Draw =
{
	local float a;

	if (!tr_cv || rec_wt_on)
		return;                     // a replay owns the picture; its line is slot 0
	if (!tr_on && !tr_prevon)
		return;

	Line_ViewFrame();
	Line_StatsReset();
	Line_WindowOff();

	// The previous run first, so the live one draws over it.
	if (tr_prevon && cvar("hud_trail_prev"))
	{
		a = 1 - (cltime - tr_prevat) / tr_fade;
		if (a > 0)
			Line_Draw(tr_prev, 99999999, '0 0 0', 1, a * 0.85);
	}
	if (tr_on)
	{
		if (tr_cur_on)
		{
			if (ui_rw_on) Line_Draw(tr_live, ui_rw_time, ui_rw_org, 0.35, 1);
			else Line_Draw(tr_live, tr_cur_t, tr_cur_p, 0.35, 1);
		}
		else
			Line_Draw(tr_live, 99999999, '0 0 0', 1, 1);
	}
};

/*
  `trail` -- what the two slots hold, and what the build pass cost.

  The sample and pass counts are here because the Line_End budget above is a
  guess until somebody reads them: passes * the slot's point count is the work
  done, and nothing else in the game prints either number for these slots.
*/
float() Trail_Console =
{
	if (argv(0) != "trail")
		return FALSE;

	// THREE PRINTS AND NOT ONE, because fteqcc caps a varargs call at eight
	// parameters -- the format string among them -- and SILENTLY DROPS the
	// rest.  The first cut of this had nine and the build said so; sv_lobby.qc
	// and sv_timer.qc are split for the same reason.
	print(sprintf("trail: cv %g  live slot %g (%g pts, on %g)\n",
	              cvar("hud_trail"), tr_live, ln_n[tr_live], tr_on));
	print(sprintf("trail: prev slot %g (on %g, %.2f s into a %.2f s fade)\n",
	              tr_prev, tr_prevon,
	              tr_prevon ? cltime - tr_prevat : 0, tr_fade));
	print(sprintf("trail: replay prefix ticket %g echo %g, latest command ack %g\n", tr_rep_tracewant,
	              tr_rep_tracegot, getstatf(STAT_FS_SLACK)));
	print(sprintf("trail: run %g samples, %g Line_End passes, %g since the "
	              "last, tick %.4f, state %g\n",
	              tr_nsamp, tr_builds, tr_since, tr_tick, tr_state));
	print(sprintf("trail: marks %g, breaks %g, stopped %g (visual discontinuities only)\n",
	              ln_evn[tr_live], ln_bkn[tr_live], tr_stopped));
	if (ln_n[tr_live] > 0)
		print(sprintf("trail: head %.3f s at %v\n", ln_t[tr_live * LN_CAP + ln_n[tr_live] - 1],
		              ln_pos[tr_live * LN_CAP + ln_n[tr_live] - 1]));
	return TRUE;
};
