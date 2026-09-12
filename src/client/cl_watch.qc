/*
===========================================================================
  cl_watch.qc -- reading a recording back.  Build 24.

  cl_replay.qc has said "PLAYBACK IS NOT HERE YET" since build 9.  This is it.

  WHAT IS BEING READ, AND WHY IT TAKES TWO FILES.

  The .rec is one sample per physics tick: position, velocity, the usercmd and
  four state bits, at 66.67 Hz, which is the rate the physics actually ran at
  and is provably enough for position -- the engine's own prediction renders an
  intermediate frame as a pure LERP of the two bracketing ticks, so a finer
  position sample would carry no information.

  The .view is one line per RENDERED frame: the view angles and the keyboard.
  Those are the two things the tick rate genuinely loses.  Between two ticks the
  camera really did sweep through angles no tick holds, and +left / +right have
  no usercmd bit at any sample rate -- they feed CL_AdjustAngles directly -- so
  no server-side recording could ever have got them back.  They are on disk only
  because the client wrote them down.

  So: POSITION comes from the .rec, ANGLES AND KEYS come from the .view, and the
  two are joined by the run clock, which is the only clock both files share.

  THE PLAYBACK CLOCK IS THE .rec's `t` COLUMN, IN SECONDS, AND IT MAY BE
  NEGATIVE.

  That choice is worth stating because the obvious alternative is wrong in a way
  that only shows up on some files.  The .view carries cltime, which is REAL
  time, and driving playback from it would be exact -- until a run that was
  paused on a save-lock hold, where cltime keeps advancing and the run clock does
  not.  A ten-second park would play as ten seconds of nothing.

  `t` has no such hole.  The recorder freezes with the clock (build 18: "rec
  lines held at 679 across the hold"), so a hold costs the file no samples at all
  and the run clock is continuous across it by construction.  reccheck.py has
  refused a non-monotone run clock since build 18, which makes that an invariant
  a reader may rely on rather than a hope.

  Negative t is the PADDING -- the 256-sample ring of approach the server keeps
  before the clock starts.  Your surf_aesthetic run opens at t = -3.8397.  The
  .view has no coverage there at all (the sidecar opens on the TF_RECORDING edge,
  and the pre-start ring is server-side only), so the approach is played with the
  first recorded angle held.  It is the run walking up to the start box, and it
  is worth seeing.

  THE THREE PANELS BUILD 23 REFUSED TO DRAW, AND WHAT CHANGED.

  The strafe bar, the board panel and the segment column are decided by
  STAT_FS_RAMPCONTACT and the PRE-CLIP STAT_FS_BOARDVEL, and .rec v3 carried
  neither -- its flags column had onground, ducked, jump and attack and that was
  all.  Build 23 drew none of the three and said so on screen, because deriving a
  ramp contact from the ground flag would have produced a bar indistinguishable
  from a measured one.

  The fix was not to derive them.  .rec v4 RECORDS them: one flags bit for the
  ramp contact, one plane per sample, and a `board` record carrying the latched
  arrival plane and the pre-clip velocity on the tick the engine's counter moved.
  All three panels now replay from measurement.

  A v3 file still refuses, and still says so.  Every recording on disk before
  this build is v3, including the surf_aesthetic run that proved the reader, so
  this is not a hypothetical branch -- it is the one you will see first.

  THE SEGMENT COLUMN IS BUILT ONCE, AT LOAD, AND NOT PER FRAME.  Board_Frame is
  an accumulator and a scrub runs the clock backwards; re-running it from t0 on
  every frame of a drag would be six thousand iterations per frame.  Watch_BuildSeq
  runs the REAL Board_Frame -- not a second copy of it, which is the thing that
  rots -- over the sample stream once, captures every row it pushes with the tick
  it was pushed at, and restores the live list afterwards.  A seek then becomes
  what Watch_Splits already is: a count into a table.
===========================================================================
*/

/*
  Declared here rather than in the cl_keys.qc override block because nothing
  before this file needs them -- only cl_main.qc does, and it compiles after.
  The block in cl_keys.qc holds exactly the ones the HUD and the timer read,
  and keeping it to those is what makes it obvious what a replay overrides.
*/
float  rec_wt_open;              // a recording is loaded (drawing or paused)
float  rec_wt_tag;               // RT_*, from the filename
float  rec_wt_pitch;
float  rec_wt_yaw;
float  rec_wt_evfin;             // the finish row is in the split list

/*
  The two buffers.  0 is the no-buffer sentinel, not -1: buf_create returns
  i + BUFSTRBASE with BUFSTRBASE == 1, so no real handle is ever 0 -- and a CSQC
  global after a map change is 0.  Same argument as rec_rp_view.
*/
float  rec_wt_rec;
float  rec_wt_view;
float  rec_wt_recn;              // lines in the .rec buffer
float  rec_wt_viewn;
float  rec_wt_rec0;              // first line after `begin`
float  rec_wt_view0;             // ditto, and always FS_VIEWHEAD

string rec_wt_path;              // the .rec we are playing
string rec_wt_owner;             // its `owner` header key
string rec_wt_map;               // its `map` header key
float  rec_wt_endticks;          // the `end` record's tick count
float  rec_wt_nsamp;             // samples in the file
float  rec_wt_recflags;          // the `flags` header key, -1 when absent
float  rec_wt_startseg;          // the SEGMENT the recording began at
// BUILD 57: and the LEG it belongs to -- 0 the full run, k stage k.  The two are
// no longer one number: a stage-1 run and a full run both begin at segment 0.
// From the `leg` header key, or derived from startseg for a file older than it.
float  rec_wt_leg;

/*
  BUILD 26: two more header facts, for hud_watch_info's file rows.

  `runid` is the .rec's only record of WHEN, and it needs no format change to be
  one: SV_RecOpen writes strftime("%Y%m%d-%H%M%S") plus the slot, so the first
  fifteen characters are a local wall clock to the second.  Kept as the raw
  string and formatted at the point of use -- a partial parse into three floats
  would be three ways to be wrong about a field whose only job is to be read.

  `pad` is the trailer's own count of pre-start samples (`end <ticks> <samples>
  <pad> <cps>`).  Nothing read it before, and it is the number that says how much
  of the span before t=0 is real approach rather than a reader's arithmetic --
  which is exactly the disagreement build 25's stage-slice bug turned out to be.
*/
string rec_wt_runid;
float  rec_wt_pad;

// rec_wt_time is declared in the cl_keys.qc override block with rec_wt_rate: it is
// the HUD's frame clock while a replay is up, and cl_hud.qc compiles first.
float  rec_wt_t0;                // first sample's t (negative with padding)
float  rec_wt_t1;                // last sample's t
// rec_wt_rate is declared in the cl_keys.qc override block: HUD_UpdateTurn needs
// it, to measure a turn per RUN second rather than per wall second at 4x speed.
float  rec_wt_slider;            // the speed slider's own 0..1 position
float  rec_wt_paused;
float  rec_wt_lastreal;          // cltime at the previous frame

/*
  The cursors.  Both are monotone in the common case -- playback only ever runs
  forward -- so an ordinary frame costs one or two tokenize calls.  A scrub is
  what makes them jump, and that is what the coarse index below is for.
*/
float  rec_wt_rcur;              // .rec line: the sample with the largest t <= now
float  rec_wt_rnext;             // the sample line after it
float  rec_wt_vti;               // the tick rec_wt_vblk0/1 were computed for
float  rec_wt_vblk0;             // .view lines [vblk0, vblk1) share that tick
float  rec_wt_vblk1;

/*
  THE COARSE INDEX, and it is what stops a scrub being a 25,000-line walk.

  Every Nth sample's line number and time, with N chosen at load so the table
  always fits whatever the file's length turns out to be.  A seek finds the
  entry with the largest t <= target -- a linear scan of at most WT_IDX floats --
  and then walks forward at most N samples.  Bounded either way, and no
  allocation.
*/
#define WT_IDX 512
float  rec_wt_ixline[WT_IDX];
float  rec_wt_ixt[WT_IDX];
float  rec_wt_ixn;
float  rec_wt_ixstep;

float  rec_wt_vxline[WT_IDX];
float  rec_wt_vxtick[WT_IDX];
float  rec_wt_vxn;
float  rec_wt_vxstep;

/*
  The stage and checkpoint records, lifted out of the sample stream at load.

  Collected up front rather than noticed as the clock passes them, because a
  scrub backwards has to rebuild the split list from scratch and re-walking the
  file for it would make a drag cost a full pass per frame.  FS_MAXSPLITS and
  FS_MAXCPS are both 24, so 64 cannot overflow on a legal file; the guard is
  there for an illegal one.
*/
#define WT_EVMAX 64
float  rec_wt_evkind[WT_EVMAX];  // SPK_STAGE or SPK_CP
float  rec_wt_evseg[WT_EVMAX];   // segment, or checkpoint ordinal
float  rec_wt_evtick[WT_EVMAX];
float  rec_wt_evn;
float  rec_wt_evshown;           // how many are in the split list right now

/*
===========================================================================
  THE PATH, AND WHY IT IS A CURVE AND NOT A POLYLINE.

  The first cut kept every Nth sample with N chosen from the sample count, drew
  a two-vertex R_BeginPolygon between each pair, and called the result a line.
  It read as a chain of separate fat blobs, and there were two independent
  reasons for that:

  1. THE CHORDS WERE NINETY UNITS LONG.  1024 points over a 5,982-sample run is
     a stride of six, and at 1000 u/s six ticks is ninety units.  A polyline
     with a corner every ninety units is a visibly faceted line, and the comment
     above it claimed a decimation "by distance and by angle change" that the
     code did not actually do.

  2. THE WIDTH JUMPED AT EVERY JOINT.  The ribbon width was computed once per
     SEGMENT from that segment's midpoint distance, so two adjacent quads had
     two different widths and did not share an edge -- a staircase of mismatched
     parallelograms, which is exactly what a slug looks like.

  So it is now built in two steps at load:

    CONTROL POINTS, chosen by distance AND by angle -- a point wherever the path
    has turned more than about four degrees, or gone WT_CTL_MAXD units without
    turning.  That is the rule the old comment promised, and it is the right one
    here: a surf run is long straight arcs joined by tight transitions, so a
    fixed stride spends its budget on the straights and starves the corners.

    THE CURVE, a Catmull-Rom spline THROUGH those controls.  Catmull-Rom passes
    exactly through every control point rather than near it, which is the whole
    reason to use it here: the drawn line goes through the recorded positions and
    is smooth between them, instead of cutting across them like a Bezier would.

  The spline is what makes the budget work.  The same 2048 drawn points that
  bought a faceted 90-unit polyline buy a C1-continuous curve at 45 units, and
  the corners are gone because the curve has none.
===========================================================================
*/
#define WT_CTLMAX   1024        // control points: the recorded turns
#define WT_PATHMAX  2048        // drawn curve points: what the strip is made of

// A turn worth a control point.  cos(4.4 degrees); below this the path is
// straight enough that the spline reproduces it from the neighbours anyway.
#define WT_CTL_ANG  0.997
// ...and one every this far regardless, so a dead-straight kilometre still has
// enough controls for the width taper to follow the distance.
#define WT_CTL_MAXD 192

vector rec_wt_cpos[WT_CTLMAX];
float  rec_wt_cspd[WT_CTLMAX];
float  rec_wt_ctick[WT_CTLMAX];
float  rec_wt_cn;

vector rec_wt_ppos[WT_PATHMAX];
float  rec_wt_pspd[WT_PATHMAX];
float  rec_wt_ptick[WT_PATHMAX];
float  rec_wt_pn;

/*
  What the screen-space drawer did on the last rendered frame, for `replay
  status`.  Declared up here with the path tables rather than beside the drawer,
  because Watch_Path -- which runs BEFORE renderscene and takes half of the
  probe -- compiles first, and a QC global has to exist before the function that
  reads it.  Same ordering constraint as the two blocks at the top of cl_keys.qc.

  When the line drew nothing at all there was no way to tell "never called" from
  "clipped everything" from "drawn off-screen" from "projected against the wrong
  camera", and those want four different fixes.  Guessing between them cost two
  builds; these five numbers cost none.
*/
float  rec_wt_p2n;               // quads emitted
float  rec_wt_p2clip;            // segments dropped by the near-plane clip
vector rec_wt_p2first;           // where the first quad landed, in screen pixels
vector rec_wt_p2pre;             // a fixed probe projected BEFORE renderscene
vector rec_wt_p2post;            // ...and the same probe projected after it
vector rec_wt_p2axr;             // 64 units RIGHT of the probe, projected
vector rec_wt_p2axu;             // ...and 64 units UP
vector rec_wt_p2min;             // screen bbox of every quad actually emitted
vector rec_wt_p2max;
float  rec_wt_p2wild;            // segments dropped for absurd screen coordinates

/*
  How far outside the viewport a projected vertex may be before its segment is
  thrown away.  Four screens' worth at 1080p, which is comfortably more than any
  segment that has a visible part needs and far less than the six figures a
  near-plane stub produces.  See the essay at the test itself.
*/
#define WT_P2GUARD 8192

/*
===========================================================================
  THE DEAD AIR.  Build 43.

  "the UI of the demo playback should mark parts where the player doesn't move
   as red, and have a selectable option that simply skips those parts during
   playback."

  Found the way everything else that classifies a stretch of this file is found:
  ONE EXTRA TEST INSIDE THE PASS THAT ALREADY WALKS EVERY SAMPLE.  Watch_Scan
  tokenizes all four thousand lines to choose control points, so the velocity is
  already in argv() and this costs a compare.  Per-frame detection was never on
  the table -- the file header's own argument applies unchanged: a scrub runs the
  clock backwards, and re-deriving spans from t0 on every frame of a drag would
  be six thousand iterations per frame.

  WHAT COUNTS AS STILL.  Horizontal speed only, and the vertical is left out
  deliberately: standing on a lift, or hanging at the apex of a jump, is not
  "not moving" in the sense the report means, and a run that idles usually idles
  on the ground where vertical speed is zero anyway.  hud_watch_idle_speed
  defaults to 20 u/s, which is under a walk and well under anything a surf map
  gives you for free.

  FOR HOW LONG.  hud_watch_idle_time, 0.5 s.  SEG_MINTIME (0.10) is this
  codebase's existing answer to "too short to be a thing", and this wants to be
  looser than that: half a second of standing still is deliberate, while a tenth
  is a landing, a crouch or a bad tick.

  A SAVE-LOCK HOLD WILL NEVER APPEAR HERE, AND THAT IS CORRECT.  The recorder
  freezes with the clock (see the file header: "rec lines held at 679 across the
  hold"), so a hold costs the file no samples at all and leaves no gap in `t` to
  find.  Only standing still WHILE THE CLOCK RUNS is marked -- which is the only
  kind that costs you a time.  Worth saying because the opposite is the obvious
  guess, and someone will otherwise go looking for the bug that is not there.

  THE PRE-START PAD IS EXCLUDED BY DEFAULT (hud_watch_idle_pad 0).  The approach
  is MEANT to be slow -- it is you walking up to the start box -- and marking two
  seconds of it red at the left end of the bar would say something false about
  the run.  The bar already marks t=0 with its own amber gradation, so the two
  halves are distinguishable without this.

  OVERFLOW IS REPORTED, not silent.  Same trade as the board cap (:1274) and the
  opposite of the segment column's (:1095): a run with more than WT_IDLEMAX
  parked stretches is doing something strange, and a bar that quietly stops
  marking them looks exactly like a run that stopped idling.
===========================================================================
*/
#define WT_IDLEMAX 64

float rec_wt_idt0[WT_IDLEMAX];   // run clock, seconds, where the stretch begins
float rec_wt_idt1[WT_IDLEMAX];   // ...and where it ends
float rec_wt_idn;
float rec_wt_idover;             // stretches the file had that would not fit

/*
  THE BOARD EVENTS, lifted out of the sample stream at load exactly as the stage
  and checkpoint records are, and for the same reason: the build pass walks the
  file forwards once and needs the board that belongs to the sample it is on.

  512 is generous rather than tight.  A surf run boards on every ramp entry --
  tens to a couple of hundred on a long map -- and a run that overflows this is
  one bouncing off a lip at 66 Hz, where the extra entries are the artifact
  SEG_MINTIME exists to absorb.  The overflow is REPORTED rather than silent; a
  segment column missing its last boards is a column that quietly lies.
*/
#define WT_BDMAX 512
float  rec_wt_bdt[WT_BDMAX];     // the run clock, seconds, at the board
float  rec_wt_bdc[WT_BDMAX];     // the engine's counter after it
vector rec_wt_bdn[WT_BDMAX];     // the latched arrival plane
vector rec_wt_bdv[WT_BDMAX];     // the PRE-clip velocity
float  rec_wt_bdn_n;
float  rec_wt_bdover;            // events the file had that would not fit

/*
  THE SEGMENT COLUMN, built once and then only counted into.

  One entry per row Seq_Push produced, in order, with the run tick it was pushed
  at.  A merge rewrites the last entry in place, exactly as it rewrites the last
  row of the live ring -- Watch_SeqRow is called from inside Seq_Push and is told
  which of the two happened, because from outside a merge and a scroll look the
  same (seq_n does not move for either).

  256 rows is about eight times what SEQ_MAX shows, which is what makes scrubbing
  backwards work: the column has to be able to show the twenty-four rows that
  were on screen at any point in the run, not just the last twenty-four.
*/
#define WT_SQMAX 256
float  rec_wt_sqkind[WT_SQMAX];
float  rec_wt_sqgain[WT_SQMAX];
float  rec_wt_sqde  [WT_SQMAX];
float  rec_wt_sqemax[WT_SQMAX];
float  rec_wt_sqdur [WT_SQMAX];
float  rec_wt_sqpct [WT_SQMAX];
float  rec_wt_sqlau [WT_SQMAX];
float  rec_wt_sqtick[WT_SQMAX];
float  rec_wt_sqn;
float  rec_wt_sqshown;           // rows applied to the live ring right now
float  rec_wt_sqbuildtick;       // the tick the build pass is currently on
float  rec_wt_bdshown;           // the board event Board_Compute last ran on
float  rec_wt_bridged;           // build 25: ramp-contact gaps the hold bridged

/*
  The live column, put back where the replay found it.

  ITS OWN ARRAYS AND NOT seq_mk_*, deliberately.  That snapshot belongs to the
  save-lock slots and is keyed by id; borrowing it would mean opening a replay
  silently discarded the snapshot a save had taken, and the save's load would
  then fall through to the file without anything saying why.  Entangling two hold
  state machines is the build 11 dead-load-key bug, and this build already
  refused to do it once for the position freeze (rec_wt_hold vs rec_sl_hold).
  170 floats is a cheap price for not doing it again.
*/
float  rec_wt_svn;
float  rec_wt_svhaslaunch;
float  rec_wt_svkind[SEQ_MAX];
float  rec_wt_svgain[SEQ_MAX];
float  rec_wt_svde  [SEQ_MAX];
float  rec_wt_svemax[SEQ_MAX];
float  rec_wt_svdur [SEQ_MAX];
float  rec_wt_svpct [SEQ_MAX];
float  rec_wt_svlau [SEQ_MAX];
float  rec_wt_svheld;            // a snapshot is out; Watch_Stop must restore it

// The .rec sample columns, named so the tokenize calls below read as English.
#define WT_C_T      0
#define WT_C_ORG    1           // +2, +3
#define WT_C_VEL    4           // +5, +6
#define WT_C_PITCH  7
#define WT_C_YAW    8
#define WT_C_FLAGS  9
#define WT_C_KEYS  10
#define WT_C_MOVE  11           // +12, +13 -- fwd, side, up
#define WT_C_NORM  14           // +15, +16 -- v4, the plane under you
#define WT_C_V4N   17           // a v4 sample has at least this many columns

// SV_RecFlags' bits.  Named here because the server names them by construction
// rather than by constant, and a reader guessing at bit order is how a replay
// ends up crouching in the wrong places.
#define WT_F_ONGROUND  1
#define WT_F_DUCKED    2
#define WT_F_JUMP      4
#define WT_F_ATTACK    8
#define WT_F_RAMP     16        // v4: the move clipped a ramp plane this tick

// The .view sample columns.
#define WT_V_CLTIME 0
#define WT_V_TICKS  2
#define WT_V_PITCH  3
#define WT_V_YAW    4
#define WT_V_KEYS   5

/*
  Is this line a sample or a record?

  A sample begins with its timestamp, so with a digit or a minus; every record
  begins with its keyword.  Testing the first character rather than tokenizing
  matters: the load scan looks at every line in the file and tokenizing all six
  thousand of them to find the dozen that are records would be most of the load
  time for none of the information.
*/
// BUILD 24: the body moved to FS_IsSample in shared/sh_defs.qc, beside the tag
// and path spellers, because the SERVER needs the same test now -- its stage
// slicer has to know which lines carry a `t` it must rebase.  Kept as a name
// because this file calls it in four places.
float(string s) Watch_IsSample = { return FS_IsSample(s); };

/*
  How many segments the replayed track has, straight out of the zone tables --
  which this VM already parsed for the map it is standing on.  The .rec header
  does not carry it, and the live STAT_FS_TIMERSEGS describes whichever leg the
  PLAYER is armed on, which is not necessarily the one being watched.

  Zone_TrackSegs and NOT `max(zone_seg) + 1`, which is what this function said
  when it was first written and which is wrong by one: the END zone's own index
  IS the count, so counting it as a segment made the replay's panel read "stage
  1/6" on surf_aesthetic beside a live panel reading "stage 1/5".  One speller,
  in shared/sh_zones.qc, and the server calls the same one.
*/
float(float track) Watch_TrackSegs = { return Zone_TrackSegs(track); };

void() Watch_Free =
{
	if (rec_wt_rec >= 1)
		buf_del(rec_wt_rec);
	if (rec_wt_view >= 1)
		buf_del(rec_wt_view);
	rec_wt_rec  = 0;
	rec_wt_view = 0;
	rec_wt_recn = rec_wt_viewn = 0;
	rec_wt_pn   = 0;
	rec_wt_evn  = 0;
	rec_wt_on   = FALSE;
};

/*
  One pass to count and to collect the records, a second to build the index and
  the path.

  Two passes rather than one because the stride both tables want is a function of
  the sample count, and the sample count is not known until the file has been
  walked.  The first pass costs a bufstr_get and a str2chr per line and tokenizes
  only the records; the second tokenizes only the strided samples.  On your
  surf_aesthetic run that is about six thousand cheap steps and a thousand
  tokenize calls, once, at load.
*/
void() Watch_Scan =
{
	local float i, n, c, ver, nextix, nextp, want;
	local float cstride, d, turn;
	local vector lastdir, step;
	local string s;
	local vector o;
	local float t, spd, idlim, idmin, idpad, idfrom, idon, idnow;

	rec_wt_rec0     = 0;
	rec_wt_nsamp    = 0;
	rec_wt_evn      = 0;
	rec_wt_endticks = 0;
	rec_wt_recflags = -1;
	rec_wt_tickrate = 0;
	ver            = 0;
	rec_wt_track    = 0;
	rec_wt_startseg = 0;
	rec_wt_leg      = -1;           // build 57: -1 = no `leg` key seen yet
	rec_wt_owner    = "";
	rec_wt_map      = "";
	rec_wt_runid    = "";
	rec_wt_pad      = 0;

	// ---- the header, up to and including `begin` -------------------------
	for (i = 0; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);
		n = tokenize(s);
		if (n < 1)
			continue;

		if (argv(0) == "begin")
		{
			rec_wt_rec0 = i + 1;
			break;
		}
		if (n < 2)
			continue;

		// Unknown keys are SKIPPED, never rejected -- the rule the .rec header
		// has followed since v2 and the whole reason v3 could add four columns.
		if (argv(0) == "FTESURF-REC") ver            = stof(argv(1));
		if (argv(0) == "map")         rec_wt_map      = argv(1);
		if (argv(0) == "track")       rec_wt_track    = stof(argv(1));
		if (argv(0) == "startseg")    rec_wt_startseg = stof(argv(1));
		if (argv(0) == "leg")         rec_wt_leg      = stof(argv(1));
		if (argv(0) == "tickrate")    rec_wt_tickrate = stof(argv(1));
		if (argv(0) == "owner")       rec_wt_owner    = argv(1);
		if (argv(0) == "flags")       rec_wt_recflags = stof(argv(1));
		if (argv(0) == "runid")       rec_wt_runid    = argv(1);
	}

	if (rec_wt_tickrate <= 0)
		rec_wt_tickrate = PM_TICK;

	/*
	  BUILD 57: A FILE WITH NO `leg` KEY IS OLDER THAN STAGE 1 BEING A LEG, and it
	  says exactly one thing: every stage run before build 57 began past segment 0
	  and every run that began AT segment 0 was the full track.  So its leg is
	  derived from the segment by the same helper the writer uses, with stagerun
	  standing in as `startseg > 0` -- which is not a guess about those files but
	  the only thing they could have meant.  After the loop, not inside it, because
	  the header's own rule is that its keys are order-free.
	*/
	if (rec_wt_leg < 0)
		rec_wt_leg = FS_LegOf(rec_wt_startseg, rec_wt_startseg > 0);

	// ---- pass one: count samples, collect records ------------------------
	for (i = rec_wt_rec0; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);
		if (Watch_IsSample(s))
		{
			rec_wt_nsamp = rec_wt_nsamp + 1;
			continue;
		}

		n = tokenize(s);
		if (n < 2)
			continue;

		if (argv(0) == "end")
		{
			rec_wt_endticks = stof(argv(1));
			// end <ticks> <samples> <pad> <cps>.  Guarded on the width rather
			// than assumed: a REC 2 trailer is two fields and argv(3) of it is
			// "", which stofs to a confident zero.
			if (n >= 4)
				rec_wt_pad = stof(argv(3));
			continue;
		}

		if (rec_wt_evn >= WT_EVMAX)
			continue;

		if (argv(0) == "stage")
		{
			if (n >= 3)
			{
				rec_wt_evkind[rec_wt_evn] = SPK_STAGE;
				rec_wt_evseg[rec_wt_evn]  = stof(argv(1));
				rec_wt_evtick[rec_wt_evn] = stof(argv(2));
				rec_wt_evn = rec_wt_evn + 1;
			}
			continue;
		}
		if (argv(0) == "cp")
		{
			if (n >= 3)
			{
				rec_wt_evkind[rec_wt_evn] = SPK_CP;
				rec_wt_evseg[rec_wt_evn]  = stof(argv(1));
				rec_wt_evtick[rec_wt_evn] = stof(argv(2));
				rec_wt_evn = rec_wt_evn + 1;
			}
			continue;
		}
	}

	/*
	  A SECOND SWEEP FOR THE BOARDS, and it is separate because the cap is.

	  Stage and checkpoint records share WT_EVMAX with each other and are bounded
	  by the zone file (24 splits, 24 checkpoints); boards are bounded by nothing
	  but how many ramps the map has, so `rec_wt_evn >= WT_EVMAX` guarding both
	  would let a board-heavy run silently push the stages out of the split list.
	  Two tables, two caps, one extra pass over lines that are already in memory.
	*/
	rec_wt_bdn_n  = 0;
	rec_wt_bdover = 0;
	for (i = rec_wt_rec0; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);
		if (Watch_IsSample(s))
			continue;
		if (substring(s, 0, 6) != "board ")
			continue;

		n = tokenize(s);
		if (n < 9)
			continue;
		if (rec_wt_bdn_n >= WT_BDMAX)
		{
			rec_wt_bdover = rec_wt_bdover + 1;
			continue;
		}

		rec_wt_bdt[rec_wt_bdn_n] = stof(argv(1));
		rec_wt_bdc[rec_wt_bdn_n] = stof(argv(2));
		rec_wt_bdn[rec_wt_bdn_n] = [stof(argv(3)), stof(argv(4)), stof(argv(5))];
		rec_wt_bdv[rec_wt_bdn_n] = [stof(argv(6)), stof(argv(7)), stof(argv(8))];
		rec_wt_bdn_n = rec_wt_bdn_n + 1;
	}

	// ---- pass two: the index and the path's control points ----------------
	//
	// Explicit "next wanted ordinal" counters rather than a modulo.  QuakeC has
	// no % of its own -- fteqcc synthesises one -- and the whole load path
	// depending on a synthesised operator over a float is not a bet worth taking
	// when two adds do the same job and read more plainly.
	rec_wt_ixstep = ceil(rec_wt_nsamp / (WT_IDX - 1));
	if (rec_wt_ixstep < 1)
		rec_wt_ixstep = 1;

	/*
	  THE PATH IS TOKENIZED IN FULL NOW, and that is a deliberate change of cost.

	  The old stride let this pass skip most lines with a str2chr; a control point
	  chosen by ANGLE cannot be, because the angle is only knowable from the
	  position, so every sample has to be read.  That is one extra tokenize per
	  sample at load -- about six thousand on your run, once -- bought against a
	  line that no longer has a corner in it every ninety units.

	  The fallback stride survives for the pathological case: if a run turns so
	  often that it fills WT_CTLMAX, `cstride` starts skipping samples so the tail
	  of the run still gets controls rather than the line simply stopping.
	*/
	cstride = ceil(rec_wt_nsamp / (WT_CTLMAX - 2));
	if (cstride < 1)
		cstride = 1;

	rec_wt_ixn = 0;
	rec_wt_cn  = 0;
	c         = 0;                  // sample ordinal
	rec_wt_t0  = 0;
	rec_wt_t1  = 0;
	nextix    = 0;
	nextp     = 0;
	lastdir   = '0 0 0';

	/*
	  The dead-air thresholds, read ONCE.  Registered by Watch_Init with these
	  same defaults; the fallbacks are here because a cvar read before its
	  registercvar returns "" and a zero speed threshold would mark nothing while
	  looking like it was working.
	*/
	rec_wt_idn    = 0;
	rec_wt_idover = 0;
	idon         = FALSE;
	idfrom       = 0;
	idlim        = cvar("hud_watch_idle_speed");
	if (idlim <= 0) idlim = 20;
	idmin        = cvar("hud_watch_idle_time");
	if (idmin <= 0) idmin = 0.5;
	idpad        = cvar("hud_watch_idle_pad");

	for (i = rec_wt_rec0; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);
		if (!Watch_IsSample(s))
			continue;

		n = tokenize(s);

		if (c == 0)
		{
			rec_wt_t0 = stof(argv(WT_C_T));

			/*
			  v4 is decided by the SAMPLE and not by the header key alone.

			  The header says what the writer believed; the column count says
			  what is actually there.  Both are required because they can
			  disagree in a way that matters: a v3 prefix resumed under a v4
			  build writes a v4 header over samples that have thirteen
			  columns, and reading argv(14) of those returns "" -- stof("") is
			  0, and a zero normal handed to the strafe bar is a target of
			  exactly nothing, drawn as confidently as a measured one.
			*/
			rec_wt_v4 = (ver >= 4 && n >= WT_C_V4N);
		}
		if (c == rec_wt_nsamp - 1)
			rec_wt_t1 = stof(argv(WT_C_T));

		if (c == nextix)
		{
			nextix = c + rec_wt_ixstep;
			if (rec_wt_ixn < WT_IDX)
			{
				rec_wt_ixline[rec_wt_ixn] = i;
				rec_wt_ixt[rec_wt_ixn]    = stof(argv(WT_C_T));
				rec_wt_ixn = rec_wt_ixn + 1;
			}
		}

		/*
		  A CONTROL POINT, by angle or by distance.

		  The first and the last are unconditional -- a spline needs its ends --
		  and everything between is kept only when it says something the
		  neighbours do not: the direction has turned by more than WT_CTL_ANG, or
		  WT_CTL_MAXD units have gone by without a turn.

		  `dir` is the step from the LAST KEPT control, not from the previous
		  sample, which is what makes this measure the turn of the drawn line
		  rather than the per-tick jitter of the recorded one.
		*/
		o_x = stof(argv(WT_C_ORG + 0));
		o_y = stof(argv(WT_C_ORG + 1));
		o_z = stof(argv(WT_C_ORG + 2));

		want = FALSE;
		if (c == 0)                     want = TRUE;
		else if (c == rec_wt_nsamp - 1)  want = TRUE;
		else if (c >= nextp)
		if (rec_wt_cn > 0)               // c == 0 above guarantees this, but the
		{                               // array read below must not depend on it
			step = o - rec_wt_cpos[rec_wt_cn - 1];
			d    = vlen(step);
			if (d >= WT_CTL_MAXD)
				want = TRUE;
			else if (d > 1)
			if (lastdir != '0 0 0')
			{
				// vector * vector is the dot product, but it needs a float lvalue
				// to land in -- fteqcc will not infer the type through a compare.
				turn = normalize(step) * lastdir;
				if (turn < WT_CTL_ANG)
					want = TRUE;
			}
		}

		if (want)
		if (rec_wt_cn < WT_CTLMAX)
		{
			if (rec_wt_cn > 0)
			if (o != rec_wt_cpos[rec_wt_cn - 1])
				lastdir = normalize(o - rec_wt_cpos[rec_wt_cn - 1]);

			rec_wt_cpos[rec_wt_cn]  = o;
			rec_wt_cspd[rec_wt_cn]  = vlen([stof(argv(WT_C_VEL + 0)),
			                              stof(argv(WT_C_VEL + 1)), 0]);
			rec_wt_ctick[rec_wt_cn] = stof(argv(WT_C_T)) / rec_wt_tickrate;
			rec_wt_cn = rec_wt_cn + 1;
			nextp = c + cstride;
		}

		/*
		  ---- DEAD AIR, and it is a state machine of one bit ----------------

		  A stretch OPENS on the first slow sample and CLOSES on the first fast
		  one, and is only kept if it lasted.  Closing on the fast sample rather
		  than on the last slow one is deliberate: the run resumed somewhere
		  between those two ticks, and a mark that stops at the last slow sample
		  leaves a tick-wide gap of unmarked standing still at the end of every
		  stretch.  Half a tick long, and wrong in the direction that under-
		  reports, which is the one worth avoiding.

		  The `t >= 0` half is nested rather than &&'d out of habit rather than
		  necessity -- there is no array index here -- but the file's rule is
		  worth keeping uniform, and the two conditions read as the two separate
		  questions they are.
		*/
		t   = stof(argv(WT_C_T));
		spd = vlen([stof(argv(WT_C_VEL + 0)), stof(argv(WT_C_VEL + 1)), 0]);

		idnow = FALSE;
		if (spd < idlim)
		if (idpad || t >= 0)
			idnow = TRUE;

		if (idnow)
		{
			if (!idon)
			{
				idon   = TRUE;
				idfrom = t;
			}
		}
		else if (idon)
		{
			idon = FALSE;
			if (t - idfrom >= idmin)
			{
				if (rec_wt_idn < WT_IDLEMAX)
				{
					rec_wt_idt0[rec_wt_idn] = idfrom;
					rec_wt_idt1[rec_wt_idn] = t;
					rec_wt_idn = rec_wt_idn + 1;
				}
				else
					rec_wt_idover = rec_wt_idover + 1;
			}
		}

		c = c + 1;
	}

	/*
	  A run that ENDS parked still ends parked, and the file's last sample is
	  where it ends.  Without this a player who crossed the line and stood there
	  -- or a `last.rec` from an attempt that was simply abandoned -- would have
	  its final stretch dropped, which is the one stretch most likely to be long.
	*/
	if (idon)
	if (rec_wt_t1 - idfrom >= idmin)
	{
		if (rec_wt_idn < WT_IDLEMAX)
		{
			rec_wt_idt0[rec_wt_idn] = idfrom;
			rec_wt_idt1[rec_wt_idn] = rec_wt_t1;
			rec_wt_idn = rec_wt_idn + 1;
		}
		else
			rec_wt_idover = rec_wt_idover + 1;
	}

	if (rec_wt_idover > 0)
		print(sprintf("^3replay: %g still stretch(es) past the %g cap were dropped; "
		              "the bar stops marking them\n", rec_wt_idover, WT_IDLEMAX));

	// ---- the .view's index -----------------------------------------------
	rec_wt_view0  = 0;
	rec_wt_vxn    = 0;
	if (rec_wt_view >= 1)
	{
		for (i = 0; i < rec_wt_viewn; i = i + 1)
		{
			s = bufstr_get(rec_wt_view, i);
			if (Watch_IsSample(s))
				break;
		}
		rec_wt_view0 = i;

		n = rec_wt_viewn - rec_wt_view0;
		rec_wt_vxstep = ceil(n / (WT_IDX - 1));
		if (rec_wt_vxstep < 1)
			rec_wt_vxstep = 1;

		/*
		  BUILD 43 -- RECORDS ARE STEPPED OVER HERE, THE WAY THE .rec'S SCAN
		  ALREADY STEPS OVER ITS OWN.

		  The .view is not all samples.  Rec_ViewFrame interleaves a FOUR-token
		  `ghost <0|1> <cltime> <ticks>` line (cl_replay.qc:1050-1056), and this
		  loop used to take whatever line the stride landed on and read argv(2)
		  as a run tick -- which on a ghost line is a CLTIME, a number in the
		  hundreds where a tick is in the thousands but on a different scale
		  entirely.  One poisoned entry sends Watch_ViewBlock's seek to the wrong
		  starting line, and the same unfiltered read in Watch_ViewBlock itself
		  could hand the camera a tick count as its pitch.

		  Latent rather than observed: no .rec or .view on disk carries a ghost
		  record, because no ghosted run has ever been recorded.  It is fixed
		  here because build 43 is editing the reader either way, and because the
		  .rec side has had FS_IsSample guarding all four of its scans since
		  build 24 -- the .view simply never got the same treatment.

		  The cost is one bufstr_get and one first-character test per line at
		  load instead of one per stride.  The .rec's own pass tokenizes every
		  line in full, so this is not the expensive half of anything.
		*/
		nextix = rec_wt_view0;
		for (i = rec_wt_view0; i < rec_wt_viewn; i = i + 1)
		{
			if (!Watch_IsSample(bufstr_get(rec_wt_view, i)))
			{
				// Push the wanted ordinal past it rather than losing the whole
				// stride: an index that skips an entry is coarser, and this one
				// is already only 512 entries over the file.
				if (i == nextix)
					nextix = i + 1;
				continue;
			}
			if (i != nextix)
				continue;
			nextix = i + rec_wt_vxstep;
			if (rec_wt_vxn >= WT_IDX)
				break;
			tokenize(bufstr_get(rec_wt_view, i));
			rec_wt_vxline[rec_wt_vxn] = i;
			rec_wt_vxtick[rec_wt_vxn] = stof(argv(WT_V_TICKS));
			rec_wt_vxn = rec_wt_vxn + 1;
		}
	}

	if (ver > 4)
		print(sprintf("^3replay: %s is FTESURF-REC %g and this build knows 4; "
		              "reading it anyway\n", rec_wt_path, ver));
};

/*
===========================================================================
  The curve

  Catmull-Rom through the control points, evaluated once at load into the
  drawn-point table.  Once, and not per frame, for the same reason the segment
  column is built once: a scrub is a user action but a frame is three
  milliseconds, and three thousand spline evaluations do not fit in one.

  CATMULL-ROM RATHER THAN A BEZIER OR A B-SPLINE, and the reason is the whole
  requirement.  It INTERPOLATES: the curve passes exactly through every control
  point.  A B-spline only approaches them, which on a surf line means the drawn
  path would be smooth and in the wrong place -- visibly missing the ramp the
  run was actually on, which is worse than faceted and right.

      p(t) = 0.5 * ( 2*P1
                   + (P2 - P0) * t
                   + (2*P0 - 5*P1 + 4*P2 - P3) * t^2
                   + (3*P1 - P0 - 3*P2 + P3) * t^3 )

  The ends REFLECT the neighbour rather than duplicating the endpoint.
  Duplication makes the first and last spans flatten out, because the phantom
  point sits on top of the real one and the tangent there goes to zero;
  reflection keeps the tangent the interior curve already has.
===========================================================================
*/
vector(vector p0, vector p1, vector p2, vector p3, float t) Watch_Spline =
{
	local float t2, t3;

	t2 = t * t;
	t3 = t2 * t;

	return 0.5 * ((2 * p1)
	            + (p2 - p0) * t
	            + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
	            + (3 * p1 - p0 - 3 * p2 + p3) * t3);
};

/*
  What a given step would COST, in drawn points.

  Count only: no spline evaluation and no array writes, because where the points
  land has no bearing on how many of them there are.  That is what makes the
  refinement in Watch_BuildCurve affordable -- it asks this question at most
  three times at load, over at most 1022 spans, against a scan pass that already
  tokenizes four thousand lines.

  It must stay a mirror of the emit loop's own arithmetic, ceil and both clamps
  included.  If they drift, the refinement stops being safe and the table can
  overrun again -- which is the bug it exists to have fixed.
*/
float(float step) Watch_CurveCost =
{
	local float i, n, sub, len;

	n = 0;
	for (i = 0; i < rec_wt_cn - 1; i = i + 1)
	{
		len = vlen(rec_wt_cpos[i + 1] - rec_wt_cpos[i]);
		sub = ceil(len / step);
		if (sub < 1)  sub = 1;
		if (sub > 16) sub = 16;
		n = n + sub;
	}

	return n + 1;                   // + the final control point, appended below
};

void() Watch_BuildCurve =
{
	local float i, j, sub, len, total, step, f;
	local float spans, budget, full, used, cst, trial, lo, hi;
	local vector p0, p1, p2, p3;

	rec_wt_pn = 0;
	if (rec_wt_cn < 2)
	{
		// One control point or none: there is no span to subdivide, so the
		// "curve" is whatever was recorded, copied straight across.
		for (i = 0; i < rec_wt_cn; i = i + 1)
		{
			rec_wt_ppos[i]  = rec_wt_cpos[i];
			rec_wt_pspd[i]  = rec_wt_cspd[i];
			rec_wt_ptick[i] = rec_wt_ctick[i];
		}
		rec_wt_pn = rec_wt_cn;
		return;
	}

	/*
	  THE STEP IS DERIVED FROM THE PATH'S OWN LENGTH, not fixed.

	  A fixed subdivision count per span would spend the same budget on a
	  four-unit span as on a two-hundred-unit one, so a run with many short
	  controls -- a twitchy section, or a bhop -- would exhaust WT_PATHMAX and
	  simply stop drawing partway through, which looks exactly like a bug.
	  Measuring the total length first and dividing fills the table once however
	  long the run is, and the floor stops a short run being chopped into
	  microsegments that cost draw calls and show nothing.

	  BUILD 43 -- IT DID NOT FILL THE TABLE ONCE.  IT OVERRAN IT, AND THE
	  OVERRUN ATE THE END OF EVERY LONG RUN.

	  The paragraph above was written as if the budget arithmetic were exact, and
	  the loop below spends `ceil(len / step)` per span.  Ceil is not free: it
	  costs up to one whole extra point PER SPAN, so the real spend is not
	  total/step but

	      sum(ceil(len_i / step))  ==  total/step + (up to one per span)
	                               ==  (WT_PATHMAX - 2) + rec_wt_cn

	  against a table of WT_PATHMAX.  Any run with more than a couple of controls
	  overspends, and the tail is what is lost -- silently, because the guard
	  below used to break only the inner loop.

	  MEASURED, not reasoned about: simulating this exact function over all 57
	  .rec files on disk, TWELVE truncate.  surf_fiellu/main/0003991_pb.rec --
	  the file the report came from -- has cn 757 and total 153432, saturates at
	  pn == 2048, and draws 86.6% of its path.  The rest land between 82.6% and
	  96.1%, which is why the same build looks fine on most files and stops
	  "at the last 10%" on some.

	  THE FIX IS TO RESERVE THE ROUNDING, and it is exact rather than generous.
	  Each span costs at most len_i/step + 1, so reserving one point per span up
	  front bounds the total at the budget:

	      total/step + spans  ==  (budget - spans) + spans  ==  budget

	  Two points are then still spare -- one for the final control point the loop
	  never emits, one so the >= guard below can never be the thing that ends the
	  curve.  A path that reaches the guard now is a bug in this arithmetic, not
	  a long run.
	*/
	total = 0;
	for (i = 0; i < rec_wt_cn - 1; i = i + 1)
		total = total + vlen(rec_wt_cpos[i + 1] - rec_wt_cpos[i]);

	spans  = rec_wt_cn - 1;
	budget = WT_PATHMAX - 2;

	/*
	  Cannot fire at the current caps -- WT_CTLMAX is 1024, so spans is at most
	  1022 against a budget of 2046 -- but the divisor must not be allowed to
	  reach zero on the word of a constant somewhere else in the file.  A step of
	  `total` gives one point per span, which is the honest answer when there is
	  no budget left to subdivide with.
	*/
	if (spans >= budget)
		step = total;
	else
		step = total / (budget - spans);

	if (step < 12)
		step = 12;

	/*
	  ...AND THEN SPEND THE SLACK, because the reservation above is a WORST case
	  and the worst case is not what happens.

	  Reserving a whole point per span assumes every ceil rounds all the way up;
	  on real spans it rounds up by half a point on average, so the conservative
	  step leaves about a fifth of the table unused.  Measured on the twelve
	  files that used to truncate: surf_fiellu spent 1583 of 2048 at a step of
	  118.9, where the essay above sets the design intent at roughly 45 units
	  between drawn points.  Shipping that would have traded a line that stops
	  early for a line that is faceted everywhere -- the exact fault the spline
	  was introduced to fix, moved rather than removed.

	  BISECTED, AND NOT SCALED IN PROPORTION, and the difference is not academic.
	  Cost is a sum of ceils, so it does not fall smoothly as the step shrinks --
	  it sits flat and then jumps, because a step crossing under a span's length
	  moves that whole span from one point to two at once.  With 757 controls
	  most spans are shorter than the safe step, so they all cross within a few
	  units of each other.  A single proportional guess lands past that cliff and
	  is rejected whole: measured, it left surf_fiellu and surf_utopia's PB at
	  exactly the conservative step while helping every other file.  Bisection
	  between the step that is known to fit and the guess that does not finds the
	  edge instead of stepping over it.

	  The invariant is that `hi` has ALWAYS been counted and found to fit, so
	  whatever the loop exits with has been proved rather than assumed.  The emit
	  loop's own guard stays where it is regardless -- a refinement that has to
	  be trusted is a refinement that can be wrong.

	  Six passes puts the answer within 2% of the true edge, over at most 1022
	  spans of one vlen each, once per replay opened.
	*/
	hi   = step;                                // counted below, always fits
	used = Watch_CurveCost(hi);

	for (i = 0; i < 5; i = i + 1)
	{
		if (used >= budget)
			break;

		// Where the budget would land if cost fell smoothly.  It does not, but
		// it is the right direction and it is one multiply.
		lo = hi * used / budget;
		if (lo < 12)
			lo = 12;
		if (lo >= hi)
			break;

		cst = Watch_CurveCost(lo);
		if (cst <= budget)
		{
			// It fits.  Take it and go again from there -- one proportional
			// step is not enough on a file whose spans are mostly shorter than
			// the step, where each pass only recovers part of the slack.
			hi   = lo;
			used = cst;
			continue;
		}

		/*
		  lo does not fit, so the cliff is between the two.  Find its edge and
		  stop: past here the sequence has converged and further passes would
		  bisect an interval smaller than one point's worth of step.
		*/
		for (j = 0; j < 5; j = j + 1)
		{
			trial = (lo + hi) * 0.5;
			if (trial >= hi)
				break;
			if (Watch_CurveCost(trial) <= budget)
				hi = trial;
			else
				lo = trial;
		}
		break;
	}

	step = hi;

	full = FALSE;
	for (i = 0; i < rec_wt_cn - 1; i = i + 1)
	{
		/*
		  BUILD 43.  The guard inside the subdivision loop below breaks only
		  ITSELF -- that is what `break` does in QuakeC as in C -- so before this
		  test existed the outer loop kept walking every remaining span, entered
		  the inner loop, re-tripped the guard and emitted nothing, all the way
		  to the end of the file.  The curve simply stopped mid-run and the last
		  control point was dropped too, because the append below is conditional
		  on the same full table.
		*/
		if (full)
			break;

		// Reflected ends; see the essay above.
		p0 = (i > 0) ? rec_wt_cpos[i - 1]
		             : (2 * rec_wt_cpos[0] - rec_wt_cpos[1]);
		p1 = rec_wt_cpos[i];
		p2 = rec_wt_cpos[i + 1];
		p3 = (i + 2 < rec_wt_cn) ? rec_wt_cpos[i + 2]
		                        : (2 * rec_wt_cpos[rec_wt_cn - 1]
		                           - rec_wt_cpos[rec_wt_cn - 2]);

		len = vlen(p2 - p1);
		sub = ceil(len / step);
		if (sub < 1)  sub = 1;
		if (sub > 16) sub = 16;

		/*
		  j runs from 0 INCLUSIVE and stops before sub, so each span emits its
		  own start and the NEXT span emits the shared joint -- one copy of every
		  point rather than two.  That matters: a duplicated point is a
		  zero-length segment, and a zero-length segment has no direction for the
		  strip below to mitre against.
		*/
		for (j = 0; j < sub; j = j + 1)
		{
			if (rec_wt_pn >= WT_PATHMAX)
			{
				full = TRUE;
				break;
			}

			f = j / sub;
			rec_wt_ppos[rec_wt_pn] = Watch_Spline(p0, p1, p2, p3, f);

			// Speed and the run clock are linear along the span.  They drive the
			// colour and the played/ahead split, and interpolating them the same
			// way the position is keeps both on the curve instead of stepping at
			// the joints.
			rec_wt_pspd[rec_wt_pn]  = rec_wt_cspd[i]
			                      + (rec_wt_cspd[i + 1] - rec_wt_cspd[i]) * f;
			rec_wt_ptick[rec_wt_pn] = rec_wt_ctick[i]
			                      + (rec_wt_ctick[i + 1] - rec_wt_ctick[i]) * f;
			rec_wt_pn = rec_wt_pn + 1;
		}
	}

	// The last control point, which the loop above never emits because every
	// span stops one short of its end.  The test survives the build-43 fix as a
	// bounds check and not as a policy: the reservation above leaves two points
	// spare, so this can no longer be the reason the curve ends short.
	if (rec_wt_pn < WT_PATHMAX)
	{
		rec_wt_ppos[rec_wt_pn]  = rec_wt_cpos[rec_wt_cn - 1];
		rec_wt_pspd[rec_wt_pn]  = rec_wt_cspd[rec_wt_cn - 1];
		rec_wt_ptick[rec_wt_pn] = rec_wt_ctick[rec_wt_cn - 1];
		rec_wt_pn = rec_wt_pn + 1;
	}

	/*
	  REPORTED, NOT SILENT, for the reason the board cap is (:1274-1276): a curve
	  that ends early looks exactly like a run that ended early, and the whole of
	  build 42's version of this bug was that nothing said so.  After the
	  reservation above this cannot fire; if it ever does, the arithmetic is
	  wrong and the number that proves it is right here.
	*/
	if (full)
		print(sprintf("^3replay: path filled the %g-point table at %g controls; "
		              "the drawn line ends early\n", WT_PATHMAX, rec_wt_cn));
};

/*
  Put the .rec cursor on the sample with the largest t <= want.

  Forward from where it is when that is forward, which is every ordinary frame;
  otherwise back to the nearest index entry and forward from there.  Records in
  the stream are stepped over rather than counted.
*/
void(float want) Watch_RecSeek =
{
	local float i, j, t;
	local string s;

	if (rec_wt_rec < 1)
		return;

	/*
	  The nearest index entry at or before the target, and it is consulted on
	  EVERY seek rather than only on a backwards one.

	  A forward drag of the scrub bar is the case that makes that necessary: the
	  cursor is valid and behind the target, so a "walk forward from where we
	  are" would be right but would step through every sample in between -- five
	  thousand of them for a drag to the end, per frame, while the mouse is down.
	  Starting from the index bounds every seek in either direction to one stride,
	  which is twelve samples on a run this length.
	*/
	j = rec_wt_rec0;
	for (i = 0; i < rec_wt_ixn; i = i + 1)
		if (rec_wt_ixt[i] <= want)
			j = rec_wt_ixline[i];

	if (rec_wt_rcur < rec_wt_rec0)
		rec_wt_rcur = j;
	else
	{
		tokenize(bufstr_get(rec_wt_rec, rec_wt_rcur));
		if (stof(argv(WT_C_T)) > want)
			rec_wt_rcur = j;             // the cursor is ahead: restart
		else if (j > rec_wt_rcur)
			rec_wt_rcur = j;             // the index is further along: skip to it
	}

	// Walk forward while the NEXT sample is still at or before `want`.
	while (1)
	{
		j = -1;
		for (i = rec_wt_rcur + 1; i < rec_wt_recn; i = i + 1)
		{
			s = bufstr_get(rec_wt_rec, i);
			if (Watch_IsSample(s))
			{
				j = i;
				break;
			}
		}
		if (j < 0)
			break;

		tokenize(bufstr_get(rec_wt_rec, j));
		t = stof(argv(WT_C_T));
		if (t > want)
			break;
		rec_wt_rcur = j;
	}

	// And find the one after it, which is the far end of the interpolation.
	rec_wt_rnext = -1;
	for (i = rec_wt_rcur + 1; i < rec_wt_recn; i = i + 1)
		if (Watch_IsSample(bufstr_get(rec_wt_rec, i)))
		{
			rec_wt_rnext = i;
			break;
		}
};

/*
  The block of .view lines belonging to one tick.

  There are about five of them at 300 fps and one or none at 60, so the block is
  found rather than assumed: [vblk0, vblk1) is every line carrying tick `ti`, and
  the caller picks inside it by where it is within the tick.  Cached, because the
  tick only changes once every 15 ms of playback and the cache therefore hits on
  four frames out of five.
*/
void(float ti) Watch_ViewBlock =
{
	local float i, j, tk;

	if (rec_wt_view < 1)
		return;
	if (ti == rec_wt_vti)
	if (rec_wt_vblk1 > rec_wt_vblk0)
		return;

	// Nearest index entry at or before the wanted tick, then walk.
	j = rec_wt_view0;
	for (i = 0; i < rec_wt_vxn; i = i + 1)
		if (rec_wt_vxtick[i] <= ti)
			j = rec_wt_vxline[i];

	/*
	  BUILD 43: SAMPLES ONLY, on both walks.  See the essay beside the index
	  build in Watch_Scan -- a `ghost` record's argv(2) is a cltime, and reading
	  it as a tick here would either end the search early or leave a record
	  inside [vblk0, vblk1), where the caller's sub-tick pick could land on it
	  and read a tick count as a pitch.
	*/
	for (i = j; i < rec_wt_viewn; i = i + 1)
	{
		if (!Watch_IsSample(bufstr_get(rec_wt_view, i)))
			continue;
		tokenize(bufstr_get(rec_wt_view, i));
		if (stof(argv(WT_V_TICKS)) >= ti)
			break;
	}
	if (i >= rec_wt_viewn)
		i = rec_wt_viewn - 1;

	rec_wt_vblk0 = i;

	tokenize(bufstr_get(rec_wt_view, i));
	tk = stof(argv(WT_V_TICKS));

	/*
	  A record ENDS the block rather than being skipped inside it, so the range
	  the caller indexes into is contiguous samples and nothing else.  The cost
	  is a shorter block on the one frame a ghost edge falls in -- a marginally
	  coarser sub-tick angle pick, once per toggle -- which is the cheap side of
	  this trade by a wide margin.
	*/
	for (j = i + 1; j < rec_wt_viewn; j = j + 1)
	{
		if (!Watch_IsSample(bufstr_get(rec_wt_view, j)))
			break;
		tokenize(bufstr_get(rec_wt_view, j));
		if (stof(argv(WT_V_TICKS)) != tk)
			break;
	}
	rec_wt_vblk1 = j;
	rec_wt_vti   = ti;
};

/*
  Rebuild the split list for a playback position.

  Wholesale rather than incrementally, because a scrub can move the clock in
  either direction by any amount and an edge detector run backwards would push a
  row for every stage the run had not reached yet.  Each row's speed and energy
  come from the .rec at THAT ROW'S OWN tick, which is why Timer_SplitsPushAt
  exists -- sampling them here would stamp twelve rows with the speed at the
  seek target.
*/
void(float ntick) Watch_Splits =
{
	local float i, save_r, save_n, sp, en, gravity, fin;
	local vector o, v;

	// Nothing to do on the common case: playing forward with no new event.
	// The finish row is tracked separately because it is not one of them -- the
	// clock passing the end changes nothing about the event count, so testing
	// that alone would mean the finish row could never appear.
	i = 0;
	for (; i < rec_wt_evn; i = i + 1)
		if (rec_wt_evtick[i] > ntick)
			break;

	fin = FALSE;
	if (rec_wt_endticks > 0)
	if (ntick >= rec_wt_endticks)
		fin = TRUE;

	if (i == rec_wt_evshown)
	if (fin == rec_wt_evfin)
		return;

	save_r = rec_wt_rcur;
	save_n = rec_wt_rnext;

	gravity = serverkeyfloat("sv_gravity");
	if (gravity < 1) gravity = 800;

	Timer_SplitsClear();
	rec_wt_evshown = i;
	rec_wt_evfin   = fin;

	for (i = 0; i < rec_wt_evshown; i = i + 1)
	{
		Watch_RecSeek(rec_wt_evtick[i] * rec_wt_tickrate);
		if (rec_wt_rcur < rec_wt_rec0)
			continue;

		tokenize(bufstr_get(rec_wt_rec, rec_wt_rcur));
		o_x = stof(argv(WT_C_ORG + 0));
		o_y = stof(argv(WT_C_ORG + 1));
		o_z = stof(argv(WT_C_ORG + 2));
		v_x = stof(argv(WT_C_VEL + 0));
		v_y = stof(argv(WT_C_VEL + 1));
		v_z = stof(argv(WT_C_VEL + 2));

		sp = vlen([v_x, v_y, 0]);

		/*
		  BUILD 39: RELATIVE, like the live path, because it is the same column.

		  HUD_SplitSample pushes Strafe_Energy(...) - HUD_EnergyRef() and this
		  pushed the raw absolute, into rows Timer_SplitsPushAt shares between
		  them.  Same list, same label, two different quantities -- a replay's
		  split energies were larger than the live ones by the whole height of
		  the anchor, which on a descending map is most of the map.

		  WHAT THIS APPROXIMATES, said out loud.  Watch_Splits rebuilds the whole
		  list at the CURRENT playback position, so every row gets the reference
		  in force now rather than the one in force at its own tick.  At
		  hud_energy_ref 0 the anchor is the leg's start zone and that is exact
		  for a whole leg.  At 1 it is the last jump and it is not, and the
		  honest reading of the column becomes "energy above the reference you
		  are looking at".  Replaying the anchor machine forward to each row's
		  tick means a second driver for HUD_UpdateJumpRef, which is more
		  machinery than this bug is worth.
		*/
		en = Strafe_Energy(o, v, gravity) - HUD_EnergyRef();

		// Zero delta: the archive holds one PB per leg and no per-split table,
		// so there is nothing on disk to compare a replayed split against.  A
		// row with no delta draws its own time, which is the honest answer.
		Timer_SplitsPushAt(rec_wt_evkind[i], rec_wt_evseg[i],
		                   rec_wt_evtick[i], 0, sp, en);
	}

	// The finish row, once the clock is past the end.
	if (fin)
	{
		Watch_RecSeek(rec_wt_t1);
		if (rec_wt_rcur >= rec_wt_rec0)
		{
			tokenize(bufstr_get(rec_wt_rec, rec_wt_rcur));
			o_x = stof(argv(WT_C_ORG + 0));
			o_y = stof(argv(WT_C_ORG + 1));
			o_z = stof(argv(WT_C_ORG + 2));
			v_x = stof(argv(WT_C_VEL + 0));
			v_y = stof(argv(WT_C_VEL + 1));
			v_z = stof(argv(WT_C_VEL + 2));
			Timer_SplitsPushAt(SPK_FINISH, -1, rec_wt_endticks, 0,
			                   vlen([v_x, v_y, 0]),
			                   // Build 39: relative, like every other row -- see above.
			                   Strafe_Energy(o, v, gravity) - HUD_EnergyRef());
		}
	}

	rec_wt_rcur  = save_r;
	rec_wt_rnext = save_n;
};

/*
===========================================================================
  The segment column and the board readout

  Everything here is a TABLE LOOKUP at draw time.  The work happened once, in
  Watch_BuildSeq, for the reason the file header gives: the machine that produces
  these rows is an accumulator and a scrub runs its clock backwards.
===========================================================================
*/

/*
  Called from inside Seq_Push during the build pass -- see the hook there.

  `merged` means Seq_Push rewrote the last row rather than appending one, which
  from outside is indistinguishable from a scroll (seq_n moves for neither).  The
  history mirrors that by stepping back one and rewriting, so a merged ramp is
  one entry here exactly as it is one row there.
*/
void(float merged) Watch_SeqRow =
{
	local float p;

	if (seq_n < 1)
		return;
	p = seq_n - 1;

	if (merged)
	if (rec_wt_sqn > 0)
		rec_wt_sqn = rec_wt_sqn - 1;

	if (rec_wt_sqn >= WT_SQMAX)
		return;

	rec_wt_sqkind[rec_wt_sqn] = seq_kind[p];
	rec_wt_sqgain[rec_wt_sqn] = seq_gain[p];
	rec_wt_sqde  [rec_wt_sqn] = seq_de[p];
	rec_wt_sqemax[rec_wt_sqn] = seq_emax[p];
	rec_wt_sqdur [rec_wt_sqn] = seq_dur[p];
	rec_wt_sqpct [rec_wt_sqn] = seq_pct[p];
	rec_wt_sqlau [rec_wt_sqn] = seq_launch[p];
	rec_wt_sqtick[rec_wt_sqn] = rec_wt_sqbuildtick;
	rec_wt_sqn = rec_wt_sqn + 1;
};

// Put the player's own column somewhere safe, and give it back.  Its own arrays
// rather than seq_mk_*; see the declaration for why that is not tidiness.
void() Watch_SeqSave =
{
	local float i;

	if (rec_wt_svheld)
		return;                     // already out; a second replay must not eat it

	rec_wt_svn         = seq_n;
	rec_wt_svhaslaunch = seq_haslaunch;
	for (i = 0; i < seq_n; i = i + 1)
	{
		rec_wt_svkind[i] = seq_kind[i];
		rec_wt_svgain[i] = seq_gain[i];
		rec_wt_svde  [i] = seq_de[i];
		rec_wt_svemax[i] = seq_emax[i];
		rec_wt_svdur [i] = seq_dur[i];
		rec_wt_svpct [i] = seq_pct[i];
		rec_wt_svlau [i] = seq_launch[i];
	}
	rec_wt_svheld = TRUE;
};

void() Watch_SeqRestore =
{
	local float i;

	if (!rec_wt_svheld)
		return;
	rec_wt_svheld = FALSE;

	seq_n         = rec_wt_svn;
	seq_haslaunch = rec_wt_svhaslaunch;
	seq_fadeat    = 0;
	for (i = 0; i < rec_wt_svn; i = i + 1)
	{
		seq_kind[i]   = rec_wt_svkind[i];
		seq_gain[i]   = rec_wt_svgain[i];
		seq_de[i]     = rec_wt_svde[i];
		seq_emax[i]   = rec_wt_svemax[i];
		seq_dur[i]    = rec_wt_svdur[i];
		seq_pct[i]    = rec_wt_svpct[i];
		seq_launch[i] = rec_wt_svlau[i];
	}

	/*
	  Consumed, exactly as Seq_Unmark consumes it and for the same reason: the
	  player's timer has been running the whole time the replay was up, so the
	  next Seq_Frame would see a state change it never saw the start of and read
	  it as a new run -- taking the list we just restored straight back off.
	*/
	seq_laststate = getstatf(STAT_FS_TIMERSTATE);

	// The open segment belongs to a machine that has not run for however long the
	// replay was up, and its e0 was measured before it.  Same call a save-load
	// makes, for the same reason.
	Board_Warped();
};

/*
  Run the REAL segment machine over the file, once.

  Not a second copy of Board_Frame -- that is the thing that rots, and this
  project has said so about the HUD twice already.  The overrides in cl_board.qc
  exist so that one implementation can be fed from two places.

  WALKED LINEARLY rather than through the coarse index, because a `board` record
  is written immediately BEFORE the sample of the tick it happened on and the
  machine needs them in that order.  The file is already in memory; this is one
  tokenize per line and about six thousand of them on an eighty-second run.

  Only for v4.  A v3 file has no ramp contact to feed it, and running the machine
  on `riding = 0` would produce a column of pure air rows -- confidently wrong,
  which is worse than the empty column build 23 shipped.
*/
void() Watch_BuildSeq =
{
	local float i, fl, n;
	local vector org, vel;
	local string s;

	rec_wt_sqn      = 0;
	rec_wt_sqshown  = -1;
	rec_wt_bdshown  = -2;            // -1 is "before the first board", a real state

	if (!rec_wt_v4 || rec_wt_rec < 1)
		return;

	Watch_SeqSave();

	rec_wt_build   = TRUE;
	board_ov_seq  = 0;
	board_ov_bnorm = board_ov_bvel = '0 0 0';
	board_ov_now  = rec_wt_t0;
	board_now     = rec_wt_t0;

	// Board_ResetRun and NOT Board_Clear: the latter also invalidates the
	// save-lock snapshot, which belongs to the player's own save and has nothing
	// to do with the file being read.  See the split in cl_board.qc.
	Board_ResetRun();

	for (i = rec_wt_rec0; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);

		if (!Watch_IsSample(s))
		{
			if (substring(s, 0, 6) == "board ")
			{
				n = tokenize(s);
				if (n >= 9)
				{
					board_ov_seq   = stof(argv(2));
					board_ov_bnorm = [stof(argv(3)), stof(argv(4)), stof(argv(5))];
					board_ov_bvel  = [stof(argv(6)), stof(argv(7)), stof(argv(8))];
				}
			}
			continue;
		}

		tokenize(s);
		board_ov_now    = stof(argv(WT_C_T));
		fl              = stof(argv(WT_C_FLAGS));
		board_ov_riding = (fl & WT_F_RAMP) ? TRUE : FALSE;

		org = [stof(argv(WT_C_ORG + 0)), stof(argv(WT_C_ORG + 1)),
		       stof(argv(WT_C_ORG + 2))];
		vel = [stof(argv(WT_C_VEL + 0)), stof(argv(WT_C_VEL + 1)),
		       stof(argv(WT_C_VEL + 2))];

		// The tick a row pushed on this sample belongs to.  Below zero it is
		// padding, which the clock has not started for; clamped so the whole
		// approach reads as tick 0 rather than as negative ticks the split list
		// and the scrub bar would have to special-case.
		rec_wt_sqbuildtick = floor(board_ov_now / rec_wt_tickrate);
		if (rec_wt_sqbuildtick < 0)
			rec_wt_sqbuildtick = 0;

		Board_Frame(org, vel, (fl & WT_F_ONGROUND) ? TRUE : FALSE);
	}

	rec_wt_build = FALSE;

	/*
	  BUILD 25: how many ramp-contact gaps the hold bridged over this whole file.

	  Captured HERE rather than read live, because ramp_bridged goes on being
	  written by the player's own frames the moment the pass ends.  This is the
	  file's number and it has to stay the file's number.

	  It is also the only headless evidence that Board_RampHold does anything at
	  all: two files that differ only in whether the ramp bit drops out produce
	  the SAME column either way -- with the hold because the ride is never split,
	  without it because every fragment falls under SEG_MINTIME and the carry and
	  the merge reassemble it.  Same rows, opposite reasons.  This number is what
	  separates them.
	*/
	rec_wt_bridged = ramp_bridged;

	// The build left the ring holding the END of the run.  The draw path fills it
	// from the history for whatever tick the clock is on, so leave it empty
	// rather than showing the finish before the replay has started.
	Seq_Clear();

	if (rec_wt_bdover > 0)
		print(sprintf("^3replay: %g board record(s) past the %g cap were dropped; "
		              "the segment column ends early\n", rec_wt_bdover, WT_BDMAX));
};

/*
  The column, as of `ticks`.  A rebuild rather than a nudge, which is what makes
  a backwards scrub free -- and the same shape Watch_Splits already has.

  rec_wt_sqshown is the guard: at 300 fps the tick changes every fifth frame, and
  refilling seven arrays on the other four would be work for no change.
*/
void(float ticks) Watch_SeqApply =
{
	local float i, n, first, p;

	if (!rec_wt_v4)
		return;

	n = 0;
	for (i = 0; i < rec_wt_sqn; i = i + 1)
	{
		if (rec_wt_sqtick[i] > ticks)
			break;
		n = i + 1;
	}

	if (n == rec_wt_sqshown)
		return;
	rec_wt_sqshown = n;

	// The ring shows the last SEQ_MAX, which is what it would have been showing
	// at this point in the run.
	first = n - SEQ_MAX;
	if (first < 0)
		first = 0;

	seq_n         = n - first;
	seq_haslaunch = FALSE;
	seq_fadeat    = 0;

	for (i = 0; i < seq_n; i = i + 1)
	{
		p = first + i;
		seq_kind[i]   = rec_wt_sqkind[p];
		seq_gain[i]   = rec_wt_sqgain[p];
		seq_de[i]     = rec_wt_sqde[p];
		seq_emax[i]   = rec_wt_sqemax[p];
		seq_dur[i]    = rec_wt_sqdur[p];
		seq_pct[i]    = rec_wt_sqpct[p];
		seq_launch[i] = rec_wt_sqlau[p];
		if (seq_launch[i])
			seq_haslaunch = TRUE;
	}

	/*
	  The one-line gain readout under the strafe bar is the newest row, and it is
	  set here rather than replayed from Board_SegmentEnd for the same reason the
	  column is: it is the last thing that FINISHED, and after a backwards scrub
	  that is a different row.  gain_time is in the .rec's own clock, which is
	  what Board_Alpha now fades against.
	*/
	if (n > 0)
	{
		p = n - 1;
		gain_kind  = rec_wt_sqkind[p];
		gain_speed = rec_wt_sqgain[p];
		gain_de    = rec_wt_sqde[p];
		gain_dur   = rec_wt_sqdur[p];
		gain_time  = rec_wt_sqtick[p] * rec_wt_tickrate;
	}
	else
	{
		gain_kind = SEG_NONE;
		gain_time = 0;
	}

	/*
	  BUILD 34: no live row in a replay.

	  Board_Frame does not run during playback -- HUD_Draw gates it on !rec_wt_on --
	  so seg_live_* would otherwise still hold whatever segment the player happened
	  to be riding when they opened the replay, and the column would draw a
	  provisional pair under a run that is not theirs and is not moving.

	  The scrubbed column is the ring and only the ring, which is also what makes
	  it match the column that was watched live: every row in it is a row that
	  Board_SegmentEnd committed.
	*/
	seg_live_kind = 0;
	seg_live_de   = 0;
	seg_live_dur  = 0;
};

/*
  The board readout, as of the playback clock.

  Board_Compute is a pure function of the plane and the pre-clip velocity -- it
  writes the board_* globals and reads nothing else -- so running it on the newest
  event at or before the clock reproduces the panel exactly, including on a
  backwards scrub, which simply lands on an earlier event.
*/
void() Watch_BoardApply =
{
	local float i, k;

	if (!rec_wt_v4)
		return;

	k = -1;
	for (i = 0; i < rec_wt_bdn_n; i = i + 1)
	{
		if (rec_wt_bdt[i] > rec_wt_time)
			break;
		k = i;
	}

	if (k == rec_wt_bdshown)
		return;
	rec_wt_bdshown = k;

	if (k < 0)
	{
		board_time = 0;             // nothing has been boarded yet; the row is blank
		leave_time = 0;
		return;
	}

	// board_now is the stamp Board_Compute takes board_time from, and the draw
	// path has already set it to the playback clock.  Set explicitly here so the
	// board is stamped with the moment it HAPPENED rather than with now.
	board_now = rec_wt_bdt[k];
	Board_Compute(rec_wt_bdv[k], rec_wt_bdn[k]);
	board_now = rec_wt_time;

	// `leaving` has no record of its own -- it is the falling edge of ramp
	// contact, which the sample stream carries -- and reproducing it would want a
	// second table for one row.  Left blank rather than stale: a leave speed from
	// somewhere else in the run is a wrong number in a slot that keeps its place.
	leave_time = 0;
};

void(float t) Watch_Seek =
{
	if (t < rec_wt_t0) t = rec_wt_t0;
	if (t > rec_wt_t1) t = rec_wt_t1;
	rec_wt_time = t;

	// A seek can go either way, so both cursors are invalidated rather than
	// nudged.  Watch_RecSeek notices it is ahead of the target and restarts from
	// the index; the view block is cleared so the next pick recomputes it.
	rec_wt_vblk0 = rec_wt_vblk1 = 0;
	rec_wt_vti   = -1;
	rec_wt_evshown = -1;             // force Watch_Splits to rebuild
	rec_wt_evfin   = -1;
	rec_wt_sqshown = -1;             // and the segment column with it
	rec_wt_bdshown = -2;
};

/*
  Fill the override block for this frame.

  The position is interpolated between two ticks, exactly as the engine's own
  prediction does, and BY TIMESTAMP rather than by index -- the recorder's own
  comment measures real sample rates of 65, 64.6 and 43.5/s against a nominal
  66.67, because a sample is written per received packet and a packet can carry
  several usercmds.  Stepping by index would play those stretches at the wrong
  speed.

  The angles are NOT interpolated, and that is deliberate.  The .view carries one
  line per rendered frame, so at the rate it was recorded the steps are already
  finer than the display; and yaw wraps at +-180, where a naive lerp spins the
  camera the long way round through a whole revolution.  Picking the right line
  is both simpler and correct.
*/
void() Watch_Sample =
{
	local float t, tick, frac, k, i, fl, kb;
	local vector a, b, va, vb, mv, fwd, rgt;
	local float ta, tb;
	local float sidecar;

	Watch_RecSeek(rec_wt_time);
	if (rec_wt_rcur < rec_wt_rec0)
		return;

	tokenize(bufstr_get(rec_wt_rec, rec_wt_rcur));
	ta  = stof(argv(WT_C_T));
	a_x = stof(argv(WT_C_ORG + 0));
	a_y = stof(argv(WT_C_ORG + 1));
	a_z = stof(argv(WT_C_ORG + 2));
	va_x = stof(argv(WT_C_VEL + 0));
	va_y = stof(argv(WT_C_VEL + 1));
	va_z = stof(argv(WT_C_VEL + 2));
	fl  = stof(argv(WT_C_FLAGS));

	frac = 0;
	if (rec_wt_rnext >= rec_wt_rec0)
	{
		tokenize(bufstr_get(rec_wt_rec, rec_wt_rnext));
		tb  = stof(argv(WT_C_T));
		b_x = stof(argv(WT_C_ORG + 0));
		b_y = stof(argv(WT_C_ORG + 1));
		b_z = stof(argv(WT_C_ORG + 2));
		vb_x = stof(argv(WT_C_VEL + 0));
		vb_y = stof(argv(WT_C_VEL + 1));
		vb_z = stof(argv(WT_C_VEL + 2));

		if (tb > ta)
		{
			frac = (rec_wt_time - ta) / (tb - ta);
			if (frac < 0) frac = 0;
			if (frac > 1) frac = 1;
		}
		a  = a  + (b  - a)  * frac;
		va = va + (vb - va) * frac;
	}

	rec_wt_org      = a;
	rec_wt_vel      = va;
	rec_wt_onground = (fl & WT_F_ONGROUND) ? TRUE : FALSE;
	rec_wt_ducked   = (fl & WT_F_DUCKED)   ? TRUE : FALSE;

	/*
	  v4: the plane, the ramp contact and the wishdir.

	  THE PLANE IS NOT INTERPOLATED between the two bracketing samples, and the
	  reason is the same one the angles are not: it is a direction, and a lerp of
	  two unit vectors is neither a unit vector nor on the shorter arc.  Down a
	  curved ramp the normal turns by a fraction of a degree per tick and the
	  nearest one is right to well inside what the bar can show; at a ramp edge it
	  changes discontinuously, and a blend across that would draw a target for a
	  plane that was never there.

	  The wishdir is rebuilt the way AirMove builds it -- the recorded usercmd's
	  forward and side signs against the recorded yaw -- rather than taken from
	  input_movevalues, which CSQC_Input_Frame zeroes while a replay is up
	  precisely so the frozen player cannot be nudged.  It is finished below,
	  after the .view has supplied the yaw.
	*/
	if (rec_wt_v4)
	{
		// Re-tokenize: the interpolation above left argv() holding rnext, and
		// the plane belongs to the sample the clock is actually ON.
		tokenize(bufstr_get(rec_wt_rec, rec_wt_rcur));
		rec_wt_gnorm = [stof(argv(WT_C_NORM + 0)),
		               stof(argv(WT_C_NORM + 1)),
		               stof(argv(WT_C_NORM + 2))];
		rec_wt_rc    = (fl & WT_F_RAMP) ? TRUE : FALSE;
		mv_x = stof(argv(WT_C_MOVE + 0));
		mv_y = stof(argv(WT_C_MOVE + 1));
	}
	else
	{
		rec_wt_gnorm = '0 0 1';
		rec_wt_rc    = FALSE;
		mv = '0 0 0';
	}

	/*
	  ---- the angles and the keys ------------------------------------------

	  BUILD 43 -- THE APPROACH HAD NO ANGLES, AND THE FILE ALWAYS DID.

	  The report: "demos don't have the starting viewangles before they leave
	  the start zone, the angle is looking at the direction of the demo when it
	  leaves the start zone, and then viewangles play back correctly."

	  Exactly right, and the mechanism is the two lines below.  `tick` is
	  clamped at 0 for the whole negative-t approach, so Watch_ViewBlock(0) finds
	  the block of frames at run tick 0 -- the FIRST recorded frame -- and the
	  sub-tick pick lands on its first line every frame, because the fraction of
	  a clamped tick is always zero.  So the camera holds the angle the run
	  started at, right up until the clock reaches 0 and the sidecar takes over.
	  rec_wt_keys was stuck the same way.

	  THE SIDECAR GENUINELY HAS NO COVERAGE THERE and cannot be made to without
	  a format change: it opens on the TF_RECORDING edge, which IS leaving the
	  start zone, and its join key -- STAT_FS_TIMERTICKS -- reads 0 or, after a
	  stopped attempt, the PREVIOUS run's finish tick while armed.  A sidecar
	  opened earlier would carry a run clock that goes backwards, which is a
	  fault reccheck.py already refuses.

	  BUT THE .rec HAS COVERED IT SINCE BUILD 18.  SV_RecPad stores v_angle_x
	  and v_angle_y into the pre-start ring every tick (sv_timer.qc:1632-1633),
	  and SV_RecOpen flushes the ring in with negative timestamps.  The 129
	  padding rows of the surf_fiellu run are a coherent two seconds of
	  pre-strafing left with the pitch easing down -- real angles, not a spawn
	  default.  So the fix is to take the fallback branch that already exists for
	  a file with NO sidecar, and take it for the part of a file the sidecar does
	  not reach.  No writer change, no format change, and it repairs every
	  recording already on disk.

	  WHAT IT COSTS, and it is worth stating rather than discovering: across the
	  approach the camera is tick-rate rather than frame-rate, and the key
	  display is the .rec's coarser mask with no +left/+right and no FSI_PSREL.
	  That is already the accepted trade for a whole file without a sidecar
	  (:1565-1566), and during the approach you are walking or standing.
	*/
	tick = rec_wt_time / rec_wt_tickrate;
	if (tick < 0)
		tick = 0;

	rec_wt_keys  = 0;
	rec_wt_psrel = FALSE;

	// The sidecar covers this frame only if there IS one and the run clock has
	// started.  Both halves, in one place, so the branch below reads as the one
	// question it is.
	sidecar = (rec_wt_view >= 1 && rec_wt_time >= 0);

	if (sidecar)
	{
		Watch_ViewBlock(floor(tick));

		k = rec_wt_vblk1 - rec_wt_vblk0;
		if (k < 1)
			k = 1;

		// Where inside the tick we are, mapped onto the frames that tick held.
		i = rec_wt_vblk0 + floor((tick - floor(tick)) * k);
		if (i >= rec_wt_vblk1) i = rec_wt_vblk1 - 1;
		if (i < rec_wt_view0)  i = rec_wt_view0;

		if (i < rec_wt_viewn)
		{
			tokenize(bufstr_get(rec_wt_view, i));
			rec_wt_pitch = stof(argv(WT_V_PITCH));
			rec_wt_yaw   = stof(argv(WT_V_YAW));
			kb = stof(argv(WT_V_KEYS));
			rec_wt_keys  = kb;
			rec_wt_psrel = (kb & FSI_PSREL) ? TRUE : FALSE;
		}
	}
	else
	{
		// No sidecar, or before the run clock started: the .rec's own angle
		// columns are tick-rate and lack +left/+right entirely, but they are
		// better than a fixed camera.
		tokenize(bufstr_get(rec_wt_rec, rec_wt_rcur));
		rec_wt_pitch = stof(argv(WT_C_PITCH));
		rec_wt_yaw   = stof(argv(WT_C_YAW));
		rec_wt_keys  = stof(argv(WT_C_KEYS));

		/*
		  WRAPPED TO (-180, 180], and only on this branch.

		  The .rec's yaw is e.v_angle_y verbatim, and the engine writes that in
		  whichever range it happens to hold: the FIRST padding sample after a
		  spawn or a teleport is still in 0..360 while every sample after it is
		  in -180..180.  Your surf_fiellu run opens 270.0 then -89.5, which are
		  the same angle written two ways.

		  setproperty does not care, but anything that DIFFERENCES yaw does, and
		  HUD_UpdateTurn differences it every frame -- so without this the first
		  frame of a replay reports a 359.5-degree turn.  One statement, no loop,
		  and it also cleans up the v3-file path that has always taken this
		  branch for its whole length.
		*/
		rec_wt_yaw = rec_wt_yaw - floor((rec_wt_yaw + 180) / 360) * 360;
	}

	/*
	  The wishdir, finished now the yaw is known.

	  Flattened BEFORE normalising, which is what AirMove does and is why looking
	  up a ramp does not change where you accelerate -- HUD_WishDir says the same
	  thing about the live path in the same words.  Built from the .rec's yaw
	  column rather than the .view's, deliberately: the usercmd's forward and side
	  were resolved against the angle the SERVER simulated the tick with, and
	  pairing them with the finer per-frame angle would produce a wishdir the
	  physics never used.
	*/
	rec_wt_wish = '0 0 0';
	if (rec_wt_v4)
	if (mv_x != 0 || mv_y != 0)
	{
		tokenize(bufstr_get(rec_wt_rec, rec_wt_rcur));
		makevectors([0, stof(argv(WT_C_YAW)), 0]);
		fwd = v_forward;  fwd_z = 0;
		rgt = v_right;    rgt_z = 0;
		if (vlen(fwd) > 0.001) fwd = normalize(fwd);
		if (vlen(rgt) > 0.001) rgt = normalize(rgt);
		rec_wt_wish = fwd * mv_x + rgt * mv_y;
		rec_wt_wish_z = 0;
		if (vlen(rec_wt_wish) < 0.001)
			rec_wt_wish = '0 0 0';
		else
			rec_wt_wish = normalize(rec_wt_wish);
	}

	// ---- the clock -------------------------------------------------------
	t = floor(tick);
	if (t < 0) t = 0;
	if (rec_wt_endticks > 0)
	if (t > rec_wt_endticks)
		t = rec_wt_endticks;
	rec_wt_ticks = t;

	if (rec_wt_time < 0)
		rec_wt_state = TS_ARMED;
	else if (rec_wt_endticks > 0 && t >= rec_wt_endticks)
		rec_wt_state = TS_FINISHED;
	else
		rec_wt_state = TS_RUNNING;

	/*
	  The flags the panel may draw.

	  TF_RECORDING and TF_FROZEN are masked out because neither is a fact about
	  the run -- one says a buffer was open and the other says a save-lock was
	  being held at that instant, and both would put a word on the panel that is
	  about the recording rather than about what is on screen.

	  A file with no `flags` key is a pre-build-24 recording, and rather than
	  invent an answer the tag is used: a personal best cannot be a practice run,
	  and a shadow run is one by definition.  Anything else reads clean-unknown.
	*/
	// BUILD 44: the two class bits join the mask.  They are facts about the run
	// exactly as TF_PRACTICE is -- the panel's `format` row and the timer's
	// sub-label both read this word through FS_RunClass, and a bit masked out
	// here would silently demote a cheated replay to `stitched`.
	if (rec_wt_recflags >= 0)
		rec_wt_flags = rec_wt_recflags &
		              (TF_PRACTICE | TF_SHADOW | TF_SEGMENT | TF_CHEAT);
	else if (rec_wt_tag == RT_SHADOW)
		rec_wt_flags = TF_PRACTICE | TF_SHADOW;
	else if (rec_wt_tag == RT_CHEAT)
		// Unreachable today -- nothing writes this name without also writing a
		// v4 header -- and kept in step with cl_scores.qc's identical fallback
		// so the panel and the board cannot disagree about one file.
		rec_wt_flags = TF_PRACTICE | TF_CHEAT;
	else
		rec_wt_flags = 0;

	rec_wt_pb   = 0;
	rec_wt_seg  = rec_wt_startseg;
	for (i = 0; i < rec_wt_evn; i = i + 1)
		if (rec_wt_evkind[i] == SPK_STAGE)
		if (rec_wt_evtick[i] <= rec_wt_ticks)
			rec_wt_seg = rec_wt_evseg[i];

	Watch_Splits(rec_wt_ticks);
	Watch_SeqApply(rec_wt_ticks);
	Watch_BoardApply();
};

/*
  The path, as world-space lines.

  Zone_Line is the primitive the zone markers have used since build 9, and it is
  called from the same place for the same reason: R_BeginPolygon queues into the
  scene and the default shader is depth-tested, so a path behind a wall is
  correctly hidden by the wall.  Drawn before renderscene, never after.

  The part already played is drawn bright and the part ahead dim, so the line
  reads as a position rather than as decoration.
*/
/*
===========================================================================
  THE STRIP, AND WHY IT IS ONE STRIP AND NOT A ROW OF QUADS.

  Zone_Line is a two-vertex R_BeginPolygon, which the driver draws as GL_LINES at
  whatever width it feels like -- and every modern GL driver clamps that to one
  pixel.  A one-pixel line at 0.22 alpha over a lit surf map is not visible from
  the seat, which was half of "the paths are quite thin and faint".

  The other half was the fix for it.  The first cut drew a camera-facing quad per
  segment and took the width from THAT SEGMENT'S midpoint distance -- so two
  adjacent quads had two different widths, did not share an edge, and did not
  even share a facing plane.  The result is a staircase of mismatched
  parallelograms with a notch at every joint, which is what a slug looks like.

  A ribbon has to be a STRIP: every vertex computed once, and both quads that
  touch it built from the same vertex.  Three things follow, and all three are
  what stops it looking segmented:

  MITRED SIDES.  The side vector at a vertex is perpendicular to the AVERAGE of
  the directions coming in and going out, not to either one of them.  That is
  what makes the outer edge continuous around a bend instead of stepping.

  PER-VERTEX WIDTH.  Distance is measured at the vertex, so the taper is smooth
  along the ribbon rather than constant-per-segment.  Scaling with distance at
  all is deliberate and is the opposite choice from Zone_Quad's: a zone box is
  geometry and reading its true size is the point, while a path is an ANNOTATION
  and wants the same thickness on screen wherever it is.  hud_watch_path_scale 0
  turns it off for a constant world width.

  PER-VERTEX COLOUR AND ALPHA.  R_PolygonVertex takes both per vertex, so the
  speed gradient and the played/ahead split are interpolated across each quad by
  the rasteriser instead of changing in steps.  The playhead becomes a soft edge
  that slides along the line rather than a segment that pops.
===========================================================================
*/

/*
  The side offset at one vertex: half the width, perpendicular to both the
  averaged direction and the line of sight.

  `prev` and `next` are the neighbouring points; either may equal `p` at the
  ends, and the average then degenerates to the one real direction, which is the
  correct answer for an endpoint.
*/
vector(vector prev, vector p, vector next, vector eye, float wid) Watch_Side =
{
	local vector din, dout, dir, look;

	din  = p - prev;
	dout = next - p;

	if (din  != '0 0 0') din  = normalize(din);
	if (dout != '0 0 0') dout = normalize(dout);

	dir = din + dout;
	if (dir == '0 0 0')
		dir = (dout != '0 0 0') ? dout : din;
	if (dir == '0 0 0')
		return '0 0 0';
	dir = normalize(dir);

	look = p - eye;
	if (look == '0 0 0')
		return '0 0 0';

	return normalize(crossproduct(dir, normalize(look))) * (wid * 0.5);
};

/*
  The width at one vertex.

  Scaled so a ribbon at 512 units is exactly hud_watch_path_width wide, which
  makes it a fixed ANGULAR size -- the line a thousand units ahead reads the same
  as the one under your feet.  Clamped at both ends: the floor keeps it visible
  when the camera is almost on top of the path (which it is, constantly -- the
  camera rides this line), and the ceiling stops a distant stretch becoming a
  wall across the view.
*/
float(vector p, vector eye, float base, float scaled) Watch_Wid =
{
	local float w;

	if (!scaled)
		return base;

	w = base * (vlen(p - eye) / 512);
	if (w < base * 0.35) w = base * 0.35;
	if (w > base * 6)    w = base * 6;
	return w;
};

// Blue slow, cyan through green, hot at the top -- the speedometer's own sense
// of direction, so the two agree at a glance.
vector(float speed) Watch_SpeedColor =
{
	local float sp;
	sp = speed / 1500;
	if (sp > 1) sp = 1;
	if (sp < 0) sp = 0;
	return '0.25 0.45 1.00' + (sp * '0.60 0.45 -0.85');
};

/*
===========================================================================
  WHICH DRAWER.  Build 43.

  "Make demolines 2d lines, they look so much better then the wavy slug like
   lines we have now.  I had a 3d world matrix to screenspace ones that looks
   pretty good as a injectable on momentum mod, can we have something similar
   that's low effect / low cpu expense if we need to print hundreads of runs at
   once?"

    0   off
    1   the world-space ribbon.  Build 26's, unchanged, depth-tested.
    2   screen-space.  DEFAULT from build 45.

  ---- WHY MODE 2 DREW NOTHING FOR TWO BUILDS ------------------------------

  It was wound backwards, and every quad was backface-culled.

  Build 43 established, correctly and by measurement, that project() was stable
  and right, that the drawer ran and emitted 900-1800 quads a frame with a
  screen bbox over the viewport, that a fixed magenta square through the
  IDENTICAL four calls in the IDENTICAL place in the frame rendered, and that
  the path's own quads did not.  Every one of those is still true.  The
  conclusion drawn from them -- "so it is not the primitive, not the call site,
  not the matrices and not the clip; what is left is that the quads are thin and
  that there are eighteen hundred of them" -- is where it went wrong, and the
  error is worth naming because it is not a slip in reasoning.  It is a list of
  differences that was taken to be complete when it was not.  IDENTICAL CALLS
  ARE NOT IDENTICAL ARGUMENTS: the probe's four vertices go round the square one
  way and the path's four go round the quad the other, and nothing about the
  call sites shows it.  Thin-versus-fat and one-versus-many were the two
  differences that were easy to see, so they were the two that got listed.

  The mechanism, and it is entirely ordinary once it is stated.  An untextured
  2D polygon gets shader_draw_fill_trans (pr_csqc.c:1633), whose shader text
  carries no `cull` line (r_2d.c:328-338), and a shader with no cull line
  defaults to SHADER_CULL_FRONT (gl_shader.c:8288) rather than to twosided.  So
  the 2D pass culls, the winding decides which way, and the perpendicular's sign
  decides the winding.  `side = (-dy, dx)` gives one, `(dy, -dx)` the other; the
  quad sits symmetrically about the line either way, which is exactly why the
  sign looks arbitrary and gets picked by coin-flip.

  THE ANSWER WAS ALREADY WRITTEN DOWN IN THIS TREE, in cl_defs.qc's build-40
  note on the R_BeginPolygon flags: "TWOSIDED matters for any closed shape you
  can stand inside -- without it the batch is single-sided and back faces
  disappear."  That note was written about a 3D box and read as being about 3D
  boxes.  It is about any polygon whose winding you have not checked.

  hud_watch_path_probe 4 and 5 keep the finding falsifiable: 4 is the probe
  square wound the path's old way and MUST NOT DRAW; 5 is the same square with
  the cull disabled and must.  `replay status` prints mode, quads, clipped, wild
  and the first coordinate, so none of the rest has to be rediscovered.

  ONE THING FOUND ON THE WAY AND NOT FIXED, because it is not this bug and not
  reachable from here: CSQC_PolyFlush's 2D branch ends with
  `cl_numstrisidx = csqc_poly_origvert` (pr_csqc.c:1619), assigning a VERTEX
  offset to an INDEX counter where every neighbouring line uses origidx.  It is
  harmless whenever the two counters happen to agree -- which is every frame
  whose 2D polygons are the first scene tris of the frame, i.e. all of ours --
  and it corrupts the index array of a following batch when they do not.  It is
  an engine bug in a shared tree; logged, not patched.

  ONE THING MODE 2 GIVES UP EVEN WHEN IT WORKS, said plainly because three
  separate essays in this codebase went out of their way to preserve it: IT
  DRAWS THROUGH WALLS.  Mode 1 queues into the scene before renderscene and the
  default shader is depth-tested, so a path behind a wall is correctly hidden by
  the wall (cl_main.qc's draw-order note, the strip essay below, and
  cl_zones.qc:28-31).  A screen-space line is drawn after the scene and cannot be
  occluded by it without a traceline per point, which would cap the whole thing
  at a few hundred points and foreclose the many-runs case outright.

  BOTH ARE KEPT AND NOTHING IS DELETED, so the two are one cvar apart and an
  A/B is free.  hud_watch_path stays the master on/off switch so existing
  configs and binds keep meaning what they meant.

===========================================================================
*/
float() Watch_PathMode =
{
	local float m;

	// Registered with a default of 2, but a cvar read before its registercvar
	// returns "" -- and "" is 0, which is "off", which would look exactly like
	// the feature having been removed.
	m = cvar("hud_watch_path_mode");
	if (m <= 0)
	if (cvar_string("hud_watch_path_mode") == "")
		m = 2;

	return m;
};

void() Watch_Path =
{
	local float i, wid, ahead, scaled, near;
	local float a0, a1;
	local vector eye, c0, c1, s0, s1, p0, p1;
	local vector pin;

	if (!cvar("hud_watch_path"))
		return;
	if (rec_wt_pn < 2)
		return;

	if (Watch_PathMode() != 1)
	{
		/*
		  Mode 2 draws in the 2D pass, after renderscene -- but it still wants
		  ONE projection taken from here, and this is the only place in the frame
		  that can take it.

		  cs_buildmatricies is lazy: it rebuilds when clearscene or any
		  setproperty sets its flag, and caches otherwise.  renderscene
		  temporarily rewrites r_refdef.vrect for renderscale and portals, so a
		  projection whose FIRST call of the frame happens after renderscene is a
		  projection against a viewport that may not be the one the scene used.
		  Taking one throwaway here, at the same point in the frame the ribbon
		  would have been queued, pins the matrix to the refdef the scene is
		  about to be drawn with.  One matrix multiply, and it removes a class of
		  bug that would have shown up only under vid_framebuffer or a portal.
		*/
		if (Watch_PathMode() == 2)
		{
			/*
			  A FIXED PROBE, not just a pin.  256 units straight ahead of the
			  camera projects to the centre of the screen if the matrices
			  describe the view the scene is drawn with.  Watch_Path2D takes the
			  same probe after renderscene and `replay status` prints both: if
			  they disagree, something between here and there has moved the view
			  out from under the projection, and every path coordinate is being
			  computed against the wrong camera.
			*/
			makevectors(getproperty(VF_ANGLES));
			pin = getproperty(VF_ORIGIN) + v_forward * 256;
			rec_wt_p2pre = project(pin);
		}
		return;
	}

	/*
	  The eye the strip faces, and it is the REPLAY camera rather than the local
	  player -- who is frozen somewhere else entirely.  getproperty(VF_ORIGIN) is
	  right for both, because Watch_Camera has already written it this frame:
	  CSQC_UpdateView runs it before Zone_Draw and this, deliberately, and that
	  ordering is what makes the ribbon face the viewer.
	*/
	eye = getproperty(VF_ORIGIN);

	wid    = cvar("hud_watch_path_width");
	ahead  = cvar("hud_watch_path_ahead");
	scaled = cvar("hud_watch_path_scale");

	/*
	  THE SKIP AT THE CAMERA, and it is not cosmetic.

	  The camera rides this line, so the part of it the playhead is on passes
	  through the eye -- and a camera-facing quad centred on the viewpoint has no
	  facing plane at all (the look vector is zero-length) and would be drawn as a
	  smear across the middle of the screen.  Everything inside this radius is
	  skipped, which also stops the ribbon obscuring the thing you opened the
	  replay to look at.
	*/
	near = 48;

	// Vertex 0 is computed outside the loop and every later vertex is carried
	// forward from the previous iteration, so each is built exactly once and the
	// two quads that share it share it exactly.
	p0 = rec_wt_ppos[0];
	s0 = Watch_Side(p0, p0, rec_wt_ppos[1], eye,
	                Watch_Wid(p0, eye, wid, scaled));
	c0 = Watch_SpeedColor(rec_wt_pspd[0]);
	a0 = (rec_wt_ptick[0] <= rec_wt_ticks) ? 1.0 : 0.5;

	for (i = 0; i < rec_wt_pn - 1; i = i + 1)
	{
		p1 = rec_wt_ppos[i + 1];
		s1 = Watch_Side(rec_wt_ppos[i],
		                p1,
		                (i + 2 < rec_wt_pn) ? rec_wt_ppos[i + 2] : p1,
		                eye, Watch_Wid(p1, eye, wid, scaled));
		c1 = Watch_SpeedColor(rec_wt_pspd[i + 1]);

		/*
		  0.5 for the part ahead, not the 0.22 the first cut used.  It has to be
		  dimmer than the part behind -- that is what makes the line read as a
		  position rather than as decoration -- but it also has to be VISIBLE,
		  and a quarter alpha over a bright ramp is not.  The contrast is carried
		  by the past being fully opaque.
		*/
		a1 = (rec_wt_ptick[i + 1] <= rec_wt_ticks) ? 1.0 : 0.5;

		if (!ahead)
		if (a1 < 1)
		if (a0 < 1)
		{
			p0 = p1;  s0 = s1;  c0 = c1;  a0 = a1;
			continue;
		}

		if (s0 == '0 0 0' || s1 == '0 0 0'
		 || vlen(p0 - eye) < near || vlen(p1 - eye) < near)
		{
			p0 = p1;  s0 = s1;  c0 = c1;  a0 = a1;
			continue;
		}

		/*
		  ONE QUAD, FOUR VERTICES, EACH WITH ITS OWN COLOUR AND ALPHA.  The two
		  on the left edge are this vertex's, the two on the right are the next
		  one's, and the next iteration reuses them verbatim -- so there is no
		  seam to see because there is no seam.

		  Wound as a ring (left, right, right, left) rather than as a triangle
		  strip's zig-zag: R_PolygonVertex builds a fan, and a zig-zag order would
		  fold the quad into a bowtie.
		*/
		R_BeginPolygon("");
		R_PolygonVertex(p0 - s0, '0 0 0', c0, a0);
		R_PolygonVertex(p0 + s0, '0 0 0', c0, a0);
		R_PolygonVertex(p1 + s1, '0 0 0', c1, a1);
		R_PolygonVertex(p1 - s1, '0 0 0', c1, a1);
		R_EndPolygon();

		p0 = p1;  s0 = s1;  c0 = c1;  a0 = a1;
	}
};

/*
===========================================================================
  THE PATH IN SCREEN SPACE.  Build 43, and the default.

  WHY IT IS CHEAPER AS WELL AS BETTER-LOOKING.  The ribbon above costs about
  fifteen builtin calls a segment -- five normalize, one crossproduct, three
  vlen and six draw -- because a world-space quad that must face the camera and
  hold a constant ANGULAR width has to be rebuilt from the eye every frame.
  Project first and all of that goes away: the perpendicular is two negations,
  the width is a literal pixel count, and there is nothing to face.  About eight
  calls a segment, and every one of them cheaper.

  AND MEASURED, build 45, because the paragraph above is an argument and the
  report asked for "low effect / low cpu expense".  cfg/testrun/b45perf.cfg:
  surf_rise, the same paused camera, developer 0, no frame cap, the three modes
  interleaved four times rather than run in three blocks.  Frame times, medians
  of four:

      mode 0  off       4.65 ms
      mode 2  screen    5.21 ms       the drawer costs 0.56 ms
      mode 1  ribbon    7.39 ms       the drawer costs 2.75 ms

  The ribbon is about five times the cost of the line.  Two things keep that
  from being a clean per-segment number and both are worth stating rather than
  rounding off.  The control DRIFTED, 3.63 ms on the first sample to 5.00 ms on
  the last, so the arm-minus-control figures are the shakiest thing on the page;
  what is solid is mode1-minus-mode2 measured inside each round, which came out
  2.48, 1.92, 2.14 and 2.05 ms with no overlap between the arms at all.  And the
  two modes were not asked for the same number of quads: at that camera mode 2
  emitted 926 of the curve's 2021 spans, the rest going to the near clip and the
  guard band, while mode 1's emitted count is not instrumented.  So this is the
  cost of the FEATURE at a representative camera, which is the question, and not
  a normalised cost per segment, which is not.

  `project` (#311) transforms by the same matrix the scene was drawn with and
  returns coordinates in r_refdef.vrect -- which after clearscene is the full
  virtual screen, i.e. the exact space every HUD panel already lays out in.  So
  there is no scaling step and no viewport arithmetic here at all.  Nothing else
  in this codebase had ever called it.

  ---- THE RESCALED-VIEWPORT GUARD, WHICH IS DELIBERATELY NOT HERE -----------

  The plan prescribed one: compare VF_SCREENVSIZE against VF_SIZE and fall back
  to mode 1 if they disagree.  It is not written, for two reasons, and the first
  is that AS STATED IT WOULD FIRE ON A CASE THAT IS ALREADY CORRECT.  project()
  ends with out[0]*r_refdef.vrect.width + r_refdef.vrect.x (pr_csqc.c:2096-2097)
  -- it carries the viewport's OFFSET as well as its size -- so a 3D viewport
  merely smaller than the screen projects correctly and needs no fallback.  A
  guard keyed on "the two sizes differ" would switch drawers on those frames.

  The second is that the real hazard was measurable and was measured.
  cfg/testrun/b45scale.cfg drives r_renderscale, which is the knob that rewrites
  r_refdef.vrect.width to vid.fbvwidth*scale (gl_backend.c:6058-6059) and is
  therefore the one that could put project's output in a different space from
  the 2D pass.  At r_renderscale 2 the frame cost went from 86.6 to 20.0 fps, so
  the arm certainly took effect, and the probe still projected to 960,600 of a
  1920x1200 screen -- exactly half, which is where dead-ahead lands only if the
  two spaces still agree -- with the line unmoved on the geometry.  The pin
  projection taken before renderscene (see Watch_Path, and it predates this) is
  what makes that true.

  ONE ARM OF THAT TEST PROVED NOTHING AND IS NOT BEING COUNTED: vid_conwidth and
  vid_conheight are inert without a vid_restart, and VF_SCREENVSIZE still read
  1920x1200 after they were set, so the "virtual screen fixed independently of
  the physical one" case is UNTESTED rather than passed.  If the line is ever
  reported misplaced, that is the first thing to try and this is the note that
  says so.

  ---- CLIPPING, WHICH IS THE PART THAT IS EASY TO GET WRONG ----------------

  A polyline in screen space MUST be clipped at the near plane, not culled.
  Culling a segment because one end is behind you leaves the line stopping short
  of the screen edge wherever the path passes the camera -- and the camera rides
  this line constantly, so that is not a corner case, it is most frames.

  The clip is one dot product per vertex and no builtin: d = (p - eye) . forward
  is the distance along the view axis, and a segment with one end short of NEAR
  is shortened to the crossing rather than dropped.  Exact for a perspective
  near plane, because the plane is perpendicular to that axis by construction.

  NEAR IS 8 AND THE ENGINE'S IS 4, deliberately.  project() divides by w with no
  zero guard (pr_csqc.c:2075-2077), so a point ON the eye plane returns a NaN
  into QC and a NaN vertex is a polygon smeared across the whole screen.  The
  dot-product clip runs FIRST and keeps every projected point comfortably clear
  of that; the z test below is belt to those braces, not the mechanism.

  ---- AND WHY THERE IS NO MITRE ---------------------------------------------

  The ribbon needs one because its width varies per vertex with distance, so two
  adjacent quads built independently do not share an edge -- that mismatch is
  what "wavy slug like lines" was describing.  In screen space the width is the
  SAME NUMBER at every vertex, so the only artefact left at a joint is the wedge
  on the outside of a turn, whose size is (width/2)*tan(theta/2).  The curve is
  a C1-continuous spline, so theta is small; at the default three pixels the
  wedge is comfortably under one.  If a much thicker line is ever wanted this is
  the first thing that will show, and a per-vertex 2D mitre is the fix -- it is
  left out because it would be code carrying no visible weight today.

  BUILD 45 PUT THAT QUESTION AT 8 PIXELS -- which could not be asked at all
  until the line drew -- and the wedge IS there by then.  b45line's 8px arm is
  smooth along every sweeping curve on surf_rise, and at the one tight elbow in
  frame it shows an obvious notch on the OUTSIDE of the turn, several pixels of
  it, exactly the (width/2)*tan(theta/2) the paragraph above predicts.  The same
  elbow at the default 3 px shows nothing.

  So the threshold is somewhere between 3 and 8, the default is comfortably
  under it, and "a per-vertex 2D mitre is the fix" stops being hypothetical the
  moment anyone raises hud_watch_path_px far.  That is the trigger to write it;
  it is still not worth writing now.

  ---- ON "HUNDREDS OF RUNS AT ONCE", WHICH IS NOT BUILT ---------------------

  The report asked for two things and this drawer answers one of them.  The
  obstacle to the second is NOT the rendering any more; it is that there is no
  multi-run data model at all.  One set of rec_wt_* globals, one rec_wt_on, one
  live strbuf and one cursor -- a second run has nowhere to be.  That is a
  data-model change (a flat point pool with per-run first/count, and no per-run
  strbuf) at least as large as this drawing change was, and doing half of it
  here would leave a drawer that takes N runs and a loader that cannot supply
  them.

  What this build leaves ready, so the next one does not have to rediscover it:

    - the emit is already ONE batch and one draw call for however many quads go
      through it, because consecutive R_BeginPolygon calls sharing a shader and
      flags do not flush between each other.  N runs stay one draw call.
    - draw rec_wt_cpos[] instead of rec_wt_ppos[] and the per-run cost drops by
      about two thirds at a glance you would have to look hard to see: the
      control points are ~750 against the curve's ~2000, and they are already
      chosen where the path actually turns.  That is the first lever and it
      needs no new data.
    - addtrisoup_simple (cl_defs.qc:1451) takes a whole vertex/index soup in ONE
      builtin, against this loop's eight per segment.  That is the second lever,
      and it is worth reaching for only once the pool exists, because it wants
      the points laid out contiguously anyway.

  Watch_Path2D deliberately does not take the arrays as parameters, which the
  plan asked for: QuakeC has no array parameter and no way to pass a global
  array by reference, so "take them as parameters" is not a thing that can be
  written here.  The pool version will index one flat array with an offset,
  which is the same refactor arriving from the other side.
===========================================================================
*/
/*
  What the screen-space drawer did on the last rendered frame, for `replay
  status`.  Three numbers, because when this drew nothing at all there was no
  way to tell "not called" from "called and clipped everything" from "drawn
  off-screen" -- and those want three different fixes.
*/
void() Watch_Path2D =
{
	local float i, wid, ahead, near, t;
	local float d0, d1, a0, a1, len;
	local vector eye, fwd, p0, p1, w0, w1, q0, q1, dir, side, c0, c1;

	rec_wt_p2n    = 0;
	rec_wt_p2clip = 0;
	rec_wt_p2wild = 0;

	if (!cvar("hud_watch_path"))
		return;
	if (Watch_PathMode() != 2)
		return;
	if (rec_wt_pn < 2)
		return;

	/*
	  The replay camera, and the same getproperty the ribbon uses for the same
	  reason: Watch_Camera has already written it this frame.  makevectors here
	  rather than per segment -- it writes three globals and the view does not
	  change between segments.
	*/
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;

	// The other half of the probe; see Watch_Path.  Same point, same frame, one
	// renderscene apart.
	rec_wt_p2post = project(eye + fwd * 256);

	/*
	  AND THE AXES, because a centre-of-screen probe cannot fail.  Any projection
	  matrix, however wrong, sends the point dead ahead of the eye to the middle
	  of the viewport -- so "pre and post both read 960,600" proved the matrix was
	  STABLE and proved nothing whatever about it being RIGHT.

	  These two are off-axis: 256 ahead and 64 to the right must land right of
	  centre and at the same height; 256 ahead and 64 up must land above centre
	  and at the same x.  If either comes back mirrored, swapped, or scaled
	  absurdly, that is the projection and not this drawer.
	*/
	rec_wt_p2axr = project(eye + fwd * 256 + v_right * 64);
	rec_wt_p2axu = project(eye + fwd * 256 + v_up * 64);

	/*
	  A KNOWN-GOOD QUAD, on demand.  hud_watch_path_probe 1 draws one 200x200
	  magenta square at the centre of the screen through EXACTLY the calls the
	  path uses -- same shader, same flags, same 2D mode, same winding.  If the
	  square appears and the path does not, the 2D polygon path works and the
	  fault is in the path's own geometry; if neither appears, the fault is in
	  these four calls or in what flushes them.  That is a distinction no
	  screenshot of a missing line can make, and it is two builds' worth of
	  guessing avoided the next time this happens.
	*/
	/*
	  WHICH 2D PRIMITIVE ACTUALLY DRAWS FROM HERE.  Five probes, all at literal
	  screen coordinates, all magenta, so one run answers the question a missing
	  line cannot:

	    1  R_BeginPolygon(..., TRUE) -- the arbitrary-quad path this drawer wants
	    2  drawline                  -- one draw call per line, no per-vertex colour
	    3  drawfill                  -- axis-aligned only, but known to work
	    4  probe 1 WOUND BACKWARDS   -- the build-43 bug, kept.  MUST NOT DRAW.
	    5  probe 4 plus TWOSIDED     -- the same backwards square, uncullable

	  3 is the control: if even that does not appear, the fault is that nothing
	  drawn from this point in the frame is visible, and the primitive is not the
	  question at all.

	  4 AND 5 ARE THE PAIR THAT DIAGNOSED THIS, and they stay in because the
	  thing they prove is invisible in every other way.  1 and 4 are the same
	  square at the same coordinates through the same four calls, differing only
	  in the order the four vertices are given; 1 draws and 4 does not, which is
	  culling and can be nothing else.  5 is 4 with the cull turned off, and it
	  draws.  If a future change makes 4 appear, this build's shader is no longer
	  single-sided and the winding rule below has stopped mattering -- which is
	  worth knowing and is not otherwise discoverable.
	*/
	t = cvar("hud_watch_path_probe");
	if (t == 1)
	{
		// A literal, not a derived centre: getproperty returns __variant and
		// scaling it implicitly casts to float, which put the square at 0,0 and
		// made a working probe look like a broken one.
		q0 = '400 300 0';
		R_BeginPolygon("", 0, TRUE);
		R_PolygonVertex(q0 + '-100 -100 0', '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 -100 0',  '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 100 0',   '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '-100 100 0',  '0 0 0', '1 0 1', 1);
		R_EndPolygon();
	}
	else if (t == 2)
		drawline(4, '400 300 0', '900 700 0', '1 0 1', 1, 0);
	else if (t == 3)
		drawfill('400 300 0', '200 200 0', '1 0 1', 1, 0);
	else if (t == 4)
	{
		q0 = '400 300 0';
		R_BeginPolygon("", 0, TRUE);
		R_PolygonVertex(q0 + '-100 100 0',  '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 100 0',   '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 -100 0',  '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '-100 -100 0', '0 0 0', '1 0 1', 1);
		R_EndPolygon();
	}
	else if (t == 5)
	{
		q0 = '400 300 0';
		R_BeginPolygon("", DRAWFLAG_TWOSIDED, TRUE);
		R_PolygonVertex(q0 + '-100 100 0',  '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 100 0',   '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 -100 0',  '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '-100 -100 0', '0 0 0', '1 0 1', 1);
		R_EndPolygon();
	}

	// Read once.  At one run the four cvar() calls the ribbon does per frame are
	// noise; the moment this draws more than one run they are not, and the
	// Zone_ReadCvars pattern exists for exactly that.
	wid = cvar("hud_watch_path_px");
	if (wid <= 0)
		wid = 3;
	ahead = cvar("hud_watch_path_ahead");
	near  = 8;

	p0 = rec_wt_ppos[0];
	d0 = (p0 - eye) * fwd;
	c0 = Watch_SpeedColor(rec_wt_pspd[0]);
	a0 = (rec_wt_ptick[0] <= rec_wt_ticks) ? 1.0 : 0.5;

	for (i = 0; i < rec_wt_pn - 1; i = i + 1)
	{
		p1 = rec_wt_ppos[i + 1];
		d1 = (p1 - eye) * fwd;
		c1 = Watch_SpeedColor(rec_wt_pspd[i + 1]);
		a1 = (rec_wt_ptick[i + 1] <= rec_wt_ticks) ? 1.0 : 0.5;

		// The part still ahead of the playhead, if it is not wanted.  Same test
		// and same meaning as the ribbon's.
		if (!ahead)
		if (a1 < 1)
		if (a0 < 1)
		{
			p0 = p1;  d0 = d1;  c0 = c1;  a0 = a1;
			continue;
		}

		w0 = p0;
		w1 = p1;

		if (d0 < near)
		if (d1 < near)
		{
			// Both behind, or both inside the near plane: there is no visible
			// part of this segment to shorten to.
			rec_wt_p2clip = rec_wt_p2clip + 1;
			p0 = p1;  d0 = d1;  c0 = c1;  a0 = a1;
			continue;
		}

		/*
		  One end short: move it to where the segment crosses the plane.  The
		  colour and alpha are NOT interpolated to the crossing -- the clipped
		  stub is a fraction of one already-short spline span, and carrying the
		  endpoint's own values there is invisible against paying for two more
		  lerps on the frames this fires.
		*/
		if (d0 < near)
		{
			t  = (near - d0) / (d1 - d0);
			w0 = p0 + (p1 - p0) * t;
		}
		else if (d1 < near)
		{
			t  = (near - d1) / (d0 - d1);
			w1 = p1 + (p0 - p1) * t;
		}

		q0 = project(w0);
		q1 = project(w1);

		// Belt to the clip's braces: project negates the returned z for a point
		// behind the eye plane, so anything under -1 is behind us or inside the
		// engine's own near plane.  The clip above should have made this
		// unreachable; if it ever fires, the clip is wrong and this stops it
		// becoming a smear across the middle of the screen.
		if (q0_z < -1)
		{
			p0 = p1;  d0 = d1;  c0 = c1;  a0 = a1;
			continue;
		}
		if (q1_z < -1)
		{
			p0 = p1;  d0 = d1;  c0 = c1;  a0 = a1;
			continue;
		}

		/*
		  FLATTEN, and this is not tidiness -- it is the difference between the
		  line drawing and not drawing at all.

		  project() returns the NDC depth in z, which for anything in front of
		  the camera is a number approaching 1.  A 2D polygon's vertices are
		  screen coordinates on a plane, and handing one a z of 0.99 puts it
		  outside the 2D pass's clip volume: the whole path silently disappears
		  while every mode switch and every cvar still reads correct, which is
		  exactly how this was found.  Zero both BEFORE the direction is taken,
		  so the perpendicular is a genuine 2D perpendicular as well.
		*/
		q0_z = 0;
		q1_z = 0;

		/*
		  A GUARD BAND, and it is not belt and braces -- without it the whole
		  batch drew nothing.

		  The near-plane clip is geometrically right and produces, for a segment
		  passing close beside the camera, a stub whose far end is a few units
		  ahead and a thousand units to the side.  That projects honestly to a
		  screen x in the hundreds of thousands, and a quad a hundred thousand
		  pixels wide does not merely draw off-screen: it takes the rest of the
		  2D batch with it, so the visible part of the path vanishes as well.

		  Measured: 1828 quads emitted, bbox -124342..1568, and nothing on
		  screen -- while a fixed magenta square through the identical four calls
		  in the identical place rendered perfectly.  That pair is what says the
		  fault is the coordinates and not the primitive, and it took three
		  builds to ask the question that way round.

		  Dropping the segment rather than clipping it in 2D is the cheap answer
		  and costs almost nothing visible: a segment this extreme is one the
		  camera is practically inside, and the next point along the curve is a
		  few units further on and back inside the band.  A parametric 2D clip
		  would keep that sliver at the very edge of the frame; not worth it.
		*/
		if (q0_x < -WT_P2GUARD || q0_x > WT_P2GUARD
		 || q0_y < -WT_P2GUARD || q0_y > WT_P2GUARD
		 || q1_x < -WT_P2GUARD || q1_x > WT_P2GUARD
		 || q1_y < -WT_P2GUARD || q1_y > WT_P2GUARD)
		{
			rec_wt_p2wild = rec_wt_p2wild + 1;
			p0 = p1;  d0 = d1;  c0 = c1;  a0 = a1;
			continue;
		}

		/*
		  THE 2D PERPENDICULAR, AND ITS SIGN IS THE WHOLE BUG.  Build 45.

		  (dy, -dx) and not (-dy, dx), and the difference between the two is not
		  which side of the line the quad sits on -- it is symmetric about the
		  line either way -- it is the WINDING ORDER of the four vertices that
		  come out of it.  The other sign wound every quad the opposite way round
		  from every other 2D quad in the engine, and single-sided is the default,
		  so the entire path was backface-culled.  See the essay above.
		*/
		dir   = q1 - q0;
		dir_z = 0;
		len   = vlen(dir);
		if (len < 0.001)
		{
			p0 = p1;  d0 = d1;  c0 = c1;  a0 = a1;
			continue;                       // a sub-pixel segment has no direction
		}
		dir  = dir * (1 / len);
		side = [dir_y, 0 - dir_x, 0] * (wid * 0.5);

		/*
		  TRUE for the third argument is 2D mode: the polygon is drawn at
		  EndPolygon rather than queued for renderscene.  Consecutive polygons
		  sharing a shader and flags do NOT flush between them, so the whole path
		  is still one draw call -- which is the property that makes this the
		  shape to extend to many runs later.

		  DRAWFLAG_TWOSIDED, and it is belt to the sign's braces rather than the
		  fix.  The winding above is correct on its own and this flag is not
		  needed to make the line appear; it is here because the sign of a 2D
		  perpendicular is a coin-flip that nothing in the code makes obvious, a
		  future mitre or a multi-run pool could easily emit the other way, and
		  the failure mode when that happens is the feature silently vanishing
		  rather than looking wrong.  With the flag, a sign error is a non-event.
		  Costs one bit in the batch key; the path is its own batch either way.

		  Wound as a ring, not a zig-zag, for the reason the ribbon states:
		  R_PolygonVertex builds a fan and a zig-zag folds the quad into a bowtie.
		*/
		R_BeginPolygon("", DRAWFLAG_TWOSIDED, TRUE);
		R_PolygonVertex(q0 - side, '0 0 0', c0, a0);
		R_PolygonVertex(q0 + side, '0 0 0', c0, a0);
		R_PolygonVertex(q1 + side, '0 0 0', c1, a1);
		R_PolygonVertex(q1 - side, '0 0 0', c1, a1);
		R_EndPolygon();

		/*
		  The screen bbox of what was actually emitted.  This is the number that
		  separates "the geometry is wrong" from "the geometry is right and the
		  batch is not reaching the screen": if the bbox spans the viewport, the
		  quads are where the ribbon's curve is and the fault is downstream.
		*/
		if (rec_wt_p2n == 0)
		{
			rec_wt_p2first = q0;
			rec_wt_p2min   = q0;
			rec_wt_p2max   = q0;
		}
		if (q0_x < rec_wt_p2min_x) rec_wt_p2min_x = q0_x;
		if (q0_y < rec_wt_p2min_y) rec_wt_p2min_y = q0_y;
		if (q0_x > rec_wt_p2max_x) rec_wt_p2max_x = q0_x;
		if (q0_y > rec_wt_p2max_y) rec_wt_p2max_y = q0_y;
		rec_wt_p2n = rec_wt_p2n + 1;

		p0 = p1;  d0 = d1;  c0 = c1;  a0 = a1;
	}
};

void() Watch_Camera =
{
	local float eye;

	// 64 standing, 46 ducked -- Source's VEC_VIEW and VEC_DUCK_VIEW, published
	// to serverinfo by pm_viewheight / pm_duckviewheight.  The mid-duck slide
	// between them is NOT recoverable: the .rec stores the duck STATE and not
	// the eye, so a replay of a crouch transition steps where the original slid.
	// Four frames, once per duck, and inventing a spline would be a guess.
	eye = serverkeyfloat(rec_wt_ducked ? "pm_duckviewheight" : "pm_viewheight");
	if (eye <= 0)
		eye = rec_wt_ducked ? 46 : 64;

	setproperty(VF_ORIGIN, rec_wt_org + [0, 0, eye]);
	setproperty(VF_ANGLES, [rec_wt_pitch, rec_wt_yaw, 0]);

	/*
	  BUILD 43: and TELL THE SERVER, which is the one thing this function used to
	  do that nothing else could and did not do.  Not so the server can move
	  anything -- it still knows nothing about the recording -- but so the
	  entities it decides to send are the ones in front of the camera rather than
	  the ones in front of a body standing where you pressed the key.  Throttled
	  in PVS_Publish; see the essay there and the measurement in sv_saveloc.qc.

	  Here, at the single site the camera origin exists, rather than in
	  Watch_Frame: a seek, a scrub and an ordinary frame all arrive through this
	  function, so there is no path that moves the camera without publishing it.
	*/
	PVS_Publish(rec_wt_org + [0, 0, eye]);
};

void() Watch_Stop =
{
	if (!rec_wt_open)
		return;

	rec_wt_open = FALSE;
	rec_wt_on   = FALSE;
	Watch_Free();
	Timer_SplitsClear();

	// The player's own segment column, back where it was.  Before the print, so
	// that a restore that faults says so with the stop line still to come.
	Watch_SeqRestore();

	/*
	  BUILD 47: ONLY IF NOTHING ELSE STILL WANTS THE CURSOR.

	  This was an unconditional release and it was not carelessness -- it was
	  unwritable.  rec_sb_open lived in cl_scores.qc, which compiles AFTER this
	  file, so the test could not be spelled here at all.  Build 47 moved that
	  declaration up to cl_hud.qc, beside ui_he_open, which is the same thing
	  done for the same reason; see the block there.

	  The sequence it cost is the one Scores_Close calls ordinary: open the
	  board, click a row to watch it, stop the replay -- and the cursor went back
	  to the game underneath a board that was still drawn, with nothing able to
	  press anything on it.  The only way out was to guess that ESC still worked.

	  All three panels now ask the same question at the one place each lets go.

	  BUILD 55: there were FOUR by then, and this site could not test the
	  fourth either.  ui_rs_cursor (the results card) is declared at
	  cl_results.qc:58, which also compiles after this file -- so the same
	  constraint that made rec_sb_open unwritable in build 47 was still hiding
	  the card.  Moving one more declaration up would have worked once more and
	  then broken again on the fifth owner, so the question itself moved
	  instead: see the cursor claim register in cl_hud.qc.
	*/
	UI_CursorRelease(UIC_WATCH);
	localcmd("cmd rec_watch 0\n");
	print("replay: stopped\n");
};

/*
  Open a recording.

  The .view is found by replacing the extension, which is the whole of the
  relationship between the two files -- they are joined by nothing but their
  names, which is exactly why build 23 moved the naming to one function in
  shared/sh_defs.qc.  A missing sidecar is not fatal: the .rec's own angle
  columns are a coarser camera and a partial replay beats a refused one.
*/
float(string path) Watch_Open =
{
	local float buf;
	local string vp;

	Watch_Free();

	if (strstrofs(path, ".rec") < 0)
	{
		print(sprintf("replay: %s is not a .rec\n", path));
		return FALSE;
	}

	buf = buf_create_ex("string", 0);
	if (buf < 1)
	{
		print("replay: buf_create failed\n");
		return FALSE;
	}
	if (!buf_loadfile(path, buf))
	{
		buf_del(buf);
		print(sprintf("replay: cannot read %s\n", path));
		return FALSE;
	}
	rec_wt_rec  = buf;
	rec_wt_recn = buf_getsize(buf);
	rec_wt_path = strzone(path);

	vp = strcat(substring(path, 0, strlen(path) - 4), ".view");
	buf = buf_create_ex("string", 0);
	if (buf >= 1)
	{
		if (buf_loadfile(vp, buf))
		{
			rec_wt_view  = buf;
			rec_wt_viewn = buf_getsize(buf);
		}
		else
		{
			buf_del(buf);
			print(sprintf("replay: no sidecar at %s -- "
			              "angles will be tick-rate and the turn keys are lost\n", vp));
		}
	}

	// The tag, from the name.  Only used as the fallback for a file with no
	// `flags` header key; see Watch_Sample.
	//
	// The archived two match on `_<tag>.rec` because a stamp always precedes
	// them.  `cheat` is unstamped, so its whole basename is the tag and the '/'
	// is what an underscore is for the others -- matching on "cheat.rec" alone
	// would also fire on a leg folder somebody named `cheat`.
	rec_wt_tag = RT_LAST;
	if (strstrofs(path, "_pb.rec") >= 0)     rec_wt_tag = RT_PB;
	if (strstrofs(path, "_shadow.rec") >= 0) rec_wt_tag = RT_SHADOW;
	if (strstrofs(path, "/cheat.rec") >= 0)  rec_wt_tag = RT_CHEAT;

	Watch_Scan();

	if (rec_wt_nsamp < 2)
	{
		print(sprintf("replay: %s holds %g samples -- nothing to play\n",
		              path, rec_wt_nsamp));
		Watch_Free();
		return FALSE;
	}

	if (rec_wt_map != "")
	if (rec_wt_map != serverkey("map"))
		print(sprintf("^3replay: this run is on %s and you are on %s -- "
		              "the camera will fly through nothing\n",
		              rec_wt_map, serverkey("map")));

	rec_wt_segs   = Watch_TrackSegs(rec_wt_track);
	rec_wt_rate   = 1;
	rec_wt_slider = 0.5;
	rec_wt_paused = FALSE;
	rec_wt_rcur   = -1;
	rec_wt_lastreal = cltime;
	rec_wt_open   = TRUE;

	// The two passes that cost anything at load, and between them the reason both
	// a scrub and a frame are cheap: the drawn curve and the segment column are
	// tables by the time anything asks for them.
	Watch_BuildCurve();
	Watch_BuildSeq();

	if (!rec_wt_v4)
		print("^3replay: this recording is FTESURF-REC 3 -- no ramp contact and no "
		      "pre-clip velocity, so the strafe bar, the board panel and the "
		      "segment column stay off.  Runs recorded from build 24 carry them.\n");

	Watch_Seek(rec_wt_t0);

	// Pin the player.  MOVETYPE_NONE maps to PM_NONE, which is what stops the
	// CLIENT predicting as well as the server moving -- build 11's finding.  The
	// input gate in CSQC_Input_Frame covers the round trip until this lands.
	localcmd("cmd rec_watch 1\n");
	// Build 43: so the first Watch_Camera publishes immediately rather than
	// waiting out a throttle window seeded by the last replay this session.
	PVS_Forget();
	UI_CursorClaim(UIC_WATCH);

	print(sprintf("replay: %s  %s  %s  %g samples\n",
	              rec_wt_path, rec_wt_owner,
	              Time_TickString(rec_wt_endticks, rec_wt_tickrate), rec_wt_nsamp));

	// Said once per replay rather than once per session, and only when it is
	// off: the panel is the answer to "what am I actually watching" and there
	// is no other route to knowing it exists.  See the chrome's hint line.
	if (!cvar("hud_watch_info"))
		print("        ^5hud_watch_info 1^7 for the run's frame rate, tick rate, "
		      "sample rate and file details\n");
	return TRUE;
};

/*
===========================================================================
  The chrome
===========================================================================
*/
void(float v) Watch_ScrubTo =
{
	Watch_Seek(rec_wt_t0 + v * (rec_wt_t1 - rec_wt_t0));
};

/*
  The speed slider is 0..1 and 1x is the MIDDLE, which is what was asked for and
  is not what a linear 0.1..4 gives -- that would put 1x at 0.23.  So the two
  halves are separate ranges, 0.1..1 below the centre and 1..4 above it, with a
  dead zone either side of 0.5 so the natural place to let go is exactly 1x.
*/
void(float v) Watch_SetSpeed =
{
	if (v > 0.47)
	if (v < 0.53)
		v = 0.5;

	rec_wt_slider = v;

	if (v <= 0.5)
		rec_wt_rate = 0.1 + (v / 0.5) * 0.9;
	else
		rec_wt_rate = 1 + ((v - 0.5) / 0.5) * 3;
};

// The same setting from the other end: a console `replay speed 2` means two
// times, not slider position 2.  Inverting the two halves keeps the knob and
// the command describing one value rather than two that drift.
void(float r) Watch_SetRate =
{
	if (r < 0.1) r = 0.1;
	if (r > 4)   r = 4;

	rec_wt_rate = r;
	if (r <= 1)
		rec_wt_slider = ((r - 0.1) / 0.9) * 0.5;
	else
		rec_wt_slider = 0.5 + ((r - 1) / 3) * 0.5;
};

/*
  The chrome, and every number in it is DERIVED.

  Build 24's first cut hardcoded a 46-pixel panel and drew the hint line at
  `small - 1`, and both were wrong for the same underlying reason: the text
  scales with hud_scale and the box did not.  At hud_scale 2 the hint ran out
  through the bottom border, and `small - 1` was a size one pixel off whichever
  rung Font_Px had just snapped to -- which is not a smaller font, it is the same
  font resampled by 0.94, sitting next to crisp text that makes it obvious.  That
  is the exact defect build 21 found in HUD_DrawSeq and wrote a ladder essay
  about; it went straight back in here because these constants were typed rather
  than measured.

  So: two font sizes, both snapped, and every vertical is a sum of those two plus
  named padding.  The panel's height is what its contents came to.

  THE MONO FACE, WHICH IS THE GOOGLE ONE ON DISK.  gfx/fonts/GoogleMed.ttf is
  Google Sans Code Medium and every glyph in it advances exactly 0.6 em -- see
  the ladder essay in sh_font.qc.  For a panel whose entire top line is a CLOCK
  that is not a preference: with a proportional face the elapsed time shifts
  sideways as the digits change under it, and at 1x that is a readout that
  jitters four times a second.  Fixed pitch also makes the width of a line
  computable from its character count, which is what lets the layout below fit
  itself to the window instead of hoping.
*/
#define WT_PAD   10                 // panel edge to content, both axes
#define WT_GAP    6                 // between the three rows

/*
  BUILD 34 -- THE PANEL IS MEASURED, AND IT SCALES.

      "when I pause the demo, the text in the demo player extends to the point
       where the word pause is off the UI.  can you extend the size of the demo
       player?"

  Two separate things, and the first one is the bug.

  THE WIDTH WAS A CHARACTER COUNT WITH A MAGIC NUMBER IN IT: (owner + 46) * cw.
  46 assumed a 34-character status line and reserved nothing at all for the close
  button or its gap.  The status line is 27 characters running and 35 PAUSED --
  and 37 past ten minutes, 41 past an hour, because Time_TickString grows a field
  at each.  At hud_scale 2 the paused string therefore overlapped the X by about
  30 px and at ten minutes ran 19 px past the border.  At hud_scale 1 the 380
  floor absorbed it, which is why this only ever showed up on a scaled HUD.

  It also asked for strlen(rec_wt_owner) while the title DRAWS "unknown" when that
  is empty, so a headerless .rec under-reserved by seven characters.

  Now both strings are built before the panel is sized and measured with
  stringwidth, so the panel fits what it is actually about to draw.  The mono
  face makes that identical to strlen*cw today (sh_font.qc's ladder essay), but
  it stops being an assumption -- and it lifts the "no colour codes in these
  values" constraint Watch_InfoRow carries for the same reason.

  hud_watch_scale is the second half: the panel and its text together, on top of
  hud_scale, because "bigger" was asked for separately from "not broken".
*/
void(vector scr) Watch_Chrome =
{
	local vector p, sz;
	local float w, h, y, sp, small, tiny, cw, bx, bw, sw, xs;
	local float wsc, pad, gap, wtitle, wclock, th, kw;
	local string s, stitle, sclock;
	local float i, xa, xb, skw, skx, skon;

	wsc = cvar("hud_watch_scale");
	if (wsc < 0.5) wsc = 0.5;       // below this the hint is unreadable anyway
	if (wsc > 4)   wsc = 4;         // above it the panel is wider than any window

	Font_Set(ui_font_mono);
	small = Font_Px(8 * ui_cv_scale * wsc);
	tiny  = Font_Px(7 * ui_cv_scale * wsc);
	cw    = small * 0.6;            // this face's advance, exactly
	pad   = floor(WT_PAD * wsc);    // panel edge to content
	gap   = floor(WT_GAP * wsc);    // between rows, and either side of the clock

	/*
	  The two strings the top row actually holds, built BEFORE the panel is sized.
	  The owner is spelled once, here, so the width and the draw cannot disagree
	  about whether it is "unknown".
	*/
	s = (rec_wt_owner != "") ? rec_wt_owner : "unknown";
	stitle = sprintf("%s   %s", s, Time_TickString(rec_wt_endticks, rec_wt_tickrate));
	sclock = sprintf("%s / %s   %.2fx%s",
	                 Time_TickString(rec_wt_ticks, rec_wt_tickrate),
	                 Time_TickString(rec_wt_endticks, rec_wt_tickrate),
	                 rec_wt_rate, rec_wt_paused ? "  paused" : "");

	wtitle = stringwidth(stitle, TRUE, [small, small]);
	wclock = stringwidth(sclock, TRUE, [small, small]);
	bw     = small + 4;             // the close button is square on the row height

	/*
	  The width the panel WANTS, and then what the window will give it: both
	  strings, the gap between them, the gap before the close button, and the
	  button.  Everything on the widest row, named rather than counted.
	*/
	w = pad * 2 + wtitle + gap + wclock + gap + bw;
	if (w < 380 * wsc) w = 380 * wsc;
	if (w > scr_x - 24) w = scr_x - 24;

	// Height: title, bar, hint, with a gap between each and padding top and
	// bottom.  The bar is the tallest of the three because it is a control.
	h = pad * 2 + small + gap + (small + 4) + gap + tiny;

	p  = [floor((scr_x - w) * 0.5), 12];
	sz = [w, h];

	// Published for Timer_DrawPanel, which is drawn EARLIER in the frame -- so
	// this is last frame's value and the timer settles one frame after a
	// hud_scale change.  Publishing it from here rather than recomputing the
	// layout twice is the same trade ui_strafe_bottom makes, and one frame of
	// a panel being 8 px out on a cvar change is not worth a second layout pass.
	rec_wt_chromebot = p_y + h;

	sui_fill(p, sz, '0.03 0.04 0.06', 0.88, 0);
	sui_border_box(p, sz, 1, '0.30 0.55 0.85', 0.9, 0);

	// --- the title line ---------------------------------------------------
	y  = p_y + pad;
	bx = p_x + w - pad - bw;

	drawstring([p_x + pad, y], stitle, [small, small], '0.90 0.93 0.98', 1, 0);

	/*
	  Where we are, against how long it is -- RIGHT-ALIGNED off the close button
	  rather than placed at 42% of the width.  A fraction of the width is a
	  guess about how long the owner's name is, and it was the reason this line
	  could collide with the title on a narrow window.

	  The floor is the title's MEASURED end plus a gap, not a second guess at how
	  long the owner's name is.  With the width above sized off the same two
	  measurements it cannot fire unless the window itself clamped the panel --
	  which is the one case where something has to give, and the title is the half
	  you can afford to lose the end of.
	*/
	xs = bx - gap - wclock;
	if (xs < p_x + pad + wtitle + gap)
		xs = p_x + pad + wtitle + gap;
	drawstring([xs, y], sclock, [small, small],
	           rec_wt_paused ? '1.00 0.82 0.20' : '0.65 0.70 0.78', 1, 0);

	// --- the close button, top right --------------------------------------
	sui_action_element([bx, y - 2], [bw, bw], "wt_x", sui_noop);
	if (sui_is_hovered("wt_x"))
		sui_fill([bx, y - 2], [bw, bw], '0.55 0.15 0.15', 1, 0);
	drawstring([bx + (bw - cw) * 0.5, y], "X", [small, small], '1 1 1', 1, 0);
	if (sui_is_released("wt_x"))
	{
		Watch_Stop();
		return;
	}

	// --- the scrub bar ----------------------------------------------------
	//
	// The speed slider is a fixed share of the width rather than a fixed 110
	// pixels: at hud_scale 2 on a 4K window 110 px is a knob you cannot hit, and
	// on a 720p window it was a third of the panel.
	y  = p_y + pad + small + gap;
	sw = w * 0.22;
	// Build 34: the clamps travel with hud_watch_scale too, or a scaled-up panel
	// gets the same 80px slider it had at 1x sitting in a much wider row.
	if (sw < 80 * wsc) sw = 80 * wsc;
	if (sw > 220 * wsc) sw = 220 * wsc;

	sp = (rec_wt_t1 > rec_wt_t0)
	   ? (rec_wt_time - rec_wt_t0) / (rec_wt_t1 - rec_wt_t0) : 0;

	bw = w - pad * 2 - sw - gap * 2;      // the scrub bar's own width
	th = floor(6 * wsc);                  // the track's own thickness
	kw = floor(4 * wsc);                  // and the width of a slider knob

	sui_fill([p_x + pad, y + (small + 4) * 0.5 - th * 0.5], [bw, th],
	         '0.12 0.14 0.18', 1, 0);
	sui_fill([p_x + pad, y + (small + 4) * 0.5 - th * 0.5], [bw * sp, th],
	         '0.35 0.72 1.00', 1, 0);

	/*
	  The t = 0 mark: everything left of it is the approach the padding ring
	  kept, which is time the clock had not started for.

	  BUILD 26 -- IT IS DRAWN UNDER THE TRACK NOW, AND THIS WAS THE REPORT.

	  It used to be a two-pixel FULL-HEIGHT bar in bright amber, cutting through
	  the track at a FIXED position -- and it was the only thing on this bar
	  shaped like a handle, because the scrub bar had no playhead at all (see
	  below).  So the one control-looking object on the control never moved, and
	  it sits near the left end: on an 86s run with the usual 256-sample ring the
	  padding is 3.84s, i.e. 4.5% along, which reads as zero.  "The playback head
	  is stuck at 0" is exactly right about what it looks like and exactly wrong
	  about what it is.

	  So it becomes a gradation on the ruler rather than a control: three pixels
	  tall, hanging below the track, in the amber the timer already uses for a
	  clock that has not started.  It is still a fact worth marking -- it is
	  where the run's own clock begins -- and it is no longer competing with the
	  thing you grab.
	*/
	if (rec_wt_t0 < 0)
	if (rec_wt_t1 > rec_wt_t0)
		sui_fill([p_x + pad + bw * (-rec_wt_t0 / (rec_wt_t1 - rec_wt_t0)) - kw * 0.5,
		          y + (small + 4) * 0.5 + th * 0.5 + 1],
		         [kw * 0.5, floor(3 * wsc)], '1.00 0.82 0.20', 0.9, 0);

	/*
	  THE DEAD AIR, IN RED.  Build 43.

	  ON the track and not below it, unlike the t=0 gradation above -- that one is
	  a single instant and wants to be a tick mark on a ruler, while these are
	  EXTENTS and want to read as parts of the run.  Drawn AFTER the progress fill
	  so a stretch is visible whether it has been played or not: the blue fill
	  would otherwise swallow every mark behind the playhead, which is exactly the
	  half you look at after a run to see where the time went.

	  0.9 rather than 1 so the blue still shows through faintly and the mark reads
	  as part of the bar rather than as a hole in it.

	  A run can legitimately have none of these, and most do; the loop then costs
	  one compare.  Clamped to the track at both ends because a stretch that runs
	  to the last sample would otherwise put half a pixel past the right edge.
	*/
	if (rec_wt_t1 > rec_wt_t0)
	for (i = 0; i < rec_wt_idn; i = i + 1)
	{
		xa = bw * (rec_wt_idt0[i] - rec_wt_t0) / (rec_wt_t1 - rec_wt_t0);
		xb = bw * (rec_wt_idt1[i] - rec_wt_t0) / (rec_wt_t1 - rec_wt_t0);
		xa = bound(0, xa, bw);
		xb = bound(0, xb, bw);
		// Never thinner than a pixel: a two-tick park is a real fact about the
		// run and a zero-width fill is not a mark.
		if (xb - xa < 1)
			xb = xa + 1;
		sui_fill([p_x + pad + xa, y + (small + 4) * 0.5 - th * 0.5],
		         [xb - xa, th], '0.85 0.25 0.25', 0.9, 0);
	}

	/*
	  THE PLAYHEAD, and there was not one.

	  sui_slidercontrol draws NOTHING -- it is sui_action_element plus the drag
	  and keyboard handling, and every caller draws its own track and its own
	  knob (sui_sys.qc:1140).  The speed slider beside this one does exactly that
	  four lines down; this one drew a track and a progress fill and stopped, so
	  the leading edge of the fill was the only indication of where you were and
	  there was nothing to aim a mouse at.

	  Drawn like the speed slider's knob, deliberately: same width, same full row
	  height, same near-white, so the two controls on this row look like the same
	  kind of object.  Clamped a knob's width inside either end so it is still
	  wholly on the bar at t0 and t1 rather than half outside the panel.
	*/
	sui_fill([p_x + pad + bound(0, bw * sp, bw) - kw * 0.5, y], [kw, small + 4],
	         '0.90 0.93 0.98', 1, 0);

	sui_slidercontrol("wt_scrub", [p_x + pad, y], [bw, small + 4],
	                  [0, 1, 0], sp, Watch_ScrubTo);

	// --- the speed slider -------------------------------------------------
	xs = p_x + w - pad - sw;
	sui_fill([xs, y + (small + 4) * 0.5 - th * 0.5], [sw, th], '0.12 0.14 0.18', 1, 0);
	sui_fill([xs + sw * 0.5 - kw * 0.25, y + 1], [kw * 0.5, small + 2],
	         '0.55 0.58 0.65', 1, 0);
	sui_fill([xs + sw * rec_wt_slider - kw * 0.5, y], [kw, small + 4],
	         '0.90 0.93 0.98', 1, 0);
	sui_slidercontrol("wt_speed", [xs, y], [sw, small + 4],
	                  [0, 1, 0], rec_wt_slider, Watch_SetSpeed);

	// --- the hint ---------------------------------------------------------
	//
	// Drawn at a SNAPPED size, and shortened when the window cannot hold the long
	// form.  A string that runs out of the box is worse than a shorter one.
	/*
	  BUILD 26 -- IT NAMES hud_watch_info, AND THAT IS THE WHOLE OF THAT REPORT.

	  The detail panel shipped in build 25 and was asked for again in build 26,
	  because it defaults to 0 and NOTHING anywhere said it existed: not this
	  line, not the console, not default.cfg's own section.  A feature nobody can
	  find has not shipped.  It is still off by default -- it covers a third of
	  the left edge -- but it is now one readable string away.
	*/
	y = p_y + h - pad - tiny;

	/*
	  THE SKIP TOGGLE, and why it is a visible control rather than only a cvar.

	  Build 25 shipped hud_watch_info defaulting to 0 with nothing anywhere
	  naming it; build 26 got the same feature reported as missing, and the note
	  that came out of it was "A feature nobody can find has not shipped."  A
	  switch that changes what playback DOES is a worse thing to hide than a
	  panel, so it gets a label you can click.

	  ON THE HINT ROW rather than the control row, which costs no layout change
	  at all: the row already exists, `h` is unchanged, and the hint beside it
	  simply measures itself against what is left.  Putting it on the scrub row
	  would have meant re-deriving bw and the two sliders around it.

	  It carries the COUNT because that is the fact the toggle is about -- "skip
	  still (3)" says both that the switch exists and that this particular run
	  has three stretches worth skipping, which the red on the bar above says in
	  the other direction.
	*/
	skon = cvar("hud_watch_skipidle");
	if (rec_wt_idn > 0)
		s = sprintf("skip still (%g)", rec_wt_idn);
	else
		s = "skip still";

	skw = stringwidth(s, TRUE, [tiny, tiny]) + pad;
	skx = p_x + w - pad - skw;

	sui_action_element([skx, y - 2], [skw, tiny + 4], "wt_skip", sui_noop);
	if (sui_is_hovered("wt_skip"))
		sui_fill([skx, y - 2], [skw, tiny + 4], '0.16 0.20 0.26', 1, 0);

	// Green only when it is both on AND has something to do.  On with nothing to
	// skip is a true statement about the switch and a misleading one about the
	// run, so it reads as dim -- the same distinction the KIND column makes
	// between "clean" and "--".
	drawstring([skx + pad * 0.5, y], s, [tiny, tiny],
	           (skon && rec_wt_idn > 0) ? '0.45 0.85 0.50' : '0.40 0.42 0.48', 1, 0);

	if (sui_is_released("wt_skip"))
		localcmd(skon ? "hud_watch_skipidle 0\n" : "hud_watch_skipidle 1\n");

	s = "space pause   arrows seek 5s   drag to scrub   hud_watch_info 1   esc close";
	// Build 34: measured like everything else on the panel now.  This ladder was
	// already the only part that adapted to the width; it just did it by counting.
	// Build 43: measured against what the toggle left, not against the whole
	// row, or the long form runs under it on a narrow window.
	if (stringwidth(s, TRUE, [tiny, tiny]) > w - pad * 2 - skw - gap)
		s = "space  arrows  esc   hud_watch_info 1";
	if (stringwidth(s, TRUE, [tiny, tiny]) > w - pad * 2 - skw - gap)
		s = "space  arrows  esc";
	if (stringwidth(s, TRUE, [tiny, tiny]) > w - pad * 2 - skw - gap)
		s = "";
	drawstring([p_x + pad, y], s, [tiny, tiny], '0.45 0.48 0.55', 1, 0);

	Font_Reset();
};

/*
===========================================================================
  hud_watch_info -- WHAT THIS RECORDING ACTUALLY IS.  Build 25.

  Most of it is header keys and cursor state that `replay status` has printed
  since build 24, and repeating them on screen is worth doing only because of
  the three that are NOT in there and cannot usefully be:

  THE RUN'S OWN FRAME RATE, LIVE.  The .view sidecar is one line per RENDERED
  frame and the reader already brackets the lines belonging to the tick it is
  drawing (rec_wt_vblk0/vblk1, computed in Watch_ViewBlock for the sub-tick
  angle pick).  So the count in that bracket, over the tick length, is the frame
  rate the run was actually being played at AT THIS MOMENT -- not an average over
  the file, which is a different and much less interesting number.  Watch it
  against the scrub and you can see where the recording's own machine struggled.

  THE .rec's MEASURED SAMPLE RATE.  The nominal rate is 66.67, and the recorder's
  own comment measures 65, 64.6 and 43.5 on real files, because a sample is
  written per received PACKET and a packet can carry several usercmds.  Which of
  those you are watching decides how much of the smoothness is interpolation.

  AND THE VIEWER'S OWN FRAME RATE, so the two are distinguishable.  Without it,
  "the run was at 300" and "you are at 300" look like the same statement.

  DRAWN LEFT, UNDER THE CHROME.  rec_wt_chromebot is published by Watch_Chrome
  for exactly this kind of thing (Timer_DrawPanel already reads it), so the panel
  cannot land on top of the scrub bar at any hud_scale.
===========================================================================
*/
float rec_wt_fps;                // the VIEWER's frame rate, smoothed

/*
  HOW TALL THE PANEL IS, counted where the rows are rather than once at the top.

  Build 25 wrote `rows = 14` a hundred lines above the fourteen rows, and build
  26 adds five -- which is exactly the shape of the constant that goes stale.
  Four small numbers, each sitting immediately above the block it counts, is not
  self-deriving but it is countable on one screen, which the single 19 was not.
  Add a row, bump the number three lines above it.
*/
#define WT_INFO_FILE   7        // path, owner, format, map, tag, recorded, size
#define WT_INFO_RUN    5        // leg, time, tick, at, playback
#define WT_INFO_RATE   4        // run fps, your fps, rec rate, samples
#define WT_INFO_STATE  3        // ramp, rows, path

// One row: label left, value right-aligned inside the panel's width.
void(vector p, float w, float sz, float cw, string k, string v) Watch_InfoRow =
{
	drawstring([p_x, p_y], k, [sz, sz], '0.52 0.56 0.64', 1, 0);
	drawstring([p_x + w - strlen(v) * cw, p_y], v, [sz, sz], '0.86 0.90 0.96', 1, 0);
};

/*
  WHEN THIS RUN WAS RECORDED, out of the header key that already carries it.

  The .rec has no `created` key and does not need one: `runid` is
  strftime("%Y%m%d-%H%M%S") plus the slot (sv_timer.qc:1045), so the answer has
  been in every file since v3.  Sliced rather than parsed into numbers -- three
  stofs would be three ways to be wrong about a field whose only job is to be
  read by a person -- and refused outright below fifteen characters, because a
  runid from some other writer is not a date and must not be printed as one.
*/
string(string id) Watch_RunDate =
{
	if (strlen(id) < 15)
		return "--";
	return sprintf("%s-%s-%s %s:%s",
	               substring(id, 0, 4), substring(id, 4, 2), substring(id, 6, 2),
	               substring(id, 9, 2), substring(id, 11, 2));
};

void(vector scr) Watch_Info =
{
	local vector p;
	local float w, h, sz, cw, lh, y, rows;
	local float span, rechz, viewhz, livehz, tick;
	local string s;

	Font_Set(ui_font_mono);
	sz = Font_Px(7 * ui_cv_scale);
	cw = sz * 0.6;                  // GoogleMed advances 0.6em for every glyph
	lh = sz + 3 * ui_cv_scale;

	rows = WT_INFO_FILE + WT_INFO_RUN + WT_INFO_RATE + WT_INFO_STATE;
	w    = 34 * cw;                 // the widest row, in characters
	h    = WT_PAD * 2 + rows * lh;

	p = [12, rec_wt_chromebot + 10, 0];
	if (p_y + h > scr_y - 12)
		p_y = scr_y - 12 - h;       // a short window pushes it up rather than off

	sui_fill(p, [w + WT_PAD * 2, h], '0.03 0.04 0.06', 0.82, 0);
	sui_border_box(p, [w + WT_PAD * 2, h], 1, '0.30 0.55 0.85', 0.55, 0);

	p_x = p_x + WT_PAD;
	y   = p_y + WT_PAD;

	/*
	  The three rates.

	  span is the .rec's own, padding included, so rechz is measured over exactly
	  the samples the file holds rather than over the run clock -- a file with 256
	  samples of pre-start ring has a real 3.8s of them and they are real samples.

	  The .view's average is taken over the same span deliberately, even though
	  the sidecar has no coverage over the negative padding: the two numbers are
	  then in the same denominator and the ratio between them is the frames per
	  tick, which is the thing worth reading off two adjacent rows.  The live one
	  below is exact and is what to trust for a moment.
	*/
	span   = rec_wt_t1 - rec_wt_t0;
	rechz  = (span > 0.001) ? (rec_wt_nsamp / span) : 0;
	viewhz = (span > 0.001) ? ((rec_wt_viewn - rec_wt_view0) / span) : 0;

	tick   = rec_wt_tickrate;
	if (tick <= 0) tick = PM_TICK;
	livehz = (rec_wt_vblk1 - rec_wt_vblk0) / tick;

	s = rec_wt_path;
	if (strlen(s) > 34)
		s = substring(s, strlen(s) - 34, 34);
	Watch_InfoRow([p_x, y], w, sz, cw, "", s);                              y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "owner",
	              (rec_wt_owner != "") ? rec_wt_owner : "unknown");           y = y + lh;

	/*
	  What kind of run this is -- the same states the leaderboard shows, from the
	  same source.  A REC 3 file cannot answer (its header has no `flags` key),
	  and saying so is the point: the alternative is asserting one of the others,
	  which would be a guess about somebody's run.

	  BUILD 44: FOUR WORDS, FROM FS_RunClass.  This was a truth test on the whole
	  masked word, which was correct while the mask admitted only TF_PRACTICE and
	  TF_SHADOW and stops being correct the moment it admits anything else -- and
	  the mask two thousand lines up now admits two more bits.  A test that is
	  right because of what a distant line masks out is the shape of bug this
	  build is fixing one level up.  This is the second of the three readers the
	  shared classifier exists to keep in step; the third is cl_timer.qc's
	  sub-label, which this same panel draws through Timer_DrawPanel.
	*/
	if (!rec_wt_v4)             s = "rec3  unknown";
	else                       s = strcat("rec4  ",
	                                      FS_RunClassName(FS_RunClass(rec_wt_flags)));
	Watch_InfoRow([p_x, y], w, sz, cw, "format", s);                        y = y + lh;

	/*
	  WHICH MAP, and whether it is the one under you.

	  Watch_Open already prints this as a console warning when they differ, and a
	  warning that scrolled past ten replays ago is not an answer to "why is the
	  camera flying through nothing".  Same comparison, on screen, permanently.

	  No colour code in it, deliberately: Watch_InfoRow right-aligns on
	  strlen(v) and a ^1 is two characters that occupy no width, so a coloured
	  value would sit four characters off the edge every other row.
	*/
	s = (rec_wt_map != "") ? rec_wt_map : "unknown";
	if (rec_wt_map != "")
	if (rec_wt_map != serverkey("map"))
		s = strcat(s, " (elsewhere)");
	Watch_InfoRow([p_x, y], w, sz, cw, "map", s);                           y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "tag", FS_TagName(rec_wt_tag));       y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "recorded",
	              Watch_RunDate(rec_wt_runid));                              y = y + lh;

	/*
	  How big the two files are, in LINES rather than bytes: buf_getsize is free
	  and a byte count would be a guess at the average line length of a format
	  whose lines vary by a factor of three.

	  These are whole-file counts and the `samples` row below is the payload, so
	  the difference between them is the header plus every split, checkpoint and
	  board record -- which is the one thing neither number says on its own.
	*/
	Watch_InfoRow([p_x, y], w, sz, cw, "file",
	              sprintf("%g rec  %g view lines",
	                      rec_wt_recn, rec_wt_viewn));                        y = y + lh;

	// Build 57: the LEG and the segment it began at, which stopped being one
	// number when stage 1 became a leg -- a stage-1 run and a full run both read
	// `seg 0`, and only `leg` tells them apart.
	Watch_InfoRow([p_x, y], w, sz, cw, "leg",
	              sprintf("track %g  leg %g  seg %g",
	                      rec_wt_track, rec_wt_leg, rec_wt_startseg));        y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "time",
	              sprintf("%s  %g ticks",
	                      Time_TickString(rec_wt_endticks, tick),
	                      rec_wt_endticks));                                 y = y + lh;

	/*
	  The tick the run was SIMULATED at, and the padding ring in front of it.

	  Both matter for the same reason and neither was on screen: a 100Hz bhop
	  recording and a 66.7Hz surf one are different files that look identical
	  here, and the span before t=0 is approach rather than run -- the trailer
	  counts it, so this prints the trailer's own number rather than deriving one
	  from t0, which is the disagreement build 25's stage slices turned out to be.

	  The Hz deliberately stays on the `rec rate` row below and is not repeated
	  here: that row already frames it as measured-against-nominal, and two rows
	  of one number is the thing this panel exists to avoid.
	*/
	Watch_InfoRow([p_x, y], w, sz, cw, "tick",
	              sprintf("%.4f s   pad %g samples", tick, rec_wt_pad));     y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "at",
	              sprintf("%.3f  of %.3f..%.3f",
	                      rec_wt_time, rec_wt_t0, rec_wt_t1));                 y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "playback",
	              sprintf("%.2fx%s", rec_wt_rate,
	                      rec_wt_paused ? "  paused" : ""));                 y = y + lh;

	// --- the three rates, together, because they are only useful compared ---
	/*
	  "no sidecar" rather than two zeros, and this is not cosmetic.

	  The run's frame rate is a property of the .view, and a .rec with no .view
	  beside it has no answer -- a recording made before build 17, or a fixture,
	  or a run whose sidecar was lost.  Printing 0 there says "that machine
	  rendered no frames", which is a claim about somebody's run rather than an
	  admission that the file cannot say.  The leaderboard's clean/stitched column
	  makes the same distinction for the same reason.
	*/
	Watch_InfoRow([p_x, y], w, sz, cw, "run fps",
	              (rec_wt_view >= 1)
	                ? sprintf("%.0f now  %.0f avg", livehz, viewhz)
	                : "no sidecar");                                        y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "your fps",
	              sprintf("%.0f", rec_wt_fps));                              y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "rec rate",
	              sprintf("%.1f Hz of %.1f", rechz,
	                      (tick > 0) ? (1 / tick) : 0));                    y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "samples",
	              sprintf("%g rec  %g view", rec_wt_nsamp,
	                      rec_wt_viewn - rec_wt_view0));                      y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "ramp",
	              rec_wt_v4
	                ? sprintf("%g  %.2f %.2f %.2f", rec_wt_rc ? 1 : 0,
	                          rec_wt_gnorm_x, rec_wt_gnorm_y, rec_wt_gnorm_z)
	                : "not recorded");                                      y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "rows",
	              sprintf("%g seq (%g)  %g board", rec_wt_sqn,
	                      rec_wt_sqshown, rec_wt_bdn_n));                     y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "path",
	              sprintf("%g ctl  %g curve  %g ev",
	                      rec_wt_cn, rec_wt_pn, rec_wt_evn));

	Font_Reset();
};

/*
  sui_begin / sui_end bracket every frame that draws with sui, and they are here
  rather than in cl_main.qc so that the one caller cannot forget: sui_end is what
  clears the click-once actions, and without it sui_is_released would latch true
  forever and the close button would fire on every subsequent frame.
*/
void(vector scr) Watch_Draw =
{
	if (!rec_wt_open)
	{
		rec_wt_chromebot = 0;
		return;
	}

	sui_begin(scr_x, scr_y);
	Watch_Chrome(scr);

	// AFTER the chrome, which is what publishes rec_wt_chromebot -- this panel
	// hangs off it, so drawing first would lay it out against last frame's.
	if (cvar("hud_watch_info"))
		Watch_Info(scr);

	sui_end();
};

/*
===========================================================================
  Per frame
===========================================================================
*/
void() Watch_Frame =
{
	local float dt, i;

	rec_wt_on = FALSE;
	if (!rec_wt_open)
		return;

	// The map changed under us.  The camera would be flying through another
	// map's geometry, and the frozen player is a different edict now.
	if (rec_wt_map != "")
	if (rec_wt_map != serverkey("map"))
	{
		Watch_Stop();
		return;
	}

	dt = cltime - rec_wt_lastreal;
	rec_wt_lastreal = cltime;
	if (dt < 0 || dt > 0.5)             // a hitch, a load, or the first frame
		dt = 0;

	/*
	  BUILD 25: the VIEWER's frame rate, for the info panel.

	  Exponentially smoothed at about a fifth of a second, which is the same time
	  constant the strafe bar's turn window uses and for the same reason: 1/dt on
	  a single frame is a number that swings by a third at 300 fps and reads as
	  noise rather than as a rate.  Taken here because this is where the replay
	  already measures real elapsed time, before the playback rate scales it --
	  rec_wt_time's clock is the recording's and this one has to be yours.
	*/
	if (dt > 0)
		rec_wt_fps = rec_wt_fps + ((1 / dt) - rec_wt_fps) * (dt / 0.2 > 1 ? 1 : dt / 0.2);

	if (!rec_wt_paused)
	{
		rec_wt_time = rec_wt_time + dt * rec_wt_rate;
		if (rec_wt_time >= rec_wt_t1)
		{
			rec_wt_time   = rec_wt_t1;
			rec_wt_paused = TRUE;        // hold on the last frame rather than
		}                               // snapping back to your own body

		/*
		  ---- AND SKIP THE DEAD AIR.  Build 43. ------------------------------

		  Only while PLAYING, and that is the whole of the gating this needs.  A
		  pause is someone looking at a still frame -- including, deliberately,
		  a still frame inside a parked stretch, which is exactly where you would
		  pause to see what the player was doing -- and yanking the clock out
		  from under that would make the pause useless.  A drag is a pause too:
		  sui_slidercontrol calls Watch_ScrubTo, which sets rec_wt_time directly
		  and does not come through here, so a scrub INTO a stretch stays where
		  it was put and only starts skipping when you press play again.  That
		  falls out of the structure rather than needing a test, and it is the
		  behaviour you want: the marks are on the bar to be scrubbed to.

		  THROUGH Watch_Seek AND NOT BY WRITING rec_wt_time.  Watch_Seek is the
		  one entry point that invalidates all four cursor caches -- the view
		  block, the split list, the segment column and the board -- and a jump
		  of thirty seconds that skipped them would leave the panels describing
		  where the clock used to be.  That is the same reason Watch_ScrubTo goes
		  through it.

		  Landed just PAST the end of the stretch rather than exactly on it, by
		  one tick.  Exactly on it re-enters the same span on the next frame if
		  the sample at that boundary is still under the threshold, which it is
		  by construction -- the span closes on the first FAST sample, so its end
		  time is a tick after the last slow one.  Half a tick of margin costs
		  nothing and removes a loop that would otherwise be possible.
		*/
		if (rec_wt_idn > 0)
		if (cvar("hud_watch_skipidle"))
		for (i = 0; i < rec_wt_idn; i = i + 1)
		{
			if (rec_wt_time < rec_wt_idt0[i])
				break;                  // the spans are in order; the rest are ahead
			if (rec_wt_time < rec_wt_idt1[i])
			{
				Watch_Seek(rec_wt_idt1[i] + rec_wt_tickrate);
				break;
			}
		}
	}

	Watch_Sample();
	rec_wt_on = TRUE;
};

float(float evtype, float scanx, float chary, float devid) Watch_InputEvent =
{
	if (!rec_wt_open)
		return FALSE;

	// The cursor.  sui wants absolute positions and gets them because
	// setcursormode(TRUE) put kdm_game into key_dest_absolutemouse, which is
	// what makes the engine call CSQC_MousePosition instead of CSQC_MouseMove.
	// Returning TRUE is not optional: the deltas are zeroed only on a true
	// return, so forgetting it leaves the view turning under the cursor.
	if (evtype == IE_MOUSEABS)
	{
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}

	if (evtype == IE_KEYDOWN || evtype == IE_KEYUP)
	{
		/*
		  MOUSE1 is bound to +duck and MOUSE2 to +jump, so a click on the close
		  button would also crouch the frozen player.  Both are swallowed whole
		  while the chrome is up -- and the caller must not have fed them to
		  Keys_Edge either, or the duck box lights every time you click.
		*/
		if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
		{
			sui_input_event(evtype, scanx, chary, devid);
			return TRUE;
		}

		if (evtype == IE_KEYUP)
			return FALSE;

		// Escape closes.  keys.c:3205 says csqc may steal it, and the board is
		// open with key_dest still kdm_game, so the test there passes and the
		// menu does not open behind us.
		if (scanx == K_ESCAPE)
		{
			Watch_Stop();
			return TRUE;
		}
		if (scanx == K_SPACE)
		{
			rec_wt_paused = !rec_wt_paused;
			return TRUE;
		}
		if (scanx == K_LEFTARROW)
		{
			Watch_Seek(rec_wt_time - 5);
			return TRUE;
		}
		if (scanx == K_RIGHTARROW)
		{
			Watch_Seek(rec_wt_time + 5);
			return TRUE;
		}
	}

	return FALSE;
};

/*
  `replay` -- the command.

  The name is free: nothing in the engine registers it.  That had to be checked
  rather than assumed, because PF_cs_registercommand is `if (!Cmd_Exists(...))`
  and therefore SILENTLY does nothing when the name is taken -- the command would
  simply never arrive and nothing would say why.
*/
// BUILD 57: `leg` is the LEG -- 0 the full run, k stage k -- as FS_RunPath takes it.
string(float track, float leg, string tag) Watch_LegPath =
{
	return FS_RunPath(serverkey("map"), track, leg, -1, tag, "rec");
};

/*
  The best archived run on a leg: the archive is sorted by name and the names are
  zero-padded tick counts, so the first match IS the fastest.  That property is
  the whole reason build 23 padded them, and it is what lets a leaderboard exist
  with no index file.

  BUILD 57: keyed on the LEG.  It took the 0-based starting segment and handed it
  to FS_RunDir as though it were one, which is why `replay stage 2` opened stage
  3's folder and `replay stage 1` opened stage 2's.
*/
string(float track, float leg, string tag) Watch_BestOnLeg =
{
	local float h;
	local string fn;

	h = search_begin(sprintf("%s*_%s.rec", FS_RunDir(serverkey("map"),
	                                                 track, leg), tag),
	                 FS_NAMESORT, TRUE);
	if (h < 0)
		return "";
	if (search_getsize(h) < 1)
	{
		search_end(h);
		return "";
	}
	fn = search_getfilename(h, 0);
	search_end(h);
	return fn;
};

/*
  `replay status` -- the reader, said out loud.

  This engine has no viewpos and no way to ask what the camera is doing, so
  without a line like this the entire playback path would be verifiable only by
  looking at it, which is exactly the class of thing that ships subtly wrong.
  It is the same instrument as the server timer's "would write" line: every
  number on it is the one the frame actually used, not a recomputation.

  Three prints because fteqcc caps varargs at eight and SILENTLY drops the rest,
  which would fill the tail of the line with zeroes rather than fail to compile.
*/
void() Watch_Status =
{
	local vector sv;
	if (!rec_wt_open)
	{
		print("replay: nothing loaded\n");
		return;
	}

	print(sprintf("replay: %s\n", rec_wt_path));
	print(sprintf("  owner %s  map %s  track %g seg %g  end %g  samples %g\n",
	              (rec_wt_owner != "") ? rec_wt_owner : "-",
	              (rec_wt_map != "") ? rec_wt_map : "-",
	              rec_wt_track, rec_wt_startseg, rec_wt_endticks, rec_wt_nsamp));
	print(sprintf("  t %.4f  span %.4f..%.4f  tick %g  rate %.2f  paused %g\n",
	              rec_wt_time, rec_wt_t0, rec_wt_t1, rec_wt_ticks,
	              rec_wt_rate, rec_wt_paused));
	print(sprintf("  org %.2f %.2f %.2f  vel %.2f %.2f %.2f\n",
	              rec_wt_org_x, rec_wt_org_y, rec_wt_org_z,
	              rec_wt_vel_x, rec_wt_vel_y, rec_wt_vel_z));
	print(sprintf("  ang %.2f %.2f  keys %g  ground %g  duck %g  flags %g\n",
	              rec_wt_pitch, rec_wt_yaw, rec_wt_keys,
	              rec_wt_onground, rec_wt_ducked, rec_wt_flags));
	print(sprintf("  view %g lines (%g index)  path %g ctl -> %g curve  events %g\n",
	              rec_wt_viewn, rec_wt_vxn, rec_wt_cn, rec_wt_pn, rec_wt_evn));
	// Build 43.  A SECOND print rather than six more fields on the one above --
	// fteqcc caps varargs at 8 including the format and drops the ninth silently.
	// `curve` reaching exactly WT_PATHMAX is the build-42 truncation bug; `still`
	// is what the red on the bar is drawn from and what skip would jump.
	print(sprintf("  still %g stretch(es)%s  skip %g\n",
	              rec_wt_idn,
	              (rec_wt_idover > 0) ? sprintf(" (+%g dropped)", rec_wt_idover) : "",
	              cvar("hud_watch_skipidle")));
	/*
	  The screen-space drawer's last frame.  Three numbers because "the line is
	  not there" has three different causes and they need telling apart: mode/0
	  quads means it never ran, quads 0 with clip high means the near-plane clip
	  ate everything, and quads high with `first` outside the screen means it
	  drew somewhere you cannot see.  Guessing between those cost a build.
	*/
	print(sprintf("  path mode %g  2d %g quad(s)  clipped %g  wild %g  first %.0f,%.0f\n",
	              Watch_PathMode(), rec_wt_p2n, rec_wt_p2clip, rec_wt_p2wild,
	              rec_wt_p2first_x, rec_wt_p2first_y));
	// The probe: 256 units dead ahead, projected either side of renderscene.
	// Both should read the centre of the screen and they should agree.
	sv = getproperty(VF_SCREENVSIZE);
	print(sprintf("  probe pre %.0f,%.0f  post %.0f,%.0f  screen %g x %g\n",
	              rec_wt_p2pre_x, rec_wt_p2pre_y,
	              rec_wt_p2post_x, rec_wt_p2post_y, sv_x, sv_y));
	print(sprintf("  2d bbox %.0f,%.0f .. %.0f,%.0f\n",
	              rec_wt_p2min_x, rec_wt_p2min_y,
	              rec_wt_p2max_x, rec_wt_p2max_y));

	/*
	  THE v4 HALF, and it is the whole of what stage 1b added.

	  Six lines was the varargs cap on ONE sprintf, not on the function, so these
	  are two more prints rather than a squeeze.  They are here for the same
	  reason the rest of this exists: no config can look at the strafe bar, and
	  without these the ramp contact, the plane, the board table and the segment
	  build would be verifiable only by watching the screen.

	  `seq` reading `0 rows` on a v4 file is the failure that matters -- it means
	  the build pass ran and Board_Frame produced nothing, which is either a
	  missing ramp bit or a plane the engine never wrote.
	*/
	print(sprintf("  v4 %g  rc %g  plane %.3f %.3f %.3f  wish %.2f %.2f\n",
	              rec_wt_v4, rec_wt_rc,
	              rec_wt_gnorm_x, rec_wt_gnorm_y, rec_wt_gnorm_z,
	              rec_wt_wish_x, rec_wt_wish_y));
	print(sprintf("  seq %g rows (%g shown)  boards %g (at %g)  turn %.0f/s\n",
	              rec_wt_sqn, rec_wt_sqshown, rec_wt_bdn_n, rec_wt_bdshown,
	              ui_turnrate));
	// Build 25.  See Watch_BuildSeq: this is the only headless evidence that the
	// ramp hold does anything, because the column looks the same either way.
	print(sprintf("  ramp gaps bridged %g  (hold %.2fs, the engine's own board gate)\n",
	              rec_wt_bridged, RAMP_GAP));

	/*
	  BUILD 25: the same three rates the info panel draws, so the console and the
	  screen cannot say different things.  See Watch_Info for what each is and why
	  the live one is worth more than the average.
	*/
	{
		local float span, tick;
		span = rec_wt_t1 - rec_wt_t0;
		tick = rec_wt_tickrate;
		if (tick <= 0) tick = PM_TICK;

		// See Watch_Info: with no sidecar the run's own frame rate has no answer,
		// and two zeros would read as one.
		if (rec_wt_view >= 1)
			print(sprintf("  run fps %.0f now / %.0f avg   yours %.0f   rec %.1f Hz of %.1f\n",
			              (rec_wt_vblk1 - rec_wt_vblk0) / tick,
			              (span > 0.001) ? ((rec_wt_viewn - rec_wt_view0) / span) : 0,
			              rec_wt_fps,
			              (span > 0.001) ? (rec_wt_nsamp / span) : 0,
			              1 / tick));
		else
			print(sprintf("  run fps no sidecar   yours %.0f   rec %.1f Hz of %.1f\n",
			              rec_wt_fps,
			              (span > 0.001) ? (rec_wt_nsamp / span) : 0,
			              1 / tick));
	}
};

float(string cmd) Watch_ConsoleCommand =
{
	local string a, p;
	local float track, leg;

	tokenize(cmd);
	if (argv(0) != "replay")
		return FALSE;

	a = argv(1);

	if (a == "stop" || a == "off")
	{
		Watch_Stop();
		return TRUE;
	}

	/*
	  The scripted controls.  They exist so a config can drive the reader to an
	  exact position and read it back -- playback otherwise advances with the
	  wall clock, and at the 4 fps a headless run manages, "wait 40 frames" is
	  ten seconds of a run rather than a fixed place in it.
	*/
	if (a == "status")
	{
		Watch_Status();
		return TRUE;
	}
	if (a == "pause")  { rec_wt_paused = TRUE;  return TRUE; }
	if (a == "play")   { rec_wt_paused = FALSE; return TRUE; }
	if (a == "seek")
	{
		if (!rec_wt_open)
		{
			print("replay: nothing loaded\n");
			return TRUE;
		}
		// `end` rather than a number, because the last sample's t is in the file
		// and a config cannot know it -- and the end is the position the whole
		// reader is most worth checking at.
		Watch_Seek((argv(2) == "end") ? rec_wt_t1 : stof(argv(2)));
		Watch_Sample();
		return TRUE;
	}
	if (a == "speed")
	{
		Watch_SetRate(stof(argv(2)));
		print(sprintf("replay: %.2fx\n", rec_wt_rate));
		return TRUE;
	}

	track = 0;
	leg   = 0;
	p     = "";

	if (a == "")
		p = Watch_BestOnLeg(0, 0, "pb");
	/*
	  The word IS the tag, so there is no list here to keep in step -- build 45
	  asks FS_TagFromName whether the argument names one, and a fifth tag needs
	  no edit in this file at all.  `stage`, `bonus` and a bare path fall past it
	  because none of them is a tag word.

	  The branch inside is archived-or-not rather than a second list of names: an
	  archived tag has many files on the leg and wants the fastest, an unstamped
	  one has exactly one and its path is already known.  Same reason SV_RecClose
	  stopped spelling that test out in the same build.
	*/
	/*
	  BUILD 57: A LOBBY TIME HAS NO REPLAY, and saying so is the whole fix.  Its
	  .rec is a header with `samples 0`: the server measured the run and kept
	  nothing, and this client wrote down only what the stats told it.  Left to
	  fall through, Watch_Open reports "holds 0 samples -- nothing to play", which
	  reads as a truncated or corrupt recording rather than as the shape every
	  lobby row has.  The leaderboard already refuses the same click in the same
	  words; this is the console door to it.
	*/
	else if (FS_TagFromName(a) == RT_LOBBY)
	{
		print("^3replay:^7 that time was set on a lobby -- no replay was recorded\n");
		return TRUE;
	}
	else if (FS_TagFromName(a) != RT_NONE)
	{
		p = FS_TagArchived(FS_TagFromName(a)) ? Watch_BestOnLeg(0, 0, a)
		                                      : Watch_LegPath(0, 0, a);
	}
	/*
	  BUILD 57: `replay stage N` IS LEG N -- stage N as the HUD, `!s N` and the
	  scoreboard all count it.  The number used to reach FS_RunDir as a 0-based
	  segment, so `replay stage 2` opened stage 3's folder and stage 1 could not
	  be asked for at all.  `bonus T N` takes the same leg for the bonus's stage N.
	*/
	else if (a == "stage")
	{
		leg = stof(argv(2));
		p   = Watch_BestOnLeg(0, leg, "pb");
	}
	else if (a == "bonus")
	{
		track = stof(argv(2));
		leg   = stof(argv(3));
		p     = Watch_BestOnLeg(track, leg, "pb");
	}
	else
		p = a;

	if (p == "")
	{
		print(sprintf("replay: no recording for %s\n",
		              FS_RunDir(serverkey("map"), track, leg)));
		return TRUE;
	}

	Watch_Open(p);
	return TRUE;
};

void() Watch_RegisterCvars =
{
	registercommand("replay");

	// The path.  Drawn behind walls correctly because Zone_Line queues into the
	// scene before renderscene; see Watch_Path.
	registercvar("hud_watch_path", "1");

	// The part of the run you have not reached yet.  On by default because a
	// line that stops at the camera is much harder to read as a route.
	registercvar("hud_watch_path_ahead", "1");

	/*
	  The ribbon's width, in world units at 512 units of range.  6 is about a
	  finger's width at arm's length on a 1080p window.
	*/
	registercvar("hud_watch_path_width", "6");

	/*
	  Whether that width follows the distance to the camera.

	  1 (default) makes it a fixed ANGULAR size, so the line reads the same
	  thickness the whole way down the map; 0 makes it a fixed WORLD size, which
	  is honest geometry and vanishes into a hairline at range.  Both are
	  computed per VERTEX rather than per segment either way -- that is the thing
	  that stopped it looking like a row of slugs, and it is not optional.
	*/
	registercvar("hud_watch_path_scale", "1");

	/*
	  BUILD 25 -- the tech panel.

	  `replay status` has printed most of this to the console since build 24, and
	  a console line is the wrong instrument for three of the numbers below: they
	  change every frame, and reading them means watching them move against the
	  scrub rather than sampling one.  Off by default because it covers a third of
	  the left of the screen and the ride is what a replay is for.
	*/
	registercvar("hud_watch_info", "0");

	/*
	  BUILD 34 -- how big the playback panel is, on top of hud_scale.

	  hud_scale sizes the whole HUD together, and the demo player is a control
	  rather than a readout: it wants to be reachable with a mouse without
	  dragging every other panel up with it.  Multiplies the two font sizes, the
	  padding, the row gaps, the track and the slider knobs, so the panel keeps
	  its proportions rather than growing a fat border around 1x text.

	  Clamped 0.5..4 in Watch_Chrome: below that the hint row is unreadable and
	  above it the panel is wider than any window it would sit in.

	  CVAR_ARCHIVE like the rest of the hud_watch_* family.  Note the caveat the
	  cl_hud.qc essay makes about that flag on an install with a cfg/default.cfg:
	  the flag is inert there and default.cfg's value is what you get.
	*/
	registercvar("hud_watch_scale", "1", CVAR_ARCHIVE);

	/*
	  BUILD 43 -- the dead air, and skipping it.

	  hud_watch_idle_speed is the horizontal speed under which the run counts as
	  parked, and hud_watch_idle_time is how long it has to stay under it before
	  the bar says so.  Both are read ONCE, in Watch_Scan, because the spans are
	  built at load -- so changing either takes effect on the NEXT `replay`, not
	  on the one already open.  That is the same contract Watch_BuildSeq's
	  thresholds have and it is worth knowing before someone tunes one live and
	  concludes it does nothing.

	  hud_watch_idle_pad brings the pre-start approach into scope.  Off, because
	  the approach is meant to be slow and marking it red says something false
	  about the run; on, if what you want to see is the whole file rather than
	  the timed part of it.

	  hud_watch_skipidle is ON by default and this is a deliberate choice about
	  which way round the surprise should go.  Someone who opens a replay to
	  study a line does not want to sit through forty seconds of a parked player,
	  and the marks on the bar make it obvious what was skipped and that a switch
	  exists -- the chrome carries a clickable toggle beside the speed slider for
	  the same reason.  hud_watch_info shipped defaulting to 0 in build 25, was
	  reported missing in build 26, and the note that came out of it was "A
	  feature nobody can find has not shipped."
	*/
	/*
	  BUILD 43 -- which path drawer, and how wide the screen-space one is.

	  DEFAULT 2 FROM BUILD 45.  It shipped at 1 for two builds because mode 2
	  computed correct geometry and did not reach the screen, and a default that
	  draws nothing is worse than the ribbon it replaced.  The cause was the
	  winding, the fix is one sign, and the essay at Watch_PathMode says why the
	  three builds of measurement either side of it all read correct.

	  Mode 1 is not deprecated and is not going away.  It is the depth-tested
	  one: a path behind a wall is hidden by the wall in mode 1 and drawn over it
	  in mode 2, and that is a real preference and not a defect in either.

	  hud_watch_path_px is a SEPARATE cvar from hud_watch_path_width rather than
	  a reinterpretation of it, because the two are not the same quantity: the
	  ribbon's 6 is world units at a 512-unit reference distance, and this one is
	  pixels.  Sharing the name would have silently made every existing config a
	  six-pixel line, and 3 is what a crisp one wants.
	*/
	registercvar("hud_watch_path_mode", "2", CVAR_ARCHIVE);
	registercvar("hud_watch_path_px", "3", CVAR_ARCHIVE);
	registercvar("hud_watch_path_probe", "0");

	registercvar("hud_watch_idle_speed", "20", CVAR_ARCHIVE);
	registercvar("hud_watch_idle_time", "0.5", CVAR_ARCHIVE);
	registercvar("hud_watch_idle_pad", "0", CVAR_ARCHIVE);
	registercvar("hud_watch_skipidle", "1", CVAR_ARCHIVE);
};
