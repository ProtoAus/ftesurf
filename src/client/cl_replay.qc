/*
===========================================================================
  cl_replay.qc -- the half of a recording that only the client can see.

  WHAT IS MISSING FROM THE .rec, AND WHY IT CANNOT BE ADDED THERE.

  The server's recording is one sample per physics tick, 66.67 Hz, because that
  is the rate the physics actually ran at.  That is the right rate for position
  and velocity and it is provably enough for them: the engine's own prediction
  renders an intermediate frame as a pure LERP of the two bracketing tick states
  (cl_pred.c:1409-1425), so a per-frame position sample carries no information
  the two ticks around it did not already carry.  Recording positions at 300 fps
  would be five times the file for zero extra truth.

  Two things are NOT like that.

  The CAMERA is mouse-sampled continuously and only quantised into a usercmd at
  66.67 Hz.  Between two ticks the view really did sweep through angles that no
  tick holds, and at 300 fps that is four out of every five frames of a replay
  looking at a direction the player never looked at.  This is the one quantity
  where the render rate is the true rate.

  The KEYBOARD is worse than merely coarse: parts of it never reach the server at
  all.  +left and +right have no usercmd button bit -- they feed CL_AdjustAngles
  directly (cl_input.c:1368) -- so no server-side sample rate could ever recover
  them.  And run_prestrafe deliberately drops +forward for a pre-strafe jump, so
  the key you are holding and the movement being sent disagree on purpose.  The
  server records what was SENT, which is correct for physics; the display needs
  what was HELD.

  So the sidecar is: one line per rendered frame, carrying the view angles and
  the keyboard.  Together with the .rec it reproduces HUD_DrawKeys exactly,
  including the forced crouch and the pre-strafe release, which neither file can
  do alone.  See the FSI_* block in shared/sh_defs.qc.

  HOW THE TWO FILES FIND EACH OTHER.

  They are written by two different VMs and nothing connects them but their
  names, so the server owns the naming and publishes it: STAT_FS_RUNLEG says
  which leg is being run, STAT_FS_RUNTAG says how it ended.  The client spells
  the server's own filename out of those two and writes .view beside .rec.

  That ordering is not incidental.  The server finishes and closes its file
  during a physics tick; the client sees the new stats on its next rendered
  frame, which is strictly afterwards.  So the client can write straight to the
  final name and the server never has to rename a file the client might still be
  holding -- there is no window in which both are touching either path.

  A run that is thrown away sets RUNTAG back to RT_NONE, so a voided run drops
  its buffer and cannot overwrite the sidecar of the recording that is still
  good.

  PLAYBACK IS NOT HERE YET.  Phase 5 reads these two files back; this file is
  currently only the writer.
===========================================================================
*/

/*
  The accumulating sidecar.

  A strbuf and one write at the end, for the same reason the server's recorder
  is one: fclose is what actually puts bytes on disk (PF_fclose calls
  COM_WriteFile unconditionally), so an "incremental" fputs per frame would be
  an append to a memory buffer with a builtin call and a filesystem handle
  wrapped around it.  This just is the memory buffer.

  0 is the no-buffer sentinel rather than -1: buf_create returns i + BUFSTRBASE
  with BUFSTRBASE == 1 (pr_bgcmd.c:5157), so no real handle is ever 0 -- and a
  CSQC global after a map change is 0, not -1, which makes 0 the value this
  actually has to survive.
*/
float rec_rp_view;               // strbuf, or 0
float rec_rp_lines;
float rec_rp_wasrec;             // TF_RECORDING as of last frame

/*
  Build 30.  rec_gh_on as of the last frame that was RECORDED, so the ghost edges
  can be bracketed into the sidecar.

  Kept per-file rather than per-session, and cleared by Rec_ViewBegin: a run that
  STARTS while already ghosting has to open with a `ghost 1`, or the file has a
  close bracket with nothing opening it.  Seeding it FALSE and letting the ordinary
  edge test fire on the first recorded frame gets that for free, with no second
  code path that could disagree with the first.
*/
float rec_rp_wasghost;
float rec_rp_full;               // said once that this run hit the cap

/*
  SAVE STATES: the client's half of the mark.  Build 17.

  A save keeps the run so far and a load rewinds to it, so the .view has to move
  in lockstep with the .rec or a shadow run replays with the camera of one
  attempt over the movement of another -- which is worse than having no camera
  at all, because it looks like it works.

  rec_rp_mark[id] is the line this client was at when slot `id` was saved, or 0
  for a slot it has not seen saved this session.  Zero is a usable sentinel
  because a real mark is always at least FS_VIEWHEAD -- a sidecar with no header
  is not a sidecar.

  Indexed by SLOT ID and not by list position, for the same reason the server
  indexes its folders that way: deleting an earlier save renumbers the list and
  would otherwise silently re-point every mark held here.
*/
float rec_rp_mark[FS_MAXSAVES + 1];
float rec_rp_slseq;              // STAT_FS_SLSEQ as of last frame

// The two-argument buf_create the shipped prototype hides; see the same
// declaration in server/sv_timer.qc for why the default flags are wrong here.
strbuf(string bufclass, float bufflags) buf_create_ex = #460;

// Builtin 652, present in BOTH VMs, but pr_dumpplatform only emits a prototype
// for a builtin carrying an extension-group flag and this one carries none --
// so defs/cl_defs.qc has no declaration for it.  Named here the same way
// server/sv_timer.qc:101 names it.
float(string fname) fremove = #0:fremove;

/*
  Frames one sidecar may hold.  At 300 fps that is 22 minutes, against the
  50 minutes FS_RECMAX gives the .rec at 66.67 Hz -- deliberately the same
  order, so neither file can run away while the other stops.

  bufstr_set refuses an index past 1024*1024 with only a PR_RunWarning, so
  without a cap of our own a runaway recording would stop growing silently in
  the middle and leave a file that looks complete.
*/
#define FS_VIEWMAX 400000

/*
  THE MAP NAME, and it is NOT the `mapname` global.

  In CSQC `mapname` is the world MODEL -- "maps/surf_666.bsp", slashes and
  extension and all -- while the server's is the bare "surf_666".  So every
  path below was being spelled as

      data/runs/maps/surf_666.bsp_t0_s0_last.view

  which is a real directory the engine happily creates, next to nothing that
  was looking for it.  The sidecar has therefore never once landed beside the
  .rec it belongs to, since the day it was written; nothing noticed because no
  reader exists yet and because a file that is merely in the wrong place still
  looks like it was written.

  It surfaced only because build 17 put a second writer on the same convention
  and the save states' folders turned up under data/saves/maps/surf_666.bsp/.

  serverkey("map") is the short name, and is what cl_zones.qc has always used
  to find a map's zone file -- so the correct source was already in this VM,
  three files away.
*/
string() Rec_MapName = { return serverkey("map"); };

// data/runs/<map>/<leg>/<ticks>_<tag>.<ext>.
//
// BUILD 22 gave this an extension parameter rather than adding a third speller.
// BUILD 23 finished the job: the convention itself moved to FS_RunPath in
// shared/sh_defs.qc, which all three VMs compile, so there is now ONE definition
// instead of two that each carried a comment begging the other to be kept in
// step.  This is a thin adapter from the wire encoding to that call, and nothing
// more.
//
// `ticks` comes from STAT_FS_RUNTICKS and must be the value the server closed
// the run with -- NOT the live clock, which by this frame is describing the next
// attempt.  Pass -1 for a tag that is not archived.
string(float runleg, float ticks, string tag, string ext) Rec_ViewPath =
{
	local float track, leg;

	// RUNLEG is track*100 + leg + 1; see shared/sh_defs.qc for the +1.  BUILD 57:
	// a LEG (0 the full run, k stage k), where it used to be the 0-based segment
	// the run began at -- which could not tell a stage-1 run from a full one.
	runleg = runleg - 1;
	track  = floor(runleg / 100);
	leg    = runleg - track * 100;

	return FS_RunPath(Rec_MapName(), track, leg, ticks, tag, ext);
};

// Kept as a name because this file calls it in several places; the definition is
// FS_TagName in shared/sh_defs.qc, which the server uses too.
string(float tag) Rec_TagName = { return FS_TagName(tag); };

/*
  data/saves/<map>/saveNNN/run.view -- beside the server's run.rec.

  Spelled from the slot id the SLOP stat carries, which is the same id the
  server spelled its folder from -- and, as of build 25, with the same function.
  It used to have its own copy of the two-digit form, as did Seq_Path and the
  server's SL_NN: three spellers of the one directory that joins a save's four
  files across two VMs.  See FS_SaveSlotName in sh_defs.qc for why that is the
  bug class it is.
*/
string(float id) Rec_SavePath =
{
	return sprintf("data/saves/%s/save%s/run.view",
	               Rec_MapName(), FS_SaveSlotName(id));
};

/*
  What the keyboard is doing, as an FSI_* mask.

  A loop over the key table rather than eight hand-written ORs, because
  FSI_<x> is defined as exactly 1 << FSK_<x> and writing them out again here
  would be a second copy of that mapping to keep in step with the first.
*/
float() Rec_ViewKeys =
{
	local float i, bit, m;

	m   = 0;
	bit = 1;
	for (i = 0; i < FSK_COUNT; i = i + 1)
	{
		if (Keys_Held(i))
			m = m + bit;
		bit = bit * 2;
	}

	// Not a key: the game is suppressing a key you ARE holding.  Recorded so a
	// replay can draw the released-W state rather than a plain unlit W, which
	// would look like you let go.
	if (run_ps_release)
		m = m + FSI_PSREL;

	return m;
};

/*
  MAY A RAW INPUT JOURNAL BE TAKEN AT ALL.  Build 22.

  Two conditions, and the second is the consent gate doing the only work that
  matters.  A terms screen that merely blocks a button is a reminder; what makes
  it a consent gate is that somebody who has never seen it IS NOT RECORDED.  So
  the test is here, at the one place a journal can start, rather than only in the
  menu -- where it would be bypassed by the console `map` command, by a
  command-line +map, and by anything else that reaches a run without ever drawing
  a menu frame.

  rec_terms is published by m_init in menu.dat, which is the earliest QC of any
  kind on a launch, so this cannot race it.  It reads 0 when unset, and
  0 < FS_TERMS_VERSION.

  Defined up here rather than beside Rec_HidBegin because Rec_ViewBegin's header
  needs it too, and fteqcc wants the definition first.
*/
float rec_rp_consent;            // the accepted terms version, read off disk at init
float rec_rp_hidsent;            // last `setinfo rechid` value sent; -1 = none yet

/*
  THE ACCEPTED VERSION, READ FROM THE RECORD ITSELF and not only from the cvar.

  rec_terms is written by menu.dat's m_init, and the assumption that m_init always
  runs before this VM exists turned out to be untrue: a headless launch that
  execs a config with `map` in it reaches a loaded map with the cvar still
  UNREGISTERED -- the b22c test log says `Unknown command "rec_terms"` after
  surf_666 had finished loading.

  That direction is safe (an absent cvar reads 0, so no journal is taken), but
  the failure it implies is not acceptable: a player who HAS accepted could have
  a run recorded with `hid 0` in its sidecar, which is a false statement about
  them in their own file.  So the gate does not depend on a cross-VM ordering it
  cannot control -- it reads data/consent.txt, which is where the record actually
  lives.

  Both sources are consulted because each covers a case the other does not: the
  file covers "the menu VM has not run yet", and the cvar covers "the terms were
  accepted after this VM was created", which happens when a player opens the menu
  mid-map and accepts.  Neither can produce a false ACCEPT: the file has to say
  so, or the menu has to have written it.
*/
float() Rec_ConsentRead =
{
	local filestream fh;
	local string l;
	local float v;

	v  = 0;
	fh = fopen("data/consent.txt", FILE_READ);
	if (fh < 0)
		return 0;

	for (l = fgets(fh); l != ""; l = fgets(fh))
	{
		tokenize(l);
		if (argv(0) == "version")
			v = stof(argv(1));
	}
	fclose(fh);
	return v;
};

float() Rec_HidOK =
{
	if (!cvar("rec_hid"))
		return FALSE;
	if (rec_rp_consent >= FS_TERMS_VERSION)
		return TRUE;
	if (cvar("rec_terms") >= FS_TERMS_VERSION)
		return TRUE;
	return FALSE;
};

/*
  TELL THE SERVER WHETHER THIS CLIENT IS JOURNALLING.  Build 58.

  The server cannot see rec_hid -- it is a client cvar, and the `hid` key in the
  .view header is written by this same client after the fact.  So the answer is
  published as userinfo, which sv_lobby.qc already uses as a client->server
  channel (`setinfo lobbycolor`), and SV_TimerJournal reads it with infokey.

  SENT ON CHANGE, FROM THE PER-FRAME DRIVER, RATHER THAN AT RUN START, and the
  timing is the whole reason this is not simply a line in Rec_HidBegin.  A
  userinfo update is a round trip; setting it as the clock starts would race the
  server's own read of it, and the run that lost the race would be recorded as
  making no claim when it had in fact just made one.  Sent from Rec_ViewFrame,
  the value has been on the server since long before any start zone was left.

  The cached compare is what keeps that free: rec_hid changes approximately
  never, so this is one cvar read per frame and a localcmd only on an edge.
  -1 seeds it, so the first frame of every map always sends -- a reconnect
  rebuilds the server's userinfo from scratch and a cache primed to the right
  answer would skip the send that repopulates it.

  IT REPORTS Rec_HidOK(), NOT cvar("rec_hid"), so a run declined for want of
  consent reports the same 0 as one declined by the switch. That is correct:
  the question the server is asking is "will a journal exist for this run",
  and both answers to it are no.
*/
void() Rec_HidReport =
{
	local float v;

	v = Rec_HidOK() ? 1 : 0;
	if (v == rec_rp_hidsent)
		return;

	rec_rp_hidsent = v;
	localcmd(sprintf("setinfo rechid %g\n", v));
};

/*
  One line in.  The server's SV_RecPut, and for the same three reasons: no
  trailing newline (buf_writefile adds one), no holes (buf_writefile SKIPS a null
  entry rather than writing a blank line, so a gap would shorten the file
  silently), and one place that enforces the cap.
*/
void(string s) Rec_ViewPut =
{
	if (rec_rp_view < 1)
		return;

	if (rec_rp_lines >= FS_VIEWMAX)
	{
		if (!rec_rp_full)
		{
			rec_rp_full = TRUE;
			dprint(sprintf("replay: angle sidecar hit the %g-line cap; "
			               "the rest of this run is not being kept\n", FS_VIEWMAX));
		}
		return;
	}

	bufstr_set(rec_rp_view, rec_rp_lines, s);
	rec_rp_lines = rec_rp_lines + 1;
};

// Header lines, so a length can be turned back into a frame count.
// Build 22 made it four; see the `hid` key below.
#define FS_VIEWHEAD 4

void() Rec_ViewBegin =
{
	rec_rp_lines = 0;
	rec_rp_full  = FALSE;
	// Build 30: see the declaration.  A run that begins while already ghosting
	// must open with a `ghost 1`, and clearing this here is what makes the
	// ordinary edge test produce one on the first recorded frame.
	rec_rp_wasghost = FALSE;
	rec_rp_view  = buf_create_ex("string", 0);
	if (rec_rp_view < 1)
	{
		rec_rp_view = 0;
		dprint("replay: buf_create failed; no angle sidecar for this run\n");
		return;
	}

	// A header, so the file says what it is without the .rec beside it.  Same
	// one-key-per-line shape, same rule: skip a key you do not know.
	//
	// VERSION 2, and the bump is for one added key.  The grammar's own rule says
	// an unknown header key is skipped, so `hid` alone would not need it -- but
	// reccheck.py reports an unknown key AS a finding, per version, and a build
	// that makes its own checker complain has taught everyone to ignore it.
	Rec_ViewPut("FTESURF-VIEW 2");
	// The short name, so this line matches the .rec's `map surf_666` rather
	// than saying "maps/surf_666.bsp" about the same run.  See Rec_MapName.
	Rec_ViewPut(sprintf("map %s", Rec_MapName()));
	/*
	  WHETHER A RAW INPUT JOURNAL WAS TAKEN FOR THIS RUN.

	  rec_hid can be turned off, and it should be able to be -- but a run recorded
	  without one must not be silently indistinguishable from a run recorded with
	  one, or the whole archive becomes untrustworthy at the moment somebody
	  notices the switch exists.  So the sidecar says, in the run's own file,
	  which regime produced it.  A `1` here is a claim that a .hid was STARTED,
	  not that one survived to disk -- Rec_HidEnd writes only for a PB, and says
	  why.
	*/
	Rec_ViewPut(sprintf("hid %g", Rec_HidOK() ? 1 : 0));
	Rec_ViewPut("begin");
};

/*
  One frame:  <cltime> <cmdframe> <ticks> <pitch> <yaw> <keys>

  THREE clocks, and each answers a question the others cannot.

  cltime is realtime - cl.mapstarttime: it advances per RENDERED frame, is
  unaffected by pause, latency or packet loss, and is the only thing that orders
  two frames inside one usercmd.  That ordering is the entire reason this file
  exists.

  clientcommandframe is cl.movesequence, the client's own usercmd counter.  It
  groups frames into the command they were folded into -- EXACTLY, from local
  state, with no snapshot in the way.  Without it the grouping would have to be
  inferred from the tick stat, which arrives at snapshot rate and lags.

  STAT_FS_TIMERTICKS is the run clock as the SERVER sees it, and it is the join
  key to the .rec, because that is the only clock both files share.

  Do not assume a fixed rate on either side.  Measured sample intervals in real
  .rec files are 65/s, 64.6/s and 43.5/s against a nominal 66.67, because a
  sample is written once per received PACKET and a packet can carry several
  usercmds.  Interpolate by the timestamps, never by index.

  Angles come from getproperty(VF_CL_VIEWANGLES) rather than the `view_angles`
  global: that global is a snapshot taken at CSQC_ChangeLocalPlayer time and so
  does not see a setproperty made later in the same frame -- which is precisely
  what SaveLoc_LockAngles is.  Reading the property reads the same storage the
  lock writes.

  No trailing newline: buf_writefile writes one after every string.
*/
void() Rec_ViewSample =
{
	local vector ang;

	ang = getproperty(VF_CL_VIEWANGLES);

	Rec_ViewPut(sprintf("%.4f %g %g %.2f %.2f %g",
	                    cltime, clientcommandframe, getstatf(STAT_FS_TIMERTICKS),
	                    ang_x, ang_y, Rec_ViewKeys()));
};

void() Rec_ViewDrop =
{
	if (rec_rp_view >= 1)
		buf_del(rec_rp_view);
	rec_rp_view  = 0;
	rec_rp_lines = 0;
};

/*
  The run ended.  Write, or throw away.

  RUNTAG is read rather than inferred: the client cannot tell a personal best
  from a voided run by watching the timer, and guessing wrong either loses a
  sidecar or overwrites a good one.
*/
void() Rec_ViewEnd =
{
	local float tag, leg, fh;
	local string dst;

	if (rec_rp_view < 1)
	{
		Rec_ViewDrop();
		return;
	}

	tag = getstatf(STAT_FS_RUNTAG);
	leg = getstatf(STAT_FS_RUNLEG);

	if (tag == RT_NONE || leg < 1)
	{
		// Voided, or the server was not keeping this one either.
		Rec_ViewDrop();
		return;
	}

	// A run that began and ended inside one rendered frame.  The header alone
	// is not a sidecar; writing it would leave a file that a reader has to
	// special-case for nothing.
	if (rec_rp_lines <= FS_VIEWHEAD)
	{
		Rec_ViewDrop();
		return;
	}

	/*
	  BUILD 23: the time is part of the name for the archived tags, and it comes
	  from STAT_FS_RUNTICKS -- published by the server in the same breath as
	  RUNTAG and standing exactly as long, precisely so that this line cannot
	  read a clock that has already moved on to the next attempt.
	*/
	dst = Rec_ViewPath(leg,
	                   FS_TagArchived(tag) ? getstatf(STAT_FS_RUNTICKS) : -1,
	                   Rec_TagName(tag), "view");

	fh = fopen(dst, FILE_WRITE);
	if (fh < 0)
		dprint(sprintf("replay: cannot open %s for writing\n", dst));
	else
	{
		// Four arguments: the three-argument form of buf_writefile computes its
		// end as `used - start`, not `used`.  See server/sv_timer.qc.
		buf_writefile(fh, rec_rp_view, 0, rec_rp_lines);
		fclose(fh);
		dprint(sprintf("replay: wrote %s (%g frames)\n",
		               dst, rec_rp_lines - FS_VIEWHEAD));
	}

	Rec_ViewDrop();
};

/*
===========================================================================
  BUILD 24 -- THE SIDECAR FOR A STAGE LIFTED OUT OF A MAIN RUN.

  The server slices a stage's .rec out of the run it is in the middle of (see
  SV_StageClose).  This is the other half: the same range of THIS buffer, under
  the same filename, so the pair is not orphaned.

  EVERY NUMBER COMES FROM THE SERVER, and none of it is recomputed here.  The
  client can see the stage boundaries go past -- it draws a split row at each one
  -- so it could in principle work out which stages were recorded and how long
  they were.  It must not.  The server's decision involves a jump detector and a
  ramp latch the client cannot observe, and its filename is a tick count from its
  own clock; two spellers of one filename is exactly what build 23 moved
  FS_RunPath to stop, and the failure mode is a .view that pairs with nothing.

  So STAGEREC is the edge and the other three stats are the answer, all four
  written in one server tick.

  THE TICKS COLUMN IS REBASED and cltime is not.  Column 2 is the run clock and
  is the join key to the .rec, so it has to start at zero for a file whose .rec
  starts at zero -- reccheck.py's cross-file test compares exactly those two
  ranges.  cltime is real time and is only ever used for ORDERING two frames
  inside one tick, so shifting it would buy nothing and lose the ability to tell
  how long the slice really took.  clientcommandframe is left alone for the same
  reason.
===========================================================================
*/
#define FS_VIEW_C_CLTIME  0
#define FS_VIEW_C_CMDFRAME 1
#define FS_VIEW_C_TICKS   2

float rec_rp_stagerec;           // last STAT_FS_STAGEREC acted on; -1 = seeding

void(float seg, float dur, float at) Rec_ViewStage =
{
	local float buf, i, n, t, frames, fh;
	local string l, dst;

	if (rec_rp_view < 1)
		return;
	if (dur <= 0)
		return;

	buf = buf_create_ex("string", 0);
	if (buf < 1)
	{
		dprint("replay: buf_create failed; this stage gets no sidecar\n");
		return;
	}

	// The same header the whole-run sidecar writes.  `hid` is the run's answer
	// and stays the run's answer: a stage of a journalled run was journalled.
	bufstr_set(buf, buf_getsize(buf), "FTESURF-VIEW 2");
	bufstr_set(buf, buf_getsize(buf), sprintf("map %s", Rec_MapName()));
	bufstr_set(buf, buf_getsize(buf), sprintf("hid %g", Rec_HidOK() ? 1 : 0));
	bufstr_set(buf, buf_getsize(buf), "begin");

	frames = 0;
	for (i = FS_VIEWHEAD; i < rec_rp_lines; i = i + 1)
	{
		l = bufstr_get(rec_rp_view, i);
		n = tokenize(l);
		if (n < 6)
			continue;

		t = stof(argv(FS_VIEW_C_TICKS));
		if (t < at)
			continue;
		/*
		  `>` and not `>=` on the far end.  The boundary tick belongs to the
		  stage that ENDS there -- the server's slice runs up to and including the
		  sample at that tick, because that sample is where the crossing was
		  detected -- so dropping it here would leave the sidecar one tick short
		  of its .rec and reccheck's range test would say so.
		*/
		if (t > at + dur)
			break;

		bufstr_set(buf, buf_getsize(buf),
		           sprintf("%s %s %g %s %s %s",
		                   argv(FS_VIEW_C_CLTIME), argv(FS_VIEW_C_CMDFRAME),
		                   t - at, argv(3), argv(4), argv(5)));
		frames = frames + 1;
	}

	if (frames < 1)
	{
		// The run produced no rendered frame inside this stage, which on a stage
		// shorter than one frame is possible and is not an error.  A header with
		// no body is not a sidecar; writing it would leave a file a reader has to
		// special-case for nothing.
		buf_del(buf);
		return;
	}

	/*
	  The leg is (this run's TRACK, the STAGE's leg) -- not the run's own leg,
	  which is `main`.  Rec_ViewPath decomposes RUNLEG for the whole-run sidecar
	  and is reused rather than repeated: track*100 + leg + 1 is spelled in
	  exactly one place on this side, and adding a second one here is how the two
	  drift and orphan a file.  The addition puts the stage's leg where RUNLEG's
	  leg goes, which for a main run is zero.

	  BUILD 57: seg + 1, AND THE +1 IS THE WHOLE STAGE.  STAT_FS_STAGESEG is still
	  the 0-based SEGMENT that closed, and the server writes the slice under leg
	  seg + 1 (FS_LegOf(seg, TRUE)) -- so stage 1, segment 0, has a folder of its
	  own at last.  Adding the bare segment here would name the folder one stage
	  early and orphan every sidecar, which is exactly the drift described above.
	  Only a full run lifts stages, so the run's own leg under RUNLEG is 0.
	*/
	dst = Rec_ViewPath(getstatf(STAT_FS_RUNLEG) + seg + 1, dur,
	                   FS_TagName(RT_PB), "view");

	fh = fopen(dst, FILE_WRITE);
	if (fh < 0)
		dprint(sprintf("replay: cannot open %s for writing\n", dst));
	else
	{
		buf_writefile(fh, buf, 0, buf_getsize(buf));
		fclose(fh);
		dprint(sprintf("replay: wrote %s (%g frames of stage %g)\n",
		               dst, frames, seg + 1));
	}

	buf_del(buf);
};

/*
  Watch STAT_FS_STAGEREC for the edge, exactly as Rec_ViewSaveEvents watches
  STAT_FS_SLSEQ -- including the seeding guard, and for the same reason: a client
  that joined mid-session would otherwise see the counter's current value as a
  change and write a sidecar for a stage it never recorded a frame of.
*/
void() Rec_ViewStageEvents =
{
	local float seq;

	seq = getstatf(STAT_FS_STAGEREC);

	if (rec_rp_stagerec < 0)
	{
		rec_rp_stagerec = seq;       // seeding; act on the NEXT change
		return;
	}
	if (seq == rec_rp_stagerec)
		return;
	rec_rp_stagerec = seq;

	Rec_ViewStage(getstatf(STAT_FS_STAGESEG),
	              getstatf(STAT_FS_STAGETICKS),
	              getstatf(STAT_FS_STAGEAT));
};

/*
  THE RAW INPUT JOURNAL, build 22.  The third file on this run.

  It is written by the ENGINE, not by this VM -- see the long note above
  IN_Commands in engine/client/in_generic.c for what it holds and, more
  importantly, what its timestamps do and do not mean.  All this file does is
  say when a run starts and when it stops, on the same TF_RECORDING edge that
  opens and closes the .view, so that the three files always describe the same
  run and no third opinion about "when the run began" can exist.

  WHAT localcmd COSTS HERE, because it is not free and the number matters.  The
  frame order is Sys_SendKeyEvents -> IN_Commands -> Cbuf_Execute -> render ->
  CSQC_UpdateView -> here.  So this frame queues the begin; the NEXT frame drains
  input at IN_Commands BEFORE Cbuf_Execute opens the journal, and that frame's
  input is lost; the frame after is the first one journalled.  About two video
  frames: ~6 ms at 300 fps, and ~500 ms at the 4 fps a headless config runs at,
  which is the loud version and is what the test config measures.  The end edge
  is symmetric -- the journal runs one frame long and catches input after the run
  ended.

  It is RECOVERABLE rather than hidden: the .hid's first `f` line carries an
  absolute time and the .view's first line carries cltime, so a reader can state
  the gap.  hidcheck.py reports it rather than assuming it is zero.  The fix, if
  it ever needs one, is a back-fill -- walk the engine's event ring backwards on
  begin and emit the entries still in it -- which is possible only because Patch
  200 timestamps every event.  Not in this build; measure it first.
*/
void() Rec_HidBegin =
{
	if (!Rec_HidOK())
		return;
	localcmd("in_journal_begin\n");
};

/*
  PB ONLY, and this is the one place the .hid deliberately does NOT follow the
  .view.

  Rec_ViewEnd above writes for every tag including `last`, because a .view is
  about 100 KB.  A .hid is about 1 MB per MINUTE, so a player taking forty
  attempts in an hour would write hundreds of megabytes of journals for runs
  nobody will ever audit -- and pay a multi-megabyte blocking write at the exact
  instant a run ends and the HUD is meant to show the result.

  The invariant that actually matters survives: a .hid that EXISTS describes
  exactly the run its .rec and .view describe.  What is given up is that every
  run has one, and the .view's `hid` key is what keeps that visible.

  The discard branch is not optional.  With no path the engine frees the buffer;
  without the call it stays resident until the next begin.
*/
void() Rec_HidEnd =
{
	local float tag, leg;

	if (!Rec_HidOK())
		return;

	tag = getstatf(STAT_FS_RUNTAG);
	leg = getstatf(STAT_FS_RUNLEG);

	if (tag != RT_PB || leg < 1)
	{
		localcmd("in_journal_end\n");
		return;
	}

	// RT_PB only, so the archived stamp always applies here -- but it is asked
	// through FS_TagArchived rather than assumed, because the tag test above is
	// a policy that has already changed once.
	localcmd(sprintf("in_journal_end %s\n",
	                 Rec_ViewPath(leg,
	                              FS_TagArchived(tag) ? getstatf(STAT_FS_RUNTICKS) : -1,
	                              Rec_TagName(tag), "hid")));
};

/*
  Trim the sidecar back to the run clock the SERVER saved at.

  BUILD 18, AND IT FIXES A BUILD 17 DEFECT THE RETRY WORK'S CROSS-FILE CHECK
  FOUND.  The save handshake is deliberately asymmetric: the server acts inside
  a physics tick, and this client sees the stat on its NEXT RENDERED FRAME,
  which is strictly afterwards, so the two never touch the same buffer at once.
  That ordering is right and stays.  What it also means is that the .view prefix
  runs PAST the .rec prefix -- by however long one rendered frame is.

  So on a load, the server rewound its recording to tick 110 while this rewound
  its camera to tick 148, and the resumed attempt then wrote tick 122 next: the
  sidecar's run clock ran backwards at the join, and a reader pairing the two
  files found a stretch of camera describing ticks that the recording no longer
  contained.  A measured file had a 26-tick overlap -- inflated there by a 4 fps
  headless window, and 1-3 ticks at a real frame rate, but wrong at any.

  STAT_FS_SAVETICKS is the exact answer: the run clock stored in the slot the
  cursor is on, which on a save event is the slot just written.  Walk back over
  the frames that describe time the server did not keep.

  Bounded, and the bound is not paranoia -- it is what stops a stat that is
  briefly stale or a slot that reads 0 from walking the whole buffer back to the
  header and silently discarding the run.
*/
#define FS_VIEWTRIM 256

float(float lines) Rec_ViewTrim =
{
	local float t, i, n;

	t = getstatf(STAT_FS_SAVETICKS);
	if (t <= 0)
		return lines;           // an idle save has no clock to trim against

	n = 0;
	i = lines;
	while (i > FS_VIEWHEAD && n < FS_VIEWTRIM)
	{
		tokenize(bufstr_get(rec_rp_view, i - 1));
		if (stof(argv(2)) <= t)
			break;
		i = i - 1;
		n = n + 1;
	}
	return i;
};

/*
  A save was taken: write the prefix, and remember where we were.

  The two have to happen together.  Writing without remembering means the next
  load of that slot takes the slow path and re-reads a file we could have skipped
  entirely; remembering without writing means a load in a LATER session finds
  nothing on disk and the sidecar starts halfway up a ramp.
*/
void(float id) Rec_ViewSaved =
{
	local float fh, lines;

	// FS_RETRY_SLOT is 0, so the lower bound is >= rather than > -- slot 0 is a
	// real path here, just one the save list is bounded to exclude.
	if (id < FS_RETRY_SLOT || id > FS_MAXSAVES)
		return;

	rec_rp_mark[id] = 0;

	// Nothing to keep.  A save taken outside a run is the ordinary case for
	// this, not a failure -- there is no recording open to take a prefix of.
	if (rec_rp_view < 1 || rec_rp_lines <= FS_VIEWHEAD)
		return;

	// Back to the instant the SERVER saved at, not the frame we noticed on.
	lines = Rec_ViewTrim(rec_rp_lines);
	if (lines <= FS_VIEWHEAD)
		return;

	fh = fopen(Rec_SavePath(id), FILE_WRITE);
	if (fh < 0)
	{
		dprint(sprintf("replay: cannot write %s\n", Rec_SavePath(id)));
		return;
	}

	// Four arguments: the three-argument form computes its end as `used - start`
	// rather than `used`.  See server/sv_timer.qc.
	buf_writefile(fh, rec_rp_view, 0, lines);
	fclose(fh);

	// The mark is the TRIMMED length, so a warm rewind lands where the file
	// does.  Marking the untrimmed one would put the two back out of step on
	// the very next load, which is the bug this exists to close.
	rec_rp_mark[id] = lines;
};

/*
  A save was loaded: put the sidecar back where that save left it.

  WARM -- we still hold the buffer this session's mark was taken in, and it is
  at least that long: assign.  Lines past the mark are stale but unreachable,
  because every write goes through Rec_ViewPut by index and Rec_ViewEnd passes an
  explicit count.

  COLD -- a different session, a map change, or a run that was thrown away since:
  read the prefix back off disk.  This is what makes a save survive a restart.

  A load with no sidecar either way leaves the buffer alone rather than clearing
  it.  The alternative is a replay whose camera stops at the load point, and a
  camera that is stale for the first half is strictly better than one that is
  absent for the second.
*/
void(float id) Rec_ViewLoaded =
{
	local float buf;

	// See Rec_ViewSaved.  Slot 0 is the retry point, and for it the cold branch
	// below is the ONLY one that can ever run: a map restart shuts this VM down
	// (CSQC_Shutdown in CLQW_ParseServerData), so rec_rp_mark is all zeroes by
	// the time the event arrives.  That is the whole reason the retry point
	// lives at a normal slot path instead of one of its own.
	if (id < FS_RETRY_SLOT || id > FS_MAXSAVES)
		return;

	if (rec_rp_view >= 1)
	if (rec_rp_mark[id] > 0)
	if (rec_rp_lines >= rec_rp_mark[id])
	{
		rec_rp_lines = rec_rp_mark[id];
		rec_rp_full  = FALSE;        // room again, so the cap may be re-reported
		return;
	}

	buf = buf_create_ex("string", 0);
	if (buf < 1)
		return;

	if (!buf_loadfile(Rec_SavePath(id), buf))
	{
		buf_del(buf);
		return;
	}

	if (rec_rp_view >= 1)
		buf_del(rec_rp_view);

	// The buffer is the truth about the file; the remembered mark was only this
	// session's claim about it, so it is replaced rather than trusted.
	rec_rp_view  = buf;
	rec_rp_lines = buf_getsize(buf);
	rec_rp_mark[id] = rec_rp_lines;
	rec_rp_full  = FALSE;
};

/*
  `retry` -- write the sidecar's prefix NOW, before the map restart takes it.

  This runs synchronously inside the engine's `retry` command, which offers the
  command to CSQC before it queues map_restart.  PR_ExecuteProgram runs QC to
  completion and PF_fclose writes through COM_WriteFile unconditionally, so the
  bytes are on disk before the builtin returns -- there is no race with the
  restart, which cannot begin until this returns and the Cbuf is pumped.

  It has to be done here rather than on the server's event, the way an ordinary
  save is, because there will not BE a client VM by then: CLQW_ParseServerData
  calls CSQC_Shutdown unconditionally, so this buffer and every mark in
  rec_rp_mark are destroyed by the restart.

  THE fremove IS NOT TIDINESS.  Without it, a retry taken with nothing to write
  -- outside a run, or before the first sample -- would leave the sidecar from a
  PREVIOUS retry on this map sitting at the path, to be paired with the fresh
  state.txt the server is about to write.  A camera track from the wrong attempt
  is worse than no camera track, because it looks like it worked.
*/
/*
  NO .hid IS ATTEMPTED HERE, and the reason is structural rather than a choice.

  This function runs SYNCHRONOUSLY inside the engine's `retry`, precisely because
  the map restart that follows destroys this VM -- that is why it writes the file
  itself instead of queueing anything.  localcmd cannot follow it there: an
  in_journal_end queued from here would sit in the Cbuf until after CL_ClearState
  had already dropped the journal (Patch 202), so it would name a file that was
  never going to be written and print a "no journal open" line for its trouble.

  A retry is not a PB either, so Rec_HidEnd would discard it in any case.
*/
void() Rec_ViewRetry =
{
	local float fh;

	fremove(Rec_SavePath(FS_RETRY_SLOT));

	if (rec_rp_view < 1 || rec_rp_lines <= FS_VIEWHEAD)
		return;

	fh = fopen(Rec_SavePath(FS_RETRY_SLOT), FILE_WRITE);
	if (fh < 0)
	{
		dprint("replay: cannot write the retry sidecar\n");
		return;
	}

	// Four arguments, for the reason Rec_ViewSaved gives.
	buf_writefile(fh, rec_rp_view, 0, rec_rp_lines);
	fclose(fh);
};

/*
  The save/load event stream.  See STAT_FS_SLSEQ in shared/sh_defs.qc.

  EDGE-DETECTED ON A COUNTER, not on the op.  Two saves to the same slot in a
  row are two events with the same SLOP, and polling the op alone would see one.

  rec_rp_slseq is seeded rather than zeroed on the first frame it is read: a
  client that connects to a server which has already been running has a non-zero
  counter for events that happened before it was watching, and replaying those
  would rewind a recording that never had them.
*/
void() Rec_ViewSaveEvents =
{
	local float seq, op, id;

	seq = getstatf(STAT_FS_SLSEQ);
	if (seq == rec_rp_slseq)
		return;

	op = getstatf(STAT_FS_SLOP);
	id = FS_SlopId(op);
	op = FS_SlopOp(op);

	/*
	  A RETRY IS HONOURED WHATEVER THE COUNTER SAYS, and that is the one way it
	  differs from the other two.

	  The seeding guard below exists to stop a client that joined a server
	  mid-session from replaying events it never saw.  But a retry point is the
	  first thing this VM is told about AFTER the restart that produced it --
	  the VM is brand new, so rec_rp_slseq is 0, while the server's counter is
	  whatever it had climbed to before the restart.  Any save or load earlier
	  in the session leaves seq > 1, and the guard would then silently drop the
	  single event that matters.
	*/
	if (op == SLOP_RETRY)
		Rec_ViewLoaded(FS_RETRY_SLOT);

	// One event or a hundred, the newest is the only one that can still be
	// acted on -- each is a rewind to an absolute mark, so the last wins.
	else if (rec_rp_slseq != 0 || seq == 1)
	{
		if (op == SLOP_SAVED)
			Rec_ViewSaved(id);
		else if (op == SLOP_LOADED)
			Rec_ViewLoaded(id);
	}

	/*
	  THE JOURNAL IS NOT REWOUND WITH THEM, and that is deliberate rather than a
	  shortfall.

	  Rec_ViewSaved/Loaded work because the .view is an INDEXED strbuf: a mark is
	  a line number and a rewind is an assignment.  A journal is a byte buffer in
	  the engine that this VM cannot index -- and, more fundamentally, its lines
	  are stamped on the WALL clock, so it has no run-clock column to trim
	  against.  Rec_ViewTrim can exist only because STAT_FS_SAVETICKS names a
	  clock that appears in column 3 of every .view line; the .hid has no such
	  column by construction.

	  So it keeps appending, and records that the splice happened.  The journal
	  then covers the whole SESSION of attempts with the rewind points marked --
	  which for an audit is better than the alternative, because the abandoned
	  attempts between saves are exactly where scripted input would show, and
	  those are the ones the .rec throws away.
	*/
	if (Rec_HidOK())
	{
		if (op == SLOP_SAVED)
			localcmd(sprintf("in_journal_note save %g\n", id));
		else if (op == SLOP_LOADED)
			localcmd(sprintf("in_journal_note load %g\n", id));
	}

	rec_rp_slseq = seq;
};

/*
  Per rendered frame, from CSQC_UpdateView.

  Edge-triggered on TF_RECORDING rather than polled, so the begin and the end
  each happen exactly once and neither depends on the frame rate.

  It is called AFTER SaveLoc_LockAngles for a reason: that function can rewrite
  the view angles, and what belongs in the file is the angle the frame was
  actually drawn at, not the one the mouse asked for.
*/
void() Rec_ViewFrame =
{
	local float rec, flags;

	// Build 58: unconditional and first, because the server has to have this
	// before a run arms rather than when one does.  See Rec_HidReport.
	Rec_HidReport();

	flags = getstatf(STAT_FS_TIMERFLAGS);
	rec = (flags & TF_RECORDING) ? TRUE : FALSE;

	if (rec)
	{
		if (!rec_rp_wasrec)
		{
			Rec_ViewBegin();
			Rec_HidBegin();
		}

		/*
		  NOT WHILE THE CLOCK IS HELD, and this one is a cap problem rather
		  than a tidiness one.  The .rec is sampled per usercmd and stops dead
		  while frozen; this file is sampled per RENDERED FRAME and would not.
		  A twenty-minute park at 300 fps is 360,000 lines against a
		  FS_VIEWMAX of 400,000 -- enough to blow the sidecar on a hold alone,
		  while the recording it is meant to accompany has not moved.  The two
		  caps are deliberately the same order of magnitude (see the header)
		  and that only holds if both stop together.
		*/
		/*
		  BUILD 30: DECLARE THE GHOST WINDOW HERE TOO, before the sample.

		  The server writes the same pair of edges into the .rec.  This file
		  needs its own because across a ghost THE TWO DISAGREE, for the first
		  time in this format's life and entirely legitimately: the .rec's angle
		  columns are the BODY's, pinned where you left it, while the lines below
		  keep recording VF_CL_VIEWANGLES -- which is the ghost camera, being
		  flown by a real hand on a real mouse.

		  That matters most for the check that does not exist yet.  hidcheck.py's
		  own list of what it deliberately does not verify has "that the recorded
		  view angles are the integral of the recorded mouse deltas" at the top of
		  it, and a ghost window is exactly where that check would fire on an
		  honest run: the mouse moved, the .view followed it, and the .rec did
		  not.  Without a marker the only available conclusions are "the angles
		  were forged" or "the journal was", and both are wrong.

		  Written even though the sample below may be skipped: a frozen clock
		  cannot coexist with a ghost anyway (SV_GhostSet refuses under both
		  holds), and an edge that is dropped because of an unrelated guard is an
		  unclosed bracket in the file.
		*/
		if (rec_gh_on != rec_rp_wasghost)
		{
			Rec_ViewPut(sprintf("ghost %g %.4f %g",
			                    rec_gh_on ? 1 : 0, cltime,
			                    getstatf(STAT_FS_TIMERTICKS)));
			rec_rp_wasghost = rec_gh_on;
		}

		if (!(flags & TF_FROZEN))
			Rec_ViewSample();
	}
	else if (rec_rp_wasrec)
	{
		/*
		  ORDER: the journal is closed AFTER the sidecar, because Rec_HidEnd
		  reads STAT_FS_RUNTAG to decide whether to keep the file and
		  Rec_ViewEnd reads the same stat for the same decision.  Reading it
		  twice in one frame is free and cannot disagree; splitting them across
		  frames could.
		*/
		Rec_ViewEnd();
		Rec_HidEnd();
	}

	rec_rp_wasrec = rec;

	/*
	  AFTER the sample, and that ordering is the whole of "seamless".

	  A save is taken at a moment in the run, so the prefix has to include the
	  frame the player was looking at when they pressed the key -- and the load
	  that follows has to rewind to a mark that includes it too.  Sampling after
	  the rewind would put one frame of the abandoned attempt at the head of the
	  resumed one; taking the mark before the sample would drop a frame from the
	  save.  This way both are exact.

	  It also has to run while `rec` is false: a save taken before the clock
	  starts still has to clear the slot's mark, or a load of it would rewind to
	  a mark belonging to a run that no longer exists.
	*/
	Rec_ViewSaveEvents();

	/*
	  BUILD 24: the stage-record edge, and it runs beside the save edge because it
	  is the same shape of thing -- a server-side event the client learns about
	  from a counter and has to act on with the buffer as it stands right now.

	  AFTER the sample, unlike the save mark.  A save is a rewind point and wants
	  the buffer as it was BEFORE this frame; a stage slice is a range that has
	  already ended, and the server closed it on a tick this frame's sample may
	  belong to.  Including it costs at most one frame past the boundary, which
	  the .rec's own slice also includes; dropping it would leave the pair
	  disagreeing about where the stage ended.
	*/
	Rec_ViewStageEvents();
};

/*
  A map change tears the CSQC VM down, and PF_buf_shutdown frees every strbuf it
  held.  buf_create then hands the same slot out again, so a handle carried
  across would ALIAS a live buffer belonging to something else -- a buf_del on it
  would destroy real data.  Zero it; the run in progress is lost, which is
  correct, because you changed the map.

  Called from CSQC_Init, which is the entrypoint that runs on the new VM.

  AND NOTHING IS FLUSHED ON THE WAY OUT, deliberately.  CSQC_Shutdown does run
  before the teardown and could write the buffer -- but the SERVER discards its
  half of the recording on a map change (SV_TimerMapInit), so a sidecar salvaged
  there would be an orphan describing a .rec that does not exist.  Two halves of
  one recording, dropped together.
*/
void() Rec_ViewInit =
{
	local float i;

	rec_rp_view   = 0;
	rec_rp_lines  = 0;
	rec_rp_wasrec = FALSE;
	rec_rp_full   = FALSE;

	// Build 58: -1, not 0 or 1.  CSQC_Init runs per map load, and a reconnect
	// gives the server a fresh userinfo -- so the cache must start at a value
	// no real answer can equal, or the first frame skips the send that would
	// have repopulated it.  See Rec_HidReport.
	rec_rp_hidsent = -1;

	// -1 rather than 0: the stage counter is per-connection and never resets, so
	// a client joining a session in progress must SEED from whatever it currently
	// reads rather than treat it as a change.  See Rec_ViewStageEvents.
	rec_rp_stagerec = -1;

	/*
	  BUILD 22.  Registered here, at the point of first read, which is the lesson
	  build 20 paid for on the server side: a cvar read before it is registered is
	  auto-created as the empty string and registercvar then declines to overwrite
	  it, so the feature boots silently OFF while printing "(default)" beside it.
	  Nothing reads rec_hid before Rec_HidBegin, and CSQC_Init runs long before any
	  run can start.

	  Read live rather than latched: it is a recording switch, not a physics rule,
	  and a player turning it off mid-session should get the next run without one
	  -- correctly marked in that run's own .view header.
	*/
	registercvar("rec_hid", "1");

	/*
	  Read once per VM rather than per run: CSQC_Init runs at every map load, so
	  a terms acceptance between maps is picked up, and one fopen per map is
	  nothing against one per run start.  See Rec_ConsentRead for why the file is
	  consulted at all when there is a cvar for it.
	*/
	rec_rp_consent = Rec_ConsentRead();
	// Published for cl_hud.qc's submit banner, which compiles BEFORE this file
	// and so cannot see rec_rp_consent.  Same value, one read; see the block
	// above HUD_DrawSubmitWarn for why the banner may not rely on the cvar alone.
	ui_consent_ver = rec_rp_consent;

	/*
	  The marks go with the buffer they were taken in.  They are line numbers
	  into a strbuf that no longer exists, so carrying one across a map change
	  would rewind the NEXT map's sidecar to an offset from the last one -- and
	  the saves themselves are per map, so there is nothing on the other side of
	  the change they could still be about.  The files on disk are untouched, so
	  a load after this simply takes the cold path and reads one back.

	  rec_rp_slseq is zeroed with them, which re-seeds the edge detector against
	  whatever counter the server is already at -- see Rec_ViewSaveEvents.
	*/
	for (i = 0; i <= FS_MAXSAVES; i = i + 1)
		rec_rp_mark[i] = 0;
	rec_rp_slseq = 0;
};
